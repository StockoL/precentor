import unittest

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

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
