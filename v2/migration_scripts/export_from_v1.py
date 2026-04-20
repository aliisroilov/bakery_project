#!/usr/bin/env python
"""
Export V1 bakery data to a JSON snapshot.

Run this INSIDE the V1 project directory with the V1 virtualenv active:

    cd /path/to/bakery_project   # V1 root
    source venv/bin/activate      # or bakery_env/
    python v2/migration_scripts/export_from_v1.py --out /tmp/v1_snapshot.json

The script uses V1's Django ORM (no hardcoded SQL), so schema drift is caught
at import time. Only the fields we care about are exported — password hashes
are preserved so existing users can log in unchanged.

Output JSON is consumed by ``import_to_v2.py``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _setup_django() -> None:
    """Bootstrap V1 Django. Assumes CWD is V1 project root."""
    v1_root = Path.cwd()
    if not (v1_root / "manage.py").exists():
        _die(
            "manage.py not found in current directory. "
            "Run this script from the V1 project root."
        )
    sys.path.insert(0, str(v1_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bakery_project.settings")
    import django  # noqa: E402

    django.setup()


def _json_default(value):
    """JSON encoder that handles Decimal and date/datetime from Django."""
    if isinstance(value, Decimal):
        return str(value)
    # datetime.date / datetime.datetime — isoformat is lossless
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Not JSON serialisable: {type(value).__name__}")


def export() -> dict:
    # Imports are lazy — Django must be set up first.
    from users.models import User
    from shops.models import Region, Shop
    from products.models import Product
    from orders.models import Order, OrderItem
    from dashboard.models import Payment, LoanRepayment

    data: dict = {
        "meta": {"source": "v1", "export_script_version": 1},
        "users": [],
        "regions": [],
        "shops": [],
        "products": [],
        "orders": [],
        "order_items": [],
        "payments": [],
        "loan_repayments": [],
        "ingredients": [],
        "purchases": [],
    }

    # ── Users (preserve password hash so logins keep working in V2) ──
    for u in User.objects.all().order_by("id"):
        data["users"].append(
            {
                "id": u.id,
                "username": u.username,
                "password": u.password,  # hash — NOT plain text
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "role": u.role,
                "is_active": u.is_active,
                "is_staff": u.is_staff,
                "is_superuser": u.is_superuser,
                "date_joined": u.date_joined,
                "last_login": u.last_login,
            }
        )

    # ── Regions ──
    for r in Region.objects.all().order_by("id"):
        data["regions"].append({"id": r.id, "name": r.name})

    # ── Shops ──
    for s in Shop.objects.all().order_by("id"):
        data["shops"].append(
            {
                "id": s.id,
                "name": s.name,
                "owner_name": s.owner_name or "",
                "phone": s.phone or "",
                "address": s.address or "",
                "region_id": s.region_id,
                "loan_balance": s.loan_balance,  # V1: single currency (UZS)
            }
        )

    # ── Products ──
    for p in Product.objects.all().order_by("id"):
        data["products"].append(
            {
                "id": p.id,
                "name": p.name,
                "description": p.description or "",
                "is_active": p.is_active,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            }
        )

    # ── Orders + OrderItems ──
    for o in Order.objects.all().order_by("id"):
        data["orders"].append(
            {
                "id": o.id,
                "shop_id": o.shop_id,
                "order_date": o.order_date,
                "created_at": o.created_at,
                "status": o.status,  # Pending / Partially Delivered / Delivered
                "received_amount": o.received_amount,
            }
        )
    for it in OrderItem.objects.all().order_by("id"):
        data["order_items"].append(
            {
                "id": it.id,
                "order_id": it.order_id,
                "product_id": it.product_id,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "delivered_quantity": it.delivered_quantity,
            }
        )

    # ── Payments + LoanRepayments ──
    for p in Payment.objects.all().order_by("id"):
        data["payments"].append(
            {
                "id": p.id,
                "order_id": p.order_id,
                "shop_id": p.shop_id,
                "amount": p.amount,
                "payment_type": p.payment_type,
                "collected_by_id": p.collected_by_id,
                "notes": p.notes or "",
                "date": p.date,
            }
        )
    for r in LoanRepayment.objects.all().order_by("id"):
        data["loan_repayments"].append(
            {
                "id": r.id,
                "shop_id": r.shop_id,
                "amount": r.amount,
                "date": r.date,
            }
        )

    # ── Ingredients + Purchases (optional — only if V1 has them populated) ──
    try:
        from inventory.models import Ingredient, Purchase, Unit  # noqa: E402
    except ImportError:
        pass
    else:
        data["units"] = [
            {"id": u.id, "name": u.name, "short": u.short or ""}
            for u in Unit.objects.all().order_by("id")
        ]
        for ing in Ingredient.objects.all().order_by("id"):
            data["ingredients"].append(
                {
                    "id": ing.id,
                    "name": ing.name,
                    "quantity": ing.quantity,
                    "unit_id": ing.unit_id,
                    "low_stock_threshold": ing.low_stock_threshold,
                }
            )
        for pur in Purchase.objects.all().order_by("id"):
            data["purchases"].append(
                {
                    "id": pur.id,
                    "ingredient_id": pur.ingredient_id,
                    "quantity": pur.quantity,
                    "price": pur.price,
                    "date": pur.date,
                    "note": pur.note or "",
                }
            )

    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="v1_snapshot.json",
        help="Output JSON path (default: ./v1_snapshot.json)",
    )
    args = parser.parse_args()

    _setup_django()
    data = export()

    out_path = Path(args.out)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=_json_default)

    # Short summary
    counts = {k: len(v) for k, v in data.items() if isinstance(v, list)}
    print(f"✓ Exported V1 snapshot → {out_path.resolve()}")
    for key, n in counts.items():
        print(f"  {key:20s} {n:>6d}")


if __name__ == "__main__":
    main()
