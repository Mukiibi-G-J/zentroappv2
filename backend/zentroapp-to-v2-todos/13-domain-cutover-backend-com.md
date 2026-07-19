# 13 — Domain cutover: V2 on `zentroapp-backend.com`

**Status:** ✅ Done on this server (2026-07-19)  
**Index:** [README.md](./README.md)

## Target layout

| App | Nginx `server_name` | Upstream | SSL |
|-----|---------------------|----------|-----|
| **V2** (`zentro-appv2`) | `.zentroapp-backend.com` | `127.0.0.1:8002` | `*.zentroapp-backend.com` (wildcard exists) |
| **V1** (`zentro-app`) | `zentroapp-api.uncodedsolutions.com` | `127.0.0.1:8000` | apex-only (no `*.zentroapp-api...` yet) |

## Files

- Live: `/etc/nginx/sites-available/zentro-api-v2` (V2), `/etc/nginx/sites-available/zentro` (V1)
- Template: [`../../deploy/nginx/zentro-api.conf`](../../deploy/nginx/zentro-api.conf)
- V2 settings: `BACKEND_DOMAIN = "zentroapp-backend.com"` in `core/settingsprod.py`
- V1 settings: `BACKEND_DOMAIN = "zentroapp-api.uncodedsolutions.com"`

## DB domain rows

- V2 DB: `*.zentroapp-backend.com`
- V1 DB: `*.zentroapp-api.uncodedsolutions.com`

## Frontend / clients

| Role | Host |
|------|------|
| **App / login** | `{tenant}.zentroapp.app` (e.g. `https://primewise.zentroapp.app/login`) |
| **API** | `https://zentroapp-backend.com` / `{tenant}.zentroapp-backend.com` |

Vercel env (required):

```
NEXT_PUBLIC_APP_HOST=zentroapp.app
NEXT_PUBLIC_API_HOST=zentroapp-backend.com
NEXT_PUBLIC_API_URL=https://zentroapp-backend.com
```

Do **not** set `NEXT_PUBLIC_APP_HOST` to `zentroapp-backend.com` — that sends “Continue to sign in” to the API host (`/verify-company/` Django page) instead of Next.js `/login`.

Backend `DOMAIN` / `FRONTEND_DOMAINS` must include `zentroapp.app` so Origin `https://{tenant}.zentroapp.app` resolves the tenant for `/api/auth/token/` and `/api/auth/me/` (otherwise `"Unknown tenant"`).

Workspace gateway uses `buildTenantAppUrl(slug, '/login')` and prefers the current marketing apex (`zentroapp.app`) even if env is mis-set.

Nginx on the API host redirects `/login`, `/verify-company`, `/sign-in`, `/workspace`, `/signup` on `*.zentroapp-backend.com` → `https://{tenant}.zentroapp.app/login`.

V2 CORS must allow marketing/workspace hosts:

- `https://zentroapp.app` / `https://*.zentroapp.app`
- `https://zentroapp.uncodedsolutions.com` / `https://*.zentroapp.uncodedsolutions.com`

Company name for the pilot is **`primewise`** (not `primevisa`).

## Smoke

```bash
curl -o /dev/null -w '%{http_code}\n' https://zentroapp-backend.com/admin/login/
curl -o /dev/null -w '%{http_code}\n' https://primewise.zentroapp-backend.com/admin/login/
curl -o /dev/null -w '%{http_code}\n' https://zentroapp-api.uncodedsolutions.com/admin/login/
```
