"""
Demo data for the README screenshots only. It makes an invented church,
St Aelred's, Ripon, with three people, a library, a hymn book of its
own, a past term, an Advent term and a 1962 Mass, using the app's own
models and create_organisation(). No real church, person or hymnal is
used: the hymn book's numbers are made up, and its first lines and the
one motet text are long out of copyright.

It writes to its own SQLite file, screenshots.sqlite3, not my
development database. settings.py reads the database from DATABASE_URL,
so setting that for one PowerShell session points everything run in
that session at the separate file:

    $env:DATABASE_URL = "sqlite:///screenshots.sqlite3"
    python tools/seed_demo.py

It migrates that file and loads the calendar into it first, and removes
the demo church and its people before adding them again, so it can be
run more than once. The file is ignored by git (*.sqlite3).
"""

import io
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "precentor_project.settings")
django.setup()

from django.core.management import call_command  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from accounts.models import Organisation, User  # noqa: E402
from accounts.organisations import create_organisation  # noqa: E402
from comments.models import Comment  # noqa: E402
from core.models import SiteConfig  # noqa: E402
from library.models import Hymnal, HymnEntry, Score  # noqa: E402
from ordo.models import LiturgicalSeason, UseType, occasion_for_date  # noqa: E402
from planning.models import RolePiece, Service, SlotTemplate, Term, TermMarker  # noqa: E402

PASSWORD = "demo-precentor-2026"
CHURCH = "St Aelred's, Ripon"

# Title, composer surname, other names, voicing, language, seasons.
SCORES = [
    ("Rorate caeli", "Plainchant", "", "Unison", "Latin", ["Advent"]),
    ("Ave Maria", "Parsons", "Robert", "SATBB", "Latin", ["Advent"]),
    ("Vigilate", "Byrd", "William", "SATBB", "Latin", ["Advent"]),
    ("This is the record of John", "Gibbons", "Orlando", "SATB", "English", ["Advent"]),
    ("Canite tuba", "Guerrero", "Francisco", "SATB", "Latin", ["Advent"]),
    ("O magnum mysterium", "Victoria", "Tomás Luis de", "SATB", "Latin", ["Christmas"]),
    ("Hodie Christus natus est", "Sweelinck", "Jan Pieterszoon", "SSATB", "Latin", ["Christmas"]),
    ("A spotless rose", "Howells", "Herbert", "SATB", "English", ["Christmas"]),
    ("Missa brevis", "Palestrina", "Giovanni Pierluigi da", "SATB", "Latin", []),
    ("Mass for four voices", "Byrd", "William", "SATB", "Latin", []),
    ("Missa O quam gloriosum", "Victoria", "Tomás Luis de", "SATB", "Latin", []),
    ("Magnificat primi toni", "Palestrina", "Giovanni Pierluigi da", "SATB", "Latin", []),
    ("Ave verum corpus", "Mozart", "Wolfgang Amadeus", "SATB", "Latin", []),
    ("Ave verum corpus", "Byrd", "William", "SATB", "Latin", []),
    ("Sicut cervus", "Palestrina", "Giovanni Pierluigi da", "SATB", "Latin", []),
    ("If ye love me", "Tallis", "Thomas", "SATB", "English", []),
    ("O sacrum convivium", "Tallis", "Thomas", "SATBB", "Latin", []),
    ("Os justi", "Bruckner", "Anton", "SATB", "Latin", []),
    ("Locus iste", "Bruckner", "Anton", "SATB", "Latin", []),
    ("Ubi caritas", "Duruflé", "Maurice", "SATB", "Latin", []),
    ("Alma Redemptoris Mater", "Plainchant", "", "Unison", "Latin", ["Advent", "Christmas"]),
    ("Salve Regina", "Plainchant", "", "Unison", "Latin", ["Ordinary Time"]),
    ("Justorum animae", "Stanford", "Charles Villiers", "SATB", "Latin", ["Ordinary Time"]),
    ("Beati quorum via", "Stanford", "Charles Villiers", "SSATBB", "Latin", ["Ordinary Time"]),
    ("Tantum ergo", "Séverac", "Déodat de", "SATB", "Latin", []),
]

# The church's own invented hymn book: a made-up number and a first line
# from a hymn long out of copyright. The last has no first line yet, so
# the completeness page has a hymn line to show.
HYMNS = [
    ("11", "Creator of the stars of night"),
    ("12", "O come, O come, Emmanuel"),
    ("14", "Lo, he comes with clouds descending"),
    ("16", "Hark the glad sound! the Saviour comes"),
    ("18", ""),
]

# The Ave Maria's words, with the prayer's usual English.
AVE_TEXT = (
    "Ave Maria, gratia plena,\nDominus tecum,\nbenedicta tu in mulieribus,\n"
    "et benedictus fructus ventris tui. Amen."
)
AVE_TRANSLATION = (
    "Hail Mary, full of grace,\nthe Lord is with thee;\nblessed art thou among women,\n"
    "and blessed is the fruit of thy womb. Amen."
)


def crest_png():
    """A plain invented emblem, drawn here so no real crest is used."""
    image = Image.new("RGB", (400, 400), "#f4efe6")
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 40, 360, 360), outline="#8b1a2b", width=18)
    draw.line((200, 90, 200, 310), fill="#8b1a2b", width=22)
    draw.line((120, 170, 280, 170), fill="#8b1a2b", width=22)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def person(church, email, name, role, is_owner=False):
    return User.objects.create_user(
        email=email, password=PASSWORD, name=name, organisation=church, role=role, is_owner=is_owner
    )


def service(term, day, service_type, template):
    occasions = occasion_for_date(day, term.calendar_use, "england")
    new = Service.objects.create(
        term=term, date=day, service_type=service_type, occasion=occasions[0] if occasions else None
    )
    new.use_template(template)
    return new


def fill(new_service, scores, confirmed=True, not_applicable=(), hymn=None):
    """Give each slot a piece, in turn, except those marked N/A. A Hymn
    slot takes the hymn entry, if one is given."""
    for number, slot in enumerate(new_service.roles.order_by("position")):
        if slot.role_name in not_applicable:
            slot.is_not_applicable = True
            slot.save()
            continue
        piece = {"hymn_entry": hymn} if hymn and slot.kind == "hymn" else {"score": scores[number % len(scores)]}
        RolePiece.objects.create(service_role=slot, is_confirmed=confirmed or number % 2 == 0, **piece)


def main():
    call_command("migrate", verbosity=0)
    call_command("createcachetable", verbosity=0)
    call_command("load_calendar", verbosity=0)
    # One at a time, as a queryset's delete() skips Organisation.delete(),
    # which clears what would otherwise protect the church's scores.
    for church in Organisation.objects.filter(name=CHURCH):
        church.delete()
    User.objects.filter(email__endswith="@stealred.example").delete()

    church = create_organisation(CHURCH)
    settings = SiteConfig.of(church)
    settings.church_name = CHURCH
    settings.national_calendar = "england"
    settings.set_crest(crest_png(), "image/png")
    settings.save()

    conductor = person(church, "conductor@stealred.example", "Clare Thornton", "conductor", is_owner=True)
    librarian = person(church, "librarian@stealred.example", "Tom Ashby", "librarian")
    viewer = person(church, "viewer@stealred.example", "Ruth Penrose", "viewer")

    seasons = {season.name: season for season in LiturgicalSeason.objects.all()}
    mass_use = UseType.objects.get(organisation=church, name="Mass")
    scores = []
    for number, (title, surname, others, voicing, language, tags) in enumerate(SCORES):
        score = Score.objects.create(
            organisation=church, title=title, composer_surname=surname, composer_other_names=others,
            voicing=voicing, language=language, copies_owned=12 + number % 20,
            filing_location=f"Cabinet {1 + number // 8}, drawer {1 + number % 8}",
        )
        score.suited_seasons.set([seasons[name] for name in tags if name in seasons])
        if title.startswith("Missa") or title.startswith("Mass"):
            score.suited_use_types.add(mass_use)
        scores.append(score)
    by_title = {score.title: score for score in scores}
    ave = by_title["Ave Maria"]
    ave.text, ave.translation = AVE_TEXT, AVE_TRANSLATION
    ave.translation_credit = "Traditional English"
    ave.save()

    hymnal = Hymnal.objects.create(
        organisation=church, name="St Aelred's Hymn Book", short_name="SAH",
        copies_owned=60, filing_location="Choir vestry",
    )
    hymns = []
    for number, first_line in HYMNS:
        entry = HymnEntry.find_or_make(hymnal, number)
        entry.hymn.first_line = first_line
        entry.hymn.save()
        hymns.append(entry)

    mass = SlotTemplate.objects.get(organisation=church, name="Mass")
    vespers = SlotTemplate.objects.get(organisation=church, name="Vespers")

    # A past term, so the library has "last sung" dates.
    michaelmas = Term.objects.create(
        organisation=church, name="Michaelmas 2026", start_date=date(2026, 9, 6),
        end_date=date(2026, 11, 22), calendar_use="current",
    )
    for day in (date(2026, 9, 13), date(2026, 9, 27), date(2026, 10, 11)):
        fill(service(michaelmas, day, "Sung Mass", mass), scores[8:20])

    advent = Term.objects.create(
        organisation=church, name="Advent 2026", start_date=date(2026, 11, 29),
        end_date=date(2026, 12, 24), calendar_use="current",
    )
    advent_music = [by_title[title] for title in (
        "Rorate caeli", "Missa brevis", "Vigilate", "Ave Maria", "Canite tuba",
        "This is the record of John", "Alma Redemptoris Mater",
    )]
    sundays = [date(2026, 11, 29) + timedelta(weeks=week) for week in range(4)]
    planned = []
    for week, sunday in enumerate(sundays):
        planned.append((service(advent, sunday, "Sung Mass", mass), week))
        planned.append((service(advent, sunday, "Vespers", vespers), week))
    feast = service(advent, date(2026, 12, 8), "Sung Mass", mass)
    service(advent, date(2026, 12, 24), "Midnight Mass", mass)  # left empty on purpose

    for new_service, week in planned:
        if week < 2:
            fill(new_service, advent_music, confirmed=True, not_applicable=("Gloria", "Credo"), hymn=hymns[week])
        elif week == 2:
            fill(new_service, advent_music, confirmed=False, not_applicable=("Gloria",), hymn=hymns[week])
    fill(feast, advent_music[1:], confirmed=True)

    # A Mass in the 1962 form, left empty, so its Proper slots offer the
    # day's chants from the 1962 Missal.
    extraordinary = Term.objects.create(
        organisation=church, name="Advent 2026, 1962 Missal", start_date=date(2026, 11, 29),
        end_date=date(2026, 12, 20), calendar_use="historic",
    )
    service(extraordinary, date(2026, 11, 29), "Missa cantata", mass)

    TermMarker.objects.create(term=advent, date=date(2026, 12, 1), text="Extra rehearsal for the carol service")
    TermMarker.objects.create(term=advent, date=date(2026, 12, 15), text="Copies of the Christmas music handed out")

    first_mass = planned[0][0]
    Comment.objects.create(
        author=librarian, target=first_mass, is_open=False,
        body="Twelve copies of the Parsons are in Cabinet 1, ready for Thursday.",
    )
    Comment.objects.create(
        author=conductor, target=advent, body="Can we keep the Vespers music the same for the first two weeks?",
    )
    Comment.objects.create(
        author=viewer, target=feast, body="Will the Immaculate Conception be at 7pm as usual?",
    )
    print(f"Seeded {CHURCH}: {len(scores)} scores, {Service.objects.filter(organisation=church).count()} services.")
    print(f"Sign in as conductor@, librarian@ or viewer@stealred.example with {PASSWORD}")


if __name__ == "__main__":
    main()
