# Local development: CORS, Chrome Private Network Access, and the Vite `/api` proxy

This note explains why the browser sometimes reports **CORS errors** (often with **0 B** response size) when the SPA runs on `http://{tenant}.localhost:5173` and Django runs on `http://{tenant}.localhost:8000`, and how the project mitigates it.

---

## Symptoms

- **DevTools Network**: failed XHR/fetch to `/api/...` labeled **CORS error**, very fast (~tens of ms), **0.0 kB** body.
- **Django `runserver` console**: lines like `code 400, message Bad request version (...)` and *You're accessing the development server over HTTPS, but it only supports HTTP* (separate issue; see below).

---

## Root causes

### 1. Cross-origin even on “localhost”

The SPA and API use **different origins** when ports differ, for example:

- Page: `http://demo1.localhost:5173`
- API: `http://demo1.localhost:8000`

Browsers apply **CORS** and may send an **OPTIONS** preflight for non-simple requests (e.g. `Authorization` header).

### 2. Chrome Private Network Access (PNA)

For some **cross-port localhost** requests, Chrome sends a preflight that includes:

`Access-Control-Request-Private-Network: true`

The server must respond with:

`Access-Control-Allow-Private-Network: true`

**django-cors-headers** only adds that header when **`CORS_ALLOW_PRIVATE_NETWORK`** is enabled (it defaults to `False`). If it is missing, the preflight fails and Chrome surfaces the failure as a **CORS error**, even when normal `Access-Control-Allow-Origin` logic looks correct.

### 3. HTTPS clients hitting HTTP `runserver`

If anything opens **`https://...:8000`** against Django’s development server (TLS bytes on a plain-HTTP socket), the console shows binary garbage and the HTTPS message. Typical causes: page or tool using `https` for the API base URL, HSTS, or another client probing port 8000 with TLS. **`runserver` does not terminate TLS.**

---

## What we configure

### Backend (Django)

In **`core/settings.py`** (and mirrored for dev in **`core/settingsprod.py`**) when `ENVIRONMENT == "development"`:

- **`CORS_ALLOW_ALL_ORIGINS = True`** — permissive list for local dev.
- **`CORS_ALLOW_PRIVATE_NETWORK = True`** — satisfies Chrome’s PNA preflight when the browser still talks **directly** to `:8000` from the SPA origin (e.g. onboarding routes; see below).

Relevant snippet:

```python
if ENVIRONMENT == "development":
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_PRIVATE_NETWORK = True
```

**Middleware order** already keeps **`corsheaders.middleware.CorsMiddleware`** before subscription checks so error responses (e.g. 402) still get CORS headers.

### Frontend (Vite + axios)

1. **`zentro-frontend/vite.config.ts`** — **`server.proxy`**

   - Proxies paths starting with **`/api`** to **`http://127.0.0.1:8000`**.
   - Rewrites the **`Host`** header from `{host}:5173` (or whatever dev port Vite uses) to **`{host}:8000`** so **django-tenants** still sees the correct tenant host (e.g. `demo1.localhost:8000`).

2. **`zentro-frontend/src/services/BaseService.ts`** — **`getBaseUrl`**

   - **Tenant / normal API routes (development):** base URL is **`window.location.origin` + `VITE_API_PREFIX`** (e.g. `http://demo1.localhost:5173/api`). The browser calls the **same origin** as the SPA; Vite forwards to Django. This avoids cross-port CORS/PNA for most app traffic.
   - **`mainDomainRoutes` (development):** still use **`http://{VITE_DEV_DOMAIN}:{VITE_DEV_BACKEND_PORT}/api`** (typically `http://localhost:8000/api`) so **public / onboarding** flows keep **`Host: localhost:8000`** as intended, instead of the tenant subdomain.

---

## Operational notes

- After changing **Django CORS settings**, restart **`runserver`**.
- After changing **`vite.config.ts`**, restart **`npm run dev`** (Vite).
- **`vite preview`** does **not** automatically apply **`server.proxy`** from the dev server config. Preview builds that call `/api` on the preview origin need a separate proxy strategy or a production-like API URL.

---

## Files reference

| Area | File |
|------|------|
| CORS + PNA (dev) | `zentro-backend/core/settings.py` |
| CORS + PNA (dev mirror) | `zentro-backend/core/settingsprod.py` |
| Vite `/api` proxy + `Host` rewrite | `zentro-frontend/vite.config.ts` |
| API base URL logic | `zentro-frontend/src/services/BaseService.ts` |

---

## Related

- django-cors-headers: `CORS_ALLOW_PRIVATE_NETWORK` (see package docs / middleware implementation).
- Chrome: Local / Private Network Access and preflight behavior (search “Private Network Access” in Chromium documentation).
