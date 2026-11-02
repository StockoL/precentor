from datetime import date
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from core.models import SiteConfig
from precentor_project.testing import make_slot_template, make_term

from .models import RolePiece, Service, ServiceRole


class CheckCopiedDataTests(TestCase):
    """The check run on merge day: the old hymns, psalm and template text
    against what the migrations copied them into."""

    def setUp(self):
        self.term = make_term()
        self.church = self.term.organisation
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 4), service_type="Sung Mass", hymns="NEH 1, NEH 2", psalm="Psalm 98"
        )

    def copy(self, hymns=("NEH 1", "NEH 2"), psalm="Psalm 98"):
        """What the migration would have made."""
        slot = ServiceRole.objects.create(service=self.service, role_name="Hymns")
        for hymn in hymns:
            RolePiece.objects.create(service_role=slot, reference=hymn, is_confirmed=True)
        if psalm:
            psalm_slot = ServiceRole.objects.create(service=self.service, role_name="Psalm")
            RolePiece.objects.create(service_role=psalm_slot, reference=psalm, is_confirmed=True)

    def run_check(self):
        out = StringIO()
        call_command("check_copied_data", stdout=out)
        return out.getvalue()

    def test_all_copied_passes(self):
        self.copy()
        make_slot_template(organisation=self.church)
        self.assertIn("Everything was copied", self.run_check())

    def test_a_missing_hymn_or_psalm_fails(self):
        self.copy(hymns=["NEH 1"], psalm="")
        with self.assertRaisesMessage(CommandError, "2 problem(s)"):
            self.run_check()

    def test_a_template_whose_rows_differ_fails(self):
        self.copy()
        template = make_slot_template(organisation=self.church)
        template.template_slots.filter(name="Tantum ergo").delete()
        with self.assertRaisesMessage(CommandError, "1 problem(s)"):
            self.run_check()

    def test_a_church_that_hid_hymns_is_named(self):
        self.copy()
        config = SiteConfig.of(self.church)
        config.show_hymns_psalm = False
        config.save()
        self.assertIn("hid hymns and the psalm on its music list, and 1 of its services", self.run_check())

    def test_it_changes_nothing(self):
        self.copy()
        before = (RolePiece.objects.count(), ServiceRole.objects.count())
        self.run_check()
        self.assertEqual((RolePiece.objects.count(), ServiceRole.objects.count()), before)
