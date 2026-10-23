from datetime import date, timedelta

from django.utils import timezone

from ordo.models import LiturgicalOccasion
from precentor_project.test_browser import PlaywrightTestCase
from precentor_project.testing import make_score, make_slot_template, make_term

from .models import RolePiece, Service, ServiceRole, TermMarker


class ConfirmToggleBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        term = make_term(
            name="Browser Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        score = make_score(title="Browser Anthem", composer_surname="Browser Composer")
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
        term = make_term(
            name="Browser Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        self.score = make_score(title="Browser Anthem", composer_surname="Browser Composer")
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
        term = make_term(
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
        term = make_term(
            name="Browser Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        self.score_a = make_score(title="Ave Verum", composer_surname="Byrd")
        self.score_b = make_score(title="Locus Iste", composer_surname="Bruckner")
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
        self.term = make_term(
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
        self.term = make_term(
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
            score = make_score(
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


class SlotOrderBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        term = make_term(
            name="Browser Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), calendar_use="current"
        )
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        self.roles = [ServiceRole.objects.create(service=self.service, role_name=n) for n in ("Introit", "Gloria", "Communion")]

    def order(self):
        return self.page.eval_on_selector_all(
            "#roles-list > .role-block summary", "els => els.map(el => el.textContent.trim().replace(/^\W+/, ''))"
        )

    def test_move_buttons_reorder_without_a_reload_and_keep_focus(self):
        self.page.goto(f"/services/{self.service.pk}/")
        self.page.evaluate("window.__marker = true")
        self.page.click(f"#move-down-{self.roles[0].pk}")
        self.page.wait_for_function(
            "document.querySelector('#roles-list > .role-block summary').textContent.includes('Gloria')"
        )
        assert self.order() == ["Gloria", "Introit", "Communion"]
        assert self.page.evaluate("window.__marker") is True
        assert self.page.evaluate("document.activeElement.id") == f"move-down-{self.roles[0].pk}"
        # The first slot has no Move up, the last no Move down.
        assert not self.page.is_visible(f"#move-up-{self.roles[1].pk}")
        assert not self.page.is_visible(f"#move-down-{self.roles[2].pk}")

    def pick_up(self, role):
        # Playwright's drag_to jumps in a single move, which never starts a
        # native drag in Chromium, so move the mouse in steps instead.
        box = self.page.locator(f"#role-block-{role.pk} .role-block__handle").bounding_box()
        self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        self.page.mouse.down()
        self.page.mouse.move(box["x"] + 20, box["y"] + 20, steps=5)

    def drop_on_top_of(self, role):
        box = self.page.locator(f"#role-block-{role.pk}").bounding_box()
        self.page.mouse.move(box["x"] + 30, box["y"] + 8, steps=10)
        self.page.mouse.up()

    def test_dragging_a_slot_by_its_handle(self):
        # Tall enough that all three slots are on screen at once.
        self.page.set_viewport_size({"width": 1280, "height": 1400})
        self.page.goto(f"/services/{self.service.pk}/")
        self.pick_up(self.roles[2])
        self.drop_on_top_of(self.roles[0])
        self.page.wait_for_selector(".toast--success")
        assert self.order() == ["Communion", "Introit", "Gloria"]
        assert [r.role_name for r in self.service.roles.all()] == ["Communion", "Introit", "Gloria"]

    def test_holding_a_slot_at_the_edge_of_the_window_scrolls_the_page(self):
        more = [ServiceRole.objects.create(service=self.service, role_name=f"Motet {n}") for n in range(1, 9)]
        self.page.set_viewport_size({"width": 1000, "height": 600})
        self.page.goto(f"/services/{self.service.pk}/")
        self.page.locator(f"#role-block-{more[-1].pk}").scroll_into_view_if_needed()
        assert self.page.evaluate("window.scrollY") > 0

        self.pick_up(more[-1])
        self.page.mouse.move(300, 4, steps=10)
        self.page.wait_for_function("window.scrollY === 0", timeout=10000)
        self.drop_on_top_of(self.roles[0])
        self.page.wait_for_selector(".toast--success")
        assert self.order()[:2] == ["Motet 8", "Introit"]


class ReplaceTemplateBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        term = make_term(
            name="Browser Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), calendar_use="current"
        )
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        make_slot_template(name="Mass", slot_names="Introit\nKyrie")
        make_slot_template(name="Vespers", slot_names="Psalms\nMagnificat")

    def test_another_template_asks_in_the_dialog(self):
        # Headless Chromium stops painting after this form's redirect back
        # to the same page when the page transition is on, so the next click
        # never lands. Reduced motion turns the transition off.
        self.page.emulate_media(reduced_motion="reduce")
        self.page.goto(f"/services/{self.service.pk}/")
        with self.page.expect_navigation():
            self.page.click("form.apply-template button:has-text('Mass')")
        assert self.page.is_visible(".role-block summary:has-text('Kyrie')")

        self.page.click("form.apply-template button:has-text('Vespers')")
        dialog = self.page.locator("dialog.confirm-dialog")
        assert "Replace the Mass slots with Vespers?" in dialog.inner_text()
        dialog.get_by_role("button", name="Cancel").click()
        dialog.wait_for(state="detached")
        assert [r.role_name for r in self.service.roles.all()] == ["Introit", "Kyrie"]

        self.page.click("form.apply-template button:has-text('Vespers')")
        with self.page.expect_navigation():
            self.page.locator("dialog.confirm-dialog").get_by_role("button", name="Use Vespers").click()
        assert [r.role_name for r in self.service.roles.all()] == ["Psalms", "Magnificat"]


class RemoveSlotBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        term = make_term(
            name="Browser Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), calendar_use="current"
        )
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        self.introit, self.motet, self.communion = [
            ServiceRole.objects.create(service=self.service, role_name=n) for n in ("Introit", "Offertory motet", "Communion")
        ]
        score = make_score(title="Ave verum", composer_surname="Byrd")
        RolePiece.objects.create(service_role=self.motet, score=score)

    def names(self):
        return [r.role_name for r in self.service.roles.all()]

    def test_an_empty_slot_goes_at_once_and_focus_moves_on(self):
        self.page.goto(f"/services/{self.service.pk}/")
        self.page.click(f"#remove-slot-{self.introit.pk}")
        self.page.wait_for_selector(f"#role-block-{self.introit.pk}", state="detached")
        assert "Removed Introit" in self.page.inner_text(".toast--success")
        assert self.page.evaluate("document.activeElement.closest('.role-block')?.id") == f"role-block-{self.motet.pk}"
        assert self.names() == ["Offertory motet", "Communion"]

    def test_a_slot_with_pieces_asks_in_the_dialog(self):
        self.page.goto(f"/services/{self.service.pk}/")
        self.page.click(f"#remove-slot-{self.motet.pk}")
        dialog = self.page.locator("dialog.confirm-dialog")
        assert "Its 1 proposed piece" in dialog.inner_text()
        dialog.get_by_role("button", name="Cancel").click()
        dialog.wait_for(state="detached")
        assert self.names() == ["Introit", "Offertory motet", "Communion"]

        self.page.click(f"#remove-slot-{self.motet.pk}")
        self.page.locator("dialog.confirm-dialog").get_by_role("button", name="Remove").click()
        self.page.wait_for_selector(f"#role-block-{self.motet.pk}", state="detached")
        assert self.names() == ["Introit", "Communion"]
        assert not RolePiece.objects.exists()


class OccasionCalendarFilterBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        self.term = make_term(
            name="Browser Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), calendar_use="current"
        )
        self.new = LiturgicalOccasion.objects.create(name="Baptism of the Lord", calendar_use="current", fixed_month=1, fixed_day=11)
        self.old = LiturgicalOccasion.objects.create(name="Holy Family", calendar_use="historic", fixed_month=1, fixed_day=11)

    def visible_options(self):
        return self.page.eval_on_selector_all(
            "#id_occasion option[data-calendar-use]", "els => els.filter(o => !o.hidden).map(o => o.textContent)"
        )

    def test_only_the_chosen_calendars_occasions_are_listed(self):
        self.page.goto(f"/terms/{self.term.pk}/services/add/")
        # Blank follows the term, which keeps the Ordinary Form.
        assert self.visible_options() == ["Baptism of the Lord"]
        self.page.select_option("#id_calendar_use", "historic")
        assert self.visible_options() == ["Holy Family (1962)"]

        # One already chosen stays listed when the calendar changes.
        self.page.select_option("#id_occasion", str(self.old.pk))
        self.page.select_option("#id_calendar_use", "current")
        assert self.visible_options() == ["Baptism of the Lord", "Holy Family (1962)"]


class TermPagesForViewersBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        # Around today, so the Terms page shows it as a current term.
        today = timezone.localdate()
        self.term = make_term(
            name="Lent", start_date=today - timedelta(days=30), end_date=today + timedelta(days=30),
            calendar_use="current",
        )
        Service.objects.create(term=self.term, date=today + timedelta(days=3), service_type="Sung Mass")
        TermMarker.objects.create(term=self.term, date=today + timedelta(days=10), text="Half term")

    def write_links(self):
        return self.page.eval_on_selector_all(
            "main a[href*='/add/'], main a[href*='/edit/'], main a[href*='/delete/']",
            "links => links.map(a => a.getAttribute('href'))",
        )

    def test_a_viewer_reads_terms_without_write_controls(self):
        self.log_in_as("viewer")
        self.page.goto("/")
        assert self.page.locator(".term-card", has_text="Lent").is_visible()
        assert self.write_links() == []

        self.page.goto(f"/terms/{self.term.pk}/")
        assert "Half term" in self.page.inner_text("main")
        assert self.write_links() == []
        assert self.page.locator(f"a[href='/terms/{self.term.pk}/music-list/']").is_visible()

    def test_a_conductor_still_has_them(self):
        self.log_in_as("conductor")
        self.page.goto(f"/terms/{self.term.pk}/")
        assert len(self.write_links()) == 6  # new service, new notice, edit and delete term, edit and delete notice


class ServicePageForViewersBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        term = make_term(
            name="Lent", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), calendar_use="current"
        )
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        role = ServiceRole.objects.create(service=self.service, role_name="Offertory motet")
        score = make_score(title="Ave verum", composer_surname="Byrd")
        RolePiece.objects.create(service_role=role, score=score)

    def planning_controls(self):
        return self.page.locator(
            ".role-block__handle, .role-block__actions, .ajax-toggle-confirm, [data-fallback-for],"
            " .ajax-propose-piece, .apply-template, .ajax-add-role,"
            f" a[href='/services/{self.service.pk}/edit/'], a[href='/services/{self.service.pk}/delete/']"
        )

    def test_a_viewer_reads_the_slots_and_pieces_without_planning_controls(self):
        self.log_in_as("viewer")
        self.page.goto(f"/services/{self.service.pk}/")
        assert self.page.locator(".role-block summary", has_text="Offertory motet").is_visible()
        assert self.page.locator(".list-row", has_text="Ave verum").is_visible()
        assert self.planning_controls().count() == 0

    def test_a_conductor_still_has_them(self):
        self.log_in_as("conductor")
        self.page.goto(f"/services/{self.service.pk}/")
        assert self.planning_controls().count() > 0
        assert self.page.locator(".ajax-toggle-confirm").count() == 1
