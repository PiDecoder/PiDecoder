#!/usr/bin/env python3
"""Messages HTTP bilingues (FR/EN) pour config-web.py.

Ce module ne dépend d'aucune bibliothèque externe (pas de gettext/Babel),
conformément à la philosophie « dépendances minimales » du projet. Il ne
couvre que les messages qui atteignent effectivement le navigateur via les
réponses JSON de l'API (`error`/`message`). Les journaux serveur uniquement
(operator-facing, non retournés au navigateur) restent en français : voir
la note en bas de fichier.

La langue active est portée par un cookie `pidecoder_lang` (non HttpOnly,
lisible par le JavaScript du frontend), lu par `lang_from_cookie_header()`.
Par défaut : français, pour ne rien changer au comportement existant.
"""
from __future__ import annotations

DEFAULT_LANG = 'fr'
SUPPORTED_LANGS = ('fr', 'en')

MESSAGES: dict[str, dict[str, str]] = {
    'auth.required': {
        'fr': 'Authentification requise',
        'en': 'Authentication required',
    },
    'login.too_many_attempts': {
        'fr': 'Trop de tentatives, réessaie dans quelques minutes',
        'en': 'Too many attempts, try again in a few minutes',
    },
    'login.invalid_password': {
        'fr': 'Mot de passe incorrect',
        'en': 'Incorrect password',
    },
    'diagnostics.failed': {
        'fr': 'Impossible de générer les diagnostics : {error}',
        'en': 'Unable to generate diagnostics: {error}',
    },
    'onvif.rtsp_uri_invalid': {
        'fr': 'URI RTSP ONVIF invalide',
        'en': 'Invalid ONVIF RTSP URI',
    },
    'camera.grid_url_missing': {
        'fr': 'URL mosaïque absente pour {name}',
        'en': 'Missing mosaic URL for {name}',
    },
    'onvif.media_or_profile_missing': {
        'fr': 'Service Media ou profil mosaïque/plein écran absent',
        'en': 'Media service or mosaic/fullscreen profile missing',
    },
    'camera.manage.action_added': {
        'fr': 'ajoutée',
        'en': 'added',
    },
    'camera.manage.action_updated': {
        'fr': 'mise à jour',
        'en': 'updated',
    },
    'camera.manage.duplicates': {
        'fr': '{count} doublon(s) supprimé(s). ',
        'en': '{count} duplicate(s) removed. ',
    },
    'camera.manage.message': {
        'fr': '{name} {action}. {duplicates}Clique sur Appliquer pour charger les flux.',
        'en': '{name} {action}. {duplicates}Click Apply to load the streams.',
    },
    'ptz.unknown_command': {
        'fr': 'Commande PTZ inconnue',
        'en': 'Unknown PTZ command',
    },
    'config.at_least_one_camera': {
        'fr': 'Au moins une caméra est nécessaire',
        'en': 'At least one camera is required',
    },
    'apply.restart_failed': {
        'fr': 'Échec du redémarrage',
        'en': 'Restart failed',
    },
    'apply.saved_manual_restart': {
        'fr': (
            'Configuration sauvegardée. Le moteur PiDecoder doit être '
            'redémarré manuellement.'
        ),
        'en': (
            'Configuration saved. The PiDecoder engine must be restarted '
            'manually.'
        ),
    },
    'apply.applied_restarted': {
        'fr': 'Configuration appliquée. PiDecoder a redémarré.',
        'en': 'Configuration applied. PiDecoder restarted.',
    },
    'tls.generate_failed': {
        'fr': 'Échec de la génération du certificat',
        'en': 'Certificate generation failed',
    },
    'tls.import_failed': {
        'fr': 'Échec de l\'import du certificat',
        'en': 'Certificate import failed',
    },
    'tls.import_requires_https': {
        'fr': (
            'Import possible uniquement en HTTPS : la clé privée transiterait '
            'en clair en HTTP. Active d\'abord HTTPS, ou utilise '
            'scripts/manage-tls.sh en SSH.'
        ),
        'en': (
            'Import only available over HTTPS: the private key would '
            'otherwise be sent in the clear over HTTP. Enable HTTPS first, '
            'or use scripts/manage-tls.sh over SSH.'
        ),
    },
    'tls.cert_and_key_required': {
        'fr': 'Certificat et clé requis',
        'en': 'Certificate and key are required',
    },
    'tls.enable_failed': {
        'fr': 'Échec de l\'activation de HTTPS',
        'en': 'Failed to enable HTTPS',
    },
    'tls.disable_failed': {
        'fr': 'Échec de la désactivation de HTTPS',
        'en': 'Failed to disable HTTPS',
    },
    'tls.reload_failed': {
        'fr': 'Certificat installé mais rechargement TLS échoué : {error}',
        'en': 'Certificate installed but the TLS reload failed: {error}',
    },
    'tls.disable_blocked_no_http': {
        'fr': (
            'Impossible de désactiver HTTPS : l\'accès HTTP est lui aussi '
            'désactivé, ça couperait tout accès à l\'interface Web. '
            'Réactive HTTP d\'abord.'
        ),
        'en': (
            'Cannot disable HTTPS: HTTP access is also disabled, which '
            'would cut off all access to the Web interface. Re-enable '
            'HTTP first.'
        ),
    },
    'http.disable_blocked_no_https': {
        'fr': (
            'Impossible de désactiver l\'accès HTTP : HTTPS est lui aussi '
            'désactivé, ça couperait tout accès à l\'interface Web. Active '
            'HTTPS d\'abord (génère un certificat si besoin).'
        ),
        'en': (
            'Cannot disable HTTP access: HTTPS is also disabled, which '
            'would cut off all access to the Web interface. Enable HTTPS '
            'first (generate a certificate if needed).'
        ),
    },
    'update.no_repo_path': {
        'fr': (
            'Mise à jour indisponible : cette installation ne connaît pas '
            'l\'emplacement du dépôt Git. Relance sudo ./scripts/install.sh '
            'depuis ton clone Git une première fois pour activer cette '
            'fonctionnalité.'
        ),
        'en': (
            'Update unavailable: this installation does not know where the '
            'Git clone is. Run sudo ./scripts/install.sh from your Git '
            'clone once to enable this feature.'
        ),
    },
    'update.already_running': {
        'fr': 'Une mise à jour est déjà en cours',
        'en': 'An update is already in progress',
    },
    'update.no_service_user': {
        'fr': 'Impossible de déterminer l\'utilisateur du service vidéo',
        'en': 'Unable to determine the video service user',
    },
    'network.invalid_hostname': {
        'fr': 'Nom d\'hôte invalide (lettres, chiffres et tirets, 63 caractères maximum)',
        'en': 'Invalid hostname (letters, digits and hyphens, 63 characters max)',
    },
    'network.hostname_change_failed': {
        'fr': 'Échec du changement de nom d\'hôte : {error}',
        'en': 'Hostname change failed: {error}',
    },
    'network.nmcli_unavailable': {
        'fr': 'NetworkManager (nmcli) est introuvable sur ce système',
        'en': 'NetworkManager (nmcli) was not found on this system',
    },
    'network.unknown_connection': {
        'fr': 'Connexion réseau inconnue',
        'en': 'Unknown network connection',
    },
    'network.invalid_method': {
        'fr': 'Mode d\'adressage invalide',
        'en': 'Invalid addressing mode',
    },
    'network.invalid_address': {
        'fr': 'Adresse IP, passerelle ou DNS invalide',
        'en': 'Invalid IP address, gateway or DNS server',
    },
    'network.invalid_ntp_server': {
        'fr': 'Adresse de serveur NTP invalide',
        'en': 'Invalid NTP server address',
    },
    'network.ntp_failed': {
        'fr': 'Échec de la configuration NTP : {error}',
        'en': 'NTP configuration failed: {error}',
    },
    'network.invalid_timezone': {
        'fr': 'Fuseau horaire invalide',
        'en': 'Invalid timezone',
    },
    'network.timezone_failed': {
        'fr': 'Échec du changement de fuseau horaire : {error}',
        'en': 'Timezone change failed: {error}',
    },
    'import.invalid_file': {
        'fr': 'Fichier PiDecoder invalide',
        'en': 'Invalid PiDecoder file',
    },
    'import.no_valid_camera': {
        'fr': 'Le fichier ne contient aucune caméra valide',
        'en': 'The file contains no valid camera',
    },
    'import.imported': {
        'fr': 'Configuration importée',
        'en': 'Configuration imported',
    },
    'password.current_incorrect': {
        'fr': 'Mot de passe actuel incorrect',
        'en': 'Current password is incorrect',
    },
    'password.must_be_typed_twice': {
        'fr': 'Le nouveau mot de passe doit être saisi deux fois',
        'en': 'The new password must be entered twice',
    },
    'password.too_short': {
        'fr': 'Le nouveau mot de passe doit contenir au moins 8 caractères',
        'en': 'The new password must be at least 8 characters long',
    },
    'password.mismatch': {
        'fr': 'Les mots de passe ne correspondent pas',
        'en': 'Passwords do not match',
    },
    'password.changed': {
        'fr': 'Mot de passe modifié',
        'en': 'Password changed',
    },
    'server.error': {
        'fr': 'Erreur serveur : {error}',
        'en': 'Server error: {error}',
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """Traduit `key` dans `lang`, avec repli français puis sur la clé elle-même.

    `kwargs` sont substitués via `str.format` (ex: t('camera.grid_url_missing',
    'en', name='Cam 1')). Une clé inconnue est renvoyée telle quelle plutôt que
    de lever une exception : un message non traduit ne doit jamais faire
    planter une réponse API.
    """
    entry = MESSAGES.get(key)

    if entry is None:
        return key

    template = entry.get(lang) or entry.get(DEFAULT_LANG) or key

    if not kwargs:
        return template

    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def lang_from_cookie_header(cookie_header: str | None) -> str:
    """Extrait `pidecoder_lang` d'un en-tête HTTP `Cookie` brut.

    Volontairement indépendant de `http.cookies.SimpleCookie` pour rester
    utilisable sans objet requête complet ; `config-web.py` utilise déjà
    SimpleCookie pour le cookie de session, ce qui reste inchangé.
    """
    if not cookie_header:
        return DEFAULT_LANG

    for part in cookie_header.split(';'):
        if '=' not in part:
            continue

        name, _, value = part.strip().partition('=')

        if name == 'pidecoder_lang':
            value = value.strip().strip('"')
            return value if value in SUPPORTED_LANGS else DEFAULT_LANG

    return DEFAULT_LANG


# Note sur la portée : les messages d'erreur ONVIF détaillés générés par
# onvif_client.py (échecs SOAP/HTTP/XML pendant la découverte ou
# l'identification d'une caméra, voir _soap() dans ce fichier) restent en
# français pour cette première version du bilinguisme. Ce sont des messages
# de diagnostic ponctuels (configuration initiale d'une caméra), déjà
# doublés dans le journal de debug ONVIF, et non les messages d'usage
# courant de l'interface — voir docs/PROJECT-STATE.md pour le suivi de cette
# limitation connue.
