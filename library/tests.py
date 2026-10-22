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
                      "Suitable occasions"):
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
        for legend in ("Identity", "Forces", "Library", "Liturgical use", "Notes"):
            with self.subTest(legend=legend):
                self.assertContains(response, f"<legend>{legend}</legend>", html=True)
        # Every field in the form class appears in the hand-written layout.
        for field in ScoreForm.Meta.fields:
            with self.subTest(field=field):
                self.assertContains(response, f'name="{field}"')


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
        })
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
        config = SiteConfig.get_solo()
        config.national_calendar = "wales"
        config.save()

    def labels(self, form):
        return [label for _, label in form.fields["suited_occasions"].choices]

    def test_only_the_churchs_calendar_is_offered(self):
        from .forms import ScoreForm

        labels = self.labels(ScoreForm())
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


class FillScoreOrganisationTests(TestCase):
    """The fill-in migration, run against today's models while the column
    can still be empty. These go when the column becomes required."""

    def run_migration(self):
        import importlib

        from django.apps import apps

        importlib.import_module("library.migrations.0016_fill_score_organisation").give_scores_an_organisation(apps, None)

    def test_scores_without_one_join_the_organisation(self):
        church = make_organisation("St Cecilia's")
        Score.objects.create(title="Ave verum", composer_surname="Byrd")
        self.run_migration()
        self.assertEqual(Score.objects.get().organisation, church)

    def test_no_scores_means_no_organisation_is_made(self):
        from accounts.models import Organisation

        self.run_migration()
        self.assertFalse(Organisation.objects.exists())
