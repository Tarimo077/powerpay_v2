from .models import Notification

def notify(user, title, message, type="info"):
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        type=type
    )
