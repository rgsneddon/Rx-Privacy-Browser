# Rx Privacy Browser

**Rx** is a from-scratch, privacy-oriented browser under the **Restore Privacy** umbrella.

It is **not** a fork or clone of Chromium, Firefox, Brave, LibreWolf, or any third-party browser template. The shell (tabs, chrome, privacy defaults, extension load path) is original to this repository and hosts system web surfaces for navigation.

## Features

- **Multi-tab** browsing: open, switch, close
- **Extensions permitted**, including the bundled **Restore Privacy VPN 3.3.3** browser extension
- **Privacy defaults**: no shell telemetry/analytics, private `about:newtab` start, tracker-blocking flag on, Do Not Track on
- **Restore Privacy branding** (icons and logos from the product brand kit)

## Launch

```bash
python launch_rx.py
```

Smoke / CI (no blocking GUI):

```bash
python launch_rx.py --smoke
```

## Tests

```bash
python -m unittest discover -s tests -v
```

## Bundled VPN extension (3.3.3)

Path: `extensions/restore-privacy-vpn/`

| Item | Detail |
|------|--------|
| Product | Restore Privacy VPN (browser-scoped Connect/Disconnect) |
| Version pin | **3.3.3** (`manifest.json` + `VERSION`) |
| Load | Unpacked MV3 package (background service worker, popup, `lib/vpn_core.js`) |

See `extensions/restore-privacy-vpn/VERSION_MAPPING.md` for source alignment notes.

## Layout

```
launch_rx.py          # entry point
rx/                   # pure shell modules + Tk chrome
  tabs.py
  privacy.py
  extensions.py
  shell.py
  ui_tk.py
extensions/
  restore-privacy-vpn/   # bundled VPN 3.3.3
assets/brand/            # Restore Privacy icons & logos
tests/
```

## Privacy

- `telemetry_enabled = false` and empty analytics endpoints in the shipped shell
- Start URL: `about:newtab` (private new-tab, not a third-party portal)
- Third-party cookies default off; HTTPS preferred for bare hosts

Native OS residual VPN remains a separate Restore Privacy product path: https://restoreprivacy.online/
