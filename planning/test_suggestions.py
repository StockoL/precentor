from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.testing import make_organisation
from ordo.models import LiturgicalOccasion, LiturgicalSeason
from precentor_project.testing import make_score, make_term, make_use_type

from .models import RolePiece, Service, ServiceRole
from .suggestions import facts_for


class SuggestionTestMixin:
    def setUp(self):
        self.church = make_organisation()
        today = timezone.localdate()
        self.term = make_term(organisation=self.church, start_date=today - timedelta(days=200),
                              end_date=today + timedelta(days=60))
        self.advent = LiturgicalSeason.objects.create(name="Advent")
        self.sunday = LiturgicalOccasion.objects.create(name="Advent Sunday 1", season=self.advent)
        self.service = Service.objects.create(term=self.term, date=today + timedelta(days=7),
                                              service_type="Sung Mass", occasion=self.sunday)
        self.slot = ServiceRole.objects.create(service=self.service, role_name="Communion")

    def score(self, title, **tags):
        score = make_score(organisation=self.church, title=title, composer_surname="Byrd")
        for name, values in tags.items():
            getattr(score, name).set(values)
        return score

    def sing(self, score, days_ago):
        past = Service.objects.create(term=self.term, date=timezone.localdate() - timedelta(days=days_ago),
                                      service_type="Sung Mass")
        slot = ServiceRole.objects.create(service=past, role_name="Motet")
        RolePiece.objects.create(service_role=slot, score=score, is_confirmed=True)

    def facts(self, window=8):
        return {facts.score.title: facts for facts in facts_for(self.service, window)}


class FactsTests(SuggestionTestMixin, TestCase):
    def test_tags_for_the_occasion_and_season_are_named(self):
        self.score("Rorate caeli", suited_occasions=[self.sunday])
        self.score("Vigilate", suited_seasons=[self.advent])
        self.score("Untagged")
        facts = self.facts()
        self.assertEqual((facts["Rorate caeli"].occasion, facts["Rorate caeli"].season), ("Advent Sunday 1", ""))
        self.assertEqual((facts["Vigilate"].occasion, facts["Vigilate"].season), ("", "Advent"))
        self.assertEqual((facts["Untagged"].occasion, facts["Untagged"].season), ("", ""))

    def test_another_occasion_of_the_service_counts_too(self):
        feast = LiturgicalOccasion.objects.create(name="St Andrew")
        self.service.additional_occasions.add(feast)
        self.score("Dum ambularet", suited_occasions=[feast])
        self.assertEqual(self.facts()["Dum ambularet"].occasion, "St Andrew")

    def test_use_types_are_listed_for_each_score(self):
        communion = make_use_type("Communion", organisation=self.church)
        self.score("Ave verum", suited_use_types=[communion])
        self.assertEqual(self.facts()["Ave verum"].use_type_ids, {communion.pk})

    def test_sung_inside_the_window_is_recent_outside_it_is_not(self):
        self.sing(self.score("Lately"), days_ago=14)
        self.sing(self.score("Long ago"), days_ago=400)
        self.score("Never")
        facts = self.facts(window=8)
        self.assertEqual((facts["Lately"].recent, facts["Lately"].sung_text), (True, "Sung 2 weeks ago"))
        self.assertEqual((facts["Long ago"].recent, facts["Long ago"].sung_text), (False, "Last sung 1 year ago"))
        self.assertEqual((facts["Never"].recent, facts["Never"].sung_text), (False, ""))
        self.assertFalse(self.facts(window=1)["Lately"].recent)

    def test_a_score_planned_later_this_term_is_marked_but_not_one_already_sung(self):
        ave = self.score("Ave verum")
        self.score("Locus iste")
        later = Service.objects.create(term=self.term, date=timezone.localdate() + timedelta(days=21),
                                       service_type="Sung Mass")
        RolePiece.objects.create(service_role=ServiceRole.objects.create(service=later, role_name="Motet"), score=ave)
        self.sing(self.score("Os justi"), days_ago=14)
        facts = self.facts()
        self.assertTrue(facts["Ave verum"].in_term)
        self.assertFalse(facts["Locus iste"].in_term)
        self.assertFalse(facts["Os justi"].in_term)

    def test_only_the_churchs_own_scores_and_a_fixed_number_of_queries(self):
        make_score(organisation=make_organisation("St Elsewhere"), title="Theirs")
        for n in range(5):
            self.score(f"Ours {n}", suited_seasons=[self.advent])
        with self.assertNumQueries(6):
            titles = [facts.score.title for facts in facts_for(self.service, 8)]
        self.assertEqual(titles, [f"Ours {n}" for n in range(5)])

    def test_a_service_with_no_occasion_has_no_tag_facts(self):
        self.service.occasion = None
        self.service.save()
        self.score("Vigilate", suited_seasons=[self.advent])
        self.assertEqual(self.facts()["Vigilate"].season, "")


class GroupingTests(SuggestionTestMixin, TestCase):
    def test_the_slots_use_type_comes_from_its_name_then_its_kind(self):
        from .suggestions import slot_use_type

        communion = make_use_type("Communion", organisation=self.church)
        motet = make_use_type("Motet", organisation=self.church)
        offertory_motet = ServiceRole.objects.create(service=self.service, role_name="Offertory motet")
        procession = ServiceRole.objects.create(service=self.service, role_name="Procession")
        use_types = [communion, motet]
        self.assertEqual(slot_use_type(self.slot, use_types), communion)
        self.assertEqual(slot_use_type(offertory_motet, use_types), motet)
        self.assertIsNone(slot_use_type(procession, use_types))

    def test_groups_order_and_reasons(self):
        from .suggestions import grouped

        communion = make_use_type("Communion", organisation=self.church)
        self.score("By use", suited_use_types=[communion])
        self.score("By season", suited_seasons=[self.advent])
        self.score("By day", suited_occasions=[self.sunday])
        self.sing(self.score("Lately", suited_seasons=[self.advent]), days_ago=14)
        self.score("Untagged")
        self.sing(self.score("Untagged lately"), days_ago=7)
        groups = grouped(facts_for(self.service, 8), communion)
        self.assertEqual([(label, [score.title for score, _ in entries]) for label, entries in groups], [
            ("Suggested", ["By day", "By season", "By use"]),
            ("Suggested, sung recently", ["Lately"]),
            ("Other scores", ["Untagged"]),
            ("Other scores, sung recently", ["Untagged lately"]),
        ])
        reasons = {score.title: reasons for _, entries in groups for score, reasons in entries}
        self.assertEqual(reasons["By day"], ["For Advent Sunday 1"])
        self.assertEqual(reasons["By use"], ["For Communion"])
        self.assertEqual(reasons["Lately"], ["For Advent", "Sung 2\u00a0weeks ago"])
        self.assertEqual(reasons["Untagged"], [])

    def test_an_untagged_library_is_one_group_in_title_order(self):
        from .suggestions import grouped

        for title in ("Locus iste", "Ave verum", "Os justi"):
            self.score(title)
        self.assertEqual([(label, [s.title for s, _ in e]) for label, e in grouped(facts_for(self.service, 8))], [
            ("Other scores", ["Ave verum", "Locus iste", "Os justi"]),
        ])


class ProposePageSuggestionTests(SuggestionTestMixin, TestCase):
    def test_the_page_groups_the_scores_and_gives_reasons(self):
        from accounts.testing import make_user

        conductor = make_user("conductor", organisation=self.church)
        self.client.force_login(conductor)
        rorate = self.score("Rorate caeli", suited_occasions=[self.sunday])
        self.score("Untagged")
        response = self.client.get(f"/roles/{self.slot.pk}/pieces/add/")
        self.assertContains(response, '<optgroup label="Suggested">')
        self.assertContains(response, '<optgroup label="Other scores">')
        self.assertContains(response, f'<option value="{rorate.pk}">{rorate}: For Advent Sunday 1</option>', html=True)

    def test_a_score_is_still_accepted_only_from_the_church(self):
        from accounts.testing import make_user

        self.client.force_login(make_user("conductor", organisation=self.church))
        theirs = make_score(organisation=make_organisation("St Elsewhere"), title="Theirs")
        self.client.post(f"/roles/{self.slot.pk}/pieces/add/", {"score": theirs.pk, "reference": ""})
        self.assertFalse(RolePiece.objects.filter(score=theirs).exists())


class PageOptionsTests(SuggestionTestMixin, TestCase):
    def test_the_service_page_sends_each_scores_facts_in_group_order(self):
        import json

        from accounts.testing import make_user

        communion = make_use_type("Communion", organisation=self.church)
        self.sing(self.score("Aaa sung lately"), days_ago=7)
        self.score("Bbb untagged")
        self.score("Zzz for the day", suited_occasions=[self.sunday], suited_use_types=[communion])
        self.client.force_login(make_user("conductor", organisation=self.church))
        response = self.client.get(self.service.get_absolute_url())
        # What the page embeds, read back as the script reads it.
        options = json.loads(json.dumps(response.context["score_options"]))
        self.assertEqual([o["label"].split(" (")[0] for o in options],
                         ["Zzz for the day", "Bbb untagged", "Aaa sung lately"])
        self.assertEqual(options[0]["occasion"], "Advent Sunday 1")
        self.assertEqual(options[0]["useTypes"], [communion.pk])
        self.assertEqual((options[2]["recent"], options[2]["sung"]), (True, "Sung 1\u00a0week ago"))
        self.assertContains(response, 'id="use-types"')
        self.assertEqual(response.context["use_type_options"], [{"id": communion.pk, "name": "Communion"}])


class VoicingPromptTests(SuggestionTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.no_voicing = self.score("Ave verum")
        self.sung = self.score("Locus iste")
        self.sung.voicing = "SATB"
        self.sung.save()
        for score in (self.no_voicing, self.sung):
            RolePiece.objects.create(service_role=self.slot, score=score)
        RolePiece.objects.create(service_role=self.slot, reference="NEH 1")

    def page(self, role):
        from accounts.testing import make_user

        self.client.force_login(make_user(role, organisation=self.church))
        return self.client.get(self.service.get_absolute_url())

    def test_a_score_with_no_voicing_asks_for_one_and_comes_back(self):
        for role in ("conductor", "librarian"):
            with self.subTest(role=role):
                response = self.page(role)
                self.assertContains(response, "No voicing recorded yet.", count=1)
                piece = RolePiece.objects.get(score=self.no_voicing)
                self.assertContains(
                    response, f"/library/{self.no_voicing.pk}/edit/?next=/services/{self.service.pk}/%23piece-row-{piece.pk}"
                )

    def test_a_viewer_isnt_asked(self):
        self.assertNotContains(self.page("viewer"), "No voicing recorded yet.")
