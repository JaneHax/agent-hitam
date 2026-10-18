# Common API Discovery Patterns

## SPA/JS-Heavy Sites
Problem: API endpoints hidden in JavaScript bundles, not visible in HTML source.

**Workflow:**
1. `harcapture 'https://site.com' --headless --wait 15`
2. Review XHR/Fetch calls in terminal output
3. Look for `/api/`, `/v1/`, `/graphql` patterns
4. Check request/response bodies for data structures

## GraphQL Endpoints
Many SPAs use GraphQL (single endpoint, multiple queries).

**Indicators:**
- Single endpoint like `/graphql` or `/api/graphql`
- POST requests with `query` and `variables` fields
- Response has `data` wrapper object

**Capture tips:**
- Filter by `xhr,fetch` to reduce noise
- Look for repeated POST to same URL with different bodies
- Introspection query: `{ __schema { types { name } } }`

## WebSocket-Heavy Apps
Real-time apps (chat, trading, live updates) use WS.

**Indicators:**
- `wss://` connections in Network tab
- Frames with JSON payloads
- Heartbeat/ping-pong frames

**Capture tips:**
- Use default filter `xhr,fetch,ws`
- WS frames show as `[WS RECV]` and `[WS SENT]`
- Look for subscription patterns (client sends subscribe, server pushes updates)

## Authentication Flows
Most APIs need auth. Capture the login flow.

**Workflow:**
1. Start capture: `harcapture 'https://site.com/login'`
2. Perform login manually in browser
3. Stop capture
4. Look for:
   - POST to `/login`, `/auth/token`, `/oauth/authorize`
   - Response with `token`, `access_token`, `session_id`
   - Subsequent requests with `Authorization` or `Cookie` header

## Reverse-Engineering Checklist

After capture, extract:
1. **Base URL** — common prefix for all API calls
2. **Auth method** — Cookie, Bearer token, API key header
3. **Endpoints** — unique paths with methods
4. **Request format** — JSON body, query params, form data
5. **Response format** — data wrapper, pagination, error structure
6. **Rate limits** — 429 responses, Retry-After headers
