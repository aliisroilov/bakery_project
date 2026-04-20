# Bakery v2

Rewrite of the sutli-non.uz bakery management system.

- **Backend**: Django 5.2 + DRF + SimpleJWT + PostgreSQL + Celery + Redis
- **Frontend**: React 18 + Vite + TypeScript + TailwindCSS + shadcn/ui + TanStack Query
- **Auth**: JWT (SimpleJWT)
- **Currencies**: UZS + USD tracked separately (never summed)
- **No Django admin** — everything via React UI

## Directory

```
v2/
├── backend/             Django + DRF API server
├── frontend/            React SPA
├── migration_scripts/   v1 → v2 data migration
├── docs/                Architecture + feature docs
├── docker-compose.yml   Local Postgres + Redis
└── README.md
```

## Quick start

```bash
# Local dev
docker compose up -d            # Postgres + Redis
cd backend && ./dev.sh          # Django at :8000
cd frontend && npm run dev      # Vite at :5173
```

## Migration from v1

v2 runs on a separate database. The migration script reads v1 production DB
and writes to v2 schema. No v1 data is modified. See `migration_scripts/README.md`.
