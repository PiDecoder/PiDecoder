#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-/opt/pidecoder}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.backup-v0.7.5-${STAMP}"

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
    "$PATCH_DIR/src/Player.cpp" \
    "$TARGET/src/Player.cpp"

if [[ -f "$PATCH_DIR/scripts/config-web.py" ]]; then
    install -m 0755 \
        "$PATCH_DIR/scripts/config-web.py" \
        "$TARGET/scripts/config-web.py"
fi

cd "$TARGET"
rm -rf build

export PKG_CONFIG_PATH="/usr/local/lib/aarch64-linux-gnu/pkgconfig:/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:${LD_LIBRARY_PATH:-}"

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"

if systemctl is-enabled pidecoder-config.service >/dev/null 2>&1; then
    systemctl restart pidecoder-config.service
fi

echo
echo "PiDecoder v0.7.6 Untimed Grid compilé."
echo "Mosaïque : UDP + 640x360/12 + untimed=yes + video-sync=desync + correct-pts=no"
echo "Focus    : TCP + timing classique"
echo "Backup   : $BACKUP"
