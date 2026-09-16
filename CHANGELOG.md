# Changelog

## 1.3 (nouveau — testé en bac à sable, jamais sur le Pi réel)

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

**Tests effectués et leurs limites.** Contrairement à la plupart des
tournées précédentes, ce lot a été testé de bout en bout dans un bac à
sable avec des exécutables factices (`nmcli`, `hostnamectl`,
`timedatectl`, `systemd-run`, `runuser`, `systemctl`) et de vrais dépôts
Git locaux : cycle complet nom d'hôte/IP (appliqué → confirmé, et
appliqué → annulé automatiquement faute de confirmation), rejets de
validation (connexion inconnue, IP sans masque, serveur NTP invalide,
fuseau horaire invalide), et mise à jour complète (vérification, git
pull + install.sh réussis, et le cas d'échec d'install.sh). **Ce lot n'a
en revanche jamais été testé contre un vrai NetworkManager, un vrai
systemd-timesyncd/hostnamed, ni sur le Raspberry Pi physique.**
Recommandation avant de l'utiliser en production : tester d'abord le nom
d'hôte, le NTP et le fuseau horaire (aucun risque de perte d'accès), et
ne tester la bascule IP/DHCP qu'en gardant un second accès au Pi ouvert
(écran/clavier branchés, ou une seconde session SSH sur une connexion
qui ne dépend pas de l'adresse en cours de changement).

## 1.2 (en cours — étape 1 confirmée sur le Pi par l'utilisateur)

### HTTPS pour l'interface d'administration (étape 1/2)

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
