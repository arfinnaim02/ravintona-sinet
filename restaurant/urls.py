"""URL definitions for the restaurant application."""

from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
app_name = "restaurant"

urlpatterns = [
    # Public pages
    path("", views.home, name="home"),
    path("menu/", views.menu, name="menu"),
    path("menu/item/<int:pk>/", views.menu_item_detail, name="menu_item_detail"),
    path("about/", views.about, name="about"),
    path("book/", views.reservation, name="reservation"),
    path("contact/", views.contact, name="contact"),

    # Custom admin UI (NOT Django admin)
    path("admin/login/", views.admin_login, name="admin_login"),
    path("admin/logout/", views.admin_logout, name="admin_logout"),
    path("admin/dashboard/", views.dashboard, name="dashboard"),

    # Menu item management
    path("admin/menu/", views.menu_items_list, name="menu_items_list"),
    path("admin/menu/add/", views.add_menu_item, name="add_menu_item"),
    path("admin/menu/<int:pk>/edit/", views.edit_menu_item, name="edit_menu_item"),
    path("admin/menu/<int:pk>/delete/", views.delete_menu_item, name="delete_menu_item"),

    # Category management
    path("admin/categories/", views.categories_list, name="categories_list"),
    path("admin/category/add/", views.add_category, name="add_category"),
    path("admin/category/<int:pk>/edit/", views.edit_category, name="edit_category"),
    path("admin/category/<int:pk>/delete/", views.delete_category, name="delete_category"),

    # Reservations management
    path("admin/reservations/", views.reservations_list, name="reservations_list"),
    path("admin/reservations/<int:pk>/", views.reservation_detail_admin, name="reservation_detail_admin"),
    path("admin/reservations/<int:pk>/status/", views.reservation_update_status, name="reservation_update_status"),

    # Promotions placeholders
    path("admin/promotions/", views.promotions_list, name="promotions_list"),
    path("admin/promotions/add/", views.add_promotion, name="add_promotion"),
    path("admin/promotions/<int:pk>/edit/", views.edit_promotion, name="edit_promotion"),
    path("admin/promotions/<int:pk>/delete/", views.delete_promotion, name="delete_promotion"),

    path("admin/delivery-coupons/", views.delivery_coupons_list, name="delivery_coupons_list"),
    path("admin/delivery-coupons/add/", views.delivery_coupon_add, name="delivery_coupon_add"),
    path("admin/delivery-coupons/<int:pk>/edit/", views.delivery_coupon_edit, name="delivery_coupon_edit"),
    path("admin/delivery-coupons/<int:pk>/delete/", views.delivery_coupon_delete, name="delivery_coupon_delete"),

    # Delivery
    path("delivery/location/", views.delivery_location, name="delivery_location"),
    path("delivery/calc/", views.delivery_calc, name="delivery_calc"),
    path("delivery/set-location/", views.delivery_set_location, name="delivery_set_location"),
    path("delivery/order/", views.delivery_order, name="delivery_order"),
    path("delivery/checkout/", views.delivery_checkout, name="delivery_checkout"),
    path("delivery/place-order/", views.delivery_place_order, name="delivery_place_order"),

    # Delivery: coupon apply/remove (NEW)
    path("delivery/coupon/apply/", views.delivery_apply_coupon, name="delivery_apply_coupon"),
    path("delivery/coupon/remove/", views.delivery_remove_coupon, name="delivery_remove_coupon"),

    # Nominatim
    path("delivery/nominatim/search/", views.nominatim_search, name="nominatim_search"),
    path("delivery/nominatim/reverse/", views.nominatim_reverse, name="nominatim_reverse"),

    # Cart endpoints
    path("delivery/cart/add/", views.delivery_cart_add, name="delivery_cart_add"),
    path("delivery/cart/update/", views.delivery_cart_update, name="delivery_cart_update"),
    path("delivery/cart/summary/", views.delivery_cart_summary, name="delivery_cart_summary"),

    # Admin: delivery orders
    path("admin/delivery-orders/", views.delivery_orders_list, name="delivery_orders_list"),
    path("admin/delivery-orders/<int:pk>/", views.delivery_order_detail_admin, name="delivery_order_detail_admin"),
    path("admin/delivery-orders/<int:pk>/status/", views.delivery_order_update_status, name="delivery_order_update_status"),



]
