const assert = require("assert");
const fs = require("fs");
const path = require("path");
const gate = require("./gate.js");

const root = path.resolve(__dirname, "..", "..");
const vectors = JSON.parse(fs.readFileSync(path.join(root, "tests", "url_vectors.json"), "utf8"));

for (const v of vectors) {
  const got = gate.classifyUrl(v.in);
  assert.strictEqual(got.ok, v.ok, "ok " + JSON.stringify(v.in));
  assert.strictEqual(got.network, v.network, "network " + JSON.stringify(v.in));
  assert.strictEqual(got.onion, v.onion, "onion " + JSON.stringify(v.in));
  assert.strictEqual(got.url, v.url, "url " + JSON.stringify(v.in) + " -> " + got.url);
  assert.strictEqual(got.reason, v.reason, "reason " + JSON.stringify(v.in) + " -> " + got.reason);
}

const down = {
  routing: false,
  private: false,
  bootstrapped: false,
  bootstrapProgress: 0,
  circuitEstablished: false,
  vpnRelay: false,
  socksPort: 9050,
};
const onion = "http://" + "c".repeat(56) + ".onion/";
const blocked = gate.decideNavigation(down, onion);
assert.strictEqual(blocked.allow, false);
assert.strictEqual(blocked.fetch, false);
assert.strictEqual(blocked.private, false);
assert.strictEqual(blocked.status, "unprivate unless tor");
assert.strictEqual(blocked.reason, "tor-down");

const up = {
  routing: true,
  private: true,
  bootstrapped: true,
  bootstrapProgress: 100,
  circuitEstablished: true,
  vpnRelay: false,
  socksListening: true,
  socksHost: "127.0.0.1",
  socksPort: 9050,
  engineProxied: false,
  isolatedTorWebView: false,
};
const vpn = Object.assign({}, up, { vpnRelay: true });
const vpnNav = gate.decideNavigation(vpn, "https://example.com/");
assert.strictEqual(vpnNav.fetch, false);
assert.strictEqual(vpnNav.status, "unprivate unless tor");
const allowed = gate.decideNavigation(up, onion);
assert.strictEqual(allowed.allow, true);
assert.strictEqual(allowed.fetch, true);
assert.strictEqual(allowed.private, true);
assert.strictEqual(allowed.status, "private via tor");
assert.strictEqual(allowed.engine, false);

const port = gate.decideNavigation(Object.assign({}, up, { socksPort: 1080 }), onion);
assert.strictEqual(port.fetch, false);
assert.strictEqual(port.status, "unprivate unless tor");

const caption = Object.assign({}, down, { status: "private via tor" });
const captionNav = gate.decideNavigation(caption, "https://example.com/");
assert.strictEqual(captionNav.fetch, false);
assert.strictEqual(captionNav.private, false);
assert.strictEqual(captionNav.status, "unprivate unless tor");
assert.strictEqual(captionNav.engine, false);

const quietSocks = gate.decideNavigation(Object.assign({}, up, { socksListening: false }), onion);
assert.strictEqual(quietSocks.fetch, false);
assert.strictEqual(quietSocks.status, "unprivate unless tor");

const remoteSocks = gate.decideNavigation(Object.assign({}, up, { socksHost: "10.0.0.1" }), onion);
assert.strictEqual(remoteSocks.fetch, false);
assert.strictEqual(remoteSocks.status, "unprivate unless tor");

const partial = gate.decideNavigation(Object.assign({}, up, { bootstrapProgress: 99, bootstrapped: false }), onion);
assert.strictEqual(partial.fetch, false);
assert.strictEqual(partial.status, "unprivate unless tor");

const noCircuit = gate.decideNavigation(Object.assign({}, up, { circuitEstablished: false }), onion);
assert.strictEqual(noCircuit.fetch, false);
assert.strictEqual(noCircuit.status, "unprivate unless tor");

const contradicted = gate.decideNavigation(Object.assign({}, up, { status: "unprivate unless tor" }), onion);
assert.strictEqual(contradicted.fetch, false);
assert.strictEqual(contradicted.status, "unprivate unless tor");

const mnemonic = new Array(11).fill("abandon").concat(["about"]).join(" ");
const secretDown = gate.decideNavigation(down, mnemonic);
assert.strictEqual(secretDown.fetch, false);
assert.strictEqual(secretDown.reason, "secret-refused");
assert.strictEqual(secretDown.url, "");
assert.strictEqual(secretDown.status, "unprivate unless tor");
assert.strictEqual(secretDown.engine, false);
const secretUp = gate.decideNavigation(up, "shewall.bin");
assert.strictEqual(secretUp.fetch, false);
assert.strictEqual(secretUp.reason, "secret-refused");
assert.strictEqual(secretUp.url, "");
assert.strictEqual(secretUp.status, "private via tor");
assert.strictEqual(secretUp.private, true);
const hexKey = gate.decideNavigation(down, "ab".repeat(32));
assert.strictEqual(hexKey.reason, "secret-refused");
assert.strictEqual(hexKey.url, "");

const loopback6 = gate.decideNavigation(Object.assign({}, up, { socksHost: "::1" }), onion);
assert.strictEqual(loopback6.fetch, true);
assert.strictEqual(loopback6.status, "private via tor");

console.log("gate ok");
