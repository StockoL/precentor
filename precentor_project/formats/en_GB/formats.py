# Project date formats for en-gb, found through FORMAT_MODULE_PATH.
# Django checks this module before its own en_GB formats, so these two
# names are the single place the app's date style is set; anything not
# defined here (input formats, for instance) falls through to Django's.
# Syntax: https://docs.djangoproject.com/en/6.0/ref/templates/builtins/#date

DATE_FORMAT = "D j M Y"  # Sun 4 Oct 2026
DATETIME_FORMAT = "D j M Y, H:i"  # Sun 4 Oct 2026, 18:30
