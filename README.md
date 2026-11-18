# Low Orbit

*Low Orbit* is a piece of electronic music of about 8 minutes, with a film of low Earth orbit.
Code makes all parts of the work.

The music is in the style of Jake Chudnow and of related artists: warm analogue synthesizers,
a short loop of chords, a drum machine with swing, and the sound of old tape. The film looks
like a reel of 16 mm film. Its pictures are NASA footage of the Earth from the space station
and film of the Gemini and Apollo flights.

## Documents

| Document | Content |
|---|---|
| `design/brief.toml` | The request of the owner and the decisions |
| `docs/style-study.md` | The study of the style; the parameters and their values |
| `docs/work.md` | The form of the piece; the commands |
| `docs/film.md` | The look of the film; the sources and their credits |
| `research/footage.csv` | The address of each footage file |

## Make the work

```bash
uv sync
uv run python -m loworbit.piece     # the music
uv run python tools/footage.py      # the footage (6 GB)
uv run python -m loworbit.film      # the film
```

The film needs `ffmpeg`. The electric piano and the recorded drums need free sample libraries
in `.cache/samples`: jRhodes3d (the electric piano) and DRSKit (the drums). If DRSKit is not
there, the drums are only the drum machine.

## Credits of the samples

- Drum samples: DRSKit 2.1, the DrumGizmo team and DRSDrums (Deva and Lars Muldjord), licence
  CC BY 4.0, <https://www.drumgizmo.org>.
- Electric piano samples: jRhodes3d (a 1977 Rhodes Mark I).

## Licences

The code has the licence in `LICENSE`. The music and the film have the licence in
`LICENSE-CC-BY-4.0`. The footage is from NASA; see `docs/film.md`.
