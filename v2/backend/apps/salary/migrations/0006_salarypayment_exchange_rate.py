from django.db import migrations, models

DEFAULT_USD_RATE = 12000


def backfill_usd_rate(apps, schema_editor):
    SalaryPayment = apps.get_model("salary", "SalaryPayment")
    SalaryPayment.objects.filter(currency="USD", exchange_rate=0).update(
        exchange_rate=DEFAULT_USD_RATE
    )


def clear_usd_rate(apps, schema_editor):
    SalaryPayment = apps.get_model("salary", "SalaryPayment")
    SalaryPayment.objects.filter(currency="USD").update(exchange_rate=0)


class Migration(migrations.Migration):

    dependencies = [
        ("salary", "0005_salaryrate_week_start_day"),
    ]

    operations = [
        migrations.AddField(
            model_name="salarypayment",
            name="exchange_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="1 USD = ? UZS. Faqat USD to'lov uchun.",
                max_digits=16,
            ),
        ),
        migrations.RunPython(backfill_usd_rate, clear_usd_rate),
    ]
