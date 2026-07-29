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
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
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
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
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

    def test_add_comment_ajax_top_level_returns_new_comment_fragment(self):
        response = self.client.post(
            f"/comments/add/{self.content_type_id}/{self.term.pk}/",
            {"body": "A query"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        comment = Comment.objects.get()
        fragments = response.json()["fragments"]
        self.assertEqual(list(fragments.keys()), [f"comment-{comment.pk}"])
        self.assertIn("A query", fragments[f"comment-{comment.pk}"])

    def test_add_comment_ajax_reply_returns_parent_card_fragment(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term
        )

        response = self.client.post(
            f"/comments/add/{self.content_type_id}/{self.term.pk}/",
            {"body": "A reply", "parent_id": comment.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        fragments = response.json()["fragments"]
        self.assertEqual(list(fragments.keys()), [f"comment-{comment.pk}"])
        self.assertIn("comment--open_with_replies", fragments[f"comment-{comment.pk}"])
        self.assertIn("A reply", fragments[f"comment-{comment.pk}"])

    def test_add_comment_ajax_nested_reply_returns_400_with_form_errors(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term
        )
        reply = Comment.objects.create(
            author=self.user, body="A reply", target=self.term, parent=comment
        )

        response = self.client.post(
            f"/comments/add/{self.content_type_id}/{self.term.pk}/",
            {"body": "A nested reply", "parent_id": reply.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Comment.objects.count(), 2)
        fragments = response.json()["fragments"]
        self.assertIn(f"reply-form-{reply.pk}", fragments)
        self.assertIn("errorlist", fragments[f"reply-form-{reply.pk}"])

    def test_add_comment_ajax_invalid_returns_400_with_form_fragment(self):
        response = self.client.post(
            f"/comments/add/{self.content_type_id}/{self.term.pk}/",
            {"body": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Comment.objects.count(), 0)
        fragments = response.json()["fragments"]
        self.assertIn("add-comment-form", fragments)
        self.assertIn("errorlist", fragments["add-comment-form"])

    def test_add_comment_non_ajax_invalid_sets_error_message(self):
        response = self.client.post(
            f"/comments/add/{self.content_type_id}/{self.term.pk}/",
            {"body": ""},
            follow=True,
        )

        self.assertEqual(Comment.objects.count(), 0)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn("Couldn't add that comment", str(messages[0]))

    def test_toggle_close_ajax_returns_updated_card(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term
        )

        response = self.client.post(
            f"/comments/{comment.pk}/toggle-close/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        fragments = response.json()["fragments"]
        self.assertEqual(list(fragments.keys()), [f"comment-{comment.pk}"])
        self.assertIn("comment--closed", fragments[f"comment-{comment.pk}"])
        self.assertIn("Re-open", fragments[f"comment-{comment.pk}"])
