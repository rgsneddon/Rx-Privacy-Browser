/**
 * Popup UI: Connect / Disconnect + status for browser-scoped VPN.
 */
(function () {
  "use strict";

  var statusText = document.getElementById("status-text");
  var errorText = document.getElementById("error-text");
  var disclaimer = document.getElementById("disclaimer");
  var btnConnect = document.getElementById("btn-connect");
  var btnDisconnect = document.getElementById("btn-disconnect");
  var panel = document.getElementById("panel");

  function render(state, disc) {
    var status = (state && state.status) || "disconnected";
    statusText.textContent = status;
    panel.classList.toggle("is-connected", status === "connected");
    if (state && state.error) {
      errorText.hidden = false;
      errorText.textContent = state.error;
    } else {
      errorText.hidden = true;
      errorText.textContent = "";
    }
    if (disc) {
      disclaimer.textContent = disc;
    }
    btnConnect.disabled = status === "connected";
    btnDisconnect.disabled = status === "disconnected";
  }

  function send(type, opts) {
    return new Promise(function (resolve) {
      chrome.runtime.sendMessage(
        { type: type, opts: opts || {} },
        function (resp) {
          resolve(resp || { ok: false, error: "no response" });
        }
      );
    });
  }

  async function refresh() {
    var resp = await send("get_status");
    if (resp && resp.state) {
      render(resp.state, resp.disclaimer);
    } else {
      statusText.textContent = "error";
      errorText.hidden = false;
      errorText.textContent = (resp && resp.error) || "status unavailable";
    }
  }

  btnConnect.addEventListener("click", async function () {
    btnConnect.disabled = true;
    var resp = await send("connect", {});
    if (resp && resp.state) {
      render(resp.state, disclaimer.textContent);
    }
    await refresh();
  });

  btnDisconnect.addEventListener("click", async function () {
    btnDisconnect.disabled = true;
    var resp = await send("disconnect");
    if (resp && resp.state) {
      render(resp.state, disclaimer.textContent);
    }
    await refresh();
  });

  refresh();
})();
