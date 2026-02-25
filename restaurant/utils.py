import math
from django.conf import settings
from decimal import Decimal
from .models import DeliveryPricing
def haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)

    a = (math.sin(dp / 2) ** 2) + math.cos(p1) * math.cos(p2) * (math.sin(dl / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def delivery_fee_for_distance(distance_km: float) -> float:
    try:
        d = float(distance_km or 0)
    except (TypeError, ValueError):
        return 0.0

    if d <= 0:
        return 0.0

    # fallback defaults (same as your current hardcoded values)
    BASE_KM = Decimal("2.00")
    BASE_FEE = Decimal("0.00")
    PER_KM_FEE = Decimal("0.99")
    MAX_FEE = Decimal("8.99")

    p = DeliveryPricing.objects.filter(is_active=True).order_by("-updated_at").first()
    if p:
        BASE_KM = Decimal(p.base_km)
        BASE_FEE = Decimal(p.base_fee)
        PER_KM_FEE = Decimal(p.per_km_fee)
        MAX_FEE = Decimal(p.max_fee)

    d_dec = Decimal(str(d))

    if d_dec <= BASE_KM:
        fee = BASE_FEE
    else:
        extra_km = d_dec - BASE_KM
        fee = BASE_FEE + (extra_km * PER_KM_FEE)

    if fee > MAX_FEE:
        fee = MAX_FEE

    return float(fee.quantize(Decimal("0.01")))
