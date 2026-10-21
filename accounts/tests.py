from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from .permissions import can_edit_library, can_plan
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


class CanPlanTests(TestCase):
    def test_only_a_conductor_plans(self):
        self.assertTrue(can_plan(make_user("conductor")))
        self.assertFalse(can_plan(make_user("librarian")))
        self.assertFalse(can_plan(make_user("viewer")))

    def test_nobody_signed_out_or_deactivated_plans(self):
        self.assertFalse(can_plan(AnonymousUser()))
        conductor = make_user("conductor")
        conductor.is_active = False
        self.assertFalse(can_plan(conductor))

    def test_being_a_superuser_gives_no_role(self):
        admin = make_user("viewer")
        admin.is_superuser = True
        admin.save()
        self.assertFalse(can_plan(admin))


class CanEditLibraryTests(TestCase):
    def test_conductors_and_librarians_edit_the_library(self):
        self.assertTrue(can_edit_library(make_user("conductor")))
        self.assertTrue(can_edit_library(make_user("librarian")))
        self.assertFalse(can_edit_library(make_user("viewer")))
        self.assertFalse(can_edit_library(AnonymousUser()))
