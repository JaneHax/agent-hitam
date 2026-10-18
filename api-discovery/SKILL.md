---
name: api-discovery
description: "Discover and document APIs from websites: source code analysis, HAR capture, WebSocket monitoring, and reverse-engineering SPA endpoints."
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

# API Discovery

Two complementary approaches for discovering undocumented or partially-documented APIs on any website. Use BOTH when needed — source code first (fast, complete), HAR capture second (actual payloads, timing, real behavior).

## Approach 1: Source Code Analysis (Fast)

Best for: SPAs, static sites, any site that serves readable JavaScript.

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

## Approach 2: HAR Capture (Thorough)

Best for: complex auth flows, encrypted payloads, WebSocket-heavy apps, when source code is minified/obfuscated.

### Tool: `harcapture`

Location: `scripts/har_capture.py` (relative to this skill directory)
Global command: `harcapture` (symlinked in `~/.hermes/node/bin/`)

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

**CDP Attach mode** connects to an existing Chrome browser via raw CDP websocket. Captures ALL traffic regardless of how navigation is triggered (Playwright, raw CDP, or user clicks). Same protocol as DevTools Network tab. Presets: `camofox`, `cloakbrowser`. See `har-capture` skill for full CDP attach workflow.

### When to use HAR vs curl:

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

## Pitfalls

1. **Minified JS is still readable.** Use `grep` for patterns, don't try to read the whole file. Search for `fetch(`, `/api/`, `endpoint`, `url:`.

2. **Some APIs are server-side only.** If an endpoint is called by the server (SSR, form POST), it won't appear in client JS or network capture. Look at form `action` attributes and `<script>` blocks in SSR HTML.

3. **CDP event handlers in Playwright Python.** Use `cdp.on("event", callback)` — NOT the `@cdp.on("event")` decorator syntax. Decorator syntax raises `missing 1 required positional argument 'f'`. See references/cdp-pitfalls.md.

4. **"Invalid client" vs "invalid code".** When fuzzing API endpoints, differentiate between request-level errors (missing headers/origin → "invalid client") and content-level errors ("invalid code"). Always test with proper headers (Referer, Origin, User-Agent) first to ensure you're getting content-level errors.

5. **Rate limiting on API fuzzing.** When testing many codes/inputs, add 1-2s delays between requests. Some sites rate-limit by IP even without explicit rate limit headers.

6. **Honeypot fields.** Many SPAs include hidden form fields (honeypot) that must be empty. Bot detection checks if these are filled. When replicating API calls programmatically, always check for `display: none` fields and exclude them.

7. **SPA routing ≠ API calls.** Client-side routing (React Router, Next.js, Vue Router) navigates without server requests. Navigating to `/dashboard`, `/settings`, `/profile` on an SPA may produce zero XHR/Fetch traffic. API calls only happen on user interactions (button clicks, form submissions, data fetches). For SPA API discovery, you MUST interact with the page (click, fill, submit), not just navigate between routes.
