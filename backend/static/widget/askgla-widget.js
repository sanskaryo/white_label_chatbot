/*
 * WHAT DOES THIS FILE DO: self-contained embeddable AskGLA chat widget.
 * Drop one <script> tag on any page and a floating chat button appears.
 * Everything (markup, styles, state, API calls) lives inside a Shadow DOM
 * so it never collides with the host page's CSS or JS.
 *
 * Embed:
 *   <script src="https://YOURHOST/widget/askgla-widget.js"
 *           data-api-base="https://YOURHOST"
 *           data-dept="admissions"></script>
 */
(function () {
  "use strict";

  // Guard: never inject twice if the script is included more than once
  if (window.__askglaWidgetLoaded) return;
  window.__askglaWidgetLoaded = true;

  // =========== READ SCRIPT TAG CONFIG ===========
  // currentScript is only valid while the script first executes — capture now
  var scriptEl = document.currentScript;
  var API_BASE = (scriptEl && scriptEl.getAttribute("data-api-base") || "").replace(/\/+$/, "");
  var DEPARTMENT = (scriptEl && scriptEl.getAttribute("data-dept")) || "";
  // If no api-base given, assume the widget is served from the same origin
  if (!API_BASE) API_BASE = window.location.origin;
  // =========== READ SCRIPT TAG CONFIG ===========

  var REQUEST_TIMEOUT_MS = 20000;
  var MAX_HISTORY_TURNS = 6;       // backend caps conversation_history at 6
  var MAX_QUESTION_LEN = 500;      // backend caps question at 500 chars

  // =========== RUNTIME STATE ===========
  var config = null;               // resolved widget config from the API
  var isOpen = false;
  var isSending = false;
  var history = [];                // [{role:"user"|"assistant", content:string}]
  var shadow = null;               // shadow root
  var els = {};                    // cached element references
  // =========== RUNTIME STATE ===========


  // =========== SESSION ID ===========
  // Per-tab session id so analytics can group a visitor's questions
  function getSessionId() {
    try {
      var sid = sessionStorage.getItem("askgla_session_id");
      if (!sid) {
        sid = "askgla-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
        sessionStorage.setItem("askgla_session_id", sid);
      }
      return sid;
    } catch (e) {
      // sessionStorage blocked (private mode / cookies off) — fall back to memory
      if (!window.__askglaMemSid) {
        window.__askglaMemSid = "askgla-mem-" + Math.random().toString(36).slice(2, 12);
      }
      return window.__askglaMemSid;
    }
  }

  function getDeviceType() {
    return /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent) ? "mobile" : "desktop";
  }
  // =========== SESSION ID ===========


  // =========== HTML ESCAPE ===========
  // Everything from the API and user is rendered as text, never raw HTML
  function esc(str) {
    return String(str == null ? "" : str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
  // =========== HTML ESCAPE ===========


  // =========== STYLES ===========
  // Built as a template so the two brand colors can be injected from config
  function buildStyles(theme, accent) {
    return [
      ":host { all: initial; }",
      "*, *::before, *::after { box-sizing: border-box; }",
      ".askgla-root { font-family: 'Segoe UI', system-ui, -apple-system, Roboto, Helvetica, Arial, sans-serif; }",

      // Floating action button
      ".fab { position: fixed; bottom: 22px; z-index: 2147483000; width: 60px; height: 60px;",
      "  border-radius: 50%; border: none; cursor: pointer; background: " + theme + ";",
      "  color: #fff; box-shadow: 0 6px 20px rgba(0,0,0,0.28); display: flex; align-items: center;",
      "  justify-content: center; transition: transform .18s ease, box-shadow .18s ease; }",
      ".fab:hover { transform: scale(1.06); box-shadow: 0 8px 26px rgba(0,0,0,0.34); }",
      ".fab svg { width: 28px; height: 28px; }",
      ".fab.pos-right { right: 22px; }",
      ".fab.pos-left { left: 22px; }",
      ".fab.hidden { display: none; }",

      // Chat panel
      ".panel { position: fixed; bottom: 96px; z-index: 2147483000; width: 380px; height: 560px;",
      "  max-height: calc(100vh - 120px); background: #fff; border-radius: 16px; overflow: hidden;",
      "  box-shadow: 0 12px 40px rgba(0,0,0,0.28); display: flex; flex-direction: column;",
      "  opacity: 0; transform: translateY(16px) scale(0.98); pointer-events: none;",
      "  transition: opacity .2s ease, transform .2s ease; }",
      ".panel.pos-right { right: 22px; }",
      ".panel.pos-left { left: 22px; }",
      ".panel.open { opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }",

      // Header
      ".hdr { background: " + theme + "; color: #fff; padding: 14px 16px; display: flex;",
      "  align-items: center; gap: 10px; flex-shrink: 0; }",
      ".hdr .avatar { width: 34px; height: 34px; border-radius: 50%; background: rgba(255,255,255,0.16);",
      "  display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 15px; }",
      ".hdr .meta { flex: 1; min-width: 0; }",
      ".hdr .name { font-weight: 600; font-size: 15px; line-height: 1.2; }",
      ".hdr .status { font-size: 11px; opacity: 0.82; display: flex; align-items: center; gap: 5px; }",
      ".hdr .dot { width: 7px; height: 7px; border-radius: 50%; background: #4ade80; display: inline-block; }",
      ".hdr .close { background: none; border: none; color: #fff; cursor: pointer; font-size: 22px;",
      "  line-height: 1; opacity: 0.85; padding: 4px; border-radius: 6px; }",
      ".hdr .close:hover { opacity: 1; background: rgba(255,255,255,0.12); }",

      // Messages area
      ".msgs { flex: 1; overflow-y: auto; padding: 16px; background: #f7f8f7; display: flex;",
      "  flex-direction: column; gap: 12px; }",
      ".msgs::-webkit-scrollbar { width: 7px; }",
      ".msgs::-webkit-scrollbar-thumb { background: #ccc; border-radius: 4px; }",

      ".row { display: flex; }",
      ".row.user { justify-content: flex-end; }",
      ".row.bot { justify-content: flex-start; }",
      ".bubble { max-width: 82%; padding: 10px 13px; border-radius: 14px; font-size: 14px;",
      "  line-height: 1.5; white-space: pre-wrap; word-wrap: break-word; }",
      ".row.user .bubble { background: " + theme + "; color: #fff; border-bottom-right-radius: 4px; }",
      ".row.bot .bubble { background: #fff; color: #1a1a1a; border: 1px solid #e6e6e6;",
      "  border-bottom-left-radius: 4px; }",

      // Verified badge
      ".badge { display: inline-block; margin-top: 6px; font-size: 10.5px; font-weight: 600;",
      "  color: #2e7d32; background: #e8f5e9; padding: 2px 7px; border-radius: 10px; }",

      // Sources toggle
      ".sources { margin-top: 7px; font-size: 12px; }",
      ".sources summary { cursor: pointer; color: " + theme + "; font-weight: 600; outline: none; }",
      ".sources ul { margin: 6px 0 0; padding-left: 16px; color: #555; }",
      ".sources li { margin: 2px 0; }",
      ".sources a { color: " + theme + "; }",

      // Starter question pills
      ".pills { display: flex; flex-direction: column; gap: 7px; margin-top: 4px; }",
      ".pill { text-align: left; background: #fff; border: 1px solid " + accent + ";",
      "  color: #333; padding: 9px 12px; border-radius: 12px; cursor: pointer; font-size: 13px;",
      "  transition: background .15s ease, color .15s ease; }",
      ".pill:hover { background: " + accent + "; color: #1a1a1a; }",

      // Typing indicator
      ".typing { display: inline-flex; gap: 4px; align-items: center; padding: 12px 14px; }",
      ".typing span { width: 7px; height: 7px; border-radius: 50%; background: #999;",
      "  animation: askgla-bounce 1.2s infinite ease-in-out; }",
      ".typing span:nth-child(2) { animation-delay: .18s; }",
      ".typing span:nth-child(3) { animation-delay: .36s; }",
      "@keyframes askgla-bounce { 0%, 60%, 100% { transform: translateY(0); opacity: .5; }",
      "  30% { transform: translateY(-5px); opacity: 1; } }",

      // Error line + retry
      ".errline { font-size: 12.5px; color: #c0392b; display: flex; align-items: center; gap: 8px; }",
      ".retry { background: none; border: 1px solid #c0392b; color: #c0392b; border-radius: 8px;",
      "  padding: 3px 10px; font-size: 12px; cursor: pointer; }",
      ".retry:hover { background: #c0392b; color: #fff; }",

      // Input bar
      ".input { display: flex; align-items: flex-end; gap: 8px; padding: 10px; background: #fff;",
      "  border-top: 1px solid #eee; flex-shrink: 0; }",
      ".input textarea { flex: 1; resize: none; border: 1px solid #ddd; border-radius: 12px;",
      "  padding: 9px 12px; font-size: 14px; font-family: inherit; max-height: 96px; outline: none;",
      "  line-height: 1.4; }",
      ".input textarea:focus { border-color: " + theme + "; }",
      ".send { width: 40px; height: 40px; border-radius: 50%; border: none; cursor: pointer;",
      "  background: " + accent + "; color: #1a1a1a; display: flex; align-items: center;",
      "  justify-content: center; flex-shrink: 0; transition: opacity .15s ease; }",
      ".send:disabled { opacity: 0.45; cursor: not-allowed; }",
      ".send svg { width: 19px; height: 19px; }",

      // Footer
      ".foot { text-align: center; font-size: 10.5px; color: #aaa; padding: 5px 0 8px; background: #fff; }",

      // Mobile: full screen
      "@media (max-width: 768px) {",
      "  .panel { width: 100vw; height: 100vh; max-height: 100vh; bottom: 0; right: 0; left: 0;",
      "    border-radius: 0; }",
      "  .fab { bottom: 16px; }",
      "  .fab.pos-right { right: 16px; }",
      "  .fab.pos-left { left: 16px; }",
      "}"
    ].join("\n");
  }
  // =========== STYLES ===========


  // =========== ICONS ===========
  var ICON_CHAT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';
  var ICON_SEND = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>';
  // =========== ICONS ===========


  // =========== BUILD DOM ===========
  function buildWidget() {
    var pos = config.position === "bottom-left" ? "left" : "right";
    var initial = (config.bot_name || "A").trim().charAt(0).toUpperCase() || "A";

    var host = document.createElement("div");
    host.id = "askgla-widget-host";
    shadow = host.attachShadow({ mode: "open" });

    var style = document.createElement("style");
    style.textContent = buildStyles(config.theme_color || "#1a3a2a", config.accent_color || "#c9a227");
    shadow.appendChild(style);

    var root = document.createElement("div");
    root.className = "askgla-root";
    root.innerHTML =
      '<button class="fab pos-' + pos + '" aria-label="Open ' + esc(config.bot_name) + ' chat">' + ICON_CHAT + '</button>' +
      '<div class="panel pos-' + pos + '" role="dialog" aria-label="' + esc(config.bot_name) + ' chat window">' +
        '<div class="hdr">' +
          '<div class="avatar">' + esc(initial) + '</div>' +
          '<div class="meta">' +
            '<div class="name">' + esc(config.bot_name) + '</div>' +
            '<div class="status"><span class="dot"></span> Online</div>' +
          '</div>' +
          '<button class="close" aria-label="Close chat">&times;</button>' +
        '</div>' +
        '<div class="msgs"></div>' +
        '<div class="input">' +
          '<textarea rows="1" maxlength="' + MAX_QUESTION_LEN + '" placeholder="Type your question..." aria-label="Message"></textarea>' +
          '<button class="send" aria-label="Send message">' + ICON_SEND + '</button>' +
        '</div>' +
        '<div class="foot">Powered by ' + esc(config.bot_name) + '</div>' +
      '</div>';
    shadow.appendChild(root);

    document.body.appendChild(host);

    // Cache element references
    els.fab = shadow.querySelector(".fab");
    els.panel = shadow.querySelector(".panel");
    els.msgs = shadow.querySelector(".msgs");
    els.textarea = shadow.querySelector("textarea");
    els.send = shadow.querySelector(".send");
    els.close = shadow.querySelector(".close");

    wireEvents();
    renderWelcome();
  }
  // =========== BUILD DOM ===========


  // =========== EVENTS ===========
  function wireEvents() {
    els.fab.addEventListener("click", togglePanel);
    els.close.addEventListener("click", togglePanel);
    els.send.addEventListener("click", onSend);

    els.textarea.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        onSend();
      }
    });

    // Auto-grow textarea up to the CSS max-height
    els.textarea.addEventListener("input", function () {
      els.textarea.style.height = "auto";
      els.textarea.style.height = Math.min(els.textarea.scrollHeight, 96) + "px";
    });
  }

  function togglePanel() {
    isOpen = !isOpen;
    els.panel.classList.toggle("open", isOpen);
    els.fab.classList.toggle("hidden", isOpen);
    if (isOpen) setTimeout(function () { els.textarea.focus(); }, 220);
  }
  // =========== EVENTS ===========


  // =========== RENDER HELPERS ===========
  function scrollDown() {
    els.msgs.scrollTop = els.msgs.scrollHeight;
  }

  function renderWelcome() {
    var row = document.createElement("div");
    row.className = "row bot";
    row.innerHTML = '<div class="bubble">' + esc(config.welcome_message) + '</div>';
    els.msgs.appendChild(row);

    var starters = (config.starter_questions || []).filter(Boolean).slice(0, 4);
    if (starters.length) {
      var pillsWrap = document.createElement("div");
      pillsWrap.className = "pills";
      starters.forEach(function (q) {
        var b = document.createElement("button");
        b.className = "pill";
        b.textContent = q;
        b.addEventListener("click", function () {
          if (isSending) return;
          removePills();
          sendQuestion(q);
        });
        pillsWrap.appendChild(b);
      });
      els.msgs.appendChild(pillsWrap);
    }
    scrollDown();
  }

  function removePills() {
    var p = els.msgs.querySelector(".pills");
    if (p) p.remove();
  }

  function addUserBubble(text) {
    var row = document.createElement("div");
    row.className = "row user";
    row.innerHTML = '<div class="bubble">' + esc(text) + '</div>';
    els.msgs.appendChild(row);
    scrollDown();
  }

  function addBotBubble(data) {
    var row = document.createElement("div");
    row.className = "row bot";

    var inner = '<div class="bubble">' + esc(data.answer || "");

    // "Verified" badge only for human-corrected answers
    if (data.route === "correction") {
      inner += '<div class="badge">&#10003; Verified answer</div>';
    }

    // Sources toggle for RAG answers that returned real sources
    var sources = (data.sources || []).filter(function (s) {
      return s && s.title && s.category !== "cache" && s.category !== "correction";
    });
    if (sources.length) {
      inner += '<div class="sources"><details><summary>' + sources.length +
        (sources.length === 1 ? " source" : " sources") + '</summary><ul>';
      sources.forEach(function (s) {
        if (s.url) {
          inner += '<li><a href="' + esc(s.url) + '" target="_blank" rel="noopener noreferrer">' + esc(s.title) + '</a></li>';
        } else {
          inner += '<li>' + esc(s.title) + '</li>';
        }
      });
      inner += '</ul></details></div>';
    }

    inner += '</div>';
    row.innerHTML = inner;
    els.msgs.appendChild(row);
    scrollDown();
  }

  function showTyping() {
    var row = document.createElement("div");
    row.className = "row bot typing-row";
    row.innerHTML = '<div class="bubble typing"><span></span><span></span><span></span></div>';
    els.msgs.appendChild(row);
    scrollDown();
    return row;
  }

  function addError(message, retryText) {
    var row = document.createElement("div");
    row.className = "row bot";
    var html = '<div class="bubble"><div class="errline">' + esc(message);
    if (retryText) html += ' <button class="retry">Retry</button>';
    html += '</div></div>';
    row.innerHTML = html;
    els.msgs.appendChild(row);
    if (retryText) {
      row.querySelector(".retry").addEventListener("click", function () {
        row.remove();
        sendQuestion(retryText);
      });
    }
    scrollDown();
  }
  // =========== RENDER HELPERS ===========


  // =========== SEND FLOW ===========
  function onSend() {
    var text = (els.textarea.value || "").trim();
    if (!text || isSending) return;
    removePills();
    els.textarea.value = "";
    els.textarea.style.height = "auto";
    sendQuestion(text);
  }

  function sendQuestion(text) {
    if (isSending) return;
    text = text.slice(0, MAX_QUESTION_LEN);

    isSending = true;
    els.send.disabled = true;
    addUserBubble(text);

    var typingRow = showTyping();
    var controller = new AbortController();
    var timedOut = false;
    var timer = setTimeout(function () {
      timedOut = true;
      controller.abort();
    }, REQUEST_TIMEOUT_MS);

    fetch(API_BASE + "/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": getSessionId(),
        "X-Department-Slug": DEPARTMENT,
        "X-Device-Type": getDeviceType(),
        "X-Referrer-Page": (location.pathname || "").slice(0, 200)
      },
      body: JSON.stringify({
        question: text,
        conversation_history: history.slice(-MAX_HISTORY_TURNS)
      }),
      signal: controller.signal
    })
      .then(function (res) {
        clearTimeout(timer);
        if (res.status === 429) {
          var e = new Error("rate_limited");
          e.code = 429;
          throw e;
        }
        if (!res.ok) {
          var e2 = new Error("http_" + res.status);
          e2.code = res.status;
          throw e2;
        }
        return res.json();
      })
      .then(function (data) {
        typingRow.remove();
        addBotBubble(data);
        // Record turns for follow-up context
        history.push({ role: "user", content: text });
        history.push({ role: "assistant", content: (data.answer || "").slice(0, 800) });
        if (history.length > MAX_HISTORY_TURNS) {
          history = history.slice(-MAX_HISTORY_TURNS);
        }
      })
      .catch(function (err) {
        typingRow.remove();
        if (err && err.code === 429) {
          addError("You're sending messages too fast. Please wait a moment.", null);
        } else if (timedOut) {
          addError("This is taking too long.", text);
        } else {
          addError("Connection error. Please check your network.", text);
        }
      })
      .then(function () {
        clearTimeout(timer);
        isSending = false;
        els.send.disabled = false;
        if (isOpen) els.textarea.focus();
      });
  }
  // =========== SEND FLOW ===========


  // =========== BOOT ===========
  function fetchConfigThenBuild() {
    var url = API_BASE + "/api/widget-config";
    if (DEPARTMENT) url += "?department_slug=" + encodeURIComponent(DEPARTMENT);

    fetch(url)
      .then(function (res) { return res.ok ? res.json() : Promise.reject(); })
      .then(function (cfg) {
        config = cfg || {};
      })
      .catch(function () {
        // API unreachable — fall back to built-in defaults so the widget still works
        config = {
          bot_name: "AskGLA",
          welcome_message: "Hi! I'm AskGLA. How can I help you today?",
          starter_questions: [],
          theme_color: "#1a3a2a",
          accent_color: "#c9a227",
          position: "bottom-right",
          is_active: true
        };
      })
      .then(function () {
        if (config.is_active === false) return;  // admin disabled the widget
        buildWidget();
      });
  }

  // Wait for body to exist before injecting
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", fetchConfigThenBuild);
  } else {
    fetchConfigThenBuild();
  }
  // =========== BOOT ===========
})();
