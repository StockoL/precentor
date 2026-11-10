from datetime import date

from django.test import TestCase

from accounts.testing import make_organisation, make_user
from comments.models import Comment
from ordo.models import LiturgicalOccasion
from precentor_project.testing import make_score, make_term

from .models import RolePiece, Service, ServiceRole
from .test_propers import chant

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class RemovePieceTests(TestCase):
    def setUp(self):
        self.church = make_organisation()
        self.conductor = make_user("conductor", organisation=self.church)
        self.client.force_login(self.conductor)
        term = make_term(organisation=self.church, start_date=date(2027, 2, 17), end_date=date(2027, 4, 3))
        self.service = Service.objects.create(term=term, date=date(2027, 2, 21), service_type="Sung Mass")
        self.slot = ServiceRole.objects.create(service=self.service, role_name="Credo")
        self.score = make_score(organisation=self.church, title="Credo III", composer_surname="Plainchant")

    def piece(self, **fields):
        return RolePiece.objects.create(service_role=self.slot, score=self.score, **fields)

    def url(self, piece):
        return f"/pieces/{piece.pk}/remove/"

    def test_a_proposed_piece_with_no_comments_goes_at_once(self):
        piece = self.piece()
        response = self.client.post(self.url(piece), {}, **AJAX)
        self.assertFalse(RolePiece.objects.exists())
        fragments = response.json()["fragments"]
        self.assertEqual(sorted(fragments), sorted([
            f"role-{self.slot.pk}-pieces", "service-status-badge", f"add-piece-form-{self.slot.pk}",
        ]))
        # The last piece gone, the slot says it has none.
        self.assertIn(f'id="role-{self.slot.pk}-pieces-empty"', fragments[f"role-{self.slot.pk}-pieces"])

    def test_a_confirmed_piece_asks_first_and_says_why(self):
        piece = self.piece(is_confirmed=True)
        response = self.client.post(self.url(piece))
        self.assertContains(response, "It&#x27;s confirmed, so it will leave the music list.")
        self.assertTrue(RolePiece.objects.exists())
        self.client.post(self.url(piece), {"confirm": "1"})
        self.assertFalse(RolePiece.objects.exists())

    def test_a_piece_with_comments_asks_first_and_they_go_with_it(self):
        piece = self.piece()
        for body in ("Too long?", "Fine by me"):
            Comment.objects.create(author=self.conductor, body=body, target=piece)
        response = self.client.post(self.url(piece))
        self.assertContains(response, "Its 2 comments go with it.")
        self.assertTrue(RolePiece.objects.exists())
        self.client.post(self.url(piece), {"confirm": "1"})
        self.assertFalse(RolePiece.objects.exists())
        self.assertFalse(Comment.objects.exists())

    def test_the_status_changes_when_the_last_confirmed_piece_goes(self):
        piece = self.piece(is_confirmed=True)
        self.assertEqual(self.service.status_label, "Complete")
        response = self.client.post(self.url(piece), {"confirm": "1"}, **AJAX)
        self.assertIn(">Not started<", response.json()["fragments"]["service-status-badge"])

    def test_a_removed_chant_is_offered_again(self):
        chant("sancti:12-08", "introit", "Gaudens gaudebo in Domino")
        feast = LiturgicalOccasion.objects.create(name="Immaculate Conception", key="sancti:12-08",
                                                  calendar_use="historic")
        term = make_term(organisation=self.church, name="Advent 1962", start_date=date(2026, 11, 29),
                         end_date=date(2026, 12, 24), calendar_use="historic")
        service = Service.objects.create(term=term, date=date(2026, 12, 8), service_type="Sung Mass", occasion=feast)
        introit = ServiceRole.objects.create(service=service, role_name="Introit")
        piece = RolePiece.objects.create(service_role=introit, reference="Gaudens gaudebo in Domino")
        response = self.client.post(self.url(piece), {}, **AJAX)
        self.assertIn('data-propose-reference="Gaudens gaudebo in Domino"',
                      response.json()["fragments"][f"add-piece-form-{introit.pk}"])

    def test_without_javascript_the_page_asks_and_goes_back_to_the_service(self):
        piece = self.piece(is_confirmed=True)
        page = self.client.get(self.url(piece))
        self.assertContains(page, "Remove Credo III (Plainchant)?")
        self.assertContains(page, 'name="confirm" value="1"')
        self.assertContains(page, f'name="next" value="{self.service.get_absolute_url()}"')
        response = self.client.post(self.url(piece), {"confirm": "1"}, follow=True)
        self.assertRedirects(response, self.service.get_absolute_url())
        self.assertContains(response, "Removed Credo III (Plainchant) from the Credo.")

    def test_a_second_removal_says_its_gone_and_goes_back(self):
        piece = self.piece()
        back = self.service.get_absolute_url()
        self.client.post(self.url(piece), {"next": back})
        response = self.client.post(self.url(piece), {"next": back}, follow=True)
        self.assertRedirects(response, back)
        self.assertContains(response, "That piece has already been removed.")
        # With JavaScript the message waits for the page to be reloaded.
        self.assertEqual(self.client.post(self.url(piece), {"next": back}, **AJAX).status_code, 410)
        self.assertContains(self.client.get(back), "That piece has already been removed.")

    def test_another_churchs_piece_is_answered_as_gone_and_left_alone(self):
        piece = self.piece()
        self.client.force_login(make_user("conductor", organisation=make_organisation("St Elsewhere")))
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url(piece), follow=True)
                self.assertContains(response, "That piece has already been removed.")
                self.assertNotContains(response, "Credo III")
        self.assertTrue(RolePiece.objects.filter(pk=piece.pk).exists())

    def test_a_viewer_is_refused(self):
        piece = self.piece()
        self.client.force_login(make_user("viewer", organisation=self.church))
        for method in ("get", "post"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(self.url(piece)).status_code, 403)
        self.assertTrue(RolePiece.objects.exists())


class RemoveButtonTests(TestCase):
    def setUp(self):
        self.church = make_organisation()
        self.conductor = make_user("conductor", organisation=self.church)
        term = make_term(organisation=self.church, start_date=date(2027, 2, 17), end_date=date(2027, 4, 3))
        self.service = Service.objects.create(term=term, date=date(2027, 2, 21), service_type="Sung Mass")
        self.slot = ServiceRole.objects.create(service=self.service, role_name="Credo")
        score = make_score(organisation=self.church, title="Credo III", composer_surname="Plainchant")
        self.proposed = RolePiece.objects.create(service_role=self.slot, reference="Credo I")
        self.confirmed = RolePiece.objects.create(service_role=self.slot, score=score, is_confirmed=True)

    def page(self, user):
        self.client.force_login(user)
        return self.client.get(self.service.get_absolute_url())

    def test_each_piece_has_a_remove_button_named_with_it_and_its_slot(self):
        response = self.page(self.conductor)
        for piece in (self.proposed, self.confirmed):
            with self.subTest(piece=piece.title):
                self.assertContains(response, f'action="/pieces/{piece.pk}/remove/"')
                self.assertContains(
                    response, f'Remove<span class="visually-hidden"> {piece.title} from the Credo</span>', html=False
                )
        self.assertContains(response, f'name="next" value="{self.service.get_absolute_url()}"', count=2)

    def test_only_a_piece_that_would_lose_something_asks_first(self):
        response = self.page(self.conductor).content.decode()
        self.assertIn('data-confirm-title="Remove Credo III (Plainchant)?"', response)
        self.assertIn("data-confirm-message=\"It&#x27;s confirmed, so it will leave the music list. "
                      "This can't be undone.\"", response)
        self.assertNotIn('data-confirm-title="Remove Credo I?"', response)

    def test_a_viewer_sees_no_remove_button(self):
        response = self.page(make_user("viewer", organisation=self.church))
        self.assertContains(response, "Credo III")
        self.assertNotContains(response, "/remove/\"")
        self.assertNotContains(response, "ajax-remove-piece")

    def test_the_wording_costs_no_query_per_piece(self):
        self.client.force_login(self.conductor)
        url = self.service.get_absolute_url()
        self.client.get(url)
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as before:
            self.client.get(url)
        for n in range(4):
            piece = RolePiece.objects.create(service_role=self.slot, reference=f"Extra {n}")
            Comment.objects.create(author=self.conductor, body="Hmm", target=piece)
        with self.assertNumQueries(len(before)):
            self.client.get(url)
