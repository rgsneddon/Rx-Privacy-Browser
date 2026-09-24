/**
 * Navigation gate for the Continuum browser UI.
 * Network fetches are refused unless Tor is bootstrapped and a circuit is up.
 * VPN relay is never treated as private.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.RxGate = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var UNPRIVATE_UNLESS_TOR = "unprivate unless tor";
  var PRIVATE_VIA_TOR = "private via tor";
  var VPN_PROXY_PORT = 1080;
  var TRACKING = {
    utm_source: 1,
    utm_medium: 1,
    utm_campaign: 1,
    utm_term: 1,
    utm_content: 1,
    utm_id: 1,
    fbclid: 1,
    gclid: 1,
    mc_cid: 1,
    mc_eid: 1,
    igshid: 1,
  };
  var TRACKERS = [
    "doubleclick.net",
    "google-analytics.com",
    "googletagmanager.com",
    "facebook.net",
    "scorecardresearch.com",
    "hotjar.com",
  ];

  function quotePlus(s) {
    return encodeURIComponent(s).replace(/%20/g, "+");
  }

  function isOnionHost(host) {
    var h = String(host || "").toLowerCase().replace(/\.$/, "");
    if (h.slice(-6) !== ".onion") return false;
    var labels = h.split(".");
    if (labels.length < 2 || labels[labels.length - 1] !== "onion") return false;
    var addr = labels[labels.length - 2];
    if (!/^[a-z2-7]{16}$/.test(addr) && !/^[a-z2-7]{56}$/.test(addr)) return false;
    for (var i = 0; i < labels.length - 1; i++) {
      if (!/^[a-z2-7]{1,63}$/.test(labels[i])) return false;
    }
    return true;
  }

  function isPrivateIp(host) {
    var m = /^(\d+)\.(\d+)\.(\d+)\.(\d+)$/.exec(host);
    if (m) {
      var a = +m[1];
      var b = +m[2];
      if (a === 10 || a === 127 || a === 0) return true;
      if (a === 169 && b === 254) return true;
      if (a === 172 && b >= 16 && b <= 31) return true;
      if (a === 192 && b === 168) return true;
      if (a >= 224) return true;
      return false;
    }
    var low = String(host || "").toLowerCase();
    if (low === "::1" || low === "0:0:0:0:0:0:0:1") return true;
    if (low.indexOf("fe80:") === 0) return true;
    if (low.indexOf("fc") === 0 || low.indexOf("fd") === 0) return true;
    return false;
  }

  function badHost(host) {
    var h = String(host || "").toLowerCase().replace(/\.$/, "");
    if (!h) return "empty-host";
    if (h === "localhost" || h === "localhost.localdomain" || /\.localhost$/.test(h) || /\.local$/.test(h)) {
      return "local-name";
    }
    if (isPrivateIp(h)) return "private-ip";
    if (h.slice(-6) === ".onion") {
      return isOnionHost(h) ? null : "bad-onion";
    }
    if (h.indexOf("..") >= 0 || !/^[a-z0-9.-]{1,253}$/.test(h)) return "bad-host";
    var labels = h.split(".");
    for (var i = 0; i < labels.length; i++) {
      var lab = labels[i];
      if (!lab || lab.length > 63 || lab.charAt(0) === "-" || lab.charAt(lab.length - 1) === "-") {
        return "bad-host";
      }
    }
    return null;
  }

  function stripQuery(query) {
    if (!query) return "";
    var parts = query.split("&");
    var kept = [];
    for (var i = 0; i < parts.length; i++) {
      if (!parts[i]) continue;
      var key = parts[i].split("=")[0];
      var decoded = key.replace(/\+/g, " ");
      try {
        decoded = decodeURIComponent(decoded);
      } catch (e) {
        decoded = key;
      }
      if (TRACKING[decoded.toLowerCase()]) continue;
      kept.push(parts[i]);
    }
    return kept.join("&");
  }

  function bad(reason) {
    return { ok: false, url: "", network: false, onion: false, reason: reason, host: "" };
  }

  function classifyUrl(raw) {
    var s = String(raw == null ? "" : raw).trim();
    if (!s) {
      return { ok: true, url: "about:newtab", network: false, onion: false, reason: "empty", host: "" };
    }
    var lower = s.toLowerCase();
    if (lower.indexOf("about:") === 0) {
      if (lower === "about:newtab" || lower === "about:blank" || lower.indexOf("about:search?") === 0) {
        return {
          ok: true,
          url: lower === "about:blank" ? "about:newtab" : s,
          network: false,
          onion: false,
          reason: "local",
          host: "",
        };
      }
      return bad("about-blocked");
    }
    if (
      /^[a-z][a-z0-9+.-]*:/i.test(s) &&
      lower.indexOf("http://") !== 0 &&
      lower.indexOf("https://") !== 0
    ) {
      return bad("scheme");
    }
    if (s.indexOf("://") < 0) {
      if (s.indexOf(" ") >= 0 || s.indexOf(".") < 0) {
        return {
          ok: true,
          url: "about:search?q=" + quotePlus(s),
          network: false,
          onion: false,
          reason: "local-search",
          host: "",
        };
      }
      var hostpart = s.split("/")[0].split("@").pop();
      var hostonly = hostpart.split(":")[0];
      if (isOnionHost(hostonly)) s = "http://" + s;
      else s = "https://" + s;
    }
    var match = /^(https?):\/\/([^\/?#]*)([^?#]*)(?:\?([^#]*))?/i.exec(s);
    if (!match) return bad("scheme");
    var scheme = match[1].toLowerCase();
    if (scheme !== "http" && scheme !== "https") return bad("scheme");
    var authority = match[2];
    var path = match[3] || "/";
    var query = match[4] || "";
    if (authority.indexOf("@") >= 0) return bad("userinfo");
    var host = "";
    var port = "";
    if (authority.charAt(0) === "[") {
      var end = authority.indexOf("]");
      if (end < 0) return bad("bad-host");
      host = authority.slice(1, end);
      port = authority.slice(end + 1).replace(/^:/, "");
    } else {
      var idx = authority.lastIndexOf(":");
      if (idx >= 0 && authority.indexOf(":") === idx) {
        host = authority.slice(0, idx);
        port = authority.slice(idx + 1);
      } else {
        host = authority;
      }
    }
    host = host.toLowerCase().replace(/\.$/, "");
    if (port) {
      if (!/^\d+$/.test(port)) return bad("port");
      var pnum = parseInt(port, 10);
      if (pnum < 1 || pnum > 65535) return bad("port");
    }
    var why = badHost(host);
    if (why) return bad(why);
    var onion = isOnionHost(host);
    if (path.charAt(0) !== "/") path = "/" + path;
    var q = stripQuery(query);
    var url = scheme + "://" + host + (port ? ":" + port : "") + path + (q ? "?" + q : "");
    return {
      ok: true,
      url: url,
      network: true,
      onion: onion,
      reason: onion ? "onion" : "clearnet",
      host: host,
    };
  }

  function isTrackerHost(host) {
    var h = String(host || "").toLowerCase().replace(/\.$/, "");
    for (var i = 0; i < TRACKERS.length; i++) {
      var suf = TRACKERS[i];
      if (h === suf || h.slice(-(suf.length + 1)) === "." + suf) return true;
    }
    return false;
  }

  function isRouting(status) {
    // A caption is not a circuit. Private only with loopback SOCKS up,
    // bootstrap 100, and a confirmed circuit. VPN port 1080 never qualifies.
    if (!status || typeof status !== "object") return false;
    if (status.vpnRelay === true) return false;
    if (typeof status.status === "string" && status.status !== PRIVATE_VIA_TOR) return false;
    var host = String(status.socksHost || "");
    if (host !== "127.0.0.1" && host !== "::1") return false;
    if (status.socksListening !== true) return false;
    if (typeof status.socksPort !== "number" && typeof status.socksPort !== "string") return false;
    var port = Number(status.socksPort);
    if (!isFinite(port) || port !== Math.floor(port) || port < 1 || port > 65535) return false;
    if (port === VPN_PROXY_PORT) return false;
    var progress = Number(status.bootstrapProgress);
    return (
      status.routing === true &&
      status.private === true &&
      status.bootstrapped === true &&
      status.circuitEstablished === true &&
      progress >= 100
    );
  }

  function decideNavigation(status, raw) {
    var routing = isRouting(status);
    var live = routing ? PRIVATE_VIA_TOR : UNPRIVATE_UNLESS_TOR;
    var classified = classifyUrl(raw);
    if (!classified.ok) {
      return {
        allow: false,
        fetch: false,
        local: false,
        private: routing,
        status: live,
        url: "",
        reason: classified.reason,
        engine: false,
        onion: false,
      };
    }
    if (!classified.network) {
      return {
        allow: true,
        fetch: false,
        local: true,
        private: routing,
        status: live,
        url: classified.url,
        reason: "local",
        engine: false,
        onion: false,
      };
    }
    if (!routing) {
      return {
        allow: false,
        fetch: false,
        local: false,
        private: false,
        status: UNPRIVATE_UNLESS_TOR,
        url: classified.url,
        reason: "tor-down",
        engine: false,
        onion: classified.onion,
      };
    }
    if (isTrackerHost(classified.host)) {
      return {
        allow: false,
        fetch: false,
        local: false,
        private: true,
        status: PRIVATE_VIA_TOR,
        url: classified.url,
        reason: "tracker-blocked",
        engine: false,
        onion: classified.onion,
      };
    }
    var engine = !!(status && (status.engineProxied === true || status.isolatedTorWebView === true));
    return {
      allow: true,
      fetch: true,
      local: false,
      private: true,
      status: PRIVATE_VIA_TOR,
      url: classified.url,
      reason: classified.reason,
      engine: engine,
      onion: classified.onion,
    };
  }

  return {
    UNPRIVATE_UNLESS_TOR: UNPRIVATE_UNLESS_TOR,
    PRIVATE_VIA_TOR: PRIVATE_VIA_TOR,
    classifyUrl: classifyUrl,
    decideNavigation: decideNavigation,
    isOnionHost: isOnionHost,
    isRouting: isRouting,
  };
});
