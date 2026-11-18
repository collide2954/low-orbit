"""Get the footage of the film from the NASA Image and Video Library.

Use: uv run python tools/footage.py [sizes]

The files go to the directory `.cache/footage` (not in the repository). The
table `research/footage.csv` has one row for each file: its name, its title,
its date, its address, and its licence. With the word "sizes" the script
only prints the size of each file.

The material of NASA is in the public domain (NASA media usage guidelines).
"""

from __future__ import annotations

import csv
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

FOLDER = Path(".cache/footage")
TABLE = Path("research/footage.csv")
AGENT = {"User-Agent": "footage-script/1.0"}

# The identifier in the library, and the size of the file ("orig", "large", "medium").
VIDEOS = [
    ("jsc2021m000138_4K_Earth_Views_Extended_Cut_for_Earth_Day_ 2021_210422-4KMP4", "medium"),
    ("jsc2022m000172_Earth_in_4K_Expedition_65_Edition", "large"),
    ("jsc2023m000111_Earth_in_4K_Space_Station_Expedition_67_68_Edition", "large"),
    ("Earth Views from the International Space Station", "large"),
    ("GSFC_20180124_m12825_ISS_Airglow", "large"),
    ("HD 049 Mercury_Gemini_Apollo_Resource Reel 1", "medium"),
]


def _get(url: str) -> bytes:
    request = urllib.request.Request(urllib.parse.quote(url, safe=":/~%"), headers=AGENT)
    with urllib.request.urlopen(request, timeout=120) as reply:
        return reply.read()


def _size(url: str) -> int:
    request = urllib.request.Request(
        urllib.parse.quote(url, safe=":/~%"), headers=AGENT, method="HEAD"
    )
    with urllib.request.urlopen(request, timeout=120) as reply:
        return int(reply.headers.get("Content-Length", 0))


def assets(identifier: str) -> list[str]:
    base = "https://images-assets.nasa.gov/video/" + identifier + "/collection.json"
    return [url.replace("http://", "https://") for url in json.loads(_get(base))]


def details(identifier: str) -> dict:
    url = "https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"nasa_id": identifier})
    try:
        request = urllib.request.Request(url, headers=AGENT)
        with urllib.request.urlopen(request, timeout=120) as reply:
            items = json.load(reply)["collection"]["items"]
    except OSError:
        return {}
    return items[0]["data"][0] if items else {}


def main() -> None:
    only_sizes = "sizes" in sys.argv
    FOLDER.mkdir(parents=True, exist_ok=True)
    rows = []
    for identifier, wanted in VIDEOS:
        files = [url for url in assets(identifier) if url.endswith(".mp4")]
        chosen = next((url for url in files if f"~{wanted}." in url), None)
        chosen = chosen or next((url for url in files if "~orig." in url), files[0])
        size = _size(chosen)
        print(f"{size / 1e6:8.0f} MB  {chosen.rsplit('/', 1)[-1]}")
        if only_sizes:
            continue
        target = FOLDER / chosen.rsplit("/", 1)[-1].replace(" ", "_")
        if not target.exists() or target.stat().st_size != size:
            request = urllib.request.Request(urllib.parse.quote(chosen, safe=":/~%"), headers=AGENT)
            with urllib.request.urlopen(request, timeout=300) as reply, target.open("wb") as out:
                while block := reply.read(1 << 20):
                    out.write(block)
        info = details(identifier)
        rows.append(
            {
                "file": target.name,
                "title": info.get("title", identifier),
                "date": info.get("date_created", "")[:10],
                "source": "NASA Image and Video Library",
                "identifier": identifier,
                "address": chosen,
                "licence": "Public domain (NASA)",
            }
        )
    if rows:
        TABLE.parent.mkdir(parents=True, exist_ok=True)
        with TABLE.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
