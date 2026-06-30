// WHAT DOES THIS FILE DO: reads and writes extension settings via chrome.storage.sync

var DEFAULTS = {
  apiBase: "http://localhost:8000",
  dept: "",
  enabled: true,
};

var elEnabled = document.getElementById("enabled");
var elApiBase = document.getElementById("apiBase");
var elDept    = document.getElementById("dept");
var elSave    = document.getElementById("save");
var elStatus  = document.getElementById("status");

// Load saved settings into the form on popup open
chrome.storage.sync.get(DEFAULTS, function (cfg) {
  elEnabled.checked  = cfg.enabled;
  elApiBase.value    = cfg.apiBase || DEFAULTS.apiBase;
  elDept.value       = cfg.dept   || "";
});

// Save on button click
elSave.addEventListener("click", function () {
  var apiBase = (elApiBase.value || "").trim().replace(/\/+$/, "");
  var dept    = (elDept.value   || "").trim();

  if (!apiBase) {
    showStatus("Backend URL is required.", true);
    return;
  }

  chrome.storage.sync.set(
    { apiBase: apiBase, dept: dept, enabled: elEnabled.checked },
    function () {
      showStatus("Saved! Reload the page to apply.");
    }
  );
});

function showStatus(msg, isError) {
  elStatus.textContent  = msg;
  elStatus.style.color  = isError ? "#c0392b" : "#2e7d32";
  setTimeout(function () { elStatus.textContent = ""; }, 3000);
}
