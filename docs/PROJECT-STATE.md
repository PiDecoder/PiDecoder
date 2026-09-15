# PiDecoder project state

## Active version

- Stable version: **v1.0.0** — tagged, deployed on the production
  Raspberry Pi (`olympus-vss-mon1`), confirmed running with all services
  active and the version string consistent everywhere (Web header/login,
  Diagnostics, native on-screen overlay).
- Base version: v0.9.9.5 RC3 (merged to `main`, tagged, deployed)
- Active phase: v1.1 roadmap — native audio support in the Focus view,
  implemented on `main` and awaiting a build + field test on the
  Raspberry Pi before it is considered a beta (see "v1.1 — audio support"
  below). No git branch or tag decision made yet for this milestone.

## v1.1 — audio support (beta, awaiting hardware validation)

Per the roadmap, v1.1 adds audio playback. Scope decided with the user
before implementation:

- audio plays **only in the Focus view** (one enlarged camera at a
  time). The mosaic/grid view stays silent — playing the audio of every
  visible tile at once would be unusable. A future version could add
  audio for a hovered/selected mosaic tile, but that is not in this
  beta;
- the audio output device is whatever ALSA/mpv picks as the system
  default on the Pi (HDMI if that's what's configured, jack otherwise).
  No device is forced;
- the sound starts **muted** every time the Focus view is opened, on
  any camera. The user has to press **M** to unmute — this avoids a
  surprise sound on what is primarily a surveillance video wall.

Implementation (native C++ engine only — no Web UI or backend changes,
since the Web browser never receives this audio, only the Pi's own local
output does):

- `Player` (`role_ == PlayerRole::Focus`): `configure()` now sets
  `audio=auto` instead of the previous blanket `audio=no`, and applies
  the current mute state as an mpv `mute` option/property immediately
  (also re-applied by `configure()` on every reconnect, so a transient
  RTSP drop does not silently reset the user's choice). Grid-role
  players are unchanged (`audio=no`, always silent). New methods:
  `set_muted(bool)`, `muted()`, `has_audio_track()` (queries mpv's
  `audio-codec-name` property; empty/unavailable means the camera's
  stream has no audio track at all);
- `Application`: **M** toggles `focus_player_`'s mute state while a
  camera is in Focus (`SDLK_m`, alongside the existing `SDLK_ESCAPE`/
  `SDLK_f` handling). A short-lived on-screen indicator (2 seconds,
  same pattern as the existing zoom-percentage indicator) confirms the
  new state, including pressing M on a camera with no audio track at
  all;
- `Renderer`: new `draw_audio_indicator()`, top-left of the Focus view
  (the zoom indicator already owns the top-right corner), showing
  `SON ACTIF` / `SON COUPE` / `PAS DE SON` in the same pixel-font style
  used for the PTZ preset labels.

**Known, deliberately deferred scope** for this beta:

- no volume level control — only mute/unmute. mpv's own volume stays
  at its default (100%);
- no per-camera memory of the user's mute choice — every Focus session
  starts muted, by design (see above);
- no ONVIF-based advance detection of which cameras actually have a
  microphone/audio profile — `has_audio_track()` only becomes accurate
  once mpv has started decoding the stream (i.e. once Focus is already
  open), so there's no "this camera has audio" hint in the camera list
  or the Web UI;
- not yet validated on real hardware — needs a build (`cmake --build`)
  and a field test on the Pi: opening Focus on a camera that has an
  audio stream (if any of the test cameras expose one), confirming M
  toggles sound audibly and the indicator matches, and confirming a
  camera without audio shows `PAS DE SON` and does nothing harmful when
  M is pressed.

## v1.0 — English localization

Per the roadmap, v1.0's focus is the first stable public release and English
localization. The user explicitly chose a real bilingual FR/EN toggle
(rather than dropping French), implemented as follows:

- language stored in a `pidecoder_lang` cookie (non-HttpOnly, so both the
  browser JS and the Python backend can read it), default `fr`; a new
  `POST /api/language` endpoint (no auth required, so it also works on the
  login screen) sets it;
- `scripts/web/i18n.js` (new): a small dependency-free translation engine —
  `STRINGS.fr`/`STRINGS.en` dictionaries (213 keys, full parity verified —
  see below), `t(key, vars)`, `applyTranslations()` (walks
  `[data-i18n]`/`[data-i18n-title]` etc.), `setLang()`. Loaded before
  `app.js` in `index.html`;
- `scripts/web/index.html`: all static labels/headings/buttons now carry
  `data-i18n` attributes instead of hardcoded French text; a FR/EN toggle
  added to the login screen and the app header;
- `scripts/web/app.js`: every dynamically-generated French string (camera
  editor, mosaic, ONVIF discovery/PTZ panel, diagnostics, notifications,
  toasts, error fallbacks) now goes through `t('key')`; language changes
  re-run the affected render functions (`render()`, `renderMosaic()`,
  `renderOnvifDiscovery()`, etc.) since their output is JS-generated and
  `data-i18n` alone can't reach it;
- `scripts/i18n.py` (new): the backend mirror — a `MESSAGES` dict (25 keys,
  full FR/EN parity verified) and `t(key, lang, **kwargs)`, used by
  `scripts/config-web.py` for every HTTP-facing error/message string
  (login, auth, apply/import/export, password change, camera/ONVIF
  validation errors) so the API responds in the same language as the UI.

Verified (scripted, not just by hand): every translation key referenced
from `app.js`/`index.html` exists in both `STRINGS.fr` and `STRINGS.en` (and
vice versa — no orphaned keys); same cross-check for `i18n_t()` call sites
in `config-web.py` against `i18n.py`'s `MESSAGES`. `node --check` and
`python3 -m py_compile` pass on all new/changed files.

Also validated on real hardware, on `feature/v1.0-i18n-en`, browser pass on
every tab (Caméras, ONVIF, Disposition, Système, Sécurité, Sauvegarde) in
both languages: no leftover untranslated text found. Two real bugs were
found and fixed during this pass (both unrelated to translation itself):
the header/login version label was a static HTML string instead of coming
from `/api/session`, and the Diagnostics tab's `version`/`release` fields
in `diagnostics_payload()` were hardcoded to the old `'0.9.9.5 RC2'` /
`'Release Candidate'` literals, never updated since RC2. Both now derive
from the real `VERSION` constant. The native C++ engine's on-screen version
(`PIDECODER_VERSION_STRING`, from `Version.hpp.in`) was also found
out of sync and aligned to the same `1.0.0-dev` marker.

**Known, deliberately deferred scope** (documented rather than silently
skipped):

- `scripts/onvif_client.py`'s detailed SOAP/HTTP/XML failure messages
  (`OnvifError`, raised from `_soap()`) stay French. These are diagnostic
  messages for camera discovery/identification failures, not routine-use
  strings, and are already duplicated in the ONVIF debug log;
- the diagnostics/system tab's service-state words that originate in
  Python (`system_info()`/`diagnostics_payload()` in `config-web.py`:
  values like `détecté`/`indisponible`/`non déterminé`/`inconnu`) are not
  yet threaded through `i18n.py` — they'll still show up in French on the
  English UI. Threading `lang` into those functions is the next chunk of
  backend work;
- console-only/operator-facing strings (`ptz-bridge.py`,
  `check-camera-config.py`) are unchanged — not browser-facing, lowest
  priority.

Version strings were finalized from `1.0.0-dev` to `1.0.0` across
`Version.hpp.in`, `config-web.py`'s `VERSION`, `install.sh`'s
`INSTALLER_VERSION` and `validate-release.sh`. The
README/CONTRIBUTING/SECURITY public-launch documentation pass is done —
see "Merge and release checklist" below.

## Merge and release checklist — v1.0.0

1. ~~Implement bilingual FR/EN Web UI (frontend + backend), with scripted
   key-parity verification.~~ Done.
2. ~~Deploy `feature/v1.0-i18n-en` to the Raspberry Pi and validate every
   tab in both languages.~~ Done.
3. ~~Fix the two version/release bugs found during that validation
   (stale header label, hardcoded Diagnostics version).~~ Done.
4. ~~Bump the development version to `1.0.0-dev` in all three places it is
   defined, plus the installer and release validator.~~ Done.
5. ~~Merge `feature/v1.0-i18n-en` into `main`.~~ Done.
6. ~~Finalize the version strings from `1.0.0-dev` to `1.0.0`.~~ Done.
7. ~~Tag `main` as `v1.0.0`~~ Done — the tag also had to be moved once,
   to point past a CI-only fix (see the CI note below); it now sits on
   the same commit as `main`'s tip.
8. ~~Redeploy `main` on the Raspberry Pi and confirm the app starts
   correctly and shows `1.0.0` everywhere (header, login, Diagnostics,
   native overlay).~~ Done and confirmed on `olympus-vss-mon1`.
9. ~~README/CONTRIBUTING/SECURITY public-launch documentation pass.~~
   Done — README, CONTRIBUTING, SECURITY, and also
   `docs/faq.md`/`docs/configuration.md`/`docs/installation.md`/
   `docs/onvif.md`, which had drifted further out of date than expected
   (stale RC1/RC3 version mentions, an FAQ answer incorrectly claiming
   PTZ and English were not yet available). Historical test-checklist
   files (`docs/ptz-native-test-checklist.md`,
   `docs/installer-test-checklist.md`) were deliberately left untouched
   as archives.

**v1.0.0 milestone closed.** No open items remain for this release.

### CI note

The "Check for committed runtime secrets" job in
`.github/workflows/validate.yml` started failing on the `1.0.0` release
commit: its regex for embedded RTSP credentials (a username and password
between the `rtsp://` prefix and the `@`) matched the deliberately fake
credentials in `tests/test_redact_url.cpp` (RC3's redaction unit test)
and its own literal mention in this file's RC3 field-validation
paragraph. Fixed by excluding `test_redact_url.cpp` from the scan and
rewording this file's paragraph to avoid the literal pattern. This check
had apparently been broken since the RC3 merge without anyone noticing.

## Operational field state

Validated on the Raspberry Pi host:

- native RTSP mosaic: operational;
- native focus view: operational;
- digital inspection zoom and pan: operational;
- `pidecoder-config.service`: active;
- `pidecoder-ptz.service`: active;
- `pidecoder-wayland.path`: active;
- `pidecoder.service`: active;
- Axis Q6074 pan and tilt: operational;
- Axis Q6074 optical zoom: operational;
- Axis Q6074 native presets: operational;
- PTZ overlay auto-hide after five seconds: operational;
- fixed cameras do not display the PTZ overlay.

The Axis Q6074 ONVIF/PTZ metadata was restored and persisted in
`/opt/pidecoder/config/cameras.json`.

The repair helper was a one-time configuration repair. It is not a runtime
service and is no longer required once RC3 is installed.

## RC2 implementation completed

- persist `ptz_xaddr`, `ptz_profile_token` and PTZ presets in camera metadata;
- local Unix-datagram PTZ bridge at `/run/pidecoder/ptz.sock`;
- native PTZ overlay in the focus view;
- pan, tilt, optical zoom and forced Stop controls;
- native preset selector sending `GotoPreset` immediately;
- Stop on pointer release, pointer exit, focus loss, Escape and focus close;
- compact controls hidden after five seconds without mouse activity;
- overlay hidden automatically for cameras without valid PTZ metadata.

## RC3 hotfix completed

- browser camera synchronization preserves the existing `onvif` object;
- `/api/config` merges stored ONVIF metadata when an older browser tab omits it;
- changing camera resolution or FPS no longer removes PTZ endpoints, tokens or presets;
- using **Valeurs PiDecoder**, then saving and applying, preserves the native PTZ module;
- the digital zoom percentage is moved to the top-right corner;
- Web, installer and release-validator labels changed from RC2 to RC3;
- the PTZ movement table (pan/tilt/zoom vectors) is now defined once in
  `onvif_client.py` and shared by `ptz-bridge.py` and `config-web.py`,
  instead of two copies that could silently diverge;
- `/api/onvif/ptz` and `/api/onvif/preset` now derive ONVIF credentials from
  the camera's stored RTSP URL when it is already registered in
  `cameras.json`, instead of requiring them from the browser on every
  movement; the browser-supplied credentials are still used as a fallback
  while a camera is being discovered and tested, before it has been saved;
- a lightweight Layout/Grid unit test suite (`tests/`, `ctest`) now runs in
  CI on every push, as a regression safety net for the mosaic/layout logic.

## RC3 field validation (reboot test)

Full reboot test performed on the production Raspberry Pi
(`olympus-vss-mon1`) after installing RC3 with the fixes above:

- all four services (`pidecoder`, `pidecoder-config`, `pidecoder-ptz`,
  `pidecoder-wayland.path`) report `active` after reboot;
- mosaic and focus video start automatically without manual action;
- native PTZ movement (pan/tilt/zoom) and Stop behave correctly on the Axis
  Q6074 after reboot;
- native preset selection works after reboot;
- applying **Valeurs PiDecoder** again, then saving and applying, still
  preserves `ptz_xaddr`, `ptz_profile_token` and the 3 stored presets.

During this validation, a real credential leak was found and fixed: the
video engine (`src/Player.cpp`) was logging the full RTSP URL — including
the embedded ONVIF username and password — to `journalctl` every time a
stream loaded, stalled, disconnected, or reconnected. A shared
`redact_credentials()` helper (`include/pidecoder/RedactUrl.hpp`,
`src/RedactUrl.cpp`, covered by `tests/test_redact_url.cpp`) now masks the
`user:pass@` part of any logged URL. Verified clean after rebuilding: a
grep for embedded RTSP credentials (a username and password between
the `rtsp://` prefix and the `@`) across `pidecoder`,
`pidecoder-ptz` and `pidecoder-config` logs generated since the rebuild
returns `0` matches.

## Field performance note

During testing, the Axis Q6074 showed additional latency when two high-frame-rate
streams were requested simultaneously.

Recommended field configuration:

- mosaic: 640 × 360 at 12 FPS;
- focus: 1920 × 1080 at 25 FPS.

Keep the mosaic stream lightweight when a camera has a strict simultaneous-stream
or aggregate-frame-rate limit.

## Configuration ownership

Runtime configuration remains under:

```text
/opt/pidecoder/config/cameras.json
/opt/pidecoder/config/layout.json
/opt/pidecoder/config/web-auth.json
```

The installer preserves these files during upgrades and stores complete installation
backups under:

```text
/var/backups/pidecoder/
```

Camera configuration and logs may contain private RTSP addresses or credentials.
Never commit runtime configuration or raw camera logs.

## Remaining validation before merge to main

1. ~~Reboot the Raspberry Pi with RC3 installed.~~ Done.
2. ~~Confirm all four services return `active`.~~ Done.
3. ~~Confirm mosaic and focus video start automatically.~~ Done.
4. ~~Confirm native PTZ movement works after reboot.~~ Done.
5. ~~Confirm native preset selection works after reboot.~~ Done.
6. ~~Apply **Valeurs PiDecoder** once more and confirm PTZ metadata remains present.~~ Done.
7. ~~Review runtime logs and remove or redact full credential-bearing RTSP URLs before public release.~~ Done — see "RC3 field validation" above.
8. ~~Update this file with the reboot result.~~ Done.
9. Merge the feature branch to `main`.
10. Create the release tag only after the final validation passes.

## Outside the current RC3 scope

- keyboard PTZ shortcuts;
- native PTZ speed adjustment;
- audio support;
- HTTPS;
- public REST API.
