# Public installer test checklist

Use this checklist on a Raspberry Pi test host before documenting the installer as stable.

## Preflight

```bash
sudo ./scripts/install.sh --check --user admin
```

- [ ] Debian/Raspberry Pi OS is detected
- [ ] The intended desktop user is shown
- [ ] The Wayland socket path is correct
- [ ] Missing dependencies are listed without changing the host
- [ ] Source validation passes

## Existing installation upgrade

```bash
sudo ./scripts/install.sh --user admin
```

- [ ] Existing `cameras.json` is preserved
- [ ] Existing `layout.json` is preserved
- [ ] Existing `web-auth.json` is preserved
- [ ] A backup is created under `/var/backups/pidecoder/`
- [ ] The Web service starts
- [ ] The video service starts when the Wayland session and cameras are available
- [ ] The administration password still works

## Fresh installation

- [ ] The installer asks for an administrator password
- [ ] The Web interface is reachable on port 8080
- [ ] The video service remains stopped while no camera is configured
- [ ] Adding and applying the first camera starts the video service

## Rollback test

Perform this only on a disposable test host.

- [ ] Force a build failure after a previous version has been backed up
- [ ] The former target directory is restored
- [ ] The former systemd units are restored
- [ ] The former Web service starts again

## Logs

```bash
systemctl status pidecoder-config.service --no-pager
systemctl status pidecoder.service --no-pager
journalctl -u pidecoder-config.service -n 50 --no-pager
journalctl -u pidecoder.service -n 50 --no-pager
```
