---
name: har-capture
description: "Capture network traffic (XHR, Fetch, WebSocket) from any website using Playwright. Saves HAR 1.2 format, extracts API endpoints automatically. Supports standalone mode and CDP attach to existing browsers."
---

# HAR Capture Tool

Capture HTTP requests/responses and WebSocket frames from any website. Saves in HAR 1.2 format (importable in browser DevTools).

## When to Use

- Discovering API endpoints from SPAs/JS-heavy sites (instead of manual curl guessing)
- Capturing WebSocket traffic (real-time data, live updates)
- Recording request/response payloads for replay or analysis
- Debugging network issues on websites
- Reverse engineering API flows (auth, captcha, data submission)

## Command

```bash
harcapture <url> [options]
harcapture --cdp-url <endpoint> [url] [options]
```

**Options:**
- `-o, --output <file>` — Output HAR file (default: `~/scripts/har-capture/output/<domain>_<timestamp>.har`)
- `-f, --filter <types>` — Resource types: `xhr,fetch,ws,document,script,all` (default: `xhr,fetch,ws`)
- `--headless` — Run without visible browser window (standalone mode)
- `--wait <sec>` — Auto-close after N seconds (default: 0 = manual, press Enter to stop)
- `--cdp-url <url>` — Attach to existing browser via CDP (URL or preset name)
- `--existing-tab` — Attach to first existing tab instead of opening new one

**CDP Presets:**
- `camofox` → `http://localhost:9377` (NOTE: Camofox does NOT expose CDP — use Chrome/CloakBrowser)
- `cloakbrowser` → `http://localhost:9222`

## Two Modes

### Standalone (default)
Opens its own Playwright browser. Best for quick captures.

```bash
# Interactive — browse manually, press Enter when done
harcapture 'https://target.com'

# Headless + auto-close after 10s
harcapture 'https://target.com' --headless --wait 10

# Filter XHR/Fetch only (skip WS)
harcapture 'https://target.com' -f xhr,fetch

# Capture everything including static assets
harcapture 'https://target.com' -f all

# Custom output path
harcapture 'https://target.com' -o ~/scripts/project/api-capture.har
```

### CDP Attach
Connects to an existing Chrome/Chromium browser via **raw CDP websocket** (NOT Playwright). Captures ALL traffic regardless of how navigation is triggered.

```bash
# 1. Start Chrome with CDP port
google-chrome --remote-debugging-port=9222 --no-first-run &

# 2. Attach harcapture (creates new tab with URL)
harcapture --cdp-url http://localhost:9222 'https://target.com'

# 3. Interact via raw CDP websocket, browser_cdp, or user clicks
# 4. Press Enter in harcapture terminal → stop capture

# Attach to existing tab instead of creating new one
harcapture --cdp-url http://localhost:9222 --existing-tab

# Preset shortcuts
harcapture --cdp-url cloakbrowser 'https://target.com'
```

**When to use CDP Attach:**
- Need to interact with the site (click buttons, fill forms, navigate SPA)
- Want to use a real Chrome profile (cookies, extensions)
- Server-side: launch Chrome on Xvfb with CDP, attach from terminal
- Complex multi-step flows (login → dashboard → API calls)

**CDP Attach workflow on server:**
1. `export DISPLAY=:99` (Xvfb)
2. `google-chrome --remote-debugging-port=9222 --no-first-run &`
3. `harcapture --cdp-url http://localhost:9222 'https://target.com'`
4. Interact via raw CDP websocket or `browser_cdp` tool
5. Press Enter → capture stops with all traffic recorded

**How CDP Attach works internally:**
- Connects to Chrome via raw CDP websocket (`ws://localhost:9222/devtools/...`)
- Creates new tab via `PUT /json/new?<url>` (or attaches to existing)
- Listens to CDP `Network.requestWillBeSent`, `Network.responseReceived`, `Network.loadingFinished`
- Fetches response bodies via `Network.getResponseBody`
- Captures WebSocket frames via `Network.webSocketCreated/FrameReceived/FrameSent/Closed`
- Uses `drain_events()` loop for timed capture or manual Enter stop

## Usage Patterns

```bash
# Quick API discovery (headless, 10s)
harcapture 'https://target.com' --headless --wait 10

# Interactive SPA capture (CDP attach, manual close)
harcapture --cdp-url http://localhost:9222 'https://app.com/dashboard'

# WebSocket-only capture
harcapture 'https://trading.com' -f ws --headless --wait 30

# Full capture (all resources)
harcapture 'https://target.com' -f all -o full-capture.har
```

## Workflow: API Discovery

1. Run `harcapture <url>` (headless if on server, CDP attach if interactive)
2. Perform actions in browser (click buttons, submit forms, navigate)
3. Press Enter to stop
4. Review extracted API summary in terminal output
5. HAR file saved — import in DevTools (Network → Import HAR) for full inspection
6. Use extracted endpoints in scripts (curl, Python requests, etc.)

## Output

**Terminal:** Live log of captured requests + API summary at the end.

**HAR file:** JSON with all request/response data:
- Request: method, URL, headers, body
- Response: status, headers, body
- WebSocket: connection URLs, frame direction (recv/sent), payload data

## WebSocket Capture

Uses CDP (Chrome DevTools Protocol) to intercept WebSocket frames:
- `[WS OPEN]` — new WS connection detected
- `[WS RECV]` — incoming frame (server → client)
- `[WS SENT]` — outgoing frame (client → server)
- `[WS CLOSE]` — connection closed

WS frames saved in HAR under `_websockets[]` with direction, data, and timestamp.

## Pitfalls

1. **Event listener syntax** — Playwright's CDP session does NOT support `@cdp.on()` decorator syntax. Use direct method calls: `cdp.on('Network.webSocketFrameReceived', handler)`, NOT `@cdp.on('Network.webSocketFrameReceived')`. The decorator pattern causes `TypeError` at runtime.

2. **`asyncio.sleep` in event handlers** — CDP event handlers run in the event loop. Using `await asyncio.sleep()` inside a handler blocks all other event processing. Use fire-and-forget patterns or queue events for later processing.

3. **WebSocket capture requires CDP `Network.enable`** — Before intercepting WS frames, must call `await cdp.send('Network.enable')`. Without this, no WS events fire.

4. **Camofox does NOT expose CDP** — Camofox is a REST API proxy, not a raw CDP endpoint. `/json/list` and `/json/version` return 404. Use Chrome with `--remote-debugging-port` or CloakBrowser for CDP attach.

5. **Chrome `/json/new` requires PUT** — Chrome 148+ rejects GET requests to `/json/new` with "Using unsafe HTTP verb GET". Must use `PUT` method: `urllib.request.Request(url, method="PUT")` or `curl -X PUT`. Used internally by `--cdp-url` to create new tabs.

6. **Playwright `page.on("response")` misses raw CDP traffic** — In CDP attach mode, if navigation is triggered via raw CDP websocket (`Page.navigate`), Playwright's response listener does NOT see those responses. The CDP attach mode uses raw CDP `Network.*` events instead, which capture ALL traffic regardless of navigation source.

7. **SPA routing may not trigger API calls** — Client-side routing (React Router, Next.js, etc.) navigates without server requests. Navigating to `/puzzle`, `/memory`, `/leaderboard` on an SPA may produce zero XHR/Fetch traffic. API calls only happen on user interactions (button clicks, form submissions, data fetches). Don't assume navigation = API calls.

## Limitations

- Playwright Chromium only in standalone mode (no Firefox/WebKit)
- CDP attach works with any Chromium-based browser (Chrome, Edge, Brave, CloakBrowser)
- WebSocket capture requires CDP session (works in both standalone and attach modes)
- Response body capture may fail for large responses or streaming
- Some sites detect Playwright — use Camofox or CloakBrowser for anti-detect needs (standalone only)
- Filter applies at resource type level, not URL pattern
- Camofox REST API (`http://localhost:9377`) does NOT support CDP — use Chrome directly

## File Location

Script: `scripts/har_capture.py` (relative to this skill directory)
Symlink: `~/.hermes/node/bin/harcapture`
References: `references/cdp-protocol.md`, `references/api-discovery-patterns.md`
