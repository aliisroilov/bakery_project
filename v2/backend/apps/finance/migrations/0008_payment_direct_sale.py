from django.db import migrations, models


class Migration(migrations.Migration):
    """New kirim type "Buyurtmasiz sotuv" — choices only, no schema change."""

    dependencies = [
        ("finance", "0007_generalexpense_exchange_rate"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="payment_type",
            field=models.CharField(
                choices=[
                    ("collection", "Kirim (delivery payment)"),
                    ("loan_repayment", "Qarz to'lovi"),
                    ("other", "Boshqa"),
                    ("direct_sale", "Buyurtmasiz sotuv"),
                ],
                default="collection",
                max_length=20,
            ),
        ),
    ]
