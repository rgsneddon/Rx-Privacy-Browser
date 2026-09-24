# HANDOFF — CODEBASE-RX-TOR-MAP

Authoritative map: **CODEBASE-RX-TOR-MAP**. Gallery stays **not Ready** until an onion smoke is not-refuted. This host work is separate from invent, pool, ledger reconstruct, spendable, and shewall.

## Pins

| Pin | Value |
| --- | --- |
| WebView package | `webview_flutter` **4.13.0** for Android, iOS, and macOS |
| In `wallet/pubspec.yaml` | **no**. Linux and Windows Continuum release builds have no implementation of that package. `RxWebViewHost` is the mount. Page loads do not use `url_launcher`. |
| Linux / macOS Tor binary | `tor` (not vendored) |
| Windows Tor binary | `tor.exe` (not vendored) |
| Android Tor binary | `libtor.so` (not vendored) |
| SOCKS | `127.0.0.1:9070` |
| Control | `127.0.0.1:9071` |
| VPN port | `1080` is refused. It is not the browser relay. |
| Missing binary | status stays `unprivate unless tor` |
| Live vort1 origin | **none**. No public origin is published. |
| Example origin | `https://rx-privacy-browser.example/vortice/rx-privacy-browser.vortice.json` |
| Gallery | `galleryReady: false` |

## Host (shear-testnet, not this repo’s default branch)

Tip Continuum `c02f787` cannot render the Tor browser body. Apply both patches on that commit, branch `cursor/rx-isolated-tor-host-d7ca`:

1. `continuum/host/0001-isolate-rx-chip-behind-tor-socks.patch`
2. `continuum/host/0002-pin-rx-webview-host-and-tor-sidecars.patch`

Local tip of that branch is `c90a1c4`. Push to `rgsneddon/shear-testnet` returned 403 for this agent, so the host PR is these patches. They do not edit invent or pool.

The second patch:

- `wallet/lib/main.dart` third-party pane mounts `RxWebViewHost` only for `rx-privacy-browser-v1`. Other chips stay metadata plus Remove.
- Deploy/fetch still uses the origin `HttpClient` as a vort1 pin. `browserMayUseOriginClient()` is false.
- `wallet/lib/shear_tor_bridge.dart` plus `wallet/tor/` sidecars. Binaries are not in the tree.

`dart wallet/tool/rx_host_check.dart` printed `rx host check ok`.

## Rx body

- `rx/privacy.py` `navigate` is the Tor gate. `RxShell` navigation calls it before the session. Bootstrap does not require the VPN extension.
- `enableVpn(..., { forRxBrowser: true })` returns error `unprivate unless tor` and a null proxy config. The dormant package’s own Connect tests still use port 1080. Rx Python does not call `enableVpn`.
