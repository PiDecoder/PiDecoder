# Changelog

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

### À venir (étape 2/2) : RTSPS entre le Pi et les caméras

Pas encore commencé. Contrairement à la page Web, ce n'est pas un chantier
autonome : ça dépend du support RTSPS de chaque caméra (souvent absent ou
partiel selon la marque/firmware), ça force probablement le transport TCP
là où la mosaïque utilise de l'UDP pour la latence minimale, et la
politique de confiance du certificat caméra (le plus souvent auto-signé
côté caméra aussi) reste à définir. Sera abordé une fois l'étape 1 validée
sur le Pi.

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
