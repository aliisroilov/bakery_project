# V2 Deployment Guide — parallel to V1

**Goal:** run V2 side-by-side with the live V1 so clients can try the beta
without losing their real workflow. V1 stays the primary system; V2 gets a
**snapshot copy** of V1 data in its own database. Changes made in V2 do **not**
propagate back to V1.

```
┌──────────────────────────┐      ┌────────────────────────────┐
│  sutli-non.uz  (V1)      │      │  v2.sutli-non.uz  (V2)     │
│  Django templates        │      │  React SPA (dist/)         │
│  PostgreSQL: bakery_db   │      │  Django API on :8001       │
│                          │      │  PostgreSQL: bakery_v2     │
│  ↑ "Try V2 Beta" banner  │  ──▶ │  (separate DB)             │
└──────────────────────────┘      └────────────────────────────┘
        same server, two Nginx vhosts, two systemd services
```

After V2 passes acceptance testing, we flip `sutli-non.uz` to V2 and retire V1.
Until then V1 is the source of truth.

---

## 0. Prerequisites on the server

V1 is already running. This guide only describes the **additional** pieces V2 needs.

- PostgreSQL ≥ 13 (same instance V1 uses is fine)
- Python ≥ 3.11 (V2 targets 3.12)
- Node.js ≥ 20 + npm (only for the frontend build; can be uninstalled after)
- Nginx (same instance V1 uses)
- A DNS A record for `v2.sutli-non.uz` pointing to the server
- TLS certificate for `v2.sutli-non.uz` (use certbot — see step 6)

---

## 1. Pull the code

```bash
cd /opt   # or wherever V1 lives — adjust paths below to match
sudo mkdir -p bakery_v2
sudo chown $USER:$USER bakery_v2
cd bakery_v2
git clone https://github.com/<your-org>/bakery_project.git .
cd v2   # everything below assumes CWD is /opt/bakery_v2/v2
```

From here `$V2` means `/opt/bakery_v2/v2` and `$V1` means the existing V1 root.

---

## 2. Create the V2 database (empty for now)

```bash
sudo -u postgres psql <<SQL
CREATE USER bakery_v2 WITH PASSWORD 'choose-a-strong-password';
CREATE DATABASE bakery_v2 OWNER bakery_v2;
GRANT ALL PRIVILEGES ON DATABASE bakery_v2 TO bakery_v2;
SQL
```

---

## 3. Backend — install, configure, migrate

```bash
cd $V2/backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.production.example .env
# Edit .env:
#   SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(50))">
#   DATABASE_URL=postgres://bakery_v2:<password>@localhost:5432/bakery_v2
#   ALLOWED_HOSTS=v2.sutli-non.uz,www.v2.sutli-non.uz
#   CORS_ALLOWED_ORIGINS=https://v2.sutli-non.uz

python manage.py migrate
python manage.py collectstatic --no-input
python manage.py check --deploy   # should be clean; warnings about SECURE_SSL_REDIRECT etc. are OK if Nginx terminates TLS
```

---

## 4. Seed V2 with a snapshot of V1's data

**This is the "clone real data" step.** Run once; V2 then diverges.

Two approaches exist — pick the one that matches V1's database backend:

### 4.a  If V1 is on PostgreSQL (production) — use the JSON snapshot scripts

```bash
# Export from V1 (uses V1's Django ORM — needs V1 venv active)
cd $V1
source venv/bin/activate   # or bakery_env/
python v2/migration_scripts/export_from_v1.py --out /tmp/v1_snapshot.json
deactivate

# Import into V2
cd $V2/backend
source venv/bin/activate
python ../migration_scripts/import_to_v2.py /tmp/v1_snapshot.json
```

### 4.b  If V1 is on SQLite (dev/small deployments) — use the management command

The management command reads V1's SQLite file directly and covers more tables
(recipes, bakery stock, inventory revisions, expense categories, bakery balance):

```bash
cd $V2/backend
source venv/bin/activate
python manage.py migrate_from_v1 --source /path/to/v1/db.sqlite3 --wipe
```


The importer is wrapped in a transaction — if anything fails, the V2 DB is
left untouched and you can re-run after fixing. Expected output lists counts
(users, shops, orders, …).

**What the snapshot preserves:**
- All users with their password hashes (logins keep working)
- Regions, shops, products, orders, order items
- Payments + loan repayments (merged into V2's unified Payment model)
- Ingredients, purchases, units (if V1 had the inventory tables populated)
- V1 primary keys — so `/orders/123` still refers to the same order in V2

**What the snapshot does NOT cover:**
- Per-shop custom product prices (V1 didn't have this — set them in V2 UI)
- Kassa accounts (V2 seeds `Seyf` + `Rizoxon` automatically; all migrated
  payments are attributed to `Seyf`)
- Recipes (V2-only feature; fill in via the Products page)
- Activity logs (V2 starts a clean audit trail)

**Re-running the importer** updates users/shops/products/regions in place,
but appends new Payment rows — so for a full re-import, drop and recreate
the V2 database first:

```bash
sudo -u postgres psql -c "DROP DATABASE bakery_v2;"
sudo -u postgres psql -c "CREATE DATABASE bakery_v2 OWNER bakery_v2;"
python manage.py migrate
python ../migration_scripts/import_to_v2.py /tmp/v1_snapshot.json
```

---

## 5. Frontend — build the React SPA

```bash
cd $V2/frontend
npm ci
cp .env.production.example .env.production
# The default VITE_API_BASE=/api/v1 works for the same-origin Nginx setup.
npm run build
# → produces $V2/frontend/dist/ — static files Nginx will serve
```

---

## 6. Nginx — new vhost for v2.sutli-non.uz

Create `/etc/nginx/sites-available/v2.sutli-non.uz`:

```nginx
# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name v2.sutli-non.uz www.v2.sutli-non.uz;
    return 301 https://v2.sutli-non.uz$request_uri;
}

server {
    listen 443 ssl http2;
    server_name v2.sutli-non.uz;

    # TLS — fill in after running certbot (step 7)
    ssl_certificate     /etc/letsencrypt/live/v2.sutli-non.uz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/v2.sutli-non.uz/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 10M;

    # Django API — proxied to gunicorn on :8001
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Django static (admin, DRF browsable API) — rarely needed in prod
    location /static/ {
        alias /opt/bakery_v2/v2/backend/staticfiles/;
        expires 30d;
    }

    # Django admin (for superuser bootstrap only — restrict in firewall if possible)
    location /admin/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # React SPA — serve dist/ and fall back to index.html for client-side routes
    root /opt/bakery_v2/v2/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache built assets aggressively (Vite adds content hash to filenames)
    location /assets/ {
        expires 1y;
        access_log off;
        add_header Cache-Control "public, immutable";
    }
}
```

Enable and test:

```bash
sudo ln -s /etc/nginx/sites-available/v2.sutli-non.uz /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 7. TLS with certbot

```bash
sudo certbot --nginx -d v2.sutli-non.uz -d www.v2.sutli-non.uz
```

---

## 8. systemd service for the V2 backend

Create `/etc/systemd/system/bakery-v2-backend.service`:

```ini
[Unit]
Description=Bakery V2 Django API (gunicorn)
After=network.target postgresql.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/bakery_v2/v2/backend
EnvironmentFile=/opt/bakery_v2/v2/backend/.env
ExecStart=/opt/bakery_v2/v2/backend/venv/bin/gunicorn config.wsgi:application \
    --bind 127.0.0.1:8001 \
    --workers 3 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bakery-v2-backend
sudo systemctl status bakery-v2-backend
```

Logs: `sudo journalctl -u bakery-v2-backend -f`

---

## 9. Smoke test

```bash
# API health (should return an auth-required 401, which proves routing works)
curl -i https://v2.sutli-non.uz/api/v1/users/

# SPA loads
curl -I https://v2.sutli-non.uz/
# → HTTP/2 200, content-type: text/html
```

Then log in via the browser with an existing V1 username/password — it should
work because we preserved password hashes.

---

## 10. Enable the "Try V2 Beta" banner on V1

Nothing to do — the V1 `templates/base.html` already has a dismissable banner
pointing at `https://v2.sutli-non.uz`. It shows for authenticated users only.
If the domain is different, edit the link in `templates/base.html` (search for
`v2-beta-banner`) and restart V1.

---

## 11. Ongoing operations

### Deploying V2 changes
```bash
cd /opt/bakery_v2
git pull
# Backend
cd v2/backend
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --no-input
sudo systemctl restart bakery-v2-backend
# Frontend
cd ../frontend
npm ci
npm run build
# Nginx serves dist/ directly — no reload needed
```

### Re-syncing from V1 (rare, destructive)
Only if you want to throw away V2 changes and reseed from current V1 data:

```bash
sudo systemctl stop bakery-v2-backend
sudo -u postgres psql -c "DROP DATABASE bakery_v2;"
sudo -u postgres psql -c "CREATE DATABASE bakery_v2 OWNER bakery_v2;"
# Export + import (same as step 4)
cd $V1 && source venv/bin/activate && python v2/migration_scripts/export_from_v1.py --out /tmp/v1_snapshot.json
cd $V2/backend && source venv/bin/activate && python manage.py migrate
python ../migration_scripts/import_to_v2.py /tmp/v1_snapshot.json
sudo systemctl start bakery-v2-backend
```

### The eventual cutover (V2 becomes primary)
When V2 is approved:

1. Re-run the snapshot export/import one last time to catch recent V1 writes.
2. Point `sutli-non.uz` Nginx vhost at the V2 SPA/backend (same config as
   v2.sutli-non.uz above, but with `server_name sutli-non.uz`).
3. Remove the beta banner from V1 (or leave V1 off entirely —
   `sudo systemctl stop bakery-erp`).
4. Keep the V1 database as an archive for 90 days before dropping.

---

## Troubleshooting

**Gunicorn fails to start** — check `journalctl -u bakery-v2-backend -n 50`.
Common causes: missing `.env`, wrong `DATABASE_URL`, `SECRET_KEY` unset.

**API returns 502 Bad Gateway** — gunicorn isn't bound to 127.0.0.1:8001.
Check the service is running and listening: `ss -ltnp | grep 8001`.

**SPA loads but every API call 404s** — verify `VITE_API_BASE` in
`.env.production` matches Nginx's `location /api/` prefix, and that you
rebuilt (`npm run build`) after changing it.

**Import script says "orphan — skip" for ingredients** — V1 had Units that
were deleted before export. Safe to ignore or clean up V1 first.

**Users can't log in after import** — check
`SELECT username, length(password) FROM users_user LIMIT 5;` in V2 — password
column should contain hashes starting with `pbkdf2_sha256$…`. If empty, the
exporter didn't have access to the field (permissions issue on V1).
