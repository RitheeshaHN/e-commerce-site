"""Cart app tests: guest session cart, DB cart, AJAX endpoints, merge."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from store.models import Brand, Category, Product, ProductSize

from .models import Cart, CartItem


def make_sized_product(name="Air Zoom", stock=10, size="8", price=1000):
    brand, _ = Brand.objects.get_or_create(name="Nike")
    cat, _ = Category.objects.get_or_create(
        slug="running", defaults={"name": "Running"}
    )
    product = Product.objects.create(
        name=name, brand=brand, category=cat,
        description="x", price=price,
    )
    sz = ProductSize.objects.create(product=product, size=size, stock=stock)
    return product, sz


def ajax(client, url, payload=None):
    """POST JSON like our fetch() JavaScript does."""
    return client.post(
        url, data=json.dumps(payload or {}),
        content_type="application/json",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )


class GuestCartTests(TestCase):
    def setUp(self):
        self.product, self.size = make_sized_product()

    def test_add_to_session_cart(self):
        r = ajax(self.client, reverse("cart:cart_add", args=[self.size.pk]),
                 {"quantity": 2})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["count"], 2)

    def test_cart_page_shows_session_item(self):
        ajax(self.client, reverse("cart:cart_add", args=[self.size.pk]),
             {"quantity": 2})
        r = self.client.get(reverse("cart:cart_detail"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context["items"]), 1)
        self.assertEqual(r.context["subtotal"], 2000.0)

    def test_add_same_size_bumps_quantity(self):
        url = reverse("cart:cart_add", args=[self.size.pk])
        ajax(self.client, url, {"quantity": 1})
        ajax(self.client, url, {"quantity": 2})
        r = self.client.get(reverse("cart:cart_detail"))
        self.assertEqual(r.context["items"][0]["quantity"], 3)

    def test_cannot_exceed_stock(self):
        url = reverse("cart:cart_add", args=[self.size.pk])
        ajax(self.client, url, {"quantity": 8})  # only 10 in stock
        ajax(self.client, url, {"quantity": 8})  # would be 16
        r = self.client.get(reverse("cart:cart_detail"))
        self.assertEqual(r.context["items"][0]["quantity"], 10)

    def test_out_of_stock_size_rejected(self):
        _, oos = make_sized_product(name="Sold Out", stock=0, size="9")
        r = ajax(self.client, reverse("cart:cart_add", args=[oos.pk]),
                 {"quantity": 1})
        self.assertFalse(r.json()["ok"])
        self.assertIn("out of stock", r.json()["message"].lower())

    def test_update_quantity_ajax(self):
        ajax(self.client, reverse("cart:cart_add", args=[self.size.pk]),
             {"quantity": 2})
        r = ajax(self.client, reverse("cart:cart_update", args=[self.size.pk]),
                 {"quantity": 5})
        data = r.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["count"], 5)
        self.assertEqual(data["totals"]["subtotal"], 5000.0)

    def test_update_to_zero_removes(self):
        ajax(self.client, reverse("cart:cart_add", args=[self.size.pk]),
             {"quantity": 2})
        r = ajax(self.client, reverse("cart:cart_update", args=[self.size.pk]),
                 {"quantity": 0})
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r.json()["count"], 0)

    def test_remove_ajax(self):
        ajax(self.client, reverse("cart:cart_add", args=[self.size.pk]))
        r = ajax(self.client, reverse("cart:cart_remove", args=[self.size.pk]))
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r.json()["count"], 0)

    def test_shipping_free_over_threshold(self):
        _, big = make_sized_product(name="Big Spender", stock=5, price=2500)
        ajax(self.client, reverse("cart:cart_add", args=[big.pk]), {"quantity": 1})
        r = self.client.get(reverse("cart:cart_detail"))
        self.assertEqual(r.context["shipping"], 0.0)
        self.assertEqual(r.context["total"], 2500.0)

    def test_shipping_fee_under_threshold(self):
        r = self.client.get(reverse("cart:cart_detail"))
        self.assertEqual(r.context["shipping"], 0.0)  # empty cart

    def test_mutation_requires_post(self):
        r = self.client.get(reverse("cart:cart_add", args=[self.size.pk]))
        self.assertEqual(r.status_code, 405)

    def test_bad_json_body_handled(self):
        r = self.client.post(
            reverse("cart:cart_add", args=[self.size.pk]),
            data="not json{", content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200)  # falls back to defaults

    def test_bad_size_404(self):
        r = ajax(self.client, reverse("cart:cart_add", args=[999999]))
        self.assertEqual(r.status_code, 404)


class UserCartTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="buyer", email="b@x.com", password="pass12345"
        )
        self.product, self.size = make_sized_product()

    def test_cart_created_on_demand(self):
        self.client.login(username="buyer", password="pass12345")
        ajax(self.client, reverse("cart:cart_add", args=[self.size.pk]),
             {"quantity": 2})
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.count, 2)
        item = cart.items.first()
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.size, self.size)

    def test_db_cart_totals(self):
        self.client.login(username="buyer", password="pass12345")
        ajax(self.client, reverse("cart:cart_add", args=[self.size.pk]),
             {"quantity": 2})
        r = self.client.get(reverse("cart:cart_detail"))
        self.assertEqual(r.context["subtotal"], 2000.0)

    def test_user_cannot_touch_others_cart(self):
        other = get_user_model().objects.create_user(
            username="other", email="o@x.com", password="pass12345"
        )
        cart = Cart.objects.create(user=other)
        item = CartItem.objects.create(
            cart=cart, product=self.product, size=self.size, quantity=3
        )
        self.client.login(username="buyer", password="pass12345")
        r = ajax(self.client, reverse("cart:cart_update", args=[item.pk]),
                 {"quantity": 1})
        self.assertFalse(r.json()["ok"])
        item.refresh_from_db()
        self.assertEqual(item.quantity, 3)


class CartMergeTests(TestCase):
    """Guest session cart must merge into the DB cart on login/register."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="merger", email="m@x.com", password="pass12345"
        )
        self.product, self.size = make_sized_product()

    def test_login_merges_session_cart(self):
        # 1. guest adds 2 to the session cart
        ajax(self.client, reverse("cart:cart_add", args=[self.size.pk]),
             {"quantity": 2})
        self.assertEqual(self.client.session.get("guest_cart"), [
            {"product_id": self.product.id, "size_id": self.size.pk,
             "quantity": 2}
        ])

        # 2. logging in must move it into the database cart
        self.client.post(reverse("accounts:login"),
                         {"username": "merger", "password": "pass12345"})

        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.count, 2)
        # session cart cleared
        self.assertNotIn("guest_cart", self.client.session)

    def test_register_merges_session_cart(self):
        ajax(self.client, reverse("cart:cart_add", args=[self.size.pk]),
             {"quantity": 3})
        self.client.post(reverse("accounts:register"), {
            "username": "newbie", "first_name": "New", "last_name": "Bee",
            "email": "n@x.com", "phone": "9876543210",
            "password1": "S3curePass!xyz", "password2": "S3curePass!xyz",
        })
        user = get_user_model().objects.get(username="newbie")
        cart = Cart.objects.get(user=user)
        self.assertEqual(cart.count, 3)

    def test_merge_sums_quantities(self):
        # existing DB item + incoming session item => summed
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=cart, product=self.product, size=self.size, quantity=2
        )
        ajax(self.client, reverse("cart:cart_add", args=[self.size.pk]),
             {"quantity": 3})
        self.client.post(reverse("accounts:login"),
                         {"username": "merger", "password": "pass12345"})
        cart.refresh_from_db()
        self.assertEqual(cart.items.get().quantity, 5)

    def test_merge_respects_stock(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=cart, product=self.product, size=self.size, quantity=9
        )
        ajax(self.client, reverse("cart:cart_add", args=[self.size.pk]),
             {"quantity": 5})  # would be 14 but stock is 10
        self.client.post(reverse("accounts:login"),
                         {"username": "merger", "password": "pass12345"})
        cart.refresh_from_db()
        self.assertEqual(cart.items.get().quantity, 10)

    def test_cart_badge_context_processor(self):
        r = self.client.get(reverse("store:home"))
        self.assertEqual(r.context["cart_count"], 0)
        ajax(self.client, reverse("cart:cart_add", args=[self.size.pk]),
             {"quantity": 4})
        r = self.client.get(reverse("store:home"))
        self.assertEqual(r.context["cart_count"], 4)


class SizeSystemLabelTests(TestCase):
    """The cart shows the right prefix for each size system."""

    def _add_and_open_cart(self, product_size):
        ajax(self.client, reverse("cart:cart_add", args=[product_size.pk]),
             {"quantity": 1})
        return self.client.get(reverse("cart:cart_detail"))

    def test_adult_size_shows_uk_prefix(self):
        product, size = make_sized_product(name="Adult Pair", size="8")
        Product.objects.filter(pk=product.pk).update(size_system="adult")
        r = self._add_and_open_cart(size)
        self.assertContains(r, "Size: UK 8")

    def test_kids_size_shows_kids_prefix(self):
        product, size = make_sized_product(name="Kids Pair", size="10")
        Product.objects.filter(pk=product.pk).update(size_system="kids")
        r = self._add_and_open_cart(size)
        self.assertContains(r, "Size: Kids 10")

    def test_slipper_size_shows_no_prefix(self):
        product, size = make_sized_product(name="Slide Slipper", size="M")
        Product.objects.filter(pk=product.pk).update(size_system="label")
        r = self._add_and_open_cart(size)
        self.assertContains(r, "Size: M")
        self.assertNotContains(r, "UK M")
