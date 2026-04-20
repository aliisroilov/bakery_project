"""
Migrate data from v1 SQLite database into v2 Postgres.

Usage:
    python manage.py migrate_from_v1 --source /path/to/db.sqlite3 [--wipe]

The v1 DB is READ ONLY. The v2 DB is populated via the ORM (so signals, defaults,
and constraints all fire correctly).

--wipe clears the v2 tables before importing. Useful for re-running during dev.

Currency note: v1 is single-currency (UZS). All money values go to _uzs fields
and USD fields stay 0.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone as py_tz
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.finance.models import (
    ExpenseCategory,
    GeneralExpense,
    KassaAccount,
    KassaTransaction,
    KassaTransactionType,
    Payment,
    PaymentType,
)
from apps.inventory.models import (
    Ingredient,
    ProductRecipe,
    Purchase as IngredientPurchase,
    Unit,
)
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.production.models import (
    BakeryProductStock,
    InventoryRevisionReport,
)
from apps.products.models import Product
from apps.shops.models import Region, Shop
from apps.users.models import User, UserActivityLog

V1_STATUS_MAP = {
    "Pending": OrderStatus.PENDING,
    "Partially Delivered": OrderStatus.PARTIALLY_DELIVERED,
    "Delivered": OrderStatus.DELIVERED,
}

V1_ROLES_ALLOWED = {"manager", "driver", "viewer", "nonvoy"}


def _dt(s: str | None) -> datetime | None:
    """Parse v1 SQLite datetime string → aware UTC datetime."""
    if not s:
        return None
    # SQLite stores as "YYYY-MM-DD HH:MM:SS[.fff][+TZ]"
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=py_tz.utc)
            return dt
        except ValueError:
            continue
    return None


def _d(s: str | None) -> datetime | None:
    """Parse v1 SQLite date string → date."""
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Migrate data from a v1 SQLite DB into v2 Postgres."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            required=True,
            help="Path to the v1 db.sqlite3 file.",
        )
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete all v2 data (except superuser + seeded kassa) before importing.",
        )

    def handle(self, *args, **opts):
        source = Path(opts["source"])
        if not source.exists():
            raise CommandError(f"Source DB not found: {source}")

        # One connection, row as dicts.
        conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        with transaction.atomic():
            if opts["wipe"]:
                self._wipe()
            ctx = Context(self, conn)
            ctx.run()

        self.stdout.write(self.style.SUCCESS("✓ Migration complete."))

    def _wipe(self):
        self.stdout.write("Wiping existing v2 data...")
        # Delete in FK-safe order.
        KassaTransaction.objects.all().delete()
        Payment.objects.all().delete()
        GeneralExpense.objects.all().delete()
        ExpenseCategory.objects.all().delete()
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        IngredientPurchase.objects.all().delete()
        ProductRecipe.objects.all().delete()
        InventoryRevisionReport.objects.all().delete()
        BakeryProductStock.objects.all().delete()
        Ingredient.objects.all().delete()
        Unit.objects.all().delete()
        Product.objects.all().delete()
        Shop.objects.all().delete()
        Region.objects.all().delete()
        UserActivityLog.objects.all().delete()
        # Keep superuser(s); remove imported ones.
        User.objects.filter(is_superuser=False).delete()


class Context:
    """Per-run state holding id maps from v1 → v2."""

    def __init__(self, cmd: Command, conn: sqlite3.Connection):
        self.cmd = cmd
        self.conn = conn
        self.users: dict[int, User] = {}
        self.regions: dict[int, Region] = {}
        self.shops: dict[int, Shop] = {}
        self.products: dict[int, Product] = {}
        self.units: dict[int, Unit] = {}
        self.ingredients: dict[int, Ingredient] = {}
        self.orders: dict[int, Order] = {}
        self.categories: dict[int, ExpenseCategory] = {}
        self.seyf = KassaAccount.objects.get(slug=KassaAccount.SEYF)

    def log(self, msg: str):
        self.cmd.stdout.write(msg)

    def fetch(self, sql: str) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql))

    def run(self):
        self.migrate_users()
        self.migrate_regions()
        self.migrate_shops()
        self.migrate_products()
        self.migrate_units()
        self.migrate_ingredients()
        self.migrate_orders()
        self.migrate_ingredient_purchases()
        self.migrate_recipes()
        self.migrate_bakery_stock()
        self.migrate_inventory_revisions()
        self.migrate_expense_categories()
        self.migrate_general_expenses()
        self.migrate_payments()
        self.migrate_loan_repayments()
        self.migrate_user_activity()
        self.migrate_bakery_balance()
        self.recalc_shop_loan_balances()

    # ─────── Users ───────
    def migrate_users(self):
        for row in self.fetch("SELECT * FROM users_user"):
            # Skip already-existing usernames (e.g. admin superuser we seeded).
            existing = User.objects.filter(username=row["username"]).first()
            if existing:
                self.users[row["id"]] = existing
                continue
            role = row["role"] if row["role"] in V1_ROLES_ALLOWED else "viewer"
            u = User.objects.create(
                username=row["username"],
                password=row["password"],  # pbkdf2 hash carries over unchanged
                is_superuser=bool(row["is_superuser"]),
                is_staff=bool(row["is_staff"]),
                is_active=bool(row["is_active"]),
                role=role,
                full_name=f"{row['first_name']} {row['last_name']}".strip(),
                date_joined=_dt(row["date_joined"]) or timezone.now(),
                last_login=_dt(row["last_login"]),
                email=row["email"] or "",
            )
            self.users[row["id"]] = u
        self.log(f"  users: {len(self.users)}")

    # ─────── Regions / Shops ───────
    def migrate_regions(self):
        for row in self.fetch("SELECT * FROM shops_region"):
            r, _ = Region.objects.get_or_create(name=row["name"])
            self.regions[row["id"]] = r
        self.log(f"  regions: {len(self.regions)}")

    def migrate_shops(self):
        for row in self.fetch("SELECT * FROM shops_shop"):
            region = self.regions.get(row["region_id"])
            if not region:
                continue
            s = Shop.objects.create(
                name=row["name"],
                owner_name=row["owner_name"] or "",
                phone=row["phone"] or "",
                address=row["address"] or "",
                region=region,
                loan_balance_uzs=Decimal(row["loan_balance"] or 0),
            )
            self.shops[row["id"]] = s
        self.log(f"  shops: {len(self.shops)}")

    # ─────── Products ───────
    def migrate_products(self):
        for row in self.fetch("SELECT * FROM products_product"):
            p = Product.objects.create(
                name=row["name"],
                description=row["description"] or "",
                is_archived=not bool(row["is_active"]),
            )
            self.products[row["id"]] = p
        self.log(f"  products: {len(self.products)}")

    # ─────── Inventory ───────
    def migrate_units(self):
        for row in self.fetch("SELECT * FROM inventory_unit"):
            u, _ = Unit.objects.get_or_create(
                name=row["name"], defaults={"short": row["short"] or ""}
            )
            self.units[row["id"]] = u
        self.log(f"  units: {len(self.units)}")

    def migrate_ingredients(self):
        for row in self.fetch("SELECT * FROM inventory_ingredient"):
            unit = self.units.get(row["unit_id"])
            if not unit:
                continue
            i = Ingredient.objects.create(
                name=row["name"],
                unit=unit,
                quantity=Decimal(row["quantity"] or 0),
                low_stock_threshold=Decimal(row["low_stock_threshold"] or 0),
            )
            self.ingredients[row["id"]] = i
        self.log(f"  ingredients: {len(self.ingredients)}")

    def migrate_recipes(self):
        n = 0
        for row in self.fetch("SELECT * FROM inventory_productrecipe"):
            product = self.products.get(row["product_id"])
            ingredient = self.ingredients.get(row["ingredient_id"])
            if not product or not ingredient:
                continue
            ProductRecipe.objects.create(
                product=product,
                ingredient=ingredient,
                amount_per_meshok=Decimal(row["amount_per_meshok"]),
            )
            n += 1
        self.log(f"  recipes: {n}")

    def migrate_ingredient_purchases(self):
        n = 0
        for row in self.fetch("SELECT * FROM inventory_purchase"):
            ingredient = self.ingredients.get(row["ingredient_id"])
            if not ingredient:
                continue
            qty = Decimal(row["quantity"] or 0)
            total = Decimal(row["price"] or 0)
            unit_price = (total / qty) if qty else Decimal(0)
            IngredientPurchase.objects.create(
                ingredient=ingredient,
                quantity=qty,
                total_price=total,
                unit_price=unit_price.quantize(Decimal("0.01")),
                currency="UZS",
                account=self.seyf,
                occurred_at=_dt(row["date"]) or timezone.now(),
                note=row["note"] or "",
            )
            n += 1
        self.log(f"  ingredient purchases: {n}")

    def migrate_bakery_stock(self):
        n = 0
        for row in self.fetch("SELECT * FROM inventory_bakeryproductstock"):
            product = self.products.get(row["product_id"])
            if not product:
                continue
            BakeryProductStock.objects.update_or_create(
                product=product,
                defaults={
                    "quantity": Decimal(row["quantity"] or 0),
                    "pinned": bool(row["pinned"]),
                },
            )
            n += 1
        self.log(f"  bakery stock: {n}")

    def migrate_inventory_revisions(self):
        n = 0
        for row in self.fetch("SELECT * FROM inventory_inventoryrevisionreport"):
            ingredient = self.ingredients.get(row["ingredient_id"]) if row["ingredient_id"] else None
            product = self.products.get(row["product_id"]) if row["product_id"] else None
            user = self.users.get(row["user_id"]) if row["user_id"] else None
            InventoryRevisionReport.objects.create(
                item_type=row["item_type"],
                ingredient=ingredient,
                product=product,
                old_quantity=Decimal(row["old_quantity"]),
                new_quantity=Decimal(row["new_quantity"]),
                note=row["note"] or "",
                user=user,
            )
            n += 1
        self.log(f"  inventory revisions: {n}")

    # ─────── Orders ───────
    def migrate_orders(self):
        n_orders = 0
        n_items = 0
        for row in self.fetch("SELECT * FROM orders_order"):
            shop = self.shops.get(row["shop_id"])
            if not shop:
                continue
            o = Order.objects.create(
                shop=shop,
                order_date=_d(row["order_date"]) or timezone.now().date(),
                status=V1_STATUS_MAP.get(row["status"], OrderStatus.PENDING),
                currency="UZS",
                note="",
            )
            # Preserve original created_at (bypass auto_now_add via update).
            created_at = _dt(row["created_at"])
            if created_at:
                Order.objects.filter(pk=o.pk).update(created_at=created_at)
            self.orders[row["id"]] = o
            n_orders += 1
        # Items
        for row in self.fetch("SELECT * FROM orders_orderitem"):
            order = self.orders.get(row["order_id"])
            product = self.products.get(row["product_id"])
            if not order or not product:
                continue
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=row["quantity"],
                unit_price=Decimal(row["unit_price"] or 0),
                delivered_quantity=row["delivered_quantity"] or 0,
            )
            n_items += 1
        self.log(f"  orders: {n_orders}, items: {n_items}")

    # ─────── Expenses ───────
    def migrate_expense_categories(self):
        for row in self.fetch("SELECT * FROM reports_category"):
            c = ExpenseCategory.objects.create(
                name=row["name"], note=row["description"] or ""
            )
            self.categories[row["id"]] = c
        self.log(f"  expense categories: {len(self.categories)}")

    def migrate_general_expenses(self):
        n = 0
        for row in self.fetch("SELECT * FROM reports_purchase"):
            category = self.categories.get(row["category_id"]) if row["category_id"] else None
            occurred = (
                _dt(row["created_at"])
                or datetime.combine(_d(row["purchase_date"]) or timezone.now().date(), datetime.min.time()).replace(tzinfo=py_tz.utc)
            )
            GeneralExpense.objects.create(
                category=category,
                title=row["item_name"],
                currency="UZS",
                amount=Decimal(row["unit_price"] or 0),
                account=self.seyf,
                occurred_at=occurred,
                note=row["notes"] or "",
            )
            n += 1
        self.log(f"  general expenses: {n}")

    # ─────── Payments ───────
    def migrate_payments(self):
        n = 0
        for row in self.fetch("SELECT * FROM dashboard_payment"):
            shop = self.shops.get(row["shop_id"]) if row["shop_id"] else None
            order = self.orders.get(row["order_id"]) if row["order_id"] else None
            if not shop and order:
                shop = order.shop
            if not shop:
                continue
            pt = row["payment_type"] or "collection"
            if pt == "repayment":
                pt = PaymentType.LOAN_REPAYMENT
            elif pt == "collection":
                pt = PaymentType.COLLECTION
            else:
                pt = PaymentType.OTHER
            Payment.objects.create(
                shop=shop,
                order=order,
                order_date=order.order_date if order else None,
                payment_type=pt,
                currency="UZS",
                amount=Decimal(row["amount"] or 0),
                account=self.seyf,
                collected_by=self.users.get(row["collected_by_id"]) if row["collected_by_id"] else None,
                received_at=_dt(row["date"]) or timezone.now(),
                note=row["notes"] or "",
            )
            n += 1
        self.log(f"  payments: {n}")

    def migrate_loan_repayments(self):
        n = 0
        for row in self.fetch("SELECT * FROM dashboard_loanrepayment"):
            shop = self.shops.get(row["shop_id"])
            if not shop:
                continue
            Payment.objects.create(
                shop=shop,
                payment_type=PaymentType.LOAN_REPAYMENT,
                currency="UZS",
                amount=Decimal(row["amount"] or 0),
                account=self.seyf,
                received_at=_dt(row["date"]) or timezone.now(),
                note="Migrated from v1 LoanRepayment",
            )
            n += 1
        self.log(f"  loan repayments → payments: {n}")

    # ─────── Activity logs ───────
    def migrate_user_activity(self):
        rows = self.fetch("SELECT * FROM users_useractivitylog")
        batch: list[UserActivityLog] = []
        for row in rows:
            user = self.users.get(row["user_id"])
            if not user:
                continue
            batch.append(
                UserActivityLog(
                    user=user,
                    path=(row.keys() and row["path"] if "path" in row.keys() else "")[:500],
                    method=(row["method"] if "method" in row.keys() else "")[:10],
                    ip=row["ip"] if "ip" in row.keys() else None,
                )
            )
        if batch:
            UserActivityLog.objects.bulk_create(batch, batch_size=500)
        self.log(f"  activity logs: {len(batch)}")

    # ─────── Bakery balance → Seyf ───────
    def migrate_bakery_balance(self):
        rows = self.fetch("SELECT * FROM reports_bakerybalance LIMIT 1")
        if not rows:
            return
        amount = Decimal(rows[0]["amount"] or 0)
        # Set Seyf balance directly; the ledger sum won't match without back-filling
        # ledger entries, but the business "cash on hand" number is preserved.
        self.seyf.balance_uzs = amount
        self.seyf.save(update_fields=["balance_uzs"])
        self.log(f"  bakery_balance → Seyf: {amount} UZS")

    def recalc_shop_loan_balances(self):
        # Shop.loan_balance was copied directly from v1; nothing to recalculate.
        # (v2's single-source-of-truth formula matches what v1 had stored.)
        pass
