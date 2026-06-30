/*
 * WHAT DOES THIS FILE DO: content script — reads saved settings from chrome.storage,
 * then injects widget.js (bundled inside the extension) as a <script> tag so it runs
 * in the page's world with the correct data-api-base and data-dept attributes.
 *
 * Runs on every page at document_idle (after DOM is ready).
 */

chrome.storage.sync.get(
  { apiBase: "http://localhost:8000", dept: "", enabled: true },
  function (cfg) {
    // Bail if user toggled the widget off
    if (!cfg.enabled) return;

    // Guard: never inject twice (e.g. if content script fires more than once)
    if (document.getElementById("__askgla_ext_script__")) return;

    var s = document.createElement("script");
    s.id = "__askgla_ext_script__";

    // chrome.runtime.getURL gives the extension-local path to widget.js
    s.src = chrome.runtime.getURL("widget.js");

    // These are read by widget.js via document.currentScript on first execution
    s.setAttribute("data-api-base", (cfg.apiBase || "").replace(/\/+$/, ""));
    s.setAttribute("data-dept", cfg.dept || "");

    // Remove the tag once loaded — keeps the DOM clean
    s.onload = function () { s.remove(); };

    (document.head || document.documentElement).appendChild(s);
  }
);
