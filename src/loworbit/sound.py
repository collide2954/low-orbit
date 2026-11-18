"""The instruments of Low Orbit.

Each function returns sound with two channels at the sample rate of the
project. The synthesizer patches are models of the instruments that the
style study names: a polyphonic synthesizer of about 1982 with one
oscillator, a sub oscillator, and a chorus (the pad, the pluck, the bass),
a lead with a slow slide and an unsteady pitch, an electric piano (samples
of a 1977 Rhodes), bells, and a drum machine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import soundfile
import soxr
from scipy import signal

from .audio import drumsynth, dsp, effects
from .audio.synth import Envelope, FMPatch, Operators, Osc, Patch

RATE = dsp.RATE
SAMPLES = Path(".cache/samples")

# ----------------------------------------------------------------------------
# Synthesizer patches
# ----------------------------------------------------------------------------

# The pad: a saw wave and a pulse wave with a slow change of its width, a sub
# oscillator one octave lower, a low-pass filter that opens slowly, and a chorus.
PAD = Patch(
    "pad",
    (
        Osc("saw", level=0.8, voices=2, spread=9.0),
        Osc("pulse", level=0.55, width=0.5, pwm=0.32),
        Osc("pulse", semitones=-12.0, level=0.35, width=0.5),
    ),
    noise=0.004,
    cutoff=1350.0,
    tracking=0.4,
    resonance=0.12,
    filter_envelope=Envelope(1.2, 2.5, 0.75, 1.6),
    envelope_octaves=1.3,
    velocity_octaves=0.8,
    amplitude=Envelope(0.55, 1.5, 0.85, 1.8),
    stereo=0.7,
    drift_cents=7.0,
)

# The lead: one voice, a slide between its notes, a vibrato that comes late,
# and a pitch that is never exactly steady.
LEAD = Patch(
    "lead",
    (
        Osc("saw", level=0.7, voices=2, spread=14.0),
        Osc("pulse", level=0.5, width=0.34, pwm=0.1, cents=-6.0),
        Osc("triangle", semitones=12.0, level=0.18),
    ),
    cutoff=2100.0,
    tracking=0.6,
    resonance=0.28,
    drive=1.4,
    filter_envelope=Envelope(0.02, 0.9, 0.45, 0.4),
    envelope_octaves=1.4,
    amplitude=Envelope(0.02, 0.6, 0.8, 0.35),
    vibrato_hz=5.1,
    vibrato_cents=16.0,
    vibrato_delay=0.32,
    glide=0.09,
    stereo=0.35,
    drift_cents=11.0,
)

# The bass: a sine-like tone with a little edge, for the root of each chord.
BASS = Patch(
    "bass",
    (Osc("triangle", level=1.0), Osc("saw", level=0.22), Osc("sine", semitones=-12.0, level=0.5)),
    cutoff=260.0,
    tracking=0.3,
    resonance=0.1,
    drive=1.6,
    filter_envelope=Envelope(0.004, 0.35, 0.3, 0.2),
    envelope_octaves=1.6,
    amplitude=Envelope(0.006, 0.5, 0.75, 0.16),
    glide=0.05,
    stereo=0.0,
    drift_cents=2.0,
)

# The pluck: a short note for the fast figures.
PLUCK = Patch(
    "pluck",
    (Osc("pulse", level=0.8, width=0.42, pwm=0.12), Osc("saw", level=0.4, cents=7.0)),
    cutoff=800.0,
    tracking=0.55,
    resonance=0.3,
    filter_envelope=Envelope(0.002, 0.28, 0.0, 0.25),
    envelope_octaves=3.0,
    velocity_octaves=1.4,
    amplitude=Envelope(0.002, 0.5, 0.0, 0.3),
    stereo=0.2,
    drift_cents=5.0,
)

# The bell: two pairs of sine waves (a soft metal sound).
BELL = FMPatch(
    "bell",
    (
        Operators(ratio=3.5, index=1.6, index_decay=0.5, index_sustain=0.05,
                  amplitude=Envelope(0.002, 2.6, 0.0, 1.2), pan=0.35),
        Operators(ratio=7.0, index=0.7, index_decay=0.2, index_sustain=0.0, level=0.4,
                  amplitude=Envelope(0.002, 1.2, 0.0, 0.8), cents=6.0, pan=0.65),
    ),
    velocity_index=1.0,
)  # fmt: skip


def chorus(sound: np.ndarray, deep: bool = False) -> np.ndarray:
    """The chorus of the pad synthesizer: two slow rates, or the two together."""
    out = effects.chorus(sound, rate_hz=0.51, depth_ms=2.6, mix=0.55, voices=2)
    if deep:
        out = effects.chorus(out, rate_hz=0.83, depth_ms=1.8, mix=0.35, voices=2)
    return out


# ----------------------------------------------------------------------------
# The electric piano
# ----------------------------------------------------------------------------

_RHODES_NAME = re.compile(r"A_(\d{3})__[A-G]#?\d_(\d)\.flac")


@lru_cache(maxsize=1)
def _rhodes_files() -> dict[int, dict[int, Path]]:
    folder = SAMPLES / "jrhodes3d" / "jRhodes3d-mono"
    found: dict[int, dict[int, Path]] = {}
    for path in sorted(folder.glob("A_*.flac")):
        match = _RHODES_NAME.fullmatch(path.name)
        if match:
            found.setdefault(int(match.group(1)), {})[int(match.group(2))] = path
    if not found:
        raise FileNotFoundError(f"no samples of the electric piano in {folder}")
    return found


@lru_cache(maxsize=256)
def _rhodes_sample(key: int, layer: int) -> np.ndarray:
    data, rate = soundfile.read(str(_rhodes_files()[key][layer]), dtype="float64")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return soxr.resample(data, rate, RATE, quality="HQ") if rate != RATE else data


def rhodes(midi: float, seconds: float, level: float) -> np.ndarray:
    """Return one note of the electric piano (one channel).

    The nearest recorded key plays at a different speed. A loud note uses a
    louder recording: it has more of the hard sound of the hammer.
    """
    files = _rhodes_files()
    key = min(files, key=lambda number: abs(number - midi))
    layers = sorted(files[key])
    layer = layers[min(len(layers) - 1, int(np.clip(level, 0.0, 0.999) * len(layers)))]
    sample = _rhodes_sample(key, layer)
    ratio = 2.0 ** ((midi - key) / 12.0)
    wanted = int((seconds + 0.6) * RATE)
    source = sample[: int(wanted * ratio) + 8]
    positions = np.arange(min(wanted, int(len(source) / ratio) - 1)) * ratio
    note = np.interp(positions, np.arange(len(source)), source)
    time = np.arange(len(note)) / RATE
    release = np.where(time < seconds, 1.0, np.exp(-(time - seconds) / 0.09))
    gain = 10.0 ** (-18.0 * (1.0 - level) / 20.0)
    return note * release * gain


def tremolo(sound: np.ndarray, rate_hz: float = 4.6, depth: float = 0.35) -> np.ndarray:
    """Move a sound with one channel between left and right (the vibrato of a suitcase piano)."""
    time = np.arange(len(sound)) / RATE
    wave = np.sin(2 * np.pi * rate_hz * time)
    left = sound * (1.0 + depth * wave) * 0.7
    right = sound * (1.0 - depth * wave) * 0.7
    return np.stack([left, right], axis=1)


# ----------------------------------------------------------------------------
# The drum machine
# ----------------------------------------------------------------------------


def drum(name: str, level: float, seed: int) -> np.ndarray:
    """Return one stroke of the drum machine (one channel or two channels)."""
    if name == "kick":
        return drumsynth.kick(level, seed, pitch=51.0, sweep=110.0, decay=0.26, click=0.3)
    if name == "snare":
        return drumsynth.snare(level, seed, pitch=205.0, decay=0.13, brightness=0.7)
    if name == "rim":
        return drumsynth.rim(level, seed)
    if name == "clap":
        return drumsynth.clap(level, seed)
    if name == "hat":
        return drumsynth.hat(level, seed, decay=0.03, tone=0.92)
    if name == "open":
        return drumsynth.hat(level, seed, decay=0.22, tone=0.92)
    raise ValueError(f"no drum with the name {name}")


# ----------------------------------------------------------------------------
# The recorded drums (DRSKit, DrumGizmo team, CC BY 4.0)
# ----------------------------------------------------------------------------

# The channels of each file of the kit, in their sequence.
_KIT_CHANNELS = (
    "AmbL", "AmbR", "Hihat", "Kdrum_back", "Kdrum_front", "OHL", "OHR", "Ride",
    "Snare_bottom", "Snare_top", "Tom1", "Tom2", "Tom3",
)  # fmt: skip


@dataclass(frozen=True)
class KitDrum:
    """How one drum of the machine gets a recorded stroke."""

    folder: str
    close: tuple[str, ...]  # the microphones near the drum
    seconds: float  # the length that the work uses
    low_cut: float  # the machine gives the range below this frequency
    overhead: float = 0.45  # the level of the pair above the kit
    room: float = 0.3  # the level of the pair in the room


KIT = {
    "kick": KitDrum("Kdrum_with_contact", ("Kdrum_front", "Kdrum_back"), 0.5, 95.0, 0.3, 0.25),
    "snare": KitDrum("Snare", ("Snare_top",), 0.8, 150.0),
    "rim": KitDrum("Snare_rim", ("Snare_top",), 0.5, 200.0),
    "hat": KitDrum("Hihat_closed", ("Hihat",), 0.3, 500.0, 0.5, 0.15),
    "open": KitDrum("Hihat_semi_open", ("Hihat",), 0.55, 500.0, 0.5, 0.15),
}


@lru_cache(maxsize=8)
def _kit_strokes(name: str) -> tuple[np.ndarray, ...]:
    """Return all recorded strokes of one drum, from the softest to the loudest.

    Each stroke has two channels, starts 1 ms before its attack, and has a
    largest value of 1.
    """
    spec = KIT[name]
    folder = SAMPLES / "drskit" / "DRSKit" / spec.folder
    found = re.findall(
        r'<sample name="[^"]*" power="([0-9.eE+-]+)">\s*<audiofile[^>]*file="([^"]+)"',
        (folder / f"{spec.folder}.xml").read_text(),
    )
    if not found:
        raise FileNotFoundError(f"no recorded strokes in {folder}")
    column = {channel: number for number, channel in enumerate(_KIT_CHANNELS)}
    strokes = []
    for _power, file in sorted(found, key=lambda item: float(item[0])):
        data, rate = soundfile.read(str(folder / file), dtype="float64")
        close = sum(data[:, column[channel]] for channel in spec.close) / len(spec.close)
        left = close * np.sqrt(0.5) + spec.overhead * data[:, column["OHL"]]
        right = close * np.sqrt(0.5) + spec.overhead * data[:, column["OHR"]]
        left = left + spec.room * data[:, column["AmbL"]]
        right = right + spec.room * data[:, column["AmbR"]]
        attack = int(np.argmax(np.abs(close) > 0.08 * np.abs(close).max()))
        first = max(0, attack - int(0.001 * rate))
        stroke = np.stack([left, right], axis=1)[first : first + int(spec.seconds * rate)]
        if rate != RATE:
            stroke = soxr.resample(stroke, rate, RATE, quality="HQ")
        stroke = signal.sosfilt(dsp.highpass(spec.low_cut, 2), stroke, axis=0)
        fade = min(len(stroke), int(0.08 * RATE))
        stroke[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
        strokes.append(stroke / max(float(np.abs(stroke).max()), 1e-9))
    return tuple(strokes)


def kit_available() -> bool:
    return (SAMPLES / "drskit" / "DRSKit" / "Snare" / "Snare.xml").exists()


def kit(name: str, level: float, random: np.random.Generator) -> np.ndarray | None:
    """Return one recorded stroke of a drum (two channels), or None if the kit has no such drum.

    A louder stroke uses a recording of a harder stroke. Two strokes of the
    same loudness do not use the same recording.
    """
    if name not in KIT:
        return None
    strokes = _kit_strokes(name)
    place = level * (len(strokes) - 1) + random.integers(-2, 3)
    return strokes[int(np.clip(place, 0, len(strokes) - 1))] * level
