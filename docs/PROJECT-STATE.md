# PiDecoder project state

## Active version

- Development version: **v0.9.9.5 RC2**
- Base version: v0.9.9.4 RC1
- Active work: native PTZ controls and presets in the SDL video wall

## Completed before RC2

- Native low-latency RTSP grid and focus view
- Digital inspection zoom and pan
- Web administration and ONVIF discovery
- Web PTZ control using ONVIF `ContinuousMove`, `Stop` and `GotoPreset`
- Public installer, Wayland startup trigger and rollback validation
- Public documentation and system diagnostics

## RC2 implementation

- Persist `ptz_xaddr`, `ptz_profile_token` and PTZ presets in camera metadata
- Local Unix-datagram PTZ bridge at `/run/pidecoder/ptz.sock`
- Native PTZ overlay in the focus view
- Pan, tilt, optical zoom and forced stop controls
- Native preset selector: selecting an item immediately sends `GotoPreset`
- Stop on pointer release, pointer exit, focus loss, Escape and focus close
- Compact controls hidden after five seconds without mouse activity
- Overlay hidden automatically for cameras without PTZ metadata

## Required real-hardware validation

1. Install the current RC2 branch on the Raspberry Pi.
2. In the Web ONVIF page, re-identify the PTZ camera and select **Mettre à jour** once so the preset list is stored.
3. Apply the configuration.
4. Open that camera in the native focus view.
5. Validate every direction, optical zoom and Stop.
6. Open the preset selector and validate that selecting a preset moves the camera immediately.
7. Confirm that a fixed camera does not show the overlay.
8. Reboot and confirm all services start automatically.

## Still outside RC2 scope

- Keyboard PTZ shortcuts
- PTZ speed adjustment in the native overlay
