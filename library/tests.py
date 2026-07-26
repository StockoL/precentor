from django.contrib.auth import get_user_model
from django.test import TestCase

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
