#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/opt/pidecoder}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.backup-v0.9.0.1-${STAMP}"

cp -a "$TARGET" "$BACKUP"
install -m 0644 "$PATCH_DIR/CMakeLists.txt" "$TARGET/CMakeLists.txt"
install -m 0755 "$PATCH_DIR/scripts/config-web.py" "$TARGET/scripts/config-web.py"
install -m 0755 "$PATCH_DIR/scripts/onvif_client.py" "$TARGET/scripts/onvif_client.py"

cd "$TARGET"
rm -rf build
export PKG_CONFIG_PATH="/usr/local/lib/aarch64-linux-gnu/pkgconfig:/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:${LD_LIBRARY_PATH:-}"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
systemctl restart pidecoder-config.service
systemctl restart pidecoder.service 2>/dev/null || true

echo "PiDecoder v0.9.0.2 installé."
echo "Backup : $BACKUP"
