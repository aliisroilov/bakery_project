"""
Sync missing data from V1 PostgreSQL (bakery_db) into V2 PostgreSQL (bakery_v2).

Usage:
    python manage.py sync_from_v1

What it syncs:
- Missing orders (orders with ID > max V2 order ID)
- Order items for those orders
- Productions from V1 (without nonvoy attribution)
- Salary payments from V1

V1 DB: bakery_db / bakuser / localhost:5432
V2 DB: bakery_v2 / bakery_v2 / localhost:5432 (from .env)

Safe to run multiple times - idempotent for orders/productions/salary.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone as py_tz
from decimal import Decimal

import psycopg2
import psycopg2.extras
from django.core.management.base import BaseCommand
from django.db import transaction


V1_DB = {
    "dbname": os.environ.get("V1_DB_NAME", "bakery_db"),
    "user": os.environ.get("V1_DB_USER", "bakuser"),
    "password": os.environ.get("V1_DB_PASSWORD", "0270"),
    "host": os.environ.get("V1_DB_HOST", "localhost"),
    "port": os.environ.get("V1_DB_PORT", "5432"),
}


def _dt(val):
    """Ensure timezone-aware datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=py_tz.utc)
        return val
    return val


class Command(BaseCommand):
    help = "Sync missing data from V1 PostgreSQL into V2."

    def handle(self, *args, **options):
        self.stdout.write("Connecting to V1 database...")
        try:
            conn = psycopg2.connect(**V1_DB)
        except Exception as e:
            self.stderr.write(f"Cannot connect to V1 DB: {e}")
            return

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        self.stdout.write("Syncing orders...")
        self._sync_orders(cur)

        self.stdout.write("Syncing productions...")
        self._sync_productions(cur)

        self.stdout.write("Syncing salary payments...")
        self._sync_salary_payments(cur)

        self.stdout.write("Syncing ingredient recipes...")
        self._sync_recipes(cur)

        self.stdout.write("Syncing finance payments...")
        self._sync_finance_payments(cur)

        self.stdout.write("Syncing loan repayments...")
        self._sync_loan_repayments(cur)

        self.stdout.write("Syncing kassa balance...")
        self._sync_kassa_balance(cur)

        cur.close()
        conn.close()
        self.stdout.write(self.style.SUCCESS("Sync completed!"))

    def _sync_orders(self, cur):
        from apps.orders.models import Order, OrderItem
        from apps.shops.models import Shop

        # Find the max order ID already in V2
        max_v2_id = Order.objects.order_by("-id").values_list("id", flat=True).first() or 0
        self.stdout.write(f"  V2 max order ID: {max_v2_id}")

        # Get missing orders from V1 (V1 has: id, shop_id, order_date, status, received_amount, created_at)
        cur.execute("""
            SELECT o.id, o.shop_id, o.order_date, o.status,
                   o.received_amount, o.created_at
            FROM orders_order o
            WHERE o.id > %s
            ORDER BY o.id
        """, (max_v2_id,))
        v1_orders = cur.fetchall()
        self.stdout.write(f"  Found {len(v1_orders)} new orders in V1 to sync")

        # Build shop ID mapping (V1 shop IDs → V2 shop IDs by name)
        cur.execute("SELECT id, name FROM shops_shop")
        v1_shops = {row["id"]: row["name"] for row in cur.fetchall()}

        from apps.shops.models import Shop as V2Shop
        v2_shops_by_name = {s.name: s.id for s in V2Shop.objects.all()}

        # Build product mapping (needed for order items)
        cur.execute("SELECT id, name FROM products_product")
        v1_products = {row["id"]: row["name"] for row in cur.fetchall()}
        from apps.products.models import Product as V2Product
        v2_products_by_name = {p.name: p.id for p in V2Product.objects.all()}

        STATUS_MAP = {
            "Pending": "pending",
            "Partially Delivered": "partial",
            "Delivered": "delivered",
            "Cancelled": "cancelled",
        }

        created_orders = 0
        created_items = 0
        skipped = 0

        # Pre-fetch all items for all missing orders (more efficient)
        if v1_orders:
            order_ids = [row["id"] for row in v1_orders]
            placeholders = ",".join(["%s"] * len(order_ids))
            cur.execute(f"""
                SELECT oi.order_id, oi.product_id, oi.quantity, oi.unit_price,
                       oi.delivered_quantity
                FROM orders_orderitem oi
                WHERE oi.order_id IN ({placeholders})
            """, order_ids)
            all_items = cur.fetchall()
            items_by_order = {}
            for item in all_items:
                items_by_order.setdefault(item["order_id"], []).append(item)

        for row in v1_orders:
            v1_shop_name = v1_shops.get(row["shop_id"], "")
            v2_shop_id = v2_shops_by_name.get(v1_shop_name)
            if not v2_shop_id:
                skipped += 1
                continue

            status = STATUS_MAP.get(str(row["status"]), "pending")
            order_date = row["order_date"]
            if hasattr(order_date, "date"):
                order_date = order_date.date()

            # Use savepoint for each order to avoid transaction abort on conflict
            try:
                with transaction.atomic():
                    order = Order.objects.create(
                        id=row["id"],
                        shop_id=v2_shop_id,
                        order_date=order_date,
                        status=status,
                        currency="UZS",
                        note="",
                    )
                    # Add order items
                    items = items_by_order.get(row["id"], [])
                    for item in items:
                        v1_prod_name = v1_products.get(item["product_id"], "")
                        v2_prod_id = v2_products_by_name.get(v1_prod_name)
                        if not v2_prod_id:
                            continue
                        OrderItem.objects.create(
                            order=order,
                            product_id=v2_prod_id,
                            unit_price=item["unit_price"] or Decimal("0"),
                            quantity=item["quantity"] or 1,
                            delivered_quantity=item.get("delivered_quantity") or 0,
                            returned_quantity=0,
                        )
                        created_items += 1
                    created_orders += 1
            except Exception as e:
                skipped += 1

        self.stdout.write(
            f"  Orders: created={created_orders}, skipped={skipped}, "
            f"items_created={created_items}"
        )

    def _sync_productions(self, cur):
        from apps.production.models import Production, BakeryProductStock
        from apps.products.models import Product as V2Product
        from django.db.models import F

        # Get existing V2 production dates to avoid duplicates
        existing_v2_dates = set(
            Production.objects.values_list("occurred_at__date", flat=True)
        )

        # Build product name → V2 product ID mapping
        cur.execute("SELECT id, name FROM products_product")
        v1_products = {row["id"]: row["name"] for row in cur.fetchall()}
        v2_products_by_name = {p.name: p.id for p in V2Product.objects.all()}

        # Get all V1 productions
        cur.execute("""
            SELECT p.id, p.product_id, p.meshok, p.date, p.note
            FROM inventory_production p
            ORDER BY p.date
        """)
        v1_prods = cur.fetchall()
        self.stdout.write(f"  Found {len(v1_prods)} V1 productions")

        created = 0
        skipped = 0
        with transaction.atomic():
            for row in v1_prods:
                occurred_at = _dt(row["date"])
                if occurred_at is None:
                    skipped += 1
                    continue

                v1_prod_name = v1_products.get(row["product_id"], "")
                v2_prod_id = v2_products_by_name.get(v1_prod_name)
                if not v2_prod_id:
                    skipped += 1
                    continue

                # Check if we already have a production for this date/product combo
                # (simple dedup by date + product + meshok)
                if Production.objects.filter(
                    product_id=v2_prod_id,
                    occurred_at__date=occurred_at.date(),
                    meshok_count=row["meshok"],
                ).exists():
                    skipped += 1
                    continue

                try:
                    prod = Production.objects.create(
                        product_id=v2_prod_id,
                        nonvoy=None,
                        group=None,
                        meshok_count=row["meshok"] or Decimal("0"),
                        unit_count=Decimal("0"),
                        occurred_at=occurred_at,
                        note=(row.get("note") or "") + " [V1]",
                    )
                    created += 1
                except Exception as e:
                    self.stderr.write(f"    Production error: {e}")
                    skipped += 1

        self.stdout.write(f"  Productions: created={created}, skipped={skipped}")

    def _sync_salary_payments(self, cur):
        from apps.salary.models import SalaryPayment
        from apps.finance.models import KassaAccount
        from apps.users.models import User

        # Get V1 salary payments
        cur.execute("""
            SELECT sp.id, sp.user_id, sp.amount, sp.note, sp.created_at
            FROM salary_salarypayment sp
            ORDER BY sp.created_at
        """)
        v1_payments = cur.fetchall()
        self.stdout.write(f"  Found {len(v1_payments)} V1 salary payments")

        # Build user mapping (V1 user IDs → V2 user IDs by username)
        cur.execute("SELECT id, username FROM users_user")
        v1_users = {row["id"]: row["username"] for row in cur.fetchall()}
        v2_users_by_username = {u.username: u for u in User.objects.all()}

        # Get V2 kassa account (Rizoxon as default)
        try:
            rizoxon = KassaAccount.objects.get(name="Rizoxon")
        except KassaAccount.DoesNotExist:
            rizoxon = KassaAccount.objects.first()
            if not rizoxon:
                self.stderr.write("  No kassa accounts found, skipping salary payments")
                return

        created = 0
        skipped = 0
        with transaction.atomic():
            for row in v1_payments:
                v1_username = v1_users.get(row["user_id"])
                v2_user = v2_users_by_username.get(v1_username) if v1_username else None
                if not v2_user:
                    skipped += 1
                    continue

                occurred_at = _dt(row["created_at"])
                if not occurred_at:
                    skipped += 1
                    continue

                # Avoid duplicates: check if same user+amount+date
                if SalaryPayment.objects.filter(
                    user=v2_user,
                    amount=row["amount"],
                    occurred_at__date=occurred_at.date(),
                ).exists():
                    skipped += 1
                    continue

                try:
                    SalaryPayment.objects.create(
                        user=v2_user,
                        kind="salary",
                        currency="UZS",
                        amount=row["amount"] or Decimal("0"),
                        account=rizoxon,
                        occurred_at=occurred_at,
                        note=(row.get("note") or "") + " [V1]",
                        created_by=None,
                    )
                    created += 1
                except Exception as e:
                    self.stderr.write(f"    SalaryPayment error: {e}")
                    skipped += 1

        self.stdout.write(f"  Salary payments: created={created}, skipped={skipped}")

    def _sync_recipes(self, cur):
        from apps.inventory.models import Ingredient, ProductRecipe, Unit
        from apps.products.models import Product as V2Product

        # Sync units
        cur.execute("SELECT id, name, short FROM inventory_unit")
        v1_units = cur.fetchall()
        v2_units_by_name = {u.name: u for u in Unit.objects.all()}
        unit_id_map = {}  # v1 id → v2 Unit object
        for row in v1_units:
            unit = v2_units_by_name.get(row["name"])
            if not unit:
                unit = Unit.objects.create(name=row["name"], short=row["short"])
                v2_units_by_name[row["name"]] = unit
                self.stdout.write(f"    Created unit: {row['name']}")
            unit_id_map[row["id"]] = unit

        # Sync ingredients
        cur.execute("SELECT id, name, quantity, low_stock_threshold, unit_id FROM inventory_ingredient")
        v1_ingredients = cur.fetchall()
        v2_ingr_by_name = {i.name: i for i in Ingredient.objects.all()}
        ingr_id_map = {}  # v1 id → v2 Ingredient object
        for row in v1_ingredients:
            ingr = v2_ingr_by_name.get(row["name"])
            unit = unit_id_map.get(row["unit_id"])
            if not unit:
                skipped_ingr = True
                continue
            if not ingr:
                ingr = Ingredient.objects.create(
                    name=row["name"],
                    unit=unit,
                    quantity=row["quantity"] or Decimal("0"),
                    low_stock_threshold=row["low_stock_threshold"] or Decimal("0"),
                )
                v2_ingr_by_name[row["name"]] = ingr
                self.stdout.write(f"    Created ingredient: {row['name']}")
            else:
                # Update quantity from v1
                ingr.quantity = row["quantity"] or Decimal("0")
                ingr.low_stock_threshold = row["low_stock_threshold"] or Decimal("0")
                ingr.save(update_fields=["quantity", "low_stock_threshold"])
            ingr_id_map[row["id"]] = ingr

        # Sync product recipes
        cur.execute("SELECT id, product_id, ingredient_id, amount_per_meshok FROM inventory_productrecipe")
        v1_recipes = cur.fetchall()

        cur.execute("SELECT id, name FROM products_product")
        v1_products = {row["id"]: row["name"] for row in cur.fetchall()}
        v2_products_by_name = {p.name: p.id for p in V2Product.objects.all()}

        created = skipped = 0
        for row in v1_recipes:
            prod_name = v1_products.get(row["product_id"], "")
            v2_prod_id = v2_products_by_name.get(prod_name)
            ingr = ingr_id_map.get(row["ingredient_id"])
            if not v2_prod_id or not ingr:
                skipped += 1
                continue

            _, was_created = ProductRecipe.objects.update_or_create(
                product_id=v2_prod_id,
                ingredient=ingr,
                defaults={"amount_per_meshok": row["amount_per_meshok"] or Decimal("0")},
            )
            if was_created:
                created += 1

        self.stdout.write(
            f"  Recipes: ingredients={len(ingr_id_map)}, "
            f"recipes_created={created}, skipped={skipped}"
        )

    def _sync_finance_payments(self, cur):
        from apps.finance.models import KassaAccount, Payment
        from apps.orders.models import Order
        from apps.shops.models import Shop as V2Shop
        from apps.users.models import User

        # Build mappings
        cur.execute("SELECT id, name FROM shops_shop")
        v1_shops = {row["id"]: row["name"] for row in cur.fetchall()}
        v2_shops_by_name = {s.name: s.id for s in V2Shop.objects.all()}

        cur.execute("SELECT id, username FROM users_user")
        v1_users = {row["id"]: row["username"] for row in cur.fetchall()}
        v2_users_by_username = {u.username: u.id for u in User.objects.all()}

        v2_order_ids = set(Order.objects.values_list("id", flat=True))

        try:
            account = KassaAccount.objects.get(name="Rizoxon")
        except KassaAccount.DoesNotExist:
            account = KassaAccount.objects.first()
        if not account:
            self.stderr.write("  No kassa account found, skipping finance payments")
            return

        # Determine already-synced V1 IDs
        from django.db.models import Q
        synced_ids = set(
            Payment.objects.filter(note__contains="[V1-")
            .exclude(note__contains="[V1-LR-")
            .values_list("note", flat=True)
        )
        synced_v1_ids = set()
        for n in synced_ids:
            import re
            m = re.search(r"\[V1-(\d+)\]", n)
            if m:
                synced_v1_ids.add(int(m.group(1)))

        cur.execute("""
            SELECT id, amount, payment_type, notes, date, collected_by_id, order_id, shop_id
            FROM dashboard_payment
            ORDER BY date
        """)
        rows = cur.fetchall()
        self.stdout.write(f"  Found {len(rows)} V1 finance payments")

        created = skipped = 0
        for row in rows:
            if row["id"] in synced_v1_ids:
                skipped += 1
                continue

            v2_shop_id = v2_shops_by_name.get(v1_shops.get(row["shop_id"], ""))
            if not v2_shop_id:
                skipped += 1
                continue

            collector_id = None
            if row["collected_by_id"]:
                uname = v1_users.get(row["collected_by_id"])
                collector_id = v2_users_by_username.get(uname) if uname else None

            order_id = row["order_id"]
            if order_id and order_id not in v2_order_ids:
                order_id = None

            received_at = _dt(row["date"])
            if not received_at:
                skipped += 1
                continue

            note = (row.get("notes") or "").strip()
            note = f"{note} [V1-{row['id']}]".strip()

            try:
                Payment.objects.create(
                    shop_id=v2_shop_id,
                    order_id=order_id,
                    payment_type=row["payment_type"] or "collection",
                    currency="UZS",
                    amount=row["amount"] or Decimal("0"),
                    discount=Decimal("0"),
                    account=account,
                    collected_by_id=collector_id,
                    received_at=received_at,
                    note=note,
                )
                created += 1
            except Exception as e:
                self.stderr.write(f"    Payment error (id={row['id']}): {e}")
                skipped += 1

        self.stdout.write(f"  Finance payments: created={created}, skipped={skipped}")

    def _sync_loan_repayments(self, cur):
        from apps.finance.models import KassaAccount, Payment
        from apps.shops.models import Shop as V2Shop

        cur.execute("SELECT id, name FROM shops_shop")
        v1_shops = {row["id"]: row["name"] for row in cur.fetchall()}
        v2_shops_by_name = {s.name: s.id for s in V2Shop.objects.all()}

        try:
            account = KassaAccount.objects.get(name="Rizoxon")
        except KassaAccount.DoesNotExist:
            account = KassaAccount.objects.first()
        if not account:
            self.stderr.write("  No kassa account found, skipping loan repayments")
            return

        # Determine already-synced V1 loan repayment IDs
        import re
        synced_lr_ids = set()
        for n in Payment.objects.filter(note__contains="[V1-LR-").values_list("note", flat=True):
            m = re.search(r"\[V1-LR-(\d+)\]", n)
            if m:
                synced_lr_ids.add(int(m.group(1)))

        cur.execute("SELECT id, amount, date, shop_id FROM dashboard_loanrepayment ORDER BY date")
        rows = cur.fetchall()
        self.stdout.write(f"  Found {len(rows)} V1 loan repayments")

        created = skipped = 0
        for row in rows:
            if row["id"] in synced_lr_ids:
                skipped += 1
                continue

            v2_shop_id = v2_shops_by_name.get(v1_shops.get(row["shop_id"], ""))
            if not v2_shop_id:
                skipped += 1
                continue

            received_at = _dt(row["date"])
            if not received_at:
                skipped += 1
                continue

            try:
                Payment.objects.create(
                    shop_id=v2_shop_id,
                    payment_type="loan_repayment",
                    currency="UZS",
                    amount=row["amount"] or Decimal("0"),
                    discount=Decimal("0"),
                    account=account,
                    received_at=received_at,
                    note=f"[V1-LR-{row['id']}]",
                )
                created += 1
            except Exception as e:
                self.stderr.write(f"    LoanRepayment error (id={row['id']}): {e}")
                skipped += 1

        self.stdout.write(f"  Loan repayments: created={created}, skipped={skipped}")

    def _sync_kassa_balance(self, cur):
        from apps.finance.models import KassaAccount
        from decimal import Decimal

        # Get V1's current balance
        cur.execute("SELECT amount FROM reports_bakerybalance ORDER BY id LIMIT 1")
        row = cur.fetchone()
        if not row:
            self.stdout.write("  No V1 balance found")
            return

        v1_balance = Decimal(str(row["amount"]))
        self.stdout.write(f"  V1 balance: {v1_balance} UZS")

        try:
            rizoxon = KassaAccount.objects.get(name="Rizoxon")
            rizoxon.balance_uzs = v1_balance
            rizoxon.save(update_fields=["balance_uzs"])
            self.stdout.write(f"  Updated Rizoxon balance to {v1_balance} UZS")
        except KassaAccount.DoesNotExist:
            self.stderr.write("  Rizoxon account not found")
