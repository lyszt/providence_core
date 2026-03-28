import django.contrib.postgres.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("platform_id", models.CharField(max_length=150, primary_key=True, serialize=False)),
                (
                    "permissions",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.IntegerField(
                            choices=[(1, "Admin"), (2, "Premium"), (3, "Basic")]
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigIntegerField(primary_key=True, serialize=False)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="authentication.user",
                    ),
                ),
                ("content", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
