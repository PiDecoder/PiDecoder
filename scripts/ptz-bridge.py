#!/usr/bin/env python3
"""Local Unix-datagram bridge between PiDecoder SDL and ONVIF PTZ."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from onvif_client import Credentials, continuous_move, goto_preset, stop

MOVES: dict[str, tuple[float, float, float]] = {
    "up": (0.0, 0.5, 0.0),
    "down": (0.0, -0.5, 0.0),
    "left": (-0.5, 0.0, 0.0),
    "right": (0.5, 0.0, 0.0),
    "zoomin": (0.0, 0.0, 0.5),
    "zoomout": (0.0, 0.0, -0.5),
}

RUNNING = True


def log(message: str) -> None:
    print(message, flush=True)


def stop_signal(_signum: int, _frame: object) -> None:
    global RUNNING
    RUNNING = False


def load_document(root: Path) -> dict:
    path = root / "config" / "cameras.json"
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)

    if not isinstance(document, dict):
        raise ValueError("Configuration caméra invalide")

    return document


def credentials_from_camera(camera: dict) -> Credentials:
    uri = str(
        camera.get("focus_url")
        or camera.get("grid_url")
        or ""
    ).strip()

    parsed = urlsplit(uri)

    if parsed.scheme.lower() != "rtsp":
        raise ValueError("URL RTSP absente pour la caméra PTZ")

    return Credentials(
        unquote(parsed.username or ""),
        unquote(parsed.password or ""),
    )


def find_camera(
    document: dict,
    ptz_xaddr: str,
    profile_token: str,
) -> tuple[dict, str]:
    cameras = document.get("cameras", [])

    if not isinstance(cameras, list):
        raise ValueError("La clé cameras doit contenir une liste")

    for camera in cameras:
        if not isinstance(camera, dict):
            continue

        metadata = camera.get("onvif", {})

        if not isinstance(metadata, dict):
            continue

        stored_xaddr = str(
            metadata.get("ptz_xaddr", "")
        ).strip()

        if stored_xaddr != ptz_xaddr:
            continue

        stored_token = str(
            metadata.get("ptz_profile_token")
            or metadata.get("focus_profile_token")
            or metadata.get("grid_profile_token")
            or ""
        ).strip()

        token = profile_token or stored_token

        if not token:
            raise ValueError("Profil PTZ absent")

        if profile_token and stored_token and profile_token != stored_token:
            continue

        return camera, token

    raise ValueError("Caméra PTZ introuvable dans la configuration")


def execute(root: Path, request: dict) -> None:
    action = str(request.get("action", "")).strip().lower()
    ptz_xaddr = str(request.get("ptz_xaddr", "")).strip()
    profile_token = str(
        request.get("profile_token", "")
    ).strip()

    if action not in MOVES and action not in {"stop", "preset"}:
        raise ValueError("Commande PTZ inconnue")

    if not ptz_xaddr:
        raise ValueError("Adresse PTZ absente")

    document = load_document(root)
    camera, token = find_camera(
        document,
        ptz_xaddr,
        profile_token,
    )
    credentials = credentials_from_camera(camera)

    if action == "preset":
        preset_token = str(
            request.get("preset_token", "")
        ).strip()

        if not preset_token:
            raise ValueError("Token de preset absent")

        goto_preset(
            ptz_xaddr,
            token,
            preset_token,
            credentials,
        )
        return

    if action == "stop":
        stop(
            ptz_xaddr,
            token,
            credentials,
        )
        return

    pan, tilt, zoom = MOVES[action]
    continuous_move(
        ptz_xaddr,
        token,
        credentials,
        pan,
        tilt,
        zoom,
    )


def serve(root: Path, socket_path: Path) -> int:
    socket_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        socket_path.unlink()
    except FileNotFoundError:
        pass

    server = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_DGRAM,
    )

    server.bind(str(socket_path))
    os.chmod(socket_path, 0o660)
    server.settimeout(0.5)

    log(f"Pont PTZ prêt : {socket_path}")
    active_request: dict | None = None

    try:
        while RUNNING:
            try:
                payload = server.recv(8192)
            except socket.timeout:
                continue

            try:
                request = json.loads(
                    payload.decode("utf-8")
                )

                if not isinstance(request, dict):
                    raise ValueError("Message PTZ invalide")

                execute(root, request)

                action = str(
                    request.get("action", "")
                ).lower()

                if action in {"stop", "preset"}:
                    active_request = None
                else:
                    active_request = dict(request)

            except Exception as error:  # noqa: BLE001
                log(f"Erreur PTZ : {error}")

    finally:
        if active_request is not None:
            try:
                emergency_stop = dict(active_request)
                emergency_stop["action"] = "stop"
                execute(root, emergency_stop)
            except Exception as error:  # noqa: BLE001
                log(f"Erreur PTZ pendant l’arrêt : {error}")

        server.close()

        try:
            socket_path.unlink()
        except FileNotFoundError:
            pass

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default="/opt/pidecoder",
    )
    parser.add_argument(
        "--socket",
        default="/run/pidecoder/ptz.sock",
    )
    arguments = parser.parse_args()

    signal.signal(signal.SIGTERM, stop_signal)
    signal.signal(signal.SIGINT, stop_signal)

    return serve(
        Path(arguments.root).resolve(),
        Path(arguments.socket),
    )


if __name__ == "__main__":
    raise SystemExit(main())
