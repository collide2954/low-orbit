"""The first sketch of Low Orbit: one minute, to test the sound of the instruments.

Run: uv run python -m loworbit.sketch
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import soundfile

from . import sound, studio, tapefx
from .audio import dsp

RATE = dsp.RATE
BPM = 88.0
BARS = 24

# The four chords of the loop: the bass note, the notes of the pad, the notes of the piano.
CHORDS = [
    (34, (62, 65, 69, 72), (57, 60, 62, 65)),  # B-flat major 9
    (36, (64, 67, 69, 74), (55, 57, 62, 64)),  # C 6/9
    (38, (65, 69, 72, 76), (53, 57, 60, 64)),  # D minor 9
    (33, (64, 67, 72, 74), (55, 60, 62, 64)),  # A minor 11
]

# The melody of the lead, for bars 12 to 19: (bar, beat, length, note, loudness, legato).
MELODY = [
    (12, 0.5, 0.5, 69, 0.7, False), (12, 1.0, 0.5, 72, 0.7, True), (12, 1.5, 1.5, 74, 0.8, True),
    (12, 3.0, 0.5, 77, 0.8, True), (12, 3.5, 0.5, 76, 0.7, True),
    (13, 0.0, 2.0, 74, 0.75, True), (13, 3.0, 0.5, 67, 0.6, False), (13, 3.5, 0.5, 69, 0.65, True),
    (14, 0.0, 1.5, 72, 0.75, True), (14, 1.5, 2.5, 69, 0.7, True),
    (15, 1.0, 0.5, 76, 0.75, False), (15, 1.5, 0.5, 74, 0.7, True), (15, 2.0, 1.0, 72, 0.7, True),
    (15, 3.0, 1.0, 69, 0.65, True),
    (16, 0.0, 0.5, 69, 0.7, False), (16, 0.5, 0.5, 72, 0.7, True), (16, 1.0, 1.5, 74, 0.8, True),
    (16, 2.5, 1.0, 81, 0.85, True), (16, 3.5, 0.5, 79, 0.75, True),
    (17, 0.0, 3.0, 76, 0.8, True), (17, 3.0, 0.5, 74, 0.65, True), (17, 3.5, 0.5, 72, 0.65, True),
    (18, 0.0, 4.0, 74, 0.75, True),
    (19, 0.0, 2.5, 69, 0.6, True),
]  # fmt: skip

# One bar of the drums: the sixteenth notes with a stroke, and the loudness of each.
KICK = {0: 0.9, 7: 0.55, 10: 0.8}
SNARE = {4: 0.85, 12: 0.9, 15: 0.25}
HATS = {0: 0.5, 2: 0.7, 3: 0.3, 4: 0.5, 6: 0.7, 8: 0.5, 10: 0.7, 11: 0.3, 12: 0.5, 14: 0.75}


def drums(session: studio.Session, bar: int, fill: bool = False) -> None:
    kick = dict(KICK)
    snare = dict(SNARE)
    if bar % 4 == 3:
        kick[14] = 0.6
        snare[9] = 0.2
    if fill:
        snare.update({13: 0.35, 14: 0.5})
    for step, level in kick.items():
        session.hit("kick", bar, step / 4.0, level)
    for step, level in snare.items():
        session.hit("snare", bar, step / 4.0, level, late=0.009)
    for step, level in HATS.items():
        session.hit("open" if step == 14 and bar % 2 == 1 else "hat", bar, step / 4.0, level)


def compose() -> studio.Session:
    session = studio.Session(BPM, BARS)
    random = session.random("pluck")
    for bar in range(BARS):
        root, pad, keys = CHORDS[bar % 4]
        last = bar >= 20
        # The pad: one chord in each bar.
        session.chord("pad", sound.PAD, bar, 0.0, 4.3, pad, 0.62 if bar >= 4 else 0.5)
        # The electric piano: three chords in a bar, off the beat.
        if bar >= 2:
            session.keys("keys", bar, 0.0, 1.4, keys, 0.55)
            session.keys("keys", bar, 1.5, 0.5, keys[1:], 0.4)
            session.keys("keys", bar, 2.75, 1.1, keys, 0.5)
        if 4 <= bar < 20:
            drums(session, bar, fill=bar in (11, 19))
            following = CHORDS[(bar + 1) % 4][0]
            session.line(
                "bass",
                sound.BASS,
                [
                    (bar, 0.0, 1.3, root, 0.85, False),
                    (bar, 1.75, 0.5, root, 0.7, False),
                    (bar, 2.5, 1.0, root + 12 if bar % 4 == 2 else root, 0.75, False),
                    (bar, 3.5, 0.45, (root + following) // 2 + 1, 0.6, False),
                ],
            )
        elif bar == 3:
            session.hit("snare", bar, 3.25, 0.3)
            session.hit("snare", bar, 3.5, 0.5)
            session.hit("hat", bar, 3.0, 0.5)
            session.hit("hat", bar, 3.75, 0.6)
        elif last:
            session.line("bass", sound.BASS, [(bar, 0.0, 3.5, root, 0.7, False)])
        # The pluck: sixteenth notes through the chord, with some notes left out.
        if 8 <= bar < 20:
            order = (0, 2, 1, 3, 2, 0, 3, 1, 0, 3, 2, 1, 3, 2, 0, 1)
            for step in range(16):
                if random.uniform() < 0.3:
                    continue
                midi = pad[order[(step + bar) % 16]] + 12
                level = 0.75 if step % 4 == 0 else 0.5 + 0.15 * random.uniform()
                session.chord(
                    "pluck", sound.PLUCK, bar, step / 4.0, 0.2, (midi,), level, swung=True
                )
        # The bells: single high notes.
        if bar >= 12 and bar % 2 == 0:
            session.bell("bell", bar, 0.0, pad[2] + 12, 0.6)
            session.bell("bell", bar, 2.5, pad[3] + 12, 0.45)
    session.line("lead", sound.LEAD, MELODY)
    # The air: tape hiss, crackle, and the tones of a satellite at the start.
    total = session.total
    air = tapefx.hiss(total) + tapefx.crackle(total)
    signal_length = int(session.time(5) * RATE)
    tones = tapefx.beeps(signal_length, session.beat * 2.0)
    tones *= np.linspace(1.0, 0.0, signal_length)[:, None]
    air[:signal_length] += tones
    session.add("air", air, 0.0)
    return session


def render(folder: Path = Path("build/audio"), name: str = "sketch") -> Path:
    session = compose()
    total = session.total
    time = np.arange(total) / RATE
    # The start comes out of a low-pass filter: a level curve here, and the filter below.
    fade_in = np.clip(time / session.time(2), 0.0, 1.0) ** 1.5
    fade_out = np.clip((session.time(BARS) + 3.0 - time) / 6.0, 0.0, 1.0)
    audio, numbers = studio.mixdown(session, {"master": fade_in * fade_out})
    folder.mkdir(parents=True, exist_ok=True)
    flac = folder / f"{name}.flac"
    soundfile.write(str(flac), audio, RATE, subtype="PCM_24")
    mp3 = folder / f"{name}.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(flac), "-codec:a", "libmp3lame",
         "-q:a", "1", str(mp3)],
        check=True,
    )  # fmt: skip
    print({key: round(value, 2) for key, value in numbers.items()})
    return mp3


if __name__ == "__main__":
    print(render())
