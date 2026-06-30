# Chatbot Widget — Shadow DOM Architecture and Full Deployment Plan

## What is this document

This document captures the full technical plan for building an embeddable chatbot widget for the white-label RAG chatbot project. The user (Pragyan) and assistant agreed on this plan after discussing three options. This is given as context to avoid re-discussing decisions already made.

---

## Decision Made: Shadow DOM (Option 2)

We discussed three embedding approaches:

**Option 1 — Direct DOM injection:** Widget injects HTML/CSS directly into the host page. Simple but causes CSS conflicts with the college's existing styles. Rejected.

**Option 2 — Shadow DOM (CHOSEN):** Widget renders inside a Shadow DOM root which is completely isolated from the host page's CSS. Still a floating button + chat panel, but fully isolated. React renders inside the shadow root.

**Option 3 — iframe:** Full isolation but behaves like a completely separate page inside a box. Harder to style to match the host, no access to parent page context. Rejected.

### Why Shadow DOM was chosen

- CSS is fully isolated — college's own CSS never bleeds into the widget
- Widget still lives as part of the page (not an iframe), so it feels native
- React works inside shadow DOM with minor adjustments
- Single script tag integration for college tech teams
- Easy to customize colors/branding via data attributes on the script tag

---

## Widget Architecture

### How it looks on the host page

```
Host Page (college website)
  |
  +-- <div id="chatbot-widget-root">     <-- we inject this div
        |
        +-- Shadow Root                   <-- CSS isolation boundary
              |
              +-- React App               <-- our full widget UI
                    |
                    +-- Floating Button   <-- bottom-right corner
                    +-- Chat Panel        <-- slides up when button clicked
                          |
                          +-- Header (bot name, close button)
                          +-- Message list (user + bot bubbles)
                          +-- Input area (text box + send button)
                          +-- Suggested questions (optional)
```

### Single script tag integration

College tech team adds ONE line to their HTML:

```html
<script
  src="https://your-deployed-backend.com/widget.js"
  data-bot-name="AskGLA"
  data-primary-color="#1a73e8"
  data-position="bottom-right"
  defer
></script>
```

That's it. The script:
1. Creates a `<div id="chatbot-widget-root">` and appends to body
2. Attaches a Shadow DOM root to that div
3. Injects bundled CSS inside the shadow root
4. Mounts the React app inside the shadow root

---

## Tech Stack for the Widget

| Layer | Technology | Reason |
|---|---|---|
| UI framework | React 18 | Already used in admin dashboard, team familiar |
| Bundler | Vite (library mode) | Produces single JS bundle, supports Shadow DOM |
| CSS | Plain CSS or CSS Modules | No Tailwind — shadow DOM handles isolation |
| State | useState / useRef | Simple enough, no Redux needed |
| API calls | fetch | No axios dependency, keep bundle small |
| Bundle output | Single `widget.js` file | One file = one script tag for colleges |

---

## File Structure (to be created)

```
white_label_chatbot/
  widget/                        <-- new folder, separate from frontend/
    src/
      Widget.jsx                 <-- root component, mounts into shadow DOM
      components/
        FloatingButton.jsx       <-- the chat bubble button
        ChatPanel.jsx            <-- the sliding chat panel
        MessageList.jsx          <-- renders conversation history
        MessageBubble.jsx        <-- individual message bubble
        InputBar.jsx             <-- text input + send button
        SuggestedQuestions.jsx   <-- clickable suggested questions
      hooks/
        useChat.js               <-- chat API call logic, conversation state
        useConfig.js             <-- reads data-* attributes from script tag
      styles/
        widget.css               <-- all widget styles, isolated in shadow DOM
      index.js                   <-- entry point, shadow DOM mounting logic
    vite.config.js               <-- library mode config
    package.json
```

---

## How Shadow DOM Mounting Works (index.js)

```javascript
// index.js — entry point
import React from 'react'
import { createRoot } from 'react-dom/client'
import Widget from './Widget.jsx'

function mount() {
  // Step 1: create container div and append to body
  const container = document.createElement('div')
  container.id = 'chatbot-widget-root'
  document.body.appendChild(container)

  // Step 2: attach shadow root for CSS isolation
  const shadowRoot = container.attachShadow({ mode: 'open' })

  // Step 3: inject CSS into shadow root (not into the main page)
  const style = document.createElement('style')
  style.textContent = INJECTED_CSS   // bundled at build time by Vite
  shadowRoot.appendChild(style)

  // Step 4: create mount point inside shadow root
  const mountPoint = document.createElement('div')
  shadowRoot.appendChild(mountPoint)

  // Step 5: mount React inside shadow root
  const root = createRoot(mountPoint)
  root.render(<Widget scriptTag={document.currentScript} />)
}

// Run after DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mount)
} else {
  mount()
}
```

---

## How the Widget Reads Config (useConfig.js)

Config comes from `data-*` attributes on the script tag:

```javascript
// useConfig.js
function useConfig(scriptTag) {
  return {
    botName: scriptTag?.dataset.botName || 'Assistant',
    primaryColor: scriptTag?.dataset.primaryColor || '#1a73e8',
    position: scriptTag?.dataset.position || 'bottom-right',
    apiBase: scriptTag?.dataset.apiBase || '',   // where backend is deployed
    departmentSlug: scriptTag?.dataset.departmentSlug || '',
  }
}
```

---

## API Communication

Widget talks to the same FastAPI backend via these endpoints:

| Action | Endpoint | Method |
|---|---|---|
| Send message | `/api/chat` | POST |
| Get suggested questions | `/api/admin/predefined-questions` | GET |
| Submit feedback | `/api/feedback` | POST |

Request headers the widget sends:
- `X-Session-ID` — UUID generated per browser session (stored in sessionStorage)
- `X-Department-Slug` — from `data-department-slug` on script tag (for analytics)

---

## Full Deployment Plan

### Phase A — Backend is already done (current state)
The FastAPI backend is fully functional with:
- `/api/chat` — RAG pipeline
- `/api/admin/*` — all admin endpoints
- CORS configured
- Supabase pgvector + S3 storage

### Phase B — Build the widget (to be built last, per Pragyan's instruction)

Steps in order:

1. Create `widget/` folder with Vite config in library mode
2. Build `index.js` — shadow DOM mounting logic
3. Build `useConfig.js` — reads data attributes from script tag
4. Build `useChat.js` — manages conversation state, calls `/api/chat`
5. Build `FloatingButton.jsx` — bottom-right floating button
6. Build `ChatPanel.jsx` — sliding panel with header
7. Build `MessageList.jsx` and `MessageBubble.jsx`
8. Build `InputBar.jsx`
9. Build `SuggestedQuestions.jsx`
10. Build `widget.css` — all styles go here, isolated by shadow DOM
11. Run `vite build` — outputs single `widget.js` file

### Phase C — Serve the widget file

Two options for serving `widget.js`:

**Option C1 — Serve from the same FastAPI backend:**
```python
# in main.py
app.mount("/widget.js", StaticFiles(directory="widget/dist"), name="widget")
```
College script tag: `<script src="https://your-backend.com/widget.js">`

**Option C2 — Upload to Supabase S3 storage:**
- Upload `widget.js` to the `chatbot-uploads` S3 bucket
- Get a public URL from Supabase
- College script tag: `<script src="https://supabase-url/storage/v1/object/public/chatbot-uploads/widget.js">`

Recommended: Option C1 (same backend) — simpler, no CDN needed for MVP.

### Phase D — CORS configuration

When a college embeds the widget on their domain (e.g., `college.edu`), the browser will block API calls to the backend unless CORS allows it.

Update `ALLOWED_ORIGINS` in `.env`:
```
ALLOWED_ORIGINS=https://college.edu,https://another-college.edu
```

Or for development:
```
ALLOWED_ORIGINS=*
```

The FastAPI backend already has CORS middleware configured in `main.py`.

### Phase E — College integration checklist

What the college tech team needs to do:

1. Get the script tag from Pragyan's team (with correct `data-api-base` URL)
2. Paste the script tag before `</body>` in their HTML
3. Done

What Pragyan's team configures per college:
- `BOT_NAME` — chatbot name
- `ADMIN_EMAIL` — who manages the bot
- Uploaded documents — the knowledge base
- Department slug — for analytics tracking

---

## Widget Behavior Spec

| Behavior | Detail |
|---|---|
| Default state | Floating button in bottom-right corner |
| Open | Click button — chat panel slides up from bottom-right |
| Close | Click X button or click outside panel |
| First message | Suggested questions appear before user types |
| Typing | User types in input bar, hits Enter or Send |
| Bot response | Shows typing indicator (three dots) while waiting |
| Error | Shows friendly error message if API fails |
| Session | Conversation stored in component state, cleared on page refresh |
| Responsive | Works on mobile (panel takes full screen on small viewports) |

---

## What Has NOT Been Built Yet (as of session date)

- The `widget/` folder does not exist yet
- No `widget.js` bundle
- No React widget components
- No `vite.config.js` for widget build

**Pragyan's explicit instruction:** Build all missing backend features first. Chatbot widget comes last.

---

## Missing Backend Features Still To Build

After Phase 1 (Users + Departments + S3) and Phase 2 (Analytics) are done, remaining backend features:

1. Live Activity Monitoring
2. Visitor Sessions Tracking
3. Moderation Panel
4. Pending Approvals Workflow
5. CSV Export
6. Chat Console endpoints
7. Tester Page endpoints
8. Langfuse Integration
9. Intent Distribution Tracking

Only after all of these are built does the chatbot widget work begin.
