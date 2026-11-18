"""Effects for the stems and for the mix: space, time, tone, and level.

All functions take a signal with two channels (samples x 2) and return a
new signal with two channels, if the description does not say a different
thing. The sample rate is that of the project.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import soxr
from scipy import ndimage, signal

from . import dsp, kernels

RATE = float(dsp.RATE)


def stereo(samples: np.ndarray) -> np.ndarray:
    """Return a signal with two channels (a signal with one channel goes to the centre)."""
    if samples.ndim == 1:
        return np.repeat(samples[:, None], 2, axis=1) * np.float32(np.sqrt(0.5))
    return samples


def each(samples: np.ndarray, function) -> np.ndarray:
    """Apply a function for one channel to the two channels."""
    return np.stack([function(samples[:, 0]), function(samples[:, 1])], axis=1)


def pan(samples: np.ndarray, position: float) -> np.ndarray:
    """Put a signal with one channel at a place between left (-1) and right (+1)."""
    angle = (position + 1.0) * np.pi / 4.0
    return np.stack([samples * np.cos(angle), samples * np.sin(angle)], axis=1)


def width(samples: np.ndarray, amount: float) -> np.ndarray:
    """Change the stereo width: 0 = one point, 1 = no change, 2 = very wide."""
    mid = 0.5 * (samples[:, 0] + samples[:, 1])
    side = 0.5 * (samples[:, 0] - samples[:, 1]) * amount
    return np.stack([mid + side, mid - side], axis=1)


def equalize(samples: np.ndarray, *filters: np.ndarray) -> np.ndarray:
    """Apply filters of `dsp` (peaking, shelf, highpass, lowpass) one after the other."""
    if not filters:
        return samples
    return signal.sosfilt(np.vstack(filters), samples, axis=0)


# ----------------------------------------------------------------------------
# Space
# ----------------------------------------------------------------------------


@lru_cache(maxsize=32)
def room(
    seconds: float = 1.6,
    brightness: float = 0.5,
    predelay: float = 0.012,
    density: float = 1.0,
    seed: int = 7,
) -> np.ndarray:
    """Make the impulse response of a room or a plate: noise that becomes soft.

    `seconds` is the time for a decay of 60 dB at middle frequencies. The
    high frequencies decay faster (`brightness` 0 = dark, 1 = bright). A
    small `density` gives single early echoes. The result has two channels
    that are not the same: thus the room has width.
    """
    random = np.random.default_rng(seed)
    total = int((seconds * 1.3 + predelay + 0.05) * RATE)
    time = np.arange(total) / RATE
    result = np.zeros((total, 2))
    edges = [0.0, 250.0, 1000.0, 3000.0, 7000.0, RATE / 2]
    factors = [1.15, 1.0, 0.85 - 0.25 * (1 - brightness), 0.6 - 0.3 * (1 - brightness),
               0.35 - 0.2 * (1 - brightness)]  # fmt: skip
    for channel in range(2):
        noise = random.normal(0.0, 1.0, total)
        if density < 1.0:
            # Few echoes at the start: keep only some samples in the first 80 ms.
            early = time < 0.08
            noise[early] *= random.uniform(0.0, 1.0, int(early.sum())) < 0.02 + 0.3 * density
            noise[early] *= 4.0
        spectrum = np.fft.rfft(noise)
        frequencies = np.fft.rfftfreq(total, 1.0 / RATE)
        for low, high, factor in zip(edges[:-1], edges[1:], factors, strict=True):
            band = np.where((frequencies >= low) & (frequencies < high), spectrum, 0.0)
            part = np.fft.irfft(band, total)
            decay = max(0.1, seconds * factor)
            result[:, channel] += part * 10.0 ** (-3.0 * time / decay)
    shift = int(predelay * RATE)
    result = np.concatenate([np.zeros((shift, 2)), result])[:total]
    result *= np.minimum(1.0, np.arange(total) / (0.003 * RATE))[:, None] if shift == 0 else 1.0
    return (result / np.sqrt((result**2).sum(axis=0).mean())).astype(np.float32)


def reverb(samples: np.ndarray, response: np.ndarray, tail: bool = True) -> np.ndarray:
    """Return only the sound of the room (no direct sound)."""
    wet = np.stack([signal.oaconvolve(samples[:, c], response[:, c]) for c in range(2)], axis=1)
    return wet if tail else wet[: len(samples)]


def delay(
    samples: np.ndarray,
    seconds: float,
    feedback: float = 0.4,
    damping: float = 0.4,
    ping_pong: bool = True,
    repeats: int = 8,
) -> np.ndarray:
    """Return the echoes of a signal (no direct sound). `seconds` is the time between echoes."""
    step = int(round(seconds * RATE))
    total = len(samples) + step * repeats
    out = np.zeros((total, 2))
    current = samples.astype(np.float64)
    cutoff = 12000.0 * (1.0 - damping) + 800.0
    lowpass = dsp.lowpass(cutoff, 1)
    for number in range(1, repeats + 1):
        current = signal.sosfilt(lowpass, current, axis=0) * feedback
        if ping_pong:
            current = (
                current[:, ::-1]
                if number > 1
                else np.stack([current.mean(axis=1) * 1.2, current.mean(axis=1) * 0.2], axis=1)
            )
        out[number * step : number * step + len(current)] += current
    return out


def chorus(
    samples: np.ndarray, rate_hz: float = 0.6, depth_ms: float = 3.0, mix: float = 0.5,
    voices: int = 3,
) -> np.ndarray:  # fmt: skip
    """Add copies of the signal whose pitch moves slowly (the sound of an ensemble)."""
    total = len(samples)
    time = np.arange(total) / RATE
    out = samples.astype(np.float64) * (1.0 - 0.5 * mix)
    for voice in range(voices):
        phase = 2 * np.pi * voice / voices
        for channel in range(2):
            wave = np.sin(2 * np.pi * rate_hz * (1.0 + 0.13 * voice) * time + phase + channel * 1.3)
            lag = (0.012 + 0.001 * depth_ms * (1.0 + wave)) * RATE
            moved = kernels.comb(samples[:, channel].astype(np.float64), lag, 0.0, 0.0)
            out[:, channel] += moved * mix / voices * 1.4
    return out


# ----------------------------------------------------------------------------
# Tone
# ----------------------------------------------------------------------------


def _oversampled(samples: np.ndarray, function, factor: int = 4) -> np.ndarray:
    """Apply a function at a higher sample rate: thus the new partials make no alias tones."""
    high = soxr.resample(samples, RATE, RATE * factor, quality="HQ")
    return soxr.resample(function(high), RATE * factor, RATE, quality="HQ")[: len(samples)]


def saturate(samples: np.ndarray, drive_db: float = 6.0, bias: float = 0.0) -> np.ndarray:
    """A soft limit, as a tape or a tube: louder input gives more partials.

    `bias` makes the two halves of the wave different: this adds even partials.
    The loudness of a full-level signal stays about the same.
    """
    gain = dsp.db(drive_db)

    def shape(high: np.ndarray) -> np.ndarray:
        return np.tanh(gain * high + bias) - np.tanh(bias)

    return _oversampled(samples.astype(np.float64), shape) / np.tanh(gain)


def fold(samples: np.ndarray, drive_db: float = 6.0) -> np.ndarray:
    """A wave folder: the peaks of the wave turn back. The sound is hard and metallic."""
    gain = dsp.db(drive_db)
    return _oversampled(samples.astype(np.float64), lambda high: np.sin(0.5 * np.pi * gain * high))


def crush(samples: np.ndarray, bits: float = 8.0, hold: int = 1) -> np.ndarray:
    """Give the signal few level steps and a low sample rate (old digital sound)."""
    steps = 2.0 ** (bits - 1.0)
    out = np.round(samples * steps) / steps
    if hold > 1:
        index = (np.arange(len(out)) // hold) * hold
        out = out[index]
    return out


def sweep(
    samples: np.ndarray, cutoff: np.ndarray, mode: str = "lowpass", resonance: float = 0.7
) -> np.ndarray:
    """A filter whose cutoff frequency changes: `cutoff` gives the value for each sample."""
    number = {"lowpass": 0, "bandpass": 1, "highpass": 2}[mode]
    quality = np.full(len(samples), resonance)
    return each(
        samples.astype(np.float64),
        lambda channel: kernels.state_variable(channel, cutoff, quality, RATE, number),
    )


# ----------------------------------------------------------------------------
# Level
# ----------------------------------------------------------------------------


def compress(
    samples: np.ndarray,
    threshold_db: float = -18.0,
    ratio: float = 4.0,
    attack: float = 0.01,
    release: float = 0.12,
    knee_db: float = 6.0,
    makeup_db: float = 0.0,
    key: np.ndarray | None = None,
    mix: float = 1.0,
) -> np.ndarray:
    """A compressor. `key` is a different signal that controls the gain (one channel).

    `mix` below 1 keeps a part of the signal with no change (parallel compression).
    """
    control = np.abs(samples).max(axis=1) if key is None else np.abs(key)
    level = kernels.follow(control.astype(np.float64), attack, release, RATE)
    gain_db = kernels.compressor_gain(level, threshold_db, ratio, knee_db)
    gain = 10.0 ** ((gain_db + makeup_db) / 20.0)
    return samples * (1.0 - mix) + samples * gain[:, None] * mix


def duck(
    total: int, times: np.ndarray, depth_db: float = 6.0, hold: float = 0.02,
    release: float = 0.18,
) -> np.ndarray:  # fmt: skip
    """Return a gain curve that goes down at each given time and comes back (side-chain).

    `times` are the moments of the kick drum in seconds. The result has one
    value for each sample: multiply a stem by it.
    """
    curve = np.zeros(total)
    shape_length = int((hold + release * 4.0) * RATE)
    time = np.arange(shape_length) / RATE
    shape = np.where(time < hold, 1.0, np.exp(-(time - hold) / (release / 2.5)))
    for moment in times:
        start = int(moment * RATE) - int(0.004 * RATE)
        if start >= total or start + shape_length <= 0:
            continue
        first = max(0, start)
        last = min(total, start + shape_length)
        curve[first:last] = np.maximum(curve[first:last], shape[first - start : last - start])
    return 10.0 ** (-depth_db * curve / 20.0)


def transient(samples: np.ndarray, attack_db: float = 3.0, sustain_db: float = 0.0) -> np.ndarray:
    """Make the start of each sound louder or softer than its body (transient shaper)."""
    control = np.abs(samples).max(axis=1).astype(np.float64)
    fast = kernels.follow(control, 0.001, 0.05, RATE)
    slow = kernels.follow(control, 0.02, 0.05, RATE)
    body = kernels.follow(control, 0.02, 0.4, RATE)
    start = np.clip((fast - slow) / np.maximum(fast, 1e-6), 0.0, 1.0)
    held = np.clip((body - slow) / np.maximum(body, 1e-6), 0.0, 1.0)
    gain = 10.0 ** ((attack_db * start + sustain_db * held) / 20.0)
    return samples * gain[:, None]


def limit(
    samples: np.ndarray, ceiling_db: float = -1.0, lookahead: float = 0.004, release: float = 0.08
) -> np.ndarray:
    """A limiter that sees the peaks before they come: no sample goes above the ceiling."""
    window = max(1, int(lookahead * RATE))
    peak = np.abs(samples).max(axis=1)
    ahead = ndimage.maximum_filter1d(peak, size=2 * window + 1, mode="constant")
    gain = kernels.limiter_gain(ahead.astype(np.float64), dsp.db(ceiling_db), release, RATE)
    smooth = ndimage.uniform_filter1d(gain, size=window, mode="nearest")
    return samples * np.minimum(gain, smooth)[:, None]


def clip(samples: np.ndarray, ceiling_db: float = -0.5, knee: float = 0.2) -> np.ndarray:
    """Cut the highest peaks softly. A short peak that is cut is not audible as distortion."""
    ceiling = dsp.db(ceiling_db)
    start = ceiling * (1.0 - knee)
    size = np.abs(samples)
    over = np.maximum(size - start, 0.0)
    span = ceiling - start
    shaped = start + span * np.tanh(over / max(span, 1e-9))
    return np.where(size > start, np.sign(samples) * shaped, samples)
