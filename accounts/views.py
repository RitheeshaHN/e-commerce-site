"""
Accounts app views: register, login (merges guest cart), logout,
password reset, profile page and the saved-address book.

Password reset uses Django's built-in views but with our templates
(see stepup/urls.py). It sends reset links to the console backend
during development.
"""
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cart.utils import merge_session_cart

from .forms import AddressForm, ProfileForm, RegisterForm
from .models import Address


def register(request):
    """Create a new account, then log them in and merge any guest cart."""
    if request.user.is_authenticated:
        return redirect("store:home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Merge the guest session cart into the new DB cart.
            merged = merge_session_cart(user, request.session)
            login(request, user)  # logs in without re-entering credentials
            if merged:
                messages.success(
                    request, f"Welcome! {merged} cart item(s) carried over."
                )
            else:
                messages.success(request, "Account created. Welcome to StepUp Shoes!")
            return redirect(request.GET.get("next") or "store:home")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


def user_login(request):
    """Login view with guest-cart merge on success."""
    if request.user.is_authenticated:
        return redirect("store:home")

    if request.method == "POST":
        from django.contrib.auth.forms import AuthenticationForm

        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            merged = merge_session_cart(user, request.session)
            if merged:
                messages.success(
                    request, f"Welcome back! {merged} item(s) added to your cart."
                )
            next_url = request.POST.get("next") or request.GET.get("next")
            return redirect(next_url if next_url else "store:home")
        # Invalid credentials -> fall through and re-render with errors.
    else:
        from django.contrib.auth.forms import AuthenticationForm

        form = AuthenticationForm()

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


def user_logout(request):
    """Log out (session cart of a guest is left intact by design)."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("store:home")


@login_required
def profile(request):
    """Profile page: edit personal info + manage saved addresses."""
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)

    addresses = request.user.addresses.all()
    addr_form = AddressForm()
    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "addresses": addresses,
            "addr_form": addr_form,
            "orders_count": request.user.orders.count(),
        },
    )


@login_required
@require_POST
def address_add(request):
    """Add a new saved address (profile page modal/form)."""
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            addr = form.save(commit=False)
            addr.user = request.user
            addr.save()
            messages.success(request, "Address saved.")
        else:
            messages.error(request, "Please correct the errors in the address form.")
    return redirect("accounts:profile")


@login_required
def address_edit(request, pk):
    """Edit one of the user's saved addresses."""
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == "POST":
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "Address updated.")
            return redirect("accounts:profile")
    else:
        form = AddressForm(instance=address)
    return render(request, "accounts/address_form.html", {"form": form, "address": address})


@login_required
@require_POST
def address_delete(request, pk):
    """Delete a saved address."""
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.delete()
    messages.success(request, "Address removed.")
    return redirect("accounts:profile")
