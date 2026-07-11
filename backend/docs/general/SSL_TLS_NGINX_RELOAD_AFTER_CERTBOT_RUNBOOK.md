# SSL/TLS: Certbot renewed the certificate but browsers still show `ERR_CERT_DATE_INVALID`

This runbook documents an incident on production where Let’s Encrypt had already renewed files under `/etc/letsencrypt/live/`, but **nginx continued to serve the previous certificate** until nginx was reloaded. It also records the **permanent fix** (deploy hook) so future renewals reload nginx automatically.

**Related:** High-level wildcard setup (Cloudflare DNS-01, API token, first issuance) lives in the repo root [`hosting.md`](../../../hosting.md) (not duplicated here in full).

---

## Scope

- **Domain / cert:** `zentroapp-backend.com` and `*.zentroapp-backend.com` (one wildcard certificate).
- **Stack:** nginx terminates TLS on the host (no Docker for TLS in this setup); Gunicorn/Django behind `proxy_pass`.
- **Issuance / renewal:** `certbot` with **DNS-01** via **Cloudflare** (`authenticator = dns-cloudflare`, credentials in `/etc/letsencrypt/cloudflare.ini`).
- **Nginx config:** Certificate paths point at the `live` symlinks, for example:
  - `ssl_certificate /etc/letsencrypt/live/zentroapp-backend.com/fullchain.pem`
  - `ssl_certificate_key /etc/letsencrypt/live/zentroapp-backend.com/privkey.pem`

Tenant hostnames such as `primewise.zentroapp-backend.com` use the **wildcard** entry on that same certificate; they do not need separate certificates.

---

## Symptoms

- Browsers show **Your connection is not private** with **`net::ERR_CERT_DATE_INVALID`** (or the padlock shows an expired chain).
- Inspecting the certificate in the browser matches an **old** validity window (for example, issued January, expiring April).
- On the server, **`sudo certbot certificates`** may still report a **newer** expiry date, and `openssl x509 -in /etc/letsencrypt/live/zentroapp-backend.com/fullchain.pem -noout -dates` may show **valid** dates.

So: **on-disk cert is fine; what clients receive is wrong.**

---

## Root cause

1. **Renewal method:** For this deployment, certificates are typically obtained/renewed with `certbot certonly` (DNS plugin). That **updates files** under `/etc/letsencrypt/archive/` and the `live` symlinks; it does **not** restart or reload nginx by itself unless configured to do so.
2. **nginx behavior:** OpenSSL loads the certificate and key when nginx **starts** or **reloads**. Until then, the running worker processes keep using the **previously loaded** certificate material.
3. **Result:** After a successful renewal, **clients still see the old expiry** until nginx reloads (or restarts).

This is easy to miss because `certbot renew` exits successfully and `certbot certificates` looks healthy.

---

## Verification (compare disk vs what the world sees)

On the server, check the file on disk:

```bash
sudo openssl x509 -in /etc/letsencrypt/live/zentroapp-backend.com/fullchain.pem -noout -dates -subject
```

Check what is actually served on HTTPS (pick any tenant hostname or the apex):

```bash
echo | openssl s_client -connect primewise.zentroapp-backend.com:443 -servername primewise.zentroapp-backend.com 2>/dev/null \
  | openssl x509 -noout -dates -subject
```

If the **two `notAfter` dates differ**, nginx is still serving an older cert from memory.

---

## Immediate fix (restore valid TLS now)

Reload nginx so it picks up the current `fullchain.pem` / `privkey.pem`:

```bash
sudo systemctl reload nginx
```

Then re-run the `openssl s_client` check; it should match the on-disk certificate.

A full restart also works but is heavier:

```bash
sudo systemctl restart nginx
```

---

## Permanent fix (after each successful renewal)

Ensure Certbot runs a **deploy hook** that reloads nginx when a certificate is actually renewed.

### Option A — renewal config (this deployment)

The renewal profile is:

`/etc/letsencrypt/renewal/zentroapp-backend.com.conf`

Under `[renewalparams]`, include:

```ini
deploy_hook = /usr/bin/systemctl reload nginx
```

After editing, validate with:

```bash
sudo certbot renew --dry-run
```

### Option B — one-off when obtaining a cert

You can set a deploy hook when requesting a certificate (syntax may vary slightly by Certbot version); the important part is that **something** reloads nginx after new files are written.

---

## Ongoing operations

| Task | Command / note |
|------|----------------|
| List certs and expiry | `sudo certbot certificates` |
| Renewal dry run | `sudo certbot renew --dry-run` |
| Scheduled renewals | `certbot.timer` (systemd) runs periodic renewal on Ubuntu/Debian installs |
| Logs | `/var/log/letsencrypt/letsencrypt.log` |
| Wildcard / DNS issues | See [`hosting.md`](../../../hosting.md) (Cloudflare token, `_acme-challenge`, troubleshooting) |

---

## Summary

| Item | Detail |
|------|--------|
| **Problem** | Renewed PEM files on disk; nginx served stale TLS material until reload. |
| **Quick fix** | `sudo systemctl reload nginx` |
| **Prevention** | `deploy_hook` → `systemctl reload nginx` in the Certbot renewal configuration |

---

**Category:** General / production infrastructure  
**Status:** Active
