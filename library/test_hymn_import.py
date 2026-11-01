from datetime import date

from django.test import TestCase

from accounts.testing import make_organisation

from .models import Hymn, Hymnal, HymnEntry, HymnImport, Tune


class HymnImportBatchTests(TestCase):
    """Removing a pending hymnal import undoes it: entries it added, blanks
    it filled and tunes it added, but nothing that's been used since."""

    def setUp(self):
        self.church = make_organisation()
        self.neh = Hymnal.objects.create(organisation=self.church, name="New English Hymnal", short_name="NEH")
        self.batch = HymnImport.objects.create(
            organisation=self.church, hymnal=self.neh, original_filename="neh.csv"
        )

    def added(self, number):
        entry = HymnEntry.find_or_make(self.neh, number)
        entry.import_batch = self.batch
        entry.save()
        return entry

    def test_removing_deletes_what_it_added(self):
        self.added("1")
        self.added("2")
        self.assertEqual(self.batch.remove(), (2, 0))
        self.assertFalse(HymnEntry.objects.exists())
        self.assertFalse(Hymn.objects.exists())
        self.assertFalse(HymnImport.objects.exists())

    def test_a_sung_entry_is_kept_and_unlinked(self):
        from planning.models import RolePiece, Service, ServiceRole
        from precentor_project.testing import make_term

        entry = self.added("1")
        term = make_term(organisation=self.church)
        service = Service.objects.create(term=term, date=date(2026, 1, 4), service_type="Sung Mass")
        RolePiece.objects.create(
            service_role=ServiceRole.objects.create(service=service, role_name="Entrance hymn"), hymn_entry=entry
        )
        self.assertEqual(self.batch.remove(), (0, 1))
        entry.refresh_from_db()
        self.assertIsNone(entry.import_batch)

    def test_a_hymn_also_in_another_book_stays(self):
        entry = self.added("1")
        other = Hymnal.objects.create(organisation=self.church, name="Catholic Hymns", short_name="CH")
        HymnEntry.objects.create(organisation=self.church, hymn=entry.hymn, hymnal=other, number="7")
        self.batch.remove()
        self.assertTrue(Hymn.objects.filter(pk=entry.hymn.pk).exists())

    def test_blanks_it_filled_are_emptied_unless_changed_since(self):
        entry = HymnEntry.find_or_make(self.neh, "5")
        other = HymnEntry.find_or_make(self.neh, "6")
        tune = Tune.objects.create(organisation=self.church, name="Winchester New")
        entry.hymn.first_line = "On Jordan's bank"
        entry.hymn.save()
        entry.tune = tune
        entry.save()
        other.hymn.first_line = "Changed by hand"
        other.hymn.save()
        self.batch.changes = {"filled": [
            ["Hymn", entry.hymn.pk, "first_line", "On Jordan's bank"],
            ["HymnEntry", entry.pk, "tune_id", tune.pk],
            ["Hymn", other.hymn.pk, "first_line", "From the file"],
        ]}
        self.batch.save()
        self.batch.remove()
        entry.refresh_from_db()
        entry.hymn.refresh_from_db()
        other.hymn.refresh_from_db()
        self.assertEqual((entry.hymn.first_line, entry.tune_id), ("", None))
        self.assertEqual(other.hymn.first_line, "Changed by hand")

    def test_tunes_it_added_go_unless_used(self):
        unused = Tune.objects.create(organisation=self.church, name="Unused")
        used = Tune.objects.create(organisation=self.church, name="Used")
        HymnEntry.objects.filter(pk=HymnEntry.find_or_make(self.neh, "9").pk).update(tune=used)
        self.batch.changes = {"tunes": [unused.pk, used.pk]}
        self.batch.save()
        self.batch.remove()
        self.assertEqual(list(Tune.objects.values_list("name", flat=True)), ["Used"])

    def test_a_kept_import_cant_be_removed(self):
        self.batch.keep()
        with self.assertRaises(ValueError):
            self.batch.remove()
