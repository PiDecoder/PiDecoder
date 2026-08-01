#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/opt/pidecoder}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.backup-v0.9.9-rc1-${STAMP}"
INSTALLED=0

rollback() {
    local exit_code=$?

    if [[ "$INSTALLED" -eq 1 && -d "$BACKUP" ]]; then
        echo
        echo "ERREUR pendant l'installation — restauration automatique."
        rm -rf "$TARGET"
        cp -a "$BACKUP" "$TARGET"
        systemctl reset-failed pidecoder-config.service 2>/dev/null || true
        systemctl restart pidecoder-config.service 2>/dev/null || true
        systemctl restart pidecoder.service 2>/dev/null || true
        echo "Version précédente restaurée depuis : $BACKUP"
    fi

    exit "$exit_code"
}

trap rollback ERR

if [[ ! -d "$TARGET" ]]; then
    echo "Dossier cible introuvable : $TARGET" >&2
    exit 1
fi

echo "Pré-vérification complète du paquet..."
"$PATCH_DIR/scripts/validate-release.sh"

echo "Sauvegarde : $BACKUP"
cp -a "$TARGET" "$BACKUP"
INSTALLED=1

install -m 0644 "$PATCH_DIR/CMakeLists.txt" "$TARGET/CMakeLists.txt"
cp -a "$PATCH_DIR/include/." "$TARGET/include/"
cp -a "$PATCH_DIR/src/." "$TARGET/src/"
install -m 0755 "$PATCH_DIR/scripts/config-web.py" "$TARGET/scripts/config-web.py"
install -m 0755 "$PATCH_DIR/scripts/onvif_client.py" "$TARGET/scripts/onvif_client.py"
install -m 0755 "$PATCH_DIR/scripts/validate-release.sh" "$TARGET/scripts/validate-release.sh"

cd "$TARGET"
rm -rf build

export PKG_CONFIG_PATH="/usr/local/lib/aarch64-linux-gnu/pkgconfig:/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:${LD_LIBRARY_PATH:-}"

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"

python3 -m py_compile \
    "$TARGET/scripts/config-web.py" \
    "$TARGET/scripts/onvif_client.py"

find "$TARGET/scripts" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find "$TARGET/scripts" -type f -name '*.pyc' -delete 2>/dev/null || true

systemctl reset-failed pidecoder-config.service || true
systemctl restart pidecoder-config.service
systemctl restart pidecoder.service 2>/dev/null || true

sleep 2
systemctl is-active --quiet pidecoder-config.service

if systemctl list-unit-files pidecoder.service >/dev/null 2>&1; then
    systemctl is-active --quiet pidecoder.service
fi

INSTALLED=0
trap - ERR

echo
echo "PiDecoder v0.9.9.1 RC1 Fix installé."
echo "Diagnostics intégrés à Système."
echo "Backup : $BACKUP"
