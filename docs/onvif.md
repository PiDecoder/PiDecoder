# ONVIF camera and PTZ setup

PiDecoder can discover ONVIF devices, identify them, list usable media profiles,
read PTZ capabilities and presets, and create the RTSP camera configuration.

Open the **ONVIF** tab in the Web administration interface.

## Requirements

Before discovery:

- the Raspberry Pi must be able to reach the camera network;
- the camera must have ONVIF enabled;
- the ONVIF account must have permission to read device, media and PTZ information;
- multicast discovery must be allowed when using automatic discovery;
- routed cameras can be added manually by IPv4.

ONVIF credentials may differ from the credentials used by the camera Web interface.

## Automatic discovery

Enter:

- `Utilisateur ONVIF`
- `Mot de passe ONVIF`

Then click:

```text
Rechercher les caméras
```

PiDecoder sends WS-Discovery probes and displays:

- discovered IP address;
- ONVIF endpoint;
- manufacturer and model when available;
- identification state;
- whether the camera is already configured;
- discovery diagnostics.

Automatic discovery normally works only within the same broadcast or multicast domain.

## Manual IPv4 identification

For a camera that is:

- on another routed network;
- not visible through WS-Discovery;
- configured with multicast discovery disabled;

use:

```text
Ajouter manuellement par IPv4
```

Fields:

| Field | Typical value |
|---|---|
| `Adresse` | `192.168.1.100` |
| `Port ONVIF` | `80` |
| `Chemin ONVIF` | `/onvif/device_service` |

Then click **Identifier**.

PiDecoder validates the IPv4 address and builds an endpoint such as:

```text
http://192.168.1.100/onvif/device_service
```

The last manual address, port and path are stored locally in the browser.

## Identification

After discovery, click:

```text
Identifier
```

PiDecoder requests:

- device information;
- manufacturer;
- model;
- firmware version;
- serial number;
- hardware identifier;
- media service address;
- PTZ service address when available;
- available media profiles;
- profile PTZ compatibility;
- RTSP stream URIs;
- presets for compatible PTZ profiles.

A failed identification displays the error and points to:

```bash
sudo cat /tmp/pidecoder-onvif.log
```

Redact credentials and private addresses before sharing that log.

## Selecting profiles

After identification, select:

- `Profil mosaïque`
- `Profil plein écran`

Recommended approach:

- choose a lower-resolution H.264 profile for the mosaic;
- choose a higher-resolution H.264 profile for full screen;
- keep the mosaic frame rate low when the camera limits simultaneous streams.

Typical PiDecoder defaults:

| View | Resolution | Frame rate |
|---|---:|---:|
| Mosaic | 640 × 360 | 12 FPS |
| Focus | 1920 × 1080 | 25 FPS |

PiDecoder prioritizes H.264 profiles with a usable RTSP URI. When no H.264 profile
is available, it may display other profiles that expose a stream URI, but the
validated playback target remains H.264.

## PTZ metadata and presets

When a selected profile supports PTZ, PiDecoder stores the PTZ service address,
the selected PTZ profile token and the presets returned by the camera.

A generated camera entry can contain:

```json
{
  "onvif": {
    "device_xaddr": "http://192.168.1.90/onvif/device_service",
    "media_xaddr": "http://192.168.1.90/onvif/media_service",
    "ptz_xaddr": "http://192.168.1.90/onvif/ptz_service",
    "ip": "192.168.1.90",
    "grid_profile_token": "profile-low",
    "focus_profile_token": "profile-high",
    "ptz_profile_token": "profile-high",
    "ptz_presets": [
      {
        "token": "preset-token",
        "name": "Entrance"
      }
    ],
    "manufacturer": "Example",
    "model": "Example PTZ Camera",
    "serial_number": "REDACTED",
    "hardware_id": "REDACTED"
  }
}
```

The actual endpoint paths and token values depend on the camera.

## Add or update a camera

Enter the name used by PiDecoder, then click:

```text
Ajouter à PiDecoder
```

When the device already exists, the button becomes:

```text
Mettre à jour
```

PiDecoder attempts to match an existing camera by:

- serial number;
- ONVIF device endpoint;
- IPv4 address;
- existing stream URI.

When multiple entries match the same ONVIF device, duplicate entries may be removed during the update.

Before changing the camera list, PiDecoder rotates timestamped camera backups and keeps the latest five.

## Changing video values safely

In v0.9.9.5 RC3, changing camera resolution or FPS from the **Caméras** tab preserves
the stored ONVIF and PTZ metadata.

This includes:

```text
Valeurs PiDecoder
→ Sauvegarder
→ Appliquer
```

Protection is implemented twice:

- the browser keeps the existing camera `onvif` object;
- the server merges stored ONVIF metadata if an older browser tab omits it.

Reload the Web interface with `Ctrl + F5` after upgrading to RC3 so the browser uses
the newest JavaScript.

## Apply the new camera

Adding or updating a camera stores the configuration, but the video engine must reload it.

Click:

```text
Appliquer
```

The Web service restarts:

```text
pidecoder.service
```

The persistent PTZ bridge remains available through:

```text
pidecoder-ptz.service
```

## Native PTZ controls

Open a PTZ camera in the native focus view.

PiDecoder displays:

- left, right, up and down controls;
- optical zoom out and in;
- a forced Stop control;
- a `PRESET` selector when presets are available.

Selecting a preset immediately sends ONVIF `GotoPreset`.

The controls disappear after five seconds without mouse movement and return as soon
as the pointer moves. They remain visible while a PTZ command or preset menu is active.

PiDecoder sends Stop when:

- the mouse button is released;
- the pointer leaves the active button;
- the application window loses focus;
- Escape closes the focus view;
- the focus view is otherwise closed.

Fixed cameras and cameras without complete PTZ metadata do not display the overlay.

## Discovery diagnostics

The ONVIF diagnostics panel can show:

- network interfaces used;
- probes sent;
- packets received;
- XML packets parsed;
- message types;
- probe matches;
- socket errors;
- unknown XML samples;
- detailed discovery events.

These diagnostics are useful when devices respond but are not recognized as standard probe matches.

## Common ONVIF problems

### No camera discovered

Check:

```bash
ip address
ip route
```

Confirm that:

- the Raspberry Pi is on the expected network;
- no firewall blocks UDP multicast discovery;
- ONVIF discovery is enabled on the camera.

Use manual IPv4 identification when discovery across subnets is not possible.

### Authentication failed

Confirm:

- the ONVIF username;
- the ONVIF password;
- the camera date and time;
- the permissions assigned to the account.

Some cameras require a dedicated ONVIF user.

### Device identified but no usable profile

Check whether the camera exposes:

- an H.264 encoder profile;
- a valid media service;
- a valid RTSP URI.

JPEG-only or unsupported profiles are not part of the currently validated PiDecoder target.

### PTZ controls are not displayed

Confirm that the camera entry contains both:

```text
onvif.ptz_xaddr
onvif.ptz_profile_token
```

Then restart:

```bash
sudo systemctl restart pidecoder-ptz.service
sudo systemctl restart pidecoder.service
```

Reload the focus view after the services are active.

### No presets are displayed

Confirm that the camera exposes presets for the selected PTZ profile and that the
camera entry contains a non-empty:

```text
onvif.ptz_presets
```

Identify the camera again and use **Mettre à jour** to refresh the preset list.

### Focus view is delayed

Some cameras restrict simultaneous streams or aggregate frame rate. Use a lightweight
mosaic profile and avoid requesting two high-frame-rate streams at the same time.

### Camera already configured more than once

Identify the camera again and use **Mettre à jour**. PiDecoder uses ONVIF identity
fields and stream information to detect matching entries and remove duplicates when possible.
