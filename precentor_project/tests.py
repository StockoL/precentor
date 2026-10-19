from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

User = get_user_model()


class BaseTemplateTests(TestCase):
    """Checks on templates/base.html, through the login page, which
    renders it without needing a signed-in user."""

    def setUp(self):
        self.response = self.client.get("/accounts/login/")

    def test_viewport_meta_tag_present(self):
        # Without it, phones lay the page out at desktop width and zoom
        # out, so the fluid type scale and media queries never apply.
        self.assertContains(
            self.response,
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            html=True,
        )

    def test_skip_link_targets_main(self):
        self.assertContains(
            self.response,
            '<a class="skip-link" href="#main">Skip to main content</a>',
            html=True,
        )
        self.assertContains(self.response, '<main id="main"')


class NavWordingTests(TestCase):
    def setUp(self):
        self.client.force_login(
            User.objects.create_superuser(username="admin", password="testpass123")
        )

    def test_nav_links_and_page_headings_use_the_same_words(self):
        pages = {
            "/library/": "Library",
            "/comments/inbox/": "Inbox",
            "/settings/": "Settings",
        }
        for url, word in pages.items():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, f'<a href="{url}">{word}</a>', html=True)
                self.assertContains(response, f"<h1>{word}</h1>", html=True)
                self.assertContains(response, f"<title>{word} — Precentor</title>", html=True)


class NavSettingsLinkTests(TestCase):
    """Settings is conductor-only, so the link shows only to conductors."""

    def test_conductor_sees_settings_link(self):
        conductor = User.objects.create_user(username="conductor", password="pw")
        conductor.groups.add(Group.objects.get_or_create(name="Conductor")[0])
        self.client.force_login(conductor)
        self.assertContains(self.client.get("/library/"), 'href="/settings/"')

    def test_librarian_does_not_see_settings_link(self):
        librarian = User.objects.create_user(username="librarian", password="pw")
        librarian.groups.add(Group.objects.get_or_create(name="Librarian")[0])
        self.client.force_login(librarian)
        self.assertNotContains(self.client.get("/library/"), 'href="/settings/"')
