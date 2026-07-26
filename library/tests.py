from django.test import TestCase

from .models import Score


class ScoreFilterTests(TestCase):
    def setUp(self):
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
