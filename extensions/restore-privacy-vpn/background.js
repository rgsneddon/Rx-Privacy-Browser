/**
 * Service worker: Connect/Disconnect browser-scoped proxy via pure vpn_core.
 */
/* global chrome, importScripts, RptBrowserVpnCore, RptProxyAdapter */

importScripts("lib/vpn_core.js", "lib/proxy_adapter.js");

var STORAGE_KEY = "rpt_browser_vpn_state";
var core = RptBrowserVpnCore;
var adapter = null;

try {
  adapter = RptProxyAdapter.createProxyAdapter(chrome);
} catch (e) {
  console.warn("RPT browser extension: proxy adapter init failed", e);
}

function loadState() {
  return new Promise(function (resolve) {
    chrome.storage.local.get([STORAGE_KEY], function (data) {
      resolve(data[STORAGE_KEY] || core.defaultState());
    });
  });
}

function saveState(state) {
  return new Promise(function (resolve) {
    var payload = {};
    payload[STORAGE_KEY] = state;
    chrome.storage.local.set(payload, function () {
      resolve(state);
    });
  });
}

function setBadge(state) {
  var connected = core.isConnected(state);
  chrome.action.setBadgeText({ text: connected ? "ON" : "" });
  chrome.action.setBadgeBackgroundColor({
    color: connected ? "#39ff6a" : "#666666",
  });
}

async function connect(opts) {
  var prev = await loadState();
  var next = core.enableVpn(prev, opts || {});
  if (next.status === core.STATUS.ERROR) {
    await saveState(next);
    setBadge(next);
    return next;
  }
  if (adapter && next.proxyConfig) {
    try {
      await adapter.applyProxyConfig(next.proxyConfig);
    } catch (err) {
      next = {
        status: core.STATUS.ERROR,
        proxyConfig: null,
        error: String(err && err.message ? err.message : err),
        browserScopeOnly: true,
        productTitle: next.productTitle,
        catalogVersion: next.catalogVersion,
      };
      await saveState(next);
      setBadge(next);
      return next;
    }
  }
  await saveState(next);
  setBadge(next);
  return next;
}

async function disconnect() {
  var prev = await loadState();
  if (adapter) {
    try {
      await adapter.clearProxyConfig();
    } catch (err) {
      var failed = core.disableVpn(prev);
      failed.status = core.STATUS.ERROR;
      failed.error = String(err && err.message ? err.message : err);
      await saveState(failed);
      setBadge(failed);
      return failed;
    }
  }
  var next = core.disableVpn(prev);
  await saveState(next);
  setBadge(next);
  return next;
}

chrome.runtime.onInstalled.addListener(function () {
  loadState().then(setBadge);
});

chrome.runtime.onStartup.addListener(function () {
  loadState().then(async function (state) {
    // Re-apply proxy if we were connected (browser restart)
    if (core.isConnected(state) && adapter && state.proxyConfig) {
      try {
        await adapter.applyProxyConfig(state.proxyConfig);
      } catch (e) {
        state = core.disableVpn(state);
        state.error = "re-apply failed: " + e;
        await saveState(state);
      }
    }
    setBadge(state);
  });
});

chrome.runtime.onMessage.addListener(function (msg, _sender, sendResponse) {
  if (!msg || !msg.type) {
    sendResponse({ ok: false, error: "bad message" });
    return false;
  }
  if (msg.type === "get_status") {
    loadState().then(function (state) {
      sendResponse({
        ok: true,
        state: state,
        disclaimer: core.browserScopeDisclaimer(),
      });
    });
    return true;
  }
  if (msg.type === "connect") {
    connect(msg.opts || {}).then(function (state) {
      sendResponse({ ok: state.status !== core.STATUS.ERROR, state: state });
    });
    return true;
  }
  if (msg.type === "disconnect") {
    disconnect().then(function (state) {
      sendResponse({ ok: true, state: state });
    });
    return true;
  }
  sendResponse({ ok: false, error: "unknown type" });
  return false;
});
