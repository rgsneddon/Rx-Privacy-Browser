# Restore Privacy VPN — browser extension (catalog 3.3.3)

**Not the Rx Privacy Browser relay.** The Continuum Rx vortice does not load this
extension and does not send clearnet or .onion traffic through it. Shear Privacy
VPN remains a separate vortice. Rx browsing is Tor circuits only.

Chromium **Manifest V3** extension for **browser-scoped** Connect / Disconnect.
This package is dormant inside Rx. Do not point the Rx bridge or engine at its proxy.

## Honesty

- **Browser only:** routes this browser’s traffic via the configured **local proxy** path (`chrome.proxy`).
- **Not OS residual:** does **not** create Wintun / Packet Tunnel / system residual TUN. Paid native clients (Windows · Android · macOS · iOS · Linux) remain the residual product path.
- Default proxy target is `socks5://127.0.0.1:1080` (local companion / future bridge). Override via Connect options if your browser stack exposes a different local path.

## Load unpacked (developer)

1. Open Chromium / Chrome / Edge → `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select this `browser_extension/` directory

Any custom browser that loads Chromium MV3 extensions can use the same package.

## Files

| Path | Role |
|------|------|
| `manifest.json` | MV3 manifest (`proxy`, `storage`) |
| `lib/vpn_core.js` | Pure enable/disable/status (unit-tested) |
| `lib/proxy_adapter.js` | `chrome.proxy.settings` adapter |
| `background.js` | Service worker |
| `popup.html` / `popup.js` / `popup.css` | Connect / Disconnect UI |

## Package zip (release asset)

```bash
cd browser_extension
zip -r ../releases/3.3.3/restore-privacy-browser-extension-3.3.3.zip . \
  -x '*.DS_Store' -x '*__pycache__*'
```

## Pay / native residual

https://restoreprivacy.online/
