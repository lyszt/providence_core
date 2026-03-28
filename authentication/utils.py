from rest_framework import status
from rest_framework.response import Response

from .models import User


def authorize(username: str, permission: int = User.PermissionFlags.BASIC):
    """
    Validates username format (context:identifier) and checks the required permission.
    Returns None if authorized, or a Response on failure.
    """
    if not username or ":" not in username or username.startswith(":") or username.endswith(":"):
        return Response({"error": "No username provided."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(platform_id=username)
        if permission not in user.permissions:
            raise User.DoesNotExist
    except User.DoesNotExist:
        return Response({"response": "Sorry, I can't talk to you."}, status=status.HTTP_403_FORBIDDEN)
    return None
