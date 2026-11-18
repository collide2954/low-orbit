"""Make contact sheets of a video: small pictures at regular times, with the time below each.

Use: uv run python tools/contact.py VIDEO [SECONDS BETWEEN PICTURES [FIRST SECOND [LAST SECOND]]]

The script reads one frame at each time (it does not decode the full
video). The sheets go to `.cache/contact`. They are for the selection of the
shots of the film.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

FOLDER = Path(".cache/contact")
COLUMNS, ROWS, SIZE = 7, 6, (256, 144)


def duration(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(video)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return float(out.stdout.strip())


def frame(video: Path, second: float) -> Image.Image:
    data = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-ss", f"{second:.2f}", "-i", str(video), "-frames:v",
         "1", "-vf", f"scale={SIZE[0]}:{SIZE[1]}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout  # fmt: skip
    if len(data) < SIZE[0] * SIZE[1] * 3:
        return Image.new("RGB", SIZE)
    return Image.frombytes("RGB", SIZE, data[: SIZE[0] * SIZE[1] * 3])


def main() -> None:
    video = Path(sys.argv[1])
    step = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
    FOLDER.mkdir(parents=True, exist_ok=True)
    name = video.stem.split("~")[0][:36].replace(" ", "_")
    first = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    last = float(sys.argv[4]) if len(sys.argv) > 4 else duration(video)
    if first:
        name = f"{name}-from-{int(first)}"
    times = [second for second in _range(first, last, step)]
    per_sheet = COLUMNS * ROWS
    for sheet_number in range(0, len(times), per_sheet):
        sheet = Image.new("RGB", (COLUMNS * SIZE[0], ROWS * (SIZE[1] + 16)), (0, 0, 0))
        draw = ImageDraw.Draw(sheet)
        for place, second in enumerate(times[sheet_number : sheet_number + per_sheet]):
            x, y = (place % COLUMNS) * SIZE[0], (place // COLUMNS) * (SIZE[1] + 16)
            sheet.paste(frame(video, second), (x, y))
            draw.text((x + 4, y + SIZE[1] + 2), f"{int(second) // 60}:{int(second) % 60:02d}",
                      fill=(255, 255, 0))  # fmt: skip
        sheet.save(FOLDER / f"{name}-{sheet_number // per_sheet:02d}.jpg", quality=80)
    print(len(times), "pictures")


def _range(first: float, last: float, step: float):
    value = first
    while value < last:
        yield value
        value += step


if __name__ == "__main__":
    main()
