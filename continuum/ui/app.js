/* Rx Privacy Browser chrome. Fail closed: no network page unless Tor is routing. */
(function () {
  "use strict";
  var gate = window.RxGate;
  var UNPRIVATE = gate.UNPRIVATE_UNLESS_TOR;
  var PRIVATE = gate.PRIVATE_VIA_TOR;
  var seq = 1;
  var tabs = [];
  var activeId = 0;
  var pollTimer = 0;

  function boot() {
    var el = document.getElementById("rx-boot-data");
    try {
      var parsed = JSON.parse(el ? el.textContent || "{}" : "{}");
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function current() {
    for (var i = 0; i < tabs.length; i++) {
      if (tabs[i].id === activeId) return tabs[i];
    }
    return tabs[0];
  }

  function makeTab() {
    return {
      id: seq++,
      url: "about:newtab",
      title: "New Tab",
      history: [],
      forward: [],
      network: false,
    };
  }

  function paint(decision) {
    var el = document.getElementById("rx-status");
    var ok = decision && decision.private === true && decision.status === PRIVATE;
    el.textContent = ok ? PRIVATE : UNPRIVATE;
    document.body.classList.toggle("is-private", !!ok);
  }

  function forceUnprivate() {
    paint({ private: false, status: UNPRIVATE });
  }

  function blankFrame() {
    var frame = document.getElementById("view");
    frame.hidden = true;
    if (frame.getAttribute("src")) frame.removeAttribute("src");
  }

  function showNewTab() {
    blankFrame();
    var snap = document.getElementById("snapshot");
    snap.hidden = true;
    var panel = document.getElementById("panel");
    panel.hidden = false;
    panel.textContent = [
      "Rx Privacy Browser",
      "",
      "Private new tab. Telemetry is off. Tracker blocking is on.",
      "Traffic relay is Tor circuits only.",
      "Restore Privacy VPN and Shear Privacy VPN do not carry this browser.",
      "",
      "The status line is the session state.",
      "It reads " + UNPRIVATE + " until Tor is bootstrapped and a circuit is routing.",
      "Clearnet and .onion are not fetched until then.",
    ].join("\n");
  }

  function showBlocked(url) {
    blankFrame();
    var snap = document.getElementById("snapshot");
    snap.hidden = true;
    var panel = document.getElementById("panel");
    panel.hidden = false;
    forceUnprivate();
    panel.textContent = [
      UNPRIVATE,
      "",
      "Not fetched" + (url ? ": " + url : ""),
      "Tor is not bootstrapped and routing. No VPN relay.",
    ].join("\n");
  }

  function showSnapshot(page) {
    blankFrame();
    document.getElementById("panel").hidden = true;
    var snap = document.getElementById("snapshot");
    snap.hidden = false;
    snap.textContent = [
      page.status || PRIVATE,
      page.url || "",
      page.title || "",
      page.onion ? "onion via tor" : "clearnet via tor",
      "",
      page.text || "",
    ].join("\n");
  }

  function showEngine(url) {
    document.getElementById("panel").hidden = true;
    document.getElementById("snapshot").hidden = true;
    var frame = document.getElementById("view");
    frame.hidden = false;
    frame.src = url;
  }

  async function bridgeStatus() {
    try {
      var res = await fetch("/rx/status", { cache: "no-store" });
      if (!res.ok) return null;
      var body = await res.json();
      return body && typeof body === "object" ? body : null;
    } catch (e) {
      return null;
    }
  }

  function renderTabs() {
    var bar = document.getElementById("tabs");
    bar.textContent = "";
    tabs.forEach(function (tab) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tab" + (tab.id === activeId ? " active" : "");
      btn.textContent = (tab.title || "Tab").slice(0, 28);
      btn.addEventListener("click", function () {
        activeId = tab.id;
        document.getElementById("url").value = tab.url;
        renderTabs();
        if (tab.network) {
          go(tab.url, { replace: true, fromHistory: true });
        } else {
          showNewTab();
        }
      });
      bar.appendChild(btn);
    });
    var add = document.createElement("button");
    add.type = "button";
    add.textContent = "+";
    add.addEventListener("click", function () {
      var tab = makeTab();
      tabs.push(tab);
      activeId = tab.id;
      document.getElementById("url").value = tab.url;
      renderTabs();
      showNewTab();
    });
    bar.appendChild(add);
    var close = document.createElement("button");
    close.type = "button";
    close.textContent = "×";
    close.addEventListener("click", function () {
      if (tabs.length === 1) {
        var only = makeTab();
        tabs = [only];
        activeId = only.id;
      } else {
        var idx = 0;
        for (var i = 0; i < tabs.length; i++) if (tabs[i].id === activeId) idx = i;
        tabs.splice(idx, 1);
        activeId = tabs[Math.min(idx, tabs.length - 1)].id;
      }
      document.getElementById("url").value = current().url;
      renderTabs();
      if (!current().network) showNewTab();
      else go(current().url, { replace: true, fromHistory: true });
    });
    bar.appendChild(close);
  }

  async function hostStatus(base) {
    if (!window.rxHost || typeof window.rxHost.status !== "function") return base;
    try {
      var host = await window.rxHost.status();
      if (!host || typeof host !== "object") {
        forceUnprivate();
        return null;
      }
      if (host.vpnRelay === true) {
        forceUnprivate();
        return null;
      }
      var merged = Object.assign({}, base, host);
      merged.engineProxied = base.engineProxied === true;
      if (host.isolatedTorWebView === true) merged.isolatedTorWebView = true;
      return merged;
    } catch (e) {
      forceUnprivate();
      return null;
    }
  }

  async function loadStatus() {
    var info = boot();
    var status;
    try {
      var res = await fetch("/rx/status", { cache: "no-store" });
      if (!res.ok) throw new Error("status");
      status = await res.json();
    } catch (e) {
      status = {
        routing: false,
        private: false,
        bootstrapped: false,
        bootstrapProgress: 0,
        circuitEstablished: false,
        vpnRelay: false,
        status: UNPRIVATE,
      };
    }
    status.engineProxied = info.engineProxied === true;
    status.isolatedTorWebView = info.isolatedTorWebView === true;
    if (window.rxHost && window.rxHost.isolatedTorWebView === true) {
      status.isolatedTorWebView = true;
    }
    return hostStatus(status);
  }

  function remember(tab, url, title, network) {
    if (tab.url && tab.url !== url) tab.history.push(tab.url);
    tab.forward = [];
    tab.url = url;
    tab.title = title || tab.title;
    tab.network = !!network;
    document.getElementById("url").value = url;
    renderTabs();
  }

  async function go(raw, opts) {
    opts = opts || {};
    var tab = current();
    var status = await loadStatus();
    if (!status) {
      showBlocked(raw);
      return false;
    }
    var decision = gate.decideNavigation(status, raw);
    paint(decision);
    if (decision.reason === "secret-refused") {
      document.getElementById("url").value = "";
      blankFrame();
      document.getElementById("snapshot").hidden = true;
      var heldSecret = document.getElementById("panel");
      heldSecret.hidden = false;
      heldSecret.textContent = [decision.private === true ? PRIVATE : UNPRIVATE, "Refused."].join("\n");
      return false;
    }
    if (!decision.allow || decision.fetch !== true) {
      if (decision.local && decision.allow) {
        if (!opts.replace && !opts.fromHistory) remember(tab, decision.url, "New Tab", false);
        else {
          tab.url = decision.url;
          tab.network = false;
          tab.title = "New Tab";
          document.getElementById("url").value = decision.url;
          renderTabs();
        }
        showNewTab();
        return true;
      }
      if (decision.private === true && decision.status === PRIVATE) {
        paint(decision);
        blankFrame();
        document.getElementById("snapshot").hidden = true;
        var held = document.getElementById("panel");
        held.hidden = false;
        held.textContent = [PRIVATE, decision.reason || "blocked", decision.url || ""].join("\n");
        return false;
      }
      showBlocked(decision.url || raw);
      if (decision.reason === "tor-down") tab.network = false;
      return false;
    }
    if (decision.engine && window.rxHost && typeof window.rxHost.navigate === "function") {
      var hosted;
      try {
        hosted = await window.rxHost.navigate(decision.url);
      } catch (e) {
        showBlocked(decision.url);
        return false;
      }
      if (!hosted || hosted.blocked || hosted.private !== true || hosted.status !== PRIVATE || hosted.vpnRelay === true) {
        showBlocked(decision.url);
        return false;
      }
      if (!opts.replace && !opts.fromHistory) remember(tab, decision.url, hosted.title || decision.url, true);
      else {
        tab.url = decision.url;
        tab.network = true;
        tab.title = hosted.title || tab.title;
        renderTabs();
      }
      paint({ private: true, status: PRIVATE });
      if (hosted.text) showSnapshot(hosted);
      else showEngine(decision.url);
      return true;
    }
    if (decision.engine && status.engineProxied === true) {
      var proof = await bridgeStatus();
      if (!gate.isRouting(proof)) {
        showBlocked(decision.url);
        return false;
      }
      if (!opts.replace && !opts.fromHistory) remember(tab, decision.url, decision.url, true);
      else {
        tab.url = decision.url;
        tab.network = true;
        renderTabs();
      }
      paint({ private: true, status: PRIVATE });
      showEngine(decision.url);
      return true;
    }
    var page;
    try {
      var info = boot();
      var res = await fetch("/rx/navigate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Rx-Token": info.token || "",
        },
        body: JSON.stringify({ url: decision.url }),
      });
      page = await res.json();
    } catch (e) {
      showBlocked(decision.url);
      return false;
    }
    if (!page || page.private !== true || page.status !== PRIVATE || page.vpnRelay === true) {
      showBlocked(decision.url || (page && page.url) || "");
      return false;
    }
    if (page.blocked || page.fetch !== true) {
      paint({ private: true, status: PRIVATE });
      blankFrame();
      document.getElementById("snapshot").hidden = true;
      var refused = document.getElementById("panel");
      refused.hidden = false;
      refused.textContent = [PRIVATE, page.reason || "blocked", page.url || ""].join("\n");
      return false;
    }
    if (!opts.replace && !opts.fromHistory) remember(tab, page.url || decision.url, page.title || page.url, true);
    else {
      tab.url = page.url || decision.url;
      tab.title = page.title || tab.title;
      tab.network = true;
      document.getElementById("url").value = tab.url;
      renderTabs();
    }
    paint({ private: true, status: PRIVATE });
    showSnapshot(page);
    return true;
  }

  async function refreshStatus() {
    var status = await loadStatus();
    if (!status) {
      showBlocked(current().url);
      return;
    }
    var decision = gate.decideNavigation(status, "about:newtab");
    paint(decision);
    var tab = current();
    if (tab.network && decision.private !== true) {
      showBlocked(tab.url);
      tab.network = false;
    }
  }

  async function back() {
    var tab = current();
    if (!tab.history.length) return;
    var target = tab.history[tab.history.length - 1];
    var previous = tab.url;
    var ok = await go(target, { replace: true, fromHistory: true });
    if (!ok) return;
    tab.history.pop();
    tab.forward.push(previous);
  }

  async function forward() {
    var tab = current();
    if (!tab.forward.length) return;
    var target = tab.forward[tab.forward.length - 1];
    var previous = tab.url;
    var ok = await go(target, { replace: true, fromHistory: true });
    if (!ok) return;
    tab.forward.pop();
    tab.history.push(previous);
  }

  function reload() {
    go(current().url, { replace: true, fromHistory: true });
  }

  async function openEngine() {
    var info = boot();
    var data;
    try {
      var res = await fetch("/rx/engine", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Rx-Token": info.token || "",
        },
        body: "{}",
      });
      data = await res.json();
    } catch (e) {
      showBlocked(current().url);
      return;
    }
    if (!data || data.private !== true || data.status !== PRIVATE || data.vpnRelay === true) {
      showBlocked(current().url);
      return;
    }
    paint({ private: true, status: PRIVATE });
    if (data.launched !== true) {
      blankFrame();
      document.getElementById("snapshot").hidden = true;
      var panel = document.getElementById("panel");
      panel.hidden = false;
      panel.textContent = PRIVATE + "\n\nTor engine did not start. Snapshot navigation still uses Tor.";
    }
  }

  document.getElementById("go").addEventListener("click", function () {
    go(document.getElementById("url").value);
  });
  document.getElementById("url").addEventListener("keydown", function (ev) {
    if (ev.key === "Enter") go(document.getElementById("url").value);
  });
  document.getElementById("back").addEventListener("click", back);
  document.getElementById("forward").addEventListener("click", forward);
  document.getElementById("reload").addEventListener("click", reload);
  document.getElementById("engine").addEventListener("click", openEngine);

  var first = makeTab();
  tabs = [first];
  activeId = first.id;
  renderTabs();
  showNewTab();
  forceUnprivate();
  refreshStatus();
  pollTimer = window.setInterval(refreshStatus, 2000);
})();
