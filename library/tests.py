from django.contrib.auth import get_user_model
from django.test import TestCase

from ordo.models import LiturgicalOccasion

from .models import Score

User = get_user_model()


class ScoreFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conductor", password="testpass123"
        )
        self.client.login(username="conductor", password="testpass123")
        Score.objects.create(
            title="Ave Verum", composer="Byrd", language="Latin", tenor_parts=1
        )
        Score.objects.create(
            title="O Taste and See",
            composer="Vaughan Williams",
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
        self.occasion = LiturgicalOccasion.objects.create(
            name="Advent Sunday 4", tradition="cofe"
        )
        self.other_occasion = LiturgicalOccasion.objects.create(
            name="Trinity 7", tradition="cofe"
        )
        self.untagged = Score.objects.create(
            title="Untagged Anthem", composer="Nobody"
        )
        self.matching = Score.objects.create(
            title="Zzz Matching Anthem", composer="Somebody"
        )
        self.matching.suited_occasions.add(self.occasion)
        self.non_matching = Score.objects.create(
            title="Aaa Non-Matching Anthem", composer="Someone Else"
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
