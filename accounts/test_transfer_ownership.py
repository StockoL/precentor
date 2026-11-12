"""
transfer_ownership: the way the site's administrator hands a church's
ownership on when the owner can't do it from Members.
"""

from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from .testing import make_organisation, make_user


class TransferOwnershipTests(TestCase):
    def setUp(self):
        self.church = make_organisation("St Cecilia's")
        self.owner = make_user("conductor", organisation=self.church, email="owner@example.com")
        self.owner.is_owner = True
        self.owner.save()
        self.librarian = make_user("librarian", organisation=self.church, email="librarian@example.com")

    def transfer(self, email, church=None):
        out = StringIO()
        # As typed at the command line.
        call_command("transfer_ownership", "--church", str(church or self.church.pk), "--to", email, stdout=out)
        return out.getvalue()

    def refreshed(self):
        self.owner.refresh_from_db()
        self.librarian.refresh_from_db()

    def test_it_hands_ownership_over_and_says_who_held_it(self):
        out = self.transfer("Librarian@Example.com")
        self.refreshed()
        self.assertTrue(self.librarian.is_owner)
        self.assertFalse(self.owner.is_owner)
        self.assertEqual(self.owner.role, "conductor")
        self.assertIn("Owner before: ", out)
        self.assertIn("owner@example.com", out)
        self.assertIn("Owner after: ", out)
        self.assertIn("librarian@example.com, Librarian", out)

    def test_an_owner_whose_account_is_switched_off_can_still_be_replaced(self):
        self.owner.is_active = False
        self.owner.save()
        out = self.transfer("librarian@example.com")
        self.refreshed()
        self.assertTrue(self.librarian.is_owner)
        self.assertFalse(self.owner.is_owner)
        self.assertIn("account switched off", out)

    def test_a_church_left_without_an_owner_gets_one(self):
        self.owner.is_owner = False
        self.owner.save()
        out = self.transfer("librarian@example.com")
        self.refreshed()
        self.assertTrue(self.librarian.is_owner)
        self.assertIn("Owner before: nobody", out)

    def test_it_refuses_anyone_who_cant_be_the_owner(self):
        viewer = make_user("viewer", organisation=self.church, email="viewer@example.com")
        gone = make_user("librarian", organisation=self.church, email="gone@example.com")
        gone.is_active = False
        gone.save()
        make_user("conductor", organisation=make_organisation("Elsewhere"), email="outsider@example.com")
        refusals = {
            viewer.email: "only an active Conductor or Librarian",
            gone.email: "only an active Conductor or Librarian",
            "outsider@example.com": "Nobody in St Cecilia's has the address",
            "owner@example.com": "is already the owner",
        }
        for email, message in refusals.items():
            with self.subTest(email=email), self.assertRaisesMessage(CommandError, message):
                self.transfer(email)
        self.refreshed()
        self.assertTrue(self.owner.is_owner)

    def test_it_refuses_a_church_that_doesnt_exist(self):
        with self.assertRaisesMessage(CommandError, "No church has the id 999999."):
            self.transfer("librarian@example.com", church=999999)
