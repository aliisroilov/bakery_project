# Bakery ERP - Deployment & Setup Guide

## 📋 Overview

This document provides complete instructions for setting up, testing, and deploying the fixed Bakery ERP system.

---

## 🚀 Quick Start (Development)

### Prerequisites
- Python 3.12+
- PostgreSQL (production) or SQLite (development)
- Git

### Setup
```bash
# Clone the repository
cd bakery_project-main

# Install dependencies
pip install -r requirements_clean.txt

# Set up environment
cp .env.example .env  # Edit with your settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### Run Tests
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov --cov-report=html

# View coverage report
open htmlcov/index.html
```

---

## 📦 Installation

### 1. System Requirements

**Production:**
- Ubuntu 20.04+ or similar
- Python 3.12+
- PostgreSQL 13+
- Nginx
- Gunicorn
- 2GB RAM minimum

**Development:**
- Python 3.12+
- SQLite (included)

### 2. Python Dependencies

```bash
pip install -r requirements_clean.txt
```

**Key Dependencies:**
- Django 5.2.6
- psycopg2-binary (PostgreSQL adapter)
- gunicorn (WSGI server)
- whitenoise (static files)
- pytest, pytest-django (testing)

### 3. Database Setup

**Development (SQLite):**
```bash
python manage.py migrate
```

**Production (PostgreSQL):**
```bash
# Create database
createdb bakery_erp

# Update .env
DATABASE_URL=postgresql://user:pass@localhost/bakery_erp

# Run migrations
python manage.py migrate
```

### 4. Environment Configuration

Create `.env` file:
```env
SECRET_KEY=your-secret-key-here
DEBUG=False  # Set to False in production
DATABASE_URL=postgresql://user:pass@localhost/bakery_erp
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

---

## 🧪 Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest tests/ -m unit

# Integration tests only
pytest tests/ -m integration

# Skip slow tests
pytest tests/ -m "not slow"
```

### Bug Reproduction Script
```bash
# Verify bugs are fixed
python reproduce_bugs.py
```

Expected output: All checks should show ✓ PASS

---

## 🔧 Data Migration (For Existing Systems)

If upgrading from a system with the zero-payment bug:

```bash
# Backup database first!
pg_dump bakery_erp > backup_$(date +%Y%m%d).sql

# Run migration script
python migrate_fix_payments.py

# Verify results
python reproduce_bugs.py
```

The script will:
1. Find orders with zero payments
2. Recalculate shop loan balances
3. Update BakeryBalance
4. Provide detailed report

---

## 🚢 Production Deployment

### 1. Preparation

```bash
# Collect static files
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### 2. Gunicorn Setup

Create `gunicorn_config.py`:
```python
bind = "0.0.0.0:8000"
workers = 4
worker_class = "sync"
timeout = 120
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
```

Start Gunicorn:
```bash
gunicorn bakery_project.wsgi:application -c gunicorn_config.py
```

### 3. Nginx Configuration

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    client_max_body_size 10M;

    location /static/ {
        alias /path/to/bakery_project/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 4. Systemd Service

Create `/etc/systemd/system/bakery-erp.service`:
```ini
[Unit]
Description=Bakery ERP
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/path/to/bakery_project
Environment="DJANGO_SETTINGS_MODULE=bakery_project.settings"
ExecStart=/path/to/venv/bin/gunicorn bakery_project.wsgi:application -c gunicorn_config.py
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable bakery-erp
sudo systemctl start bakery-erp
sudo systemctl status bakery-erp
```

---

## 📊 Monitoring & Logging

### Check Logs
```bash
# Application logs
tail -f /var/log/gunicorn/error.log

# Django logs
python manage.py shell
>>> import logging
>>> logger = logging.getLogger('orders.utils')
```

### Key Metrics to Monitor
1. **Payment Creation**
   - Monitor for zero-amount payments
   - Check logs for `[PROCESS] Payment created`

2. **Loan Balances**
   - Verify shop.loan_balance matches calculation
   - Check for negative balances

3. **BakeryBalance**
   - Should always equal sum of all payments
   - Run reconciliation daily

### Daily Reconciliation Script
```bash
python << 'EOF'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bakery_project.settings')
django.setup()

from decimal import Decimal
from dashboard.models import Payment
from reports.models import BakeryBalance

total_payments = Payment.objects.aggregate(
    total=django.db.models.Sum("amount")
)["total"] or Decimal("0.00")

balance = BakeryBalance.get_instance()

if abs(total_payments - balance.amount) > Decimal("0.01"):
    print(f"⚠️ MISMATCH: Payments={total_payments}, Balance={balance.amount}")
else:
    print(f"✓ OK: {balance.amount}")
EOF
```

---

## 🐛 Troubleshooting

### Issue: Payments showing as $0
**Solution:**
```bash
# Check if form.save() is being called correctly
# Look for this in logs:
grep "[DELIVERY] Order" /var/log/gunicorn/error.log

# If missing, the form fix wasn't applied
# Re-apply fixes from FIXES_APPLIED.md
```

### Issue: Shop loan balances incorrect
**Solution:**
```bash
# Run recalculation for specific shop
python << 'EOF'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bakery_project.settings')
django.setup()

from orders.utils import process_order_payment
from shops.models import Shop

shop = Shop.objects.get(id=YOUR_SHOP_ID)
for order in shop.orders.filter(status__in=['Delivered', 'Partially Delivered']):
    process_order_payment(order)
EOF
```

### Issue: Tests failing
**Solution:**
```bash
# Clean test database
python manage.py flush --no-input

# Recreate migrations
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete
python manage.py makemigrations
python manage.py migrate

# Run tests again
pytest tests/ -v
```

---

## 📈 Performance Optimization

### Database Indexes
```sql
-- Add indexes for common queries
CREATE INDEX idx_order_shop_status ON orders_order(shop_id, status);
CREATE INDEX idx_payment_shop ON dashboard_payment(shop_id);
CREATE INDEX idx_payment_order ON dashboard_payment(order_id);
CREATE INDEX idx_orderitem_order ON orders_orderitem(order_id);
```

### Query Optimization
```python
# In views, use select_related and prefetch_related
orders = Order.objects.select_related('shop', 'shop__region').prefetch_related('items__product')
```

---

## 🔐 Security Checklist

- [ ] DEBUG=False in production
- [ ] SECRET_KEY is random and secure
- [ ] DATABASE_URL not in version control
- [ ] ALLOWED_HOSTS configured
- [ ] HTTPS enabled
- [ ] CSRF protection enabled (default)
- [ ] SQL injection prevention (using ORM)
- [ ] XSS prevention (template auto-escaping)
- [ ] Regular security updates

---

## 📝 Maintenance Tasks

### Daily
- Monitor error logs
- Check payment processing
- Verify loan balances

### Weekly
- Run full test suite
- Review system performance
- Check for failed transactions

### Monthly
- Database backup
- Security updates
- Performance review

---

## 🆘 Support

### Common Commands
```bash
# Check Django version
python manage.py version

# Check for migrations
python manage.py showmigrations

# Shell access
python manage.py shell

# Database shell
python manage.py dbshell
```

### Useful Queries
```python
# In Django shell (python manage.py shell)

# Get all orders with zero payments
from orders.models import Order
Order.objects.filter(status='Delivered', received_amount=0)

# Check shop loan balance consistency
from shops.models import Shop
for shop in Shop.objects.all():
    # Compare shop.loan_balance with calculated value
    print(f"{shop.name}: {shop.loan_balance}")

# View recent payments
from dashboard.models import Payment
Payment.objects.order_by('-date')[:10]
```

---

## 📚 Additional Resources

- **Bug Report:** See `BUGS_FOUND.md`
- **Fixes Applied:** See `FIXES_APPLIED.md`
- **Test Suite:** See `tests/` directory
- **Django Docs:** https://docs.djangoproject.com/
- **PostgreSQL Docs:** https://www.postgresql.org/docs/

---

## 🎯 Success Criteria

System is working correctly when:
- ✅ All 19 tests pass
- ✅ Payments created with correct amounts
- ✅ Shop loan balances accurate
- ✅ BakeryBalance matches total payments
- ✅ No errors in logs
- ✅ Stock deduction works correctly

---

**Last Updated:** 2025-11-11  
**Version:** 1.0.0 (Post-Fix)  
**Status:** Production Ready ✅
