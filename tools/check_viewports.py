"""
Opens every main page at five widths in each of Playwright's three
browser engines and reports, for the testing record, anything wider
than the window and any error in the console.

It uses the demo church from tools/seed_demo.py, served as for the
README screenshots:

    $env:DATABASE_URL = "sqlite:///screenshots.sqlite3"
    python tools/seed_demo.py
    python manage.py runserver 8766
    python tools/check_viewports.py > viewports.md

in a second terminal with the same DATABASE_URL for the last line. A
page passes when nothing makes the page scroll sideways. The library's
table is allowed to be wider than a phone, as it scrolls inside its own
box; that box is checked instead.
"""

import os
import sys
from datetime import date
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "precentor_project.settings")
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
django.setup()

from playwright.sync_api import sync_playwright  # noqa: E402

from library.models import Hymnal, Score  # noqa: E402
from planning.models import Service, SlotTemplate, Term  # noqa: E402

BASE = "http://127.0.0.1:8766"
PASSWORD = "demo-precentor-2026"
WIDTHS = (320, 375, 768, 1024, 1280)
HEIGHT = 900

# Measured in the page: how far the page scrolls sideways, and the
# element that sticks out furthest past the right edge, if any.
OVERFLOW = """() => {
    const width = document.documentElement.clientWidth;
    const extra = document.documentElement.scrollWidth - width;
    let widest = null, right = width;
    for (const el of document.querySelectorAll("body *")) {
        if (el.closest(".table-scroll, [data-scroll]")) continue;
        const box = el.getBoundingClientRect();
        if (box.width && box.right > right + 0.5) { right = box.right; widest = el; }
    }
    const name = widest && (widest.tagName.toLowerCase() + (widest.id ? "#" + widest.id : "")
        + (widest.className && typeof widest.className === "string" ? "." + widest.className.split(" ")[0] : ""));
    return {extra, widest: name, by: Math.round(right - width)};
}"""


def pages():
    """(name, address, signed in) for every main page."""
    advent = Term.objects.get(name="Advent 2026")
    church = advent.organisation
    service = Service.objects.filter(term=advent, service_type="Sung Mass").order_by("date").first()
    score = Score.objects.get(organisation=church, title="Ave Maria", composer_surname="Parsons")
    hymnal = Hymnal.objects.get(organisation=church, short_name="SAH")
    hymn = hymnal.entries.order_by("number").first().hymn
    mass = SlotTemplate.objects.get(organisation=church, name="Mass")
    introit = service.roles.get(role_name="Introit")
    return [
        ("Sign in", "/accounts/login/", False),
        ("Register", "/accounts/signup/", False),
        ("Privacy", "/privacy/", False),
        ("Terms", "/", True),
        ("A term", f"/terms/{advent.pk}/", True),
        ("A service", f"/services/{service.pk}/", True),
        ("Propose a piece", f"/roles/{introit.pk}/pieces/add/", True),
        ("Pew sheet", f"/services/{service.pk}/sheet/", True),
        ("Music list", f"/terms/{advent.pk}/music-list/", True),
        ("Library", "/library/", True),
        ("A score", f"/library/{score.pk}/", True),
        ("Add a score", "/library/add/", True),
        ("Completeness", "/library/completeness/", True),
        ("Import", "/library/import/", True),
        ("Imports", "/library/imports/", True),
        ("Hymnals", "/library/hymnals/", True),
        ("A hymnal", f"/library/hymnals/{hymnal.pk}/", True),
        ("A hymn", f"/library/hymns/{hymn.pk}/", True),
        ("Tunes", "/library/tunes/", True),
        ("Templates", "/templates/", True),
        ("Edit a template", f"/templates/{mass.pk}/edit/", True),
        ("Inbox", "/comments/inbox/", True),
        ("Settings", "/settings/", True),
        ("Members", "/members/", True),
        # None: rendered as the live site renders it (see not_found_page).
        ("Not found (404)", None, True),
    ]


def sign_in(context):
    page = context.new_page()
    page.goto(BASE + "/accounts/login/")
    page.fill("#id_username", "conductor@stealred.example")
    page.fill("#id_password", PASSWORD)
    page.click("main button.btn-primary")
    page.wait_for_url(BASE + "/")
    page.close()


def not_found_page():
    """The 404 page as the live site shows it. My .env runs the local
    server with DEBUG on, which answers a made-up address with Django's
    debug page instead, so it's rendered here with DEBUG off, as
    take_screenshots.py does."""
    from django.test import Client, override_settings

    from accounts.models import User

    with override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"]):
        client = Client()
        client.force_login(User.objects.get(email="conductor@stealred.example"))
        return client.get("/no-such-page/").content.decode()


def check(page, url, errors, not_found):
    errors.clear()
    if url is None:
        page.goto(BASE + "/")
        page.set_content(not_found)
    else:
        page.goto(BASE + url)
    page.wait_for_load_state("networkidle")
    return page.evaluate(OVERFLOW), list(errors)


def main():
    targets = pages()
    not_found = not_found_page()
    rows, versions = [], {}
    with sync_playwright() as playwright:
        for engine in (playwright.chromium, playwright.firefox, playwright.webkit):
            browser = engine.launch()
            versions[engine.name] = browser.version
            for width in WIDTHS:
                viewport = {"width": width, "height": HEIGHT}
                contexts = {False: browser.new_context(viewport=viewport), True: browser.new_context(viewport=viewport)}
                sign_in(contexts[True])
                tabs = {}
                for signed_in, context in contexts.items():
                    errors = []
                    page = context.new_page()
                    page.on("console", lambda m, errors=errors: m.type == "error" and errors.append(m.text))
                    page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                    tabs[signed_in] = (page, errors)
                for name, url, signed_in in targets:
                    page, errors = tabs[signed_in]
                    found, console = check(page, url, errors, not_found)
                    rows.append((name, width, engine.name, found, console))
                    status = "wider" if found["extra"] > 0 else "ok"
                    print(f"  {engine.name} {width} {name}: {status}, {len(console)} errors", file=sys.stderr)
                for context in contexts.values():
                    context.close()
            browser.close()

    failures = [r for r in rows if r[3]["extra"] > 0 or r[4]]
    print(f"Checked on {date.today().day} {date.today():%B %Y}: {len(targets)} pages, "
          f"{len(WIDTHS)} widths, {len(versions)} engines, {len(rows)} loads.")
    print()
    print("| Engine | Version |")
    print("| ------ | ------- |")
    for name, version in versions.items():
        print(f"| {name.capitalize()} | {version} |")
    print()
    print("| Page | " + " | ".join(f"{w} px" for w in WIDTHS) + " |")
    print("| ---- | " + " | ".join("------" for _ in WIDTHS) + " |")
    for name, _, _ in targets:
        cells = []
        for width in WIDTHS:
            bad = [r for r in rows if r[0] == name and r[1] == width and (r[3]["extra"] > 0 or r[4])]
            cells.append("Pass" if not bad else "Fail: " + ", ".join(r[2] for r in bad))
        print(f"| {name} | " + " | ".join(cells) + " |")
    print()
    for name, width, engine, found, console in failures:
        if found["extra"] > 0:
            print(f"- {name}, {width} px, {engine}: {found['extra']} px wider, by {found['widest']} ({found['by']} px)")
        for error in console:
            print(f"- {name}, {width} px, {engine}: console: {error}")
    if not failures:
        print("Every page fitted its window with no console errors, in every engine at every width.")


if __name__ == "__main__":
    main()
