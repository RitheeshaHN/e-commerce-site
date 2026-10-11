"""
Accounts app models: custom User (extends AbstractUser) and Address.

Using AbstractUser keeps all of Django's auth features (hashed
passwords, permissions, groups) while letting us add fields later
without a full custom auth backend.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """App user. Email is stored and used as the login identifier."""

    email = models.EmailField("email address", unique=True)
    phone = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["username"]

    def __str__(self) -> str:
        return self.username

    # `USERNAME_FIELD` stays `username` (Django default). Email must still
    # be unique so we can use it for password reset later.


class Address(models.Model):
    """A saved shipping address belonging to a user (profile page)."""

    ADDRESS_TYPE = (
        ("home", "Home"),
        ("office", "Office"),
        ("other", "Other"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    line1 = models.CharField(max_length=255, help_text="House no, street, area")
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPE, default="home")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name_plural = "addresses"  # not "Addresss"

    def __str__(self) -> str:
        return f"{self.full_name}, {self.city}"

    def as_single_line(self) -> str:
        """Compact representation used on order confirmation pages."""
        parts = [self.line1, self.line2, self.city, self.state, self.pincode]
        return ", ".join(p for p in parts if p)

    def save(self, *args, **kwargs):
        # Only one default address per user at a time.
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)
