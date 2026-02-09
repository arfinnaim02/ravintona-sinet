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

from .forms import (
    AdminLoginForm,
    CategoryForm,
    ContactForm,
    MenuItemForm,
    ReservationForm,
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
)
from .utils import haversine_km, delivery_fee_for_distance
from .forms import DeliveryCouponForm

from django.utils.translation import gettext as _

from django.http import JsonResponse
from django.shortcuts import redirect

from django.views.decorators.http import require_POST

# -------------------------
# Public pages
# -------------------------

def home(request: HttpRequest) -> HttpResponse:
    """Render the home page."""
    popular_items = (
        MenuItem.objects.filter(status=MenuItem.STATUS_ACTIVE)
        .filter(tags__icontains="popular")
        .select_related("category")
        .order_by("-created_at")[:4]
    )
    categories = Category.objects.filter(is_active=True).order_by("order", "name")
    return render(request, "home.html", {"popular_items": popular_items, "categories": categories})


def menu(request: HttpRequest) -> HttpResponse:
    """Display the menu (category + search only)."""
    categories = Category.objects.filter(is_active=True).order_by("order", "name")

    category_slug = (request.GET.get("category") or "").strip()
    q = (request.GET.get("q") or "").strip()

    items = MenuItem.objects.select_related("category").exclude(status=MenuItem.STATUS_HIDDEN)

    current_category: Category | None = None
    if category_slug:
        current_category = get_object_or_404(Category, slug=category_slug, is_active=True)
        items = items.filter(category=current_category)

    if q:
        items = items.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(category__name__icontains=q)
        )

    items = items.order_by("category__order", "name")

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
            messages.success(request, "Thank you for your message! We'll get back to you soon.")
            return redirect(reverse("restaurant:contact"))
    else:
        form = ContactForm()
    return render(request, "contact.html", {"form": form})


def menu_item_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Partial template for menu modal."""
    item = get_object_or_404(MenuItem.objects.select_related("category"), pk=pk)
    if item.status == MenuItem.STATUS_HIDDEN:
        return HttpResponse(status=404)

    ctx = (request.GET.get("ctx") or "menu").strip().lower()
    if ctx not in {"menu", "reservation", "delivery"}:
        ctx = "menu"

    return render(request, "partials/menu_item_modal.html", {"item": item, "ctx": ctx})


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

    return render(request, "admin/login.html", {"form": form})


@login_required
def admin_logout(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect(reverse("restaurant:admin_login"))


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    total_items = MenuItem.objects.count()
    total_categories = Category.objects.count()
    sold_out_count = MenuItem.objects.filter(status=MenuItem.STATUS_SOLD_OUT).count()

    recent_items = MenuItem.objects.select_related("category").order_by("-created_at")[:50]
    categories = Category.objects.all().order_by("order", "name")

    total_reservations = Reservation.objects.count()
    pending_reservations = Reservation.objects.filter(status=Reservation.STATUS_PENDING).count()
    upcoming_reservations = Reservation.objects.filter(start_datetime__gte=timezone.now()).count()
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
def delete_menu_item(request: HttpRequest, pk: int) -> HttpResponse:
    item = get_object_or_404(MenuItem, pk=pk)
    if request.method == "POST":
        item.delete()
        messages.success(request, "Menu item deleted.")
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
    return render(request, "admin/edit_category.html", {"form": form, "category": category})


@login_required
def delete_category(request: HttpRequest, pk: int) -> HttpResponse:
    category = get_object_or_404(Category, pk=pk)
    has_items = category.menu_items.exists()

    if request.method == "POST":
        if has_items:
            messages.error(request, "Cannot delete category while it contains menu items.")
            return redirect(reverse("restaurant:categories_list"))
        category.delete()
        messages.success(request, "Category deleted.")
        return redirect(reverse("restaurant:categories_list"))

    return render(request, "admin/delete_category.html", {"category": category, "has_items": has_items})


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
        {"items": items, "categories": categories, "q": q, "category_slug": category_slug, "status": status},
    )


@login_required
def reservations_list(request: HttpRequest) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = Reservation.objects.all().order_by("-start_datetime", "-created_at")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))
    if status:
        qs = qs.filter(status=status)

    return render(
        request,
        "admin/reservations.html",
        {"reservations": qs[:300], "q": q, "status": status, "status_choices": Reservation.STATUS_CHOICES},
    )


@login_required
def reservation_detail_admin(request: HttpRequest, pk: int) -> HttpResponse:
    r = get_object_or_404(Reservation.objects.prefetch_related("items__menu_item"), pk=pk)
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


def reservation(request: HttpRequest) -> HttpResponse:
    """Public reservation page (with optional pre-order items)."""
    categories = Category.objects.filter(is_active=True).order_by("order", "name")
    menu_items = (
        MenuItem.objects.select_related("category")
        .exclude(status=MenuItem.STATUS_HIDDEN)
        .order_by("category__order", "name")
    )

    if request.method == "POST":
        form = ReservationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                r = form.save(commit=False)
                r.full_clean()
                r.save()

                preorder_ids = request.POST.getlist("preorder_ids")
                preorder_qty = request.POST.getlist("preorder_qty")

                pairs = list(zip(preorder_ids, preorder_qty))
                ids: list[int] = []
                qty_map: dict[int, int] = {}

                for mid, q in pairs:
                    mid = (mid or "").strip()
                    if not mid.isdigit():
                        continue
                    qty = int(q) if (q or "").isdigit() else 0
                    if qty <= 0:
                        continue
                    mid_int = int(mid)
                    ids.append(mid_int)
                    qty_map[mid_int] = qty

                if ids:
                    items = MenuItem.objects.filter(id__in=ids).exclude(status=MenuItem.STATUS_HIDDEN)
                    bulk = []
                    for mi in items:
                        qty = qty_map.get(mi.id, 0)
                        if qty <= 0:
                            continue
                        bulk.append(
                            ReservationItem(
                                reservation=r,
                                menu_item=mi,
                                qty=qty,
                                unit_price=mi.price,
                            )
                        )
                    if bulk:
                        ReservationItem.objects.bulk_create(bulk)

                    # ✅ store last reservation id so we can show it once in popup
                    request.session["last_reservation_id"] = r.id
                    request.session.modified = True

                    messages.success(request, f"Reservation received! Your reservation number is #{r.id}.")
                    return redirect(reverse("restaurant:reservation") + "?placed=1")

    else:
        form = ReservationForm()

    # ✅ popup logic (same as checkout)
    placed = (request.GET.get("placed") or "").strip() == "1"
    last_id = request.session.get("last_reservation_id")

    reservation_obj = None
    if placed and last_id:
        reservation_obj = (
            Reservation.objects
            .prefetch_related("items__menu_item")
            .filter(id=last_id)
            .first()
        )

    return render(
        request,
        "reservation.html",
        {
            "form": form,
            "categories": categories,
            "menu_items": menu_items,

            # ✅ popup
            "show_reservation_modal": bool(reservation_obj),
            "reservation_obj": reservation_obj,
        },
    )


# -------------------------
# Delivery (location + calc + order + checkout)
# -------------------------

def _active_promo() -> DeliveryPromotion | None:
    promo = DeliveryPromotion.objects.filter(is_active=True).order_by("-created_at").first()
    if promo and promo.is_current():
        return promo
    return None


def _apply_promo_delivery_fee(fee: float, subtotal: float) -> tuple[float, dict]:
    promo = _active_promo()
    if not promo:
        return float(fee), {"active": False}

    min_sub = float(promo.min_subtotal or 0)
    ok_min = subtotal >= min_sub

    if promo.free_delivery and ok_min:
        return 0.0, {
            "active": True,
            "title": promo.title,
            "free_delivery": True,
            "min_subtotal": min_sub,
        }

    return float(fee), {
        "active": True,
        "title": promo.title,
        "free_delivery": False,
        "min_subtotal": min_sub,
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
        return None
    return coupon


def _coupon_discount_for_request(request: HttpRequest, subtotal: float) -> tuple[float, dict]:
    coupon = _get_coupon_from_session(request)
    if not coupon:
        return 0.0, {"active": False}

    disc = coupon.compute_discount(Decimal(str(subtotal)))
    disc_f = float(disc)

    if disc_f <= 0:
        return 0.0, {"active": False}

    return disc_f, {
        "active": True,
        "code": coupon.code,
        "discount": round(disc_f, 2),
        "type": coupon.discount_type,
        "value": float(coupon.discount_value or 0),
        "min_subtotal": float(coupon.min_subtotal or 0),
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

    # If cart empty, force fee/discount zero
    if count <= 0:
        fee = 0.0
        discount = 0.0
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
        return redirect("restaurant:delivery_location")

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

    return redirect("restaurant:delivery_order")


def delivery_order(request: HttpRequest) -> HttpResponse:
    """Menu + cart page for delivery."""
    if not request.session.get("delivery_lat") or not request.session.get("delivery_lng"):
        return redirect("restaurant:delivery_location")

    lat = float(request.session["delivery_lat"])
    lng = float(request.session["delivery_lng"])

    rest_lat = float(getattr(settings, "RESTAURANT_LAT", 0))
    rest_lng = float(getattr(settings, "RESTAURANT_LNG", 0))

    distance_km = haversine_km(rest_lat, rest_lng, lat, lng)
    base_fee = float(delivery_fee_for_distance(distance_km))

    subtotal = _cart_subtotal(request)
    final_fee, promo_info = _apply_promo_delivery_fee(base_fee, subtotal)

    request.session["delivery_distance_km"] = round(distance_km, 2)
    request.session["delivery_fee"] = round(float(final_fee), 2)
    request.session["delivery_base_fee"] = round(float(base_fee), 2)
    request.session["delivery_promo"] = promo_info
    request.session.modified = True

    categories = Category.objects.filter(is_active=True).order_by("order", "name")
    items = (
        MenuItem.objects.select_related("category")
        .filter(status__in=[MenuItem.STATUS_ACTIVE, MenuItem.STATUS_SOLD_OUT])
        .exclude(status=MenuItem.STATUS_HIDDEN)
        .order_by("category__order", "name")
    )

    ctx = {
        "categories": categories,
        "items": items,
        "subtotal": round(subtotal, 2),
        "delivery_distance_km": request.session.get("delivery_distance_km", 0),
        "delivery_fee": request.session.get("delivery_fee", 0),
        "delivery_base_fee": request.session.get("delivery_base_fee", 0),
        "promo": request.session.get("delivery_promo") or {"active": False},
        "estimated_total": round(subtotal + float(request.session.get("delivery_fee") or 0), 2),
            # ✅ NEW (for coupon UI)
    "coupon_code": request.session.get("delivery_coupon_code", ""),
    "cart": _cart_totals(request),
    }
    return render(request, "delivery_order.html", ctx)


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
            {"display_name": it.get("display_name", ""), "lat": it.get("lat"), "lon": it.get("lon")}
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
    if not request.session.get("delivery_lat") or not request.session.get("delivery_lng"):
        return redirect("restaurant:delivery_location")

    if request.method == "POST":
        request.session["customer_name"] = (request.POST.get("name") or "").strip()
        request.session["customer_phone"] = (request.POST.get("phone") or "").strip()
        request.session["customer_note"] = (request.POST.get("note") or "").strip()
        request.session["customer_address_extra"] = (request.POST.get("address_extra") or "").strip()
        request.session.modified = True
        return redirect("restaurant:delivery_checkout")

    cart = _cart_totals(request)

    placed = (request.GET.get("placed") or "").strip() == "1"
    last_id = request.session.get("last_delivery_order_id")
    order_obj = None

    if placed and last_id:
        order_obj = (
            DeliveryOrder.objects
            .prefetch_related("items")
            .filter(id=last_id)
            .first()
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
        "pay_method": "Pay on delivery",
        "coupon_code": request.session.get("delivery_coupon_code", ""),

        # ✅ popup
        "show_order_modal": bool(order_obj),
        "order_obj": order_obj,
    }
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
        return redirect(request.META.get("HTTP_REFERER") or "restaurant:delivery_order")

    if not code:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Please enter a coupon code."}, status=400)
        messages.error(request, "Please enter a coupon code.")
        return _back()

    coupon = DeliveryCoupon.objects.filter(code__iexact=code).first()
    if not coupon or not coupon.is_current():
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Invalid or expired coupon."}, status=400)
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
    return redirect(request.META.get("HTTP_REFERER") or "restaurant:delivery_order")

@require_POST
def delivery_place_order(request: HttpRequest) -> HttpResponse:
    # must have location
    if not request.session.get("delivery_lat") or not request.session.get("delivery_lng"):
        messages.error(request, "Please set your delivery location first.")
        return redirect("restaurant:delivery_location")

    # must have cart items
    cart = _cart_totals(request)
    lines = cart.get("lines") or []
    if not lines:
        messages.error(request, "Your cart is empty.")
        return redirect("restaurant:delivery_order")

    # customer details from session (set in checkout POST)
    name = (request.session.get("customer_name") or "").strip()
    phone = (request.session.get("customer_phone") or "").strip()
    note = (request.session.get("customer_note") or "").strip()
    extra = (request.session.get("customer_address_extra") or "").strip()

    if not name or not phone:
        messages.error(request, "Please enter your name and phone number.")
        return redirect("restaurant:delivery_checkout")

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
    )

    # snapshot items (NO menu_item FK in model)
    ids = [int(x["id"]) for x in lines if str(x.get("id", "")).isdigit()]
    menu_map = {m.id: m for m in MenuItem.objects.filter(id__in=ids).exclude(status=MenuItem.STATUS_HIDDEN)}

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
        DeliveryCoupon.objects.filter(pk=coupon.pk).update(used_count=F("used_count") + 1)

    # clear cart + coupon (keep location optional)
    request.session["delivery_cart"] = {"items": {}}
    request.session.pop("delivery_coupon_code", None)

    # ✅ store last order id so we can safely show it once
    request.session["last_delivery_order_id"] = order.id
    request.session.modified = True

    messages.success(request, f"Order received! Your order number is #{order.id}.")
    return redirect(reverse("restaurant:delivery_checkout") + "?placed=1")

# -------------------------
# Admin: Delivery orders
# -------------------------

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

    return render(request, "admin/delivery_coupon_form.html", {"form": form, "mode": "add"})


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
