"""Low Orbit: the piece.

One orbit of the Earth, in eight minutes: the signal at the start, the day
side, the line between day and night, the night side with the lights of the
cities, the aurora, the sunrise, the day side again, and the signal that
goes away.

The piece has sections. Each section is one `Session` of the studio: it has
its own bars, and the code mixes it alone. Then the sections go one after
the other into the full mix, and the master is made one time.

Run: uv run python -m loworbit.piece [first section] [last section]
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile

from . import sound, studio, tapefx
from .audio import dsp

RATE = dsp.RATE
BPM = 88.0

# A chord: the bass note, the notes of the pad, the notes of the electric piano.
Chord = tuple[int, tuple[int, ...], tuple[int, ...]]

DAY: list[Chord] = [
    (34, (62, 65, 69, 72), (57, 60, 62, 65)),  # B-flat major 9
    (36, (64, 67, 69, 74), (55, 57, 62, 64)),  # C 6/9
    (38, (65, 69, 72, 76), (53, 57, 60, 64)),  # D minor 9
    (33, (64, 67, 72, 74), (55, 60, 62, 64)),  # A minor 11
]
# The second loop: its second chord has the colour note of the style (the note B-flat
# above A, with C-sharp: the Phrygian sound of "Moon Men").
BRIDGE: list[Chord] = [
    (43, (58, 62, 65, 69), (53, 57, 58, 62)),  # G minor 9
    (33, (61, 64, 67, 70), (55, 58, 61, 64)),  # A 7 with a minor ninth
    (38, (65, 69, 72, 76), (53, 57, 60, 64)),  # D minor 9
    (34, (62, 64, 69, 72), (57, 60, 62, 64)),  # B-flat major 9 with a raised eleventh
]
# The night side: B-flat minor. The chord of B-flat changes from major to minor.
NIGHT: list[Chord] = [
    (34, (61, 65, 68, 72), (56, 60, 61, 65)),  # B-flat minor 9
    (30, (61, 65, 66, 70), (53, 58, 61, 65)),  # G-flat major 7
    (37, (63, 65, 68, 73), (56, 61, 63, 65)),  # D-flat with a ninth
    (32, (60, 63, 65, 68), (56, 60, 63, 65)),  # A-flat 6
]
RISE: list[Chord] = [
    (30, (61, 65, 66, 70), (53, 58, 61, 65)),  # G-flat major 7
    (30, (61, 65, 68, 70), (53, 58, 61, 65)),
    (33, (62, 64, 67, 69), (55, 57, 62, 64)),  # A 7 with a fourth: the way back to D
    (33, (62, 64, 67, 73), (55, 57, 61, 64)),  # A 7
]

# The theme of the lead, 8 bars: (bar, beat, length, note, loudness, legato).
THEME = [
    (0, 0.5, 0.5, 69, 0.7, False), (0, 1.0, 0.5, 72, 0.7, True), (0, 1.5, 1.5, 74, 0.8, True),
    (0, 3.0, 0.5, 77, 0.8, True), (0, 3.5, 0.5, 76, 0.7, True),
    (1, 0.0, 2.0, 74, 0.75, True), (1, 3.0, 0.5, 67, 0.6, False), (1, 3.5, 0.5, 69, 0.65, True),
    (2, 0.0, 1.5, 72, 0.75, True), (2, 1.5, 2.5, 69, 0.7, True),
    (3, 1.0, 0.5, 76, 0.75, False), (3, 1.5, 0.5, 74, 0.7, True), (3, 2.0, 1.0, 72, 0.7, True),
    (3, 3.0, 1.0, 69, 0.65, True),
    (4, 0.0, 0.5, 69, 0.7, False), (4, 0.5, 0.5, 72, 0.7, True), (4, 1.0, 1.5, 74, 0.8, True),
    (4, 2.5, 1.0, 81, 0.85, True), (4, 3.5, 0.5, 79, 0.75, True),
    (5, 0.0, 3.0, 76, 0.8, True), (5, 3.0, 0.5, 74, 0.65, True), (5, 3.5, 0.5, 72, 0.65, True),
    (6, 0.0, 4.0, 74, 0.75, True),
    (7, 0.0, 2.5, 69, 0.6, True),
]  # fmt: skip
# The answer to the theme: the same start, a higher end.
ANSWER = [
    *THEME[:14],
    (4, 0.0, 0.5, 72, 0.7, False), (4, 0.5, 0.5, 74, 0.7, True), (4, 1.0, 1.5, 77, 0.8, True),
    (4, 2.5, 1.0, 81, 0.85, True), (4, 3.5, 0.5, 84, 0.8, True),
    (5, 0.0, 2.5, 83, 0.8, True), (5, 2.5, 0.5, 81, 0.7, True), (5, 3.0, 1.0, 79, 0.7, True),
    (6, 0.0, 1.5, 76, 0.75, True), (6, 1.5, 2.5, 74, 0.7, True),
    (7, 0.0, 3.0, 69, 0.6, True),
]  # fmt: skip
# The melody of the night side: long notes with slides.
NOCTURNE = [
    (0, 0.0, 3.0, 77, 0.7, False), (0, 3.0, 1.0, 75, 0.6, True),
    (1, 0.0, 2.5, 73, 0.7, True), (1, 2.5, 1.5, 72, 0.6, True),
    (2, 0.0, 3.5, 68, 0.7, True),
    (3, 1.0, 1.0, 70, 0.6, False), (3, 2.0, 2.0, 72, 0.65, True),
    (4, 0.0, 3.0, 77, 0.75, True), (4, 3.0, 1.0, 80, 0.7, True),
    (5, 0.0, 2.0, 78, 0.7, True), (5, 2.0, 2.0, 77, 0.65, True),
    (6, 0.0, 4.0, 75, 0.7, True),
    (7, 0.0, 3.0, 72, 0.6, True),
]  # fmt: skip

# The drums of one bar: the sixteenth notes with a stroke, and the loudness of each.
BEATS = {
    "day": (
        {0: 0.9, 7: 0.55, 10: 0.8},
        {4: 0.85, 12: 0.9, 15: 0.25},
        {0: 0.5, 2: 0.7, 3: 0.3, 4: 0.5, 6: 0.7, 8: 0.5, 10: 0.7, 11: 0.3, 12: 0.5, 14: 0.75},
    ),
    "full": (
        {0: 0.95, 3: 0.4, 7: 0.6, 10: 0.85},
        {4: 0.9, 12: 0.95, 15: 0.3, 9: 0.18},
        {step: (0.75 if step % 4 == 2 else 0.5 if step % 2 == 0 else 0.3) for step in range(16)},
    ),
    "half": (
        {0: 0.85, 10: 0.5},
        {8: 0.8},
        {0: 0.4, 4: 0.55, 6: 0.25, 8: 0.4, 12: 0.55, 15: 0.25},
    ),
    "light": ({0: 0.7, 10: 0.5}, {}, {2: 0.5, 6: 0.5, 10: 0.5, 14: 0.5, 15: 0.25}),
}


def drums(s: studio.Session, bar: int, style: str, fill: bool = False, steps: int = 16) -> None:
    kick, snare, hats = (dict(part) for part in BEATS[style])
    if bar % 4 == 3 and style in ("day", "full"):
        kick[14] = 0.6
        snare[9] = 0.2
    if fill:
        snare.update({13: 0.35, 14: 0.5, 15: 0.6})
    for step, level in kick.items():
        if step < steps:
            s.hit("kick", bar, step / 4.0, level)
    for step, level in snare.items():
        if step < steps:
            name = "rim" if style == "light" or (style == "half" and step != 8) else "snare"
            s.hit(name, bar, step / 4.0, level, late=0.009)
    for step, level in hats.items():
        if step < steps:
            name = "open" if step == 14 and bar % 2 == 1 and style != "half" else "hat"
            s.hit(name, bar, step / 4.0, level)


def bass(s: studio.Session, bar: int, chord: Chord, following: Chord, style: str) -> None:
    root = chord[0]
    if style == "long":
        s.line("bass", sound.BASS, [(bar, 0.0, 3.6, root, 0.7, False)])
        return
    if style == "half":
        s.line(
            "bass",
            sound.BASS,
            [(bar, 0.0, 2.3, root, 0.8, False), (bar, 2.5, 1.2, root + 7, 0.6, True)],
        )
        return
    step = (root + following[0]) // 2 + 1
    high = root + 12 if bar % 4 == 2 else root
    s.line(
        "bass",
        sound.BASS,
        [
            (bar, 0.0, 1.3, root, 0.85, False),
            (bar, 1.75, 0.5, root, 0.7, False),
            (bar, 2.5, 1.0, high, 0.75, False),
            (bar, 3.5, 0.45, step, 0.6, False),
        ],
    )


def keys(s: studio.Session, bar: int, chord: Chord, style: str) -> None:
    notes = chord[2]
    if style == "slow":
        s.keys("keys", bar, 0.0, 3.0, notes, 0.5, strum=0.03)
        return
    s.keys("keys", bar, 0.0, 1.4, notes, 0.55)
    s.keys("keys", bar, 1.5, 0.5, notes[1:], 0.4)
    s.keys("keys", bar, 2.75, 1.1, notes, 0.5)


def pluck(s: studio.Session, bar: int, chord: Chord, density: float, shift: int = 12) -> None:
    random = s.random("pluck", bar)
    order = (0, 2, 1, 3, 2, 0, 3, 1, 0, 3, 2, 1, 3, 2, 0, 1)
    for step in range(16):
        if random.uniform() > density:
            continue
        midi = chord[1][order[(step + bar) % 16]] + shift
        level = 0.75 if step % 4 == 0 else 0.5 + 0.15 * random.uniform()
        s.chord("pluck", sound.PLUCK, bar, step / 4.0, 0.2, (midi,), level, swung=True)


def lights(s: studio.Session, bar: int, chord: Chord, count: int) -> None:
    """The lights of the cities: single bell notes at irregular places."""
    random = s.random("lights", bar)
    for _ in range(count):
        beat = float(random.integers(0, 16)) / 4.0
        midi = chord[1][int(random.integers(0, 4))] + 12 * int(random.integers(1, 3))
        s.bell("bell", bar, beat, midi, 0.35 + 0.3 * random.uniform())


def melody(s: studio.Session, notes, first_bar: int, shift: int = 0, soft: float = 1.0) -> None:
    moved = [
        (bar + first_bar, beat, length, midi + shift, level * soft, legato)
        for bar, beat, length, midi, level, legato in notes
    ]
    s.line("lead", sound.LEAD, moved)


def air(s: studio.Session, beeps: tuple[float, float] | None = None, level_db: float = -52.0):
    """The air of a section: hiss and crackle. `beeps`: the first and the last second of a signal."""
    total = s.total
    sound_air = tapefx.hiss(total, level_db, seed=s.seed + 20) + tapefx.crackle(
        total, seed=s.seed + 30
    )
    if beeps is not None:
        first, last = (int(value * RATE) for value in beeps)
        tones = tapefx.beeps(last - first, s.beat * 2.0)
        tones *= np.sin(np.linspace(0.0, np.pi, last - first))[:, None] ** 0.5
        sound_air[first:last] += tones
    s.add("air", sound_air, 0.0)


# ----------------------------------------------------------------------------
# The sections
# ----------------------------------------------------------------------------


@dataclass
class Result:
    session: studio.Session
    automation: dict[str, np.ndarray]


def _ramp(s: studio.Session, first: float, last: float, start: float, end: float) -> np.ndarray:
    """Return a curve that goes from `start` to `end` between two bars (in octaves if for a filter)."""
    time = np.arange(s.total) / RATE
    share = np.clip((time - s.time(first)) / max(s.time(last) - s.time(first), 1e-6), 0.0, 1.0)
    return start + (end - start) * share


def signal_start(seed: int) -> Result:
    """The signal: 8 bars. The music comes out of a low-pass filter, as from far away."""
    s = studio.Session(BPM, 8, seed=seed)
    for bar in range(8):
        chord = DAY[bar % 4]
        s.chord("pad", sound.PAD, bar, 0.0, 4.3, chord[1], 0.5)
        if bar >= 2:
            keys(s, bar, chord, "day")
        if bar >= 4:
            bass(s, bar, chord, DAY[(bar + 1) % 4], "long")
    s.hit("snare", 7, 3.25, 0.3)
    s.hit("snare", 7, 3.5, 0.5)
    s.hit("hat", 7, 3.0, 0.5)
    s.hit("hat", 7, 3.75, 0.6)
    air(s, (0.0, s.time(7)), -48.0)
    octaves = _ramp(s, 0, 7, 0.0, 6.0)
    return Result(s, {"sweep": 250.0 * 2.0**octaves, "master": _ramp(s, 0, 2, 0.0, 1.0) ** 1.5})


def day(seed: int, bars: int, theme: bool, style: str = "day", busy: bool = False) -> Result:
    """The day side: the loop of four chords with the drums; the theme if `theme` is true."""
    s = studio.Session(BPM, bars, seed=seed)
    for bar in range(bars):
        chord = DAY[bar % 4]
        s.chord("pad", sound.PAD, bar, 0.0, 4.3, chord[1], 0.62)
        keys(s, bar, chord, "day")
        drums(s, bar, style, fill=bar % 8 == 7)
        bass(s, bar, chord, DAY[(bar + 1) % 4], "day")
        if theme or bar >= 8:
            pluck(s, bar, chord, 0.75 if busy else 0.6)
        if theme and bar % 2 == 0:
            s.bell("bell", bar, 0.0, chord[1][2] + 12, 0.6)
            s.bell("bell", bar, 2.5, chord[1][3] + 12, 0.45)
    if theme:
        for start in range(0, bars, 16):
            melody(s, THEME, start)
            if start + 8 < bars:
                melody(s, ANSWER, start + 8)
        if busy:
            # A second voice one octave lower, softer, in the second half.
            for start in range(8, bars, 16):
                melody(s, ANSWER, start, shift=-12, soft=0.8)
    air(s)
    return Result(s, {})


def bridge(seed: int, bars: int, style: str = "day") -> Result:
    """The second loop: its bells have the melody. The last bar is short (three beats)."""
    s = studio.Session(BPM, bars, seed=seed)
    motif = ((0.0, 69, 0.6), (1.5, 74, 0.5), (2.5, 77, 0.55), (3.5, 76, 0.4))
    for bar in range(bars):
        chord = BRIDGE[bar % 4]
        s.chord("pad", sound.PAD, bar, 0.0, 4.3, chord[1], 0.62)
        keys(s, bar, chord, "day")
        drums(s, bar, style, fill=bar == bars - 1)
        bass(s, bar, chord, BRIDGE[(bar + 1) % 4], "day")
        pluck(s, bar, chord, 0.45, shift=0)
        for beat, midi, level in motif:
            shift = (0, -1, 0, 0)[bar % 4] if midi in (74, 77) else 0
            s.bell("bell", bar, beat, midi + 12 + shift, level)
    air(s)
    return Result(s, {})


def gap(seed: int, chord: Chord) -> Result:
    """One bar of three beats: the music takes a short breath, and the bar line moves."""
    s = studio.Session(BPM, 1, beats=3, seed=seed, tail=5.0)
    s.chord("pad", sound.PAD, 0, 0.0, 3.2, chord[1], 0.55)
    s.keys("keys", 0, 0.0, 2.5, chord[2], 0.5, strum=0.04)
    s.hit("kick", 0, 0.0, 0.8)
    s.hit("rim", 0, 1.5, 0.5)
    s.hit("snare", 0, 2.0, 0.4)
    s.hit("snare", 0, 2.5, 0.6)
    s.hit("snare", 0, 2.75, 0.7)
    air(s)
    return Result(s, {})


def terminator(seed: int) -> Result:
    """The line between day and night: 12 bars. The drums go away and the key changes."""
    s = studio.Session(BPM, 12, seed=seed)
    chords = [DAY[0], DAY[1], DAY[2], DAY[3], DAY[0], DAY[1], DAY[2], DAY[0],
              NIGHT[0], NIGHT[1], NIGHT[0], NIGHT[1]]  # fmt: skip
    for bar, chord in enumerate(chords):
        s.chord("pad", sound.PAD, bar, 0.0, 4.3, chord[1], 0.6)
        keys(s, bar, chord, "day" if bar < 4 else "slow")
        if bar < 4:
            drums(s, bar, "day")
            bass(s, bar, chord, chords[bar + 1], "day")
        elif bar < 8:
            drums(s, bar, "light")
            bass(s, bar, chord, chords[bar + 1], "long")
        else:
            bass(s, bar, chord, chord, "long")
            lights(s, bar, chord, 2)
    melody(s, THEME[:14], 0, soft=0.85)
    air(s, (s.time(8), s.time(12)), -48.0)
    octaves = _ramp(s, 4, 9, 6.0, 2.3)
    return Result(s, {"sweep": 250.0 * 2.0**octaves})


def night(seed: int, bars: int) -> Result:
    """The night side: B-flat minor, slow drums, the lights of the cities, a slow melody."""
    s = studio.Session(BPM, bars, seed=seed)
    for bar in range(bars):
        chord = NIGHT[bar % 4]
        s.chord("pad", sound.PAD, bar, 0.0, 4.3, chord[1], 0.58)
        keys(s, bar, chord, "slow")
        if bar >= 4:
            drums(s, bar, "half", fill=False)
        bass(s, bar, chord, NIGHT[(bar + 1) % 4], "half" if bar >= 4 else "long")
        lights(s, bar, chord, 2 + bar // 6)
        if bar >= 8:
            pluck(s, bar, chord, 0.3, shift=12)
    for start in range(8, bars - 7, 8):
        melody(s, NOCTURNE, start)
    air(s)
    octaves = _ramp(s, 0, 6, 2.3, 6.0)
    return Result(s, {"sweep": 250.0 * 2.0**octaves})


def aurora(seed: int) -> Result:
    """The aurora: 16 bars with no drums. Plucked notes in groups of five against the beat."""
    s = studio.Session(BPM, 16, seed=seed)
    for bar in range(16):
        chord = NIGHT[bar % 4] if bar < 12 else RISE[bar % 4]
        s.chord("pad", sound.PAD, bar, 0.0, 4.4, chord[1], 0.66)
        s.chord("pad", sound.PAD, bar, 0.0, 4.4, (chord[1][0] + 12, chord[1][2] + 12), 0.45)
        keys(s, bar, chord, "slow")
        bass(s, bar, chord, chord, "long")
        # Five notes in the time of four beats: the figure moves against the bar.
        for number in range(5):
            midi = chord[1][(number * 2 + bar) % 4] + 12 + (12 if number == 3 else 0)
            level = 0.45 + 0.25 * np.sin(np.pi * bar / 15.0)
            s.chord("pluck", sound.PLUCK, bar, number * 0.8, 0.5, (midi,), level)
        if bar % 2 == 0:
            lights(s, bar, chord, 3)
    melody(s, NOCTURNE, 0, shift=0, soft=0.9)
    air(s, (s.time(10), s.time(16)), -50.0)
    return Result(s, {})


def sunrise(seed: int) -> Result:
    """The sunrise: 12 bars. The chord of A leads back to D minor, and the drums come back."""
    s = studio.Session(BPM, 12, seed=seed)
    chords = [RISE[0], RISE[1], RISE[2], RISE[3]] * 2 + [RISE[2], RISE[2], RISE[3], RISE[3]]
    for bar, chord in enumerate(chords):
        s.chord("pad", sound.PAD, bar, 0.0, 4.3, chord[1], 0.55 + 0.012 * bar)
        keys(s, bar, chord, "day" if bar >= 4 else "slow")
        bass(s, bar, chord, chords[min(bar + 1, 11)], "long" if bar < 8 else "day")
        pluck(s, bar, chord, 0.25 + 0.05 * bar)
        if bar >= 4:
            drums(s, bar, "light" if bar < 8 else "day", fill=bar == 11)
        if bar >= 8:
            for step in range(0, 16, 2 if bar < 10 else 1):
                s.hit("snare", bar, step / 4.0, 0.12 + 0.03 * (bar - 8) + 0.012 * step)
    air(s)
    octaves = _ramp(s, 0, 11, 4.0, 6.2)
    return Result(s, {"sweep": 250.0 * 2.0**octaves, "master": _ramp(s, 0, 11, 0.8, 1.0)})


def signal_end(seed: int) -> Result:
    """The end: 16 bars. The players go away one by one, and the tape stops."""
    s = studio.Session(BPM, 16, seed=seed, tail=8.0)
    for bar in range(16):
        chord = DAY[bar % 4]
        s.chord("pad", sound.PAD, bar, 0.0, 4.3, chord[1], 0.6 - 0.012 * bar)
        if bar < 12:
            keys(s, bar, chord, "day" if bar < 8 else "slow")
        if bar < 8:
            drums(s, bar, "day" if bar < 4 else "light")
            bass(s, bar, chord, DAY[(bar + 1) % 4], "day" if bar < 4 else "long")
        if bar < 6:
            pluck(s, bar, chord, 0.5 - 0.07 * bar)
        if bar % 2 == 0:
            lights(s, bar, chord, 1)
    melody(s, THEME, 0, soft=0.8)
    air(s, (s.time(8), s.time(16)), -48.0)
    octaves = _ramp(s, 6, 16, 6.0, 1.0)
    return Result(s, {"sweep": 250.0 * 2.0**octaves, "master": _ramp(s, 12, 16.5, 1.0, 0.0)})


# The sections of the piece, in sequence: the name, and the function that makes it.
SECTIONS = [
    ("signal", lambda seed: signal_start(seed)),
    ("day side", lambda seed: day(seed, 8, theme=False)),
    ("theme", lambda seed: day(seed, 16, theme=True)),
    ("second loop", lambda seed: bridge(seed, 15)),
    ("breath", lambda seed: gap(seed, BRIDGE[3])),
    ("terminator", lambda seed: terminator(seed)),
    ("night side", lambda seed: night(seed, 24)),
    ("aurora", lambda seed: aurora(seed)),
    ("sunrise", lambda seed: sunrise(seed)),
    ("day side again", lambda seed: day(seed, 32, theme=True, style="full", busy=True)),
    ("second loop again", lambda seed: bridge(seed, 15, style="full")),
    ("breath again", lambda seed: gap(seed, BRIDGE[3])),
    ("signal lost", lambda seed: signal_end(seed)),
]


def render(
    folder: Path = Path("build/audio"), first: int = 0, last: int | None = None
) -> tuple[Path, dict]:
    """Render the piece, or some of its sections. Return the MP3 file and the cue sheet."""
    chosen = SECTIONS[first:last]
    parts = []
    cues = {"bpm": BPM, "sections": [], "kicks": [], "snares": []}
    cursor = 0.0
    for number, (name, make) in enumerate(chosen, start=first):
        result = make(number + 1)
        s = result.session
        mix = studio.premix(s, result.automation)
        length = s.bars * s.beats * s.beat
        cues["sections"].append(
            {"name": name, "start": round(cursor, 3), "bars": s.bars, "beats": s.beats}
        )
        cues["kicks"].extend(round(cursor + moment, 3) for moment in s.kicks)
        parts.append((cursor, mix))
        print(f"{name}: {s.bars} bars, starts at {cursor:.1f} s", flush=True)
        cursor += length
    total = int(cursor * RATE) + max(len(mix) for _start, mix in parts)
    full = np.zeros((total, 2), dtype=np.float32)
    for start, mix in parts:
        offset = int(round(start * RATE))
        full[offset : offset + len(mix)] += mix
    full = full[: int((cursor + 7.0) * RATE)]
    whole = first == 0 and last is None
    if whole:
        full = tapefx.stop(full.astype(np.float64), 2.5).astype(np.float32)
        # Keep the mix before the master: a new master then needs no new mix.
        folder.mkdir(parents=True, exist_ok=True)
        np.save(folder / "premix.npy", full)
    return finish(full, cues, folder, "low-orbit" if whole else f"sections-{first}-{last}")


def remaster(folder: Path = Path("build/audio")) -> tuple[Path, dict]:
    """Make the master again from the mix that the last full render kept."""
    cues = json.loads((folder / "low-orbit.json").read_text(encoding="utf-8"))
    return finish(np.load(folder / "premix.npy"), cues, folder, "low-orbit")


def finish(full: np.ndarray, cues: dict, folder: Path, name: str) -> tuple[Path, dict]:
    """Make the master of a mix and write the audio files and the cue sheet."""
    audio, numbers = studio.master(full)
    cues["seconds"] = round(len(audio) / RATE, 3)
    cues["numbers"] = {key: round(value, 2) for key, value in numbers.items()}
    folder.mkdir(parents=True, exist_ok=True)
    flac = folder / f"{name}.flac"
    soundfile.write(str(flac), audio, RATE, subtype="PCM_24")
    mp3 = folder / f"{name}.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(flac), "-codec:a", "libmp3lame",
         "-q:a", "1", str(mp3)],
        check=True,
    )  # fmt: skip
    (folder / f"{name}.json").write_text(json.dumps(cues, indent=1), encoding="utf-8")
    print(cues["numbers"])
    return mp3, cues


if __name__ == "__main__":
    if sys.argv[1:2] == ["master"]:
        print(remaster()[0])
        sys.exit()
    arguments = [int(value) for value in sys.argv[1:]]
    print(render(first=arguments[0] if arguments else 0,
                 last=arguments[1] if len(arguments) > 1 else None)[0])  # fmt: skip
