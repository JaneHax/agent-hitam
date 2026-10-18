# Auth Flow Capture & API Replay

## Capturing Authenticated Requests

Many APIs require auth. Capture the login flow to get tokens/cookies.

### Workflow
1. Start `harcapture` (standalone or CDP attach)
2. Login manually in the browser
3. Stop capture
4. Find the auth token in captured requests

### What to look for

**Login request:**
```
POST /api/login
Body: { "email": "...", "password": "..." }
Response: { "token": "eyJ...", "user": {...} }
```

**Subsequent requests:**
```
GET /api/dashboard
Headers: Authorization: Bearer eyJ...
```

### Token types
- **JWT** — `eyJ...` format, decodable at jwt.io, has `exp` claim
- **Session cookie** — `Set-Cookie` header on login, sent automatically
- **API key** — static, in header or query param
- **OAuth** — redirect flow, `code` → `token` exchange

## Replaying Captured Requests

After capture, replay requests with curl or Python:

```bash
# Simple GET with auth
curl -H "Authorization: Bearer TOKEN" https://api.target.com/data

# POST with body
curl -X POST https://api.target.com/action \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{"key": "value"}'
```

```python
import requests

headers = {"Authorization": "Bearer TOKEN"}
resp = requests.get("https://api.target.com/data", headers=headers)
print(resp.json())
```

## Common Auth Pitfalls

1. **Token expiry** — JWT tokens have `exp` claim. Check before replaying.
2. **CORS** — Browser blocks cross-origin requests. Server-side scripts don't have this limit.
3. **CSRF tokens** — Forms may include `_csrf` token. Extract from page HTML before submitting.
4. **Cookie domains** — Cookies are domain-scoped. Don't assume cookies from `api.target.com` work on `target.com`.
5. **Fingerprinting** — Some APIs check User-Agent, headers order, TLS fingerprint. Match the original request headers exactly.
6. **Rate limiting** — Authenticated endpoints may have stricter rate limits. Check `X-RateLimit-*` headers.
