"""
Store app models: Category, Brand, Product, ProductImage, ProductSize, Review.

Design notes
------------
* Prices are stored in DecimalField (never float) so money maths is exact.
* Stock lives on ProductSize (one row per size) so we can disable an
  out-of-stock size on the product page while keeping other sizes selling.
* Sizing depends on the footwear type: adults use UK/India 5–12, kids use
  kids-UK 1–13 and slippers/flip-flops use S/M/L. Every product picks its
  own list of sizes (ProductSize rows) and the matching size guide chart
  (see ``store.size_guides``).
* Product has a denormalised ``stock`` property computed from its sizes --
  convenient for list pages and for `select_related`-free quick checks.
* All foreign keys use `on_delete` deliberately: catalog data is deleted
  with the shop, but review/order references behave predictably.
"""
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from .size_guides import SIZE_GUIDES


class Category(models.Model):
    """
    Hierarchical *footwear type* category (the store covers every kind of
    footwear, not just shoes).

    ``parent`` supports optional sub-categories, e.g.
        Boots -> Ankle Boots / Chelsea Boots / Trekking Boots
    A category with no parent is a top-level type shown in the navbar
    mega-menu and on the home page.

    The audience (Men / Women / Kids) is NOT a category -- it lives on
    ``Product.audience`` so a product has exactly one type + one audience.
    That keeps filters independent: "?category=boots&audience=women" just works.
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    # Emoji shown on the category cards / mega-menu (pure decoration).
    icon = models.CharField(max_length=8, blank=True, help_text="Emoji, e.g. 👟")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        """'Boots / Chelsea Boots' for breadcrumbs."""
        return f"{self.parent.name} / {self.name}" if self.parent else self.name

    def descendant_slugs(self) -> list:
        """
        This category's slug plus every descendant slug.

        Used by the filter: choosing "Boots" should also surface products
        filed under "Ankle Boots" / "Trekking Boots".
        """
        slugs = [self.slug]
        stack = [self]
        while stack:
            node = stack.pop()
            for child in node.children.all():
                slugs.append(child.slug)
                stack.append(child)
        return slugs


class Brand(models.Model):
    """Footwear brand (Nike, Adidas, Bata, ...)."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    logo = models.ImageField(upload_to="brands/", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductQuerySet(models.QuerySet):
    """Shared queryset helpers used by views and the seed command."""

    def active(self):
        return self.filter(is_active=True)

    def in_stock(self):
        return self.filter(sizes__stock__gt=0).distinct()

    def featured(self):
        return self.active().filter(is_featured=True)

    def on_sale(self):
        return self.active().filter(discount_price__isnull=False)


class Product(models.Model):
    """A single footwear product (shoe, sandal, slipper, boot, ...)."""

    # Who the product is for. Driven by the navbar links (Men / Women / Kids).
    AUDIENCE = (
        ("men", "Men"),
        ("women", "Women"),
        ("kids", "Kids"),
    )

    # Size systems differ by footwear type:
    #   adult -> UK/India 3-12 (numeric, incl. halves)
    #   kids  -> UK kids 1-13 with an age hint in the size guide
    #   label -> S / M / L for slippers, flip-flops and floaters
    SIZE_SYSTEMS = (
        ("adult", "Adult (UK/India 3–12)"),
        ("kids", "Kids (UK 1–13)"),
        ("label", "S / M / L"),
    )

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products")
    # The footwear *type* (Loafers, Ankle Boots, Slippers, ...). One level of
    # children is supported, so "Boots" also matches "Ankle Boots".
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    # Men / Women / Kids -- independent of the category.
    audience = models.CharField(
        max_length=10, choices=AUDIENCE, default="men", db_index=True
    )
    # Determines which size list and size-guide chart this product shows.
    size_system = models.CharField(
        max_length=10, choices=SIZE_SYSTEMS, default="adult"
    )
    description = models.TextField()
    material = models.CharField(max_length=200, blank=True, help_text="e.g. Mesh + Rubber sole")

    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    discount_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )

    colour = models.CharField(max_length=60, blank=True)
    colours = models.CharField(
        max_length=255, blank=True,
        help_text="Comma separated colour options, e.g. Black,White,Blue",
    )

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    # Simple popularity metric used by the "Popularity" sort option.
    popularity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "-created_at"]),
            models.Index(fields=["price"]),
            models.Index(fields=["brand", "category"]),
        ]

    def __str__(self) -> str:
        return f"{self.brand.name} {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.brand.name}-{self.name}")[:200]
            slug, n = base, 2
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("store:product_detail", args=[self.slug])

    # ------------------------------------------------------------ helpers ---
    @property
    def final_price(self) -> float:
        """Price the customer actually pays (discount if present)."""
        return float(self.discount_price if self.discount_price else self.price)

    @property
    def has_discount(self) -> bool:
        return self.discount_price is not None and self.discount_price < self.price

    @property
    def discount_percent(self) -> int:
        if not self.has_discount:
            return 0
        return round((1 - float(self.discount_price) / float(self.price)) * 100)

    @property
    def total_stock(self) -> int:
        """Total units across all sizes (DB query -- avoid in tight loops)."""
        return sum(s.stock for s in self.sizes.all())

    @property
    def in_stock(self) -> bool:
        return any(s.stock > 0 for s in self.sizes.all())

    @property
    def average_rating(self) -> float:
        reviews = list(self.reviews.all())
        if not reviews:
            return 0.0
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    @property
    def review_count(self) -> int:
        return self.reviews.count()

    @property
    def colour_list(self) -> list:
        return [c.strip() for c in self.colours.split(",") if c.strip()]

    @property
    def size_unit(self) -> str:
        """
        Name of the size system, used in labels: "Size (UK)" for adults,
        "Size (Kids)" for kids' UK sizes, plain "Size" for S/M/L products.
        """
        return {"adult": "UK", "kids": "Kids", "label": ""}[self.size_system]

    @property
    def size_prefix(self) -> str:
        """
        Label shown in front of a size in the UI.

        Adults -> "UK 9", kids -> "Kids 10", S/M/L products (slippers,
        flip-flops) -> just "M".
        """
        unit = self.size_unit
        return f"{unit} " if unit else ""

    @property
    def audience_label(self) -> str:
        return dict(self.AUDIENCE).get(self.audience, "")

    @property
    def size_guide(self) -> dict:
        """The size-guide chart matching this product's size system."""
        return SIZE_GUIDES[self.size_system]


class ProductImage(models.Model):
    """Multiple gallery images per product (first image = primary)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/")
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-is_primary", "position", "id"]

    def __str__(self) -> str:
        return f"Image for {self.product.name}"


class ProductSize(models.Model):
    """
    Stock per size for a product (the size selector on the detail page).

    ``size`` is a CharField so every sizing system fits in one field:
      * adults   -> "6", "8.5", "12"  (UK/India)
      * kids     -> "4", "10", "13"   (kids UK)
      * label    -> "S", "M", "L"     (slippers / flip-flops)
    ``sort_order`` lets each product control the display order, so sizes
    render 5, 6, 7 ... 12 instead of lexicographic "10, 11, 6, 7".
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="sizes")
    size = models.CharField(max_length=12)
    stock = models.PositiveIntegerField(default=0)
    # Display order within the product (0, 1, 2, ... left to right).
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        unique_together = ("product", "size")
        constraints = [
            models.CheckConstraint(
                check=models.Q(stock__gte=0), name="size_stock_non_negative"
            )
        ]

    def __str__(self) -> str:
        return f"{self.product.name} {self.product.size_prefix}{self.size} ({self.stock})"


class Review(models.Model):
    """Customer review + star rating (1-5) shown on the product page."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=150, blank=True)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("product", "user")  # one review per user per product

    def __str__(self) -> str:
        return f"{self.user} - {self.product} ({self.rating}★)"
