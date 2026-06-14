from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0003_production_group_alter_production_nonvoy"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryrevisionreport",
            name="batch_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
