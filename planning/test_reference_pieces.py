from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.testing import make_organisation, make_user
from precentor_project.testing import make_score, make_term

from .models import RolePiece, Service, ServiceRole


class ReferencePieceTestMixin:
    def setUp(self):
        self.conductor = make_user("conductor")
        self.church = self.conductor.organisation
        term = make_term(organisation=self.church)
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        self.slot = ServiceRole.objects.create(service=self.service, role_name="Entrance hymn")
        self.score = make_score(organisation=self.church, title="Ave verum corpus", composer_surname="Byrd")


class ScoreOrReferenceTests(ReferencePieceTestMixin, TestCase):
    def test_a_reference_is_a_piece_of_its_own(self):
        piece = RolePiece.objects.create(service_role=self.slot, reference="  NEH 123 ")
        self.assertEqual((piece.score, piece.reference, piece.title), (None, "NEH 123", "NEH 123"))

    def test_a_score_is_titled_as_the_score(self):
        piece = RolePiece.objects.create(service_role=self.slot, score=self.score)
        self.assertEqual(piece.title, str(self.score))

    def test_the_database_refuses_neither_or_both(self):
        for fields in ({}, {"score": self.score, "reference": "NEH 123"}):
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                RolePiece.objects.create(service_role=self.slot, **fields)

    def test_the_rule_gives_its_message_before_the_database_is_asked(self):
        message = "Choose one: a score, a hymn number or a reference."
        for fields in ({}, {"score": self.score, "reference": "NEH 123"}):
            with self.subTest(fields=fields), self.assertRaisesMessage(ValidationError, message):
                RolePiece(service_role=self.slot, **fields).validate_constraints()
        RolePiece(service_role=self.slot, reference="NEH 123").validate_constraints()


class ReferenceShownTests(ReferencePieceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.hymn = RolePiece.objects.create(service_role=self.slot, reference="NEH 123", is_confirmed=True)
        motet = ServiceRole.objects.create(service=self.service, role_name="Offertory motet")
        RolePiece.objects.create(service_role=motet, score=self.score, is_confirmed=True)
        self.client.force_login(self.conductor)

    def test_the_service_page_shows_the_reference(self):
        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, "NEH 123")

    def test_the_music_list_gives_references_and_scores_alike(self):
        rows = self.service.music_list_rows()
        self.assertEqual([(row["role_name"], row["kind"], row["proper_part"], row["pieces"]) for row in rows], [
            ("Entrance hymn", "hymn", "", ["NEH 123"]),
            ("Offertory motet", "motet", "", [str(self.score)]),
        ])
        response = self.client.get(f"/terms/{self.service.term.pk}/music-list/")
        self.assertContains(response, "NEH 123")
        self.assertContains(response, '<dt data-kind="hymn">Entrance hymn</dt>', html=True)

    def test_a_reference_piece_is_named_by_its_reference(self):
        self.assertEqual(str(self.hymn), "NEH 123 (confirmed)")


class ProposeReferenceTests(ReferencePieceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.conductor)
        self.url = f"/roles/{self.slot.pk}/pieces/add/"

    def test_a_reference_can_be_proposed_without_javascript(self):
        response = self.client.post(self.url, {"score": "", "reference": "NEH 123"})
        self.assertRedirects(response, self.service.get_absolute_url())
        self.assertEqual(RolePiece.objects.get().title, "NEH 123")

    def test_neither_or_both_is_refused_with_one_message(self):
        for data in ({"score": "", "reference": ""}, {"score": self.score.pk, "reference": "NEH 123"}):
            with self.subTest(data=data):
                response = self.client.post(self.url, data)
                self.assertContains(response, "Choose one: a score, a hymn number or a reference.", count=1)
        self.assertFalse(RolePiece.objects.exists())

    def test_a_hymn_slot_asks_for_the_reference_first(self):
        form = self.client.get(self.url).context["form"]
        self.assertEqual(list(form.fields), ["reference", "score"])
        self.assertEqual(form.fields["score"].label, "Or a score from the library")

    def test_other_slots_ask_for_a_score_first(self):
        motet = ServiceRole.objects.create(service=self.service, role_name="Offertory motet")
        form = self.client.get(f"/roles/{motet.pk}/pieces/add/").context["form"]
        self.assertEqual(list(form.fields), ["score", "reference"])
        self.assertEqual(form.fields["reference"].label, "Or type a reference")


class MusicListArrangementTests(ReferencePieceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        pieces = (("Introit", "Ad te levavi"), ("Kyrie", "Missa de Angelis"), ("Communion", "Dominus dabit"))
        for name, reference in pieces:
            slot = ServiceRole.objects.create(service=self.service, role_name=name)
            RolePiece.objects.create(service_role=slot, reference=reference, is_confirmed=True)
        RolePiece.objects.create(service_role=self.slot, reference="NEH 1", is_confirmed=True)

    def names(self, groups):
        return [[row["role_name"] for row in group] for group in groups]

    def test_in_service_order_is_one_group(self):
        self.assertEqual(self.names(self.service.music_list_groups()), [
            ["Entrance hymn", "Introit", "Kyrie", "Communion"],
        ])

    def test_propers_beside_the_rest_is_two_groups_each_in_order(self):
        self.assertEqual(self.names(self.service.music_list_groups(arrangement="propers_beside")), [
            ["Introit", "Communion"],
            ["Entrance hymn", "Kyrie"],
        ])

    def test_a_service_with_no_propers_has_one_group_either_way(self):
        self.service.roles.filter(kind="proper").delete()
        self.assertEqual(len(self.service.music_list_groups(arrangement="propers_beside")), 1)

    def test_the_music_list_follows_the_setting(self):
        from core.models import SiteConfig

        config = SiteConfig.of(self.church)
        config.music_list_arrangement = "propers_beside"
        config.save()
        self.client.force_login(self.conductor)
        response = self.client.get(f"/terms/{self.service.term.pk}/music-list/")
        self.assertEqual(response.content.decode().count("<dl>"), 2)


class HymnPieceTests(ReferencePieceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from library.models import Hymnal, HymnEntry

        neh = Hymnal.objects.create(organisation=self.church, name="New English Hymnal", short_name="NEH")
        self.entry = HymnEntry.find_or_make(neh, "53")

    def test_a_hymn_piece_is_titled_by_book_and_number(self):
        piece = RolePiece.objects.create(service_role=self.slot, hymn_entry=self.entry, is_confirmed=True)
        self.assertEqual((piece.title, str(piece)), ("NEH 53", "NEH 53 (confirmed)"))
        self.assertEqual(self.service.music_list_rows()[0]["pieces"], ["NEH 53"])

    def test_only_one_of_the_three(self):
        both = ({"hymn_entry": self.entry, "reference": "NEH 53"}, {"hymn_entry": self.entry, "score": self.score})
        for fields in both:
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                RolePiece.objects.create(service_role=self.slot, **fields)

    def test_the_pew_sheet_prints_the_number(self):
        RolePiece.objects.create(service_role=self.slot, hymn_entry=self.entry, is_confirmed=True)
        self.client.force_login(self.conductor)
        response = self.client.get(f"/services/{self.service.pk}/sheet/")
        self.assertContains(response, '<p class="pew-sheet__piece">NEH 53</p>', html=True)


class ProposeHymnTests(ReferencePieceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from library.models import Hymnal

        self.neh = Hymnal.objects.create(organisation=self.church, name="New English Hymnal", short_name="NEH")
        self.chon = Hymnal.objects.create(
            organisation=self.church, name="Catholic Hymns Old and New", short_name="CHON"
        )
        Hymnal.objects.create(organisation=self.church, name="Hymns Ancient and Modern", short_name="AM", archived=True)
        self.client.force_login(self.conductor)
        self.url = f"/roles/{self.slot.pk}/pieces/add/"

    def test_a_hymn_slot_asks_for_book_and_number_first_from_books_in_use(self):
        form = self.client.get(self.url).context["form"]
        self.assertEqual(list(form.fields), ["hymnal", "number", "reference", "score"])
        self.assertEqual(sorted(h.short_name for h in form.fields["hymnal"].queryset), ["CHON", "NEH"])
        self.assertIn("not in a hymnal", form.fields["reference"].help_text)

    def test_a_new_number_becomes_a_hymn_and_the_book_is_remembered(self):
        response = self.client.post(self.url, {"hymnal": self.chon.pk, "number": "211", "reference": "", "score": ""})
        self.assertRedirects(response, self.service.get_absolute_url())
        self.assertEqual(RolePiece.objects.get().title, "CHON 211")
        self.assertEqual(self.client.get(self.url).context["form"].fields["hymnal"].initial, self.chon)

    def test_a_number_and_a_reference_together_are_refused(self):
        response = self.client.post(self.url, {"hymnal": self.neh.pk, "number": "53", "reference": "Psalm 23"})
        self.assertContains(response, "Choose one: a score, a hymn number or a reference.", count=1)
        self.assertFalse(RolePiece.objects.exists())

    def test_another_churchs_or_an_archived_hymnal_is_refused(self):
        from library.models import Hymnal

        theirs = Hymnal.objects.create(organisation=make_organisation("St Elsewhere"), name="Theirs", short_name="TH")
        archived = Hymnal.objects.get(short_name="AM")
        for hymnal in (theirs, archived):
            with self.subTest(hymnal=hymnal.short_name):
                self.client.post(self.url, {"hymnal": hymnal.pk, "number": "1"})
                self.assertFalse(RolePiece.objects.exists())

    def test_other_slots_and_churches_with_no_hymnals_are_unchanged(self):
        motet = ServiceRole.objects.create(service=self.service, role_name="Offertory motet")
        self.assertNotIn("hymnal", self.client.get(f"/roles/{motet.pk}/pieces/add/").context["form"].fields)


class FirstLinePromptTests(ReferencePieceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from library.models import Hymnal, HymnEntry

        neh = Hymnal.objects.create(organisation=self.church, name="New English Hymnal", short_name="NEH")
        self.entry = HymnEntry.find_or_make(neh, "53")
        self.piece = RolePiece.objects.create(service_role=self.slot, hymn_entry=self.entry)

    def test_a_hymn_with_no_first_line_asks_for_one_and_comes_back(self):
        self.client.force_login(self.conductor)
        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, "No first line recorded yet.")
        back = f"/services/{self.service.pk}/%23piece-row-{self.piece.pk}"
        self.assertContains(response, f"/library/hymns/{self.entry.hymn_id}/edit/?next={back}")

    def test_once_it_has_one_or_for_a_viewer_nothing_is_asked(self):
        self.client.force_login(make_user("viewer", organisation=self.church))
        self.assertNotContains(self.client.get(self.service.get_absolute_url()), "No first line recorded yet.")
        self.entry.hymn.first_line = "Praise to the Holiest"
        self.entry.hymn.save()
        self.client.force_login(self.conductor)
        self.assertNotContains(self.client.get(self.service.get_absolute_url()), "No first line recorded yet.")


class TuneChoiceTests(ReferencePieceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from library.models import Hymnal, HymnEntry, Tune

        self.neh = Hymnal.objects.create(organisation=self.church, name="New English Hymnal", short_name="NEH")

        def tune(name, metre):
            return Tune.objects.create(organisation=self.church, name=name, metre=metre)

        self.usual, self.printed, self.elsewhere, self.other_metre = (
            tune("Usual", "LM"), tune("Printed", "88 88"), tune("Elsewhere", "LM"), tune("Other metre", "CM"),
        )
        self.entry = HymnEntry.find_or_make(self.neh, "53")
        self.entry.tune = self.usual
        self.entry.save()
        printed_with = HymnEntry.find_or_make(self.neh, "115")
        printed_with.tune = self.printed
        printed_with.save()
        self.piece = RolePiece.objects.create(service_role=self.slot, hymn_entry=self.entry)

    def test_the_usual_tune_then_same_metre_in_the_book_then_the_rest(self):
        groups = [(label, [tune.name for tune in tunes]) for label, tunes in self.piece.tune_choices()]
        self.assertEqual(groups, [
            ("Its usual tune", ["Usual"]),
            ("Same metre, in NEH", ["Printed"]),
            ("Other tunes", ["Elsewhere", "Other metre"]),
        ])

    def test_only_a_hymn_has_tune_choices_or_a_tune(self):
        reference = RolePiece.objects.create(service_role=self.slot, reference="Psalm 23")
        self.assertEqual(reference.tune_choices(), [])
        with self.assertRaises(IntegrityError), transaction.atomic():
            RolePiece.objects.create(service_role=self.slot, reference="Psalm 23", tune=self.usual)

    def choose(self, tune, role="conductor"):
        user = self.conductor if role == "conductor" else make_user(role, organisation=self.church)
        self.client.force_login(user)
        return self.client.post(f"/pieces/{self.piece.pk}/tune/", {"tune": tune.pk})

    def test_a_conductor_chooses_another_tune_and_back_to_the_usual(self):
        self.assertRedirects(self.choose(self.printed), self.service.get_absolute_url())
        self.piece.refresh_from_db()
        self.assertEqual((self.piece.tune, self.piece.sung_tune), (self.printed, self.printed))
        self.assertContains(self.client.get(self.service.get_absolute_url()), "NEH 53, to Printed")
        self.choose(self.usual)
        self.piece.refresh_from_db()
        self.assertEqual((self.piece.tune, self.piece.sung_tune), (None, self.usual))

    def test_another_churchs_tune_or_a_librarian_is_refused(self):
        from library.models import Tune

        theirs = Tune.objects.create(organisation=make_organisation("St Elsewhere"), name="Theirs", metre="LM")
        self.choose(theirs)
        self.assertEqual(self.choose(self.printed, role="librarian").status_code, 403)
        self.piece.refresh_from_db()
        self.assertIsNone(self.piece.tune)

    def test_the_pew_sheet_numbers_another_tune_from_the_same_book(self):
        self.piece.is_confirmed = True
        self.piece.save()
        self.assertEqual(self.piece.sheet_title, "NEH 53")
        self.piece.tune = self.printed
        self.piece.save()
        self.assertEqual(self.piece.sheet_title, "NEH 53, tune NEH 115")
        self.piece.tune = self.elsewhere
        self.piece.save()
        self.assertEqual(self.piece.sheet_title, "NEH 53, tune Elsewhere")
        self.client.force_login(self.conductor)
        response = self.client.get(f"/services/{self.service.pk}/sheet/")
        self.assertContains(response, '<p class="pew-sheet__piece">NEH 53, tune Elsewhere</p>', html=True)
