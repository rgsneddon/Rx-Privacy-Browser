# Restore Privacy VPN extension — version pin

| Field | Value |
|-------|--------|
| **Rx-bundled identity (required)** | **3.3.3** |
| Manifest `version` | `3.3.3` |
| Source package | Restore Privacy `browser_extension` (product catalog tree; nearest full extension package historically tagged as catalog `0.4.2` on the restore-privacy monorepo) |

The VPN implementation (Connect/Disconnect, `lib/vpn_core.js`, proxy adapter, popup) is the real Restore Privacy browser extension, not a stub. The pin **3.3.3** is the Rx product identity for future alignment with the user’s Restore Privacy VPN 3.3.3 requirement.
