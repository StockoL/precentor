"""Form fields for choosing occasions, labelled so the two forms of the
calendar can be told apart."""

from django import forms


class OccasionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.choice_label


class OccasionMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.choice_label
