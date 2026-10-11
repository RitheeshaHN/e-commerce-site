"""Admin configuration for the store app (catalog management)."""
from django.contrib import admin

from .models import Brand, Category, Product, ProductImage, ProductSize, Review


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    ordering = ["-is_primary", "position"]


class ProductSizeInline(admin.TabularInline):
    """Manage sizes + stock right on the product page."""

    model = ProductSize
    extra = 1
    fields = ("size", "stock")
    ordering = ["size"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "parent", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name", "brand", "category", "price", "discount_price",
        "is_active", "is_featured", "stock_total", "created_at",
    )
    list_filter = ("is_active", "is_featured", "brand", "category", "created_at")
    search_fields = ("name", "brand__name", "description")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("is_active", "is_featured", "price", "discount_price")
    date_hierarchy = "created_at"
    inlines = [ProductSizeInline, ProductImageInline]
    readonly_fields = ("created_at", "updated_at", "popularity")

    @admin.display(description="Stock")
    def stock_total(self, obj):
        """Total units across sizes (small N per page, so this is cheap)."""
        return sum(s.stock for s in obj.sizes.all())


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "title", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("product__name", "user__username", "comment")
    readonly_fields = ("product", "user", "rating", "comment", "created_at")
