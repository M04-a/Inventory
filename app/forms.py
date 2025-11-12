from django import forms
from .models import Item, City, Building, Delivery
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ["name", "sku", "quantity"]  # keep it simple; no free-text city/building here

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if len(name) < 3:
            raise forms.ValidationError("Name must be at least 3 characters")
        return name

    def clean_sku(self):
        sku = self.cleaned_data["sku"].strip()
        if len(sku) < 4:
            raise forms.ValidationError("SKU must be at least 4 characters")
        return sku


class MoveItemForm(forms.ModelForm):
    city = forms.ModelChoiceField(
        queryset=City.objects.order_by("name"),
        empty_label="— choose city —",
        label="City",
        required=True,
    )
    building = forms.ModelChoiceField(
        queryset=Building.objects.none(),
        empty_label="— choose building —",
        label="Building",
        required=True,
    )

    class Meta:
        model = Item
        fields = ["city", "building"]  # address is taken from building

    def __init__(self, *args, **kwargs):
        city_id = kwargs.pop("city_id", None)
        super().__init__(*args, **kwargs)

        # Preselect current city from instance if present
        if self.instance and self.instance.building_ref_id:
            self.initial.setdefault("city", self.instance.building_ref.city_id)

        cid = city_id or self.data.get("city") or self.initial.get("city")
        try:
            if cid:
                cid = int(cid)
                self.fields["building"].queryset = Building.objects.filter(city_id=cid).order_by("name")
        except (TypeError, ValueError):
            pass

        # Preselect current building when editing/moving
        if self.instance and self.instance.building_ref_id:
            self.initial.setdefault("building", self.instance.building_ref_id)

    def clean(self):
        cleaned = super().clean()
        city = cleaned.get("city")
        building = cleaned.get("building")
        if city and building and building.city_id != city.id:
            self.add_error("building", "Selected building doesn't belong to the chosen city.")
        return cleaned

    def save(self, commit=True):
        item = super().save(commit=False)
        b = self.cleaned_data["building"]
        # mirror data from building
        item.building_ref = b
        item.city = b.city.name
        item.building = b.name
        item.address = b.address
        item.lat = b.lat
        item.lng = b.lng
        if commit:
            item.save()
        return item

class ItemCreateForm(forms.ModelForm):
    city = forms.ModelChoiceField(
        queryset=City.objects.order_by("name"),
        empty_label="— choose city —",
        label="City",
        required=True,
    )
    building = forms.ModelChoiceField(
        queryset=Building.objects.none(),
        empty_label="— choose building —",
        label="Building",
        required=True,
    )

    class Meta:
        model = Item
        fields = ["name", "sku", "quantity", "city", "building"]
        widgets = {"quantity": forms.NumberInput(attrs={"min": 0})}

    def __init__(self, *args, **kwargs):
        city_id = kwargs.pop("city_id", None)
        super().__init__(*args, **kwargs)

        # Populează clădirile în funcție de oraș (din GET/POST)
        if city_id:
            self.fields["building"].queryset = (
                Building.objects.filter(city_id=city_id).order_by("name")
            )
            try:
                self.initial.setdefault("city", int(city_id))
            except (TypeError, ValueError):
                pass
        elif self.data.get("city"):
            try:
                cid = int(self.data.get("city"))
                self.fields["building"].queryset = (
                    Building.objects.filter(city_id=cid).order_by("name")
                )
            except (TypeError, ValueError):
                pass

    def clean(self):
        cleaned = super().clean()
        city = cleaned.get("city")
        building = cleaned.get("building")
        if city and building and building.city_id != city.id:
            self.add_error("building", "Selected building doesn't belong to the chosen city.")
        return cleaned

    def save(self, commit=True):
        item = super().save(commit=False)
        city = self.cleaned_data["city"]
        building = self.cleaned_data["building"]

        # Setează referința și oglindește câmpurile text + coordonatele
        item.building_ref = building
        item.city = city.name
        item.building = building.name
        item.address = building.address
        item.lat = building.lat
        item.lng = building.lng

        if commit:
            item.save()
        return item


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = get_user_model()
        fields = ["username", "email", "password1", "password2"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_staff = False  # Regular users are NOT staff
        if commit:
            user.save()
        return user

class DeliveryCreateForm(forms.ModelForm):
    item = forms.ModelChoiceField(
        queryset=Item.objects.none(),
        label="Select Item",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantity = forms.IntegerField(
        min_value=1,
        label="Quantity to Deliver",
        widget=forms.NumberInput(attrs={'min': 1, 'placeholder': 'Enter quantity'})
    )
    to_city = forms.CharField(
        max_length=100,
        required=False,
        label="Destination City",
        widget=forms.TextInput(attrs={'placeholder': 'e.g. București'})
    )
    to_building = forms.CharField(
        max_length=100,
        required=False,
        label="Destination Building",
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Warehouse 2'})
    )
    to_address = forms.CharField(
        max_length=255,
        required=False,
        label="Destination Address",
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Str. Exemple 123'})
    )

    class Meta:
        model = Delivery
        fields = ['item', 'quantity', 'to_city', 'to_building', 'to_address']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['item'].queryset = Item.objects.filter(
                owner=user,
                quantity__gt=0
            ).order_by('name')

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get('item')
        quantity = cleaned.get('quantity')

        if item and quantity:
            if quantity > item.quantity:
                raise forms.ValidationError(
                    f"Cannot deliver {quantity} items. Only {item.quantity} available in stock."
                )
        return cleaned