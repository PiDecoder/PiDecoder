#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-/opt/pidecoder}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.backup-v0.7.0-${STAMP}"

if [[ ! -d "$TARGET" ]]; then
    echo "Dossier cible introuvable : $TARGET" >&2
    exit 1
fi

echo "Sauvegarde : $BACKUP"
cp -a "$TARGET" "$BACKUP"

install -m 0755     "$PATCH_DIR/scripts/config-web.py"     "$TARGET/scripts/config-web.py"

install -m 0644     "$PATCH_DIR/systemd/pidecoder-config.service"     "/etc/systemd/system/pidecoder-config.service"

systemctl daemon-reload
systemctl enable --now pidecoder-config.service

echo
echo "PiDecoder Config v0.7.1 installé."
echo "Interface : http://IP_DU_PI:8080"
echo "Backup : $BACKUP"
