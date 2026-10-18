---
name: har-capture
description: "Capture network traffic (XHR, Fetch, WebSocket) from any website using Playwright. Saves HAR 1.2 format, extracts API endpoints automatically. Supports standalone mode and CDP attach to existing browsers. Includes the full API discovery workflow: source analysis, HAR capture, WebSocket monitoring, SPA endpoint reverse-engineering."
triggers:
  - "find API endpoints"
  - "capture network traffic"
  - "reverse engineer API"
  - "HAR capture"
  - "what API does this site use"
  - "how does this website work"
  - "intercept requests"
  - "WebSocket capture"
---

# HAR Capture Tool

Capture HTTP requests/responses and WebSocket frames from any website. Saves in HAR 1.2 format (importable in browser DevTools).

## When to Use

- Discovering API endpoints from SPAs/JS-heavy sites (instead of manual curl guessing)
- Capturing WebSocket traffic (real-time data, live updates)
- Recording request/response payloads for replay or analysis
- Debugging network issues on websites
- Reverse engineering API flows (auth, captcha, data submission)

## Default Policy

When exploring a new website or reverse-engineering its API:

- **Default tool: `harcapture`** (CDP-based HAR capture) — **NOT** manual `curl` + `grep`
  through source code.
- `harcapture` captures XHR, Fetch, **and** WebSocket traffic automatically with
  request/response bodies, headers, and an API summary.
- `curl` + source code grep is the **fallback only** when:
  1. a headless browser is unavailable,
  2. the site blocks Playwright, or
  3. you only need to check a single known endpoint.

**Don't:** download all JS files and manually grep for `fetch()` calls when
`harcapture` can capture the actual live traffic with real payloads and responses.
Source code only shows what the client *could* send; HAR capture shows what it
*actually* sends.

**Standard flow:**

1. `harcapture '<url>' --headless --wait N` — standalone, quick capture
2. Or start Chrome with `--remote-debugging-port=9222`, then
   `harcapture --cdp-url http://localhost:9222 '<url>'` — interactive, CDP attach
3. Review the API summary in the terminal output
4. HAR file is saved persistently at
   `~/scripts/har-capture/output/<domain>_<timestamp>.har`
5. Use the extracted endpoints in scripts

Two complementary approaches exist for discovering undocumented APIs. Reach for
HAR capture first per the policy above; fall back to source analysis only under the
conditions listed.

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

### Fallback: Source Code Analysis

Only when the default policy above says to fall back. Best for: SPAs, static sites,
any site that serves readable JavaScript — or when you just need to confirm one
endpoint exists.

```bash
# 1. Download HTML, find JS files
curl -sL 'https://target.com/' | grep -oP 'src="[^"]*\.js[^"]*"'

# 2. Download each JS file, search for fetch/XMLHttpRequest/axios
curl -sL 'https://target.com/app.js' | grep -B2 -A10 'fetch('
curl -sL 'https://target.com/app.js' | grep -oP '"/api/[^"]*"'

# 3. Extract endpoint patterns, methods, payload shapes
# Look for: JSON.stringify({...}), headers, Content-Type
```

**What to look for in JS:**
- `fetch('/api/...')` calls — endpoint + method + body shape
- `XMLHttpRequest` — older pattern, same info
- `axios.get/post` — wrapper, same pattern
- `WebSocket('wss://...')` — WS endpoints
- Error messages — reveal valid/invalid states
- Constants/enums — API field values, status codes
- Honeypot fields — fields that must be empty (anti-bot)

### Default: HAR Capture

The default path. Best for: complex auth flows, encrypted payloads, WebSocket-heavy
apps, and any case where source code is minified or obfuscated.

```bash
# Default: XHR + Fetch + WS, manual close (press Enter)
harcapture 'https://target.com'

# Headless mode (for servers)
harcapture 'https://target.com' --headless

# Auto-close after 10s idle
harcapture 'https://target.com' --wait 10

# CDP attach to existing Chrome (captures ALL traffic)
harcapture --cdp-url http://localhost:9222 'https://target.com'

# Custom output
harcapture 'https://target.com' -o my_capture.har
```

**Default filter:** `xhr,fetch,ws` — skips static assets (images, CSS, JS files)
**Close mode:** Manual (press Enter) — browse the site, trigger actions, then stop
**Output:** HAR 1.2 file + live API summary in terminal. Saved persistently at `~/scripts/har-capture/output/<domain>_<timestamp>.har`
**WebSocket:** Captured via CDP (frames recv/sent/connection lifecycle)

### When to use HAR vs curl

| Scenario | Use |
|---|---|
| Need to find endpoints | curl + source code |
| Need actual request/response payloads | HAR capture |
| Auth flow (cookies, tokens, redirects) | HAR capture |
| Encrypted/obfuscated JS | HAR capture |
| WebSocket protocol | HAR capture |
| Quick one-off endpoint test | curl |
| Site with readable JS | curl + source code |

## Extracting API Summary from HAR

After capture, the tool auto-extracts unique API endpoints:

```
  GET    /api/data      Status: 200 | Response: {...}
  POST   /api/submit    Request: {...}  [POST body]
  WS     /ws            [12 frames]
```

HAR files can also be imported in browser DevTools → Network → Import HAR for visual inspection.

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

### Tool internals

1. **Event listener syntax** — Playwright's CDP session does NOT support `@cdp.on()` decorator syntax. Use direct method calls: `cdp.on('Network.webSocketFrameReceived', handler)`, NOT `@cdp.on('Network.webSocketFrameReceived')`. The decorator pattern causes `TypeError` at runtime.

2. **`asyncio.sleep` in event handlers** — CDP event handlers run in the event loop. Using `await asyncio.sleep()` inside a handler blocks all other event processing. Use fire-and-forget patterns or queue events for later processing.

3. **WebSocket capture requires CDP `Network.enable`** — Before intercepting WS frames, must call `await cdp.send('Network.enable')`. Without this, no WS events fire.

4. **Camofox does NOT expose CDP** — Camofox is a REST API proxy, not a raw CDP endpoint. `/json/list` and `/json/version` return 404. Use Chrome with `--remote-debugging-port` or CloakBrowser for CDP attach.

5. **Chrome `/json/new` requires PUT** — Chrome 148+ rejects GET requests to `/json/new` with "Using unsafe HTTP verb GET". Must use `PUT` method: `urllib.request.Request(url, method="PUT")` or `curl -X PUT`. Used internally by `--cdp-url` to create new tabs.

6. **Playwright `page.on("response")` misses raw CDP traffic** — In CDP attach mode, if navigation is triggered via raw CDP websocket (`Page.navigate`), Playwright's response listener does NOT see those responses. The CDP attach mode uses raw CDP `Network.*` events instead, which capture ALL traffic regardless of navigation source.

### Discovery process

7. **SPA routing may not trigger API calls** — Client-side routing (React Router, Next.js, Vue Router) navigates without server requests. Navigating to `/dashboard`, `/settings`, `/profile` on an SPA may produce zero XHR/Fetch traffic. API calls only happen on user interactions (button clicks, form submissions, data fetches). For SPA API discovery you MUST interact with the page, not just navigate between routes.

8. **Minified JS is still readable** — Use `grep` for patterns, don't try to read the whole file. Search for `fetch(`, `/api/`, `endpoint`, `url:`.

9. **Some APIs are server-side only** — If an endpoint is called by the server (SSR, form POST), it won't appear in client JS or network capture. Look at form `action` attributes and `<script>` blocks in SSR HTML.

10. **"Invalid client" vs "invalid code"** — When fuzzing API endpoints, differentiate between request-level errors (missing headers/origin → "invalid client") and content-level errors ("invalid code"). Always test with proper headers (Referer, Origin, User-Agent) first to ensure you're getting content-level errors.

11. **Rate limiting on API fuzzing** — When testing many codes/inputs, add 1-2s delays between requests. Some sites rate-limit by IP even without explicit rate limit headers.

12. **Honeypot fields** — Many SPAs include hidden form fields (honeypot) that must be empty. Bot detection checks if these are filled. When replicating API calls programmatically, always check for `display: none` fields and exclude them.

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

## References

| File | Contents |
|------|----------|
| `references/cdp-protocol.md` | CDP domain/method reference for capture |
| `references/interactive-cdp-workflow.md` | Attaching to an interactive browser session |
| `references/api-discovery-patterns.md` | Endpoint pattern extraction |
| `references/spa-api-discovery.md` | SPA-specific discovery strategy |
| `references/auth-flow-capture.md` | Capturing login/token/redirect flows |
| `references/response-analysis.md` | Reading captured responses |
| `references/cdp-pitfalls.md` | CDP gotchas |
