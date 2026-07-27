from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from precentor_project.utils import ajax_or_redirect

from .forms import CommentForm
from .models import Comment


def _comment_form_id(parent_id):
    return f"reply-form-{parent_id}" if parent_id else "add-comment-form"


def _render_comment_form(request, form, content_type_id, object_id, parent_id):
    return render_to_string(
        "comments/_comment_form.html",
        {
            "form": form,
            "content_type_id": content_type_id,
            "object_id": object_id,
            "parent_id": parent_id,
        },
        request=request,
    )


@login_required
@require_POST
def add_comment(request, content_type_id, object_id):
    content_type = get_object_or_404(ContentType, pk=content_type_id)
    target = get_object_or_404(content_type.model_class(), pk=object_id)
    form = CommentForm(request.POST)
    parent_id = request.POST.get("parent_id") or None
    redirect_url = request.META.get("HTTP_REFERER", "/")

    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.target = target
        comment.parent_id = parent_id
        try:
            comment.full_clean()
            comment.save()
        except ValidationError as e:
            form.add_error(None, e.messages)
            fragments = {
                _comment_form_id(parent_id): _render_comment_form(
                    request, form, content_type_id, object_id, parent_id
                ),
            }
            return ajax_or_redirect(
                request, fragments, redirect_url,
                error_message=" ".join(e.messages), status=400,
            )

        # Card context shared by both success branches below.
        ctx = {
            "content_type_id": content_type_id,
            "object_id": object_id,
            "comment_form": CommentForm(),
        }
        if parent_id:
            # Re-render the whole parent card — comment--{{ state }} is a
            # class on its outer <div>, so only a full swap can flip it
            # (open -> open_with_replies). This already contains the new
            # reply, so no separate reply fragment is needed or returned.
            fragments = {
                f"comment-{parent_id}": render_to_string(
                    "comments/_comment_card.html", {"comment": comment.parent, **ctx}, request=request
                ),
            }
        else:
            fragments = {
                f"comment-{comment.pk}": render_to_string(
                    "comments/_comment_card.html", {"comment": comment, **ctx}, request=request
                ),
            }
        return ajax_or_redirect(request, fragments, redirect_url)

    fragments = {
        _comment_form_id(parent_id): _render_comment_form(
            request, form, content_type_id, object_id, parent_id
        ),
    }
    return ajax_or_redirect(
        request, fragments, redirect_url,
        error_message="Couldn't add that comment — please check the form.", status=400,
    )


@login_required
@require_POST
def toggle_close(request, comment_pk):
    comment = get_object_or_404(Comment, pk=comment_pk)
    comment.is_open = not comment.is_open
    comment.save()

    # content_type_id/object_id are already stored fields on Comment — no
    # need for ContentType.objects.get_for_model(), a redundant query.
    fragments = {
        f"comment-{comment.pk}": render_to_string(
            "comments/_comment_card.html",
            {
                "comment": comment,
                "content_type_id": comment.content_type_id,
                "object_id": comment.object_id,
                "comment_form": CommentForm(),
            },
            request=request,
        ),
    }
    return ajax_or_redirect(request, fragments, request.META.get("HTTP_REFERER", "/"))


class CommentInboxView(LoginRequiredMixin, ListView):
    model = Comment
    context_object_name = "comments"
    template_name = "comments/inbox.html"

    def get_queryset(self):
        return Comment.objects.filter(is_open=True).order_by("-created_at")
