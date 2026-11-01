"""
Each page's JavaScript modules, and what they import. A module a page's
scripts import should already be on the page, from base.html or the page
itself, or be preloaded with <link rel="modulepreload">, so the browser
fetches it at once rather than only after its importer has arrived.
"""

import re

from django.conf import settings
from django.test import SimpleTestCase

JS_DIR = settings.BASE_DIR / "static" / "src" / "js"
LOADED = re.compile(r"""<script type="module" src="\{% static 'src/js/([\w-]+\.js)' %\}">""")
PRELOADED = re.compile(r"""<link rel="modulepreload" href="\{% static 'src/js/([\w-]+\.js)' %\}">""")
IMPORTS = re.compile(r"""^import .* from "\./([\w-]+\.js)";""", re.M)


def imports_of(module, seen=None):
    """Everything a module imports, and what those import in turn."""
    seen = set() if seen is None else seen
    for name in IMPORTS.findall((JS_DIR / module).read_text(encoding="utf-8")):
        if name not in seen:
            seen.add(name)
            imports_of(name, seen)
    return seen


def templates():
    for folder in [settings.BASE_DIR / "templates", *settings.BASE_DIR.glob("*/templates")]:
        yield from folder.rglob("*.html")


class ModulePreloadTests(SimpleTestCase):
    def test_every_import_is_on_the_page_or_preloaded(self):
        base = LOADED.findall((settings.BASE_DIR / "templates" / "base.html").read_text(encoding="utf-8"))
        for template in templates():
            text = template.read_text(encoding="utf-8")
            loaded = LOADED.findall(text)
            if not loaded or template.name == "base.html":
                continue
            available = set(base) | set(loaded) | set(PRELOADED.findall(text))
            needed = set().union(*(imports_of(module) for module in loaded))
            with self.subTest(template=template.name):
                self.assertEqual(sorted(needed - available), [], "Add a modulepreload link for these")

    def test_the_import_reader_finds_imports(self):
        self.assertEqual(imports_of("service-detail.js"),
                         {"ajax.js", "toast.js", "score-picker.js", "confirm-dialog.js"})
