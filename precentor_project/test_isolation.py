"""
The isolation test: one church can't reach another's data by any route.

Two complete churches are built, A and B. Every piece of B's text carries
the marker B-ONLY, so a leak shows up wherever it appears. Each check
starts from what exists, not from a hand-kept list, so it fails, and says
what to add, when a new model or route arrives without being covered.
"""

from datetime import date

from django.apps import apps
from django.test import TestCase

from accounts.models import Invitation, User
from accounts.organisations import create_organisation
from comments.models import Comment
from core.models import SiteConfig
from library.models import Score
from ordo.models import UseType
from planning.models import RolePiece, Service, ServiceRole, SlotTemplate, Term, TermMarker

PASSWORD = "testpass123"


def build_church(marker):
    """A church with one of everything a church can own, each carrying the
    marker in its text. Returns the rows by name."""
    church = create_organisation(f"{marker} church")
    settings = SiteConfig.of(church)
    settings.church_name = f"{marker} church"
    settings.set_crest(b"crest", "image/png")
    settings.save()
    owner = User.objects.create_user(
        email=f"{marker.lower()}-owner@example.com", password=PASSWORD, name=f"{marker} owner",
        organisation=church, role="conductor", is_owner=True,
    )
    member = User.objects.create_user(
        email=f"{marker.lower()}-member@example.com", password=PASSWORD, name=f"{marker} member",
        organisation=church, role="librarian",
    )
    former = User.objects.create_user(
        email=f"{marker.lower()}-former@example.com", password=PASSWORD, name=f"{marker} former",
        organisation=church, role="viewer", is_active=False,
    )
    score = Score.objects.create(
        organisation=church, title=f"{marker} score", composer_surname=f"{marker} composer",
        voicing="SATB", language="Latin",
    )
    use_type = UseType.objects.create(organisation=church, name=f"{marker} use")
    score.suited_use_types.add(use_type)
    template = SlotTemplate.objects.create(organisation=church, name=f"{marker} template", slot_names="Introit")
    term = Term.objects.create(
        organisation=church, name=f"{marker} term", start_date=date(2026, 11, 29),
        end_date=date(2026, 12, 24), calendar_use="current",
    )
    service = Service.objects.create(term=term, date=date(2026, 12, 6), service_type=f"{marker} service")
    slot = ServiceRole.objects.create(service=service, role_name=f"{marker} slot")
    piece = RolePiece.objects.create(service_role=slot, score=score)
    marker_row = TermMarker.objects.create(term=term, date=date(2026, 12, 1), text=f"{marker} notice")
    comment = Comment.objects.create(author=owner, target=service, body=f"{marker} comment")
    invitation, _ = Invitation.make(organisation=church, role="viewer", created_by=owner, note=f"{marker} invitation")
    return {
        "church": church, "settings": settings, "owner": owner, "member": member, "former": former,
        "score": score, "use_type": use_type, "template": template, "term": term, "service": service,
        "slot": slot, "piece": piece, "marker": marker_row, "comment": comment, "invitation": invitation,
    }


def tenant_models():
    """Every model that holds a church's own data: those with an
    organisation field."""
    return {
        model for model in apps.get_models()
        if any(field.name == "organisation" for field in model._meta.get_fields())
    }


class TwoChurchesMixin:
    @classmethod
    def setUpTestData(cls):
        cls.a = build_church("A-ONLY")
        cls.b = build_church("B-ONLY")


class EveryChurchModelIsCoveredTests(TwoChurchesMixin, TestCase):
    def test_the_builder_makes_a_row_of_every_model_that_holds_church_data(self):
        made = {type(row) for row in self.b.values()}
        missing = sorted(model.__name__ for model in tenant_models() - made)
        self.assertEqual(missing, [], "Add these to build_church() in the isolation test so they're checked")

    def test_each_church_has_a_row_of_every_one(self):
        for model in tenant_models():
            with self.subTest(model=model.__name__):
                for church in (self.a, self.b):
                    rows = model.objects.filter(organisation=church["church"])
                    self.assertTrue(rows.exists())
