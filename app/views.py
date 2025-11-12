import csv
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from .models import Item, MoveRequest
from .forms import MoveItemForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.db.models import Q
from django.conf import settings
from urllib.parse import quote_plus
from decimal import Decimal
from django.shortcuts import redirect, get_object_or_404
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseRedirect
from .forms import ItemCreateForm
from .models import City, Building
from django.shortcuts import render
from .forms import UserRegisterForm
from .forms import DeliveryCreateForm
from .models import Delivery, Notification, NotificationSettings
from django.utils import timezone

BASE_STATIC_MAP = "https://maps.googleapis.com/maps/api/staticmap"

def register(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            messages.success(request, f"Account created for {username}! You can now log in.")
            return redirect("login")
    else:
        form = UserRegisterForm()
    return render(request, "app/register.html", {"form": form})

class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff
    def handle_no_permission(self):
        return HttpResponseForbidden("Admins only.")

def _build_map_urls(items, width=1024, height=640, scale=2, chunk_size=80):
    items = list(items)
    if not items:
        return []
    urls = []
    for i in range(0, len(items), chunk_size):
        chunk = items[i:i+chunk_size]
        parts = [("size", f"{width}x{height}"), ("scale", str(scale)), ("maptype", "roadmap")]
        for it in chunk:
            color = "red" if (it.quantity or 0) < 10 else "blue"
            label = (it.name[:1].upper() if it.name else "")
            parts.append(("markers", f"color:{color}|label:{label}|{float(it.lat)},{float(it.lng)}"))
            parts.append(("visible", f"{float(it.lat)},{float(it.lng)}"))
        parts.append(("key", settings.GOOGLE_MAPS_API_KEY))
        query = "&".join(f"{k}={quote_plus(v)}" for k, v in parts)
        urls.append(f"{BASE_STATIC_MAP}?{query}")
    return urls

def _map_url_for_buildings(buildings, width=1024, height=640, scale=2):
    buildings = [b for b in buildings if b.lat is not None and b.lng is not None]
    if not buildings or not getattr(settings, "GOOGLE_MAPS_API_KEY", None):
        return ""
    parts = [("size", f"{width}x{height}"), ("scale", str(scale)), ("maptype", "roadmap")]
    for b in buildings:
        label = (b.name[:1].upper() if b.name else "B")
        parts.append(("markers", f"color:purple|label:{label}|{float(b.lat)},{float(b.lng)}"))
        parts.append(("visible", f"{float(b.lat)},{float(b.lng)}"))
    parts.append(("key", settings.GOOGLE_MAPS_API_KEY))
    query = "&".join(f"{k}={quote_plus(v)}" for k, v in parts)
    return f"{BASE_STATIC_MAP}?{query}"


# --- USER: listă itemuri
class ItemListView(LoginRequiredMixin, ListView):
    model = Item
    def get_queryset(self):
        qs = Item.objects.filter(owner=self.request.user)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
        city = self.request.GET.get('city')
        if city:
            qs = qs.filter(city=city)
        building = self.request.GET.get('building')
        if building:
            qs = qs.filter(building=building)
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cities = City.objects.order_by("name")
        selected_city = None
        city_id = self.request.GET.get("city")
        if city_id:
            selected_city = City.objects.filter(pk=city_id).first()

        buildings = Building.objects.filter(city=selected_city).order_by(
            "name") if selected_city else Building.objects.none()
        url = _map_url_for_buildings(buildings)

        ctx.update({
            "cities": cities,
            "selected_city": selected_city,
            "buildings": buildings,
            "map_url": url,
            # derive availability from the URL we actually generated
            "map_available": bool(url),
        })
        return ctx


# --- USER: export CSV
@login_required
def export_items_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_items.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'SKU', 'Quantity', 'City', 'Building', 'Address', 'Created At'])

    items = Item.objects.filter(owner=request.user)
    q = request.GET.get('q')
    if q:
        items = items.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    loc = request.GET.get('city')
    if loc:
        items = items.filter(city=loc)
    building = request.GET.get('building')
    if building:
        items = items.filter(building=building)
    items = items.order_by('-created_at')

    for item in items:
        writer.writerow([item.name, item.sku, item.quantity, item.city, item.building, item.address,
                         item.created_at.strftime('%Y-%m-%d %H:%M:%S')])
    return response

# --- USER: create item (userul setează doar iteme în orașe/clădiri existente prin formular)
class ItemCreateView(LoginRequiredMixin, CreateView):
    model = Item
    form_class = ItemCreateForm
    template_name = "app/item_create.html"
    success_url = reverse_lazy("item-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["city_id"] = self.request.GET.get("city") or self.request.POST.get("city")
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        cid = self.request.GET.get("city")
        if cid and cid.isdigit():
            initial["city"] = int(cid)
        return initial

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.owner = self.request.user
        obj.save()
        return redirect(self.success_url)


# --- USER: detail + history (vizibile doar proprietarului)
class ItemDetailView(LoginRequiredMixin, DetailView):
    model = Item
    def get_queryset(self):
        return Item.objects.filter(owner=self.request.user)

class MoveHistoryView(LoginRequiredMixin, DetailView):
    model = Item
    context_object_name = 'item'
    def get_queryset(self):
        return Item.objects.filter(owner=self.request.user)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['moves'] = self.object.moves.order_by('-moved_at')
        return ctx
    def get_template_names(self):
        return [f'{self.model._meta.app_label}/{self.model._meta.model_name}_history.html']

# --- ADMIN: edit/delete/move item (blocate pentru useri)
class ItemUpdateView(StaffRequiredMixin, UpdateView):
    model = Item
    fields = ['name', 'sku', 'quantity']  # poți extinde cu city/building dacă vrei ca adminul să modifice
    success_url = reverse_lazy('item-list')
    def get_queryset(self):
        return Item.objects.all()

class ItemDeleteView(StaffRequiredMixin, DeleteView):
    model = Item
    success_url = reverse_lazy('item-list')
    def get_queryset(self):
        return Item.objects.all()

class MoveItemView(StaffRequiredMixin, UpdateView):
    model = Item
    form_class = MoveItemForm
    template_name = "app/item_move.html"
    success_url = reverse_lazy('item-list')

    def get_queryset(self):
        return Item.objects.all()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["city_id"] = self.request.GET.get("city") or self.request.POST.get("to_city")
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cities'] = City.objects.order_by('name')
        return ctx

    def form_valid(self, form):
        old = Item.objects.get(pk=form.instance.pk)
        resp = super().form_valid(form)

        MoveRequest.objects.create(
            item=self.object,
            from_city=old.city,
            from_building=old.building,
            from_address=old.address,
            to_city=self.object.city,
            to_building=self.object.building,
            to_address=self.object.address,
            moved_by=self.request.user.username,
        )
        messages.success(self.request, f'Item "{self.object.name}" was successfully moved.')
        return resp

    def get_template_names(self):
        return [f'{self.model._meta.app_label}/{self.model._meta.model_name}_move.html']



# --- USER: harta (vizibilă tuturor userilor)
class MapView(LoginRequiredMixin, TemplateView):
    template_name = 'app/map.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = (self.request.GET.get('q') or '').strip()
        sel_city = (self.request.GET.get('city') or '').strip()
        sel_building = (self.request.GET.get('building') or '').strip()

        items_qs = Item.objects.filter(owner=self.request.user, lat__isnull=False, lng__isnull=False)
        if q:
            items_qs = items_qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
        if sel_city:
            items_qs = items_qs.filter(city=sel_city)
        if sel_building:
            items_qs = items_qs.filter(building=sel_building)
        items_qs = items_qs.order_by('-created_at')

        map_urls = _build_map_urls(items_qs)
        cities = (Item.objects.filter(owner=self.request.user).exclude(city__exact='')
                  .values_list('city', flat=True).distinct().order_by('city'))
        buildings = (Item.objects.filter(owner=self.request.user).exclude(building__exact='')
                     .values_list('building', flat=True).distinct().order_by('building'))

        ctx.update({
            'map_urls': map_urls,
            'items': items_qs.only('id','name','sku','quantity','city','building','address','lat','lng'),
            'has_key': bool(settings.GOOGLE_MAPS_API_KEY),
            'q': q, 'sel_city': sel_city, 'sel_building': sel_building,
            'cities': cities, 'buildings': buildings,
            'low_stock_threshold': 10,
        })
        return ctx

# --- ADMIN: City/Building management
class AdminInventoryView(StaffRequiredMixin, TemplateView):
    template_name = "app/admin_inventory.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cities = City.objects.order_by("name")
        selected_city = None
        city_id = self.request.GET.get("city")
        if city_id:
            selected_city = City.objects.filter(pk=city_id).first()

        buildings = Building.objects.filter(city=selected_city).order_by("name") if selected_city else Building.objects.none()
        ctx.update({
            "cities": cities,
            "selected_city": selected_city,
            "buildings": buildings,
            "map_url": _map_url_for_buildings(buildings),
            "has_key": bool(getattr(settings, "GOOGLE_MAPS_API_KEY", None)),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

        # 1) Add city
        if action == "add_city":
            name = (request.POST.get("city_name") or "").strip()
            if not name:
                messages.error(request, "City name is required.")
                return redirect(request.path)
            city, _ = City.objects.get_or_create(name=name)
            messages.success(request, f'City "{city.name}" added.')
            return redirect(f"{request.path}?city={city.id}")

        # 2) Delete city
        if action == "delete_city":
            city_id = request.POST.get("city_id")
            c = City.objects.filter(pk=city_id).first()
            if not c:
                messages.error(request, "City not found.")
                return redirect(request.path)
            try:
                c.delete()  # va ridica ProtectedError daca are cladiri
                messages.success(request, "City deleted.")
            except ProtectedError:
                messages.error(request, "Cannot delete a city that has buildings.")
            return redirect(request.path)

        if action == "add_building":
            city_id = request.POST.get("city_id")
            c = City.objects.filter(pk=city_id).first()
            if not c:
                messages.error(request, "Select a city first.")
                return redirect(request.path)

            name = (request.POST.get("name") or "").strip()
            address = (request.POST.get("address") or "").strip()
            lat_raw = (request.POST.get("lat") or "").strip()
            lng_raw = (request.POST.get("lng") or "").strip()

            # acum Address e obligatoriu
            if not name or not address or not lat_raw or not lng_raw:
                messages.error(request, "Name, address, latitude and longitude are required.")
                return redirect(f"{request.path}?city={c.id}")

            try:
                lat = Decimal(lat_raw)
                lng = Decimal(lng_raw)
            except Exception:
                messages.error(request, "Latitude/Longitude must be numeric.")
                return redirect(f"{request.path}?city={c.id}")

            b, created = Building.objects.get_or_create(
                city=c, name=name,
                defaults={"address": address, "lat": lat, "lng": lng},
            )
            if not created:
                messages.info(request, "Building already exists in this city.")
            else:
                messages.success(request, f'Building "{name}" added to {c.name}.')
            return redirect(f"{request.path}?city={c.id}")

        # 4) Delete building
        if action == "delete_building":
            b_id = request.POST.get("building_id")
            b = Building.objects.filter(pk=b_id).select_related("city").first()
            if not b:
                messages.error(request, "Building not found.")
                return redirect(request.path)
            c_id = b.city_id
            try:
                b.delete()  # va ridica ProtectedError daca exista Item-uri legate
                messages.success(request, "Building deleted.")
            except ProtectedError:
                messages.error(request, "Cannot delete a building that has items.")
            return redirect(f"{request.path}?city={c_id}")

        messages.error(request, "Unknown action.")
        return redirect(request.path)

class DeliveryCreateView(LoginRequiredMixin, CreateView):
    model = Delivery
    form_class = DeliveryCreateForm
    template_name = "app/delivery_create.html"
    success_url = reverse_lazy("delivery-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        delivery = form.save(commit=False)
        item = delivery.item

        # Store origin location from item
        delivery.from_city = item.city
        delivery.from_building = item.building
        delivery.from_address = item.address
        delivery.created_by = self.request.user.username

        # Reduce item quantity
        item.quantity -= delivery.quantity
        item.save()

        delivery.save()
        messages.success(
            self.request,
            f"{delivery.quantity} units of {item.name} placed in delivery. Remaining stock: {item.quantity}"
        )
        return redirect(self.success_url)


class DeliveryListView(LoginRequiredMixin, ListView):
    model = Delivery
    template_name = "app/delivery_list.html"
    context_object_name = "deliveries"

    def get_queryset(self):
        # Show only deliveries created by the current user
        qs = Delivery.objects.filter(created_by=self.request.user.username)

        # Filter by status
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        # Search by item name
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(item__name__icontains=q)

        return qs.select_related('item').order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Delivery.STATUS_CHOICES
        return ctx


class DeliveryDetailView(LoginRequiredMixin, DetailView):
    model = Delivery
    template_name = "app/delivery_detail.html"
    context_object_name = "delivery"

    def get_queryset(self):
        return Delivery.objects.filter(created_by=self.request.user.username)

class DeliveryUpdateView(LoginRequiredMixin, UpdateView):
    model = Delivery
    fields = ['to_city', 'to_building', 'to_address', 'status']
    template_name = "app/delivery_update.html"
    success_url = reverse_lazy("delivery-list")

    def get_queryset(self):
        return Delivery.objects.filter(created_by=self.request.user.username)

@login_required
def cancel_delivery(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk, created_by=request.user.username)
    if delivery.status == 'in_progress':
        # Restore item quantity
        delivery.item.quantity += delivery.quantity
        delivery.item.save()
        delivery.status = 'cancelled'
        delivery.save()
        messages.success(request, "Delivery cancelled and stock restored.")
    return redirect('delivery-list')


# ===== NOTIFICATION VIEWS =====

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "app/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def _filtered_qs(self):
        qs = Notification.objects.filter(user=self.request.user)
        status = self.request.GET.get("status")
        if status == "unread":
            qs = qs.filter(is_read=False)
        elif status == "read":
            qs = qs.filter(is_read=True)

        notification_type = self.request.GET.get("type")
        if notification_type:
            qs = qs.filter(type=notification_type)
        return qs

    def get_queryset(self):
        return self._filtered_qs().order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = self._filtered_qs()             # acelasi set ca in lista, dar nepaginat
        ctx["notification_types"] = Notification.TYPES
        ctx["total_count"]  = base.count()
        ctx["unread_count"] = base.filter(is_read=False).count()
        ctx["read_count"]   = base.filter(is_read=True).count()

        # optional: numarul global de unread (indiferent de filtre), util pt. butonul "Mark All Read"
        ctx["global_unread_count"] = Notification.objects.filter(
            user=self.request.user, is_read=False
        ).count()
        return ctx


@login_required
def mark_notification_read(request, pk):
    """Mark a single notification as read"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_read()

    # Redirect to the item or delivery if available
    if notification.item:
        return redirect('item-detail', pk=notification.item.pk)
    elif notification.delivery:
        return redirect('delivery-detail', pk=notification.delivery.pk)

    return redirect('notification-list')


@login_required
def mark_notification_read_ajax(request, pk):
    """Mark a single notification as read via AJAX"""
    if request.method == 'POST':
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        was_unread = not notification.is_read
        notification.mark_as_read()

        return JsonResponse({
            'success': True,
            'was_unread': was_unread,
            'notification_id': pk
        })

    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=400)


@login_required
def mark_notification_unread(request, pk):
    """Mark a single notification as unread"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_unread()
    return redirect('notification-list')


@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read for the current user"""
    Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now()
    )
    messages.success(request, "All notifications marked as read.")
    return redirect('notification-list')


@login_required
def delete_notification(request, pk):
    """Delete a notification"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.delete()
    messages.success(request, "Notification deleted.")
    return redirect('notification-list')


@login_required
def clear_all_notifications(request):
    """Delete all read notifications"""
    if request.method == 'POST':
        count = Notification.objects.filter(user=request.user, is_read=True).count()
        Notification.objects.filter(user=request.user, is_read=True).delete()
        messages.success(request, f"Deleted {count} read notifications.")
    return redirect('notification-list')


class NotificationSettingsView(LoginRequiredMixin, UpdateView):
    """View and update notification settings"""
    model = NotificationSettings
    template_name = 'app/notification_settings.html'
    fields = [
        'low_stock_threshold',
        'critical_stock_threshold',
        'enable_low_stock_alerts',
        'enable_delivery_alerts',
        'enable_move_alerts',
        'auto_mark_read',
    ]
    success_url = reverse_lazy('notification-settings')

    def get_object(self, queryset=None):
        """Get or create notification settings for current user"""
        obj, created = NotificationSettings.objects.get_or_create(user=self.request.user)
        return obj

    def form_valid(self, form):
        messages.success(self.request, "Notification settings updated successfully.")
        return super().form_valid(form)


class BuildingItemsView(LoginRequiredMixin, ListView):
    """View all items in a specific building"""
    model = Item
    template_name = 'app/building_items.html'
    context_object_name = 'items'
    paginate_by = 50

    def get_queryset(self):
        building_id = self.kwargs.get('building_id')
        self.building = get_object_or_404(Building, pk=building_id)
        return Item.objects.filter(building_ref=self.building).order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['building'] = self.building
        ctx['total_items'] = self.get_queryset().count()
        ctx['total_quantity'] = sum(item.quantity or 0 for item in self.get_queryset())
        return ctx


