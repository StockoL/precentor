from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import CALENDAR_USE_CHOICES, occasion_for_date


@login_required
def occasion_lookup(request):
    """
    JSON endpoint behind the Service date field's auto-suggest: given a
    date/calendar_use, returns every matching LiturgicalOccasion
    (zero, one, or more) for the conductor to confirm — never silently
    picked or applied by the caller.
    """
    try:
        target_date = date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        return JsonResponse({"occasions": []})

    calendar_use = request.GET.get("calendar_use", "")
    if calendar_use not in dict(CALENDAR_USE_CHOICES):
        return JsonResponse({"occasions": []})

    matches = occasion_for_date(target_date, calendar_use)
    return JsonResponse(
        {
            "occasions": [
                {"id": occasion.pk, "name": occasion.name, "colour": occasion.colour}
                for occasion in matches
            ]
        }
    )
