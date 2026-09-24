# Rx Privacy Browser

**Rx Privacy Browser** is a Continuum vortice: a browser you install by pasting a `vort1.` deploy key. It is not preinstalled in shear-wallet or shear-testnet.

Traffic for this browser is **Tor circuits only**. Clearnet and `.onion` are fetched through a Tor SOCKS proxy with remote DNS. Typed `.onion` names are not sent to the system resolver.

Bootstrap does **not** require the bundled Restore Privacy VPN extension. The shell starts with extensions disabled, and loading that package is refused. It is not the relay. Shear Privacy VPN stays a separate vortice. The Continuum host hook, when added, is status plus Tor SOCKS only: no peer RPC, no Send bypass, no invent or pool edits.

**Gallery:** not Ready. Do not mark this Ready on vortices.shear.digital until an onion smoke is not-refuted.

## Session status (code, not a caption)

The session is private only when Tor is bootstrapped (`PROGRESS=100`) **and** a circuit is established.

- Tor down, or SOCKS open without a confirmed circuit: navigation to clearnet and `.onion` is **not fetched**. The status line is exactly `unprivate unless tor`.
- A status caption of `private via tor` does not unlock navigation. The session and the page gate both require a listening loopback SOCKS port (`127.0.0.1` or `::1`), bootstrap 100, and `circuit-established`. If any of those is missing, the status stays `unprivate unless tor` and nothing is fetched.
- Tor bootstrapped and routing: status is `private via tor`. Clearnet goes out through Tor. `.onion` is connected by hostname (no local DNS).
- Port `1080` (the bundled VPN extension proxy) is rejected. `vpnRelay` is false.
- The Tor engine may frame a remote page only after a live circuit check, and only in the process launched with that proxy. Other clients keep `frame-src 'none'`.

Local `about:newtab` still opens when Tor is down. It does not make the session private.

A paste that is a seed, mnemonic, `shewall` path, or private key is refused. It is not fetched, not stored as the tab URL, and not echoed in the status line. The same class of material is refused from Rx into Continuum Send and Closure by the host gate.

## Continuum install

1. Host the pinned file unchanged:
   `continuum/rx-privacy-browser.vortice.json`
   URL path: `/vortice/rx-privacy-browser.vortice.json`
2. Mint a `vort1.` key for that exact origin and those exact bytes (below).
3. In the Shear wallet: **Vortex → Add new vortice → paste the key**.
   The wallet downloads the origin, checks the bundle hash, and stores the dapp.
4. Opening the chip shows a real page only after the Continuum host hook. Tip `c02f787` stores the body and shows name, program id, and origin. It does not run a WebView or Tor SOCKS. That host change is **OPEN-HOST**: apply `continuum/host/0001-isolate-rx-chip-behind-tor-socks.patch` on shear-testnet at `c02f787`. It is an out-of-process surface, status `unprivate unless tor`, and a Tor SOCKS bridge. No preinstall. No second vault. No invent or pool edits.

This repo does not mint SHE, does not ask for a Shear password or `shewall.bin`, and does not use a reserved program id.

| Field | Value |
| --- | --- |
| programId | `rx-privacy-browser-v1` |
| name | `Rx Privacy Browser` |
| example origin | `https://rx-privacy-browser.example/vortice/rx-privacy-browser.vortice.json` |
| path | `/vortice/rx-privacy-browser.vortice.json` |

`.example` is a documentation host. Point the key at the origin you actually serve. If the bytes change, mint a new key.

### Serve the origin

Static file only (no browse proxy), exact bytes:

```bash
python -m rx.serve --host 127.0.0.1 --port 8080
# http://127.0.0.1:8080/vortice/rx-privacy-browser.vortice.json
```

Bind a public address only for this static server when you publish. Do not expose `python -m rx.bridge` — that process can fetch through Tor and is loopback-only on purpose.

### Mint

Local key (no Shear node, no SHE). The wallet checks the MAC and the bundle hash against the bytes it downloads:

```bash
python -m rx.mint --origin http://127.0.0.1:8080/vortice/rx-privacy-browser.vortice.json
```

Node sketch, same fields as shear-testnet `store.mintVorticeDeployKey`:

```text
store.mintVorticeDeployKey({
  programId: 'rx-privacy-browser-v1',
  name: 'Rx Privacy Browser',
  origin: 'https://YOUR_HOST/vortice/rx-privacy-browser.vortice.json',
  source: <exact bytes of continuum/rx-privacy-browser.vortice.json>,
})
```

A program id can be minted once per node. Republish only when you intend to mint again.

## Tor requirements

- A Tor daemon (`tor`) or an embedded Tor/Arti that exposes SOCKS on loopback and a control port with cookie auth.
- Bootstrap must reach 100 and `status/circuit-established` must be 1 before any clearnet or onion fetch.
- Remote DNS (SOCKS5 domain name / `socks5h`). Typed `.onion` names are not sent to the system resolver.
- The bridge can spawn `tor` in `~/.local/share/rx-privacy-browser/tor` (override with `RX_STATE_DIR`). That directory is refused if the path overlaps `shewall` or the Shear wallet tree.
- Android Continuum needs the host hook (isolated WebView + Tor SOCKS). A desktop Tk or Chrome window is not the phone WebView.

Check a circuit and fetch one onion (default DuckDuckGo onion) only when Tor is up:

```bash
python -m rx.onion_smoke --wait 60
```

Exit `2` means the session was not private: the process prints `unprivate unless tor` and `not_fetched`. It does not fall back to clearnet.

## Run the browser

```bash
python launch_rx.py
```

Opens the loopback bridge at `http://127.0.0.1:8844/`. Tabs, address bar, back, forward, and reload call the same gate.

- Tor down: the status line is `unprivate unless tor`. Go does not fetch.
- Tor up, snapshot mode: the bridge fetches the page through Tor and shows text. Page scripts are not executed in the unproxied shell, so they cannot bypass Tor.
- **Open Tor engine** (only after a circuit exists) starts an isolated Chrome or Firefox profile with Tor SOCKS, remote DNS, extensions disabled, and WebRTC non-proxied UDP disabled. That window can load full pages, including `.onion`, inside the proxied process. The bridge enables remote frames only when that process presents its engine mark and Tor is still routing. It does not load the VPN extension.

```bash
python launch_rx.py --tk       # Tk shell, same fail-closed gate, no system browser
python launch_rx.py --smoke    # identity check, no network
```

Rebuild the pinned body after UI edits:

```bash
python -m rx.pack
```

## Tests

```bash
python -m unittest discover -s tests -v
```

Covers Tor config, onion URL acceptance, fail-closed navigation (no socket while Tor is down), a SOCKS5 onion CONNECT, vort1 bundle stability, and the VPN-port refusal.

## Privacy

- Telemetry off. Private new tab. Tracker blocking on (tracker hosts are not fetched; `utm_*` and similar query parameters are stripped).
- No shewall read. Browser profile and Tor data use a separate directory.
- Do not describe this as unlinkable from a Shear session on the same device.
- Clearnet-via-Tor is still Tor exit traffic. Onion services stay on Tor circuits.

## Layout

```text
launch_rx.py                         # bridge by default; --smoke; --tk
rx/                                  # gate, Tor SOCKS, mint, bridge
continuum/rx-privacy-browser.vortice.json   # exact origin bytes
continuum/browser.html               # UI embedded in that JSON
continuum/HOST_HOOK.md               # shear-testnet follow-up, not applied there
continuum/ui/                        # gate + chrome sources
extensions/restore-privacy-vpn/      # on-disk package, not the traffic relay
```
