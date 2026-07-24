/**
 * Thin Chrome proxy API adapter. Pure core decides config; this applies it.
 * In unit tests, inject a fake chrome.proxy.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.RptProxyAdapter = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  /**
   * @param {object} chromeApi - chrome global or mock { proxy: { settings: { set, clear } } }
   */
  function createProxyAdapter(chromeApi) {
    if (!chromeApi || !chromeApi.proxy || !chromeApi.proxy.settings) {
      throw new Error("chrome.proxy.settings API unavailable");
    }
    var settings = chromeApi.proxy.settings;

    function applyProxyConfig(proxyConfig) {
      return new Promise(function (resolve, reject) {
        try {
          settings.set(
            { value: proxyConfig, scope: "regular" },
            function () {
              var err =
                chromeApi.runtime && chromeApi.runtime.lastError
                  ? chromeApi.runtime.lastError
                  : null;
              if (err) {
                reject(new Error(err.message || String(err)));
              } else {
                resolve(true);
              }
            }
          );
        } catch (e) {
          reject(e);
        }
      });
    }

    function clearProxyConfig() {
      return new Promise(function (resolve, reject) {
        try {
          settings.clear({ scope: "regular" }, function () {
            var err =
              chromeApi.runtime && chromeApi.runtime.lastError
                ? chromeApi.runtime.lastError
                : null;
            if (err) {
              reject(new Error(err.message || String(err)));
            } else {
              resolve(true);
            }
          });
        } catch (e) {
          reject(e);
        }
      });
    }

    return {
      applyProxyConfig: applyProxyConfig,
      clearProxyConfig: clearProxyConfig,
    };
  }

  return { createProxyAdapter: createProxyAdapter };
});
