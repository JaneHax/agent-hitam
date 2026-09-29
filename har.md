## API Discovery

When exploring a new website or reverse-engineering its API:

- **Default tool:** `harcapture` (CDP-based HAR capture), NOT manual `curl` + `grep` through source code.
- `harcapture` captures XHR, Fetch, AND WebSocket traffic automatically with request/response bodies, headers, and API summary.
- `curl` + source code grep is the **fallback** only when: (1) headless browser is unavailable, (2) site blocks Playwright, or (3) only need to check a single known endpoint.

**Two modes:**
1. **Standalone** — opens its own Playwright browser: `harcapture '<url>' --headless --wait N`
2. **CDP Attach** — connects to existing Chrome via raw CDP websocket: `harcapture --cdp-url http://localhost:9222 '<url>'`

**CDP Attach mode uses raw CDP `Network.*` events** (NOT Playwright response listener). This captures ALL traffic regardless of how navigation is triggered — Playwright, raw CDP scripts, or user clicks. Same protocol as DevTools Network tab.

**Standard flow:**
1. `harcapture '<url>' --headless --wait N` (standalone, quick capture)
2. Or: start Chrome with `--remote-debugging-port=9222`, then `harcapture --cdp-url http://localhost:9222 '<url>'` (interactive, CDP attach)
3. Review API summary in terminal output
4. HAR file saved persistently at `~/scripts/har-capture/output/<domain>_<timestamp>.har`
5. Use extracted endpoints in scripts

**Don't:** Download all JS files and manually grep for `fetch()` calls when `harcapture` can capture the actual live traffic with real payloads and responses. Source code only shows what the client *could* send; HAR capture shows what it *actually* sends.
