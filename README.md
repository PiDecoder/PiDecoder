<p align="center">
  <img
    src="docs/images/hero-banner.png"
    width="100%"
    alt="PiDecoder — RTSP and ONVIF Video Wall for Raspberry Pi"
  >
</p>

<p align="center">
  <a href="https://github.com/PiDecoder/PiDecoder/actions/workflows/validate.yml">
    <img src="https://github.com/PiDecoder/PiDecoder/actions/workflows/validate.yml/badge.svg" alt="Validation">
  </a>
  <img src="https://img.shields.io/badge/release-v1.2.0-7A1F5C" alt="Release v1.2.0">
  <img src="https://img.shields.io/badge/platform-Raspberry%20Pi%205-C51A4A" alt="Raspberry Pi 5">
  <img src="https://img.shields.io/badge/OS-Debian%2013-A81D33" alt="Debian 13">
  <img src="https://img.shields.io/badge/license-GPLv3-2EA44F" alt="GPLv3">
</p>

<p align="center">
  <strong>A fast, lightweight and reliable RTSP & ONVIF video wall for Raspberry Pi.</strong>
</p>

<p align="center">
  PiDecoder turns a Raspberry Pi 5 into a dedicated multi-camera display with a native video engine,
  ONVIF discovery, native PTZ controls, flexible layouts and a modern Web administration interface.
</p>

---

> [!NOTE]
> **PiDecoder v1.2.0** is the current stable release. It adds HTTPS for the Web
> administration interface (HTTP and HTTPS on two independent, editable ports),
> a one-click software update and a full network configuration panel (hostname,
> DHCP/static IP, NTP, timezone) with automatic rollback on a lockout-prone change,
> and an on-screen IP/hostname/MAC/port overlay at startup — on top of the native
> audio support introduced in v1.0.0 and v1.1.0.
> It is validated on a Raspberry Pi 5 running Debian 13 and Wayland.
> Native PTZ movement, optical zoom, Stop and preset selection are available and have been
> field-tested with an Axis Q6074.
>
> HTTPS is on by default with a self-signed certificate generated on first install; the
> certificate, the HTTP/HTTPS ports and either protocol's on/off state can all be changed
> from the Security tab without SSH access. The hostname/IP/NTP/timezone panel and the
> one-click update button have been field-tested and had several real bugs fixed as a
> result — see [`CHANGELOG.md`](CHANGELOG.md) for the full trail. NTP and timezone changes
> specifically have not had a dedicated field test, though they share the same proven
> mechanism as the hostname/IP change.
>
> Audio is opt-in per camera and validated with an Axis camera (RTSP stream with an enabled
> microphone). The Aqara G410 intercom has a known residual audio issue that does not affect
> video-only use — see [`docs/faq.md`](docs/faq.md#is-audio-available) for details.
>
> The Web interface also protects stored ONVIF and PTZ metadata when camera video settings are
> changed, including when an older browser tab submits a camera without that metadata.
>
> The upgrade path, configuration preservation, automatic startup and an 8+ hour continuous run
> were validated during the release-candidate phase. A fresh installation on a blank Debian 13
> system, Web configuration restore and a forced-failure installer rollback were also
> successfully validated.
>
> The blank-system installation test was performed on an x86_64 virtual machine.
> Raspberry Pi 5 AArch64 remains the official validated hardware target.
>
> The Web administration interface is bilingual (French/English), with a toggle on the login
> screen and in the application header; the language choice is remembered in a cookie. Some
> low-level ONVIF client error messages and a few backend-generated diagnostic terms still
> appear in French regardless of the selected language.

## Why PiDecoder?

PiDecoder focuses on one job: displaying IP cameras reliably without the weight and complexity of a full Video Management System.

<table>
  <tr>
    <td width="25%" valign="top">
      <strong>Fast</strong><br>
      Native C++ video wall built around SDL2 and libmpv.
    </td>
    <td width="25%" valign="top">
      <strong>Lightweight</strong><br>
      Designed specifically for Raspberry Pi 5 and continuous display.
    </td>
    <td width="25%" valign="top">
      <strong>Practical</strong><br>
      Configure cameras, layouts, ONVIF and services from a Web interface.
    </td>
    <td width="25%" valign="top">
      <strong>Open</strong><br>
      GPLv3 project built around RTSP, ONVIF and standard Linux tools.
    </td>
  </tr>
</table>

## Features

| Video wall | Audio | ONVIF and PTZ | Layout | Administration |
|---|---|---|---|---|
| Multiple RTSP streams | Native playback in the focus view, opt-in per camera | Automatic discovery | Drag and drop reordering | Bilingual (FR/EN) Web interface |
| H.264 playback | Mute/unmute with the speaker button or the **M** key | Manual IPv4 addition | Resize camera tiles | System diagnostics (CPU, memory, temperature, throttling) |
| Automatic reconnection | Auto-hiding audio button, mirroring the PTZ overlay | Profile and preset detection | Uniform, main-camera and free layout templates | Configurable log viewer (20/50/100 lines) |
| Fullscreen focus view | "Audio on by default" toggle in Layout | Native pan and tilt | Persistent, auto-saved configuration | Notification history with unread counter |
| Digital zoom and pan | Mosaic stays silent by design, whatever the setting | Optical zoom and forced Stop | Full screen at startup toggle | Keyboard shortcuts panel |
| On-screen digital zoom percentage | Per-camera flag also protects mosaic latency for cameras without audio | Native preset selector | Grid-too-small guardrails | Configuration export and import |
| Native Raspberry Pi display (SDL2/OpenGL, no browser needed) | | PTZ overlay auto-hide | | Rate-limited authentication with lockout |
| On-screen IP/hostname/MAC/Web-port overlay, 30s at startup or on demand with the **I** key | | | | One-click software update check and install |
| | | | | Hostname, IP (DHCP/static), NTP and timezone configuration, with automatic rollback |
| | | ONVIF/PTZ metadata preserved on camera save | | HTTPS by default, HTTP and HTTPS on two independent ports, each individually enabled/disabled |
| | | | | HTTP/HTTPS ports editable, and TLS certificate managed, from the Web UI (no SSH needed) |
| | | | | Ready-to-flash SD card image, with per-device identity generated at first boot |
| | | | | Link to the [GitHub repository](https://github.com/PiDecoder/PiDecoder) in the header |
| | | | | systemd sandboxing per service, credential redaction in logs |

## Native PTZ controls

When a configured camera contains valid ONVIF PTZ metadata, opening its native focus view displays a compact PTZ overlay.

Available controls:

- pan left and right;
- tilt up and down;
- optical zoom out and in;
- forced Stop;
- preset selection through a compact drop-down menu.

The controls disappear after five seconds without mouse activity and reappear as soon as the pointer moves. They remain visible while a PTZ command or preset menu is active.

Safety stops are sent when the pointer is released, leaves the active control, the window loses focus, the focus view closes or Escape is pressed.

Fixed cameras do not display the PTZ overlay.

## Video profile guidance

Use a lightweight stream for the mosaic and a higher-quality stream for the focus view.

Typical PiDecoder defaults:

| View | Resolution | Frame rate |
|---|---:|---:|
| Mosaic | 640 × 360 | 12 FPS |
| Focus | 1920 × 1080 | 25 FPS |

Some cameras limit the number or total frame rate of simultaneous streams. When focus opening becomes slow or delayed, reduce the mosaic profile before increasing the focus profile.

## Preview

<table>
  <tr>
    <td width="50%" align="center">
      <img src="docs/images/cameras.png" alt="PiDecoder camera management"><br>
      <strong>Camera management</strong>
    </td>
    <td width="50%" align="center">
      <img src="docs/images/onvif.png" alt="PiDecoder ONVIF discovery"><br>
      <strong>ONVIF discovery</strong>
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="docs/images/layout.png" alt="PiDecoder layout editor"><br>
      <strong>Mosaic layout editor</strong>
    </td>
    <td width="50%" align="center">
      <img src="docs/images/system.png" alt="PiDecoder system diagnostics"><br>
      <strong>System diagnostics</strong>
    </td>
  </tr>
</table>

## Documentation

| Guide | Description |
|---|---|
| [Installation and updates](docs/installation.md) | Requirements, installer options, updates and systemd startup |
| [Camera configuration](docs/configuration.md) | RTSP streams, credentials, camera order and applying changes |
| [ONVIF and PTZ setup](docs/onvif.md) | Discovery, profiles, PTZ metadata, presets and native controls |
| [Mosaic layout](docs/layout.md) | Grid size, templates, moving and resizing camera tiles |
| [Backup and restore](docs/backup.md) | Web exports, runtime backups and installer recovery |
| [FAQ and troubleshooting](docs/faq.md) | Common startup, RTSP, ONVIF and Wayland issues |

The public documentation is currently written in English.
The Web administration interface is bilingual (French/English) since v1.0.0, with a language toggle on the login screen and in the application header; a few low-level ONVIF and backend diagnostic messages still appear in French regardless of the selected language.

## Quick start

### The short way: flash the ready-made image

Download `PiDecoder-<version>-arm64.img.xz` from the
[Releases page](https://github.com/PiDecoder/PiDecoder/releases) and write it
to an SD card with Raspberry Pi Imager ("Use custom" → the downloaded file).
No Raspberry Pi OS installation, no build, no terminal: the card boots
straight into the video wall, resizes itself to the card, and generates its own
SSH host keys, TLS certificate and hostname on first boot.

The first login to the Web interface (`admin` / `pidecoder`) lands on a
mandatory password change — the same default is in every copy of the image, so
the server refuses everything else until it has been replaced. See
[`docs/installation.md`](docs/installation.md#ready-made-sd-card-image) for the
details, including how to enable SSH.

The image is built by `scripts/build-image.sh`, which you can also run
yourself; the manual installation below is the alternative when the Pi is
already set up.

### 1. Clone PiDecoder

```bash
git clone https://github.com/PiDecoder/PiDecoder.git
cd PiDecoder
```

### 2. Run the preflight check

```bash
sudo ./scripts/install.sh --check
```

The preflight validates the operating system, architecture, desktop user, Wayland session, dependencies and project sources without modifying the host.

When automatic user detection is not possible:

```bash
sudo ./scripts/install.sh --check --user YOUR_DESKTOP_USER
```

### 3. Install

```bash
sudo ./scripts/install.sh
```

The installer:

- installs the required Debian packages;
- builds PiDecoder in release mode;
- installs it under `/opt/pidecoder`;
- preserves existing camera, ONVIF, layout and Web configuration;
- creates a backup under `/var/backups/pidecoder`;
- installs and enables the systemd services;
- starts the video wall when the Wayland session becomes available.

Open the administration interface at:

```text
http://RASPBERRY_PI_IP:8080
https://RASPBERRY_PI_IP:8443
```

Both HTTP and HTTPS are active by default, each on its own port; both are editable — and either protocol can be turned off — from the Security tab. See [`docs/installation.md`](docs/installation.md#https-and-tls-certificates) for details.

## Safe updates

Update the repository and run the same installer again:

```bash
git pull --ff-only
sudo ./scripts/install.sh
```

Existing runtime configuration is preserved automatically before the new version is installed.

## Startup architecture

```text
pidecoder-config.service
└── Web administration on ports 8080 (HTTP) and 8443 (HTTPS)

pidecoder-ptz.service
└── persistent local ONVIF PTZ bridge
    └── /run/pidecoder/ptz.sock

pidecoder-wayland.path
└── waits for /run/user/<uid>/wayland-0
    └── reaches pidecoder-wayland.target
        └── requests pidecoder.service
            └── native RTSP video wall
```

The Wayland path trigger prevents the video engine from starting before the graphical session is ready.
The intermediate target keeps the path unit healthy when no camera is configured; the video service
remains inactive until a valid camera configuration exists.

The PTZ bridge uses a local Unix datagram socket. Camera PTZ credentials and endpoints are read from the protected runtime configuration when a native command is sent.

## Service status

```bash
systemctl status pidecoder-config.service --no-pager
systemctl status pidecoder-ptz.service --no-pager
systemctl status pidecoder-wayland.path --no-pager
systemctl status pidecoder-wayland.target --no-pager
systemctl status pidecoder.service --no-pager
```

Logs:

```bash
journalctl -u pidecoder-config.service -n 50 --no-pager
journalctl -u pidecoder-ptz.service -n 50 --no-pager
journalctl -u pidecoder.service -n 50 --no-pager
```

> [!WARNING]
> Camera configurations and some runtime logs can contain private RTSP addresses or credentials.
> Never publish them or commit them to the repository.

## Supported platform

| Component | Validated configuration |
|---|---|
| Hardware | Raspberry Pi 5 |
| Operating system | Debian 13 |
| Architecture | AArch64 |
| Display server | Wayland |
| Video engine | libmpv / FFmpeg |
| Rendering | SDL2 / OpenGL |
| PTZ transport | ONVIF through a local Unix socket bridge |
| Administration | Python 3 Web service |

Other Linux platforms may work, but they are not yet part of the validated v1.2 target.

## Current validation status

| Test | Status |
|---|---|
| Source and configuration validation | Passed |
| Existing installation upgrade | Passed |
| Camera, ONVIF and layout preservation | Passed |
| Web authentication preservation | Passed |
| Automatic startup after reboot | Passed |
| Wayland-triggered video startup | Passed |
| Continuous 8+ hour run | Passed |
| Fresh installation on blank Debian 13 x86_64 | Passed |
| Web configuration export and restore | Passed |
| Forced-failure installer rollback | Passed |
| Native PTZ directions, optical zoom and Stop | Passed on Axis Q6074 |
| Native PTZ preset selector | Passed on Axis Q6074 |
| PTZ overlay auto-hide and fixed-camera filtering | Passed |
| ONVIF metadata preservation during camera save | Passed in field test |
| Native audio playback in the focus view | Passed on Axis (mic enabled) |
| Mosaic stability with an audio-bearing RTSP stream | Passed on Axis (mic enabled) |
| Audio playback and mosaic stability on an Aqara G410 intercom | Known residual issue, not blocking — see [FAQ](docs/faq.md#is-audio-available) |
| Native C++ unit tests (Grid, Layout, credential redaction) | Passed in CI |
| Native engine build (CMake + compile) | Passed in CI on every push |
| FR/EN translation parity (frontend and backend) | Passed in CI |
| Login rate limiting and lockout | Passed in CI |
| Credential redaction in service logs | Passed in CI |
| HTTPS by default, self-signed certificate generation and import | Passed on the Pi |
| HTTP/HTTPS independent on/off toggle and port editing from the Web UI | Passed on the Pi |
| On-screen IP/hostname/MAC/port overlay at startup and on the **I** key | Passed on the Pi |
| One-click software update from the Web UI, including a forced-failure rollback | Passed on the Pi |
| Hostname/IP change with confirm-or-auto-revert safety net, including across a software update | Passed on the Pi |
| NTP server and timezone configuration | Passed in a sandbox with fake system tools only, not yet field-tested |

The Web configuration export contains cameras, ONVIF metadata and layout data.
Administrator credentials are configured separately and are not included in the exported file.

## Roadmap

| Version | Status | Focus |
|---|---|---|
| v1.0.0 | Released | First stable public release, native PTZ and bilingual FR/EN Web UI |
| v1.1.0 | Released | Native audio support in the focus view, validated on Axis |
| v1.2.0 | Released | HTTPS on independent, editable HTTP/HTTPS ports; one-click software update; network configuration (hostname, IP, NTP, timezone) with automatic rollback; startup IP/MAC/port overlay |
| v1.3 | Planned | REST API |
| v2.0 | Long-term | Multi-Raspberry cluster |

Roadmap items are planned goals and may change as the project evolves. No version is currently in active development; the next item will be picked from the list above.

## Project principles

- Keep it lightweight.
- Keep it fast.
- Keep it reliable.
- Keep it understandable.
- Do not add complexity without a real benefit.

## Contributing

Contributions, testing feedback and bug reports are welcome.

Before submitting a pull request:

1. Read [`CONTRIBUTING.md`](CONTRIBUTING.md).
2. Open an issue before proposing a major architectural change.
3. Keep commits focused and easy to review.
4. Never commit credentials, camera configurations or private logs.

Security issues should follow the process described in [`SECURITY.md`](SECURITY.md).

## License

PiDecoder is distributed under the GNU General Public License v3.0.

See [`LICENSE`](LICENSE) for the full license text.

---

<p align="center">
  <img src="docs/images/pico.png" width="150" alt="Pico, the PiDecoder mascot">
</p>

<p align="center">
  <strong>Pico is watching your cameras.</strong><br>
  Built for Raspberry Pi, RTSP and ONVIF.
</p>
