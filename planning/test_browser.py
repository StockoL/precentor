from datetime import date

from library.models import Score
from precentor_project.test_browser import PlaywrightTestCase

from .models import RolePiece, Service, ServiceRole, Term


class ConfirmToggleBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        term = Term.objects.create(
            name="Browser Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
        )
        self.service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Eucharist"
        )
        score = Score.objects.create(title="Browser Anthem", composer="Browser Composer")
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        self.piece = RolePiece.objects.create(service_role=role, score=score)

    def test_confirm_toggle_updates_without_reload_and_preserves_focus(self):
        button = f"#confirm-toggle-{self.piece.pk}"

        self.page.goto(f"/services/{self.service.pk}/")
        self.page.wait_for_selector(button)
        assert self.page.inner_text(button) == "Confirm"

        # A full page reload would clear this — the clearest available
        # signal that the click only triggered a fetch(), not a navigation.
        self.page.evaluate("window.__browser_test_marker = true")

        self.page.click(button)
        self.page.wait_for_function(
            f"document.querySelector('{button}')?.textContent.trim() === 'Un-confirm'"
        )

        assert self.page.evaluate("window.__browser_test_marker") is True, (
            "marker was cleared — page reloaded instead of using fetch()"
        )

        self.piece.refresh_from_db()
        assert self.piece.is_confirmed is True

        # Service status badge recomputed in place, no reload.
        assert "complete" in self.page.inner_text("#service-status-badge")

        # Success toast appeared.
        self.page.wait_for_selector(".toast--success")
        assert "Piece updated" in self.page.inner_text(".toast--success")

        # Focus restored onto the same button (now reading "Un-confirm"),
        # not lost to <body> by the outerHTML swap.
        assert self.page.evaluate("document.activeElement.id") == button.lstrip("#")

        # Toast auto-dismisses on its own (6s timer).
        self.page.wait_for_selector(".toast--success", state="detached", timeout=8000)


class ProposePieceBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        term = Term.objects.create(
            name="Browser Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
        )
        self.service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Eucharist"
        )
        self.score = Score.objects.create(title="Browser Anthem", composer="Browser Composer")
        self.role = ServiceRole.objects.create(service=self.service, role_name="Anthem")

    def test_propose_piece_appends_row_without_reload(self):
        empty_state = f"#role-{self.role.pk}-pieces-empty"

        self.page.goto(f"/services/{self.service.pk}/")
        self.page.wait_for_selector(empty_state)

        self.page.evaluate("window.__browser_test_marker = true")

        self.page.select_option(f"#id_role_{self.role.pk}_score", str(self.score.pk))
        self.page.click(f"#add-piece-form-{self.role.pk} button[type=submit]")

        self.page.wait_for_selector(f"#role-{self.role.pk}-pieces li.list-row")

        assert self.page.evaluate("window.__browser_test_marker") is True, (
            "marker was cleared — page reloaded instead of using fetch()"
        )

        piece = RolePiece.objects.get(service_role=self.role)
        assert self.page.is_visible(f"#piece-row-{piece.pk}")
        assert not self.page.is_visible(empty_state)

        self.page.wait_for_selector(".toast--success")
        assert "Piece proposed" in self.page.inner_text(".toast--success")
