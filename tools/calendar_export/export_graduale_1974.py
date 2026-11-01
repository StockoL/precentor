"""
One-off export of the Ordinary Form's proper chants for Sundays and the
major feasts, as the Graduale Romanum (1974) assigns them, from the
index "Propers of the Mass for the Church Year", a six-page PDF table.

It writes ordo/data/graduale_1974/propers_current.json, which manage.py
load_calendar loads: each day's Introit, Gradual, Alleluia, Tract,
Sequence, Offertory and Communion by its opening words, keyed like the
Ordinary Form occasions in ordo/data/romcal/, with a year of the Sunday
cycle where the Graduale gives one ("A: Tolle puerum").

The PDF's text is read with each piece's position, as its columns sit at
fixed distances from the left edge; read as plain text, a year's
alternative loses the column it belongs to. Each row's name in the
Calendar column must match the next name in DAYS exactly, or the script
stops, so a misread row can't pass unnoticed.

Run it with pypdf installed, in an environment of its own:

  python export_graduale_1974.py PATH/TO/propers1974.pdf
"""

import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

OUT = Path(__file__).resolve().parents[2] / "ordo" / "data" / "graduale_1974" / "propers_current.json"
SOURCE = "Graduale Romanum (1974), Sundays and major feasts"

# The columns' left edges in points, and the chant in each.
CALENDAR, INTROIT, GRADUAL, OFFERTORY, COMMUNION = 42, 122, 257, 384, 483
COLUMN_PARTS = {INTROIT: "introit", OFFERTORY: "offertory", COMMUNION: "communion"}
# Marks that start an entry in any column; the processional antiphons,
# responsories and hymns of Palm Sunday and the Presentation have no slot.
MARKS = {"IN.": "introit", "GR.": "gradual", "AL.": "alleluia", "TR.": "tract", "SEQ.": "sequence",
         "ANT.": None, "RESP.": None, "HYM.": None, "CANT.": None, "VARIA:": None, "CONCLUSIO:": None}

# Some Lent Sundays give a chant for when a particular Gospel is read,
# which belongs to one year of the cycle: the prodigal son is the fourth
# Sunday's Gospel in Year C; Lazarus is the fifth Sunday's in Year A and
# the woman taken in adultery its Gospel in Year C.
GOSPELS = {"prodigal son": "C", "lazarus": "A", "the adulteress": "C"}
GOSPEL = re.compile(r"\s*If gospel reading is ([^:]+):\s*")

# Rows the table can't be read right from its layout alone, each checked
# against the PDF: (occasion, part, year) -> the opening words, or None to
# leave a chant out.
FIXES = {
    # The next line, Lux fulgebit, is an alternative, not more of the words.
    ("mary_mother_of_god", "introit", ""): "Salve, sancta Parens",
    # "vel. Ecce advenit" is set outside the column, leaving "advenit".
    ("presentation_of_the_lord", "introit", ""): "Suscepimus",
    # Likewise "vel. Sanctificavit" after it.
    ("most_holy_body_and_blood_of_christ", "offertory", ""): "Portas caeli",
    # Marked SEQ. in the index, but Trinity Sunday has no Sequence.
    ("most_holy_trinity", "sequence", ""): None,
    # Misprinted "Sancticavit".
    ("ordinary_time_18_sunday", "offertory", "C"): "Sanctificavit",
}

# Every row of the table in order: its name as printed, and the Ordinary
# Form occasion it is, or None for a row with no day of its own.
DAYS = [
    ("First Sunday of Advent", "advent_1_sunday"),
    ("Immaculate Conception", "immaculate_conception_of_the_blessed_virgin_mary"),
    ("Second Sunday of Advent", "advent_2_sunday"),
    ("Third Sunday of Advent", "advent_3_sunday"),
    ("Fourth Sunday of Advent", "advent_4_sunday"),
    ("Nativity Mass at Midnight", None),  # Ordo has one Christmas; the Mass during the Day is used
    ("Nativity Mass at Day", "nativity_of_the_lord"),
    ("Holy Family", "holy_family_of_jesus_mary_and_joseph"),
    ("Blessed Virgin Mary", "mary_mother_of_god"),
    ("Epiphany", "epiphany_of_the_lord"),
    ("Baptism of the Lord", "baptism_of_the_lord"),
    ("Second Sunday", "ordinary_time_2_sunday"),
    ("Third Sunday", "sunday_of_the_word_of_god"),  # how the calendar keys it since 2019
    ("Presentation of the Lord", "presentation_of_the_lord"),
    ("Fourth Sunday", "ordinary_time_4_sunday"),
    ("Fifth Sunday", "ordinary_time_5_sunday"),
    ("Sixth Sunday", "ordinary_time_6_sunday"),
    ("Seventh Sunday", "ordinary_time_7_sunday"),
    ("Eighth Sunday", "ordinary_time_8_sunday"),
    ("Ash Wednesday", "ash_wednesday"),
    ("First Sunday in Lent", "lent_1_sunday"),
    ("Second Sunday in Lent", "lent_2_sunday"),
    ("Third Sunday in Lent", "lent_3_sunday"),
    ("Annunciation of the Lord", "annunciation_of_the_lord"),
    ("Fourth Sunday in Lent", "lent_4_sunday"),
    ("Fifth Sunday in Lent", "lent_5_sunday"),
    ("Palm Sunday", "palm_sunday_of_the_passion_of_the_lord"),
    ("Maundy Thursday", "thursday_of_the_lords_supper"),
    ("Good Friday", None),  # no Mass
    ("Easter Vigil", None),  # part of Easter, which has its own row
    ("Easter Sunday", "easter_sunday"),
    ("Second Sunday of Easter", "divine_mercy_sunday"),
    ("Third Sunday of Easter", "easter_time_3_sunday"),
    ("Fourth Sunday of Easter", "easter_time_4_sunday"),
    ("Fifth Sunday of Easter", "easter_time_5_sunday"),
    ("Sixth Sunday of Easter", "easter_time_6_sunday"),
    ("Ascension of the Lord", "ascension_of_the_lord"),
    ("Seventh Sunday of Easter", "easter_time_7_sunday"),
    ("Pentecost", "pentecost_sunday"),
    ("Most Holy Trinity", "most_holy_trinity"),
    ("Body and Blood of Christ", "most_holy_body_and_blood_of_christ"),
    ("Ninth Sunday", "ordinary_time_9_sunday"),
    ("Tenth Sunday", "ordinary_time_10_sunday"),
    ("Eleventh Sunday", "ordinary_time_11_sunday"),
    ("Twelfth Sunday", "ordinary_time_12_sunday"),
    ("Nativity of John the Baptist", "nativity_of_john_the_baptist"),
    ("Saints Peter and Paul", "peter_and_paul_apostles"),
    ("Thirteenth Sunday", "ordinary_time_13_sunday"),
    ("Fourteenth Sunday", "ordinary_time_14_sunday"),
    ("Fifteenth Sunday", "ordinary_time_15_sunday"),
    ("Sixteenth Sunday", "ordinary_time_16_sunday"),
    ("Seventeenth Sunday", "ordinary_time_17_sunday"),
    ("Eighteenth Sunday", "ordinary_time_18_sunday"),
    ("Transfiguration of the Lord", "transfiguration_of_the_lord"),
    ("Nineteenth Sunday", "ordinary_time_19_sunday"),
    ("Assumption of the Blessed Virgin Mary", "assumption_of_the_blessed_virgin_mary"),
    ("Twentieth Sunday", "ordinary_time_20_sunday"),
    ("Twenty-first Sunday", "ordinary_time_21_sunday"),
    ("Twenty-second Sunday", "ordinary_time_22_sunday"),
    ("Twenty-third Sunday", "ordinary_time_23_sunday"),
    ("Birth of the Blessed Virgin Mary", "nativity_of_the_blessed_virgin_mary"),
    ("Exaltation of the Holy Cross", "exaltation_of_the_holy_cross"),
    ("Twenty-fourth Sunday", "ordinary_time_24_sunday"),
    ("Twenty-fifth Sunday", "ordinary_time_25_sunday"),
    ("Twenty-sixth Sunday", "ordinary_time_26_sunday"),
    ("Twenty-seventh Sunday", "ordinary_time_27_sunday"),
    ("Twenty-eighth Sunday", "ordinary_time_28_sunday"),
    ("Twenty-ninth Sunday", "ordinary_time_29_sunday"),
    ("Thirtieth Sunday", "ordinary_time_30_sunday"),
    ("Solemnity of All Saints", "all_saints"),
    ("Commemoration of the Faithful Departed", "commemoration_of_all_the_faithful_departed"),
    ("Thirty-first Sunday", "ordinary_time_31_sunday"),
    ("Thirty-second Sunday", "ordinary_time_32_sunday"),
    ("Thirty-third Sunday", "ordinary_time_33_sunday"),
    ("Presentation of the Blessed Virgin Mary", "presentation_of_the_blessed_virgin_mary"),
    ("Christ the King", "our_lord_jesus_christ_king_of_the_universe"),
]


def pieces(pdf):
    """Every piece of text as (page, y from the top, column, text)."""
    found = []
    for number, page in enumerate(PdfReader(pdf).pages):
        def visit(text, cm, tm, font, size, number=number, height=page.mediabox.height):
            text = text.replace("\xa0", " ").replace("­", "-").strip()
            x = round(tm[4] + cm[4])
            column = min((CALENDAR, INTROIT, GRADUAL, OFFERTORY, COMMUNION), key=lambda edge: abs(edge - x))
            if text and abs(column - x) <= 6:
                found.append((number, round(float(height) - (tm[5] + cm[5])), column, text))
        page.extract_text(visitor_text=visit)
    return sorted(found)


def rows(found):
    """Each table row as (name, its pieces), by joining Calendar lines until
    they spell the next name in DAYS."""
    # Below each page's column headings: page one starts with a key to
    # the abbreviations, set close to the Calendar column.
    headings = {page: y for page, y, column, text in found if column == CALENDAR and text == "Calendar"}
    calendar = [p for p in found if p[2] == CALENDAR and p[1] > headings[p[0]]]
    starts, i = [], 0
    for name, _ in DAYS:
        joined, first = "", i
        while i < len(calendar) and normal(joined) != normal(name):
            joined = f"{joined} {calendar[i][3]}" if joined else calendar[i][3]
            i += 1
        if normal(joined) != normal(name):
            sys.exit(f'Expected the row "{name}" but read "{joined}"')
        starts.append(calendar[first][:2])
    # A row runs from its name's first line to the next row's.
    # The headings repeated at the top of each page are left out.
    for (name, _), start, end in zip(DAYS, starts, starts[1:] + [(99, 0)]):
        yield name, [p for p in found if start <= p[:2] < end and p[2] != CALENDAR and p[1] > headings[p[0]] + 15]


def normal(text):
    """A name as compared: hyphens and line-break joins ignored."""
    return re.sub(r"[\s-]+", "", text).casefold()


def incipit(text):
    """The opening words as the index prints them, without a psalm verse
    after "...", an alternative after "vel.", or a note in brackets."""
    text = re.split(r"\.\.\.|\s+vel\.(?:\s+|$)|;|\(|\s+ad\.? lib\b|Imposition of Ashes", text)[0]
    return " ".join(text.split()).strip(" ,;:-")


def entries(column, lines):
    """One column's lines in a row as (part, cycle, incipit) entries. A
    line starting with a mark or a year starts an entry; any other line
    continues the one before."""
    found = []
    for line in lines:
        if line == "none":
            continue
        mark = next((m for m in MARKS if line == m or line.startswith(m + " ")), None)
        rest = line[len(mark):].strip() if mark else line
        year = re.match(r"^([ABC]):\s*", rest)
        if mark or year or not found:
            part = MARKS[mark] if mark else (COLUMN_PARTS.get(column) or (found[-1][0] if found else None))
            found.append([part, year.group(1) if year else "", rest[year.end():] if year else rest])
        else:
            found[-1][2] += " " + line
    split = []
    for part, cycle, text in found:
        # "Laudate Dominum If gospel reading is prodigal son: Illumina…"
        pieces = GOSPEL.split(text)
        split.append((part, cycle, pieces[0]))
        split += [(part, GOSPELS[gospel.lower()], words) for gospel, words in zip(pieces[1::2], pieces[2::2])]
    return [(part, cycle, incipit(text)) for part, cycle, text in split if part and incipit(text)]


def settle(chants):
    """
    One day's chants put in order. In Eastertide two Alleluias are sung,
    the first where the Gradual would be: listed as a pair ("- Exivi a
    Patre - Ego vos elegi") or as two Alleluias on a day without a Gradual,
    the first goes in the Gradual's place. Otherwise a second chant for
    the same part and year is an alternative and the first is kept.
    """
    paired = []
    for part, cycle, words in chants:
        first, _, second = words.partition(" - ")
        if part == "alleluia" and second:
            paired += [("gradual", cycle, first.strip(" -")), ("alleluia", cycle, second.strip(" -"))]
        else:
            paired.append((part, cycle, words.strip(" -")))
    if not any(part == "gradual" for part, _, _ in paired):
        plain = [i for i, (part, cycle, _) in enumerate(paired) if part == "alleluia" and not cycle]
        if len(plain) >= 2:
            paired[plain[0]] = ("gradual", "", paired[plain[0]][2])
    settled = {}
    for part, cycle, words in paired:
        settled.setdefault((part, cycle), words)
    return settled


def main():
    chants, by_name = [], dict(DAYS)
    for name, found in rows(pieces(sys.argv[1])):
        key = by_name[name]
        if key is None:
            continue
        day = []
        for column in (INTROIT, GRADUAL, OFFERTORY, COMMUNION):
            day += entries(column, [text for page, y, col, text in sorted(found) if col == column])
        for (part, cycle), words in settle(day).items():
            words = FIXES.get((key, part, cycle), words)
            if words:
                chants.append({"key": key, "part": part, "cycle": cycle, "incipit": words, "source": name})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": SOURCE, "chants": chants}, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    print(f"{len(chants)} chants for {len({c['key'] for c in chants})} days")


if __name__ == "__main__":
    main()
