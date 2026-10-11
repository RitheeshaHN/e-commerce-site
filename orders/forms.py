"""Forms for the orders app (checkout with server-side validation)."""
from django import forms

from accounts.models import Address
from .models import Order


class CheckoutForm(forms.Form):
    """
    Shipping address + payment choice for checkout.

    Validation runs on the server; JavaScript mirrors the same rules
    for instant feedback on the client.
    """

    PAYMENT_CHOICES = (
        ("cod", "Cash on Delivery"),
        ("online", "Online Payment (mock)"),
    )

    full_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Full name", "autocomplete": "name"}),
    )
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "10-digit phone number", "inputmode": "tel"}),
    )
    address_line1 = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "House no, street, area", "autocomplete": "street-address"}),
    )
    address_line2 = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={"placeholder": "Landmark (optional)"}),
    )
    city = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"placeholder": "City"}))
    state = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"placeholder": "State"}))
    pincode = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={"placeholder": "6-digit PIN code", "inputmode": "numeric"}),
    )
    payment_method = forms.ChoiceField(choices=PAYMENT_CHOICES, initial="cod")
    note = forms.CharField(
        max_length=500, required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Delivery notes (optional)"}),
    )
    save_address = forms.BooleanField(required=False, initial=True)

    # Which saved address (if any) the customer picked on the page.
    saved_address_id = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 10:
            raise forms.ValidationError("Enter a valid phone number (at least 10 digits).")
        return phone

    def clean_pincode(self):
        pin = self.cleaned_data["pincode"].strip()
        if not pin.isdigit() or len(pin) != 6:
            raise forms.ValidationError("Enter a valid 6-digit PIN code.")
        return pin

    def clean_full_name(self):
        name = self.cleaned_data["full_name"].strip()
        if len(name) < 3:
            raise forms.ValidationError("Please enter your full name.")
        return name


class OrderStatusForm(forms.ModelForm):
    """Used by the admin action to change an order's status."""

    class Meta:
        model = Order
        fields = ("status",)
