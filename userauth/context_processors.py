from .models import Notification

def notifications(request):
    unread_count = 0
    unread_notifications = []
    if request.user.is_authenticated:
        unread_notifications = request.user.notifications.filter(read=False).order_by('-created_at')[:10]
        unread_count = unread_notifications.count()
    return {
        'unread_notifications': unread_notifications,
        'unread_count': unread_count
    }