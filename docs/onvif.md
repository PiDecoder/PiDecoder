# ONVIF camera setup

PiDecoder can discover ONVIF devices, identify them, list usable media profiles and create the RTSP camera configuration.

Open the **ONVIF** tab in the Web administration interface.

## Requirements

Before discovery:

- the Raspberry Pi must be able to reach the camera network;
- the camera must have ONVIF enabled;
- the ONVIF account must have permission to read device and media information;
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
- available media profiles;
- RTSP stream URIs.

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
- choose a higher-resolution H.264 profile for full screen.

PiDecoder prioritizes H.264 profiles with a usable RTSP URI. When no H.264 profile is available, it may display other profiles that expose a stream URI, but the validated playback target remains H.264.

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

The generated camera metadata may include:

```json
{
  "onvif": {
    "device_xaddr": "http://192.168.1.90/onvif/device_service",
    "media_xaddr": "http://192.168.1.90/onvif/media_service",
    "ip": "192.168.1.90",
    "grid_profile_token": "profile-low",
    "focus_profile_token": "profile-high",
    "manufacturer": "Example",
    "model": "Example Camera",
    "serial_number": "REDACTED",
    "hardware_id": "REDACTED"
  }
}
```

Before changing the camera list, PiDecoder rotates timestamped camera backups and keeps the latest five.

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

### Camera already configured more than once

Identify the camera again and use **Mettre à jour**. PiDecoder uses ONVIF identity fields and stream information to detect matching entries and remove duplicates when possible.
