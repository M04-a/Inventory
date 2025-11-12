"""
Django signals for automatic notification creation
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Item, Delivery, MoveRequest, Notification, NotificationSettings


@receiver(post_save, sender='auth.User')
def create_notification_settings(sender, instance, created, **kwargs):
    """Create notification settings for new users"""
    if created:
        NotificationSettings.objects.create(user=instance)


@receiver(post_save, sender=Item)
def check_low_stock(sender, instance, created, **kwargs):
    """Create notification when item stock is low"""
    if not created:  # Only for updates, not new items
        try:
            settings = instance.owner.notification_settings
        except NotificationSettings.DoesNotExist:
            # Create settings if they don't exist
            settings = NotificationSettings.objects.create(user=instance.owner)

        if not settings.enable_low_stock_alerts:
            return

        # Check if stock is below threshold
        if instance.quantity <= settings.low_stock_threshold and instance.quantity > 0:
            # Check if we already have a recent notification for this item
            recent_notification = Notification.objects.filter(
                user=instance.owner,
                item=instance,
                type='low_stock',
                is_read=False
            ).first()

            if not recent_notification:
                # Determine if it's critical
                level = "CRITICAL" if instance.quantity <= settings.critical_stock_threshold else "LOW"

                Notification.objects.create(
                    user=instance.owner,
                    type='low_stock',
                    title=f'{level} Stock Alert: {instance.name}',
                    message=f'Item "{instance.name}" (SKU: {instance.sku}) has only {instance.quantity} units remaining in stock.',
                    item=instance
                )


@receiver(post_save, sender=Delivery)
def notify_delivery_status_change(sender, instance, created, **kwargs):
    """Create notification when delivery status changes"""
    # Get user from created_by username
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        user = User.objects.get(username=instance.created_by)
    except User.DoesNotExist:
        return

    try:
        settings = user.notification_settings
    except NotificationSettings.DoesNotExist:
        settings = NotificationSettings.objects.create(user=user)

    if not settings.enable_delivery_alerts:
        return

    if created:
        # New delivery created
        Notification.objects.create(
            user=user,
            type='delivery_created',
            title=f'Delivery Created: {instance.item.name}',
            message=f'Delivery #{instance.id} created for {instance.quantity} units of "{instance.item.name}" from {instance.from_city}.',
            item=instance.item,
            delivery=instance
        )
    else:
        # Delivery updated - check status changes
        if instance.status == 'finished':
            # Check if we already have a notification for this
            existing = Notification.objects.filter(
                user=user,
                delivery=instance,
                type='delivery_finished'
            ).first()

            if not existing:
                Notification.objects.create(
                    user=user,
                    type='delivery_finished',
                    title=f'Delivery Completed: {instance.item.name}',
                    message=f'Delivery #{instance.id} of {instance.quantity} units of "{instance.item.name}" has been successfully completed.',
                    item=instance.item,
                    delivery=instance
                )

        elif instance.status == 'cancelled':
            existing = Notification.objects.filter(
                user=user,
                delivery=instance,
                type='delivery_cancelled'
            ).first()

            if not existing:
                Notification.objects.create(
                    user=user,
                    type='delivery_cancelled',
                    title=f'Delivery Cancelled: {instance.item.name}',
                    message=f'Delivery #{instance.id} of {instance.quantity} units of "{instance.item.name}" has been cancelled. Stock has been restored.',
                    item=instance.item,
                    delivery=instance
                )


@receiver(post_save, sender=MoveRequest)
def notify_item_moved(sender, instance, created, **kwargs):
    """Create notification when item is moved"""
    if created:
        user = instance.item.owner

        try:
            settings = user.notification_settings
        except NotificationSettings.DoesNotExist:
            settings = NotificationSettings.objects.create(user=user)

        if not settings.enable_move_alerts:
            return

        Notification.objects.create(
            user=user,
            type='item_moved',
            title=f'Item Moved: {instance.item.name}',
            message=f'Item "{instance.item.name}" has been moved from {instance.from_city}/{instance.from_building} to {instance.to_city}/{instance.to_building}.',
            item=instance.item
        )

