"""
Orders app models: Order and OrderItem.

Order lifecycle
---------------
Pending -> Confirmed -> Shipped -> Delivered
   |          |
   v          v
Cancelled  Cancelled   (cancelling restores stock)

Stock is decremented when the order is placed and restored if the
order is cancelled while still Pending.
"""
from django.conf import settings
from django.db import models

from accounts.models import Address
from store.models import Product, ProductSize


class Order(models.Model):
    """A placed order for one user."""

    STATUS = (
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Shipped", "Shipped"),
        ("Delivered", "Delivered"),
        ("Cancelled", "Cancelled"),
    )
    PAYMENT_METHOD = (
        ("cod", "Cash on Delivery"),
        ("online", "Online Payment (mock)"),
    )
    PAYMENT_STATUS = (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders"
    )
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    status = models.CharField(max_length=12, choices=STATUS, default="Pending")
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD, default="cod")
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default="pending")

    # Address is *copied* (snapshot) so later edits to the user's saved
    # address don't rewrite history on old orders.
    address = models.ForeignKey(
        Address, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Optional free-text note from the customer.
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self) -> str:
        return f"Order {self.order_number}"

    # ------------------------------------------------------------ helpers ---
    @staticmethod
    def generate_order_number() -> str:
        """Short human-friendly id like SU-240517-8391."""
        import random
        from django.utils import timezone

        stamp = timezone.now().strftime("%y%m%d")
        return f"SU-{stamp}-{random.randint(1000, 9999)}"

    @property
    def can_cancel(self) -> bool:
        """Only Pending orders may be cancelled by the customer."""
        return self.status == "Pending"

    @property
    def shipping_address(self) -> str:
        parts = [self.address_line1, self.address_line2, self.city, self.state, self.pincode]
        return ", ".join(p for p in parts if p)

    @property
    def item_count(self) -> int:
        return sum(i.quantity for i in self.items.all())


class OrderItem(models.Model):
    """Immutable snapshot of one purchased product+size."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    size = models.ForeignKey(ProductSize, on_delete=models.PROTECT, related_name="order_items")
    # Price/name captured at purchase time (product may change later).
    product_name = models.CharField(max_length=255)
    product_slug = models.SlugField(max_length=255)
    size_label = models.CharField(max_length=10)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.quantity} × {self.product_name} UK {self.size_label}"

    @property
    def line_total(self) -> float:
        return round(float(self.unit_price) * self.quantity, 2)

    @property
    def image_url(self) -> str:
        """First gallery image (or placeholder)."""
        img = self.product.images.first()
        return img.image.url if img else ""
