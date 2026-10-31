"""
Test helpers for the things a church owns directly: terms, scores, slot
templates and use types. Each takes the same arguments as the model and
fills in the organisation, the shared "Test Church" unless a test passes
its own. Services, slots, pieces, notices and comments need no helper:
they take their organisation from what they belong to.

These live at project level, not in accounts/testing.py, so that the
accounts app doesn't import the apps that depend on it.
"""

from datetime import date

from accounts.testing import make_organisation
from library.models import Score
from ordo.models import UseType
from planning.models import SlotTemplate, Term


def make_term(*, organisation=None, **fields):
    fields = {
        "name": "Test Term",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 3, 31),
        "calendar_use": "current",
        **fields,
    }
    return Term.objects.create(organisation=organisation or make_organisation(), **fields)


def make_score(*, organisation=None, **fields):
    fields = {"title": "Test Anthem", "composer_surname": "Test Composer", **fields}
    return Score.objects.create(organisation=organisation or make_organisation(), **fields)


def template_form_data(name, new=(), template=None, remove=(), order=None):
    """What the template form posts: its name and its slots as formset
    rows. A template's existing slots come first, kept unless named in
    remove, then a row for each new name. order, if given, lists the
    names in the order wanted."""
    existing = list(template.template_slots.all()) if template else []
    names = [slot.name for slot in existing] + list(new)
    data = {
        "name": name,
        "slots-TOTAL_FORMS": str(len(names)), "slots-INITIAL_FORMS": str(len(existing)),
        "slots-MIN_NUM_FORMS": "0", "slots-MAX_NUM_FORMS": "1000",
    }
    for index, slot_name in enumerate(names):
        prefix = f"slots-{index}-"
        data[prefix + "name"] = slot_name
        data[prefix + "kind"] = existing[index].kind if index < len(existing) else ""
        data[prefix + "proper_part"] = existing[index].proper_part if index < len(existing) else ""
        data[prefix + "ORDER"] = str((order.index(slot_name) if order else index) + 1)
        if index < len(existing):
            data[prefix + "id"] = str(existing[index].pk)
            if slot_name in remove:
                data[prefix + "DELETE"] = "on"
    return data


def make_slot_template(*, organisation=None, **fields):
    """A template whose slots are written as lines of text, one each."""
    fields = {"name": "Benediction", "slot_names": "O salutaris\nTantum ergo", **fields}
    template = SlotTemplate.objects.create(organisation=organisation or make_organisation(), **fields)
    template.set_slots(template.names_from_text(template.slot_names))
    return template


def make_use_type(name, *, organisation=None):
    return UseType.objects.create(name=name, organisation=organisation or make_organisation())
