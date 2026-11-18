# Style study: the music of Jake Chudnow and of related artists

This document gives the style of the model as parameters and values. The work *Low Orbit* uses these values. It does not copy a melody, a chord sequence, or a sound of a published track.

## Evidence

Each row has a code for its evidence.

| Code | Meaning |
| --- | --- |
| R | Read: a source says it. The source is in the column "Source". |
| K | Reference knowledge of the assistant that wrote the study: a known property of the style, the instrument, or the method. No measurement of a recording is behind it. |
| M | Measured: the project measured it in audio (see "S5"). |

## Limits

- Public writing about how Jake Chudnow makes his music is small. The study found one analysis of one track (tempo, key, chords), three short descriptions, and one note of the artist.
- The owner of the project told the project to get recordings of the model. The script `tools/reference.py` got 14 tracks from the SoundCloud page of the artist and measured them (see "S5"). The recordings stay in a local cache. They are not in the repository, and the work uses none of their sound.
- The measurement gives the tempo, the key, the loudness, the tone balance, and the stereo width. It does not give the swing or the pitch drift: the rows for these keep the code K.
- The assistant cannot hear. The measured values of the work (loudness, tone balance, level of each track) are checks of numbers, not a judgment of the sound.

## S1. The model: what the sources say

| Fact | Value | Evidence | Source |
| --- | --- | --- | --- |
| Who | Musician from New York, lives in London; producer, drummer, and film maker; born about 1987 | R | Last.fm, artist page |
| Known for | The music of the science channel Vsauce | R | Electronic Sound, "Pulse", 10 June 2021 (headline); Tildes, thread "Moon Men" |
| Instruments | "analogue synthesisers, drum machines, found sounds and samples drawn from his own drum recordings" | R | Resident Advisor, biography (in the summary of a search engine) |
| Synthesizer of "Olive" | Most sounds are a Roland Juno-6; some software synthesizers; layered drums | R | Description of the video "Olive" (in the summary of a search engine) |
| Mood | "lush and melancholy"; pensive, nostalgic; music for headphones | R | Reviews (in the summary of a search engine) |
| Size of the work | More than 300 tracks in about 20 years; most are not released | R | Resident Advisor, biography |
| "Moon Men": tempo and metre | 93 quarter notes in a minute, 4/4 | R | Hooktheory, TheoryTab "Moon Men (Instrumental)" |
| "Moon Men": key | D Phrygian dominant (the fifth mode of G harmonic minor) | R | Hooktheory |
| "Moon Men": chords | Three chords in a loop; the most used chord is a diminished chord on the third step | R | Hooktheory |
| "Moon Men": melody | Range of 14 semitones, mostly steps, repeated notes, "punchy" syncopation, 3 notes in a beat | R | Hooktheory |
| "Moon Men": length | About 1 minute 33 seconds | R | Tildes |
| "Shona": harmony | A cycle of three chords for the full track | R | Beautiful Song of the Week, week 791 |
| "Shona": form | It fades in with only its low frequencies ("music from a passing car"); layers of percussion and synthesizers come one by one; at about 2:30 the cycle breaks for a moment and comes back | R | Beautiful Song of the Week |
| "Dream": method | A melody from a dream, recorded at night, finished one year later | R | Bandcamp, note of the artist |
| Tags of the artist | electronic, experimental, cinematic, synth, headphone music | R | Bandcamp |

## S2. Related artists

The reference lists of listeners put these artists near the model. Each has one property that the work uses.

| Artist | Property | Evidence |
| --- | --- | --- |
| Boards of Canada | Synthesizers with unsteady pitch (tape wow), detuned pairs of oscillators, old educational film as a picture of the sound, hip-hop drums below soft chords | K |
| Tycho | Clean, wide pads and plucked figures with echo; a picture of landscape and sun | K |
| Bibio | Tape hiss and flutter as part of the instrument | K |
| Air ("Moon Safari") | Electric piano, soft analog bass, space as a subject | K |
| Com Truise, Lone | Bright synthesizer chords of the 1980s over slow, heavy drums | K |
| Teebs, Shlohmo | Layers of percussion and found sound; loose timing | K |

## S3. The parameters of the style, and the values of this work

| Parameter | Style | Value in *Low Orbit* | Evidence |
| --- | --- | --- | --- |
| Tempo | 80 to 100 quarter notes in a minute; "Moon Men" has 93 | 88 | R, K |
| Metre | 4/4 | 4/4, with some bars of a different length (see the plan of the work) | R |
| Timing of the drums | Each second sixteenth note is late (swing of hip-hop); the snare drum is a little behind the beat; no stroke is exactly on the grid | Swing 12 percent of a sixteenth note; snare drum 9 ms late; each stroke moves by about 3.5 ms | K |
| Drum sound | A drum machine with recorded drums on top; dull, with saturation; a short room | Drum machine in code (the recorded drums on top are not made yet); saturation; low-pass filter at 11.5 kHz; parallel compressor | R, K |
| Harmony | A loop of three or four chords; minor keys and modes; chords with a seventh and a ninth; one "wrong" note that gives the colour | Loops of four chords in D minor; a second part in a far key; the Phrygian second step as the colour note | R, K |
| Melody | Short, with repeated notes and steps; syncopation; one clear leap | As the style; the leap is a fifth up | R |
| Pad | A polyphonic analog synthesizer (Juno-6): one oscillator with saw and pulse, a sub oscillator, a low-pass filter with a slow envelope, a chorus | A model of that instrument: saw, pulse with a slow change of its width, sub oscillator, ladder filter, chorus with two rates | R, K |
| Lead | One voice, a slide between the notes, a late vibrato, a pitch that is never steady | Slide of 90 ms, vibrato of 16 cents at 5.1 Hz after 0.32 s, random drift of 11 cents | K |
| Electric piano | Soft chords off the beat, with tremolo between left and right | Samples of a 1977 Rhodes; tremolo of 4.6 Hz | K |
| Bass | A soft, round tone on the root of the chord; it leaves room for the kick drum | Triangle and sine below 260 Hz; the kick drum pushes it down by 2 dB | K |
| Tape | Slow wow, fast flutter, hiss | Wow of 7 cents below 1.3 Hz, flutter of 1.6 cents at 6 to 9 Hz, hiss at -52 dB | K |
| Space | A dark plate reverb; an echo of three sixteenth notes | Plate of 2.8 s; echo with 42 percent feedback | K |
| Form | A filter opens at the start; layers come one by one; a break; the loop comes back | As the style, for 8 minutes: see the plan of the work | R |
| Loudness of the master | -15 to -7 LUFS; the middle value is -9.9 | -12 LUFS integrated, peak below -1 dB (between the model and the -14 of the streaming services) | M |
| Tone balance of the master | Dark: in relation to the octave of 1 kHz, the octave of 4 kHz is at -4.5 dB and the octave of 8 kHz at -10 dB | The master has filters that give these values (see "S5") | M |

## S5. Measurements of 14 recordings of the model

The table `research/reference.csv` has all numbers. The tracks: Banana, Columbia, Darwin, Flan, Going Down, Hanami, Hydrogen, Olive, Pines and Pavement, Pressed Pennies, Shallow Anne, Shona, You Could Sunbathe in this Storm, Turquoise.

| Parameter | Smallest | Middle | Largest | *Low Orbit*, first master | Decision |
| --- | --- | --- | --- | --- | --- |
| Loudness (LUFS) | -15.1 | -9.9 | -7.3 | -14.0 | Make it -12 |
| Loudness range (LU) | 0.7 | 4.8 | 11.1 | 11.0 | No change: the piece has a quiet start and a quiet end |
| Octave of 63 Hz (dB, in relation to 1 kHz) | 1.2 | 9.0 | 16.8 | 15.1 | Decrease by 5 dB |
| Octave of 125 Hz | -1.4 | 7.7 | 17.0 | 7.8 | No change |
| Octave of 250 Hz | -1.8 | 8.3 | 12.4 | 7.0 | No change |
| Octave of 500 Hz | -0.4 | 2.8 | 10.0 | 1.6 | Increase by 1 dB |
| Octave of 2 kHz | -6.1 | -2.5 | 1.4 | 0.1 | Decrease by 2 dB |
| Octave of 4 kHz | -14.0 | -4.5 | 4.5 | 0.4 | Decrease by 5 dB |
| Octave of 8 kHz | -28.8 | -9.8 | 2.5 | -3.5 | Decrease by 6 dB |
| Side signal (dB, in relation to the middle signal) | -20.7 | -11.9 | -3.2 | -14.4 | No change |

- The first master of *Low Orbit* was too bright and had too much of the lowest octave. The model has the tone of old tape: the high range falls fast.
- The tempo that the script finds is between 70 and 140. It can be half or two times the real tempo. Slow tracks are there (Darwin 88, Pines and Pavement 95, Hydrogen 103), thus 88 is in the style.
- 10 of the 14 tracks are in a minor key. Olive and Pressed Pennies are in D minor, as is *Low Orbit*.

## S4. Sources

| Source | Address |
| --- | --- |
| Hooktheory, TheoryTab "Moon Men (Instrumental)" | https://www.hooktheory.com/theorytab/view/jake-chudnow/moon-men-(instrumental) |
| Beautiful Song of the Week, week 791: "Shona" | https://www.beautifulsongoftheweek.com/week-791-shona-by-jake-chudnow/ |
| Bandcamp, Jake Chudnow, "Dream" | https://jakechudnow.bandcamp.com/ |
| Electronic Sound, "Pulse: Jake Chudnow" (the text is not public) | https://electronicsound.co.uk/the-regulars/pulse/jake-chudnow/ |
| Resident Advisor, biography (the page gave no access) | https://ra.co/dj/jakechudnow/biography |
| Tildes, thread "jake chudnow - moon men" | https://tildes.net/~music/m9o/jake_chudnow_moon_men |
| Last.fm, artist page | https://www.last.fm/music/Jake+Chudnow |
| YouTube, "Olive" by Jake Chudnow | https://www.youtube.com/watch?v=3QQS8fJqXoI |
