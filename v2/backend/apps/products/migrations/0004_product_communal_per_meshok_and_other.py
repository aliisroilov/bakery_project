from django.db import migrations, models


class Migration(migrations.Migration):
    """Communal cost is now per meshok (qop) — rename to preserve existing values —
    plus a new per-meshok 'other' (boshqa) cost. Both fold into tan narxi."""

    dependencies = [
        ("products", "0003_product_communal_cost_per_unit_uzs"),
    ]

    operations = [
        migrations.RenameField(
            model_name="product",
            old_name="communal_cost_per_unit_uzs",
            new_name="communal_cost_per_meshok_uzs",
        ),
        migrations.AlterField(
            model_name="product",
            name="communal_cost_per_meshok_uzs",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=16,
                help_text="Kommunal (gaz/svet) — 1 qop (meshok) uchun, so'm. Tan narxiga qo'shiladi.",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="other_cost_per_meshok_uzs",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=16,
                help_text="Boshqa xarajat — 1 qop (meshok) uchun, so'm. Tan narxiga qo'shiladi.",
            ),
        ),
    ]
