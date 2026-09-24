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

const vpn = Object.assign({}, down, {
  routing: true,
  private: true,
  bootstrapped: true,
  bootstrapProgress: 100,
  circuitEstablished: true,
  vpnRelay: true,
});
const vpnNav = gate.decideNavigation(vpn, "https://example.com/");
assert.strictEqual(vpnNav.fetch, false);
assert.strictEqual(vpnNav.status, "unprivate unless tor");

const up = {
  routing: true,
  private: true,
  bootstrapped: true,
  bootstrapProgress: 100,
  circuitEstablished: true,
  vpnRelay: false,
  socksPort: 9050,
  engineProxied: false,
  isolatedTorWebView: false,
};
const allowed = gate.decideNavigation(up, onion);
assert.strictEqual(allowed.allow, true);
assert.strictEqual(allowed.fetch, true);
assert.strictEqual(allowed.private, true);
assert.strictEqual(allowed.status, "private via tor");
assert.strictEqual(allowed.engine, false);

const port = gate.decideNavigation(Object.assign({}, up, { socksPort: 1080 }), onion);
assert.strictEqual(port.fetch, false);
assert.strictEqual(port.status, "unprivate unless tor");

console.log("gate ok");
