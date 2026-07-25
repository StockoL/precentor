from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from planning.models import Term

from .models import Comment

User = get_user_model()


class CommentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conductor", password="testpass123"
        )
        self.term = Term.objects.create(
            name="Test Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
        )

    def test_comment_links_to_arbitrary_target(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term
        )
        self.assertEqual(comment.target, self.term)

    def test_state_open_with_no_replies(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term
        )
        self.assertEqual(comment.state, "open")

    def test_state_open_with_replies(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term
        )
        Comment.objects.create(
            author=self.user, body="A reply", target=self.term, parent=comment
        )
        self.assertEqual(comment.state, "open_with_replies")

    def test_state_closed(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term, is_open=False
        )
        self.assertEqual(comment.state, "closed")

    def test_nested_reply_rejected(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term
        )
        reply = Comment.objects.create(
            author=self.user, body="A reply", target=self.term, parent=comment
        )
        nested = Comment(
            author=self.user, body="A nested reply", target=self.term, parent=reply
        )
        with self.assertRaises(ValidationError):
            nested.full_clean()
