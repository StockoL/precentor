"""
The one stylesheet, static/src/precentor.css, is built from the source
files by build-css.js. These tests fail if a source has changed, or a new
one exists, since it was last built, so a forgotten build can't reach a
page. They read the files directly, so the suite doesn't need Node.
"""

import hashlib
import re
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase

SOURCE_DIR = settings.BASE_DIR / "static" / "src"
BUILT = SOURCE_DIR / "precentor.css"
# Linked on its own by the sign-in pages, never built in (it says why).
NO_TRANSITION = SOURCE_DIR / "no-page-transition.css"
REBUILD = "Run `node build-css.js` to build static/src/precentor.css again."


def header():
    text = BUILT.read_text(encoding="utf-8")
    return text[: text.index("*/")]


def listed_sources():
    return re.findall(r"^ \*   (\S+\.css)$", header(), re.M)


class OneStylesheetTests(SimpleTestCase):
    def test_every_source_file_is_in_it_once(self):
        on_disk = sorted(
            path.relative_to(SOURCE_DIR).as_posix()
            for path in SOURCE_DIR.rglob("*.css")
            if path not in (BUILT, NO_TRANSITION)
        )
        self.assertEqual(sorted(listed_sources()), on_disk, REBUILD)

    def test_it_was_built_from_the_sources_as_they_are_now(self):
        digest = hashlib.sha256()
        for name in listed_sources():
            text = (SOURCE_DIR / name).read_text(encoding="utf-8").replace("\r\n", "\n")
            digest.update(f"{name}\n{text}".encode("utf-8"))
        recorded = re.search(r"Fingerprint: ([0-9a-f]{64})", header()).group(1)
        self.assertEqual(recorded, digest.hexdigest(), REBUILD)

    def test_the_cascade_layers_are_declared_first(self):
        self.assertEqual(listed_sources()[0], "global/layers.css")

    def test_pages_link_only_the_one_stylesheet(self):
        base = (settings.BASE_DIR / "templates" / "base.html").read_text(encoding="utf-8")
        links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', base)
        self.assertEqual(links, ["{% static 'src/precentor.css' %}"])

    def test_no_template_has_a_style_block(self):
        # CSS belongs in the stylesheets. The HTML validator also reads
        # CSS inside a page, and flagged @view-transition when the
        # sign-in pages kept it in a <style> block.
        # The project's own template folders: the shared one, and those of
        # the apps that sit at the top of the project.
        folders = [settings.BASE_DIR / "templates"] + [
            Path(app.path) / "templates"
            for app in apps.get_app_configs()
            if Path(app.path).parent == settings.BASE_DIR
        ]
        templates = [path for folder in folders for path in folder.rglob("*.html")]
        self.assertGreater(len(templates), 50)
        for path in templates:
            with self.subTest(template=path.name):
                self.assertNotIn("<style", path.read_text(encoding="utf-8"))
