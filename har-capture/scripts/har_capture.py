#!/usr/bin/env python3
"""
HAR Capture Tool — Capture network traffic from any website.

Two modes:
  1. Standalone: Opens its own Playwright browser, navigate to URL, capture.
  2. CDP Attach: Connect to existing browser (Chrome/CloakBrowser) via CDP URL.
     Uses CDP Network events for capture — ALL traffic captured regardless of
     how navigation is triggered (Playwright, raw CDP, or user clicks).

Usage:
    harcapture <url> [options]
    harcapture --cdp-url http://localhost:9222 [url] [options]

Defaults: XHR + Fetch + WebSocket filter, manual close (press Enter).
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Error: playwright not installed. Run: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

# Built-in CDP endpoint shortcuts
CDP_PRESETS = {
    "camofox": "http://localhost:9377",
    "cloakbrowser": "http://localhost:9222",
}


class HARCapture:
    def __init__(self, url, output="capture.har", resource_filter="xhr,fetch,ws",
                 headless=False, wait=0, cdp_url=None, existing_tab=False):
        self.url = url
        self.output = output
        self.resource_filter = resource_filter
        self.headless = headless
        self.wait = wait
        self.cdp_url = cdp_url
        self.existing_tab = existing_tab
        self.entries = []
        self.ws_messages = []
        self.started = datetime.now(timezone.utc)
        self._page = None
        self._ws_connections = {}
        self._pending_requests = {}  # requestId -> request info (for CDP mode)

    # ──────────────────────────────────────────────────────────────
    # Standalone mode — Playwright response listener
    # ──────────────────────────────────────────────────────────────

    async def _on_response_standalone(self, response):
        """Playwright response handler for standalone mode."""
        try:
            request = response.request
            resource_type = request.resource_type

            if self.resource_filter != "all":
                filter_types = [t.strip() for t in self.resource_filter.split(",")]
                filter_types = ["websocket" if t == "ws" else t for t in filter_types]
                if resource_type not in filter_types:
                    return

            req_headers = [{"name": k, "value": v} for k, v in request.headers.items()]
            req_body = None
            try:
                req_body = request.post_data
            except:
                pass

            resp_headers = [{"name": k, "value": v} for k, v in response.headers.items()]
            resp_body = None
            resp_size = 0
            try:
                resp_body = await response.text()
                resp_size = len(resp_body.encode("utf-8"))
            except:
                pass

            entry = self._build_entry(
                method=request.method,
                url=request.url,
                req_headers=req_headers,
                req_body=req_body,
                status=response.status,
                status_text=response.status_text,
                resp_headers=resp_headers,
                resp_body=resp_body,
                resp_size=resp_size,
                resource_type=resource_type,
            )
            self.entries.append(entry)
            self._log_request(request.method, response.status, request.url, resource_type)

        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────
    # CDP Attach mode — CDP Network events
    # ──────────────────────────────────────────────────────────────

    async def _on_cdp_request_will_be_sent(self, params):
        """CDP Network.requestWillBeSent — store request info."""
        req = params.get("request", {})
        request_id = params.get("requestId", "")
        resource_type = params.get("type", "Other")

        # Apply filter
        if self.resource_filter != "all":
            filter_types = [t.strip() for t in self.resource_filter.split(",")]
            filter_types = ["websocket" if t == "ws" else t for t in filter_types]
            # Map CDP types to our filter types
            type_map = {
                "XHR": "xhr",
                "Fetch": "fetch",
                "WebSocket": "websocket",
                "Document": "document",
                "Script": "script",
            }
            mapped = type_map.get(resource_type, resource_type.lower())
            if mapped not in filter_types:
                return

        self._pending_requests[request_id] = {
            "method": req.get("method", "GET"),
            "url": req.get("url", ""),
            "headers": req.get("headers", {}),
            "post_data": req.get("postData", None),
            "resource_type": resource_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _on_cdp_response_received(self, params):
        """CDP Network.responseReceived — fetch response body."""
        request_id = params.get("requestId", "")
        resp = params.get("response", {})
        resource_type = params.get("type", "Other")

        if request_id not in self._pending_requests:
            return

        req_info = self._pending_requests[request_id]

        # Get response body via CDP
        resp_body = None
        resp_size = 0
        try:
            # Network.getResponseBody works for completed requests
            # But we need to wait for loadingFinished first
            # Store info, we'll fetch body in loadingFinished
            pass
        except:
            pass

        req_headers = [{"name": k, "value": v} for k, v in req_info["headers"].items()]
        resp_headers = [{"name": k, "value": v} for k, v in resp.get("headers", {}).items()]

        entry = self._build_entry(
            method=req_info["method"],
            url=req_info["url"],
            req_headers=req_headers,
            req_body=req_info["post_data"],
            status=resp.get("status", 0),
            status_text=resp.get("statusText", ""),
            resp_headers=resp_headers,
            resp_body=None,  # Will be filled by loadingFinished
            resp_size=resp.get("headers", {}).get("content-length", 0),
            resource_type=req_info["resource_type"],
        )
        entry["_request_id"] = request_id
        self.entries.append(entry)
        self._log_request(
            req_info["method"],
            resp.get("status", 0),
            req_info["url"],
            req_info["resource_type"],
        )

    async def _on_cdp_loading_finished(self, params, cdp):
        """CDP Network.loadingFinished — fetch response body."""
        request_id = params.get("requestId", "")

        # Find the entry for this request
        entry = None
        for e in self.entries:
            if e.get("_request_id") == request_id:
                entry = e
                break

        if not entry:
            return

        # Fetch response body
        try:
            result = await cdp.send("Network.getResponseBody", {"requestId": request_id})
            body = result.get("body", "")
            is_base64 = result.get("base64Encoded", False)
            if is_base64:
                import base64
                body = base64.b64decode(body).decode("utf-8", errors="replace")

            entry["response"]["content"]["text"] = body
            entry["response"]["bodySize"] = len(body.encode("utf-8"))
            entry["response"]["content"]["size"] = len(body.encode("utf-8"))
        except Exception:
            pass

        # Cleanup
        self._pending_requests.pop(request_id, None)

    async def _on_cdp_ws_created(self, params):
        """CDP Network.webSocketCreated."""
        ws_id = params.get("requestId", "")
        url = params.get("url", "")
        self._ws_connections[ws_id] = {"url": url, "frames": []}
        print(f"  [WS OPEN] {url}")

    async def _on_cdp_ws_recv(self, params):
        """CDP Network.webSocketFrameReceived."""
        ws_id = params.get("requestId", "")
        resp = params.get("response", {})
        payload = resp.get("payloadData", "")
        if ws_id in self._ws_connections:
            self._ws_connections[ws_id]["frames"].append({
                "direction": "recv",
                "data": payload[:2000],
                "opcode": resp.get("opcode", 1),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            url_short = self._ws_connections[ws_id]["url"][:80]
            print(f"  [WS RECV] {url_short}  {payload[:100]}")

    async def _on_cdp_ws_sent(self, params):
        """CDP Network.webSocketFrameSent."""
        ws_id = params.get("requestId", "")
        resp = params.get("response", {})
        payload = resp.get("payloadData", "")
        if ws_id in self._ws_connections:
            self._ws_connections[ws_id]["frames"].append({
                "direction": "sent",
                "data": payload[:2000],
                "opcode": resp.get("opcode", 1),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            url_short = self._ws_connections[ws_id]["url"][:80]
            print(f"  [WS SENT] {url_short}  {payload[:100]}")

    async def _on_cdp_ws_closed(self, params):
        """CDP Network.webSocketClosed."""
        ws_id = params.get("requestId", "")
        if ws_id in self._ws_connections:
            url_short = self._ws_connections[ws_id]["url"][:80]
            print(f"  [WS CLOSE] {url_short}")

    # ──────────────────────────────────────────────────────────────
    # Shared helpers
    # ──────────────────────────────────────────────────────────────

    def _build_entry(self, method, url, req_headers, req_body,
                     status, status_text, resp_headers, resp_body,
                     resp_size, resource_type):
        """Build a HAR entry dict."""
        return {
            "startedDateTime": datetime.now(timezone.utc).isoformat(),
            "time": 0,
            "request": {
                "method": method,
                "url": url,
                "httpVersion": "HTTP/1.1",
                "headers": req_headers,
                "queryString": self._parse_query(url),
                "postData": {
                    "mimeType": next((h["value"] for h in req_headers if h["name"].lower() == "content-type"), ""),
                    "text": req_body or ""
                } if req_body else None,
                "headersSize": -1,
                "bodySize": len(req_body) if req_body else 0,
            },
            "response": {
                "status": status,
                "statusText": status_text,
                "httpVersion": "HTTP/1.1",
                "headers": resp_headers,
                "content": {
                    "size": resp_size if isinstance(resp_size, int) else len((resp_body or "").encode("utf-8")),
                    "mimeType": next((h["value"] for h in resp_headers if h["name"].lower() == "content-type"), ""),
                    "text": resp_body or ""
                },
                "headersSize": -1,
                "bodySize": resp_size if isinstance(resp_size, int) else len((resp_body or "").encode("utf-8")),
            },
            "cache": {},
            "timings": {"send": 0, "wait": 0, "receive": 0},
            "_resourceType": resource_type,
        }

    def _log_request(self, method, status, url, resource_type):
        """Print live log line."""
        url_short = url[:120]
        print(f"  [{status}] {method} {url_short}  ({resource_type})")

    @staticmethod
    def _parse_query(url):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        return [{"name": k, "value": v[0]} for k, v in params.items()]

    def _resolve_cdp_url(self):
        """Resolve CDP URL from presets or direct URL."""
        url = self.cdp_url.lower().strip()
        for name, preset in CDP_PRESETS.items():
            if url == name or url == f"{name}:" or url == f"{name}://":
                return preset
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if ":" in url:
            return f"http://{url}"
        return f"http://{url}"

    async def _get_cdp_targets(self, cdp_base):
        """Get list of available browser targets/tabs."""
        import urllib.request
        try:
            req = urllib.request.Request(f"{cdp_base}/json/list")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"  Error fetching targets: {e}")
            return []

    # ──────────────────────────────────────────────────────────────
    # CDP Attach mode — main flow
    # ──────────────────────────────────────────────────────────────

    async def _attach_to_existing_browser(self):
        """Attach to existing browser via raw CDP websocket.

        Uses raw CDP Network events (NOT Playwright) so ALL traffic is captured
        regardless of how navigation is triggered (Playwright, raw CDP, or user clicks).
        """
        import websockets
        import urllib.request

        cdp_base = self._resolve_cdp_url()
        print(f"Connecting to: {cdp_base}")

        targets = await self._get_cdp_targets(cdp_base)
        if not targets:
            print("Error: No targets found. Is the browser running?")
            sys.exit(1)

        page_targets = [t for t in targets if t.get("type") == "page"]
        print(f"\nAvailable tabs ({len(targets)}):")
        for i, t in enumerate(targets):
            title = t.get("title", "")[:60]
            url = t.get("url", "")[:80]
            ttype = t.get("type", "page")
            print(f"  [{i}] ({ttype}) {title} — {url}")

        if not page_targets:
            print("Error: No page targets found.")
            sys.exit(1)

        # Find or create a tab
        ws_url = None
        if self.existing_tab:
            # Use first page tab
            target = page_targets[0]
            ws_url = target.get("webSocketDebuggerUrl")
            print(f"\nAttaching to: {target.get('url', '')[:80]}")
        elif self.url:
            # Create new tab with URL
            try:
                import urllib.parse
                new_url = f"{cdp_base}/json/new?{urllib.parse.quote(self.url, safe='')}"
                req = urllib.request.Request(new_url, method="PUT")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    new_tab = json.loads(resp.read())
                ws_url = new_tab.get("webSocketDebuggerUrl")
                print(f"\nNew tab: {self.url}")
            except Exception as e:
                # Fallback to first page tab
                print(f"\nNew tab failed ({e}), using existing tab")
                target = page_targets[0]
                ws_url = target.get("webSocketDebuggerUrl")
        else:
            target = page_targets[0]
            ws_url = target.get("webSocketDebuggerUrl")
            print(f"\nUsing: {target.get('url', '')[:80]}")

        if not ws_url:
            print("Error: No WebSocket debugger URL found.")
            sys.exit(1)

        # Connect via raw CDP websocket
        msg_id = 0
        pending_requests = {}

        async def send_cmd(ws, method, params=None):
            nonlocal msg_id
            msg_id += 1
            cmd = {"id": msg_id, "method": method}
            if params:
                cmd["params"] = params
            await ws.send(json.dumps(cmd))
            while True:
                resp = json.loads(await ws.recv())
                if resp.get("id") == msg_id:
                    return resp
                await handle_event(ws, resp)

        async def handle_event(ws, event):
            method = event.get("method", "")
            params = event.get("params", {})

            if method == "Network.requestWillBeSent":
                req = params.get("request", {})
                req_id = params.get("requestId", "")
                res_type = params.get("type", "Other")

                if self.resource_filter != "all":
                    filter_types = [t.strip() for t in self.resource_filter.split(",")]
                    filter_types = ["websocket" if t == "ws" else t for t in filter_types]
                    type_map = {"XHR": "xhr", "Fetch": "fetch", "WebSocket": "websocket",
                                "Document": "document", "Script": "script"}
                    mapped = type_map.get(res_type, res_type.lower())
                    if mapped not in filter_types:
                        return

                pending_requests[req_id] = {
                    "method": req.get("method", "GET"),
                    "url": req.get("url", ""),
                    "headers": req.get("headers", {}),
                    "post_data": req.get("postData"),
                    "resource_type": res_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            elif method == "Network.responseReceived":
                req_id = params.get("requestId", "")
                resp = params.get("response", {})
                if req_id not in pending_requests:
                    return

                p = pending_requests[req_id]
                entry = self._build_entry(
                    method=p["method"],
                    url=p["url"],
                    req_headers=[{"name": k, "value": v} for k, v in p["headers"].items()],
                    req_body=p["post_data"],
                    status=resp.get("status", 0),
                    status_text=resp.get("statusText", ""),
                    resp_headers=[{"name": k, "value": v} for k, v in resp.get("headers", {}).items()],
                    resp_body=None,
                    resp_size=int(resp.get("headers", {}).get("content-length", 0)),
                    resource_type=p["resource_type"],
                )
                entry["_request_id"] = req_id
                self.entries.append(entry)
                self._log_request(p["method"], resp.get("status", 0), p["url"], p["resource_type"])

            elif method == "Network.loadingFinished":
                req_id = params.get("requestId", "")
                for entry in self.entries:
                    if entry.get("_request_id") == req_id:
                        try:
                            result = await send_cmd(ws, "Network.getResponseBody", {"requestId": req_id})
                            body = result.get("result", {}).get("body", "")
                            is_b64 = result.get("result", {}).get("base64Encoded", False)
                            if is_b64:
                                import base64
                                body = base64.b64decode(body).decode("utf-8", errors="replace")
                            entry["response"]["content"]["text"] = body
                            body_size = len(body.encode("utf-8"))
                            entry["response"]["content"]["size"] = body_size
                            entry["response"]["bodySize"] = body_size
                        except:
                            pass
                        pending_requests.pop(req_id, None)
                        break

            elif method == "Network.webSocketCreated":
                ws_id = params.get("requestId", "")
                url = params.get("url", "")
                self._ws_connections[ws_id] = {"url": url, "frames": []}
                print(f"  [WS OPEN] {url}")

            elif method == "Network.webSocketFrameReceived":
                ws_id = params.get("requestId", "")
                resp = params.get("response", {})
                if ws_id in self._ws_connections:
                    self._ws_connections[ws_id]["frames"].append({
                        "direction": "recv",
                        "data": resp.get("payloadData", "")[:2000],
                        "opcode": resp.get("opcode", 1),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })

            elif method == "Network.webSocketFrameSent":
                ws_id = params.get("requestId", "")
                resp = params.get("response", {})
                if ws_id in self._ws_connections:
                    self._ws_connections[ws_id]["frames"].append({
                        "direction": "sent",
                        "data": resp.get("payloadData", "")[:2000],
                        "opcode": resp.get("opcode", 1),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })

            elif method == "Network.webSocketClosed":
                ws_id = params.get("requestId", "")
                if ws_id in self._ws_connections:
                    url_short = self._ws_connections[ws_id]["url"][:80]
                    print(f"  [WS CLOSE] {url_short}")

        async def drain_events(ws, duration):
            """Receive events for `duration` seconds."""
            end = asyncio.get_event_loop().time() + duration
            while asyncio.get_event_loop().time() < end:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    event = json.loads(raw)
                    if "method" in event:
                        await handle_event(ws, event)
                except asyncio.TimeoutError:
                    continue
                except:
                    break

        async with websockets.connect(ws_url, max_size=50*1024*1024) as ws:
            # Enable Network capture
            await send_cmd(ws, "Network.enable")
            print("CDP Network capture active")

            # Navigate if URL provided and we didn't create a new tab with URL
            if self.url and not self.existing_tab:
                # Check if already navigated
                pass  # Already navigated via /json/new

            print(f"Filter: {self.resource_filter}")
            print(f"{'='*60}")
            print(f"\nInteract with the browser (navigate, click, submit).")
            print(f"All XHR/Fetch/WS traffic will be captured.")

            if self.wait > 0:
                print(f"Waiting {self.wait}s...")
                await drain_events(ws, self.wait)
            else:
                print(f"Press Enter to stop capture...")
                # Run input() in executor while draining events
                loop = asyncio.get_event_loop()
                input_task = loop.run_in_executor(None, input)
                while not input_task.done():
                    await drain_events(ws, 0.5)

        self._save_results()

    # ──────────────────────────────────────────────────────────────
    # Standalone mode
    # ──────────────────────────────────────────────────────────────

    async def _run_standalone(self):
        """Run with standalone Playwright browser."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            self._page = page

            # Use Playwright response listener (works fine for standalone)
            page.on("response", self._on_response_standalone)

            # Also setup CDP for WebSocket capture
            filter_types = [t.strip() for t in self.resource_filter.split(",")]
            if "ws" in filter_types or "websocket" in filter_types or self.resource_filter == "all":
                cdp = await page.context.new_cdp_session(page)
                await cdp.send("Network.enable")
                cdp.on("Network.webSocketCreated", self._on_cdp_ws_created)
                cdp.on("Network.webSocketFrameReceived", self._on_cdp_ws_recv)
                cdp.on("Network.webSocketFrameSent", self._on_cdp_ws_sent)
                cdp.on("Network.webSocketClosed", self._on_cdp_ws_closed)

            print(f"Navigating to: {self.url}")
            try:
                await page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
                print(f"Page loaded. Capturing traffic...")
            except Exception as e:
                print(f"Navigation: {e}")
                print("Continuing capture...")

            print(f"Filter: {self.resource_filter}")
            print(f"{'='*60}")

            if self.wait > 0:
                print(f"Waiting {self.wait}s...")
                await asyncio.sleep(self.wait)
            else:
                print(f"\nBrowse the site. Press Enter to stop capture...")
                await asyncio.get_event_loop().run_in_executor(None, input)

            self._save_results()

            await browser.close()

    # ──────────────────────────────────────────────────────────────
    # Output
    # ──────────────────────────────────────────────────────────────

    def _save_results(self):
        """Save HAR file and print API summary."""
        har = self.build_har()
        with open(self.output, "w") as f:
            json.dump(har, f, indent=2)

        ws_frame_count = sum(
            len(ws["frames"])
            for ws in self._ws_connections.values()
        )

        print(f"\n{'='*60}")
        print(f"Capture complete!")
        print(f"  HTTP entries: {len(self.entries)}")
        print(f"  WS connections: {len(self._ws_connections)}")
        print(f"  WS frames: {ws_frame_count}")
        print(f"  Output: {self.output}")
        print(f"  Size: {Path(self.output).stat().st_size / 1024:.1f} KB")

        apis = self.extract_apis()
        if apis:
            print(f"\n{'='*60}")
            print(f"API Endpoints: {len(apis)}")
            print(f"{'='*60}")
            for key, info in sorted(apis.items()):
                body_marker = " [POST body]" if info.get("has_body") else ""
                ws_marker = f" [{info.get('frame_count', 0)} frames]" if info["method"] == "WS" else ""
                print(f"\n  {info['method']:6} {info['url']}")
                print(f"         Status: {info['status']} | Type: {info['content_type'][:60]}{body_marker}{ws_marker}")
                if info.get("sample_request"):
                    req_str = json.dumps(info["sample_request"], ensure_ascii=False)
                    print(f"         Request:  {req_str[:200]}")
                if info.get("sample_response"):
                    resp_str = json.dumps(info["sample_response"], ensure_ascii=False)
                    print(f"         Response: {resp_str[:200]}")
                if info.get("sample_frames"):
                    for frame in info["sample_frames"][:3]:
                        d = frame["direction"].upper()
                        print(f"         WS {d}: {frame['data'][:150]}")
        else:
            print(f"\nNo API endpoints captured.")

    def build_har(self):
        """Build HAR 1.2 with WS messages appended."""
        ws_entries = []
        for ws_id, ws in self._ws_connections.items():
            if ws["frames"]:
                ws_entries.append({
                    "_type": "websocket",
                    "url": ws["url"],
                    "frameCount": len(ws["frames"]),
                    "frames": ws["frames"]
                })

        # Remove internal fields from entries
        clean_entries = []
        for entry in self.entries:
            clean = {k: v for k, v in entry.items() if not k.startswith("_")}
            clean_entries.append(clean)

        return {
            "log": {
                "version": "1.2",
                "creator": {"name": "har-capture", "version": "2.1.0"},
                "entries": clean_entries,
                "_websockets": ws_entries
            }
        }

    def extract_apis(self):
        """Extract unique API endpoints from captured entries."""
        apis = {}
        for entry in self.entries:
            url = entry["request"]["url"]
            method = entry["request"]["method"]
            status = entry["response"]["status"]
            resp_headers = entry["response"]["headers"]
            content_type_val = ""
            for h in resp_headers:
                if h["name"].lower() == "content-type":
                    content_type_val = h["value"]
                    break

            skip_ext = (".js", ".css", ".png", ".jpg", ".gif", ".svg", ".woff",
                        ".woff2", ".ico", ".ttf", ".map")
            if any(url.split("?")[0].endswith(ext) for ext in skip_ext):
                continue

            key = f"{method} {url.split('?')[0]}"
            if key not in apis:
                apis[key] = {
                    "method": method,
                    "url": url.split("?")[0],
                    "full_url": url,
                    "status": status,
                    "content_type": content_type_val,
                    "has_body": entry["request"]["postData"] is not None,
                    "sample_request": None,
                    "sample_response": None,
                }
                if entry["request"]["postData"]:
                    try:
                        apis[key]["sample_request"] = json.loads(entry["request"]["postData"]["text"])
                    except:
                        apis[key]["sample_request"] = entry["request"]["postData"]["text"][:500]
                try:
                    resp_text = entry["response"]["content"]["text"]
                    if resp_text:
                        apis[key]["sample_response"] = json.loads(resp_text)
                except:
                    if entry["response"]["content"]["text"]:
                        apis[key]["sample_response"] = entry["response"]["content"]["text"][:500]

        # Add WebSocket endpoints
        for ws_id, ws in self._ws_connections.items():
            key = f"WS {ws['url']}"
            if key not in apis:
                recv_count = sum(1 for f in ws["frames"] if f["direction"] == "recv")
                sent_count = sum(1 for f in ws["frames"] if f["direction"] == "sent")
                apis[key] = {
                    "method": "WS",
                    "url": ws["url"],
                    "full_url": ws["url"],
                    "status": f"{recv_count} recv, {sent_count} sent",
                    "content_type": "websocket",
                    "has_body": False,
                    "sample_request": None,
                    "sample_response": None,
                    "frame_count": len(ws["frames"]),
                    "sample_frames": ws["frames"][:5]
                }

        return apis

    async def run(self):
        """Run the capture — standalone or CDP attach."""
        if self.cdp_url:
            await self._attach_to_existing_browser()
        else:
            await self._run_standalone()


def main():
    parser = argparse.ArgumentParser(
        description="HAR Capture Tool — capture network traffic from any website",
        epilog="""
CDP Attach mode:
  harcapture --cdp-url http://localhost:9222 https://example.com
  harcapture --cdp-url cloakbrowser https://example.com   (preset)
  harcapture --cdp-url http://localhost:9222 --existing-tab (attach to current tab)

Presets:
  camofox       → http://localhost:9377
  cloakbrowser  → http://localhost:9222
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url", nargs="?", default=None,
                        help="URL to capture (optional in CDP attach mode)")
    parser.add_argument("-o", "--output", default=None,
                        help="Output HAR file (default: ~/scripts/har-capture/output/<domain>.har)")
    parser.add_argument("-f", "--filter", default="xhr,fetch,ws",
                        help="Resource types: xhr,fetch,ws,document,script,all (default: xhr,fetch,ws)")
    parser.add_argument("--headless", action="store_true", help="Run headless (standalone mode only)")
    parser.add_argument("--wait", type=int, default=0,
                        help="Wait N seconds then auto-close (default: 0 = manual)")
    parser.add_argument("--cdp-url", default=None,
                        help="Attach to existing browser via CDP (URL or preset: camofox, cloakbrowser)")
    parser.add_argument("--existing-tab", action="store_true",
                        help="Attach to existing tab instead of opening new one")

    args = parser.parse_args()

    if not args.url and not args.cdp_url:
        parser.error("URL is required in standalone mode (or use --cdp-url)")

    # Auto-generate output path from domain
    if args.output is None:
        from urllib.parse import urlparse
        source_url = args.url or args.cdp_url or "unknown"
        parsed = urlparse(source_url)
        domain = parsed.hostname or "unknown"
        # Clean domain for filename
        domain = domain.replace(".", "_").replace(":", "_")
        output_dir = Path.home() / "scripts" / "har-capture" / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = str(output_dir / f"{domain}_{timestamp}.har")

    capture = HARCapture(
        url=args.url,
        output=args.output,
        resource_filter=args.filter,
        headless=args.headless,
        wait=args.wait,
        cdp_url=args.cdp_url,
        existing_tab=args.existing_tab,
    )

    asyncio.run(capture.run())


if __name__ == "__main__":
    main()
