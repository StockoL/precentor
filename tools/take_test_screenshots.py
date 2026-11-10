"""
Takes the screenshots that docs/testing.md shows beside its rows, from
the demo church made by tools/seed_demo.py, served as for the README
screenshots:

    $env:DATABASE_URL = "sqlite:///screenshots.sqlite3"
    python tools/seed_demo.py
    python manage.py runserver 8766
    python tools/take_test_screenshots.py

The last line in a second terminal with the same DATABASE_URL. The
images go to docs/screenshots/testing/, named after the row they support
(r01-320-terms-chromium.png is row R01, at 320 pixels, in Chromium), and
are reduced to 256 colours if they would be over 300 KB. The printed
music list is also saved as a PDF, as Chromium prints it.
"""

import io
import os
import sys
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
from planning.models import Service, Term  # noqa: E402

BASE = "http://127.0.0.1:8766"
OUT = ROOT / "docs" / "screenshots" / "testing"
PASSWORD = "demo-precentor-2026"
LIMIT = 300 * 1024
IMPORT_FILE = "\r\n".join([
    "Title,Composer surname,Composer other names,Voicing,Language,Copies owned,Filing location",
    "Christus factus est,Anerio,Felice,,Latin,16,Cabinet 1",
    ",Victoria,Tomás Luis de,SATB,Latin,12,Cabinet 3",
]).encode("utf-8")


def save(png, name):
    """Write the PNG, cutting it to 256 colours if it's too large."""
    path = OUT / name
    image = Image.open(io.BytesIO(png))
    image.save(path, optimize=True)
    if path.stat().st_size > LIMIT:
        image.convert("RGB").quantize(colors=256).save(path, optimize=True)
    print(f"{name}: {path.stat().st_size // 1024} KB")


def open_page(browser, width, email="conductor@stealred.example", scheme="light"):
    context = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme,
                                  reduced_motion="reduce")
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


def not_found_page():
    """The 404 page with DEBUG off, as the live site shows it (see
    check_viewports.py)."""
    from django.test import Client, override_settings

    from accounts.models import User

    with override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"]):
        client = Client()
        client.force_login(User.objects.get(email="conductor@stealred.example"))
        return client.get("/no-such-page/").content.decode()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    advent = Term.objects.get(name="Advent 2026")
    service = Service.objects.filter(term=advent, service_type="Sung Mass").order_by("date").first()
    score = Score.objects.get(organisation=advent.organisation, title="Ave Maria", composer_surname="Parsons")
    key_pages = [("terms", "/"), ("service", f"/services/{service.pk}/"), ("library", "/library/")]

    with sync_playwright() as playwright:
        engines = {"chromium": playwright.chromium.launch(), "firefox": playwright.firefox.launch(),
                   "webkit": playwright.webkit.launch()}
        chromium = engines["chromium"]

        # R01 to R03: the key pages at a phone's, a tablet's and a laptop's
        # width, in Chromium; at 320 pixels in the other two engines too.
        for row, width in (("r01", 320), ("r02", 768), ("r03", 1280)):
            for engine_name, browser in engines.items():
                if engine_name != "chromium" and width != 320:
                    continue
                context, page = open_page(browser, width)
                # The window only: a whole service page at 320 pixels is
                # several thousand tall. check_viewports.py measures the rest.
                for name, url in key_pages:
                    shot(page, url, f"{row}-{width}-{name}-{engine_name}.png", full_page=False)
                context.close()

        context, page = open_page(chromium, 1280)
        # M04: a score form sent empty.
        page.goto(BASE + "/library/add/")
        page.click("main button.btn-primary")
        page.wait_for_load_state("networkidle")
        save(page.screenshot(), "m04-score-form-errors.png")
        # M06: the delete confirmation.
        shot(page, f"/library/{score.pk}/delete/", "m06-delete-confirmation.png", full_page=False)
        # M19: the music list as printed: the print styles as an image, and
        # Chromium's own PDF of it.
        page.goto(BASE + f"/terms/{advent.pk}/music-list/")
        page.wait_for_load_state("networkidle")
        page.emulate_media(media="print")
        save(page.screenshot(full_page=True), "m19-music-list-print.png")
        page.pdf(path=str(OUT / "m19-music-list.pdf"), format="A4", print_background=True)
        print("m19-music-list.pdf:", (OUT / "m19-music-list.pdf").stat().st_size // 1024, "KB")
        page.emulate_media(media="screen")
        # M27: the 404 page as the live site shows it.
        page.goto(BASE + "/")
        page.set_content(not_found_page())
        page.wait_for_load_state("networkidle")
        save(page.screenshot(), "m27-not-found.png")
        # M33: an import's result page, then the import removed again so
        # the demo church is left as it was.
        page.goto(BASE + "/library/import/")
        page.set_input_files("#id_file", {"name": "two-rows.csv", "mimeType": "text/csv", "buffer": IMPORT_FILE})
        page.click("main button.btn-primary")
        page.wait_for_url("**/library/import/*/")
        page.wait_for_load_state("networkidle")
        save(page.screenshot(full_page=True), "m33-import-result.png")
        page.click("text=Remove this import")
        page.click("main button.btn-danger")
        page.wait_for_url(BASE + "/library/")
        # M44 and M47: the pew sheet and the hymnal list.
        shot(page, f"/services/{service.pk}/sheet/", "m44-pew-sheet.png")
        shot(page, "/library/hymnals/", "m47-hymnals.png", full_page=False)
        # R04: keyboard focus, three presses of Tab from the top of Terms.
        page.goto(BASE + "/")
        page.wait_for_load_state("networkidle")
        for _ in range(3):
            page.keyboard.press("Tab")
        save(page.screenshot(), "r04-keyboard-focus.png")
        context.close()

        # M25: a Viewer refused.
        context, page = open_page(chromium, 1280, email="viewer@stealred.example")
        shot(page, "/terms/add/", "m25-forbidden.png", full_page=False)
        context.close()

        # R05: dark mode, from the device's setting.
        context, page = open_page(chromium, 1280, scheme="dark")
        for name, url in key_pages + [("music-list", f"/terms/{advent.pk}/music-list/"), ("settings", "/settings/")]:
            shot(page, url, f"r05-dark-{name}.png")
        context.close()

        for browser in engines.values():
            browser.close()


if __name__ == "__main__":
    main()
