"""Database models for the restaurant application.

The models defined here represent menu categories, individual menu
items and contact messages submitted via the website. They use
simple field types and avoid unnecessary complexity so they can
easily be managed via custom admin views rather than the default
Django admin interface.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError

from decimal import Decimal
from django.db import models
from django.urls import reverse
from django.utils import timezone
from cloudinary.models import CloudinaryField
import math
class Category(models.Model):
    """A grouping for menu items.

    Categories are displayed on the menu page to help diners find
    items more easily. Categories have an order field so they can
    be arranged manually.
    """

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("restaurant:menu") + f"?category={self.slug}"


class MenuItem(models.Model):
    """A single dish or drink available at the restaurant.

    Menu items belong to a category and can carry a list of tags
    and allergens. Tags and allergens are stored as comma
    separated strings to avoid the overhead of many to many
    relations in this simple example.
    """

    STATUS_ACTIVE = "active"
    STATUS_HIDDEN = "hidden"
    STATUS_SOLD_OUT = "sold_out"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_HIDDEN, "Hidden"),
        (STATUS_SOLD_OUT, "Sold Out"),
    ]

    name = models.CharField(max_length=100)
    # PROTECT so category cannot be deleted if items exist (matches outline protection requirement)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="menu_items")
    price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="menu_items/", blank=True, null=True)

    tags = models.CharField(max_length=200, blank=True, help_text="Comma separated list of tags.")
    allergens = models.CharField(max_length=200, blank=True, help_text="Comma separated list of allergens.")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "name"]

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def _csv_to_list(value: str) -> list[str]:
        if not value:
            return []
        out: list[str] = []
        for raw in value.split(","):
            v = raw.strip()
            if v and v not in out:
                out.append(v)
        return out

    def get_tags_list(self) -> list[str]:
        """Return tags as a list of strings."""
        return self._csv_to_list(self.tags)

    def get_allergens_list(self) -> list[str]:
        """Return allergens as a list of strings."""
        return self._csv_to_list(self.allergens)

    def is_popular(self) -> bool:
        return "popular" in self.get_tags_list()


class ContactMessage(models.Model):
    """A simple contact form submission."""

    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Message from {self.name} <{self.email}>"







class Reservation(models.Model):
    """
    A single reservation is a fixed 30-minute slot.
    Capacity is enforced per slot (same start_datetime).
    """

    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_COMPLETED, "Completed"),
    ]

    start_datetime = models.DateTimeField(db_index=True)

    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40)
    email = models.EmailField(blank=True)

    party_size = models.PositiveIntegerField(default=2)  # chairs needed
    baby_seats = models.PositiveIntegerField(default=0)

    # ✅ add this (your template already posts preferred_table)
    preferred_table = models.PositiveIntegerField(blank=True, null=True)

    # derived
    tables_needed = models.PositiveIntegerField(default=1)

    notes = models.TextField(blank=True)

    # ✅ add status for backend handling
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    created_at = models.DateTimeField(auto_now_add=True)

    # Capacity constants (as requested)
    TABLES_TOTAL = 14
    CHAIRS_TOTAL = 55
    BABY_SEATS_TOTAL = 2
    SLOT_MINUTES = 30

    class Meta:
        ordering = ["-start_datetime", "-created_at"]

    def __str__(self) -> str:
        return f"{self.name} – {self.start_datetime} ({self.party_size})"

    @staticmethod
    def compute_tables_needed(party_size: int) -> int:
        if party_size <= 0:
            return 1
        return max(1, math.ceil(party_size / 4))

    def clean(self):
        if self.start_datetime and self.start_datetime < timezone.now():
            raise ValidationError({"start_datetime": "Please choose a future time."})

        if self.start_datetime:
            minute = self.start_datetime.minute
            if minute not in (0, 30) or self.start_datetime.second != 0:
                raise ValidationError({"start_datetime": "Bookings are available only in 30-minute intervals."})

        self.tables_needed = self.compute_tables_needed(self.party_size)

        if self.start_datetime:
            qs = Reservation.objects.filter(start_datetime=self.start_datetime)
            if self.pk:
                qs = qs.exclude(pk=self.pk)

            totals = qs.aggregate(
                chairs=models.Sum("party_size"),
                babies=models.Sum("baby_seats"),
                tables=models.Sum("tables_needed"),
            )

            chairs_used = int(totals["chairs"] or 0)
            babies_used = int(totals["babies"] or 0)
            tables_used = int(totals["tables"] or 0)

            if chairs_used + self.party_size > self.CHAIRS_TOTAL:
                raise ValidationError(
                    {"party_size": f"Not enough seats left for this time. ({self.CHAIRS_TOTAL - chairs_used} seats remaining)"}
                )

            if babies_used + self.baby_seats > self.BABY_SEATS_TOTAL:
                raise ValidationError(
                    {"baby_seats": f"Not enough baby seats left for this time. ({self.BABY_SEATS_TOTAL - babies_used} remaining)"}
                )

            if tables_used + self.tables_needed > self.TABLES_TOTAL:
                raise ValidationError(
                    {"party_size": f"Not enough tables left for this time. ({self.TABLES_TOTAL - tables_used} tables remaining)"}
                )

    @property
    def preorder_total(self):
        return sum((it.line_total for it in self.items.all()), 0)


class ReservationItem(models.Model):
    reservation = models.ForeignKey(Reservation, related_name="items", on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        unique_together = [("reservation", "menu_item")]

    @property
    def line_total(self):
        return self.qty * self.unit_price

    def __str__(self) -> str:
        return f"{self.menu_item.name} x {self.qty}"





class DeliveryPromotion(models.Model):
    title = models.CharField(max_length=120, default="Free Delivery")
    is_active = models.BooleanField(default=False)

    # optional schedule
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)

    # optional condition
    min_subtotal = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # for now we only need free delivery season
    free_delivery = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_active", "-created_at"]

    def __str__(self) -> str:
        return f"{self.title} ({'active' if self.is_active else 'off'})"

    def is_current(self) -> bool:
        if not self.is_active:
            return False
        now = timezone.now()
        if self.start_at and now < self.start_at:
            return False
        if self.end_at and now > self.end_at:
            return False
        return True




class DeliveryOrder(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_PREPARING = "preparing"
    STATUS_OUT_FOR_DELIVERY = "out_for_delivery"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_PREPARING, "Preparing"),
        (STATUS_OUT_FOR_DELIVERY, "Out for delivery"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    # coupon snapshot (optional)
    coupon_code = models.CharField(max_length=32, blank=True)
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # customer
    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=40)
    customer_note = models.TextField(blank=True)
    
    PAYMENT_CASH = "cash"
    PAYMENT_CARD = "card"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_CASH, "Cash on Delivery"),
        (PAYMENT_CARD, "Card on Delivery (POS)"),
    ]

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_CASH,
    )


    # location
    address_label = models.CharField(max_length=255, blank=True)
    address_extra = models.CharField(max_length=255, blank=True)
    lat = models.FloatField()
    lng = models.FloatField()
    distance_km = models.FloatField(default=0)

    # money snapshot
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # promo snapshot (optional)
    promo_title = models.CharField(max_length=120, blank=True)
    promo_free_delivery = models.BooleanField(default=False)
    promo_min_subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Order #{self.id} ({self.get_status_display()})"





class DeliveryOrderItem(models.Model):
    order = models.ForeignKey("DeliveryOrder", related_name="items", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    qty = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    @property
    def line_total(self):
        return (self.unit_price or Decimal("0.00")) * Decimal(self.qty or 0)




#cupon state
class DeliveryCoupon(models.Model):
    DISCOUNT_PERCENT = "percent"
    DISCOUNT_FIXED = "fixed"

    DISCOUNT_TYPE_CHOICES = [
        (DISCOUNT_PERCENT, "Percent (%)"),
        (DISCOUNT_FIXED, "Fixed (€)"),
    ]

    code = models.CharField(max_length=32, unique=True)
    is_active = models.BooleanField(default=True)

    discount_type = models.CharField(max_length=16, choices=DISCOUNT_TYPE_CHOICES, default=DISCOUNT_PERCENT)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    min_subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)

    max_uses = models.PositiveIntegerField(null=True, blank=True)  # null = unlimited
    used_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_active", "-created_at"]

    def __str__(self):
        return self.code

    def is_current(self) -> bool:
        if not self.is_active:
            return False
        now = timezone.now()
        if self.start_at and now < self.start_at:
            return False
        if self.end_at and now > self.end_at:
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        return True

    def compute_discount(self, subtotal: Decimal) -> Decimal:
        """
        Discount applies to subtotal (NOT delivery fee).
        Returns a safe discount (never > subtotal).
        """
        if subtotal is None:
            subtotal = Decimal("0")
        if subtotal < Decimal(str(self.min_subtotal or 0)):
            return Decimal("0")

        val = Decimal(str(self.discount_value or 0))

        if self.discount_type == self.DISCOUNT_FIXED:
            disc = val
        else:
            # percent
            disc = (subtotal * val) / Decimal("100")

        if disc < 0:
            disc = Decimal("0")
        if disc > subtotal:
            disc = subtotal
        return disc



# -------------------------
# Hero Banner (Homepage Slideshow)
# -------------------------




class HeroBanner(models.Model):
    image = CloudinaryField("image")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return f"Hero Banner #{self.id}"
