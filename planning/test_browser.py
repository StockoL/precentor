from datetime import date

from library.models import Score
from ordo.models import LiturgicalOccasion
from precentor_project.test_browser import PlaywrightTestCase

from .models import RolePiece, Service, ServiceRole, Term


class ConfirmToggleBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        term = Term.objects.create(
            name="Browser Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
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
            name="Browser Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Eucharist"
        )
        self.score = Score.objects.create(title="Browser Anthem", composer="Browser Composer")
        self.role = ServiceRole.objects.create(service=self.service, role_name="Anthem")

    def test_propose_piece_appends_row_without_reload(self):
        empty_state = f"#role-{self.role.pk}-pieces-empty"
        form = f"#add-piece-form-{self.role.pk}"

        self.page.goto(f"/services/{self.service.pk}/")
        self.page.wait_for_selector(empty_state)

        self.page.evaluate("window.__browser_test_marker = true")

        # The native <select> is now hidden behind the score-picker
        # combobox — drive the real, visible control a user would.
        self.page.fill(f"{form} .score-combobox__input", "Browser Anthem")
        self.page.click(f"{form} .score-combobox__listbox li")
        self.page.click(f"{form} button[type=submit]")

        self.page.wait_for_selector(f"#role-{self.role.pk}-pieces li.list-row")

        assert self.page.evaluate("window.__browser_test_marker") is True, (
            "marker was cleared — page reloaded instead of using fetch()"
        )

        piece = RolePiece.objects.get(service_role=self.role)
        assert self.page.is_visible(f"#piece-row-{piece.pk}")
        assert not self.page.is_visible(empty_state)

        self.page.wait_for_selector(".toast--success")
        assert "Piece proposed" in self.page.inner_text(".toast--success")


class AddRoleBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        term = Term.objects.create(
            name="Browser Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Eucharist"
        )

    def test_add_role_appends_role_block_without_reload(self):
        empty_state = "#roles-list-empty"

        self.page.goto(f"/services/{self.service.pk}/")
        self.page.wait_for_selector(empty_state)

        self.page.evaluate("window.__browser_test_marker = true")

        self.page.fill("#add-role-form input[name=role_name]", "Anthem")
        self.page.click("#add-role-form button[type=submit]")

        self.page.wait_for_selector("#roles-list .role-block")

        assert self.page.evaluate("window.__browser_test_marker") is True, (
            "marker was cleared — page reloaded instead of using fetch()"
        )

        role = ServiceRole.objects.get(service=self.service)
        assert self.page.is_visible(f"#role-block-{role.pk}")
        assert not self.page.is_visible(empty_state)
        assert "Anthem" in self.page.inner_text(f"#role-block-{role.pk}")

        self.page.wait_for_selector(".toast--success")
        assert "Role added" in self.page.inner_text(".toast--success")


class ScoreComboboxBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        term = Term.objects.create(
            name="Browser Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Eucharist"
        )
        self.score_a = Score.objects.create(title="Ave Verum", composer="Byrd")
        self.score_b = Score.objects.create(title="Locus Iste", composer="Bruckner")
        self.role = ServiceRole.objects.create(service=self.service, role_name="Anthem")

    def test_combobox_filters_and_supports_keyboard_selection(self):
        form = f"#add-piece-form-{self.role.pk}"
        input_sel = f"{form} .score-combobox__input"
        listbox_sel = f"{form} .score-combobox__listbox"
        select_sel = f"#id_role_{self.role.pk}_score"
        count_js = f"document.querySelectorAll('{listbox_sel} li').length"
        open_js = f"!document.querySelector('{listbox_sel}').hidden"

        self.page.goto(f"/services/{self.service.pk}/")
        self.page.wait_for_selector(input_sel)

        # The native <select> is hidden behind the combobox once enhanced —
        # it's still in the DOM (the fallback if JS had failed), just not
        # what a sighted user interacts with.
        assert not self.page.is_visible(select_sel)

        # Typing filters down to only the matching result. Polled via a
        # plain JS predicate (wait_for_function) rather than a selector-
        # based wait — the listbox rebuilds its <li>s from scratch on every
        # keystroke (innerHTML = "" then re-append), and Playwright's
        # node-identity-based selector waits are flaky against that kind of
        # rapid wholesale replacement even though the DOM state itself,
        # confirmed via screenshot and manual polling, is correct throughout.
        self.page.fill(input_sel, "Locus")
        self.page.wait_for_function(f"{count_js} === 1")
        items = self.page.eval_on_selector_all(
            f"{listbox_sel} li", "els => els.map(el => el.textContent)"
        )
        assert "Locus Iste" in items[0]

        # Clear back to the full list, then choose the second result with
        # the keyboard alone — never clicking a result directly.
        self.page.fill(input_sel, "")
        self.page.click(input_sel)
        self.page.wait_for_function(f"{count_js} === 2")
        self.page.keyboard.press("ArrowDown")
        self.page.keyboard.press("ArrowDown")
        self.page.keyboard.press("Enter")

        assert self.page.input_value(input_sel) == f"{self.score_b.title} ({self.score_b.composer})"
        assert self.page.eval_on_selector(select_sel, "el => el.value") == str(self.score_b.pk)
        self.page.wait_for_function(f"!({open_js})")

        # Escape closes the list without altering the selection.
        self.page.click(input_sel)
        self.page.wait_for_function(f"{open_js} && {count_js} === 2")
        self.page.keyboard.press("Escape")
        self.page.wait_for_function(f"!({open_js})")
        assert self.page.eval_on_selector(select_sel, "el => el.value") == str(self.score_b.pk)

        # Clicking outside the combobox also closes it.
        self.page.click(input_sel)
        self.page.wait_for_function(f"{open_js} && {count_js} === 2")
        self.page.click("h1")
        self.page.wait_for_function(f"!({open_js})")


class OccasionAutoSuggestBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        self.term = Term.objects.create(
            name="Browser Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
        )
        self.christmas = LiturgicalOccasion.objects.create(
            name="Christmas Day",
            tradition="cofe",
            calendar_use="current",
            fixed_month=12,
            fixed_day=25,
        )

    def test_matching_date_offers_suggestion_and_sets_occasion_on_click(self):
        self.page.goto(f"/terms/{self.term.pk}/services/add/")
        self.page.wait_for_selector("#id_date")

        self.page.fill("#id_date", "2026-12-25")
        self.page.dispatch_event("#id_date", "change")

        self.page.wait_for_selector("#occasion-suggestions button")
        assert "Christmas Day" in self.page.inner_text("#occasion-suggestions")
        assert self.page.eval_on_selector("#id_occasion", "el => el.value") == ""

        self.page.click("#occasion-suggestions button")
        assert self.page.eval_on_selector("#id_occasion", "el => el.value") == str(
            self.christmas.pk
        )

    def test_non_matching_date_shows_no_suggestion(self):
        self.page.goto(f"/terms/{self.term.pk}/services/add/")
        self.page.wait_for_selector("#id_date")

        self.page.fill("#id_date", "2026-06-01")
        self.page.dispatch_event("#id_date", "change")

        # Give the fetch a moment to (not) resolve, then confirm nothing appeared.
        self.page.wait_for_timeout(300)
        assert not self.page.is_visible("#occasion-suggestions")
