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

from onvif_client import (
    PTZ_MOVES,
    continuous_move,
    credentials_for_ptz_camera,
    find_ptz_camera,
    goto_preset,
    stop,
)

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


def execute(root: Path, request: dict) -> None:
    action = str(request.get("action", "")).strip().lower()
    ptz_xaddr = str(request.get("ptz_xaddr", "")).strip()
    profile_token = str(
        request.get("profile_token", "")
    ).strip()

    if action not in PTZ_MOVES and action not in {"stop", "preset"}:
        raise ValueError("Commande PTZ inconnue")

    if not ptz_xaddr:
        raise ValueError("Adresse PTZ absente")

    document = load_document(root)
    camera, token = find_ptz_camera(
        document.get("cameras", []),
        ptz_xaddr,
        profile_token,
    )
    credentials = credentials_for_ptz_camera(camera)

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

    pan, tilt, zoom = PTZ_MOVES[action]
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
