const crypto = require("crypto");
const fs = require("fs");

const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const source = fs.readFileSync(spec.sourcePath, "utf8");

function bundle(programId, name, origin, body) {
  return crypto
    .createHash("sha256")
    .update("chronoflux-Omega-v1")
    .update(String(programId))
    .update("\0")
    .update(String(name))
    .update("\0")
    .update(String(origin))
    .update("\0")
    .update(String(body))
    .digest("hex");
}

const hashed = bundle(spec.programId, spec.name, spec.origin, source);
const canonical = JSON.stringify({
  v: 1,
  id: spec.programId,
  name: spec.name,
  origin: spec.origin,
  bundle: hashed,
  n: spec.n,
});
const mac = crypto
  .createHash("sha256")
  .update("chronoflux-Omega-v1")
  .update(canonical)
  .digest("hex")
  .slice(0, 40);
const payload = JSON.stringify({
  v: 1,
  id: spec.programId,
  name: spec.name,
  origin: spec.origin,
  bundle: hashed,
  n: spec.n,
  mac,
});
const key = "vort1." + Buffer.from(payload).toString("base64url");
process.stdout.write(JSON.stringify({ bundle: hashed, mac, key }));
