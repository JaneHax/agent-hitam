# API Response Analysis & Error Handling

## Response Format Patterns

### Standard REST
```json
{
  "data": { ... },
  "meta": { "page": 1, "total": 100 },
  "links": { "next": "...", "prev": "..." }
}
```

### Error responses
```json
{
  "error": "invalid_request",
  "message": "Missing required field: email",
  "code": 400,
  "details": { "field": "email" }
}
```

### GraphQL
```json
{
  "data": { "user": { "id": "1", "name": "..." } },
  "errors": [{ "message": "...", "path": ["user", "email"] }]
}
```

## Status Code Patterns

| Code | Meaning | Action |
|---|---|---|
| 200 | OK | Success |
| 201 | Created | Resource created |
| 204 | No Content | Success, no body |
| 400 | Bad Request | Fix request format |
| 401 | Unauthorized | Need auth token |
| 403 | Forbidden | Token valid but no permission |
| 404 | Not Found | Wrong endpoint or ID |
| 409 | Conflict | Resource already exists |
| 422 | Unprocessable | Validation error |
| 429 | Too Many Requests | Rate limited, check Retry-After |
| 500 | Server Error | Bug on their side |

## Rate Limit Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1623456789
Retry-After: 60
```

## Response Body Extraction

When building automation from HAR capture:

1. **Find the data path** — `response.data`, `response.result`, `response.items`, etc.
2. **Check pagination** — does response have `next`, `cursor`, `offset`, `page`?
3. **Identify required fields** — which fields are needed for subsequent requests?
4. **Map error codes** — what errors trigger retry vs stop?

## Common Anti-Bot Indicators

- `403` with `cf-ray` header → Cloudflare challenge
- `403` with `x-amz-cf-id` → AWS WAF
- Response body with `captcha`, `challenge`, `verify` → CAPTCHA required
- `Set-Cookie` with `cf_clearance` → Cloudflare clearance needed
- `X-Honeypot` or hidden form fields → trap for bots
