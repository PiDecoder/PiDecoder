#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-/opt/pidecoder}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.backup-v0.9.5-${STAMP}"

if [[ ! -d "$TARGET" ]]; then
    echo "Dossier cible introuvable : $TARGET" >&2
    exit 1
fi

echo "Pré-vérification du paquet..."
python3 -m py_compile \
    "$PATCH_DIR/scripts/config-web.py" \
    "$PATCH_DIR/scripts/onvif_client.py"

if ! grep -Eq '^[[:space:]]*VERSION[[:space:]]+0\.9\.5\.1([[:space:]]|$)' "$PATCH_DIR/CMakeLists.txt"; then
    echo "ERREUR : CMakeLists.txt ne contient pas VERSION 0.9.5.1" >&2
    exit 1
fi

echo "Sauvegarde : $BACKUP"
cp -a "$TARGET" "$BACKUP"

install -m 0644 \
    "$PATCH_DIR/CMakeLists.txt" \
    "$TARGET/CMakeLists.txt"

cp -a \
    "$PATCH_DIR/include/." \
    "$TARGET/include/"

cp -a \
    "$PATCH_DIR/src/." \
    "$TARGET/src/"

install -m 0755 \
    "$PATCH_DIR/scripts/config-web.py" \
    "$TARGET/scripts/config-web.py"

install -m 0755 \
    "$PATCH_DIR/scripts/onvif_client.py" \
    "$TARGET/scripts/onvif_client.py"

cd "$TARGET"
rm -rf build

export PKG_CONFIG_PATH="/usr/local/lib/aarch64-linux-gnu/pkgconfig:/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:${LD_LIBRARY_PATH:-}"

cmake -S . -B build \
    -DCMAKE_BUILD_TYPE=Release

cmake --build build \
    -j"$(nproc)"

systemctl reset-failed pidecoder-config.service || true
systemctl restart pidecoder-config.service
systemctl restart pidecoder.service 2>/dev/null || true

echo
echo "PiDecoder v0.9.5.1 Smart Mosaic Editor installé."
echo "Backup : $BACKUP"
