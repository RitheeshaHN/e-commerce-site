"""
Management command:  python manage.py seed_store

Loads demo data for local development:
  * Categories (Men / Women / Kids  +  Running / Casual / Formal / Sports)
  * Brands (Nike, Adidas, Puma, Reebok, Clarks, Bata)
  * 15 products with sizes/stock, colours, discounts and reviews
  * Placeholder images generated locally with Pillow (no downloads needed)

Idempotent: running it twice will not duplicate anything (get-or-create).
Pass --wipe to wipe the catalog first and start fresh.
"""
import random
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from accounts.models import User
from store.models import Brand, Category, Product, ProductImage, ProductSize, Review

# (name, kind, parent_name_or_None)
CATEGORIES = [
    ("Men", "audience", None),
    ("Women", "audience", None),
    ("Kids", "audience", None),
    ("Running", "type", None),
    ("Casual", "type", None),
    ("Formal", "type", None),
    ("Sports", "type", None),
    # Sub-categories so filters have something to drill into
    ("Running", "type", "Men"),
    ("Casual", "type", "Men"),
    ("Formal", "type", "Men"),
    ("Running", "type", "Women"),
    ("Casual", "type", "Women"),
    ("Sports", "type", "Women"),
    ("Running", "type", "Kids"),
    ("Casual", "type", "Kids"),
    ("Sports", "type", "Kids"),
]

BRANDS = ["Nike", "Adidas", "Puma", "Reebok", "Clarks", "Bata"]

# ---------------------------------------------------------------- products ---
# name, brand, audience, type, price, discount, colour, colours, material,
# sizes {size: stock}, featured, popularity, description
PRODUCTS = [
    (
        "Air Zoom Pegasus 41", "Nike", "Men", "Running", 12995, 10495,
        "Black/Red", "Black,White,Blue", "Engineered mesh + ZoomX foam",
        {"6": 8, "7": 12, "8": 15, "9": 10, "10": 6, "11": 3}, True, 98,
        "The everyday running shoe trusted by millions. Responsive ZoomX foam "
        "returns energy with every stride, while the engineered mesh upper "
        "keeps your feet cool on long runs.",
    ),
    (
        "Ultraboost Light", "Adidas", "Men", "Running", 16999, 13999,
        "Cloud White", "White,Black,Grey", "Primeknit upper + BOOST midsole",
        {"7": 6, "8": 9, "9": 11, "10": 7, "11": 4, "12": 2}, True, 94,
        "Lighter BOOST midsole with the same incredible energy return. "
        "Primeknit upper adapts to your foot like a sock for a locked-in feel.",
    ),
    (
        "RS-X Efekt Retro", "Puma", "Men", "Casual", 8999, 6499,
        "Grey Blue", "Grey,Blue,Red", "Mesh + synthetic leather overlays",
        {"6": 5, "7": 8, "8": 10, "9": 9, "10": 5, "11": 2}, False, 81,
        "Chunky retro silhouette with modern cushioning. A streetwear staple "
        "that pairs as easily with jeans as it does with joggers.",
    ),
    (
        "Classic Leather Legacy", "Reebok", "Men", "Casual", 7499, 5999,
        "White", "White,Black,Navy", "Leather upper + die-cut EVA sockliner",
        {"6": 7, "7": 9, "8": 12, "9": 8, "10": 6, "11": 3}, False, 76,
        "An icon since 1983. Soft leather, clean lines and all-day comfort "
        "that works from the office to the weekend.",
    ),
    (
        "Carrera Formal Derby", "Clarks", "Men", "Formal", 11995, 9595,
        "Dark Brown", "Brown,Black", "Full-grain leather + cushioned footbed",
        {"6": 4, "7": 7, "8": 9, "9": 8, "10": 5, "11": 3}, False, 64,
        "Hand-finished leather derby with a cushioned OrthoLite footbed. "
        "Boardroom-ready without the break-in pain.",
    ),
    (
        "Sporto Smart Oxford", "Bata", "Men", "Formal", 2999, 2399,
        "Black", "Black,Brown", "PU leather + anti-skid sole",
        {"6": 10, "7": 14, "8": 16, "9": 12, "10": 8, "11": 4}, False, 70,
        "Affordable formal shoes with a lightweight, anti-skid sole. "
        "perfect for daily office wear and long commutes.",
    ),
    (
        "Pegasus Trail 4 GTX", "Nike", "Men", "Sports", 14995, 11995,
        "Volt", "Volt,Black", "GORE-TEX + trail-tuned rubber outsole",
        {"7": 5, "8": 7, "9": 8, "10": 6, "11": 3}, True, 88,
        "Waterproof trail runner with aggressive lugs for grip on wet rock. "
        "GORE-TEX bootie keeps rain out without cooking your feet.",
    ),
    (
        "Cloudflow Runner", "Adidas", "Women", "Running", 11995, 9595,
        "Lilac", "Lilac,Pink,White", "Lightweight mesh + Lightstrike foam",
        {"5": 9, "6": 12, "7": 11, "8": 8, "9": 5, "10": 3}, True, 92,
        "A lightweight tempo shoe with a snappy Lightstrike midsole. "
        "built for speed days, comfortable enough for easy miles.",
    ),
    (
        "Fresh Foam X 1080v13", "Reebok", "Women", "Running", 13999, 11199,
        "Black Pink", "Black,Pink,Blue", "Hypoknit upper + Fresh Foam X",
        {"5": 6, "6": 9, "7": 10, "8": 7, "9": 4, "10": 2}, False, 85,
        "Plush Fresh Foam X midsole delivers the softest, most cushioned "
        "ride in the lineup, ideal for recovery runs and all-day wear.",
    ),
    (
        "Cali Star Sneaker", "Puma", "Women", "Casual", 7999, 5999,
        "White Rose", "White,Pink,Grey", "Leather upper + SoftFoam comfort",
        {"5": 8, "6": 11, "7": 10, "8": 7, "9": 4, "10": 2}, True, 90,
        "A clean low-top with a platform sole and SoftFoam sockliner. "
        "The easiest yes in any wardrobe.",
    ),
    (
        "Freya Ballerina Flat", "Bata", "Women", "Casual", 2499, 1999,
        "Maroon", "Maroon,Black,Beige", "Suede upper + flexible TPR sole",
        {"5": 12, "6": 15, "7": 13, "8": 9, "9": 5}, False, 73,
        "Feather-light ballerinas with a flexible sole that folds with your "
        "foot. Dress them up or throw them on with denims.",
    ),
    (
        "Court Vision Alta", "Nike", "Women", "Sports", 9995, 7995,
        "Sail", "Sail,Black,Red", "Leather + foam midsole",
        {"5": 7, "6": 10, "7": 9, "8": 6, "9": 3}, False, 79,
        "Elevated court-inspired trainer with a padded collar. Cushioned "
        "and stable for gym sessions and everyday movement.",
    ),
    (
        "Lightster K Kids", "Adidas", "Kids", "Running", 5999, 4499,
        "Blue", "Blue,Green,Pink", "Mesh upper + lightweight EVA",
        {"9": 14, "10": 16, "11": 12, "12": 10, "13": 6}, True, 87,
        "Feather-light trainers for kids who never stop moving. Breathable "
        "mesh and a grippy outsole for playground adventures.",
    ),
    (
        "Validate K Sneaker", "Puma", "Kids", "Casual", 4499, 3599,
        "Grey Lime", "Grey,Lime,Blue", "Synthetic upper + rubber outsole",
        {"9": 11, "10": 13, "11": 12, "12": 8, "13": 5}, False, 68,
        "Durable everyday sneakers that survive the playground and still "
        "look sharp at family dinners. Hook-and-loop closure.",
    ),
    (
        "Speedop K Trainer", "Reebok", "Kids", "Sports", 5499, 4199,
        "Purple", "Purple,Pink,White", "Mesh upper + non-marking outsole",
        {"9": 9, "10": 12, "11": 10, "12": 7, "13": 4}, False, 71,
        "Court-ready trainers with lateral support for little athletes, "
        "plus a non-marking sole that's safe for indoor gyms.",
    ),
]

# Sample reviews keyed by product name.
REVIEWS = [
    ("Air Zoom Pegasus 41", 5, "Best daily runner", "Took these on a half marathon straight out of the box. No blisters, great bounce. True to size."),
    ("Air Zoom Pegasus 41", 4, "Solid, slightly narrow", "Love the cushioning. If you have wide feet, go half a size up."),
    ("Ultraboost Light", 5, "Worth every rupee", "Like walking on clouds. The Primeknit hugs the foot perfectly."),
    ("RS-X Efekt Retro", 4, "Very comfortable", "Great looks and comfort. Slightly heavy for long walks."),
    ("Carrera Formal Derby", 5, "Office favourite", "Soft leather, no break-in period. Received compliments on day one."),
    ("Cloudflow Runner", 5, "Fast and light", "Perfect tempo shoe. Snappy toe-off and the fit is spot on."),
    ("Cali Star Sneaker", 5, "So cute!", "Goes with everything and the platform adds a little height. Sized up for comfort."),
    ("Freya Ballerina Flat", 4, "Comfy flats", "Flexible sole and no pinching. Maroon colour is gorgeous."),
    ("Lightster K Kids", 5, "Kids love them", "Lightweight and easy to wear. My son refuses to take them off."),
    ("Classic Leather Legacy", 4, "Retro done right", "Clean look, soft leather. Runs a touch large, I sized down half."),
    ("Fresh Foam X 1080v13", 5, "Cloud-like", "The softest shoe I have owned. Great for recovery runs."),
    ("Sporto Smart Oxford", 4, "Great value", "For the price these are unbeatable. Survived a full monsoon season."),
]

# UK size  stock range used when a product doesn't specify sizes.
DEFAULT_SIZES = {"5", "6", "7", "8", "9", "10", "11"}


def make_placeholder_image(path: Path, label: str, colour: str, index: int) -> None:
    """
    Draw a simple, good-looking placeholder PNG with Pillow.

    A gradient background + a shoe glyph + the product name. Keeps the
    project fully self-contained (no external image downloads).
    """
    from PIL import Image, ImageDraw, ImageFont

    w, h = 800, 600

    def hex_to_rgb(c: str):
        c = c.lstrip("#")
        return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))

    base = hex_to_rgb(colour)

    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):  # vertical gradient
        t = y / h
        for x in range(w):
            s = 0.12 * (x / w)  # slight horizontal lightening too
            px[x, y] = (
                min(255, int(base[0] * (1 - t) + 250 * t + 8 * s)),
                min(255, int(base[1] * (1 - t) + 250 * t + 8 * s)),
                min(255, int(base[2] * (1 - t) + 250 * t + 8 * s)),
            )

    draw = ImageDraw.Draw(img)

    # A simple side-profile "shoe" made of shapes (readable at any size).
    sole_y = int(h * 0.66)
    draw.rounded_rectangle(
        [w * 0.18, sole_y, w * 0.82, sole_y + h * 0.07],
        radius=18, fill=(35, 38, 45),
    )
    # upper
    draw.polygon(
        [
            (w * 0.22, sole_y),
            (w * 0.26, sole_y - h * 0.16),
            (w * 0.42, sole_y - h * 0.20),
            (w * 0.55, sole_y - h * 0.13),
            (w * 0.72, sole_y - h * 0.05),
            (w * 0.78, sole_y),
        ],
        fill=(255, 255, 255),
        outline=(35, 38, 45),
        width=4,
    )
    # swoosh-ish stripe
    draw.arc(
        [w * 0.30, sole_y - h * 0.13, w * 0.70, sole_y + h * 0.02],
        start=200, end=340, fill=base, width=10,
    )
    # laces
    for i in range(3):
        lx = w * (0.34 + i * 0.07)
        ly = sole_y - h * (0.15 - i * 0.018)
        draw.line([lx, ly, lx + w * 0.05, ly + h * 0.05], fill=(35, 38, 45), width=5)

    # Label
    try:
        font = ImageFont.truetype("arial.ttf", 34)
        small = ImageFont.truetype("arial.ttf", 22)
    except OSError:  # pragma: no cover - font missing on this system
        font = ImageFont.load_default()
        small = font

    draw.text((w * 0.5, h * 0.14), label, fill=(35, 38, 45), font=font, anchor="mm")
    draw.text((w * 0.5, h * 0.86), f"STEPUP view {index}", fill=(90, 96, 110), font=small, anchor="mm")

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)


class Command(BaseCommand):
    help = "Load sample categories, brands and 15 shoe products with images."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wipe", action="store_true",
            help="Delete existing catalog data first (keeps users/orders).",
        )

    def handle(self, *args, **options):
        random.seed(42)  # deterministic reviews/popularity

        if options["wipe"]:
            self.stdout.write("Wiping catalog data")
            Review.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            Brand.objects.all().delete()

        # ------------------------------------------------ categories ---
        category_map = {}
        for name, kind, parent_name in CATEGORIES:
            parent = category_map.get(parent_name) if parent_name else None
            slug = slugify(f"{parent_name}-{name}" if parent_name else name)
            cat, _ = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "kind": kind, "parent": parent},
            )
            category_map[f"{parent_name}-{name}" if parent_name else name] = cat
        self.stdout.write(f"  [ok] {Category.objects.count()} categories")

        # --------------------------------------------------- brands ---
        brand_map = {}
        for name in BRANDS:
            brand, _ = Brand.objects.get_or_create(name=name)
            brand_map[name] = brand
        self.stdout.write(f"  [ok] {Brand.objects.count()} brands")

        # -------------------------------------------------- products ---
        media_root = Path(settings.MEDIA_ROOT)
        created = 0

        # Colour palettes used for the placeholder gradients.
        palette = {
            "Black": "#2b2f36", "Red": "#d9483b", "White": "#eef1f6",
            "Blue": "#2f6fed", "Grey": "#8b93a3", "Navy": "#22315b",
            "Brown": "#7a4b2a", "Green": "#2f9e63", "Pink": "#e86fa4",
            "Purple": "#7a4fd6", "Maroon": "#8a2f45", "Lilac": "#a58bf0",
            "Lime": "#9ccb3b", "Volt": "#c8e63c", "Sail": "#efe9dc",
            "Beige": "#d9c7a7", "Cloud": "#e9edf4", "Black/Red": "#2b2f36",
            "Dark Brown": "#5a3520", "Cloud White": "#e9edf4",
            "Black Pink": "#2b2f36", "White Rose": "#f0dfe6",
            "Grey Blue": "#6c7a94", "Grey Lime": "#8b93a3",
        }

        for (
            name, brand_name, audience, type_name, price, discount,
            colour, colours, material, sizes, featured, popularity, description,
        ) in PRODUCTS:
            brand = brand_map[brand_name]
            category = category_map.get(f"{audience}-{type_name}") or category_map[
                type_name  # fall back to the top-level type (Running/Casual/...)
            ]

            product, was_created = Product.objects.get_or_create(
                brand=brand,
                name=name,
                defaults={
                    "category": category,
                    "description": description,
                    "material": material,
                    "price": price,
                    "discount_price": discount,
                    "colour": colour.split("/")[0],
                    "colours": colours,
                    "is_featured": featured,
                    "popularity": popularity,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1

            # ------------------------------------------------ sizes ---
            for size_label, stock in sizes.items():
                ProductSize.objects.get_or_create(
                    product=product, size=size_label,
                    defaults={"stock": stock},
                )

            # ----------------------------------------------- images ---
            if not product.images.exists():
                colour_hex = palette.get(colour, "#5b6fae")
                for idx in (1, 2, 3):
                    fname = f"{slugify(brand_name)}-{slugify(name)}-{idx}.png"
                    rel = Path("products") / fname
                    make_placeholder_image(
                        media_root / rel, f"{brand_name} {name}", colour_hex, idx
                    )
                    ProductImage.objects.create(
                        product=product,
                        image=f"products/{fname}",
                        alt_text=f"{brand_name} {name} view {idx}",
                        is_primary=(idx == 1),
                        position=idx,
                    )

        self.stdout.write(
            f"  [ok] {Product.objects.count()} products ({created} new)"
        )

        # --------------------------------------------------- reviews ---
        demo_user, created_u = User.objects.get_or_create(
            username="demo",
            defaults={
                "email": "demo@stepupshoes.example",
                "first_name": "Demo",
                "last_name": "Shopper",
            },
        )
        if created_u:
            demo_user.set_password("demo1234")
            demo_user.save()

        # A second reviewer so product averages aren't all one vote.
        demo_user2, created_u2 = User.objects.get_or_create(
            username="aria",
            defaults={
                "email": "aria@stepupshoes.example",
                "first_name": "Aria",
                "last_name": "Menon",
            },
        )
        if created_u2:
            demo_user2.set_password("demo1234")
            demo_user2.save()

        for product_name, rating, title, comment in REVIEWS:
            product = Product.objects.filter(name=product_name).first()
            if not product:
                continue
            user = demo_user if random.random() < 0.6 else demo_user2
            Review.objects.get_or_create(
                product=product, user=user,
                defaults={"rating": rating, "title": title, "comment": comment},
            )

        self.stdout.write(f"  [ok] {Review.objects.count()} reviews")
        self.stdout.write(self.style.SUCCESS("\nDone! Catalog is ready."))
        self.stdout.write("  Demo login -> username: demo  password: demo1234")

