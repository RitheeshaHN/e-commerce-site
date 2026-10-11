"""Accounts app tests: register, login, logout, profile, addresses."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Address


class RegisterTests(TestCase):
    def test_register_page_renders(self):
        r = self.client.get(reverse("accounts:register"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Create your account")

    def test_successful_registration(self):
        r = self.client.post(reverse("accounts:register"), {
            "username": "shopper", "first_name": "Shop", "last_name": "Per",
            "email": "Shop@Example.com", "phone": "9876543210",
            "password1": "S3curePass!xyz", "password2": "S3curePass!xyz",
        })
        user = get_user_model().objects.get(username="shopper")
        # email normalised to lowercase by our clean_email()
        self.assertEqual(user.email, "shop@example.com")
        self.assertTrue(user.check_password("S3curePass!xyz"))
        # logged in automatically
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_duplicate_email_rejected(self):
        get_user_model().objects.create_user(
            username="taken", email="dup@x.com", password="pass12345"
        )
        r = self.client.post(reverse("accounts:register"), {
            "username": "newuser", "first_name": "N", "last_name": "U",
            "email": "dup@x.com",
            "password1": "S3curePass!xyz", "password2": "S3curePass!xyz",
        })
        self.assertEqual(r.status_code, 200)  # re-rendered with errors
        self.assertContains(r, "already exists")
        self.assertFalse(get_user_model().objects.filter(username="newuser").exists())

    def test_password_mismatch_rejected(self):
        r = self.client.post(reverse("accounts:register"), {
            "username": "newuser2", "first_name": "N", "last_name": "U",
            "email": "n2@x.com",
            "password1": "S3curePass!xyz", "password2": "Different!xyz",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="newuser2").exists())

    def test_missing_email_rejected(self):
        r = self.client.post(reverse("accounts:register"), {
            "username": "noemail", "first_name": "N", "last_name": "U",
            "email": "",
            "password1": "S3curePass!xyz", "password2": "S3curePass!xyz",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="noemail").exists())


class LoginTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(
            username="logme", email="l@x.com", password="pass12345"
        )

    def test_login_page_renders(self):
        r = self.client.get(reverse("accounts:login"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Welcome back")

    def test_successful_login(self):
        r = self.client.post(
            reverse("accounts:login"),
            {"username": "logme", "password": "pass12345"},
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.wsgi_request.user.is_authenticated)

    def test_wrong_password_rejected(self):
        r = self.client.post(
            reverse("accounts:login"),
            {"username": "logme", "password": "wrongpass"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.wsgi_request.user.is_authenticated)

    def test_logout(self):
        self.client.login(username="logme", password="pass12345")
        r = self.client.get(reverse("accounts:logout"), follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.wsgi_request.user.is_authenticated)

    def test_login_next_redirect(self):
        r = self.client.post(
            reverse("accounts:login") + "?next=/orders/checkout/",
            {"username": "logme", "password": "pass12345"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/orders/checkout/")


class ProfileTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prof", email="p@x.com", password="pass12345"
        )

    def test_profile_requires_login(self):
        r = self.client.get(reverse("accounts:profile"))
        self.assertEqual(r.status_code, 302)

    def test_profile_renders(self):
        self.client.login(username="prof", password="pass12345")
        r = self.client.get(reverse("accounts:profile"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Personal information")

    def test_profile_update(self):
        self.client.login(username="prof", password="pass12345")
        self.client.post(reverse("accounts:profile"), {
            "first_name": "Updated", "last_name": "Name",
            "email": "p@x.com", "phone": "9999999999",
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.phone, "9999999999")

    def test_profile_email_conflict_rejected(self):
        get_user_model().objects.create_user(
            username="other", email="taken@x.com", password="pass12345"
        )
        self.client.login(username="prof", password="pass12345")
        r = self.client.post(reverse("accounts:profile"), {
            "first_name": "P", "last_name": "R",
            "email": "taken@x.com", "phone": "",
        })
        self.assertContains(r, "already exists")


class AddressTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="addr", email="a@x.com", password="pass12345"
        )
        self.client.login(username="addr", password="pass12345")

    def test_add_address(self):
        self.client.post(reverse("accounts:address_add"), {
            "full_name": "Addr User", "phone": "9876543210",
            "line1": "42, Wall Street", "line2": "",
            "city": "Mumbai", "state": "Maharashtra",
            "pincode": "400001", "address_type": "home",
            "is_default": "on",
        })
        addr = Address.objects.get(user=self.user)
        self.assertEqual(addr.city, "Mumbai")
        self.assertTrue(addr.is_default)

    def test_invalid_pincode_rejected(self):
        self.client.post(reverse("accounts:address_add"), {
            "full_name": "Addr User", "phone": "9876543210",
            "line1": "42, Wall Street", "line2": "",
            "city": "Mumbai", "state": "Maharashtra",
            "pincode": "12", "address_type": "home",
        })
        self.assertEqual(Address.objects.count(), 0)

    def test_only_one_default_address(self):
        data1 = {
            "full_name": "First", "phone": "9876543210",
            "line1": "A St", "line2": "", "city": "Pune",
            "state": "MH", "pincode": "411001",
            "address_type": "home", "is_default": "on",
        }
        data2 = dict(data1, full_name="Second", city="Nashik", pincode="422001")
        self.client.post(reverse("accounts:address_add"), data1)
        self.client.post(reverse("accounts:address_add"), data2)
        defaults = Address.objects.filter(user=self.user, is_default=True)
        self.assertEqual(defaults.count(), 1)
        self.assertEqual(defaults.get().city, "Nashik")

    def test_edit_and_delete_address(self):
        addr = Address.objects.create(
            user=self.user, full_name="X", phone="1234567890",
            line1="St", city="Delhi", state="DL", pincode="110001",
        )
        r = self.client.post(
            reverse("accounts:address_edit", args=[addr.pk]),
            {
                "full_name": "X", "phone": "1234567890",
                "line1": "St", "line2": "", "city": "Gurgaon",
                "state": "HR", "pincode": "122001",
                "address_type": "home",
            },
        )
        addr.refresh_from_db()
        self.assertEqual(addr.city, "Gurgaon")

        self.client.post(reverse("accounts:address_delete", args=[addr.pk]))
        self.assertEqual(Address.objects.count(), 0)

    def test_cannot_edit_others_address(self):
        other = get_user_model().objects.create_user(
            username="stranger", email="s@x.com", password="pass12345"
        )
        addr = Address.objects.create(
            user=other, full_name="S", phone="1234567890",
            line1="St", city="Kolkata", state="WB", pincode="700001",
        )
        r = self.client.post(
            reverse("accounts:address_edit", args=[addr.pk]),
            {
                "full_name": "H", "phone": "1234567890",
                "line1": "St", "line2": "", "city": "Hackville",
                "state": "WB", "pincode": "700001", "address_type": "home",
            },
        )
        self.assertEqual(r.status_code, 404)


class PasswordResetTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(
            username="resetme", email="reset@x.com", password="oldpass123"
        )

    def test_reset_request_page(self):
        r = self.client.get(reverse("password_reset"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Forgot your password")

    def test_reset_flow_sends_email(self):
        r = self.client.post(
            reverse("password_reset"), {"email": "reset@x.com"}
        )
        self.assertRedirects(r, reverse("password_reset_done"))

    def test_reset_done_page(self):
        r = self.client.get(reverse("password_reset_done"))
        self.assertEqual(r.status_code, 200)
