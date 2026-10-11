"""
Cart utilities that work the same way for guests and logged-in users.

Views call these functions and never care where the cart actually
lives (session vs. database) -- that keeps the code in one place.
"""
from django.db import transaction

from store.models import Product, ProductSize

from . import session as guest
from .models import Cart, CartItem


def get_or_create_cart(user):
    """Database cart for a logged-in user (created on first use)."""
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def get_cart(request):
    """
    Return ``(cart_object_or_None, items_list)`` for the current request.

    Every entry in ``items_list`` is a plain dict with the same keys for
    guests and logged-in users, so templates never need branching:

        {"id", "product", "size", "quantity"}

    ``id`` is the CartItem PK for users and the ProductSize PK for guests
    (session rows have no PK) -- matching what cart_update/remove expect.
    """
    if request.user.is_authenticated:
        cart = get_or_create_cart(request.user)
        rows = cart.items.select_related("product", "product__brand", "size")
        return cart, [
            {
                "id": item.pk,          # CartItem PK
                "product": item.product,
                "size": item.size,
                "quantity": item.quantity,
                "unit_price": item.product.final_price,
                "line_total": item.line_total,
            }
            for item in rows
        ]

    # Guest: build a lightweight list from the session.
    items = []
    for entry in guest.get_session_cart(request):
        try:
            size = ProductSize.objects.select_related("product", "product__brand").get(
                pk=entry["size_id"]
            )
        except ProductSize.DoesNotExist:
            continue  # stale session row (product removed) -- ignore
        qty = max(1, int(entry.get("quantity", 1)))
        qty = min(qty, size.stock) if size.stock else qty
        items.append(
            {
                "id": size.pk,          # ProductSize PK for guest rows
                "product": size.product,
                "size": size,
                "quantity": qty,
                "unit_price": size.product.final_price,
                "line_total": round(size.product.final_price * qty, 2),
            }
        )
    return None, items


def cart_totals(request) -> dict:
    """Subtotal / shipping / total / count for the current request."""
    _, items = get_cart(request)
    subtotal = round(sum(i["product"].final_price * i["quantity"] for i in items), 2)
    shipping = guest.shipping_for(subtotal)
    count = sum(i["quantity"] for i in items)
    return {
        "subtotal": subtotal,
        "shipping": shipping,
        "total": round(subtotal + shipping, 2),
        "count": count,
        "items": items,
    }


def add_item(request, product: Product, size: ProductSize, quantity: int) -> dict:
    """
    Add a product/size to the cart (guest -> session, user -> DB).

    Returns a dict: {ok, message, count}
    """
    if size.stock < 1:
        return {"ok": False, "message": f"UK {size.size} is out of stock."}

    if request.user.is_authenticated:
        cart = get_or_create_cart(request.user)
        with transaction.atomic():
            item, created = CartItem.objects.get_or_create(
                cart=cart, product=product, size=size,
                defaults={"quantity": quantity},
            )
            if not created:
                new_qty = item.quantity + quantity
                if new_qty > size.stock:
                    # Clamp to available stock instead of failing outright.
                    if item.quantity >= size.stock:
                        return {
                            "ok": False,
                            "message": f"Only {size.stock} left in UK {size.size}.",
                            "count": cart.count,
                        }
                    new_qty = size.stock
                item.quantity = new_qty
                item.save(update_fields=["quantity"])
        return {"ok": True, "message": "Added to cart.", "count": cart.count}

    # Guest path
    current = 0
    for entry in guest.get_session_cart(request):
        if entry["product_id"] == product.id and entry["size_id"] == size.id:
            current = entry["quantity"]
            break
    if current + quantity > size.stock:
        if current >= size.stock:
            return {"ok": False, "message": f"Only {size.stock} left in UK {size.size}."}
        quantity = size.stock - current
    guest.add_to_session_cart(request, product.id, size.id, quantity)
    return {"ok": True, "message": "Added to cart.", "count": guest.session_cart_count(request)}


def update_item(request, item_id: int, quantity: int, is_guest: bool) -> dict:
    """Update quantity for a cart line. Returns {ok, message, count, totals}."""
    if is_guest:
        items = guest.get_session_cart(request)
        idx = next(
            (n for n, e in enumerate(items)
             if str(e["size_id"]) == str(item_id)),
            None,
        )
        if idx is None:
            return {"ok": False, "message": "Item not found in cart."}

        size = ProductSize.objects.filter(pk=items[idx]["size_id"]).first()
        max_qty = size.stock if size else 0
        if quantity < 1:
            items.pop(idx)
        elif quantity > max_qty:
            quantity = max_qty
            items[idx]["quantity"] = quantity
        else:
            items[idx]["quantity"] = quantity
        guest.save_session_cart(request, items)
        if quantity < 1:
            items = guest.get_session_cart(request)
        totals = cart_totals(request)
        return {
            "ok": True,
            "message": "Cart updated." if quantity >= 1 else "Item removed.",
            "count": totals["count"],
            "totals": {k: totals[k] for k in ("subtotal", "shipping", "total")},
            "line_total": None,
        }

    # Logged-in path
    try:
        item = CartItem.objects.select_related("size", "product").get(
            pk=item_id, cart__user=request.user
        )
    except CartItem.DoesNotExist:
        return {"ok": False, "message": "Item not found in cart."}

    if quantity < 1:
        item.delete()
        totals = cart_totals(request)
        return {
            "ok": True, "message": "Item removed.",
            "count": totals["count"],
            "totals": {k: totals[k] for k in ("subtotal", "shipping", "total")},
            "line_total": None,
        }

    if quantity > item.size.stock:
        quantity = item.size.stock
    item.quantity = quantity
    item.save(update_fields=["quantity"])
    totals = cart_totals(request)
    return {
        "ok": True, "message": "Cart updated.",
        "count": totals["count"],
        "totals": {k: totals[k] for k in ("subtotal", "shipping", "total")},
        "line_total": round(item.line_total, 2),
    }


def remove_item(request, item_id: int, is_guest: bool) -> dict:
    """Remove a line from the cart."""
    if is_guest:
        items = [e for e in guest.get_session_cart(request) if str(e["size_id"]) != str(item_id)]
        guest.save_session_cart(request, items)
    else:
        CartItem.objects.filter(pk=item_id, cart__user=request.user).delete()
    totals = cart_totals(request)
    return {
        "ok": True, "message": "Item removed.",
        "count": totals["count"],
        "totals": {k: totals[k] for k in ("subtotal", "shipping", "total")},
    }


def clear_cart(request) -> None:
    """Empty the cart after a successful order."""
    if request.user.is_authenticated:
        Cart.objects.filter(user=request.user).delete()
    else:
        guest.clear_session_cart(request)


def merge_session_cart(user, session) -> int:
    """
    Merge a guest's session cart into their database cart on login.

    Called from the login view after successful authentication.
    Quantities are summed and clamped to available stock.
    Returns the number of lines merged.
    """
    entries = session.get(guest.SESSION_KEY, [])
    if not entries:
        return 0

    cart, _ = Cart.objects.get_or_create(user=user)
    merged = 0
    with transaction.atomic():
        for entry in entries:
            try:
                size = ProductSize.objects.select_related("product").get(pk=entry["size_id"])
            except ProductSize.DoesNotExist:
                continue
            qty = max(1, int(entry.get("quantity", 1)))
            qty = min(qty, size.stock) if size.stock else qty
            if qty < 1:
                continue
            item, created = CartItem.objects.get_or_create(
                cart=cart, product=size.product, size=size,
                defaults={"quantity": qty},
            )
            if not created:
                new_qty = min(item.quantity + qty, size.stock or (item.quantity + qty))
                if new_qty != item.quantity:
                    item.quantity = new_qty
                    item.save(update_fields=["quantity"])
            merged += 1

    guest.clear_session_cart(session)  # drop the guest cart now that it's merged
    return merged
