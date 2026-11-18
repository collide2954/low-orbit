"""Electronic drums and noise effects that code makes with no samples.

Each function returns one stroke as a signal with one channel. `level` is
the loudness from 0 to 1. `seed` gives each stroke its small random
differences: two strokes with different seeds are not the same.
"""

from __future__ import annotations

import numpy as np
from scipy import signal

from . import dsp, kernels

RATE = float(dsp.RATE)


def _time(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * RATE)) / RATE


def _random(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _band(noise: np.ndarray, low: float, high: float, order: int = 2) -> np.ndarray:
    sections = signal.butter(order, [low, min(high, 0.49 * RATE)], "bandpass", fs=RATE,
                             output="sos")  # fmt: skip
    return signal.sosfilt(sections, noise)


def kick(
    level: float = 0.8,
    seed: int = 0,
    *,
    pitch: float = 48.0,  # hertz, at the end of the stroke
    sweep: float = 150.0,  # hertz above `pitch` at the start
    sweep_time: float = 0.035,
    decay: float = 0.32,
    click: float = 0.5,
    drive: float = 1.5,
) -> np.ndarray:
    """A kick drum: a sine tone whose pitch goes down fast, and a click."""
    random = _random(seed)
    time = _time(decay * 3.0 + 0.05)
    level = float(np.clip(level, 0.0, 1.0))
    start = sweep * (0.6 + 0.6 * level) * (1.0 + 0.03 * random.normal())
    frequency = pitch * (1.0 + 0.004 * random.normal()) + start * np.exp(-time / sweep_time)
    body = kernels.sine(frequency, RATE, 0.0) * np.exp(-time / (decay * (0.7 + 0.5 * level)))
    body = np.tanh(drive * body) / np.tanh(drive)
    snap = random.normal(0.0, 1.0, len(time)) * np.exp(-time / 0.003)
    snap = _band(snap, 1500.0, 7000.0) * click * (0.4 + 0.8 * level)
    return (body + snap) * (0.25 + 0.75 * level**1.5)


# The dubstep passage is in F-sharp minor: its sub tone is F-sharp 1 (46 Hz). The kick drum
# and the snare drum of the passage have the same note, one and two octaves higher.
DEEP_KICK_HERTZ = 92.5
DEEP_SNARE_HERTZ = 185.0


def hard_kick(level: float = 0.9, seed: int = 0, pitch: float = DEEP_KICK_HERTZ) -> np.ndarray:
    """The kick drum of dubstep: short, with a click, one octave above the sub tone.

    The sub tone is the lowest sound of the style, and it is long. A kick
    drum with a long low body (the first form: 50 Hz, 0.17 seconds) is in
    the same place and makes the two unclear. This drum is at the note of
    the key, one octave above the sub, and its body is gone after a tenth
    of a second: the stroke is the drum, the weight after it is the sub.
    """
    out = kick(level, seed, pitch=pitch, sweep=230.0, sweep_time=0.022, decay=0.055, click=1.0,
               drive=2.5)  # fmt: skip
    return signal.sosfilt(dsp.highpass(50.0, 2), out)


def sub_drop(level: float = 0.8, seconds: float = 1.6, start: float = 90.0, end: float = 32.0):
    """A long low tone whose pitch falls (the "drop" of electronic dance music)."""
    time = _time(seconds)
    frequency = end + (start - end) * np.exp(-time / (seconds / 5.0))
    tone = kernels.sine(frequency, RATE, 0.0)
    shape = np.minimum(time / 0.004, 1.0) * np.exp(-time / (seconds / 3.5))
    return np.tanh(1.8 * tone * shape) * level


def snare(
    level: float = 0.8,
    seed: int = 0,
    *,
    pitch: float = 190.0,
    decay: float = 0.16,
    noise: float = 1.0,
    brightness: float = 1.0,
) -> np.ndarray:
    """A snare drum: two shell tones and filtered noise."""
    random = _random(seed)
    time = _time(decay * 3.5 + 0.05)
    level = float(np.clip(level, 0.0, 1.0))
    tune = 1.0 + 0.01 * random.normal()
    bend = 1.0 + 0.25 * level * np.exp(-time / 0.012)
    shell = kernels.sine(np.full(len(time), pitch * tune) * bend, RATE, 0.0) * np.exp(-time / 0.07)
    shell += (
        0.5
        * kernels.sine(np.full(len(time), pitch * 1.78 * tune) * bend, RATE, 0.25)
        * np.exp(-time / 0.045)
    )
    wires = random.normal(0.0, 1.0, len(time)) * np.exp(-time / (decay * (0.6 + 0.6 * level)))
    wires = _band(wires, 900.0, 9000.0 * brightness) + 0.4 * _band(wires, 4000.0, 14000.0)
    snap = random.normal(0.0, 1.0, len(time)) * np.exp(-time / 0.002)
    out = 0.9 * shell + noise * 0.55 * wires + 0.35 * signal.sosfilt(dsp.highpass(2000.0), snap)
    return np.tanh(1.4 * out) * (0.12 + 0.88 * level**1.7)


def heavy_snare(
    level: float = 0.9, seed: int = 0, *, pitch: float = DEEP_SNARE_HERTZ, tail: float = 0.42
) -> np.ndarray:
    """The snare drum of dubstep, with two channels.

    Four layers: a low body at the note of the key whose pitch falls, a hard crack of
    noise, hand claps, and a long tail of noise that is different on the
    left and on the right (the "room" of the stroke).
    """
    random = _random(seed)
    time = _time(tail * 2.5 + 0.1)
    level = float(np.clip(level, 0.0, 1.0))
    bend = 1.0 + 0.7 * np.exp(-time / 0.012)
    tune = pitch * (1.0 + 0.008 * random.normal())
    body = kernels.sine(tune * bend, RATE, 0.0) * np.exp(-time / 0.09)
    body += 0.6 * kernels.sine(1.6 * tune * bend, RATE, 0.25) * np.exp(-time / 0.05)
    crack = _band(random.normal(0.0, 1.0, len(time)) * np.exp(-time / 0.035), 1200.0, 9000.0)
    snap = random.normal(0.0, 1.0, len(time)) * np.exp(-time / 0.002)
    snap = signal.sosfilt(dsp.highpass(2500.0), snap)
    hands = clap(1.0, seed + 1)
    centre = body + 0.8 * crack + 0.4 * snap
    centre[: len(hands)] += 0.6 * hands[: len(centre)]
    centre = np.tanh(1.6 * centre)
    out = np.empty((len(time), 2))
    shape = np.exp(-time / (tail / 3.0)) * np.minimum(time / 0.01, 1.0)
    for channel in range(2):
        noise = _band(random.normal(0.0, 1.0, len(time)) * shape, 700.0, 6000.0)
        out[:, channel] = centre + 0.3 * noise
    return out * (0.15 + 0.85 * level**1.6)


def roll_snare(level: float = 0.8, seed: int = 0, pitch: float = 220.0) -> np.ndarray:
    """A short, tight snare drum for a roll. The pitch can rise from stroke to stroke."""
    return snare(level, seed, pitch=pitch, decay=0.07, noise=0.9, brightness=0.9)


def reverse_cymbal(seconds: float, level: float = 0.8, seed: int = 0) -> np.ndarray:
    """A cymbal that plays backwards, with two channels: noise that grows and stops at the end."""
    random = _random(seed)
    time = _time(seconds)
    left = seconds - time  # the time to the end of the sound
    shape = np.exp(-left / (seconds / 3.5)) * np.minimum(left / 0.004, 1.0)
    out = np.empty((len(time), 2))
    for channel in range(2):
        out[:, channel] = _band(random.normal(0.0, 1.0, len(time)), 2500.0, 9000.0) * shape
    return out * 0.3 * level


def clap(level: float = 0.8, seed: int = 0, *, decay: float = 0.22, spread: float = 0.011):
    """Hand claps: some short bursts of noise, then a tail."""
    random = _random(seed)
    time = _time(decay * 3.0 + 0.08)
    out = np.zeros(len(time))
    for number in range(4):
        start = number * spread * (1.0 + 0.2 * random.normal())
        burst = np.where(time >= start, np.exp(-(time - start) / 0.004), 0.0)
        out += burst * random.normal(0.0, 1.0, len(time)) * (0.7 if number < 3 else 0.0)
    tail = np.where(time >= 3 * spread, np.exp(-(time - 3 * spread) / (decay / 3.0)), 0.0)
    out += tail * random.normal(0.0, 1.0, len(time))
    out = _band(out, 700.0, 6500.0) + 0.3 * _band(out, 1100.0, 1700.0)
    return out * 0.6 * (0.2 + 0.8 * level**1.5)


def hat(
    level: float = 0.7,
    seed: int = 0,
    *,
    decay: float = 0.04,  # 0.04 = closed; 0.3 = open
    tone: float = 1.0,
) -> np.ndarray:
    """A hi-hat: six square waves that are not in tune, through a high filter, and noise."""
    random = _random(seed)
    time = _time(decay * 4.0 + 0.03)
    level = float(np.clip(level, 0.0, 1.0))
    metal = np.zeros(len(time))
    for ratio in (2.0, 3.0, 4.16, 5.43, 6.79, 8.21):
        frequency = np.full(len(time), 205.3 * ratio * tone * (1.0 + 0.004 * random.normal()))
        metal += kernels.pulse(frequency, np.full(len(time), 0.5), RATE, random.uniform())
    metal = _band(metal, 7000.0, 16000.0) * 0.35
    hiss = signal.sosfilt(dsp.highpass(6500.0, 2), random.normal(0.0, 1.0, len(time)))
    shape = np.exp(-time / (decay * (0.6 + 0.7 * level))) * np.minimum(time / 0.0005, 1.0)
    return (metal + 0.6 * hiss) * shape * 0.35 * (0.08 + 0.92 * level**1.8)


def tom(level: float = 0.8, seed: int = 0, *, pitch: float = 110.0, decay: float = 0.3):
    """A tom-tom: a sine tone whose pitch goes down a little."""
    random = _random(seed)
    time = _time(decay * 3.5)
    bend = 1.0 + 0.35 * np.exp(-time / 0.03)
    tone = kernels.sine(np.full(len(time), pitch * (1 + 0.006 * random.normal())) * bend, RATE, 0.0)
    snap = signal.sosfilt(dsp.highpass(1200.0), random.normal(0.0, 1.0, len(time)))
    out = tone * np.exp(-time / decay) + 0.15 * snap * np.exp(-time / 0.004)
    return np.tanh(1.3 * out) * (0.2 + 0.8 * level**1.5)


def rim(level: float = 0.8, seed: int = 0) -> np.ndarray:
    """A short click with a pitch: a stroke on the rim of a drum."""
    random = _random(seed)
    time = _time(0.09)
    out = np.zeros(len(time))
    for frequency, decay in ((1720.0, 0.012), (480.0, 0.02), (3300.0, 0.006)):
        tone = np.sin(2 * np.pi * frequency * (1 + 0.004 * random.normal()) * time)
        out += tone * np.exp(-time / decay)
    return out * 0.4 * (0.25 + 0.75 * level**1.4)


def zap(level: float = 0.8, seed: int = 0, *, start: float = 6000.0, end: float = 120.0,
        seconds: float = 0.12) -> np.ndarray:  # fmt: skip
    """A laser sound of old video games: a tone that falls very fast."""
    time = _time(seconds)
    frequency = end + (start - end) * np.exp(-time / (seconds / 6.0))
    wave = kernels.pulse(frequency, np.full(len(time), 0.5), RATE, 0.0)
    return wave * np.exp(-time / (seconds / 2.5)) * 0.3 * level


def riser(seconds: float, level: float = 0.8, seed: int = 0, *, low: float = 300.0,
          high: float = 12000.0, tone: bool = True) -> np.ndarray:  # fmt: skip
    """Noise and a tone that go up for `seconds`: the tension before a new section."""
    random = _random(seed)
    time = _time(seconds)
    share = time / max(seconds, 1e-6)
    cutoff = low * (high / low) ** share
    noise = random.normal(0.0, 1.0, len(time))
    swept = kernels.state_variable(noise, cutoff, np.full(len(time), 2.5), RATE, 1)
    out = swept * share**2
    if tone:
        frequency = 110.0 * 2.0 ** (3.0 * share**1.5)
        out += 0.35 * kernels.saw(frequency, RATE, 0.0) * share**2.5
    return out * 0.3 * level


def downlifter(seconds: float, level: float = 0.8, seed: int = 0) -> np.ndarray:
    """Noise that goes down and becomes soft: the release after a loud moment."""
    random = _random(seed)
    time = _time(seconds)
    share = time / max(seconds, 1e-6)
    cutoff = 14000.0 * (200.0 / 14000.0) ** share
    noise = random.normal(0.0, 1.0, len(time))
    swept = kernels.state_variable(noise, cutoff, np.full(len(time), 1.2), RATE, 0)
    return swept * (1.0 - share) ** 1.5 * 0.3 * level


def impact(level: float = 0.9, seed: int = 0, seconds: float = 2.5) -> np.ndarray:
    """A large stroke for the start of a section: a low drum, noise, and a long tail."""
    random = _random(seed)
    time = _time(seconds)
    low = kick(1.0, seed, pitch=38.0, sweep=110.0, decay=0.9, click=0.8, drive=2.5)
    out = np.zeros(len(time))
    out[: min(len(low), len(out))] += low[: len(out)]
    noise = random.normal(0.0, 1.0, len(time)) * np.exp(-time / (seconds / 5.0))
    out += 0.5 * signal.sosfilt(dsp.lowpass(3500.0, 1), noise)
    return np.tanh(out) * level
