from django.urls import path
from . import views
from .views import register

urlpatterns = [
    path("", views.ItemListView.as_view(), name="item-list"),
    path("export-csv/", views.export_items_csv, name="export-csv"),
    path("item/<int:pk>/", views.ItemDetailView.as_view(), name="item-detail"),
    path("item/create/", views.ItemCreateView.as_view(), name="item-create"),
    path("item/<int:pk>/history/", views.MoveHistoryView.as_view(), name="item-history"),
    path("map/", views.MapView.as_view(), name="map"),

    path("delivery/create/", views.DeliveryCreateView.as_view(), name="delivery-create"),
    path("delivery/", views.DeliveryListView.as_view(), name="delivery-list"),
    path("delivery/<int:pk>/", views.DeliveryDetailView.as_view(), name="delivery-detail"),
    path("delivery/<int:pk>/update/", views.DeliveryUpdateView.as_view(), name="delivery-update"),
    path("delivery/<int:pk>/cancel/", views.cancel_delivery, name="delivery-cancel"),

    path("item/<int:pk>/update/", views.ItemUpdateView.as_view(), name="item-update"),
    path("item/<int:pk>/delete/", views.ItemDeleteView.as_view(), name="item-delete"),
    path("item/<int:pk>/move/",   views.MoveItemView.as_view(),   name="item-move"),

    path("inventory/admin/", views.AdminInventoryView.as_view(), name="admin-inventory"),
    path("building/<int:building_id>/items/", views.BuildingItemsView.as_view(), name="building-items"),

    # Notifications
    path("notifications/", views.NotificationListView.as_view(), name="notification-list"),
    path("notifications/<int:pk>/read/", views.mark_notification_read, name="notification-mark-read"),
    path("notifications/<int:pk>/read-ajax/", views.mark_notification_read_ajax, name="notification-mark-read-ajax"),
    path("notifications/<int:pk>/unread/", views.mark_notification_unread, name="notification-mark-unread"),
    path("notifications/<int:pk>/delete/", views.delete_notification, name="notification-delete"),
    path("notifications/mark-all-read/", views.mark_all_notifications_read, name="notification-mark-all-read"),
    path("notifications/clear-all/", views.clear_all_notifications, name="notification-clear-all"),
    path("notifications/settings/", views.NotificationSettingsView.as_view(), name="notification-settings"),

    path("register/", register, name="register"),
]
