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

    def test_ordering_falls_back_to_title_when_suitability_ties(self):
        response = self.client.get("/library/")
        titles = [score.title for score in response.context["scores"]]
        self.assertEqual(titles, sorted(titles))
