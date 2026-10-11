"""Forms for the accounts app: registration, profile, address book."""
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import User, Address


class RegisterForm(UserCreationForm):
    """
    Registration form.

    ``UserCreationForm`` handles password hashing (PBKDF2) plus the
    "passwords don't match" / common-password checks for us.
    """

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autocomplete": "email"}),
    )
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"placeholder": "First name"}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={"placeholder": "Last name (optional)"}))
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={"placeholder": "Phone (optional)"}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone")

    def clean_email(self):
        """Server-side validation: email must be unique + well-formed."""
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class ProfileForm(forms.ModelForm):
    """Edit basic profile info from the profile page."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone")
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Last name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "phone": forms.TextInput(attrs={"placeholder": "Phone number"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class AddressForm(forms.ModelForm):
    """Add / edit a saved shipping address (profile page)."""

    class Meta:
        model = Address
        fields = (
            "full_name", "phone", "line1", "line2",
            "city", "state", "pincode", "address_type", "is_default",
        )
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Full name"}),
            "phone": forms.TextInput(attrs={"placeholder": "10-digit phone"}),
            "line1": forms.TextInput(attrs={"placeholder": "House no, street, area"}),
            "line2": forms.TextInput(attrs={"placeholder": "Landmark (optional)"}),
            "city": forms.TextInput(attrs={"placeholder": "City"}),
            "state": forms.TextInput(attrs={"placeholder": "State"}),
            "pincode": forms.TextInput(attrs={"placeholder": "PIN code", "inputmode": "numeric"}),
        }

    def clean_pincode(self):
        pin = self.cleaned_data["pincode"].strip()
        if not pin.isdigit() or len(pin) != 6:
            raise forms.ValidationError("Enter a valid 6-digit PIN code.")
        return pin
