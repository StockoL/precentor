"""Form fields for choosing occasions, labelled so the two forms of the
calendar can be told apart. Each option also carries its form as
data-calendar-use, so a page script can show only one form's days."""

from django import forms


class CalendarUseOptionsMixin:
    def create_option(self, name, value, *args, **kwargs):
        option = super().create_option(name, value, *args, **kwargs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-calendar-use"] = instance.calendar_use
        return option


class OccasionSelect(CalendarUseOptionsMixin, forms.Select):
    pass


class OccasionSelectMultiple(CalendarUseOptionsMixin, forms.SelectMultiple):
    pass


class OccasionChoiceField(forms.ModelChoiceField):
    widget = OccasionSelect

    def label_from_instance(self, obj):
        return obj.choice_label


class OccasionMultipleChoiceField(forms.ModelMultipleChoiceField):
    widget = OccasionSelectMultiple

    def label_from_instance(self, obj):
        return obj.choice_label
