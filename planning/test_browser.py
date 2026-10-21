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
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        score = Score.objects.create(title="Browser Anthem", composer_surname="Browser Composer")
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
            f"document.querySelector('{button}')?.textContent.trim() === 'Unconfirm'"
        )

        assert self.page.evaluate("window.__browser_test_marker") is True, (
            "marker was cleared — page reloaded instead of using fetch()"
        )

        self.piece.refresh_from_db()
        assert self.piece.is_confirmed is True

        # Service status badge recomputed in place, no reload.
        assert self.page.inner_text("#service-status-badge").strip() == "Complete"

        # Success toast appeared.
        self.page.wait_for_selector(".toast--success")
        assert "Piece updated" in self.page.inner_text(".toast--success")
        # The × keeps a 24px target, not the buttons' 40px control height.
        assert self.page.locator(".toast-dismiss").bounding_box()["height"] == 24

        # Focus restored onto the same button (now reading "Unconfirm"),
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
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        self.score = Score.objects.create(title="Browser Anthem", composer_surname="Browser Composer")
        self.role = ServiceRole.objects.create(service=self.service, role_name="Anthem")

    def test_propose_piece_appends_row_without_reload(self):
        empty_state = f"#role-{self.role.pk}-pieces-empty"
        form = f"#add-piece-form-{self.role.pk}"

        self.page.goto(f"/services/{self.service.pk}/")
        self.page.wait_for_selector(empty_state)

        self.page.evaluate("window.__browser_test_marker = true")

        # Drive the visible search box, as a person would.
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
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Mass"
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
        # The new slot's search box is built from the list already on the page.
        assert self.page.is_visible(f"#add-piece-form-{role.pk} .score-combobox__input")

        self.page.wait_for_selector(".toast--success")
        assert "Slot added" in self.page.inner_text(".toast--success")


class ScoreComboboxBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        term = Term.objects.create(
            name="Browser Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        self.score_a = Score.objects.create(title="Ave Verum", composer_surname="Byrd")
        self.score_b = Score.objects.create(title="Locus Iste", composer_surname="Bruckner")
        self.role = ServiceRole.objects.create(service=self.service, role_name="Anthem")

    def test_combobox_filters_and_supports_keyboard_selection(self):
        form = f"#add-piece-form-{self.role.pk}"
        input_sel = f"{form} .score-combobox__input"
        listbox_sel = f"{form} .score-combobox__listbox"
        value_sel = f"{form} input[name=score]"
        count_js = f"document.querySelectorAll('{listbox_sel} li').length"
        open_js = f"!document.querySelector('{listbox_sel}').hidden"

        self.page.goto(f"/services/{self.service.pk}/")
        self.page.wait_for_selector(input_sel)

        # Once the search box is built, the form takes the place of the
        # link that serves visitors without JavaScript.
        assert self.page.is_visible(form)
        assert not self.page.is_visible(f"[data-fallback-for=add-piece-form-{self.role.pk}]")
        assert self.page.get_attribute(input_sel, "aria-label") == "Score for the Anthem"

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
        assert self.page.eval_on_selector(value_sel, "el => el.value") == str(self.score_b.pk)
        self.page.wait_for_function(f"!({open_js})")

        # Escape closes the list without altering the selection.
        self.page.click(input_sel)
        self.page.wait_for_function(f"{open_js} && {count_js} === 2")
        self.page.keyboard.press("Escape")
        self.page.wait_for_function(f"!({open_js})")
        assert self.page.eval_on_selector(value_sel, "el => el.value") == str(self.score_b.pk)

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
            calendar_use="current",
        )
        self.christmas = LiturgicalOccasion.objects.create(
            name="Christmas Day",
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

    def test_a_day_kept_alongside_can_be_added_as_a_chip(self):
        # A Lent weekday with a memorial: the weekday is the celebration and
        # the memorial is also kept.
        LiturgicalOccasion.objects.create(
            name="Saturday of the Second Week of Lent", key="lent_2_saturday", fixed_month=3, fixed_day=7,
            precedence="9", rank="weekday", is_proper_of_time=True,
        )
        LiturgicalOccasion.objects.create(
            name="Saints Perpetua and Felicity", key="perpetua", fixed_month=3, fixed_day=7,
            precedence="10", rank="memorial",
        )
        self.page.goto(f"/terms/{self.term.pk}/services/add/")
        self.page.fill("#id_date", "2026-03-07")
        self.page.dispatch_event("#id_date", "change")
        self.page.wait_for_selector("#occasion-suggestions button")
        text = self.page.inner_text("#occasion-suggestions")
        assert text.index("Saturday of the Second Week") < text.index("Perpetua"), text
        assert "Saints Perpetua and Felicity (also kept)" in text

        # Other occasions is a chip input, so ticking the box shows a chip.
        box = self.page.locator("#occasion-suggestions input[type=checkbox]").nth(1)
        self.page.locator("#occasion-suggestions label", has_text="Add to other occasions").nth(1).click()
        chip = self.page.locator(".tag-input__chip", has_text="Saints Perpetua and Felicity")
        assert chip.is_visible()
        assert box.is_checked()

        # Removing the chip unticks the box: the two stay in step.
        chip.click()
        assert chip.count() == 0
        assert not box.is_checked()


class MusicListLayoutBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        self.term = Term.objects.create(
            name="Layout Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        for day in (4, 11, 18):
            service = Service.objects.create(
                term=self.term, date=date(2026, 1, day), service_type="Choral Evensong",
                hymns="123, 345", psalm="150",
            )
            role = ServiceRole.objects.create(service=service, role_name="Setting")
            score = Score.objects.create(
                title="Missa Aeterna Christi Munera", composer_surname="Palestrina"
            )
            RolePiece.objects.create(service_role=role, score=score, is_confirmed=True)
        self.page.set_viewport_size({"width": 1280, "height": 800})
        self.page.goto(f"/terms/{self.term.pk}/music-list/")

    def test_print_button_appears_and_prints(self):
        # Stand in for the print dialog, which would block the test.
        self.page.evaluate("window.print = () => { window.__printed = true; }")
        self.page.click("[data-print]")
        assert self.page.evaluate("window.__printed") is True

    def test_narrow_columns_put_hymns_under_the_pieces(self):
        entry = self.page.locator(".service-entry").first
        main = entry.locator(".service-entry-main").bounding_box()
        aside = entry.locator(".service-entry-aside").bounding_box()
        assert aside["y"] >= main["y"] + main["height"], (main, aside)

    def test_print_uses_fixed_point_sizes(self):
        self.page.emulate_media(media="print")
        sizes = self.page.evaluate("""() => [
            getComputedStyle(document.querySelector('.music-list')).fontSize,
            getComputedStyle(document.querySelector('.music-list h2')).fontSize,
        ]""")
        # 11pt and 14pt in CSS pixels (1pt = 4/3px).
        assert sizes == ["14.6667px", "18.6667px"], sizes
