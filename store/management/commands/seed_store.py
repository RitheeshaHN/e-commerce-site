"""
Management command:  python manage.py seed_store

Loads demo data for local development:
  * 11 top-level footwear types (+ sub-types) for the navbar mega-menu
    e.g. Boots -> Ankle / Chelsea / Trekking, Kids' Footwear -> Infant/Boys/Girls
  * Brands (Nike, Adidas, Puma, Reebok, Clarks, Bata, Woodland, Metro)
  * 27 products covering every type, audience (Men/Women/Kids) and size
    system (adult UK/India, kids UK, S/M/L for slippers & flip-flops)
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

# ---------------------------------------------------------------- catalog ---
# (top-level name, icon, [(sub name, icon), ...])
# The top-level entries are what the navbar mega-menu and the home page show.
CATEGORY_TREE = [
    ("Sneakers, Running & Sports", "👟", [("Sneakers", "👟"), ("Running", "🏃"), ("Sports", "⚽")]),
    ("Formal, Office & Loafers", "👞", [("Formal", "👔"), ("Office", "💼"), ("Loafers", "🥿")]),
    ("Casual & Canvas", "🎨", [("Casual", "👟"), ("Canvas", "🎨")]),
    ("Sandals & Floaters", "🩴", [("Sandals", "🩴"), ("Floaters", "👡")]),
    ("Slippers & Flip-Flops", "🩴", [("Slippers", "🥿"), ("Flip-Flops", "🩴")]),
    ("Boots", "🥾", [("Ankle Boots", "🥾"), ("Chelsea Boots", "👢"), ("Trekking Boots", "🥾")]),
    ("Heels, Flats, Wedges & Bellies", "👠", [("Heels", "👠"), ("Flats", "🥿"), ("Wedges", "👡"), ("Bellies", "🥿")]),
    ("School Footwear", "🎒", []),
    ("Kids' Footwear", "🧒", [("Infant", "👶"), ("Boys", "🧒"), ("Girls", "👧")]),
    ("Safety & Work", "🦺", [("Safety", "🦺"), ("Work", "👷")]),
    ("Rain & Monsoon", "🌧️", [("Clogs", "🩴"), ("Gumboots", "🥾")]),
]

BRANDS = ["Nike", "Adidas", "Puma", "Reebok", "Clarks", "Bata", "Woodland", "Metro"]

# ---------------------------------------------------------------- products ---
# name, brand, audience, category, size_system, price, discount, colour,
# colours, material, sizes {size: stock}, featured, popularity, description
#
# size_system drives both the size list and the size guide chart:
#   "adult" -> UK/India 3–12, "kids" -> kids UK 1–13, "label" -> S/M/L
PRODUCTS = (
    # ---------------------------------------- Sneakers, Running & Sports ---
    (
        "Air Zoom Pegasus 41", "Nike", "men", "Running", "adult",
        12995, 10495, "Black/Red", "Black,White,Blue", "Engineered mesh + ZoomX foam",
        {"6": 8, "7": 12, "8": 15, "9": 10, "10": 6, "11": 3}, True, 98,
        "The everyday running pair trusted by millions. Responsive ZoomX foam "
        "returns energy with every stride, while the engineered mesh upper "
        "keeps your feet cool on long runs.",
    ),
    (
        "Ultraboost Light", "Adidas", "men", "Sneakers", "adult",
        16999, 13999, "Cloud White", "White,Black,Grey", "Primeknit upper + BOOST midsole",
        {"7": 6, "8": 9, "9": 11, "10": 7, "11": 4, "12": 2}, True, 94,
        "Lighter BOOST midsole with the same incredible energy return. "
        "Primeknit upper adapts to your foot like a sock for a locked-in feel.",
    ),
    (
        "Pegasus Trail 4 GTX", "Nike", "men", "Sports", "adult",
        14995, 11995, "Volt", "Volt,Black", "GORE-TEX + trail-tuned rubber outsole",
        {"7": 5, "8": 7, "9": 8, "10": 6, "11": 3}, True, 88,
        "Waterproof trail runner with aggressive lugs for grip on wet rock. "
        "The GORE-TEX bootie keeps rain out without cooking your feet.",
    ),
    (
        "Cali Star Sneaker", "Puma", "women", "Sneakers", "adult",
        7999, 5999, "White Rose", "White,Pink,Grey", "Leather upper + SoftFoam comfort",
        {"4": 8, "5": 11, "6": 10, "7": 7, "8": 4}, True, 90,
        "A clean low-top with a platform sole and SoftFoam sockliner. "
        "The easiest yes in any wardrobe.",
    ),
    (
        "Cloudflow Runner", "Adidas", "women", "Running", "adult",
        11995, 9595, "Lilac", "Lilac,Pink,White", "Lightweight mesh + Lightstrike foam",
        {"4": 9, "5": 12, "6": 11, "7": 8, "8": 5}, True, 92,
        "A lightweight tempo pair with a snappy Lightstrike midsole — "
        "built for speed days and comfortable enough for easy miles.",
    ),
    (
        "Court Vision Alta", "Nike", "women", "Sports", "adult",
        9995, 7995, "Sail", "Sail,Black,Red", "Leather + foam midsole",
        {"4": 7, "5": 10, "6": 9, "7": 6, "8": 3}, False, 79,
        "Elevated court-inspired trainer with a padded collar. Cushioned "
        "and stable for gym sessions and everyday movement.",
    ),
    # ---------------------------------------- Formal, Office & Loafers ---
    (
        "Carrera Formal Derby", "Clarks", "men", "Formal", "adult",
        11995, 9595, "Dark Brown", "Brown,Black", "Full-grain leather + cushioned footbed",
        {"6": 4, "7": 7, "8": 9, "9": 8, "10": 5, "11": 3}, False, 64,
        "Hand-finished leather derby with a cushioned OrthoLite footbed. "
        "Boardroom-ready without the break-in pain.",
    ),
    (
        "Sporto Smart Oxford", "Bata", "men", "Office", "adult",
        2999, 2399, "Black", "Black,Brown", "PU leather + anti-skid sole",
        {"6": 10, "7": 14, "8": 16, "9": 12, "10": 8, "11": 4}, False, 70,
        "Affordable formal footwear with a lightweight, anti-skid sole — "
        "perfect for daily office wear and long commutes.",
    ),
    (
        "Lane Penny Loafer", "Metro", "men", "Loafers", "adult",
        5499, 4399, "Tan", "Tan,Black", "Suede upper + cushioned EVA footbed",
        {"6": 6, "7": 8, "8": 10, "9": 9, "10": 6, "11": 3}, False, 69,
        "Slip-on penny loafers that go from desk to dinner. Soft suede, "
        "no laces and a footbed that stays comfortable all day.",
    ),
    # ------------------------------------------- Casual & Canvas ---
    (
        "RS-X Efekt Retro", "Puma", "men", "Casual", "adult",
        8999, 6499, "Grey Blue", "Grey,Blue,Red", "Mesh + synthetic leather overlays",
        {"6": 5, "7": 8, "8": 10, "9": 9, "10": 5, "11": 2}, False, 81,
        "Chunky retro silhouette with modern cushioning. A streetwear staple "
        "that pairs as easily with jeans as it does with joggers.",
    ),
    (
        "Canvas Court Low", "Reebok", "men", "Canvas", "adult",
        4999, 3999, "White", "White,Navy,Black", "Washed canvas + vulcanised rubber sole",
        {"6": 7, "7": 9, "8": 12, "9": 8, "10": 6, "11": 3}, False, 76,
        "Washed canvas uppers on a vulcanised rubber sole. An icon since "
        "1983 — soft, clean-lined and effortless with denims.",
    ),
    # --------------------------------------- Sandals / Slippers / Flip-Flops ---
    (
        "Drift Fisherman Sandal", "Bata", "men", "Sandals", "adult",
        2799, 2199, "Brown", "Brown,Black", "Leather-touch straps + EVA footbed",
        {"6": 9, "7": 12, "8": 14, "9": 11, "10": 8, "11": 5}, False, 72,
        "Closed-toe fisherman sandals with quick-dry straps and a squishy "
        "EVA footbed — built for humid days and long walks.",
    ),
    (
        "Solar Slide Slipper", "Bata", "women", "Slippers", "label",
        2499, 1999, "Maroon", "Maroon,Black,Beige", "Contoured memory-foam footbed",
        {"S": 14, "M": 18, "L": 12}, True, 73,
        "Cloud-soft slides with a memory-foam footbed that keeps its shape. "
        "The slipper you will wear from the doorstep to the grocery store.",
    ),
    (
        "Tide Flip-Flop", "Puma", "men", "Flip-Flops", "label",
        1999, 1499, "Black", "Black,Grey,Blue", "Water-friendly EVA + textured strap",
        {"S": 12, "M": 16, "L": 10}, False, 67,
        "Water-friendly flip-flops with a grippy textured strap and a "
        "footbed that dries in minutes. Beach-to-street ready.",
    ),
    # -------------------------------------------------------- Boots ---
    (
        "Ridge Trek Boot", "Woodland", "men", "Trekking Boots", "adult",
        8999, 7199, "Dark Brown", "Brown,Grey", "Nubuck leather + high-traction outsole",
        {"7": 5, "8": 7, "9": 8, "10": 6, "11": 3}, True, 83,
        "Nubuck trekking boots with a high-traction outsole and a padded "
        "collar. Grip for wet rock, comfort for the long walk back.",
    ),
    (
        "Chisel Chelsea Boot", "Clarks", "men", "Chelsea Boots", "adult",
        12999, 10399, "Black", "Black,Brown", "Full-grain leather + elastic gusset",
        {"6": 4, "7": 7, "8": 9, "9": 8, "10": 5, "11": 3}, False, 74,
        "A sleek chelsea boot with elastic gussets and a leather heel. "
        "Dresses up denim instantly and never looks out of place.",
    ),
    (
        "Trailhead Ankle Boot", "Metro", "women", "Ankle Boots", "adult",
        7999, 6399, "Tan", "Tan,Black", "Leather upper + side zip",
        {"4": 5, "5": 8, "6": 10, "7": 8, "8": 5}, False, 71,
        "Everyday ankle boots with a side zip and a low block heel. "
        "Sturdy enough for cobbles, soft enough for all-day wear.",
    ),
    # -------------------------------------- Heels, Flats, Wedges & Bellies ---
    (
        "Grace Stiletto Heel", "Metro", "women", "Heels", "adult",
        5999, 4799, "Black", "Black,Nude,Red", "Suede upper + cushioned insole",
        {"3": 4, "4": 7, "5": 9, "6": 8, "7": 5}, False, 77,
        "A classic stiletto with a cushioned insole and an ankle strap "
        "that actually keeps you stable on the dance floor.",
    ),
    (
        "Freya Ballerina Flat", "Bata", "women", "Flats", "adult",
        2499, 1999, "Maroon", "Maroon,Black,Beige", "Suede upper + flexible TPR sole",
        {"3": 12, "4": 15, "5": 13, "6": 9, "7": 5}, False, 73,
        "Feather-light ballerinas with a flexible sole that folds with your "
        "foot. Dress them up or throw them on with denims.",
    ),
    (
        "Coastal Cork Wedge", "Metro", "women", "Wedges", "adult",
        4999, 3999, "Beige", "Beige,Black", "Cork wedge + jute wrap",
        {"3": 5, "4": 8, "5": 10, "6": 9, "7": 6}, False, 75,
        "Cork wedges with a jute-wrapped heel — the height of a heel with "
        "the balance of a flat. Summer dresses approve.",
    ),
    # ------------------------------------------------- Safety & Work ---
    (
        "SteelCore Safety Shoe", "Woodland", "men", "Safety", "adult",
        6999, 5599, "Black", "Black,Yellow", "Steel toe + anti-static, anti-skid sole",
        {"6": 6, "7": 9, "8": 11, "9": 10, "10": 7, "11": 4}, False, 61,
        "ISI-rated steel toe with a scuff cap and an anti-static, anti-skid "
        "sole. Site-ready comfort for twelve-hour shifts.",
    ),
    # -------------------------------------------- Rain & Monsoon ---
    (
        "RainGro Clog", "Bata", "men", "Clogs", "adult",
        2299, 1799, "Navy", "Navy,Black,Grey", "Water-resistant EVA + drainage ports",
        {"6": 10, "7": 13, "8": 15, "9": 12, "10": 8, "11": 5}, False, 66,
        "Water-resistant clogs with drainage ports and a grippy outsole. "
        "Monsoon mornings and quick errands, sorted.",
    ),
    (
        "Aqua Guard Gumboot", "Woodland", "men", "Gumboots", "adult",
        3499, 2799, "Black", "Black,Green", "PVC upper + cotton lining",
        {"6": 6, "7": 9, "8": 11, "9": 9, "10": 6, "11": 3}, False, 58,
        "Knee-high PVC gumboots with a cotton lining so your feet stay "
        "dry and sweat-free through the heaviest downpour.",
    ),
    # ------------------------------------------------ Kids' Footwear ---
    (
        "Little Runner Trainer", "Adidas", "kids", "Boys", "kids",
        5999, 4499, "Blue", "Blue,Green,Pink", "Mesh upper + lightweight EVA",
        {"9": 14, "10": 16, "11": 12, "12": 10, "13": 6}, True, 87,
        "Feather-light trainers for kids who never stop moving. Breathable "
        "mesh and a grippy outsole for playground adventures.",
    ),
    (
        "Tiny Steps First Walker", "Bata", "kids", "Infant", "kids",
        2499, 1999, "Pink", "Pink,Blue", "Soft textile + flexible rubber sole",
        {"3": 12, "4": 14, "5": 12, "6": 9}, False, 80,
        "First-walker footwear with a soft textile upper and a sole that "
        "flexes the way little feet do. Wide toe box, easy velcro.",
    ),
    (
        "Sparkle Mary Jane", "Metro", "kids", "Girls", "kids",
        3499, 2799, "Purple", "Purple,Pink,Black", "Patent upper + hook-and-loop strap",
        {"9": 9, "10": 12, "11": 10, "12": 7}, False, 68,
        "Sparkly mary janes with a hook-and-loop strap little hands can "
        "manage alone. Party-ready and washable.",
    ),
    (
        "StepWell School Trainer", "Bata", "kids", "School Footwear", "kids",
        2499, 1999, "Black", "Black,Brown", "PU leather + anti-skid sole",
        {"9": 16, "10": 18, "11": 15, "12": 12, "13": 8}, True, 85,
        "Durable school footwear with a reinforced toe, easy buckle strap "
        "and an anti-skid sole built for the playground after class.",
    ),
)

# Sample reviews keyed by product name.
REVIEWS = [
    ("Air Zoom Pegasus 41", 5, "Best daily runner", "Took these on a half marathon straight out of the box. No blisters, great bounce. True to size."),
    ("Air Zoom Pegasus 41", 4, "Solid, slightly narrow", "Love the cushioning. If you have wide feet, go half a size up."),
    ("Ultraboost Light", 5, "Worth every rupee", "Like walking on clouds. The Primeknit hugs the foot perfectly."),
    ("RS-X Efekt Retro", 4, "Very comfortable", "Great looks and comfort. Slightly heavy for long walks."),
    ("Carrera Formal Derby", 5, "Office favourite", "Soft leather, no break-in period. Received compliments on day one."),
    ("Cloudflow Runner", 5, "Fast and light", "Perfect tempo pair. Snappy toe-off and the fit is spot on."),
    ("Cali Star Sneaker", 5, "So cute!", "Goes with everything and the platform adds a little height. Sized up for comfort."),
    ("Freya Ballerina Flat", 4, "Comfy flats", "Flexible sole and no pinching. Maroon colour is gorgeous."),
    ("Little Runner Trainer", 5, "Kids love them", "Lightweight and easy to wear. My son refuses to take them off."),
    ("Canvas Court Low", 4, "Canvas done right", "Clean look, soft canvas. Runs a touch large, I sized down half."),
    ("Solar Slide Slipper", 5, "Never taking them off", "The memory foam is genuinely soft. Bought a second pair for home."),
    ("Sporto Smart Oxford", 4, "Great value", "For the price these are unbeatable. Survived a full monsoon season."),
    ("Ridge Trek Boot", 5, "Grip for days", "Took them to Coorg in the rain. Dry feet, no slips."),
    ("StepWell School Trainer", 4, "Survives the playground", "Third term and they still look presentable. Easy buckle is a lifesaver."),
]

# Fallback size list (adult UK) used when a product doesn't specify sizes.
DEFAULT_SIZES = {"5": 8, "6": 8, "7": 8, "8": 8, "9": 8, "10": 8, "11": 8}


def make_placeholder_image(path: Path, label: str, colour: str, index: int) -> None:
    """
    Draw a simple, good-looking placeholder PNG with Pillow.

    A gradient background + a trainer glyph + the product name. Keeps the
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

    # A simple side-profile "trainer" made of shapes (readable at any size).
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
    help = "Load sample categories, brands and 27 footwear products with images."

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
        # Top-level types first (they appear in the navbar mega-menu), then
        # their sub-types (Loafers, Chelsea Boots, Infant, ...).
        category_map: dict = {}
        for name, icon, subs in CATEGORY_TREE:
            cat, _ = Category.objects.get_or_create(
                slug=slugify(name),
                defaults={"name": name, "icon": icon, "parent": None},
            )
            category_map[name] = cat
            for sub_name, sub_icon in subs:
                sub, _ = Category.objects.get_or_create(
                    slug=slugify(sub_name),
                    defaults={
                        "name": sub_name,
                        "icon": sub_icon,
                        "parent": cat,
                    },
                )
                category_map[sub_name] = sub
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
            "Tan": "#c08a52", "Black/Yellow": "#2b2f36",
            "Black/Green": "#2b2f36", "Navy/Black": "#22315b",
        }

        for (
            name, brand_name, audience, category_name, size_system,
            price, discount, colour, colours, material, sizes,
            featured, popularity, description,
        ) in PRODUCTS:
            brand = brand_map[brand_name]
            category = category_map[category_name]

            product, was_created = Product.objects.get_or_create(
                brand=brand,
                name=name,
                defaults={
                    "category": category,
                    "audience": audience,
                    "size_system": size_system,
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
            # sort_order keeps the on-page order sane (6, 7, 8 ... not
            # "10, 11, 6"); the dict order is the display order.
            for position, (size_label, stock) in enumerate(
                (sizes or DEFAULT_SIZES).items()
            ):
                ProductSize.objects.get_or_create(
                    product=product, size=size_label,
                    defaults={"stock": stock, "sort_order": position},
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
                "email": "demo@stepupfootwear.example",
                "first_name": "Demo",
                "last_name": "Shopper",
            },
        )
        if created_u:
            demo_user.set_password("demo12345")
            demo_user.save()

        # A second reviewer so product averages aren't all one vote.
        demo_user2, created_u2 = User.objects.get_or_create(
            username="aria",
            defaults={
                "email": "aria@stepupfootwear.example",
                "first_name": "Aria",
                "last_name": "Menon",
            },
        )
        if created_u2:
            demo_user2.set_password("demo12345")
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
        self.stdout.write("  Demo login -> username: demo  password: demo12345")
