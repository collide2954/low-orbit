"""The film of Low Orbit: a reel of footage and photographs of low Earth orbit.

The picture is a strip of 16 mm film in a projector: a frame with round
corners, the holes of the film at the left, and the optical sound track at
the right (the white line is the real sound of the music at that moment).
The film has the faults of an old reel, and the music controls them:

- The cuts are on the beats of the music. The lengths of the shots are not
  regular: the list `LENGTHS` gives them in beats.
- Each kick drum makes the lamp of the projector a little brighter.
- A new section starts with a splice: one white frame and a jump of the picture.
- The picture moves in the gate, and it slips at some places.
- Grain, dust, scratches, light that leaks in, and colours that are not the
  same from shot to shot.
- Some frames stay as photographs: a white border, and a slow move into the picture.

Run: uv run python -m loworbit.film [first second] [last second]
"""

from __future__ import annotations

import json
import math
import multiprocessing
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FPS = 24
WIDTH, HEIGHT = 1920, 1080
STRIP_X, STRIP_W = 232, 1456  # the film strip on the screen
PICTURE_X, PICTURE_W, PICTURE_H = 80, 1296, 972  # the picture on the strip
PICTURE_Y = (HEIGHT - PICTURE_H) // 2
TRACK_X, TRACK_W = PICTURE_X + PICTURE_W + 14, 52  # the sound track on the strip
FOOTAGE = Path(".cache/footage")
FONT = "/home/brettgilio/.local/share/fonts/cmuntt.otf"
FALLBACK_FONT = "/usr/share/fonts/urw-base35/NimbusMonoPS-Bold.otf"

# The lengths of the shots in beats, in a cycle: not regular.
LENGTHS = (8, 5, 3, 8, 2, 6, 1, 4, 7, 3, 5, 2, 9, 4, 1, 6)


@dataclass(frozen=True)
class Clip:
    """A part of a source file that the film can use: the file, and its first and last second."""

    source: str  # a part of the file name
    first: float
    last: float
    speed: float = 3.0  # how much faster than the source the film shows it


# The clips of each kind of picture. The times come from the contact sheets of the sources.
E65 = "Expedition_65"
E67 = "Expedition_67_68"
OLD = "Mercury_Gemini_Apollo"


def _clips(source: str, speed: float, *ranges: tuple[float, float]) -> list[Clip]:
    return [Clip(source, first, last, speed) for first, last in ranges]


def _near(source: str, speed: float, *moments: float) -> list[Clip]:
    """Clips near the moments of a coarse contact sheet (a picture each 25 seconds)."""
    return [Clip(source, moment - 4.0, moment + 6.0, speed) for moment in moments]


POOLS: dict[str, list[Clip]] = {
    "day": _clips(
        E65, 3.0, (22, 98), (262, 282), (342, 382), (442, 482), (562, 582), (602, 642),
        (702, 722), (782, 842), (982, 996), (1002, 1062), (1162, 1222), (1262, 1282),
        (1322, 1382), (1402, 1542), (1562, 1582),
    )
    + _near(
        E67, 3.0, 450, 475, 600, 625, 650, 750, 1325, 1375, 1525, 2125, 2275, 3025, 3075,
        1600, 1625, 1850, 1875, 2625, 2650, 2675, 2725, 2750, 250,
    ),
    "night": _clips(E65, 1.5, (497, 512), (742, 762), (882, 902), (1657, 1672))
    + _near(E65, 1.5, 1980, 2240, 2320, 2540, 2960)
    + _near(
        E67, 1.5, 100, 800, 2200, 2225, 2250, 2325, 2350, 2375, 2575, 2600, 2700, 2775, 2900,
        2925,
    ),
    "aurora": _clips(
        E65, 1.8, (122, 162), (202, 222), (402, 422), (522, 542), (922, 932), (962, 972),
        (1102, 1122), (1242, 1252), (1302, 1312), (1602, 1612), (1920, 1940),
    )
    + _near(E65, 1.8, 2440, 2640, 2840, 2940)
    + _near(E67, 1.8, 225, 525, 550, 725, 1725, 1975, 2425, 2550),
    "dawn": _clips(E65, 1.5, (178, 188), (1138, 1148))
    + _near(E67, 1.5, 275, 1775, 2025, 2175, 2400, 2975, 3000, 3125),
    "dusk": _clips(E65, 1.8, (242, 252), (302, 322), (1082, 1092), (1622, 1648))
    + _near(E65, 1.8, 2580, 2660)
    + _near(E67, 1.8, 25, 50, 75, 125, 150, 1200, 1500, 1800, 1825, 2800, 2825),
    # Film of the years 1965 to 1969 (Gemini and Apollo), at its own speed.
    "old": _clips(
        OLD, 1.0, (1909, 1927), (1937, 1949), (2188, 2196), (2196, 2210), (2212, 2246),
        (2515, 2524), (2525, 2529), (2595, 2609), (2620, 2629), (2630, 2644), (2920, 2944),
        (2950, 2990), (3030, 3044), (3415, 3432), (3435, 3450), (3470, 3498), (3500, 3512),
        (3540, 3554),
    ),
    # The last section: things that go away.
    "fall": _clips(OLD, 1.0, (2990, 3035), (2840, 2905), (2196, 2210), (3540, 3554))
    + _clips(E65, 1.8, (1622, 1648), (302, 322))
    + _near(E67, 1.8, 1200, 1500, 2800),
}  # fmt: skip

# The kind of picture and the look of each section of the music.
LOOKS = {
    "signal": ("old", "print"),
    "day side": ("day", "warm"),
    "theme": ("day", "warm"),
    "second loop": ("day", "faded"),
    "breath": ("old", "print"),
    "terminator": ("dusk", "faded"),
    "night side": ("night", "cold"),
    "aurora": ("aurora", "vivid"),
    "sunrise": ("dawn", "warm"),
    "day side again": ("day", "warm"),
    "second loop again": ("day", "vivid"),
    "breath again": ("old", "print"),
    "signal lost": ("fall", "faded"),
}

# The words on the picture at the start of a section.
CAPTIONS = {
    "day side": "REV 1   DAY SIDE   ALT 408 KM",
    "theme": "VEL 7.66 KM/S   PERIOD 92.7 MIN",
    "terminator": "TERMINATOR   LOCAL SUNSET",
    "night side": "NIGHT SIDE   CITY LIGHTS",
    "aurora": "AURORA AUSTRALIS   LAT 51.6 S",
    "sunrise": "SUNRISE 16 OF 16",
    "day side again": "REV 2   DAY SIDE",
    "signal lost": "LOSS OF SIGNAL",
}

# Each look: gain of red, green, and blue; saturation; black level; contrast; grain.
GRADES = {
    "warm": ((1.06, 1.0, 0.9), 0.85, 0.035, 1.05, 0.045),
    "faded": ((1.02, 1.0, 0.95), 0.6, 0.07, 0.92, 0.055),
    "cold": ((0.92, 1.0, 1.1), 0.8, 0.02, 1.12, 0.07),
    "vivid": ((1.0, 1.04, 1.06), 1.25, 0.02, 1.1, 0.06),
    "sepia": ((1.1, 1.0, 0.82), 0.15, 0.06, 1.0, 0.07),
    "print": ((1.03, 1.0, 0.96), 1.05, 0.03, 1.04, 0.03),  # for film that has its own grain
}


@dataclass(frozen=True)
class Shot:
    """One shot of the film: its frames on the screen, and the clip that it shows."""

    first: int  # the first frame on the screen
    last: int  # the frame after its last frame
    clip: Clip
    offset: float  # seconds into the clip
    look: str
    photograph: bool = False  # the shot is one frame that stays
    backwards: bool = False
    section_start: bool = False
    caption: str = ""


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in (FONT, FALLBACK_FONT):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def source_file(name: str) -> Path:
    found = sorted(path for path in FOOTAGE.glob("*.mp4") if name in path.name)
    if not found:
        raise FileNotFoundError(f"no footage with '{name}' in {FOOTAGE}")
    return found[0]


def plan(cues: dict, seed: int = 7) -> list[Shot]:
    """Make the list of the shots from the cue sheet of the music."""
    random = np.random.default_rng(seed)
    beat = 60.0 / cues["bpm"]
    sections = cues["sections"]
    shots: list[Shot] = []
    number = 0
    used: dict[str, int] = {}
    for index, section in enumerate(sections):
        start = section["start"]
        end = sections[index + 1]["start"] if index + 1 < len(sections) else cues["seconds"]
        pool_name, look = LOOKS.get(section["name"], ("day", "warm"))
        pool = POOLS.get(pool_name) or POOLS["day"]
        moment = start
        first_of_section = True
        while moment < end - 0.05:
            length = LENGTHS[number % len(LENGTHS)] * beat
            stop = min(end, moment + length)
            if end - stop < 0.9 * beat:
                stop = end
            # One shot in nine is a memory: film of the 1960s in the middle of the new pictures.
            memory = number % 9 == 3 and pool_name not in ("old", "fall")
            name = "old" if memory else pool_name
            pool_now = POOLS[name] if memory else pool
            count = used.get(name, 0)
            # The step has no common factor with the size of the pool: no clip comes twice
            # before all the clips have come.
            step = next(n for n in (5, 7, 3, 1) if math.gcd(n, len(pool_now)) == 1)
            clip = pool_now[(count * step) % len(pool_now)]
            used[name] = count + 1
            if clip.source == OLD and look != "print":
                look_now = "print"
            else:
                look_now = look if random.uniform() > 0.12 else str(random.choice(list(GRADES)))
            # A shot that is longer than its clip shows the clip more slowly.
            need = (stop - moment) * clip.speed
            if need > clip.last - clip.first:
                clip = Clip(
                    clip.source, clip.first, clip.last, (clip.last - clip.first) / (stop - moment)
                )
            room = max(clip.last - clip.first - (stop - moment) * clip.speed, 0.0)
            shots.append(
                Shot(
                    int(round(moment * FPS)),
                    int(round(stop * FPS)),
                    clip,
                    float(random.uniform(0.0, room)),
                    look_now,
                    photograph=number % 7 == 4,
                    backwards=number % 11 == 6,
                    section_start=first_of_section,
                    caption=CAPTIONS.get(section["name"], "") if first_of_section else "",
                )
            )
            first_of_section = False
            number += 1
            moment = stop
    return shots


# ----------------------------------------------------------------------------
# The frames of the sources
# ----------------------------------------------------------------------------


def read_frames(shot: Shot, first: int, count: int) -> np.ndarray:
    """Read `count` frames of a shot, from its frame `first`. Return them as numbers 0 to 1."""
    clip = shot.clip
    total = shot.last - shot.first
    if shot.photograph:
        first, count_read = 0, 1
    elif shot.backwards:
        first, count_read = total - first - count, count
    else:
        count_read = count
    start = clip.first + shot.offset + max(first, 0) / FPS * clip.speed
    chain = (
        f"setpts=PTS/{clip.speed},fps={FPS},crop=ih*4/3:ih,"
        f"scale={PICTURE_W}:{PICTURE_H}:flags=bicubic"
    )
    command = [
        "ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", str(source_file(clip.source)),
        "-an", "-vf", chain, "-frames:v", str(count_read), "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-",
    ]  # fmt: skip
    data = subprocess.run(command, capture_output=True, check=True).stdout
    size = PICTURE_W * PICTURE_H * 3
    got = len(data) // size
    if got == 0:
        return np.zeros((count, PICTURE_H, PICTURE_W, 3), dtype=np.float32)
    frames = np.frombuffer(data[: got * size], dtype=np.uint8).reshape(got, PICTURE_H, PICTURE_W, 3)
    frames = frames.astype(np.float32) / 255.0
    if got < count:
        frames = np.concatenate([frames, np.repeat(frames[-1:], count - got, axis=0)])
    if shot.backwards and not shot.photograph:
        frames = frames[::-1]
    return frames


# ----------------------------------------------------------------------------
# The look of the film
# ----------------------------------------------------------------------------

_Y, _X = np.mgrid[0:PICTURE_H, 0:PICTURE_W].astype(np.float32)
_RADIUS = np.hypot((_X - PICTURE_W / 2) / (PICTURE_W / 2), (_Y - PICTURE_H / 2) / (PICTURE_H / 2))
VIGNETTE = (1.0 - 0.32 * np.clip(_RADIUS - 0.35, 0.0, None) ** 1.6)[:, :, None]


def _gate() -> np.ndarray:
    """Return the shape of the picture: 1 inside, 0 outside, with round corners."""
    mask = Image.new("L", (PICTURE_W, PICTURE_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PICTURE_W - 1, PICTURE_H - 1), 34, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.5))
    return (np.asarray(mask, dtype=np.float32) / 255.0)[:, :, None]


GATE = _gate()


def grade(frame: np.ndarray, look: str) -> np.ndarray:
    gains, saturation, black, contrast, _grain = GRADES[look]
    grey = frame @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    out = grey[:, :, None] + (frame - grey[:, :, None]) * saturation
    out = out * np.array(gains, dtype=np.float32)
    out = (out - 0.5) * contrast + 0.5
    return black + (1.0 - black) * np.clip(out, 0.0, 1.0)


def halation(frame: np.ndarray, amount: float = 0.35) -> np.ndarray:
    """Make a soft red light around the bright places, as film does."""
    small = Image.fromarray((np.clip(frame, 0, 1) * 255).astype(np.uint8)).resize(
        (PICTURE_W // 6, PICTURE_H // 6), Image.BILINEAR
    )
    glow = np.asarray(small.filter(ImageFilter.GaussianBlur(5)), dtype=np.float32) / 255.0
    glow = np.clip(glow - 0.55, 0.0, None) * np.array([1.0, 0.45, 0.25], dtype=np.float32)
    glow = (
        np.asarray(
            Image.fromarray((np.clip(glow * 2.0, 0, 1) * 255).astype(np.uint8)).resize(
                (PICTURE_W, PICTURE_H), Image.BILINEAR
            ),
            dtype=np.float32,
        )
        / 255.0
    )
    return frame + amount * glow


def photograph(frame: np.ndarray, share: float, random: np.random.Generator) -> np.ndarray:
    """Show one frame as a photograph on a table: a white border and a slow move in."""
    zoom = 1.0 + 0.1 * share
    image = Image.fromarray((np.clip(frame, 0, 1) * 255).astype(np.uint8))
    width, height = int(PICTURE_W * 0.74 * zoom), int(PICTURE_H * 0.74 * zoom)
    print_ = Image.new("RGB", (width + 44, height + 60), (236, 232, 220))
    print_.paste(image.resize((width, height), Image.BICUBIC), (22, 22))
    print_ = print_.rotate(-2.2 + 0.5 * share, expand=True, resample=Image.BICUBIC,
                           fillcolor=(14, 13, 12))  # fmt: skip
    table = Image.new("RGB", (PICTURE_W, PICTURE_H), (14, 13, 12))
    table.paste(print_, ((PICTURE_W - print_.width) // 2, (PICTURE_H - print_.height) // 2))
    return np.asarray(table, dtype=np.float32) / 255.0


def dirt(frame: np.ndarray, random: np.random.Generator, amount: float) -> np.ndarray:
    """Put dust, hairs, and scratches on a frame."""
    layer = Image.new("L", (PICTURE_W, PICTURE_H), 0)
    draw = ImageDraw.Draw(layer)
    for _ in range(random.poisson(5 * amount)):
        x, y = random.integers(0, PICTURE_W), random.integers(0, PICTURE_H)
        size = int(random.integers(1, 5))
        draw.ellipse((x, y, x + size, y + size), fill=int(random.integers(120, 255)))
    if random.uniform() < 0.1 * amount:
        x, y = random.integers(0, PICTURE_W), random.integers(0, PICTURE_H)
        points = [(x, y)]
        for _ in range(6):
            x, y = x + random.integers(-40, 40), y + random.integers(-40, 40)
            points.append((x, y))
        draw.line(points, fill=220, width=2)
    marks = np.asarray(layer.filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32) / 255.0
    out = frame * (1.0 - 0.85 * marks[:, :, None])
    return out


def caption(text: str, shown: int, shift: tuple[int, int]) -> np.ndarray:
    """Return a layer with words in the letters of a typewriter: `shown` letters are there."""
    layer = Image.new("L", (PICTURE_W, PICTURE_H), 0)
    draw = ImageDraw.Draw(layer)
    draw.text((64 + shift[0], PICTURE_H - 96 + shift[1]), text[:shown], font=font(34), fill=235)
    return (np.asarray(layer.filter(ImageFilter.GaussianBlur(0.6)), dtype=np.float32) / 255.0)[
        :, :, None
    ]


def leader(frame_number: int, random: np.random.Generator) -> np.ndarray:
    """The start of the reel: numbers that count down, then the title."""
    second = frame_number / FPS
    image = Image.new("RGB", (PICTURE_W, PICTURE_H), (26, 25, 22))
    draw = ImageDraw.Draw(image)
    centre = (PICTURE_W // 2, PICTURE_H // 2)
    if second < 4.0:
        count = 5 - int(second)
        share = second - int(second)
        draw.ellipse((centre[0] - 300, centre[1] - 300, centre[0] + 300, centre[1] + 300),
                     outline=(200, 196, 180), width=5)  # fmt: skip
        draw.ellipse((centre[0] - 250, centre[1] - 250, centre[0] + 250, centre[1] + 250),
                     outline=(200, 196, 180), width=3)  # fmt: skip
        draw.line((0, centre[1], PICTURE_W, centre[1]), fill=(200, 196, 180), width=3)
        draw.line((centre[0], 0, centre[0], PICTURE_H), fill=(200, 196, 180), width=3)
        draw.pieslice((centre[0] - 300, centre[1] - 300, centre[0] + 300, centre[1] + 300),
                      -90, -90 + 360 * share, fill=(70, 68, 60))  # fmt: skip
        draw.text(centre, str(count), font=font(330), fill=(225, 221, 205), anchor="mm")
    else:
        jitter = (int(random.integers(-2, 3)), int(random.integers(-2, 3)))
        draw.text((centre[0] + jitter[0], centre[1] - 30 + jitter[1]), "LOW ORBIT",
                  font=font(150), fill=(232, 228, 212), anchor="mm")  # fmt: skip
        draw.text(
            (centre[0] + jitter[0], centre[1] + 110 + jitter[1]),
            "REEL 1 OF 1   16 MM   24 FPS",
            font=font(34),
            fill=(190, 186, 170),
            anchor="mm",
        )
    return np.asarray(image, dtype=np.float32) / 255.0


# ----------------------------------------------------------------------------
# The strip and the screen
# ----------------------------------------------------------------------------


def strip_base() -> np.ndarray:
    """Return the film strip with no picture: dark film, the holes, and the place of the track."""
    image = Image.new("RGB", (STRIP_W, HEIGHT * 2), (9, 8, 8))
    draw = ImageDraw.Draw(image)
    for row in range(-1, 3):
        y = row * HEIGHT + HEIGHT // 2 + PICTURE_H // 2 + 54  # at the line between two frames
        draw.rounded_rectangle((18, y - 38, 62, y + 38), 9, fill=(0, 0, 0))
        draw.rounded_rectangle((20, y - 36, 60, y + 36), 8, outline=(40, 38, 34), width=2)
    return np.asarray(image, dtype=np.float32) / 255.0


STRIP = strip_base()


def sound_track(samples: np.ndarray) -> np.ndarray:
    """Return the picture of the sound track for one frame: the width of the line is the sound."""
    rows = np.abs(samples[: (len(samples) // HEIGHT) * HEIGHT].reshape(HEIGHT, -1)).max(axis=1)
    half = np.clip(2.0 + 22.0 * rows, 1.0, TRACK_W / 2 - 2)
    columns = np.abs(np.arange(TRACK_W, dtype=np.float32) - TRACK_W / 2)[None, :]
    line = (columns < half[:, None]).astype(np.float32)
    return 0.05 + 0.8 * line


def compose(
    picture: np.ndarray, track: np.ndarray, weave: tuple[int, int], roll: int, lamp: float
) -> np.ndarray:
    """Put the picture and the sound track on the strip, and the strip on the screen."""
    strip = STRIP[:HEIGHT].copy()
    y0 = PICTURE_Y
    area = strip[y0 : y0 + PICTURE_H, PICTURE_X : PICTURE_X + PICTURE_W]
    area[:] = area * (1.0 - GATE) + picture * GATE
    strip[:, TRACK_X : TRACK_X + TRACK_W] = track[:, :, None] * np.array([0.95, 0.93, 0.85])
    if roll:
        strip = np.roll(strip, roll, axis=0)
    screen = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
    x = STRIP_X + weave[0]
    screen[:, x : x + STRIP_W] = strip
    if weave[1]:
        screen = np.roll(screen, weave[1], axis=0)
    return np.clip(screen * lamp, 0.0, 1.0)


CARD_TITLE, CARD_NAME = "LOW ORBIT", "Brett Gilio"
CARD_SECONDS = 5.0  # the card goes away after this time
CARD_PLACE = (150, 800)  # on the screen


def _card() -> tuple[np.ndarray, np.ndarray]:
    """Return the small paper card with the title and the name: its colours and its cover."""
    width, height, edge = 430, 170, 24
    image = Image.new("RGBA", (width + 2 * edge, height + 2 * edge), (0, 0, 0, 0))
    shadow = Image.new("L", image.size, 0)
    ImageDraw.Draw(shadow).rectangle((edge + 6, edge + 8, edge + width + 6, edge + height + 8), 150)
    image.putalpha(shadow.filter(ImageFilter.GaussianBlur(7)))
    draw = ImageDraw.Draw(image)
    draw.rectangle((edge, edge, edge + width, edge + height), fill=(226, 219, 198, 255))
    draw.rectangle((edge + 8, edge + 8, edge + width - 8, edge + height - 8),
                   outline=(60, 54, 46, 255), width=2)  # fmt: skip
    middle = edge + width // 2
    draw.text((middle, edge + 58), CARD_TITLE, font=font(58), fill=(34, 30, 26, 255), anchor="mm")
    draw.line((edge + 60, edge + 98, edge + width - 60, edge + 98), fill=(60, 54, 46, 255), width=2)
    draw.text((middle, edge + 128), CARD_NAME, font=font(36), fill=(34, 30, 26, 255), anchor="mm")
    image = image.rotate(2.5, resample=Image.BICUBIC, expand=True)
    data = np.asarray(image, dtype=np.float32) / 255.0
    return data[:, :, :3], data[:, :, 3:]


CARD, CARD_COVER = _card()


def put_card(screen: np.ndarray, frame_number: int) -> np.ndarray:
    """Put the card on the screen for the first seconds of the film. Then it fades fast."""
    left = CARD_SECONDS * FPS - frame_number
    if left <= 0:
        return screen
    share = min(1.0, left / 8.0)  # the last 8 frames
    x, y = CARD_PLACE
    height, width = CARD.shape[:2]
    area = screen[y : y + height, x : x + width]
    cover = CARD_COVER * share
    area[:] = area * (1.0 - cover) + CARD * cover
    return screen


def render_range(job: tuple[int, int, str, str, str]) -> str:
    """Render the frames from `first` to `last` into one file. Return the name of the file."""
    first, last, cue_file, audio_file, target = job
    cues = json.loads(Path(cue_file).read_text(encoding="utf-8"))
    shots = plan(cues)
    audio, rate = soundfile.read(audio_file, dtype="float32")
    mono = audio.mean(axis=1)
    per_frame = rate // FPS
    kicks = np.array(sorted(cues["kicks"]))
    starts = {shot.first for shot in shots if shot.section_start}
    writer = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-", "-c:v", "libopenh264", "-b:v",
         "18M", "-pix_fmt", "yuv420p", target],
        stdin=subprocess.PIPE,
    )  # fmt: skip
    leader_frames = int(5.6 * FPS)
    walk = np.random.default_rng(99)
    weave_x = np.cumsum(walk.normal(0.0, 0.5, last + 10))
    weave_x = weave_x - np.convolve(weave_x, np.ones(48) / 48, mode="same")
    buffer: np.ndarray | None = None
    buffer_shot: Shot | None = None
    buffer_first = 0
    for frame_number in range(first, last):
        random = np.random.default_rng(frame_number * 7919 + 13)
        shot = next((s for s in shots if s.first <= frame_number < s.last), shots[-1])
        local = frame_number - shot.first
        if frame_number < leader_frames:
            picture = leader(frame_number, random)
            look = "sepia"
        else:
            if (
                buffer is None
                or buffer_shot != shot
                or not (buffer_first <= local < buffer_first + len(buffer))
            ):
                count = min(48, shot.last - shot.first - local)
                buffer = read_frames(shot, local, max(count, 1))
                buffer_shot, buffer_first = shot, local
            picture = buffer[0 if shot.photograph else local - buffer_first]
            look = shot.look
            picture = grade(picture, look)
            if shot.photograph:
                share = local / max(shot.last - shot.first, 1)
                picture = photograph(picture, share, random)
            picture = halation(picture)
        _gains, _saturation, _black, _contrast, grain = GRADES[look]
        noise = random.normal(0.0, grain, (PICTURE_H // 2, PICTURE_W // 2)).astype(np.float32)
        noise = np.repeat(np.repeat(noise, 2, axis=0), 2, axis=1)
        # The grain is strongest in the middle tones, and small in the black parts.
        picture = picture + noise[:, :, None] * (0.22 + 1.6 * picture * (1.1 - picture))
        picture = dirt(picture * VIGNETTE, random, 1.6 if look == "sepia" else 1.0)
        # A scratch: a thin light line that stays at one place for some frames.
        scratch = np.random.default_rng(frame_number // 30)
        if scratch.uniform() < 0.3:
            x = int(scratch.integers(40, PICTURE_W - 40)) + int(random.integers(-1, 2))
            picture[:, x : x + 2] += 0.22
        if shot.caption and frame_number >= leader_frames and local < 4.5 * FPS:
            shown = int(local / 1.6)
            jitter = (int(random.integers(-1, 2)), int(random.integers(-1, 2)))
            picture = picture + caption(shot.caption, shown, jitter) * 0.9
        # The lamp: a flicker, and more light at each kick drum.
        second = frame_number / FPS
        lamp = 1.0 + 0.025 * random.normal()
        if len(kicks):
            since = second - kicks[np.searchsorted(kicks, second + 1e-3) - 1]
            if 0.0 <= since < 0.12:
                lamp += 0.07 * (1.0 - since / 0.12)
        roll = 0
        splice = frame_number in starts and frame_number >= leader_frames
        if splice:
            picture = np.clip(picture * 0.3 + 0.85, 0.0, 1.0)
        elif frame_number - 1 in starts or frame_number - 2 in starts:
            roll = int(random.integers(-160, 160))
        elif random.uniform() < 0.004:
            roll = int(random.integers(-60, 60))
        # Light that leaks in at the side, at the start of a section and at some other places.
        leak = np.random.default_rng(frame_number // 18)
        distance = min((frame_number - start for start in starts if start <= frame_number),
                       default=999)  # fmt: skip
        if distance < 20 or leak.uniform() < 0.05:
            power = 0.5 * (1.0 - distance / 20.0) if distance < 20 else 0.18
            edge = np.exp(-_X / (PICTURE_W * (0.12 + 0.1 * leak.uniform())))[:, :, None]
            picture = picture + power * edge * np.array([1.0, 0.5, 0.15], dtype=np.float32)
        track = sound_track(mono[frame_number * per_frame : (frame_number + 1) * per_frame + 1])
        weave = (int(round(float(weave_x[frame_number]))), int(random.integers(-1, 2)))
        screen = compose(np.clip(picture, 0.0, 1.0), track, weave, roll, lamp)
        screen = put_card(screen, frame_number)
        writer.stdin.write((screen * 255.0).astype(np.uint8).tobytes())
    writer.stdin.close()
    writer.wait()
    return target


def render(
    audio: Path = Path("build/audio/low-orbit.flac"),
    cue_file: Path = Path("build/audio/low-orbit.json"),
    folder: Path = Path("build/video"),
    first_second: float = 0.0,
    last_second: float | None = None,
    workers: int = 6,
) -> Path:
    cues = json.loads(cue_file.read_text(encoding="utf-8"))
    end = cues["seconds"] if last_second is None else last_second
    first, last = int(first_second * FPS), int(end * FPS)
    folder.mkdir(parents=True, exist_ok=True)
    step = max(FPS * 4, (last - first) // (workers * 4) + 1)
    jobs = [
        (
            start,
            min(last, start + step),
            str(cue_file),
            str(audio),
            str(folder / f"part-{n:03d}.mp4"),
        )
        for n, start in enumerate(range(first, last, step))
    ]
    with multiprocessing.get_context("fork").Pool(workers) as pool:
        parts = pool.map(render_range, jobs)
    listing = folder / "parts.txt"
    listing.write_text("".join(f"file '{Path(part).name}'\n" for part in parts), encoding="utf-8")
    whole = first_second == 0.0 and last_second is None
    output = folder / ("low-orbit.mp4" if whole else f"excerpt-{int(first_second)}.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-ss", f"{first_second:.3f}", "-t", f"{end - first_second:.3f}", "-i", str(audio),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-shortest",
         str(output)],
        check=True,
    )  # fmt: skip
    for part in parts:
        Path(part).unlink(missing_ok=True)
    listing.unlink(missing_ok=True)
    return output


if __name__ == "__main__":
    values = [float(value) for value in sys.argv[1:]]
    print(render(first_second=values[0] if values else 0.0,
                 last_second=values[1] if len(values) > 1 else None))  # fmt: skip
