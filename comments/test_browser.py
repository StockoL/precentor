from datetime import date

from planning.models import Term
from precentor_project.test_browser import PlaywrightTestCase

from .models import Comment


class CommentThreadBrowserTest(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        self.login_as_conductor()
        self.term = Term.objects.create(
            name="Browser Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
        )

    def test_add_comment_reply_and_toggle_close_without_reload(self):
        self.page.goto(f"/terms/{self.term.pk}/")
        self.page.wait_for_selector("#comment-list-empty")

        self.page.evaluate("window.__browser_test_marker = true")

        # Post a top-level comment — appended into #comment-list.
        self.page.fill("#add-comment-form textarea", "A query")
        self.page.click("#add-comment-form button[type=submit]")
        self.page.wait_for_selector("#comment-list .comment")

        assert self.page.evaluate("window.__browser_test_marker") is True, (
            "marker was cleared — page reloaded instead of using fetch()"
        )

        comment = Comment.objects.get()
        card = f"#comment-{comment.pk}"
        assert self.page.is_visible(card)
        assert "comment--open" in self.page.get_attribute(card, "class")
        self.page.wait_for_selector(".toast--success")
        assert "Comment posted" in self.page.inner_text(".toast--success")

        # Reply to it — the parent card is re-rendered in place, flipping
        # its state from open to open_with_replies (comment--{{ state }}
        # is a class on the card's own outer element, so this can only be
        # observed via a full card swap, not a partial DOM patch).
        self.page.fill(f"{card} textarea", "A reply")
        self.page.click(f"{card} button:has-text('Reply')")
        self.page.wait_for_function(
            f"document.querySelector('{card}')?.className.includes('comment--open_with_replies')"
        )
        assert "A reply" in self.page.inner_text(card)

        # Close it — card re-renders again, button label flips to Re-open.
        self.page.click(f"{card} button:has-text('Close')")
        self.page.wait_for_function(
            f"document.querySelector('{card}')?.className.includes('comment--closed')"
        )
        assert "Re-open" in self.page.inner_text(card)

        comment.refresh_from_db()
        assert comment.is_open is False
        assert comment.replies.count() == 1
