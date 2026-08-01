#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-/opt/pidecoder}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.backup-v0.8.0-${STAMP}"

if [[ ! -d "$TARGET" ]]; then
    echo "Dossier cible introuvable : $TARGET" >&2
    exit 1
fi

echo "Sauvegarde : $BACKUP"
cp -a "$TARGET" "$BACKUP"

install -m 0644 \
    "$PATCH_DIR/CMakeLists.txt" \
    "$TARGET/CMakeLists.txt"

install -m 0644 \
    "$PATCH_DIR/include/pidecoder/Application.hpp" \
    "$TARGET/include/pidecoder/Application.hpp"

install -m 0644 \
    "$PATCH_DIR/include/pidecoder/Player.hpp" \
    "$TARGET/include/pidecoder/Player.hpp"

install -m 0644 \
    "$PATCH_DIR/include/pidecoder/Renderer.hpp" \
    "$TARGET/include/pidecoder/Renderer.hpp"

install -m 0644 \
    "$PATCH_DIR/src/Application.cpp" \
    "$TARGET/src/Application.cpp"

install -m 0644 \
    "$PATCH_DIR/src/Player.cpp" \
    "$TARGET/src/Player.cpp"

install -m 0644 \
    "$PATCH_DIR/src/Renderer.cpp" \
    "$TARGET/src/Renderer.cpp"

cd "$TARGET"
rm -rf build

export PKG_CONFIG_PATH="/usr/local/lib/aarch64-linux-gnu/pkgconfig:/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:${LD_LIBRARY_PATH:-}"

cmake -S . -B build \
    -DCMAKE_BUILD_TYPE=Release

cmake --build build \
    -j"$(nproc)"

if systemctl cat pidecoder.service >/dev/null 2>&1; then
    systemctl restart pidecoder.service
fi

echo
echo "PiDecoder v0.8.1 Inspection Mode compilé."
echo "Moteur RTSP/libmpv : inchangé"
echo "Backup : $BACKUP"
