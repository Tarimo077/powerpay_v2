from notifications.models import Notification

def unread_notifications_count(request):
    if request.user.is_authenticated:
        return {'unread_notif_count': request.user.notifications.filter(is_read=False).count()}
    return {'unread_notif_count': 0}

def user_roles(request):
    user = request.user

    return {
        "is_superuser": user.is_authenticated and user.is_superuser,
        "is_admin": user.is_authenticated and (
            user.is_superuser or getattr(user, "role", None) == "admin"
        ),
        "user_org": getattr(user, "organization", None),
    }
