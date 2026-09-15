# Changelog

## 1.1 (beta, field-tested on the Raspberry Pi, not yet merged to main)

### Native audio support

- the native engine can now play audio in the Focus view (one enlarged
  camera at a time); the mosaic/grid view stays silent, since playing
  every visible tile's audio at once would be unusable;
- sound starts muted every time Focus opens, on any camera; press **M**
  or click the new audio button to unmute;
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
  before this feature existed.

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
