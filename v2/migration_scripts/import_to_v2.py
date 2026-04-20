#!/usr/bin/env python
"""
Import a V1 snapshot (produced by ``export_from_v1.py``) into V2.

Run INSIDE the V2 backend directory with V2's virtualenv active:

    cd /path/to/bakery_project/v2/backend
    source venv/bin/activate
    python ../migration_scripts/import_to_v2.py /tmp/v1_snapshot.json

Behaviour:
- Idempotent for users/regions/shops/products (uses username / unique name as the
  natural key), but orders/payments/purchases are append-only — running twice
  will duplicate them. Drop & recreate the V2 DB if you need a clean re-import.
- Wrapped in a single transaction — either the whole snapshot loads or nothing.
- Preserves V1 IDs where possible so bookmarked URLs (e.g. /orders/123) stay
  stable for users transitioning to V2.
- Creates the two seed KassaAccounts (Seyf, Rizoxon) if missing, and routes
  all migrated payments through Seyf by default.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path


# V1 → V2 order-status mapping
STATUS_MAP = {
    "Pending": "pending",
    "Partially Delivered": "partial",
    "Delivered": "delivered",
}

# V1 → V2 payment-type mapping
PAYMENT_TYPE_MAP = {
    "collection": "collection",
    "repayment": "loan_repayment",
    "other": "other",
}


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _setup_django() -> None:
    """Bootstrap V2 Django. Assumes CWD is /v2/backend."""
    here = Path.cwd()
    if not (here / "manage.py").exists() or not (here / "config" / "settings.py").exists():
        _die(
            "Run from V2 backend directory "
            "(must contain manage.py and config/settings.py)."
        )
    sys.path.insert(0, str(here))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django  # noqa: E402

    django.setup()


def _parse_dt(value):
    """Parse an ISO-format datetime/date string from JSON back into a Python object."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value
    # Django's DateTimeField can accept ISO strings directly, but we normalise anyway.
    try:
        # datetime with tz
        return datetime.fromisoformat(value)
    except ValueError:
        # plain date
        return date.fromisoformat(value)


def _dec(value):
    return Decimal(str(value)) if value is not None else Decimal("0")


def _import(data: dict) -> dict[str, int]:
    """Translate V1 rows into V2 rows. Returns counts per entity."""
    from django.db import transaction
    from django.utils import timezone

    from apps.finance.models import (
        KassaAccount,
        Payment as V2Payment,
        PaymentType as V2PaymentType,
    )
    from apps.inventory.models import Ingredient as V2Ingredient, Purchase as V2Purchase, Unit as V2Unit
    from apps.orders.models import (
        Order as V2Order,
        OrderItem as V2OrderItem,
        OrderStatus as V2OrderStatus,
    )
    from apps.products.models import Product as V2Product
    from apps.shops.models import Region as V2Region, Shop as V2Shop
    from apps.users.models import User as V2User

    counts: dict[str, int] = {}

    with transaction.atomic():
        # ── 1. Seed KassaAccounts ──
        seyf, _ = KassaAccount.objects.get_or_create(
            slug=KassaAccount.SEYF,
            defaults={"name": "Seyf", "description": "Asosiy kassa"},
        )
        KassaAccount.objects.get_or_create(
            slug=KassaAccount.RIZOXON,
            defaults={"name": "Rizoxon", "description": "Yordamchi kassa"},
        )

        # ── 2. Users ──
        n = 0
        for u in data.get("users", []):
            obj, created = V2User.objects.update_or_create(
                username=u["username"],
                defaults={
                    "password": u["password"],  # already hashed — keeps login working
                    "email": u.get("email", "") or "",
                    "first_name": u.get("first_name", "") or "",
                    "last_name": u.get("last_name", "") or "",
                    "full_name": (
                        f"{u.get('first_name', '') or ''} {u.get('last_name', '') or ''}"
                    ).strip(),
                    "role": u.get("role") or "viewer",
                    "is_active": bool(u.get("is_active", True)),
                    "is_staff": bool(u.get("is_staff", False)),
                    "is_superuser": bool(u.get("is_superuser", False)),
                    "date_joined": _parse_dt(u.get("date_joined")) or timezone.now(),
                    "last_login": _parse_dt(u.get("last_login")),
                },
            )
            # We do NOT force V2 user IDs to match V1 — V2 User model has
            # different schema and FK reassignment is done via username lookup below.
            _ = created
            n += 1
        counts["users"] = n

        # Build username → v2_user_id map for FK remapping.
        # V1 payments have collected_by_id pointing to V1 users — we look them up
        # by (V1 id → V1 username → V2 user.pk).
        v1_id_to_username: dict[int, str] = {u["id"]: u["username"] for u in data.get("users", [])}
        username_to_v2_id: dict[str, int] = dict(V2User.objects.values_list("username", "id"))

        def user_v2_id(v1_user_id: int | None) -> int | None:
            if not v1_user_id:
                return None
            uname = v1_id_to_username.get(v1_user_id)
            return username_to_v2_id.get(uname) if uname else None

        # ── 3. Regions (preserve V1 id) ──
        n = 0
        for r in data.get("regions", []):
            V2Region.objects.update_or_create(
                id=r["id"],
                defaults={"name": r["name"]},
            )
            n += 1
        counts["regions"] = n

        # ── 4. Shops (preserve V1 id; map loan_balance → loan_balance_uzs) ──
        n = 0
        for s in data.get("shops", []):
            V2Shop.objects.update_or_create(
                id=s["id"],
                defaults={
                    "name": s["name"],
                    "owner_name": s.get("owner_name", "") or "",
                    "phone": s.get("phone", "") or "",
                    "address": s.get("address", "") or "",
                    "region_id": s["region_id"],
                    "loan_balance_uzs": _dec(s.get("loan_balance", 0)),
                    "loan_balance_usd": Decimal("0"),
                },
            )
            n += 1
        counts["shops"] = n

        # ── 5. Products (preserve V1 id; set default price = 0, to be filled in V2 UI) ──
        n = 0
        for p in data.get("products", []):
            V2Product.objects.update_or_create(
                id=p["id"],
                defaults={
                    "name": p["name"],
                    "description": p.get("description", "") or "",
                    "is_archived": not bool(p.get("is_active", True)),
                },
            )
            n += 1
        counts["products"] = n

        # ── 6. Units + Ingredients + Purchases (if V1 had inventory) ──
        unit_v1_to_v2: dict[int, int] = {}
        n = 0
        for u in data.get("units", []):
            obj, _ = V2Unit.objects.get_or_create(
                name=u["name"],
                defaults={"short": u.get("short", "") or ""},
            )
            unit_v1_to_v2[u["id"]] = obj.id
            n += 1
        counts["units"] = n

        n = 0
        for ing in data.get("ingredients", []):
            v2_unit_id = unit_v1_to_v2.get(ing["unit_id"])
            if not v2_unit_id:
                continue  # orphan — skip
            V2Ingredient.objects.update_or_create(
                id=ing["id"],
                defaults={
                    "name": ing["name"],
                    "quantity": _dec(ing.get("quantity", 0)),
                    "unit_id": v2_unit_id,
                    "low_stock_threshold": _dec(ing.get("low_stock_threshold", 0)),
                },
            )
            n += 1
        counts["ingredients"] = n

        n = 0
        for pur in data.get("purchases", []):
            qty = _dec(pur.get("quantity", 0)) or Decimal("1")
            total = _dec(pur.get("price", 0) or 0)
            V2Purchase.objects.update_or_create(
                id=pur["id"],
                defaults={
                    "ingredient_id": pur["ingredient_id"],
                    "quantity": qty,
                    "currency": "UZS",
                    "total_price": total,
                    "unit_price": (total / qty) if qty else Decimal("0"),
                    "account": seyf,
                    "occurred_at": _parse_dt(pur.get("date")) or timezone.now(),
                    "note": pur.get("note", "") or "",
                },
            )
            n += 1
        counts["purchases"] = n

        # ── 7. Orders (preserve V1 id) ──
        n = 0
        for o in data.get("orders", []):
            V2Order.objects.update_or_create(
                id=o["id"],
                defaults={
                    "shop_id": o["shop_id"],
                    "order_date": _parse_dt(o.get("order_date")) or timezone.now().date(),
                    "status": STATUS_MAP.get(o.get("status"), V2OrderStatus.PENDING),
                    "currency": "UZS",
                    "note": "",
                },
            )
            n += 1
        counts["orders"] = n

        # ── 8. OrderItems (preserve V1 id) ──
        n = 0
        for it in data.get("order_items", []):
            V2OrderItem.objects.update_or_create(
                id=it["id"],
                defaults={
                    "order_id": it["order_id"],
                    "product_id": it["product_id"],
                    "quantity": it["quantity"],
                    "unit_price": _dec(it.get("unit_price", 0)),
                    "delivered_quantity": it.get("delivered_quantity", 0),
                    "returned_quantity": 0,
                },
            )
            n += 1
        counts["order_items"] = n

        # ── 9. Payments — merge collection + loan_repayments into V2's unified Payment ──
        n = 0
        for p in data.get("payments", []):
            if not p.get("shop_id") and not p.get("order_id"):
                continue  # no target — skip
            # shop_id either directly, or derived from order.shop
            shop_id = p.get("shop_id")
            if not shop_id and p.get("order_id"):
                shop_id = (
                    V2Order.objects.filter(id=p["order_id"])
                    .values_list("shop_id", flat=True)
                    .first()
                )
                if not shop_id:
                    continue

            V2Payment.objects.create(
                shop_id=shop_id,
                order_id=p.get("order_id"),
                payment_type=PAYMENT_TYPE_MAP.get(p.get("payment_type"), V2PaymentType.COLLECTION),
                currency="UZS",
                amount=_dec(p.get("amount", 0)),
                discount=Decimal("0"),
                account=seyf,
                collected_by_id=user_v2_id(p.get("collected_by_id")),
                received_at=_parse_dt(p.get("date")) or timezone.now(),
                note=p.get("notes", "") or "",
            )
            n += 1

        # Convert V1 LoanRepayment rows into V2 Payment(loan_repayment) rows.
        for r in data.get("loan_repayments", []):
            if not r.get("shop_id"):
                continue
            V2Payment.objects.create(
                shop_id=r["shop_id"],
                order_id=None,
                payment_type=V2PaymentType.LOAN_REPAYMENT,
                currency="UZS",
                amount=_dec(r.get("amount", 0)),
                discount=Decimal("0"),
                account=seyf,
                collected_by_id=None,
                received_at=_parse_dt(r.get("date")) or timezone.now(),
                note="Migrated from V1 LoanRepayment",
            )
            n += 1
        counts["payments"] = n

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", help="Path to v1_snapshot.json")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    if not snapshot_path.exists():
        _die(f"Snapshot not found: {snapshot_path}")

    _setup_django()
    with snapshot_path.open(encoding="utf-8") as f:
        data = json.load(f)

    counts = _import(data)

    print(f"✓ Imported V1 snapshot from {snapshot_path}")
    for key, n in counts.items():
        print(f"  {key:20s} {n:>6d}")
    print(
        "\nReminder: product prices are NOT migrated (V1 had only one price "
        "field per order-item). Set default_price_uzs/_usd per product in V2 UI."
    )


if __name__ == "__main__":
    main()
