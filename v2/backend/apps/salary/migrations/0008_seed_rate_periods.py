"""Seed one SalaryRatePeriod per existing SalaryRate, effective from the epoch
(2000-01-01) at the current rate. This makes the rate timeline cover all of
history at today's rate, so calculate_earned returns exactly what it did before
effective-dated rates existed — only FUTURE rate changes append new periods and
diverge. reset_date stays an independent floor applied at calc time."""
from datetime import date

from django.db import migrations


def seed(apps, schema_editor):
    SalaryRate = apps.get_model("salary", "SalaryRate")
    SalaryRatePeriod = apps.get_model("salary", "SalaryRatePeriod")
    EPOCH = date(2000, 1, 1)
    for r in SalaryRate.objects.all():
        SalaryRatePeriod.objects.get_or_create(
            user_id=r.user_id,
            effective_from=EPOCH,
            defaults=dict(
                rate_type=r.rate_type,
                currency=r.currency,
                rate=r.rate,
                week_start_day=r.week_start_day,
            ),
        )


def unseed(apps, schema_editor):
    SalaryRatePeriod = apps.get_model("salary", "SalaryRatePeriod")
    SalaryRatePeriod.objects.filter(effective_from=date(2000, 1, 1)).delete()


class Migration(migrations.Migration):
    dependencies = [("salary", "0007_salaryrateperiod")]
    operations = [migrations.RunPython(seed, unseed)]
