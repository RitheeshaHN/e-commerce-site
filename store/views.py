"""
Store app views: home, product list (filters/search/sort/pagination),
product detail (gallery, sizes, reviews, related), and review posting.
"""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Case, Count, DecimalField, F, OrderBy, Q, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ReviewForm
from .models import Brand, Category, Product


# ---------------------------------------------------------------- helpers ---
def _filtered_products(request):
    """
    Build the queryset shared by the product list page.

    Reads GET params: q, category, audience, brand, min_price, max_price,
    size, sale, sort. Returns (queryset, sort).
    """
    qs = Product.objects.active().select_related("brand", "category").prefetch_related(
        "images", "sizes"
    )

    filters = Q()

    # ---- text search (matches name, brand or description) --------------
    q = request.GET.get("q", "").strip()
    if q:
        filters &= Q(name__icontains=q) | Q(brand__name__icontains=q) | Q(
            description__icontains=q
        )

    # ---- category filter (slug; matches the category or a descendant) --
    # Choosing "Boots" must also surface products filed under
    # "Ankle Boots" / "Trekking Boots".
    category_slug = request.GET.get("category", "").strip()
    if category_slug:
        cat = Category.objects.filter(slug=category_slug).first()
        if cat:
            filters &= Q(category__slug__in=cat.descendant_slugs())
        else:
            # Unknown slug (typo / stale link) -> show the empty state
            # instead of silently ignoring the filter.
            filters &= Q(pk__in=[])

    # ---- audience filter (men / women / kids, from the navbar) ----------
    audience = request.GET.get("audience", "").strip()
    if audience in dict(Product.AUDIENCE):
        filters &= Q(audience=audience)

    # ---- sale filter (?sale=1 shows only discounted products) -----------
    if request.GET.get("sale") in ("1", "true", "yes"):
        filters &= Q(discount_price__isnull=False) & Q(discount_price__lt=F("price"))

    # ---- brand filter (supports multiple: ?brand=nike&brand=adidas) ----
    brands = request.GET.getlist("brand")
    if brands:
        filters &= Q(brand__slug__in=brands)

    # ---- price range ---------------------------------------------------
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()
    if min_price:
        try:
            filters &= Q(discount_price__gte=float(min_price)) | Q(
                discount_price__isnull=True, price__gte=float(min_price)
            )
        except ValueError:
            pass
    if max_price:
        try:
            filters &= (
                Q(discount_price__lte=float(max_price))
                | Q(discount_price__isnull=True, price__lte=float(max_price))
            )
        except ValueError:
            pass

    # ---- size filter (any size row with stock) -------------------------
    size = request.GET.get("size", "").strip()
    if size:
        filters &= Q(sizes__size=size, sizes__stock__gt=0)

    qs = qs.filter(filters).distinct()

    # ---- sorting -------------------------------------------------------
    sort = request.GET.get("sort", "newest")
    sort_map = {
        "newest": "-created_at",
        "oldest": "created_at",
        "price_asc": "price",              # price field; see note below
        "price_desc": "-price",
        "popularity": "-popularity",
        "name": "name",
    }
    if sort in sort_map:
        qs = qs.order_by(sort_map[sort])

    # For price sorting, sort by the *effective* price (discount if set).
    if sort in ("price_asc", "price_desc"):
        effective = Case(
            When(discount_price__isnull=False, then=F("discount_price")),
            default=F("price"),
            output_field=DecimalField(),
        )
        qs = qs.order_by(
            OrderBy(effective, descending=(sort == "price_desc"))
        )

    return qs, sort


def _filter_context(request):
    """Values needed to re-render the filter sidebar with current state."""
    current_category = request.GET.get("category", "")
    current_cat_obj = (
        Category.objects.filter(slug=current_category).first() if current_category else None
    )
    return {
        # Top-level footwear types (Boots, Sandals, ...) with their children
        # for the sidebar tree and the navbar mega-menu.
        "categories": Category.objects.filter(
            is_active=True, parent__isnull=True
        ).prefetch_related("children"),
        "brands": Brand.objects.all(),
        # Audience choices come from the model so the sidebar can never drift
        # from the navbar links.
        "audience_choices": Product.AUDIENCE,
        # Every distinct size present in the catalog (adult numbers + S/M/L).
        "sizes": (
            Product.objects.active()
            .values_list("sizes__size", flat=True)
            .distinct()
            .exclude(sizes__size__isnull=True)
        ),
        "selected_brands": set(request.GET.getlist("brand")),
        "selected_sizes": request.GET.get("size", ""),
        "current_category": current_category,
        # Human label for the results heading ("Boots / Chelsea Boots").
        "current_category_name": current_cat_obj.full_name if current_cat_obj else "",
        "current_audience": request.GET.get("audience", ""),
        "current_sale": request.GET.get("sale", ""),
        "current_q": request.GET.get("q", ""),
        "min_price": request.GET.get("min_price", ""),
        "max_price": request.GET.get("max_price", ""),
        "sort": request.GET.get("sort", "newest"),
    }


# ------------------------------------------------------------------ views ---
# Emoji used for the Men / Women / Kids cards on the home page.
AUDIENCE_EMOJI = {"men": "🚹", "women": "🚺", "kids": "🧒"}


def _type_category_counts():
    """
    Active top-level footwear types, each annotated with

    * ``product_count`` -- active products in the type *and* its children
    * ``children``      -- already fetched (no N+1 in the navbar/menu)

    Two queries total: one for the whole tree, one for per-category counts.
    """
    cats = list(Category.objects.filter(is_active=True).order_by("name"))
    children: dict = {}
    for c in cats:
        children.setdefault(c.parent_id, []).append(c)

    per_cat = dict(
        Product.objects.active()
        .values("category_id")
        .annotate(n=Count("pk"))
        .values_list("category_id", "n")
    )

    memo: dict = {}

    def count_of(node):
        """Products in this category plus every descendant."""
        if node.pk not in memo:
            memo[node.pk] = per_cat.get(node.pk, 0) + sum(
                count_of(c) for c in children.get(node.pk, [])
            )
        return memo[node.pk]

    for cat in cats:
        # Plain attribute (not a model field) -- safe, not persisted.
        cat.product_count = count_of(cat)
    return children.get(None, [])


def home(request):
    """
    Home page: hero, audience + category cards, featured, deals and new in.
    """
    featured = (
        Product.objects.featured()
        .select_related("brand", "category")
        .prefetch_related("images", "sizes")[:8]
    )
    newest = (
        Product.objects.active()
        .select_related("brand", "category")
        .prefetch_related("images", "sizes")[:8]
    )
    on_sale = (
        Product.objects.on_sale()
        .select_related("brand", "category")
        .prefetch_related("images", "sizes")[:4]
    )

    per_audience = dict(
        Product.objects.active()
        .values("audience")
        .annotate(n=Count("pk"))
        .values_list("audience", "n")
    )
    audience_cards = [
        {
            "slug": slug,
            "name": name,
            "emoji": AUDIENCE_EMOJI[slug],
            "count": per_audience.get(slug, 0),
        }
        for slug, name in Product.AUDIENCE
    ]

    context = {
        "featured": featured,
        "newest": newest,
        "on_sale": on_sale,
        "audience_cards": audience_cards,
        "type_categories": _type_category_counts(),
    }
    return render(request, "store/home.html", context)


def product_list(request):
    """Product listing with filters, search, sort and pagination."""
    qs, sort = _filtered_products(request)
    context = _filter_context(request)

    # paginate: 12 per page
    paginator = Paginator(qs, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Query string *without* the page param, used to build prev/next links.
    from django.http import QueryDict

    qd = request.GET.copy()
    qd.pop("page", None)
    base_query = qd.urlencode()
    if base_query:
        base_query += "&"

    context.update(
        {
            "products": page_obj,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "total_results": paginator.count,
            "sort": sort,
            "base_query": base_query,
        }
    )
    return render(request, "store/product_list.html", context)


def product_detail(request, slug):
    """Product detail page: gallery, sizes, reviews, related products."""
    product = get_object_or_404(
        Product.objects.active()
        .select_related("brand", "category")
        .prefetch_related("images", "sizes", "reviews__user"),
        slug=slug,
    )

    # Only show sizes that exist for this product (stock shown per size).
    sizes = list(product.sizes.all())

    # Related = same category or same brand, excluding current product.
    related = (
        Product.objects.active()
        .filter(Q(category=product.category) | Q(brand=product.brand))
        .exclude(pk=product.pk)
        .select_related("brand", "category")
        .prefetch_related("images", "sizes")[:4]
    )

    reviews = product.reviews.select_related("user")
    # Rating breakdown (5 → 1 stars) for the summary bars.
    breakdown = {i: 0 for i in range(1, 6)}
    for r in reviews:
        breakdown[r.rating] = breakdown.get(r.rating, 0) + 1

    # Percentage width for each bar (avoids maths in the template).
    total_reviews = sum(breakdown.values())
    rating_rows = [
        {
            "stars": stars,
            "count": count,
            "pct": round(count * 100 / total_reviews) if total_reviews else 0,
        }
        for stars, count in sorted(breakdown.items(), reverse=True)
    ]

    context = {
        "product": product,
        "images": list(product.images.all()),
        "sizes": sizes,
        "related": related,
        "reviews": reviews,
        "review_form": ReviewForm(),
        "rating_breakdown": breakdown,
        "rating_rows": rating_rows,
        "can_review": request.user.is_authenticated,
        "already_reviewed": (
            request.user.is_authenticated
            and product.reviews.filter(user=request.user).exists()
        ),
        # Size-guide chart matching the product's size system
        # (adult UK/India, kids UK, or S/M/L) -- see store/size_guides.py.
        "size_guide": product.size_guide,
    }
    return render(request, "store/product_detail.html", context)


@require_POST
def post_review(request, slug):
    """Handle the review form (login required, one review per product)."""
    product = get_object_or_404(Product, slug=slug, is_active=True)

    if not request.user.is_authenticated:
        messages.info(request, "Please log in to write a review.")
        return redirect("accounts:login")

    if product.reviews.filter(user=request.user).exists():
        messages.warning(request, "You have already reviewed this product.")
        return redirect(product.get_absolute_url())

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        review.save()
        messages.success(request, "Thanks! Your review has been posted.")
    else:
        messages.error(request, "Please check your review and try again.")

    return redirect(product.get_absolute_url())


def search_suggestions(request):
    """
    Lightweight JSON endpoint used by the navbar search box
    (progressive enhancement -- plain form submit still works).
    """
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    products = (
        Product.objects.active()
        .filter(name__icontains=q)
        .select_related("brand")[:6]
        .values("slug", "name", "brand__name")
    )
    return JsonResponse(
        {
            "results": [
                {
                    "slug": p["slug"],
                    "name": p["name"],
                    "brand": p["brand__name"],
                }
                for p in products
            ]
        }
    )
