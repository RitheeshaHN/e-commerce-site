"""Admin configuration for the cart app (inspect abandoned carts)."""
from django.contrib import admin

from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    raw_id_fields = ("product", "size")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "count", "subtotal", "updated_at")
    inlines = [CartItemInline]
    search_fields = ("user__username",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Items")
    def count(self, obj):
        return obj.count
