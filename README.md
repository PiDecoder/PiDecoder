<p align="center">
  <img src="docs/images/pidecoder-logo.png" width="220" alt="PiDecoder Logo">
</p>

<h1 align="center">PiDecoder</h1>

<p align="center">
<strong>Professional RTSP & ONVIF Video Wall built for Raspberry Pi</strong>
<br>
Lightweight • Hardware Accelerated • Modern Web Administration
</p>

<p align="center">

![License](https://img.shields.io/badge/License-GPLv3-green.svg)
![Release](https://img.shields.io/badge/Release-v0.9.9.4_RC1-blue)
![Platform](https://img.shields.io/badge/Raspberry%20Pi-5-C51A4A)
![C++](https://img.shields.io/badge/C%2B%2B-17-blue)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB)
![ONVIF](https://img.shields.io/badge/ONVIF-Compatible-success)
![RTSP](https://img.shields.io/badge/RTSP-Supported-orange)

</p>

---

<p align="center">
<img src="docs/images/cameras.png" width="95%">
</p>

---

# Why PiDecoder?

PiDecoder was created with a simple objective:

> **Provide a fast, lightweight and reliable RTSP & ONVIF Video Wall specifically designed for Raspberry Pi.**

Unlike many traditional Video Management Systems, PiDecoder focuses on simplicity, performance and ease of deployment while taking full advantage of Raspberry Pi hardware acceleration.

Whether monitoring a home lab, workshop, business or industrial site, PiDecoder delivers a responsive and modern surveillance experience without unnecessary complexity.

---

# Features

| 🎥 Video | 🔍 ONVIF | 🖥 Layout | ⚙ Administration |
|----------|----------|----------|------------------|
| RTSP Streaming | Automatic Discovery | Drag & Drop | Modern Web Interface |
| H264 | Manual IPv4 Add | Camera Resize | Diagnostics |
| JPEG | Profile Detection | Fullscreen View | Logs |
| Hardware Decoding | Camera Update | Zoom & Pan | Services |
| Auto Reconnect | RTSP URI Extraction | Flexible Layouts | Backup |
| Low CPU Usage | PTZ Ready | Main Camera Mode | Security |

---

# Screenshots

## Camera Management

<p align="center">
<img src="docs/images/cameras.png" width="90%">
</p>

---

## ONVIF Discovery

<p align="center">
<img src="docs/images/onvif.png" width="90%">
</p>

---

## Mosaic Layout Editor

<p align="center">
<img src="docs/images/layout.png" width="90%">
</p>

---

## System Diagnostics

<p align="center">
<img src="docs/images/system.png" width="90%">
</p>

---

# Installation

Clone the repository

```bash
git clone https://github.com/PiDecoder/PiDecoder.git

cd PiDecoder
```

Configure and build

```bash
mkdir build

cd build

cmake ..

make -j$(nproc)
```

Install

```bash
sudo make install
```

---

# Supported Platform

PiDecoder is currently validated on:

- Raspberry Pi 5
- Debian 13
- Wayland
- SDL2
- FFmpeg
- libmpv

Support for additional Linux platforms will be expanded after the v1.0 release.

---

# Roadmap

| Version | Status |
|----------|--------|
| ✅ v1.0 | Stable Release |
| 🚧 v1.1 | PTZ Controls |
| 🚧 v1.2 | Audio Support |
| 🚧 v1.3 | HTTPS |
| 🚧 v1.4 | REST API |
| 🚀 v2.0 | Multi-Raspberry Cluster |

---

# Project Philosophy

PiDecoder follows a few simple principles:

- Keep it lightweight.
- Keep it fast.
- Keep it reliable.
- Keep it simple.

Every new feature should respect these principles.

---

# Contributing

Contributions are welcome.

Before submitting a Pull Request:

- Read `CONTRIBUTING.md`
- Open an Issue for major changes
- Keep commits focused
- Never commit credentials or private configuration files

---

# License

PiDecoder is distributed under the GNU General Public License v3.0.

See the `LICENSE` file for more information.

---

<p align="center">
<img src="docs/images/pico.png" width="150">
</p>

<p align="center">
<strong>Pico is watching your cameras.</strong>
<br>
Thank you for supporting PiDecoder ❤️
</p>
