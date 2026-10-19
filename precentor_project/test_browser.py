import os
import unittest

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

# Playwright's sync API runs its own event loop on a background thread,
# which makes Django misdetect the live server's request-handling thread
# as an async context and refuse ORM access there (SynchronousOnlyOperation).
# This project has no async views, so it's safe to disable that check for
# this test-only module rather than require everyone who runs these tests
# to know to set the env var themselves first.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

try:
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

User = get_user_model()


@unittest.skipUnless(
    PLAYWRIGHT_AVAILABLE,
    "playwright not installed — see requirements-dev.txt (pip install -r "
    "requirements-dev.txt && playwright install chromium)",
)
class PlaywrightTestCase(StaticLiveServerTestCase):
    """
    Base class for tests that need a real, JS-executing browser against
    a real server — the one thing unit tests and Django's plain test
    client can't exercise: DOM updates from fetch(), focus retention
    across a DOM swap, toast rendering/timing. StaticLiveServerTestCase
    (not plain LiveServerTestCase) is required so static/src/js/*.css
    actually get served during the test, matching `manage.py runserver`
    under DEBUG rather than a production collectstatic build.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.page = self.browser.new_page(base_url=self.live_server_url)

    def tearDown(self):
        self.page.close()
        super().tearDown()

    def login_as_conductor(self, username="browser_conductor", password="testpass123"):
        user = User.objects.create_user(username=username, password=password)
        user.groups.add(Group.objects.get_or_create(name="Conductor")[0])
        self.page.goto("/accounts/login/")
        self.page.fill("#id_username", username)
        self.page.fill("#id_password", password)
        self.page.click("button[type=submit]")
        self.page.wait_for_load_state("networkidle")
        return user


class RootFontSizeBrowserTest(PlaywrightTestCase):
    def test_root_font_size_is_left_at_the_browser_default(self):
        # Every rem is measured from <html>. A fluid size there would
        # silently scale every token, so body text is sized on <body>.
        self.page.goto("/accounts/login/")
        root_size = self.page.evaluate(
            "getComputedStyle(document.documentElement).fontSize"
        )
        assert root_size == "16px", root_size


class ControlHeightBrowserTest(PlaywrightTestCase):
    def test_text_input_and_button_share_the_control_height(self):
        # --layout-control-height is 2.5rem: 40px at the default 16px root.
        self.page.goto("/accounts/login/")
        input_height = self.page.locator("#id_username").bounding_box()["height"]
        button_height = self.page.locator("button[type=submit]").bounding_box()["height"]
        assert input_height == button_height == 40, (input_height, button_height)


class ListRowWidthBrowserTest(PlaywrightTestCase):
    def test_list_row_spans_its_list_not_the_reading_measure(self):
        from datetime import date

        from planning.models import Service, Term

        self.login_as_conductor()
        term = Term.objects.create(
            name="Layout Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        self.page.set_viewport_size({"width": 1280, "height": 800})
        self.page.goto(term.get_absolute_url())

        # Compare with the list's content box: its own padding is not the row's.
        row_width, list_content_width = self.page.locator(".list-row").first.evaluate(
            """row => {
                const list = getComputedStyle(row.parentElement);
                const content = row.parentElement.clientWidth
                    - parseFloat(list.paddingInlineStart)
                    - parseFloat(list.paddingInlineEnd);
                return [row.getBoundingClientRect().width, content];
            }"""
        )
        assert abs(row_width - list_content_width) < 1, (row_width, list_content_width)


class SkipLinkBrowserTest(PlaywrightTestCase):
    def test_first_tab_reveals_skip_link_and_enter_jumps_to_main(self):
        # Not the login page: Django's login form autofocuses the
        # username field, so Tab starts from there instead of the top.
        self.login_as_conductor()
        self.page.goto("/")
        skip_link = self.page.locator(".skip-link")

        # Off-screen until focused: its bottom edge is above the viewport.
        box = skip_link.bounding_box()
        assert box["y"] + box["height"] <= 0

        self.page.keyboard.press("Tab")
        assert skip_link.evaluate("el => el === document.activeElement")
        assert skip_link.bounding_box()["y"] >= 0

        self.page.keyboard.press("Enter")
        assert self.page.url.endswith("#main")
