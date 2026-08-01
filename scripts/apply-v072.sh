#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-/opt/pidecoder}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.backup-v0.7.1-${STAMP}"

if [[ ! -d "$TARGET" ]]; then
    echo "Dossier cible introuvable : $TARGET" >&2
    exit 1
fi

echo "Sauvegarde : $BACKUP"
cp -a "$TARGET" "$BACKUP"

install -m 0755     "$PATCH_DIR/scripts/config-web.py"     "$TARGET/scripts/config-web.py"

if [[ -f "$TARGET/config/cameras.json" ]]; then
    chown admin:admin "$TARGET/config/cameras.json"
    chmod 600 "$TARGET/config/cameras.json"
fi

if [[ -f "$TARGET/config/layout.json" ]]; then
    chown admin:admin "$TARGET/config/layout.json"
    chmod 600 "$TARGET/config/layout.json"
fi

systemctl restart pidecoder-config.service

echo
echo "PiDecoder Config v0.7.2 installé."
echo "Les JSON resteront admin:admin en 0600 après chaque sauvegarde."
echo "Backup : $BACKUP"
