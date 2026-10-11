"""Orders app tests: checkout, stock, cancel, mock payment, protection."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from store.models import Brand, Category, Product, ProductSize

from .models import Order, OrderItem

VALID = {
    "full_name": "Flow Tester",
    "phone": "9876543210",
    "address_line1": "12, Test Street",
    "address_line2": "",
    "city": "Bengaluru",
    "state": "Karnataka",
    "pincode": "560001",
    "payment_method": "cod",
    "note": "",
    "save_address": "on",
    "saved_address_id": "",
}


def make_sized_product(name="Air Zoom", stock=10, size="8", price=1000):
    brand, _ = Brand.objects.get_or_create(name="Nike")
    cat, _ = Category.objects.get_or_create(
        slug="running", defaults={"name": "Running", "kind": "type"}
    )
    product = Product.objects.create(
        name=name, brand=brand, category=cat,
        description="x", price=price,
    )
    sz = ProductSize.objects.create(product=product, size=size, stock=stock)
    return product, sz


class BaseOrderTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="buyer", email="b@x.com", password="pass12345"
        )
        self.product, self.size = make_sized_product()
        self.client.login(username="buyer", password="pass12345")
        # put 3 in the cart
        self.client.post(reverse("cart:cart_add", args=[self.size.pk]),
                         data='{"quantity": 3}',
                         content_type="application/json",
                         HTTP_X_REQUESTED_WITH="XMLHttpRequest")


class CheckoutTests(BaseOrderTest):
    def test_checkout_page_renders(self):
        r = self.client.get(reverse("orders:checkout"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Shipping address")
        self.assertContains(r, "Cash on Delivery")

    def test_checkout_requires_login(self):
        self.client.logout()
        r = self.client.get(reverse("orders:checkout"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("login", r["Location"])

    def test_checkout_requires_cart(self):
        # Empty the cart (POST, same as the Remove button does).
        self.client.post(reverse("cart:cart_remove", args=[self.size.pk]),
                         HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        # empty cart -> redirected away
        r = self.client.get(reverse("orders:checkout"))
        self.assertEqual(r.status_code, 302)

    def test_cod_order_created(self):
        r = self.client.post(reverse("orders:checkout"), VALID, follow=True)
        self.assertEqual(r.status_code, 200)

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.status, "Pending")
        self.assertEqual(order.payment_method, "cod")
        self.assertEqual(order.payment_status, "pending")
        self.assertEqual(order.items.count(), 1)

        item = order.items.get()
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.unit_price, 1000)
        self.assertEqual(item.size_label, "8")
        # snapshot fields captured
        self.assertEqual(item.product_name, str(self.product))

        self.assertEqual(float(order.subtotal), 3000.0)
        # 3000 >= 1999 => free shipping
        self.assertEqual(float(order.shipping), 0.0)
        self.assertEqual(float(order.total), 3000.0)

    def test_order_number_generated(self):
        self.client.post(reverse("orders:checkout"), VALID)
        order = Order.objects.get(user=self.user)
        self.assertTrue(order.order_number.startswith("SU-"))
        self.assertEqual(len(order.order_number), len("SU-000000-0000"))

    def test_stock_reduced(self):
        self.assertEqual(self.size.stock, 10)
        self.client.post(reverse("orders:checkout"), VALID)
        self.size.refresh_from_db()
        self.assertEqual(self.size.stock, 7)

    def test_cart_cleared_after_order(self):
        self.client.post(reverse("orders:checkout"), VALID)
        r = self.client.get(reverse("cart:cart_detail"))
        self.assertEqual(len(r.context["items"]), 0)

    def test_shipping_fee_applied_under_threshold(self):
        # Replace the setUp cart (3000 = free shipping) with a cheap item.
        self.client.post(reverse("cart:cart_remove", args=[self.size.pk]),
                         HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        _, small = make_sized_product(name="Cheap Pair", price=800, size="7")
        self.client.post(reverse("cart:cart_add", args=[small.pk]),
                         data='{"quantity": 1}', content_type="application/json",
                         HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.client.post(reverse("orders:checkout"), VALID)
        order = Order.objects.latest("created_at")
        self.assertEqual(float(order.subtotal), 800.0)
        self.assertEqual(float(order.shipping), 99.0)
        self.assertEqual(float(order.total), 899.0)

    def test_validation_rejects_bad_address(self):
        bad = dict(VALID, pincode="12", phone="1", full_name="A")
        r = self.client.post(reverse("orders:checkout"), bad)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        # cart untouched
        r = self.client.get(reverse("cart:cart_detail"))
        self.assertEqual(len(r.context["items"]), 1)

    def test_cannot_order_more_than_stock(self):
        # Try to buy 10 while only 10 exist... stock check passes.
        # Now sneak in a cart with quantity > stock via direct DB edit.
        from cart.models import CartItem

        item = CartItem.objects.get(cart__user=self.user)
        item.quantity = 99
        item.save()
        r = self.client.post(reverse("orders:checkout"), VALID, follow=True)
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(r, "left for") if r.status_code == 200 else None

    def test_address_saved_to_profile(self):
        self.client.post(reverse("orders:checkout"), VALID)
        addr = self.user.addresses.get()
        self.assertEqual(addr.city, "Bengaluru")
        self.assertEqual(addr.pincode, "560001")
        self.assertEqual(addr.full_name, "Flow Tester")

    def test_address_not_saved_when_unchecked(self):
        data = dict(VALID)
        data.pop("save_address")
        self.client.post(reverse("orders:checkout"), data)
        self.assertEqual(self.user.addresses.count(), 0)


class MockPaymentTests(BaseOrderTest):
    def _place_online_order(self):
        data = dict(VALID, payment_method="online")
        r = self.client.post(reverse("orders:checkout"), data)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/pay/", r["Location"])
        return Order.objects.get(user=self.user)

    def test_online_redirects_to_gateway(self):
        order = self._place_online_order()
        self.assertEqual(order.status, "Pending")

    def test_successful_payment_confirms(self):
        order = self._place_online_order()
        r = self.client.post(
            reverse("orders:mock_payment_process", args=[order.order_number]),
            {"action": "pay"}, follow=True,
        )
        self.assertEqual(r.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.status, "Confirmed")

    def test_failed_payment_keeps_pending(self):
        order = self._place_online_order()
        self.client.post(
            reverse("orders:mock_payment_process", args=[order.order_number]),
            {"action": "fail"}, follow=True,
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "failed")
        self.assertEqual(order.status, "Pending")

    def test_cannot_pay_other_users_order(self):
        order = self._place_online_order()
        other = get_user_model().objects.create_user(
            username="intruder", email="i@x.com", password="pass12345"
        )
        self.client.logout()
        self.client.login(username="intruder", password="pass12345")
        r = self.client.get(
            reverse("orders:mock_payment", args=[order.order_number])
        )
        self.assertEqual(r.status_code, 404)


class OrderHistoryTests(BaseOrderTest):
    def test_order_list_shows_own_orders(self):
        self.client.post(reverse("orders:checkout"), VALID)
        r = self.client.get(reverse("orders:order_list"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context["orders"]), 1)

    def test_order_list_login_required(self):
        self.client.logout()
        r = self.client.get(reverse("orders:order_list"))
        self.assertEqual(r.status_code, 302)

    def test_order_detail_shows_items(self):
        self.client.post(reverse("orders:checkout"), VALID)
        order = Order.objects.get(user=self.user)
        r = self.client.get(
            reverse("orders:order_detail", args=[order.order_number])
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, order.order_number)
        self.assertContains(r, "Pending")

    def test_order_detail_404_for_stranger(self):
        self.client.post(reverse("orders:checkout"), VALID)
        order = Order.objects.get(user=self.user)
        self.client.logout()
        self.client.post(reverse("accounts:login"),
                         {"username": "x", "password": "y"})  # fails
        r = self.client.get(
            reverse("orders:order_detail", args=[order.order_number])
        )
        self.assertIn(r.status_code, (302, 404))


class CancelOrderTests(BaseOrderTest):
    def test_cancel_pending_restores_stock(self):
        self.client.post(reverse("orders:checkout"), VALID)
        order = Order.objects.get(user=self.user)
        self.size.refresh_from_db()
        self.assertEqual(self.size.stock, 7)

        r = self.client.post(
            reverse("orders:order_cancel", args=[order.order_number]),
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        order.refresh_from_db()
        self.size.refresh_from_db()
        self.assertEqual(order.status, "Cancelled")
        self.assertEqual(self.size.stock, 10)  # restored

    def test_cancelled_order_cannot_be_cancelled_again(self):
        self.client.post(reverse("orders:checkout"), VALID)
        order = Order.objects.get(user=self.user)
        self.client.post(reverse("orders:order_cancel", args=[order.order_number]))
        order.refresh_from_db()
        stock_after_first = self.size.stock

        self.client.post(reverse("orders:order_cancel", args=[order.order_number]))
        order.refresh_from_db()
        self.size.refresh_from_db()
        # status unchanged and stock NOT double-credited
        self.assertEqual(order.status, "Cancelled")
        self.assertEqual(self.size.stock, stock_after_first)

    def test_confirmed_order_cannot_be_cancelled(self):
        self.client.post(reverse("orders:checkout"), VALID)
        order = Order.objects.get(user=self.user)
        order.status = "Confirmed"
        order.save()
        self.client.post(reverse("orders:order_cancel", args=[order.order_number]))
        order.refresh_from_db()
        self.size.refresh_from_db()
        self.assertEqual(order.status, "Confirmed")
        self.assertEqual(self.size.stock, 7)  # stock untouched

    def test_cancel_requires_login(self):
        self.client.post(reverse("orders:checkout"), VALID)
        order = Order.objects.get(user=self.user)
        self.client.logout()
        r = self.client.post(
            reverse("orders:order_cancel", args=[order.order_number])
        )
        self.assertEqual(r.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "Pending")


class OrderModelTests(BaseOrderTest):
    def test_can_cancel_property(self):
        self.client.post(reverse("orders:checkout"), VALID)
        order = Order.objects.get(user=self.user)
        self.assertTrue(order.can_cancel)
        order.status = "Shipped"
        self.assertFalse(order.can_cancel)

    def test_status_choices(self):
        choices = {c[0] for c in Order.STATUS}
        self.assertEqual(
            choices,
            {"Pending", "Confirmed", "Shipped", "Delivered", "Cancelled"},
        )

    def test_item_count(self):
        self.client.post(reverse("orders:checkout"), VALID)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.item_count, 3)

    def test_shipping_address_string(self):
        self.client.post(reverse("orders:checkout"), VALID)
        order = Order.objects.get(user=self.user)
        self.assertIn("Bengaluru", order.shipping_address)
        self.assertIn("560001", order.shipping_address)
