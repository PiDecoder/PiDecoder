#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/pidecoder/config/cameras.json")

data = json.loads(path.read_text(encoding="utf-8"))
changed = 0

for camera in data.get("cameras", []):
    url = camera.get("grid_url")
    if not isinstance(url, str):
        continue

    new_url = url

    if "resolution=" in new_url:
        new_url = re.sub(
            r"resolution=[^&]+",
            "resolution=640x360",
            new_url,
            count=1,
        )
    else:
        new_url += ("&" if "?" in new_url else "?") + "resolution=640x360"

    if "fps=" in new_url:
        new_url = re.sub(
            r"fps=[^&]+",
            "fps=12",
            new_url,
            count=1,
        )
    else:
        new_url += ("&" if "?" in new_url else "?") + "fps=12"

    if new_url != url:
        camera["grid_url"] = new_url
        changed += 1

path.write_text(
    json.dumps(data, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

print(f"{changed} URL(s) mosaïque configurée(s) en 640x360 @ 12 fps.")
