"""The studio: a time grid, the players, the mix, and the master.

A `Session` has a tempo and a number of bars. The music code tells each
player what to play, in bars and beats. Each player has its own track. The
function `mixdown` gives each track its effects, makes the sum, and makes
the master.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field

import numpy as np
from scipy import signal

from . import sound, tapefx
from .audio import dsp, effects, loudness, synth
from .audio.synth import LineNote

RATE = dsp.RATE
TARGET_LUFS = -14.0
VARIANTS = 3  # the same note has this number of different renders


@dataclass
class Session:
    """The time grid and the tracks of one render."""

    bpm: float
    bars: int
    beats: int = 4  # quarter notes in a bar
    swing: float = 0.12  # how late each second sixteenth note is (share of a sixteenth)
    tail: float = 6.0  # seconds after the last bar
    seed: int = 1
    tracks: dict[str, np.ndarray] = field(default_factory=dict)
    kicks: list[float] = field(default_factory=list)
    cache: dict[tuple, np.ndarray] = field(default_factory=dict, repr=False)

    @property
    def beat(self) -> float:
        return 60.0 / self.bpm

    @property
    def total(self) -> int:
        return int((self.bars * self.beats * self.beat + self.tail) * RATE)

    def time(self, bar: float, beat: float = 0.0, swung: bool = True) -> float:
        """Return the time in seconds of a place: the bar (0 = first) and the beat (0 = first)."""
        position = bar * self.beats + beat
        if swung:
            sixteenth = position * 4.0
            step = int(np.floor(sixteenth + 1e-9))
            if step % 2 == 1 and abs(sixteenth - step) < 1e-6:
                position += self.swing * 0.25
        return position * self.beat

    def random(self, *keys: object) -> np.random.Generator:
        return np.random.default_rng(zlib.crc32(repr((self.seed, *keys)).encode()))

    def track(self, name: str) -> np.ndarray:
        if name not in self.tracks:
            self.tracks[name] = np.zeros((self.total, 2))
        return self.tracks[name]

    def add(self, name: str, audio: np.ndarray, seconds: float, gain: float = 1.0) -> None:
        """Put a sound on a track at a time."""
        target = self.track(name)
        audio = effects.stereo(np.asarray(audio, dtype=np.float64))
        start = int(round(seconds * RATE))
        if start < 0:
            audio, start = audio[-start:], 0
        stop = min(len(target), start + len(audio))
        if stop > start:
            target[start:stop] += audio[: stop - start] * gain

    # ------------------------------------------------------------------ players

    def chord(
        self, name: str, patch, bar: float, beat: float, length: float, notes, level: float,
        strum: float = 0.0, swung: bool = False,
    ) -> None:  # fmt: skip
        """Play some notes together with a synthesizer patch. `length` is in beats."""
        start = self.time(bar, beat, swung)
        variant = int(bar * self.beats + beat * 4) % VARIANTS
        for number, midi in enumerate(notes):
            key = (patch.name, midi, round(length * self.beat, 3), round(level * 20), variant)
            if key not in self.cache:
                self.cache[key] = synth.render_note(
                    patch, midi, length * self.beat, round(level * 20) / 20.0, seed=key
                )
            self.add(name, self.cache[key], start + number * strum)

    def line(self, name: str, patch, notes, pan: float = 0.0) -> None:
        """Play a line of one voice. Each note: (bar, beat, length in beats, MIDI, level, legato)."""
        found = []
        for bar, beat, length, midi, level, legato in notes:
            start = self.time(bar, beat, swung=False)
            found.append(LineNote(start, length * self.beat, midi, level, legato=legato))
        if not found:
            return
        first = found[0].start
        moved = [
            LineNote(n.start - first, n.seconds, n.midi, n.level, legato=n.legato) for n in found
        ]
        audio = synth.render_line(patch, moved, seed=(name, len(moved), round(first, 3)))
        if pan:
            audio = audio * np.array([1.0 - max(pan, 0.0), 1.0 + min(pan, 0.0)])
        self.add(name, audio, first)

    def keys(
        self, name: str, bar: float, beat: float, length: float, notes, level: float,
        strum: float = 0.012,
    ) -> None:  # fmt: skip
        """Play a chord of the electric piano. The notes come one after the other, very fast."""
        random = self.random(name, bar, beat)
        start = self.time(bar, beat)
        for number, midi in enumerate(notes):
            touch = float(np.clip(level + random.normal(0.0, 0.04), 0.05, 1.0))
            audio = sound.rhodes(midi, length * self.beat, touch)
            late = number * strum + abs(random.normal(0.0, 0.004))
            self.add(name, effects.stereo(audio), start + late)

    def bell(self, name: str, bar: float, beat: float, midi: float, level: float) -> None:
        audio = synth.render_fm(sound.BELL, midi, 0.4, level, seed=(bar, beat, midi))
        self.add(name, audio, self.time(bar, beat))

    def hit(self, drum: str, bar: float, beat: float, level: float, late: float = 0.0) -> None:
        """Play one stroke of the drum machine. Each stroke is a little different."""
        random = self.random(drum, bar, beat)
        level = float(np.clip(level * (1.0 + random.normal(0.0, 0.06)), 0.02, 1.0))
        moment = self.time(bar, beat) + late + random.normal(0.0, 0.0035)
        audio = sound.drum(drum, level, int(random.integers(0, 1 << 30)))
        track = {"kick": "kick", "snare": "snare", "rim": "snare", "clap": "snare"}.get(
            drum, "hats"
        )
        if track == "hats":
            side = 0.25 if drum == "hat" else 0.35
            audio = effects.pan(audio, side)
        self.add(track, audio, moment)
        if drum == "kick":
            self.kicks.append(moment)


# ----------------------------------------------------------------------------
# The mix
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Strip:
    """The settings of one track in the mix."""

    gain_db: float = 0.0
    low_cut: float = 30.0
    high_cut: float = 16000.0
    drive_db: float = 0.0  # saturation
    chorus: int = 0  # 0 = none, 1 = one rate, 2 = two rates
    width: float = 1.0
    reverb: float = 0.0  # share of the track that goes to the reverb
    echo: float = 0.0  # share of the track that goes to the echo
    duck_db: float = 0.0  # how far each kick drum pushes the track down
    wobble: float = 1.0  # how much of the tape wow the track gets
    tremolo: bool = False


STRIPS = {
    "pad": Strip(-4.0, 150.0, 9500.0, 2.0, chorus=2, width=1.2, reverb=0.3, duck_db=2.5),
    "keys": Strip(-12.5, 260.0, 7500.0, 4.0, chorus=1, reverb=0.22, duck_db=1.5, tremolo=True),
    "lead": Strip(-5.0, 220.0, 8500.0, 3.0, chorus=1, reverb=0.3, echo=0.3),
    "pluck": Strip(-9.0, 280.0, 8500.0, 0.0, chorus=1, width=1.3, reverb=0.3, echo=0.35),
    "bell": Strip(-14.0, 400.0, 11000.0, 0.0, width=1.3, reverb=0.55, echo=0.3),
    "bass": Strip(-12.0, 28.0, 2200.0, 5.0, width=0.0, duck_db=2.0, wobble=0.3),
    "kick": Strip(-8.0, 28.0, 7000.0, 4.0, width=0.0, wobble=0.0),
    "snare": Strip(-6.5, 130.0, 10000.0, 5.0, width=0.6, reverb=0.14, wobble=0.0),
    "hats": Strip(-12.5, 600.0, 12000.0, 3.0, reverb=0.06, wobble=0.0),
    "air": Strip(0.0, 60.0, 12000.0, 0.0, wobble=0.0),
}


def _tone(audio: np.ndarray, strip: Strip) -> np.ndarray:
    out = signal.sosfilt(dsp.highpass(strip.low_cut, 2), audio, axis=0)
    return signal.sosfilt(dsp.lowpass(strip.high_cut, 2), out, axis=0)


def mixdown(
    session: Session, automation: dict[str, np.ndarray] | None = None
) -> tuple[np.ndarray, dict[str, float]]:
    """Make the master from the tracks of a session. Return the sound and some numbers.

    `automation` gives a gain curve (one value for each sample) for some tracks,
    or for all tracks under the name "master".
    """
    automation = automation or {}
    total = session.total
    cents = tapefx.speed_curve(total, seed=session.seed)
    duck = None
    mix = np.zeros((total, 2))
    wet = np.zeros((total, 2))
    echo = np.zeros((total, 2))
    drums = np.zeros((total, 2))
    for name, audio in session.tracks.items():
        strip = STRIPS[name]
        out = audio
        if strip.tremolo:
            mono = out.mean(axis=1)
            out = sound.tremolo(mono) * 1.4
        if strip.chorus:
            out = sound.chorus(out, deep=strip.chorus == 2)
        if strip.drive_db:
            out = effects.saturate(out, strip.drive_db) * dsp.db(-0.5 * strip.drive_db)
        out = _tone(out, strip)
        out = effects.width(out, strip.width) if strip.width != 1.0 else out
        if strip.wobble:
            out = tapefx.warp(out, cents * strip.wobble)
        if strip.duck_db and session.kicks:
            if duck is None:
                duck = effects.duck(total, np.array(session.kicks), 1.0, 0.03, 0.22)
            out = out * (duck**strip.duck_db)[:, None]
        if name in automation:
            out = out * automation[name][:total, None]
        out = out * dsp.db(strip.gain_db)
        wet += out * strip.reverb
        echo += out * strip.echo
        if name in ("kick", "snare", "hats"):
            drums += out
        else:
            mix += out
    # The drums together: a compressor beside the dry sound, and the sound of a small room.
    if drums.any():
        hard = effects.compress(drums, -24.0, 6.0, 0.004, 0.09, makeup_db=8.0)
        drums = drums + 0.35 * hard
        small = effects.reverb(drums, effects.room(0.35, 0.3, 0.004, 0.6, seed=11), tail=False)
        drums = drums + 0.1 * small
        drums = effects.crush(drums, 12.0, 2) * 0.35 + drums * 0.65
        drums = signal.sosfilt(dsp.lowpass(11500.0, 2), drums, axis=0)
        mix += drums
    # The echo: three sixteenth notes, between left and right.
    if echo.any():
        repeats = effects.delay(echo, 0.75 * session.beat, 0.42, 0.55)[:total]
        mix += repeats * 0.7
        wet += repeats * 0.25
    # The reverb: a plate with a dark, long sound.
    if wet.any():
        plate = effects.room(2.8, 0.3, 0.035, 1.0, seed=5)
        space = effects.reverb(wet, plate, tail=False)
        space = signal.sosfilt(dsp.highpass(220.0, 2), space, axis=0)
        mix += space * 0.2
    return master(mix, automation.get("master"))


def master(mix: np.ndarray, gain: np.ndarray | None = None) -> tuple[np.ndarray, dict[str, float]]:
    """Make the master: tone, a slow compressor, tape saturation, loudness, and a limiter."""
    out = signal.sosfilt(dsp.highpass(27.0, 2), mix, axis=0)
    out = effects.equalize(
        out,
        dsp.peaking(280.0, -3.0, 0.8),
        dsp.peaking(1100.0, 1.5, 0.6),
        dsp.shelf(10000.0, -1.0, high=True),
    )
    if gain is not None:
        out = out * gain[: len(out), None]
    peak = float(np.abs(out).max()) or 1.0
    out = out / peak * dsp.db(-6.0)
    out = effects.compress(out, -16.0, 2.0, 0.03, 0.25, knee_db=8.0, makeup_db=2.0)
    out = effects.saturate(out, 2.5) * dsp.db(-1.0)
    measured = loudness.integrated(loudness.block_power(out.astype(np.float32)))
    out = out * dsp.db(TARGET_LUFS - measured)
    out = effects.limit(effects.clip(out, -0.3), -1.0)
    power = loudness.block_power(out.astype(np.float32))
    spread, _ = loudness.loudness_range(loudness.short_term(power))
    numbers = {
        "lufs": float(loudness.integrated(power)),
        "range_lu": float(spread),
        "peak_db": float(dsp.to_db(np.abs(out).max())),
        "seconds": len(out) / RATE,
    }
    numbers.update(octave_levels(out))
    return out.astype(np.float32), numbers


def octave_levels(audio: np.ndarray) -> dict[str, float]:
    """Return the level of each octave band in dB, in relation to the band of 1 kHz."""
    mono = audio.mean(axis=1)
    spectrum = np.abs(np.fft.rfft(mono)) ** 2
    frequencies = np.fft.rfftfreq(len(mono), 1.0 / RATE)
    centres = (63, 125, 250, 500, 1000, 2000, 4000, 8000)
    power = {}
    for centre in centres:
        band = (frequencies >= centre / np.sqrt(2)) & (frequencies < centre * np.sqrt(2))
        power[centre] = 10.0 * np.log10(spectrum[band].sum() + 1e-20)
    return {f"band_{centre}": float(power[centre] - power[1000]) for centre in centres}
