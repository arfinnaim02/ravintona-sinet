import math
from django.conf import settings

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
    """
    Delivery pricing rules:
    - First 2 km: €1.99 fixed
    - After 2 km: €0.99 per km
    - Max delivery fee (8–13 km): €8.99
    """

    try:
        d = float(distance_km or 0)
    except (TypeError, ValueError):
        return 0.0

    if d <= 0:
        return 0.0

    BASE_KM = 2.0
    BASE_FEE = 1.99
    PER_KM_FEE = 0.99
    MAX_FEE = 8.99

    if d <= BASE_KM:
        fee = BASE_FEE
    else:
        extra_km = d - BASE_KM
        fee = BASE_FEE + (extra_km * PER_KM_FEE)

    # Cap the fee (important for 8–13 km range)
    if fee > MAX_FEE:
        fee = MAX_FEE

    return round(fee, 2)
