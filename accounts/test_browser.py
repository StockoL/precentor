from precentor_project.test_browser import PlaywrightTestCase

from .models import User
from .testing import make_organisation


class CopyLinkBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        # Page transitions stall headless Chromium after a redirect.
        self.page.emulate_media(reduced_motion="reduce")
        User.objects.create_user(
            email="owner@example.com",
            password="testpass123",
            organisation=make_organisation(),
            role="conductor",
            is_owner=True,
        )
        self.page.goto("/accounts/login/")
        self.page.fill("#id_username", "owner@example.com")
        self.page.fill("#id_password", "testpass123")
        self.page.click("main button[type=submit]")
        self.page.wait_for_load_state("networkidle")

    def make_invitation(self):
        self.page.goto("/members/invite/")
        self.page.click("main button[type=submit]")
        self.page.wait_for_load_state("networkidle")

    def test_copy_link_puts_the_link_on_the_clipboard(self):
        self.page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=self.live_server_url)
        self.make_invitation()
        link = self.page.input_value("#invitation-link")
        self.page.click("text=Copy link")
        self.page.wait_for_selector(".toast--success")
        assert self.page.evaluate("navigator.clipboard.readText()") == link
        assert "Link copied." in self.page.inner_text("#toast-region")

    def test_if_the_clipboard_is_refused_the_link_is_selected(self):
        self.make_invitation()
        self.page.evaluate("() => { navigator.clipboard.writeText = () => Promise.reject(new Error('refused')); }")
        self.page.click("text=Copy link")
        self.page.wait_for_selector(".toast--warning")
        selected = self.page.evaluate("(() => { const i = document.getElementById('invitation-link'); "
                                      "return [i.selectionStart, i.selectionEnd, i.value.length]; })()")
        assert selected[0] == 0 and selected[1] == selected[2], selected
