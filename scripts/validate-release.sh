#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup_python_cache() {
    find "$ROOT" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
    find "$ROOT" -type f -name '*.pyc' -delete 2>/dev/null || true
}

trap cleanup_python_cache EXIT

echo "[1/8] Vérification Python"
python3 -m py_compile \
    "$ROOT/scripts/config-web.py" \
    "$ROOT/scripts/onvif_client.py" \
    "$ROOT/scripts/check-camera-config.py"

# py_compile creates caches by design; remove them before package checks.
cleanup_python_cache

echo "[2/8] Vérification JavaScript"
if command -v node >/dev/null 2>&1; then
    python3 - "$ROOT" <<'PY'
from pathlib import Path
import re
import sys

root=Path(sys.argv[1])
text=(root/'scripts/config-web.py').read_text(encoding='utf-8')
match=re.search(r'<script>(.*)</script>',text,re.S)

if not match:
    raise SystemExit('Bloc JavaScript introuvable')

target=root/'scripts/config-web.embedded.js'
target.write_text(match.group(1),encoding='utf-8')
PY
    node --check "$ROOT/scripts/config-web.embedded.js"
    rm -f "$ROOT/scripts/config-web.embedded.js"
else
    echo "  Node.js absent : contrôle JavaScript ignoré"
fi

echo "[3/8] Vérification des scripts Shell"
bash -n \
    "$ROOT/scripts/install.sh" \
    "$ROOT/scripts/validate-release.sh"

echo "[4/8] Vérification de la version CMake"
grep -Eq \
    '^[[:space:]]*VERSION[[:space:]]+0\.9\.9\.4([[:space:]]|$)' \
    "$ROOT/CMakeLists.txt"

echo "[5/8] Vérification des fichiers essentiels"
required=(
    "CMakeLists.txt"
    "scripts/config-web.py"
    "scripts/onvif_client.py"
    "scripts/install.sh"
    "scripts/check-camera-config.py"
    "systemd/pidecoder.service.in"
    "systemd/pidecoder-config.service.in"
    "systemd/pidecoder-wayland.path.in"
    "systemd/pidecoder-wayland.target.in"
    "src/main.cpp"
    "src/Application.cpp"
    "src/Player.cpp"
    "src/Renderer.cpp"
    "src/Grid.cpp"
    "src/Layout.cpp"
    "include/pidecoder/Application.hpp"
    "include/pidecoder/Player.hpp"
    "include/pidecoder/Renderer.hpp"
    "include/pidecoder/Grid.hpp"
    "include/pidecoder/Layout.hpp"
)

for relative in "${required[@]}"; do
    test -f "$ROOT/$relative" || {
        echo "Fichier manquant : $relative" >&2
        exit 1
    }
done

echo "[6/8] Vérification JSON"
python3 - "$ROOT" <<'PY'
from pathlib import Path
import json
import sys

root = Path(sys.argv[1])

for path in sorted((root / "config").glob("*.json")):
    with path.open("r", encoding="utf-8") as handle:
        json.load(handle)
    print(f"  OK {path.name}")
PY

cleanup_python_cache

echo "[7/8] Recherche de résidus indésirables"
if find "$ROOT" -type d -name __pycache__ -print -quit | grep -q .; then
    echo "Un dossier __pycache__ est présent" >&2
    exit 1
fi

if find "$ROOT" -type f -name '*.pyc' -print -quit | grep -q .; then
    echo "Un fichier .pyc est présent" >&2
    exit 1
fi

echo "[8/8] Validation terminée"
echo "PiDecoder v0.9.9.4 RC1 : paquet cohérent."
