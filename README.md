# Sutli-Non Bakery ERP

Bakery management system for tracking orders, deliveries, inventory, payments, and employee salary. Live at **sutli-non.uz**.

## System Versions

| Version | Stack | Status |
|---------|-------|--------|
| **V1** | Django 5 + server-rendered templates + PostgreSQL | Production |
| **V2** | Django REST Framework + React 18 + PostgreSQL | Beta at v2.sutli-non.uz |

---

## Modules

| App | Purpose |
|-----|---------|
| `users` | User accounts and roles (manager / driver / viewer / baker) |
| `products` | Bakery products and ingredient recipes |
| `shops` | Customer shops and loan (nasiya) balances |
| `orders` | Daily orders, delivery confirmation, payment collection |
| `dashboard` | Financial summary, loan repayments, today's income |
| `inventory` | Raw materials, production batches, stock levels |
| `reports` | Sales, purchases, and financial reports |
| `salary` | Employee salary tracking |

---

## Local Setup (V1 — Django)

### Requirements
- Python 3.12+
- PostgreSQL 14+

### Steps

```bash
# 1. Clone and enter the project
git clone https://github.com/aliisroilov/bakery_project.git
cd bakery_project

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env with your SECRET_KEY and database credentials

# 5. Create the PostgreSQL database
createdb bakery_db

# 6. Run migrations
python manage.py migrate

# 7. Create a superuser (admin)
python manage.py createsuperuser

# 8. Collect static files
python manage.py collectstatic --noinput

# 9. Start the development server
python manage.py runserver
```

Open http://127.0.0.1:8000 — log in with the superuser credentials.

---

## Environment Variables

Copy `.env.example` to `.env`. Required variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key (keep this private) | `django-abc123...` |
| `DEBUG` | `True` for dev, `False` for production | `False` |
| `POSTGRES_DB` | Database name | `bakery_db` |
| `POSTGRES_USER` | Database user | `bakuser` |
| `POSTGRES_PASSWORD` | Database password | `strongpassword` |
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | Database port | `5432` |

---

## User Roles

| Role | Access |
|------|--------|
| `manager` | Full access — orders, payments, reports, users, settings |
| `driver` | Can view and confirm deliveries |
| `viewer` | Read-only access to orders and dashboard |
| `nonvoy` (baker) | Inventory and production tracking |

---

## Running Tests

```bash
pip install pytest pytest-django pytest-cov
pytest
```

Coverage report:
```bash
pytest --cov=orders --cov=dashboard --cov=inventory --cov=reports
```

---

## Production Deployment

See [DEPLOY.md](DEPLOY.md) for full instructions for deploying on Render.com or a VPS.

Quick summary:
- The `Procfile` handles Heroku/Render deployments.
- The `render.yaml` file defines Render.com services.
- Static files are served via WhiteNoise.
- Set `DEBUG=False` and all required env vars on the server.

---

## V2 Setup (React + DRF)

```bash
cd v2

# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in values
python manage.py migrate
python manage.py runserver 8001

# Frontend (separate terminal)
cd ../frontend
npm install
npm run dev
```

See `v2/DEPLOY.md` for production deployment of V2.

---

## Known Issues & Audit

- [BUGS_FOUND.md](BUGS_FOUND.md) — List of identified bugs by severity
- [FIXES_APPLIED.md](FIXES_APPLIED.md) — Bugs that have been fixed with code details
- [PROJECT_AUDIT_REPORT.md](PROJECT_AUDIT_REPORT.md) — Full project audit (security, architecture, code quality)

---

## Tech Stack

**V1**
- Python 3.12, Django 5.2
- PostgreSQL (production), SQLite (local dev)
- Tailwind CSS (CDN), Django Templates
- Gunicorn, WhiteNoise
- pytest, pytest-django

**V2**
- Django REST Framework, SimpleJWT
- React 18, Vite, TypeScript, shadcn/ui, Tailwind CSS
- Celery + Redis (background tasks)
- Docker Compose (local dev)
