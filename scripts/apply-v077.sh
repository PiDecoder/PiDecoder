#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/opt/pidecoder}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.backup-v0.7.6-${STAMP}"
AUTH_FILE="$TARGET/config/web-auth.json"

[[ -d "$TARGET" ]] || { echo "Dossier cible introuvable : $TARGET" >&2; exit 1; }
echo "Sauvegarde : $BACKUP"
cp -a "$TARGET" "$BACKUP"
install -m 0644 "$PATCH_DIR/CMakeLists.txt" "$TARGET/CMakeLists.txt"
install -m 0755 "$PATCH_DIR/scripts/config-web.py" "$TARGET/scripts/config-web.py"
install -m 0644 "$PATCH_DIR/systemd/pidecoder-config.service" /etc/systemd/system/pidecoder-config.service

if [[ ! -f "$AUTH_FILE" ]]; then
  echo; echo "Initialisation du compte Web admin."
  /usr/bin/python3 "$TARGET/scripts/config-web.py" --root "$TARGET" --set-password --username admin
else
  echo "Compte Web existant conservé."
fi

for f in cameras.json layout.json; do
  [[ -f "$TARGET/config/$f" ]] && chown admin:admin "$TARGET/config/$f" && chmod 600 "$TARGET/config/$f"
done

cd "$TARGET"
rm -rf build
export PKG_CONFIG_PATH="/usr/local/lib/aarch64-linux-gnu/pkgconfig:/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:${LD_LIBRARY_PATH:-}"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
systemctl daemon-reload
systemctl enable --now pidecoder-config.service
systemctl restart pidecoder-config.service

echo
echo "PiDecoder v0.7.7 installé."
echo "Interface : http://IP_DU_PI:8080"
echo "Moteur vidéo : logique v0.7.6 inchangée"
echo "Backup : $BACKUP"
