from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum
from users.models import User
from salary.models import SalaryRate, SalaryPayment
from salary.utils import calculate_auto_salary


class Command(BaseCommand):
    help = 'Check detailed salary balance breakdown for an employee'

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            type=str,
            help='Username of the employee to check'
        )

    def handle(self, *args, **options):
        username = options['username']

        # Get the user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS(f'SALARY BALANCE BREAKDOWN FOR: {username}'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

        # Check if SalaryRate exists
        try:
            salary_rate = user.salary_rate
        except SalaryRate.DoesNotExist:
            self.stdout.write(self.style.ERROR('❌ No SalaryRate configured for this user!\n'))
            return

        # Show SalaryRate details
        self.stdout.write(self.style.WARNING('📊 SALARY RATE CONFIGURATION:'))
        self.stdout.write(f'   Rate: {salary_rate.rate:,}')
        self.stdout.write(f'   Rate Type: {salary_rate.get_rate_type_display()}')
        self.stdout.write(f'   Initial Balance: {salary_rate.initial_balance:,}')
        if salary_rate.notes:
            self.stdout.write(f'   Notes: {salary_rate.notes}')
        self.stdout.write('')

        # Calculate auto earnings
        total_earned = calculate_auto_salary(user)
        auto_calculated = total_earned - salary_rate.initial_balance

        self.stdout.write(self.style.WARNING('💰 EARNINGS BREAKDOWN:'))
        self.stdout.write(f'   Initial Balance (pre-system): {salary_rate.initial_balance:,}')
        self.stdout.write(f'   Auto-calculated Earnings:     {auto_calculated:,}')
        self.stdout.write(f'   ' + '-'*50)
        self.stdout.write(f'   TOTAL EARNED:                 {total_earned:,}')
        self.stdout.write('')

        # Show all payments
        payments = SalaryPayment.objects.filter(user=user).order_by('created_at')
        total_paid = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        self.stdout.write(self.style.WARNING(f'💸 PAYMENT HISTORY ({payments.count()} payments):'))
        if payments.exists():
            for i, payment in enumerate(payments, 1):
                self.stdout.write(
                    f'   {i}. {payment.created_at.strftime("%Y-%m-%d %H:%M")} - '
                    f'{payment.amount:,} sum'
                    f'{" (PENDING)" if not payment.processed else ""}'
                )
                if payment.note:
                    self.stdout.write(f'      Note: {payment.note}')
        else:
            self.stdout.write('   No payments yet')

        self.stdout.write(f'   ' + '-'*50)
        self.stdout.write(f'   TOTAL PAID:                   {total_paid:,}')
        self.stdout.write('')

        # Calculate balance
        balance = total_earned - total_paid

        self.stdout.write(self.style.WARNING('🧮 BALANCE CALCULATION:'))
        self.stdout.write(f'   Total Earned:  {total_earned:,}')
        self.stdout.write(f'   Total Paid:    {total_paid:,}')
        self.stdout.write(f'   ' + '-'*50)

        if balance > 0:
            self.stdout.write(
                self.style.SUCCESS(f'   BALANCE DUE:   {balance:,} (you OWE employee)')
            )
        elif balance < 0:
            self.stdout.write(
                self.style.ERROR(f'   BALANCE DUE:   {balance:,} (employee OVERPAID)')
            )
        else:
            self.stdout.write(f'   BALANCE DUE:   {balance:,} (settled)')

        self.stdout.write('\n' + '='*70 + '\n')

        # Show how to fix common issues
        if balance != salary_rate.initial_balance and total_paid == Decimal('0.00'):
            self.stdout.write(self.style.WARNING('⚠️  NOTICE:'))
            self.stdout.write(f'   Balance ({balance:,}) differs from initial balance ({salary_rate.initial_balance:,})')
            self.stdout.write(f'   This means there are auto-calculated earnings of {auto_calculated:,}')
            self.stdout.write('')

        if total_paid > 0 and balance < salary_rate.initial_balance:
            self.stdout.write(self.style.WARNING('💡 POSSIBLE ISSUE:'))
            self.stdout.write(f'   Balance ({balance:,}) is less than initial balance ({salary_rate.initial_balance:,})')
            self.stdout.write(f'   There are {payments.count()} payment(s) totaling {total_paid:,}')
            self.stdout.write('')
            self.stdout.write('   To remove incorrect payments:')
            self.stdout.write('   1. Go to: /admin/salary/salarypayment/')
            self.stdout.write(f'   2. Find payments for {username}')
            self.stdout.write('   3. Delete incorrect payments')
            self.stdout.write('   OR use Django shell:')
            self.stdout.write(f'      python manage.py shell -c "from salary.models import SalaryPayment; SalaryPayment.objects.filter(user__username=\'{username}\').delete()"')
            self.stdout.write('')
