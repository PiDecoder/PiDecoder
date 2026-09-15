#!/usr/bin/env bash
# Gestion du certificat TLS de l'interface d'administration PiDecoder, sans
# repasser par l'installeur complet (qui recompile le moteur natif et coupe
# tous les services). Ce script ne touche que config/tls/ et redémarre
# uniquement pidecoder-config.service.
set -Eeuo pipefail

TARGET="/opt/pidecoder"
ACTION=""
CERT_PATH=""
KEY_PATH=""
FORCE=0
NO_RESTART=0

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
Gestion du certificat TLS de PiDecoder (interface d'administration)

Usage:
  sudo ./scripts/manage-tls.sh status
  sudo ./scripts/manage-tls.sh generate [--force]
  sudo ./scripts/manage-tls.sh import --cert PATH --key PATH
  sudo ./scripts/manage-tls.sh disable
  sudo ./scripts/manage-tls.sh enable
  sudo ./scripts/manage-tls.sh [-h|--help]

Sous-commandes:
  status     Affiche l'état actuel (HTTPS actif ou non, détails du certificat).
  generate   Génère un nouveau certificat auto-signé (mêmes réglages que
             l'installeur : nom d'hôte + IPv4 locales en SAN, 10 ans de
             validité). Refuse d'écraser un certificat existant sans --force.
  import     Installe un certificat/clé fournis (ex. une CA interne). Les
             deux fichiers doivent être au format PEM et former une paire
             valide — vérifié avant toute copie.
  disable    Désactive HTTPS : le certificat actif est mis de côté
             (cert.pem.disabled / key.pem.disabled) et le service repasse en
             HTTP simple. Rien n'est supprimé, "enable" restaure.
  enable     Réactive HTTPS : restaure un certificat mis de côté par
             "disable", ou en génère un nouveau si aucun n'existe.

Options:
  --target PATH   Répertoire d'installation (défaut : /opt/pidecoder)
  --cert PATH     Certificat PEM à importer (avec "import")
  --key PATH      Clé privée PEM à importer (avec "import")
  --force         Avec "generate" : écrase un certificat existant
  --no-restart    Ne redémarre pas pidecoder-config.service (l'appelant s'en
                  charge lui-même — utilisé par l'interface Web, qui a besoin
                  de contrôler précisément quand la coupure de connexion a
                  lieu plutôt que de la subir pendant cet appel)
  -h, --help      Affiche cette aide

Chaque sous-commande (sauf "status") redémarre pidecoder-config.service pour
appliquer le changement immédiatement, sauf avec --no-restart.
EOF
}

require_root() {
    [[ "$EUID" -eq 0 ]] || fail "Relancer avec sudo"
}

require_install() {
    [[ -d "$TARGET/config" ]] || fail "PiDecoder n'est pas installé sous $TARGET (ou --target incorrect)"
}

tls_dir() { printf '%s/config/tls' "$TARGET"; }

set_tls_permissions() {
    local dir; dir="$(tls_dir)"
    [[ -f "$dir/cert.pem" ]] && chown root:root "$dir/cert.pem" && chmod 0644 "$dir/cert.pem"
    [[ -f "$dir/key.pem" ]] && chown root:root "$dir/key.pem" && chmod 0600 "$dir/key.pem"
    chown root:root "$dir"
    chmod 0750 "$dir"
}

restart_service() {
    if [[ "$NO_RESTART" -eq 1 ]]; then
        log "Redémarrage ignoré (--no-restart) — à la charge de l'appelant"
        return 0
    fi
    if ! systemctl cat pidecoder-config.service >/dev/null 2>&1; then
        warn "pidecoder-config.service introuvable — redémarre-le manuellement si besoin."
        return 0
    fi
    systemctl restart pidecoder-config.service \
        || fail "Échec du redémarrage de pidecoder-config.service — voir : journalctl -u pidecoder-config.service -n 50"
    log "pidecoder-config.service redémarré"
}

print_cert_summary() {
    local certfile="$1"
    [[ -f "$certfile" ]] || return 0
    local subject enddate
    subject="$(openssl x509 -in "$certfile" -noout -subject 2>/dev/null | sed 's/^subject=//')"
    enddate="$(openssl x509 -in "$certfile" -noout -enddate 2>/dev/null | sed 's/^notAfter=//')"
    printf '  Sujet      : %s\n' "${subject:-inconnu}"
    printf '  Expire le  : %s\n' "${enddate:-inconnu}"
    openssl x509 -in "$certfile" -noout -ext subjectAltName 2>/dev/null \
        | tail -n +2 \
        | sed 's/^ */  SAN        : /'
}

cmd_status() {
    local dir; dir="$(tls_dir)"
    if [[ -f "$dir/cert.pem" && -f "$dir/key.pem" ]]; then
        printf 'HTTPS       : actif\n'
        print_cert_summary "$dir/cert.pem"
    elif [[ -f "$dir/cert.pem.disabled" && -f "$dir/key.pem.disabled" ]]; then
        printf 'HTTPS       : désactivé (certificat mis de côté, "enable" pour le restaurer)\n'
        print_cert_summary "$dir/cert.pem.disabled"
    else
        printf 'HTTPS       : inactif (aucun certificat installé — "generate" ou "import")\n'
    fi
}

validate_pair() {
    local certfile="$1" keyfile="$2"
    [[ -r "$certfile" ]] || fail "Certificat introuvable ou illisible : $certfile"
    [[ -r "$keyfile" ]] || fail "Clé introuvable ou illisible : $keyfile"
    openssl x509 -in "$certfile" -noout >/dev/null 2>&1 || fail "Certificat invalide (PEM attendu) : $certfile"
    openssl pkey -in "$keyfile" -noout >/dev/null 2>&1 || fail "Clé invalide (PEM attendue) : $keyfile"
    local key_digest cert_digest
    key_digest="$(openssl pkey -in "$keyfile" -pubout -outform DER 2>/dev/null | openssl dgst -sha256)"
    cert_digest="$(openssl x509 -in "$certfile" -noout -pubkey 2>/dev/null | openssl pkey -pubin -outform DER 2>/dev/null | openssl dgst -sha256)"
    [[ -n "$key_digest" && "$cert_digest" == "$key_digest" ]] || fail "Le certificat et la clé fournis ne correspondent pas"
}

cmd_generate() {
    require_root; require_install
    local dir; dir="$(tls_dir)"
    mkdir -p "$dir"
    if [[ "$FORCE" -eq 0 && -f "$dir/cert.pem" ]]; then
        fail "Un certificat est déjà actif — relancer avec --force pour l'écraser (ou \"disable\" d'abord)."
    fi

    log "Génération d'un certificat TLS auto-signé"
    local cert_cn san_entries san_list ip
    cert_cn="$(hostname -f 2>/dev/null || hostname)"
    san_entries=("DNS:$cert_cn" "DNS:localhost" "IP:127.0.0.1")
    while IFS= read -r ip; do
        [[ -n "$ip" ]] || continue
        san_entries+=("IP:$ip")
    done < <(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$')
    san_list="$(IFS=,; echo "${san_entries[*]}")"

    local tmp_dir; tmp_dir="$(mktemp -d)"
    trap 'rm -rf "$tmp_dir"' RETURN

    openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
        -keyout "$tmp_dir/key.pem" \
        -out "$tmp_dir/cert.pem" \
        -subj "/CN=$cert_cn" \
        -addext "subjectAltName=$san_list" \
        >/dev/null 2>&1 \
        || fail "Échec de la génération du certificat TLS"

    rm -f "$dir/cert.pem.disabled" "$dir/key.pem.disabled"
    install -m 0644 "$tmp_dir/cert.pem" "$dir/cert.pem"
    install -m 0600 "$tmp_dir/key.pem" "$dir/key.pem"
    set_tls_permissions
    restart_service
    printf '\nNouveau certificat auto-signé installé. Le navigateur affichera un\n'
    printf 'avertissement la première fois — valider/accepter pour continuer.\n'
}

cmd_import() {
    require_root; require_install
    [[ -n "$CERT_PATH" && -n "$KEY_PATH" ]] || fail "\"import\" nécessite --cert et --key"
    validate_pair "$CERT_PATH" "$KEY_PATH"

    local dir; dir="$(tls_dir)"
    mkdir -p "$dir"
    log "Installation du certificat fourni"
    rm -f "$dir/cert.pem.disabled" "$dir/key.pem.disabled"
    install -m 0644 "$CERT_PATH" "$dir/cert.pem"
    install -m 0600 "$KEY_PATH" "$dir/key.pem"
    set_tls_permissions
    restart_service
    printf '\nCertificat importé et actif.\n'
}

cmd_disable() {
    require_root; require_install
    local dir; dir="$(tls_dir)"
    if [[ ! -f "$dir/cert.pem" || ! -f "$dir/key.pem" ]]; then
        warn "HTTPS n'est pas actif — rien à désactiver."
        return 0
    fi
    [[ -f "$dir/cert.pem.disabled" || -f "$dir/key.pem.disabled" ]] \
        && fail "Un certificat désactivé existe déjà sous $dir — le supprimer manuellement avant de continuer."

    log "Désactivation de HTTPS"
    mv "$dir/cert.pem" "$dir/cert.pem.disabled"
    mv "$dir/key.pem" "$dir/key.pem.disabled"
    restart_service
    printf '\nHTTPS désactivé — le service sert maintenant en HTTP simple.\n'
    printf '"sudo ./scripts/manage-tls.sh enable" pour le réactiver.\n'
    printf '\nATTENTION : si un navigateur s'"'"'est déjà connecté en HTTPS\n'
    printf 'auparavant, il a gardé en mémoire un cookie de session marqué\n'
    printf '« Secure ». Un tel cookie ne peut pas être remplacé par une\n'
    printf 'connexion HTTP simple (règle de sécurité du navigateur) : la\n'
    printf 'connexion semblera acceptée (mot de passe validé) mais restera\n'
    printf 'bloquée juste après, sans message d'"'"'erreur visible. Si ça arrive,\n'
    printf 'effacer les cookies du site (ou juste "pidecoder_session") pour\n'
    printf 'ce Pi dans le navigateur concerné, une seule fois.\n'
}

cmd_enable() {
    require_root; require_install
    local dir; dir="$(tls_dir)"
    if [[ -f "$dir/cert.pem.disabled" && -f "$dir/key.pem.disabled" ]]; then
        log "Restauration du certificat désactivé"
        mv "$dir/cert.pem.disabled" "$dir/cert.pem"
        mv "$dir/key.pem.disabled" "$dir/key.pem"
        set_tls_permissions
        restart_service
        printf '\nHTTPS réactivé avec le certificat précédent.\n'
    elif [[ -f "$dir/cert.pem" && -f "$dir/key.pem" ]]; then
        # Un certificat est déjà sur le disque, mais ça ne veut pas dire que
        # le service qui tourne l'utilise déjà : avec --no-restart, un appel
        # précédent à "generate"/"import" a pu simplement le préparer sans
        # jamais redémarrer le service (cas de l'interface Web, qui recharge
        # le certificat à chaud tant que HTTPS est déjà actif, mais laisse le
        # fichier "en attente" tant qu'il ne l'est pas). Redémarrer ici, sans
        # condition, garantit que le service reflète toujours ce qu'il y a
        # sur le disque plutôt que de supposer un état qu'on ne peut pas
        # vérifier depuis ce script.
        log "Certificat déjà présent — redémarrage du service pour le prendre en compte"
        restart_service
        printf '\nHTTPS actif.\n'
    else
        cmd_generate
    fi
}

[[ $# -ge 1 ]] || { usage; exit 1; }
ACTION="$1"; shift

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            [[ $# -ge 2 ]] || fail "Valeur manquante après --target"
            TARGET="$2"; shift 2 ;;
        --cert)
            [[ $# -ge 2 ]] || fail "Valeur manquante après --cert"
            CERT_PATH="$2"; shift 2 ;;
        --key)
            [[ $# -ge 2 ]] || fail "Valeur manquante après --key"
            KEY_PATH="$2"; shift 2 ;;
        --force)
            FORCE=1; shift ;;
        --no-restart)
            NO_RESTART=1; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            fail "Option inconnue : $1" ;;
    esac
done

TARGET="$(realpath -m "$TARGET")"

case "$ACTION" in
    status)   cmd_status ;;
    generate) cmd_generate ;;
    import)   cmd_import ;;
    disable)  cmd_disable ;;
    enable)   cmd_enable ;;
    -h|--help) usage ;;
    *) usage; fail "Sous-commande inconnue : $ACTION" ;;
esac
