"""
Management command to zero out bakery product inventory.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from inventory.models import BakeryProductStock, InventoryRevisionReport

User = get_user_model()


class Command(BaseCommand):
    help = 'Zero out specific bakery product inventory items'

    def add_arguments(self, parser):
        parser.add_argument(
            '--products',
            nargs='+',
            type=str,
            help='Product names to zero out (e.g., "Chap chap" "Sutli")',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Zero out all bakery products',
        )
        parser.add_argument(
            '--note',
            type=str,
            default='Inventarizatsiya: balansni nolga tushirish',
            help='Note for the audit log',
        )

    def handle(self, *args, **options):
        products = options.get('products')
        zero_all = options.get('all')
        note = options.get('note')

        if not products and not zero_all:
            self.stdout.write(
                self.style.ERROR(
                    'Please specify --products or --all flag'
                )
            )
            return

        # Get or create a system user for audit trail
        user, _ = User.objects.get_or_create(
            username='system',
            defaults={
                'is_staff': False,
                'is_superuser': False,
            }
        )

        with transaction.atomic():
            if zero_all:
                stocks = BakeryProductStock.objects.select_related('product').select_for_update()
            else:
                stocks = BakeryProductStock.objects.select_related('product').filter(
                    product__name__in=products
                ).select_for_update()

            if not stocks.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f'No matching products found for: {products}'
                    )
                )
                return

            zeroed_count = 0
            for stock in stocks:
                old_qty = stock.quantity

                if old_qty == Decimal('0.000'):
                    self.stdout.write(
                        f'  Skipping {stock.product.name} - already zero'
                    )
                    continue

                # Update stock to zero
                stock.quantity = Decimal('0.000')
                stock.save(update_fields=['quantity'])

                # Create audit trail
                InventoryRevisionReport.objects.create(
                    item_type='product',
                    product=stock.product,
                    old_quantity=old_qty,
                    new_quantity=Decimal('0.000'),
                    note=note,
                    user=user
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Zeroed {stock.product.name}: {old_qty} → 0.000'
                    )
                )
                zeroed_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully zeroed {zeroed_count} product(s)'
                )
            )
