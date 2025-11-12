from .models import Item, Notification

def low_stock_items(request):
    """Add low stock items to the context for all templates"""
    if request.user.is_authenticated:
        items = Item.objects.filter(
            owner=request.user,
            quantity__lt=10
        ).order_by('quantity')[:10]  # Limit to 10 items
        return {'low_stock_items': items}
    return {'low_stock_items': []}


def unread_notifications(request):
    """Add unread notifications count and recent notifications to context"""
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()

        recent_notifications = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).order_by('-created_at')[:5]  # Last 5 unread

        return {
            'unread_notifications_count': unread_count,
            'recent_notifications': recent_notifications,
        }
    return {
        'unread_notifications_count': 0,
        'recent_notifications': [],
    }
