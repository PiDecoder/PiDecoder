#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-/opt/pidecoder}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.backup-v0.6.5-${STAMP}"

if [[ ! -d "$TARGET" ]]; then
    echo "Dossier cible introuvable : $TARGET" >&2
    exit 1
fi

echo "Sauvegarde : $BACKUP"
cp -a "$TARGET" "$BACKUP"

install -m 0644 "$PATCH_DIR/CMakeLists.txt" "$TARGET/CMakeLists.txt"
install -m 0644 "$PATCH_DIR/include/pidecoder/Player.hpp" "$TARGET/include/pidecoder/Player.hpp"
install -m 0644 "$PATCH_DIR/src/Player.cpp" "$TARGET/src/Player.cpp"
install -m 0644 "$PATCH_DIR/src/Application.cpp" "$TARGET/src/Application.cpp"

echo
echo "Passage des URL mosaïque à 640x360 / 12 fps..."
python3 "$PATCH_DIR/scripts/set-grid-640x360.py" \
    "$TARGET/config/cameras.json"

if grep -R -n '```' "$TARGET/src" "$TARGET/include"; then
    echo "Balises Markdown détectées." >&2
    exit 1
fi

cd "$TARGET"
rm -rf build

export PKG_CONFIG_PATH="/usr/local/lib/aarch64-linux-gnu/pkgconfig:/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:${LD_LIBRARY_PATH:-}"

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"

echo
echo "PiDecoder v0.6.6 compilé."
echo "Backup complet : $BACKUP"
echo
echo "Mode mosaïque : 640x360 / 12 fps + framedrop live-first"
echo "Mode focus     : URL focus inchangée + framedrop standard"
