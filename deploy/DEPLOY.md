# Zentro V2 Backend — DigitalOcean Deploy

Same pattern as Medi-Link. Shared droplet with MedLink.

**Server:** `64.226.98.20` (Frankfurt)  
**API domain:** `zentroapp-api.uncodedsolutions.com`  
**Tenant API subdomains:** `*.zentroapp-api.uncodedsolutions.com`  
  e.g. `ekk.zentroapp-api.uncodedsolutions.com`  
**Frontend:** `zentroapp.uncodedsolutions.com`  
**Tenant frontend subdomains:** `*.zentroapp.uncodedsolutions.com`  
  e.g. `ekk.zentroapp.uncodedsolutions.com`

**Repo:** `git@github.com:Mukiibi-G-J/zentroappv2.git`  
**App path on server:** `/root/projects/zentro-appv2`  
**Layout:** `backend/` (Django) + `deploy/` (this folder) + `frontend/` (not deployed by this workflow)

> **Coexists with** `/root/projects/zentro-app` (V1). Do not overwrite that tree. V2 uses different supervisor program names and ports.

---

## Port map (shared with Medi-Link + Zentro V1)

| Port | Owner |
|------|-------|
| 8000 | Zentro V1 gunicorn |
| 8001 | MedLink gunicorn |
| 8002 | Zentro V2 gunicorn |
| 5555 | Zentro V1 Flower (`127.0.0.1` only) |
| 5556 | MedLink Flower |
| 5557 | Zentro V2 Flower |
| 80/443 | Nginx |
| 5432 | PostgreSQL |
| 6379 | Redis (V1 DB 0, MedLink 2/3, V2 DB 4) |

---

## Phase 0 — DNS

At your DNS provider for `uncodedsolutions.com`:

| Type | Name | Value | Purpose |
|------|------|-------|---------|
| **A** | `zentroapp-api` | `64.226.98.20` | API apex |
| **A** | `*.zentroapp-api` | `64.226.98.20` | Tenant API subdomains |
| **A** / **CNAME** | `zentroapp` | (frontend host / Vercel / etc.) | Frontend apex |
| **A** / **CNAME** | `*.zentroapp` | (frontend host / Vercel / etc.) | Tenant frontend subdomains |

Live V1 keeps `zentroapp-backend.com` / `zentroapp.app` — do not change those records.
---

## Phase 1 — Server prep

```bash
mkdir -p /root/projects/zentro-appv2/logs
```

---

## Phase 2 — Clone & virtualenv (uv)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

cd /root/projects
git clone git@github.com:Mukiibi-G-J/zentroappv2.git zentro-appv2
cd zentro-appv2

uv python install 3.12
uv python -m venv env
source env/bin/activate
uv pip install -r backend/requirements.txt
```

---

## Phase 3 — Database

Separate DB from V1 (`zentroapp_db`):

```bash
sudo -u postgres psql -c "CREATE DATABASE zentroapp_v2_db OWNER jom;"
```

---

## Phase 4 — Environment

```bash
cd /root/projects/zentro-appv2
cp deploy/env.production.example backend/.env
nano backend/.env   # set DJANGO_SECRET_KEY, DB_*_PROD, AWS, Stripe, etc.
```

`core.settingsprod` expects:

```dotenv
ENVIRONMENT=production
DJANGO_SECRET_KEY=...
DB_NAME_PROD=zentroapp_v2_db
DB_USER_PROD=jom
DB_PASSWORD_PROD=...
DB_HOST_PROD=127.0.0.1
REDIS_URL=redis://127.0.0.1:6379/4
```

---

## Phase 5 — Migrations & static

```bash
cd /root/projects/zentro-appv2/backend
source ../env/bin/activate
export DJANGO_SETTINGS_MODULE=core.settingsprod

python manage.py migrate_schemas --shared
python manage.py migrate_schemas
python manage.py collectstatic --noinput
```

---

## Phase 6 — Supervisor

```bash
cp /root/projects/zentro-appv2/deploy/supervisor/*.conf /etc/supervisor/conf.d/

# Edit flower auth before starting:
nano /etc/supervisor/conf.d/zentrov2-flower.conf

supervisorctl reread
supervisorctl update
supervisorctl status
```

| Service | Bind |
|---------|------|
| Gunicorn (`zentrov2`) | `127.0.0.1:8002` |
| Flower (`zentrov2-flower`) | `127.0.0.1:5557` |

---

## Phase 7 — Nginx

```bash
cp /root/projects/zentro-appv2/deploy/nginx/zentro-api.conf /etc/nginx/sites-available/zentro-api-v2
ln -sf /etc/nginx/sites-available/zentro-api-v2 /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

Keep V1’s existing nginx site untouched. Point V2 DNS (or a temporary host) at this new vhost when ready.

---

## Phase 8 — SSL

```bash
certbot certonly --manual --preferred-challenges dns \
  -d zentroapp-api.uncodedsolutions.com \
  -d '*.zentroapp-api.uncodedsolutions.com'
```

Then:

```bash
nginx -t && systemctl reload nginx
```

---

## Phase 9 — Verify

```bash
curl -sI https://zentroapp-api.uncodedsolutions.com/admin/login/
curl -sI https://ekk.zentroapp-api.uncodedsolutions.com/admin/login/

supervisorctl status zentrov2 zentrov2-celery zentrov2-celery-beat
tail -f /root/projects/zentro-appv2/logs/gunicorn.err.log
```

---

## Routine deploy (manual)

```bash
cd /root/projects/zentro-appv2
git pull origin main
source env/bin/activate
uv pip install -r backend/requirements.txt

cd backend
export DJANGO_SETTINGS_MODULE=core.settingsprod
python manage.py migrate_schemas --shared
python manage.py migrate_schemas
python manage.py collectstatic --noinput

supervisorctl restart zentrov2 zentrov2-celery zentrov2-celery-beat
```

Automated deploy: push to `main` (after CI passes) — see **GitHub Actions** below.

---

## GitHub Actions (automated deploy)

Workflow: `.github/workflows/django.yml`

| Job | When it runs |
|-----|----------------|
| `test` | Every PR + push to `main` (paths under `backend/**` / `deploy/**`) |
| `lint` | Every PR + push to `main` |
| `deploy` | Push to `main` only, after `test` + `lint` pass |

### 1) One-time server: allow GitHub to pull code

On the droplet (SSH deploy key recommended):

```bash
ssh-keygen -t ed25519 -C "zentro-deploy" -f ~/.ssh/zentro_deploy -N ""
cat ~/.ssh/zentro_deploy.pub
```

Add the public key in GitHub → **zentroappv2** → **Settings** → **Deploy keys** → **Add deploy key** (read-only is enough).

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
  IdentityFile ~/.ssh/zentro_deploy
  IdentitiesOnly yes
EOF

cd /root/projects/zentro-appv2
git remote -v   # should be git@github.com:Mukiibi-G-J/zentroappv2.git
git pull origin main
```

### 2) One-time: SSH key for GitHub Actions → droplet

On your **local machine**:

```bash
ssh-keygen -t ed25519 -C "github-actions-zentro" -f ~/.ssh/github_actions_zentro -N ""
```

On the **droplet**, add the **public** key:

```bash
cat >> ~/.ssh/authorized_keys <<'EOF'
<paste github_actions_zentro.pub contents here>
EOF
```

You can reuse the same Actions key already used for Medi-Link if that key can SSH as `root` to this droplet.

### 3) Add GitHub secrets

Repo: **zentroappv2** → **Settings** → **Secrets and variables** → **Actions**

The deploy job uses `environment: production`. Put secrets as **repository** secrets and/or under the **production** environment.

| Secret | Value |
|--------|-------|
| `DO_HOST` | `64.226.98.20` |
| `DO_USER` | `root` |
| `DO_SSH_KEY` | Full **private** key contents (`-----BEGIN...` through `-----END...`) |

Windows copy:

```powershell
Get-Content ~\.ssh\github_actions_zentro
```

### 4) Optional: production environment approvals

GitHub → **Settings** → **Environments** → **New environment** → `production`.

### 5) How deploy runs

1. Push changes under `backend/**` or `deploy/**` to `main`
2. `test` and `lint` run
3. If both pass, `deploy` SSHs to the droplet and runs:
   - `git fetch` + `git reset --hard origin/main`
   - `uv pip install -r backend/requirements.txt`
   - `migrate_schemas --shared` + `migrate_schemas`
   - `collectstatic`
   - `supervisorctl restart zentrov2 zentrov2-celery zentrov2-celery-beat`
4. Health check: `Host: zentroapp-api.uncodedsolutions.com` → `http://127.0.0.1:8002/admin/login/`

Manual run: **Actions** → **Backend CI/CD** → **Run workflow**.
