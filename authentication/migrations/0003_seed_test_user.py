from django.db import migrations


def create_test_user(apps, schema_editor):
    User = apps.get_model("authentication", "User")
    User.objects.get_or_create(
        platform_id="test:test",
        defaults={"permissions": [3]},  # 3 = BASIC
    )


def remove_test_user(apps, schema_editor):
    User = apps.get_model("authentication", "User")
    User.objects.filter(platform_id="test:test").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0002_user_message"),
    ]

    operations = [
        migrations.RunPython(create_test_user, remove_test_user),
    ]
