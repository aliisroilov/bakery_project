# Generated migration

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('salary', '0003_salaryrate_initial_balance'),
    ]

    operations = [
        migrations.AddField(
            model_name='salaryrate',
            name='production_start_date',
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Only count production from this date forward. Leave blank to count all production."
            ),
        ),
    ]
