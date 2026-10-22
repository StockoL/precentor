import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


def start_django(**env):
    """Start Django in a fresh process with some environment variables
    changed, since settings are read once, when Django starts."""
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "precentor_project.settings", **env},
        cwd=settings.BASE_DIR,
        capture_output=True,
        text=True,
    )


class SecretKeyTests(SimpleTestCase):
    def test_starting_without_a_secret_key_fails_with_a_plain_reason(self):
        # An empty variable counts as missing, and python-dotenv won't
        # replace it with the value in .env.
        result = start_django(SECRET_KEY="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SECRET_KEY is not set", result.stderr)

    def test_starting_with_one_works(self):
        self.assertEqual(start_django(SECRET_KEY="a-test-key").returncode, 0)
