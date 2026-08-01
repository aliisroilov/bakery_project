from django.db import migrations, models

# Categories that are owner draws rather than operating costs. Flipped onto the
# post-Op. foyda "Harajatlar" line; requested by the owner 2026-08-01.
OWNER_DRAW_CATEGORIES = ["Rizoxon", "Bahodir"]


def flag_owner_draws(apps, schema_editor):
    ExpenseCategory = apps.get_model("finance", "ExpenseCategory")
    ExpenseCategory.objects.filter(name__in=OWNER_DRAW_CATEGORIES).update(
        below_op_profit=True, include_in_pnl=True
    )


def unflag_owner_draws(apps, schema_editor):
    ExpenseCategory = apps.get_model("finance", "ExpenseCategory")
    ExpenseCategory.objects.filter(name__in=OWNER_DRAW_CATEGORIES).update(
        below_op_profit=False
    )


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0005_expensecategory_include_in_pnl"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="exchange_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="1 USD = ? UZS. Faqat USD kirim uchun.",
                max_digits=16,
            ),
        ),
        migrations.AddField(
            model_name="expensecategory",
            name="below_op_profit",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Yoqilsa, bu kategoriya Xarajatlar emas, Op. foydadan keyingi "
                    "Harajatlar qatoriga tushadi."
                ),
                verbose_name="Harajatlar (Op. foydadan keyin)",
            ),
        ),
        migrations.RunPython(flag_owner_draws, unflag_owner_draws),
    ]
