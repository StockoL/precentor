from ordo.models import LiturgicalSeason, UseType
from precentor_project.test_browser import PlaywrightTestCase

from .models import Score


class TagInputBrowserTest(PlaywrightTestCase):
    """The chip inputs over the score form's "suitable for" selects."""

    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        # A live-server test empties the database between tests, rows
        # seeded by migrations included, so create what's needed here.
        self.advent = LiturgicalSeason.objects.create(name="Advent")
        LiturgicalSeason.objects.create(name="Lent")
        UseType.objects.create(name="Mass")
        self.score = Score.objects.create(
            title="Ave verum", composer_surname="Byrd", voicing="SATB", language="Latin",
            soprano_parts=1, alto_parts=1, tenor_parts=1, bass_parts=1,
        )
        self.page.goto(f"/library/{self.score.pk}/edit/")
        self.seasons = "#id_suited_seasons-tags-search"
        self.uses = "#id_suited_use_types-tags-search"

    def save(self):
        self.page.click("button.btn-primary")
        self.page.wait_for_url(f"**/library/{self.score.pk}/")

    def test_type_and_enter_adds_a_chip_that_is_saved(self):
        self.page.fill(self.seasons, "adv")
        self.page.keyboard.press("Enter")  # the only match
        assert self.page.locator(".tag-input__chip", has_text="Advent").is_visible()
        # The hidden select is still what the form submits.
        assert self.page.eval_on_selector(
            "#id_suited_seasons", "s => [...s.selectedOptions].map(o => o.text)"
        ) == ["Advent"]
        self.save()
        assert list(self.score.suited_seasons.all()) == [self.advent]

    def test_clicking_a_chip_removes_it(self):
        self.page.fill(self.seasons, "adv")
        self.page.keyboard.press("Enter")
        self.page.click("button[aria-label='Remove Advent']")
        assert self.page.locator(".tag-input__chip", has_text="Advent").count() == 0
        self.save()
        assert self.score.suited_seasons.count() == 0

    def test_a_new_use_type_is_created_on_save(self):
        self.page.fill(self.uses, "Benediction")
        self.page.keyboard.press("Enter")  # the only option: Add "Benediction"
        assert self.page.locator(".tag-input__chip", has_text="Benediction").is_visible()
        self.save()
        assert list(self.score.suited_use_types.values_list("name", flat=True)) == ["Benediction"]

    def test_seasons_cannot_be_invented(self):
        self.page.fill(self.seasons, "Septuagesima")
        assert self.page.locator("#id_suited_seasons-tags-listbox li").count() == 0

    def test_native_controls_hand_over_to_the_chips(self):
        assert self.page.is_hidden("#id_suited_seasons")
        assert self.page.is_hidden("#id_new_use_types")
        # The label now focuses the search box, and the help text stays linked.
        self.page.click("label[for='id_suited_seasons-tags-search']")
        assert self.page.evaluate("document.activeElement.id") == "id_suited_seasons-tags-search"
        assert self.page.get_attribute(self.seasons, "aria-describedby") == "id_suited_seasons_helptext"
