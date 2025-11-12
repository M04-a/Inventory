from django.contrib import admin
from .models import Item, MoveRequest, CityLocation, City, Building, Notification, NotificationSettings, Delivery

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "address")
    list_filter = ("city",)
    search_fields = ("name", "address", "city__name")

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "quantity", "city_name", "building_name", "address", "owner", "created_at")
    list_filter = ("building_ref__city", "building_ref")
    search_fields = ("name", "sku", "building_ref__name", "building_ref__city__name", "city", "building")
    autocomplete_fields = ("building_ref", "owner")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("building_ref__city", "owner")

    def city_name(self, obj):
        return obj.building_ref.city.name if obj.building_ref_id else obj.city
    city_name.short_description = "Oras"
    city_name.admin_order_field = "building_ref__city__name"

    def building_name(self, obj):
        return obj.building_ref.name if obj.building_ref_id else obj.building
    building_name.short_description = "Cladire"
    building_name.admin_order_field = "building_ref__name"

@admin.register(MoveRequest)
class MoveRequestAdmin(admin.ModelAdmin):
    list_display = ("item", "from_city", "to_city", "moved_by", "moved_at")
    search_fields = ("item__name", "from_city", "to_city", "moved_by")


@admin.register(CityLocation)
class CityLocationAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "quantity", "status", "from_city", "to_city", "created_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("item__name", "created_by", "from_city", "to_city")
    ordering = ("-created_at",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "type", "title", "is_read", "created_at")
    list_filter = ("type", "is_read", "created_at")
    search_fields = ("user__username", "title", "message")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "read_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "item", "delivery")


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "low_stock_threshold", "critical_stock_threshold",
                   "enable_low_stock_alerts", "enable_delivery_alerts", "enable_move_alerts")
    list_filter = ("enable_low_stock_alerts", "enable_delivery_alerts", "enable_move_alerts")
    search_fields = ("user__username",)
