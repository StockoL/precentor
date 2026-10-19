from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from ordo.models import LiturgicalOccasion

from .models import Score

User = get_user_model()


class ScoreFormLabelTests(TestCase):
    """Labels come from explicit verbose_name, not field names."""

    def test_score_form_labels_read_naturally(self):
        self.client.force_login(
            User.objects.create_superuser(username="admin", password="testpass123")
        )
        response = self.client.get("/library/add/")
        for label in ("Composer&#x27;s other names", "Sopranos", "Basses",
                      "Duration (minutes)", "Suitable uses", "Suitable seasons",
                      "Suitable occasions"):
            with self.subTest(label=label):
                self.assertContains(response, f"{label}:</label>")
        for old in ("Soprano parts", "Duration minutes", "Suited use types"):
            with self.subTest(old=old):
                self.assertNotContains(response, old)


class ScoreEditorTests(TestCase):
    def test_editor_can_be_recorded_from_the_form(self):
        self.client.force_login(
            User.objects.create_superuser(username="admin", password="testpass123")
        )
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

        from planning.models import Service, Term

        # The same "today" as with_last_sung, which uses the UK time zone.
        self.today = timezone.localdate()
        self.term = Term.objects.create(
            name="Term",
            start_date=self.today - timedelta(days=365),
            end_date=self.today + timedelta(days=365),
            calendar_use="current",
        )
        self.Service = Service
        self.score = Score.objects.create(title="Ave verum", composer_surname="Byrd")

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


class ScoreDetailListTests(TestCase):
    def test_facts_are_a_description_list(self):
        self.client.force_login(
            User.objects.create_superuser(username="admin", password="testpass123")
        )
        score = Score.objects.create(
            title="Ave verum", composer_surname="Byrd", voicing="SATB", language="Latin"
        )
        response = self.client.get(score.get_absolute_url())
        self.assertContains(response, '<dl class="detail-list">', count=2)
        self.assertContains(response, "<dt>Voicing</dt>", html=True)
        self.assertContains(response, "<dd>SATB</dd>", html=True)
        self.assertNotContains(response, "<p>Voicing:")


class LibraryEmptyStateTests(TestCase):
    def setUp(self):
        self.client.force_login(
            User.objects.create_superuser(username="admin", password="testpass123")
        )

    def test_empty_library_offers_the_first_score(self):
        response = self.client.get("/library/")
        self.assertContains(response, "The library is empty.")
        self.assertContains(response, ">Add the first score</a>")

    def test_filters_with_no_matches_offer_to_clear_them(self):
        Score.objects.create(title="Ave verum", composer_surname="Byrd", language="Latin")
        response = self.client.get("/library/?language=German")
        self.assertContains(response, "No scores match these filters.")
        self.assertContains(response, ">Clear filters</a>")
        self.assertNotContains(response, "The library is empty.")


class ScoreComposerTests(TestCase):
    def test_surname_only_displays_as_surname(self):
        score = Score.objects.create(title="Ave Verum", composer_surname="Byrd")
        self.assertEqual(score.composer, "Byrd")

    def test_surname_and_other_names_displays_combined(self):
        score = Score.objects.create(
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
            Score.objects.create(title=title, composer_surname=surname, composer_other_names=other)
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
        )
        score.full_clean()  # should not raise


class ScoreFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conductor", password="testpass123"
        )
        self.client.login(username="conductor", password="testpass123")
        Score.objects.create(
            title="Ave Verum", composer_surname="Byrd", language="Latin", tenor_parts=1
        )
        Score.objects.create(
            title="O Taste and See",
            composer_surname="Vaughan Williams",
            language="English",
            tenor_parts=0,
        )

    def test_filter_by_language(self):
        response = self.client.get("/library/", {"language": "Latin"})
        self.assertContains(response, "Ave Verum")
        self.assertNotContains(response, "O Taste and See")

    def test_filter_by_voice_part(self):
        response = self.client.get("/library/", {"voice_part": "tenor"})
        self.assertContains(response, "Ave Verum")
        self.assertNotContains(response, "O Taste and See")


class ScoreSuitabilityRankingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conductor", password="testpass123"
        )
        self.client.login(username="conductor", password="testpass123")
        self.occasion = LiturgicalOccasion.objects.create(name="Advent Sunday 4")
        self.other_occasion = LiturgicalOccasion.objects.create(
            name="Ordinary Time 7"
        )
        self.untagged = Score.objects.create(
            title="Untagged Anthem", composer_surname="Nobody"
        )
        self.matching = Score.objects.create(
            title="Zzz Matching Anthem", composer_surname="Somebody"
        )
        self.matching.suited_occasions.add(self.occasion)
        self.non_matching = Score.objects.create(
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

    def test_ordering_falls_back_to_title_when_suitability_ties(self):
        response = self.client.get("/library/")
        titles = [score.title for score in response.context["scores"]]
        self.assertEqual(titles, sorted(titles))
