# Native PTZ RC2 test checklist

## Services

```bash
systemctl is-active pidecoder-config.service
systemctl is-active pidecoder-ptz.service
systemctl is-active pidecoder-wayland.path
systemctl is-active pidecoder.service
```

Expected: all four services report `active` when a camera configuration and the Wayland session are available.

## Camera metadata

After re-identifying and updating the PTZ camera in the Web interface:

```bash
sudo python3 - <<'PY'
import json
from pathlib import Path

document=json.loads(Path('/opt/pidecoder/config/cameras.json').read_text())
for camera in document.get('cameras',[]):
    metadata=camera.get('onvif',{})
    print(camera.get('name'), bool(metadata.get('ptz_xaddr')), bool(metadata.get('ptz_profile_token')))
PY
```

The PTZ camera must print `True True`.

The same camera metadata must also contain a non-empty `ptz_presets` array after it has been re-identified and updated from the Web ONVIF page.

## Native overlay

- [ ] Double-clicking the PTZ camera opens the focus view
- [ ] The PTZ overlay appears in the lower-right corner
- [ ] A fixed camera does not show the overlay
- [ ] Holding Up moves the camera upward
- [ ] Holding Down moves the camera downward
- [ ] Holding Left moves the camera left
- [ ] Holding Right moves the camera right
- [ ] Holding Zoom + performs optical zoom in
- [ ] Holding Zoom - performs optical zoom out
- [ ] Releasing the mouse sends Stop immediately
- [ ] Leaving the active button sends Stop immediately
- [ ] The center Stop button stops the camera even after a lost release event
- [ ] Escape stops movement and closes the focus view
- [ ] Losing window focus sends Stop
- [ ] Digital inspection zoom and pan still work outside the PTZ controls
- [ ] The compact `PRESET` selector is visible when presets are available
- [ ] Opening the selector keeps the PTZ overlay visible
- [ ] Selecting a preset immediately moves the camera and closes the menu
- [ ] Preset names are readable and long names are safely truncated

## Logs

```bash
journalctl -u pidecoder-ptz.service -n 100 --no-pager
journalctl -u pidecoder.service -n 100 --no-pager
```

The logs must not expose RTSP usernames or passwords.
