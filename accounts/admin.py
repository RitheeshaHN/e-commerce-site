"""Admin configuration for the accounts app (users, addresses)."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Address, User


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Django's User admin plus our extra columns (email, phone)."""

    list_display = ("username", "email", "first_name", "last_name", "phone", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")
    list_filter = ("is_staff", "is_active", "date_joined")
    inlines = [AddressInline]

    # Show email + phone on the edit form (BaseUserAdmin fieldsets).
    fieldsets = BaseUserAdmin.fieldsets + (("Extra", {"fields": ("phone",)}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Extra", {"fields": ("email", "phone")}),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("full_name", "city", "state", "pincode", "user", "is_default")
    search_fields = ("full_name", "city", "pincode", "user__username")
    list_filter = ("address_type", "is_default", "state")
