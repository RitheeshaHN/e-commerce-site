"""URLs for the orders app."""
from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("", views.order_list, name="order_list"),
    path("<str:order_number>/", views.order_detail, name="order_detail"),
    path("<str:order_number>/cancel/", views.order_cancel, name="order_cancel"),
    path("<str:order_number>/pay/", views.mock_payment, name="mock_payment"),
    path(
        "<str:order_number>/pay/process/",
        views.mock_payment_process,
        name="mock_payment_process",
    ),
]
