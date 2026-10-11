"""URLs for the cart app (page + AJAX endpoints)."""
from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_detail, name="cart_detail"),
    # AJAX endpoints -- item_id is a CartItem PK for users,
    # and a ProductSize PK for guests (session carts have no PK).
    path("add/<int:size_id>/", views.cart_add, name="cart_add"),
    path("update/<int:item_id>/", views.cart_update, name="cart_update"),
    path("remove/<int:item_id>/", views.cart_remove, name="cart_remove"),
]
