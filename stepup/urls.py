"""
Root URL configuration for StepUp Shoes.

Includes:
  /            store  (home, product list, product detail, search)
  /accounts/   accounts (register, login, logout, password reset, profile)
  /cart/       cart (cart page + AJAX endpoints)
  /orders/     orders (checkout, payment, history)
  /admin/      customized Django admin
  /media/      uploaded images (only when DEBUG=True)
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("store.urls")),
    path("accounts/", include("accounts.urls")),
    path("cart/", include("cart.urls")),
    path("orders/", include("orders.urls")),

    # ---------------------------------------------------------------
    # Password reset (Django's built-in views + our templates)
    # ---------------------------------------------------------------
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(template_name="accounts/password_reset.html"),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]

# Serve uploaded media during development (not for production).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Friendly admin site headers.
admin.site.site_header = "StepUp Shoes Admin"
admin.site.site_title = "StepUp Admin"
admin.site.index_title = "Store management"
