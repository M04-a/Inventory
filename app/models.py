from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from .utils import normalize_city_name


class CityManager(models.Manager):
    """Custom manager for City that normalizes names in get_or_create"""

    def get_or_create(self, defaults=None, **kwargs):
        if 'name' in kwargs:
            kwargs['name'] = normalize_city_name(kwargs['name'])
        return super().get_or_create(defaults=defaults, **kwargs)

    def get(self, *args, **kwargs):
        if 'name' in kwargs:
            kwargs['name'] = normalize_city_name(kwargs['name'])
        return super().get(*args, **kwargs)


class City(models.Model):
    name = models.CharField(max_length=100, unique=True)

    objects = CityManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Normalize city name before saving (remove diacritics)
        if self.name:
            self.name = normalize_city_name(self.name)
        super().save(*args, **kwargs)


class Building(models.Model):
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="buildings")
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True, default="")
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        unique_together = ("city", "name")
        ordering = ["city__name", "name"]

    def __str__(self):
        return f"{self.name} ({self.city.name})"


class Item(models.Model):
    owner = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=100)
    sku = models.CharField(max_length=100)
    quantity = models.IntegerField(default=0)
    city = models.CharField(max_length=100, blank=True, default="")
    building = models.CharField(max_length=100, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    building_ref = models.ForeignKey(
        Building, on_delete=models.PROTECT, related_name="items",
        null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "sku"], name="uniq_owner_sku")
        ]
        indexes = [
            models.Index(fields=["owner", "sku"]),
            models.Index(fields=["city"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def full_address(self):
        if self.building_ref_id:
            parts = [
                self.building_ref.address or "",
                self.building_ref.name,
                self.building_ref.city.name,
                "Romania",
            ]
            return ", ".join([p for p in parts if p])
        parts = [self.address, self.building, self.city, "Romania"]
        return ", ".join([p for p in parts if p])

    @property
    def city_display(self):
        return self.building_ref.city.name if self.building_ref_id else self.city

    @property
    def building_display(self):
        return self.building_ref.name if self.building_ref_id else self.building


class MoveRequest(models.Model):
    item = models.ForeignKey('Item', on_delete=models.CASCADE, related_name='moves')
    from_city = models.CharField(max_length=100, default='NULL')
    from_building = models.CharField(max_length=100, default="NULL")
    from_address = models.CharField(max_length=255, default="NULL")
    to_city = models.CharField(max_length=100, default='NULL')
    to_building = models.CharField(max_length=100, default="NULL")
    to_address = models.CharField(max_length=255, default="NULL")
    moved_by = models.CharField(max_length=100)
    moved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.item.name} moved from {self.from_city} to {self.to_city}"


class CityLocation(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"{self.name}"


class Delivery(models.Model):
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('finished', 'Finished'),
        ('cancelled', 'Cancelled'),
    ]

    item = models.ForeignKey('Item', on_delete=models.PROTECT, related_name='deliveries')
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')

    # Original location (where item was taken from)
    from_city = models.CharField(max_length=100)
    from_building = models.CharField(max_length=100)
    from_address = models.CharField(max_length=255)

    # Destination (optional - can be added later)
    to_city = models.CharField(max_length=100, blank=True, default='')
    to_building = models.CharField(max_length=100, blank=True, default='')
    to_address = models.CharField(max_length=255, blank=True, default='')

    created_by = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Delivery #{self.id} - {self.item.name} ({self.quantity} pcs) - {self.status}"


class Notification(models.Model):
    """Model for in-app notifications"""
    TYPES = [
        ('low_stock', 'Low Stock Alert'),
        ('delivery_update', 'Delivery Update'),
        ('item_moved', 'Item Moved'),
        ('delivery_created', 'Delivery Created'),
        ('delivery_finished', 'Delivery Finished'),
        ('delivery_cancelled', 'Delivery Cancelled'),
    ]

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=30, choices=TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()

    # Optional references
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.CASCADE)
    delivery = models.ForeignKey(Delivery, null=True, blank=True, on_delete=models.CASCADE)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.get_type_display()} - {self.title}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()

    def mark_as_unread(self):
        """Mark notification as unread"""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save()


class NotificationSettings(models.Model):
    """User notification preferences"""
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='notification_settings')

    # Thresholds
    low_stock_threshold = models.IntegerField(default=10, help_text="Alert when stock falls below this number")
    critical_stock_threshold = models.IntegerField(default=5, help_text="Critical alert threshold")

    # Notification toggles
    enable_low_stock_alerts = models.BooleanField(default=True)
    enable_delivery_alerts = models.BooleanField(default=True)
    enable_move_alerts = models.BooleanField(default=True)

    # Auto-mark as read after viewing
    auto_mark_read = models.BooleanField(default=False, help_text="Automatically mark as read when viewing")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Notification Settings"
        verbose_name_plural = "Notification Settings"

    def __str__(self):
        return f"Settings for {self.user.username}"
