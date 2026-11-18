"""Get reference recordings and measure them.

Use: uv run python tools/reference.py fetch      (needs `uvx yt-dlp`)
     uv run python tools/reference.py measure [MORE AUDIO FILES]

The recordings go to `.cache/reference` (not in the repository: they are the
property of their makers; this project only measures them). The table
`research/reference.csv` has one row of numbers for each recording.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import signal

from loworbit.audio import loudness
from loworbit.audio.dsp import RATE

FOLDER = Path(".cache/reference")
TABLE = Path("research/reference.csv")
PAGE = "https://soundcloud.com/jakechudnow/"
TRACKS = [
    "olive", "shona", "going-down", "pressed-pennies", "hydrogen", "columbia-jake-chudnow",
    "sunbathe", "shallow-anne-1", "banana", "flan", "turqoise", "hanami", "darwinism",
    "pines-and-pavement",
]  # fmt: skip
CENTRES = (31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
MAJOR = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
MINOR = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)
NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")


def fetch() -> None:
    FOLDER.mkdir(parents=True, exist_ok=True)
    for track in TRACKS:
        if list(FOLDER.glob(f"{track}.*")):
            continue
        subprocess.run(
            ["uvx", "yt-dlp", "-q", "--no-warnings", "-f", "bestaudio", "-o",
             str(FOLDER / f"{track}.%(ext)s"), PAGE + track],
            check=False,
        )  # fmt: skip
    for path in sorted(FOLDER.iterdir()):
        print(f"{path.stat().st_size / 1e6:6.1f} MB  {path.name}")


def read(path: Path) -> np.ndarray:
    data = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar",
         str(RATE), "-"],
        capture_output=True, check=True,
    ).stdout  # fmt: skip
    return np.frombuffer(data, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def tempo(mono: np.ndarray) -> tuple[float, float]:
    """Return the tempo (70 to 140 beats in a minute) and how clear it is (0 to 1)."""
    hop = 256
    _, _, spectrum = signal.stft(mono, RATE, nperseg=1024, noverlap=1024 - hop)
    level = np.log1p(40.0 * np.abs(spectrum))
    flux = np.clip(np.diff(level, axis=1), 0.0, None).sum(axis=0)
    flux = flux - flux.mean()
    size = 1 << int(np.ceil(np.log2(2 * len(flux))))
    spectrum_flux = np.fft.rfft(flux, size)
    relation = np.fft.irfft(spectrum_flux * np.conj(spectrum_flux))[: len(flux)]
    relation = relation / max(relation[0], 1e-12)
    frames = RATE / hop
    best, strength = 0.0, -1.0
    for value in np.arange(70.0, 140.0, 0.1):
        lag = 60.0 / value * frames
        # A beat, two beats, and four beats must all agree.
        score = sum(
            np.interp(lag * factor, np.arange(len(relation)), relation) for factor in (1, 2, 4)
        )
        if score > strength:
            best, strength = float(value), float(score)
    return best, strength / 3.0


def key(mono: np.ndarray) -> str:
    _, _, spectrum = signal.stft(mono, RATE, nperseg=16384, noverlap=8192)
    power = (np.abs(spectrum) ** 2).mean(axis=1)
    frequencies = np.fft.rfftfreq(16384, 1.0 / RATE)
    use = (frequencies > 55.0) & (frequencies < 2000.0)
    pitch = np.round(69 + 12 * np.log2(frequencies[use] / 440.0)).astype(int) % 12
    chroma = np.bincount(pitch, weights=np.sqrt(power[use]), minlength=12)
    best, found = -2.0, ""
    for tonic in range(12):
        for profile, mode in ((MAJOR, "major"), (MINOR, "minor")):
            score = np.corrcoef(np.roll(profile, tonic), chroma)[0, 1]
            if score > best:
                best, found = score, f"{NAMES[tonic]} {mode}"
    return found


def measure(path: Path) -> dict[str, object]:
    audio = read(path)
    mono, side = audio.mean(axis=1), (audio[:, 0] - audio[:, 1]) / 2.0
    power = loudness.block_power(audio)
    lufs = loudness.integrated(power)
    span, _ = loudness.loudness_range(loudness.short_term(power))
    peak = 20 * np.log10(np.abs(audio).max() + 1e-12)
    rms = 10 * np.log10((audio**2).mean() + 1e-20)
    frequencies, density = signal.welch(mono, RATE, nperseg=32768)
    _, density_side = signal.welch(side, RATE, nperseg=32768)
    bands = {}
    for centre in CENTRES:
        band = (frequencies >= centre / np.sqrt(2)) & (frequencies < centre * np.sqrt(2))
        bands[centre] = 10 * np.log10(density[band].sum() + 1e-30)
    total = np.cumsum(density)
    low = frequencies < 150.0
    bpm, clear = tempo(mono)
    row: dict[str, object] = {
        "name": path.stem[:28],
        "seconds": round(len(audio) / RATE, 1),
        "bpm": round(bpm, 1),
        "beat_clear": round(clear, 2),
        "key": key(mono),
        "lufs": round(lufs, 1),
        "range_lu": round(float(span), 1),
        "peak_db": round(float(peak), 1),
        "crest_db": round(float(peak - rms), 1),
    }
    for centre in CENTRES:
        row[f"b{centre}"] = round(float(bands[centre] - bands[1000]), 1)
    row["roll95_hz"] = int(frequencies[np.searchsorted(total, 0.95 * total[-1])])
    row["roll99_hz"] = int(frequencies[np.searchsorted(total, 0.99 * total[-1])])
    row["side_db"] = round(float(10 * np.log10(density_side.sum() / density.sum() + 1e-12)), 1)
    row["side_low_db"] = round(
        float(10 * np.log10(density_side[low].sum() / density[low].sum() + 1e-12)), 1
    )
    return row


def main() -> None:
    if sys.argv[1:2] == ["fetch"]:
        fetch()
        return
    paths = sorted(FOLDER.iterdir()) + [Path(name) for name in sys.argv[2:]]
    rows = []
    for path in paths:
        try:
            rows.append(measure(path))
        except (subprocess.CalledProcessError, ValueError) as problem:
            print("no measurement:", path.name, problem)
            continue
        print("  ".join(f"{value}" for value in rows[-1].values()), flush=True)
    TABLE.parent.mkdir(exist_ok=True)
    with TABLE.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("  ".join(rows[0]))


if __name__ == "__main__":
    main()
