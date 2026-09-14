# PiDecoder project state

## Active version

- Development version: **v1.0 (in progress)**
- Base version: v0.9.9.5 RC3 (merged to `main`, tagged, deployed)
- Active phase: v1.0 roadmap — English localization (bilingual FR/EN Web UI)

## v1.0 — English localization (in progress)

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
`python3 -m py_compile` pass on all new/changed files. Not yet validated on
real hardware — needs a browser pass on the Pi (toggle FR→EN→FR on every
tab, confirm no leftover French text on the English side and vice versa)
before this is considered done.

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

Still pending for v1.0 after localization: bump version strings from RC3 to
a final `1.0.0` (`Version.hpp.in`, `config-web.py`'s `VERSION`,
`install.sh`'s `INSTALLER_VERSION`, `CHANGELOG.md`), and a public-launch
pass on README/CONTRIBUTING/SECURITY.

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
grep for the `rtsp://user:pass@` pattern across `pidecoder`,
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
