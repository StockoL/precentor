from .forms import CommentForm


def attach_reply_form(comment):
    """
    Gives a single comment its own CommentForm instance with a distinct
    auto_id. Every comment on a page renders its own reply form, so
    Django's default auto_id ("id_body") would otherwise be duplicated
    once per comment — invalid HTML, and it breaks getElementById-based
    lookups — the same class of bug fixed for the per-role score picker
    forms via RolePieceForm's auto_id.
    """
    comment.comment_form = CommentForm(auto_id=f"id_comment_{comment.pk}_%s")
    return comment


def attach_reply_forms(comments):
    """Materializes `comments` into a list, each with its own reply form."""
    return [attach_reply_form(comment) for comment in comments]
