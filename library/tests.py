from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.testing import make_organisation, make_user
from ordo.models import LiturgicalOccasion, UseType
from precentor_project.testing import make_score, make_term, make_use_type

from .models import Score


class ScoreFormLabelTests(TestCase):
    """Labels come from explicit verbose_name, not field names."""

    def test_score_form_labels_read_naturally(self):
        self.client.force_login(make_user("librarian"))
        response = self.client.get("/library/add/")
        for label in ("Background", "Interpretation notes",
                      "Composer&#x27;s other names", "Sopranos", "Basses",
                      "Duration (minutes)", "Suitable uses", "Suitable seasons",
                      "Suitable occasions", "Text", "Translation", "Translation credit"):
            with self.subTest(label=label):
                self.assertContains(response, f"{label}:</label>")
        for old in ("Soprano parts", "Duration minutes", "Suited use types"):
            with self.subTest(old=old):
                self.assertNotContains(response, old)


class ScoreFormLayoutTests(TestCase):
    def test_fields_are_grouped_and_none_are_missing(self):
        from .forms import ScoreForm

        self.client.force_login(make_user("librarian"))
        response = self.client.get("/library/add/")
        for legend in ("Identity", "Forces", "Library", "Liturgical use", "Notes", "Text"):
            with self.subTest(legend=legend):
                self.assertContains(response, f"<legend>{legend}</legend>", html=True)
        # Every field in the form class appears in the hand-written layout.
        for field in ScoreForm.Meta.fields:
            with self.subTest(field=field):
                self.assertContains(response, f'name="{field}"')

    def test_the_text_section_reminds_about_rights(self):
        self.client.force_login(make_user("librarian"))
        self.assertContains(self.client.get("/library/add/"), "Only enter texts you're entitled to reproduce.")


class VoicingSuggestionTests(TestCase):
    def test_voicing_field_suggests_existing_voicings_once_each(self):
        for title, voicing in (("A", "SATB"), ("B", "SATB"), ("C", "SSA"), ("D", "")):
            make_score(title=title, composer_surname="X", voicing=voicing)
        self.client.force_login(make_user("librarian"))
        response = self.client.get("/library/add/")
        self.assertContains(response, 'list="voicing-options"')
        self.assertContains(response, '<option value="SATB"></option>', count=1, html=True)
        self.assertContains(response, '<option value="SSA"></option>', count=1, html=True)
        self.assertNotContains(response, '<option value=""></option>', html=True)


class NewUseTypeTests(TestCase):
    """Use types can be typed in on the score form and are created on save."""

    BASE = {
        "title": "Ave verum", "composer_surname": "Byrd", "voicing": "SATB",
        "language": "Latin", "soprano_parts": 1, "alto_parts": 1, "tenor_parts": 1,
        "bass_parts": 1, "copies_owned": 0,
    }

    def save(self, new_use_types, **extra):
        from .forms import ScoreForm

        # The score belongs to a church, as the create view arranges.
        form = ScoreForm(
            data={**self.BASE, "new_use_types": new_use_types, **extra},
            instance=Score(organisation=make_organisation()),
        )
        self.assertTrue(form.is_valid(), form.errors)
        return form.save()

    def names(self, score):
        return sorted(score.suited_use_types.values_list("name", flat=True))

    def test_new_names_are_created_and_tagged(self):
        score = self.save("Benediction, Funeral")
        self.assertEqual(self.names(score), ["Benediction", "Funeral"])
        self.assertTrue(UseType.objects.filter(name="Benediction").exists())

    def test_an_existing_name_is_reused_whatever_its_case(self):
        make_use_type("Mass")
        make_use_type("Vespers")
        before = UseType.objects.count()
        score = self.save("mass,  VESPERS ")
        self.assertEqual(self.names(score), ["Mass", "Vespers"])  # the church's own
        self.assertEqual(UseType.objects.count(), before)

    def test_blanks_and_repeats_are_ignored_and_spaces_tidied(self):
        score = self.save(" ,  Wedding   Mass , wedding mass,, ")
        self.assertEqual(self.names(score), ["Wedding Mass"])

    def test_works_alongside_picked_use_types(self):
        general = make_use_type("General use")
        score = self.save("Benediction", suited_use_types=[general.pk])
        self.assertEqual(self.names(score), ["Benediction", "General use"])

    def test_commit_false_adds_them_with_save_m2m(self):
        from .forms import ScoreForm

        form = ScoreForm(
            data={**self.BASE, "new_use_types": "Benediction"}, instance=Score(organisation=make_organisation())
        )
        self.assertTrue(form.is_valid())
        score = form.save(commit=False)
        score.save()
        form.save_m2m()
        self.assertEqual(self.names(score), ["Benediction"])


class ScoreEditorTests(TestCase):
    def test_editor_can_be_recorded_from_the_form(self):
        self.client.force_login(make_user("librarian"))
        response = self.client.post("/library/add/", {
            "title": "Sicut cervus", "composer_surname": "Palestrina",
            "editor": "Stockton", "voicing": "SATB", "language": "Latin",
            "soprano_parts": 1, "alto_parts": 1, "tenor_parts": 1, "bass_parts": 1,
            "copies_owned": 0,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Score.objects.get().editor, "Stockton")


class LastSungManualFieldTests(TestCase):
    def test_form_offers_a_native_date_picker(self):
        from datetime import date

        from .forms import ScoreForm

        score = Score(title="Ave verum", composer_surname="Byrd", last_sung_manual=date(2019, 6, 2))
        field = str(ScoreForm(instance=score)["last_sung_manual"])
        self.assertIn('type="date"', field)
        self.assertIn('value="2019-06-02"', field)


class LastSungTests(TestCase):
    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        from planning.models import Service

        # The same "today" as with_last_sung, which uses the UK time zone.
        self.today = timezone.localdate()
        self.term = make_term(
            name="Term",
            start_date=self.today - timedelta(days=365),
            end_date=self.today + timedelta(days=365),
            calendar_use="current",
        )
        self.Service = Service
        self.score = make_score(title="Ave verum", composer_surname="Byrd")

    def sing(self, days_from_today, confirmed=True):
        from datetime import timedelta

        from planning.models import RolePiece, ServiceRole

        service = self.Service.objects.create(
            term=self.term,
            date=self.today + timedelta(days=days_from_today),
            service_type="Sung Mass",
        )
        role = ServiceRole.objects.create(service=service, role_name="Motet")
        RolePiece.objects.create(service_role=role, score=self.score, is_confirmed=confirmed)
        return service.date

    def last_sung(self):
        return Score.objects.with_last_sung().get(pk=self.score.pk).last_sung

    def test_latest_confirmed_past_service(self):
        self.sing(-30)
        latest = self.sing(-7)
        self.assertEqual(self.last_sung(), latest)

    def test_unconfirmed_pieces_do_not_count(self):
        self.sing(-7, confirmed=False)
        self.assertIsNone(self.last_sung())

    def test_a_future_service_is_scheduled_not_sung(self):
        past = self.sing(-7)
        self.sing(14)
        self.assertEqual(self.last_sung(), past)

    def test_the_later_of_recorded_and_manual_wins(self):
        from datetime import timedelta

        recorded = self.sing(-7)
        self.score.last_sung_manual = recorded - timedelta(days=400)
        self.score.save()
        self.assertEqual(self.last_sung(), recorded)

        self.score.last_sung_manual = recorded + timedelta(days=1)
        self.score.save()
        self.assertEqual(self.last_sung(), recorded + timedelta(days=1))

    def test_manual_date_alone(self):
        from datetime import date

        self.score.last_sung_manual = date(2019, 6, 2)
        self.score.save()
        self.assertEqual(self.last_sung(), date(2019, 6, 2))

    def test_never_sung(self):
        self.assertIsNone(self.last_sung())


class VocalRangeTests(TestCase):
    def test_accepts_note_names_from_low_to_high(self):
        from .validators import validate_vocal_range

        for value in ("A3–E5", "A3-E5", "c4 - a5", "F#3–Bb4", "Bb2–E♭4", "C4–C4"):
            with self.subTest(value=value):
                validate_vocal_range(value)  # raises if invalid

    def test_refuses_anything_else(self):
        from .validators import validate_vocal_range

        for value in ("A3", "H3–E5", "A–E5", "low to high", "A3–E5–G5"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as caught:
                    validate_vocal_range(value)
                self.assertEqual(caught.exception.code, "format")

    def test_refuses_the_wrong_way_round(self):
        from .validators import validate_vocal_range

        for value in ("E5–A3", "C4–B3", "C#4–C4"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as caught:
                    validate_vocal_range(value)
                self.assertEqual(caught.exception.code, "order")

    def test_form_stores_one_tidy_form(self):
        from .forms import ScoreForm

        form = ScoreForm(data={
            "title": "Ave verum", "composer_surname": "Byrd", "voicing": "SATB",
            "language": "Latin", "soprano_parts": 1, "alto_parts": 1, "tenor_parts": 1,
            "bass_parts": 1, "copies_owned": 0, "range_soprano": "d4 - f#5",
            "range_bass": "F♯2–D4",
        }, instance=Score(organisation=make_organisation()))
        self.assertTrue(form.is_valid(), form.errors)
        score = form.save()
        self.assertEqual(score.range_soprano, "D4–F#5")
        self.assertEqual(score.range_bass, "F#2–D4")

    def test_form_shows_the_error_against_the_field(self):
        from .forms import ScoreForm

        form = ScoreForm(data={"title": "T", "composer_surname": "X", "range_tenor": "E5–A3"})
        self.assertIn("Put the lower note first, as in A3–E5.", form.errors["range_tenor"])


class ScoreDetailPageTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("librarian"))
        self.score = make_score(
            title="Sicut cervus", composer_surname="Palestrina", editor="Stockton",
            voicing="SATB", language="Latin",
        )

    def get(self):
        return self.client.get(self.score.get_absolute_url())

    def test_summary_is_a_description_list(self):
        response = self.get()
        self.assertContains(response, "<dt>Composer</dt>", html=True)
        self.assertContains(response, "<dd>Palestrina (ed. Stockton)</dd>", html=True)
        self.assertContains(response, "<dd>Never</dd>", html=True)
        self.assertNotContains(response, "<p>Voicing:")

    def test_optional_sections_appear_only_when_filled(self):
        response = self.get()
        for heading in ("Background", "Interpretation notes", "Vocal ranges"):
            with self.subTest(heading=heading):
                self.assertNotContains(response, f"<h2>{heading}</h2>", html=True)
        self.score.background = "Psalm 42.\n\nPublished 1604."
        self.score.notes = "Keep it moving."
        self.score.range_bass = "F2–D4"
        self.score.save()
        response = self.get()
        self.assertContains(response, "<p>Psalm 42.</p>", html=True)  # line breaks kept
        self.assertContains(response, "<h2>Interpretation notes</h2>", html=True)
        self.assertContains(response, "<dd>F2–D4</dd>", html=True)

    def test_history_lists_each_service_with_its_state(self):
        from datetime import timedelta

        from django.utils import timezone

        from planning.models import RolePiece, Service, ServiceRole

        today = timezone.localdate()
        term = make_term(
            name="Lent", start_date=today - timedelta(days=60),
            end_date=today + timedelta(days=60), calendar_use="current",
        )
        for days, confirmed in ((-14, True), (14, True), (21, False)):
            service = Service.objects.create(
                term=term, date=today + timedelta(days=days), service_type="Sung Mass"
            )
            role = ServiceRole.objects.create(service=service, role_name="Offertory motet")
            RolePiece.objects.create(service_role=role, score=self.score, is_confirmed=confirmed)

        response = self.get()
        for state, label in (("sung", "Sung"), ("scheduled", "Scheduled"), ("proposed", "Proposed")):
            with self.subTest(state=state):
                self.assertContains(
                    response, f'<span class="badge badge--{state}">{label}</span>', html=True
                )
        history = list(response.context["history"])
        self.assertEqual(len(history), 3)
        self.assertGreater(  # newest first
            history[0].service_role.service.date, history[-1].service_role.service.date
        )
        # The summary's last sung is the sung service, not the scheduled one.
        self.assertEqual(response.context["score"].last_sung, today - timedelta(days=14))

    def test_empty_history_says_so(self):
        self.assertContains(self.get(), "Not yet proposed for any service.")


class LibraryEmptyStateTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("librarian"))

    def test_empty_library_offers_the_first_score(self):
        response = self.client.get("/library/")
        self.assertContains(response, "The library is empty.")
        self.assertContains(response, ">Add the first score</a>")

    def test_filters_with_no_matches_offer_to_clear_them(self):
        make_score(title="Ave verum", composer_surname="Byrd", language="Latin")
        response = self.client.get("/library/?language=German")
        self.assertContains(response, "No scores match these filters.")
        self.assertContains(response, ">Clear filters</a>")
        self.assertNotContains(response, "The library is empty.")


class ScoreComposerTests(TestCase):
    def test_surname_only_displays_as_surname(self):
        score = make_score(title="Ave Verum", composer_surname="Byrd")
        self.assertEqual(score.composer, "Byrd")

    def test_surname_and_other_names_displays_combined(self):
        score = make_score(
            title="O Taste and See",
            composer_surname="Vaughan Williams",
            composer_other_names="Ralph",
        )
        self.assertEqual(score.composer, "Ralph Vaughan Williams")

    def test_catalogue_form_puts_the_surname_first_with_credits(self):
        cases = [
            ({"composer_surname": "Byrd"}, "Byrd"),
            ({"composer_surname": "Palestrina", "composer_other_names": "Giovanni Pierluigi da",
              "editor": "Stockton"}, "Palestrina, Giovanni Pierluigi da (ed. Stockton)"),
            ({"composer_surname": "Tallis", "arranger": "Rutter"}, "Tallis (arr. Rutter)"),
            ({"composer_surname": "Victoria", "arranger": "Smith", "editor": "Jones"},
             "Victoria (arr. Smith; ed. Jones)"),
        ]
        for fields, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(Score(title="T", **fields).composer_catalogue, expected)

    def test_default_order_is_composer_then_title(self):
        for surname, other, title in [
            ("Bach", "Johann Sebastian", "Jesu, meine Freude"),
            ("Bach", "Carl Philipp Emanuel", "Magnificat"),
            ("Byrd", "", "Ave verum corpus"),
            ("Bach", "Johann Sebastian", "Der Geist hilft"),
        ]:
            make_score(title=title, composer_surname=surname, composer_other_names=other)
        self.assertEqual(
            [s.title for s in Score.objects.all()],
            ["Magnificat", "Der Geist hilft", "Jesu, meine Freude", "Ave verum corpus"],
        )

    def test_surname_is_required(self):
        score = Score(
            title="Untitled Anthem",
            composer_surname="",
            voicing="SATB",
            language="English",
        )
        with self.assertRaises(ValidationError) as cm:
            score.full_clean()
        self.assertIn("composer_surname", cm.exception.message_dict)

    def test_other_names_is_optional(self):
        score = Score(
            title="Untitled Anthem",
            composer_surname="Byrd",
            voicing="SATB",
            language="English",
            organisation=make_organisation(),
        )
        score.full_clean()  # should not raise


class ScoreFilterTests(TestCase):
    def setUp(self):
        self.user = make_user("viewer")
        self.client.force_login(self.user)
        make_score(
            title="Ave Verum", composer_surname="Byrd", language="Latin", tenor_parts=1
        )
        make_score(
            title="O Taste and See",
            composer_surname="Vaughan Williams",
            language="English",
            tenor_parts=0,
        )

    def test_filter_by_language(self):
        response = self.client.get("/library/", {"language": "Latin"})
        self.assertContains(response, "Ave Verum")
        self.assertNotContains(response, "O Taste and See")

    def titles(self, **params):
        return [s.title for s in self.client.get("/library/", params).context["scores"]]

    def test_search_needs_every_word_to_match_somewhere(self):
        make_score(title="Ave Maria", composer_surname="Parsons")
        make_score(
            title="Sicut cervus", composer_surname="Palestrina", editor="Stockton"
        )
        self.assertCountEqual(self.titles(q="ave"), ["Ave Verum", "Ave Maria"])
        self.assertEqual(self.titles(q="byrd ave"), ["Ave Verum"])
        self.assertEqual(self.titles(q="AVE   byrd"), ["Ave Verum"])  # case, spacing
        self.assertEqual(self.titles(q="stockton"), ["Sicut cervus"])  # editor
        self.assertEqual(self.titles(q="byrd parsons"), [])

    def test_filter_by_voicing(self):
        Score.objects.all().update(voicing="SATB")
        make_score(title="Laudate", composer_surname="Ssa", voicing="SSA")
        self.assertEqual(self.titles(voicing="SSA"), ["Laudate"])

    def test_any_four_part_mixed_needs_all_four_parts(self):
        make_score(
            title="Full", composer_surname="A", voicing="SSATB",
            soprano_parts=2, alto_parts=1, tenor_parts=1, bass_parts=1,
        )
        make_score(
            title="Upper voices", composer_surname="B", voicing="SSA",
            soprano_parts=2, alto_parts=1,
        )
        self.assertEqual(self.titles(voicing="mixed"), ["Full"])

    def test_voicing_menu_counts_each_voicing(self):
        Score.objects.all().update(voicing="SATB")
        make_score(title="Laudate", composer_surname="Ssa", voicing="SSA")
        response = self.client.get("/library/")
        self.assertContains(response, '<option value="SATB">SATB (2)</option>', html=True)
        self.assertContains(response, '<option value="SSA">SSA (1)</option>', html=True)

    def test_a_score_without_a_language_adds_no_blank_option(self):
        make_score(title="Untitled", composer_surname="Anon", language="")
        response = self.client.get("/library/")
        self.assertContains(response, '<option value="">Any</option>', count=2, html=True)
        self.assertNotContains(response, '<option value=""></option>', html=True)

    def test_clear_link_only_when_filtering(self):
        self.assertNotContains(self.client.get("/library/"), ">Clear</a>")
        self.assertContains(self.client.get("/library/", {"q": "ave"}), ">Clear</a>")


class ScoreSuitabilityRankingTests(TestCase):
    def setUp(self):
        self.user = make_user("viewer")
        self.client.force_login(self.user)
        self.occasion = LiturgicalOccasion.objects.create(name="Advent Sunday 4")
        self.other_occasion = LiturgicalOccasion.objects.create(
            name="Ordinary Time 7"
        )
        self.untagged = make_score(
            title="Untagged Anthem", composer_surname="Nobody"
        )
        self.matching = make_score(
            title="Zzz Matching Anthem", composer_surname="Somebody"
        )
        self.matching.suited_occasions.add(self.occasion)
        self.non_matching = make_score(
            title="Aaa Non-Matching Anthem", composer_surname="Someone Else"
        )
        self.non_matching.suited_occasions.add(self.other_occasion)

    def test_untagged_score_still_appears_in_suited_for_query(self):
        response = self.client.get(
            "/library/", {"suited_occasion": self.occasion.pk}
        )
        self.assertContains(response, "Untagged Anthem")

    def test_matching_score_sorts_above_non_matching(self):
        response = self.client.get(
            "/library/", {"suited_occasion": self.occasion.pk}
        )
        titles = [score.title for score in response.context["scores"]]
        self.assertLess(
            titles.index(self.matching.title), titles.index(self.untagged.title)
        )
        self.assertLess(
            titles.index(self.matching.title), titles.index(self.non_matching.title)
        )

    def test_a_score_with_several_tags_appears_once(self):
        # Ranking used to join through the tags, so a score tagged with
        # two occasions came back twice: once suited, once not.
        self.matching.suited_occasions.add(self.other_occasion)
        ranked = list(Score.objects.ranked_by_suitability(occasion=self.occasion))
        self.assertEqual(ranked.count(self.matching), 1)
        self.assertEqual(len(ranked), Score.objects.count())

    def test_without_suitability_the_library_is_in_catalogue_order(self):
        response = self.client.get("/library/")
        surnames = [score.composer_surname for score in response.context["scores"]]
        self.assertEqual(surnames, sorted(surnames))


class LibrarySortTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("librarian"))
        make_score(title="Ave verum", composer_surname="Byrd", duration_minutes=4)
        make_score(title="Sicut cervus", composer_surname="Palestrina")
        make_score(title="Jesu, joy", composer_surname="Bach", duration_minutes=3)

    def titles(self, **params):
        return [s.title for s in self.client.get("/library/", params).context["scores"]]

    def test_default_is_composer_ascending(self):
        self.assertEqual(self.titles(), ["Jesu, joy", "Ave verum", "Sicut cervus"])

    def test_sort_by_title_either_way(self):
        self.assertEqual(self.titles(sort="title"), ["Ave verum", "Jesu, joy", "Sicut cervus"])
        self.assertEqual(
            self.titles(sort="title", dir="desc"), ["Sicut cervus", "Jesu, joy", "Ave verum"]
        )

    def test_blanks_sort_last_both_ways(self):
        self.assertEqual(self.titles(sort="duration")[-1], "Sicut cervus")
        self.assertEqual(self.titles(sort="duration", dir="desc")[-1], "Sicut cervus")

    def test_unknown_sort_falls_back_to_the_default(self):
        self.assertEqual(self.titles(sort="nonsense", dir="sideways"), self.titles())

    def test_headings_carry_aria_sort_and_flip_direction(self):
        response = self.client.get("/library/", {"sort": "title"})
        self.assertContains(response, 'aria-sort="ascending"', count=1)
        # The sorted heading's link asks for the other direction next.
        self.assertContains(response, 'href="?sort=title&amp;dir=desc"')
        self.assertContains(response, 'href="?sort=composer&amp;dir=asc"')

    def test_sort_links_keep_the_filters(self):
        response = self.client.get("/library/", {"q": "ave", "sort": "title"})
        self.assertContains(response, 'href="?q=ave&amp;sort=title&amp;dir=desc"')

    def test_fifty_to_a_page_with_filters_kept_in_the_links(self):
        church = make_organisation()
        Score.objects.bulk_create(
            Score(title=f"Motet {n:02}", composer_surname="Anon", organisation=church) for n in range(60)
        )
        first = self.client.get("/library/", {"q": "motet", "sort": "title"})
        self.assertEqual(len(first.context["scores"]), 50)
        self.assertContains(first, "60 scores, page 1 of 2")
        self.assertContains(first, 'href="?q=motet&amp;sort=title&amp;page=2"')
        second = self.client.get("/library/", {"q": "motet", "sort": "title", "page": 2})
        self.assertEqual(len(second.context["scores"]), 10)

    def test_table_shows_catalogue_names_and_last_sung(self):
        Score.objects.filter(title="Sicut cervus").update(editor="Stockton")
        response = self.client.get("/library/")
        self.assertContains(response, "<td>Palestrina (ed. Stockton)</td>", html=True)
        self.assertContains(response, "Never")


class ScoreFormOccasionChoicesTests(TestCase):
    """The "suitable for" occasions follow the national calendar on Settings."""

    @classmethod
    def setUpTestData(cls):
        from core.models import SiteConfig
        from ordo.calendar_data import load_calendar_files

        load_calendar_files()
        config = SiteConfig.of(make_organisation())
        config.national_calendar = "wales"
        config.save()

    def labels(self, form):
        return [label for _, label in form.fields["suited_occasions"].choices]

    def test_only_the_churchs_calendar_is_offered(self):
        from .forms import ScoreForm

        labels = self.labels(ScoreForm(instance=Score(organisation=make_organisation())))
        self.assertIn("St. David, Bishop & Confessor, Patron of Wales (1962)", labels)
        self.assertNotIn("Saint George, Martyr, Patron of England", labels)

    def test_a_scores_existing_tags_stay_listed(self):
        from .forms import ScoreForm

        england_george = LiturgicalOccasion.objects.get(calendar="england", key="george_of_lydda_martyr")
        score = make_score(title="Te Deum", composer_surname="Stanford")
        score.suited_occasions.add(england_george)
        self.assertIn(england_george.choice_label, self.labels(ScoreForm(instance=score)))


class LibraryEditAccessTests(TestCase):
    def setUp(self):
        self.score = make_score(title="Ave verum", composer_surname="Byrd")
        self.urls = ("/library/add/", f"/library/{self.score.pk}/edit/", f"/library/{self.score.pk}/delete/")

    def test_a_viewer_cannot_add_edit_or_delete_scores(self):
        self.client.force_login(make_user("viewer"))
        for url in self.urls:
            for method in (self.client.get, self.client.post):
                with self.subTest(url=url, method=method.__name__):
                    self.assertEqual(method(url).status_code, 403)
        self.assertTrue(Score.objects.filter(pk=self.score.pk).exists())

    def test_a_librarian_can(self):
        self.client.force_login(make_user("librarian"))
        for url in self.urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class ScoreOrganisationTests(TestCase):
    def test_a_score_belongs_to_an_organisation(self):
        church = make_organisation()
        score = make_score(title="Ave verum", composer_surname="Byrd", organisation=church)
        self.assertEqual(score.organisation, church)
        self.assertEqual(list(church.scores.all()), [score])

    def test_a_score_made_through_the_app_and_its_typed_use_types_join_the_makers_church(self):
        from ordo.models import UseType

        church = make_organisation("St Cecilia's")
        make_use_type("Benediction", organisation=make_organisation("St Elsewhere"))
        self.client.force_login(make_user("librarian", organisation=church))
        self.client.post("/library/add/", {
            **NewUseTypeTests.BASE, "title": "O salutaris", "composer_surname": "Elgar",
            "new_use_types": "benediction",
        })
        score = Score.objects.get(title="O salutaris")
        self.assertEqual(score.organisation, church)
        # A new "Benediction" for St Cecilia's, not St Elsewhere's reused.
        self.assertEqual([u.organisation for u in score.suited_use_types.all()], [church])
        self.assertEqual(UseType.objects.filter(name__iexact="benediction").count(), 2)


class LibraryForOneChurchTests(TestCase):
    """A church sees and changes only its own library."""

    def setUp(self):
        self.ours, theirs = make_organisation("St Cecilia's"), make_organisation("St Elsewhere")
        self.mine = make_score(title="Ave verum", voicing="SATB", language="Latin", organisation=self.ours)
        self.theirs = make_score(title="Hymn to the Trinity", voicing="SSA", language="Russian", organisation=theirs)
        self.client.force_login(make_user("librarian", organisation=self.ours))

    def test_the_list_and_its_menus_show_only_our_scores(self):
        response = self.client.get("/library/")
        self.assertEqual(list(response.context["scores"]), [self.mine])
        self.assertEqual(list(response.context["languages"]), ["Latin"])
        self.assertEqual([v["voicing"] for v in response.context["voicings"]], ["SATB"])

    def test_another_churchs_score_is_not_found(self):
        for url in (f"/library/{self.theirs.pk}/", f"/library/{self.theirs.pk}/edit/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        self.client.post(f"/library/{self.theirs.pk}/edit/", {"title": "Changed", "composer_surname": "X"})
        self.client.post(f"/library/{self.theirs.pk}/delete/")
        self.theirs.refresh_from_db()
        self.assertEqual(self.theirs.title, "Hymn to the Trinity")

    def test_the_score_form_offers_and_accepts_only_our_use_types(self):
        ours = make_use_type("Communion", organisation=self.ours)
        theirs = make_use_type("Funeral", organisation=self.theirs.organisation)
        form = self.client.get("/library/add/").context["form"]
        self.assertEqual(list(form.fields["suited_use_types"].queryset), [ours])

        response = self.client.post("/library/add/", {
            **NewUseTypeTests.BASE, "title": "Libera me", "suited_use_types": [theirs.pk],
        })
        self.assertIn("suited_use_types", response.context["form"].errors)
        self.assertFalse(Score.objects.filter(title="Libera me").exists())


class OptionalVoicingAndLanguageTests(TestCase):
    """Only the title and composer are needed; voicing and language help
    with planning but can be filled in later."""

    def setUp(self):
        self.client.force_login(make_user("librarian"))
        make_score(title="Complete", composer_surname="Byrd", voicing="SATB", language="Latin")
        make_score(title="No voicing", composer_surname="Tallis", voicing="", language="English")
        make_score(title="Bare", composer_surname="Anon.", voicing="", language="")

    def test_a_score_needs_only_a_title_and_composer(self):
        from .forms import ScoreForm

        form = ScoreForm(
            data={"title": "Ave verum", "composer_surname": "Byrd", "copies_owned": 0,
                  "soprano_parts": 0, "alto_parts": 0, "tenor_parts": 0, "bass_parts": 0},
            instance=Score(organisation=make_organisation()),
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_the_filters_offer_unspecified_with_its_count(self):
        response = self.client.get("/library/")
        self.assertContains(response, '<option value="unspecified">(unspecified) (1)</option>', html=True)
        self.assertContains(response, '<option value="unspecified">(unspecified) (2)</option>', html=True)

    def titles(self, **filters):
        return sorted(score.title for score in self.client.get("/library/", filters).context["scores"])

    def test_choosing_unspecified_finds_only_those(self):
        self.assertEqual(self.titles(voicing="unspecified"), ["Bare", "No voicing"])
        self.assertEqual(self.titles(language="unspecified"), ["Bare"])

    def test_unspecified_isnt_offered_when_everything_has_one(self):
        Score.objects.filter(voicing="").update(voicing="SATB", language="Latin")
        self.assertNotContains(self.client.get("/library/"), "(unspecified)")


class ScoreImportBatchTests(TestCase):
    def setUp(self):
        from .models import ScoreImport

        self.church = make_organisation()
        self.batch = ScoreImport.objects.create(organisation=self.church, original_filename="library.csv")
        self.scores = [
            make_score(organisation=self.church, title=f"Imported {n}", import_batch=self.batch) for n in range(3)
        ]
        self.by_hand = make_score(organisation=self.church, title="Added by hand")

    def plan(self, score):
        from datetime import date

        from planning.models import RolePiece, Service, ServiceRole

        from precentor_project.testing import make_term

        service = Service.objects.create(term=make_term(organisation=self.church), date=date(2026, 1, 11),
                                         service_type="Sung Mass")
        RolePiece.objects.create(service_role=ServiceRole.objects.create(service=service, role_name="Introit"),
                                 score=score)

    def test_a_new_import_is_pending(self):
        self.assertTrue(self.batch.is_pending)
        self.assertEqual(self.batch.scores.count(), 3)

    def test_removing_deletes_its_scores_and_itself_but_not_others(self):
        from .models import ScoreImport

        self.assertEqual(self.batch.remove(), (3, 0))
        self.assertFalse(ScoreImport.objects.exists())
        self.assertEqual(list(Score.objects.values_list("title", flat=True)), ["Added by hand"])

    def test_a_score_already_planned_is_kept_and_unlinked(self):
        self.plan(self.scores[0])
        self.assertEqual(self.batch.remove(), (2, 1))
        kept = Score.objects.get(title="Imported 0")
        self.assertIsNone(kept.import_batch)

    def test_keeping_closes_it_for_good(self):
        self.batch.keep()
        self.batch.refresh_from_db()
        self.assertFalse(self.batch.is_pending)
        with self.assertRaises(ValueError):
            self.batch.remove()
        self.assertEqual(Score.objects.count(), 4)

    def test_deleting_the_person_who_imported_keeps_the_record(self):
        user = make_user("librarian", organisation=self.church)
        self.batch.created_by = user
        self.batch.save()
        user.delete()
        self.batch.refresh_from_db()
        self.assertIsNone(self.batch.created_by)


class ScoreTextTests(TestCase):
    def setUp(self):
        self.viewer = make_user("viewer")
        self.client.force_login(self.viewer)

    def test_the_page_shows_the_text_beside_its_translation(self):
        score = make_score(
            organisation=self.viewer.organisation, title="Ave verum corpus",
            text="Ave verum corpus,\nnatum de Maria Virgine", translation="Hail, true body,\nborn of the Virgin Mary",
            translation_credit="Tr. the choir",
        )
        response = self.client.get(f"/library/{score.pk}/")
        self.assertContains(response, "<h2>Text</h2>", html=True)
        original = '<p class="parallel-text__original">Ave verum corpus,<br>natum de Maria Virgine</p>'
        self.assertContains(response, original, html=True)
        self.assertContains(response, '<p class="parallel-text__credit">Tr. the choir</p>', html=True)

    def test_no_text_means_no_section(self):
        score = make_score(organisation=self.viewer.organisation, title="Locus iste")
        self.assertNotContains(self.client.get(f"/library/{score.pk}/"), "<h2>Text</h2>", html=True)


class EditScoreReturnTests(TestCase):
    def setUp(self):
        self.librarian = make_user("librarian")
        self.client.force_login(self.librarian)
        self.score = make_score(organisation=self.librarian.organisation, title="Ave verum", composer_surname="Byrd")
        self.url = f"/library/{self.score.pk}/edit/"
        self.data = {"title": "Ave verum", "composer_surname": "Byrd", "voicing": "SATB",
                     "copies_owned": 0, "soprano_parts": 1, "alto_parts": 1, "tenor_parts": 1, "bass_parts": 1}

    def test_saving_goes_back_to_where_the_edit_began(self):
        self.assertContains(self.client.get(self.url, {"next": "/services/4/"}),
                            '<input type="hidden" name="next" value="/services/4/">', html=True)
        response = self.client.post(self.url, {**self.data, "next": "/services/4/"})
        self.assertRedirects(response, "/services/4/", fetch_redirect_response=False)

    def test_another_site_is_ignored(self):
        response = self.client.post(self.url, {**self.data, "next": "https://example.com/"})
        self.assertRedirects(response, f"/library/{self.score.pk}/", fetch_redirect_response=False)


class NeedingTextTests(TestCase):
    def test_only_untexted_scores_from_motet_or_antiphon_slots_count_once(self):
        from datetime import date

        from planning.models import RolePiece, Service, ServiceRole

        church = make_organisation()
        service = Service.objects.create(term=make_term(organisation=church), date=date(2026, 1, 11),
                                         service_type="Sung Mass")
        motet = ServiceRole.objects.create(service=service, role_name="Offertory motet")
        antiphon = ServiceRole.objects.create(service=service, role_name="Marian antiphon")
        kyrie = ServiceRole.objects.create(service=service, role_name="Kyrie")
        needs = make_score(organisation=church, title="Ave verum")
        texted = make_score(organisation=church, title="Locus iste", text="Locus iste a Deo factus est")
        setting = make_score(organisation=church, title="Missa brevis")
        salve = make_score(organisation=church, title="Salve Regina")
        make_score(organisation=church, title="Never planned")
        for slot, score in ((motet, needs), (antiphon, needs), (motet, texted), (kyrie, setting), (antiphon, salve)):
            RolePiece.objects.create(service_role=slot, score=score)
        found = Score.objects.for_organisation(church).needing_text()
        self.assertEqual(sorted(found.values_list("title", flat=True)), ["Ave verum", "Salve Regina"])


class CompletenessPageTests(TestCase):
    def setUp(self):
        self.librarian = make_user("librarian")
        self.church = self.librarian.organisation
        self.client.force_login(self.librarian)

    def test_the_counts_match_the_library_filters(self):
        make_score(organisation=self.church, title="A", voicing="", language="Latin")
        make_score(organisation=self.church, title="B", voicing="", language="")
        make_score(organisation=self.church, title="C", voicing="SATB", language="English")
        response = self.client.get("/library/completeness/")
        self.assertContains(response, "2 scores with no voicing")
        self.assertContains(response, "1 score with no language")
        for param, count in (("voicing", 2), ("language", 1)):
            with self.subTest(param=param):
                listed = self.client.get("/library/", {param: "unspecified"}).context["scores"]
                self.assertEqual(len(listed), count)

    def test_nothing_missing_reads_as_done(self):
        make_score(organisation=self.church, title="C", voicing="SATB", language="English")
        response = self.client.get("/library/completeness/")
        for done in ("Every score has a voicing.", "Every score has a language.",
                     "Every score planned as a motet or antiphon has its text."):
            with self.subTest(done=done):
                self.assertContains(response, done)

    def test_the_library_links_to_it(self):
        self.assertContains(self.client.get("/library/"), 'href="/library/completeness/"')


class HymnalModelTests(TestCase):
    def test_a_hymnal_is_named_with_its_code(self):
        from .models import Hymnal

        hymnal = Hymnal.objects.create(organisation=make_organisation(), name="New English Hymnal", short_name="NEH")
        self.assertEqual(str(hymnal), "New English Hymnal (NEH)")
        self.assertEqual((hymnal.copies_owned, hymnal.archived), (0, False))

    def test_a_code_is_used_once_in_each_church(self):
        from django.db import IntegrityError, transaction

        from .models import Hymnal

        ours, theirs = make_organisation(), make_organisation("St Elsewhere")
        Hymnal.objects.create(organisation=ours, name="New English Hymnal", short_name="NEH")
        Hymnal.objects.create(organisation=theirs, name="New English Hymnal", short_name="NEH")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Hymnal.objects.create(organisation=ours, name="Another", short_name="NEH")

    def test_archived_hymnals_come_last(self):
        from .models import Hymnal

        church = make_organisation()
        Hymnal.objects.create(organisation=church, name="Ancient and Modern", short_name="AM", archived=True)
        Hymnal.objects.create(organisation=church, name="New English Hymnal", short_name="NEH")
        self.assertEqual([h.short_name for h in Hymnal.objects.for_organisation(church)], ["NEH", "AM"])


class HymnalListTests(TestCase):
    def setUp(self):
        from .models import Hymnal

        self.viewer = make_user("viewer")
        church = self.viewer.organisation
        Hymnal.objects.create(organisation=church, name="New English Hymnal", short_name="NEH", copies_owned=40,
                              filing_location="Vestry")
        Hymnal.objects.create(organisation=church, name="Ancient and Modern", short_name="AM", archived=True)
        Hymnal.objects.create(organisation=make_organisation("St Elsewhere"), name="Theirs", short_name="TH")
        self.client.force_login(self.viewer)

    def test_everyone_sees_the_churchs_hymnals_archived_apart(self):
        response = self.client.get("/library/hymnals/")
        self.assertEqual([h.short_name for h in response.context["in_use"]], ["NEH"])
        self.assertEqual([h.short_name for h in response.context["archived"]], ["AM"])
        self.assertContains(response, "40 copies · Vestry")
        self.assertNotContains(response, "Theirs")

    def test_the_library_links_to_it_for_everyone(self):
        self.assertContains(self.client.get("/library/"), 'href="/library/hymnals/"')


class HymnalFormTests(TestCase):
    def setUp(self):
        from .models import Hymnal

        self.librarian = make_user("librarian")
        self.church = self.librarian.organisation
        self.neh = Hymnal.objects.create(organisation=self.church, name="New English Hymnal", short_name="NEH")
        self.client.force_login(self.librarian)

    def test_a_librarian_adds_a_hymnal(self):
        from .models import Hymnal

        response = self.client.post("/library/hymnals/add/", {
            "name": "Catholic Hymns Old and New", "short_name": "CHON", "copies_owned": 30, "filing_location": "",
        })
        self.assertRedirects(response, "/library/hymnals/")
        self.assertEqual(Hymnal.objects.get(short_name="CHON").organisation, self.church)

    def test_a_code_already_used_is_refused_whatever_its_case(self):
        data = {"name": "Another", "short_name": "neh", "copies_owned": 0}
        response = self.client.post("/library/hymnals/add/", data)
        self.assertContains(response, "You already have a hymnal with the code neh.")

    def test_editing_keeps_its_own_code_and_can_archive(self):
        response = self.client.post(f"/library/hymnals/{self.neh.pk}/edit/", {
            "name": "New English Hymnal", "short_name": "NEH", "copies_owned": 12, "archived": "on",
        })
        self.assertRedirects(response, "/library/hymnals/")
        self.neh.refresh_from_db()
        self.assertEqual((self.neh.copies_owned, self.neh.archived), (12, True))

    def test_a_viewer_can_look_but_not_change(self):
        self.client.force_login(make_user("viewer", organisation=self.church))
        self.assertNotContains(self.client.get("/library/hymnals/"), "/library/hymnals/add/")
        self.assertEqual(self.client.get("/library/hymnals/add/").status_code, 403)
        self.assertEqual(self.client.get(f"/library/hymnals/{self.neh.pk}/edit/").status_code, 403)

    def test_deleting_asks_first_and_suggests_archiving(self):
        from .models import Hymnal

        url = f"/library/hymnals/{self.neh.pk}/delete/"
        self.assertContains(self.client.get(url), "archiving it on its edit page")
        self.assertRedirects(self.client.post(url), "/library/hymnals/")
        self.assertFalse(Hymnal.objects.filter(pk=self.neh.pk).exists())
        # Back to the page once it's gone: the list, with a message.
        self.assertRedirects(self.client.get(url), "/library/hymnals/")


class HymnEntryTests(TestCase):
    def setUp(self):
        from .models import Hymnal

        self.church = make_organisation()
        self.neh = Hymnal.objects.create(organisation=self.church, name="New English Hymnal", short_name="NEH")

    def test_a_new_number_makes_its_entry_and_hymn_once(self):
        from .models import Hymn, HymnEntry

        entry = HymnEntry.find_or_make(self.neh, " 53 ")
        self.assertEqual(str(entry), "NEH 53")
        self.assertEqual((entry.organisation, entry.hymn.organisation), (self.church, self.church))
        self.assertEqual(HymnEntry.find_or_make(self.neh, "53"), entry)
        self.assertEqual(Hymn.objects.count(), 1)

    def test_a_number_is_used_once_in_a_hymnal(self):
        from django.db import IntegrityError, transaction

        from .models import Hymn, HymnEntry

        HymnEntry.find_or_make(self.neh, "53")
        hymn = Hymn.objects.create(organisation=self.church)
        with self.assertRaises(IntegrityError), transaction.atomic():
            HymnEntry.objects.create(organisation=self.church, hymn=hymn, hymnal=self.neh, number="53")

    def test_a_hymnal_with_entries_is_kept_and_archiving_suggested(self):
        from .models import Hymnal, HymnEntry

        HymnEntry.find_or_make(self.neh, "53")
        self.client.force_login(make_user("librarian", organisation=self.church))
        response = self.client.post(f"/library/hymnals/{self.neh.pk}/delete/", follow=True)
        self.assertContains(response, "has hymns recorded from it, so it&#x27;s kept. Archive it instead")
        self.assertTrue(Hymnal.objects.filter(pk=self.neh.pk).exists())


class HymnLastSungTests(TestCase):
    def test_the_same_hymn_from_two_books_counts_once_and_only_when_sung(self):
        from datetime import timedelta

        from django.utils import timezone

        from planning.models import RolePiece, Service, ServiceRole

        from .models import Hymn, Hymnal, HymnEntry

        church = make_organisation()
        neh = Hymnal.objects.create(organisation=church, name="New English Hymnal", short_name="NEH")
        chon = Hymnal.objects.create(organisation=church, name="Catholic Hymns Old and New", short_name="CHON")
        in_neh = HymnEntry.find_or_make(neh, "53")
        # The same hymn printed in a second book.
        in_chon = HymnEntry.objects.create(organisation=church, hymn=in_neh.hymn, hymnal=chon, number="211")
        never = HymnEntry.find_or_make(neh, "1")
        today = timezone.localdate()
        term = make_term(
            organisation=church, start_date=today - timedelta(days=60), end_date=today + timedelta(days=60)
        )

        def plan(entry, days_ago, confirmed=True):
            service = Service.objects.create(term=term, date=today - timedelta(days=days_ago), service_type="Mass")
            slot = ServiceRole.objects.create(service=service, role_name="Hymn")
            RolePiece.objects.create(service_role=slot, hymn_entry=entry, is_confirmed=confirmed)
            return service.date

        plan(in_neh, 21)
        latest = plan(in_chon, 7)
        plan(in_neh, 3, confirmed=False)  # proposed, not sung
        plan(in_chon, -7)  # confirmed, but still to come
        hymns = {hymn.pk: hymn.last_sung for hymn in Hymn.objects.for_organisation(church).with_last_sung()}
        self.assertEqual(hymns[in_neh.hymn_id], latest)
        self.assertIsNone(hymns[never.hymn_id])


class HymnalPageTests(TestCase):
    def test_its_hymns_are_listed_in_the_books_number_order(self):
        from .models import Hymnal, HymnEntry

        viewer = make_user("viewer")
        neh = Hymnal.objects.create(organisation=viewer.organisation, name="New English Hymnal", short_name="NEH")
        for number in ("10", "123a", "9", "123"):
            HymnEntry.find_or_make(neh, number)
        first = HymnEntry.objects.get(number="9").hymn
        first.first_line = "Praise to the Holiest"
        first.save()
        self.client.force_login(viewer)
        response = self.client.get(f"/library/hymnals/{neh.pk}/")
        self.assertEqual([entry.number for entry in response.context["entries"]], ["9", "10", "123", "123a"])
        self.assertContains(response, "Praise to the Holiest")
        self.assertContains(response, "No first line yet", count=3)
        self.assertContains(self.client.get("/library/hymnals/"), f'href="/library/hymnals/{neh.pk}/"')


class HymnPageTests(TestCase):
    def setUp(self):
        from .models import Hymnal, HymnEntry

        self.viewer = make_user("viewer")
        church = self.viewer.organisation
        neh = Hymnal.objects.create(organisation=church, name="New English Hymnal", short_name="NEH")
        self.entry = HymnEntry.find_or_make(neh, "53")
        self.hymn = self.entry.hymn
        self.client.force_login(self.viewer)

    def test_a_hymn_with_no_first_line_is_headed_by_where_its_printed(self):
        response = self.client.get(f"/library/hymns/{self.hymn.pk}/")
        self.assertContains(response, "<h1>NEH 53</h1>", html=True)
        self.assertContains(response, "Not sung yet")

    def test_its_details_and_tags_show_when_given(self):
        from ordo.models import LiturgicalSeason

        self.hymn.first_line = "Ye choirs of new Jerusalem"
        self.hymn.text = "First verse\nSecond line"
        self.hymn.text_credit = "Words: the choir's own translation"
        self.hymn.save()
        self.hymn.suited_seasons.add(LiturgicalSeason.objects.create(name="Easter"))
        response = self.client.get(f"/library/hymns/{self.hymn.pk}/")
        self.assertContains(response, "<h1>Ye choirs of new Jerusalem</h1>", html=True)
        self.assertContains(response, "First verse<br>Second line")
        self.assertContains(response, "<dd>Easter</dd>", html=True)
        hymnal_page = self.client.get(f"/library/hymnals/{self.entry.hymnal_id}/")
        self.assertContains(hymnal_page, f'href="/library/hymns/{self.hymn.pk}/"')


class HymnFormTests(TestCase):
    def setUp(self):
        from .models import Hymnal, HymnEntry

        self.librarian = make_user("librarian")
        self.church = self.librarian.organisation
        neh = Hymnal.objects.create(organisation=self.church, name="New English Hymnal", short_name="NEH")
        self.hymn = HymnEntry.find_or_make(neh, "53").hymn
        self.url = f"/library/hymns/{self.hymn.pk}/edit/"
        self.client.force_login(self.librarian)

    def test_a_librarian_adds_details_and_tags(self):
        use = make_use_type("Communion", organisation=self.church)
        response = self.client.post(self.url, {
            "first_line": "Ye choirs of new Jerusalem", "text": "", "text_credit": "", "suited_use_types": [use.pk],
        })
        self.assertRedirects(response, f"/library/hymns/{self.hymn.pk}/")
        self.hymn.refresh_from_db()
        self.assertEqual(self.hymn.first_line, "Ye choirs of new Jerusalem")
        self.assertEqual(list(self.hymn.suited_use_types.all()), [use])

    def test_another_churchs_use_type_isnt_accepted(self):
        theirs = make_use_type("Theirs", organisation=make_organisation("St Elsewhere"))
        response = self.client.post(self.url, {"first_line": "", "suited_use_types": [theirs.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.hymn.suited_use_types.exists())

    def test_saving_goes_back_to_where_the_edit_began(self):
        response = self.client.post(self.url, {"first_line": "", "next": "/services/4/"})
        self.assertRedirects(response, "/services/4/", fetch_redirect_response=False)

    def test_a_viewer_cant_edit(self):
        self.client.force_login(make_user("viewer", organisation=self.church))
        self.assertEqual(self.client.get(self.url).status_code, 403)


class SameHymnTests(TestCase):
    def setUp(self):
        from .models import Hymnal, HymnEntry

        self.church = make_organisation()
        neh = Hymnal.objects.create(organisation=self.church, name="New English Hymnal", short_name="NEH")
        chon = Hymnal.objects.create(organisation=self.church, name="Catholic Hymns Old and New", short_name="CHON")
        self.in_neh = HymnEntry.find_or_make(neh, "53")
        self.in_chon = HymnEntry.find_or_make(chon, "211")
        self.hymn, self.other = self.in_neh.hymn, self.in_chon.hymn
        self.hymn.first_line = "Praise to the Holiest in the height"
        self.hymn.save()
        self.other.first_line = "praise to the holiest, in the height!"
        self.other.text = "The words"
        self.other.save()

    def test_a_matching_first_line_is_a_possible_match_whatever_its_punctuation(self):
        self.assertEqual(self.hymn.possible_matches(), [self.other])

    def test_once_said_not_to_be_the_same_it_isnt_asked_again_either_way(self):
        self.hymn.not_same_as.add(self.other)
        self.assertEqual(self.hymn.possible_matches(), [])
        self.assertEqual(self.other.possible_matches(), [])

    def test_another_churchs_hymn_is_never_a_match(self):
        from .models import Hymn

        Hymn.objects.create(organisation=make_organisation("St Elsewhere"), first_line=self.hymn.first_line)
        self.assertEqual(self.hymn.possible_matches(), [self.other])

    def test_absorbing_keeps_every_entry_and_its_history(self):
        from datetime import date

        from planning.models import RolePiece, Service, ServiceRole

        from .models import Hymn

        service = Service.objects.create(term=make_term(organisation=self.church), date=date(2026, 1, 11),
                                         service_type="Sung Mass")
        piece = RolePiece.objects.create(service_role=ServiceRole.objects.create(service=service, role_name="Hymn"),
                                         hymn_entry=self.in_chon, is_confirmed=True)
        self.hymn.absorb(self.other)
        self.assertFalse(Hymn.objects.filter(pk=self.other.pk).exists())
        self.assertEqual(sorted(str(e) for e in self.hymn.entries.select_related("hymnal")), ["CHON 211", "NEH 53"])
        self.assertEqual(self.hymn.text, "The words")
        piece.refresh_from_db()
        self.assertEqual(piece.hymn_entry.hymn, self.hymn)

    def ask(self, answer, role="librarian"):
        self.client.force_login(make_user(role, organisation=self.church))
        return self.client.post(f"/library/hymns/{self.hymn.pk}/same-as/{self.other.pk}/", {"answer": answer})

    def test_the_hymns_page_asks_those_who_edit_the_library(self):
        self.client.force_login(make_user("librarian", organisation=self.church))
        self.assertContains(self.client.get(f"/library/hymns/{self.hymn.pk}/"), "Is this the same hymn as CHON 211?")
        self.client.force_login(make_user("viewer", organisation=self.church))
        self.assertNotContains(self.client.get(f"/library/hymns/{self.hymn.pk}/"), "Is this the same hymn")

    def test_yes_joins_them(self):
        from .models import Hymn

        self.assertRedirects(self.ask("same"), f"/library/hymns/{self.hymn.pk}/")
        self.assertFalse(Hymn.objects.filter(pk=self.other.pk).exists())

    def test_no_is_remembered(self):
        self.ask("different")
        self.assertEqual(self.hymn.possible_matches(), [])

    def test_a_viewer_cant_answer(self):
        self.assertEqual(self.ask("same", role="viewer").status_code, 403)


class HymnCompletenessTests(TestCase):
    def test_hymns_missing_details_are_listed_by_where_theyre_printed(self):
        from ordo.models import LiturgicalSeason

        from .models import Hymnal, HymnEntry

        librarian = make_user("librarian")
        neh = Hymnal.objects.create(organisation=librarian.organisation, name="New English Hymnal", short_name="NEH")
        bare = HymnEntry.find_or_make(neh, "53").hymn
        full = HymnEntry.find_or_make(neh, "1").hymn
        full.first_line, full.text = "A first line", "The words"
        full.save()
        full.suited_seasons.add(LiturgicalSeason.objects.create(name="Advent"))
        self.client.force_login(librarian)
        response = self.client.get("/library/completeness/")
        self.assertContains(response, "1 hymn with no first line:")
        self.assertContains(response, "1 hymn with no words:")
        self.assertContains(response, f'href="/library/hymns/{bare.pk}/edit/?next=/library/completeness/">NEH 53</a>')

    def test_a_church_with_no_hymns_has_no_hymn_section(self):
        self.client.force_login(make_user("librarian"))
        self.assertNotContains(self.client.get("/library/completeness/"), "<h2>Hymns</h2>", html=True)


class HymnMetreTests(TestCase):
    def test_a_metre_is_stored_written_one_way_and_shown(self):
        from .models import Hymnal, HymnEntry

        librarian = make_user("librarian")
        neh = Hymnal.objects.create(organisation=librarian.organisation, name="New English Hymnal", short_name="NEH")
        hymn = HymnEntry.find_or_make(neh, "53").hymn
        self.client.force_login(librarian)
        self.client.post(f"/library/hymns/{hymn.pk}/edit/", {"first_line": "", "metre": "lm"})
        hymn.refresh_from_db()
        self.assertEqual(hymn.metre, "8.8.8.8")
        self.assertContains(self.client.get(f"/library/hymns/{hymn.pk}/"), "<dd>8.8.8.8</dd>", html=True)


class TuneTests(TestCase):
    def setUp(self):
        from .models import Tune

        self.librarian = make_user("librarian")
        self.church = self.librarian.organisation
        self.repton = Tune.objects.create(organisation=self.church, name="Repton", metre="86 88 6")
        self.client.force_login(self.librarian)

    def test_a_tunes_metre_is_written_one_way(self):
        self.assertEqual(self.repton.metre, "8.6.8.8.6")

    def test_a_librarian_adds_a_tune_and_everyone_sees_the_list(self):
        from .models import Tune

        response = self.client.post("/library/tunes/add/", {"name": "Westminster Abbey", "metre": "87 87 87"})
        self.assertRedirects(response, "/library/tunes/")
        self.assertEqual(Tune.objects.get(name="Westminster Abbey").metre, "8.7.8.7.8.7")
        self.client.force_login(make_user("viewer", organisation=self.church))
        response = self.client.get("/library/tunes/")
        self.assertContains(response, "Westminster Abbey")
        self.assertNotContains(response, "/library/tunes/add/")
        self.assertContains(self.client.get("/library/hymnals/"), 'href="/library/tunes/"')

    def test_a_name_already_used_is_refused_whatever_its_case(self):
        response = self.client.post("/library/tunes/add/", {"name": "repton", "metre": ""})
        self.assertContains(response, "You already have a tune called repton.")


class EntryTuneTests(TestCase):
    def setUp(self):
        from .models import Hymnal, HymnEntry, Tune

        self.librarian = make_user("librarian")
        self.church = self.librarian.organisation
        self.neh = Hymnal.objects.create(organisation=self.church, name="New English Hymnal", short_name="NEH")
        self.repton = Tune.objects.create(organisation=self.church, name="Repton", metre="86 88 6")
        self.entry = HymnEntry.find_or_make(self.neh, "353")
        self.client.force_login(self.librarian)

    def test_a_tune_is_numbered_by_the_lowest_hymn_printed_with_it(self):
        from .models import HymnEntry

        self.assertIsNone(self.repton.number_in(self.neh))
        for number in ("353", "115"):
            entry = HymnEntry.find_or_make(self.neh, number)
            entry.tune = self.repton
            entry.save()
        self.assertEqual(self.repton.number_in(self.neh), "115")

    def test_a_librarian_sets_an_entrys_tune_from_the_churchs_own(self):
        from .models import Tune

        url = f"/library/hymn-entries/{self.entry.pk}/tune/"
        response = self.client.post(url, {"tune": self.repton.pk})
        self.assertRedirects(response, f"/library/hymns/{self.entry.hymn_id}/")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.tune, self.repton)
        self.assertContains(self.client.get(f"/library/hymns/{self.entry.hymn_id}/"), "NEH 353</a>, to Repton")
        theirs = Tune.objects.create(organisation=make_organisation("St Elsewhere"), name="Theirs")
        self.client.post(url, {"tune": theirs.pk})
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.tune, self.repton)
