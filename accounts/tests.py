import os
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.views import View

from .context_processors import Can
from .decorators import role_required
from .forms import EmailAuthenticationForm
from .mixins import RoleRequiredMixin
from .models import Organisation, User
from .permissions import (
    can_comment,
    can_delete_comments,
    can_edit_library,
    can_manage_organisation,
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

    def test_an_email_address_is_stored_in_lowercase(self):
        user = make_user(email="Anne.Organist@Example.COM")
        user.refresh_from_db()
        self.assertEqual(user.email, "anne.organist@example.com")

    def test_the_password_works_for_signing_in(self):
        user = make_user(password="s3cret-pass")
        self.assertTrue(self.client.login(username=user.email, password="s3cret-pass"))

    def test_signing_in_ignores_the_case_of_the_address(self):
        make_user(email="anne@example.com", password="s3cret-pass")
        self.assertTrue(self.client.login(username="Anne@Example.COM", password="s3cret-pass"))

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


class CreateSuperuserCommandTests(TestCase):
    def test_it_asks_only_for_an_email_and_makes_an_admin_outside_any_organisation(self):
        with mock.patch.dict(os.environ, {"DJANGO_SUPERUSER_PASSWORD": "a-long-passphrase"}):
            call_command("createsuperuser", interactive=False, email="Admin@Example.com", verbosity=0)
        admin = User.objects.get()
        self.assertEqual(admin.email, "admin@example.com")
        self.assertTrue(admin.is_superuser and admin.is_staff)
        self.assertEqual((admin.organisation, admin.role, admin.is_owner), (None, "", False))
        self.assertTrue(admin.check_password("a-long-passphrase"))


class UserConstraintTests(TestCase):
    def assert_refused(self, message, **fields):
        fields.setdefault("email", "someone@example.com")
        user = User(**fields)
        with self.assertRaisesMessage(ValidationError, message):
            user.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            user.save()

    def test_an_organisation_needs_a_role_and_a_role_needs_an_organisation(self):
        message = "needs a role there"
        self.assert_refused(message, organisation=make_organisation(), role="")
        self.assert_refused(message, organisation=None, role="viewer")

    def test_an_owner_needs_an_organisation(self):
        self.assert_refused("Only someone in an organisation can own it.", is_owner=True)

    def test_an_owner_cannot_be_a_viewer(self):
        self.assert_refused(
            "An owner must be a Conductor or a Librarian.",
            organisation=make_organisation(), role="viewer", is_owner=True,
        )

    def test_an_organisation_has_one_owner(self):
        church = make_organisation()
        User.objects.create_user(
            email="anne@example.com", organisation=church, role="conductor", is_owner=True
        )
        self.assert_refused(
            "This organisation already has an owner.", organisation=church, role="librarian", is_owner=True
        )

    def test_each_organisation_can_have_its_own_owner(self):
        for number, name in enumerate(["St Cecilia's", "St Elsewhere"]):
            User.objects.create_user(
                email=f"owner{number}@example.com",
                organisation=make_organisation(name),
                role="conductor",
                is_owner=True,
            )
        self.assertEqual(User.objects.filter(is_owner=True).count(), 2)

    def test_an_email_address_is_taken_whatever_its_case(self):
        make_user(email="anne@example.com")
        self.assert_refused(
            "Someone already has an account with this email address.",
            email="Anne@Example.com", organisation=make_organisation(), role="viewer",
        )

    def test_both_or_neither_is_fine(self):
        make_user("viewer").full_clean()
        make_superuser().full_clean()


class CanManageOrganisationTests(TestCase):
    """Ownership is a flag on a Conductor or Librarian, not a fourth role,
    so it sits outside the roles table."""

    def test_only_the_owner_manages_the_organisation(self):
        owner = make_user("librarian")
        owner.is_owner = True
        self.assertIs(can_manage_organisation(owner), True)
        self.assertIs(can_manage_organisation(make_user("conductor")), False)

    def test_an_owner_loses_it_when_deactivated_and_a_superuser_never_has_it(self):
        owner = make_user("conductor")
        owner.is_owner = True
        owner.is_active = False
        self.assertIs(can_manage_organisation(owner), False)
        self.assertIs(can_manage_organisation(make_superuser()), False)
        self.assertIs(can_manage_organisation(AnonymousUser()), False)


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


class OrganisationAdminTests(TestCase):
    def test_a_superuser_can_list_and_add_organisations(self):
        self.client.force_login(make_superuser())
        make_organisation("St Mary's")
        self.assertContains(self.client.get("/admin/accounts/organisation/"), "St Mary&#x27;s")
        self.client.post("/admin/accounts/organisation/add/", {"name": "St Cecilia's"})
        church = Organisation.objects.get(name="St Cecilia's")
        # Added here, it starts like a church that signed up.
        self.assertEqual(sorted(church.slot_templates.values_list("name", flat=True)), ["Mass", "Vespers"])
        self.assertTrue(hasattr(church, "settings"))

    def test_renaming_a_church_adds_nothing(self):
        self.client.force_login(make_superuser())
        church = make_organisation("St Mary's")
        self.client.post(f"/admin/accounts/organisation/{church.pk}/change/", {"name": "St Mary's, Oxford"})
        church.refresh_from_db()
        self.assertEqual(church.name, "St Mary's, Oxford")
        self.assertFalse(church.slot_templates.exists())


class UserAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(make_superuser())

    def test_a_superuser_adds_someone_to_an_organisation_with_a_password(self):
        church = make_organisation("St Mary's")
        self.client.post("/admin/accounts/user/add/", {
            "email": "organist@example.com", "name": "Anne Organist",
            "organisation": church.pk, "role": "conductor", "usable_password": "true",
            "password1": "a-long-passphrase", "password2": "a-long-passphrase",
        })
        user = User.objects.get(email="organist@example.com")
        self.assertEqual((user.organisation, user.role, user.name), (church, "conductor", "Anne Organist"))
        self.assertTrue(user.check_password("a-long-passphrase"))

    def test_the_list_and_edit_pages_show_email_organisation_and_role(self):
        user = make_user("librarian", email="librarian@example.com")
        listing = self.client.get("/admin/accounts/user/")
        for text in ("librarian@example.com", "Test Church", "Librarian"):
            with self.subTest(text=text):
                self.assertContains(listing, text)
        self.assertContains(self.client.get(f"/admin/accounts/user/{user.pk}/change/"), 'name="role"')


class EmailAuthenticationFormTests(TestCase):
    def test_the_field_asks_for_an_email_address(self):
        html = str(EmailAuthenticationForm()["username"])
        self.assertIn('type="email"', html)
        self.assertIn('autocomplete="email"', html)
        self.assertEqual(EmailAuthenticationForm().fields["username"].label, "Email address")

    def test_it_signs_someone_in_whatever_the_case(self):
        user = make_user(email="anne@example.com", password="s3cret-pass")
        form = EmailAuthenticationForm(data={"username": "Anne@Example.com", "password": "s3cret-pass"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.get_user(), user)


class LoginPageTests(TestCase):
    def test_the_login_page_asks_for_an_email_address(self):
        response = self.client.get("/accounts/login/")
        self.assertIsInstance(response.context["form"], EmailAuthenticationForm)
        self.assertContains(response, 'type="email"')
        self.assertContains(response, 'href="/accounts/signup/"')

    def test_signing_in_with_any_capitals_lands_on_terms(self):
        make_user(email="anne@example.com", password="s3cret-pass")
        response = self.client.post(
            "/accounts/login/", {"username": "Anne@Example.com", "password": "s3cret-pass"}
        )
        self.assertRedirects(response, "/")


class MigrationSupportTests(TestCase):
    """The helper the organisation fill-in migrations share, run against
    today's models."""

    def setUp(self):
        from django.apps import apps

        self.apps = apps

    def test_with_none_it_makes_my_church_once_needed(self):
        from .migration_support import no_organisations_yet, organisation_for_existing_rows

        self.assertTrue(no_organisations_yet(self.apps))
        church = organisation_for_existing_rows(self.apps)
        self.assertEqual(church.name, "My church")
        self.assertFalse(no_organisations_yet(self.apps))
        self.assertEqual(organisation_for_existing_rows(self.apps), church)

    def test_with_one_it_uses_that_one(self):
        from .migration_support import organisation_for_existing_rows

        church = make_organisation("St Cecilia's")
        self.assertEqual(organisation_for_existing_rows(self.apps), church)
        self.assertEqual(Organisation.objects.count(), 1)

    def test_with_several_it_stops_rather_than_guess(self):
        from .migration_support import SeveralOrganisationsError, organisation_for_existing_rows

        make_organisation("St Cecilia's")
        make_organisation("St Elsewhere")
        with self.assertRaises(SeveralOrganisationsError):
            organisation_for_existing_rows(self.apps)


class UserWithOrganisationBackendTests(TestCase):
    def test_the_signed_in_person_comes_with_their_organisation_in_one_query(self):
        from .backends import UserWithOrganisationBackend

        user = make_user(organisation=make_organisation("St Cecilia's"))
        with self.assertNumQueries(1):
            loaded = UserWithOrganisationBackend().get_user(user.pk)
            self.assertEqual(loaded.organisation.name, "St Cecilia's")

    def test_signing_in_still_works_and_a_deactivated_person_is_not_loaded(self):
        from .backends import UserWithOrganisationBackend

        user = make_user(email="anne@example.com", password="s3cret-pass")
        self.assertTrue(self.client.login(username="Anne@Example.com", password="s3cret-pass"))
        user.is_active = False
        user.save()
        self.assertIsNone(UserWithOrganisationBackend().get_user(user.pk))


class OrganisationMiddlewareTests(TestCase):
    def organisation_on(self, user=None):
        if user:
            self.client.force_login(user)
        return self.client.get("/accounts/login/").wsgi_request.organisation

    def test_it_is_the_signed_in_persons_organisation(self):
        church = make_organisation("St Cecilia's")
        self.assertEqual(self.organisation_on(make_user("viewer", organisation=church)), church)

    def test_signed_out_and_superusers_have_none(self):
        self.assertIsNone(self.organisation_on())
        self.assertIsNone(self.organisation_on(make_superuser()))


class ForOrganisationTests(TestCase):
    def test_every_model_holding_a_churchs_data_can_be_limited_to_one(self):
        from django.apps import apps

        tenant_models = [
            model for model in apps.get_models()
            if any(field.name == "organisation" and field.many_to_one for field in model._meta.fields)
            and model is not User
        ]
        self.assertGreaterEqual(len(tenant_models), 9)
        for model in tenant_models:
            with self.subTest(model=model.__name__):
                self.assertTrue(hasattr(model.objects, "for_organisation"))

    def test_it_finds_only_that_churchs_rows_and_nothing_without_one(self):
        from library.models import Score
        from precentor_project.testing import make_score

        ours, theirs = make_organisation("St Cecilia's"), make_organisation("St Elsewhere")
        mine = make_score(title="Ave verum", organisation=ours)
        make_score(title="Ave verum", organisation=theirs)
        self.assertEqual(list(Score.objects.for_organisation(ours)), [mine])
        self.assertFalse(Score.objects.for_organisation(None).exists())

    def test_own_gives_the_requests_churchs_rows(self):
        from library.models import Score
        from precentor_project.testing import make_score

        from .querysets import own

        ours = make_organisation("St Cecilia's")
        mine = make_score(organisation=ours)
        make_score(organisation=make_organisation("St Elsewhere"))
        request = RequestFactory().get("/")
        request.organisation = ours
        self.assertEqual(list(own(Score, request)), [mine])


class CreateOrganisationTests(TestCase):
    def test_a_new_church_gets_its_settings_and_starters(self):
        from core.models import SiteConfig
        from ordo.models import UseType
        from planning.models import SlotTemplate

        from .organisations import STARTER_TEMPLATES, create_organisation

        church = create_organisation("St Cecilia's")
        self.assertEqual(church.name, "St Cecilia's")
        self.assertTrue(SiteConfig.objects.filter(organisation=church).exists())
        mass = SlotTemplate.objects.for_organisation(church).get(name="Mass")
        self.assertEqual(mass.slots, STARTER_TEMPLATES["Mass"])
        self.assertEqual(
            list(UseType.objects.for_organisation(church).values_list("name", flat=True)),
            ["General", "Mass", "Vespers"],
        )

    def test_each_church_gets_its_own_copies(self):
        from planning.models import SlotTemplate

        from .organisations import create_organisation

        ours, theirs = create_organisation("St Cecilia's"), create_organisation("St Elsewhere")
        SlotTemplate.objects.for_organisation(ours).filter(name="Mass").update(slot_names="Introit")
        self.assertEqual(len(SlotTemplate.objects.for_organisation(theirs).get(name="Mass").slots), 10)

    def test_nothing_is_left_behind_if_it_fails(self):
        from .organisations import create_organisation

        with mock.patch("core.models.SiteConfig.of", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                create_organisation("St Cecilia's")
        self.assertFalse(Organisation.objects.exists())


class SignUpFormTests(TestCase):
    DATA = {
        "church_name": "St Cecilia's",
        "name": "Anne Byrd",
        "email": "Anne@Example.com",
        "password1": "a quiet cantor sings",
        "password2": "a quiet cantor sings",
    }

    def form(self, **changes):
        from .forms import SignUpForm

        return SignUpForm(data={**self.DATA, **changes})

    def test_makes_the_church_and_its_owner(self):
        form = self.form()
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(
            (user.email, user.name, user.role, user.is_owner), ("anne@example.com", "Anne Byrd", "conductor", True)
        )
        self.assertEqual(user.organisation.name, "St Cecilia's")
        self.assertTrue(user.organisation.slot_templates.filter(name="Mass").exists())
        self.assertTrue(user.check_password("a quiet cantor sings"))

    def test_an_address_already_used_in_any_case_is_refused(self):
        make_user(email="anne@example.com")
        self.assertIn("already has an account", self.form().errors["email"][0])

    def test_every_field_is_needed(self):
        for field in self.DATA:
            with self.subTest(field=field):
                self.assertIn(field, self.form(**{field: ""}).errors)

    def test_the_passwords_must_match_and_follow_the_rules(self):
        self.assertIn("password2", self.form(password2="something else entirely").errors)
        self.assertIn("password2", self.form(password1="12345678", password2="12345678").errors)

    def test_nothing_is_made_when_the_person_cant_be_saved(self):
        form = self.form()
        self.assertTrue(form.is_valid())
        with mock.patch.object(User, "save", side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                form.save()
        self.assertFalse(Organisation.objects.filter(name="St Cecilia's").exists())


class SignUpPageTests(TestCase):
    DATA = SignUpFormTests.DATA

    def test_registering_signs_the_owner_in_and_goes_home(self):
        response = self.client.post("/accounts/signup/", self.DATA)
        self.assertRedirects(response, "/")
        user = User.objects.get(email="anne@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_a_mistake_shows_the_form_again_and_makes_nothing(self):
        response = self.client.post("/accounts/signup/", {**self.DATA, "password2": "something else"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Organisation.objects.exists())

    def test_anyone_signed_in_is_sent_home(self):
        self.client.force_login(make_user())
        self.assertRedirects(self.client.get("/accounts/signup/"), "/")

    def test_signed_out_pages_offer_registration(self):
        response = self.client.get("/accounts/signup/")
        self.assertContains(response, "Register your church")
        self.assertContains(response, 'autocomplete="new-password"')
        self.assertContains(response, 'href="/accounts/signup/">Register</a>')
