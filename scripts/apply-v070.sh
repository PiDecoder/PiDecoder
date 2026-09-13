#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-/opt/pidecoder}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.backup-v0.6.6-${STAMP}"

if [[ ! -d "$TARGET" ]]; then
    echo "Dossier cible introuvable : $TARGET" >&2
    exit 1
fi

echo "Sauvegarde : $BACKUP"
cp -a "$TARGET" "$BACKUP"

install -m 0644 "$PATCH_DIR/CMakeLists.txt" "$TARGET/CMakeLists.txt"
install -m 0644 "$PATCH_DIR/include/pidecoder/Layout.hpp" "$TARGET/include/pidecoder/Layout.hpp"
install -m 0644 "$PATCH_DIR/src/Layout.cpp" "$TARGET/src/Layout.cpp"
install -m 0644 "$PATCH_DIR/include/pidecoder/Application.hpp" "$TARGET/include/pidecoder/Application.hpp"
install -m 0644 "$PATCH_DIR/src/Application.cpp" "$TARGET/src/Application.cpp"
install -m 0644 "$PATCH_DIR/src/main.cpp" "$TARGET/src/main.cpp"

if [[ ! -f "$TARGET/config/layout.json" ]]; then
    cp "$PATCH_DIR/config/layout.example.json" "$TARGET/config/layout.json"
fi

chmod 600 "$TARGET/config/layout.json"

cd "$TARGET"
rm -rf build

export PKG_CONFIG_PATH="/usr/local/lib/aarch64-linux-gnu/pkgconfig:/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:${LD_LIBRARY_PATH:-}"

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"

echo
echo "PiDecoder v0.7.0 compilé."
echo "Backup : $BACKUP"
echo "Layout : $TARGET/config/layout.json"
