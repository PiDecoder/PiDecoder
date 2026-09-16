# Changelog

## 1.3 (nouveau — image SD, en cours de validation sur matériel réel)

### Image .img flashable directement sur carte SD (demande explicite)

Jusqu'ici, installer PiDecoder demandait deux étapes : installer Raspberry Pi
OS, puis cloner le dépôt et lancer `install.sh`. Nouveau
`scripts/build-image.sh` : il fabrique une image `.img.xz` qu'on écrit
directement sur une carte SD avec Raspberry Pi Imager, et qui démarre sur le
mur d'images sans qu'on ait jamais ouvert un terminal.

Le principe est volontairement modeste : **on ne reconstruit pas un système**.
Le script part de l'image officielle Raspberry Pi OS Lite arm64 (épinglée à
une version précise et vérifiée par sa somme SHA256), l'ouvre en boucle locale,
et y lance dans un chroot exactement le même `install.sh` que sur un Pi réel.
L'alternative aurait été pi-gen, l'outil officiel, qui reconstruit tout depuis
un debootstrap : des heures de construction et un système complet à maintenir,
là où on n'a besoin que d'ajouter une application à une base déjà éprouvée. La
seule différence entre une carte flashée et une installation manuelle, c'est
qui a tapé les commandes.

- **base Lite plutôt que Desktop** (choix explicite) : Raspberry Pi OS Lite
  n'a aucun environnement graphique, donc le script ajoute le strict
  nécessaire — `labwc` (le compositeur Wayland de Raspberry Pi OS Desktop,
  donc pas un inconnu), la pile Mesa/EGL du GPU V3D, PipeWire pour l'audio de
  la vue Focus, NetworkManager pour l'onglet Réseau, et Avahi pour la
  résolution `<nom>.local`. Résultat : une image nettement plus légère qu'avec
  la base Desktop, sans bureau ni applications dont un mur d'images n'a que
  faire ;
- **session graphique** : connexion automatique sur tty1 (extension de
  `getty@tty1`), puis `~/.bash_profile` lance `labwc`, qui crée le socket
  `/run/user/<uid>/wayland-0` — exactement ce qu'attend déjà
  `pidecoder-wayland.path` pour déclencher le moteur vidéo. Passer par un vrai
  getty n'est pas cosmétique : c'est ce qui ouvre une session logind, donc ce
  qui fournit le siège dont labwc a besoin et le bus D-Bus utilisateur dont
  dépend PipeWire ;
- **tout ce qui doit rester unique par appareil est retiré de l'image** et
  regénéré au premier démarrage par un nouveau service
  `pidecoder-firstboot.service` : clés d'hôte SSH (une clé privée partagée
  permettrait d'usurper n'importe quel autre Pi du parc), identifiant machine
  (sinon toutes les cartes présentent le même DUID DHCP), certificat TLS — dont
  la clé privée serait publique, et dont les Subject Alternative Names
  porteraient le nom d'hôte et les IP de la machine de construction — et le nom
  d'hôte lui-même, dérivé du numéro de série du SoC (`pidecoder-xxxxxx`) pour
  que deux appareils ne se disputent pas la même adresse `.local` ;
- **l'agrandissement de la partition racine n'a pas été réimplémenté** : le
  mécanisme natif de Raspberry Pi OS (`init=` dans `cmdline.txt`) s'en charge
  déjà, plus tôt que tout ce qu'on pourrait écrire, et le script vérifie qu'il
  est toujours armé avant de refermer l'image ;
- **la chaîne de compilation reste dans l'image**, à dessein. La retirer
  gagnerait environ 1 Gio, mais la mise à jour en un clic de l'onglet Système
  fait `git pull` puis `install.sh`, donc recompile le moteur natif : une image
  allégée serait une image incapable de se mettre à jour. Pour la même raison
  l'image embarque un vrai clone Git, avec son dépôt distant, et pas une copie
  des fichiers ;
- `.github/workflows/build-image.yml` fabrique l'image à chaque tag `v*` et
  l'attache à la Release GitHub, somme de contrôle comprise. Le coureur GitHub
  est en x86_64 : le chroot arm64 y passe par qemu, c'est plus lent mais c'est
  le même script, sans variante.

### Bouton « Activer SSH » dans la page Web (demande explicite)

SSH est installé mais désactivé par défaut sur l'image (voir plus haut, clés
d'hôte régénérées au premier démarrage) — jusqu'ici, l'activer demandait un
accès physique à l'écran/clavier du Pi (console locale, ou modifier la carte
SD sur un autre poste). Nouveau panneau dans l'onglet Sécurité de la page
Web : bouton pour activer (et désactiver) SSH à la volée, sans redémarrage
du service Web ni du moteur vidéo.

Même contrainte de conception que la mise à jour logicielle et les
changements réseau (voir `system_admin.py`) : `pidecoder-config.service`
tourne avec `ProtectSystem=strict`, qui interdirait l'écriture du lien
`/etc/systemd/system/...` que fait `systemctl enable`. L'activation est donc
déléguée à une unité `systemd-run` indépendante, hors de ce bac à sable —
même mécanisme, pas de nouvelle dérogation à ajouter au service.

### Retour terrain : l'assistant de Raspberry Pi OS renommait l'utilisateur de l'image

Première carte réellement flashée, et un seul défaut expliquait tous les
symptômes : la console demandait de créer un mot de passe au premier
démarrage, l'écran restait noir, et l'ajout d'une caméra échouait avec
« Job for pidecoder.service failed ».

Cause : sur une image Lite, `userconfig.service` s'accapare tty1 au premier
démarrage pour demander un nom d'utilisateur, puis **renomme l'utilisateur
d'uid 1000** — c'est-à-dire celui que l'image venait de créer. Sur le Pi de
test, `pidecoder` était devenu `admin` (`getent passwd 1000` ne renvoyait plus
que `admin`). Tout ce qui le désignait par son nom cassait alors en cascade :
la connexion automatique de tty1 pointait sur un utilisateur inexistant, donc
labwc ne démarrait pas, donc aucun socket Wayland n'existait, donc
`pidecoder.service` échouait à son `ExecStartPre` — d'où l'erreur au moment
d'appliquer une configuration caméra. Le `User=` des unités rendues par
`install.sh` était cassé pour la même raison.

Corrigé dans `build-image.sh` : l'assistant est masqué, et `getty@tty1` est
réactivé explicitement — sans ça la neutralisation serait pire que le mal,
puisque sur ces images userconfig.service *remplace* getty@tty1, désactivé.
Deux vérifications ont été ajoutées en fin de construction : que l'assistant
est bien masqué, et que l'utilisateur de l'image existe toujours.

### Retour terrain : fermer la fenêtre laissait l'écran vide pour de bon

Une fermeture de la fenêtre (raccourci du compositeur, par ex. Alt+F4 lié
par défaut sous labwc) fait quitter le processus proprement (code 0). Or
`pidecoder.service` avait `Restart=on-failure` : une sortie propre n'étant
pas un « échec » au sens systemd, le service ne redémarrait pas — écran
vide, sans la moindre erreur dans les journaux pour expliquer pourquoi.

Corrigé en passant `pidecoder.service` en `Restart=always` : ce service est
un mur d'images qui doit rester affiché en permanence, peu importe la
raison de son arrêt. Le garde-fou contre un vrai plantage en boucle (voir
plus haut, le SIGILL sous Trixie) reste actif : c'est le comportement par
défaut de systemd (`StartLimitIntervalSec`/`StartLimitBurst`), pas
`Restart=`, qui l'assure, et il n'a pas été touché.

### Retour terrain : fenêtre minuscule dans le coin au démarrage, corrigée par F puis F

Au premier lancement, la fenêtre s'affichait en tout petit dans le coin
supérieur haut gauche au lieu de tout l'écran, malgré le plein écran activé
en configuration — un rebasculement manuel (touche F deux fois) suffisait
à corriger la géométrie.

Cause : `SDL_SetWindowFullscreen()` était appelé juste après
`SDL_CreateWindow()`, sans qu'aucun événement SDL n'ait encore été traité.
Sous Wayland, la taille réelle de la sortie n'est communiquée au client
qu'après un aller-retour du protocole (configuration de la surface), qui ne
se produit qu'en pompant les événements — ce qui n'avait pas encore eu lieu
à cet instant précis. Le rebasculement manuel fonctionnait simplement parce
que le temps de l'appuyer, cet aller-retour avait eu le temps de se faire.

Corrigé dans `Application::run()` : on attend maintenant la confirmation
d'affichage de la fenêtre (événement SDL `SHOWN`/`EXPOSED`, avec un plafond
de 500 ms pour ne jamais bloquer indéfiniment si cet événement n'arrivait
pas) avant le seul et unique appel à `toggle_fullscreen()` au démarrage.

**Ces deux correctifs touchent le C++** (`Application.cpp` et
`pidecoder.service.in`) : recompilation nécessaire (`sudo ./scripts/install.sh`).

### Retour terrain : le curseur de souris ne disparaissait plus

Le curseur restait affiché en permanence au milieu de la mosaïque, même
sans y toucher — jamais remarqué avant l'image SD, tout simplement parce
que ce comportement n'a jamais été implémenté dans le moteur natif
lui-même : le seul poste déjà validé sur le terrain (`olympus-vss-mon1`)
tourne sur Raspberry Pi OS Desktop, dont l'environnement de bureau s'en
chargeait à la place de l'application. L'image, elle, ne fait tourner que
labwc seul — rien qui masque le curseur d'un client à sa place.

Ajouté dans `Application.cpp`/`Application.hpp` : le curseur se masque
après 3 secondes sans mouvement de souris (`SDL_ShowCursor`, déjà utilisé
ailleurs dans le projet — portable, sans dépendance à une fonctionnalité
particulière du compositeur), et réapparaît au moindre mouvement. Même
principe déjà utilisé pour l'overlay PTZ et l'indicateur audio (minuteur
`std::chrono::steady_clock` remis à zéro à chaque activité).

**Changement C++** : nécessite `sudo ./scripts/install.sh` (recompilation),
pas seulement `sync-dev.sh`.

### Retour terrain : écran noir au premier démarrage tant qu'aucune caméra n'est configurée

Le passage sur Bookworm a corrigé le plantage du mur vidéo, mais un souci
distinct est apparu : `pidecoder.service` refuse de démarrer tant qu'aucune
caméra active n'est configurée (`check-camera-config.py`, voulu pour ne pas
afficher un mur vide). Sur une image flashée fraîche, ça veut dire qu'au
tout premier démarrage l'écran reste noir — et donc que l'overlay natif qui
affiche l'adresse IP de l'appareil ne s'affiche jamais non plus, alors que
c'est précisément l'information dont on a besoin pour aller le configurer
depuis un autre poste (l'image ne propose pas de clavier/écran de secours).

Corrigé en ajoutant une **caméra de démonstration** au `cameras.json` par
défaut de l'image (uniquement l'image — l'installation manuelle garde une
configuration vide, ce qui reste le bon choix quand on installe depuis un
terminal). Elle pointe vers une image fixe générée à la construction
(`/opt/pidecoder/share/demo/demo.bmp`, un aplat de couleur sans aucune
dépendance réseau ni service tiers), juste assez pour que la condition de
démarrage soit satisfaite. L'overlay réseau (nom d'hôte, IP, ports Web) est
géré indépendamment du contenu de la caméra : il s'affiche donc normalement
dès que le service démarre. Cette caméra de démonstration disparaît d'elle
-même dès qu'une vraie caméra est ajoutée depuis l'interface Web — ce n'est
qu'une entrée JSON ordinaire, pas un mode spécial à désactiver.

### Retour terrain : l'onglet Mise à jour annonçait « Aucune branche distante suivie »

Signalé après le passage sur Bookworm : l'onglet Système affichait « No
tracked remote branch — unable to check for updates » alors que le dépôt
Git de l'image a bien un distant `origin` configuré.

Cause : `build-image.sh` clone le dépôt source puis fait
`git checkout <commit exact>` pour figer la version construite — ce qui
laisse le dépôt en **HEAD détachée**, sans branche du tout. Or
`check_update()` (`system_admin.py`) détecte les mises à jour via
`git rev-parse @{upstream}`, qui exige une branche avec un suivi configuré :
sans branche, pas de suivi possible, d'où le message.

Corrigé en faisant pointer une vraie branche (`main`, la branche de
développement principale — pas la référence utilisée pour la construction,
qui est souvent un tag figé et ne bougera donc plus jamais) sur ce commit
au moment du clone dans l'image, et en configurant son suivi de
`origin/main` directement dans la configuration Git (sans dépendre d'un
`git fetch` préalable, impossible à ce stade puisque ce clone n'a encore
jamais parlé au vrai `origin`). Le premier `git fetch` fait sur l'appareil,
déclenché par l'onglet Mise à jour lui-même, complète alors normalement
cette référence.

### Retour terrain : le mur vidéo plantait en boucle (SIGILL) — retour à Bookworm

Sur la première carte flashée avec la base Trixie, `pidecoder.service`
redémarrait toutes les 30 secondes environ, avec un flot de
`MESA: error: Export failed` juste avant chaque plantage (`SIGILL`).

Diagnostic mené par élimination, chaque hypothèse vérifiée sur le Pi avant
d'être écartée :

- session/« seat » : `loginctl` montrait une session Wayland active et
  correctement attribuée à `seat0` — pas un souci de gestion de siège ;
- pilote noyau : `dmesg` ne montrait que l'initialisation normale du V3D au
  démarrage, aucune erreur ni redémarrage du GPU au moment du plantage ;
- durcissement systemd : `pidecoder.service` exclut déjà délibérément
  `SystemCallFilter`/`MemoryDenyWriteExecute` (voir le commentaire dans
  `pidecoder.service.in`), donc pas un filtre trop strict qui bloquerait le
  rendu.

Un relevé `WAYLAND_DEBUG=1` a montré que le protocole Wayland continuait de
fonctionner (les `attach`/`commit` réussissaient) malgré des dizaines
d'échecs d'export répétés, pendant plusieurs centaines de millisecondes,
avant que le crash ne survienne — le profil d'un bug interne au pilote
Mesa/V3D plutôt que d'un blocage immédiat côté configuration.

Cause retenue : l'image de base utilisée pour la construction était
**Trixie (Debian 13)**, publiée la veille du premier flashage — jamais
testée sur ce pipeline de rendu. La machine de production déjà validée sur
le terrain (`olympus-vss-mon1`, voir plus bas « RC3 field validation »)
tourne sur **Bookworm (Debian 12)**, où ce même rendu SDL2/labwc/V3D est
confirmé opérationnel. `build-image.sh` est repassé sur la dernière image
Bookworm (« oldstable ») disponible plutôt que sur Trixie, en attendant que
cette dernière ait fait ses preuves sur ce pipeline précis.

### Retour terrain : le scan ONVIF ne trouvait plus aucune caméra depuis l'interface Web

Signalé après le premier flashage réel : le bouton « Rechercher les caméras »
renvoyait systématiquement « 0 équipement(s) ONVIF trouvé(s) », avec un
diagnostic affichant « Interfaces : Aucune » et 0 sonde envoyée — comme si le
Pi n'avait plus aucune interface réseau active, ce qui était faux (le reste
de l'administration Web fonctionnait normalement).

En lançant `onvif_client.discover()` directement en SSH (donc hors du
service Web), la découverte fonctionnait parfaitement : 6 caméras trouvées
en quelques secondes. La seule différence entre les deux appels est le
service systemd qui les héberge.

Cause : exactement le même défaut que celui déjà rencontré et corrigé pour
l'overlay réseau du player natif (voir plus bas, « `RestrictAddressFamilies`
du service bloquait `getifaddrs()` »), mais cette fois côté administration
Web. `_ipv4_interfaces()` (dans `onvif_client.py`) énumère les interfaces en
lançant `ip -j -4 addr show up`, qui interroge le noyau via une socket
`AF_NETLINK` — et `pidecoder-config.service` n'autorisait que `AF_UNIX`,
`AF_INET` et `AF_INET6`. La socket netlink échouait silencieusement
(`EAFNOSUPPORT`), la commande sortait en erreur, `_ipv4_interfaces()`
renvoyait une liste vide, et `discover()` s'arrêtait tout de suite sans
émettre la moindre sonde — d'où le « Interfaces : Aucune » du diagnostic.

Corrigé en ajoutant `AF_NETLINK` à `RestrictAddressFamilies` dans
`systemd/pidecoder-config.service.in`, au même titre que pour
`pidecoder.service`.

### Le certificat n'est plus généré pendant la construction de l'image

Deuxième échec en CI, après 11 minutes cette fois : `install.sh` s'arrêtait sur
« Échec de la génération du certificat TLS auto-signé ». Dans un chroot,
`hostname -f` et `hostname -I` ne décrivent pas la machine cible mais la
machine de construction — et quand le nom d'hôte remonte vide, le SAN devient
`DNS:,DNS:localhost,...`, qu'openssl refuse (« invalid null value »).
Reproduit à l'identique en bac à sable pour confirmer.

La correction n'est pas de rafistoler la détection du nom d'hôte : c'est de ne
pas générer de certificat du tout à la construction. Celui-ci était de toute
façon supprimé quelques lignes plus loin (clé privée identique sur toutes les
cartes, SAN portant l'identité de la machine de build) — on payait donc une
génération de clé RSA sous émulation pour jeter le résultat, avec un point de
panne en prime. `build-image.sh` passe désormais `--no-https` à `install.sh`,
et c'est `pidecoder-firstboot.service` qui crée le certificat sur l'appareil,
avec les bonnes valeurs. HTTPS s'active tout seul dès que le certificat existe,
il n'y avait rien d'autre à prévoir. La suppression du certificat reste en
place à la fin de la construction, comme filet.

Au passage, un défaut qui a coûté ce cycle de 11 minutes pour rien :
l'erreur d'openssl partait dans `/dev/null` avec le reste, et l'échec ne disait
donc rien de sa cause. Elle est maintenant capturée et remontée, avec le nom
et les SAN qui ont été refusés.

### Bit exécutable des scripts, perdu au passage par Windows

Premier déclenchement réel du workflow : échec en une seconde, code 1, sans
message parlant. Cause : le dépôt est édité depuis Windows, qui n'a pas de bit
exécutable, donc `build-image.sh` est arrivé dans Git en mode 100644 —
`sudo ./scripts/build-image.sh` ne peut alors tout simplement pas s'exécuter
sur le coureur Linux. `install.sh` et `validate-release.sh`, plus anciens,
étaient bien en 100755, ce qui rendait le problème invisible jusqu'ici.

Deux corrections, parce que l'une sans l'autre laisse un piège :
`git update-index --chmod=+x` sur les scripts destinés à être lancés
directement (`build-image.sh`, `manage-tls.sh`, `sync-dev.sh`,
`image/firstboot.sh` — les deux du milieu étaient dans le même cas, et
`docs/installation.md` documente pourtant `sudo ./scripts/manage-tls.sh`), et
appel via `bash ./scripts/build-image.sh` dans le workflow, pour que la CI
soit indifférente au mode du fichier même si un futur ajout depuis Windows
repasse en 100644.

### Contrôle d'espace disque par emplacement

Retour immédiat au premier essai : un Pi en service n'a pas forcément 10 Gio
libres sur sa propre carte. Rien n'oblige pourtant à construire l'image sur
cette carte — le script a déjà `--work-dir`, `--cache-dir` et `--output`, et
une clé USB branchée sur le Pi suffit. Le contrôle d'espace a été revu en
conséquence : il ne vérifiait que le répertoire de travail, alors que les trois
emplacements peuvent être sur des systèmes de fichiers différents (le cache et
la sortie seraient restés sur la carte SD, pour environ 1,5 Gio à eux deux, et
la construction serait morte en cours de route au lieu d'échouer tout de
suite). Ils sont désormais vérifiés séparément, avant de commencer, et le
message d'erreur nomme l'option à utiliser pour déplacer l'emplacement fautif.

### Mot de passe par défaut imposé au premier démarrage

Corollaire de l'image : une image distribuée contient forcément un mot de passe
identique sur toutes les cartes, donc public. Le compte Web de l'image
(`admin` / `pidecoder`) est marqué `must_change` dans `web-auth.json`, et ce
n'est pas qu'un écran :

- côté serveur, `need()` refuse désormais **tous** les points d'API sauf
  `/api/change-password` tant que le drapeau est présent. Un blocage purement
  visuel aurait été contournable par un simple `curl`, ou par un onglet resté
  ouvert ;
- côté navigateur, la connexion mène directement à un écran dédié
  (« Premier démarrage »), et pas à l'application ;
- le drapeau disparaît tout seul au premier changement réussi : la fonction qui
  écrit le nouveau mot de passe est la même, appelée sans l'argument.

Nouveaux drapeaux pour permettre tout ça sans console interactive, puisque la
construction se fait dans un chroot : `config-web.py --password-stdin
--must-change`, et `install.sh --web-password-stdin
--web-password-must-change`. Le mot de passe transite par l'entrée standard et
n'apparaît donc jamais dans une ligne de commande, ni dans la liste des
processus.

**Testé** : toute la partie interface Web a été exercée pour de vrai dans ce
bac à sable — un `config-web.py` lancé avec un compte marqué, connexion,
vérification que `/api/config` et `/api/network/hostname` répondent bien 403,
changement refusé si le mot de passe est trop court, changement accepté, puis
reconnexion et accès normal retrouvé.

La plomberie de l'image a elle aussi été exercée réellement, sur une fausse
image fabriquée pour l'occasion (même table MBR, mêmes partitions qu'une vraie
image Pi OS) : agrandissement, montage, réduction, réécriture de la table,
troncature, compression, et vérification que le système de fichiers final passe
`e2fsck` et que son contenu est intact octet pour octet. Ces tests ont trouvé
deux vrais bugs avant livraison : les périphériques en boucle locale n'étaient
jamais détachés (la fonction qui les attachait était appelée dans une
substitution de commande, donc dans un sous-shell, et la liste utilisée par le
nettoyage restait vide), et le fichier de somme de contrôle contenait `-` au
lieu du nom de l'image, ce qui faisait attendre `sha256sum -c` sur l'entrée
standard. Un troisième point a été durci au passage : les codes de retour
d'`e2fsck` étaient tous ignorés, y compris ceux qui signalent des erreurs **non
corrigées** — une image au système de fichiers douteux serait partie en
production sans un mot.

**Pas encore testé** : la construction complète elle-même, qui exige un chroot
arm64 (impossible ici : pas de qemu-user, et apt est bloqué dans ce bac à
sable), donc l'installation des paquets, la compilation du moteur dans l'image,
et évidemment le démarrage réel d'une carte flashée. Le premier essai est à
faire sur le Pi avec `sudo ./scripts/build-image.sh`, et la première carte à
tester sur un Pi qui n'est pas en production.

## 1.2.0 — HTTPS, mise à jour Web, configuration réseau et gestion des ports (2026-09-16)

Version publiée regroupant tout ce qui a été construit depuis la
v1.1.0 : HTTPS pour l'interface d'administration (avec HTTP et HTTPS sur
deux ports indépendants, éditables depuis la Web UI), la mise à jour en
un clic, le panneau de configuration réseau (nom d'hôte, IP DHCP/manuelle,
NTP, fuseau horaire) avec son filet de sécurité automatique, et l'overlay
IP/nom d'hôte/MAC/ports affiché sur l'écran du player au démarrage. Le
détail ci-dessous liste chaque fonctionnalité avec son propre historique
de tests (bac à sable puis retours terrain successifs sur le Pi réel).

### HTTP et HTTPS sur deux ports distincts (demande explicite)

Jusqu'ici, l'interface d'administration Web n'écoutait que sur **un seul
port** (8080 par défaut), qui servait soit HTTP soit HTTPS selon qu'un
certificat était actif — activer/désactiver HTTPS depuis l'onglet Sécurité
faisait donc *disparaître* l'autre protocole plutôt que de coexister avec
lui. Sur demande explicite : HTTP et HTTPS écoutent désormais **en
parallèle, chacun sur son propre port** (8080 pour HTTP, 8443 pour HTTPS
par défaut), tous les deux configurables séparément.

- `scripts/install.sh` : nouvelle option `--https-port PORT` (défaut
  8443), à côté de `--port` (HTTP, défaut 8080, inchangé) — les deux
  doivent être différents (vérifié). Rappel du port HTTP : `--port` reste
  le nom historique, pas renommé pour ne pas casser les installations qui
  le passent déjà ;
- `scripts/config-web.py` fait maintenant tourner **deux serveurs HTTP en
  parallèle** (un thread chacun) : le port HTTP est actif tant que le
  marqueur `config/http-disabled` est absent, le port HTTPS tant qu'un
  certificat (`config/tls/cert.pem`+`key.pem`) est présent — exactement le
  même mécanisme que la présence/absence de certificat gérait déjà pour
  HTTPS seul, maintenant symétrique des deux côtés. Garde-fou : impossible
  de désactiver le second si le premier est déjà coupé (ça couperait tout
  accès à l'interface Web) — refusé avec un message clair côté API ; et si,
  malgré tout, les deux se retrouvaient désactivés sur le disque en même
  temps (édition manuelle, par exemple), le port HTTP est forcé au
  démarrage plutôt que de ne rien écouter du tout ;
- onglet **Sécurité** : le panneau HTTPS existant affiche maintenant son
  port, et un nouveau panneau **Accès HTTP** permet de l'activer/désactiver
  indépendamment, avec le même mécanisme de redémarrage (~30s) et de
  redirection automatique que HTTPS — la redirection ne se déclenche que si
  le navigateur est connecté par le port qu'on vient justement de couper
  (sinon rien ne change pour la session en cours, HTTP et HTTPS étant
  désormais deux ports indépendants) ;
- l'overlay IP du player (voir plus bas) affiche maintenant les deux ports
  (`WEB 8080/8443`) plutôt qu'un seul, puisque le player n'a aucun moyen de
  savoir lequel des deux est actif à cet instant ;
- **mise à jour logicielle** : `install.sh` est réinvoqué avec `--port` ET
  `--https-port` repris de la configuration en cours (pas seulement
  `--port` comme avant) — sans ça, un port HTTPS personnalisé aurait été
  silencieusement réinitialisé à 8443 par défaut à chaque mise à jour,
  exactement le genre de piège qui a été signalé pour l'adresse IP fixe
  (voir juste en dessous).

**Testé** : la partie Python (le plus gros du changement — double serveur,
bascule HTTP/HTTPS indépendante, garde-fous, rechargement du certificat
quel que soit le port d'où arrive la requête) a été testée pour de vrai
dans ce bac à sable — un vrai `config-web.py` lancé avec les deux ports,
requêtes HTTP et HTTPS en parallèle, activation/désactivation croisée des
deux protocoles dans tous les ordres, y compris les cas qui doivent être
refusés (désactiver le dernier protocole restant). Un bug a d'ailleurs été
trouvé et corrigé par ce test (le port HTTP affiché était parfois confondu
avec le port HTTPS selon par où arrivait la requête). Ce qui n'a **pas** pu
être testé ici : le redémarrage réel des services via systemd (le binaire
`systemd-run` est présent dans ce bac à sable mais n'y pilote pas de vrais
services — seul le comportement autour, avant/après l'appel, a pu être
vérifié), et bien sûr tout le rendu de l'onglet Sécurité dans un vrai
navigateur. Premier test réel recommandé avec un seul appareil sous la main
au départ, pas en plein remplacement d'écrans, au cas où.

**Confirmé fonctionnel sur le Pi** — bascule HTTP/HTTPS testée depuis
l'onglet Sécurité ("c'est bien").

### Changer les numéros de port sans réinstaller (demande explicite)

Jusqu'ici, changer le port HTTP ou HTTPS voulait dire relancer
`install.sh` (qui recompile aussi le moteur vidéo — bien plus que
nécessaire pour un simple numéro de port). Nouveau panneau **Ports de
l'administration Web** dans l'onglet Sécurité, à côté des panneaux
HTTP/HTTPS : deux champs pré-remplis avec les ports actuels, un bouton
Appliquer.

- côté serveur (`system_admin.start_port_change`), édite directement les
  deux unités systemd déjà installées plutôt que de les regénérer depuis
  leurs gabarits `.in` (les autres valeurs — utilisateur, groupe, uid...
  — ne sont conservées nulle part après l'installation pour être
  réutilisées ici ; les re-dériver dupliquerait la logique de détection
  d'`install.sh` pour un gain nul puisque seuls les deux ports changent) :
  le `--port`/`--https-port` de l'`ExecStart` de `pidecoder-config.service`,
  et les variables d'environnement `PIDECODER_WEB_PORT`/
  `PIDECODER_WEB_HTTPS_PORT` de `pidecoder.service` (celles que l'overlay
  IP du player affiche, voir `NetworkInfo.cpp`) ;
- **par choix explicite** : `pidecoder.service` (le moteur vidéo) est aussi
  redémarré, pas seulement `pidecoder-config.service` — coupure de
  quelques secondes de l'affichage vidéo à chaque changement de port, pour
  que l'overlay du player reflète le nouveau port tout de suite plutôt que
  d'attendre son prochain redémarrage naturel ;
- contrairement au changement d'IP/nom d'hôte, **pas de filet de
  rattrapage à 120s** : un mauvais numéro de port ne coupe jamais l'accès
  réseau au Pi (l'accès SSH reste disponible, ou on relance `install.sh`
  avec les bons `--port`/`--https-port`) — le risque est nettement
  moindre, la confirmation différée n'apportait donc rien ici ;
- validation : ports entre 1 et 65535, HTTP et HTTPS obligatoirement
  différents (vérifié côté serveur, pas seulement dans le formulaire).

**Testé** : la substitution qui édite les fichiers d'unité a été vérifiée
de bout en bout dans ce bac à sable — de vraies unités générées par
`install.sh` (mêmes gabarits que sur le Pi), la même édition que celle
lancée par `start_port_change` appliquée dessus, résultat comparé ligne à
ligne (`--port`/`--https-port` et les deux variables d'environnement
correctement changés, rien d'autre touché). Le point de terminaison
`/api/tls/set-ports` a aussi été testé en conditions réelles (serveur
lancé, ports invalides/identiques refusés avec le bon message, ports
valides acceptés, serveur toujours réactif ensuite). Comme pour le reste
de cette section, le redémarrage réel des deux services via systemd n'a
pas pu être vérifié ici — à confirmer sur le Pi.

### Rappel : la « perte » de l'IP fixe après une mise à jour n'est pas liée à la mise à jour

Un utilisateur a signalé qu'après avoir mis à jour PiDecoder, l'IP fixe
configurée semblait être repassée en DHCP. Relecture complète du code de
mise à jour (`git pull` + `install.sh`, voir `system_admin.start_update`) :
**aucune de ces deux étapes ne touche à la configuration réseau** — la
seule chose dans PiDecoder qui repasse une IP fixe en DHCP, c'est le filet
de sécurité du changement d'IP lui-même (annulation automatique si `/api/
network/confirm` n'est pas appelé dans les ~120s, voir "Corrections après
troisième/quatrième retour terrain" plus bas), pas la mise à jour. Le
timing a probablement coïncidé : le changement d'IP n'avait pas été
confirmé (popup manqué), puis la mise à jour est arrivée après coup — sans
lien de cause à effet entre les deux.

Les trois correctifs déjà livrés plus bas dans cette section (popup
vérifié dès la connexion au lieu d'attendre un clic sur l'onglet, plus de
minuteur visible qui expire trop vite, correction de la course qui faisait
réapparaître le popup juste après confirmation) devraient déjà avoir réglé
ce qui causait un changement d'IP manqué. À reconfirmer lors du prochain
changement d'IP fixe : bien surveiller le popup de confirmation et cliquer
Confirmer.

### Affichage de l'IP sur l'écran du player au démarrage

Demande explicite de l'utilisateur : pouvoir retrouver l'adresse du Pi sur
le réseau directement depuis l'écran du mur vidéo, sans clavier/écran de
diagnostic ni accès SSH préalable — utile en particulier après un
changement d'IP/DHCP fait depuis la page Web (voir ci-dessus).

- petit bandeau discret en bas à droite de l'écran (mosaïque ou vue
  Focus), affichant l'adresse IPv4 locale, le nom d'hôte et le port de
  l'interface Web d'administration (ex. `IP 192.168.1.50  HOTE
  PIDECODER-PI  WEB :8080`) ;
- affiché automatiquement 30 secondes au lancement du player, et
  rappelable à tout moment avec la touche **I** ;
- nouveau fichier `src/NetworkInfo.cpp` : détection de l'adresse IPv4
  locale via `getifaddrs()` (première interface active, hors boucle
  locale et hors plage link-local 169.254.0.0/16) et du nom d'hôte via
  `gethostname()` — aucune nouvelle dépendance, uniquement des appels
  POSIX standard ;
- le port de l'admin Web est communiqué au binaire vidéo via une nouvelle
  variable d'environnement `PIDECODER_WEB_PORT`, injectée par
  `systemd/pidecoder.service.in` (le binaire vidéo et l'admin Web sont
  deux processus séparés, voir docs/PROJECT-STATE.md) ;
- rendu par la police bitmap déjà utilisée pour les overlays PTZ/son
  (`Renderer::draw_text`, majuscules uniquement) — le nom d'hôte est donc
  affiché en majuscules ;
- **non testé sur le matériel réel** : validé uniquement par relecture
  soigneuse et par une compilation+exécution isolée de
  `NetworkInfo.cpp` (le seul fichier de ce lot sans dépendance
  SDL2/mpv) — l'environnement de développement ne peut pas installer les
  bibliothèques de développement SDL2/mpv (accès réseau apt bloqué), donc
  le reste (intégration dans `Renderer`/`Application`, rendu à l'écran,
  raccourci clavier) n'a pas pu être compilé ici, comme pour les
  précédentes fonctionnalités touchant à l'affichage. À vérifier en
  premier lieu sur le Pi : que `sudo ./scripts/install.sh` compile bien
  sans erreur.

### Corrections sur l'overlay IP du player : bug d'affichage + adresse MAC

Retour terrain : l'overlay IP/nom d'hôte/port Web ne s'affichait jamais à
l'écran, ni au démarrage ni via la touche **I**. Cause trouvée à la
relecture : `startup_info_text_` (le texte de l'overlay) n'était calculé
**qu'une seule fois**, dans le constructeur d'`Application` — c'est-à-dire
avant même l'initialisation de SDL, et donc potentiellement avant que le
réseau du Pi ne soit complètement prêt (l'unité systemd attend bien
`network-online.target`, mais ce n'est pas une garantie absolue selon que
`NetworkManager-wait-online.service` est actif ou non). Si `getifaddrs()`
ne trouvait aucune interface active à ce moment précis, le texte restait
vide **pour le reste de l'exécution** — y compris pour la touche I, qui ne
faisait que relire ce même texte figé au lieu de le recalculer. Corrigé :
`show_startup_info_overlay()` recalcule désormais l'IP/le nom d'hôte à
chaque appel (démarrage *et* touche I) plutôt que de se fier à une valeur
capturée une fois pour toutes — ce qui, en prime, permet à la touche I de
refléter un changement d'IP fait depuis la page Web sans redémarrer le
player.

Par la même occasion, ajout demandé de l'**adresse MAC** dans l'overlay
(utile pour une réservation DHCP, par exemple) : `NetworkInfo.cpp` va
désormais chercher, via `getifaddrs()`, l'entrée `AF_PACKET` de la *même*
interface que celle qui porte l'adresse IPv4 affichée (pas une adresse
MAC au hasard si plusieurs interfaces existent) — ex. `IP 192.168.1.50
MAC AA:BB:CC:DD:EE:FF HOTE PIDECODER-PI WEB :8080`.

**Testé** : `NetworkInfo.cpp` (aucune dépendance SDL2/mpv) compile et
s'exécute correctement ici, adresse MAC comprise. Le reste
(`Application.cpp`/`Application.hpp`, non modifiés cette fois côté
rendu — seul le moment du calcul du texte a changé) n'a toujours pas pu
être compilé dans cet environnement (SDL2/mpv indisponibles) : à vérifier
en premier sur le Pi via `sudo ./scripts/install.sh`, en particulier que
l'overlay apparaît bien cette fois-ci au démarrage et via la touche I.

### Toujours rien à l'écran malgré le correctif ci-dessus — ajout d'un diagnostic

Retour terrain (confirmé après recompilation propre, et alors que les
autres éléments à l'écran — zoom, PTZ, bouton son en vue Focus — s'affichent
normalement) : l'overlay IP/MAC reste invisible, aussi bien au démarrage
qu'avec la touche I. Comme le reste de l'affichage fonctionne (même
`fill_ui_rect`/`draw_text` que les overlays qui marchent), la piste la
plus probable est que `startup_network_info_text()` renvoie une chaîne
vide sur ce Pi précis — c'est-à-dire que `NetworkInfo.cpp` ne trouve
aucune interface réseau correspondant à ses critères (active, hors
boucle locale, hors plage lien-local) sur ce matériel, pour une raison
qui reste à identifier sans accès direct au Pi depuis cet environnement.
Ajout d'une trace de diagnostic (`Application::show_startup_info_overlay()`
affiche désormais le texte calculé, ou `[]` s'il est vide, dans le journal
du service — visible via `journalctl -u pidecoder`, aucun outil
supplémentaire nécessaire) pour trancher sans deviner à l'aveugle.

### Le texte n'est pas vide — diagnostic étendu côté rendu

Un test autonome de `NetworkInfo.cpp` compilé et exécuté directement sur
le Pi réel confirme que `startup_network_info_text()` renvoie bien un
texte correct et non vide (`IP ... MAC ... HOTE ... WEB :8080`) — la
détection réseau elle-même n'est donc pas en cause, contrairement à
l'hypothèse de l'entrée précédente. Le problème est forcément plus loin,
côté dessin (`Renderer::draw_startup_info_overlay` ou le choix entre
`render()`/`render_focus()` selon la vue mosaïque/Focus). Relu en détail
sans rien trouver d'évident par la seule lecture du code (position,
taille de boîte, ordre de dessin — tout paraît cohérent avec les autres
overlays qui, eux, s'affichent bien). Ajout d'une seconde trace, cette
fois dans `Renderer::draw_startup_info_overlay` (log une seule fois par
activation, pas à chaque frame) : dimensions du canvas et géométrie
exacte de la boîte calculée, pour voir directement si le souci vient
d'un canvas inattendu, d'une boîte hors écran ou de taille nulle, plutôt
que de continuer à deviner sans preuve.

### Trouvé : `RestrictAddressFamilies` du service bloquait `getifaddrs()`

Cause réelle, confirmée par le journal (`[]` à chaque appel, alors que le
même `NetworkInfo.cpp` compilé et exécuté hors du service fonctionnait
parfaitement sur ce même Pi) : sous Linux, `getifaddrs()` interroge le
noyau via une socket `AF_NETLINK`/`NETLINK_ROUTE` pour énumérer les
interfaces réseau. `pidecoder.service.in` restreint les familles
d'adresses autorisées à `AF_UNIX AF_INET AF_INET6` — sans `AF_NETLINK`,
cette socket échoue silencieusement, `getifaddrs()` renvoie -1, et
`startup_network_info_text()` renvoie donc systématiquement une chaîne
vide, sans rien faire planter par ailleurs (d'où un service par ailleurs
parfaitement fonctionnel). Exactement la même famille de bug que le
`runuser` bloqué par `SystemCallFilter` pour la mise à jour : une
restriction systemd légitime, écrite avant l'existence de cette
fonctionnalité, qui ne l'autorisait pas explicitement. Corrigé en
ajoutant `AF_NETLINK` à `RestrictAddressFamilies` dans
`systemd/pidecoder.service.in`.

**Confirmé fonctionnel sur le Pi.** Les deux traces de diagnostic
ajoutées dans les deux entrées précédentes ont donc été retirées
(`Application.cpp` et `Renderer.cpp`).

### Présentation de l'overlay retravaillée (demande explicite)

Maintenant que ça s'affiche, un peu de mise en forme : l'encart passe
d'une seule ligne dense à un petit cadre à deux lignes avec une bordure
colorée (même teinte d'accent que le bouton son actif en vue Focus, pour
rester cohérent avec le reste de l'interface) et un fin séparateur entre
les deux lignes.

- ligne 1 : adresse IP + nom d'hôte (l'essentiel pour retrouver le Pi) ;
- ligne 2 : adresse MAC + port Web (informations plus techniques) ;
- `NetworkInfo.cpp` renvoie désormais ces deux lignes séparées par `\n`
  (`Renderer::draw_startup_info_overlay` coupe dessus avant de dessiner,
  `draw_text()` lui-même ne les interprète pas) ;
- toujours dessiné avec les mêmes primitives que le reste de l'UI
  (rectangles pleins uniquement, pas de vraie transparence ni de coins
  arrondis possibles avec `fill_ui_rect`/`draw_text`, voir leurs
  commentaires) — la bordure colorée est en fait un rectangle plein sous
  un rectangle intérieur plus sombre, pas un vrai contour.

**Testé** : géométrie de la boîte (position, largeur, hauteur) vérifiée
par calcul pour plusieurs résolutions courantes (640×480 à 4K) avec le
texte réel remonté par l'utilisateur — toujours à l'écran, jamais de
taille nulle ni négative. Le rendu à l'écran lui-même n'a pas pu être
vérifié dans cet environnement (toujours pas de SDL2/mpv disponibles
ici) : à confirmer visuellement sur le Pi.

### Retour terrain : cadre trop petit — police agrandie

Après vérification sur le Pi, le nouveau cadre à deux lignes était
lisible mais nettement trop petit. Cause : le seuil qui fait passer la
police bitmap en « gros caractères » (`scale = 2`) dans `draw_text()`
est `hauteur de ligne >= 32px` ; la hauteur de ligne calculée pour le
cadre était bornée entre 20 et 30px, donc ce seuil n'était jamais
atteint et le cadre restait toujours en petits caractères — contrairement
à l'ancien encart à une seule ligne, qui pouvait dépasser ce seuil sur
les écrans 720p et plus.

- hauteur de ligne : bornée désormais entre 34 et 46px (au lieu de
  20–30) — toujours calculée à partir de la plus petite dimension de
  l'écran, donc toujours proportionnée, mais avec un plancher qui
  garantit d'atteindre `scale = 2` (gros caractères) sur tous les
  écrans réalistes ;
- bordure, séparateur et marges ajustés en proportion (légèrement plus
  épais/plus larges) pour rester cohérents avec le cadre agrandi.

**Testé** : géométrie recalculée par le même script Python que pour la
version précédente, sur les mêmes résolutions (640×480, 1280×720,
1920×1080, 3840×2160) avec le texte réel de l'utilisateur — cadre
toujours entièrement à l'écran, `scale = 2` atteint dans tous les cas
(gros caractères garantis). Rendu visuel réel à reconfirmer sur le Pi.

### Corrections après premier retour terrain

- **« Update unavailable: this folder is not a Git repository »** alors que
  le dépôt est bien un clone Git valide : `check_update()` ne testait que
  la présence d'un dossier `.git` (`(repo / '.git').is_dir()`), qui ne
  couvre pas tous les clones Git valides (worktree, sous-module,
  `--separate-git-dir`, où `.git` est un *fichier* pointant ailleurs).
  Remplacé par un test via `git rev-parse --is-inside-work-tree`, fiable
  dans tous les cas, et qui remonte désormais un message d'erreur détaillé
  côté page Web si le problème est ailleurs (permissions, chemin
  introuvable...) plutôt qu'un « pas un dépôt Git » générique ;
- **expérience du compte à rebours réseau retravaillée** : remplacée par
  un plein écran (même cadre visuel que le redémarrage HTTPS) avec un
  compte à rebours qui défile localement seconde par seconde au lieu de
  se rafraîchir tous les quelques secondes depuis le serveur — l'ancien
  rendu donnait une impression saccadée ;
- **lien direct vers la nouvelle adresse** : quand un changement d'IP fixe
  est en cours, le plein écran propose désormais un lien cliquable vers
  la nouvelle adresse (et, pour un changement de nom d'hôte, vers
  `<nom>.local`), pour éviter de la retaper à la main ;
- le fichier de statut d'un changement d'IP en cours n'incluait pas
  l'ancienne/nouvelle valeur une fois appliqué (seulement au moment de la
  demande initiale) — corrigé, nécessaire pour afficher ce lien.

### Corrections après second retour terrain (test réel sur le Pi)

Les deux correctifs ci-dessus n'étaient pas suffisants une fois testés sur
le vrai matériel — le message d'erreur plus détaillé introduit par le
premier correctif a justement permis de voir le vrai problème.

- **« Update unavailable » persistant, cause réelle trouvée** : le message
  d'erreur remonté sur le Pi réel était en fait
  `runuser: cannot set user id: Operation not permitted`. Cause : contrairement
  à toutes les autres opérations privilégiées de ce module (mise à jour,
  changement de nom d'hôte/IP, NTP...), `check_update()` appelait
  `runuser`/`git` **directement dans le process de
  `pidecoder-config.service`**, qui tourne sous un bac à sable systemd
  strict (`SystemCallFilter=@system-service`). Ce filtre bloque les appels
  système de changement d'UID (`setuid`/`setresuid`...) dont `runuser` a
  besoin — d'où l'échec, alors même que le service tourne en root.
  `check_update()` délègue désormais chacun de ses appels `git` à
  `run_sync_unsandboxed()` (unité `systemd-run` indépendante, hors bac à
  sable), exactement comme c'était déjà fait pour NTP et le fuseau
  horaire. Vérifié avec un faux `runuser`/`systemd-run`/dépôt Git local
  (dépôt à jour, en retard, sans upstream, invalide) ;
- **le plein écran de confirmation réseau restait affiché jusqu'à
  expiration du délai, même après reconnexion sur la nouvelle IP** :
  deux causes cumulées. D'abord, `/api/network/status` (et donc le plein
  écran) n'était consulté que si l'utilisateur pensait à recliquer
  manuellement sur l'onglet Réseau une fois reconnecté sur la nouvelle
  adresse — la page ne vérifiait jamais spontanément s'il y avait un
  changement en attente juste après la connexion. Ensuite, le délai de 45
  secondes avant rétablissement automatique était trop court une fois
  compté le temps réel de cliquer le lien, recharger la page sur la
  nouvelle origine et s'authentifier à nouveau (nouvelle IP = nouvelle
  origine = cookie de session à refaire). Corrections : la page vérifie
  désormais s'il y a un changement réseau en attente dès la connexion
  (avant même d'ouvrir l'onglet Réseau) et affiche immédiatement le plein
  écran avec le temps restant réel ; le délai avant rétablissement
  automatique est passé de 45 à 120 secondes ; le lien vers la nouvelle
  adresse précise maintenant qu'une reconnexion sera nécessaire.

### Corrections après troisième retour terrain : suppression du compte à rebours affiché

Même après les correctifs ci-dessus, le popup de confirmation réseau
continuait à afficher un compte à rebours en secondes une fois reconnecté
sur la nouvelle adresse — alors qu'en pratique, le changement (`nmcli`)
est appliqué quasi instantanément, donc ce timer qui défilait n'apportait
rien et laissait penser à tort qu'il fallait attendre. Le plein écran
n'affiche désormais plus aucun nombre qui défile : juste un message fixe
et le bouton « Confirmer ce changement » à cliquer, sur une page qui
répond déjà. Le filet de sécurité (rétablissement automatique de l'ancien
réglage si la confirmation n'arrive jamais, toujours à 120 secondes) reste
actif en arrière-plan exactement comme avant — un seul minuteur silencieux
programmé sur l'échéance réelle a remplacé la boucle d'affichage seconde
par seconde ; rien n'a changé côté sécurité, seul l'affichage a été
simplifié.

### Corrections après quatrième retour terrain : le popup réapparaissait juste après avoir cliqué Confirmer

Cause trouvée : une course entre la confirmation et le script détaché qui
gère le rétablissement automatique. Cliquer sur « Confirmer » touchait
uniquement un fichier sentinelle ; c'est la boucle du script détaché,
côté serveur, qui remarque ce fichier et fait passer le statut d'
« applied » à « confirmed » — mais cette boucle ne vérifie qu'une fois par
seconde. Le navigateur, lui, rafraîchit `/api/network/status` tout de
suite après la confirmation : pendant cette fenêtre pouvant aller jusqu'à
une seconde, le statut était donc encore « applied », et le popup qu'on
venait juste de fermer réapparaissait aussitôt. `confirm_change()` met
désormais à jour le fichier de statut immédiatement (en plus du fichier
sentinelle, toujours nécessaire pour que le script détaché s'arrête sans
tout annuler), ce qui supprime complètement la fenêtre de course. Vérifié
de bout en bout avec un vrai changement d'IP simulé (délai raccourci pour
le test uniquement, jamais en production) : confirmation immédiatement
prise en compte, pas de retour du popup.

### Mise à jour en un clic et configuration réseau depuis la page Web

Demande explicite de l'utilisateur : un bouton de vérification/installation
des mises à jour, et un panneau complet de configuration réseau (nom
d'hôte, IP DHCP/manuelle, NTP, fuseau horaire), avec un filet de sécurité
automatique pour ne jamais perdre l'accès au Pi à cause d'une erreur de
frappe sur l'adresse IP.

- nouvel onglet **Réseau** dans la page Web : nom d'hôte, adresse IP
  (DHCP ou manuelle par connexion NetworkManager), synchronisation de
  l'heure (NTP) et fuseau horaire ;
- nouveau panneau **Mise à jour** dans l'onglet Système : vérifie l'état
  du dépôt Git par rapport à sa branche distante et affiche un bouton de
  mise à jour si une nouvelle version est disponible ;
- **sécurité — rétablissement automatique** : un changement de nom
  d'hôte ou d'adresse IP est appliqué immédiatement mais annulé
  automatiquement s'il n'est pas confirmé depuis la page Web dans les 45
  secondes qui suivent. Ce mécanisme est entièrement côté serveur (une
  minuterie détachée qui surveille un fichier de confirmation), donc il
  fonctionne même si le changement rend la page inaccessible — c'est
  justement le cas qu'il doit couvrir ;
- **architecture** : `pidecoder-config.service` tourne avec un bac à
  sable systemd strict (`ProtectSystem=strict`, `ProtectHostname=true`,
  etc.) qui interdit d'écrire directement dans `/etc/hostname`,
  `/etc/hosts`, `/etc/systemd/timesyncd.conf` ou d'appeler `nmcli`
  directement depuis son propre processus. Comme pour la bascule
  HTTPS on/off (v1.2), tout changement système passe par une unité
  `systemd-run` transitoire indépendante — qui n'hérite pas du bac à
  sable de l'unité appelante — dans un nouveau module
  `scripts/system_admin.py` ;
- `git fetch`/`git pull` (vérification et mise à jour) sont lancés via
  `runuser -u <utilisateur du service vidéo> --` pour ne jamais laisser
  de fichiers appartenant à `root` dans le dépôt Git de l'utilisateur, ce
  qui casserait ensuite les commandes Git lancées à la main en SSH ;
- la mise à jour s'appuie sur le mécanisme de restauration déjà présent
  dans `scripts/install.sh` (restauration automatique de la version
  précédente en cas d'échec) plutôt que de le dupliquer ;
- toutes les entrées (nom d'hôte, adresse IP/passerelle/DNS en CIDR,
  serveurs NTP, fuseau horaire, nom de connexion réseau) sont validées
  côté serveur avant d'être utilisées dans une commande système exécutée
  en root ;
- nouvelle variable de template `@REPO_PATH@` dans
  `systemd/pidecoder-config.service.in` et `scripts/install.sh`, pour que
  le service connaisse l'emplacement du clone Git. **Important : ce
  changement nécessite un `sudo ./scripts/install.sh` complet sur le Pi
  pour prendre effet — `sync-dev.sh` ne touche jamais aux fichiers
  systemd et ne suffit pas cette fois-ci, même en l'absence de
  changement C++.**

**Tests effectués.** Avant tout retour terrain, ce lot a été testé de bout
en bout dans un bac à sable avec des exécutables factices (`nmcli`,
`hostnamectl`, `timedatectl`, `systemd-run`, `runuser`, `systemctl`) et de
vrais dépôts Git locaux : cycle complet nom d'hôte/IP (appliqué →
confirmé, et appliqué → annulé automatiquement faute de confirmation),
rejets de validation (connexion inconnue, IP sans masque, serveur NTP
invalide, fuseau horaire invalide), et mise à jour complète (vérification,
git pull + install.sh réussis, et le cas d'échec d'install.sh).

**Depuis, testé pour de vrai sur le Pi et confirmé** pour l'essentiel du
lot : le changement d'IP manuelle (avec son filet de sécurité et son
popup de confirmation, voir les quatre rounds de correctifs juste
au-dessus) et la mise à jour en un clic ont chacun été éprouvés sur le
matériel réel, avec plusieurs bugs trouvés et corrigés en cours de route ;
l'utilisateur a également confirmé qu'une IP manuelle survit désormais à
une mise à jour (« il a bien garder l'ip manuel après update »). Ce qui
n'a en revanche **pas fait l'objet d'un retour terrain explicite** :
la configuration NTP et le changement de fuseau horaire spécifiquement
(le mécanisme sous-jacent est le même que pour le nom d'hôte/IP, déjà
validé, mais ces deux réglages précis n'ont pas été testés séparément par
l'utilisateur) — à essayer en priorité une fois en production, sans risque
de perte d'accès contrairement au changement d'IP.

### HTTPS pour l'interface d'administration (étape 1/2, confirmé sur le Pi)

Premier volet du chantier HTTPS de bout en bout : la page Web
d'administration. Le chiffrement du flux RTSP entre le Pi et les caméras
(RTSPS) est traité séparément dans une étape 2, car il dépend du support de
chaque caméra et n'a pas de rapport avec le protocole HTTP.

- `scripts/config-web.py` sert désormais en HTTPS par défaut : le socket du
  serveur (`ThreadingHTTPServer`) est enveloppé dans un `ssl.SSLContext`
  (TLS 1.2 minimum) dès qu'un certificat et une clé sont trouvés sous
  `<root>/config/tls/{cert.pem,key.pem}` (chemins surchargeables avec
  `--tls-cert`/`--tls-key`). En l'absence de certificat valide — installation
  très ancienne, fichier corrompu — le service journalise un avertissement
  clair et bascule en HTTP simple plutôt que de planter, pour ne jamais
  bloquer l'accès à l'administration ;
- nouveau drapeau `--no-https` (`config-web.py`) pour forcer explicitement
  le HTTP ;
- le cookie de session (`pidecoder_session`) et le cookie de langue
  (`pidecoder_lang`) reçoivent l'attribut `Secure` uniquement quand la
  connexion est effectivement chiffrée — un cookie `Secure` envoyé en HTTP
  simple serait silencieusement ignoré par le navigateur et casserait la
  session ;
- `scripts/install.sh` génère un certificat auto-signé au premier
  déploiement (`openssl req -x509`, clé RSA 2048, 10 ans de validité),
  avec le nom d'hôte du Pi et ses adresses IPv4 locales en Subject
  Alternative Name, pour que le navigateur accepte l'IP utilisée pour se
  connecter une fois l'avertissement initial validé manuellement. Un
  certificat existant est conservé tel quel lors d'une mise à jour (même
  logique de préservation que `cameras.json`/`layout.json`/
  `web-auth.json`) ;
- nouvelles options `--tls-cert`/`--tls-key` pour importer son propre
  certificat au lieu de celui auto-signé (ex. une CA interne déjà
  approuvée sur les postes du réseau) ; l'installeur vérifie que le
  certificat est un PEM valide et que la clé correspond bien au certificat
  (comparaison par clé publique, compatible RSA et EC) avant de les
  installer, pour éviter un déploiement avec une paire invalide ;
- nouvelle option `--no-https` (`install.sh`) pour installer sans aucun
  certificat, dès le premier déploiement : le service démarre directement
  en HTTP simple. Incompatible avec `--tls-cert`/`--tls-key` ; sur une
  mise à jour, un certificat précédemment installé n'est délibérément pas
  repris (il reste dans la sauvegarde automatique de l'installeur si besoin
  de revenir en arrière) ;
- permissions alignées sur celles de `web-auth.json` : `config/tls/`
  en 0750, `key.pem` en 0600, `cert.pem` en 0644, propriétaire
  `root:root` (le service `pidecoder-config` tourne déjà en root) ;
- **nouveau** `scripts/manage-tls.sh` : bascule HTTPS/HTTP ou change de
  certificat après coup, sans repasser par l'installeur complet (qui
  recompile le moteur natif et coupe tous les services). Sous-commandes
  `status` (état courant, sujet/expiration/SAN du certificat actif),
  `generate [--force]` (nouveau certificat auto-signé, mêmes réglages que
  l'installeur), `import --cert PATH --key PATH` (certificat personnalisé,
  avec la même vérification de correspondance certificat/clé que
  l'installeur), `disable` (met le certificat actif de côté —
  `cert.pem.disabled`/`key.pem.disabled` — et repasse en HTTP, sans rien
  supprimer) et `enable` (restaure le certificat mis de côté, ou en génère
  un nouveau s'il n'y en a aucun). Redémarre automatiquement
  `pidecoder-config.service` à la fin de chaque changement ;
- validé en local (génération de certificat, bascule HTTP↔HTTPS, cookie
  `Secure` présent/absent selon le mode, dégradation propre sur un
  certificat corrompu, et chaque sous-commande de `manage-tls.sh` —
  `generate`/`import`/`disable`/`enable`/`status`, y compris le rejet
  d'une paire certificat/clé non correspondante) mais **pas encore testé
  sur le Raspberry Pi réel** — reste à valider : avertissement du
  navigateur au premier accès, login, PTZ et audio par-dessus HTTPS, mise
  à jour d'une installation existante en conservant le certificat, et
  `manage-tls.sh` contre le vrai `pidecoder-config.service`.

### Gestion du certificat et bascule HTTPS/HTTP directement dans la Web UI

Confirmé sur le Pi : la partie précédente (HTTPS + `manage-tls.sh` en SSH)
fonctionne. Suite logique demandée : plutôt que de passer par SSH pour
chaque changement, un nouveau panneau « Certificat HTTPS » dans l'onglet
Sécurité de l'interface Web permet de tout faire sans quitter le
navigateur.

- nouveaux points d'API sur `config-web.py` : `GET /api/tls/status`
  (sujet, expiration, SAN du certificat actif, présence d'un certificat mis
  de côté) et `POST /api/tls/generate`, `/api/tls/import`, `/api/tls/enable`,
  `/api/tls/disable`. Chacun délègue le travail de fichiers à
  `scripts/manage-tls.sh` (nouveau drapeau `--no-restart`, pour laisser
  `config-web.py` décider seul du moment du redémarrage) ;
- **génération et import de certificat sans coupure** : `generate` et
  `import` rechargent le certificat à chaud sur le processus déjà actif via
  un second appel à `ssl.SSLContext.load_cert_chain()` sur le contexte TLS
  en cours d'utilisation — les connexions en cours ne sont pas coupées, et
  aucun redémarrage n'est nécessaire. Testé de bout en bout en local
  (génération puis import, statut mis à jour immédiatement, session
  toujours active après coup) ;
- **import bloqué tant que la connexion n'est pas déjà en HTTPS** : envoyer
  une clé privée en clair sur un réseau local reste un risque inutile,
  donc `POST /api/tls/import` refuse la requête si la connexion active
  n'est pas déjà chiffrée, avec un message renvoyant vers l'activation de
  HTTPS ou vers `manage-tls.sh` en SSH ;
- **bascule HTTPS on/off complète, aussi depuis la Web UI** : contrairement
  au changement de certificat, activer/désactiver HTTPS change l'origine
  du navigateur (`http://` et `https://` sur le même hôte:port sont deux
  origines distinctes — cookies et session ne survivent pas au
  changement), donc `enable`/`disable` redémarrent réellement le service.
  Un processus ne peut pas se redemander son propre redémarrage
  `systemctl` de façon synchrone (systemd le tue avant/pendant la
  transaction), et un simple `subprocess.Popen` différé serait lui aussi
  tué (même cgroup). Solution retenue : `systemd-run --collect
  --on-active=2 systemctl restart pidecoder-config.service`, qui crée une
  unité transitoire indépendante hors du cgroup du service appelant,
  survit à son arrêt, et déclenche le redémarrage 2 secondes plus tard —
  le temps que la réponse JSON atteigne le navigateur. La réponse indique
  `redirect_url` (nouveau schéma déjà calculé) pour que le frontend
  redirige au bon moment ;
- **aucune boîte de dialogue de confirmation native** (`window.confirm`) —
  cohérent avec le reste de l'interface : un texte d'avertissement clair
  avant le bouton on/off, plus le retour visuel habituel (toast) ;
- traductions FR/EN complètes (22 nouvelles clés `sec.tls_*` côté
  frontend, 7 nouvelles clés `tls.*` côté backend), parité FR/EN vérifiée ;
- validé en local : `GET /api/tls/status`, `POST /api/tls/generate`,
  `POST /api/tls/import` (y compris le rejet en HTTP simple) testés de
  bout en bout contre une instance réelle de `config-web.py` (connexion,
  authentification, appels API, vérification que le certificat change
  effectivement et que la session survit). `POST /api/tls/enable` et
  `/disable` validés pour la partie fichiers (`cert.pem` ↔
  `cert.pem.disabled`, redémarrage simulé confirmant la bascule HTTP↔HTTPS
  au redémarrage suivant, `redirect_url` correct dans les deux sens) —
  **le mécanisme `systemd-run` lui-même n'a pas pu être testé** (pas de
  systemd fonctionnel dans l'environnement de développement) et reste le
  point le plus risqué de cette étape : **à valider en priorité sur le Pi
  réel**, avec une session SSH ouverte en secours au cas où le
  redémarrage ne se déclencherait pas ou que le service ne redémarre pas
  correctement.

### Correctif (retour terrain) : login bloqué après un retour en HTTP

Trouvé par l'utilisateur en testant `--no-https` après avoir déjà utilisé
HTTPS dans le même navigateur : le login semblait accepté (mot de passe
validé, pas de message d'erreur) mais l'interface restait bloquée sur
l'écran de connexion. En cause : un cookie `Secure` posé lors d'une
session HTTPS précédente ne peut pas être remplacé par un cookie non
`Secure` émis depuis une connexion HTTP simple — le navigateur rejette
silencieusement la tentative (règle de sécurité standard, indépendante de
PiDecoder), laissant l'ancien cookie, invalide, bloquer toute nouvelle
session tant qu'il n'est pas supprimé manuellement.

- `POST /api/tls/disable` expire désormais explicitement les cookies
  `pidecoder_session` et `pidecoder_lang` (avec l'attribut `Secure`, donc
  acceptés par le navigateur) dans sa réponse, avant la bascule vers
  HTTP — c'est le dernier moment où le serveur répond encore en HTTPS,
  donc le seul où cette suppression est possible. `H.j()` accepte
  maintenant plusieurs cookies (liste) en plus d'un seul ;
- `scripts/manage-tls.sh disable` ne peut pas faire ce nettoyage (le
  service n'est plus en HTTPS au moment de désactiver) : affiche donc un
  avertissement explicite invitant à vider les cookies du site dans le
  navigateur si ça arrive. Même avertissement dans `install.sh` sur une
  mise à jour avec `--no-https` d'une installation qui avait un
  certificat actif ;
- validé en local : cycle complet login HTTPS → `/api/tls/disable` →
  vérification que les deux `Set-Cookie` d'expiration sont bien renvoyés
  et que le cookie jar les retire effectivement ;
- reste un point d'attention non corrigible par le code : si HTTPS tombe
  en HTTP de façon *non contrôlée* (ex. certificat corrompu détecté au
  démarrage, bascule automatique — voir étape 1 ci-dessus), il n'y a plus
  de réponse HTTPS disponible pour nettoyer le cookie côté navigateur.
  Seul le cas du bouton on/off de la Web UI et de `manage-tls.sh disable`
  (chemins contrôlés) sont couverts ; documenté comme limitation connue.

### Confort (retour terrain) : attente pendant le redémarrage HTTPS on/off

Deux remarques après un nouveau test sur le Pi : le message sur les
cookies aurait dû être visible avant même de cliquer, et la redirection
automatique (fixée à 2,5s) tombait souvent sur une page inaccessible —
`pidecoder-config.service` mettant plus longtemps que ça à redémarrer
complètement (arrêt de l'ancien processus, rechargement du certificat,
nouvelle écoute).

- le message d'avertissement au-dessus du bouton on/off (déjà visible
  avant de cliquer, affiché en continu pendant le redémarrage) mentionne
  maintenant explicitement le cas des cookies : « si la connexion semble
  acceptée sans rien afficher ensuite, vide les cookies de ce site » ;
- remplacement de la redirection fixe à 2,5s par un compte à rebours de
  30 secondes affiché en direct dans le panneau (« Redirection
  automatique dans Ns… »), avant de rediriger une seule fois à la fin —
  30s est large par rapport au temps de redémarrage observé, pour éviter
  d'atterrir sur une page d'erreur du navigateur pendant l'attente ;
- limitation assumée : une vérification active (sonder l'URL cible et
  rediriger dès qu'elle répond, plutôt qu'attendre 30s à l'aveugle) a été
  envisagée mais écartée — passer de HTTPS à HTTP déclencherait un blocage
  « contenu mixte » du navigateur (une page HTTPS ne peut pas interroger
  une URL HTTP en JavaScript), donc une vérification active ne
  fonctionnerait que dans un sens (HTTP→HTTPS) et pas dans l'autre
  (HTTPS→HTTP, le sens justement le plus délicat). Un délai fixe généreux,
  identique dans les deux sens, reste plus simple et plus prévisible ;
- validé : `node --check` sur `app.js`/`i18n.js`, parité des clés FR/EN
  (242 de chaque côté) ; **le comportement réel du compte à rebours et du
  redémarrage n'a pas pu être rejoué dans l'environnement de
  développement** (pas de service `pidecoder-config` ni de navigateur
  réel disponibles ici) — à confirmer sur le Pi.

### Confort (retour terrain, suite) : message plus visible + garde-fou navigateur

Deuxième retour après test du compte à rebours : le message dans le
panneau restait trop discret pour être vu à temps, et sur la
désactivation, la page a rechargé en HTTPS (pas HTTP) après ~2 secondes
seulement plutôt que d'attendre les 30 secondes prévues.

- nouvelle superposition plein écran (`#tlsRestartOverlay`) affichée
  pendant tout le compte à rebours : fond sombre semi-opaque, gros
  chiffre du décompte (64px), message et avertissement cookies inclus —
  impossible à manquer ou à fermer par erreur, contrairement au texte
  discret dans le panneau (conservé en parallèle) ;
- **cause probable du rechargement à 2s en HTTPS plutôt qu'en HTTP** :
  aucune piste ne pointe vers un bug côté PiDecoder — `tls_redirect_url()`
  reçoit le schéma explicitement (`'http'` côté `disable`, jamais
  recalculé) et le compte à rebours ne redirige qu'à la toute fin (30
  intervalles d'1s, pas 2s). Deux explications restent probables et sont
  hors du contrôle du code serveur : (1) `app.js` mis en cache par le
  navigateur — il a encore changé cette manche, un rechargement forcé
  (Ctrl+Maj+R) est nécessaire après chaque mise à jour de ce fichier ;
  (2) un réglage du navigateur du type « HTTPS-Only Mode » (présent
  nativement dans Firefox et Chrome récents) qui force silencieusement
  toute navigation `http://` vers `https://` pour un site déjà visité en
  HTTPS — dans ce cas la requête vers le nouveau serveur (qui n'écoute
  plus qu'en HTTP) échoue immédiatement, ce qui expliquerait un retour
  rapide à une page (d'erreur) en HTTPS. À vérifier sur le Pi : dans les
  préférences du navigateur, chercher un mode « HTTPS uniquement » et
  désactiver l'application automatique pour l'IP du Pi, ou ajouter une
  exception ;
- validé : `node --check`, parité FR/EN (244 clés de chaque côté),
  vérification qu'aucun `id` HTML n'est dupliqué. **Comme pour le point
  précédent, le comportement réel en conditions de restart n'a pas pu
  être rejoué ici** — à reconfirmer sur le Pi après un rechargement forcé
  du navigateur.

### Correction de procédure : `git pull` + redémarrage ne suffisait pas

Cause trouvée après que l'utilisateur ait signalé ne voir aucun changement
malgré plusieurs manches livrées d'affilée (superposition plein écran
invisible, désactivation toujours instantanée à ~2s, numéro de version
qui ne bouge jamais) : **la consigne donnée précédemment était fausse**.
`pidecoder-config.service` exécute les fichiers sous `/opt/pidecoder/`
(voir `ExecStart` dans `systemd/pidecoder-config.service.in`), une copie
physique distincte du clone Git (`~/PiDecoder`) — copie faite uniquement
par `install.sh` (`cp -a "$STAGED_ROOT" "$TARGET"`), jamais par `git
pull`. Redémarrer le service sans jamais relancer `install.sh` ne fait
donc que relancer le même fichier déjà en place : rien de nouveau n'est
jamais exécuté, quel que soit le nombre de fois où `git pull` est fait
dans `~/PiDecoder`.

- **`scripts/sync-dev.sh`** (nouveau, outil de développement uniquement —
  ne fait pas partie de l'installeur) : copie `scripts/` du clone Git vers
  `/opt/pidecoder/scripts/` (permissions alignées sur celles
  d'`install.sh` pour les scripts exécutables), puis redémarre
  `pidecoder-config.service`. Beaucoup plus rapide que l'installeur
  complet (qui recompile le moteur natif et coupe l'affichage vidéo) —
  pensé pour itérer sur des changements Python/JS/HTML/CSS en
  développement. Ne touche ni `config/` (caméras, disposition,
  identifiants Web, certificats TLS), ni le moteur natif, ni les unités
  systemd ;
- `VERSION` dans `config-web.py` passe de `'1.1.0'` à `'1.1.0-dev'` —
  réutilise un mécanisme déjà présent dans le code (`release_label`
  affiché en diagnostics : Stable/Development/RC/Beta/Alpha selon un
  suffixe `-dev`/`-rc`/`-beta`/`-alpha` dans `VERSION`) pour rendre visible,
  dans l'en-tête et la page de connexion, qu'une version de développement
  tourne — sert de vérification indépendante que la synchronisation a
  bien eu lieu, en plus de `sync-dev.sh` lui-même. Sans effet sur
  `CMakeLists.txt` (qui reste à `1.1.0`, requis par CMake pour le moteur
  natif) ni sur la validation CI, qui ne contrôle pas cette chaîne ;
- ajouté à `validate-release.sh` (vérification syntaxe shell et fichiers
  requis), comme chaque script livré ;
- **pour toutes les manches HTTPS précédentes de cette session** : il est
  possible qu'aucune n'ait jamais réellement tourné sur le Pi avant
  celle-ci, malgré les confirmations de test — à revalider entièrement
  une fois `sync-dev.sh` utilisé pour la première fois.

### Correctif : le certificat auto-signé semblait ne jamais se renouveler

Signalé une fois `sync-dev.sh` en place (donc en testant vraiment le
nouveau code cette fois) : cliquer sur « Générer un nouveau certificat »
plusieurs fois de suite affichait toujours le même certificat (mêmes
dates de validité) dans le visualiseur de certificat du navigateur.

Le serveur régénérait pourtant bien un nouveau certificat à chaque clic
(vérifié en local : la date d'expiration change à chaque appel de
`POST /api/tls/generate`, et le panneau « Certificat HTTPS » de
PiDecoder lui-même l'affiche correctement, immédiatement). En cause : la
**reprise de session TLS** (« session resumption », TLS 1.3 en
particulier, négocié par défaut avec un navigateur récent). Un navigateur
qui a déjà une session ouverte avec le serveur peut reprendre cette
session lors d'une nouvelle connexion — poignée de main abrégée — sans
jamais représenter de certificat ; le visualiseur de certificat du
navigateur continue alors d'afficher celui de la session d'origine tant
qu'une poignée de main *complète* ne se reproduit pas par hasard.

- `ssl.SSLContext.options |= ssl.OP_NO_TICKET` seul ne suffisait pas — ce
  drapeau ne couvre que le mécanisme de tickets « historique »
  (TLS ≤ 1.2). En TLS 1.3, c'est l'attribut `SSLContext.num_tickets`
  (Python ≥ 3.8) qui contrôle l'émission des tickets de session ; ajout de
  `ctx.num_tickets = 0` en plus de `OP_NO_TICKET`, pour couvrir les deux
  mécanismes et garantir qu'aucune connexion ne peut être reprise sans
  poignée de main complète — donc sans présenter le certificat réellement
  actif au moment de la connexion ;
- reproduit et confirmé en local avec `openssl s_client`
  (`-sess_out`/`-sess_in`) : avant le correctif, une session capturée
  avant une régénération de certificat pouvait être reprise ensuite
  (`Reused, TLSv1.3` dans la sortie d'`s_client`), présentant l'ancien
  certificat malgré `OP_NO_TICKET` seul ; après l'ajout de
  `num_tickets = 0`, plus aucun ticket n'est émis (le fichier de session
  `-sess_out` n'est même plus créé), et une connexion fraîche présente
  systématiquement le certificat tout juste régénéré ;
- léger compromis assumé : chaque nouvelle connexion HTTPS refait une
  poignée de main complète (légèrement plus coûteuse qu'une reprise de
  session) — sans impact perceptible pour une interface d'administration
  à faible trafic, et cohérent avec HTTP/1.0 déjà utilisé par
  `config-web.py` (chaque requête ouvre de toute façon une nouvelle
  connexion TCP, avec ou sans TLS) ;
- **remarque** : ce correctif rend aussi plus fiable la bascule
  HTTPS→HTTP→HTTPS et l'import de certificat — dans tous ces cas, une
  session TLS reprise aurait pu masquer un changement réel côté serveur
  de la même manière.

### À venir (étape 2/2) : RTSPS entre le Pi et les caméras

Abandonné pour le moment, à la demande explicite de l'utilisateur : un
début d'implémentation avait été fait (option par caméra dans le menu
avancé), mais après vérification de la documentation Axis
(`developer.axis.com`), il s'est avéré que RTSPS chez Axis écoute sur un
port séparé (322, pas 554) et ne chiffre de toute façon que la connexion
de contrôle RTSP, pas le flux vidéo/audio lui-même (ça, c'est SRTP, un
mécanisme différent et nettement plus complexe à implémenter avec
mpv/ffmpeg). Jugé pas indispensable et probablement jamais utilisé en
pratique — retiré du code avant toute mise en production. Pourra être
repris plus tard si besoin, en gardant à l'esprit cette distinction
RTSPS/SRTP et la spécificité du port 322 chez Axis.

## 1.1.0

Field-tested and validated on the Raspberry Pi with an Axis camera (RTSP
stream with an enabled microphone) — see `docs/faq.md` and
`docs/configuration.md` for the hardware-compatibility details, including
the known Aqara G410 exception below.

### Native audio support

- the native engine can now play audio in the Focus view (one enlarged
  camera at a time); the mosaic/grid view stays silent, since playing
  every visible tile's audio at once would be unusable;
- sound starts muted every time Focus opens, on any camera, unless the
  new "Micro actif par défaut en plein écran" layout toggle (see below)
  is enabled; press **M** or click the new audio button to unmute;
- the audio button is a small speaker icon, bottom-right of the Focus
  view (shifted left of the PTZ pad instead, on cameras that have
  one, so the two never overlap). It follows the same show/hide
  principle as the existing PTZ overlay: shown immediately when Focus
  opens, then reappears on any mouse movement and auto-hides after 5
  seconds of inactivity. Blue = unmuted, grey = muted (with a bar
  across the icon) or no audio track at all (dimmer, no bar);
- a camera whose RTSP stream has no audio track at all shows the
  dimmed speaker icon — pressing M or clicking does nothing audible
  in that case;
- audio output uses whatever device ALSA/mpv picks as the system
  default on the Pi; nothing is forced;
- no volume control (mute/unmute only) and no per-camera memory of the
  mute choice in this beta — see `docs/PROJECT-STATE.md` for the full
  list of deferred scope;
- native engine only; no Web UI or backend change, since this audio
  plays on the Pi's own local output, not through the browser;
- fixed a regression introduced by an earlier commit in this same
  beta: enabling audio decoding unconditionally as soon as Focus
  opened (silencing it only through mpv's `mute` property) caused a
  visible video lag/slow-motion effect, because Focus's `video-sync`
  setting paces the image against the audio clock, and a live RTSP
  audio stream's clock can be irregular. Audio decoding is now only
  turned on for as long as the user has actually asked for sound
  (pressed M or clicked the button); while muted — the default — no
  audio is decoded at all and video timing is exactly as it was
  before this feature existed;
- **new**: "has a microphone (audio)" checkbox per camera in the Web
  config, unchecked by default. It decides whether the Focus audio
  button is offered for that camera at all (no icon whatsoever if
  unchecked) — and it also fixes a real, separate bug: any camera
  whose RTSP stream carries an audio track (not just the ones this
  beta cares about) was breaking the mosaic/grid view with a frame
  lag that grew worse over time, reproduced with both an Axis camera
  (mic enabled) and an Aqara G410 intercom, and confirmed to happen
  even on `main`/v1.0.0 with none of this beta's code. Root cause:
  the mosaic's low-latency UDP settings don't tolerate a second
  audio RTP stream interleaved with the video one. Checking this box
  for a camera relaxes just enough of those settings for that
  camera's tile to fix it, while every other (unchecked) camera keeps
  the exact proven settings, unchanged;
- fixed the mosaic lag for the Axis camera with its mic on, confirmed
  on hardware. The Aqara G410 intercom still has some residual audio
  trouble even with the box checked — set aside for now, low priority,
  and does not affect video-only use of the G410;
- the "Audio" checkbox label was shortened (was "a un micro (audio)" /
  "has a microphone (audio)"), with the fuller explanation moved to
  its tooltip;
- new global toggle in the Web config's Disposition/Layout tab,
  "Micro actif par défaut en plein écran" / "Microphone on by default
  in fullscreen", next to "Fullscreen on startup". Off by default; when
  on, Focus opens with sound already on instead of muted, for any
  camera whose own "Audio" box is checked (no effect on the others);
- every checkbox in the Web config (camera active/audio, layout
  fullscreen/audio-default) now renders as an on/off slider toggle
  instead of a plain checkbox — a visual-only change.

## 1.0.0

### English localization

- the Web interface is now bilingual (FR/EN), selectable from a toggle on
  the login screen and in the app header, instead of French-only;
- language choice is stored in a `pidecoder_lang` cookie shared between the
  browser and the server, plus a new `POST /api/language` endpoint;
- `scripts/web/i18n.js` (new): dependency-free FR/EN translation engine for
  the frontend (219 keys, full FR/EN parity verified by an automated
  cross-check against every `t()` call site);
- `scripts/i18n.py` (new): FR/EN message dictionary for the backend's
  HTTP-facing error/message strings (25 keys, same parity check);
- validated live on the Raspberry Pi, in both languages, across every Web
  UI tab; wording adjusted for a few keys after review (`sys.hint`,
  `onvif.hint`, `notifications.none`, `diag.no_logs`);
- known limitation, deliberately deferred: `onvif_client.py`'s detailed
  ONVIF failure messages and the System tab's backend-sourced service
  state words are not yet translated — see `docs/PROJECT-STATE.md`.

### Bug fixes found during localization testing

- the header/login version label was a static piece of HTML text instead
  of coming from `/api/session`; it now updates dynamically and reflects
  the real running version;
- the Diagnostics tab's `version` and `release` fields were hardcoded to
  `'0.9.9.5 RC2'` / `'Release Candidate'` inside `diagnostics_payload()`,
  disconnected from the actual version in use since RC2; they now derive
  from the real `VERSION` constant, with the release label classified from
  its `-dev`/`-rc`/`-beta`/`-alpha` suffix (or `Stable` when none).

### Release

- first stable public release: version finalized to `1.0.0` (from the
  `1.0.0-dev` marker used during the localization work) in
  `scripts/config-web.py` (`VERSION`), `CMakeLists.txt` /
  `include/pidecoder/Version.hpp.in` (native engine's on-screen overlay),
  and `scripts/install.sh` (`INSTALLER_VERSION`); `scripts/validate-release.sh`
  updated to match;
- README/CONTRIBUTING/SECURITY public-launch documentation pass completed,
  along with `docs/faq.md`, `docs/configuration.md`, `docs/installation.md`
  and `docs/onvif.md`, which had drifted out of date (stale RC1/RC3 version
  references, an FAQ answer incorrectly claiming PTZ and English were not
  yet available);
- deployed and confirmed on the production Raspberry Pi
  (`olympus-vss-mon1`): all services active, version `1.0.0` consistent
  across the Web header/login, Diagnostics tab and the native engine's
  on-screen overlay;
- fixed a CI false positive: the "Check for committed runtime secrets"
  job's regex for embedded RTSP credentials matched the deliberately fake
  ones in `tests/test_redact_url.cpp` (an RC3-era unit test) and its own
  literal mention in `docs/PROJECT-STATE.md`'s field-validation
  notes; excluded the test file from the scan and reworded the affected
  documentation.

## 0.9.9.5 RC3

### Native PTZ field hotfix

- ONVIF and PTZ metadata are preserved when camera video values are edited from the Web interface;
- the browser keeps the existing `onvif` object when rebuilding camera entries;
- the `/api/config` endpoint merges stored ONVIF metadata when an older browser tab omits it;
- native PTZ directions, optical zoom, forced Stop and preset selection remain available after camera saves;
- the digital zoom percentage is displayed in the top-right corner instead of behind the PTZ overlay;
- Web, installer and validation labels updated from RC2 to RC3.

### Field validation

- native PTZ movement validated on an Axis Q6074;
- native preset selection validated on an Axis Q6074;
- five-second PTZ overlay auto-hide validated;
- ONVIF/PTZ metadata preservation validated after applying PiDecoder stream defaults;
- full reboot test performed on the production Raspberry Pi: all four
  services active, mosaic/focus autostart, native PTZ movement and preset
  selection, and PTZ metadata preservation all confirmed again after reboot.

### CI and tooling

- CI now actually compiles the C++ project (`cmake` + build) on every push,
  in addition to the existing Python/JavaScript/JSON checks;
- removed roughly 40 redundant `apply-v0XX.sh` update scripts, superseded by
  `install.sh`'s own idempotent update logic;
- split the monolithic embedded HTML/CSS/JS in `scripts/config-web.py` into
  `scripts/web/index.html`, `app.css` and `app.js`;
- fixed a repository-wide file-mode regression (scripts losing their
  executable bit through certain git/OneDrive workflows) and restored the
  affected permissions;
- `install.sh` now refuses to run when launched from the already-installed
  target directory, or when the current shell is positioned inside it —
  both previously invalidated the running process's working directory
  mid-install and produced a cryptic `cmake` failure.

### Security hardening

- added login rate-limiting on `/api/login` (5 attempts per 5 minutes per
  IP address, 5-minute lockout);
- added systemd sandboxing directives to all three services (`pidecoder`,
  `pidecoder-config`, `pidecoder-ptz`), tuned to each service's actual
  needs — the video engine keeps a more conservative profile because of its
  Wayland/OpenGL dependency;
- deduplicated the PTZ movement table (pan/tilt/zoom vectors) between
  `ptz-bridge.py` and `config-web.py` into a single definition in
  `onvif_client.py`;
- `/api/onvif/ptz` and `/api/onvif/preset` now derive ONVIF credentials
  from the camera's stored RTSP URL once it is registered in
  `cameras.json`, instead of requiring them from the browser on every
  movement; browser-supplied credentials remain a fallback while a camera
  is still being discovered and tested, before it has been saved;
- fixed a credential leak: the video engine was logging the full RTSP URL —
  including the embedded ONVIF username and password — to `journalctl` on
  every stream load, stall, disconnect and reconnect attempt. A shared
  `redact_credentials()` helper now masks the credentials part everywhere a
  stream URL is logged.

### Testing

- added a lightweight, dependency-free C++ unit test suite (`tests/`, wired
  into CMake and `ctest`) covering `Grid::calculate()`,
  `LayoutStore::normalize()`/`load()`/`save()`, and the new
  `redact_credentials()` helper;
- the CI build job now runs `ctest` after building, failing the pipeline on
  any regression in this logic.

## 0.9.9.5 RC2

### Native PTZ controls

- persistent local PTZ bridge through `/run/pidecoder/ptz.sock`;
- native SDL overlay shown only for cameras with valid PTZ metadata;
- pan, tilt, optical zoom and forced Stop controls;
- Stop safety on pointer release, pointer exit, focus loss, Escape and focus close;
- compact PTZ controls hidden after five seconds without pointer activity;
- native preset selector sending ONVIF `GotoPreset`;
- PTZ profiles, endpoints and presets stored in camera ONVIF metadata.

## 0.9.9.4 RC1 UI Polish

- page Système réorganisée sans doublons ;
- compteur ONVIF corrigé ;
- état global et services colorés ;
- journaux configurables sur 20, 50 ou 100 lignes ;
- aucun changement du moteur vidéo.

## 0.9.9.3 RC1

- import `re` ajouté pour les diagnostics ;
- endpoint Diagnostics protégé contre les exceptions ;
- sérialisation JSON rendue plus robuste ;
- onglets réordonnés : Caméras, ONVIF, Disposition, Système, Sécurité, Sauvegarde.

## 0.9.9.2 RC1 Login Fix

- JavaScript de connexion réparé ;
- fragment orphelin supprimé ;
- accolade manquante restaurée ;
- contrôle syntaxique JavaScript ajouté.

## 0.9.9.1 RC1 Fix

### Correctifs

- diagnostics intégrés à l’onglet Système ;
- route `/api/diagnostics` déplacée de POST vers GET ;
- structure HTML ONVIF/Système corrigée ;
- gestion des réponses non JSON améliorée.

## 0.9.9 RC1

### Release Candidate

- gel des fonctionnalités ;
- nouvel onglet Diagnostics en lecture seule ;
- rapport de support copiable ;
- journaux récents des deux services ;
- checklist de stabilité 4 h / 24 h / 72 h ;
- aucun changement volontaire du moteur vidéo.

## 0.9.8.1

### Correctifs UX

- réouverture fiable de l’historique des notifications ;
- notifications temporaires décalées de la cloche ;
- panneau compact des raccourcis clavier ;
- aucun changement fonctionnel du moteur vidéo.

## 0.9.8

### Ergonomie

- historique des cinq dernières notifications ;
- compteur de notifications non consultées ;
- raccourcis clavier Web ;
- aucun changement du moteur vidéo ou des formats de configuration.

## 0.9.7

### Nettoyage

- paquet simplifié ;
- anciens README retirés ;
- caches Python exclus ;
- styles et messages harmonisés.

### Fiabilité

- validation Python et JSON ;
- contrôle des fichiers essentiels ;
- contrôle strict de la version CMake ;
- restauration automatique en cas d'échec ;
- contrôle des services après installation.

### Compatibilité

Aucun changement du format de configuration ni du comportement du moteur
vidéo par rapport à la v0.9.6.
