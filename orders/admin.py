"""
Admin configuration for the orders app.

Includes a bulk action so the admin can select several orders and
move them to Confirmed / Shipped / Delivered / Cancelled in one go.
"""
from django.contrib import admin
from django.db.models import F

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "product", "size", "product_name", "size_label",
        "unit_price", "quantity",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number", "user", "status", "payment_method",
        "payment_status", "total", "created_at",
    )
    list_filter = ("status", "payment_method", "payment_status", "created_at")
    search_fields = ("order_number", "full_name", "phone", "user__username")
    readonly_fields = (
        "order_number", "subtotal", "shipping", "total",
        "created_at", "updated_at",
    )
    inlines = [OrderItemInline]
    date_hierarchy = "created_at"
    # Fields the admin edits most often.
    fieldsets = (
        ("Order", {"fields": ("order_number", "user", "status", "created_at")}),
        ("Payment", {"fields": ("payment_method", "payment_status")}),
        (
            "Shipping address",
            {
                "fields": (
                    "full_name", "phone", "address_line1",
                    "address_line2", "city", "state", "pincode",
                )
            },
        ),
        ("Totals", {"fields": ("subtotal", "shipping", "total", "note")}),
    )

    # ----------------------------------------------------- bulk actions ---
    actions = ["mark_confirmed", "mark_shipped", "mark_delivered", "mark_cancelled"]

    @admin.action(description="Mark selected orders as Confirmed")
    def mark_confirmed(self, request, queryset):
        queryset.update(status="Confirmed")

    @admin.action(description="Mark selected orders as Shipped")
    def mark_shipped(self, request, queryset):
        queryset.update(status="Shipped")

    @admin.action(description="Mark selected orders as Delivered")
    def mark_delivered(self, request, queryset):
        queryset.update(status="Delivered")

    @admin.action(description="Cancel selected orders (restores stock)")
    def mark_cancelled(self, request, queryset):
        """
        Cancelling from admin also gives the stock back, mirroring the
        customer-facing cancel view.
        """
        from store.models import ProductSize

        for order in queryset.filter(status="Pending"):
            for item in order.items.all():
                ProductSize.objects.filter(pk=item.size_id).update(
                    stock=F("stock") + item.quantity
                )
            order.status = "Cancelled"
            order.save(update_fields=["status", "updated_at"])


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_name", "size_label", "unit_price", "quantity")
    search_fields = ("order__order_number", "product_name")
    list_filter = ("size_label",)
