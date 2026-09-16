#!/usr/bin/env bash
# Outil de développement uniquement — ne fait PAS partie de l'installeur.
#
# Synchronise le contenu de scripts/ (Python, Shell, Web) depuis ce clone
# Git vers /opt/pidecoder, sans passer par install.sh. install.sh copie
# scripts/ vers /opt/pidecoder une seule fois, au moment de l'installation
# — un simple "git pull" dans ce clone ne met donc PAS à jour
# /opt/pidecoder tout seul, et un "systemctl restart" relance le même
# fichier déjà en place tant que cette copie n'a pas été refaite. Ce
# script fait uniquement cette copie, puis redémarre le service Web —
# beaucoup plus rapide que l'installeur complet (qui recompile le moteur
# natif et coupe l'affichage vidéo), utile pour itérer sur des
# changements Python/JS/HTML/CSS pendant le développement.
#
# Ne touche pas : config/ (cameras.json, layout.json, web-auth.json,
# certificats TLS), le moteur natif compilé, les unités systemd.
#
# Usage : sudo bash scripts/sync-dev.sh
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "ERREUR : lance ce script avec sudo." >&2
    exit 1
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="/opt/pidecoder"

if [[ ! -d "$TARGET/scripts" ]]; then
    echo "ERREUR : $TARGET/scripts introuvable — installer d'abord avec scripts/install.sh." >&2
    exit 1
fi

echo "Synchronisation : $SOURCE_DIR/scripts -> $TARGET/scripts"
cp -a "$SOURCE_DIR/scripts/." "$TARGET/scripts/"
chown -R root:root "$TARGET/scripts"
chmod 0755 \
    "$TARGET/scripts/install.sh" \
    "$TARGET/scripts/config-web.py" \
    "$TARGET/scripts/onvif_client.py" \
    "$TARGET/scripts/ptz-bridge.py" \
    "$TARGET/scripts/check-camera-config.py" \
    "$TARGET/scripts/validate-release.sh" \
    "$TARGET/scripts/manage-tls.sh" \
    "$TARGET/scripts/sync-dev.sh"

echo "Redémarrage de pidecoder-config.service"
systemctl restart pidecoder-config.service

echo "OK — synchronisé et service redémarré."
