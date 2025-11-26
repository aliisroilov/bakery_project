from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from users.models import User
from salary.models import SalaryRate


class Command(BaseCommand):
    help = '''Set initial salary balance for employees (pre-system debt)

    Examples:
        python manage.py set_initial_balance Umarxon 3210000
        python manage.py set_initial_balance Ali 500000 --rate 150000 --rate-type per_week
        python manage.py set_initial_balance --list
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            nargs='?',  # Make optional when using --list
            type=str,
            help='Username of the employee'
        )
        parser.add_argument(
            'amount',
            nargs='?',  # Make optional when using --list
            type=str,
            help='INITIAL BALANCE amount (pre-system debt, can be negative)'
        )
        parser.add_argument(
            '--rate',
            type=str,
            help='SALARY RATE (not initial balance!) - only used when creating new SalaryRate',
            default='0'
        )
        parser.add_argument(
            '--rate-type',
            type=str,
            choices=['per_qop', 'per_week', 'fixed'],
            help='Rate type - only used when creating new SalaryRate (default: fixed)',
            default='fixed'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all employees and their current balances'
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_employees()
            return

        username = options.get('username')
        amount = options.get('amount')
        rate = options['rate']
        rate_type = options['rate_type']

        # Validate required arguments
        if not username or not amount:
            raise CommandError(
                'Both username and amount are required.\n'
                'Usage: python manage.py set_initial_balance <username> <amount>\n'
                'Example: python manage.py set_initial_balance Umarxon 3210000'
            )

        try:
            amount_decimal = Decimal(amount)
        except Exception as e:
            raise CommandError(f'Invalid amount: {amount}. Error: {e}')

        try:
            rate_decimal = Decimal(rate)
        except Exception as e:
            raise CommandError(f'Invalid rate: {rate}. Error: {e}')

        # Get the user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        # Show what will be done
        self.stdout.write(
            self.style.WARNING(
                f'\n📝 Setting initial balance for {username}:\n'
                f'   Initial Balance: {amount_decimal:,}\n'
                f'   Rate: {rate_decimal} ({rate_type})\n'
            )
        )

        # Get or create SalaryRate
        with transaction.atomic():
            salary_rate, created = SalaryRate.objects.get_or_create(
                user=user,
                defaults={
                    'rate': rate_decimal,
                    'rate_type': rate_type,
                    'initial_balance': amount_decimal
                }
            )

            if not created:
                # Update existing record
                old_balance = salary_rate.initial_balance
                old_rate = salary_rate.rate
                old_rate_type = salary_rate.rate_type

                salary_rate.initial_balance = amount_decimal
                salary_rate.save(update_fields=['initial_balance'])

                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✓ Updated initial balance for {username}:\n'
                        f'  Initial Balance: {old_balance:,} → {amount_decimal:,}\n'
                        f'  Rate: {old_rate:,} ({old_rate_type}) [unchanged]\n'
                    )
                )
            else:
                # Created new record
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✓ Created NEW SalaryRate for {username}:\n'
                        f'  Initial balance: {amount_decimal:,}\n'
                        f'  Rate: {rate_decimal} ({rate_type})\n'
                    )
                )

    def list_employees(self):
        """List all employees and their salary information"""
        from salary.utils import calculate_auto_salary
        from salary.models import SalaryPayment
        from django.db.models import Sum

        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('EMPLOYEE SALARY OVERVIEW'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        employees = User.objects.filter(role__in=['nonvoy', 'driver']).order_by('username')

        if not employees.exists():
            self.stdout.write(self.style.WARNING('No employees found (nonvoy/driver roles)'))
            return

        for user in employees:
            try:
                salary_rate = user.salary_rate
                has_rate = True
            except SalaryRate.DoesNotExist:
                has_rate = False
                salary_rate = None

            self.stdout.write(f'\n👤 {user.username} ({user.get_role_display()})')
            self.stdout.write('─' * 60)

            if has_rate:
                # Calculate earnings
                total_earned = calculate_auto_salary(user)

                # Calculate payments
                total_paid = user.salary_payments.aggregate(
                    total=Sum('amount')
                )['total'] or Decimal('0.00')

                # Calculate balance
                balance = total_earned - total_paid

                self.stdout.write(f'  Rate: {salary_rate.rate:,} ({salary_rate.get_rate_type_display()})')
                self.stdout.write(f'  Initial balance: {salary_rate.initial_balance:,}')
                self.stdout.write(f'  Total earned: {total_earned:,}')
                self.stdout.write(f'  Total paid: {total_paid:,}')

                if balance > 0:
                    self.stdout.write(self.style.SUCCESS(f'  Balance due: {balance:,} (owe employee)'))
                elif balance < 0:
                    self.stdout.write(self.style.ERROR(f'  Balance due: {balance:,} (employee owes)'))
                else:
                    self.stdout.write(f'  Balance due: {balance:,} (settled)')
            else:
                self.stdout.write(self.style.WARNING('  ⚠ No SalaryRate configured'))

        self.stdout.write('\n' + '='*80 + '\n')
