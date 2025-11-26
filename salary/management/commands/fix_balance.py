from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum
from users.models import User
from salary.models import SalaryRate, SalaryPayment
from salary.utils import calculate_auto_salary


class Command(BaseCommand):
    help = '''Fix employee balance by removing auto-calculation and payments

    This command:
    1. Deletes all payment records for the employee
    2. Sets rate to 0 to prevent auto-calculation
    3. Sets rate_type to 'fixed'
    4. Keeps only the initial balance

    Use this when you want balance to show ONLY the initial balance amount.

    Examples:
        python manage.py fix_balance Umarxon 3210000
        python manage.py fix_balance Ziyoxon 260000
        python manage.py fix_balance --all  (fix all employees)
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            nargs='?',
            type=str,
            help='Username of the employee'
        )
        parser.add_argument(
            'initial_balance',
            nargs='?',
            type=str,
            help='Initial balance amount (will show as final balance)'
        )
        parser.add_argument(
            '--keep-payments',
            action='store_true',
            help='Keep existing payment records (not recommended)'
        )
        parser.add_argument(
            '--keep-rate',
            action='store_true',
            help='Keep existing rate (not recommended, will auto-calculate)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Fix all nonvoy/driver employees'
        )

    def handle(self, *args, **options):
        if options['all']:
            self.fix_all_employees()
            return

        username = options.get('username')
        initial_balance = options.get('initial_balance')

        if not username or not initial_balance:
            raise CommandError(
                'Both username and initial_balance are required.\n'
                'Usage: python manage.py fix_balance <username> <amount>\n'
                'Example: python manage.py fix_balance Umarxon 3210000'
            )

        try:
            initial_balance_decimal = Decimal(initial_balance)
        except Exception as e:
            raise CommandError(f'Invalid amount: {initial_balance}. Error: {e}')

        self.fix_employee(
            username=username,
            initial_balance=initial_balance_decimal,
            delete_payments=not options['keep_payments'],
            set_rate_to_zero=not options['keep_rate']
        )

    def fix_employee(self, username, initial_balance, delete_payments=True, set_rate_to_zero=True):
        """Fix a single employee's balance"""

        # Get user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        self.stdout.write(self.style.WARNING('\n' + '='*70))
        self.stdout.write(self.style.WARNING(f'FIXING BALANCE FOR: {username}'))
        self.stdout.write(self.style.WARNING('='*70 + '\n'))

        # Get or create SalaryRate
        try:
            sr = user.salary_rate
            self.stdout.write(f'📊 Current configuration:')
            self.stdout.write(f'   Initial Balance: {sr.initial_balance:,}')
            self.stdout.write(f'   Rate: {sr.rate:,} ({sr.get_rate_type_display()})')
        except SalaryRate.DoesNotExist:
            sr = SalaryRate.objects.create(
                user=user,
                rate=Decimal('0'),
                rate_type='fixed',
                initial_balance=initial_balance
            )
            self.stdout.write(self.style.SUCCESS('✓ Created new SalaryRate'))

        with transaction.atomic():
            # Delete payments
            if delete_payments:
                payments = SalaryPayment.objects.filter(user=user)
                payment_count = payments.count()
                total_paid = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

                if payment_count > 0:
                    self.stdout.write(f'\n💸 Found {payment_count} payment(s) totaling {total_paid:,}:')
                    for p in payments:
                        self.stdout.write(f'   - {p.created_at.strftime("%Y-%m-%d")}: {p.amount:,}')
                        if p.note:
                            self.stdout.write(f'     Note: {p.note}')

                    payments.delete()
                    self.stdout.write(self.style.SUCCESS(f'✓ Deleted all payments'))
                else:
                    self.stdout.write(f'\n💸 No payments to delete')

            # Set rate to zero
            if set_rate_to_zero:
                old_rate = sr.rate
                old_type = sr.rate_type
                sr.rate = Decimal('0')
                sr.rate_type = 'fixed'

                self.stdout.write(f'\n⚙️  Setting rate to 0 (fixed):')
                self.stdout.write(f'   Old: {old_rate:,} ({old_type})')
                self.stdout.write(f'   New: 0 (fixed)')

            # Set initial balance
            old_balance = sr.initial_balance
            sr.initial_balance = initial_balance
            sr.save()

            self.stdout.write(f'\n💰 Setting initial balance:')
            self.stdout.write(f'   Old: {old_balance:,}')
            self.stdout.write(f'   New: {sr.initial_balance:,}')

        # Verify
        total_earned = calculate_auto_salary(user)
        total_paid = user.salary_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        balance = total_earned - total_paid

        self.stdout.write(f'\n{"="*70}')
        self.stdout.write(self.style.SUCCESS('✅ FINAL RESULT:'))
        self.stdout.write(f'   Initial Balance: {sr.initial_balance:,}')
        self.stdout.write(f'   Auto-calculated: {total_earned - sr.initial_balance:,}')
        self.stdout.write(f'   Total Earned: {total_earned:,}')
        self.stdout.write(f'   Total Paid: {total_paid:,}')

        if balance == sr.initial_balance:
            self.stdout.write(self.style.SUCCESS(f'   BALANCE DUE: {balance:,} ✓'))
            self.stdout.write(self.style.SUCCESS(f'\n🎉 SUCCESS! Balance equals initial balance'))
        else:
            self.stdout.write(f'   BALANCE DUE: {balance:,}')
            self.stdout.write(self.style.WARNING(f'\n⚠️  WARNING: Balance != Initial Balance'))

        self.stdout.write('='*70 + '\n')

    def fix_all_employees(self):
        """Fix all employees with the pattern of having payments and auto-calculated earnings"""
        self.stdout.write(self.style.WARNING('\n' + '='*70))
        self.stdout.write(self.style.WARNING('FIX ALL EMPLOYEES'))
        self.stdout.write(self.style.WARNING('='*70 + '\n'))

        employees = User.objects.filter(role__in=['nonvoy', 'driver'])

        self.stdout.write(f'Found {employees.count()} employees\n')

        for user in employees:
            try:
                sr = user.salary_rate
                total_earned = calculate_auto_salary(user)
                auto_calc = total_earned - sr.initial_balance
                payments = SalaryPayment.objects.filter(user=user)

                if auto_calc > 0 or payments.exists():
                    self.stdout.write(f'\n{user.username}:')
                    self.stdout.write(f'  Initial: {sr.initial_balance:,}')
                    self.stdout.write(f'  Auto-calc: {auto_calc:,}')
                    self.stdout.write(f'  Payments: {payments.count()}')

                    # Ask to fix
                    response = input(f'  Fix this employee? (y/n): ')
                    if response.lower() == 'y':
                        self.fix_employee(
                            username=user.username,
                            initial_balance=sr.initial_balance,
                            delete_payments=True,
                            set_rate_to_zero=True
                        )
            except SalaryRate.DoesNotExist:
                self.stdout.write(f'{user.username}: No SalaryRate (skipping)')

        self.stdout.write(self.style.SUCCESS('\n✅ All done!'))
