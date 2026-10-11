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
    category = kwargs.pop("category", None)
    if category is None:
        category, _ = Category.objects.get_or_create(
            slug="running", defaults={"name": "Running"}
        )
    product = Product.objects.create(
        name=name, brand=brand, category=category,
        description="A great running pair.",
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
        self.assertContains(r, "All footwear")
        self.assertEqual(r.context["total_results"], 3)

    def test_audience_filter(self):
        Product.objects.filter(pk=self.p1.pk).update(audience="men")
        Product.objects.filter(pk=self.p2.pk).update(audience="women")
        Product.objects.filter(pk=self.p3.pk).update(audience="kids")

        r = self.client.get(reverse("store:product_list"), {"audience": "women"})
        self.assertEqual(r.context["total_results"], 1)
        self.assertEqual(r.context["products"][0], self.p2)

    def test_unknown_audience_is_ignored(self):
        r = self.client.get(reverse("store:product_list"), {"audience": "bots"})
        self.assertEqual(r.context["total_results"], 3)

    def test_sale_filter_shows_only_discounted(self):
        # p1 is the only product with a discount_price
        r = self.client.get(reverse("store:product_list"), {"sale": "1"})
        self.assertEqual(r.context["total_results"], 1)
        self.assertEqual(r.context["products"][0], self.p1)

    def test_sale_filter_never_matches_price_equals_discount(self):
        Product.objects.filter(pk=self.p1.pk).update(discount_price=1000)
        r = self.client.get(reverse("store:product_list"), {"sale": "1"})
        self.assertEqual(r.context["total_results"], 0)

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
    def setUp(self):
        self.boots = Category.objects.create(name="Boots", slug="boots")
        self.ankle = Category.objects.create(
            name="Ankle Boots", slug="ankle-boots", parent=self.boots
        )
        self.sandals = Category.objects.create(name="Sandals", slug="sandals")
        brand, _ = Brand.objects.get_or_create(name="Woodland")
        self.in_boots = Product.objects.create(
            name="Gumboots", brand=brand, category=self.boots,
            description="x", price=1000,
        )
        self.in_ankle = Product.objects.create(
            name="Ankle Boot", brand=brand, category=self.ankle,
            description="x", price=1000,
        )
        self.sandal = Product.objects.create(
            name="Fisherman Sandal", brand=brand, category=self.sandals,
            description="x", price=800,
        )

    def test_parent_category_includes_descendants(self):
        # Choosing "Boots" also shows products filed under "Ankle Boots".
        r = self.client.get(reverse("store:product_list"), {"category": "boots"})
        self.assertEqual(r.context["total_results"], 2)

    def test_child_category_shows_only_its_own(self):
        r = self.client.get(reverse("store:product_list"), {"category": "ankle-boots"})
        self.assertEqual(r.context["total_results"], 1)
        self.assertEqual(r.context["products"][0], self.in_ankle)

    def test_audience_and_category_combine(self):
        Product.objects.filter(pk=self.in_ankle.pk).update(audience="women")
        Product.objects.filter(pk=self.in_boots.pk).update(audience="men")
        r = self.client.get(
            reverse("store:product_list"),
            {"category": "boots", "audience": "women"},
        )
        self.assertEqual(r.context["total_results"], 1)
        self.assertEqual(r.context["products"][0], self.in_ankle)

    def test_unknown_category_returns_nothing(self):
        r = self.client.get(reverse("store:product_list"), {"category": "spaceships"})
        self.assertEqual(r.context["total_results"], 0)


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
        self.assertContains(r, "Foot length (cm)")  # adult size guide
        self.assertContains(r, "Add to cart")

    def test_size_picker_is_an_accessible_dialog(self):
        r = self.client.get(self.product.get_absolute_url())
        # The size list lives in a dialog with a visible close button.
        self.assertContains(r, 'id="sizePicker"')
        self.assertContains(r, 'role="dialog"')
        self.assertContains(r, 'aria-modal="true"')
        self.assertContains(r, 'aria-controls="sizePicker"')
        self.assertContains(r, 'aria-expanded="false"')
        self.assertContains(r, 'aria-label="Close size selector"')
        # The trigger shows the chosen size after picking one.
        self.assertContains(r, "Select size")

    def test_size_guide_matches_the_size_system(self):
        # Kids products show the kids chart (UK 1–13 + age), not the adult one.
        kids = make_product(name="Kids Trainer", audience="kids", size_system="kids")
        ProductSize.objects.create(product=kids, size="10", stock=4)
        r = self.client.get(kids.get_absolute_url())
        self.assertContains(r, "Kids size guide")
        self.assertContains(r, "Approx. age")

        # S/M/L products (slippers) show the label chart.
        slippers = make_product(name="Solar Slide", size_system="label")
        ProductSize.objects.create(product=slippers, size="M", stock=4)
        r = self.client.get(slippers.get_absolute_url())
        self.assertContains(r, "Size guide (S / M / L)")
        self.assertContains(r, ">M<")

    def test_size_prefix_used_in_the_ui(self):
        kids = make_product(name="Kids Trainer", audience="kids", size_system="kids")
        r = self.client.get(kids.get_absolute_url())
        self.assertContains(r, "(Kids)")

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

    def test_audience_cards_with_counts(self):
        make_product(name="Men Pair", audience="men")
        make_product(name="Women Pair", audience="women", brand_name="Bata")
        r = self.client.get(reverse("store:home"))
        self.assertContains(r, "Shop by audience")
        self.assertContains(r, "1 item")   # one product per audience

    def test_category_cards_count_descendants(self):
        boots = Category.objects.create(name="Boots", slug="boots")
        ankle = Category.objects.create(name="Ankle Boots", slug="ankle-boots", parent=boots)
        make_product(name="Ankle Boot", category=ankle, audience="men")
        make_product(name="Chelsea Boot", category=ankle, audience="women", brand_name="Clarks")
        r = self.client.get(reverse("store:home"))
        # Only the "Boots" card can show 2 — it counts its child's products.
        self.assertContains(r, "2 items")


class NavbarTests(TestCase):
    def test_mega_menu_lists_all_types_with_sub_types(self):
        boots = Category.objects.create(name="Boots", slug="boots", icon="🥾")
        Category.objects.create(name="Chelsea Boots", slug="chelsea-boots", parent=boots)
        r = self.client.get(reverse("store:home"))
        self.assertContains(r, 'id="megaMenu"')
        self.assertContains(r, "Boots")
        self.assertContains(r, "Chelsea Boots")

    def test_nav_has_new_in_audiences_and_sale(self):
        r = self.client.get(reverse("store:home"))
        self.assertContains(r, "?sort=newest")   # New In
        self.assertContains(r, "?audience=men")
        self.assertContains(r, "?audience=women")
        self.assertContains(r, "?audience=kids")
        self.assertContains(r, "?sale=1")        # Sale
        self.assertContains(r, "StepUp")         # brand name


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
