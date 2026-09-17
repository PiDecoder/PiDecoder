# FAQ and troubleshooting

## Which platform is supported?

The current validated target is:

```text
Raspberry Pi 5
Debian 13
AArch64
Wayland
```

Other Debian-based systems may work but are not yet part of the validated v1.0 target.

## Why is `pidecoder.service` disabled?

This is intentional.

PiDecoder starts through:

```text
pidecoder-wayland.path
```

The path unit waits for:

```text
/run/user/<uid>/wayland-0
```

and then starts:

```text
pidecoder.service
```

Expected state:

```bash
systemctl is-enabled pidecoder.service
```

```text
disabled
```

Expected enabled units:

```bash
systemctl is-enabled pidecoder-config.service
systemctl is-enabled pidecoder-wayland.path
```

## The Web interface works but the video wall is inactive

Check:

```bash
systemctl is-active pidecoder-config.service
systemctl is-active pidecoder-wayland.path
systemctl is-active pidecoder.service
```

Then verify the Wayland socket:

```bash
ls -l /run/user/$(id -u YOUR_DESKTOP_USER)/wayland-0
```

Validate the camera configuration:

```bash
sudo python3 \
  /opt/pidecoder/scripts/check-camera-config.py \
  /opt/pidecoder/config/cameras.json
```

Try a manual start:

```bash
sudo systemctl start pidecoder.service
```

Review:

```bash
systemctl status pidecoder.service --no-pager -l
journalctl -u pidecoder.service -n 100 --no-pager
```

## PiDecoder does not start after reboot

Check the path trigger:

```bash
systemctl status pidecoder-wayland.path --no-pager
```

Confirm that the graphical user session starts automatically and creates the configured Wayland socket.

Review current-boot messages:

```bash
journalctl -b --no-pager | grep -Ei 'pidecoder|wayland|ordering cycle'
```

The current templates avoid the former `graphical.target` ordering cycle by starting the video engine from the Wayland path unit.

## The installer cannot detect the user

Run:

```bash
sudo ./scripts/install.sh --check --user YOUR_DESKTOP_USER
```

Then install with the same explicit user:

```bash
sudo ./scripts/install.sh --user YOUR_DESKTOP_USER
```

The user must not be `root`.

## `Node.js absent : contrôle JavaScript ignoré`

This is not a runtime error.

Node.js is used only for an additional embedded JavaScript syntax check during release validation. It is not required to run PiDecoder.

## The camera shows no image

Confirm network access:

```bash
ping CAMERA_IP
```

Test the RTSP URL with a suitable client such as FFmpeg:

```bash
ffprobe 'rtsp://CAMERA_IP:554/STREAM'
```

Quote the URL so shell characters are not interpreted.

Then review:

```bash
journalctl -u pidecoder.service -n 100 --no-pager
```

Possible causes:

- incorrect RTSP path;
- incorrect credentials;
- unsupported stream codec;
- camera session limit reached;
- camera unreachable;
- special characters not URL-encoded;
- resolution or frame rate not supported by the selected stream.

## Password contains `@`, `$`, `:` or `%`

Percent-encode special characters in manually entered URLs.

Examples:

```text
@  → %40
$  → %24
:  → %3A
%  → %25
```

ONVIF-generated URLs are encoded by PiDecoder.

## ONVIF discovery finds nothing

Automatic discovery may fail across routed networks or VLANs.

Use:

```text
ONVIF → Ajouter manuellement par IPv4
```

Enter the camera address, port and device-service path.

Also check:

- multicast filtering;
- firewall rules;
- ONVIF enabled on the camera;
- camera account permissions;
- clock synchronization.

## The camera is duplicated after ONVIF setup

Identify the camera again and choose **Mettre à jour**.

PiDecoder compares:

- serial number;
- device endpoint;
- IPv4 address;
- stream URI.

Matching duplicates may be removed during the update.

## The layout says the grid is too small

Increase rows or columns, reduce a large tile, disable unused cameras or choose:

```text
Grille uniforme
```

## How do I restart PiDecoder?

Video engine:

```bash
sudo systemctl restart pidecoder.service
```

Web administration:

```bash
sudo systemctl restart pidecoder-config.service
```

Wayland trigger:

```bash
sudo systemctl restart pidecoder-wayland.path
```

## How do I update PiDecoder?

Since v1.2.0, the easiest way is the **Update** panel in the System tab of the Web interface: it checks the Git repository against its remote branch and offers a one-click update when a new version is available. It runs the same installer under the hood, so runtime configuration and network settings (including HTTP/HTTPS ports) are preserved the same way as a manual update.

The manual way still works, over SSH:

```bash
cd PiDecoder
git pull
sudo ./scripts/install.sh
```

The installer preserves runtime configuration and creates a timestamped backup under `/var/backups/pidecoder/`.

## Do I have to install Raspberry Pi OS first?

No, not since v1.3.0. A ready-to-flash image is published with each release: write `PiDecoder-<version>-arm64.img.xz` to an SD card with Raspberry Pi Imager and boot it. The card contains Raspberry Pi OS Lite, a minimal Wayland session and PiDecoder, already installed and enabled.

Installing on an existing Raspberry Pi OS with `scripts/install.sh` still works exactly as before, and is the right choice when the Pi already runs something else. See [Installation](installation.md).

## The image is the same on every card — what about keys and passwords?

Everything that must be unique to a device is generated on the device, at first boot, not baked into the image: the SSH host keys, the machine ID, the TLS certificate (its private key and the IP addresses in it), and the hostname, which is derived from the Pi's serial number (`pidecoder-xxxxxx`) so that several units don't collide on the same network.

What the image does ship with is two default passwords, which are therefore public. The Web one (`admin` / `pidecoder`) is enforced: the first login lands on a change-password screen and the server refuses every other request until it has been replaced. The Linux one (`pidecoder` / `pidecoder`) is not enforced, but SSH is disabled by default, as on stock Raspberry Pi OS — change it with `passwd` before enabling SSH on a network you don't control.

## How do I build the SD card image myself?

`sudo ./scripts/build-image.sh`, ideally on a Raspberry Pi so the build runs natively. It takes 30 to 60 minutes and about 10 GB of scratch space, and writes the image plus its checksum to `dist/`. It also runs on an x86_64 machine through qemu emulation, which is what the GitHub Actions workflow does on every tag. See [Building the SD card image yourself](installation.md#building-the-sd-card-image-yourself).

## Where are the files?

```text
/opt/pidecoder/config/cameras.json
/opt/pidecoder/config/layout.json
/opt/pidecoder/config/web-auth.json
/opt/pidecoder/config/backups/
/var/backups/pidecoder/
```

## How do I collect diagnostics?

Use the **Système** tab and click:

```text
Copier le rapport
```

Or use systemd:

```bash
systemctl status pidecoder-config.service --no-pager
systemctl status pidecoder-wayland.path --no-pager
systemctl status pidecoder.service --no-pager

journalctl -u pidecoder-config.service -n 50 --no-pager
journalctl -u pidecoder.service -n 50 --no-pager
```

## Can I publish the diagnostic report?

Review it first.

Logs may contain:

- RTSP URLs;
- usernames;
- passwords;
- camera IP addresses;
- ONVIF endpoints;
- serial numbers.

Redact private values before publishing.

## Is HTTPS included?

Yes, since v1.2.0. The Web administration interface can serve HTTP and HTTPS at the same time, each on its own port (8080/8443 by default, both editable from the Security tab). A self-signed certificate is generated automatically on first install; it can be regenerated, replaced with your own certificate/key pair, or the whole HTTPS listener can be turned off, all from the Security tab (or over SSH with `scripts/manage-tls.sh`). Either protocol can be disabled independently, but not both at once, so the Web interface can never be locked out.

Note that this only covers the Web administration interface. The RTSP video stream between the Pi and the cameras is not encrypted (RTSPS): it was evaluated and set aside, since it depends on each camera's own support and isn't worth the added complexity for a stream that never leaves the local network.

## Is PTZ fully available?

Yes. Native PTZ control (pan/tilt, optical zoom, forced Stop and preset selection) is available in the Web interface, with an auto-hiding PTZ overlay in the focus view. It has been field-tested and validated on an Axis Q6074. Support for other ONVIF PTZ cameras is expected to work through the same ONVIF profile but is not yet validated in the field the way the Axis Q6074 is.

## Is audio available?

Yes, since v1.1.0. When a camera's RTSP stream carries an audio track, PiDecoder can play it in the full-screen (focus) view through a speaker button, and only when the camera's **Audio** toggle is enabled in the Web interface (see [Audio](configuration.md#audio)). Audio is never played in the mosaic; enabling **Audio** for a camera does relax that camera's mosaic decoding settings so the extra audio stream doesn't disrupt the grid view.

It has been field-tested and validated with an **Axis** camera (mic enabled on its RTSP stream). Other ONVIF/RTSP cameras with audio are expected to work through the same mechanism but are not yet validated to the same degree.

The **Aqara G410** intercom is a known exception: it still shows residual audio-related trouble even with **Audio** enabled. This is set aside for now and not currently blocking — leave **Audio** disabled for a G410 if you only need video from it.

## Is English available in the Web interface?

Yes. The Web administration interface has been bilingual (French/English) since v1.0.0, with a language toggle on the login screen and in the application header. The language choice is remembered in a cookie.

Some low-level ONVIF client error messages (SOAP/HTTP/XML failures) and a few backend-generated system/diagnostic terms still appear in French regardless of the selected language.
