"""
Cart app views: the cart page plus JSON endpoints used by
``static/js/cart.js`` so updates happen without a page reload.

All mutating endpoints are POST + CSRF-protected.
"""
import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from store.models import ProductSize

from . import session as guest
from . import utils


def _is_ajax(request) -> bool:
    """True when the request came from our fetch() JavaScript."""
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _body(request) -> dict:
    """Parse the JSON body, falling back to an empty dict."""
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


def _cart_count(request) -> int:
    """Current unit count for the navbar badge."""
    if request.user.is_authenticated:
        return utils.get_or_create_cart(request.user).count
    return guest.session_cart_count(request)


def cart_detail(request):
    """Render the cart page with line items and live totals."""
    totals = utils.cart_totals(request)
    return render(request, "cart/cart.html", totals)


@require_POST
def cart_add(request, size_id):
    """
    Add a product/size to the cart.

    JSON body: {product_id, quantity}
    Works for guests (session) and users (database).
    """
    body = _body(request)

    # Prefer the JSON body; fall back to normal form POSTs.
    quantity = int(body.get("quantity") or request.POST.get("quantity") or 1)
    quantity = max(1, min(quantity, 10))  # sane limits

    size = get_object_or_404(ProductSize.objects.select_related("product"), pk=size_id)
    result = utils.add_item(request, size.product, size, quantity)
    result["count"] = _cart_count(request)

    if _is_ajax(request):
        return JsonResponse(result)

    # Non-JS fallback: redirect with a message instead of JSON.
    from django.contrib import messages

    if result["ok"]:
        messages.success(request, result["message"])
        return redirect("cart:cart_detail")
    messages.error(request, result["message"])
    return redirect(size.product.get_absolute_url())


@require_POST
def cart_update(request, item_id):
    """Update quantity (quantity=0 removes) a cart line."""
    body = _body(request)
    quantity = int(body.get("quantity", request.POST.get("quantity", 1)))
    is_guest = not request.user.is_authenticated

    result = utils.update_item(request, item_id, quantity, is_guest=is_guest)
    if result["ok"]:
        result["count"] = _cart_count(request)
    return JsonResponse(result)


@require_POST
def cart_remove(request, item_id):
    """Remove a cart line entirely."""
    is_guest = not request.user.is_authenticated
    result = utils.remove_item(request, item_id, is_guest=is_guest)
    result["count"] = _cart_count(request)
    return JsonResponse(result)
