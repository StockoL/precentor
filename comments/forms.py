from django import forms

from .models import Comment


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]  # noqa
        widgets = {  # noqa
            "body": forms.Textarea(attrs={"rows": 1, "placeholder": "Add a comment…"}),
        }
