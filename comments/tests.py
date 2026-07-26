from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
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


class AddCommentViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conductor", password="testpass123"
        )
        self.term = Term.objects.create(
            name="Test Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
        )
        self.client.login(username="conductor", password="testpass123")
        self.content_type_id = ContentType.objects.get_for_model(Term).id

    def test_add_comment_via_view(self):
        self.client.post(
            f"/comments/add/{self.content_type_id}/{self.term.pk}/", {"body": "A query"}
        )
        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(Comment.objects.first().target, self.term)

    def test_nested_reply_rejected_via_view(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term
        )
        reply = Comment.objects.create(
            author=self.user, body="A reply", target=self.term, parent=comment
        )
        self.client.post(
            f"/comments/add/{self.content_type_id}/{self.term.pk}/",
            {"body": "A nested reply", "parent_id": reply.pk},
        )
        self.assertEqual(
            Comment.objects.count(), 2
        )  # rejected: no third comment created

    def test_toggle_close(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term
        )
        self.client.post(f"/comments/{comment.pk}/toggle-close/")
        comment.refresh_from_db()
        self.assertFalse(comment.is_open)

    def test_inbox_shows_only_open_comments(self):
        Comment.objects.create(author=self.user, body="Open one", target=self.term)
        Comment.objects.create(
            author=self.user, body="Closed one", target=self.term, is_open=False
        )
        response = self.client.get("/comments/inbox/")
        self.assertContains(response, "Open one")
        self.assertNotContains(response, "Closed one")
