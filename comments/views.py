from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .forms import CommentForm
from .models import Comment


@login_required
@require_POST
def add_comment(request, content_type_id, object_id):
    content_type = get_object_or_404(ContentType, pk=content_type_id)
    target = get_object_or_404(content_type.model_class(), pk=object_id)
    form = CommentForm(request.POST)

    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.target = target
        comment.parent_id = request.POST.get("parent_id") or None
        try:
            comment.full_clean()
            comment.save()
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))

    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_POST
def toggle_close(request, comment_pk):
    comment = get_object_or_404(Comment, pk=comment_pk)
    comment.is_open = not comment.is_open
    comment.save()
    return redirect(request.META.get("HTTP_REFERER", "/"))


class CommentInboxView(LoginRequiredMixin, ListView):
    model = Comment
    context_object_name = "comments"
    template_name = "comments/inbox.html"

    def get_queryset(self):
        return Comment.objects.filter(is_open=True).order_by("-created_at")
