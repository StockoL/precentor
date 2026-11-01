"""
The isolation test: one church can't reach another's data by any route.

Two complete churches are built, A and B. Every piece of B's text carries
the marker B-ONLY, so a leak shows up wherever it appears. Each check
starts from what exists, not from a hand-kept list, so it fails, and says
what to add, when a new model or route arrives without being covered.
"""

from datetime import date

from django.apps import apps
from django.test import TestCase

from accounts.models import Invitation, User
from accounts.organisations import create_organisation
from comments.models import Comment
from core.models import SiteConfig
from library.models import Hymnal, HymnEntry, HymnImport, Score, ScoreImport, Tune
from ordo.models import UseType
from planning.models import RolePiece, Service, ServiceRole, SlotTemplate, Term, TermMarker

PASSWORD = "testpass123"


def build_church(marker):
    """A church with one of everything a church can own, each carrying the
    marker in its text. Returns the rows by name."""
    church = create_organisation(f"{marker} church")
    settings = SiteConfig.of(church)
    settings.church_name = f"{marker} church"
    settings.set_crest(b"crest", "image/png")
    settings.save()
    owner = User.objects.create_user(
        email=f"{marker.lower()}-owner@example.com", password=PASSWORD, name=f"{marker} owner",
        organisation=church, role="conductor", is_owner=True,
    )
    member = User.objects.create_user(
        email=f"{marker.lower()}-member@example.com", password=PASSWORD, name=f"{marker} member",
        organisation=church, role="librarian",
    )
    former = User.objects.create_user(
        email=f"{marker.lower()}-former@example.com", password=PASSWORD, name=f"{marker} former",
        organisation=church, role="viewer", is_active=False,
    )
    score = Score.objects.create(
        organisation=church, title=f"{marker} score", composer_surname=f"{marker} composer",
        voicing="SATB", language="Latin",
    )
    use_type = UseType.objects.create(organisation=church, name=f"{marker} use")
    score.suited_use_types.add(use_type)
    template = SlotTemplate.objects.create(organisation=church, name=f"{marker} template", slot_names="Introit")
    template.set_slots(["Introit"])
    term = Term.objects.create(
        organisation=church, name=f"{marker} term", start_date=date(2026, 11, 29),
        end_date=date(2026, 12, 24), calendar_use="current",
    )
    service = Service.objects.create(term=term, date=date(2026, 12, 6), service_type=f"{marker} service")
    slot = ServiceRole.objects.create(service=service, role_name=f"{marker} slot")
    piece = RolePiece.objects.create(service_role=slot, score=score)
    marker_row = TermMarker.objects.create(term=term, date=date(2026, 12, 1), text=f"{marker} notice")
    comment = Comment.objects.create(author=owner, target=service, body=f"{marker} comment")
    invitation, _ = Invitation.make(organisation=church, role="viewer", created_by=owner, note=f"{marker} invitation")
    score_import = ScoreImport.objects.create(
        organisation=church, created_by=owner, original_filename=f"{marker} library.csv"
    )
    hymnal = Hymnal.objects.create(organisation=church, name=f"{marker} hymnal", short_name=f"{marker}H")
    hymn_entry = HymnEntry.find_or_make(hymnal, "1")
    tune = Tune.objects.create(organisation=church, name=f"{marker} tune", metre="LM")
    hymn_entry.hymn.first_line = f"{marker} first line"
    hymn_entry.hymn.save()
    hymn_import = HymnImport.objects.create(
        organisation=church, hymnal=hymnal, created_by=owner, original_filename=f"{marker} hymns.csv"
    )
    return {
        "church": church, "settings": settings, "owner": owner, "member": member, "former": former,
        "score": score, "use_type": use_type, "template": template,
        "template_slot": template.template_slots.get(), "term": term, "service": service,
        "slot": slot, "piece": piece, "marker": marker_row, "comment": comment, "invitation": invitation,
        "score_import": score_import, "hymnal": hymnal, "hymn_entry": hymn_entry,
        "hymn": hymn_entry.hymn, "tune": tune, "hymn_import": hymn_import,
    }


def tenant_models():
    """Every model that holds a church's own data: those with an
    organisation field."""
    return {
        model for model in apps.get_models()
        if any(field.name == "organisation" for field in model._meta.get_fields())
    }


class TwoChurchesMixin:
    @classmethod
    def setUpTestData(cls):
        cls.a = build_church("A-ONLY")
        cls.b = build_church("B-ONLY")


class EveryChurchModelIsCoveredTests(TwoChurchesMixin, TestCase):
    def test_the_builder_makes_a_row_of_every_model_that_holds_church_data(self):
        made = {type(row) for row in self.b.values()}
        missing = sorted(model.__name__ for model in tenant_models() - made)
        self.assertEqual(missing, [], "Add these to build_church() in the isolation test so they're checked")

    def test_each_church_has_a_row_of_every_one(self):
        for model in tenant_models():
            with self.subTest(model=model.__name__):
                for church in (self.a, self.b):
                    rows = model.objects.filter(organisation=church["church"])
                    self.assertTrue(rows.exists())


def all_routes():
    """Every route in the project, as {namespace:name: its pattern}. The
    admin site is left out: it's for the site's superusers, who belong to
    no church."""
    from django.urls import URLPattern, URLResolver, get_resolver

    found = {}

    def walk(patterns, namespace="", prefix=""):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                if str(pattern.pattern).startswith("admin"):
                    continue
                inner = pattern.namespace or ""
                walk(pattern.url_patterns, f"{namespace}:{inner}".strip(":") if inner else namespace,
                     prefix + str(pattern.pattern))
            elif isinstance(pattern, URLPattern):
                found[f"{namespace}:{pattern.name}" if namespace else pattern.name] = prefix + str(pattern.pattern)

    walk(get_resolver().url_patterns)
    return found


def int_routes():
    """The routes whose address carries a number."""
    return {name for name, pattern in all_routes().items() if "<int:" in pattern}


def content_type_id(row):
    from django.contrib.contenttypes.models import ContentType

    return ContentType.objects.get_for_model(row).pk


# For each route with an id in it: the addresses that point at church B's
# rows, as church A would type them. a and b are build_church()'s rows.
ADDRESSES = {
    "members:change_role": lambda a, b: [{"pk": b["member"].pk}],
    "members:remove": lambda a, b: [{"pk": b["member"].pk}],
    "members:restore": lambda a, b: [{"pk": b["former"].pk}],
    "members:reset_link": lambda a, b: [{"pk": b["member"].pk}],
    "members:make_owner": lambda a, b: [{"pk": b["member"].pk}],
    "members:invitation_link": lambda a, b: [{"pk": b["invitation"].pk}],
    "members:invitation_cancel": lambda a, b: [{"pk": b["invitation"].pk}],
    "library:score_detail": lambda a, b: [{"pk": b["score"].pk}],
    "library:score_update": lambda a, b: [{"pk": b["score"].pk}],
    "library:score_delete": lambda a, b: [{"pk": b["score"].pk}],
    "library:score_import_detail": lambda a, b: [{"pk": b["score_import"].pk}],
    "library:keep_import": lambda a, b: [{"pk": b["score_import"].pk}],
    "library:hymnal_update": lambda a, b: [{"pk": b["hymnal"].pk}],
    "library:hymnal_detail": lambda a, b: [{"pk": b["hymnal"].pk}],
    "library:hymn_detail": lambda a, b: [{"pk": b["hymn"].pk}],
    "library:hymn_update": lambda a, b: [{"pk": b["hymn"].pk}],
    "library:tune_update": lambda a, b: [{"pk": b["tune"].pk}],
    "library:hymn_entry_update": lambda a, b: [{"pk": b["hymn_entry"].pk}],
    # Both of the other church's, and one of each either way round.
    "library:same_hymn": lambda a, b: [
        {"pk": b["hymn"].pk, "other_pk": b["hymn"].pk},
        {"pk": a["hymn"].pk, "other_pk": b["hymn"].pk},
        {"pk": b["hymn"].pk, "other_pk": a["hymn"].pk},
    ],
    "library:hymnal_delete": lambda a, b: [{"pk": b["hymnal"].pk}],
    "library:remove_import": lambda a, b: [{"pk": b["score_import"].pk}],
    "library:hymn_import": lambda a, b: [{"pk": b["hymnal"].pk}],
    "library:hymn_import_detail": lambda a, b: [{"pk": b["hymn_import"].pk}],
    "library:keep_hymn_import": lambda a, b: [{"pk": b["hymn_import"].pk}],
    "library:remove_hymn_import": lambda a, b: [{"pk": b["hymn_import"].pk}],
    "planning:term_update": lambda a, b: [{"pk": b["term"].pk}],
    "planning:term_delete": lambda a, b: [{"pk": b["term"].pk}],
    "planning:term_detail": lambda a, b: [{"pk": b["term"].pk}],
    "planning:service_create": lambda a, b: [{"term_pk": b["term"].pk}],
    "planning:service_detail": lambda a, b: [{"pk": b["service"].pk}],
    "planning:service_update": lambda a, b: [{"pk": b["service"].pk}],
    "planning:service_pew_sheet": lambda a, b: [{"pk": b["service"].pk}],
    "planning:service_delete": lambda a, b: [{"pk": b["service"].pk}],
    "planning:term_music_list": lambda a, b: [{"term_pk": b["term"].pk}],
    "planning:marker_create": lambda a, b: [{"term_pk": b["term"].pk}],
    "planning:marker_update": lambda a, b: [{"pk": b["marker"].pk}],
    "planning:marker_delete": lambda a, b: [{"pk": b["marker"].pk}],
    "planning:add_role": lambda a, b: [{"service_pk": b["service"].pk}],
    # Both halves: B's service with A's template, and A's service with B's.
    "planning:apply_template": lambda a, b: [
        {"service_pk": b["service"].pk, "template_pk": a["template"].pk},
        {"service_pk": a["service"].pk, "template_pk": b["template"].pk},
    ],
    "planning:slot_template_update": lambda a, b: [{"pk": b["template"].pk}],
    "planning:slot_template_delete": lambda a, b: [{"pk": b["template"].pk}],
    "planning:add_piece": lambda a, b: [{"role_pk": b["slot"].pk}],
    "planning:move_slot": lambda a, b: [{"role_pk": b["slot"].pk}],
    "planning:change_kind": lambda a, b: [{"role_pk": b["slot"].pk}],
    "planning:set_tune": lambda a, b: [{"piece_pk": b["piece"].pk}],
    "planning:remove_slot": lambda a, b: [{"role_pk": b["slot"].pk}],
    "planning:reorder_slots": lambda a, b: [{"service_pk": b["service"].pk}],
    "planning:toggle_confirm": lambda a, b: [{"piece_pk": b["piece"].pk}],
    "comments:add_comment": lambda a, b: [
        {"content_type_id": content_type_id(b[name]), "object_id": b[name].pk} for name in ("term", "service", "piece")
    ],
    "comments:toggle_close": lambda a, b: [{"comment_pk": b["comment"].pk}],
    "comments:delete_comment": lambda a, b: [{"comment_pk": b["comment"].pk}],
}

# Routes with a number in them that aren't about one church's rows.
NOT_CHURCH_DATA = {
    "core:crest": "the crest is public branding, served to anyone at a versioned address",
}

# Everything a form on these pages might read, so a POST that got through
# would change something the snapshot would catch.
POST_DATA = {
    "role": "viewer", "role_name": "A tried", "name": "A tried", "title": "A tried", "text": "A tried",
    "body": "A tried", "slot_names": "A tried", "service_type": "A tried", "date": "2026-12-13",
    "start_date": "2026-11-29", "end_date": "2026-12-24", "calendar_use": "current", "confirm": "1",
    "replace": "1", "direction": "up", "order": "", "composer_surname": "A tried", "voicing": "SATB",
    "language": "Latin",
}


def snapshot(church):
    """Every row of a church's data, as plain values, to compare before and
    after. last_login changes on any sign-in, so it's left out."""
    rows = {}
    for model in tenant_models():
        values = model.objects.filter(organisation=church).order_by("pk").values()
        rows[model.__name__] = [{k: v for k, v in row.items() if k != "last_login"} for row in values]
    return rows


class EveryAddressIsCheckedTests(TwoChurchesMixin, TestCase):
    def test_every_route_with_an_id_is_listed(self):
        unlisted = sorted(int_routes() - set(ADDRESSES) - set(NOT_CHURCH_DATA))
        self.assertEqual(unlisted, [], "Add these routes to ADDRESSES in the isolation test")


class AnotherChurchsAddressesTests(TwoChurchesMixin, TestCase):
    """Church A's owner, who can do everything in their own church, tries
    every address that points at church B's rows."""

    def test_nothing_of_church_bs_can_be_seen_or_changed(self):
        from django.urls import reverse

        post_data = dict(POST_DATA, score=self.a["score"].pk)
        self.client.force_login(self.a["owner"])
        before = snapshot(self.b["church"])
        for name, addresses in ADDRESSES.items():
            for kwargs in addresses(self.a, self.b):
                url = reverse(name, kwargs=kwargs)
                for method in ("get", "post"):
                    with self.subTest(route=name, url=url, method=method):
                        if method == "get":
                            response = self.client.get(url)
                        else:
                            response = self.client.post(url, post_data)
                        self.assertNotEqual(response.status_code, 200, "another church's page was shown")
                        self.assertNotIn(b"B-ONLY", response.content)
        self.assertEqual(snapshot(self.b["church"]), before, "church B's data was changed")


# Routes with other parameters, which can't be listed for a church.
TOKEN_ROUTES = {
    "join": "an invitation's secret, checked by its own tests",
    "password_reset_confirm": "Django's signed reset token, checked by its own tests",
}


class OwnPagesShowNothingOfAnotherChurchTests(TwoChurchesMixin, TestCase):
    """Church A's own pages must never list or mention church B's rows, in
    menus, lists or counts, even though B's own addresses are shut."""

    def assert_nothing_of_b(self, url):
        response = self.client.get(url, follow=True)
        html = response.content.decode()
        found = html.find("B-ONLY")
        # Only the text around the leak, so a failure stays readable.
        self.assertEqual(found, -1, f"{url} mentions church B: ...{html[max(found - 80, 0):found + 40]}...")

    def test_pages_without_an_id(self):
        from django.urls import reverse

        self.client.force_login(self.a["owner"])
        plain = [name for name, pattern in all_routes().items() if "<" not in pattern]
        for name in plain:
            with self.subTest(route=name):
                self.assert_nothing_of_b(reverse(name))

    def test_church_as_own_pages_with_an_id(self):
        from django.urls import reverse

        self.client.force_login(self.a["owner"])
        for name, addresses in ADDRESSES.items():
            # The same table, turned round to point at church A's own rows.
            for kwargs in addresses(self.b, self.a):
                with self.subTest(route=name, kwargs=kwargs):
                    self.assert_nothing_of_b(reverse(name, kwargs=kwargs))

    def test_every_route_is_covered_by_one_check_or_another(self):
        covered = set(ADDRESSES) | set(NOT_CHURCH_DATA) | set(TOKEN_ROUTES)
        plain = {name for name, pattern in all_routes().items() if "<" not in pattern}
        self.assertEqual(sorted(set(all_routes()) - covered - plain), [], "Add these routes to the isolation test")
