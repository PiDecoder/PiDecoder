#!/usr/bin/env python3
"""Mise à jour logicielle et administration réseau du Raspberry Pi.

Module séparé de config-web.py (déjà volumineux) pour les deux
fonctionnalités les plus délicates ajoutées à l'interface Web :

- vérifier/déclencher une mise à jour de PiDecoder (git pull + install.sh) ;
- consulter/modifier la configuration réseau (DHCP/IP statique, nom d'hôte,
  NTP, fuseau horaire) du Raspberry Pi lui-même.

Contrainte de conception commune aux deux : `pidecoder-config.service`
tourne sous un bac à sable systemd assez strict (voir
systemd/pidecoder-config.service.in : ProtectSystem=strict,
ProtectHostname=true, ReadWritePaths limité à <root>/config et au dépôt
Git). Plutôt que d'ajouter des dérogations pour chaque fichier système
concerné (/etc/hostname, /etc/hosts, /etc/systemd/timesyncd.conf...), toute
opération qui modifie l'état du système (mise à jour, changement réseau,
nom d'hôte, NTP) est déléguée à une unité systemd transitoire indépendante
via `systemd-run` — hors du bac à sable de ce service, exactement comme
`schedule_self_restart()` dans config-web.py le fait déjà pour le
redémarrage HTTPS on/off. Seules les opérations de lecture seule (nmcli
show, hostnamectl status, cat d'un fichier de configuration) sont
exécutées directement dans ce process.

Rien de ce module n'a pu être testé contre un vrai NetworkManager, un vrai
systemd-timesyncd ou une vraie installation PiDecoder — le bac à sable de
développement ne dispose d'aucun de ces services. Chaque fonction a été
relue avec une attention particulière et les commandes ont été vérifiées
dans la documentation officielle (Raspberry Pi OS Bookworm utilise
NetworkManager par défaut), mais un premier test prudent sur le Pi réel
reste indispensable avant de faire confiance à ce module — voir
docs/configuration.md.
"""
from __future__ import annotations

import ipaddress
import json
import re
import secrets
import shlex
import subprocess
import time
from pathlib import Path

UNIT_FILE = Path('/etc/systemd/system/pidecoder.service')


# --------------------------------------------------------------------------
# Utilitaires communs
# --------------------------------------------------------------------------

def get_service_user() -> str | None:
    """Lit l'utilisateur graphique (User=) dans pidecoder.service.

    C'est l'utilisateur sous lequel le moteur vidéo tourne (voir
    systemd/pidecoder.service.in, @SERVICE_USER@) — pas celui de
    pidecoder-config.service, qui tourne toujours en root. Utilisé pour
    lancer `git pull` et `install.sh --user` avec le bon compte plutôt que
    de laisser install.sh deviner (sa détection automatique — SUDO_USER,
    logname — ne trouve rien d'utile lancée depuis systemd-run, sans
    terminal de contrôle).
    """
    try:
        content = UNIT_FILE.read_text(encoding='utf-8')
    except OSError:
        return None

    match = re.search(r'^User=(\S+)$', content, re.MULTILINE)
    return match.group(1) if match else None


def run_detached(script: str, description: str) -> None:
    """Lance `script` (contenu shell complet) dans une unité systemd-run
    indépendante, immédiatement, sans attendre sa fin.

    Le script est écrit dans un fichier temporaire (plutôt que passé en
    ligne de commande) pour éviter toute limite de longueur et pour
    pouvoir l'inspecter après coup en cas de souci. L'unité transitoire
    n'hérite d'aucune restriction de pidecoder-config.service (bac à
    sable indépendant), donc peut librement écrire dans /etc, redémarrer
    des services, etc. — exactement comme un `sudo bash script.sh` lancé
    à la main.
    """
    script_path = Path(f'/run/pidecoder-admin-{secrets.token_hex(8)}.sh')
    script_path.write_text(script, encoding='utf-8')
    script_path.chmod(0o700)

    subprocess.Popen(
        ['systemd-run', '--collect', f'--unit=pidecoder-admin-{secrets.token_hex(4)}',
         'bash', str(script_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def run_sync_unsandboxed(command: str, timeout: int = 20) -> subprocess.CompletedProcess:
    """Exécute `command` (chaîne shell) hors du bac à sable de ce service,
    en attendant sa fin et en récupérant sa sortie — pour les changements
    à faible risque (NTP, fuseau horaire) qui n'ont pas besoin du filet de
    sécurité (rétablissement automatique) des changements réseau/hostname.

    `--wait --pipe` fait de systemd-run un simple relais synchrone : la
    sortie standard/erreur de la commande est renvoyée telle quelle et le
    code de sortie de systemd-run reflète celui de la commande.
    """
    return subprocess.run(
        ['systemd-run', '--wait', '--pipe', '--collect', '--quiet',
         'bash', '-c', command],
        capture_output=True, text=True, timeout=timeout,
    )


def _write_status(status_path: Path, data: dict) -> None:
    tmp = status_path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    tmp.replace(status_path)


# --------------------------------------------------------------------------
# Mise à jour logicielle (git pull + install.sh)
# --------------------------------------------------------------------------

def update_paths(root: Path) -> dict:
    directory = root / 'config' / 'update'
    directory.mkdir(parents=True, exist_ok=True)
    return {
        'dir': directory,
        'status': directory / 'status.json',
        'log': directory / 'update.log',
    }


def check_update(repo_path: str | None, service_user: str | None) -> dict:
    """Compare le commit local au commit distant (git fetch + rev-list).

    Ne modifie que .git/ dans le dépôt (FETCH_HEAD, refs distantes) — pas
    de checkout, pas de changement du répertoire de travail. Lancé via
    `runuser` sous l'utilisateur propriétaire du dépôt (pas root) pour ne
    pas polluer la propriété des fichiers du clone Git avec des entrées
    appartenant à root, ce qui casserait ensuite `git status`/`git pull`
    lancés à la main en SSH (« detected dubious ownership »).
    """
    if not repo_path:
        return {
            'supported': False,
            'reason': 'no_repo_path',
        }

    repo = Path(repo_path)
    if not (repo / '.git').is_dir():
        return {'supported': False, 'reason': 'not_a_git_repo'}

    def git(*args, timeout=5):
        cmd = ['git', '-C', str(repo), *args]
        if service_user:
            cmd = ['runuser', '-u', service_user, '--', *cmd]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    fetch = git('fetch', '--quiet', timeout=25)
    if fetch.returncode != 0:
        return {
            'supported': True,
            'available': None,
            'error': fetch.stderr.strip() or 'git fetch failed',
        }

    branch = git('rev-parse', '--abbrev-ref', 'HEAD').stdout.strip()
    local = git('rev-parse', 'HEAD').stdout.strip()
    upstream = git('rev-parse', '@{upstream}')

    if upstream.returncode != 0:
        return {
            'supported': True,
            'available': False,
            'branch': branch or None,
            'error': 'no_upstream',
        }

    upstream_hash = upstream.stdout.strip()

    if local == upstream_hash:
        return {'supported': True, 'available': False, 'branch': branch or None}

    count = git('rev-list', '--count', f'{local}..{upstream_hash}').stdout.strip()
    summary = git(
        'log', '-1', '--format=%s (%h, %cr)', upstream_hash,
    ).stdout.strip()

    try:
        commits_behind = int(count)
    except ValueError:
        commits_behind = None

    return {
        'supported': True,
        'available': bool(commits_behind),
        'branch': branch or None,
        'commits_behind': commits_behind,
        'latest_summary': summary or None,
    }


def start_update(
    root: Path,
    repo_path: str,
    service_user: str,
    target: str,
    bind: str,
    port: int,
    skip_deps: bool,
) -> None:
    """Déclenche git pull + install.sh en tâche de fond détachée.

    install.sh redémarre pidecoder-config.service à la fin (voir ce
    fichier) : ce process qui répond à la requête HTTP va donc être tué en
    plein milieu. C'est pour ça que tout se passe dans une unité
    systemd-run indépendante, PAS dans ce process — elle survit au
    redémarrage du service appelant. Le nouveau processus (après
    redémarrage) relit le même fichier de statut, donc la page Web peut
    continuer à suivre la progression sans interruption perceptible côté
    utilisateur (à part le rechargement de page habituel après un
    redémarrage du service).

    Rappel de sécurité déjà en place côté install.sh : en cas d'échec
    (compilation, dépendance manquante...), install.sh restaure
    automatiquement la version précédente (voir sa fonction `rollback`) —
    ce mécanisme n'est pas dupliqué ici.
    """
    paths = update_paths(root)
    _write_status(paths['status'], {
        'state': 'running', 'step': 'git_pull', 'started_at': time.time(),
    })

    skip_flag = ' --skip-deps' if skip_deps else ''

    # shlex.quote sur toutes les valeurs interpolées : repo_path/target
    # viennent de la configuration systemd (fiables), mais autant ne
    # jamais faire confiance implicitement à une chaîne interpolée dans un
    # script shell exécuté en root.
    script = f'''#!/bin/bash
set -u
LOG={shlex.quote(str(paths['log']))}
STATUS={shlex.quote(str(paths['status']))}
write_status() {{ printf '%s' "$1" > "$STATUS.tmp" && mv "$STATUS.tmp" "$STATUS"; }}

write_status '{{"state":"running","step":"git_pull","started_at":{time.time()}}}'
{{
    echo "=== git pull ($(date -Iseconds)) ==="
    runuser -u {shlex.quote(service_user)} -- git -C {shlex.quote(repo_path)} pull
}} >>"$LOG" 2>&1
if [ $? -ne 0 ]; then
    write_status '{{"state":"error","step":"git_pull","finished_at":{time.time()}}}'
    exit 1
fi

write_status '{{"state":"running","step":"install","started_at":{time.time()}}}'
{{
    echo "=== install.sh ($(date -Iseconds)) ==="
    bash {shlex.quote(repo_path)}/scripts/install.sh \\
        --user {shlex.quote(service_user)} \\
        --target {shlex.quote(target)} \\
        --bind {shlex.quote(bind)} \\
        --port {shlex.quote(str(port))}{skip_flag}
}} >>"$LOG" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
    write_status '{{"state":"error","step":"install","finished_at":{time.time()}}}'
    exit 1
fi

write_status '{{"state":"done","step":"install","finished_at":{time.time()}}}'
'''
    run_detached(script, 'pidecoder update')


def update_status(root: Path) -> dict:
    paths = update_paths(root)
    if not paths['status'].is_file():
        return {'state': 'idle'}
    try:
        data = json.loads(paths['status'].read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'state': 'idle'}

    log_tail = ''
    if paths['log'].is_file():
        try:
            lines = paths['log'].read_text(encoding='utf-8', errors='replace').splitlines()
            log_tail = '\n'.join(lines[-200:])
        except OSError:
            pass

    data['log_tail'] = log_tail
    return data


# --------------------------------------------------------------------------
# Réseau : lecture d'état
# --------------------------------------------------------------------------

def _nmcli(*args, timeout=10) -> subprocess.CompletedProcess:
    return subprocess.run(['nmcli', *args], capture_output=True, text=True, timeout=timeout)


def nmcli_available() -> bool:
    try:
        return _nmcli('--version', timeout=3).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def list_connections() -> list[dict]:
    """Connexions Ethernet/Wi-Fi connues de NetworkManager.

    -e yes force l'échappement des ':' internes aux valeurs en mode
    terse (-t), pour pouvoir séparer les champs de façon fiable même si
    une valeur en contenait un (adresse IPv6, improbable ici mais pas
    impossible sur une interface mixte).
    """
    result = _nmcli('-t', '-e', 'yes', '-f', 'NAME,TYPE,DEVICE,STATE', 'con', 'show')
    if result.returncode != 0:
        return []

    connections = []
    for line in result.stdout.splitlines():
        fields = re.split(r'(?<!\\):', line)
        fields = [f.replace('\\:', ':').replace('\\\\', '\\') for f in fields]
        if len(fields) < 4:
            continue
        name, conn_type, device, state = fields[:4]
        if conn_type not in ('802-3-ethernet', '802-11-wireless'):
            continue
        connections.append({
            'name': name,
            'type': 'ethernet' if conn_type == '802-3-ethernet' else 'wifi',
            'device': device or None,
            'active': state == 'activated',
            **connection_ipv4(name),
        })
    return connections


def connection_ipv4(name: str) -> dict:
    def field(key):
        result = _nmcli('-t', '-e', 'yes', '-g', key, 'con', 'show', name)
        return result.stdout.strip() if result.returncode == 0 else ''

    method = field('ipv4.method') or 'auto'
    addresses = field('ipv4.addresses')
    gateway = field('ipv4.gateway')
    dns = field('ipv4.dns')

    return {
        'method': 'manual' if method == 'manual' else 'auto',
        'address': addresses.split(',')[0] if addresses else None,
        'gateway': gateway or None,
        'dns': [d for d in dns.split(',') if d] if dns else [],
    }


def current_hostname() -> str:
    result = subprocess.run(['hostnamectl', '--static'], capture_output=True, text=True, timeout=5)
    return result.stdout.strip() if result.returncode == 0 else ''


def ntp_config() -> dict:
    enabled = False
    synchronized = False
    try:
        result = subprocess.run(
            ['timedatectl', 'show', '-p', 'NTP', '-p', 'NTPSynchronized'],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if line == 'NTP=yes':
                enabled = True
            if line == 'NTPSynchronized=yes':
                synchronized = True
    except (OSError, subprocess.TimeoutExpired):
        pass

    servers: list[str] = []
    conf = Path('/etc/systemd/timesyncd.conf')
    try:
        for line in conf.read_text(encoding='utf-8').splitlines():
            stripped = line.strip()
            if stripped.startswith('NTP=') and not stripped.startswith('#'):
                servers = stripped.split('=', 1)[1].split()
    except OSError:
        pass

    return {'enabled': enabled, 'synchronized': synchronized, 'servers': servers}


def current_timezone() -> str:
    result = subprocess.run(
        ['timedatectl', 'show', '-p', 'Timezone', '--value'],
        capture_output=True, text=True, timeout=5,
    )
    return result.stdout.strip() if result.returncode == 0 else ''


def list_timezones() -> list[str]:
    result = subprocess.run(['timedatectl', 'list-timezones'], capture_output=True, text=True, timeout=10)
    return result.stdout.splitlines() if result.returncode == 0 else []


# --------------------------------------------------------------------------
# Réseau : validation
# --------------------------------------------------------------------------

HOSTNAME_RE = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$')


def validate_hostname(value: str) -> str:
    value = value.strip()
    if not value or not HOSTNAME_RE.match(value) or len(value) > 63:
        raise ValueError('invalid_hostname')
    return value


def validate_cidr(value: str) -> str:
    value = value.strip()
    if '/' not in value:
        # ipaddress.ip_interface() accepterait un simple "192.168.1.50" en le
        # complétant silencieusement en /32 (un seul hôte, sans route vers
        # la passerelle sans configuration réseau supplémentaire) — presque
        # sûrement pas ce que voulait l'utilisateur s'il a juste tapé une
        # adresse sans masque. Le préfixe est donc obligatoire ici.
        raise ValueError('cidr_prefix_required')
    try:
        interface = ipaddress.ip_interface(value)
    except ValueError as exc:
        raise ValueError('invalid_address') from exc
    if interface.version != 4:
        raise ValueError('ipv6_not_supported')
    return str(interface)


def validate_ipv4(value: str) -> str:
    try:
        address = ipaddress.IPv4Address(value.strip())
    except ValueError as exc:
        raise ValueError('invalid_address') from exc
    return str(address)


def validate_dns_list(values: list[str]) -> list[str]:
    return [validate_ipv4(v) for v in values if v.strip()]


NTP_SERVER_RE = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$')


def validate_ntp_servers(values: list[str]) -> list[str]:
    """Un serveur NTP est le plus souvent un nom d'hôte (ex.
    "0.debian.pool.ntp.org"), pas une IP — contrairement aux serveurs DNS
    ci-dessus, validate_ipv4() serait donc trop strict ici. On se contente
    de vérifier un jeu de caractères raisonnable (lettres, chiffres, points,
    tirets), suffisant pour rejeter toute tentative d'injection dans la
    ligne NTP= de timesyncd.conf tout en acceptant IPs et noms d'hôte.
    """
    servers = []
    for value in values:
        value = value.strip()
        if not value:
            continue
        if not NTP_SERVER_RE.match(value):
            raise ValueError('invalid_ntp_server')
        servers.append(value)
    return servers


# --------------------------------------------------------------------------
# Réseau : changements avec filet de sécurité (rétablissement automatique)
# --------------------------------------------------------------------------

# Délai (secondes) avant rétablissement automatique si /api/network/confirm
# n'a pas été appelé entre-temps. Volontairement large : le temps que
# l'admin recharge la page sur la nouvelle adresse, s'authentifie à
# nouveau (nouvelle origine = nouveau cookie de session) et clique sur
# confirmer.
PENDING_DELAY_SECONDS = 45


def pending_paths(root: Path) -> dict:
    directory = root / 'config' / 'network-pending'
    directory.mkdir(parents=True, exist_ok=True)
    return {'dir': directory}


def _pending_files(root: Path, token: str) -> dict:
    directory = pending_paths(root)['dir']
    return {
        'status': directory / f'{token}.json',
        'confirm': directory / f'{token}.confirmed',
    }


def pending_change(root: Path) -> dict | None:
    """Dernier changement réseau/hostname en attente de confirmation,
    pour qu'une page rechargée sur la nouvelle adresse retrouve le fil
    (compte à rebours, bouton confirmer) sans dépendre de l'état
    JavaScript de l'onglet précédent, perdu au changement d'adresse.
    """
    directory = pending_paths(root)['dir']
    candidates = sorted(directory.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    for candidate in candidates:
        try:
            data = json.loads(candidate.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if data.get('state') == 'applied':
            return data
    return None


def confirm_change(root: Path, token: str) -> bool:
    files = _pending_files(root, token)
    if not files['status'].is_file():
        return False
    files['confirm'].touch()
    return True


def start_hostname_change(root: Path, new_hostname: str) -> dict:
    old_hostname = current_hostname()
    if not old_hostname:
        # Impossible de lire le nom d'hôte actuel (hostnamectl absent ou en
        # échec) : refuser plutôt que de risquer un rétablissement vers une
        # chaîne vide si la confirmation n'arrive jamais.
        raise RuntimeError('hostname_read_failed')

    token = secrets.token_hex(8)
    files = _pending_files(root, token)

    _write_status(files['status'], {
        'kind': 'hostname', 'state': 'pending', 'token': token,
        'old_value': old_hostname, 'new_value': new_hostname,
        'delay_seconds': PENDING_DELAY_SECONDS, 'started_at': time.time(),
    })

    script = f'''#!/bin/bash
set -u
CONFIRM={shlex.quote(str(files['confirm']))}
STATUS={shlex.quote(str(files['status']))}
write_status() {{ printf '%s' "$1" > "$STATUS.tmp" && mv "$STATUS.tmp" "$STATUS"; }}

# Laisse le temps à la réponse HTTP d'atteindre le navigateur avant de
# changer le nom d'hôte (sans effet sur la connectivité si l'accès se
# fait par adresse IP, mais peut couper un accès par <nom>.local via
# mDNS le temps que la nouvelle annonce Avahi se propage).
sleep 2

hostnamectl set-hostname {shlex.quote(new_hostname)}
sed -i "s/^127\\.0\\.1\\.1[[:space:]].*/127.0.1.1\\t{new_hostname}/" /etc/hosts

write_status '{{"kind":"hostname","state":"applied","token":"{token}","old_value":{json.dumps(old_hostname)},"new_value":{json.dumps(new_hostname)},"delay_seconds":{PENDING_DELAY_SECONDS},"applied_at":{time.time()}}}'

for i in $(seq 1 {PENDING_DELAY_SECONDS}); do
    sleep 1
    if [ -f "$CONFIRM" ]; then
        write_status '{{"kind":"hostname","state":"confirmed","token":"{token}"}}'
        exit 0
    fi
done

hostnamectl set-hostname {shlex.quote(old_hostname)}
sed -i "s/^127\\.0\\.1\\.1[[:space:]].*/127.0.1.1\\t{old_hostname}/" /etc/hosts
write_status '{{"kind":"hostname","state":"reverted","token":"{token}"}}'
'''
    run_detached(script, 'pidecoder hostname change')
    return {'token': token, 'delay_seconds': PENDING_DELAY_SECONDS}


def start_ip_change(root: Path, connection_name: str, method: str, address: str | None,
                     gateway: str | None, dns: list[str]) -> dict:
    """Bascule DHCP/IP statique sur `connection_name`, avec rétablissement
    automatique si /api/network/confirm n'est pas appelé à temps.

    `connection_name` doit être un nom déjà renvoyé par list_connections()
    — vérifié par l'appelant (config-web.py) avant d'arriver ici — pour ne
    jamais construire cette commande à partir d'un nom de connexion
    arbitraire non vérifié.
    """
    token = secrets.token_hex(8)
    files = _pending_files(root, token)
    old = connection_ipv4(connection_name)

    def clear_or(value):
        return value if value else ''

    new_addr = address if method == 'manual' else ''
    new_gw = gateway if method == 'manual' else ''
    new_dns = ','.join(dns) if method == 'manual' and dns else ''
    old_addr = old['address'] or ''
    old_gw = old['gateway'] or ''
    old_dns = ','.join(old['dns']) if old['dns'] else ''
    old_method = 'manual' if old['method'] == 'manual' else 'auto'

    _write_status(files['status'], {
        'kind': 'ip', 'state': 'pending', 'token': token,
        'connection': connection_name, 'old_value': old,
        'new_value': {'method': method, 'address': address, 'gateway': gateway, 'dns': dns},
        'delay_seconds': PENDING_DELAY_SECONDS, 'started_at': time.time(),
    })

    conn = shlex.quote(connection_name)
    script = f'''#!/bin/bash
set -u
CONFIRM={shlex.quote(str(files['confirm']))}
STATUS={shlex.quote(str(files['status']))}
write_status() {{ printf '%s' "$1" > "$STATUS.tmp" && mv "$STATUS.tmp" "$STATUS"; }}

# Marge avant de toucher à l'interface : laisse la réponse HTTP partir en
# premier (elle contient l'adresse à essayer ensuite côté navigateur).
sleep 2

nmcli -w 15 con mod {conn} \\
    ipv4.method {shlex.quote(method)} \\
    ipv4.addresses {shlex.quote(new_addr)} \\
    ipv4.gateway {shlex.quote(new_gw)} \\
    ipv4.dns {shlex.quote(new_dns)}
nmcli -w 15 con up {conn} >/dev/null 2>&1 || true

write_status '{{"kind":"ip","state":"applied","token":"{token}","connection":{json.dumps(connection_name)},"delay_seconds":{PENDING_DELAY_SECONDS},"applied_at":{time.time()}}}'

for i in $(seq 1 {PENDING_DELAY_SECONDS}); do
    sleep 1
    if [ -f "$CONFIRM" ]; then
        write_status '{{"kind":"ip","state":"confirmed","token":"{token}"}}'
        exit 0
    fi
done

nmcli -w 15 con mod {conn} \\
    ipv4.method {shlex.quote(old_method)} \\
    ipv4.addresses {shlex.quote(old_addr)} \\
    ipv4.gateway {shlex.quote(old_gw)} \\
    ipv4.dns {shlex.quote(old_dns)}
nmcli -w 15 con up {conn} >/dev/null 2>&1 || true
write_status '{{"kind":"ip","state":"reverted","token":"{token}"}}'
'''
    run_detached(script, 'pidecoder network change')
    return {'token': token, 'delay_seconds': PENDING_DELAY_SECONDS}


def apply_ntp(enabled: bool, servers: list[str]) -> None:
    """NTP activé/désactivé + liste de serveurs — pas de risque de perte
    de connectivité, donc application synchrone immédiate (pas de filet
    de sécurité, contrairement au nom d'hôte et à l'IP ci-dessus).

    Pas d'API D-Bus pour la liste de serveurs NTP elle-même (timedatectl
    ne gère que l'activation on/off) : reste à éditer directement
    /etc/systemd/timesyncd.conf. La section [Time] existe toujours dans le
    fichier par défaut de Debian/Raspberry Pi OS (juste commentée), mais on
    l'ajoute explicitement si absente plutôt que de supposer qu'elle l'est.
    """
    conf = shlex.quote('/etc/systemd/timesyncd.conf')
    servers_line = ' '.join(shlex.quote(s) for s in servers)
    command = f'''
set -e
timedatectl set-ntp {"true" if enabled else "false"}
grep -q '^\\[Time\\]' {conf} || printf '\\n[Time]\\n' >> {conf}
sed -i '/^NTP=/d;/^#NTP=/d' {conf}
sed -i '/^\\[Time\\]/a NTP={servers_line}' {conf}
systemctl restart systemd-timesyncd
'''
    result = run_sync_unsandboxed(command, timeout=20)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'ntp_apply_failed')


def apply_timezone(timezone: str) -> None:
    result = run_sync_unsandboxed(f'timedatectl set-timezone {shlex.quote(timezone)}', timeout=10)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'timezone_apply_failed')
