from datetime import date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from users.models import User
from salary.models import SalaryRate


class Command(BaseCommand):
    help = '''Set production start date for employees

    This sets a cutoff date - only production/work FROM this date will be counted.
    Use this when initial_balance already includes past work, so you don't double-count.

    Examples:
        # Set to today (only count future production)
        python manage.py set_production_start Umarxon

        # Set to specific date
        python manage.py set_production_start Umarxon 2025-11-26

        # Clear production start date (count ALL production)
        python manage.py set_production_start Umarxon --clear
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            type=str,
            help='Username of the employee'
        )
        parser.add_argument(
            'start_date',
            nargs='?',
            type=str,
            help='Start date (YYYY-MM-DD). Defaults to today.'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear the production start date (count all production)'
        )

    def handle(self, *args, **options):
        username = options['username']
        start_date_str = options.get('start_date')
        clear = options['clear']

        # Get user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        # Get SalaryRate
        try:
            sr = user.salary_rate
        except SalaryRate.DoesNotExist:
            raise CommandError(f'No SalaryRate configured for {username}')

        self.stdout.write(self.style.WARNING('\n' + '='*70))
        self.stdout.write(self.style.WARNING(f'SETTING PRODUCTION START DATE FOR: {username}'))
        self.stdout.write(self.style.WARNING('='*70 + '\n'))

        # Show current state
        self.stdout.write(f'Current configuration:')
        self.stdout.write(f'  Rate: {sr.rate:,} ({sr.get_rate_type_display()})')
        self.stdout.write(f'  Initial Balance: {sr.initial_balance:,}')
        self.stdout.write(f'  Current Production Start: {sr.production_start_date or "None (counts all production)"}')
        self.stdout.write('')

        if clear:
            # Clear the date
            sr.production_start_date = None
            sr.save(update_fields=['production_start_date'])

            self.stdout.write(self.style.SUCCESS('✓ Cleared production start date'))
            self.stdout.write(self.style.WARNING('  Now counting ALL production from the beginning'))

        else:
            # Set the date
            if start_date_str:
                try:
                    start_date = date.fromisoformat(start_date_str)
                except ValueError:
                    raise CommandError(f'Invalid date format: {start_date_str}. Use YYYY-MM-DD')
            else:
                start_date = date.today()

            old_date = sr.production_start_date
            sr.production_start_date = start_date
            sr.save(update_fields=['production_start_date'])

            self.stdout.write(self.style.SUCCESS(f'✓ Set production start date: {start_date}'))
            self.stdout.write(f'  Old: {old_date or "None"}')
            self.stdout.write(f'  New: {start_date}')
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(f'  Only production FROM {start_date} will be counted'))

        # Show verification
        from salary.utils import calculate_auto_salary

        total_earned = calculate_auto_salary(user)
        auto_calc = total_earned - sr.initial_balance

        self.stdout.write('')
        self.stdout.write('='*70)
        self.stdout.write(self.style.SUCCESS('VERIFICATION:'))
        self.stdout.write(f'  Initial Balance: {sr.initial_balance:,}')
        self.stdout.write(f'  Auto-calculated (from production): {auto_calc:,}')
        self.stdout.write(f'  Total Balance: {total_earned:,}')
        self.stdout.write('='*70 + '\n')

        if auto_calc == 0:
            self.stdout.write(self.style.SUCCESS('🎉 Perfect! Balance = Initial Balance only'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️  Auto-calculated is {auto_calc:,} (production from {sr.production_start_date or "beginning"})'))
