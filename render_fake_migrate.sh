#!/usr/bin/env bash
echo "⚙️ Starting safe fake migration fix..."

# 1. Apply only migrations that already exist in DB schema
python manage.py migrate dashboard 0001 --fake

# 2. Apply all remaining migrations but skip any already present columns/tables
python manage.py migrate --fake-initial

echo "✅ Fake migration fix complete!"
