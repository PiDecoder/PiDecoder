#!/usr/bin/env python3
"""Return success when a PiDecoder configuration has an active camera."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: check-camera-config.py /path/to/cameras.json",
            file=sys.stderr,
        )
        return 2

    path = Path(sys.argv[1])

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return 1
    except (OSError, json.JSONDecodeError) as error:
        print(f"Configuration caméra invalide : {error}", file=sys.stderr)
        return 2

    cameras = document.get("cameras", [])

    if not isinstance(cameras, list):
        print("La clé cameras doit contenir une liste", file=sys.stderr)
        return 2

    for camera in cameras:
        if not isinstance(camera, dict):
            continue
        if camera.get("enabled", True) is False:
            continue
        if str(camera.get("grid_url", "")).strip():
            return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
