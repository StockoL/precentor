import json
import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


def start_django(code="", **env):
    """Start Django in a fresh process with some environment variables
    changed, since settings are read once, when Django starts, then run
    any code given."""
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup(); " + code],
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


def read_settings(*names, **env):
    """The named settings as Django sees them with this environment."""
    result = start_django(
        "from django.conf import settings; import json; "
        f"print(json.dumps([getattr(settings, name) for name in {list(names)!r}]))",
        **env,
    )
    return json.loads(result.stdout)


class HostSettingsTests(SimpleTestCase):
    def test_hosts_and_origins_come_from_the_environment(self):
        hosts, origins = read_settings(
            "ALLOWED_HOSTS", "CSRF_TRUSTED_ORIGINS",
            ALLOWED_HOSTS="precentor.example.org, www.precentor.example.org",
            CSRF_TRUSTED_ORIGINS="https://precentor.example.org",
        )
        self.assertEqual(hosts, ["precentor.example.org", "www.precentor.example.org"])
        self.assertEqual(origins, ["https://precentor.example.org"])

    def test_nothing_set_means_no_extra_hosts(self):
        self.assertEqual(read_settings("ALLOWED_HOSTS", ALLOWED_HOSTS=""), [[]])


class HttpsSettingsTests(SimpleTestCase):
    NAMES = ("SECURE_SSL_REDIRECT", "SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE", "SECURE_HSTS_SECONDS")

    def test_once_deployed_everything_is_https_only(self):
        self.assertEqual(read_settings(*self.NAMES, DEBUG="False"), [True, True, True, 3600])

    def test_locally_none_of_it_applies(self):
        self.assertEqual(read_settings(*self.NAMES, DEBUG="True"), [False, False, False, 0])

    def test_the_deploy_check_is_clean(self):
        result = subprocess.run(
            [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
            env={
                # Not the variable the browser tests set for Playwright, which
                # the deploy check rightly refuses on a live server.
                **{k: v for k, v in os.environ.items() if k != "DJANGO_ALLOW_ASYNC_UNSAFE"},
                "DEBUG": "False",
                # Long and varied enough for Django's own key check.
                "SECRET_KEY": "only-for-the-deploy-check-test-0123456789-abcdefghijklmnop",
                "ALLOWED_HOSTS": "precentor.example.org",
            },
            cwd=settings.BASE_DIR, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
