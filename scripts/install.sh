#!/usr/bin/env bash
set -Eeuo pipefail

readonly INSTALLER_VERSION="1.2.0"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SOURCE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
readonly UNIT_DIR="/etc/systemd/system"
readonly BACKUP_ROOT="/var/backups/pidecoder"

TARGET="/opt/pidecoder"
SERVICE_USER=""
WAYLAND_DISPLAY_NAME="wayland-0"
WEB_BIND="0.0.0.0"
WEB_PORT="8080"
WEB_HTTPS_PORT="8443"
TLS_CERT_PATH=""
TLS_KEY_PATH=""
NO_HTTPS=0
TLS_GENERATED=0
INSTALL_DEPENDENCIES=1
START_SERVICES=1
CHECK_ONLY=0

STAMP="$(date +%Y%m%d-%H%M%S)"
WORK_DIR=""
BACKUP_DIR=""
HAD_TARGET=0
CHANGED_SYSTEM=0
INSTALL_SUCCEEDED=0

log() {
    printf '\n==> %s\n' "$*"
}

warn() {
    printf 'AVERTISSEMENT : %s\n' "$*" >&2
}

fail() {
    printf 'ERREUR : %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
PiDecoder public installer

Usage:
  sudo ./scripts/install.sh [options]

Options:
  --user USER              Desktop/Wayland user running the video wall
  --target PATH            Installation directory (default: /opt/pidecoder)
  --wayland-display NAME   Wayland socket name (default: wayland-0)
  --bind ADDRESS           Web administration bind address (default: 0.0.0.0)
  --port PORT              Web administration HTTP port (default: 8080)
  --https-port PORT        Web administration HTTPS port (default: 8443).
                            HTTP and HTTPS run at the same time, each on its
                            own port, as soon as a certificate is present —
                            either can be turned off independently from the
                            Web UI's Sécurité tab (or manage-tls.sh for
                            HTTPS) without changing the other.
  --tls-cert PATH          Import a TLS certificate (PEM) instead of generating a
                            self-signed one. Requires --tls-key.
  --tls-key PATH           Import the matching TLS private key (PEM). Requires
                            --tls-cert.
  --no-https               Do not install a certificate; serve the Web
                            administration interface over plain HTTP only.
                            Mutually exclusive with --tls-cert/--tls-key.
  --skip-deps              Do not run apt-get
  --no-start               Install and enable units without starting them
  --check                  Validate the host and source without changing anything
  -h, --help               Show this help

Environment:
  PIDECODER_ALLOW_UNSUPPORTED=1  Allow a non-Debian-based host
EOF
}

cleanup() {
    if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
        rm -rf "$WORK_DIR"
    fi
}

restore_units() {
    local unit

    for unit in pidecoder.service pidecoder-config.service pidecoder-wayland.path pidecoder-wayland.target pidecoder-ptz.service; do
        if [[ -f "$BACKUP_DIR/systemd/$unit" ]]; then
            install -m 0644 "$BACKUP_DIR/systemd/$unit" "$UNIT_DIR/$unit"
        else
            rm -f "$UNIT_DIR/$unit"
        fi
    done
}

rollback() {
    local exit_code=$?
    trap - ERR INT TERM

    if [[ "$INSTALL_SUCCEEDED" -eq 0 && "$CHANGED_SYSTEM" -eq 1 ]]; then
        printf '\nInstallation interrompue — restauration de la version précédente.\n' >&2

        systemctl stop pidecoder.service pidecoder-config.service pidecoder-wayland.path pidecoder-wayland.target pidecoder-ptz.service 2>/dev/null || true
        rm -rf "$TARGET"

        if [[ "$HAD_TARGET" -eq 1 && -d "$BACKUP_DIR/target" ]]; then
            cp -a "$BACKUP_DIR/target" "$TARGET"
        fi

        restore_units
        systemctl daemon-reload 2>/dev/null || true

        if [[ "$HAD_TARGET" -eq 1 ]]; then
            systemctl reset-failed pidecoder-config.service pidecoder.service pidecoder-wayland.path pidecoder-wayland.target pidecoder-ptz.service 2>/dev/null || true
            systemctl restart pidecoder-ptz.service 2>/dev/null || true
            systemctl restart pidecoder-wayland.path 2>/dev/null || true
            systemctl restart pidecoder-config.service 2>/dev/null || true
            systemctl restart pidecoder.service 2>/dev/null || true
        fi

        printf 'Restauration terminée. Sauvegarde : %s\n' "$BACKUP_DIR" >&2
    fi

    cleanup
    exit "$exit_code"
}

trap rollback ERR INT TERM
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)
            [[ $# -ge 2 ]] || fail "Valeur manquante après --user"
            SERVICE_USER="$2"
            shift 2
            ;;
        --target)
            [[ $# -ge 2 ]] || fail "Valeur manquante après --target"
            TARGET="$2"
            shift 2
            ;;
        --wayland-display)
            [[ $# -ge 2 ]] || fail "Valeur manquante après --wayland-display"
            WAYLAND_DISPLAY_NAME="$2"
            shift 2
            ;;
        --bind)
            [[ $# -ge 2 ]] || fail "Valeur manquante après --bind"
            WEB_BIND="$2"
            shift 2
            ;;
        --port)
            [[ $# -ge 2 ]] || fail "Valeur manquante après --port"
            WEB_PORT="$2"
            shift 2
            ;;
        --https-port)
            [[ $# -ge 2 ]] || fail "Valeur manquante après --https-port"
            WEB_HTTPS_PORT="$2"
            shift 2
            ;;
        --tls-cert)
            [[ $# -ge 2 ]] || fail "Valeur manquante après --tls-cert"
            TLS_CERT_PATH="$2"
            shift 2
            ;;
        --tls-key)
            [[ $# -ge 2 ]] || fail "Valeur manquante après --tls-key"
            TLS_KEY_PATH="$2"
            shift 2
            ;;
        --no-https)
            NO_HTTPS=1
            shift
            ;;
        --skip-deps)
            INSTALL_DEPENDENCIES=0
            shift
            ;;
        --no-start)
            START_SERVICES=0
            shift
            ;;
        --check)
            CHECK_ONLY=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "Option inconnue : $1"
            ;;
    esac
done

TARGET="$(realpath -m "$TARGET")"

[[ "$TARGET" != *[[:space:]]* ]] || fail "Le chemin cible ne doit pas contenir d’espace"
[[ "$WEB_BIND" != *[[:space:]]* ]] || fail "L’adresse d’écoute Web ne doit pas contenir d’espace"

case "$TARGET" in
    /|/opt|/usr|/etc|/home|/var|/root)
        fail "Chemin cible dangereux : $TARGET"
        ;;
esac

# Garde-fou : ce script fait un « rm -rf "$TARGET" » plus loin. S'il est
# lancé depuis la copie déjà installée dans $TARGET (au lieu du dépôt git
# cloné), ou depuis un shell dont le répertoire courant se trouve sous
# $TARGET, cette suppression invalide le répertoire courant du processus en
# cours d'exécution en plein milieu de l'installation — ce qui a déjà
# provoqué un échec cryptique de cmake ("Current working directory cannot be
# established"). On le détecte tôt, avant toute modification, avec un
# message clair plutôt que de laisser planter la compilation à mi-chemin.
case "$SOURCE_ROOT" in
    "$TARGET"|"$TARGET"/*)
        fail "Ce script est lancé depuis l’installation existante ($TARGET) au lieu du dépôt source. Relance-le depuis ton clone git, ex. : cd ~/PiDecoder && sudo bash scripts/install.sh"
        ;;
esac

case "$(pwd -P)" in
    "$TARGET"|"$TARGET"/*)
        fail "Le répertoire courant est sous $TARGET, qui va être recréé pendant l’installation. Déplace-toi ailleurs (ex. : cd ~/PiDecoder) avant de relancer."
        ;;
esac

[[ "$WEB_PORT" =~ ^[0-9]+$ ]] || fail "Port Web invalide : $WEB_PORT"
(( WEB_PORT >= 1 && WEB_PORT <= 65535 )) || fail "Port Web hors plage : $WEB_PORT"
[[ "$WEB_HTTPS_PORT" =~ ^[0-9]+$ ]] || fail "Port Web HTTPS invalide : $WEB_HTTPS_PORT"
(( WEB_HTTPS_PORT >= 1 && WEB_HTTPS_PORT <= 65535 )) || fail "Port Web HTTPS hors plage : $WEB_HTTPS_PORT"
[[ "$WEB_PORT" != "$WEB_HTTPS_PORT" ]] || fail "--port et --https-port doivent être différents (les deux valent $WEB_PORT)"
[[ "$WAYLAND_DISPLAY_NAME" =~ ^[A-Za-z0-9._-]+$ ]] || fail "Nom de socket Wayland invalide"

if [[ "$NO_HTTPS" -eq 1 && ( -n "$TLS_CERT_PATH" || -n "$TLS_KEY_PATH" ) ]]; then
    fail "--no-https est incompatible avec --tls-cert/--tls-key"
fi

if [[ -n "$TLS_CERT_PATH" || -n "$TLS_KEY_PATH" ]]; then
    [[ -n "$TLS_CERT_PATH" && -n "$TLS_KEY_PATH" ]] || fail "--tls-cert et --tls-key doivent être fournis ensemble"
    [[ -r "$TLS_CERT_PATH" ]] || fail "Certificat TLS introuvable ou illisible : $TLS_CERT_PATH"
    [[ -r "$TLS_KEY_PATH" ]] || fail "Clé TLS introuvable ou illisible : $TLS_KEY_PATH"
    openssl x509 -in "$TLS_CERT_PATH" -noout >/dev/null 2>&1 || fail "Certificat TLS invalide (PEM attendu) : $TLS_CERT_PATH"
    # Comparaison par clé publique (fonctionne pour RSA et EC, contrairement à
    # -modulus qui est spécifique RSA) : évite d'installer un certificat et
    # une clé qui ne forment pas une paire valide.
    key_pubkey_digest="$(openssl pkey -in "$TLS_KEY_PATH" -pubout -outform DER 2>/dev/null | openssl dgst -sha256)"
    cert_pubkey_digest="$(openssl x509 -in "$TLS_CERT_PATH" -noout -pubkey 2>/dev/null | openssl pkey -pubin -outform DER 2>/dev/null | openssl dgst -sha256)"
    [[ -n "$key_pubkey_digest" && "$cert_pubkey_digest" == "$key_pubkey_digest" ]] || fail "Le certificat et la clé TLS fournis ne correspondent pas"
fi

[[ -f "$SOURCE_ROOT/CMakeLists.txt" ]] || fail "CMakeLists.txt introuvable dans $SOURCE_ROOT"
[[ -f "$SOURCE_ROOT/scripts/config-web.py" ]] || fail "Source Web introuvable"
[[ -f "$SOURCE_ROOT/systemd/pidecoder.service.in" ]] || fail "Template du service vidéo introuvable"
[[ -f "$SOURCE_ROOT/systemd/pidecoder-config.service.in" ]] || fail "Template du service Web introuvable"
[[ -f "$SOURCE_ROOT/systemd/pidecoder-wayland.path.in" ]] || fail "Template du déclencheur Wayland introuvable"
[[ -f "$SOURCE_ROOT/systemd/pidecoder-wayland.target.in" ]] || fail "Template de la cible Wayland introuvable"
[[ -f "$SOURCE_ROOT/systemd/pidecoder-ptz.service.in" ]] || fail "Template du pont PTZ introuvable"

if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
else
    fail "/etc/os-release est introuvable"
fi

if [[ "${ID:-}" != "debian" && "${ID:-}" != "raspbian" && " ${ID_LIKE:-} " != *" debian "* ]]; then
    if [[ "${PIDECODER_ALLOW_UNSUPPORTED:-0}" != "1" ]]; then
        fail "Système non pris en charge (${PRETTY_NAME:-inconnu}). PiDecoder cible Debian/Raspberry Pi OS."
    fi
    warn "Installation forcée sur ${PRETTY_NAME:-un système non identifié}"
fi

find_service_user() {
    local candidate
    local -a candidates=()

    if [[ -n "$SERVICE_USER" ]]; then
        return
    fi

    if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
        SERVICE_USER="$SUDO_USER"
        return
    fi

    candidate="$(logname 2>/dev/null || true)"
    if [[ -n "$candidate" && "$candidate" != "root" ]]; then
        SERVICE_USER="$candidate"
        return
    fi

    mapfile -t candidates < <(
        awk -F: '$3 >= 1000 && $3 < 65534 && $7 !~ /(nologin|false)$/ {print $1}' /etc/passwd
    )

    if [[ "${#candidates[@]}" -eq 1 ]]; then
        SERVICE_USER="${candidates[0]}"
        return
    fi

    fail "Impossible de déterminer l’utilisateur graphique. Relancer avec --user NOM."
}

find_service_user
id "$SERVICE_USER" >/dev/null 2>&1 || fail "Utilisateur inexistant : $SERVICE_USER"

SERVICE_UID="$(id -u "$SERVICE_USER")"
SERVICE_GROUP="$(id -gn "$SERVICE_USER")"

if [[ "$SERVICE_UID" -eq 0 ]]; then
    fail "PiDecoder vidéo ne doit pas fonctionner avec l’utilisateur root"
fi

SUPPLEMENTARY_GROUP_LIST=()
for group in video render; do
    if getent group "$group" >/dev/null; then
        SUPPLEMENTARY_GROUP_LIST+=("$group")
    fi
done

SUPPLEMENTARY_GROUPS=""
if [[ "${#SUPPLEMENTARY_GROUP_LIST[@]}" -gt 0 ]]; then
    SUPPLEMENTARY_GROUPS="SupplementaryGroups=${SUPPLEMENTARY_GROUP_LIST[*]}"
fi

PACKAGES=(
    build-essential
    ca-certificates
    cmake
    ffmpeg
    iproute2
    libgl1-mesa-dev
    libmpv-dev
    libsdl2-dev
    nlohmann-json3-dev
    pkg-config
    python3
)

check_source() {
    log "Validation des sources PiDecoder"
    bash -n "$SOURCE_ROOT/scripts/install.sh"
    python3 -m py_compile \
        "$SOURCE_ROOT/scripts/config-web.py" \
        "$SOURCE_ROOT/scripts/onvif_client.py" \
        "$SOURCE_ROOT/scripts/check-camera-config.py" \
        "$SOURCE_ROOT/scripts/ptz-bridge.py"

    if [[ -x "$SOURCE_ROOT/scripts/validate-release.sh" ]]; then
        "$SOURCE_ROOT/scripts/validate-release.sh"
    fi
}

check_host() {
    local -a missing=()
    local package

    for package in "${PACKAGES[@]}"; do
        if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
            missing+=("$package")
        fi
    done

    printf 'Système       : %s\n' "${PRETTY_NAME:-inconnu}"
    printf 'Architecture  : %s\n' "$(uname -m)"
    if [[ "$(uname -m)" != "aarch64" ]]; then
        warn "La cible v1.1 validée est Raspberry Pi 5 en aarch64."
    fi
    printf 'Utilisateur   : %s (uid %s, groupe %s)\n' "$SERVICE_USER" "$SERVICE_UID" "$SERVICE_GROUP"
    printf 'Cible         : %s\n' "$TARGET"
    printf 'Wayland       : /run/user/%s/%s\n' "$SERVICE_UID" "$WAYLAND_DISPLAY_NAME"
    if [[ "$NO_HTTPS" -eq 1 ]]; then
        printf 'Administration: http://%s:%s (--no-https)\n' "$WEB_BIND" "$WEB_PORT"
    else
        printf 'Administration: http://%s:%s + https://%s:%s\n' "$WEB_BIND" "$WEB_PORT" "$WEB_BIND" "$WEB_HTTPS_PORT"
    fi

    if [[ -S "/run/user/$SERVICE_UID/$WAYLAND_DISPLAY_NAME" ]]; then
        printf 'Session vidéo : détectée\n'
    else
        printf 'Session vidéo : non détectée actuellement (le service attendra la session graphique)\n'
    fi

    if [[ "${#missing[@]}" -eq 0 ]]; then
        printf 'Dépendances   : présentes\n'
    else
        printf 'Dépendances   : manquantes : %s\n' "${missing[*]}"
    fi
}

check_source
check_host

if [[ "$CHECK_ONLY" -eq 1 ]]; then
    log "Contrôle terminé — aucune modification effectuée"
    exit 0
fi

[[ "$EUID" -eq 0 ]] || fail "Relancer l’installateur avec sudo"
command -v systemctl >/dev/null || fail "systemd est requis"
command -v apt-get >/dev/null || fail "apt-get est requis sur la plateforme actuellement prise en charge"

if [[ ! -f "$TARGET/config/web-auth.json" && ! -r /dev/tty ]]; then
    fail "Une console interactive est nécessaire pour créer le mot de passe Web initial."
fi

if [[ "$INSTALL_DEPENDENCIES" -eq 1 ]]; then
    log "Installation des dépendances Debian"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${PACKAGES[@]}"
else
    log "Installation des dépendances ignorée (--skip-deps)"
fi

for command in cmake pkg-config python3 c++; do
    command -v "$command" >/dev/null || fail "Commande requise absente : $command"
done

pkg-config --exists sdl2 || fail "pkg-config ne trouve pas SDL2"
pkg-config --exists mpv || fail "pkg-config ne trouve pas libmpv"

for group in "${SUPPLEMENTARY_GROUP_LIST[@]}"; do
    if ! id -nG "$SERVICE_USER" | tr ' ' '\n' | grep -Fxq "$group"; then
        usermod -a -G "$group" "$SERVICE_USER"
        warn "$SERVICE_USER a été ajouté au groupe $group. Une reconnexion de session peut être nécessaire."
    fi
done

WORK_DIR="$(mktemp -d /tmp/pidecoder-install.XXXXXX)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
mkdir -p "$BACKUP_DIR/systemd"

if [[ -d "$TARGET" ]]; then
    HAD_TARGET=1
    log "Sauvegarde de l’installation existante"
    cp -a "$TARGET" "$BACKUP_DIR/target"
fi

for unit in pidecoder.service pidecoder-config.service pidecoder-wayland.path pidecoder-wayland.target pidecoder-ptz.service; do
    if [[ -f "$UNIT_DIR/$unit" ]]; then
        cp -a "$UNIT_DIR/$unit" "$BACKUP_DIR/systemd/$unit"
    fi
done

log "Préparation des fichiers"
STAGED_ROOT="$WORK_DIR/root"
mkdir -p "$STAGED_ROOT"

copy_items=(
    CMakeLists.txt
    src
    include
    tests
    scripts
    systemd
    config
    README.md
    CHANGELOG.md
    LICENSE
)

for item in "${copy_items[@]}"; do
    if [[ -e "$SOURCE_ROOT/$item" ]]; then
        cp -a "$SOURCE_ROOT/$item" "$STAGED_ROOT/"
    fi
done

rm -rf "$STAGED_ROOT/build" "$STAGED_ROOT/.git"
rm -f \
    "$STAGED_ROOT/config/cameras.json" \
    "$STAGED_ROOT/config/layout.json" \
    "$STAGED_ROOT/config/web-auth.json"

if [[ "$HAD_TARGET" -eq 1 ]]; then
    for runtime in cameras.json layout.json web-auth.json; do
        if [[ -f "$TARGET/config/$runtime" ]]; then
            cp -a "$TARGET/config/$runtime" "$STAGED_ROOT/config/$runtime"
        fi
    done

    if [[ -d "$TARGET/config/backups" ]]; then
        cp -a "$TARGET/config/backups" "$STAGED_ROOT/config/backups"
    fi
fi

mkdir -p "$STAGED_ROOT/config/backups" "$STAGED_ROOT/config/tls"

if [[ "$NO_HTTPS" -eq 1 ]]; then
    log "HTTPS désactivé (--no-https) : aucun certificat ne sera installé"
    # config-web.py sert automatiquement en HTTP simple dès qu'aucun
    # certificat n'est présent sous config/tls/ — rien d'autre à faire ici.
    # Un certificat conservé d'une précédente installation n'est
    # délibérément pas repris : --no-https est un choix explicite. Il reste
    # dans la sauvegarde de $TARGET (voir plus haut) si besoin de revenir en
    # arrière.
    if [[ "$HAD_TARGET" -eq 1 && -f "$TARGET/config/tls/cert.pem" ]]; then
        warn "Un navigateur déjà connecté en HTTPS auparavant a gardé en" \
             "mémoire un cookie de session « Secure », que la connexion" \
             "HTTP simple ne pourra pas remplacer (règle de sécurité du" \
             "navigateur) : la connexion semblera acceptée mais restera" \
             "bloquée juste après, sans erreur visible. Si ça arrive," \
             "effacer les cookies du site pour ce Pi dans le navigateur" \
             "concerné, une seule fois."
    fi
elif [[ -n "$TLS_CERT_PATH" ]]; then
    log "Installation du certificat TLS fourni"
    install -m 0644 "$TLS_CERT_PATH" "$STAGED_ROOT/config/tls/cert.pem"
    install -m 0600 "$TLS_KEY_PATH" "$STAGED_ROOT/config/tls/key.pem"
elif [[ "$HAD_TARGET" -eq 1 && -f "$TARGET/config/tls/cert.pem" && -f "$TARGET/config/tls/key.pem" ]]; then
    log "Conservation du certificat TLS existant"
    cp -a "$TARGET/config/tls/cert.pem" "$STAGED_ROOT/config/tls/cert.pem"
    cp -a "$TARGET/config/tls/key.pem" "$STAGED_ROOT/config/tls/key.pem"
else
    log "Génération d'un certificat TLS auto-signé"

    # Un Raspberry Pi de ce type n'a en général ni domaine public ni DNS
    # stable : le certificat est auto-signé (comme la plupart des interfaces
    # d'administration réseau — routeur, NAS...) et couvre le nom d'hôte
    # local ainsi que les adresses IPv4 actuellement configurées, pour que le
    # navigateur accepte de faire confiance à l'IP utilisée pour se connecter,
    # une fois l'avertissement initial validé manuellement.
    cert_cn="$(hostname -f 2>/dev/null || hostname)"
    san_entries=("DNS:$cert_cn" "DNS:localhost" "IP:127.0.0.1")

    while IFS= read -r ip; do
        [[ -n "$ip" ]] || continue
        san_entries+=("IP:$ip")
    done < <(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$')

    san_list="$(IFS=,; echo "${san_entries[*]}")"

    openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
        -keyout "$STAGED_ROOT/config/tls/key.pem" \
        -out "$STAGED_ROOT/config/tls/cert.pem" \
        -subj "/CN=$cert_cn" \
        -addext "subjectAltName=$san_list" \
        >/dev/null 2>&1 \
        || fail "Échec de la génération du certificat TLS auto-signé"

    TLS_GENERATED=1
fi

if [[ ! -f "$STAGED_ROOT/config/cameras.json" ]]; then
    cat > "$STAGED_ROOT/config/cameras.json" <<'JSON'
{
  "cameras": []
}
JSON
fi

if [[ ! -f "$STAGED_ROOT/config/layout.json" ]]; then
    cat > "$STAGED_ROOT/config/layout.json" <<'JSON'
{
  "columns": 3,
  "rows": 3,
  "fullscreen_on_start": false,
  "camera_order": [],
  "placements": []
}
JSON
fi

CHANGED_SYSTEM=1
systemctl stop pidecoder.service pidecoder-config.service pidecoder-wayland.path pidecoder-wayland.target pidecoder-ptz.service 2>/dev/null || true
rm -rf "$TARGET"
install -d -m 0755 "$(dirname "$TARGET")"
cp -a "$STAGED_ROOT" "$TARGET"

log "Compilation de PiDecoder"
export PKG_CONFIG_PATH="/usr/local/lib/aarch64-linux-gnu/pkgconfig:/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:${LD_LIBRARY_PATH:-}"

cmake -S "$TARGET" -B "$TARGET/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$TARGET"
cmake --build "$TARGET/build" -j"$(nproc)"
cmake --install "$TARGET/build" --prefix "$TARGET"

test -x "$TARGET/bin/pidecoder" || fail "Le binaire installé est introuvable"

log "Configuration des droits"
chown -R root:root "$TARGET"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$TARGET/config"
chmod 0750 "$TARGET/config" "$TARGET/config/backups" "$TARGET/config/tls"
chmod 0600 "$TARGET/config/cameras.json" "$TARGET/config/layout.json"

if [[ -f "$TARGET/config/tls/cert.pem" && -f "$TARGET/config/tls/key.pem" ]]; then
    chown root:root "$TARGET/config/tls/cert.pem" "$TARGET/config/tls/key.pem"
    chmod 0644 "$TARGET/config/tls/cert.pem"
    chmod 0600 "$TARGET/config/tls/key.pem"
fi
chmod 0755 \
    "$TARGET/scripts/install.sh" \
    "$TARGET/scripts/config-web.py" \
    "$TARGET/scripts/onvif_client.py" \
    "$TARGET/scripts/ptz-bridge.py" \
    "$TARGET/scripts/check-camera-config.py" \
    "$TARGET/scripts/validate-release.sh" \
    "$TARGET/scripts/manage-tls.sh"

if [[ -f "$TARGET/config/web-auth.json" ]]; then
    chown root:root "$TARGET/config/web-auth.json"
    chmod 0600 "$TARGET/config/web-auth.json"
else
    log "Création du compte administrateur Web"
    printf 'Choisis maintenant le mot de passe du compte admin (8 caractères minimum).\n'
    PIDECODER_USER="$SERVICE_USER" \
        python3 "$TARGET/scripts/config-web.py" \
        --root "$TARGET" \
        --set-password \
        --username admin
fi

log "Génération des services systemd"
python3 - \
    "$TARGET/systemd/pidecoder.service.in" \
    "$UNIT_DIR/pidecoder.service" \
    "$TARGET/systemd/pidecoder-config.service.in" \
    "$UNIT_DIR/pidecoder-config.service" \
    "$TARGET/systemd/pidecoder-wayland.path.in" \
    "$UNIT_DIR/pidecoder-wayland.path" \
    "$TARGET/systemd/pidecoder-wayland.target.in" \
    "$UNIT_DIR/pidecoder-wayland.target" \
    "$TARGET/systemd/pidecoder-ptz.service.in" \
    "$UNIT_DIR/pidecoder-ptz.service" \
    "$SERVICE_USER" \
    "$SERVICE_GROUP" \
    "$SERVICE_UID" \
    "$SUPPLEMENTARY_GROUPS" \
    "$TARGET" \
    "$WAYLAND_DISPLAY_NAME" \
    "$WEB_BIND" \
    "$WEB_PORT" \
    "$WEB_HTTPS_PORT" \
    "$SOURCE_ROOT" <<'PY_RENDER_UNITS'
from pathlib import Path
import sys

(
    video_source,
    video_target,
    web_source,
    web_target,
    path_source,
    path_target,
    wayland_target_source,
    wayland_target_target,
    ptz_source,
    ptz_target,
    service_user,
    service_group,
    service_uid,
    supplementary_groups,
    target,
    wayland_display,
    web_bind,
    web_port,
    web_https_port,
    repo_path,
) = sys.argv[1:]

replacements = {
    "@SERVICE_USER@": service_user,
    "@SERVICE_GROUP@": service_group,
    "@SERVICE_UID@": service_uid,
    "@SUPPLEMENTARY_GROUPS@": supplementary_groups,
    "@TARGET@": target,
    "@WAYLAND_DISPLAY@": wayland_display,
    "@WEB_BIND@": web_bind,
    "@WEB_PORT@": web_port,
    "@WEB_HTTPS_PORT@": web_https_port,
    "@REPO_PATH@": repo_path,
}

for source, destination in (
    (video_source, video_target),
    (web_source, web_target),
    (path_source, path_target),
    (wayland_target_source, wayland_target_target),
    (ptz_source, ptz_target),
):
    content = Path(source).read_text(encoding="utf-8")
    for old, new in replacements.items():
        content = content.replace(old, new)
    if any(token in content for token in replacements):
        raise SystemExit(f"Placeholder non remplacé dans {source}")
    Path(destination).write_text(content, encoding="utf-8")
PY_RENDER_UNITS

chmod 0644 \
    "$UNIT_DIR/pidecoder.service" \
    "$UNIT_DIR/pidecoder-config.service" \
    "$UNIT_DIR/pidecoder-wayland.path" \
    "$UNIT_DIR/pidecoder-wayland.target" \
    "$UNIT_DIR/pidecoder-ptz.service"
systemctl daemon-reload
systemctl disable pidecoder.service 2>/dev/null || true
systemctl enable \
    pidecoder-config.service \
    pidecoder-wayland.path \
    pidecoder-ptz.service

if [[ "$START_SERVICES" -eq 1 ]]; then
    log "Démarrage de l’administration Web"
    systemctl reset-failed \
        pidecoder-config.service \
        pidecoder.service \
        pidecoder-wayland.path \
        pidecoder-wayland.target \
        pidecoder-ptz.service \
        2>/dev/null || true
    systemctl restart pidecoder-ptz.service
    systemctl restart pidecoder-wayland.path
    systemctl restart pidecoder-config.service
    sleep 2
    systemctl is-active --quiet pidecoder-ptz.service || fail "Le pont PTZ ne démarre pas"
    systemctl is-active --quiet pidecoder-config.service || fail "L’administration Web ne démarre pas"

    if python3 "$TARGET/scripts/check-camera-config.py" "$TARGET/config/cameras.json"; then
        if [[ -S "/run/user/$SERVICE_UID/$WAYLAND_DISPLAY_NAME" ]]; then
            systemctl restart pidecoder.service
            sleep 2
            if ! systemctl is-active --quiet pidecoder.service; then
                warn "Le moteur vidéo n’est pas actif. Consulter : journalctl -u pidecoder.service -n 50"
            fi
        else
            warn "Configuration caméra présente, mais le socket Wayland est absent. Le moteur démarrera avec la session graphique."
        fi
    else
        systemctl stop pidecoder.service 2>/dev/null || true
        printf 'Moteur vidéo : en attente de la première caméra.\n'
    fi
else
    log "Services installés mais non démarrés (--no-start)"
fi

INSTALL_SUCCEEDED=1
trap - ERR INT TERM

HOST_ADDRESS="$(hostname -I 2>/dev/null | awk '{print $1}')"
[[ -n "$HOST_ADDRESS" ]] || HOST_ADDRESS="ADRESSE_DU_RASPBERRY_PI"

printf '\nPiDecoder %s est installé.\n' "$INSTALLER_VERSION"
if [[ "$NO_HTTPS" -eq 1 ]]; then
    printf 'Administration Web : http://%s:%s (HTTPS désactivé, --no-https)\n' "$HOST_ADDRESS" "$WEB_PORT"
else
    printf 'Administration Web : http://%s:%s et https://%s:%s (HTTP désactivable\n' "$HOST_ADDRESS" "$WEB_PORT" "$HOST_ADDRESS" "$WEB_HTTPS_PORT"
    printf '                     séparément depuis l'"'"'onglet Sécurité si besoin)\n'
fi
printf 'Utilisateur Web     : admin\n'
printf 'Utilisateur vidéo   : %s\n' "$SERVICE_USER"
printf 'Installation        : %s\n' "$TARGET"
printf 'Sauvegarde          : %s\n' "$BACKUP_DIR"

if [[ "$TLS_GENERATED" -eq 1 ]]; then
    printf '\nLe certificat TLS est auto-signé : le navigateur affichera un avertissement\n'
    printf 'la première fois — valider/accepter le certificat pour continuer.\n'
fi

if [[ "$NO_HTTPS" -eq 0 ]]; then
    printf '\nPour changer de certificat ou désactiver HTTPS sans réinstaller :\n'
    printf '  sudo ./scripts/manage-tls.sh --help\n'
fi

if [[ ! -S "/run/user/$SERVICE_UID/$WAYLAND_DISPLAY_NAME" ]]; then
    printf '\nLe socket Wayland n’est pas présent actuellement. Connecte la session graphique de %s avant de lancer le mur vidéo.\n' "$SERVICE_USER"
fi
