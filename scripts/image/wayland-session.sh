# Démarrage de la session Wayland de PiDecoder (image .img préconstruite).
#
# Copié dans ~/.bash_profile de l'utilisateur de l'image par build-image.sh.
# Raspberry Pi OS Lite n'embarque aucun environnement graphique : il n'y a
# donc ni gestionnaire de connexion ni session de bureau pour démarrer un
# compositeur. Le schéma retenu est le plus simple qui fonctionne avec
# systemd-logind :
#
#   getty@tty1 (connexion automatique) → shell de connexion → ce fichier
#   → labwc → socket /run/user/<uid>/wayland-0
#
# C'est ce socket qu'attend pidecoder-wayland.path, qui déclenche ensuite le
# moteur vidéo (voir systemd/pidecoder.service.in et docs/installation.md).
# Passer par la connexion automatique d'un vrai getty n'est pas un détail :
# c'est ce qui fait ouvrir une session logind, qui crée /run/user/<uid>,
# fournit le siège dont labwc a besoin et démarre le bus D-Bus utilisateur
# dont dépend PipeWire pour l'audio.
#
# Lancé uniquement sur tty1 et seulement si aucune session Wayland n'existe
# déjà : une connexion en SSH ou sur un autre terminal ne doit surtout pas
# tenter de démarrer un second compositeur.

if [ -z "${WAYLAND_DISPLAY:-}" ] && [ "${XDG_VTNR:-}" = "1" ]; then
    # Le journal reste dans le dossier personnel : labwc n'écrit pas dans le
    # journal systemd ici, puisqu'il n'est pas lancé par un service.
    exec labwc >"$HOME/.labwc.log" 2>&1
fi
