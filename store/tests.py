"""
Store app tests: listing, filters, search, sorting, pagination,
product detail, and review rules.
"""
from django.test import TestCase
from django.urls import reverse

from .models import Brand, Category, Product, ProductImage, ProductSize, Review


def make_product(name="Air Zoom Pegasus", price=1000, **kwargs):
    """Tiny factory used across the store tests."""
    stock = kwargs.pop("stock", 5)
    brand, _ = Brand.objects.get_or_create(name=kwargs.pop("brand_name", "Nike"))
    cat, _ = Category.objects.get_or_create(
        slug="running", defaults={"name": "Running", "kind": "type"}
    )
    product = Product.objects.create(
        name=name, brand=brand, category=cat,
        description="A great running shoe.",
        price=price, **kwargs,
    )
    ProductSize.objects.create(product=product, size="8", stock=stock)
    return product


class ProductListTests(TestCase):
    def setUp(self):
        self.p1 = make_product("Air Zoom Pegasus", price=1000, discount_price=800)
        self.p2 = make_product("Ultraboost Light", price=3000, brand_name="Adidas")
        self.p3 = make_product("Kids Runner", price=500, brand_name="Puma", stock=0)

    def test_list_page_renders(self):
        r = self.client.get(reverse("store:product_list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "All shoes")
        self.assertEqual(r.context["total_results"], 3)

    def test_search_by_name(self):
        r = self.client.get(reverse("store:product_list"), {"q": "pegasus"})
        self.assertEqual(r.context["total_results"], 1)
        self.assertEqual(r.context["products"][0], self.p1)

    def test_search_by_brand(self):
        r = self.client.get(reverse("store:product_list"), {"q": "adidas"})
        self.assertEqual(r.context["total_results"], 1)

    def test_brand_filter(self):
        r = self.client.get(reverse("store:product_list"), {"brand": "nike"})
        self.assertEqual(r.context["total_results"], 1)

    def test_price_range_filter(self):
        r = self.client.get(
            reverse("store:product_list"), {"min_price": "400", "max_price": "1100"}
        )
        # p1 (discount 800) and p3 (500) match
        self.assertEqual(r.context["total_results"], 2)

    def test_size_filter_excludes_out_of_stock(self):
        r = self.client.get(reverse("store:product_list"), {"size": "8"})
        # p3 has size 8 but stock 0
        self.assertEqual(r.context["total_results"], 2)

    def test_sort_price_ascending_uses_discount(self):
        r = self.client.get(reverse("store:product_list"), {"sort": "price_asc"})
        prices = [p.final_price for p in r.context["products"]]
        self.assertEqual(prices, sorted(prices))
        # Discounted 800 must sort before 500? No: 500 < 800 < 3000
        self.assertEqual(prices[0], 500)

    def test_sort_price_descending(self):
        r = self.client.get(reverse("store:product_list"), {"sort": "price_desc"})
        prices = [p.final_price for p in r.context["products"]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_sort_popularity(self):
        Product.objects.filter(pk=self.p2.pk).update(popularity=999)
        r = self.client.get(reverse("store:product_list"), {"sort": "popularity"})
        self.assertEqual(r.context["products"][0], self.p2)

    def test_pagination(self):
        for i in range(15):
            make_product(name=f"Bulk {i}")
        r = self.client.get(reverse("store:product_list"))
        self.assertEqual(len(r.context["products"]), 12)
        self.assertTrue(r.context["is_paginated"])
        r2 = self.client.get(reverse("store:product_list"), {"page": "2"})
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.context["is_paginated"] or len(r2.context["products"]) > 0)

    def test_invalid_page_falls_back(self):
        r = self.client.get(reverse("store:product_list"), {"page": "999"})
        self.assertEqual(r.status_code, 200)

    def test_invalid_price_ignored(self):
        r = self.client.get(
            reverse("store:product_list"), {"min_price": "abc", "max_price": "xyz"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["total_results"], 3)


class CategoryFilterTests(TestCase):
    def test_parent_category_includes_children(self):
        men = Category.objects.create(name="Men", slug="men", kind="audience")
        Category.objects.create(
            name="Running", slug="men-running", kind="type", parent=men
        )
        brand, _ = Brand.objects.get_or_create(name="Nike")
        child = Category.objects.get(slug="men-running")
        Product.objects.create(
            name="Child shoe", brand=brand, category=child,
            description="x", price=1000,
        )
        r = self.client.get(reverse("store:product_list"), {"category": "men"})
        self.assertEqual(r.context["total_results"], 1)


class ProductDetailTests(TestCase):
    def setUp(self):
        self.product = make_product()
        ProductImage.objects.create(
            product=self.product, image="products/a.png", is_primary=True
        )
        ProductImage.objects.create(
            product=self.product, image="products/b.png"
        )
        ProductSize.objects.create(product=self.product, size="10", stock=0)

    def test_detail_renders(self):
        r = self.client.get(self.product.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.product.name)
        self.assertContains(r, "Foot length (cm)")  # size guide
        self.assertContains(r, "Add to cart")

    def test_out_of_stock_size_disabled(self):
        oos = self.product.sizes.get(size="10")
        r = self.client.get(self.product.get_absolute_url())
        # The radio input for a zero-stock size must carry `disabled`.
        self.assertContains(r, f'value="{oos.pk}"')
        self.assertContains(r, "disabled")
        # And the label gets the disabled class for styling.
        self.assertContains(r, 'class="size-opt disabled"')

    def test_unknown_slug_404(self):
        r = self.client.get("/products/does-not-exist/")
        self.assertEqual(r.status_code, 404)

    def test_review_requires_login(self):
        r = self.client.post(
            reverse("store:post_review", args=[self.product.slug]),
            {"rating": 5, "title": "t", "comment": "c"},
        )
        # redirects to login
        self.assertEqual(r.status_code, 302)
        self.assertIn("login", r["Location"])

    def test_logged_in_review_saved(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="rev", email="rev@x.com", password="pass12345"
        )
        self.client.login(username="rev", password="pass12345")
        r = self.client.post(
            reverse("store:post_review", args=[self.product.slug]),
            {"rating": 4, "title": "Nice", "comment": "Comfortable and light."},
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(self.product.reviews.count(), 1)

    def test_one_review_per_user(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="rev2", email="rev2@x.com", password="pass12345"
        )
        Review.objects.create(
            product=self.product, user=user, rating=3, comment="ok"
        )
        self.client.login(username="rev2", password="pass12345")
        self.client.post(
            reverse("store:post_review", args=[self.product.slug]),
            {"rating": 5, "title": "x", "comment": "y"},
        )
        self.assertEqual(self.product.reviews.count(), 1)


class HomePageTests(TestCase):
    def test_home_renders(self):
        make_product()
        r = self.client.get(reverse("store:home"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Shop by category")
        self.assertContains(r, "Featured picks")


class SearchSuggestionTests(TestCase):
    def test_suggestions_json(self):
        make_product(name="Cloud Runner")
        r = self.client.get(reverse("store:search_suggestions"), {"q": "cloud"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["name"], "Cloud Runner")

    def test_short_query_returns_empty(self):
        r = self.client.get(reverse("store:search_suggestions"), {"q": "c"})
        self.assertEqual(r.json()["results"], [])
