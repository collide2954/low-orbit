# The film

The film looks like a strip of 16 mm film that goes through a projector. Code makes each frame
(`src/loworbit/film.py`).

## The look

| Item | Value |
|---|---|
| Size | 1920 x 1080 pixels, 24 frames in a second |
| Picture | 4:3 (1296 x 972 pixels) in a gate with round corners |
| Strip | Holes for the sprockets on the left; an optical sound track on the right |
| Sound track | The picture of the track comes from the real audio of the moment |
| Grain | New for each frame; most in the middle tones |
| Dirt | Dust, scratches, light leaks |
| Splice | A white flash and a jump of the picture at the start of each section |
| Lamp | The brightness moves a little with each kick drum |
| Captions | Typewriter letters at the start of a section |

## How the film is not regular

- The cuts are on the beats of the music. The lengths of the shots are a cycle of 16 different
  lengths (1 to 9 beats). The cycle does not agree with the bars.
- One shot in seven is a photograph: one frame with a white border that turns slowly.
- One shot in eleven goes backwards.
- One shot in nine is film of the 1960s between the new pictures.
- One shot in eight has the look of a different section.
- The gate moves a little in each frame.

## The sources

All footage is from NASA. NASA footage is in general not copyrighted (see
<https://www.nasa.gov/nasa-brand-center/images-and-media/>). NASA does not endorse this work.
The files are not in the repository; `tools/footage.py` gets them. `research/footage.csv` has
the address of each file.

| Use in the film | Title | Date | NASA identifier |
|---|---|---|---|
| Day, night, aurora, dawn, dusk | Earth from Space in 4K – Expedition 65 Edition | 2022-08-05 | jsc2022m000172 |
| Day, night, aurora, dawn, dusk | Earth in 4K – Space Station Expedition 67-68 Edition | 2023-04-21 | jsc2023m000111 |
| Old film (1965 to 1969) | Mercury Gemini Apollo Resource Reel 1 | 2019-05-20 | HD 049 |

Three more files are in the cache but the film does not use them now: 4K Earth Views Extended
Cut (2021), Earth Views from the International Space Station (2019), ISS Airglow (2018).

## Known faults

- The times of some clips come from a contact sheet with one picture each 25 seconds. A clip
  can thus contain a cut of its source.
- The "photographs" are frames of the films, not photographs from a still camera.
- The encoder is OpenH264 at 18 Mbit/s (this computer has no x264). Grain can show blocks.
