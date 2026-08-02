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
ffprobe 'rtsp://USER:PASSWORD@CAMERA_IP:554/STREAM'
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

```bash
cd PiDecoder
git pull
sudo ./scripts/install.sh
```

The installer preserves runtime configuration and creates a timestamped backup under `/var/backups/pidecoder/`.

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

Not in v0.9.9.4 RC1.

The current Web service uses HTTP. Keep it on a trusted network. HTTPS is listed as a planned roadmap item, not a current feature.

## Is PTZ fully available?

ONVIF PTZ functions exist in the backend, but the stable public feature set and documentation are not yet claiming complete PTZ support. PTZ remains planned for a later release.

## Is English available in the Web interface?

Not yet.

The public README and documentation are in English. The current Web administration interface is in French. English localization is planned before the stable v1.0 release.
