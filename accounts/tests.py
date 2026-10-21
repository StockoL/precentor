from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.views import View

from .context_processors import Can
from .decorators import role_required
from .mixins import RoleRequiredMixin
from .permissions import (
    can_comment,
    can_delete_comments,
    can_edit_library,
    can_manage_settings,
    can_plan,
)
from .testing import make_organisation, make_superuser, make_user


class MakeUserTests(TestCase):
    def test_each_user_gets_their_role_in_the_shared_test_church(self):
        for role in ("conductor", "librarian", "viewer"):
            with self.subTest(role=role):
                user = make_user(role)
                self.assertEqual(user.role, role)
                self.assertEqual(user.organisation, make_organisation())

    def test_a_test_can_pass_its_own_organisation(self):
        elsewhere = make_organisation("St Elsewhere")
        self.assertEqual(make_user(organisation=elsewhere).organisation, elsewhere)

    def test_a_superuser_has_no_organisation_or_role(self):
        admin = make_superuser()
        self.assertTrue(admin.is_superuser and admin.is_staff)
        self.assertIsNone(admin.organisation)
        self.assertEqual(admin.role, "")

    def test_each_user_gets_their_own_address_unless_given_one(self):
        first, second = make_user(), make_user()
        self.assertNotEqual(first.email, second.email)
        self.assertEqual(make_user(email="organist@example.com").email, "organist@example.com")

    def test_the_password_works_for_signing_in(self):
        user = make_user(password="s3cret-pass")
        self.assertTrue(self.client.login(username=user.email, password="s3cret-pass"))

    def test_an_unknown_role_is_refused(self):
        with self.assertRaises(ValueError):
            make_user("organist")


class PermissionMatrixTests(TestCase):
    """The roles table in the README, as code. A change to who may do what
    has to change this table too, so the two can't drift apart."""

    MATRIX = {
        #                       conductor  librarian  viewer
        can_plan:               (True,     False,     False),
        can_edit_library:       (True,     True,      False),
        can_comment:            (True,     True,      True),
        can_manage_settings:    (True,     False,     False),
        can_delete_comments:    (True,     True,      False),
    }
    ROLES = ("conductor", "librarian", "viewer")

    def test_each_role_against_each_check(self):
        users = {role: make_user(role) for role in self.ROLES}
        for check, allowed in self.MATRIX.items():
            for role, expected in zip(self.ROLES, allowed):
                with self.subTest(check=check.__name__, role=role):
                    self.assertIs(check(users[role]), expected)

    def test_nobody_without_a_role_passes_any_check(self):
        deactivated = make_user("conductor")
        deactivated.is_active = False
        superuser = make_superuser()
        for name, user in (("signed out", AnonymousUser()), ("deactivated", deactivated), ("superuser", superuser)):
            for check in self.MATRIX:
                with self.subTest(user=name, check=check.__name__):
                    self.assertIs(check(user), False)


class RoleRequiredTests(TestCase):
    def setUp(self):
        self.view = role_required(can_plan)(lambda request: HttpResponse("planned"))
        self.request = RequestFactory().get("/services/1/edit/")

    def test_someone_signed_out_is_sent_to_log_in_and_back(self):
        self.request.user = AnonymousUser()
        response = self.view(self.request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/accounts/login/?next=/services/1/edit/")

    def test_someone_signed_in_without_the_right_is_refused(self):
        self.request.user = make_user("viewer")
        with self.assertRaises(PermissionDenied):
            self.view(self.request)

    def test_someone_with_the_right_gets_the_view(self):
        self.request.user = make_user("conductor")
        self.assertEqual(self.view(self.request).content, b"planned")


class RoleRequiredMixinTests(TestCase):
    class PlanningView(RoleRequiredMixin, View):
        permission = can_plan

        def get(self, request):
            return HttpResponse("planned")

    def setUp(self):
        self.view = self.PlanningView.as_view()
        self.request = RequestFactory().get("/terms/add/")

    def test_someone_signed_out_is_sent_to_log_in_and_back(self):
        self.request.user = AnonymousUser()
        response = self.view(self.request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/accounts/login/?next=/terms/add/")

    def test_someone_signed_in_without_the_right_is_refused(self):
        self.request.user = make_user("librarian")
        with self.assertRaises(PermissionDenied):
            self.view(self.request)

    def test_someone_with_the_right_gets_the_view(self):
        self.request.user = make_user("conductor")
        self.assertEqual(self.view(self.request).content, b"planned")


class CanContextProcessorTests(TestCase):
    def test_templates_get_the_same_answers_as_the_checks(self):
        can = Can(make_user("librarian"))
        self.assertIs(can["edit_library"], True)
        self.assertIs(can["plan"], False)

    def test_asking_costs_no_queries_and_each_answer_is_kept(self):
        user = make_user("conductor")
        with self.assertNumQueries(0):
            can = Can(user)
            can["plan"]
        self.assertEqual(dict(can), {"plan": True})

    def test_an_unknown_check_is_an_error_not_a_quiet_no(self):
        with self.assertRaises(KeyError):
            Can(make_user())["fly"]

    def test_every_page_has_it(self):
        self.client.force_login(make_user("viewer"))
        response = self.client.get("/library/")
        self.assertIs(response.context["can"]["edit_library"], False)
