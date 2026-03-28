from django.db import models
from django.contrib.postgres.fields import ArrayField

class AuthorizedApps(models.Model):
    app_name = models.CharField(max_length=255)
    api_key = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


class User(models.Model):

    class PermissionFlags(models.IntegerChoices):
        ADMIN = 1, 'Admin'
        PREMIUM = 2, 'Premium'
        BASIC = 3, 'Basic'


    platform_id = models.CharField(primary_key=True, max_length=150)
    permissions = ArrayField(models.IntegerField(choices=PermissionFlags), blank=True, default=list)
    created_at = models.DateTimeField(auto_now_add=True)

class Message(models.Model):
    id = models.BigIntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

