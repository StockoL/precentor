from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import CALENDAR_USE_CHOICES, NATIONAL_CALENDAR_CHOICES, occasion_for_date


@login_required
def occasion_lookup(request):
    """
    JSON endpoint behind the service form's suggestions: given a date, a
    form of the calendar and the church's national calendar, returns the
    occasions kept that day, the celebration first, for the conductor to
    choose from. Nothing is chosen for them.

    The national calendar comes from the page (the service form reads it
    from Settings), so ordo needn't depend on core; an unknown one falls
    back to the General Roman Calendar.
    """
    try:
        target_date = date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        return JsonResponse({"occasions": []})

    calendar_use = request.GET.get("calendar_use", "")
    if calendar_use not in dict(CALENDAR_USE_CHOICES):
        return JsonResponse({"occasions": []})

    national_calendar = request.GET.get("national_calendar", "")
    if national_calendar not in dict(NATIONAL_CALENDAR_CHOICES):
        national_calendar = "general_roman"

    matches = occasion_for_date(target_date, calendar_use, national_calendar)
    return JsonResponse(
        {
            "occasions": [
                {"id": occasion.pk, "name": occasion.name, "colour": occasion.colour}
                for occasion in matches
            ]
        }
    )
