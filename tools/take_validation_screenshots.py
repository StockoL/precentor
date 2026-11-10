"""
Screenshots of the checkers' own results, for docs/testing.md: the W3C
HTML checker on every main page, the W3C CSS validator on both
stylesheets, and Lighthouse's report on nine pages, desktop and mobile.

It uses the demo church from tools/seed_demo.py, served as for the
README screenshots:

    $env:DATABASE_URL = "sqlite:///screenshots.sqlite3"
    python tools/seed_demo.py
    python manage.py runserver 8766
    python tools/take_validation_screenshots.py

in a second terminal with the same DATABASE_URL for the last line. It
needs Google Chrome, and Node for Lighthouse, and opens a Chrome window.
Each page's HTML goes to the online checker through its text box,
because the checker can't sign in to fetch a page itself; that HTML is
the demo church's, all of it made up. Pass html, css or lighthouse to
take only those.
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Importing check_viewports sets up Django, and its page list is reused.
from check_viewports import BASE, not_found_page, pages, sign_in  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots" / "testing" / "checks"
LIMIT = 400 * 1024
LIGHTHOUSE_PAGES = ("Sign in", "Terms", "A service", "Library", "Music list",
                    "Pew sheet", "Completeness", "A hymnal", "Import")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def slug(name):
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def save(png, name):
    """Write the PNG, cutting it to 256 colours if it's too large."""
    path = OUT / name
    image = Image.open(io.BytesIO(png))
    image.save(path, optimize=True)
    if path.stat().st_size > LIMIT:
        image.convert("RGB").quantize(colors=256).save(path, optimize=True)
    print(f"{name}: {path.stat().st_size // 1024} KB")


def html_checks(browser, context):
    """Each main page's HTML, as the server sends it, through the W3C checker."""
    checker = browser.new_page(viewport={"width": 1100, "height": 800})
    for name, url, signed_in in pages():
        if url is None:
            source = not_found_page()
        else:
            client = context.request if signed_in else browser.new_context().request
            source = client.get(BASE + url).text()
        checker.goto("https://validator.w3.org/nu/#textarea")
        # The heading outline names the page in the screenshot.
        checker.check("#showoutline")
        checker.fill("textarea#doc", source)
        checker.click("#submit")
        checker.wait_for_selector("#results, .failure, .success, p.success, p.failure", timeout=60000)
        checker.wait_for_load_state("networkidle")
        summary = checker.locator("#results").inner_text().split("\n")[0]
        print(f"HTML {name}: {summary}")
        save(checker.screenshot(full_page=True), f"html-{slug(name)}.png")
        time.sleep(5)  # Spaced out, so the checker isn't hurried.
    checker.close()


def css_checks(browser):
    """Both stylesheets the site serves through the W3C CSS validator, CSS level 3."""
    page = browser.new_page(viewport={"width": 1100, "height": 800})
    for path in (ROOT / "static/src/precentor.css", ROOT / "static/src/no-page-transition.css"):
        page.goto("https://jigsaw.w3.org/css-validator/")
        page.click("a[href='#validate_by_upload']")
        page.click("#extra_opt_upload legend a")  # More Options
        page.set_input_files("#file", str(path))
        page.select_option("#profile_upload", "css3")
        # The form's own submit button is hidden behind a styled Check.
        page.locator("form:has(#file)").get_by_text("Check", exact=True).locator("visible=true").click()
        page.wait_for_selector("#results_container, #errors, #congrats", timeout=60000)
        print(f"CSS {path.name}: {page.locator('h2').first.inner_text()}")
        save(page.screenshot(full_page=True), f"css-{path.stem}.png")
        time.sleep(5)
    page.close()


def lighthouse_checks(browser, context):
    """Lighthouse 12.2.1's own report for nine pages, desktop and mobile:
    the scores at the top of each report."""
    npx = shutil.which("npx")
    session = next(c["value"] for c in context.cookies() if c["name"] == "sessionid")
    wanted = {name: (url, signed_in) for name, url, signed_in in pages() if name in LIGHTHOUSE_PAGES}
    viewer = browser.new_page(viewport={"width": 1000, "height": 700})
    with tempfile.TemporaryDirectory() as folder:
        for name in LIGHTHOUSE_PAGES:
            url, signed_in = wanted[name]
            header = f'{{"Cookie":"sessionid={session}"}}' if signed_in else "{}"
            for mode in ("desktop", "mobile"):
                report = Path(folder) / f"{slug(name)}-{mode}.html"
                command = [npx, "--yes", "lighthouse@12.2.1", BASE + url, "--quiet",
                           "--chrome-flags=--headless=new", f"--extra-headers={header}",
                           "--output=html", f"--output-path={report}"]
                if mode == "desktop":
                    command.append("--preset=desktop")
                subprocess.run(command, check=True, env={**os.environ, "CHROME_PATH": CHROME})
                viewer.goto(report.as_uri())
                viewer.wait_for_selector(".lh-scores-header")
                viewer.wait_for_timeout(2500)  # The gauges fill in as an animation.
                scores = viewer.locator(".lh-scores-header .lh-gauge__percentage").all_inner_texts()
                print(f"Lighthouse {name} {mode}: {scores}")
                # The address and the scores from the top of the report, over
                # its own note of when, on what device and with which version.
                bottom = viewer.locator(".lh-header-container").bounding_box()
                top = Image.open(io.BytesIO(viewer.screenshot(
                    clip={"x": 0, "y": 0, "width": 1000, "height": bottom["y"] + bottom["height"]})))
                meta = Image.open(io.BytesIO(viewer.locator(".lh-meta__items").screenshot()))
                both = Image.new("RGB", (top.width, top.height + meta.height + 16), "white")
                both.paste(top, (0, 0))
                both.paste(meta, ((top.width - meta.width) // 2, top.height + 16))
                buffer = io.BytesIO()
                both.save(buffer, "PNG")
                save(buffer.getvalue(), f"lighthouse-{slug(name)}-{mode}.png")
    viewer.close()


def main():
    wanted = set(sys.argv[1:]) or {"html", "css", "lighthouse"}
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context()
        sign_in(context)
        if "html" in wanted:
            html_checks(browser, context)
        if "css" in wanted:
            css_checks(browser)
        if "lighthouse" in wanted:
            lighthouse_checks(browser, context)
        browser.close()


if __name__ == "__main__":
    main()
