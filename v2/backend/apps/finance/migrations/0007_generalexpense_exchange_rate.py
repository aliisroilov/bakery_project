from django.db import migrations, models

# Every USD expense on record predates the field. They were booked around the
# 12 000 UZS/USD mark (see KassaExchange history: 11 920 – 12 050), which is also
# DEFAULT_USD_RATE — stamp it so the P&L restates them instead of dropping them.
DEFAULT_USD_RATE = 12000


def backfill_usd_rate(apps, schema_editor):
    GeneralExpense = apps.get_model("finance", "GeneralExpense")
    GeneralExpense.objects.filter(currency="USD", exchange_rate=0).update(
        exchange_rate=DEFAULT_USD_RATE
    )


def clear_usd_rate(apps, schema_editor):
    GeneralExpense = apps.get_model("finance", "GeneralExpense")
    GeneralExpense.objects.filter(currency="USD").update(exchange_rate=0)


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0006_payment_exchange_rate_and_below_op_profit"),
    ]

    operations = [
        migrations.AddField(
            model_name="generalexpense",
            name="exchange_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="1 USD = ? UZS. Faqat USD xarajat uchun.",
                max_digits=16,
            ),
        ),
        migrations.RunPython(backfill_usd_rate, clear_usd_rate),
    ]
