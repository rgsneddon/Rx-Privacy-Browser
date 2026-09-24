"""Follow-up for shear-testnet — do not land inside Rx.

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
- Until bootstrap is 100 and a circuit is established, show exactly
  `unprivate unless tor` and do not fetch clearnet or .onion.
- Do not attach Restore Privacy VPN, Shear Privacy VPN, or the wallet residual
  TUN. `vpnRelay` must be false. Do not proxy via port 1080.
- Do not mint SHE. Do not preinstall the chip. Do not mark the gallery Ready
  from this host change.
- Android (Continuum phone) is the primary surface. Desktop WebView can share
  the same hook.

### Out of scope for that PR

- Invent / pool / reconstruct plates.
- Replacing the Shear Privacy VPN vortice.
- Gallery Ready on vortices.shear.digital.
"""
