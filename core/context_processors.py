from notifications.models import Notification

def unread_notifications_count(request):
    if request.user.is_authenticated:
        return {'unread_notif_count': request.user.notifications.filter(is_read=False).count()}
    return {'unread_notif_count': 0}
