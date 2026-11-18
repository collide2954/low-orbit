"""The sound of old tape and of a radio link: unsteady speed, hiss, crackle, and signal tones."""

from __future__ import annotations

import numpy as np
from scipy import signal

from .audio import dsp

RATE = dsp.RATE


def speed_curve(
    total: int, wow_cents: float = 7.0, flutter_cents: float = 1.6, seed: int = 1
) -> np.ndarray:
    """Return the pitch error of a tape machine for each sample, in cents.

    The wow is slow (below 1.5 Hz) and not regular; the flutter is fast
    (about 6 to 9 Hz) and small.
    """
    random = np.random.default_rng(seed)
    time = np.arange(total) / RATE
    wow = np.zeros(total)
    for rate_hz, share in ((0.31, 0.5), (0.74, 0.3), (1.27, 0.2)):
        wow += share * np.sin(2 * np.pi * rate_hz * time + random.uniform(0, 6.28))
    # A slow random walk makes the wow not regular.
    steps = random.normal(0.0, 1.0, total // 4800 + 2)
    walk = signal.sosfiltfilt(dsp.lowpass(0.4, 2, rate=10), np.cumsum(steps) * 0.15)
    wow += np.interp(time * 10.0, np.arange(len(walk)), walk - walk.mean())
    flutter = np.sin(2 * np.pi * 6.3 * time + random.uniform(0, 6.28))
    flutter += 0.6 * np.sin(2 * np.pi * 8.9 * time + random.uniform(0, 6.28))
    return wow_cents * wow + flutter_cents * flutter


def warp(sound: np.ndarray, cents: np.ndarray) -> np.ndarray:
    """Play a sound at a speed that changes: `cents` is the pitch error for each sample."""
    ratio = 2.0 ** (cents[: len(sound)] / 1200.0)
    position = np.cumsum(ratio) - ratio[0]
    position *= (len(sound) - 1) / max(position[-1], 1.0)  # the length stays the same
    index = np.arange(len(sound))
    return np.stack([np.interp(position, index, sound[:, c]) for c in range(2)], axis=1)


def hiss(total: int, level_db: float = -52.0, seed: int = 2) -> np.ndarray:
    """Return tape hiss: noise with more level in the high range, a little different left and right."""
    random = np.random.default_rng(seed)
    noise = random.normal(0.0, 1.0, (total, 2))
    noise = signal.sosfilt(dsp.shelf(3000.0, 8.0, high=True), noise, axis=0)
    noise = signal.sosfilt(dsp.lowpass(11000.0, 2), noise, axis=0)
    return noise / np.sqrt(np.mean(noise**2)) * dsp.db(level_db)


def crackle(total: int, per_second: float = 5.0, level_db: float = -34.0, seed: int = 3):
    """Return the small clicks of an old record."""
    random = np.random.default_rng(seed)
    out = np.zeros((total, 2))
    count = int(total / RATE * per_second)
    places = random.integers(0, max(total - 200, 1), count)
    for place in places:
        size = random.uniform(0.2, 1.0) ** 3
        length = int(random.integers(8, 60))
        click = random.normal(0.0, 1.0, length) * np.exp(-np.arange(length) / (length / 4.0))
        side = random.uniform(0.2, 0.8)
        out[place : place + length, 0] += click * size * np.cos(side * np.pi / 2)
        out[place : place + length, 1] += click * size * np.sin(side * np.pi / 2)
    out = signal.sosfilt(dsp.highpass(900.0, 2), out, axis=0)
    return out * dsp.db(level_db)


def beeps(total: int, period: float, midi: float = 93.0, level_db: float = -30.0, seed: int = 4):
    """Return the short tones of a satellite signal: one tone each `period` seconds."""
    time = np.arange(total) / RATE
    frequency = 440.0 * 2.0 ** ((midi - 69.0) / 12.0)
    phase = (time % period) / period
    shape = np.where(phase < 0.16, np.sqrt(np.clip(np.sin(np.pi * phase / 0.16), 0, 1)), 0.0)
    tone = np.sin(2 * np.pi * frequency * time) * shape
    random = np.random.default_rng(seed)
    tone = tone + 0.05 * random.normal(0.0, 1.0, total) * shape
    tone = signal.sosfilt(dsp.highpass(700.0, 2), tone)
    return np.stack([tone * 0.8, tone * 0.5], axis=1) * dsp.db(level_db)


def radio(sound: np.ndarray) -> np.ndarray:
    """Give a sound the narrow band of a radio link."""
    out = signal.sosfilt(dsp.highpass(450.0, 2), sound, axis=0)
    out = signal.sosfilt(dsp.lowpass(2800.0, 4), out, axis=0)
    return np.tanh(2.5 * out) / 2.5


def stop(sound: np.ndarray, seconds: float = 1.8) -> np.ndarray:
    """Make the end of a sound slow down to a stop, as a tape machine that loses its power."""
    count = int(seconds * RATE)
    head, tail = sound[:-count], sound[-count:]
    speed = np.linspace(1.0, 0.0, int(count * 2.0)) ** 0.7
    position = np.cumsum(speed)
    position = position[position < count - 1]
    index = np.arange(count)
    slowed = np.stack([np.interp(position, index, tail[:, c]) for c in range(2)], axis=1)
    slowed *= np.linspace(1.0, 0.0, len(slowed))[:, None] ** 0.5
    return np.concatenate([head, slowed])
