# PiDecoder project state

## Active version

- Development version: **v0.9.9.5 RC2**
- Base version: v0.9.9.4 RC1
- Active work: native PTZ controls in the SDL video wall

## Completed before RC2

- Native low-latency RTSP grid and focus view
- Digital inspection zoom and pan
- Web administration and ONVIF discovery
- Web PTZ control using ONVIF `ContinuousMove`, `Stop` and `GotoPreset`
- Public installer, Wayland startup trigger and rollback validation
- Public documentation and system diagnostics

## RC2 implementation

- Persist `ptz_xaddr` and `ptz_profile_token` in camera metadata
- Local Unix-datagram PTZ bridge at `/run/pidecoder/ptz.sock`
- Native PTZ overlay in the focus view
- Pan, tilt, optical zoom and forced stop controls
- Stop on pointer release, pointer exit, focus loss, Escape and focus close
- Overlay hidden automatically for cameras without PTZ metadata

## Required real-hardware validation

1. Install RC2 on the Raspberry Pi.
2. In the Web ONVIF page, identify the PTZ camera and select **Mettre à jour** once so the new PTZ metadata is stored.
3. Apply the configuration.
4. Open that camera in the native focus view.
5. Validate every direction, optical zoom and Stop.
6. Confirm that a fixed camera does not show the overlay.
7. Reboot and confirm all services start automatically.

## Not included in the first RC2 test

- Native preset selector
- Keyboard PTZ shortcuts
- PTZ speed adjustment in the native overlay
