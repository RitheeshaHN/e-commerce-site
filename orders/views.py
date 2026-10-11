"""
Orders app views: checkout (address + payment), mock online payment,
order confirmation, order history, order detail and cancellation.

Stock is reduced inside a transaction when the order is placed so a
concurrent shopper can't buy the same last pair.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Address
from store.models import ProductSize

from .forms import CheckoutForm
from .models import Order, OrderItem


def _form_from_saved_address(request, order=None):
    """Prefill the checkout form from a saved address or last order."""
    initial = {}
    saved = request.user.addresses.order_by("-is_default", "-created_at").first()
    if saved:
        initial = {
            "full_name": saved.full_name,
            "phone": saved.phone,
            "address_line1": saved.line1,
            "address_line2": saved.line2,
            "city": saved.city,
            "state": saved.state,
            "pincode": saved.pincode,
            "saved_address_id": saved.pk,
        }
    elif order is None and request.user.first_name:
        initial = {"full_name": request.user.get_full_name() or request.user.username}
    return initial


@login_required
def checkout(request):
    """
    Checkout page.

    GET  -> show the address/payment form (prefilled from saved address)
    POST -> validate, create Order + OrderItem, reduce stock, clear cart.
    """
    from cart.utils import cart_totals, clear_cart

    totals = cart_totals(request)
    if not totals["items"]:
        messages.info(request, "Your cart is empty.")
        return redirect("store:product_list")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if not form.is_valid():
            # Re-render with errors; keep the cart totals visible.
            return render(
                request,
                "orders/checkout.html",
                {
                    "form": form,
                    **totals,
                    "saved_addresses": request.user.addresses.all(),
                },
                status=400,
            )

        data = form.cleaned_data

        # --- stock re-check server-side (never trust the client) --------
        for line in totals["items"]:
            if line["quantity"] > line["size"].stock:
                messages.error(
                    request,
                    f"Only {line['size'].stock} left for "
                    f"{line['product'].name} UK {line['size'].size}.",
                )
                return redirect("cart:cart_detail")

        # --- create the order atomically --------------------------------
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                order_number=Order.generate_order_number(),
                status="Pending",
                payment_method=data["payment_method"],
                payment_status=(
                    "pending" if data["payment_method"] == "cod" else "pending"
                ),
                full_name=data["full_name"],
                phone=data["phone"],
                address_line1=data["address_line1"],
                address_line2=data.get("address_line2", ""),
                city=data["city"],
                state=data["state"],
                pincode=data["pincode"],
                note=data.get("note", ""),
                subtotal=totals["subtotal"],
                shipping=totals["shipping"],
                total=totals["total"],
            )

            # Snapshot each line + decrement stock.
            for line in totals["items"]:
                size: ProductSize = line["size"]
                product = line["product"]
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    size=size,
                    product_name=str(product),
                    product_slug=product.slug,
                    # Snapshot the full human label ("UK 8" / "Kids 10" / "M")
                    # so order history still reads correctly if the product
                    # later changes size system.
                    size_label=f"{product.size_prefix}{size.size}".strip(),
                    unit_price=product.final_price,
                    quantity=line["quantity"],
                )
                # Lock the size row to avoid overselling under concurrency.
                locked = ProductSize.objects.select_for_update().get(pk=size.pk)
                locked.stock = max(0, locked.stock - line["quantity"])
                locked.save(update_fields=["stock"])

            # Remember the address for the profile page if requested.
            if data.get("save_address"):
                Address.objects.create(
                    user=request.user,
                    full_name=data["full_name"],
                    phone=data["phone"],
                    line1=data["address_line1"],
                    line2=data.get("address_line2", ""),
                    city=data["city"],
                    state=data["state"],
                    pincode=data["pincode"],
                    is_default=not request.user.addresses.exists(),
                )

        # Cart is emptied only after the order is safely stored.
        clear_cart(request)

        if data["payment_method"] == "online":
            # Mock payment step: confirm or fail, then return to confirmation.
            return redirect("orders:mock_payment", order_number=order.order_number)

        messages.success(request, f"Order {order.order_number} placed successfully!")
        return redirect("orders:order_detail", order_number=order.order_number)

    form = CheckoutForm(initial=_form_from_saved_address(request))
    return render(
        request,
        "orders/checkout.html",
        {
            "form": form,
            **totals,
            "saved_addresses": request.user.addresses.all(),
        },
    )


@login_required
def mock_payment(request, order_number):
    """
    Fake payment gateway: a page with "Pay" / "Cancel" buttons.

    Success -> order becomes Confirmed and payment_status = paid.
    Failure -> order stays Pending (customer can retry or cancel).
    """
    order = get_object_or_404(Order, order_number=order_number, user=request.user)

    if order.payment_status == "paid":
        return redirect("orders:order_detail", order_number=order.order_number)

    return render(request, "orders/mock_payment.html", {"order": order})


@login_required
@require_POST
def mock_payment_process(request, order_number):
    """Handle the mock gateway's Pay / Fail buttons."""
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    action = request.POST.get("action", "pay")

    if action == "pay":
        order.payment_status = "paid"
        order.status = "Confirmed"  # online payments confirm immediately
        order.save(update_fields=["payment_status", "status", "updated_at"])
        messages.success(request, "Payment successful! Your order is confirmed.")
    else:
        order.payment_status = "failed"
        order.save(update_fields=["payment_status", "updated_at"])
        messages.warning(
            request, "Payment failed. You can retry from the order page."
        )
    return redirect("orders:order_detail", order_number=order.order_number)


@login_required
def order_list(request):
    """Order history for the logged-in user."""
    orders = request.user.orders.all()
    return render(request, "orders/order_list.html", {"orders": orders})


@login_required
def order_detail(request, order_number):
    """Single order: items, address, totals, status, cancel button."""
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product__images"),
        order_number=order_number,
        user=request.user,
    )

    # Progress steps for the tracker, marking completed ones.
    steps = ["Pending", "Confirmed", "Shipped", "Delivered"]
    try:
        current_idx = steps.index(order.status)
    except ValueError:  # Cancelled
        current_idx = -1
    tracker_steps = [
        (
            step,
            ("✓ " if i <= current_idx else "") + step,
            "done" if i < current_idx else ("active" if i == current_idx else ""),
        )
        for i, step in enumerate(steps)
    ]

    return render(
        request,
        "orders/order_detail.html",
        {"order": order, "tracker_steps": tracker_steps},
    )


@login_required
@require_POST
def order_cancel(request, order_number):
    """
    Cancel a Pending order and restore its stock.

    Only the owner can cancel, and only while status == Pending.
    """
    order = get_object_or_404(Order, order_number=order_number, user=request.user)

    if not order.can_cancel:
        messages.error(
            request,
            f"Order {order.order_number} is {order.status} and can no longer be cancelled.",
        )
        return redirect("orders:order_detail", order_number=order.order_number)

    with transaction.atomic():
        # Restore stock for every line.
        for item in order.items.all():
            ProductSize.objects.filter(pk=item.size_id).update(
                stock=F("stock") + item.quantity
            )
        order.status = "Cancelled"
        order.save(update_fields=["status", "updated_at"])

    messages.success(request, f"Order {order.order_number} has been cancelled.")
    return redirect("orders:order_detail", order_number=order.order_number)
