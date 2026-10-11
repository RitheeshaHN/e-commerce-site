"""
Template context processor: expose the cart count on every page so the
navbar badge works without passing it manually from each view.
"""
from . import session as guest
from .utils import get_cart


def cart_summary(request):
    try:
        if request.user.is_authenticated:
            from .models import Cart

            cart, _ = Cart.objects.get_or_create(user=request.user)
            return {"cart_count": cart.count}
        return {"cart_count": guest.session_cart_count(request)}
    except Exception:  # pragma: no cover - never break page rendering
        return {"cart_count": 0}
