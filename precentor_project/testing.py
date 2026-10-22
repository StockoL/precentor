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


def make_slot_template(*, organisation=None, **fields):
    fields = {"name": "Benediction", "slot_names": "O salutaris\nTantum ergo", **fields}
    return SlotTemplate.objects.create(organisation=organisation or make_organisation(), **fields)


def make_use_type(name, *, organisation=None):
    return UseType.objects.create(name=name, organisation=organisation or make_organisation())
