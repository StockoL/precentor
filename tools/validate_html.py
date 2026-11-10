"""
Sends the HTML of every page in Precentor to the W3C Nu HTML Checker and
prints what it says about each, for the validation table in
docs/testing.md.

It works like the test suite: it makes a throwaway test database, loads
the calendar into it and builds a church with one of everything, using
build_church() from the isolation test. Each page is rendered with
Django's test client, with DEBUG off as on the live site, and the HTML is
posted to the checker with curl (part of Windows 10 and later). My
development database isn't touched and no server needs to be running;
collectstatic fills staticfiles/, as the live build does.
Run it from the repository root, online:

    python tools/validate_html.py > validation.md

or, to check only some pages, name them as the results do:

    python tools/validate_html.py planning:service_detail "404 page"

The pages come from the project's own list of routes, so a new page is
checked without being added here; a new route with a number in its
address stops the script until this file says which row it shows. Pages
that only appear after an action (a form with mistakes, a deleted
account, the 403 and 404 pages) are listed by hand at the end.

The checker turns away clients that ask too often, so the script waits
ten seconds between pages and a run takes about a quarter of an hour.
If it's turned away all the same, it prints what it had checked and the
command that checks the rest.

The same checker can be run locally, with no waiting: download
vnu.windows.zip from github.com/validator/validator/releases, unzip it,
start it with

    vnu-runtime-image\\bin\\java -m vnu/nu.validator.servlet.Main 8888

and point the script at it:

    $env:VALIDATOR_URL = "http://127.0.0.1:8888/?out=json"
"""

import io
import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "precentor_project.settings")
# As on the live site, whatever .env says: the 404 and 500 pages are the
# real ones, not Django's debug pages.
os.environ["DEBUG"] = "False"
django.setup()

from django.contrib.auth.tokens import default_token_generator  # noqa: E402
from django.contrib.contenttypes.models import ContentType  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402
from django.test import Client, RequestFactory  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.utils.encoding import force_bytes  # noqa: E402
from django.utils.http import urlsafe_base64_encode  # noqa: E402
from django.views.defaults import server_error  # noqa: E402

CHECKER = os.environ.get("VALIDATOR_URL", "https://validator.w3.org/nu/?out=json")
# Only the public checker needs a pause between pages.
PAUSE = 10 if "validator.w3.org" in CHECKER else 0
PASSWORD = "testpass123"

# Pages someone sees before signing in.
SIGNED_OUT = {"login", "signup", "join", "password_reset_confirm", "password_reset_complete", "privacy"}


def addresses(rows, join_token):
    """The address of every route, from the rows build_church() made.
    Routes without a number in them need nothing here."""
    service, slot, piece = rows["service"], rows["slot"], rows["piece"]
    member = rows["member"]
    return {
        "join": reverse("join", args=[join_token]),
        "password_reset_confirm": reverse("password_reset_confirm", kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(member.pk)),
            "token": default_token_generator.make_token(member),
        }),
        "members:change_role": [member.pk],
        "members:remove": [member.pk],
        "members:restore": [rows["former"].pk],
        "members:reset_link": [member.pk],
        "members:make_owner": [member.pk],
        "members:invitation_link": [rows["invitation"].pk],
        "members:invitation_cancel": [rows["invitation"].pk],
        "library:score_detail": [rows["score"].pk],
        "library:score_update": [rows["score"].pk],
        "library:score_delete": [rows["score"].pk],
        "library:hymnal_detail": [rows["hymnal"].pk],
        "library:hymnal_update": [rows["hymnal"].pk],
        "library:hymnal_delete": [rows["hymnal"].pk],
        "library:hymn_import": [rows["hymnal"].pk],
        "library:hymn_detail": [rows["hymn"].pk],
        "library:hymn_update": [rows["hymn"].pk],
        "library:same_hymn": [rows["hymn"].pk, rows["other_hymn"].pk],
        "library:hymn_entry_update": [rows["hymn_entry"].pk],
        "library:tune_update": [rows["tune"].pk],
        "library:score_import_detail": [rows["score_import"].pk],
        "library:keep_import": [rows["score_import"].pk],
        "library:remove_import": [rows["score_import"].pk],
        "library:hymn_import_detail": [rows["hymn_import"].pk],
        "library:keep_hymn_import": [rows["hymn_import"].pk],
        "library:remove_hymn_import": [rows["hymn_import"].pk],
        "core:crest": rows["settings"].crest_url,
        "planning:term_detail": [rows["term"].pk],
        "planning:term_update": [rows["term"].pk],
        "planning:term_delete": [rows["term"].pk],
        "planning:service_create": [rows["term"].pk],
        "planning:term_music_list": [rows["term"].pk],
        "planning:marker_create": [rows["term"].pk],
        "planning:marker_update": [rows["marker"].pk],
        "planning:marker_delete": [rows["marker"].pk],
        "planning:service_detail": [service.pk],
        "planning:service_update": [service.pk],
        "planning:service_delete": [service.pk],
        "planning:service_pew_sheet": [service.pk],
        "planning:add_role": [service.pk],
        "planning:reorder_slots": [service.pk],
        "planning:apply_template": [service.pk, rows["template"].pk],
        "planning:slot_template_update": [rows["template"].pk],
        "planning:slot_template_delete": [rows["template"].pk],
        "planning:add_piece": [slot.pk],
        "planning:move_slot": [slot.pk],
        "planning:change_kind": [slot.pk],
        "planning:remove_slot": [slot.pk],
        "planning:set_tune": [piece.pk],
        "planning:toggle_confirm": [piece.pk],
        "comments:add_comment": [ContentType.objects.get_for_model(service).pk, service.pk],
        "comments:toggle_close": [rows["comment"].pk],
        "comments:delete_comment": [rows["comment"].pk],
    }


def build():
    """The church the pages are drawn from: build_church()'s one of
    everything, with the Advent Sunday's occasion, the Mass template's
    slots and a hymn added, so the service page and the pew sheet have
    something in them."""
    from accounts.models import Invitation, User
    from accounts.organisations import create_organisation
    from library.models import HymnEntry
    from ordo.models import occasion_for_date
    from planning.models import RolePiece, ServiceRole, SlotTemplate
    from precentor_project.test_isolation import build_church

    rows = build_church("Validation")
    service = rows["service"]
    service.occasion = (occasion_for_date(service.date, "current") or [None])[0]
    service.save()
    service.use_template(SlotTemplate.objects.get(organisation=rows["church"], name="Mass"))
    hymn_slot = ServiceRole.objects.create(service=service, role_name="Entrance hymn")
    RolePiece.objects.create(service_role=hymn_slot, hymn_entry=rows["hymn_entry"])
    rows["other_hymn"] = HymnEntry.find_or_make(rows["hymnal"], "2").hymn
    rows["viewer"] = User.objects.create_user(
        email="viewer@example.com", password=PASSWORD, organisation=rows["church"], role="viewer",
    )
    _, join_token = Invitation.make(organisation=rows["church"], role="viewer", created_by=rows["owner"])
    empty = create_organisation("Empty church")
    rows["newcomer"] = User.objects.create_user(
        email="new-owner@example.com", password=PASSWORD, organisation=empty, role="conductor", is_owner=True,
    )
    return rows, join_token


def client_for(user=None):
    # Marked as HTTPS the way Render's proxy marks it, so it isn't
    # redirected there.
    client = Client(HTTP_X_FORWARDED_PROTO="https")
    if user:
        client.force_login(user)
    return client


def pages(rows, join_token):
    """(name, response) for every page that answers a GET with HTML,
    then the pages that only appear after an action. Routes that answer
    otherwise are reported on stderr, with what they answered."""
    from precentor_project.test_isolation import all_routes

    known = addresses(rows, join_token)
    owner = client_for(rows["owner"])
    for name, pattern in sorted(all_routes().items()):
        if "<" in pattern and name not in known:
            sys.exit(f"Say in addresses() which row {name} ({pattern}) shows.")
        given = known.get(name, [])
        url = given if isinstance(given, str) else reverse(name, args=given)
        client = client_for() if name in SIGNED_OUT else owner
        response = client.get(url, follow=name == "password_reset_confirm")
        kind = response.get("Content-Type", "")
        if response.status_code == 200 and kind.startswith("text/html"):
            yield name, response
        else:
            print(f"  not a page: {name} answers GET with {response.status_code} {kind}", file=sys.stderr)

    yield "404 page", owner.get("/no-such-page/")
    yield "500 page", server_error(RequestFactory().get("/"))
    yield "403 page (a Viewer adding a term)", client_for(rows["viewer"]).get(reverse("planning:term_create"))
    yield "Log in, wrong password", client_for().post(
        reverse("login"), {"username": rows["owner"].email, "password": "wrong"}
    )
    yield "Score form with mistakes", owner.post(reverse("library:score_create"), {})
    yield "Join, link no longer valid", client_for().get(reverse("join", args=["no-such-token"]))
    yield "Join, already signed in", owner.get(reverse("join", args=[join_token]))
    yield "Delete my account, as a member", client_for(rows["member"]).get(reverse("delete_account"))
    yield "Reset link for a member", owner.post(reverse("members:reset_link", args=[rows["member"].pk]))
    yield "Use another template, asked first", owner.post(
        reverse("planning:apply_template", args=[rows["service"].pk, rows["template"].pk])
    )
    yield "Terms, a new church's first steps", client_for(rows["newcomer"]).get(reverse("planning:term_list"))
    yield "Account deleted", client_for(rows["viewer"]).post(reverse("delete_account"), {"password": PASSWORD})
    yield "Church deleted", client_for(rows["newcomer"]).post(reverse("delete_church"), {"name": "Empty church"})


def check(html):
    """The checker's messages for one page, sent with curl. The checker
    sits behind Cloudflare, which answers Python's own HTTP requests with
    a "Just a moment..." challenge page but lets curl through. If the
    answer isn't the checker's JSON, wait and ask again, a little longer
    each time."""
    for wait in (15, 30, 60, 120, None):
        answer = subprocess.run(
            ["curl", "--silent", "--max-time", "60", "--user-agent", "precentor-validate",
             "--header", "Content-Type: text/html; charset=utf-8", "--data-binary", "@-", CHECKER],
            input=html, capture_output=True,
        )
        try:
            reply = json.loads(answer.stdout)
            return reply["messages"], reply.get("version", "unknown")
        except (json.JSONDecodeError, KeyError):
            if wait is None:
                return None
            print(f"  the checker didn't answer; waiting {wait} s", file=sys.stderr)
            time.sleep(wait)


def main():
    # The checker's messages have curly quotes; Windows would otherwise
    # write a redirected file in its own code page.
    sys.stdout.reconfigure(encoding="utf-8")
    setup_test_environment()
    test_db = connection.creation.create_test_db(verbosity=0, autoclobber=True)
    try:
        # With DEBUG off the pages name the hashed files collectstatic
        # makes, as Render's build does (into staticfiles/, ignored by git).
        call_command("collectstatic", interactive=False, verbosity=0)
        call_command("load_calendar", stdout=io.StringIO())
        rows, join_token = build()
        wanted = set(sys.argv[1:])
        results, unchecked, version = [], [], "unknown"
        for name, response in pages(rows, join_token):
            if wanted and name not in wanted:
                continue
            answer = None if unchecked else check(response.content)
            if answer is None:
                unchecked.append(name)
                continue
            messages, version = answer
            errors = [m for m in messages if m["type"] in ("error", "non-document-error")]
            warnings = [m for m in messages if m.get("subType") == "warning"]
            results.append((name, response.status_code, errors, warnings))
            print(f"  {name}: {len(errors)} errors, {len(warnings)} warnings", file=sys.stderr)
            time.sleep(PAUSE)
    finally:
        connection.creation.destroy_test_db(test_db, verbosity=0)

    unknown = wanted - {name for name, *_ in results} - set(unchecked)
    if unknown:
        print(f"No page is called {', '.join(sorted(unknown))}.", file=sys.stderr)
    if unchecked:
        names = " ".join(f'"{name}"' if " " in name else name for name in unchecked)
        print(f"The checker stopped answering. To check the rest later:\n\n"
              f"    python tools/validate_html.py {names}\n", file=sys.stderr)
    print(f"Checked on {date.today().day} {date.today():%B %Y} by the Nu HTML Checker {version}")
    print()
    print("| Page | Status | Errors | Warnings |")
    print("| ---- | ------ | ------ | -------- |")
    for name, status, errors, warnings in results:
        print(f"| {name} | {status} | {len(errors)} | {len(warnings)} |")
    print()
    for name, _, errors, warnings in results:
        for message in errors + warnings:
            label = "Error" if message in errors else "Warning"
            print(f"- {name}, line {message.get('lastLine', '?')}: {label}: {message['message']}")


if __name__ == "__main__":
    main()
