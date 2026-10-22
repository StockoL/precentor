from datetime import date

from django.test import TestCase

from accounts.testing import make_organisation

from .testing import make_score, make_slot_template, make_term, make_use_type


class OwnedThingHelperTests(TestCase):
    def test_each_belongs_to_the_shared_test_church_by_default(self):
        church = make_organisation()
        for thing in (make_term(), make_score(), make_slot_template(), make_use_type("Communion")):
            with self.subTest(thing=type(thing).__name__):
                self.assertEqual(thing.organisation, church)

    def test_fields_and_organisation_can_be_given(self):
        elsewhere = make_organisation("St Elsewhere")
        term = make_term(name="Lent", start_date=date(2027, 2, 10), organisation=elsewhere)
        self.assertEqual((term.name, term.start_date, term.organisation), ("Lent", date(2027, 2, 10), elsewhere))
        self.assertEqual(make_score(title="Ave verum").title, "Ave verum")
