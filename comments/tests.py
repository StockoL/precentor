from datetime import date, datetime
from datetime import timezone as dt_timezone

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


class InboxPageTests(TestCase):
    def setUp(self):
        from planning.models import Service

        self.user = User.objects.create_user(username="conductor", password="testpass123")
        self.client.force_login(self.user)
        self.term = Term.objects.create(
            name="Lent", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass"
        )

    def test_each_subject_links_to_its_page(self):
        from library.models import Score
        from planning.models import RolePiece, ServiceRole

        role = ServiceRole.objects.create(service=self.service, role_name="Motet")
        piece = RolePiece.objects.create(
            service_role=role, score=Score.objects.create(title="Ave", composer_surname="Byrd")
        )
        for target in (self.term, self.service, piece):
            Comment.objects.create(author=self.user, body="Query", target=target)
        response = self.client.get("/comments/inbox/")
        self.assertContains(response, f'<a href="{self.term.get_absolute_url()}">Lent</a>', html=True)
        self.assertContains(response, f'href="{self.service.get_absolute_url()}"')
        # A piece links to its service page, jumping to the piece's row.
        self.assertContains(
            response, f'href="{self.service.get_absolute_url()}#piece-row-{piece.pk}"'
        )

    def test_shows_how_many_replies(self):
        question = Comment.objects.create(author=self.user, body="Copies?", target=self.term)
        for body in ("Twelve", "Thanks"):
            Comment.objects.create(author=self.user, body=body, target=self.term, parent=question)
        Comment.objects.create(author=self.user, body="Other", target=self.service)
        response = self.client.get("/comments/inbox/")
        self.assertContains(response, "2 replies")
        self.assertContains(response, "No replies yet")

    def test_query_count_does_not_grow_with_more_comments(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def queries():
            self.client.get("/comments/inbox/")  # warm-up: session and caches
            with CaptureQueriesContext(connection) as captured:
                self.client.get("/comments/inbox/")
            return len(captured)

        # One query per kind of subject, so start with both kinds present.
        Comment.objects.create(author=self.user, body="On the term", target=self.term)
        Comment.objects.create(author=self.user, body="On the service", target=self.service)
        two = queries()
        for n in range(4):
            Comment.objects.create(author=self.user, body=f"Term {n}", target=self.term)
            Comment.objects.create(author=self.user, body=f"Service {n}", target=self.service)
        self.assertEqual(queries(), two)


class AddCommentViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conductor", password="testpass123"
        )
        self.term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
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

    def test_comment_form_label_says_comment(self):
        response = self.client.get(self.term.get_absolute_url())
        self.assertContains(response, "Comment:</label>")
        self.assertNotContains(response, "Body:")

    def test_inbox_shows_times_in_uk_local_time(self):
        # Stored in UTC; shown in Europe/London, which is on BST (UTC+1)
        # in July, so noon UTC must read as 13:00.
        comment = Comment.objects.create(
            author=self.user, body="Summer query", target=self.term
        )
        Comment.objects.filter(pk=comment.pk).update(
            created_at=datetime(2026, 7, 1, 12, 0, tzinfo=dt_timezone.utc)
        )
        response = self.client.get("/comments/inbox/")
        self.assertContains(response, "Wed 1 Jul 2026, 13:00")

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

    def test_delete_closed_comment(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term, is_open=False
        )
        self.client.post(f"/comments/{comment.pk}/delete/")
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_delete_open_comment_rejected(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term
        )
        self.client.post(f"/comments/{comment.pk}/delete/")
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())

    def test_delete_comment_ajax_returns_removal_fragment(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term, is_open=False
        )

        response = self.client.post(
            f"/comments/{comment.pk}/delete/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        fragments = response.json()["fragments"]
        self.assertEqual(fragments, {f"comment-{comment.pk}": ""})

    def test_delete_open_comment_ajax_returns_400(self):
        comment = Comment.objects.create(
            author=self.user, body="A query", target=self.term
        )

        response = self.client.post(
            f"/comments/{comment.pk}/delete/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())
