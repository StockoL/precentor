from django import forms


class NativeDateInput(forms.DateInput):
    """
    The browser's own date picker. <input type="date"> only accepts an
    ISO value (YYYY-MM-DD), but Django renders a date in the locale's
    first input format, which for en-gb is DD/MM/YYYY and would leave
    every edit form's date blank. Pinning the format fixes that for any
    locale.

    Lives at project level because more than one app uses it, and the
    apps' dependencies only run one way.
    """

    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")
