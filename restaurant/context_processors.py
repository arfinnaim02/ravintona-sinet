from django.conf import settings

def restaurant_settings(request):
    return {
        "settings": {
            "RESTAURANT_NAME": getattr(settings, "RESTAURANT_NAME", ""),
            "RESTAURANT_ADDRESS": getattr(settings, "RESTAURANT_ADDRESS", ""),
            "RESTAURANT_PHONE": getattr(settings, "RESTAURANT_PHONE", ""),
            "RESTAURANT_EMAIL": getattr(settings, "RESTAURANT_EMAIL", ""),
            "RESTAURANT_OPENING_HOURS": getattr(settings, "RESTAURANT_OPENING_HOURS", ""),
            "RESTAURANT_LAT": getattr(settings, "RESTAURANT_LAT", None),
            "RESTAURANT_LNG": getattr(settings, "RESTAURANT_LNG", None),
        }
    }
