from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models


class Comment(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    body = models.TextField()
    is_open = models.BooleanField(default=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]  # noqa

    def __str__(self):
        return f"Comment by {self.author} on {self.target}"

    def clean(self):
        """Enforce flat threading: a reply cannot itself be replied to."""
        if self.parent_id and self.parent.parent_id:
            raise ValidationError(
                "Replies cannot themselves be replied to — comments are flat, one level deep."
            )

    @property
    def state(self):
        """UI colour-coding state: open / open_with_replies / closed."""
        if not self.is_open:
            return "closed"
        if self.replies.exists():
            return "open_with_replies"
        return "open"
