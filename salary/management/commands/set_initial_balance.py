from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from users.models import User
from salary.models import SalaryRate


class Command(BaseCommand):
    help = 'Set initial salary balance for employees (pre-system debt)'

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            type=str,
            help='Username of the employee'
        )
        parser.add_argument(
            'amount',
            type=str,
            help='Initial balance amount (can be negative for debt)'
        )
        parser.add_argument(
            '--rate',
            type=str,
            help='Salary rate (optional, if SalaryRate does not exist)',
            default='0'
        )
        parser.add_argument(
            '--rate-type',
            type=str,
            choices=['per_qop', 'per_week', 'fixed'],
            help='Rate type (optional, if SalaryRate does not exist)',
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

        username = options['username']
        amount = options['amount']
        rate = options['rate']
        rate_type = options['rate_type']

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
                salary_rate.initial_balance = amount_decimal
                salary_rate.save(update_fields=['initial_balance'])

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Updated initial balance for {username}:\n'
                        f'  Old: {old_balance:,}\n'
                        f'  New: {amount_decimal:,}\n'
                        f'  Rate: {salary_rate.rate} ({salary_rate.rate_type})'
                    )
                )
            else:
                # Created new record
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created SalaryRate for {username}:\n'
                        f'  Initial balance: {amount_decimal:,}\n'
                        f'  Rate: {rate_decimal} ({rate_type})'
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
