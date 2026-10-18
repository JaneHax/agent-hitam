# Playwright Python CDP Pitfalls

## Event Handler Syntax

**WRONG** — decorator syntax raises `missing 1 required positional argument 'f'`:
```python
@cdp.on("Network.webSocketFrameReceived")
def handler(params):
    ...
```

**CORRECT** — pass callback directly:
```python
def handler(params):
    ...

cdp.on("Network.webSocketFrameReceived", handler)
```

This applies to ALL CDP event types in Playwright Python's async API. The `on()` method expects `(event_name, callback)` — it does NOT return a decorator.

## Common CDP Network Events

| Event | Params | Use |
|---|---|---|
| `Network.webSocketCreated` | `requestId`, `url` | WS connection opened |
| `Network.webSocketFrameReceived` | `requestId`, `response.payloadData`, `response.opcode` | WS frame received |
| `Network.webSocketFrameSent` | `requestId`, `response.payloadData`, `response.opcode` | WS frame sent |
| `Network.webSocketClosed` | `requestId` | WS connection closed |
| `Network.requestWillBeSent` | `requestId`, `request.url`, `request.method` | HTTP request |
| `Network.responseReceived` | `requestId`, `response.status`, `response.url` | HTTP response |

## Setup Pattern

```python
cdp = await page.context.new_cdp_session(page)
await cdp.send("Network.enable")

def on_ws_recv(params):
    payload = params.get("response", {}).get("payloadData", "")
    print(f"WS: {payload[:100]}")

cdp.on("Network.webSocketFrameReceived", on_ws_recv)
```

## Caveats

- CDP session must be created AFTER page navigation or it may not capture early requests
- `Network.enable` must be called before events fire
- `payloadData` for binary WS frames may be base64-encoded
- Opcode 1 = text, 2 = binary
