from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0003_bakerybalance_update_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchase",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
