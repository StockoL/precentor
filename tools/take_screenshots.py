"""
Takes the README screenshots with Playwright, from the demo church made by
tools/seed_demo.py. For screenshots only.

Point the session at the screenshots database (see seed_demo.py), seed
it, then serve it and run this in a second terminal with the same
DATABASE_URL:

    $env:DATABASE_URL = "sqlite:///screenshots.sqlite3"
    python manage.py runserver 8766
    python tools/take_screenshots.py

The images go to docs/screenshots/, numbered in the order the README shows
them, and are reduced to 256 colours if they would be over 300 KB.
"""

import io
import os
import sys
import time
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "precentor_project.settings")
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
django.setup()

from PIL import Image  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from library.models import Score  # noqa: E402
from ordo.models import LiturgicalSeason  # noqa: E402
from planning.models import Service, Term  # noqa: E402

BASE = "http://127.0.0.1:8766"
OUT = ROOT / "docs" / "screenshots"
PASSWORD = "demo-precentor-2026"
DESKTOP = {"width": 1280, "height": 800}
MOBILE = {"width": 390, "height": 844}
LIMIT = 300 * 1024


def save(png, name):
    """Write the PNG, cutting it to 256 colours if it's too large."""
    path = OUT / name
    image = Image.open(io.BytesIO(png))
    image.save(path, optimize=True)
    if path.stat().st_size > LIMIT:
        image.convert("RGB").quantize(colors=256).save(path, optimize=True)
    print(f"{name}: {path.stat().st_size // 1024} KB")


def browser_for(browser, viewport=DESKTOP, scheme="light", email=None):
    context = browser.new_context(viewport=viewport, color_scheme=scheme, reduced_motion="reduce")
    page = context.new_page()
    if email:
        page.goto(BASE + "/accounts/login/")
        page.fill("#id_username", email)
        page.fill("#id_password", PASSWORD)
        page.click("main button.btn-primary")
        page.wait_for_url(BASE + "/")
    return context, page


def shot(page, url, name, full_page=True):
    page.goto(BASE + url)
    page.wait_for_load_state("networkidle")
    save(page.screenshot(full_page=full_page), name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    advent = Term.objects.get(name="Advent 2026")
    first_mass = Service.objects.filter(term=advent, service_type="Sung Mass").order_by("date").first()
    third_mass = Service.objects.filter(term=advent, service_type="Sung Mass").order_by("date")[2]
    score = Score.objects.get(title="Ave Maria", composer_surname="Parsons")
    advent_season = LiturgicalSeason.objects.get(name="Advent")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        # Getting started, as someone new.
        context, page = browser_for(browser)
        shot(page, "/accounts/login/", "01-sign-in.png", full_page=False)
        shot(page, "/accounts/signup/", "02-register.png")
        page.fill("#id_church_name", "St Hilda's, Whitby")
        page.fill("#id_name", "Sam Carter")
        page.fill("#id_email", f"sam{int(time.time())}@sthilda.example")
        page.fill("#id_password1", PASSWORD)
        page.fill("#id_password2", PASSWORD)
        page.click("main button.btn-primary")
        page.wait_for_url(BASE + "/")
        save(page.screenshot(), "03-first-steps.png")
        # Another church's score, from this new church: not found. The
        # local .env runs with DEBUG on, which shows Django's debug page,
        # so the live site's 404 is rendered with DEBUG off and shown here.
        from django.test import Client, override_settings

        from accounts.models import User

        newcomer = User.objects.filter(email__endswith="@sthilda.example").latest("date_joined")
        with override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"]):
            client = Client()
            client.force_login(newcomer)
            html = client.get(f"/library/{score.pk}/").content.decode()
        page.set_content(html)
        page.wait_for_load_state("networkidle")
        save(page.screenshot(), "18-not-found.png")
        context.close()

        # Planning, the library and the rest, as the conductor who owns it.
        context, page = browser_for(browser, email="conductor@stealred.example")
        shot(page, "/", "04-terms.png")
        shot(page, f"/terms/{advent.pk}/", "05-term.png")
        shot(page, f"/services/{first_mass.pk}/", "06-service.png")
        page.goto(BASE + f"/services/{third_mass.pk}/")
        page.wait_for_load_state("networkidle")
        picker = page.locator(".score-combobox__input").first
        picker.scroll_into_view_if_needed()
        picker.click()
        picker.fill("a")
        page.wait_for_timeout(300)
        save(page.screenshot(), "07-propose-a-piece.png")
        shot(page, f"/library/?suited_season={advent_season.pk}", "08-library-filtered.png")
        shot(page, f"/library/{score.pk}/", "09-score.png")
        page.goto(BASE + "/library/add/")
        page.click("main button.btn-primary")
        page.wait_for_load_state("networkidle")
        save(page.screenshot(), "10-score-form-errors.png")
        shot(page, f"/library/{score.pk}/delete/", "11-delete-confirmation.png", full_page=False)
        shot(page, f"/terms/{advent.pk}/music-list/", "12-music-list.png")
        shot(page, "/comments/inbox/", "13-inbox.png")
        shot(page, "/settings/", "14-settings.png")
        page.goto(BASE + "/members/invite/")
        page.check("input[value=viewer]")
        page.fill("#id_note", "Anne, alto")
        page.click("main button.btn-primary")
        page.wait_for_load_state("networkidle")
        save(page.screenshot(), "15-invitation-link.png")
        shot(page, "/members/", "16-members.png")
        context.close()

        # Accessibility and responsive design.
        context, page = browser_for(browser, email="viewer@stealred.example")
        shot(page, "/terms/add/", "17-forbidden.png", full_page=False)
        context.close()

        context, page = browser_for(browser, viewport=MOBILE, email="conductor@stealred.example")
        shot(page, "/", "19-mobile-terms.png")
        shot(page, f"/services/{first_mass.pk}/", "20-mobile-service.png")
        shot(page, "/library/", "21-mobile-library.png")
        context.close()

        context, page = browser_for(browser, scheme="dark", email="conductor@stealred.example")
        shot(page, f"/services/{first_mass.pk}/", "22-dark-service.png")
        context.close()

        context, page = browser_for(browser, email="conductor@stealred.example")
        page.goto(BASE + "/")
        page.wait_for_load_state("networkidle")
        for _ in range(3):
            page.keyboard.press("Tab")
        save(page.screenshot(), "23-keyboard-focus.png")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
