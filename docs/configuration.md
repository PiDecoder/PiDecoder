# Camera configuration

PiDecoder stores camera settings in:

```text
/opt/pidecoder/config/cameras.json
```

The recommended way to manage cameras is through the Web administration interface:

```text
http://RASPBERRY_PI_IP:8080
```

The current Web interface is in French. This guide uses the labels displayed by the application.

## Camera fields

Open the **Caméras** tab and select **+ Ajouter**.

Each camera contains:

| Web field | Purpose |
|---|---|
| `Nom` | Friendly camera name |
| `Adresse IP` | Camera IPv4 address or hostname |
| `Port RTSP` | RTSP port, usually `554` |
| `Utilisateur` | RTSP username |
| `Mot de passe` | RTSP password |
| `Chemin RTSP` | Stream path |
| `Résolution mosaïque` | Lower-resolution stream used in the multi-camera view |
| `FPS mosaïque` | Frame-rate target for the mosaic |
| `Résolution plein écran` | Higher-resolution stream used for a focused camera |
| `FPS plein écran` | Frame-rate target for full-screen display |
| `active` | Enables or disables the camera |

The **Valeurs PiDecoder** button fills the current default values:

```text
Mosaic:     640 × 360 at 12 fps
Full screen: 1920 × 1080 at 25 fps
```

These values are practical defaults, not mandatory requirements. Use values supported by the camera.

## Mosaic and focus streams

PiDecoder supports two RTSP URLs for each camera:

```json
{
  "grid_url": "rtsp://...",
  "focus_url": "rtsp://..."
}
```

- `grid_url` is used in the mosaic.
- `focus_url` is used when a camera is shown in full screen.
- When `focus_url` is empty, PiDecoder falls back to `grid_url`.

Using a lower-resolution mosaic stream reduces decoding load when many cameras are displayed.

## Advanced URL mode

Expand:

```text
URL avancées / mode manuel
```

This exposes the complete RTSP URLs:

- `URL mosaïque`
- `URL plein écran`

When the address field is empty, the manually entered URLs are preserved.

Example configuration:

```json
{
  "cameras": [
    {
      "name": "Front entrance",
      "enabled": true,
      "grid_url": "rtsp://192.0.2.10:554/stream-low",
      "focus_url": "rtsp://192.0.2.10:554/stream-high"
    }
  ]
}
```

> [!WARNING]
> `cameras.json` contains camera addresses and may contain usernames and passwords.
> It must never be committed to Git or attached to a public issue.

## Special characters in credentials

PiDecoder URL-encodes credentials received through ONVIF.

For manually entered RTSP URLs, characters with a special meaning in URLs must be percent-encoded.

Examples:

| Character | Encoded value |
|---|---|
| `@` | `%40` |
| `:` | `%3A` |
| `/` | `%2F` |
| `$` | `%24` |
| `%` | `%25` |

A password such as:

```text
MyP@ss$word
```

becomes:

```text
MyP%40ss%24word
```

## Save and apply

The two actions are intentionally separate:

- **Sauvegarder** writes the current camera and layout configuration.
- **Appliquer** saves the configuration and restarts `pidecoder.service`.

After adding or changing a camera:

1. click **Sauvegarder**;
2. click **Appliquer**;
3. confirm that the video wall reloads;
4. review the service logs when a stream does not appear.

## Camera order

In the **Caméras** tab, cameras can be reordered using the `☰` handle.

Only the handle starts the drag operation, so text fields remain selectable.

The active camera order is also reflected in the mosaic layout.

## Enable or disable a camera

Clear the `active` checkbox to keep a camera in the configuration without loading its streams.

Disabled cameras:

- remain stored in `cameras.json`;
- are excluded from the active mosaic;
- can be enabled again later.

At least one valid camera is currently required when saving a manual camera configuration through the Web API.

## Configuration permissions

The installer sets restrictive permissions:

```text
/opt/pidecoder/config/           0750
cameras.json                     0600
layout.json                      0600
web-auth.json                    0600
```

Camera and layout files belong to the graphical PiDecoder user. The Web authentication file belongs to `root`.

## Validate the camera configuration

The installer includes:

```bash
python3 /opt/pidecoder/scripts/check-camera-config.py \
  /opt/pidecoder/config/cameras.json
```

Exit status:

| Status | Meaning |
|---|---|
| `0` | At least one active camera has a mosaic URL |
| `1` | No active camera is ready |
| `2` | Invalid file or invalid JSON structure |

## Manual service restart

```bash
sudo systemctl restart pidecoder.service
```

Then check:

```bash
systemctl status pidecoder.service --no-pager
journalctl -u pidecoder.service -n 50 --no-pager
```

## Example files

The repository includes safe public examples:

```text
config/cameras.example.json
config/layout.example.json
```

Do not rename them to runtime filenames inside the public repository. Runtime configuration belongs under `/opt/pidecoder/config/` after installation.
