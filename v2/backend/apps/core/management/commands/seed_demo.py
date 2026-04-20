"""
Seed demo data for v2 — standalone, no v1 DB required.

Usage: python manage.py seed_demo [--wipe]

Creates: kassa accounts, units, ingredients, products + recipes,
regions, shops, users (all roles), orders (various statuses),
payments, purchases, productions, activity logs.

Idempotent on non-wipe: uses get_or_create / update_or_create where safe;
orders/payments/productions are additive so re-running adds more history.
"""
from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.finance.models import KassaAccount, KassaTransaction, Payment, PaymentType
from apps.inventory.models import Ingredient, ProductRecipe, Purchase as IngredientPurchase, Unit
from apps.orders.models import Order, OrderItem, OrderPriority, OrderStatus
from apps.production.models import BakeryProductStock, Production
from apps.products.models import Product
from apps.salary.models import PaymentKind, RateType, SalaryPayment, SalaryRate
from apps.shops.models import Region, Shop
from apps.users.models import Role, User, UserActivityLog


class Command(BaseCommand):
    help = "Seed realistic demo data for v2 local development / testing."

    def add_arguments(self, parser):
        parser.add_argument("--wipe", action="store_true", help="Wipe demo data before seeding")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["wipe"]:
            self._wipe()

        accounts = self._seed_accounts()
        units = self._seed_units()
        ingredients = self._seed_ingredients(units)
        products = self._seed_products()
        self._seed_recipes(products, ingredients)
        regions = self._seed_regions()
        users = self._seed_users(products)
        shops = self._seed_shops(regions, users)
        self._seed_purchases(ingredients, accounts, users)
        self._seed_productions(products, users)
        self._seed_orders(shops, products, users)
        self._seed_payments(shops, accounts, users)
        self._seed_salary_rates(users)
        self._seed_salary_payments(users, accounts)
        self._seed_activity(users)

        self.stdout.write(self.style.SUCCESS("✓ Demo data seeded."))
        self.stdout.write(
            f"  Users: {User.objects.count()} · Shops: {Shop.objects.count()} · "
            f"Products: {Product.objects.count()} · Orders: {Order.objects.count()} · "
            f"Payments: {Payment.objects.count()}"
        )
        self.stdout.write("  Login: admin/admin · manager1/demo · driver1/demo · nonvoy1/demo")

    def _wipe(self):
        self.stdout.write("Wiping existing data…")
        for model in [
            UserActivityLog, Payment, KassaTransaction, IngredientPurchase,
            SalaryPayment, SalaryRate,
            Production, BakeryProductStock, OrderItem, Order,
            ProductRecipe, Ingredient, Unit, Product, Shop, Region,
        ]:
            model.objects.all().delete()
        # Keep kassa accounts — they're seeded by data migration, not demo.
        # Keep superuser + anyone non-demo.
        User.objects.exclude(is_superuser=True).delete()

    # ── seeders ─────────────────────────────────────────────
    def _seed_accounts(self):
        seyf, _ = KassaAccount.objects.get_or_create(
            slug="seyf",
            defaults={"name": "Seyf", "balance_uzs": Decimal("5000000"), "balance_usd": Decimal("500")},
        )
        rizoxon, _ = KassaAccount.objects.get_or_create(
            slug="rizoxon",
            defaults={"name": "Rizoxon", "balance_uzs": Decimal("2000000"), "balance_usd": Decimal("200")},
        )
        return {"seyf": seyf, "rizoxon": rizoxon}

    def _seed_units(self):
        pairs = [("Kilogramm", "kg"), ("Litr", "l"), ("Dona", "dona"), ("Gramm", "g")]
        return {
            short: Unit.objects.get_or_create(name=name, defaults={"short": short})[0]
            for name, short in pairs
        }

    def _seed_ingredients(self, units):
        data = [
            ("Un", "kg", 500, 50, 4500),
            ("Shakar", "kg", 80, 10, 12000),
            ("Tuz", "kg", 30, 5, 3500),
            ("Margarin", "kg", 40, 10, 28000),
            ("Sut", "l", 100, 20, 9000),
            ("Droja", "kg", 15, 3, 45000),
            ("Tuxum", "dona", 400, 60, 1500),
            ("Suv", "l", 200, 20, 500),
        ]
        out = {}
        for name, unit_short, qty, thr, price in data:
            ing, _ = Ingredient.objects.update_or_create(
                name=name,
                defaults={
                    "unit": units[unit_short],
                    "quantity": Decimal(qty),
                    "low_stock_threshold": Decimal(thr),
                    "avg_cost_uzs": Decimal(price),
                    "is_archived": False,
                },
            )
            out[name] = ing
        return out

    def _seed_products(self):
        data = [
            ("Sutli non", 3500, 160, 800),
            ("Chapchap", 2500, 160, 600),
            ("Marokash Patir", 5000, 100, 1200),
            ("Obi non", 2000, 200, 500),
            ("Katlama", 4000, 120, 1000),
        ]
        out = {}
        for name, price, meshok_size, salary in data:
            p, _ = Product.objects.update_or_create(
                name=name,
                defaults={
                    "default_price_uzs": Decimal(price),
                    "meshok_size": Decimal(meshok_size),
                    "production_salary_per_unit_uzs": Decimal(salary),
                    "is_archived": False,
                },
            )
            BakeryProductStock.objects.get_or_create(
                product=p, defaults={"quantity": Decimal(random.randint(80, 400))}
            )
            out[name] = p
        return out

    def _seed_recipes(self, products, ingredients):
        recipes = {
            "Sutli non": [("Un", 100), ("Shakar", 5), ("Tuz", 1), ("Sut", 20), ("Droja", 1.5), ("Suv", 30)],
            "Chapchap": [("Un", 80), ("Shakar", 3), ("Tuz", 1), ("Margarin", 5), ("Droja", 1), ("Suv", 25)],
            "Marokash Patir": [("Un", 60), ("Shakar", 2), ("Tuz", 1), ("Margarin", 8), ("Tuxum", 30), ("Suv", 15)],
            "Obi non": [("Un", 120), ("Tuz", 2), ("Droja", 2), ("Suv", 50)],
            "Katlama": [("Un", 70), ("Margarin", 15), ("Tuz", 1), ("Suv", 20)],
        }
        for pname, lines in recipes.items():
            for iname, amount in lines:
                ProductRecipe.objects.update_or_create(
                    product=products[pname],
                    ingredient=ingredients[iname],
                    defaults={"amount_per_meshok": Decimal(str(amount))},
                )

    def _seed_regions(self):
        names = ["Chilonzor", "Yunusobod", "Mirzo Ulug'bek", "Sergeli", "Yakkasaroy"]
        return {n: Region.objects.get_or_create(name=n)[0] for n in names}

    def _seed_users(self, products):
        product_list = list(products.values())
        specs = [
            ("manager1", "Aziz Karimov", Role.MANAGER, None),
            ("manager2", "Dilshod Abdullayev", Role.MANAGER, None),
            ("driver1", "Bobur Yoqubov", Role.DRIVER, None),
            ("driver2", "Javlon Raxmatov", Role.DRIVER, None),
            ("driver3", "Sanjar Nazarov", Role.DRIVER, None),
            ("nonvoy1", "Shavkat Mirzayev", Role.NONVOY, product_list[0] if product_list else None),
            ("nonvoy2", "Akram Yusupov", Role.NONVOY, product_list[1] if len(product_list) > 1 else None),
            ("nonvoy3", "Rustam Ismoilov", Role.NONVOY, product_list[2] if len(product_list) > 2 else None),
            ("accountant1", "Gulnora Saidova", Role.ACCOUNTANT, None),
            ("viewer1", "Ali Niyozov", Role.VIEWER, None),
        ]
        out = {}
        # Ensure admin exists
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                "admin", "admin@example.com", "admin", full_name="Bosh admin"
            )
        for username, fullname, role, product in specs:
            u, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "full_name": fullname,
                    "role": role,
                    "phone": f"+998 90 {random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}",
                    "produced_product": product,
                },
            )
            if created:
                u.set_password("demo")
                u.save()
            else:
                u.produced_product = product
                u.save(update_fields=["produced_product"])
            out[username] = u
        return out

    def _seed_shops(self, regions, users):
        drivers = [u for u in users.values() if u.role == Role.DRIVER]
        specs = [
            ("Alfajr", "Salim aka", "+998 90 111 22 33", "Chilonzor", drivers[0] if drivers else None, 3_000_000),
            ("Navbahor", "Olim aka", "+998 90 222 33 44", "Yunusobod", drivers[0] if drivers else None, 2_000_000),
            ("Baraka", "Karim aka", "+998 90 333 44 55", "Mirzo Ulug'bek", drivers[1] if len(drivers) > 1 else None, 5_000_000),
            ("Do'stlik", "Nodir aka", "+998 90 444 55 66", "Sergeli", drivers[1] if len(drivers) > 1 else None, 1_500_000),
            ("Yangi Osiyo", "Rahim aka", "+998 90 555 66 77", "Yakkasaroy", drivers[2] if len(drivers) > 2 else None, 4_000_000),
            ("Hilol", "Bekzod aka", "+998 90 666 77 88", "Chilonzor", drivers[0] if drivers else None, 2_500_000),
            ("Gulshan", "Temur aka", "+998 90 777 88 99", "Yunusobod", drivers[2] if len(drivers) > 2 else None, 3_500_000),
        ]
        out = {}
        for name, owner, phone, region_name, driver, loan_limit in specs:
            s, _ = Shop.objects.update_or_create(
                name=name,
                defaults={
                    "owner_name": owner,
                    "phone": phone,
                    "address": f"{region_name} tumani, {random.randint(1, 50)}-uy",
                    "region": regions[region_name],
                    "assigned_driver": driver,
                    "loan_limit_uzs": Decimal(loan_limit),
                    "is_archived": False,
                },
            )
            out[name] = s
        return out

    def _seed_purchases(self, ingredients, accounts, users):
        manager = next((u for u in users.values() if u.role == Role.MANAGER), None)
        now = timezone.now()
        for i, (name, ing) in enumerate(ingredients.items()):
            if i % 2 == 0:
                continue
            qty = Decimal(random.randint(20, 100))
            unit_price = ing.avg_cost_uzs or Decimal("3000")
            total = qty * unit_price
            IngredientPurchase.objects.create(
                ingredient=ing,
                quantity=qty,
                currency="UZS",
                total_price=total,
                unit_price=unit_price,
                account=accounts["seyf"],
                occurred_at=now - timedelta(days=random.randint(1, 10)),
                note="Demo xaridi",
                created_by=manager,
            )

    def _seed_productions(self, products, users):
        nonvoys = [u for u in users.values() if u.role == Role.NONVOY]
        if not nonvoys:
            return
        now = timezone.now()
        for days_ago in range(0, 5):
            occurred = now - timedelta(days=days_ago)
            for p in list(products.values())[:3]:
                nonvoy = random.choice(nonvoys)
                meshok = Decimal(random.randint(2, 6))
                Production.objects.create(
                    product=p,
                    nonvoy=nonvoy,
                    meshok_count=meshok,
                    unit_count=meshok * p.meshok_size,
                    occurred_at=occurred,
                    note="Demo ishlab chiqarish",
                )

    def _seed_orders(self, shops, products, users):
        manager = next((u for u in users.values() if u.role == Role.MANAGER), None)
        today = timezone.localdate()
        product_list = list(products.values())
        priorities = [OrderPriority.NORMAL, OrderPriority.NORMAL, OrderPriority.HIGH, OrderPriority.URGENT]
        statuses = [OrderStatus.PENDING, OrderStatus.PARTIALLY_DELIVERED, OrderStatus.DELIVERED]

        shop_list = list(shops.values())
        for i in range(20):
            shop = random.choice(shop_list)
            days_back = random.randint(0, 7)
            order_date = today - timedelta(days=days_back)
            st = OrderStatus.PENDING if days_back == 0 else random.choice(statuses)
            order = Order.objects.create(
                shop=shop,
                order_date=order_date,
                priority=random.choice(priorities),
                currency="UZS",
                status=st,
                note="",
                created_by=manager,
            )
            for p in random.sample(product_list, random.randint(1, 3)):
                qty = random.randint(5, 30)
                delivered = qty if st == OrderStatus.DELIVERED else (
                    random.randint(0, qty) if st == OrderStatus.PARTIALLY_DELIVERED else 0
                )
                OrderItem.objects.create(
                    order=order,
                    product=p,
                    unit_price=p.default_price_uzs,
                    quantity=qty,
                    delivered_quantity=delivered,
                )

        # Recompute shop loan balances from orders + payments
        from django.db.models import Sum, F
        for shop in shop_list:
            delivered_total = Decimal("0")
            for o in Order.objects.filter(shop=shop, currency="UZS").prefetch_related("items"):
                for it in o.items.all():
                    delivered_total += it.delivered_price
            shop.loan_balance_uzs = delivered_total
            shop.save(update_fields=["loan_balance_uzs"])

    def _seed_payments(self, shops, accounts, users):
        driver = next((u for u in users.values() if u.role == Role.DRIVER), None)
        now = timezone.now()
        for shop in list(shops.values())[:5]:
            # Two payments: one today, one a few days ago
            for days in [0, 3]:
                amount = Decimal(random.randint(100_000, 800_000))
                Payment.objects.create(
                    shop=shop,
                    payment_type=PaymentType.COLLECTION,
                    currency="UZS",
                    amount=amount,
                    discount=Decimal("0"),
                    account=accounts["seyf"],
                    collected_by=driver,
                    received_at=now - timedelta(days=days),
                    note="Demo to'lov",
                )
                # Partial recompute of shop balance
                shop.loan_balance_uzs = max(Decimal("0"), shop.loan_balance_uzs - amount)
                shop.save(update_fields=["loan_balance_uzs"])

    def _seed_salary_rates(self, users):
        """Per-role defaults: nonvoy = per_product, driver = per_week, manager = fixed_monthly."""
        defaults_by_role = {
            Role.NONVOY: (RateType.PER_PRODUCT, Decimal("0")),
            Role.DRIVER: (RateType.PER_WEEK, Decimal("350000")),
            Role.MANAGER: (RateType.FIXED_MONTHLY, Decimal("4000000")),
            Role.ACCOUNTANT: (RateType.FIXED_MONTHLY, Decimal("3500000")),
        }
        for u in users.values():
            if u.role not in defaults_by_role:
                continue
            rt, amount = defaults_by_role[u.role]
            SalaryRate.objects.update_or_create(
                user=u,
                defaults={
                    "rate_type": rt,
                    "rate": amount,
                    "currency": "UZS",
                    "initial_balance": Decimal("0"),
                    "note": "Demo seed",
                },
            )

    def _seed_salary_payments(self, users, accounts):
        """Add a few historical salary/advance/bonus rows so UI has something to show."""
        payable = [u for u in users.values() if u.role in [Role.NONVOY, Role.DRIVER, Role.MANAGER, Role.ACCOUNTANT]]
        if not payable:
            return
        now = timezone.now()
        samples = [
            (PaymentKind.SALARY, 500_000, 10),
            (PaymentKind.ADVANCE, 200_000, 5),
            (PaymentKind.BONUS, 100_000, 2),
        ]
        for u in payable[:5]:
            for kind, amount, days_back in samples:
                SalaryPayment.objects.create(
                    user=u,
                    kind=kind,
                    currency="UZS",
                    amount=Decimal(amount),
                    account=accounts["seyf"],
                    occurred_at=now - timedelta(days=days_back),
                    note=f"Demo {kind}",
                )

    def _seed_activity(self, users):
        now = timezone.now()
        methods = ["GET", "POST", "PATCH", "DELETE", "GET", "GET"]
        paths = [
            "/api/v1/orders/", "/api/v1/shops/", "/api/v1/products/",
            "/api/v1/users/", "/api/v1/finance/payments/",
            "/api/v1/inventory/ingredients/", "/api/v1/dashboard/summary/",
            "/api/v1/orders/1/confirm_delivery/",
        ]
        for u in users.values():
            for _ in range(5):
                UserActivityLog.objects.create(
                    user=u,
                    method=random.choice(methods),
                    path=random.choice(paths),
                    status_code=random.choice([200, 200, 200, 201, 204, 400]),
                    ip=f"192.168.1.{random.randint(2, 254)}",
                )
                # Walk timestamp back — we can't set auto_now_add directly,
                # but that's fine for demo.
