"""OPEN-HOST for shear-testnet — the browser body cannot run Tor inside the chip alone.

Continuum tip `c02f787` pastes a vort1 key, fetches the origin, and shows a chip.
It has no in-wallet WebView and no Tor SOCKS. Apply
`continuum/host/0001-isolate-rx-chip-behind-tor-socks.patch` on shear-testnet
at `c02f787` as branch `cursor/rx-isolated-tor-host-d7ca`. This agent cannot
push to that repo. The patch does not edit invent or pool.

Do not land inside Rx.

Continuum today stores a pasted vortice `source` and shows only name, program id,
and origin (`wallet/lib/main.dart` `_vortex`). `parseVorticeSource` exists in
`wallet/lib/shear_vortex.dart` and is not used by the chip pane. Rx cannot open
inside the wallet until the host grows the hook below. The browser body stays in
this repo.

## Suggested shear-testnet PR

Title: Continuum: open Rx Privacy Browser in an isolated Tor WebView

When a deployed vortice source JSON has `kind: continuum-dapp` and
`programId: rx-privacy-browser-v1`, load `browser.html` from that JSON into a
WebView that is not the Continuum spend / shewall view.

Host contract, injected before page scripts:

```text
window.rxHost = {
  isolatedTorWebView: true,
  async status() {
    return {
      routing: Boolean,            // true only when both flags below are true
      private: Boolean,            // same value as routing; never true via VPN
      bootstrapped: Boolean,       // Tor bootstrap progress == 100
      bootstrapProgress: Number,   // 0..100
      circuitEstablished: Boolean, // GETINFO status/circuit-established == 1
      vpnRelay: false,             // must stay false; 1080 is not Tor
      isolatedTorWebView: true,
      socksListening: Boolean,     // loopback Tor SOCKS is accepting connections
      socksHost: "127.0.0.1",      // or "::1"; anything else is unprivate
      socksPort: 9050,             // loopback Tor SOCKS, never the VPN port
      status: routing ? "private via tor" : "unprivate unless tor",
    };
  },
  async navigate(url) {
    // Called only after the page gate allows it.
    // Fetch or load url inside the isolated WebView through Tor SOCKS
    // with remote DNS (socks5h). Do not use the system resolver for .onion.
    // If the circuit is down, do not open a socket. Return:
    //   { blocked: true, private: false, fetch: false,
    //     status: "unprivate unless tor", vpnRelay: false }
  },
};
```

### Required behavior

- Process or WebView profile is separate from shewall. No shared cookies, no
  spend seed, no Shear password prompt.
- Every socket from that WebView goes through Tor (embedded Tor or Arti, or a
  local `tor` SOCKS on 127.0.0.1). Remote DNS. Onion names stay hostnames.
- Until bootstrap is 100, a circuit is established, and loopback SOCKS is
  listening, show exactly `unprivate unless tor` and do not fetch clearnet
  or .onion. The page gate treats a missing `socksListening` / `socksHost`
  as unprivate. The status string alone does not permit a fetch.
- Do not attach Restore Privacy VPN, Shear Privacy VPN, or the wallet residual
  TUN. `vpnRelay` must be false. Do not proxy via port 1080.
- Do not mint SHE. Do not preinstall the chip. Do not mark the gallery Ready
  from this host change.
- Android (Continuum phone) is the primary surface. Desktop WebView can share
  the same hook.

### Out of scope for that PR

- Invent / pool / reconstruct plates.
- Raw peer RPC, a Send bypass, or any path that spends from shewall.
- Loading Restore Privacy VPN 3.3.3. Rx bootstrap does not require that extension.
- Replacing the Shear Privacy VPN vortice.
- Gallery Ready on vortices.shear.digital.
"""
