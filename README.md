# PiDecoder

PiDecoder is a lightweight RTSP and ONVIF video wall for Raspberry Pi.

It is designed for always-on camera monitoring with hardware-assisted decoding, automatic reconnection, a configurable mosaic, fullscreen focus mode, zoom and a built-in Web administration interface.

> Current public state: **v0.9.9.4 RC1**  
> The project is in release-candidate testing before v1.0.0.

## Highlights

- RTSP camera wall
- ONVIF discovery and manual IPv4 addition
- Separate mosaic and fullscreen profiles
- Hardware-assisted video decoding
- Automatic reconnection after network or camera outages
- Fullscreen focus mode
- Mouse-wheel zoom and click-drag image movement
- Flexible mosaic editor
- 1×1, 2×1, 1×2 and 2×2 camera tiles
- Smart automatic rearrangement
- Web administration with authentication
- Diagnostics, logs and system health
- Configuration backup and restore
- Raspberry Pi 5 oriented

## Screenshots

Screenshots will be added before the v1.0.0 release.

Recommended screenshots:

1. Camera configuration
2. ONVIF discovery
3. Mosaic editor
4. System diagnostics

## Supported environment

The current release candidate is developed and validated on:

- Raspberry Pi 5
- Debian 13 / Raspberry Pi OS compatible userspace
- Wayland / labwc
- systemd
- FFmpeg / libmpv
- SDL2
- CMake
- Python 3

Other Linux systems may work but are not yet part of the validated v1.0 target.

## Repository layout

```text
.
├── config/                 Example configuration
├── include/pidecoder/      C++ headers
├── scripts/                Installer, Web admin and validation scripts
├── src/                    C++ sources
├── systemd/                Service units
├── .github/                CI and contribution templates
├── CMakeLists.txt
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
└── SECURITY.md
```

## Build

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
```

## Install the release candidate

The repository currently contains the release-candidate installer used during validation.

```bash
sudo ./scripts/apply-v0994.sh /opt/pidecoder
```

Review the script before running it on a production system.

## Configuration

Copy the examples before use:

```bash
cp config/cameras.example.json config/cameras.json
cp config/layout.example.json config/layout.json
```

Never commit real RTSP credentials, camera passwords or private network details.

## Development status

PiDecoder is currently frozen for release-candidate testing.

Allowed changes before v1.0.0:

- bug fixes
- regressions
- stability improvements
- documentation corrections
- packaging fixes

New features should wait until after v1.0.0.

## License

PiDecoder is licensed under the GNU General Public License v3.0 or later.
