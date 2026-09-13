#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/opt/pidecoder}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.backup-v0.6.1-${STAMP}"

echo "Sauvegarde : $BACKUP"
cp -a "$TARGET" "$BACKUP"

for f in CMakeLists.txt src/Application.cpp src/Player.cpp include/pidecoder/Player.hpp; do
  install -m 0644 "$PATCH_DIR/$f" "$TARGET/$f"
done

cd "$TARGET"
rm -rf build
export PKG_CONFIG_PATH="/usr/local/lib/aarch64-linux-gnu/pkgconfig:/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:${LD_LIBRARY_PATH:-}"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
echo "PiDecoder v0.6.2 compilé."
echo "Backup : $BACKUP"
