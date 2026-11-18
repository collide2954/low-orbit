"""The synthesizers: patches made from oscillators, filters, and envelopes.

A patch describes one sound. The functions `render_note` and `render_line`
make the sound of a patch for one note, or for a line of notes that one
voice plays with slides between the notes. The result has two channels.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field

import numpy as np

from . import dsp, kernels

RATE = float(dsp.RATE)


@dataclass(frozen=True)
class Envelope:
    """Attack, decay, sustain level, and release (times in seconds)."""

    attack: float = 0.005
    decay: float = 0.2
    sustain: float = 0.7
    release: float = 0.15

    def curve(self, held: float, total: int) -> np.ndarray:
        """Return the envelope for a note held for `held` seconds, as `total` samples."""
        time = np.arange(total) / RATE
        attack = max(self.attack, 1e-4)
        rise = np.minimum(time / attack, 1.0)
        fall = self.sustain + (1.0 - self.sustain) * np.exp(
            -np.maximum(time - attack, 0.0) / max(self.decay / 4.0, 1e-4)
        )
        level = np.where(time < attack, rise, fall)
        # The note stops at `held`: the level at that moment goes to zero.
        at_stop = float(np.interp(held, time, level)) if total else 0.0
        after = np.maximum(time - held, 0.0)
        tail = at_stop * np.exp(-after / max(self.release / 4.0, 1e-4))
        return np.where(time < held, level, tail)


@dataclass(frozen=True)
class Osc:
    """One oscillator of a patch."""

    wave: str = "saw"  # saw, pulse, sine, triangle
    semitones: float = 0.0
    cents: float = 0.0
    level: float = 1.0
    width: float = 0.5  # pulse: share of the high part
    pwm: float = 0.0  # pulse: depth of the slow change of the width
    voices: int = 1  # number of detuned copies
    spread: float = 0.0  # detune between the lowest and the highest copy, in cents


@dataclass(frozen=True)
class Patch:
    """A subtractive synthesizer sound."""

    name: str
    oscillators: tuple[Osc, ...]
    noise: float = 0.0
    filter: str = "ladder"  # ladder, lowpass, bandpass, highpass, none
    cutoff: float = 2000.0  # hertz, for the note C4 at mezzo forte
    tracking: float = 0.5  # how much the cutoff follows the pitch (0 to 1)
    resonance: float = 0.2
    drive: float = 1.0
    filter_envelope: Envelope = field(default_factory=Envelope)
    envelope_octaves: float = 2.0  # how far the filter envelope opens the filter
    velocity_octaves: float = 1.0  # a loud note is brighter by this much
    amplitude: Envelope = field(default_factory=Envelope)
    vibrato_hz: float = 5.5
    vibrato_cents: float = 0.0
    vibrato_delay: float = 0.25  # seconds before the vibrato starts
    glide: float = 0.0  # seconds for a slide between two notes of a line
    stereo: float = 0.5  # how far the copies of the oscillators are to the sides
    range_db: float = 24.0  # softest note relative to the loudest note
    gain_db: float = 0.0
    drift_cents: float = 3.0  # slow random change of the pitch, as on an analog instrument


def hertz(midi: float | np.ndarray) -> float | np.ndarray:
    return 440.0 * 2.0 ** ((np.asarray(midi) - 69.0) / 12.0)


def _random(*keys: object) -> np.random.Generator:
    return np.random.default_rng(zlib.crc32(repr(keys).encode()))


def _oscillate(
    patch: Patch, pitch: np.ndarray, random: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Return the left and the right signal of all oscillators. `pitch` is in MIDI numbers."""
    total = len(pitch)
    left, right = np.zeros(total), np.zeros(total)
    time = np.arange(total) / RATE
    for osc in patch.oscillators:
        for voice in range(osc.voices):
            position = 0.0 if osc.voices == 1 else voice / (osc.voices - 1) - 0.5
            detune = osc.cents + position * osc.spread
            if osc.voices > 1:
                detune += random.normal(0.0, 0.03 * max(osc.spread, 1.0))
            frequency = hertz(pitch + osc.semitones + detune / 100.0)
            phase = float(random.uniform(0.0, 1.0))
            if osc.wave == "saw":
                wave = kernels.saw(frequency, RATE, phase)
            elif osc.wave == "pulse":
                rate_hz = 0.3 + 0.5 * random.uniform()
                width = osc.width + osc.pwm * np.sin(2 * np.pi * rate_hz * time + 6.28 * phase)
                wave = kernels.pulse(frequency, width, RATE, phase)
            elif osc.wave == "triangle":
                wave = kernels.triangle(frequency, RATE, phase)
            else:
                wave = kernels.sine(frequency, RATE, phase)
            gain = osc.level / np.sqrt(osc.voices)
            pan = 0.5 + position * patch.stereo * (1.0 if osc.voices > 1 else 0.0)
            left += wave * gain * np.cos(pan * np.pi / 2)
            right += wave * gain * np.sin(pan * np.pi / 2)
    if patch.noise:
        noise = random.normal(0.0, patch.noise, total)
        left += noise
        right += noise
    return left * np.sqrt(0.5) * 1.41, right * np.sqrt(0.5) * 1.41


def _filter(patch: Patch, signal: np.ndarray, cutoff: np.ndarray) -> np.ndarray:
    if patch.filter == "none":
        return signal
    if patch.filter == "ladder":
        return kernels.ladder(signal, cutoff, patch.resonance, patch.drive, RATE)
    mode = {"lowpass": 0, "bandpass": 1, "highpass": 2}[patch.filter]
    quality = np.full(len(signal), 0.5 + 9.5 * patch.resonance)
    return kernels.state_variable(np.tanh(patch.drive * signal), cutoff, quality, RATE, mode)


def _voice(
    patch: Patch,
    pitch: np.ndarray,
    amplitude: np.ndarray,
    filter_level: np.ndarray,
    level: np.ndarray,
    random: np.random.Generator,
) -> np.ndarray:
    """Make the sound of one voice from its curves. Return two channels."""
    total = len(pitch)
    if patch.drift_cents:
        steps = random.normal(0.0, 1.0, total // 2400 + 2)
        slow = np.interp(np.arange(total) / 2400.0, np.arange(len(steps)), np.cumsum(steps) * 0.3)
        pitch = pitch + (slow - slow.mean()) * patch.drift_cents / 100.0
    left, right = _oscillate(patch, pitch, random)
    key = (pitch - 60.0) / 12.0 * patch.tracking
    octaves = key + patch.envelope_octaves * filter_level + patch.velocity_octaves * (level - 0.6)
    cutoff = np.clip(patch.cutoff * 2.0**octaves, 20.0, 18000.0)
    left, right = _filter(patch, left, cutoff), _filter(patch, right, cutoff)
    decibels = patch.gain_db - patch.range_db * (1.0 - np.clip(level, 0.0, 1.0))
    gain = amplitude * 10.0 ** (decibels / 20.0) * 0.25
    return np.stack([left * gain, right * gain], axis=1).astype(np.float32)


def _vibrato(patch: Patch, total: int, random: np.random.Generator, depth: float = 1.0):
    if not patch.vibrato_cents or not depth:
        return np.zeros(total)
    time = np.arange(total) / RATE
    fade = np.clip((time - patch.vibrato_delay) / 0.35, 0.0, 1.0)
    rate_hz = patch.vibrato_hz * (1.0 + 0.04 * random.normal())
    return depth * patch.vibrato_cents / 100.0 * fade * np.sin(2 * np.pi * rate_hz * time)


def render_note(
    patch: Patch,
    midi: float,
    seconds: float,
    level: float,
    level_end: float | None = None,
    *,
    seed: object = 0,
    bend: np.ndarray | None = None,
) -> np.ndarray:
    """Return the sound of one note (two channels). The sound continues after the note stops.

    `level` is the loudness from 0 to 1. `bend` is a pitch curve in semitones
    for the time of the note (it is made longer or shorter to fit).
    """
    random = _random(patch.name, seed, round(float(midi), 2))
    total = int((seconds + 4.0 * patch.amplitude.release + 0.02) * RATE)
    pitch = np.full(total, float(midi)) + _vibrato(patch, total, random)
    if bend is not None and len(bend):
        held = max(1, int(seconds * RATE))
        curve = np.interp(np.linspace(0, len(bend) - 1, held), np.arange(len(bend)), bend)
        pitch[:held] += curve[: min(held, total)]
        pitch[held:] += curve[-1]
    amplitude = patch.amplitude.curve(seconds, total)
    filter_level = patch.filter_envelope.curve(seconds, total)
    levels = np.full(total, level)
    if level_end is not None and level_end != level:
        held = max(1, int(seconds * RATE))
        levels[:held] = np.linspace(level, level_end, held)[: min(held, total)]
        levels[held:] = level_end
    return _voice(patch, pitch, amplitude, filter_level, levels, random)


@dataclass(frozen=True)
class LineNote:
    """One note of a line: times in seconds from the start of the line."""

    start: float
    seconds: float
    midi: float
    level: float
    level_end: float | None = None
    legato: bool = False  # the note follows the note before it with no new attack
    vibrato: float = 1.0  # depth of the vibrato relative to the patch
    bend: tuple[float, ...] = ()  # pitch curve in semitones for the time of the note


def render_line(patch: Patch, notes: list[LineNote], *, seed: object = 0) -> np.ndarray:
    """Return the sound of a line that one voice plays (two channels).

    A legato note has no new attack: the pitch slides to it in the glide
    time of the patch. The line must be in time sequence.
    """
    if not notes:
        return np.zeros((0, 2), dtype=np.float32)
    random = _random(patch.name, seed, len(notes))
    end = max(note.start + note.seconds for note in notes)
    total = int((end + 4.0 * patch.amplitude.release + 0.02) * RATE)
    pitch = np.full(total, notes[0].midi, dtype=np.float64)
    amplitude, filter_level = np.zeros(total), np.zeros(total)
    levels = np.full(total, notes[0].level)
    index = 0
    while index < len(notes):
        # A group: one attack, then legato notes.
        last = index
        while last + 1 < len(notes) and notes[last + 1].legato:
            last += 1
        group = notes[index : last + 1]
        first = int(group[0].start * RATE)
        stop = group[-1].start + group[-1].seconds
        span = total - first
        held = stop - group[0].start
        amplitude[first:] = np.maximum(amplitude[first:], patch.amplitude.curve(held, span))
        filter_level[first:] = np.maximum(
            filter_level[first:], patch.filter_envelope.curve(held, span)
        )
        for number, note in enumerate(group):
            begin = int(note.start * RATE)
            finish = min(total, int((note.start + note.seconds) * RATE))
            target = np.full(total - begin, note.midi, dtype=np.float64)
            if number > 0 and patch.glide > 0:
                before = group[number - 1].midi
                steps = np.arange(total - begin) / RATE
                target += (before - note.midi) * np.exp(-steps / (patch.glide / 3.0))
            pitch[begin:] = target
            if note.bend:
                curve = np.interp(
                    np.linspace(0, len(note.bend) - 1, max(1, finish - begin)),
                    np.arange(len(note.bend)),
                    np.array(note.bend),
                )
                pitch[begin:finish] += curve
                pitch[finish:] += curve[-1]
            wobble = _vibrato(patch, finish - begin, random, note.vibrato)
            pitch[begin:finish] += wobble
            final = note.level if note.level_end is None else note.level_end
            levels[begin:finish] = np.linspace(note.level, final, max(1, finish - begin))
            levels[finish:] = final
        index = last + 1
    # Make the steps of the loudness smooth: a new note does not click.
    step = 1.0 / (0.008 * RATE)
    levels = kernels.slew(levels, step, step)
    return _voice(patch, pitch, amplitude, filter_level, levels, random)


# ----------------------------------------------------------------------------
# Frequency modulation
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Operators:
    """One carrier and one modulator."""

    ratio: float = 1.0  # frequency of the modulator divided by that of the carrier
    carrier_ratio: float = 1.0  # frequency of the carrier divided by that of the note
    index: float = 2.0  # depth of the modulation at the start of a loud note
    index_decay: float = 0.4  # seconds
    index_sustain: float = 0.2  # share of the index that stays
    feedback: float = 0.0
    level: float = 1.0
    amplitude: Envelope = field(default_factory=lambda: Envelope(0.002, 1.5, 0.0, 0.3))
    cents: float = 0.0
    pan: float = 0.5


@dataclass(frozen=True)
class FMPatch:
    """A sound from pairs of sine operators (bells, electric pianos, growls)."""

    name: str
    pairs: tuple[Operators, ...]
    velocity_index: float = 1.5  # a loud note has this much more modulation
    range_db: float = 26.0
    gain_db: float = 0.0
    tremolo_hz: float = 0.0  # a slow change of the level between left and right
    tremolo_depth: float = 0.0


def render_fm(
    patch: FMPatch, midi: float, seconds: float, level: float, *, seed: object = 0
) -> np.ndarray:
    """Return the sound of one note of an FM patch (two channels)."""
    random = _random(patch.name, seed, round(float(midi), 2))
    longest = max(4.0 * pair.amplitude.release for pair in patch.pairs)
    total = int((seconds + longest + 0.02) * RATE)
    time = np.arange(total) / RATE
    left, right = np.zeros(total), np.zeros(total)
    for pair in patch.pairs:
        base = hertz(midi + pair.cents / 100.0 + random.normal(0.0, 0.01)) * pair.carrier_ratio
        frequency = np.full(total, base)
        depth = pair.index * (1.0 + patch.velocity_index * (level - 0.6))
        index = depth * (pair.index_sustain + (1 - pair.index_sustain) * np.exp(
            -time / max(pair.index_decay, 1e-3)))  # fmt: skip
        wave = kernels.fm_pair(frequency, pair.ratio, np.maximum(index, 0.0), pair.feedback, RATE)
        wave = wave * pair.amplitude.curve(seconds, total) * pair.level
        left += wave * np.cos(pair.pan * np.pi / 2)
        right += wave * np.sin(pair.pan * np.pi / 2)
    gain = 10.0 ** ((patch.gain_db - patch.range_db * (1.0 - min(max(level, 0.0), 1.0))) / 20.0)
    if patch.tremolo_depth:
        phase = 2 * np.pi * (patch.tremolo_hz * time + random.uniform())
        left *= 1.0 + patch.tremolo_depth * np.sin(phase)
        right *= 1.0 - patch.tremolo_depth * np.sin(phase)
    return (np.stack([left, right], axis=1) * gain * 0.3).astype(np.float32)
