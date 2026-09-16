#!/bin/bash
# Premier démarrage d'une carte SD flashée avec l'image PiDecoder.
#
# Lancé une seule fois par pidecoder-firstboot.service, avant
# pidecoder-config.service et après network-online.target.
#
# Raison d'être : une image distribuée est identique sur toutes les cartes.
# Tout ce qui doit être *unique par appareil* ne peut donc pas être fabriqué
# au moment de la construction de l'image — il faut le générer ici, au premier
# démarrage de chaque Pi :
#
#   - les clés d'hôte SSH (sinon toutes les cartes partagent la même clé
#     privée, ce qui permettrait d'usurper n'importe quel autre PiDecoder du
#     même parc) ;
#   - le nom d'hôte, dérivé du numéro de série du Pi, pour que deux appareils
#     sur le même réseau ne se disputent pas « pidecoder.local » ;
#   - le certificat TLS auto-signé, qui doit porter le vrai nom d'hôte et les
#     vraies adresses IP de *cet* appareil dans ses Subject Alternative Names,
#     inconnus au moment de la construction.
#
# L'identifiant machine (/etc/machine-id) n'est pas traité ici : il est vidé
# au moment de la construction, et systemd en génère un nouveau tout seul au
# démarrage quand le fichier est vide. C'est le mécanisme prévu par systemd,
# inutile de le refaire à la main.
#
# L'agrandissement de la partition racine n'est pas traité ici non plus :
# c'est le mécanisme natif de Raspberry Pi OS (init= dans cmdline.txt) qui
# s'en charge, plus tôt, avant même que systemd ne démarre.
set -Eeuo pipefail

readonly TARGET="/opt/pidecoder"
readonly STAMP="$TARGET/config/.firstboot-done"
readonly HOSTNAME_PREFIX="pidecoder"

log() {
    printf '[pidecoder-firstboot] %s\n' "$*"
}

if [[ -f "$STAMP" ]]; then
    log "Déjà effectué, rien à faire."
    exit 0
fi

# --- Nom d'hôte unique ------------------------------------------------------
# Le numéro de série du SoC est stable, propre à la carte, et déjà utilisé par
# Raspberry Pi OS lui-même. On n'en garde que les derniers caractères : un nom
# d'hôte complet de 16 chiffres hexadécimaux serait illisible sans rien
# apporter, et la collision sur 6 caractères est très improbable pour un parc
# de quelques dizaines d'appareils.
serial="$(awk '/^Serial/ {print $3}' /proc/cpuinfo 2>/dev/null | tail -1 || true)"
suffix="$(printf '%s' "${serial:-}" | tr -cd '0-9a-fA-F' | tail -c 6 | tr 'A-F' 'a-f')"

if [[ -z "$suffix" ]]; then
    # Pas de numéro de série lisible (matériel inattendu, /proc/cpuinfo d'un
    # autre format) : on retombe sur l'adresse MAC, puis sur un tirage
    # aléatoire. Un nom d'hôte unique vaut mieux qu'un nom d'hôte joli.
    suffix="$(cat /sys/class/net/*/address 2>/dev/null | grep -v '^00:00:00' | head -1 | tr -cd '0-9a-f' | tail -c 6 || true)"
fi

if [[ -z "$suffix" ]]; then
    suffix="$(tr -cd '0-9a-f' </dev/urandom | head -c 6)"
fi

new_hostname="${HOSTNAME_PREFIX}-${suffix}"
current_hostname="$(hostnamectl --static 2>/dev/null || cat /etc/hostname 2>/dev/null || true)"

if [[ "$current_hostname" != "$new_hostname" ]]; then
    log "Nom d'hôte : $current_hostname → $new_hostname"
    hostnamectl set-hostname "$new_hostname"
    # /etc/hosts doit suivre, sinon sudo et quelques outils mettent plusieurs
    # secondes à répondre en cherchant à résoudre un nom d'hôte inconnu.
    if grep -q '^127\.0\.1\.1' /etc/hosts; then
        sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$new_hostname/" /etc/hosts
    else
        printf '127.0.1.1\t%s\n' "$new_hostname" >>/etc/hosts
    fi
fi

# --- Clés d'hôte SSH --------------------------------------------------------
# Supprimées à la construction de l'image. ssh-keygen -A ne recrée que les
# clés absentes, donc l'appel est sans effet sur un système déjà pourvu.
if command -v ssh-keygen >/dev/null; then
    log "Génération des clés d'hôte SSH manquantes"
    ssh-keygen -A
fi

# --- Certificat TLS ---------------------------------------------------------
# Supprimé à la construction, pour deux raisons : sa clé privée serait sinon
# identique sur toutes les cartes (donc publique), et ses Subject Alternative
# Names contiendraient le nom d'hôte et les IP de la machine de build, ce qui
# ferait échouer la vérification du navigateur sur l'appareil réel.
if [[ ! -f "$TARGET/config/tls/cert.pem" ]]; then
    log "Génération du certificat TLS auto-signé de cet appareil"
    # --no-restart : pidecoder-config.service n'a pas encore démarré (ce
    # service-ci s'exécute avant), il n'y a donc rien à redémarrer, et le
    # faire échouerait au milieu du premier démarrage.
    if ! "$TARGET/scripts/manage-tls.sh" generate --force --no-restart; then
        # Un échec ici ne doit pas empêcher le Pi de démarrer : sans
        # certificat, config-web.py sert simplement en HTTP seul, et le
        # certificat pourra être généré depuis l'onglet Sécurité.
        log "AVERTISSEMENT : génération du certificat échouée, HTTPS restera inactif"
    fi
fi

mkdir -p "$(dirname "$STAMP")"
date -u '+%Y-%m-%dT%H:%M:%SZ' >"$STAMP"

# Le service ne se réexécutera plus. Le fichier témoin ci-dessus suffirait,
# mais désactiver l'unité évite aussi de la voir échouer dans l'état du
# système si quelque chose change plus tard.
systemctl disable pidecoder-firstboot.service >/dev/null 2>&1 || true

log "Premier démarrage terminé : $new_hostname"
