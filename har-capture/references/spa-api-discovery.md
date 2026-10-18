# SPA API Discovery Patterns

## Framework Detection

Identify the SPA framework to understand routing and data fetching patterns.

### React / Next.js
- Look for `__NEXT_DATA__` in HTML (JSON with page props)
- API routes: `/api/*` or `/pages/api/*`
- Data fetching: `getServerSideProps`, `getStaticProps` (SSR), `useEffect` + `fetch` (CSR)
- Next.js RSC (React Server Components): look for `?_rsc=` query params
- App Router: `/app/api/*/route.ts` handlers

### Vue / Nuxt
- Look for `__NUXT__` in HTML (hydration data)
- API routes: `/api/*` or `/server/api/*`
- Data fetching: `useFetch`, `useAsyncData`, `$fetch`
- Nuxt 3: Nitro server engine, API auto-imported

### SvelteKit
- Look for `__data.json` endpoint (page data prefetch)
- API routes: `/api/*` or `/src/routes/api/+server.ts`
- Data fetching: `load` functions in `+page.server.ts`
- SvelteKit trailing slash: `?x-sveltekit-trailing-slash=1`

### Astro
- Static site with islands architecture
- API routes: `/api/*` endpoints
- Look for `data-astro-transition-persist` attributes

## Client-Side Routing vs API Calls

**Key insight:** SPA routing (React Router, Vue Router, SvelteKit) navigates WITHOUT server requests. Navigating `/dashboard` → `/settings` produces ZERO XHR/Fetch traffic.

API calls only happen when:
1. Page load (initial data fetch)
2. User interaction (button click, form submit)
3. Polling/refetch (timers, WebSocket triggers)
4. Route loader (React Router loader, SvelteKit load function)

**For SPA API discovery:**
- DON'T just navigate between routes
- DO click buttons, fill forms, submit, scroll
- DO check `__NEXT_DATA__`, `__NUXT__`, `__data.json` for server-side data
- DO look at initial page load requests (most data comes here)

## GraphQL Discovery

Many SPAs use GraphQL (single endpoint, multiple queries).

**Indicators:**
- Single endpoint: `/graphql`, `/api/graphql`, `/gql`
- POST requests with `{ query, variables, operationName }` body
- Response has `{ data, errors }` wrapper
- `__typename` fields in response

**Capture tips:**
- Filter by `xhr,fetch` to reduce noise
- Look for repeated POST to same URL with different bodies
- Introspection query: `{ __schema { types { name fields { name } } } }`
- Use captured queries to build your own requests

## REST API Patterns

**Common endpoint structures:**
```
GET    /api/v1/resource          # List
GET    /api/v1/resource/:id      # Get one
POST   /api/v1/resource          # Create
PUT    /api/v1/resource/:id      # Update
DELETE /api/v1/resource/:id      # Delete
```

**Auth patterns:**
- `Authorization: Bearer <token>` header
- Cookie-based session (`Set-Cookie` on login)
- API key in header (`X-API-Key`) or query (`?api_key=`)
- JWT tokens (check `exp` claim for expiry)

**Pagination patterns:**
- `?page=1&limit=20` — offset-based
- `?cursor=abc&limit=20` — cursor-based
- `?offset=0&count=20` — offset with count
- `Link` header with `next`/`prev` URLs
