"""
Template context processors for the store app.

``shop_navigation`` puts the category data the global navbar needs on every
rendered page (the "Categories" mega-menu). It is intentionally tiny: one
prefetched query for the top-level footwear types.
"""
from .models import Category, Product


def shop_navigation(request):
    """
    Top-level footwear types (+ their children) for the navbar mega-menu,
    plus the Men / Women / Kids audience choices so the navbar links can
    never drift from the model.
    """
    return {
        "mega_categories": Category.objects.filter(
            is_active=True, parent__isnull=True
        )
        .order_by("name")
        .prefetch_related("children"),
        "audience_choices": Product.AUDIENCE,
    }
