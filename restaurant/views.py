"""
Views for the restaurant application.

Public pages:
- Home
- Menu (with category/tag/search filtering)
- About
- Contact (stores messages)
- Reservation
- Delivery (location + order + checkout)

Admin/Staff pages (custom, NOT Django admin UI):
- Admin Login
- Dashboard
- Add/Edit/Delete Menu Item
- Category management
- Reservations management
- Promotions placeholders

All admin pages require login via Django auth.
"""

from __future__ import annotations

import json
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.db.models.deletion import ProtectedError
import re

from .models import Review
from .forms import ReviewForm

from .forms import (
    AdminLoginForm,
    CategoryForm,
    ContactForm,
    MenuItemForm,
    ReservationForm,
    DeliveryCouponForm,
    HeroBannerForm,
)

from .models import (
    Category,
    DeliveryCoupon,
    DeliveryOrder,
    DeliveryOrderItem,
    DeliveryPromotion,
    MenuItem,
    Reservation,
    ReservationItem,
    HeroBanner,  # ← ADD THIS
)


from django.db.models import Avg, Count
from django.core.paginator import Paginator

from .utils import haversine_km, delivery_fee_for_distance

from django.utils.translation import gettext as _

from django.views.decorators.http import require_POST

from django.core.cache import cache
from django.shortcuts import redirect
# -------------------------
# Public pages
# -------------------------


def home(request: HttpRequest) -> HttpResponse:
    popular_items = (
        MenuItem.objects.filter(status=MenuItem.STATUS_ACTIVE)
        .filter(tags__icontains="popular")
        .select_related("category")
        .order_by("-created_at")[:4]
    )

    categories = Category.objects.filter(is_active=True)

    hero_banners = HeroBanner.objects.filter(is_active=True)

    return render(
        request,
        "home.html",
        {
            "popular_items": popular_items,
            "categories": categories,
            "hero_banners": hero_banners,
        },
    )


def menu(request: HttpRequest) -> HttpResponse:
    """Display the menu (category + search only)."""
    categories = Category.objects.filter(is_active=True).order_by("order", "name")

    category_slug = (request.GET.get("category") or "").strip()
    q = (request.GET.get("q") or "").strip()

    items = MenuItem.objects.select_related("category").exclude(
        status=MenuItem.STATUS_HIDDEN
    )

    current_category: Category | None = None
    if category_slug:
        current_category = get_object_or_404(
            Category, slug=category_slug, is_active=True
        )
        items = items.filter(category=current_category)

    if q:
        items = items.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(category__name__icontains=q)
        )

    items = items.order_by("category__order", "category__name", "name")

    most_ordered = (
        MenuItem.objects.select_related("category")
        .exclude(status=MenuItem.STATUS_HIDDEN)
        .filter(tags__icontains="popular")
        .order_by("-created_at")[:3]
    )

    return render(
        request,
        "menu.html",
        {
            "categories": categories,
            "items": items,
            "most_ordered": most_ordered,
            "current_category": current_category,
            "q": q,
            "tag_filter": "",
            "tag_choices": [],
            # ✅ REQUIRED for Google Maps loader in menu.html
            "GOOGLE_MAPS_API_KEY": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
            # ✅ Needed because your JS reads {{ rest_lat }} / {{ rest_lng }} in menu.html
            "rest_lat": getattr(settings, "RESTAURANT_LAT", 0),
            "rest_lng": getattr(settings, "RESTAURANT_LNG", 0),
            # Optional (if you show it in the modal)
            "max_radius": getattr(settings, "DELIVERY_MAX_RADIUS_KM", 10.0),
        },
    )


def about(request: HttpRequest) -> HttpResponse:
    """About page with a contact form section."""
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you! Your message has been sent.")
            return redirect(reverse("restaurant:about"))
    else:
        form = ContactForm()
    return render(request, "about.html", {"form": form})


def contact(request: HttpRequest) -> HttpResponse:
    """Display a contact form and handle submissions."""
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, "Thank you for your message! We'll get back to you soon."
            )
            return redirect(reverse("restaurant:contact"))
    else:
        form = ContactForm()
    return render(request, "contact.html", {"form": form})


# views.py


def menu_item_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Partial template for menu modal."""
    item = get_object_or_404(MenuItem.objects.select_related("category"), pk=pk)
    if item.status == MenuItem.STATUS_HIDDEN:
        return HttpResponse(status=404)

    ctx = (request.GET.get("ctx") or "menu").strip().lower()
    if ctx not in {"menu", "reservation", "delivery"}:
        ctx = "menu"

    # ✅ Use a reservation-specific partial so preview updates reservation pre-order (not delivery cart)
    template = "partials/menu_item_modal.html"
    if ctx == "reservation":
        template = "partials/reservation_item_modal.html"

    return render(request, template, {"item": item, "ctx": ctx})


# -------------------------
# Custom admin pages
# -------------------------


def admin_login(request: HttpRequest) -> HttpResponse:
    """Custom admin login page using Django authentication."""
    if request.user.is_authenticated:
        return redirect(reverse("restaurant:dashboard"))

    if request.method == "POST":
        form = AdminLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            remember = form.cleaned_data.get("remember_me")
            if not remember:
                request.session.set_expiry(0)

            return redirect(reverse("restaurant:dashboard"))
    else:
        form = AdminLoginForm(request)

    return render(request, "admin/custom_login.html", {"form": form})


@login_required
def admin_logout(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect(reverse("restaurant:admin_login"))


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    total_items = MenuItem.objects.count()
    total_categories = Category.objects.count()
    sold_out_count = MenuItem.objects.filter(status=MenuItem.STATUS_SOLD_OUT).count()

    recent_items = MenuItem.objects.select_related("category").order_by("-created_at")[
        :50
    ]
    categories = Category.objects.all().order_by("order", "name")

    total_reservations = Reservation.objects.count()
    pending_reservations = Reservation.objects.filter(
        status=Reservation.STATUS_PENDING
    ).count()
    upcoming_reservations = Reservation.objects.filter(
        start_datetime__gte=timezone.now()
    ).count()
    recent_reservations = Reservation.objects.order_by("-created_at")[:50]

    pending_delivery_orders = DeliveryOrder.objects.filter(status="pending").count()
    completed_delivery_orders = DeliveryOrder.objects.filter(status="delivered").count()
    active_items_count = MenuItem.objects.filter(status=MenuItem.STATUS_ACTIVE).count()
    recent_delivery_orders = DeliveryOrder.objects.order_by("-created_at")[:50]

    context = {
        "total_items": total_items,
        "total_categories": total_categories,
        "sold_out_count": sold_out_count,
        "recent_items": recent_items,
        "categories": categories,
        "total_reservations": total_reservations,
        "pending_reservations": pending_reservations,
        "upcoming_reservations": upcoming_reservations,
        "recent_reservations": recent_reservations,
        "pending_delivery_orders": pending_delivery_orders,
        "completed_delivery_orders": completed_delivery_orders,
        "active_items_count": active_items_count,
        "recent_delivery_orders": recent_delivery_orders,
    }
    return render(request, "admin/dashboard.html", context)


@login_required
def add_menu_item(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = MenuItemForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, _("Menu item created successfully."))
            return redirect(reverse("restaurant:dashboard"))
    else:
        form = MenuItemForm()
    return render(request, "admin/add_item.html", {"form": form})


@login_required
def edit_menu_item(request: HttpRequest, pk: int) -> HttpResponse:
    item = get_object_or_404(MenuItem, pk=pk)
    if request.method == "POST":
        form = MenuItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Menu item updated.")
            return redirect(reverse("restaurant:dashboard"))
    else:
        form = MenuItemForm(instance=item)
    return render(request, "admin/edit_item.html", {"form": form, "item": item})


@login_required
def delete_menu_item(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)

    if request.method == "POST":
        try:
            item.delete()
            messages.success(request, "Menu item deleted.")
            return redirect(reverse("restaurant:dashboard"))

        except ProtectedError:
            # cannot delete because used in ReservationItem
            item.status = MenuItem.STATUS_HIDDEN
            item.save(update_fields=["status"])
            messages.warning(
                request,
                "This item cannot be deleted because it was used in reservations/orders. "
                "It has been hidden instead.",
            )
            return redirect(reverse("restaurant:dashboard"))

    return render(request, "admin/delete_item.html", {"item": item})


@login_required
def categories_list(request: HttpRequest) -> HttpResponse:
    categories = Category.objects.all().order_by("order", "name")
    return render(request, "admin/categories.html", {"categories": categories})


@login_required
def add_category(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created.")
            return redirect(reverse("restaurant:categories_list"))
    else:
        form = CategoryForm()
    return render(request, "admin/add_category.html", {"form": form})


@login_required
def edit_category(request: HttpRequest, pk: int) -> HttpResponse:
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated.")
            return redirect(reverse("restaurant:categories_list"))
    else:
        form = CategoryForm(instance=category)
    return render(
        request, "admin/edit_category.html", {"form": form, "category": category}
    )


@login_required
def delete_category(request: HttpRequest, pk: int) -> HttpResponse:
    category = get_object_or_404(Category, pk=pk)
    has_items = category.menu_items.exists()

    if request.method == "POST":
        if has_items:
            messages.error(
                request, "Cannot delete category while it contains menu items."
            )
            return redirect(reverse("restaurant:categories_list"))
        category.delete()
        messages.success(request, "Category deleted.")
        return redirect(reverse("restaurant:categories_list"))

    return render(
        request,
        "admin/delete_category.html",
        {"category": category, "has_items": has_items},
    )


@login_required
def menu_items_list(request: HttpRequest) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    category_slug = (request.GET.get("category") or "").strip()
    status = (request.GET.get("status") or "").strip()

    items = MenuItem.objects.select_related("category").all().order_by("-created_at")

    if q:
        items = items.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category_slug:
        items = items.filter(category__slug=category_slug)
    if status:
        items = items.filter(status=status)

    categories = Category.objects.all().order_by("order", "name")

    return render(
        request,
        "admin/menu_items.html",
        {
            "items": items,
            "categories": categories,
            "q": q,
            "category_slug": category_slug,
            "status": status,
        },
    )


@require_POST
@login_required
def menu_items_bulk_update(request: HttpRequest) -> HttpResponse:
    ids = request.POST.getlist("item_ids")
    new_status = (request.POST.get("new_status") or "").strip()

    valid = {MenuItem.STATUS_ACTIVE, MenuItem.STATUS_SOLD_OUT, MenuItem.STATUS_HIDDEN}
    if new_status not in valid:
        messages.error(request, "Please choose a valid status.")
        return redirect("restaurant:menu_items_list")

    ids_int = [int(x) for x in ids if str(x).isdigit()]
    if not ids_int:
        messages.error(request, "No items selected.")
        return redirect("restaurant:menu_items_list")

    updated = MenuItem.objects.filter(id__in=ids_int).update(status=new_status)
    messages.success(request, f"Updated {updated} item(s).")
    return redirect("restaurant:menu_items_list")


@require_POST
@login_required
def menu_items_bulk_delete(request: HttpRequest) -> HttpResponse:
    ids = request.POST.getlist("item_ids")
    ids_int = [int(x) for x in ids if str(x).isdigit()]

    if not ids_int:
        messages.error(request, "No items selected.")
        return redirect("restaurant:menu_items_list")

    deleted = 0
    hidden = 0

    for pk in ids_int:
        item = MenuItem.objects.filter(pk=pk).first()
        if not item:
            continue
        try:
            item.delete()
            deleted += 1
        except ProtectedError:
            # used in ReservationItem / etc -> hide instead
            item.status = MenuItem.STATUS_HIDDEN
            item.save(update_fields=["status"])
            hidden += 1

    if deleted and hidden:
        messages.success(
            request, f"Deleted {deleted} item(s), hidden {hidden} item(s) (in use)."
        )
    elif deleted:
        messages.success(request, f"Deleted {deleted} item(s).")
    elif hidden:
        messages.success(request, f"Hidden {hidden} item(s) (in use).")
    else:
        messages.info(request, "No changes made.")

    return redirect("restaurant:menu_items_list")


@login_required
def reservations_list(request: HttpRequest) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = Reservation.objects.all().order_by("-start_datetime", "-created_at")
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)

    return render(
        request,
        "admin/reservations.html",
        {
            "reservations": qs[:300],
            "q": q,
            "status": status,
            "status_choices": Reservation.STATUS_CHOICES,
        },
    )


@login_required
def reservation_detail_admin(request: HttpRequest, pk: int) -> HttpResponse:
    r = get_object_or_404(
        Reservation.objects.prefetch_related("items__menu_item"), pk=pk
    )
    return render(request, "admin/reservation_detail.html", {"r": r})


@login_required
def reservation_update_status(request: HttpRequest, pk: int) -> HttpResponse:
    r = get_object_or_404(Reservation, pk=pk)
    if request.method == "POST":
        new_status = (request.POST.get("status") or "").strip()
        valid = {k for k, _ in Reservation.STATUS_CHOICES}
        if new_status in valid:
            r.status = new_status
            r.save(update_fields=["status"])
            messages.success(request, "Reservation status updated.")
        else:
            messages.error(request, "Invalid status.")
    return redirect(reverse("restaurant:reservation_detail_admin", args=[pk]))


@require_POST
@login_required
def reservations_bulk_update(request: HttpRequest) -> HttpResponse:
    ids = request.POST.getlist("reservation_ids")
    new_status = (request.POST.get("new_status") or "").strip()

    valid = {k for k, _ in Reservation.STATUS_CHOICES}
    if new_status not in valid:
        messages.error(request, "Please choose a valid status.")
        return redirect("restaurant:reservations_list")

    ids_int = [int(x) for x in ids if str(x).isdigit()]
    if not ids_int:
        messages.error(request, "No reservations selected.")
        return redirect("restaurant:reservations_list")

    updated = Reservation.objects.filter(id__in=ids_int).update(status=new_status)
    messages.success(request, f"Updated {updated} reservation(s).")
    return redirect("restaurant:reservations_list")


@require_POST
@login_required
def reservations_bulk_delete(request: HttpRequest) -> HttpResponse:
    ids = request.POST.getlist("reservation_ids")
    ids_int = [int(x) for x in ids if str(x).isdigit()]

    if not ids_int:
        messages.error(request, "No reservations selected.")
        return redirect("restaurant:reservations_list")

    deleted_count, _ = Reservation.objects.filter(id__in=ids_int).delete()
    messages.success(request, f"Deleted {deleted_count} record(s).")
    return redirect("restaurant:reservations_list")

def reservation(request: HttpRequest) -> HttpResponse:
    """Public reservation page (with optional pre-order items)."""

    categories = Category.objects.filter(is_active=True).order_by("order", "name")
    menu_items = (
        MenuItem.objects.select_related("category")
        .exclude(status=MenuItem.STATUS_HIDDEN)
        .order_by("category__order", "category__name", "name")
    )

    reservation_obj = None
    show_modal = False

    if request.method == "POST":
        form = ReservationForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                r = form.save(commit=False)
                r.user = request.user if request.user.is_authenticated else None
                r.save()

                # ---- Handle pre-order items ----
                preorder_ids = request.POST.getlist("preorder_ids")
                preorder_qty = request.POST.getlist("preorder_qty")

                bulk = []
                for mid, qty in zip(preorder_ids, preorder_qty):
                    if not str(mid).isdigit():
                        continue
                    qty_i = int(qty) if str(qty).isdigit() else 0
                    if qty_i <= 0:
                        continue

                    mi = (
                        MenuItem.objects.filter(id=int(mid))
                        .exclude(status=MenuItem.STATUS_HIDDEN)
                        .first()
                    )
                    if not mi:
                        continue

                    bulk.append(
                        ReservationItem(
                            reservation=r,
                            menu_item=mi,
                            qty=qty_i,
                            unit_price=mi.price,
                        )
                    )

                if bulk:
                    ReservationItem.objects.bulk_create(bulk)

            # ✅ store last reservation id in session (for success modal)
            request.session["last_reservation_id"] = r.id
            request.session.modified = True

            # --- Telegram notify (safe: never breaks reservation) ---
            try:
                from restaurant.telegram_utils import send_telegram_message
                from django.utils import timezone

                dt_local = timezone.localtime(r.start_datetime)
                when = dt_local.strftime("%d %b %Y, %I:%M %p")

                preorder_lines = [
                    f"• {it.menu_item.name} × {it.qty} = € {(it.unit_price * it.qty):.2f}"
                    for it in r.items.select_related("menu_item").all()
                ]
                preorder_text = "\n".join(preorder_lines) if preorder_lines else "—"

                msg = (
                    f"📅 NEW RESERVATION\n\n"
                    f"ID: #{r.id}\n"
                    f"Name: {r.name}\n"
                    f"Phone: {r.phone}\n"
                    f"Email: {r.email or '-'}\n"
                    f"Date & Time: {when}\n"
                    f"Party size: {r.party_size}\n"
                    f"Baby seats: {r.baby_seats}\n"
                    f"Preferred table: {r.preferred_table or '-'}\n"
                    f"Notes: {r.notes or '-'}\n\n"
                    f"Pre-order:\n{preorder_text}"
                )

                send_telegram_message(msg, kind="reservation")

            except Exception as e:
                try:
                    from restaurant.models import TelegramLog
                    TelegramLog.objects.create(
                        ok=False,
                        kind="reservation",
                        chat_id=str(getattr(settings, "TELEGRAM_GROUP_CHAT_ID", "")),
                        message_preview="reservation telegram failed",
                        response_text=repr(e),
                    )
                except Exception:
                    pass

            return redirect(reverse("restaurant:reservation") + "?placed=1")

    else:
        form = ReservationForm()

    # -------------------------
    # SUCCESS MODAL LOGIC
    # -------------------------
    placed = request.GET.get("placed") == "1"
    if placed:
        last_id = request.session.get("last_reservation_id")
        if last_id:
            reservation_obj = (
                Reservation.objects.prefetch_related("items__menu_item")
                .filter(id=last_id)
                .first()
            )
            show_modal = bool(reservation_obj)

            # remove so it only shows once
            request.session.pop("last_reservation_id", None)
            request.session.modified = True

    return render(
        request,
        "reservation.html",
        {
            "form": form,
            "categories": categories,
            "menu_items": menu_items,
            "show_reservation_modal": show_modal,
            "reservation_obj": reservation_obj,
        },
    )

# -------------------------
# Delivery (location + calc + order + checkout)
# -------------------------


def _active_promo() -> DeliveryPromotion | None:
    promo = (
        DeliveryPromotion.objects.filter(is_active=True).order_by("-created_at").first()
    )
    if promo and promo.is_current():
        return promo
    return None


def _apply_promo_delivery_fee(fee: float, subtotal: float) -> tuple[float, dict]:
    promo = _active_promo()
    if not promo:
        return float(fee), {"active": False}

    min_sub = float(promo.min_subtotal or 0)
    ok_min = subtotal >= min_sub

    return float(fee), {
        "active": True,
        "title": promo.title,
        "free_delivery": False,  # force false
        "min_subtotal": min_sub,
    }


from datetime import datetime
import secrets

# -------------------------
# Loyalty config loader
# -------------------------

def _loyalty_config():
    from .models import LoyaltyProgram

    obj = LoyaltyProgram.objects.first()
    if not obj or not obj.is_active:
        return {
            "enabled": False,
            "target": 10,
            "percent": 30,
        }

    return {
        "enabled": True,
        "target": int(obj.target_orders or 10),
        "percent": int(obj.reward_percent or 30),
    }

def _month_bounds(now=None):
    now = now or timezone.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # next month
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _issued_month_str(now=None) -> str:
    now = now or timezone.now()
    return now.strftime("%Y-%m")


def _loyalty_delivered_count(user) -> int:
    if not user or not user.is_authenticated:
        return 0
    start, end = _month_bounds()
    return DeliveryOrder.objects.filter(
        user=user,
        status=DeliveryOrder.STATUS_DELIVERED,
        created_at__gte=start,
        created_at__lt=end,
    ).count()


def _ensure_loyalty_coupon_for_user(user) -> DeliveryCoupon | None:
    if not user or not user.is_authenticated:
        return None

    cfg = _loyalty_config()
    if not cfg["enabled"]:
        return None

    target = int(cfg["target"] or 10)
    percent = int(cfg["percent"] or 30)

    count = _loyalty_delivered_count(user)
    if count < target:
        return None

    month_key = _issued_month_str()

    existing = DeliveryCoupon.objects.filter(
        is_active=True,
        is_personal=True,
        assigned_user=user,
        issued_month=month_key,
        discount_type=DeliveryCoupon.DISCOUNT_PERCENT,
        discount_value=Decimal(str(percent)),
    ).first()

    if existing and existing.is_current():
        return existing

    # create a new one-time coupon for this month
    code = f"LOYAL{percent}-" + secrets.token_hex(3).upper()

    start, end = _month_bounds()
    coupon = DeliveryCoupon.objects.create(
        code=code,
        is_active=True,
        discount_type=DeliveryCoupon.DISCOUNT_PERCENT,
        discount_value=Decimal(str(percent)),
        min_subtotal=Decimal("0"),
        start_at=start,
        end_at=end,
        max_uses=1,
        used_count=0,
        # personal loyalty
        is_personal=True,
        assigned_user=user,
        issued_month=month_key,
    )
    return coupon
def _loyalty_ui_context(user) -> dict:
    """
    What you show to the user as notification/progress.
    """
    if not user or not user.is_authenticated:
        return {"enabled": False}

    cfg = _loyalty_config()
    if not cfg["enabled"]:
        return {"enabled": False}

    target = int(cfg["target"] or 10)
    percent = int(cfg["percent"] or 30)

    count = _loyalty_delivered_count(user)
    remaining = max(0, target - count)

    coupon = None
    if count >= target:
        coupon = _ensure_loyalty_coupon_for_user(user)

    return {
        "enabled": True,
        "count": count,
        "target": target,
        "remaining": remaining,
        "percent": percent,
        "earned": bool(coupon),
        "coupon_code": coupon.code if coupon else "",
        "month": _issued_month_str(),
    }

# -------------------------
# Coupon helpers
# -------------------------


def _get_coupon_from_session(request: HttpRequest) -> DeliveryCoupon | None:
    code = (request.session.get("delivery_coupon_code") or "").strip()
    if not code:
        return None

    coupon = DeliveryCoupon.objects.filter(code__iexact=code).first()
    if not coupon or not coupon.is_current():
        return None  # ✅ never redirect from helper

    # ✅ If it’s a personal coupon, enforce login + ownership
    if getattr(coupon, "is_personal", False):
        if not request.user.is_authenticated:
            return None

        if coupon.assigned_user_id and coupon.assigned_user_id != request.user.id:
            return None

    # ✅ Normal coupons come here too
    return coupon
    # ✅ block using someone else’s personal coupon
    if getattr(coupon, "is_personal", False):
        if not request.user.is_authenticated:
            msg = "Please log in to use this coupon."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": msg}, status=400)
            messages.error(request, msg)
            return _back()

        if coupon.assigned_user_id and coupon.assigned_user_id != request.user.id:
            msg = "This coupon is not for your account."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": msg}, status=400)
            messages.error(request, msg)
            return _back()


def _coupon_discount_for_request(
    request: HttpRequest, subtotal: float
) -> tuple[float, dict]:
    coupon = _get_coupon_from_session(request)
    if not coupon:
        return 0.0, {"active": False}

    # Free delivery coupon: no subtotal discount, but still "active"
    if coupon.discount_type == DeliveryCoupon.DISCOUNT_FREE_DELIVERY:
        ok = coupon.grants_free_delivery(Decimal(str(subtotal)))
        return 0.0, {
            "active": True,
            "code": coupon.code,
            "type": coupon.discount_type,
            "value": 0,
            "min_subtotal": float(coupon.min_subtotal or 0),
            "free_delivery": bool(ok),
        }

    # Percent / fixed coupon:
    disc = coupon.compute_discount(Decimal(str(subtotal)))
    disc_f = float(disc)

    # ✅ IMPORTANT: if subtotal is 0, keep coupon ACTIVE for UI preview
    if float(subtotal) <= 0:
        return 0.0, {
            "active": True,
            "code": coupon.code,
            "type": coupon.discount_type,
            "value": float(coupon.discount_value or 0),
            "min_subtotal": float(coupon.min_subtotal or 0),
            "free_delivery": False,
        }

    # If subtotal > 0 but discount still 0, treat as inactive
    if disc_f <= 0:
        return 0.0, {"active": False}

    return disc_f, {
        "active": True,
        "code": coupon.code,
        "discount": round(disc_f, 2),
        "type": coupon.discount_type,
        "value": float(coupon.discount_value or 0),
        "min_subtotal": float(coupon.min_subtotal or 0),
        "free_delivery": False,
    }


# --- Session cart (ONE system only) ---


def _cart_get(session) -> dict:
    """
    Cart stored in session as:
    {
      "items": { "12": {"qty": 2}, "5": {"qty": 1} },
    }
    """
    cart = session.get("delivery_cart")
    if not isinstance(cart, dict):
        cart = {"items": {}}
        session["delivery_cart"] = cart
    if "items" not in cart or not isinstance(cart["items"], dict):
        cart["items"] = {}
        session["delivery_cart"] = cart
    return cart


def _cart_subtotal(request: HttpRequest) -> float:
    """Subtotal using the ONE cart structure."""
    cart = _cart_get(request.session)
    items_map = cart.get("items", {}) if isinstance(cart, dict) else {}

    ids: list[int] = []
    qty_map: dict[int, int] = {}

    for k, v in items_map.items():
        try:
            mid = int(k)
            qty = int((v or {}).get("qty", 0))
        except Exception:
            continue
        if qty <= 0:
            continue
        ids.append(mid)
        qty_map[mid] = qty

    if not ids:
        return 0.0

    qs = MenuItem.objects.filter(id__in=ids).exclude(status=MenuItem.STATUS_HIDDEN)
    subtotal = 0.0
    for mi in qs:
        subtotal += float(mi.price) * float(qty_map.get(mi.id, 0))
    return float(subtotal)


def _cart_totals(request: HttpRequest) -> dict:
    """
    Computes totals using MenuItem prices.
    Returns dict: subtotal, delivery_fee, total, count, lines[]
    """
    cart = _cart_get(request.session)
    items_map = cart.get("items", {})
    ids: list[int] = []
    qty_map: dict[int, int] = {}

    for k, v in items_map.items():
        try:
            mid = int(k)
            qty = int((v or {}).get("qty", 0))
        except Exception:
            continue
        if qty <= 0:
            continue
        ids.append(mid)
        qty_map[mid] = qty

    qs = MenuItem.objects.filter(id__in=ids).exclude(status=MenuItem.STATUS_HIDDEN)
    price_map = {m.id: float(m.price) for m in qs}

    lines = []
    subtotal = 0.0
    count = 0

    # keep stable order (ids order)
    for mid in ids:
        if mid not in price_map:
            continue
        qty = qty_map.get(mid, 0)
        price = price_map[mid]
        line_total = price * qty
        subtotal += line_total
        count += qty
        mi = next((m for m in qs if m.id == mid), None)
        lines.append(
            {
                "id": mid,
                "name": mi.name if mi else f"Item {mid}",
                "qty": qty,
                "unit_price": round(price, 2),
                "line_total": round(line_total, 2),
            }
        )

    fee = float(request.session.get("delivery_fee", 0) or 0)

    # coupon discount (applies to subtotal only)
    discount, coupon_info = _coupon_discount_for_request(request, subtotal)

    coupon = _get_coupon_from_session(request)

    if coupon and coupon.discount_type == DeliveryCoupon.DISCOUNT_FREE_DELIVERY:
        # Only free delivery if subtotal meets coupon min
        ok = coupon.grants_free_delivery(Decimal(str(subtotal)))
        if ok:
            fee = 0.0
            coupon_info["free_delivery"] = True
        else:
            coupon_info["free_delivery"] = False

    # If cart empty, force fee/discount zero
    # If cart empty: force totals zero, BUT keep coupon_info for UI preview
    if count <= 0:
        fee = 0.0
        discount = 0.0
        subtotal = 0.0

        coupon = _get_coupon_from_session(request)
        if coupon:
            coupon_info = {
                "active": True,
                "code": coupon.code,
                "type": coupon.discount_type,
                "value": float(coupon.discount_value or 0),
                "min_subtotal": float(coupon.min_subtotal or 0),
                "free_delivery": False,
            }
            if coupon.discount_type == DeliveryCoupon.DISCOUNT_FREE_DELIVERY:
                coupon_info["free_delivery"] = False
        else:
            coupon_info = {"active": False}

    total = max(0.0, float(subtotal) - float(discount)) + float(fee)

    return {
        "subtotal": round(subtotal, 2),
        "delivery_fee": round(fee, 2),
        "coupon_discount": round(float(discount), 2),
        "coupon": coupon_info,
        "total": round(total, 2),
        "count": count,
        "lines": lines,
        "delivery_fee_waived": bool(coupon_info.get("free_delivery")),  # ✅ NEW
    }


def delivery_location(request: HttpRequest) -> HttpResponse:
    promo = _active_promo()
    ctx = {
        "rest_lat": getattr(settings, "RESTAURANT_LAT", 0),
        "rest_lng": getattr(settings, "RESTAURANT_LNG", 0),
        "max_radius": getattr(settings, "DELIVERY_MAX_RADIUS_KM", 10.0),
        "promo_active": bool(promo),
        "promo_title": promo.title if promo else "",
        "promo_min_subtotal": float(promo.min_subtotal) if promo else 0.0,
        "promo_free_delivery": bool(promo.free_delivery) if promo else False,
        # Optional: only if you ever want to render/use it in the partial itself
        "GOOGLE_MAPS_API_KEY": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }

    return render(request, "delivery_location.html", ctx)


@require_POST
def delivery_calc(request: HttpRequest) -> JsonResponse:
    try:
        lat = float(request.POST.get("lat"))
        lng = float(request.POST.get("lng"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid coordinates"}, status=400)

    rest_lat = float(getattr(settings, "RESTAURANT_LAT", 0))
    rest_lng = float(getattr(settings, "RESTAURANT_LNG", 0))

    distance_km = haversine_km(rest_lat, rest_lng, lat, lng)
    base_fee = float(delivery_fee_for_distance(distance_km))

    max_radius = float(getattr(settings, "DELIVERY_MAX_RADIUS_KM", 10.0))
    in_range = distance_km <= max_radius

    subtotal = _cart_subtotal(request)
    final_fee, promo_info = _apply_promo_delivery_fee(base_fee, subtotal)

    return JsonResponse(
        {
            "ok": True,
            "distance_km": round(distance_km, 2),
            "delivery_fee": round(float(final_fee), 2),
            "base_delivery_fee": round(float(base_fee), 2),
            "subtotal": round(float(subtotal), 2),
            "estimated_total": round(float(subtotal + float(final_fee)), 2),
            "in_range": in_range,
            "max_radius_km": max_radius,
            "promo": promo_info,
        }
    )


@require_POST
def delivery_set_location(request: HttpRequest) -> HttpResponse:
    """Save location + fee + address label to session."""
    try:
        lat = float(request.POST.get("lat"))
        lng = float(request.POST.get("lng"))
    except (TypeError, ValueError):
        return redirect(reverse("restaurant:menu") + "?open_location=1")

    address_label = (request.POST.get("address_label") or "").strip()

    rest_lat = float(getattr(settings, "RESTAURANT_LAT", 0))
    rest_lng = float(getattr(settings, "RESTAURANT_LNG", 0))

    distance_km = haversine_km(rest_lat, rest_lng, lat, lng)
    base_fee = float(delivery_fee_for_distance(distance_km))

    subtotal = _cart_subtotal(request)
    final_fee, promo_info = _apply_promo_delivery_fee(base_fee, subtotal)

    request.session["delivery_lat"] = lat
    request.session["delivery_lng"] = lng
    request.session["delivery_distance_km"] = round(distance_km, 2)
    request.session["delivery_fee"] = round(float(final_fee), 2)
    request.session["delivery_base_fee"] = round(float(base_fee), 2)
    request.session["delivery_promo"] = promo_info
    request.session["delivery_address_label"] = address_label
    request.session.modified = True

    return redirect(reverse("restaurant:menu") + "?delivery=1")


# -------------------------
# Cart endpoints (AJAX)
# -------------------------


@require_POST
def delivery_cart_add(request: HttpRequest) -> JsonResponse:
    """POST: item_id, qty(optional default=1)"""
    try:
        item_id = int(request.POST.get("item_id"))
        qty = int(request.POST.get("qty", 1))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid payload"}, status=400)

    if qty <= 0:
        qty = 1

    mi = get_object_or_404(MenuItem, id=item_id)
    if mi.status == MenuItem.STATUS_HIDDEN:
        return JsonResponse({"ok": False, "error": "Item not available"}, status=404)

    cart = _cart_get(request.session)
    items = cart["items"]
    k = str(item_id)
    cur = int((items.get(k) or {}).get("qty", 0))
    items[k] = {"qty": cur + qty}
    request.session.modified = True

    totals = _cart_totals(request)
    return JsonResponse({"ok": True, "cart": totals})


@require_POST
def delivery_cart_update(request: HttpRequest) -> JsonResponse:
    """POST: item_id, qty"""
    try:
        item_id = int(request.POST.get("item_id"))
        qty = int(request.POST.get("qty"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid payload"}, status=400)

    mi = get_object_or_404(MenuItem, id=item_id)
    if mi.status == MenuItem.STATUS_HIDDEN:
        return JsonResponse({"ok": False, "error": "Item not available"}, status=404)

    cart = _cart_get(request.session)
    items = cart["items"]
    k = str(item_id)

    if qty <= 0:
        if k in items:
            del items[k]
    else:
        items[k] = {"qty": qty}

    request.session.modified = True
    totals = _cart_totals(request)
    return JsonResponse({"ok": True, "cart": totals})


@require_GET
def delivery_cart_summary(request: HttpRequest) -> JsonResponse:
    totals = _cart_totals(request)
    return JsonResponse({"ok": True, "cart": totals})


# -------------------------
# Nominatim helpers
# -------------------------


@require_GET
def nominatim_search(request: HttpRequest) -> JsonResponse:
    q = (request.GET.get("q") or "").strip()
    if len(q) < 3:
        return JsonResponse({"ok": True, "results": []})

    params = {
        "q": q,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 6,
        "countrycodes": "fi",
    }

    url = "https://nominatim.openstreetmap.org/search?" + urlencode(params)

    try:
        req = Request(url, headers=_nominatim_headers())
        with urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = [
            {
                "display_name": it.get("display_name", ""),
                "lat": it.get("lat"),
                "lon": it.get("lon"),
            }
            for it in data
        ]
        return JsonResponse({"ok": True, "results": results})
    except Exception:
        return JsonResponse({"ok": False, "results": []}, status=200)


@require_GET
def nominatim_reverse(request: HttpRequest) -> JsonResponse:
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")
    if not lat or not lon:
        return JsonResponse({"ok": False, "label": ""})

    params = {"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1}
    url = "https://nominatim.openstreetmap.org/reverse?" + urlencode(params)

    try:
        req = Request(url, headers=_nominatim_headers())
        with urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return JsonResponse({"ok": True, "label": data.get("display_name", "")})
    except Exception:
        return JsonResponse({"ok": False, "label": ""})


def _nominatim_headers() -> dict:
    ua = getattr(
        settings,
        "NOMINATIM_USER_AGENT",
        "RavintolaSinet/1.0 (contact: info@ravintola-sinet.fi)",
    )
    return {
        "User-Agent": ua,
        "Accept": "application/json",
        "Referer": getattr(settings, "SITE_URL", "http://127.0.0.1:8000/"),
    }


# -------------------------
# Promotions placeholders
# -------------------------


@login_required
def promotions_list(request: HttpRequest) -> HttpResponse:
    try:
        from .models import Promotion  # optional

        promos = Promotion.objects.all().order_by("-id")
    except Exception:
        promos = []

    try:
        return render(request, "admin/promotions.html", {"promos": promos})
    except Exception:
        html = "<h2>Promotions</h2><p>Promotions UI not created yet.</p>"
        html += "<p>Your URLs are working now ✅</p>"
        return HttpResponse(html)


@login_required
def add_promotion(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        messages.success(request, "Promotion saved (placeholder).")
        return redirect("restaurant:promotions_list")

    try:
        return render(request, "admin/promotion_add.html")
    except Exception:
        return HttpResponse("<h2>Add Promotion</h2><p>Template not created yet.</p>")


@login_required
def edit_promotion(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method == "POST":
        messages.success(request, "Promotion updated (placeholder).")
        return redirect("restaurant:promotions_list")

    try:
        return render(request, "admin/promotion_edit.html", {"pk": pk})
    except Exception:
        return HttpResponse(f"<h2>Edit Promotion</h2><p>ID: {pk}</p>")


@login_required
def delete_promotion(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method == "POST":
        messages.success(request, "Promotion deleted (placeholder).")
        return redirect("restaurant:promotions_list")

    try:
        return render(request, "admin/promotion_delete.html", {"pk": pk})
    except Exception:
        return HttpResponse(f"<h2>Delete Promotion</h2><p>ID: {pk}</p>")


# -------------------------
# Delivery checkout + coupons + place order
# -------------------------


def delivery_checkout(request: HttpRequest) -> HttpResponse:
    # Must have location
    if not request.session.get("delivery_lat") or not request.session.get(
        "delivery_lng"
    ):
        messages.error(request, _("Please set your delivery location first."))
        return redirect(reverse("restaurant:menu") + "?open_location=1")

    # If form was posted: save info to session then redirect
    if request.method == "POST":
        request.session["customer_name"] = (request.POST.get("name") or "").strip()
        request.session["customer_phone"] = (request.POST.get("phone") or "").strip()
        request.session["customer_note"] = (request.POST.get("note") or "").strip()
        request.session["customer_address_extra"] = (
            request.POST.get("address_extra") or ""
        ).strip()

        pm = (request.POST.get("payment_method") or "").strip()
        if pm in ["cash", "card"]:
            request.session["payment_method"] = pm

        request.session.modified = True
        return redirect("restaurant:delivery_checkout")

    # ✅ 1) Order-confirm modal logic FIRST
    placed = (request.GET.get("placed") or "").strip() == "1"
    order_obj = None

    order_id = (request.GET.get("order") or "").strip()
    if not order_id.isdigit():
        order_id = str(request.session.get("last_delivery_order_id") or "")

    if placed and order_id.isdigit():
        order_obj = (
            DeliveryOrder.objects.prefetch_related("items")
            .filter(id=int(order_id))
            .first()
        )

    # ✅ Security: only show modal for this session's latest order
    if order_obj and int(order_id) != int(
        request.session.get("last_delivery_order_id") or 0
    ):
        order_obj = None

    # ✅ 2) Then compute cart
    cart = _cart_totals(request)

    # ✅ 3) If cart empty, allow ONLY when order modal exists
    if int(cart.get("count") or 0) <= 0 and not order_obj:
        messages.error(request, _("Your cart is empty."))
        return redirect(reverse("restaurant:menu"))

    # Payment label
    pm = (request.session.get("payment_method") or "cash").strip()
    if pm not in ["cash", "card"]:
        pm = "cash"
    pay_method_label = (
        _("Cash on Delivery") if pm == "cash" else _("Card on Delivery (POS machine)")
    )

    ctx = {
        "address_label": request.session.get("delivery_address_label", ""),
        "distance_km": request.session.get("delivery_distance_km", 0),
        "delivery_fee": request.session.get("delivery_fee", 0),
        "promo": request.session.get("delivery_promo") or {"active": False},
        "cart": cart,
        "name": request.session.get("customer_name", ""),
        "phone": request.session.get("customer_phone", ""),
        "note": request.session.get("customer_note", ""),
        "address_extra": request.session.get("customer_address_extra", ""),
        "pay_method": pay_method_label,
        "coupon_code": request.session.get("delivery_coupon_code", ""),
        "show_order_modal": bool(order_obj),
        "order_obj": order_obj,
        "loyalty": _loyalty_ui_context(request.user),
    }

    # ✅ show confirmation only once
    if order_obj:
        request.session.pop("last_delivery_order_id", None)
        request.session.modified = True

    return render(request, "delivery_checkout.html", ctx)


@require_POST
def delivery_apply_coupon(request: HttpRequest):
    """
    Apply coupon:
    - If AJAX: return JSON (no redirect)
    - Else: redirect back to previous page (fallback)
    """
    code = (request.POST.get("coupon_code") or "").strip()

    # helper for fallback redirect
    def _back():
        return redirect(request.META.get("HTTP_REFERER") or reverse("restaurant:menu"))

    if not code:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "error": "Please enter a coupon code."}, status=400
            )
        messages.error(request, "Please enter a coupon code.")
        return _back()

    coupon = DeliveryCoupon.objects.filter(code__iexact=code).first()
    if not coupon or not coupon.is_current():
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "error": "Invalid or expired coupon."}, status=400
            )
        messages.error(request, "Invalid or expired coupon.")
        return _back()

    # check min subtotal against current subtotal (before coupon)
    cart = _cart_totals(request)
    subtotal = Decimal(str(cart.get("subtotal") or 0))
    if subtotal < Decimal(str(coupon.min_subtotal or 0)):
        msg = f"Coupon requires minimum subtotal € {coupon.min_subtotal}."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": msg}, status=400)
        messages.error(request, msg)
        return _back()

    request.session["delivery_coupon_code"] = coupon.code
    request.session.modified = True

    # return updated totals
    updated = _cart_totals(request)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "cart": updated})

    messages.success(request, f"Coupon {coupon.code} applied.")
    return _back()


@require_POST
def delivery_remove_coupon(request: HttpRequest):
    """
    Remove coupon:
    - If AJAX: return JSON (no redirect)
    - Else: redirect back to previous page (fallback)
    """
    request.session.pop("delivery_coupon_code", None)
    request.session.modified = True

    updated = _cart_totals(request)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "cart": updated})

    messages.success(request, "Coupon removed.")
    return redirect(request.META.get("HTTP_REFERER") or reverse("restaurant:menu"))



def _normalize_fi_phone(raw: str) -> str:
    """
    Validate Finnish phone number.
    Allowed formats ONLY:
      - +358XXXXXXXX
      - 358XXXXXXXX
    Returns cleaned string (spaces/dashes removed) or "" if invalid.
    """
    s = (raw or "").strip()
    if not s:
        return ""

    # remove spaces/dashes/parentheses
    s = re.sub(r"[()\s\-]", "", s)

    # must be digits with optional leading +
    if not re.fullmatch(r"\+?\d+", s):
        return ""

    # +358........
    if s.startswith("+358"):
        rest = s[4:]
        if 6 <= len(rest) <= 12:
            return s

    # 358........ (no +)
    if s.startswith("358"):
        rest = s[3:]
        if 6 <= len(rest) <= 12:
            return s

    return ""


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


@require_POST
def delivery_place_order(request: HttpRequest) -> HttpResponse:
    # must have location
    if not request.session.get("delivery_lat") or not request.session.get(
        "delivery_lng"
    ):
        messages.error(request, "Please set your delivery location first.")
        return redirect(reverse("restaurant:menu") + "?open_location=1")

    # must have cart items
    cart = _cart_totals(request)
    lines = cart.get("lines") or []
    if not lines:
        messages.error(request, "Your cart is empty.")
        return redirect(reverse("restaurant:menu") + "?delivery=1")

    # ✅ FIX: move this OUTSIDE the if-block
    name = (request.POST.get("name") or "").strip() or (
        request.session.get("customer_name") or ""
    ).strip()
    phone = (request.POST.get("phone") or "").strip() or (
        request.session.get("customer_phone") or ""
    ).strip()
    note = (request.POST.get("note") or "").strip() or (
        request.session.get("customer_note") or ""
    ).strip()
    extra = (request.POST.get("address_extra") or "").strip() or (
        request.session.get("customer_address_extra") or ""
    ).strip()
    payment_method = (request.POST.get("payment_method") or "cash").strip()

    if payment_method not in ["cash", "card"]:
        payment_method = "cash"

    if not name or not phone:
        messages.error(request, _("Please enter your name and phone number."))
        return redirect("restaurant:delivery_checkout")

    normalized_phone = _normalize_fi_phone(phone)
    if not normalized_phone:
        messages.error(
            request,
            _("Please use a valid Finland number to order (start with +358 or 358).")
        )
        return redirect("restaurant:delivery_checkout")

    # use normalized phone everywhere from now on
    phone = normalized_phone
    request.session["customer_phone"] = phone
    request.session.modified = True

    lat = float(request.session["delivery_lat"])
    lng = float(request.session["delivery_lng"])
    distance_km = float(request.session.get("delivery_distance_km") or 0)
    address_label = (request.session.get("delivery_address_label") or "").strip()

    promo = request.session.get("delivery_promo") or {"active": False}

    subtotal = Decimal(str(cart.get("subtotal") or 0))
    fee = Decimal(str(cart.get("delivery_fee") or 0))
    total = Decimal(str(cart.get("total") or (float(subtotal) + float(fee))))

    # coupon snapshot
    coupon = _get_coupon_from_session(request)
    coupon_code = coupon.code if coupon else ""
    coupon_discount = Decimal("0")
    if coupon:
        coupon_discount = coupon.compute_discount(subtotal)

    # create order
    order = DeliveryOrder.objects.create(
        user=request.user if request.user.is_authenticated else None,
        customer_name=name,
        customer_phone=phone,
        customer_note=note,
        address_label=address_label,
        address_extra=extra,
        lat=lat,
        lng=lng,
        distance_km=distance_km,
        subtotal=subtotal,
        delivery_fee=fee,
        total=total,
        promo_title=str(promo.get("title") or ""),
        promo_free_delivery=bool(promo.get("free_delivery") or False),
        promo_min_subtotal=Decimal(str(promo.get("min_subtotal") or 0)),
        coupon_code=coupon_code,
        coupon_discount=coupon_discount,
        payment_method=payment_method,
    )

    # snapshot items (NO menu_item FK in model)
    ids = [int(x["id"]) for x in lines if str(x.get("id", "")).isdigit()]
    menu_map = {
        m.id: m
        for m in MenuItem.objects.filter(id__in=ids).exclude(
            status=MenuItem.STATUS_HIDDEN
        )
    }

    bulk = []
    for line in lines:
        mid_raw = line.get("id")
        if not str(mid_raw).isdigit():
            continue
        mid = int(mid_raw)

        qty = int(line.get("qty") or 0)
        if qty <= 0:
            continue

        unit_price = Decimal(str(line.get("unit_price") or 0))
        mi = menu_map.get(mid)

        bulk.append(
            DeliveryOrderItem(
                order=order,
                name=(mi.name if mi else str(line.get("name") or f"Item {mid}")),
                unit_price=unit_price,
                qty=qty,
            )
        )

    if bulk:
        DeliveryOrderItem.objects.bulk_create(bulk)

    # increment coupon usage (if any) — only if order successfully created
    if coupon:
        DeliveryCoupon.objects.filter(pk=coupon.pk).update(
            used_count=F("used_count") + 1
        )

    # clear cart + coupon (keep location optional)
    request.session["delivery_cart"] = {"items": {}}
    request.session.pop("delivery_coupon_code", None)

    # ✅ store last order id so we can safely show it once
    request.session["last_delivery_order_id"] = order.id
    request.session.modified = True

    # ✅ optional: bind order to current session for security
    request.session.setdefault(
        "delivery_session_key", request.session.session_key or ""
    )
    request.session.modified = True

       # --- Telegram notify (safe: never breaks order) ---
    try:
        from restaurant.telegram_utils import send_telegram_message, maps_link, safe

        items_lines = []
        for it in order.items.all():
            items_lines.append(
                f"• {safe(it.name)} × {it.qty} = € {(it.unit_price * it.qty):.2f}"
            )
        items_text = "\n".join(items_lines) if items_lines else "—"

        gmaps = maps_link(order.lat, order.lng)

        msg = (
                f"🛵 NEW DELIVERY ORDER\n\n"
                f"Order: #{order.id}\n"
                f"Name: {order.customer_name}\n"
                f"Phone: {order.customer_phone}\n"
                f"Payment: {order.get_payment_method_display()}\n"
                f"Address: {order.address_label}\n"
                f"Extra: {order.address_extra}\n"
                f"Distance: {order.distance_km:.2f} km\n"
                f"Subtotal: € {order.subtotal:.2f}\n"
                f"Delivery fee: € {order.delivery_fee:.2f}\n"
                f"Total: € {order.total:.2f}\n"
                f"Coupon: {order.coupon_code or '-'} (-€ {order.coupon_discount:.2f})\n"
                f"Note: {order.customer_note or '-'}\n\n"
                f"Items:\n{items_text}\n\n"
                f"Map: {gmaps}"
            )

        send_telegram_message(msg, kind="delivery")
    except Exception as e:
        try:
            from restaurant.models import TelegramLog
            TelegramLog.objects.create(
                ok=False,
                kind="delivery",
                chat_id=str(getattr(settings, "TELEGRAM_GROUP_CHAT_ID", "")),
                message_preview="delivery_place_order failed to build/send telegram",
                response_text=repr(e),
            )
        except Exception:
            pass

    # ✅ Redirect back to checkout and include the order id in URL (Option A)
    return redirect(
        reverse("restaurant:delivery_checkout") + f"?placed=1&order={order.id}"
    )


# -------------------------
# Admin: Delivery orders
# -------------------------


@require_POST
@login_required
def delivery_orders_bulk_update(request: HttpRequest) -> HttpResponse:
    ids = request.POST.getlist("order_ids")
    new_status = (request.POST.get("new_status") or "").strip()

    valid = {k for k, _ in DeliveryOrder.STATUS_CHOICES}
    if new_status not in valid:
        messages.error(request, "Please choose a valid status.")
        return redirect("restaurant:delivery_orders_list")

    ids_int = [int(x) for x in ids if str(x).isdigit()]
    if not ids_int:
        messages.error(request, "No orders selected.")
        return redirect("restaurant:delivery_orders_list")

    updated = DeliveryOrder.objects.filter(id__in=ids_int).update(status=new_status)

    # ✅ Loyalty: if bulk set to delivered, ensure coupons for affected users
    if new_status == DeliveryOrder.STATUS_DELIVERED:
        user_ids = (
            DeliveryOrder.objects.filter(id__in=ids_int)
            .exclude(user__isnull=True)
            .values_list("user_id", flat=True)
            .distinct()
        )
        for uid in user_ids:
            # load user via request.user model
            # safest: fetch the user object through DeliveryOrder relation
            u = (
                DeliveryOrder.objects.filter(user_id=uid)
                .values_list("user_id", flat=True)
                .first()
            )
            if u:
                # We need actual user instance:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                user_obj = User.objects.filter(id=uid).first()
                if user_obj:
                    _ensure_loyalty_coupon_for_user(user_obj)

    messages.success(request, f"Updated {updated} order(s).")
    return redirect("restaurant:delivery_orders_list")


@require_POST
@login_required
def delivery_orders_bulk_delete(request: HttpRequest) -> HttpResponse:
    ids = request.POST.getlist("order_ids")
    ids_int = [int(x) for x in ids if str(x).isdigit()]

    if not ids_int:
        messages.error(request, "No orders selected.")
        return redirect("restaurant:delivery_orders_list")

    # Delete order + items (items are CASCADE)
    deleted_count, _ = DeliveryOrder.objects.filter(id__in=ids_int).delete()
    messages.success(request, f"Deleted {deleted_count} record(s).")
    return redirect("restaurant:delivery_orders_list")


@login_required
def delivery_orders_list(request: HttpRequest) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = DeliveryOrder.objects.all().order_by("-created_at")

    if q:
        qs = qs.filter(
            Q(customer_name__icontains=q)
            | Q(customer_phone__icontains=q)
            | Q(address_label__icontains=q)
            | Q(address_extra__icontains=q)
            | Q(id__icontains=q)
        )

    if status:
        qs = qs.filter(status=status)

    return render(
        request,
        "admin/delivery_orders.html",
        {
            "orders": qs[:400],
            "q": q,
            "status": status,
            "status_choices": DeliveryOrder.STATUS_CHOICES,
        },
    )


@login_required
def delivery_order_detail_admin(request: HttpRequest, pk: int) -> HttpResponse:
    o = get_object_or_404(DeliveryOrder.objects.prefetch_related("items"), pk=pk)
    return render(request, "admin/delivery_order_detail.html", {"o": o})


@login_required
def delivery_order_update_status(request: HttpRequest, pk: int) -> HttpResponse:
    o = get_object_or_404(DeliveryOrder, pk=pk)

    if request.method == "POST":
        new_status = (request.POST.get("status") or "").strip()
        valid = {k for k, _ in DeliveryOrder.STATUS_CHOICES}

        if new_status in valid:
            o.status = new_status
            o.save(update_fields=["status"])
            messages.success(request, "Order status updated.")

            # ✅ Loyalty: when order becomes delivered, grant coupon if eligible
            if new_status == DeliveryOrder.STATUS_DELIVERED and o.user:
                _ensure_loyalty_coupon_for_user(o.user)
        else:
            messages.error(request, "Invalid status.")

    return redirect("restaurant:delivery_order_detail_admin", pk=pk)


@login_required
def delivery_coupons_list(request: HttpRequest) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()  # active/inactive/all

    qs = DeliveryCoupon.objects.all().order_by("-created_at")

    if q:
        qs = qs.filter(code__icontains=q)

    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    return render(
        request,
        "admin/delivery_coupons.html",
        {
            "coupons": qs[:500],
            "q": q,
            "status": status,
        },
    )


@login_required
def delivery_coupon_add(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = DeliveryCouponForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.code = obj.code.strip().upper()
            obj.save()
            messages.success(request, f"Coupon {obj.code} created.")
            return redirect("restaurant:delivery_coupons_list")
    else:
        form = DeliveryCouponForm()

    return render(
        request, "admin/delivery_coupon_form.html", {"form": form, "mode": "add"}
    )


@login_required
def delivery_coupon_edit(request: HttpRequest, pk: int) -> HttpResponse:
    obj = get_object_or_404(DeliveryCoupon, pk=pk)

    if request.method == "POST":
        form = DeliveryCouponForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.code = obj.code.strip().upper()
            obj.save()
            messages.success(request, f"Coupon {obj.code} updated.")
            return redirect("restaurant:delivery_coupons_list")
    else:
        form = DeliveryCouponForm(instance=obj)

    return render(
        request,
        "admin/delivery_coupon_form.html",
        {"form": form, "mode": "edit", "obj": obj},
    )


@login_required
def delivery_coupon_delete(request: HttpRequest, pk: int) -> HttpResponse:
    obj = get_object_or_404(DeliveryCoupon, pk=pk)

    if request.method == "POST":
        code = obj.code
        obj.delete()
        messages.success(request, f"Coupon {code} deleted.")
        return redirect("restaurant:delivery_coupons_list")

    return render(request, "admin/delivery_coupon_delete.html", {"obj": obj})


@login_required
def hero_banners_list(request: HttpRequest) -> HttpResponse:
    banners = HeroBanner.objects.all()
    return render(request, "admin/hero_banners.html", {"banners": banners})


@login_required
def hero_banner_add(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = HeroBannerForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Hero banner added.")
            return redirect("restaurant:hero_banners_list")
    else:
        form = HeroBannerForm()

    return render(request, "admin/hero_banner_form.html", {"form": form})


@login_required
def hero_banner_edit(request: HttpRequest, pk: int) -> HttpResponse:
    banner = get_object_or_404(HeroBanner, pk=pk)

    if request.method == "POST":
        form = HeroBannerForm(request.POST, request.FILES, instance=banner)
        if form.is_valid():
            form.save()
            messages.success(request, "Hero banner updated.")
            return redirect("restaurant:hero_banners_list")
    else:
        form = HeroBannerForm(instance=banner)

    return render(
        request, "admin/hero_banner_form.html", {"form": form, "banner": banner}
    )


@login_required
def hero_banner_delete(request: HttpRequest, pk: int) -> HttpResponse:
    banner = get_object_or_404(HeroBanner, pk=pk)

    if request.method == "POST":
        banner.delete()
        messages.success(request, "Hero banner deleted.")
        return redirect("restaurant:hero_banners_list")

    return render(request, "admin/hero_banner_delete.html", {"banner": banner})


@login_required
def loyalty_settings(request):
    from .models import LoyaltyProgram
    from django.contrib import messages

    obj = LoyaltyProgram.objects.first()

    if request.method == "POST":
        target = int(request.POST.get("target_orders") or 10)
        percent = int(request.POST.get("reward_percent") or 30)
        is_active = bool(request.POST.get("is_active"))

        if not obj:
            obj = LoyaltyProgram.objects.create(
                target_orders=target,
                reward_percent=percent,
                is_active=is_active,
            )
        else:
            obj.target_orders = target
            obj.reward_percent = percent
            obj.is_active = is_active
            obj.save()

        messages.success(request, "Loyalty settings updated.")
        return redirect("restaurant:loyalty_settings")

    return render(request, "admin/loyalty_settings.html", {"obj": obj})





def reviews_page(request):
    # --------------------------
    # 1️⃣ Handle POST (SAVE REVIEW)
    # --------------------------
    if request.method == "POST":
        form = ReviewForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, _("Thank you! Your review has been submitted."))
            return redirect(reverse("restaurant:reviews"))
        else:
            messages.error(request, _("Please fix the errors below."))
    else:
        form = ReviewForm()

    # --------------------------
    # 2️⃣ Fetch updated reviews
    # --------------------------
    reviews_qs = Review.objects.all().order_by("-rating", "-id")

    total_reviews = reviews_qs.count()
    average_rating = reviews_qs.aggregate(avg=Avg("rating"))["avg"] or 0
    star_percentage = (average_rating / 5) * 100 if average_rating else 0

    # Rating distribution 5 → 1
    distribution = []
    for i in range(5, 0, -1):
        count = reviews_qs.filter(rating=i).count()
        percent = (count / total_reviews * 100) if total_reviews else 0
        distribution.append(
            {
                "stars": i,
                "count": count,
                "percent": percent,
            }
        )

    # Pagination
    reviews_list = list(reviews_qs)
    for review in reviews_list:
        review.star_width = (review.rating / 5) * 100

    paginator = Paginator(reviews_list, 9)
    page_number = request.GET.get("page")
    reviews = paginator.get_page(page_number)

    context = {
        "reviews": reviews,
        "total_reviews": total_reviews,
        "average_rating": round(average_rating, 1),
        "star_percentage": star_percentage,
        "distribution": distribution,
        "form": form,
    }

    return render(request, "reviews.html", context)

def delivery_location_partial(request: HttpRequest) -> HttpResponse:
    """
    Returns ONLY the location picker UI for the menu modal.
    Uses same context as delivery_location, but a partial template.
    """
    promo = _active_promo()
    ctx = {
        "rest_lat": getattr(settings, "RESTAURANT_LAT", 0),
        "rest_lng": getattr(settings, "RESTAURANT_LNG", 0),
        "max_radius": getattr(settings, "DELIVERY_MAX_RADIUS_KM", 10.0),
        "promo_active": bool(promo),
        "promo_title": promo.title if promo else "",
        "promo_min_subtotal": float(promo.min_subtotal) if promo else 0.0,
        "promo_free_delivery": bool(promo.free_delivery) if promo else False,
    }
    return render(request, "partials/delivery_location_modal.html", ctx)
