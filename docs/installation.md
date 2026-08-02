# Installation and updates

This guide covers the public installer included with PiDecoder v0.9.9.4 RC1.

> [!IMPORTANT]
> PiDecoder is currently validated on a Raspberry Pi 5 running Debian 13, AArch64 and Wayland.
> Upgrades of an existing installation have been tested on real hardware.
> A completely fresh installation on a blank system and a forced rollback test are still pending before the stable v1.0 release.

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

Open:

```text
http://RASPBERRY_PI_IP:8080
```

Default Web username:

```text
admin
```

> [!WARNING]
> The current administration interface uses HTTP.
> Do not expose port 8080 directly to the Internet.
> Keep it on a trusted management network or behind an appropriate secured reverse proxy.

## Safe updates

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

## Installer options

```text
--user USER              Desktop/Wayland user running the video wall
--target PATH            Installation directory (default: /opt/pidecoder)
--wayland-display NAME   Wayland socket name (default: wayland-0)
--bind ADDRESS           Web administration bind address (default: 0.0.0.0)
--port PORT              Web administration port (default: 8080)
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
