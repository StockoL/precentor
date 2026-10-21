from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from .decorators import role_required
from .permissions import (
    can_comment,
    can_delete_comments,
    can_edit_library,
    can_manage_settings,
    can_plan,
)
from .testing import make_user


class MakeUserTests(TestCase):
    def test_each_role_gets_its_group_and_a_viewer_gets_none(self):
        self.assertEqual(list(make_user("conductor").groups.values_list("name", flat=True)), ["Conductor"])
        self.assertEqual(list(make_user("librarian").groups.values_list("name", flat=True)), ["Librarian"])
        self.assertFalse(make_user("viewer").groups.exists())

    def test_each_user_gets_their_own_address_unless_given_one(self):
        first, second = make_user(), make_user()
        self.assertNotEqual(first.email, second.email)
        self.assertEqual(make_user(email="organist@example.com").email, "organist@example.com")

    def test_the_password_works_for_signing_in(self):
        user = make_user(password="s3cret-pass")
        self.assertTrue(self.client.login(username=user.username, password="s3cret-pass"))

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
        superuser = make_user("viewer")
        superuser.is_superuser = True
        superuser.save()
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
