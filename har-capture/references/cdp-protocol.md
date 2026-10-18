# CDP Protocol Reference for HAR Capture

## WebSocket Capture Methods

### Network.webSocketCreated
Fired when WebSocket is created.
```json
{
  "requestId": "string",
  "url": "string",
  "initiator": { "type": "string" }
}
```

### Network.webSocketFrameReceived
Fired when WebSocket frame is received (server → client).
```json
{
  "requestId": "string",
  "timestamp": 1234567.89,
  "response": {
    "opcode": 1,
    "mask": false,
    "payloadData": "string"
  }
}
```

### Network.webSocketFrameSent
Fired when WebSocket frame is sent (client → server).
```json
{
  "requestId": "string",
  "timestamp": 1234567.89,
  "response": {
    "opcode": 1,
    "mask": true,
    "payloadData": "string"
  }
}
```

### Network.webSocketClosed
Fired when WebSocket is closed.
```json
{
  "requestId": "string",
  "timestamp": 1234567.89
}
```

## Required CDP Calls

```python
# MUST call before any WS events fire
await cdp.send('Network.enable')

# Then listen
cdp.on('Network.webSocketCreated', handler)
cdp.on('Network.webSocketFrameReceived', handler)
cdp.on('Network.webSocketFrameSent', handler)
cdp.on('Network.webSocketClosed', handler)
```

## HAR 1.2 WebSocket Extension

WebSockets stored in HAR under `_websockets[]` array:
```json
{
  "_websockets": [
    {
      "type": "ws",
      "url": "wss://example.com/ws",
      "startedDateTime": "2026-05-25T00:00:00Z",
      "frames": [
        {
          "type": "receive",
          "data": "payload string",
          "time": 1234567.89
        },
        {
          "type": "send",
          "data": "payload string",
          "time": 1234567.90
        }
      ]
    }
  ]
}
```

## Playwright CDP Session

```python
async with async_playwright() as p:
    browser = await p.chromium.launch()
    page = await browser.new_page()
    
    # Get CDP session
    cdp = await page.context.new_cdp_session(page)
    
    # Enable network
    await cdp.send('Network.enable')
    
    # Attach listeners (NOT decorator syntax)
    cdp.on('Network.webSocketFrameReceived', on_ws_recv)
    cdp.on('Network.webSocketFrameSent', on_ws_sent)
```

## Common Pitfalls

1. **No decorator syntax** — `@cdp.on(...)` does NOT work. Use `cdp.on(event, handler)` directly.
2. **Blocking in handlers** — Never `await asyncio.sleep()` inside CDP event handlers. Queue events instead.
3. **Network.enable required** — WS events don't fire without it.
4. **Handler signature** — `async def handler(params)` where params is a dict.
