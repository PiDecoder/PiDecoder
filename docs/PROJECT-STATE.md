# PiDecoder project state

## Active version

- Stable version: **v1.2.0** — HTTPS for the Web administration
  interface (HTTP and HTTPS on two independent, editable ports, each
  individually enabled/disabled, certificate managed from the Web UI or
  SSH), a one-click software update from the Web UI, a full network
  configuration panel (hostname, DHCP/static IP, NTP, timezone) with an
  automatic confirm-or-revert safety net, and an on-screen
  IP/hostname/MAC/port overlay on the player's own screen at startup or
  on the **I** key. Everything below this line up to "v1.1 — audio
  support" documents how this version was built, across many rounds of
  field feedback on the real Raspberry Pi. To be merged from
  `feature/v1.2-https` into `main` and tagged.
  - **Confirmed working on the Pi**: the startup overlay (sizing and
    display bug both fixed), HTTP/HTTPS on two independent ports with
    on/off toggles, hostname/IP change with its confirm/auto-revert
    safety net (after four rounds of real-hardware bug fixes), a static
    IP surviving a software update, and editing the HTTP/HTTPS port
    numbers from the Sécurité tab.
  - **Not field-tested**: NTP server and timezone configuration
    specifically (exercised only against a fake-binary sandbox harness —
    `nmcli`/`hostnamectl`/`timedatectl`/`systemd-run`/`runuser`/
    `systemctl` stand-ins). These share the exact same privileged-change
    mechanism already proven for hostname/IP, so the risk is considered
    low, but it's worth a quick real check post-release since there's no
    lockout risk on either setting.
  - Step 2 of the original HTTPS roadmap item (RTSPS between the Pi and
    the cameras) was abandoned by explicit user decision after checking
    Axis's own documentation (see "Step 2" below for why) — not worth
    the complexity for a feature that's unlikely to ever be used.
- Base version: v1.1.0 — native audio support in the Focus view (see
  "v1.1 — audio support" below), field-tested and validated on the
  Raspberry Pi with an Axis camera. Merged to `main`, tagged, deployed.
- v1.0.0 (merged to `main`, tagged, deployed)
- **In progress (v1.3)**: a ready-to-flash SD card image, so a new unit no
  longer needs "install Raspberry Pi OS, then install PiDecoder" — see
  "v1.3 — SD card image" below. Implemented and exercised in the sandbox as
  far as it can be here, but **the image has never actually been built**
  (building it requires an arm64 chroot, which this sandbox cannot do), so
  nothing has been flashed or booted yet.
- **Scope decision (2026-09-17): Raspberry Pi OS Lite is now the only
  supported base going forward**, confirmed by the user. Context: the
  fullscreen-at-startup bug (window never actually filled the screen, see
  the long troubleshooting trail in CHANGELOG.md) was finally fixed by
  creating the SDL window directly at its final size/position instead of
  resizing it after creation — confirmed working on real Lite hardware.
  The same fix left the desktop taskbar visible on top of the video wall
  on a Raspberry Pi OS Desktop install; `SDL_WINDOW_ALWAYS_ON_TOP` +
  `SDL_RaiseWindow()` were tried and had no effect (most likely because a
  desktop panel is a Wayland `layer-shell` surface, which sits above
  ordinary client windows by protocol design, not by a stacking hint a
  client can override). Rather than keep chasing that from PiDecoder's own
  code, the user decided Desktop is dropped as a target: every unit is
  meant to run the Lite SD image. No further Desktop-specific fullscreen
  work should be pursued unless the user explicitly asks again.

## v1.3 — SD card image (built but never yet produced for real)

Explicit request: be able to flash PiDecoder straight onto an SD card,
without installing Raspberry Pi OS first and PiDecoder second.

**Approach, and the road not taken.** `scripts/build-image.sh` starts from
the *official* Raspberry Pi OS Lite arm64 image (pinned to a dated release
and verified against its SHA256), opens it through loop devices, and runs
the ordinary `scripts/install.sh` inside a chroot. The obvious alternative
was pi-gen, the official image builder, which reconstructs a whole system
from a debootstrap: hours per build, and a complete OS to own and maintain,
where all we actually need is to add one application to a base that is
already field-proven. Keeping the published base image means a flashed card
and a manual installation differ only in who typed the commands — the same
installer, the same units, the same layout.

**User's design choices** (asked before building): Raspberry Pi OS **Lite**
plus a minimal Wayland stack rather than the Desktop image; the script must
run **both** natively on a Pi and under qemu in GitHub Actions; and a
**known default Web password with a forced change at first login** rather
than a random per-device password or a first-boot wizard.

- **Wayland on a Lite base.** Lite has no graphical environment at all, so
  the image adds `labwc` (the compositor Raspberry Pi OS Desktop itself
  uses, so not an unknown quantity), the Mesa/EGL userspace for the V3D
  GPU, PipeWire for Focus-view audio, NetworkManager for the Réseau tab and
  Avahi for `.local` resolution. The session is started by autologin on
  tty1 (a `getty@tty1` drop-in) whose `~/.bash_profile` execs `labwc`,
  which creates `/run/user/<uid>/wayland-0` — precisely what the existing
  `pidecoder-wayland.path` already waits for. Going through a real getty
  matters: it is what opens a logind session, which is what provides the
  seat labwc needs and the user D-Bus instance PipeWire needs.
- **Per-device identity is removed from the image**, and regenerated on the
  device by a new `pidecoder-firstboot.service`: SSH host keys (a shared
  private key would let any unit impersonate any other), the machine ID
  (otherwise every card presents the same DHCP DUID), the TLS certificate
  (its private key would be public, and its SANs would carry the build
  machine's hostname and IPs), and the hostname, derived from the SoC
  serial as `pidecoder-xxxxxx` so units don't fight over one `.local` name.
- **Root filesystem expansion was not reimplemented**: Raspberry Pi OS's own
  `init=` mechanism in `cmdline.txt` already does it, earlier than anything
  we could run, and the builder verifies that it is still armed before
  closing the image.
- **The build toolchain stays in the image, deliberately.** Removing it
  would save roughly 1 GB, but the one-click update runs `git pull` then
  `install.sh`, which recompiles the native engine — a slimmed image would
  be an image that cannot update itself. For the same reason the image
  carries a real Git clone with its remote, not a copy of the files.
- **Forced password change.** The default Web password (`admin` /
  `pidecoder`) is flagged `must_change` in `web-auth.json`, and the block is
  enforced server-side: `need()` refuses every API path except
  `/api/change-password` while the flag is set, so a `curl` or a stale tab
  cannot walk around the screen. The flag disappears on the first successful
  change, because the function that writes the new password is the same one,
  called without that argument. New non-interactive flags make this possible
  from inside a chroot (`--password-stdin`/`--must-change` on config-web.py,
  `--web-password-stdin`/`--web-password-must-change` on install.sh), with
  the password passed on standard input so it never appears in a command
  line or in the process list.

**Tested here.** The Web half was exercised for real against a running
`config-web.py`: login on a flagged account, `/api/config` and
`/api/network/hostname` both correctly refused with 403, too-short change
rejected, successful change accepted, re-login and normal access restored.
The image plumbing was exercised against a synthetic image built for the
purpose (same MBR layout and partition geometry as a real Pi OS image):
grow, mount, shrink, partition-table rewrite, truncate, compress, and a
check that the final filesystem passes `e2fsck` with its contents intact
byte for byte. Those tests found two real bugs before delivery — loop
devices were never detached (the attach helper was called inside a command
substitution, i.e. a subshell, so the list the cleanup trap reads stayed
empty) and the checksum file named the image `-`, which made `sha256sum -c`
block on standard input — plus one weakness worth hardening: every `e2fsck`
exit code was being ignored, including the ones that report **uncorrected**
errors, so a damaged filesystem would have shipped silently.

**Not tested here, and it is the bulk of it.** The actual build needs an
arm64 chroot, which this sandbox cannot provide (no qemu-user, and apt is
blocked), so nothing has verified: the package installation inside the
image, the native engine compiling there, the labwc session actually
starting on real hardware, or a flashed card booting at all. First run
should be `sudo ./scripts/build-image.sh` on the Pi, and the first card
should go into a Pi that is not in production.

## v1.2.0, part 1 — HTTPS (step 1/2 confirmed working on the Pi; step 2 abandoned)

Per the roadmap, v1.2 adds HTTPS. The user asked to secure "the stream"
too; since PiDecoder's video is decoded natively on the Pi's own screen
(mpv/SDL2 pulling RTSP directly from each camera) and never transits
through the browser, that isn't actually an HTTP/HTTPS concern — it's
RTSP vs. RTSPS between the Pi and each camera, a separate protocol with
its own (camera-dependent) constraints. Scope agreed with the user: do
both, Web HTTPS first since it's self-contained, RTSPS second since it
depends on what each camera supports and interacts with the mosaic's
transport/latency tuning (see "v1.1" below on the UDP demuxer settings).

### Step 1 — HTTPS for the Web administration interface

Implementation (native Python stdlib only, no new dependency):

- `scripts/config-web.py`: the `ThreadingHTTPServer` socket is wrapped
  in an `ssl.SSLContext` (`PROTOCOL_TLS_SERVER`, minimum TLS 1.2)
  whenever a certificate and key are found at `<root>/config/tls/
  {cert.pem,key.pem}` (overridable with new `--tls-cert`/`--tls-key`
  arguments). If the certificate is missing or fails to load (corrupt
  file, mismatched pair on a very old manual setup), the server logs a
  clear warning to stderr and falls back to plain HTTP instead of
  crashing — administration must never become totally inaccessible
  because of a certificate problem. New `--no-https` flag forces plain
  HTTP explicitly (development use only);
- the session cookie (`pidecoder_session`) and language cookie
  (`pidecoder_lang`) gain the `Secure` attribute only when the
  connection is actually TLS (`Server.tls`, set once in `main()`) — a
  `Secure` cookie sent over plain HTTP is silently dropped by the
  browser and would break the session, so this has to track the real
  transport, not just "HTTPS is the new default";
- `scripts/install.sh`: generates a self-signed certificate on first
  install (`openssl req -x509`, RSA 2048, 10-year validity) with the
  Pi's hostname and detected local IPv4 addresses as Subject
  Alternative Names, so the browser can trust the IP actually used to
  connect once the initial warning is accepted manually — the same
  approach used by most LAN admin interfaces (router, NAS...) since a
  Raspberry Pi on a home network has no public domain/DNS to get a
  CA-signed certificate for;
- new `--tls-cert`/`--tls-key` installer options to import an existing
  certificate instead (e.g. an internal CA already trusted on the
  user's devices). The installer validates both are readable, valid
  PEM, and that the key actually matches the certificate (public-key
  digest comparison, works for RSA and EC) before installing them —
  rejects a mismatched pair up front rather than deploying something
  broken;
- on upgrade, an existing certificate at `$TARGET/config/tls/` is
  preserved as-is (same preservation pattern as `cameras.json`/
  `layout.json`/`web-auth.json`), unless `--tls-cert`/`--tls-key` are
  passed again, which always overwrite;
- permissions mirror `web-auth.json`: `config/tls/` at 0750, `key.pem`
  at 0600, `cert.pem` at 0644, owner `root:root` — the
  `pidecoder-config` service already runs as root, so no group-read
  workaround was needed;
- `install.sh`'s printed URLs (preflight summary and final install
  message) switched from `http://` to `https://`; a one-line reminder
  about the self-signed browser warning is printed after a fresh
  install, but only when a certificate was actually generated this run
  (`TLS_GENERATED`) — not when one was preserved from a previous install
  (the browser already trusts it) or imported via `--tls-cert`.

**Follow-up round after the user tried it**: confirmed working, then
asked for an explicit on/off switch and a lighter way to add a
certificate manually after the fact, without going through the full
installer (which rebuilds the native engine and stops every service):

- new `install.sh` `--no-https` flag: skips certificate generation/
  import entirely at install time, so the service starts in plain HTTP
  from the first deployment. Mutually exclusive with
  `--tls-cert`/`--tls-key`. On an upgrade, passing `--no-https`
  deliberately does not carry over a certificate that was active
  before — that's an explicit "stop using HTTPS" request; the old
  certificate still exists in the installer's automatic backup if the
  user changes their mind;
- **new `scripts/manage-tls.sh`**: a standalone script to flip
  HTTPS on/off or swap the certificate on an already-installed Pi,
  without the heavy install/rebuild path. Subcommands: `status` (prints
  whether HTTPS is active and the current certificate's subject/
  expiry/SAN), `generate [--force]` (fresh self-signed certificate,
  same SAN logic as the installer, refuses to clobber an existing one
  without `--force`), `import --cert PATH --key PATH` (installs a
  user-supplied certificate, reusing the exact same PEM/pair-matching
  validation as `install.sh`), `disable` (moves the active certificate
  aside to `cert.pem.disabled`/`key.pem.disabled` — nothing is deleted
  — and the service falls back to HTTP), and `enable` (restores a
  disabled certificate, or generates a fresh one if none exists).
  Every subcommand except `status` restarts `pidecoder-config.service`
  at the end so the change is live immediately; permissions match the
  installer's (`root:root`, `key.pem` 0600, `cert.pem` 0644). Added to
  `install.sh`'s `chmod 0755` list and to `validate-release.sh`'s
  shell-syntax and required-files checks, same as every other shipped
  script.

**Validated locally, not yet on hardware**: built a throwaway root
directory in the sandbox, generated a self-signed certificate with the
exact SAN logic used in `install.sh`, and ran `config-web.py` against
it directly — confirmed the server actually negotiates TLS (a plain
HTTP request to the HTTPS port is refused, not silently accepted), that
`/api/login` returns a `Secure` cookie over HTTPS and a non-`Secure`
one when no certificate is present (HTTP fallback), and that a
corrupted certificate degrades to a working HTTP server with a clear
stderr warning instead of crashing. Also exercised every
`manage-tls.sh` subcommand end to end against a fake install directory:
`generate` then `status`, `generate` again without `--force` (correctly
refused), `disable`/`enable` round-trip (certificate restored exactly),
`import` with a matching pair (replaces the active certificate) and
with a mismatched pair (correctly refused before touching any file),
`generate --force` (overwrites), and the usage/unknown-subcommand
paths. **Not yet tested on the Raspberry Pi itself** — still to
validate: the actual browser warning UX on first connect, login/PTZ/
audio all working normally over HTTPS, an upgrade of an existing
installation correctly preserving the generated certificate instead of
regenerating it, a real `--no-https` install, and `manage-tls.sh`
against the real `pidecoder-config.service` (the sandbox only prints a
warning and skips the restart, since no such service exists there).

**Second follow-up round — certificate management and full HTTPS on/off
in the Web UI itself**: the user asked whether adding this as a Web UI
option (instead of SSH-only) would be complicated. Explained the
trade-off — swapping/regenerating a certificate while staying on HTTPS is
simple and hot-reloadable with zero downtime, but a full on/off toggle is
trickier because switching scheme changes the browser's origin (session/
cookies don't survive) and the server has to restart itself, which a
running process can't safely do synchronously. The user chose to do both
("Le on/off complet aussi, dans la Web UI").

- new `config-web.py` API endpoints: `GET /api/tls/status` (active
  certificate's subject/expiry/SAN, whether a `.disabled` certificate
  exists), `POST /api/tls/generate`, `/api/tls/import`, `/api/tls/enable`,
  `/api/tls/disable`. Each delegates the actual file work to
  `manage-tls.sh` (new `--no-restart` flag, so `config-web.py` controls
  exactly when/how the restart happens instead of the script doing it
  synchronously);
- `generate` and `import` **hot-reload** the already-running server's live
  `ssl.SSLContext` by calling `load_cert_chain()` again on it — no
  restart, no dropped connections, the new certificate applies to the
  next TLS handshake only. `import` is refused outright when the current
  connection isn't already HTTPS, to avoid ever sending a private key in
  cleartext over the LAN (error message points to enabling HTTPS first or
  using `manage-tls.sh` over SSH);
- `enable`/`disable` **do** restart the service, since changing scheme is
  an origin change the running process can't paper over. A process can't
  synchronously `systemctl restart` its own unit (systemd kills it mid-
  transaction) and a naive delayed `subprocess.Popen` would also be
  killed (same cgroup). Fixed with `systemd-run --collect
  --on-active=2 systemctl restart pidecoder-config.service`: creates an
  independent transient unit outside the calling service's cgroup, so it
  survives the service stopping and fires the restart 2 seconds later —
  enough time for the JSON response (which includes the correct
  `redirect_url` for the frontend to follow) to reach the browser first;
- `manage-tls.sh`'s `cmd_enable` had an idempotency bug relative to the
  new `--no-restart` flag: it used to infer "HTTPS already active" purely
  from `cert.pem` existing on disk, which becomes wrong once a certificate
  can be staged via `--no-restart` without the running process having
  picked it up yet. Fixed to always restart when a valid certificate is
  present, whether just restored from `.disabled` or already there;
- new "Certificat HTTPS" panel in the Web UI's Sécurité tab: status
  display, generate button, on/off toggle, and an import sub-form (cert +
  key file inputs). A plain warning line precedes the on/off toggle
  rather than a confirmation dialog — this codebase doesn't use
  `window.confirm()` anywhere, consistent with e.g. the existing "Apply"
  button that already restarts the video engine with no confirmation
  popup;
- 22 new frontend `sec.tls_*` keys (`web/i18n.js`) and 7 new backend
  `tls.*` keys (`i18n.py`), FR/EN parity checked (241 keys each side, no
  mismatch);
- **validated in the sandbox end-to-end** against a real running
  `config-web.py` instance (fake root, self-signed cert, real HTTP
  requests via `curl`): login, `GET /api/tls/status`, `POST
  /api/tls/generate --force` (certificate changed, session survived,
  hot-reload confirmed live), `POST /api/tls/import` (certificate
  replaced, hot-reload confirmed), `POST /api/tls/import` correctly
  refused over plain HTTP, `POST /api/tls/disable` (cert files correctly
  renamed to `.disabled`, restarting a fresh instance against the same
  root confirmed it comes back up in plain HTTP), `POST /api/tls/enable`
  over HTTP (correctly restored `cert.pem`/`key.pem` from `.disabled`,
  correct `https://` `redirect_url` returned). **The `systemd-run` self-
  restart mechanism itself could not be exercised** — no functional
  systemd in this environment — so the file-level state changes and API
  contracts are confirmed correct, but the actual restart-and-redirect
  user experience on a real `pidecoder-config.service` is unverified and
  is the single highest-risk part of this round. Needs real-hardware
  validation before being considered done, ideally with an SSH session
  open as a fallback in case the toggle leaves the service in a bad
  state.

**Field bug found and fixed: login stuck after falling back to HTTP.**
The user hit this testing `--no-https` in a browser that had previously
used HTTPS against the same Pi: login appeared accepted (no error shown)
but the UI never left the login screen. Root cause: the browser had kept
a `Secure`-flagged `pidecoder_session` cookie from the earlier HTTPS
session, and browsers refuse to let a plain-HTTP response overwrite a
`Secure` cookie of the same name — the new session cookie was silently
dropped, so every request after login kept coming back 401 "session
expired" (visible in devtools as `Uncaught (in promise) Error: Session
expired`, and as "Cookie ... has been rejected because there is an
existing 'secure' cookie" in the console). Fixed for the controlled
paths: `POST /api/tls/disable` now explicitly expires both
`pidecoder_session` and `pidecoder_lang` (as `Secure`, so the browser
accepts the deletion) in its response, while the server is still
answering over HTTPS — the only moment that's possible; `H.j()` now
supports multiple `Set-Cookie` headers to allow this. `manage-tls.sh
disable` and `install.sh --no-https` (on an upgrade that had an active
certificate) can't perform this cleanup themselves (the service is no
longer on HTTPS by the time they run), so both now print an explicit
warning telling the user to clear that site's cookies in the browser if
this happens. The *uncontrolled* fallback case (a certificate goes bad
and `main()` silently drops to HTTP on its own) remains an open,
undocumented-in-code limitation — there's no HTTPS response left to
clean up the cookie from at that point.

**Process bug found: deployment instructions given to the user were
wrong for this entire round.** After several rounds of "restart the
service, no need to reinstall" guidance for Python/JS-only changes, the
user reported seeing no change at all across multiple deliveries — a
full-screen overlay that never appeared, a disable flow still closing in
~2s instead of the new 30s countdown, a version number that never moved.
Root cause: `pidecoder-config.service` runs `/opt/pidecoder/scripts/
config-web.py` (see `ExecStart` in `systemd/pidecoder-config.service.in`)
— a physical copy of `scripts/` made once by `install.sh` (`cp -a
"$STAGED_ROOT" "$TARGET"`), entirely separate from the Git checkout at
`~/PiDecoder`. `git pull` only updates the checkout; nothing copies those
files into `/opt/pidecoder` except running `install.sh` again. So
"restart the service" alone, without ever re-running `install.sh`, just
re-executes whatever was already deployed — every round since Step 1's
initial hardware confirmation may have silently been testing stale code.
Fixed by adding `scripts/sync-dev.sh` (dev-only convenience: `cp -a` of
`scripts/` into `/opt/pidecoder/scripts/` plus a service restart, skipping
the full installer's native rebuild and video-engine restart) and by
changing `config-web.py`'s `VERSION` to `'1.1.0-dev'` (reusing the
existing `-dev`/`-rc`/`-beta`/`-alpha` → `release_label` convention
already in the diagnostics code) so a successful sync is visible in the
header/login page without digging into devtools. Documented in
`docs/installation.md` ("`git pull` alone does not update a running
installation"). Going forward, every delivered round that touches
`scripts/` should tell the user to run `sudo bash scripts/sync-dev.sh`
(or `sudo ./scripts/install.sh` when C++ sources changed), never a bare
service restart.

**Bug found and fixed: the self-signed certificate appeared to never
regenerate.** Once `sync-dev.sh` was actually in place (so real code was
finally being tested), clicking "Generate" repeatedly always showed the
same certificate dates in the browser's own certificate viewer. The
server-side data was always correct (verified: `not_after` changes on
every `POST /api/tls/generate` call, and PiDecoder's own status panel
reflects it immediately) — the culprit was TLS session resumption: a
browser reusing an existing TLS 1.3 session performs an abbreviated
handshake that never re-presents the certificate, so its certificate
viewer kept showing whatever was live at the time the session was first
established. `ssl.SSLContext.options |= ssl.OP_NO_TICKET` alone didn't
fix it (that only covers pre-1.3 ticket resumption); `ctx.num_tickets = 0`
(Python's TLS 1.3-specific control) was also needed. Reproduced and
confirmed with `openssl s_client -sess_out`/`-sess_in`: before the fix, a
captured session could be resumed after a regenerate and would still
present the old certificate; after adding `num_tickets = 0`, no session
ticket is issued at all and every new connection gets a full handshake
with whatever certificate is currently loaded. Minor tradeoff: every
HTTPS connection now does a full handshake instead of a cheaper resumed
one — negligible for a low-traffic LAN admin interface, and consistent
with `config-web.py` already using HTTP/1.0 (a new TCP connection per
request regardless).

### Step 2 — RTSPS between the Pi and the cameras

Not started. Unlike step 1, this isn't a self-contained piece of work:

- depends entirely on whether each camera's RTSP server also offers
  RTSPS — support varies a lot by brand/firmware and some cameras
  (possibly including the Aqara G410, not checked yet) may not offer it
  at all;
- RTSPS runs over TCP (TLS needs a reliable transport), which conflicts
  with the mosaic's UDP-based low-latency tuning documented under
  "v1.1" below — a camera switched to RTSPS in the mosaic would need a
  transport/latency trade-off similar to (but larger than) the one
  already made for `audio_enabled` cameras;
- most consumer/prosumer cameras present a self-signed certificate on
  their own RTSPS listener, so a trust policy has to be decided
  (accept without verification like most NVRs do, or something more —
  no per-camera cert pinning exists in PiDecoder today);
- needs a real camera that actually speaks RTSPS to validate against,
  which isn't available in the development sandbox — hardware testing
  drives this step, same as everything else in this project.

**Update: abandoned per the user's explicit decision.** A first
implementation was started (per-camera toggle in each camera's advanced
menu), but checking Axis's own developer documentation afterward
revealed that Axis's RTSPS listens on a separate port (322, not 554)
and only encrypts the RTSP control channel anyway — not the actual
video/audio, which would need SRTP, a distinctly harder mechanism to
support with mpv/ffmpeg (no native MIKEY key-exchange support). Judged
not worth the complexity and unlikely to ever be used; reverted before
going anywhere near production. Left here for reference if revisited
later — keep the RTSPS/SRTP distinction and the Axis port-322 specifics
in mind.

## v1.2.0, part 2 — Software update, network configuration and port editing (Web UI)

Per the user's explicit request ("Un check update depuis la page web ca
serrait trop bien... possibilité de passé le pi en adresse manuel ou dhcp
via WEB et choisir les parametre réeau / NTP, hostname, etc"), two new
features were added to the Web UI: a software update check/install button
on the Système tab, and a full network configuration panel (new "Réseau"
tab) covering hostname, DHCP/static IP, NTP, and timezone. Clarified with
the user via `AskUserQuestion`: the update feature is "check + install
button" (not fully automatic), and the network feature must have automatic
rollback as its safety net (not, e.g., a confirmation dialog alone).

### Why this needed a new architecture: `pidecoder-config.service`'s sandbox

`pidecoder-config.service` runs as root but under fairly strict systemd
hardening (`ProtectSystem=strict`, `ProtectHostname=true`,
`RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`,
`SystemCallFilter=@system-service`, `NoNewPrivileges=true`). Running
`hostnamectl set-hostname`, editing `/etc/hosts` or
`/etc/systemd/timesyncd.conf`, or calling `nmcli con mod` directly from
`config-web.py`'s own process would fail under this confinement — read-only
filesystem protections. The same problem already existed for the HTTPS
on/off toggle (v1.2) and was solved there with `systemd-run`: a transient
unit it starts does **not** inherit the calling unit's sandboxing (it's an
independent unit with its own, empty confinement) — the same technique as
running `sudo bash script.sh` from a shell that itself couldn't touch those
paths. This round generalizes that pattern into a dedicated module,
`scripts/system_admin.py`, with two delegation modes:

- `run_detached(script, description)` — writes `script` to
  `/run/pidecoder-admin-<random>.sh` and starts it via
  `systemd-run --collect --unit=... bash <path>`, fire-and-forget. Used
  for the software update and for hostname/IP changes, which need a
  background timer (see rollback below) and, for the update, must survive
  `pidecoder-config.service` itself being restarted mid-flight by
  `install.sh`.
- `run_sync_unsandboxed(command, timeout)` — `systemd-run --wait --pipe
  --collect --quiet bash -c <command>`, which blocks and relays the
  command's stdout/stderr/exit code as if it had been run directly. Used
  for NTP and timezone changes, which are low-risk (can't lock anyone out)
  and don't need the rollback machinery, just a synchronous result to show
  in the UI.

### Software update (`/api/update/*`)

- `check_update(repo_path, service_user)` runs `git fetch` (and
  `rev-parse`/`rev-list`/`log` against `@{upstream}`) in the Git clone,
  wrapped in `runuser -u <service_user> --` so the fetch's refs stay owned
  by the account that owns the clone (the desktop/video-wall user) instead
  of `root` — `pidecoder-config.service` runs as root, and root-owned
  files inside the user's clone would later break plain `git status`/
  `git pull` run by hand over SSH ("detected dubious ownership"). Returns
  whether an update is available, how many commits behind, and the latest
  upstream commit's one-line summary; handles "not a git repo", "no
  upstream branch", and "fetch failed" as distinct, displayed states
  rather than generic errors.
- `start_update(...)` runs, in one detached script: `runuser -u
  <service_user> -- git -C <repo_path> pull`, then `bash
  <repo_path>/scripts/install.sh --user <service_user> --target <target>
  --bind <bind> --port <port>`. `install.sh` restarts
  `pidecoder-config.service` at the end of a normal run — the very process
  handling the `/api/update/start` request gets killed mid-flight — which
  is exactly why this has to run as an independent `systemd-run` unit
  rather than inline: it survives the restart, and the reincarnated
  service reads the same JSON status file, so the Web UI's progress
  display doesn't need to know a restart happened.
- `<service>` (the user running the video-wall session) is determined by
  reading `User=` back out of `/etc/systemd/system/pidecoder.service`
  rather than trusting `install.sh`'s own auto-detection
  (`SUDO_USER`/`logname`/single-passwd-candidate), which is unreliable
  when `install.sh` is re-invoked from `systemd-run` with no controlling
  terminal.
- install.sh's own existing failure handling (`trap rollback ERR INT TERM`
  restoring the previous `/opt/pidecoder` and restarting services) is
  relied on as-is for the install step; it is **not** duplicated here.
  If `git pull` or `install.sh` fails, the status file records `state:
  "error"` with the failing step and the last 200 log lines, and the
  "Update now" button reappears so the user can retry once the underlying
  issue (network, disk space, a bad merge...) is fixed.
- Requires `--repo-path`, a new `install.sh`/`pidecoder-config.service.in`
  argument (see below) — an installation that hasn't re-run `install.sh`
  since before this round won't have it, and the Web UI shows a clear
  "update unavailable, re-run install.sh once" message rather than a
  broken button.

### Network configuration (`/api/network/*`, new "Réseau" tab)

- Hostname, DHCP/static IP, NTP, and timezone are all read through
  `hostnamectl`/`nmcli`/`timedatectl` (Raspberry Pi OS Bookworm uses
  NetworkManager, not `dhcpcd`, confirmed via web research) — no
  configuration file is parsed directly for the *read* path.
- **Automatic rollback**, generalized from the same confirm-or-revert
  pattern already used for the HTTPS restart countdown: applying a new
  hostname or IP writes a `config/network-pending/<token>.json` status
  file (`state: "pending"` → `"applied"`), then the detached script sleeps
  up to `PENDING_DELAY_SECONDS` (45s) checking once a second for a
  `<token>.confirmed` sentinel file. If `/api/network/confirm` (posted
  from the Web UI once the user confirms they can still reach the page)
  creates that sentinel in time, the script exits and the status becomes
  `"confirmed"`; otherwise it reverts to the pre-change value (old
  hostname, or the connection's previous `ipv4.method`/`addresses`/
  `gateway`/`dns`) and marks the status `"reverted"`. This is entirely
  server-side — it does not depend on the browser successfully reaching
  back, which is the whole point (a bad IP change is exactly the case
  where it might not). `/api/network/status`'s `pending` field survives a
  page reload on the new address, so a countdown/confirm banner isn't lost
  if the tab that started the change can't be reached.
- Hostname change also fixes up `/etc/hosts`'s `127.0.1.1` line (`sed -i`)
  since `hostnamectl set-hostname` does not do this itself — left stale,
  the old hostname would keep resolving to the Pi's own loopback-adjacent
  address.
- IP change: `connection_name` is only ever taken from the set already
  returned by `list_connections()` (validated server-side in
  `config-web.py` before it ever reaches `system_admin.start_ip_change`),
  never accepted as an arbitrary client-supplied string, since it ends up
  interpolated into an `nmcli con mod <name> ...` command run as root.
  Static addressing requires an explicit `/prefix` (`validate_cidr`
  rejects a bare IP rather than silently assuming `/32`, which
  `ipaddress.ip_interface()` would otherwise do and which is almost
  certainly not what someone typing a LAN address intended).
- NTP: no D-Bus method exists to set a custom server list (only
  `timedatectl set-ntp true/false` for on/off), so the server list is
  written directly into `/etc/systemd/timesyncd.conf`'s `[Time]` section
  (existing file preserved, `NTP=` line replaced or added, section header
  added if missing), followed by `systemctl restart systemd-timesyncd`.
  NTP server validation (`validate_ntp_servers`) intentionally allows
  hostnames (e.g. `pool.ntp.org`), unlike the IPv4-only
  `validate_dns_list` used for DNS servers.
- Timezone: `timedatectl set-timezone`, validated against
  `timedatectl list-timezones` server-side before being accepted.
- Every mutating endpoint validates its input server-side
  (`validate_hostname`, `validate_cidr`, `validate_ipv4`,
  `validate_dns_list`, `validate_ntp_servers`, the known-connection-name
  check, the known-timezone check) before it is ever interpolated into a
  shell command run as root — none of this trusts the browser.

### Plumbing: `@REPO_PATH@`

A new `install.sh` templating variable, `@REPO_PATH@` (sourced from
`$SOURCE_ROOT`, the Git clone `install.sh` is run from), is substituted
into `pidecoder-config.service`'s `ExecStart` (`--repo-path` argument) and
`ReadWritePaths` (so the detached update script, which runs outside the
service's own sandbox anyway via `systemd-run`, isn't the only thing that
needs write access — `pidecoder-config.service` itself needs read access
to the clone for `check_update`'s `git fetch`). **This means this round
requires a full `sudo ./scripts/install.sh` on the Pi, not just
`sync-dev.sh`**, even though there is no C++ change — `sync-dev.sh`
deliberately never touches systemd unit files, and the new
`--repo-path`/`ReadWritePaths` only take effect through a full install.

### Testing performed and its limits

Both features' backends were exercised end-to-end against a fake-binary
integration harness — stand-in `nmcli`, `hostnamectl`, `timedatectl`,
`systemd-run`, `runuser`, and `systemctl` scripts on `PATH`, a real running
`config-web.py` process, and `curl` — covering: hostname change through
the full pending → applied → confirmed lifecycle and, separately, the
unconfirmed → automatic reversion path (with `PENDING_DELAY_SECONDS`
temporarily lowered to a few seconds for the test only, never in the
shipped code); the same two paths for a static/DHCP IP change on a fake
connection; rejection of an unknown connection name, a bare IP without a
CIDR prefix, an invalid NTP server, and an invalid timezone; NTP and
timezone apply; and the full update flow — `check_update` against a real
local Git remote genuinely one commit behind (correct commit count and
summary), `start_update` running a real `git pull` plus a stand-in
`install.sh` through to a `"done"` status with the repository actually
updated, and the same flow with the stand-in `install.sh` deliberately
failing, correctly producing an `"error"` status with the failing step and
log tail. This is more thorough than most previous rounds got (RTSPS, for
comparison, only got isolated `g++` snippet compilation) — deliberately,
given the stakes of a feature that can change how the Pi is reached.

**None of this exercised the real `NetworkManager`, `systemd-timesyncd`,
`hostnamed`, or `systemd-run`'s actual sandbox-escaping behavior, and none
of it ran on actual Raspberry Pi hardware.** Before relying on this in
production: test the hostname, NTP, and timezone changes first — lower
risk, nothing there can cut off network access. Test the IP/DHCP toggle
last, and keep a second way to reach the Pi open while doing it (a
keyboard/monitor on the Pi itself, or a second SSH session over a
connection that doesn't depend on the address being changed) — the
automatic rollback is designed to make this unnecessary, but it has not
yet been proven against the real `nmcli`/NetworkManager stack, only
against a shell script standing in for it.

### Follow-up after first field feedback

The user tried this on the real Pi and reported two issues, plus a new
small feature request:

- **`check_update` wrongly reported "not a Git repository"** on what was
  in fact a valid clone. Root cause: it only checked for a `.git`
  *directory* (`(repo / '.git').is_dir()`), which rejects perfectly valid
  Git layouts where `.git` is a *file* instead (a linked worktree, a
  submodule, `--separate-git-dir`). Fixed by checking with `git
  rev-parse --is-inside-work-tree` instead, which is correct for every
  Git layout and, as a side benefit, now surfaces `git`'s actual stderr
  in the Web UI when something else is wrong (permissions, an
  unreachable path...) instead of a generic "not a repo" message.
  Verified against a real `git worktree`-based clone (`.git` as a file)
  reproducing the failure and confirming the fix.
- **Confirm/rollback UX reworked**: the countdown was an inline banner
  refreshed by polling every few seconds, which looked "jerky" to the
  user. Replaced with a full-screen overlay (same visual treatment as the
  HTTPS restart overlay) with a countdown that ticks locally every
  second instead of waiting on the next poll, plus a direct link to try
  the new address (`http(s)://<new-ip>/...` for an IP change,
  `http(s)://<hostname>.local/...` for a hostname change) so the user
  doesn't have to retype it. This also uncovered that `start_ip_change`'s
  "applied" status write was missing `old_value`/`new_value` (present
  only in the initial "pending" write) — fixed, since the redirect link
  needs the new address from that same status.
- **Startup IP overlay on the player screen** — a new, separate small
  feature requested at the same time (not a fix): see "v1.2.0, part 2 —
  Software update, network configuration and port editing" for the Web
  UI half; the
  player-side half is `src/NetworkInfo.cpp` plus the
  `Renderer::draw_startup_info_overlay`/`Application::show_startup_info_overlay`
  changes, documented in the Changelog entry for this round. Same
  never-built-here caveat applies to that part specifically (SDL2/mpv
  dev headers are not installable in this sandbox — apt's network access
  is blocked here), whereas the two fixes above are Python/JS only and
  were exercised against a real running `config-web.py` the same way as
  the rest of this feature.

### Follow-up after second field feedback

Both fixes above turned out not to be enough once tried on real hardware —
the more detailed error message the first fix introduced is exactly what
made the real cause visible this time.

- **"Update unavailable" still failing, real cause found**: the error now
  shown on the real Pi was `runuser: cannot set user id: Operation not
  permitted`. Root cause: unlike every other privileged operation in this
  module (update, hostname/IP change, NTP...), `check_update()` called
  `runuser`/`git` **directly inside `pidecoder-config.service`'s own
  process**, which runs under a strict systemd sandbox
  (`SystemCallFilter=@system-service`). That filter blocks the UID-change
  syscalls (`setuid`/`setresuid`/...) `runuser` needs, even though the
  service itself runs as root — hence the failure. `check_update()` now
  routes every `git` call through `run_sync_unsandboxed()` (an independent
  `systemd-run` unit, outside the sandbox), exactly like NTP and timezone
  changes already did. Verified against a fake `runuser`/`systemd-run`
  plus a real local Git repository (up to date, behind, no upstream,
  invalid path, with and without a `service_user`).
- **The network-pending overlay stayed up until the countdown ran out,
  even after reconnecting on the new IP**: two compounding causes. First,
  `/api/network/status` (and so the overlay) was only checked when the
  user happened to click back into the Réseau tab after logging back in
  at the new address — the app never proactively checked for a pending
  change right after login. Second, the 45-second auto-revert window was
  too tight once the real cost of clicking the link, loading the page on
  the new origin, and logging in again (new IP = new origin = no shared
  session cookie) was accounted for. Fixed by having `showApp()` call
  `networkRefresh()` immediately on login (so a pending change's overlay
  appears right away, showing accurate remaining time computed from the
  server-side `applied_at` timestamp rather than restarting a fresh
  countdown) and by raising `PENDING_DELAY_SECONDS` from 45 to 120; the
  redirect link's text now also warns that a re-login will be needed.
  Verified structurally (generated script content, API return shape,
  `app.js` syntax) — the actual login-then-overlay timing still needs a
  real-world check on the Pi, this sandbox has no browser/cookie
  environment to reproduce that with.

### Follow-up after third field feedback: dropped the visible countdown

Even with the fixes above, the user reported the confirmation popup still
showed a ticking seconds counter after reconnecting on the new address —
and since the underlying `nmcli` change is applied essentially instantly
in practice, a counter that visibly ticks down was misleading (it implied
waiting was needed) rather than reassuring. Removed the live countdown
display entirely: the overlay now shows a static message and the
"Confirm" button only, no number. The automatic-revert safety net is
unchanged (still 120s, still fires if `/api/network/confirm` is never
called) — only the UI's `setInterval`-based per-second redraw was replaced
with a single silent `setTimeout` armed on the real server-computed
deadline (`renderNetworkPending`/`scheduleNetworkPendingRevertCheck` in
`app.js`); the `networkPendingCountdownValue` element was removed from
`index.html`. Verified via `node --check` syntax validation and i18n key
parity (294 keys, FR/EN) — same testing-limit caveat as above applies to
the actual on-Pi timing/UX.

### Follow-up after fourth field feedback: popup reappearing right after clicking Confirm

The user reported the popup was still there even after clicking to
confirm and following the redirect link. Root cause: a race between
confirmation and the detached script's own auto-revert loop. Clicking
"Confirm" only touched a sentinel file (`confirm_change()` in
`system_admin.py`); it's the detached script's `for i in $(seq 1
{PENDING_DELAY_SECONDS}); do sleep 1; ...; done` loop, on the server side,
that notices that file and flips the status from `"applied"` to
`"confirmed"` — but that loop only checks once per second. The browser,
meanwhile, calls `/api/network/status` again immediately after the
confirm POST returns (`networkConfirmPending()` in `app.js`) — during
that up-to-one-second window the status was still `"applied"`, so
`pending_change()` still returned it, and the popup that had just been
dismissed reappeared right away. Fixed by having `confirm_change()` write
`"confirmed"` to the status file immediately, itself, rather than only
touching the sentinel and waiting for the detached script's next poll
tick (the sentinel file is still touched too, since the detached script
still needs it to know not to revert). This closes the race regardless of
timing. Verified end-to-end with a simulated IP change (delay shortened
for the test only, never in shipped code): status reads `None` from
`pending_change()` immediately after `confirm_change()` returns, no
window where the popup could reappear.

### Follow-up after fifth field feedback: startup overlay never appeared on screen, + MAC address

The user reported the player-side IP/hostname/web-port overlay (see
"Affichage de l'IP..." in the Changelog) simply never showed up on the
actual screen, neither at startup nor via the **I** key. Found on review:
`startup_info_text_` was computed exactly **once**, in `Application`'s
constructor — i.e. before SDL was even initialized, and therefore
potentially before the Pi's network was actually ready (the systemd unit
waits on `network-online.target`, but that's not an absolute guarantee
depending on whether `NetworkManager-wait-online.service` is enabled). If
`getifaddrs()` found no active interface at that exact instant, the text
stayed empty for the **entire remaining process lifetime** — including
for the I key, which only re-read that same frozen (empty) string instead
of recomputing it. Fixed: `show_startup_info_overlay()` now recomputes
the text on every call (both at startup and on I) instead of trusting a
value captured once — which also means I now reflects an IP change made
from the Web UI without needing to restart the player.
`Application::startup_info_text_`'s constructor initializer was removed
accordingly (see the updated comment on that member in
`Application.hpp`).

Also added, per explicit request: the **MAC address** in the overlay
(useful for a DHCP reservation, for instance). `NetworkInfo.cpp` now also
looks up, via `getifaddrs()`, the `AF_PACKET` entry for the *same*
interface that carries the displayed IPv4 address (not an arbitrary
interface's MAC if more than one exists) — e.g. `IP 192.168.1.50 MAC
AA:BB:CC:DD:EE:FF HOTE PIDECODER-PI WEB :8080`.

**Testing**: `NetworkInfo.cpp` (still dependency-free) was compiled and
run here, MAC address included and correctly tied to the chosen
interface. `Application.cpp`/`Application.hpp` were not touched on the
rendering side this round — only when the text is computed — but still
could not be compiled in this sandbox (no SDL2/mpv dev headers, same
long-standing limitation). First thing to check on the Pi after `sudo
./scripts/install.sh`: that the overlay now actually appears, both at
startup and via I, and that it includes the MAC address.

**Confirmed not fixed by the above**: after a clean rebuild (`sudo
./scripts/install.sh` completed without error), the overlay still never
appeared — neither at startup nor via I — while every other on-screen
element (zoom indicator, PTZ overlay, audio button in Focus view, all
using the same `fill_ui_rect`/`draw_text` primitives) displays normally.
That rules out a general rendering-pipeline problem and points at
`startup_network_info_text()` itself returning an empty string on this
specific Pi's real network setup — i.e. `NetworkInfo.cpp`'s
interface-selection heuristic (active, non-loopback, non-link-local)
isn't matching anything there, for a reason not yet identified (no direct
shell access to that Pi from this environment). Added a diagnostic
instead of guessing further: `show_startup_info_overlay()` now logs the
computed text (or `[]` if empty) to stdout, which lands in the systemd
journal (`journalctl -u pidecoder`) since the unit already has
`StandardOutput=journal` — the next round depends on what that shows.

**Text confirmed non-empty on the real Pi**: a standalone compile of
`NetworkInfo.cpp` (zero SDL2/mpv dependency) run directly on
`olympus-vss-mon1` over SSH returned a correct, populated string (`IP
10.0.0.217  MAC 88:A2:9E:B3:CC:F7  HOTE OLYMPUS-VSS-MON1  WEB :8080`) —
ruling out the network-detection theory above. The bug is further down,
in the drawing path (`Renderer::draw_startup_info_overlay` or the
mosaic/Focus render selection) — re-reviewed in detail without finding
anything definitively wrong by inspection alone (box geometry, draw
order, and coordinate conventions all match the other overlays that do
work). Added a second, render-side diagnostic log in
`Renderer::draw_startup_info_overlay` (throttled to log once per
activation via a `static` last-logged-text guard, not every frame):
canvas dimensions and the exact computed box rectangle, to see directly
whether the box ends up off-screen or zero-sized rather than continuing
to guess from code alone. Next round depends on what both logs show, and
on whether the user was testing in mosaic or Focus view (only Focus view
is confirmed working for the *other* overlays, since zoom/PTZ/audio only
ever render there).

**User confirmed both views fail identically** (mosaic and Focus both
show nothing), which — since `draw_startup_info_overlay` is a single
shared function called from both `render()` and `render_focus()` — rules
out a mosaic/Focus-specific divergence and points at that shared function
(or the shared timing state) itself.

**Root cause found**: the journal showed `Overlay info reseau (touche I /
demarrage) : []` on every single call from the real running service —
empty, even though the standalone `NetworkInfo.cpp` test moments earlier,
run over plain SSH on the same Pi, returned a correct populated string.
Same function, same Pi, different result — the difference is the systemd
sandbox. `pidecoder.service.in` sets `RestrictAddressFamilies=AF_UNIX
AF_INET AF_INET6`; on Linux, `getifaddrs()` enumerates interfaces via an
`AF_NETLINK`/`NETLINK_ROUTE` socket, which isn't in that allowlist. The
socket call fails silently (no crash — `getifaddrs()` just returns -1,
already handled gracefully as "no interfaces found"), so
`startup_network_info_text()` deterministically returns empty whenever
called from inside the sandboxed service, while working fine from an
unrestricted shell. The exact same class of bug as the `runuser`/
`SystemCallFilter` issue found for `check_update()` earlier — a
pre-existing hardening directive, written before this feature existed,
that never explicitly allowed what the new feature needs. Fixed by adding
`AF_NETLINK` to `RestrictAddressFamilies` in `systemd/pidecoder.service.in`.

**Confirmed working on the Pi.** The two diagnostic logs added in
`Application.cpp` and `Renderer.cpp` while chasing this were removed
accordingly.

**Overlay presentation reworked** (explicit follow-up request, now that
it's visible): went from one dense line to a small two-line card with a
colored border (same accent hue as the active audio button in Focus
view, for visual consistency) and a thin divider between the lines — line
1 is IP + hostname (what you need most), line 2 is MAC + Web port (more
technical). `NetworkInfo.cpp` now returns the two lines separated by
`\n`; `Renderer::draw_startup_info_overlay` splits on that before calling
`draw_text()` twice (which doesn't interpret `\n` itself). Still built
from the same solid-rectangle-only primitives as the rest of the UI — no
real alpha blending or rounded corners available (see the comments on
`fill_ui_rect`/`draw_text`); the "border" is a solid accent-colored
rectangle with a smaller dark rectangle drawn on top of it, not a real
outline. Box geometry (position/width/height) was checked by hand-running
the same arithmetic in Python across several common resolutions
(640×480 through 4K) with the real text the user's Pi produced — always
on-screen, never zero or negative size. The actual on-screen rendering
still couldn't be verified in this sandbox (still no SDL2/mpv here); to
confirm visually on the Pi.

**Field feedback: card too small — fixed.** After testing on the Pi, the
two-line card was readable but noticeably small. Root cause: `draw_text()`
switches to its "large" bitmap font (`scale = 2`) only when the rectangle
passed to it is at least 32px tall, but the card's line height had been
clamped to a 20–30px range — always below that threshold — so the card was
stuck on the small font (`scale = 1`) regardless of screen size, unlike
the original single-line overlay, which could clear 32px (and so use the
large font) on 720p+ screens. Fixed by raising the line-height clamp to
34–46px (still derived from the screen's shortest dimension, so it stays
proportional), which always clears the 32px threshold and therefore always
gets the large font; border, divider and margins were scaled up to match.
Re-verified with the same Python geometry check across 640×480, 1280×720,
1920×1080 and 3840×2160 with the user's real text — always fully on-screen,
large font (`scale = 2`) reached in every case. Real on-screen rendering
still to be reconfirmed on the Pi.

**Confirmed good on the Pi** ("Ah la c'est bien"). Two follow-up requests
came in right after:

1. **HTTP and HTTPS on two independent ports.** Until now the Web admin
   interface only ever listened on one port (8080 by default), serving
   either HTTP or HTTPS depending on whether a certificate was active —
   toggling HTTPS from the Sécurité tab made the other protocol disappear
   rather than coexist with it. Per explicit request, `config-web.py` now
   runs two `ThreadingHTTPServer` instances in parallel (one per thread):
   HTTP on `--port` (default 8080, unchanged) whenever
   `config/http-disabled` is absent, HTTPS on the new `--https-port`
   (default 8443) whenever a certificate is present — the same
   presence/absence mechanism HTTPS already used, now made symmetric for
   HTTP too. A shared guard on both `/api/tls/disable` and
   `/api/http/disable` refuses to turn off the last remaining protocol
   (would lock out the Web UI entirely), and `main()` has one more
   fallback layer: if both ever ended up disabled on disk at once (manual
   edit, for instance), HTTP is forced on rather than binding nothing.
   `install.sh` gained `--https-port`; the update flow
   (`system_admin.start_update`) now re-passes both `--port` and
   `--https-port` to the re-invoked `install.sh`, to avoid a custom HTTPS
   port silently resetting to the 8443 default on every update — the same
   class of bug as the static-IP concern below, just for ports instead of
   network config, and actually prevented here rather than found after the
   fact. The Sécurité tab gained a second panel ("Accès HTTP") mirroring
   the HTTPS one; the player's startup overlay now shows both ports
   (`WEB 8080/8443`, see `NetworkInfo.cpp`) since it has no way to know
   which protocol is actually active at any given moment.

   **Tested**: unlike most other backend work in this sandbox, the bulk of
   this change (all of it, except the actual systemd service restart) is
   pure Python with no SDL2/mpv dependency, so it was exercised directly —
   a real `config-web.py` process was started here with both ports bound,
   logged into over both HTTP and HTTPS, and every enable/disable
   combination was driven through curl, including the cases that must be
   refused (turning off the last remaining protocol) and a cert
   regenerate/reload requested over HTTP while confirming the *HTTPS*
   listener picked up the new certificate (cross-port state, the trickiest
   part of this change). This test caught and fixed a real bug before
   delivery: the HTTP port reported by `/api/tls/status` was sometimes the
   HTTPS port's value instead, depending on which port the request arrived
   through (`_make_server()` was conflating "port this instance binds to"
   with "the configured HTTP port constant"). What remains untested here:
   the actual `systemctl restart` triggered by the Sécurité tab toggles
   (the `systemd-run` binary is present in this sandbox but doesn't drive
   real services here) and the real browser UX across two ports/self-signed
   certs. First real test recommended with a single unit on hand before
   rolling out further, just in case.

   **Confirmed working on the Pi** — HTTP/HTTPS toggling exercised from the
   Sécurité tab ("c'est bien").

2. **Static IP "reverting to DHCP after an update" — not actually caused
   by the update.** Re-read all of `start_update`/`install.sh`: neither
   touches network configuration at all. The only thing in PiDecoder that
   ever reverts a static IP to DHCP is the IP-change safety net itself
   (auto-revert if `/api/network/confirm` isn't called within ~120s — see
   "Follow-up after third/fourth field feedback" above), unrelated to
   updates. The user confirmed they weren't sure they'd seen/clicked the
   confirm popup at the time — most likely explanation: an earlier,
   unconfirmed IP change quietly auto-reverted, and the coincidence with a
   later, unrelated update created the impression of a link. The three
   fixes already shipped earlier in this section (proactive check on
   login, no more misleadingly-fast visible countdown, race-condition fix
   on confirm) should already prevent a missed confirmation going forward.
   **Confirmed by the user**: a static IP survived a subsequent update
   ("il a bien garder l'ip manuel après update").

3. **Editing the HTTP/HTTPS port numbers from the Web UI**, asked right
   after, with two explicit design choices from the user: build it now,
   and restart `pidecoder.service` (the video engine) immediately so the
   player's own overlay reflects the new ports right away, accepting a
   brief video interruption rather than waiting for the next natural
   restart. New "Ports de l'administration Web" panel in the Sécurité tab
   (two number fields pre-filled with the current ports, an Apply button),
   backed by a new `/api/tls/set-ports` endpoint and
   `system_admin.start_port_change()`. Rather than regenerating the two
   systemd unit files from their `.in` templates (the other placeholder
   values — service user, group, uid/gid — aren't persisted anywhere after
   install, so re-deriving them here would duplicate `install.sh`'s own
   detection logic for no benefit, since only the two ports actually
   change), `start_port_change()` directly regex-patches the already
   -rendered `pidecoder-config.service` (`--port`/`--https-port` on its
   `ExecStart`) and `pidecoder.service` (`PIDECODER_WEB_PORT`/
   `PIDECODER_WEB_HTTPS_PORT` environment lines — the same ones
   `NetworkInfo.cpp` reads for the overlay), then `daemon-reload`s and
   restarts both services. Unlike the IP/hostname flow, there is
   deliberately **no pending/confirm/120s-auto-revert safety net**: a bad
   port number can never lock the user out of the Pi's network or SSH
   access the way a bad IP can, so the extra complexity wasn't worth it.
   Validation (1–65535, HTTP and HTTPS must differ) is enforced server-side
   via a new `validate_port()`, not just in the form.

   **Tested**: same sandbox-executable Python as the dual-port feature
   above, so exercised directly. `start_port_change`'s unit-file-editing
   logic was run against real unit files generated by `install.sh` (same
   templates as the Pi) and the result diffed line by line — only the two
   port values and the two environment lines changed, nothing else.
   `/api/tls/set-ports` was tested against a live `config-web.py` process:
   invalid ports rejected, identical HTTP/HTTPS ports rejected, valid ports
   accepted with the correct `redirect_url`. As with the dual-port feature,
   the actual `systemctl restart` of both services could not be exercised
   here — first real test on the Pi should confirm both the video engine's
   brief restart and the overlay showing the new ports.

## v1.1 — audio support (validated on hardware, merged to `main`)

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

- `Player` (`role_ == PlayerRole::Focus`): `configure()` sets `aid`
  (mpv's audio-track-selection property) to `"no"` or `"auto"`
  depending on the current mute state, instead of a blanket
  `audio=no` — also re-applied by `configure()` on every reconnect,
  so a transient RTSP drop does not silently reset the user's choice.
  Grid-role players are unchanged (`audio=no`, always silent). New
  methods: `set_muted(bool)`, `muted()`, `has_audio_track()` (scans
  mpv's `track-list` for an entry of type `"audio"` — this works
  whether or not the audio track is currently selected/decoding,
  unlike the codec-name property used in an earlier version of this
  beta; see the "Regression" note below for why that distinction
  matters);
- **regression found and fixed during field testing**: the first cut
  of this feature set `aid=auto` (decode audio) unconditionally as
  soon as Focus opened, and only used the `mute` property to silence
  playback. That's what broke video playback — muted or not — with a
  visible frame lag and slow-motion effect the user had already fixed
  once, early in the project, before this beta existed. Root cause:
  Focus's `video-sync` option is set to `"audio"` (see below), a
  setting that had been inert for a long time because Focus never
  actually decoded audio (`audio=no`) — with no real audio clock to
  reference, mpv fell back to its own internal timing, which is the
  stable behavior that had been tuned in. The moment `aid=auto` made
  mpv decode a real (and, over RTSP, often irregular/jittery) audio
  stream, `video-sync=audio` started actually doing its job: pacing
  the video to match that audio clock, which is exactly what produced
  the lag/slow-motion. The fix keeps `video-sync=audio` untouched (it
  is the originally validated setting) and instead keeps `aid=no`
  — audio not decoded at all — for as long as the camera stays muted,
  which is the default and by far the most common state. Audio
  decoding, and therefore any dependency on the audio clock, now only
  turns on for the brief window where the user has explicitly pressed
  M or clicked the audio button;
- `Application`: **M** toggles `focus_player_`'s mute state while a
  camera is in Focus (`SDLK_m`, alongside the existing `SDLK_ESCAPE`/
  `SDLK_f` handling). The mute state can also be toggled with the
  **mouse**, by clicking the audio button described below — same
  outcome as pressing M;
- the audio button follows the exact same show/hide principle as the
  existing PTZ overlay: it appears on any mouse movement inside the
  Focus view (regardless of whether the current camera has PTZ), is
  shown immediately when Focus opens (so it's discoverable without
  having to move the mouse first), and auto-hides after 5 seconds of
  inactivity (`audio_indicator_duration_`, now matching
  `ptz_overlay_timeout_` — it was 2 seconds in the keyboard-only
  version of this beta);
- `Renderer`: `draw_audio_indicator()` draws a clickable bordered
  square button, bottom-right of the Focus view, same size as a PTZ
  button (34–46px, scales with window size) so it looks consistent
  with the PTZ pad. When the current camera has a PTZ overlay shown
  in that same corner, the audio button shifts to sit just to its
  left instead, so the two never overlap; otherwise it sits directly
  in the bottom-right corner. `audio_button(canvas_width,
  canvas_height, ptz_available)` computes that position and is shared
  between drawing and hit-testing;
- no text label anymore — just a small pixel-art speaker icon
  (a body + a flared horn drawn as stepped bars, same style as the
  PTZ arrow icons), colored blue (active/unmuted), grey (muted or no
  audio track), with a red bar drawn across it specifically when
  muted (there's no diagonal-line primitive available, so a full-width
  bar stands in for the usual "muted speaker" cross); a camera with no
  audio track at all shows a dimmer grey icon with no bar, since
  there's nothing to mute;
- new `audio_button_hit_at(logical_x, logical_y, ptz_available)`
  mirrors `ptz_command_at`'s coordinate conversion to hit-test a click
  against that button; `Application::process_sdl_event` checks it
  (while the button is visible), passing `focused_camera_has_ptz()` so
  the hit-test uses the same position as the draw call, right before
  the generic single-left-click pan handler, so a click on the button
  toggles mute instead of starting a pan;
- clicking the button when the current camera has no audio track at
  all still shows the indicator but does nothing audible, same as
  pressing M in that situation.

**Per-camera "has a microphone" setting, and a real mosaic bug it
fixes** — added after field testing surfaced a serious regression:

- new checkbox in the Web config, per camera, under "cams.audio_enabled"
  ("a un micro (audio)" / "has a microphone (audio)"), **unchecked by
  default** for every existing and newly-added camera. Persisted as
  `audio_enabled` (top-level, alongside `enabled`) in `cameras.json`;
  `sanitize()` in `config-web.py` defaults it to `false`, and it is
  explicitly preserved (not reset) when a camera is re-discovered/
  updated via ONVIF, same as the existing `enabled` field;
- native side: `CameraConfig::audio_enabled` is read by `Config::load`
  and passed into `Player`'s constructor as a new `audio_capable`
  argument (`Player::audio_capable_`, defaults to `false` so any
  existing call site that doesn't pass it keeps working). Both
  `Application::initialize_players()` (grid) and `open_focus()` pass
  each camera's `audio_enabled` through;
- **root cause found and fixed**: it turned out *any* RTSP camera
  whose stream carries an audio track — regardless of brand or codec —
  broke the mosaic with a frame lag that grew over time, even on
  `main` (v1.0.0), with zero relation to the Focus audio feature.
  Reproduced identically with an Axis camera (mic enabled) and an
  Aqara G410 intercom. Root cause: the mosaic's UDP demuxer settings
  are deliberately extreme for minimum latency
  (`max_delay=0,reorder_queue_size=0`, tuned against single-video-
  stream cameras) and don't tolerate a second (audio) RTP stream
  interleaved on the wire — unlike Focus, which uses TCP and was
  never affected. Fix: `Player::configure()` now only applies those
  extreme UDP settings to cameras where `audio_capable_` is false;
  cameras flagged as having a microphone get a slightly relaxed set
  (`max_delay=200000`, `reorder_queue_size=8`, `analyzeduration=500000`,
  `probesize=32768` — still far below FFmpeg's own defaults). Every
  other camera (the vast majority, unflagged) keeps the exact
  settings that were already proven stable, byte for byte — zero
  behavior change for them;
- this same flag also now gates the Focus audio button entirely:
  `Player::audio_capable()` (new accessor) is checked by
  `Application::audio_indicator_visible()`, so the button/icon never
  appears at all — not even dimmed — for a camera whose box isn't
  checked, and `has_audio_track()` / `set_muted()` short-circuit the
  same way (audio is never decoded for such a camera, whatever the
  user presses);
- **validated on hardware, partially**: fixed the mosaic lag for the
  Axis camera with its mic enabled — this is the validated hardware
  configuration for v1.1.0 (see `docs/faq.md` and
  `docs/configuration.md`). The Aqara G410 intercom still shows some
  trouble even with the box checked — flagged by the user as low
  priority for now (not investigated further yet), and does not block
  video-only use of the G410.

**Follow-up round after field testing** (checkbox label, a new global
default, and a UI pass):

- the per-camera checkbox label was shortened from "a un micro
  (audio)" / "has a microphone (audio)" to a single word, **"Audio"**
  (same in both languages) — the longer explanation moved to the
  checkbox's tooltip (`cams.audio_enabled_hint`) instead;
- new **global** (not per-camera) setting in the Web config's
  Disposition/Layout tab, right next to "Plein écran au démarrage" /
  "Fullscreen on startup": **"Micro actif par défaut en plein écran"**
  / "Microphone on by default in fullscreen". Off by default, like
  its neighbour. Persisted as `focus_audio_default_on` in
  `layout.json` (`LayoutConfig::focus_audio_default_on`,
  `LayoutStore::load`/`save`). When on, `Application::open_focus()`
  calls `focus_player_->set_muted(false)` right after creating the
  Focus player instead of leaving it at its muted-by-default state.
  Has no effect on a camera whose own "Audio" box isn't checked —
  `Player::set_muted()` already only ever turns decoding on when
  `audio_capable_` is true, so nothing needed to change there;
- **all the boolean checkboxes across the Web config** (camera
  "active", camera "Audio", layout "Plein écran au démarrage", layout
  "Micro actif par défaut") now render as on/off slider toggles
  instead of plain checkboxes — a pure visual change (new `.switch`
  CSS component in `app.css`; same underlying `<input
  type="checkbox">` elements and `id`/`class` names, so none of the
  read/write JS logic changed).

**Known, deliberately deferred scope** for this beta:

- no volume level control — only mute/unmute. mpv's own volume stays
  at its default (100%);
- no per-camera memory of the user's mute choice beyond the new global
  default above (still no *per-camera* override of that default).

Built and field-tested on the Raspberry Pi (`feature/v1.1-audio-focus`):
the user confirmed the tests passed and approved the release. Version
bumped to **1.1.0** in `CMakeLists.txt`, `scripts/config-web.py`,
`scripts/install.sh` and `scripts/validate-release.sh`; hardware
compatibility documented in `docs/configuration.md` and `docs/faq.md`.
Merged into `main` and tagged `v1.1.0`.

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
