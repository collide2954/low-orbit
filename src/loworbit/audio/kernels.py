"""Fast signal loops for the synthesizers and the effects.

Each function of this module is a loop that calculates one sample from the
sample before it. NumPy cannot do such loops quickly, thus Numba compiles
them. All functions use 64-bit floating-point numbers and one channel.
"""

from __future__ import annotations

import numpy as np
from numba import njit

TWO_PI = 2.0 * np.pi


# ----------------------------------------------------------------------------
# Oscillators
# ----------------------------------------------------------------------------


@njit(cache=True, fastmath=True)
def _blep(phase: float, step: float) -> float:
    """Return the correction that makes a jump of a waveform smooth (polyBLEP)."""
    if phase < step:
        value = phase / step
        return value + value - value * value - 1.0
    if phase > 1.0 - step:
        value = (phase - 1.0) / step
        return value * value + value + value + 1.0
    return 0.0


@njit(cache=True, fastmath=True)
def saw(frequency: np.ndarray, rate: float, phase: float = 0.0) -> np.ndarray:
    """A sawtooth wave with few alias tones. `frequency` gives the pitch of each sample."""
    out = np.empty(len(frequency))
    for index in range(len(frequency)):
        step = frequency[index] / rate
        out[index] = 2.0 * phase - 1.0 - _blep(phase, step)
        phase += step
        phase -= np.floor(phase)
    return out


@njit(cache=True, fastmath=True)
def pulse(frequency: np.ndarray, width: np.ndarray, rate: float, phase: float = 0.0) -> np.ndarray:
    """A pulse wave with few alias tones. `width` is the share of the high part (0 to 1)."""
    out = np.empty(len(frequency))
    for index in range(len(frequency)):
        step = frequency[index] / rate
        duty = min(max(width[index], 0.02), 0.98)
        value = 1.0 if phase < duty else -1.0
        value += _blep(phase, step)
        shifted = phase - duty
        shifted -= np.floor(shifted)
        value -= _blep(shifted, step)
        out[index] = value - (2.0 * duty - 1.0)
        phase += step
        phase -= np.floor(phase)
    return out


@njit(cache=True, fastmath=True)
def sine(frequency: np.ndarray, rate: float, phase: float = 0.0) -> np.ndarray:
    out = np.empty(len(frequency))
    for index in range(len(frequency)):
        out[index] = np.sin(TWO_PI * phase)
        phase += frequency[index] / rate
        phase -= np.floor(phase)
    return out


@njit(cache=True, fastmath=True)
def triangle(frequency: np.ndarray, rate: float, phase: float = 0.0) -> np.ndarray:
    out = np.empty(len(frequency))
    for index in range(len(frequency)):
        out[index] = 4.0 * abs(phase - 0.5) - 1.0
        phase += frequency[index] / rate
        phase -= np.floor(phase)
    return out


@njit(cache=True, fastmath=True)
def fm_pair(
    frequency: np.ndarray,
    ratio: float,
    index: np.ndarray,
    feedback: float,
    rate: float,
) -> np.ndarray:
    """Two sine operators: the modulator changes the phase of the carrier.

    `ratio` is the frequency of the modulator divided by that of the carrier.
    `index` is the depth of the modulation for each sample (radians).
    `feedback` sends the modulator into its own phase (0 to 1).
    """
    out = np.empty(len(frequency))
    carrier, modulator, last = 0.0, 0.0, 0.0
    for number in range(len(frequency)):
        last = np.sin(TWO_PI * modulator + feedback * last)
        out[number] = np.sin(TWO_PI * carrier + index[number] * last)
        step = frequency[number] / rate
        carrier += step
        carrier -= np.floor(carrier)
        modulator += step * ratio
        modulator -= np.floor(modulator)
    return out


@njit(cache=True, fastmath=True)
def stepped(frequency: np.ndarray, table: np.ndarray, rate: float) -> np.ndarray:
    """Read a short table of levels with no interpolation (the sound of old game consoles)."""
    out = np.empty(len(frequency))
    phase = 0.0
    size = len(table)
    for index in range(len(frequency)):
        out[index] = table[int(phase * size) % size]
        phase += frequency[index] / rate
        phase -= np.floor(phase)
    return out


@njit(cache=True, fastmath=True)
def shift_register_noise(frequency: np.ndarray, short: bool, rate: float) -> np.ndarray:
    """The noise of a game console: a shift register that a clock steps.

    `frequency` is the clock rate for each sample. If `short` is true, the
    register repeats after 93 steps: the noise has a metallic pitch.
    """
    out = np.empty(len(frequency))
    register = 1
    phase = 0.0
    tap = 6 if short else 1
    for index in range(len(frequency)):
        phase += frequency[index] / rate
        while phase >= 1.0:
            phase -= 1.0
            bit = (register ^ (register >> tap)) & 1
            register = (register >> 1) | (bit << 14)
        out[index] = 1.0 if register & 1 else -1.0
    return out


# ----------------------------------------------------------------------------
# Filters
# ----------------------------------------------------------------------------


@njit(cache=True, fastmath=True)
def state_variable(
    signal: np.ndarray, cutoff: np.ndarray, resonance: np.ndarray, rate: float, mode: int
) -> np.ndarray:
    """A filter whose cutoff frequency can change for each sample.

    `mode`: 0 = low-pass, 1 = band-pass, 2 = high-pass, 3 = notch.
    `resonance` is the quality factor (0.5 = no peak; 10 = a strong peak).
    """
    out = np.empty(len(signal))
    low, band = 0.0, 0.0
    for index in range(len(signal)):
        frequency = min(max(cutoff[index], 10.0), 0.45 * rate)
        g = np.tan(np.pi * frequency / rate)
        k = 1.0 / max(resonance[index], 0.3)
        a1 = 1.0 / (1.0 + g * (g + k))
        a2 = g * a1
        a3 = g * a2
        v3 = signal[index] - band
        v1 = a1 * low + a2 * v3
        v2 = band + a2 * low + a3 * v3
        low = 2.0 * v1 - low
        band = 2.0 * v2 - band
        if mode == 0:
            out[index] = v2
        elif mode == 1:
            out[index] = v1
        elif mode == 2:
            out[index] = signal[index] - k * v1 - v2
        else:
            out[index] = signal[index] - k * v1
    return out


@njit(cache=True, fastmath=True)
def ladder(
    signal: np.ndarray, cutoff: np.ndarray, resonance: float, drive: float, rate: float
) -> np.ndarray:
    """A low-pass filter of four stages with feedback, in the manner of the Moog ladder.

    `resonance` goes from 0 to about 1 (the filter makes a tone of its own near 1).
    `drive` makes the input louder before the soft limit of the filter.
    """
    out = np.empty(len(signal))
    s1, s2, s3, s4 = 0.0, 0.0, 0.0, 0.0
    for index in range(len(signal)):
        frequency = min(max(cutoff[index], 10.0), 0.45 * rate)
        g = np.tan(np.pi * frequency / rate)
        big = g / (1.0 + g)
        feedback = 4.0 * resonance
        sigma = big * big * big * (1.0 - big) * s1 + big * big * (1.0 - big) * s2
        sigma += big * (1.0 - big) * s3 + (1.0 - big) * s4
        gain = big * big * big * big
        value = np.tanh(drive * signal[index])
        value = (value - feedback * sigma) / (1.0 + feedback * gain)
        value = np.tanh(value)
        v = (value - s1) * big
        y1 = v + s1
        s1 = y1 + v
        v = (y1 - s2) * big
        y2 = v + s2
        s2 = y2 + v
        v = (y2 - s3) * big
        y3 = v + s3
        s3 = y3 + v
        v = (y3 - s4) * big
        y4 = v + s4
        s4 = y4 + v
        out[index] = y4
    return out


@njit(cache=True, fastmath=True)
def one_pole(signal: np.ndarray, cutoff: np.ndarray, rate: float) -> np.ndarray:
    """A soft low-pass filter (6 dB for each octave) with a cutoff for each sample."""
    out = np.empty(len(signal))
    state = 0.0
    for index in range(len(signal)):
        share = 1.0 - np.exp(-TWO_PI * min(cutoff[index], 0.49 * rate) / rate)
        state += share * (signal[index] - state)
        out[index] = state
    return out


@njit(cache=True, fastmath=True)
def comb(signal: np.ndarray, delay: np.ndarray, feedback: float, damping: float) -> np.ndarray:
    """A delay line with feedback. `delay` is the delay of each sample, in samples.

    `damping` (0 to 1) makes each repeat less bright.
    """
    size = int(np.max(delay)) + 4
    buffer = np.zeros(size)
    out = np.empty(len(signal))
    write, state = 0, 0.0
    for index in range(len(signal)):
        position = write - delay[index]
        while position < 0.0:
            position += size
        first = int(position)
        share = position - first
        value = buffer[first % size] * (1.0 - share) + buffer[(first + 1) % size] * share
        state = value * (1.0 - damping) + state * damping
        out[index] = value
        buffer[write] = signal[index] + feedback * state
        write = (write + 1) % size
    return out


# ----------------------------------------------------------------------------
# Level control
# ----------------------------------------------------------------------------


@njit(cache=True, fastmath=True)
def follow(signal: np.ndarray, attack: float, release: float, rate: float) -> np.ndarray:
    """Return the level of a signal (amplitude) with an attack time and a release time."""
    out = np.empty(len(signal))
    up = np.exp(-1.0 / max(attack * rate, 1.0))
    down = np.exp(-1.0 / max(release * rate, 1.0))
    state = 0.0
    for index in range(len(signal)):
        value = abs(signal[index])
        share = up if value > state else down
        state = share * state + (1.0 - share) * value
        out[index] = state
    return out


@njit(cache=True, fastmath=True)
def compressor_gain(
    level: np.ndarray, threshold_db: float, ratio: float, knee_db: float
) -> np.ndarray:
    """Return the gain (dB, 0 or less) of a compressor for each level (amplitude)."""
    out = np.empty(len(level))
    slope = 1.0 - 1.0 / ratio
    for index in range(len(level)):
        over = 20.0 * np.log10(max(level[index], 1e-9)) - threshold_db
        if over <= -0.5 * knee_db:
            out[index] = 0.0
        elif over >= 0.5 * knee_db:
            out[index] = -slope * over
        else:
            value = over + 0.5 * knee_db
            out[index] = -slope * value * value / (2.0 * max(knee_db, 1e-6))
    return out


@njit(cache=True, fastmath=True)
def limiter_gain(peak: np.ndarray, ceiling: float, release: float, rate: float) -> np.ndarray:
    """Return the gain of a limiter. `peak` is the largest sample of each look-ahead window."""
    out = np.empty(len(peak))
    down = np.exp(-1.0 / max(release * rate, 1.0))
    gain = 1.0
    for index in range(len(peak)):
        target = 1.0 if peak[index] <= ceiling else ceiling / peak[index]
        gain = target if target < gain else down * gain + (1.0 - down) * target
        out[index] = gain
    return out


# ----------------------------------------------------------------------------
# Strings
# ----------------------------------------------------------------------------


@njit(cache=True, fastmath=True)
def plucked_string(
    excitation: np.ndarray,
    frequency: np.ndarray,
    decay: np.ndarray,
    brightness: np.ndarray,
    stiffness: float,
    rate: float,
) -> np.ndarray:
    """A plucked string: a delay line with a filter in its loop (Karplus and Strong).

    `excitation` is the pluck. `frequency` is the pitch of each sample.
    `decay` is the time in seconds in which the tone goes down by 60 dB, for
    each sample: a small value is a palm-muted string. `brightness` (0 to 1)
    is the tone of the loop filter. `stiffness` (0 to 0.9) makes the high
    partials sharp, as on a thick string.
    """
    size = int(rate / max(np.min(frequency), 16.0)) + 8
    buffer = np.zeros(size)
    out = np.empty(len(excitation))
    write = 0
    lowpass, allpass_in, allpass_out = 0.0, 0.0, 0.0
    for index in range(len(excitation)):
        period = rate / frequency[index]
        bright = min(max(brightness[index], 0.0), 1.0)
        # The loop filter is late by a part of a sample: make the delay line shorter.
        late = 0.5 * (1.0 - bright) + (1.0 - stiffness) / (1.0 + stiffness)
        position = write - (period - late - 1.0)
        while position < 0.0:
            position += size
        first = int(position)
        share = position - first
        value = buffer[first % size] * (1.0 - share) + buffer[(first + 1) % size] * share
        # Loop filter: a mix of the sample and the mean of two samples.
        mixed = bright * value + (1.0 - bright) * 0.5 * (value + lowpass)
        lowpass = value
        # Stiffness: an all-pass filter makes high partials go round the loop faster.
        stiff = -stiffness * mixed + allpass_in + stiffness * allpass_out
        allpass_in, allpass_out = mixed, stiff
        loss = 10.0 ** (-3.0 * period / (max(decay[index], 0.005) * rate))
        fed = stiff * loss
        out[index] = fed + excitation[index]
        buffer[write] = out[index]
        write = (write + 1) % size
    return out


@njit(cache=True, fastmath=True)
def slew(signal: np.ndarray, up: float, down: float) -> np.ndarray:
    """Limit how fast a value changes: `up` and `down` are the largest steps for one sample."""
    out = np.empty(len(signal))
    state = signal[0] if len(signal) else 0.0
    for index in range(len(signal)):
        change = signal[index] - state
        if change > up:
            change = up
        elif change < -down:
            change = -down
        state += change
        out[index] = state
    return out
