# TMF BSS — Reverse Proxy + HTTPS

Nginx reverse proxy that fronts Odoo with HTTPS termination, gzip, caching, and WebSocket support for longpolling.

## Architecture

```
Client  --HTTPS-->  nginx (443)  --HTTP-->  Odoo (8069)
                                  --WS-->   Odoo longpolling (8072)
```

The nginx container reaches the host-running Odoo via `host-gateway` (exposed as `odoo-host` in the container).

## Quick start (local dev with self-signed cert)

```powershell
# 1. Generate a self-signed cert
./gen-selfsigned-cert.ps1

# 2. Start nginx
docker compose up -d

# 3. Visit https://localhost (accept the browser warning)
```

Odoo must already be running on the host at ports 8069 (HTTP) and 8072 (longpolling).

## Odoo config for running behind a proxy

Add to your `odoo.conf` (or pass as CLI flags):

```ini
proxy_mode = True
workers = 2       ; or more — required for longpolling to work
```

With `workers > 0`, Odoo automatically starts the longpolling worker on port 8072.

## Production (Let's Encrypt)

1. Point your real domain's DNS A record at the host's public IP
2. Edit `nginx/odoo.conf`: replace `server_name _;` with your domain
3. Uncomment the `certbot` service in `docker-compose.yml`
4. First-time cert issuance:

```bash
docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d your-domain.example.com \
  --email you@example.com --agree-tos --no-eff-email
```

5. Point `ssl_certificate` / `ssl_certificate_key` in `nginx/odoo.conf` at the Let's Encrypt paths under `/etc/letsencrypt/live/your-domain/`
6. `docker compose up -d` — certbot will auto-renew

## Security headers included

- `Strict-Transport-Security` (HSTS, 2 years)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin`
- TLS 1.2 + 1.3 only, modern cipher suite

## Firewall

In production, close ports 8069 and 8072 to external traffic — only 80/443 should be exposed.
