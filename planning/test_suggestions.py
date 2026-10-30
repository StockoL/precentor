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

    def test_a_score_already_in_this_term_is_marked(self):
        ave = self.score("Ave verum")
        self.score("Locus iste")
        later = Service.objects.create(term=self.term, date=timezone.localdate() + timedelta(days=21),
                                       service_type="Sung Mass")
        RolePiece.objects.create(service_role=ServiceRole.objects.create(service=later, role_name="Motet"), score=ave)
        facts = self.facts()
        self.assertTrue(facts["Ave verum"].in_term)
        self.assertFalse(facts["Locus iste"].in_term)

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
