# Installation and updates

This guide covers the public installer included with PiDecoder.

> [!IMPORTANT]
> PiDecoder is currently validated on a Raspberry Pi 5 running Debian 13, AArch64 and Wayland.
> Upgrades of an existing installation have been tested on real hardware.
> A completely fresh installation on a blank system and a forced rollback test have also been validated.

## Supported target

| Component | Validated configuration |
|---|---|
| Hardware | Raspberry Pi 5 |
| Operating system | Debian 13 |
| Architecture | AArch64 |
| Display server | Wayland |
| Video engine | libmpv / FFmpeg |
| Rendering | SDL2 |
| Administration | Python 3 Web service |

Other Debian-based systems may work, but they are not currently part of the validated v1.0 target.

## Before installation

PiDecoder requires:

- a graphical user with an active Wayland session;
- network access to the RTSP cameras;
- administrative access through `sudo`;
- an interactive terminal for the first Web administrator password;
- a Raspberry Pi configured to start its graphical session automatically when used as a dedicated display.

The installer adds the selected graphical user to the `video` and `render` groups when those groups exist. A session reconnect may be required after a first installation.

## 1. Clone the repository

```bash
git clone https://github.com/PiDecoder/PiDecoder.git
cd PiDecoder
```

## 2. Run the preflight check

```bash
sudo ./scripts/install.sh --check
```

The preflight check does not modify the host. It validates:

- the operating system and architecture;
- the graphical user;
- the expected Wayland socket;
- installed dependencies;
- Python sources;
- shell scripts;
- CMake metadata;
- example JSON files;
- required project files.

When the graphical user cannot be detected automatically:

```bash
sudo ./scripts/install.sh --check --user YOUR_DESKTOP_USER
```

A successful preflight ends with:

```text
Contrôle terminé — aucune modification effectuée
```

Node.js is optional. When it is not installed, the embedded JavaScript syntax check is skipped; Node.js is not required to run PiDecoder.

## 3. Install PiDecoder

```bash
sudo ./scripts/install.sh
```

Or specify the graphical user explicitly:

```bash
sudo ./scripts/install.sh --user YOUR_DESKTOP_USER
```

The installer:

1. installs the required Debian packages;
2. validates SDL2 and libmpv through `pkg-config`;
3. backs up an existing installation;
4. preserves camera, layout and Web authentication files;
5. builds PiDecoder in release mode;
6. installs the application under `/opt/pidecoder`;
7. creates the systemd units for the selected user and Wayland socket;
8. enables the Web service and Wayland path trigger;
9. starts the video engine when the Wayland socket and at least one active camera are available.

On a first installation, the installer asks for the password of the Web account named `admin`. The password must contain at least eight characters.

## 4. Open the administration interface

Open, over HTTP or HTTPS (both are active by default, on their own port):

```text
http://RASPBERRY_PI_IP:8080
https://RASPBERRY_PI_IP:8443
```

The browser will show a certificate warning the first time over HTTPS — see
[HTTPS and TLS certificates](#https-and-tls-certificates) below. Both ports
can be changed, or either protocol turned off, from the Security tab once
logged in (see [Changing the certificate later](#changing-the-certificate-later-without-reinstalling)
and [Enabling/disabling HTTP or HTTPS from the Web UI](#enablingdisabling-http-or-https-from-the-web-ui)).

Default Web username:

```text
admin
```

If you don't know the Pi's IP address, connect a screen to it: PiDecoder
shows its IP, hostname, MAC address and both Web ports as an overlay for
30 seconds at startup, and again at any time by pressing the **I** key.

> [!WARNING]
> Keep the administration interface on a trusted management network, or
> behind an appropriate secured reverse proxy, even over HTTPS — the
> certificate is self-signed by default (see below), which authenticates
> the Pi to a browser that has already accepted it, but is not equivalent
> to a certificate from a public authority.

## Safe updates

Since this version, an equivalent one-click update is also available from
the Web administration interface — see
[Software update from the Web UI](#software-update-from-the-web-ui) below.
The manual steps below still work and remain the only option on an
installation that predates this feature (identifiable by an "update
unavailable" message on that page).

Update the repository and run the same installer again:

```bash
cd PiDecoder
git pull
sudo ./scripts/install.sh
```

The installer preserves these runtime files when they exist:

```text
/opt/pidecoder/config/cameras.json
/opt/pidecoder/config/layout.json
/opt/pidecoder/config/web-auth.json
/opt/pidecoder/config/backups/
```

Before replacing an existing installation, it creates a timestamped backup under:

```text
/var/backups/pidecoder/YYYYMMDD-HHMMSS/
```

See [Backup and restore](backup.md) for details.

### `git pull` alone does not update a running installation

`pidecoder-config.service` runs the files under `/opt/pidecoder/` — a
physical copy made by `install.sh` (`cp -a`), separate from the Git
checkout. Running `git pull` in the checkout only updates the checkout
itself; it does **not** touch `/opt/pidecoder`, and restarting the
service afterwards just re-runs the same files that were already there.
To pick up changes, run `sudo ./scripts/install.sh` again as shown above.

For quick iteration on `scripts/` (Python, Shell, or the Web UI) during
development, `scripts/sync-dev.sh` copies just those files into
`/opt/pidecoder/scripts/` and restarts `pidecoder-config.service`,
without the full installer's native-engine rebuild and service restarts
(it does not touch the video engine or `config/`):

```bash
sudo bash scripts/sync-dev.sh
```

This is a development convenience only — it is not part of the supported
install/upgrade path and is not a substitute for `install.sh` on a
production deployment.

## Installer options

```text
--user USER              Desktop/Wayland user running the video wall
--target PATH            Installation directory (default: /opt/pidecoder)
--wayland-display NAME   Wayland socket name (default: wayland-0)
--bind ADDRESS           Web administration bind address (default: 0.0.0.0)
--port PORT              Web administration HTTP port (default: 8080)
--https-port PORT        Web administration HTTPS port (default: 8443).
                          Must differ from --port.
--tls-cert PATH          Import a TLS certificate (PEM) instead of generating a
                          self-signed one. Requires --tls-key.
--tls-key PATH           Import the matching TLS private key (PEM). Requires
                          --tls-cert.
--no-https               Do not install a certificate; serve the Web
                          administration interface over plain HTTP only at
                          install time. Mutually exclusive with --tls-cert/--tls-key.
                          HTTPS can still be turned on later, with a
                          certificate, from the Security tab.
--skip-deps              Do not run apt-get
--no-start               Install and enable units without starting them
--check                  Validate the host and source without changing anything
-h, --help               Show the installer help
```

Example with explicit values:

```bash
sudo ./scripts/install.sh \
  --user admin \
  --wayland-display wayland-0 \
  --bind 192.168.1.50 \
  --port 8080
```

`--skip-deps` is intended for controlled environments where all required packages are already installed.

The environment variable below allows installation on a non-Debian host, but that platform remains unsupported:

```bash
sudo PIDECODER_ALLOW_UNSUPPORTED=1 ./scripts/install.sh
```

## HTTPS and TLS certificates

The Web administration interface serves HTTP and HTTPS at the same time,
each on its own independent port — 8080 and 8443 by default. Either one
can be turned off on its own (see
[Enabling/disabling HTTP or HTTPS from the Web UI](#enablingdisabling-http-or-https-from-the-web-ui)
below), but not both at once, so the interface can never lock itself out.

On a fresh install, if no certificate is imported, `install.sh` generates a
self-signed one covering the Pi's hostname and its detected local IPv4
addresses:

```bash
sudo ./scripts/install.sh
```

The browser shows a certificate warning the first time — this is expected
for a self-signed certificate on a device with no public domain/DNS, similar
to most LAN admin interfaces (router, NAS...). Accept it once to continue.

On an upgrade, an existing certificate is preserved as-is; it is not
regenerated.

### Installing without HTTPS

```bash
sudo ./scripts/install.sh --no-https
```

No certificate is installed and the service starts in plain HTTP. This
cannot be combined with `--tls-cert`/`--tls-key`.

### Importing your own certificate

```bash
sudo ./scripts/install.sh \
  --tls-cert /path/to/cert.pem \
  --tls-key /path/to/key.pem
```

Both files must be PEM-encoded and form a matching pair — the installer
verifies this (certificate validity and a public-key comparison against the
key) before installing them, and refuses a mismatched pair.

### Changing the certificate later, without reinstalling

`install.sh` rebuilds the native engine and stops every service — not
practical just to switch a certificate. Use `scripts/manage-tls.sh` instead,
which only touches `config/tls/` and restarts `pidecoder-config.service`:

```bash
sudo ./scripts/manage-tls.sh status              # current state
sudo ./scripts/manage-tls.sh generate [--force]  # new self-signed certificate
sudo ./scripts/manage-tls.sh import --cert PATH --key PATH
sudo ./scripts/manage-tls.sh disable             # switch to plain HTTP
sudo ./scripts/manage-tls.sh enable              # restore/regenerate
```

`disable` moves the active certificate aside (`cert.pem.disabled` /
`key.pem.disabled`) instead of deleting it, so `enable` can restore the exact
same certificate later.

### Enabling/disabling HTTP or HTTPS from the Web UI

The Security tab has two panels, "HTTPS" and "Accès HTTP" (HTTP access),
mirroring each other: each lets you generate or import a certificate,
switch the corresponding protocol on or off, and see its current status,
without leaving the browser or touching SSH. Turning off the last
remaining protocol is refused with a clear message, since that would cut
off all access to the interface.

### Changing the HTTP/HTTPS port numbers

A third panel, "Ports de l'administration Web" (Web administration
ports), lets you change the two port numbers directly, without a full
reinstall. Applying a change restarts both the Web administration service
and the video engine — a brief interruption of the on-screen video — so
the startup overlay (IP/hostname/MAC/ports, see [step 4](#4-open-the-administration-interface))
reflects the new ports immediately instead of waiting for the next
natural restart. Unlike the hostname/IP change described below, there is
no confirmation step or automatic rollback: a wrong port number can never
lock you out of the Pi's network or SSH access the way a wrong IP address
can.

## Software update from the Web UI

The Système tab includes an update panel: it checks the Git repository
against its tracked remote branch and, if a newer commit is available,
shows a "Update now" button. Clicking it runs the same `git pull` +
`sudo ./scripts/install.sh` sequence described in
[Safe updates](#safe-updates) above, in the background, and streams the
progress and log output back to the page — including through the service
restart that `install.sh` performs at the end, which briefly interrupts
the page's connection to the server.

This requires `--repo-path` to have been recorded during installation,
which happens automatically as of this version. On an installation from
before this feature, the panel shows a message asking to run
`sudo ./scripts/install.sh` once from the Git clone to enable it — this is
a one-time, harmless re-install with no other effect.

If `install.sh` fails partway through (a build error, a missing
dependency...), its own existing rollback restores the previous
`/opt/pidecoder` and restarts the services automatically, exactly as it
would for a manual update — the Web UI update button does not change this
safety behavior, only how the update is triggered.

## Network configuration from the Web UI

The Réseau tab lets you change the Pi's hostname, switch a network
connection between DHCP and a manual (static) IP address, configure NTP
time servers, and set the timezone — without needing SSH access.

Because a mistake in the hostname or IP address could otherwise cut off
access to the Pi remotely, both of those changes include an automatic
safety net: the new value is applied immediately, and a full-screen
overlay with a "Confirm this change" button appears — checked for
automatically as soon as you log back in, even in a fresh browser tab, so
you don't need to remember to click back into the Réseau tab. If the
change isn't confirmed within 120 seconds, the Pi automatically reverts
to the previous value. This safety net runs on the Pi itself and does not
depend on your browser successfully reconnecting — it is designed
specifically for the case where the change makes the page briefly or
permanently unreachable at its old address.

Practical notes:

- If you change the IP address, the page will likely become unreachable
  at its old URL; reconnect at the new address within the 120-second
  window to confirm the change (the overlay gives you a direct link to
  the new address), or it will revert on its own.
- NTP and timezone changes are lower-risk (they cannot affect network
  reachability) and apply immediately without a confirmation step.
- As with any change to the Pi's network configuration, keep a fallback
  way to reach the device (a keyboard and monitor connected directly, or
  a second SSH session over a connection that does not depend on the
  address being changed) the first few times you use the IP/DHCP toggle,
  until you are comfortable with how it behaves on your network.

## Startup architecture

PiDecoder uses three systemd units:

```text
pidecoder-config.service
└── Web administration service

pidecoder-wayland.path
└── watches /run/user/<uid>/wayland-0
    └── starts pidecoder.service
        └── native RTSP video wall
```

The video service is intentionally not enabled directly. It is started by `pidecoder-wayland.path` only after the Wayland socket exists.

Therefore this output is normal:

```bash
systemctl is-enabled pidecoder.service
```

```text
disabled
```

The units that should be enabled are:

```bash
systemctl is-enabled pidecoder-config.service
systemctl is-enabled pidecoder-wayland.path
```

## Service status

```bash
systemctl status pidecoder-config.service --no-pager
systemctl status pidecoder-wayland.path --no-pager
systemctl status pidecoder.service --no-pager
```

Quick active-state check:

```bash
systemctl is-active pidecoder-config.service
systemctl is-active pidecoder-wayland.path
systemctl is-active pidecoder.service
```

The video service may remain inactive when:

- no active camera is configured;
- the camera configuration is invalid;
- the graphical session is not running;
- the selected Wayland socket does not exist yet.

## Logs

```bash
journalctl -u pidecoder-config.service -n 50 --no-pager
journalctl -u pidecoder.service -n 50 --no-pager
```

Current-boot logs:

```bash
journalctl -b -u pidecoder-config.service --no-pager
journalctl -b -u pidecoder.service --no-pager
```

> [!WARNING]
> Camera URLs and logs may contain private IP addresses, usernames or passwords.
> Redact them before sharing logs or opening a public issue.

## Useful paths

| Purpose | Path |
|---|---|
| Installation | `/opt/pidecoder` |
| Executable | `/opt/pidecoder/bin/pidecoder` |
| Cameras | `/opt/pidecoder/config/cameras.json` |
| Layout | `/opt/pidecoder/config/layout.json` |
| Web authentication | `/opt/pidecoder/config/web-auth.json` |
| Runtime configuration backups | `/opt/pidecoder/config/backups/` |
| Installer backups | `/var/backups/pidecoder/` |
| systemd units | `/etc/systemd/system/` |

## Next steps

After installation:

1. open the Web administration interface;
2. add a camera manually or through ONVIF;
3. configure the mosaic layout;
4. click **Sauvegarder** to store the configuration;
5. click **Appliquer** to restart the video engine with the new configuration.

Continue with:

- [Camera configuration](configuration.md)
- [ONVIF camera setup](onvif.md)
- [Mosaic layout](layout.md)
- [Backup and restore](backup.md)
- [FAQ and troubleshooting](faq.md)
