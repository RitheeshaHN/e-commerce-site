"""URLs for the store app (home, listing, detail, search)."""
from django.urls import path

from . import views

app_name = "store"

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.product_list, name="product_list"),
    path("products/<slug:slug>/", views.product_detail, name="product_detail"),
    path("products/<slug:slug>/review/", views.post_review, name="post_review"),
    path("api/search/", views.search_suggestions, name="search_suggestions"),
]
