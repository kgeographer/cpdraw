from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

GOOD_PW = "brillig-slithy-toves-7"


class AuthUrlTests(TestCase):
    def test_auth_url_names_reverse(self):
        for name in ["register", "login", "logout", "profile",
                     "password_change", "password_change_done",
                     "password_reset", "password_reset_done",
                     "password_reset_complete"]:
            self.assertTrue(reverse(name).startswith("/accounts/"))
        self.assertEqual(
            reverse("password_reset_confirm",
                    kwargs={"uidb64": "abc", "token": "x-y"}),
            "/accounts/reset/abc/x-y/")


class RegistrationTests(TestCase):
    def _post(self, **over):
        data = {
            "username": "newbie", "email": "newbie@example.org",
            "name": "New Bie", "affiliation": "Nowhere U", "web_page": "",
            "password1": GOOD_PW, "password2": GOOD_PW,
        }
        data.update(over)
        return self.client.post(reverse("register"), data)

    def test_register_creates_user_and_profile_and_logs_in(self):
        resp = self._post()
        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)
        u = User.objects.get(username="newbie")
        self.assertEqual(u.email, "newbie@example.org")
        self.assertEqual(u.profile.name, "New Bie")
        self.assertEqual(u.profile.affiliation, "Nowhere U")
        # session carries the new user
        self.assertEqual(int(self.client.session["_auth_user_id"]), u.pk)

    def test_duplicate_username_rejected(self):
        User.objects.create_user("newbie", password=GOOD_PW)
        resp = self._post()
        self.assertEqual(resp.status_code, 200)          # redisplayed, not redirected
        self.assertEqual(User.objects.filter(username="newbie").count(), 1)

    def test_weak_password_rejected(self):
        resp = self._post(password1="password", password2="password")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="newbie").exists())
        self.assertContains(resp, "too common")

    def test_email_required(self):
        resp = self._post(email="")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="newbie").exists())


class LoginLogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("bob", password=GOOD_PW)

    def test_login_redirects_to_dashboard(self):
        resp = self.client.post(reverse("login"),
                                {"username": "bob", "password": GOOD_PW})
        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)

    def test_bad_login_redisplays(self):
        resp = self.client.post(reverse("login"),
                                {"username": "bob", "password": "wrong"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_redirects_home(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("logout"))
        self.assertRedirects(resp, "/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)


class PasswordResetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "carol", email="carol@example.org", password=GOOD_PW)

    def test_reset_sends_one_cpdraw_email_with_confirm_link(self):
        resp = self.client.post(reverse("password_reset"),
                                {"email": "carol@example.org"})
        self.assertRedirects(resp, reverse("password_reset_done"),
                             fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, "CPDraw password reset")
        self.assertEqual(msg.from_email, "CPDraw <noreply@cpdraw.local>")
        self.assertIn("/accounts/reset/", msg.body)

    def test_reset_unknown_email_is_silent(self):
        resp = self.client.post(reverse("password_reset"),
                                {"email": "nobody@example.org"})
        self.assertRedirects(resp, reverse("password_reset_done"),
                             fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 0)


class ProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("dave", email="dave@example.org")

    def setUp(self):
        self.client.force_login(self.user)

    def test_profile_edit_updates_user_and_profile(self):
        resp = self.client.post(reverse("profile"), {
            "email": "dave2@example.org",
            "name": "Dave Two", "affiliation": "Somewhere", "web_page": "",
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "dave2@example.org")
        self.assertEqual(self.user.profile.name, "Dave Two")

    def test_profile_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("profile"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp["Location"])
