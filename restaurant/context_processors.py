from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg
from .models import Review


def restaurant_settings(request):
    """
    Global context:
    - Restaurant settings
    - Global review statistics (cached)
    """

    # --- Review Stats (cached) ---
    cache_key = "footer_review_stats_v1"
    cached = cache.get(cache_key)

    if cached is None:
        total_reviews = Review.objects.count()
        average_rating = Review.objects.aggregate(avg=Avg("rating"))["avg"] or 0
        star_percentage = (average_rating / 5) * 100 if average_rating else 0

        cached = {
            "footer_total_reviews": total_reviews,
            "footer_average_rating": round(average_rating, 1),
            "footer_star_percentage": star_percentage,
        }

        # cache for 5 minutes (adjust if you want)
        cache.set(cache_key, cached, 300)

    return {
        # Restaurant Settings
        "settings": {
            "RESTAURANT_NAME": getattr(settings, "RESTAURANT_NAME", ""),
            "RESTAURANT_ADDRESS": getattr(settings, "RESTAURANT_ADDRESS", ""),
            "RESTAURANT_PHONE": getattr(settings, "RESTAURANT_PHONE", ""),
            "RESTAURANT_EMAIL": getattr(settings, "RESTAURANT_EMAIL", ""),
            "RESTAURANT_OPENING_HOURS": getattr(settings, "RESTAURANT_OPENING_HOURS", ""),
            "RESTAURANT_LAT": getattr(settings, "RESTAURANT_LAT", None),
            "RESTAURANT_LNG": getattr(settings, "RESTAURANT_LNG", None),
        },

        # Global Review Data (cached)
        **cached,
    }
