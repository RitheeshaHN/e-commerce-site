"""
Cart app models: Cart and CartItem.

Storage strategy
----------------
* Logged-in user -> this database-backed Cart (keyed by ``user``).
* Guest          -> cart lives in the session (see cart/session.py),
                    no DB rows are created.
* On login, the guest session cart is merged into the user's DB cart
  (see cart/utils.py::merge_session_cart).
"""
from django.conf import settings
from django.db import models

from store.models import Product, ProductSize


class Cart(models.Model):
    """One cart per logged-in user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Cart of {self.user}"

    # ------------------------------------------------------------ totals ----
    @property
    def subtotal(self) -> float:
        return round(sum(item.line_total for item in self.items.all()), 2)

    @property
    def shipping(self) -> float:
        """Free shipping over the threshold, otherwise flat fee."""
        subtotal = self.subtotal
        if subtotal <= 0:
            return 0.0
        threshold = getattr(settings, "FREE_SHIPPING_THRESHOLD", 1999.0)
        fee = getattr(settings, "SHIPPING_FEE", 99.0)
        return 0.0 if subtotal >= threshold else fee

    @property
    def total(self) -> float:
        return round(self.subtotal + self.shipping, 2)

    @property
    def count(self) -> int:
        """Total *units* (used for the navbar badge)."""
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    """A line in the cart: one product + one size + a quantity."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    # Size is a FK (not a plain char) so we can decrement the right stock row.
    size = models.ForeignKey(ProductSize, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Same product+size appears only once; quantity is bumped instead.
        unique_together = ("cart", "product", "size")
        ordering = ["-added_at"]

    def __str__(self) -> str:
        return f"{self.quantity} × {self.product} UK {self.size.size}"

    @property
    def unit_price(self) -> float:
        return self.product.final_price

    @property
    def line_total(self) -> float:
        return round(self.unit_price * self.quantity, 2)

    @property
    def max_quantity(self) -> int:
        """Never let the customer order more than what's in stock."""
        return self.size.stock
