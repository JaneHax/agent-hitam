# Interactive CDP Capture Workflow

When you need to capture API traffic from user interactions (button clicks, form submissions, SPA navigation), use CDP attach mode with raw CDP websocket for interaction.

## Pattern: harcapture + raw CDP interaction

```bash
# Terminal 1: Start Chrome with CDP
export DISPLAY=:99
google-chrome --remote-debugging-port=9222 --no-first-run --no-default-browser-check --disable-gpu --window-size=1280,720 --user-data-dir=/tmp/chrome-cdp &

# Terminal 2: Start harcapture (creates new tab, waits for interaction)
harcapture --cdp-url http://localhost:9222 'https://target.com' --wait 30 -o capture.har &

# Terminal 3: Interact via raw CDP websocket
```

## Raw CDP interaction script

```python
import asyncio, json, websockets, urllib.request

# Get tab ID
targets = json.loads(urllib.request.urlopen("http://localhost:9222/json/list").read())
tab = [t for t in targets if t["type"] == "page" and "target" in t.get("url", "")][0]
ws_url = tab["webSocketDebuggerUrl"]

async def interact():
    msg_id = 0
    async with websockets.connect(ws_url, max_size=50*1024*1024) as ws:
        async def send(method, params=None):
            nonlocal msg_id
            msg_id += 1
            cmd = {"id": msg_id, "method": method}
            if params: cmd["params"] = params
            await ws.send(json.dumps(cmd))
            while True:
                resp = json.loads(await ws.recv())
                if resp.get("id") == msg_id: return resp

        # Navigate
        await send("Page.navigate", {"url": "https://target.com/page2"})
        await asyncio.sleep(3)

        # Click button
        await send("Runtime.evaluate", {
            "expression": """
                (function() {
                    var btns = document.querySelectorAll('button');
                    for (var b of btns) {
                        if (b.textContent.includes('Submit')) {
                            b.click();
                            return 'Clicked Submit';
                        }
                    }
                    return 'Not found';
                })()
            """,
            "returnByValue": True
        })
        await asyncio.sleep(3)

        # Fill form
        await send("Runtime.evaluate", {
            "expression": """
                document.querySelector('input[name="email"]').value = 'test@example.com';
                document.querySelector('form').submit();
            """,
            "returnByValue": True
        })
        await asyncio.sleep(3)

asyncio.run(interact())
```

## Why raw CDP instead of Playwright

Playwright's `page.on("response")` listener only captures responses from Playwright-initiated navigations. When you navigate via raw CDP websocket, those responses bypass Playwright's listener entirely.

The harcapture CDP attach mode uses raw CDP `Network.*` events, which capture ALL traffic on the tab regardless of how navigation was triggered.

## Chrome CDP endpoint reference

```
GET  /json/list           — list all tabs
PUT  /json/new?<url>      — create new tab (PUT required in Chrome 148+)
GET  /json/version        — browser version + webSocketDebuggerUrl
GET  /json/close/<id>     — close tab
```

## Common interactions via CDP

```python
# Navigate
await send("Page.navigate", {"url": "https://..."})

# Click element
await send("Runtime.evaluate", {
    "expression": "document.querySelector('.btn').click()",
    "returnByValue": True
})

# Fill input
await send("Runtime.evaluate", {
    "expression": "document.querySelector('input').value = 'text'",
    "returnByValue": True
})

# Get page content
await send("Runtime.evaluate", {
    "expression": "document.body.innerText",
    "returnByValue": True
})

# Wait for element
await send("Runtime.evaluate", {
    "expression": """
        new Promise(resolve => {
            const check = () => {
                const el = document.querySelector('.result');
                if (el) resolve(el.textContent);
                else setTimeout(check, 500);
            };
            check();
        })
    """,
    "awaitPromise": True,
    "returnByValue": True
})
```
