"""URL configuration for the Ravintola Sinet project."""

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin as django_admin
from django.urls import include, path
from django.views.i18n import JavaScriptCatalog

urlpatterns = [
    # Language switch endpoint (required for set_language)
    path("i18n/", include("django.conf.urls.i18n")),

    # ✅ JS translations catalog (needed for gettext() in JS)
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),

    # Django admin kept for debugging/user management (NOT translated)
    path("django-admin/", django_admin.site.urls),
]

urlpatterns += i18n_patterns(
    path("", include(("restaurant.urls", "restaurant"), namespace="restaurant")),
    path("accounts/", include(("accounts.urls", "accounts"), namespace="accounts")),  # ✅ ADD
    prefix_default_language=True,
)


# Serve uploaded media in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
