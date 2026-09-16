#!/bin/bash
# Fabrique une image .img de PiDecoder, flashable directement sur carte SD.
#
# Principe : partir de l'image officielle Raspberry Pi OS Lite arm64, l'ouvrir
# en boucle locale (loop device), y installer dans un chroot la pile Wayland
# minimale puis PiDecoder lui-même, retirer tout ce qui doit rester unique à
# chaque appareil, puis réduire et compresser le résultat.
#
# Pourquoi ne pas utiliser pi-gen (l'outil officiel) : pi-gen reconstruit tout
# le système depuis un debootstrap, ce qui prend des heures et nous mettrait
# en charge d'un système complet là où on n'a besoin que d'ajouter une
# application à une image déjà éprouvée. Partir de l'image officielle publiée
# garde exactement le même système que celui validé sur le terrain — la seule
# différence entre une carte flashée avec cette image et une installation
# manuelle, c'est qui a tapé les commandes.
#
# Deux environnements d'exécution sont prévus :
#   - sur un Raspberry Pi (ou toute machine arm64 sous Debian) : le chroot est
#     natif, rien à préparer ;
#   - sur une machine x86_64 : il faut binfmt_misc et qemu-user-static pour
#     que les binaires arm64 du chroot puissent s'exécuter. C'est ce que fait
#     le workflow .github/workflows/build-image.yml.
#
# Ce script ne touche jamais à la machine sur laquelle il tourne en dehors de
# son répertoire de travail : tout se passe dans l'image montée.
set -Eeuo pipefail

readonly BUILDER_VERSION="1.2.0"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SOURCE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Image de base épinglée (et non « la dernière en date ») : une image publiée
# doit pouvoir être refabriquée à l'identique, et la somme de contrôle vérifie
# le téléchargement. Surchargeable avec --base-url/--base-sha256 pour suivre
# une nouvelle version de Raspberry Pi OS.
#
# Bookworm (Debian 12, « oldstable ») plutôt que Trixie (Debian 13, devenue
# la version courante mi-2025) : sur la toute première carte réellement
# flashée avec une base Trixie, le mur vidéo plantait en boucle (SIGILL,
# précédé d'un flot de « MESA: error: Export failed » côté Wayland/V3D lors
# de l'export des buffers vers labwc). Le journal WAYLAND_DEBUG montrait le
# protocole continuer à fonctionner (attach/commit réussissaient malgré les
# erreurs répétées) avant le crash — le profil d'un bug du pilote Mesa/V3D
# lui-même sur une combinaison noyau/Mesa trop récente pour être mûre, pas
# d'un souci de configuration côté image. Bookworm est précisément la version
# déjà validée sur le terrain pour ce même rendu SDL2/labwc/V3D (voir
# PROJECT-STATE.md, « RC3 field validation ») sur la machine de production
# (`olympus-vss-mon1`) : c'est donc la base la plus sûre tant que Trixie n'a
# pas fait ses preuves sur ce pipeline précis.
BASE_URL="https://downloads.raspberrypi.com/raspios_oldstable_lite_arm64/images/raspios_oldstable_lite_arm64-2026-09-15/2026-09-15-raspios-bookworm-arm64-lite.img.xz"
BASE_SHA256="bcaefdf9c40dbed31dcaeb3b8494e498b4f1e3078c2604b0d9f5f595f8f6fd91"

IMAGE_USER="pidecoder"
IMAGE_USER_PASSWORD="pidecoder"
WEB_PASSWORD="pidecoder"
OUTPUT=""
WORK_ROOT=""
CACHE_DIR="${PIDECODER_IMAGE_CACHE:-${HOME:-/root}/.cache/pidecoder-image}"
BASE_IMAGE_FILE=""
# Place ajoutée à la partition racine pendant la construction. Il faut y loger
# la chaîne de compilation (build-essential, cmake, en-têtes SDL2/mpv), le
# clone Git, la compilation elle-même et le cache apt. ~3,5 Gio laisse une
# marge confortable ; tout est réduit à la fin, ça ne coûte rien au résultat.
EXTRA_SPACE_MB=3500
# Marge laissée dans la partition racine de l'image finale. Le mécanisme
# d'agrandissement de Raspberry Pi OS occupe toute la carte SD au premier
# démarrage, mais une racine réduite au strict minimum absolu est fragile si
# ce mécanisme échoue.
FREE_SPACE_MB=300
COMPRESS=1
CUSTOMIZE=1
KEEP_WORK=0

# --- Journalisation ---------------------------------------------------------
log()  { printf '\033[1;36m[build-image]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[build-image] ATTENTION :\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[build-image] ERREUR :\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
    cat <<'EOF'
PiDecoder SD-card image builder

Usage:
  sudo ./scripts/build-image.sh [options]

Options:
  --output PATH        Final .img.xz path (default: dist/PiDecoder-<version>-arm64.img.xz)
  --work-dir PATH      Scratch directory (default: a temporary directory)
  --cache-dir PATH     Where the base Raspberry Pi OS image is cached
  --base-image PATH    Use this already-downloaded base image (.img or .img.xz)
  --base-url URL       Download the base image from URL instead of the pinned one
  --base-sha256 HASH   Expected SHA256 of the base image (required with --base-url)
  --user NAME          Desktop/Wayland user created in the image (default: pidecoder)
  --user-password PW   Password of that Linux user (default: pidecoder)
  --web-password PW    Initial PiDecoder Web admin password. Always flagged as
                        "must be changed at first login" (default: pidecoder)
  --extra-space MB     Scratch space added to the root partition while building
  --free-space MB      Free space left in the shrunk image (default: 300)
  --no-compress        Leave the raw .img instead of compressing it to .img.xz
  --no-customize       Only exercise the image plumbing (grow/mount/shrink) and
                        skip every chroot step. Useful to test this script on a
                        host that cannot run arm64 binaries.
  --keep-work          Do not delete the work directory on exit
  -h, --help           Show this help

Requirements:
  root, losetup with partition support, sfdisk, e2fsck/resize2fs, xz, curl or
  wget, and either an arm64 host or binfmt_misc + qemu-user-static.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)         [[ $# -ge 2 ]] || fail "Valeur manquante après --output";        OUTPUT="$2"; shift 2 ;;
        --work-dir)       [[ $# -ge 2 ]] || fail "Valeur manquante après --work-dir";      WORK_ROOT="$2"; shift 2 ;;
        --cache-dir)      [[ $# -ge 2 ]] || fail "Valeur manquante après --cache-dir";     CACHE_DIR="$2"; shift 2 ;;
        --base-image)     [[ $# -ge 2 ]] || fail "Valeur manquante après --base-image";    BASE_IMAGE_FILE="$2"; shift 2 ;;
        --base-url)       [[ $# -ge 2 ]] || fail "Valeur manquante après --base-url";      BASE_URL="$2"; BASE_SHA256=""; shift 2 ;;
        --base-sha256)    [[ $# -ge 2 ]] || fail "Valeur manquante après --base-sha256";   BASE_SHA256="$2"; shift 2 ;;
        --user)           [[ $# -ge 2 ]] || fail "Valeur manquante après --user";          IMAGE_USER="$2"; shift 2 ;;
        --user-password)  [[ $# -ge 2 ]] || fail "Valeur manquante après --user-password"; IMAGE_USER_PASSWORD="$2"; shift 2 ;;
        --web-password)   [[ $# -ge 2 ]] || fail "Valeur manquante après --web-password";  WEB_PASSWORD="$2"; shift 2 ;;
        --extra-space)    [[ $# -ge 2 ]] || fail "Valeur manquante après --extra-space";   EXTRA_SPACE_MB="$2"; shift 2 ;;
        --free-space)     [[ $# -ge 2 ]] || fail "Valeur manquante après --free-space";    FREE_SPACE_MB="$2"; shift 2 ;;
        --no-compress)    COMPRESS=0; shift ;;
        --no-customize)   CUSTOMIZE=0; shift ;;
        --keep-work)      KEEP_WORK=1; shift ;;
        -h|--help)        usage; exit 0 ;;
        *)                usage >&2; fail "Option inconnue : $1" ;;
    esac
done

[[ "$EXTRA_SPACE_MB" =~ ^[0-9]+$ ]] || fail "--extra-space attend un nombre de Mio"
[[ "$FREE_SPACE_MB"  =~ ^[0-9]+$ ]] || fail "--free-space attend un nombre de Mio"
[[ "$IMAGE_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || fail "Nom d'utilisateur invalide : $IMAGE_USER"
[[ "$IMAGE_USER" != "root" ]] || fail "L'utilisateur de l'image ne peut pas être root"
[[ "${#WEB_PASSWORD}" -ge 8 ]] || fail "--web-password doit faire au moins 8 caractères (contrainte de l'interface Web)"

# --- Préalables -------------------------------------------------------------
[[ "$EUID" -eq 0 ]] || fail "Ce script doit tourner en root (montage en boucle locale, chroot)"

for tool in losetup sfdisk e2fsck resize2fs dumpe2fs blkid truncate xz sha256sum python3; do
    command -v "$tool" >/dev/null || fail "Outil requis absent : $tool"
done

DOWNLOADER=""
if command -v curl >/dev/null; then
    DOWNLOADER="curl"
elif command -v wget >/dev/null; then
    DOWNLOADER="wget"
elif [[ -z "$BASE_IMAGE_FILE" ]]; then
    fail "curl ou wget est requis pour télécharger l'image de base (ou utiliser --base-image)"
fi

HOST_ARCH="$(uname -m)"
NEEDS_QEMU=0
if [[ "$HOST_ARCH" != "aarch64" && "$HOST_ARCH" != "arm64" ]]; then
    NEEDS_QEMU=1
fi

VERSION="$(awk '/^[[:space:]]*VERSION[[:space:]]+[0-9]/ {print $2; exit}' "$SOURCE_ROOT/CMakeLists.txt" 2>/dev/null || true)"
[[ -n "$VERSION" ]] || VERSION="$BUILDER_VERSION"

if [[ -z "$OUTPUT" ]]; then
    OUTPUT="$SOURCE_ROOT/dist/PiDecoder-${VERSION}-arm64.img"
    [[ "$COMPRESS" -eq 1 ]] && OUTPUT="${OUTPUT}.xz"
fi

# --- Nettoyage garanti ------------------------------------------------------
# Un build interrompu ne doit jamais laisser derrière lui un montage actif ou
# un périphérique en boucle attaché : la machine de build servirait ensuite à
# autre chose avec une image à moitié montée sur le dos.
MOUNTED=()
LOOP_DEVS=()
WORK_DIR=""

cleanup() {
    local status=$?
    set +e
    local index
    for (( index=${#MOUNTED[@]}-1 ; index>=0 ; index-- )); do
        umount "${MOUNTED[index]}" 2>/dev/null || umount -l "${MOUNTED[index]}" 2>/dev/null
    done
    MOUNTED=()
    for (( index=${#LOOP_DEVS[@]}-1 ; index>=0 ; index-- )); do
        losetup -d "${LOOP_DEVS[index]}" 2>/dev/null
    done
    LOOP_DEVS=()
    if [[ -n "$WORK_DIR" && "$KEEP_WORK" -eq 0 && -d "$WORK_DIR" ]]; then
        rm -rf "$WORK_DIR"
    elif [[ -n "$WORK_DIR" && "$KEEP_WORK" -eq 1 ]]; then
        log "Répertoire de travail conservé : $WORK_DIR"
    fi
    exit "$status"
}
trap cleanup EXIT INT TERM

mount_tracked() {
    mount "$@" || fail "Montage impossible : $*"
    MOUNTED+=("${*: -1}")
}

# e2fsck renvoie un code composite qu'il ne faut surtout pas ignorer en bloc :
#   0  rien à signaler
#   1  erreurs corrigées (banal sur une image tout juste redimensionnée)
#   2  erreurs corrigées, redémarrage conseillé (sans objet : rien n'est monté)
#   >=4 erreurs NON corrigées, ou échec de l'outil lui-même
# Livrer une carte SD dont le système de fichiers est douteux donnerait un Pi
# qui ne démarre pas, avec un diagnostic très pénible à distance : on préfère
# échouer ici, bruyamment.
run_fsck() {
    local device="$1" status=0
    e2fsck -pf "$device" >/dev/null 2>&1 || status=$?
    if [[ "$status" -ge 4 ]]; then
        fail "e2fsck signale un problème non corrigé sur $device (code $status)"
    fi
}

umount_all() {
    local index
    for (( index=${#MOUNTED[@]}-1 ; index>=0 ; index-- )); do
        umount "${MOUNTED[index]}" || fail "Démontage impossible : ${MOUNTED[index]}"
    done
    MOUNTED=()
}

# --- Répertoire de travail --------------------------------------------------
if [[ -n "$WORK_ROOT" ]]; then
    mkdir -p "$WORK_ROOT"
    WORK_DIR="$(mktemp -d "$WORK_ROOT/pidecoder-image.XXXXXX")"
else
    WORK_DIR="$(mktemp -d /var/tmp/pidecoder-image.XXXXXX)"
fi

MNT="$WORK_DIR/mnt"
mkdir -p "$MNT"

available_mb() { df -Pm "$1" | awk 'NR==2 {print $4}'; }

# Trois emplacements peuvent tomber sur des systèmes de fichiers différents, et
# rien n'oblige à ce qu'ils soient tous sur la carte SD du Pi : le répertoire
# de travail (le gros morceau : image de base décompressée puis agrandie), le
# cache de téléchargement, et le dossier de sortie. Ils sont donc vérifiés
# séparément — un Raspberry Pi de production n'a bien souvent pas 10 Gio libres
# sur sa propre carte, alors qu'une clé USB branchée dessus fait très bien
# l'affaire.
check_space() {
    local label="$1" directory="$2" needed="$3" flag="$4" have
    have="$(available_mb "$directory")"
    if [[ -z "$have" ]]; then
        warn "Espace disque invérifiable pour $label ($directory)"
        return
    fi
    if [[ "$have" -lt "$needed" ]]; then
        fail "Espace disque insuffisant pour $label : ${have} Mio libres dans $directory, environ ${needed} Mio nécessaires.
       Utiliser $flag pour pointer vers un disque plus grand (clé USB, disque externe),
       ou laisser GitHub Actions fabriquer l'image (.github/workflows/build-image.yml)."
    fi
}

# Répertoire de travail : image de base décompressée (~3 Gio) + la place
# ajoutée pour la compilation.
check_space "le répertoire de travail" "$WORK_DIR" "$(( EXTRA_SPACE_MB + 3500 ))" "--work-dir"

# Sortie : l'image compressée, autour d'un gigaoctet.
OUTPUT_DIR="$(dirname "$OUTPUT")"
mkdir -p "$OUTPUT_DIR"
check_space "l'image finale" "$OUTPUT_DIR" 1500 "--output"

# Cache : uniquement si l'image de base doit être téléchargée.
if [[ -z "$BASE_IMAGE_FILE" ]]; then
    mkdir -p "$CACHE_DIR"
    check_space "le cache de l'image de base" "$CACHE_DIR" 700 "--cache-dir"
fi

log "PiDecoder $VERSION — construction de l'image (base : $(basename "$BASE_URL"))"

# --- 1. Image de base -------------------------------------------------------
IMG="$WORK_DIR/pidecoder.img"

if [[ -n "$BASE_IMAGE_FILE" ]]; then
    [[ -f "$BASE_IMAGE_FILE" ]] || fail "Image de base introuvable : $BASE_IMAGE_FILE"
    log "Image de base fournie : $BASE_IMAGE_FILE"
    if [[ "$BASE_IMAGE_FILE" == *.xz ]]; then
        xz -dc "$BASE_IMAGE_FILE" >"$IMG"
    else
        cp --sparse=always "$BASE_IMAGE_FILE" "$IMG"
    fi
else
    mkdir -p "$CACHE_DIR"
    cached="$CACHE_DIR/$(basename "$BASE_URL")"

    if [[ -f "$cached" ]]; then
        log "Image de base déjà en cache : $cached"
    else
        log "Téléchargement de l'image de base (environ 500 Mio)"
        if [[ "$DOWNLOADER" == "curl" ]]; then
            curl -fL --retry 3 --progress-bar -o "$cached.part" "$BASE_URL" || fail "Téléchargement échoué"
        else
            wget -q --show-progress -O "$cached.part" "$BASE_URL" || fail "Téléchargement échoué"
        fi
        mv "$cached.part" "$cached"
    fi

    if [[ -n "$BASE_SHA256" ]]; then
        log "Vérification de la somme de contrôle"
        actual="$(sha256sum "$cached" | awk '{print $1}')"
        if [[ "$actual" != "$BASE_SHA256" ]]; then
            # Le fichier en cache est supprimé : le laisser en place ferait
            # échouer tous les builds suivants de la même façon sans que la
            # cause (téléchargement corrompu) soit évidente.
            rm -f "$cached"
            fail "Somme de contrôle incorrecte pour l'image de base (attendu $BASE_SHA256, obtenu $actual). Fichier supprimé, relancer."
        fi
    else
        warn "Aucune somme de contrôle fournie pour --base-url : téléchargement non vérifié"
    fi

    log "Décompression de l'image de base"
    xz -dc "$cached" >"$IMG"
fi

# --- 2. Agrandissement de la partition racine -------------------------------
read_partitions() {
    sfdisk -J "$IMG" | python3 -c '
import json,sys
table=json.load(sys.stdin)["partitiontable"]
parts=table["partitions"]
if len(parts)<2:
    sys.exit("Table de partitions inattendue : moins de deux partitions")
# Raspberry Pi OS : partition 1 = démarrage (FAT), partition 2 = racine (ext4).
boot,root=parts[0],parts[1]
print(boot["start"],boot["size"],root["start"],root["size"])
'
}

read -r BOOT_START BOOT_SIZE ROOT_START ROOT_SIZE <<<"$(read_partitions)"
log "Partitions de base : démarrage @${BOOT_START} (${BOOT_SIZE} secteurs), racine @${ROOT_START} (${ROOT_SIZE} secteurs)"

log "Agrandissement de l'image de ${EXTRA_SPACE_MB} Mio pour la compilation"
truncate -s "+${EXTRA_SPACE_MB}M" "$IMG"
# ",+" : on garde le début de la partition 2 et on l'étend jusqu'au bout de
# l'espace disponible. --no-reread/--force parce qu'on travaille sur un
# fichier et non sur un disque réel, que le noyau n'a donc pas à relire.
printf ',+\n' | sfdisk --no-reread --force -N 2 "$IMG" >/dev/null

# --- 3. Montage -------------------------------------------------------------
# Une boucle locale par partition, via --offset/--sizelimit, plutôt qu'un
# unique « losetup -P ». Raison : -P délègue la création des nœuds
# /dev/loopXpN au balayage de partitions du noyau et à udev, qui n'existe pas
# dans un conteneur — le périphérique est alors attaché mais ses partitions
# n'apparaissent jamais, sans message d'erreur. Le décalage explicite marche
# partout : sur un Pi, sur un coureur GitHub, dans un conteneur.
# Le périphérique obtenu est renvoyé dans ATTACHED_DEV plutôt qu'écrit sur la
# sortie standard : un appel du style DEV="$(attach_partition ...)" s'exécute
# dans un sous-shell, où le suivi dans LOOP_DEVS serait perdu — les boucles
# locales resteraient alors attachées après le build, sans que le nettoyage
# de sortie en sache quoi que ce soit.
ATTACHED_DEV=""
attach_partition() {
    local start_sector="$1" size_sectors="$2"
    ATTACHED_DEV="$(losetup --offset "$(( start_sector * 512 ))" \
                            --sizelimit "$(( size_sectors * 512 ))" \
                            --find --show "$IMG")" || fail "losetup a échoué"
    LOOP_DEVS+=("$ATTACHED_DEV")
}

detach_loops() {
    local index
    for (( index=${#LOOP_DEVS[@]}-1 ; index>=0 ; index-- )); do
        losetup -d "${LOOP_DEVS[index]}" || fail "Détachement de ${LOOP_DEVS[index]} impossible"
    done
    LOOP_DEVS=()
}

# La table a changé depuis la lecture initiale : c'est la nouvelle taille de
# la partition racine qui doit borner la boucle locale.
read -r BOOT_START BOOT_SIZE ROOT_START ROOT_SIZE <<<"$(read_partitions)"

attach_partition "$BOOT_START" "$BOOT_SIZE"; BOOT_DEV="$ATTACHED_DEV"
attach_partition "$ROOT_START" "$ROOT_SIZE"; ROOT_DEV="$ATTACHED_DEV"

log "Vérification et extension du système de fichiers racine"
run_fsck "$ROOT_DEV"
resize2fs "$ROOT_DEV" >/dev/null || fail "resize2fs (extension) a échoué"

mount_tracked "$ROOT_DEV" "$MNT"
mkdir -p "$MNT/boot/firmware"
mount_tracked "$BOOT_DEV" "$MNT/boot/firmware"

[[ -f "$MNT/etc/rpi-issue" ]] || warn "Ceci ne ressemble pas à une image Raspberry Pi OS (pas de /etc/rpi-issue)"

# --- 4. Personnalisation dans le chroot -------------------------------------
if [[ "$CUSTOMIZE" -eq 1 ]]; then
    if [[ "$NEEDS_QEMU" -eq 1 ]]; then
        log "Hôte $HOST_ARCH : préparation de l'émulation arm64"
        [[ -d /proc/sys/fs/binfmt_misc ]] || fail "binfmt_misc n'est pas monté : impossible d'exécuter des binaires arm64 (installer qemu-user-static et binfmt-support)"
        ls /proc/sys/fs/binfmt_misc/qemu-aarch64* >/dev/null 2>&1 \
            || fail "Aucun gestionnaire binfmt pour aarch64 : installer qemu-user-static (ou lancer docker/setup-qemu-action en CI)"
        if [[ -x /usr/bin/qemu-aarch64-static ]]; then
            # Inutile quand le gestionnaire binfmt est enregistré avec le
            # drapeau F (l'interpréteur est alors déjà chargé en mémoire),
            # mais sans effet de bord dans ce cas.
            cp /usr/bin/qemu-aarch64-static "$MNT/usr/bin/"
        fi
    fi

    mount_tracked --bind /dev     "$MNT/dev"
    mount_tracked --bind /dev/pts "$MNT/dev/pts"
    mount_tracked -t proc  proc   "$MNT/proc"
    mount_tracked -t sysfs sysfs  "$MNT/sys"

    # Résolution DNS dans le chroot (apt, git). Le fichier d'origine est
    # sauvegardé : sur Raspberry Pi OS c'est un lien symbolique géré par
    # NetworkManager, qu'il faut remettre tel quel avant de refermer l'image.
    RESOLV_SAVED=0
    if [[ -e "$MNT/etc/resolv.conf" || -L "$MNT/etc/resolv.conf" ]]; then
        mv "$MNT/etc/resolv.conf" "$MNT/etc/resolv.conf.pidecoder-build"
        RESOLV_SAVED=1
    fi
    cp /etc/resolv.conf "$MNT/etc/resolv.conf"

    # Empêche dpkg de démarrer le moindre démon pendant les installations :
    # dans un chroot, ces démarrages échouent au mieux, et polluent la
    # machine de build au pire.
    cat >"$MNT/usr/sbin/policy-rc.d" <<'EOF'
#!/bin/sh
exit 101
EOF
    chmod +x "$MNT/usr/sbin/policy-rc.d"

    in_chroot() {
        # SYSTEMD_OFFLINE : dit explicitement à systemctl qu'il travaille sur
        # un système qui ne tourne pas. Sans ça, « systemctl enable » depuis
        # un chroot peut tenter de joindre un bus inexistant.
        chroot "$MNT" /usr/bin/env \
            DEBIAN_FRONTEND=noninteractive \
            SYSTEMD_OFFLINE=1 \
            LC_ALL=C.UTF-8 \
            PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
            "$@"
    }

    in_chroot /bin/true 2>/dev/null \
        || fail "Impossible d'exécuter un binaire du chroot. Sur un hôte non-arm64, vérifier qemu-user-static et binfmt_misc."

    log "Installation de la pile Wayland minimale et des dépendances"
    in_chroot apt-get update
    # Pourquoi ces paquets, sur une base Lite qui n'a aucun environnement
    # graphique :
    #   labwc          compositeur Wayland (celui de Raspberry Pi OS Desktop)
    #   libgl1-mesa-dri, libegl1, libgles2  pile OpenGL/EGL du GPU V3D
    #   dbus-user-session  bus de session utilisateur (requis par PipeWire)
    #   pipewire*, wireplumber  audio, pour la lecture du son en vue Focus
    #   network-manager  utilisé par l'onglet Réseau (nmcli)
    #   avahi-daemon   résolution <nom>.local, pratique pour trouver le Pi
    #   git            nécessaire à la mise à jour en un clic
    in_chroot apt-get install -y --no-install-recommends \
        labwc \
        libgl1-mesa-dri \
        libegl1 \
        libgles2 \
        dbus-user-session \
        pipewire \
        pipewire-pulse \
        wireplumber \
        network-manager \
        avahi-daemon \
        git \
        openssl \
        ca-certificates

    log "Création de l'utilisateur $IMAGE_USER"
    if ! in_chroot id "$IMAGE_USER" >/dev/null 2>&1; then
        in_chroot useradd --create-home --shell /bin/bash \
            --groups video,render,audio,input,plugdev,netdev,sudo "$IMAGE_USER"
    fi
    printf '%s:%s\n' "$IMAGE_USER" "$IMAGE_USER_PASSWORD" | in_chroot chpasswd
    # Le compte root reste sans mot de passe utilisable (comportement d'origine
    # de Raspberry Pi OS) : on passe par sudo.
    in_chroot passwd -l root >/dev/null 2>&1 || true

    # Assistant « premier utilisateur » de Raspberry Pi OS : à neutraliser
    # impérativement, et c'est tout sauf cosmétique. Sur une image Lite, il
    # s'accapare tty1 au premier démarrage pour demander un nom d'utilisateur
    # et un mot de passe, puis **renomme l'utilisateur d'uid 1000** — donc
    # celui qu'on vient de créer. Tout ce qui le désigne par son nom casse
    # alors d'un coup : la connexion automatique ci-dessous (qui pointe sur un
    # utilisateur devenu inexistant, donc plus de labwc, donc plus de socket
    # Wayland, donc plus de moteur vidéo) et le « User= » des unités rendues
    # par install.sh. Constaté sur la première carte réellement flashée :
    # l'utilisateur pidecoder y était devenu « admin ».
    #
    # Le démasquage ne suffit pas : sur ces images, userconfig.service prend
    # la place de getty@tty1, qui est désactivé. Il faut donc aussi le
    # réactiver explicitement, sinon tty1 n'ouvre plus aucune session du tout.
    log "Neutralisation de l'assistant de premier démarrage de Raspberry Pi OS"
    for wizard_unit in userconfig.service userconf.service; do
        in_chroot systemctl mask "$wizard_unit" >/dev/null 2>&1 || true
    done
    in_chroot systemctl enable getty@tty1.service >/dev/null 2>&1 || true

    log "Configuration de la session Wayland (connexion automatique + labwc)"
    in_chroot mkdir -p /etc/systemd/system/getty@tty1.service.d
    sed "s/@IMAGE_USER@/$IMAGE_USER/g" "$SCRIPT_DIR/image/getty-autologin.conf" \
        >"$MNT/etc/systemd/system/getty@tty1.service.d/autologin.conf"

    cp "$SCRIPT_DIR/image/wayland-session.sh" "$MNT/home/$IMAGE_USER/.bash_profile"
    in_chroot chown "$IMAGE_USER:$IMAGE_USER" "/home/$IMAGE_USER/.bash_profile"

    # Démarrage sur la console, pas sur une cible graphique : c'est bien le
    # getty de tty1 qui ouvre la session, et lui seul.
    in_chroot systemctl set-default multi-user.target >/dev/null

    # Sans ça, la console efface l'écran au bout de quelques minutes
    # d'inactivité clavier — sur un mur d'images, personne ne touche jamais
    # le clavier.
    CMDLINE="$MNT/boot/firmware/cmdline.txt"
    if [[ -f "$CMDLINE" ]] && ! grep -q 'consoleblank=' "$CMDLINE"; then
        # Le fichier doit rester sur une seule ligne, sans saut final.
        printf '%s consoleblank=0' "$(tr -d '\n' <"$CMDLINE")" >"$CMDLINE.new"
        mv "$CMDLINE.new" "$CMDLINE"
    fi

    log "Installation du dépôt PiDecoder dans l'image"
    REPO_IN_IMAGE="/home/$IMAGE_USER/PiDecoder"
    # Clone local plutôt que copie brute : l'image embarque ainsi un vrai
    # dépôt Git, ce dont dépend la mise à jour en un clic de l'onglet Système
    # (git fetch/pull). L'URL distante est reprise du dépôt source pour que
    # « git pull » sur l'appareil aille bien chercher GitHub et non un chemin
    # local de la machine de build.
    if git -C "$SOURCE_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        SOURCE_COMMIT="$(git -C "$SOURCE_ROOT" rev-parse HEAD)"
        SOURCE_REMOTE="$(git -C "$SOURCE_ROOT" remote get-url origin 2>/dev/null || true)"
        git clone --no-hardlinks --quiet "$SOURCE_ROOT" "$MNT$REPO_IN_IMAGE" \
            || fail "Clone du dépôt dans l'image impossible"
        git -C "$MNT$REPO_IN_IMAGE" checkout --quiet "$SOURCE_COMMIT"
        if [[ -n "$SOURCE_REMOTE" ]]; then
            git -C "$MNT$REPO_IN_IMAGE" remote set-url origin "$SOURCE_REMOTE"
        else
            warn "Le dépôt source n'a pas de distant « origin » : la mise à jour en un clic sera inopérante sur cette image"
        fi
    else
        warn "Le répertoire source n'est pas un dépôt Git : copie simple, la mise à jour en un clic sera inopérante"
        mkdir -p "$MNT$REPO_IN_IMAGE"
        cp -a "$SOURCE_ROOT/." "$MNT$REPO_IN_IMAGE/"
    fi
    in_chroot chown -R "$IMAGE_USER:$IMAGE_USER" "$REPO_IN_IMAGE"

    log "Installation de PiDecoder (compilation du moteur natif — c'est la partie longue)"
    # --no-start : rien ne peut démarrer dans un chroot. Les unités sont
    # installées et activées, elles démarreront au premier vrai démarrage.
    #
    # --no-https : aucun certificat n'est généré ici, et c'est voulu. Celui
    # qu'install.sh fabriquerait serait de toute façon supprimé quelques
    # lignes plus bas (sa clé privée serait identique sur toutes les cartes,
    # et ses Subject Alternative Names porteraient le nom d'hôte et les IP de
    # la machine de construction). Le générer pour le jeter coûtait une
    # génération de clé RSA sous émulation — et surtout, c'était un point de
    # panne : dans un chroot, « hostname -f » et « hostname -I » ne décrivent
    # pas la machine cible, et openssl refusait le certificat. C'est
    # pidecoder-firstboot.service qui le crée sur l'appareil, avec les bonnes
    # valeurs. HTTPS s'active tout seul dès que le certificat existe (voir
    # https_enabled_on_disk dans config-web.py), il n'y a donc rien d'autre à
    # faire ici.
    #
    # Le mot de passe arrive par l'entrée standard et n'apparaît donc jamais
    # dans la ligne de commande.
    printf '%s\n' "$WEB_PASSWORD" | in_chroot bash -c "cd '$REPO_IN_IMAGE' && ./scripts/install.sh \
        --user '$IMAGE_USER' \
        --no-start \
        --no-https \
        --web-password-stdin \
        --web-password-must-change" \
        || fail "L'installation de PiDecoder dans l'image a échoué"

    log "Installation du service de premier démarrage"
    in_chroot mkdir -p /opt/pidecoder/scripts/image
    cp "$SCRIPT_DIR/image/firstboot.sh" "$MNT/opt/pidecoder/scripts/image/firstboot.sh"
    chmod 0755 "$MNT/opt/pidecoder/scripts/image/firstboot.sh"
    cp "$SCRIPT_DIR/image/pidecoder-firstboot.service" "$MNT/etc/systemd/system/pidecoder-firstboot.service"
    in_chroot systemctl enable pidecoder-firstboot.service >/dev/null

    # --- Retrait de tout ce qui doit rester unique à chaque appareil --------
    log "Retrait de l'identité de la machine de construction"

    # Certificat TLS : normalement aucun n'existe (install.sh est lancé avec
    # --no-https, voir plus haut), mais on ne s'en remet pas à ça — un
    # certificat qui survivrait à cette étape aurait sa clé privée publiée
    # dans chaque copie de l'image. Le filet reste donc en place.
    rm -f "$MNT/opt/pidecoder/config/tls/cert.pem" \
          "$MNT/opt/pidecoder/config/tls/key.pem" \
          "$MNT/opt/pidecoder/config/tls/cert.pem.disabled" \
          "$MNT/opt/pidecoder/config/tls/key.pem.disabled"

    # Clés d'hôte SSH : même raison, en pire — une clé privée partagée
    # permettrait d'usurper n'importe quel autre appareil du parc.
    rm -f "$MNT"/etc/ssh/ssh_host_*

    # systemd regénère un identifiant machine au démarrage quand le fichier
    # existe mais est vide. Un identifiant partagé donnerait notamment le même
    # DUID DHCP à toutes les cartes.
    : >"$MNT/etc/machine-id"
    rm -f "$MNT/var/lib/dbus/machine-id"

    # Journaux, caches et historiques de la construction.
    in_chroot apt-get clean
    rm -rf "$MNT"/var/lib/apt/lists/*
    rm -rf "$MNT"/var/log/journal/* "$MNT"/var/log/*.log "$MNT"/var/log/apt/*
    rm -f "$MNT/root/.bash_history" "$MNT/home/$IMAGE_USER/.bash_history"
    rm -f "$MNT/usr/sbin/policy-rc.d"
    [[ "$NEEDS_QEMU" -eq 1 ]] && rm -f "$MNT/usr/bin/qemu-aarch64-static"

    rm -f "$MNT/etc/resolv.conf"
    if [[ "$RESOLV_SAVED" -eq 1 ]]; then
        mv "$MNT/etc/resolv.conf.pidecoder-build" "$MNT/etc/resolv.conf"
    fi

    # Vérifications de cohérence avant de refermer l'image : il vaut bien
    # mieux échouer ici que livrer une carte qui ne démarre pas.
    # L'assistant de Raspberry Pi OS doit être hors d'état de nuire : s'il
    # tournait au premier démarrage, il renommerait l'utilisateur de l'image
    # et casserait à la fois la connexion automatique et les unités systemd.
    [[ -L "$MNT/etc/systemd/system/userconfig.service" ]] \
        || warn "userconfig.service n'a pas pu être masqué : vérifier qu'il n'existe pas sous un autre nom dans cette version de Raspberry Pi OS"
    in_chroot id "$IMAGE_USER" >/dev/null 2>&1 \
        || fail "L'utilisateur $IMAGE_USER n'existe pas dans l'image"

    [[ -x "$MNT/opt/pidecoder/bin/pidecoder" ]] || fail "Le moteur vidéo n'a pas été compilé dans l'image"
    [[ -f "$MNT/opt/pidecoder/config/web-auth.json" ]] || fail "Le compte administrateur Web n'a pas été créé dans l'image"
    [[ -f "$MNT/etc/systemd/system/pidecoder-config.service" ]] || fail "Les unités systemd n'ont pas été installées dans l'image"
    grep -q 'init=' "$MNT/boot/firmware/cmdline.txt" \
        || warn "cmdline.txt ne contient plus « init= » : la partition racine ne s'agrandira pas toute seule au premier démarrage"

    log "Personnalisation terminée"
else
    log "--no-customize : étapes chroot ignorées (test de la plomberie uniquement)"
fi

# --- 5. Réduction -----------------------------------------------------------
umount_all

log "Réduction du système de fichiers racine"
run_fsck "$ROOT_DEV"

BLOCK_SIZE="$(dumpe2fs -h "$ROOT_DEV" 2>/dev/null | awk -F: '/Block size/ {gsub(/ /,"",$2); print $2}')"
MIN_BLOCKS="$(resize2fs -P "$ROOT_DEV" 2>/dev/null | awk '{print $NF}')"
[[ -n "$BLOCK_SIZE" && -n "$MIN_BLOCKS" ]] || fail "Impossible de déterminer la taille minimale du système de fichiers"

MARGIN_BLOCKS=$(( FREE_SPACE_MB * 1024 * 1024 / BLOCK_SIZE ))
TARGET_BLOCKS=$(( MIN_BLOCKS + MARGIN_BLOCKS ))
resize2fs "$ROOT_DEV" "$TARGET_BLOCKS" >/dev/null || fail "resize2fs (réduction) a échoué"
run_fsck "$ROOT_DEV"

# La taille réellement obtenue peut différer de celle demandée (arrondis de
# groupes de blocs) : c'est elle qui doit dimensionner la partition, pas la
# valeur demandée, sinon la partition serait plus petite que son contenu.
FINAL_BLOCKS="$(dumpe2fs -h "$ROOT_DEV" 2>/dev/null | awk -F: '/Block count/ {gsub(/ /,"",$2); print $2}')"
[[ -n "$FINAL_BLOCKS" ]] || fail "Impossible de relire la taille du système de fichiers réduit"

detach_loops

ROOT_SECTORS=$(( FINAL_BLOCKS * BLOCK_SIZE / 512 ))
log "Nouvelle taille de la partition racine : $(( ROOT_SECTORS / 2048 )) Mio"

printf ',%s\n' "$ROOT_SECTORS" | sfdisk --no-reread --force -N 2 "$IMG" >/dev/null \
    || fail "Réécriture de la table de partitions impossible"

IMAGE_SECTORS=$(( ROOT_START + ROOT_SECTORS ))
truncate -s "$(( IMAGE_SECTORS * 512 ))" "$IMG"

# Dernier contrôle : la partition doit tenir dans le fichier, et le système de
# fichiers dans la partition.
read -r _ _ CHECK_START CHECK_SIZE <<<"$(read_partitions)"
[[ $(( CHECK_START + CHECK_SIZE )) -le "$IMAGE_SECTORS" ]] \
    || fail "Incohérence : la partition racine dépasse la fin de l'image"

# --- 6. Résultat ------------------------------------------------------------
mkdir -p "$(dirname "$OUTPUT")"

if [[ "$COMPRESS" -eq 1 ]]; then
    log "Compression (xz, cela prend plusieurs minutes)"
    # -T0 : tous les cœurs disponibles. Préréglage 6 (le défaut) et non 9 :
    # au niveau 9, xz réclame environ 700 Mio de mémoire par fil d'exécution,
    # soit près de 3 Gio à quatre fils — de quoi mettre à genoux un Pi 5 qui
    # fait par ailleurs tourner le mur d'images, pour quelques pour cent de
    # taille finale en moins sur ce type de contenu.
    xz -T0 -6 -c "$IMG" >"$OUTPUT" || fail "Compression échouée"
else
    mv "$IMG" "$OUTPUT"
fi

# Somme de contrôle écrite avec le nom de fichier relatif, pour que
# « sha256sum -c PiDecoder-....img.xz.sha256 » fonctionne depuis le dossier de
# téléchargement, sans dépendre du chemin absolu de la machine de build.
( cd "$(dirname "$OUTPUT")" && sha256sum "$(basename "$OUTPUT")" >"$(basename "$OUTPUT").sha256" ) \
    || fail "Écriture de la somme de contrôle impossible"

log "Image prête : $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
log "Somme de contrôle : $OUTPUT.sha256"
if [[ "$CUSTOMIZE" -eq 1 ]]; then
    log "Compte Web : admin / $WEB_PASSWORD (changement imposé à la première connexion)"
    log "Compte Linux : $IMAGE_USER / $IMAGE_USER_PASSWORD (SSH désactivé par défaut)"
fi
