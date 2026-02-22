"""Forms for the restaurant application.

Defines:
- MenuItemForm (custom admin add/edit item)
- CategoryForm (custom admin category CRUD)
- ContactForm (public contact)
- AdminLoginForm (custom styled auth form)

Tags/allergens are stored as comma-separated strings in DB but displayed as checkbox groups.
"""

from __future__ import annotations

from typing import Any
from .models import HeroBanner

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.utils.text import slugify

from .models import MenuItem, Category, ContactMessage, Reservation

from django.utils import timezone

from .models import DeliveryPromotion

from .models import DeliveryCoupon
from .models import Review
from datetime import datetime
from .models import Reservation

def _csv_to_list(value: str) -> list[str]:
    if not value:
        return []
    out: list[str] = []
    for raw in value.split(","):
        v = raw.strip()
        if v and v not in out:
            out.append(v)
    return out


def _list_to_csv(values: list[str] | None) -> str:
    values = values or []
    out: list[str] = []
    for raw in values:
        v = (raw or "").strip()
        if v and v not in out:
            out.append(v)
    return ", ".join(out)


class MenuItemForm(forms.ModelForm):
    """Form for creating/updating a menu item in custom admin."""

    tags_multi = forms.MultipleChoiceField(
        choices=getattr(settings, "MENU_ITEM_TAGS", []),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Tags",
    )
    allergens_multi = forms.MultipleChoiceField(
        choices=getattr(settings, "MENU_ITEM_ALLERGENS", []),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Allergens",
    )

    class Meta:
        model = MenuItem
        fields = ["name", "category", "price", "description", "image", "status"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Only active categories in dropdown
        self.fields["category"].queryset = Category.objects.filter(is_active=True).order_by("order", "name")

        base = (
            "w-full px-4 py-3 bg-white/50 border border-dark/20 "
            "focus:border-gold focus:outline-none rounded-sm"
        )
        textarea = (
            "w-full px-4 py-3 bg-white/50 border border-dark/20 "
            "focus:border-gold focus:outline-none rounded-sm min-h-[120px]"
        )

        self.fields["name"].widget.attrs.update({"class": base, "placeholder": "Item name"})
        self.fields["category"].widget.attrs.update({"class": base})
        self.fields["price"].widget.attrs.update({"class": base, "placeholder": "11.90"})
        self.fields["description"].widget.attrs.update({"class": textarea})
        self.fields["status"].widget.attrs.update({"class": base})
        self.fields["image"].widget.attrs.update({"class": "block w-full text-sm"})

        # Preselect tags/allergens when editing
        if self.instance and self.instance.pk:
            self.fields["tags_multi"].initial = _csv_to_list(self.instance.tags)
            self.fields["allergens_multi"].initial = _csv_to_list(self.instance.allergens)

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        cleaned["tags_csv"] = _list_to_csv(cleaned.get("tags_multi") or [])
        cleaned["allergens_csv"] = _list_to_csv(cleaned.get("allergens_multi") or [])
        return cleaned

    def save(self, commit: bool = True) -> MenuItem:
        obj: MenuItem = super().save(commit=False)
        obj.tags = self.cleaned_data.get("tags_csv", "")
        obj.allergens = self.cleaned_data.get("allergens_csv", "")
        if commit:
            obj.save()
        return obj


class CategoryForm(forms.ModelForm):
    """Form for creating/updating categories in custom admin."""

    class Meta:
        model = Category
        fields = ["name", "slug", "is_active", "order"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        base = (
            "w-full px-4 py-3 bg-white/50 border border-dark/20 "
            "focus:border-gold focus:outline-none rounded-sm"
        )

        self.fields["name"].widget.attrs.update({"class": base, "placeholder": "Category name"})
        self.fields["slug"].widget.attrs.update({"class": base, "placeholder": "pizzat"})
        self.fields["order"].widget.attrs.update({"class": base, "placeholder": "0"})
        self.fields["is_active"].widget.attrs.update({"class": "h-4 w-4"})

    def clean_slug(self) -> str:
        slug = (self.cleaned_data.get("slug") or "").strip()
        name = (self.cleaned_data.get("name") or "").strip()

        # Auto-generate slug if empty
        if not slug:
            slug = slugify(name)

        # Ensure slug not empty after slugify
        if not slug:
            raise forms.ValidationError("Please enter a name or a valid slug.")

        # Uniqueness check (exclude current instance when editing)
        qs = Category.objects.filter(slug=slug)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Slug already exists. Choose a different slug.")

        return slug


class ContactForm(forms.ModelForm):
    """Public contact form."""

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "message"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 bg-white/50 border border-dark/20 focus:border-gold focus:outline-none rounded-sm",
                    "placeholder": "Your name",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-4 py-3 bg-white/50 border border-dark/20 focus:border-gold focus:outline-none rounded-sm",
                    "placeholder": "Your email",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "rows": 5,
                    "class": "w-full px-4 py-3 bg-white/50 border border-dark/20 focus:border-gold focus:outline-none rounded-sm",
                    "placeholder": "Write your message...",
                }
            ),
        }


class AdminLoginForm(AuthenticationForm):
    """Custom styled admin login form (Django auth)."""

    remember_me = forms.BooleanField(required=False, label="Remember me")

    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2 border border-lightbrown rounded bg-beige text-dark focus:outline-none focus:border-gold",
                "placeholder": "Username",
                "autofocus": True,
            }
        ),
    )

    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2 border border-lightbrown rounded bg-beige text-dark focus:outline-none focus:border-gold",
                "placeholder": "Password",
            }
        ),
    )

    def __init__(self, request=None, *args: Any, **kwargs: Any) -> None:
        super().__init__(request=request, *args, **kwargs)
        self.fields["remember_me"].widget.attrs.update({"class": "h-4 w-4"})

# =========================
# ✅ REPLACE your ReservationForm with this FULL UPDATED VERSION
# - Keeps your premium Tailwind UI classes
# - Adds preferred_table support (matches your model + template block)
# - Fixes timezone datetime combine (uses datetime from stdlib, not timezone.datetime)
# - Calls obj.full_clean() before save so model capacity rules run
# - Keeps 30-min slot + opening hours validation
# =========================



class ReservationForm(forms.ModelForm):
    """
    Premium UI form:
    - Shows separate date + time fields for the frontend
    - Combines them into start_datetime in clean()
    - Runs model-level capacity validation via full_clean() on save
    """

    # -------------------------
    # Frontend-only fields
    # -------------------------
    date = forms.DateField(
        required=True,
        widget=forms.TextInput(
            attrs={
                "id": "id_date",
                "autocomplete": "off",
                "placeholder": "Select date",
                "class": "w-full rounded-2xl border border-[#3e2723]/10 bg-white px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#bfa76f]/60",
            }
        ),
    )

    time = forms.TimeField(
        required=True,
        widget=forms.TextInput(
            attrs={
                "id": "id_time",
                "autocomplete": "off",
                "placeholder": "Select time",
                "class": "w-full rounded-2xl border border-[#3e2723]/10 bg-white px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#bfa76f]/60",
            }
        ),
    )

    class Meta:
        model = Reservation

        # ✅ include preferred_table (model field) so template can render it
        fields = [
            "name",
            "phone",
            "email",
            "party_size",
            "baby_seats",
            "preferred_table",
            "notes",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "id": "id_name",
                    "class": "w-full rounded-2xl border border-[#3e2723]/10 bg-white px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#bfa76f]/60",
                    "placeholder": "Your name",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "id": "id_phone",
                    "class": "w-full rounded-2xl border border-[#3e2723]/10 bg-white px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#bfa76f]/60",
                    "placeholder": "+358...",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "id": "id_email",
                    "class": "w-full rounded-2xl border border-[#3e2723]/10 bg-white px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#bfa76f]/60",
                    "placeholder": "Optional",
                }
            ),
            "party_size": forms.NumberInput(
                attrs={
                    "id": "id_party_size",
                    "class": "w-full rounded-2xl border border-[#3e2723]/10 bg-white px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#bfa76f]/60",
                    "min": "1",
                    "max": "55",
                }
            ),
            "baby_seats": forms.NumberInput(
                attrs={
                    "id": "id_baby_seats",
                    "class": "w-full rounded-2xl border border-[#3e2723]/10 bg-white px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#bfa76f]/60",
                    "min": "0",
                    "max": "2",
                }
            ),
            # ✅ matches your template's "table preference" block
            "preferred_table": forms.NumberInput(
                attrs={
                    "id": "id_table_preference",
                    "class": "w-full rounded-2xl border border-[#3e2723]/10 bg-white px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#bfa76f]/60",
                    "min": "1",
                    "max": "14",
                    "placeholder": "Optional",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "id": "id_notes",
                    "rows": 4,
                    "class": "w-full rounded-2xl border border-[#3e2723]/10 bg-white px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#bfa76f]/60",
                    "placeholder": "Allergies, wheelchair, special request (optional)",
                }
            ),
        }

    # -------------------------
    # Validation
    # -------------------------
    def clean(self):
        cleaned = super().clean()

        d = cleaned.get("date")
        t = cleaned.get("time")

        if not d or not t:
            return cleaned

        # Combine date+time -> timezone-aware start_datetime
        naive_dt = datetime.combine(d, t)

        # If project uses timezones, make aware using current timezone
        if timezone.is_naive(naive_dt):
            aware_dt = timezone.make_aware(naive_dt, timezone.get_current_timezone())
        else:
            aware_dt = naive_dt

        aware_dt = aware_dt.replace(second=0, microsecond=0)

        # 30-min interval validation
        if aware_dt.minute not in (0, 30):
            raise forms.ValidationError("Bookings are available only in 30-minute intervals.")

        # Opening hours: 10:00–22:00, last booking start 21:30
        local_dt = timezone.localtime(aware_dt)

        if local_dt.hour < 10:
            raise forms.ValidationError("Please choose a time between 10:00 and 22:00.")
        if local_dt.hour > 21 or (local_dt.hour == 21 and local_dt.minute > 30):
            raise forms.ValidationError("Last booking start time is 21:30.")

        if aware_dt < timezone.now():
            raise forms.ValidationError("Please choose a future time.")

        # Store for save()
        cleaned["start_datetime"] = aware_dt
        return cleaned

    # -------------------------
    # Save (runs model capacity rules)
    # -------------------------
    def save(self, commit=True):
        obj: Reservation = super().save(commit=False)

        # start_datetime is created in clean()
        obj.start_datetime = self.cleaned_data["start_datetime"]

        # ✅ very important: runs Reservation.clean() capacity checks
        obj.full_clean()

        if commit:
            obj.save()

        return obj





class DeliveryPromotionForm(forms.ModelForm):
    class Meta:
        model = DeliveryPromotion
        fields = ["title", "is_active", "start_at", "end_at", "min_subtotal", "free_delivery"]






class DeliveryCouponForm(forms.ModelForm):
    class Meta:
        model = DeliveryCoupon
        fields = [
            "code",
            "is_active",
            "discount_type",
            "discount_value",
            "min_subtotal",
            "start_at",
            "end_at",
            "max_uses",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"placeholder": "e.g. SINET10"}),
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().upper()
        if not code:
            raise forms.ValidationError("Code is required.")
        if " " in code:
            raise forms.ValidationError("Code cannot contain spaces.")
        return code

    def clean(self):
        cleaned = super().clean()
        start_at = cleaned.get("start_at")
        end_at = cleaned.get("end_at")
        if start_at and end_at and end_at <= start_at:
            self.add_error("end_at", "End must be after start.")
        # Optional: default start_at if empty
        if not start_at:
            cleaned["start_at"] = timezone.now()
        return cleaned


class HeroBannerForm(forms.ModelForm):
    class Meta:
        model = HeroBanner
        fields = ["image", "is_active", "order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        base = (
            "w-full px-4 py-3 bg-white/50 border border-dark/20 "
            "focus:border-gold focus:outline-none rounded-sm"
        )

        self.fields["order"].widget.attrs.update({"class": base})
        self.fields["is_active"].widget.attrs.update({"class": "h-4 w-4"})




class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["name", "rating", "comment"]
        widgets = {
            "rating": forms.Select(choices=[(i, i) for i in range(1, 6)]),
            "comment": forms.Textarea(attrs={"rows": 4}),
        }


def clean(self):
    cleaned = super().clean()

    start_at = cleaned.get("start_at")
    end_at = cleaned.get("end_at")
    if start_at and end_at and end_at <= start_at:
        self.add_error("end_at", "End must be after start.")

    # Optional: default start_at if empty
    if not start_at:
        cleaned["start_at"] = timezone.now()

    # ✅ If free delivery, discount_value is irrelevant
    if cleaned.get("discount_type") == DeliveryCoupon.DISCOUNT_FREE_DELIVERY:
        cleaned["discount_value"] = 0

    return cleaned
