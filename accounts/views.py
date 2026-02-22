from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import SignupForm, EmailLoginForm
from restaurant.models import DeliveryOrder, Reservation

# ✅ import your loyalty helper from restaurant.views (where you defined it)
from restaurant.views import _loyalty_ui_context



def signup_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)

            # username required (if using default User model), so auto-generate from email
            user.username = user.email.split("@")[0]
            base = user.username
            i = 1
            while type(user).objects.filter(username=user.username).exists():
                i += 1
                user.username = f"{base}{i}"

            user.save()
            login(request, user)
            messages.success(request, "Welcome! Your account has been created.")
            return redirect("accounts:dashboard")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            login(request, form.cleaned_data["user"])
            messages.success(request, "You are logged in.")
            return redirect("accounts:dashboard")
    else:
        form = EmailLoginForm()

    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("restaurant:home")


@login_required
def dashboard(request):
    # latest 5 delivery orders
    recent_orders = (
        DeliveryOrder.objects
        .filter(user=request.user)
        .order_by("-created_at")[:5]
    )

    # latest 5 reservations
    recent_reservations = (
        Reservation.objects
        .filter(user=request.user)
        .order_by("-start_datetime", "-created_at")[:5]
    )

    # quick stats
    total_orders = DeliveryOrder.objects.filter(user=request.user).count()
    total_reservations = Reservation.objects.filter(user=request.user).count()

    total_spent = (
        DeliveryOrder.objects
        .filter(user=request.user)
        .aggregate(s=Sum("total"))["s"]
    ) or 0

    upcoming_reservations = (
        Reservation.objects
        .filter(user=request.user, start_datetime__gte=timezone.now())
        .count()
    )

    # ✅ Loyalty context (progress + coupon)
    loyalty = _loyalty_ui_context(request.user)

    # ✅ Auto-notify once per month when earned
    if loyalty.get("enabled") and loyalty.get("earned"):
        month = loyalty.get("month") or ""
        key = f"loyalty_notified_{month}"
        if month and not request.session.get(key):
            messages.success(
                request,
                f"✅ Loyalty reward unlocked! {loyalty.get('percent')}% OFF coupon: {loyalty.get('coupon_code')}"
            )
            request.session[key] = True
            request.session.modified = True

    return render(request, "accounts/dashboard.html", {
        "recent_orders": recent_orders,
        "recent_reservations": recent_reservations,
        "total_orders": total_orders,
        "total_reservations": total_reservations,
        "total_spent": total_spent,
        "upcoming_reservations": upcoming_reservations,

        # ✅ pass to template
        "loyalty": loyalty,
    })


@login_required
def my_orders(request):
    orders = (
        DeliveryOrder.objects
        .filter(user=request.user)
        .prefetch_related("items")
        .order_by("-created_at")
    )
    return render(request, "accounts/my_orders.html", {"orders": orders})


@login_required
def my_reservations(request):
    reservations = (
        Reservation.objects
        .filter(user=request.user)
        .prefetch_related("items__menu_item")
        .order_by("-start_datetime", "-created_at")
    )
    return render(request, "accounts/my_reservations.html", {"reservations": reservations})
