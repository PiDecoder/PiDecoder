# Backup and restore

PiDecoder uses several backup mechanisms for different situations.

## 1. Installer backup

Before replacing an existing installation, the public installer creates:

```text
/var/backups/pidecoder/YYYYMMDD-HHMMSS/
```

A backup can contain:

```text
target/
systemd/
```

- `target/` is a copy of the previous installation directory.
- `systemd/` contains the previous PiDecoder unit files.

The installer backup preserves:

```text
cameras.json
layout.json
web-auth.json
config/backups/
```

The installer restores the previous installation when a failure occurs after system changes begin. A deliberate forced-failure rollback test has been successfully completed, including restoration of the binary, camera configuration, layout, Web authentication and systemd units.

## 2. Runtime camera and layout backups

PiDecoder stores runtime backups under:

```text
/opt/pidecoder/config/backups/
```

Depending on the operation, this directory may contain:

```text
cameras.json.previous
layout.json.previous
cameras.json.YYYYMMDD-HHMMSS.bak
cameras.json.before-import-YYYYMMDD-HHMMSS
layout.json.before-import-YYYYMMDD-HHMMSS
```

ONVIF camera updates rotate timestamped camera backups and keep the latest five matching files.

## 3. Export from the Web interface

Open:

```text
Sauvegarde → Exporter
```

The downloaded JSON includes:

- cameras;
- layout;
- PiDecoder export format;
- version;
- export timestamp.

The Web administrator password is not exported.

The browser downloads a file named similar to:

```text
pidecoder-config-2026-08-02.json
```

The exact download location is controlled by the browser or application used to access PiDecoder.

## 4. Import from the Web interface

Open:

```text
Sauvegarde → Importer
```

Select a PiDecoder JSON export and click:

```text
Importer la configuration
```

Before replacing the current files, PiDecoder creates timestamped backups.

After import:

1. review the camera list;
2. review the layout;
3. click **Appliquer** to restart the video engine with the imported configuration.

The import must contain:

```json
{
  "format": "pidecoder-config",
  "cameras": [],
  "layout": {}
}
```

At least one valid camera is required by the current import logic.

## Manual backup

Create a private manual backup:

```bash
sudo tar \
  --create \
  --gzip \
  --file /root/pidecoder-config-backup.tar.gz \
  /opt/pidecoder/config
```

This archive contains credentials and must be stored securely.

A configuration-only copy without the Web password can be created manually:

```bash
sudo mkdir -p /root/pidecoder-config-copy

sudo cp -a \
  /opt/pidecoder/config/cameras.json \
  /opt/pidecoder/config/layout.json \
  /root/pidecoder-config-copy/
```

## Manual restore from an installer backup

Stop the services:

```bash
sudo systemctl stop \
  pidecoder.service \
  pidecoder-config.service \
  pidecoder-wayland.path \
  pidecoder-wayland.target
```

Choose the required backup:

```bash
sudo ls -1 /var/backups/pidecoder
```

Restore the target:

```bash
sudo rm -rf /opt/pidecoder

sudo cp -a \
  /var/backups/pidecoder/YYYYMMDD-HHMMSS/target \
  /opt/pidecoder
```

Restore the unit files when required:

```bash
sudo cp -a \
  /var/backups/pidecoder/YYYYMMDD-HHMMSS/systemd/. \
  /etc/systemd/system/
```

Reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pidecoder-config.service pidecoder-wayland.path
sudo systemctl restart pidecoder-wayland.path
sudo systemctl restart pidecoder-config.service
```

When the Wayland socket exists, `pidecoder-wayland.path` reaches `pidecoder-wayland.target`. The target requests `pidecoder.service`, which starts only when the camera configuration is valid.

## Verify a restore

```bash
systemctl is-active pidecoder-config.service
systemctl is-active pidecoder-wayland.path
systemctl is-active pidecoder-wayland.target
systemctl is-active pidecoder.service
```

Check the configuration:

```bash
sudo python3 \
  /opt/pidecoder/scripts/check-camera-config.py \
  /opt/pidecoder/config/cameras.json
```

Review logs:

```bash
journalctl -u pidecoder-config.service -n 50 --no-pager
journalctl -u pidecoder.service -n 50 --no-pager
```

## Security

Backups may contain:

- RTSP usernames;
- RTSP passwords;
- private camera addresses;
- ONVIF endpoints;
- the Web authentication hash and session secret.

Do not commit backups to Git, upload them to public issue trackers or store them in an unprotected shared folder.
