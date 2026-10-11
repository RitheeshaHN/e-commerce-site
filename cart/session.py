"""
Session-based cart helpers for *guest* shoppers.

The session cart is a plain list of dicts:

    {"product_id": 3, "size_id": 12, "quantity": 2}

so it can later be merged into the database cart once the guest
creates an account or logs in.
"""
from django.conf import settings

SESSION_KEY = "guest_cart"


def get_session_cart(request) -> list:
    """Return the guest cart list (always a list, never None)."""
    return request.session.get(SESSION_KEY, [])


def save_session_cart(request, items: list) -> None:
    """Persist the guest cart back into the session and mark it modified."""
    request.session[SESSION_KEY] = items
    # Ensure the session is saved even if no other data changed.
    request.session.modified = True


def session_cart_count(request) -> int:
    """Total units in the guest cart (for the navbar badge)."""
    return sum(i.get("quantity", 0) for i in get_session_cart(request))


def add_to_session_cart(request, product_id: int, size_id: int, quantity: int) -> int:
    """
    Add ``quantity`` of a product/size to the guest cart.

    Returns the new quantity for that line (capped at stock by the caller).
    """
    items = get_session_cart(request)
    for item in items:
        if item["product_id"] == product_id and item["size_id"] == size_id:
            item["quantity"] += quantity
            save_session_cart(request, items)
            return item["quantity"]

    items.append({"product_id": product_id, "size_id": size_id, "quantity": quantity})
    save_session_cart(request, items)
    return quantity


def clear_session_cart(request_or_session) -> None:
    """
    Remove the guest cart (after merge or checkout).

    Accepts either a request object or the raw session -- both work
    because we only touch ``session[SESSION_KEY]``.
    """
    session = getattr(request_or_session, "session", request_or_session)
    if SESSION_KEY in session:
        del session[SESSION_KEY]
        session.modified = True


def session_has_items(request) -> bool:
    return bool(get_session_cart(request))


def shipping_for(subtotal: float) -> float:
    """Shared by guest + user carts so totals always match."""
    if subtotal <= 0:
        return 0.0
    threshold = getattr(settings, "FREE_SHIPPING_THRESHOLD", 1999.0)
    fee = getattr(settings, "SHIPPING_FEE", 99.0)
    return 0.0 if subtotal >= threshold else fee
