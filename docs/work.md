# The work

*Low Orbit* is one orbit of the Earth in 8 minutes: the day side, the sunset, the night side
with its cities, the aurora, the sunrise, and the day side again. At the end the signal goes
away.

## The values of the music

| Parameter | Value |
|---|---|
| Tempo | 88 beats in a minute |
| Metre | 4/4; two bars have 3 beats (the "breath") |
| Swing | 12 % of a sixteenth note |
| Length | 486.5 seconds (8 minutes 6 seconds) |
| Loop of the day | B-flat maj9, C 6/9, D m9, A m11 (D minor) |
| Bridge | has A7 flat 9 (the colour of the Phrygian mode) |
| Loop of the night | B-flat m9, G-flat maj7, D-flat add9, A-flat 6 (B-flat minor) |
| Loudness | -12.4 LUFS; range 8.3 LU; peak -1.0 dB |

`docs/style-study.md` gives the reasons for these values.

## The form

| Number | Section | Start (seconds) | Bars | What you hear | What you see |
|---|---|---|---|---|---|
| 1 | signal | 0.0 | 8 | Tape hiss, satellite beeps, the pad comes from below a low-pass filter | Film leader, the title, film of 1965 to 1969 |
| 2 | day side | 21.8 | 8 | The loop of the day; light drums | The Earth in daylight |
| 3 | theme | 43.6 | 16 | The lead melody; the full drums | The Earth in daylight |
| 4 | second loop | 87.3 | 15 | The answer melody; the bridge | The Earth in daylight, less colour |
| 5 | breath | 128.2 | 1 (3 beats) | Almost no sound | Old film |
| 6 | terminator | 130.2 | 12 | The drums at half speed; the filter closes | The sunset line |
| 7 | night side | 163.0 | 24 | The loop of the night; the electric piano; a slow melody | Cities at night |
| 8 | aurora | 228.4 | 16 | Bells and plucked notes; no kick drum at first | The aurora |
| 9 | sunrise | 272.0 | 12 | The filter opens; the chords go up to D minor | The sunrise on the limb |
| 10 | day side again | 304.8 | 32 | All instruments; the busy drums | The Earth in daylight |
| 11 | second loop again | 392.0 | 15 | The answer melody, with more colour | The Earth in daylight, more colour |
| 12 | breath again | 433.0 | 1 (3 beats) | Almost no sound | Old film |
| 13 | signal lost | 435.0 | 16 | The instruments go away; the tape stops | A rocket stage falls; the dark Earth |

## Commands

```bash
uv run python -m loworbit.piece     # the music: build/audio/low-orbit.flac, .mp3, .json
uv run python tools/footage.py      # get the footage (6 GB) to .cache/footage
uv run python -m loworbit.film      # the film: build/video/low-orbit.mp4
```

The film needs the cue sheet of the music (`build/audio/low-orbit.json`). Make the music first.
