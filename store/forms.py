"""Forms for the store app (product review + search)."""
from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    """Customer review form shown on the product detail page."""

    class Meta:
        model = Review
        fields = ("rating", "title", "comment")
        widgets = {
            "rating": forms.RadioSelect(
                attrs={"class": "star-input"}  # rendered as star radios in CSS
            ),
            "title": forms.TextInput(attrs={"placeholder": "Summary (optional)", "maxlength": 150}),
            "comment": forms.Textarea(
                attrs={"rows": 4, "placeholder": "How did the shoes fit and feel?"}
            ),
        }

    def clean_rating(self):
        rating = self.cleaned_data["rating"]
        if not 1 <= rating <= 5:
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return rating
