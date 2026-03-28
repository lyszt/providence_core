from django.db import migrations


def create_discord_user(apps, schema_editor):
    User = apps.get_model("authentication", "User")
    User.objects.get_or_create(
        platform_id="discord:ryujinni",
        defaults={"permissions": [1, 2, 3]},  # Admin
    )


def create_discord_kaldwin_user(apps, schema_editor):
    User = apps.get_model("authentication", "User")
    User.objects.get_or_create(
        platform_id="discord:fauxkaldwin",
        defaults={"permissions": [1, 2, 3]},  # Admin
    )

def remove_discord_user(apps, schema_editor):
    User = apps.get_model("authentication", "User")
    User.objects.filter(platform_id="discord:ryujinni").delete()


def remove_discord_kaldwin_user(apps, schema_editor):
    User = apps.get_model("authentication", "User")
    User.objects.filter(platform_id="discord:fauxkaldwin").delete()



class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0003_seed_test_user"),
    ]

    operations = [
        migrations.RunPython(create_discord_user, remove_discord_user),
        migrations.RunPython(create_discord_kaldwin_user, remove_discord_kaldwin_user)
    ]
