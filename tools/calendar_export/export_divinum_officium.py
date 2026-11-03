"""
One-off export of the 1962 Missal's proper chants from Divinum Officium.

Divinum Officium (https://github.com/DivinumOfficium/divinum-officium) is
MIT-licensed, and its liturgical texts are in the public domain. This
script reads its Latin Mass files and writes, into
ordo/data/divinum_officium/:

  propers_1962.json   the opening words (incipit) of each day's Introit,
                      Gradual, Alleluia, Tract, Sequence, Offertory and
                      Communion, keyed like the 1962 occasions, for
                      manage.py load_calendar

Only the incipits are kept, never the full texts. Divinum Officium's file
names are the keys Ordo already uses for 1962 days (tempora:Adv1-0 is
Tempora/Adv1-0.txt), as Missalemeum, which the calendar came from, is
built on the same files. Run it on a checkout of the commit named in
SOURCE (see README.md for a sparse checkout of the folders it reads):

  python export_divinum_officium.py PATH/TO/divinum-officium
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ordo" / "data" / "divinum_officium" / "propers_1962.json"
SOURCE = (
    "Divinum Officium (https://github.com/DivinumOfficium/divinum-officium) at commit db57fc0, "
    "MIT licence; the liturgical texts are in the public domain"
)
DO = Path(sys.argv[1]) / "web" / "www"
# The Mass's own days, and the Commons and saints' Office files, which
# the Mass files lean on for anything they don't say themselves.
FOLDERS = {
    "Tempora": [DO / "missa" / "Latin" / "Tempora"],
    "Sancti": [DO / "missa" / "Latin" / "Sancti"],
    "Commune": [DO / "horas" / "Latin" / "Commune"],
}
OFFICE_SANCTI = DO / "horas" / "Latin" / "Sancti"
# Words an incipit cut short shouldn't end on.
SMALL_WORDS = {"a", "ab", "ad", "cum", "de", "e", "et", "ex", "in", "per", "pro", "qui", "quia", "sub", "super", "ut"}
ALLELUIA = re.compile(r"allel[uú]ja,\s*allel[uú]ja", re.I)


def find(path):
    folder, _, name = path.partition("/")
    for directory in FOLDERS.get(folder, []):
        if (directory / f"{name}.txt").exists():
            return directory / f"{name}.txt"
    return None


def read_sections(file):
    """A file's sections as {name: [lines]}. Headings with a condition,
    such as "[Rank] (rubrica 1960)", are for other rubrics and skipped."""
    sections, name = {}, None
    for line in file.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^\[([^\]]+)\]\s*(\(.*\))?\s*$", line)
        if heading:
            name = None if heading.group(2) else heading.group(1)
            if name:
                sections[name] = []
        elif name:
            sections[name].append(line)
    return sections


def full_path(reference):
    """A reference as a folder and name: "C6" is a Common, "Adv1-0" a day
    of the Proper of Time and "12-08" a saint's day."""
    reference = reference.strip().rstrip(";")
    if "/" in reference:
        return reference
    if re.match(r"^C\d", reference):
        return "Commune/" + reference
    return ("Sancti/" if re.match(r"^\d\d-\d\d", reference) else "Tempora/") + reference


_cache = {}


def sections(path):
    """A file's sections, with any it doesn't have taken from the file
    its first line names ("@Commune/C6"), as Divinum Officium does."""
    if path not in _cache:
        _cache[path] = {}
        file = find(path)
        if file:
            own = read_sections(file)
            first = file.read_text(encoding="utf-8").lstrip().splitlines()[0]
            if first.startswith("@"):
                for name, body in sections(full_path(first[1:])).items():
                    own.setdefault(name, body)
            _cache[path] = own
    return _cache[path]


def borrows_from(path):
    """The Common or day named by a "vide C4a" or "ex Sancti/01-25" rule,
    looked for in the Mass file and then in the saint's Office file."""
    rules = list(sections(path).get("Rule", []))
    office = OFFICE_SANCTI / f"{path.partition('/')[2]}.txt"
    if path.startswith("Sancti/") and office.exists():
        rules += read_sections(office).get("Rule", [])
    for line in rules:
        rule = re.match(r"^(vide|ex)\s+([^;]+)", line.strip())
        if rule:
            return full_path(rule.group(2))
    return None


def lines_for(path, part, depth=0):
    """The lines of one part of a day's Mass, following its references."""
    if depth > 8:
        return None
    body = sections(path).get(part)
    if body is not None:
        text = [line for line in body if line.strip()]
        # The first line after any scripture citations may point elsewhere:
        # "@Commune/C3:Offertorium", or "@Commune/C3::s/…/" with a change
        # to the words, which doesn't touch the opening.
        first = next((line for line in text if not line.startswith("!")), "")
        if first.startswith("@"):
            target, _, target_part = first[1:].partition(":")
            target_part = target_part.split()[0] if target_part and not target_part.startswith(":") else part
            return lines_for(full_path(target) if target else path, target_part, depth + 1)
        return text
    source = borrows_from(path)
    if source and source != path:
        return lines_for(source, part, depth + 1)
    # A weekday with nothing of its own sings the Sunday's Mass. Holy
    # Week's reformed days (Quad6-5r, "r" for the 1955 reform) aren't
    # weekdays of Palm Sunday: their ceremonies are listed by hand below.
    weekday = re.match(r"^(Tempora/.+?\d)-[1-6](?!r)", path)
    if weekday:
        return lines_for(f"{weekday.group(1)}-0", part, depth + 1)
    return None


def words_of(line):
    """The chant's text on a line, without verse marks or citations."""
    line = line.strip()
    if not line or line[0] in "!&$(_@":
        return None
    line = re.sub(r"^[vVR]\.\s*", "", line)
    line = re.sub(r"\([^)]*\)\s*", "", line)  # rubrics, such as (Hic genuflectitur)
    line = re.sub(r"\(?allel[uú]ja[.,)]*", "", line, flags=re.I).strip()
    return line or None


def incipit(line):
    """The opening words: up to the first punctuation, or the next if that
    is a single word, at most five words, with the accents the texts are
    printed with removed (Ad te levávi is indexed as Ad te levavi)."""
    clauses = re.split(r"(?<=[,:;.!?])\s+", line)
    words = clauses[0].split()
    if len(words) < 2 and len(clauses) > 1:
        words += clauses[1].split()
    words = words[:5]
    while len(words) > 2 and words[-1].lower().strip(",") in SMALL_WORDS:
        words.pop()
    text = " ".join(words).rstrip(",:;.!?")
    decomposed = unicodedata.normalize("NFD", text)
    return unicodedata.normalize("NFC", "".join(c for c in decomposed if c not in "́̀"))


def first_words(lines):
    for line in lines or []:
        words = words_of(line)
        if words:
            return incipit(words)
    return None


def split_gradual(lines):
    """A Graduale block as {part: incipit}. Usually the Gradual and then the
    Alleluia verse after "Allelúja, allelúja"; in Lent the Tract after a
    !Tractus line; in Eastertide two Alleluia verses and no Gradual, the
    first sung where the Gradual would be."""
    lines = lines or []
    texts = [(i, words_of(line)) for i, line in enumerate(lines)]
    texts = [(i, words) for i, words in texts if words]
    if not texts:
        return {}
    first = next((line for line in lines if line.strip() and not line.startswith("!")), "")
    if ALLELUIA.match(first.strip()):
        verses = [incipit(words) for _, words in texts]
        return {"gradual": verses[0], "alleluia": verses[1]} if len(verses) > 1 else {"alleluia": verses[0]}
    parts = {"gradual": incipit(texts[0][1])}
    # "!Tractus", sometimes followed by its psalm verses ("!Tractus 21:2-9").
    tract = next((i for i, line in enumerate(lines) if re.match(r"!Tractus\b", line.strip())), None)
    if tract is not None:
        parts["tract"] = next((incipit(words) for i, words in texts if i > tract), None)
        return parts
    marker = next((i for i, line in enumerate(lines) if ALLELUIA.search(line)), None)
    if marker is not None:
        parts["alleluia"] = next((incipit(words) for i, words in texts if i > marker), None)
    return parts


# On days with extra readings, the chant after the last of them, which
# Divinum Officium doesn't mark as anything but the Graduale.
AFTER_LAST_READING = {
    "Tempora/Adv3-6": "tract",
    "Tempora/Quad1-3": "tract",
    "Tempora/Quad1-6": "tract",
    "Tempora/093-6": "tract",
    "Tempora/Quad6-3": "tract",
    "Tempora/Pasc7-6": "alleluia",
}


def reading_chants(path):
    """The chants after the extra readings before the Epistle on the Ember
    days and a few Lenten Wednesdays, in order: a Gradual after each (an
    Alleluia in Pentecost week), and on the Saturdays the Benedictus es
    sung after the reading from Daniel."""
    found = []
    for number in range(1, 6):
        if f"GradualeL{number}" in sections(path):
            # Only the chant itself, not the Gloria that can follow it.
            lines = lines_for(path, f"GradualeL{number}") or []
            lines = lines[: lines.index("_")] if "_" in lines else lines
            texts = [line for line in lines if not line.startswith("!")]
            part = "alleluia" if texts and re.match(r"^allel[uú][ij]a\.?$", texts[0].strip(), re.I) else "gradual"
            words = next((words_of(line) for line in texts[part == "alleluia":] if words_of(line)), None)
            if words:
                found.append((part, "", incipit(words)))
        if f"LectioL{number}" in sections(path):
            lines = lines_for(path, f"LectioL{number}") or []
            hymn = next((i for i, line in enumerate(lines) if line.strip() == "!Hymnus"), None)
            if hymn is not None:
                found.append(("canticle", "", first_words(lines[hymn + 1:])))
    return found


def chants(path):
    """Every chant of a day, as (part, season, incipit), in the order sung."""
    found = []
    for part, section in (("introit", "Introitus"), ("offertory", "Offertorium"), ("communion", "Communio")):
        words = first_words(lines_for(path, section))
        if words:
            found.append((part, "", words))
    found += reading_chants(path)
    gradual = split_gradual(lines_for(path, "Graduale"))
    if path in AFTER_LAST_READING and list(gradual) == ["gradual"]:
        gradual = {AFTER_LAST_READING[path]: gradual["gradual"]}
    for part, words in gradual.items():
        if words:
            found.append((part, "", words))
    # Only the few days with a Sequence of their own have one, so it isn't
    # looked for in a Common or the Sunday, unless the day's rule asks for
    # it: All Souls' Dies iræ is in the Requiem Common.
    rule = [line.strip() for line in sections(path).get("Rule", [])]
    if "Sequentia" in sections(path) or "Sequentia" in rule:
        sequence = first_words(lines_for(path, "Sequentia"))
        if sequence:
            found.append(("sequence", "", sequence))
    # A saint's day keeps its forms for Lent and Eastertide; the days of
    # the Proper of Time already belong to one season.
    if path.startswith("Sancti/"):
        tract = first_words(lines_for(path, "Tractus"))
        if tract:
            found.append(("tract", "septuagesima", tract))
        for part, words in split_gradual(lines_for(path, "GradualeP")).items():
            if words:
                found.append((part, "paschaltide", words))
    return found


def keys():
    """The 1962 occasions' keys, from the calendar files Ordo loads."""
    seen = []
    for name in ("missalemeum/general_1962.json", "lms/england_1962.json", "lms/wales_1962.json"):
        for occasion in json.loads((ROOT / "ordo" / "data" / name).read_text(encoding="utf-8"))["occasions"]:
            if occasion["key"] not in seen:
                seen.append(occasion["key"])
    return seen


def main():
    rows, missing = [], []
    for key in keys():
        kind, _, name = key.partition(":")
        path = f"{kind.capitalize()}/{name}"
        found = chants(path) if find(path) else []
        if not found:
            missing.append(key)
        # A day with several chants of one part, such as an Ember Saturday's
        # graduals, numbers them in the order sung from the second on.
        counted = {}
        for part, season, words in found:
            row = {"key": key, "part": part, "season": season, "incipit": words, "source": path}
            position = counted[part, season] = counted.get((part, season), -1) + 1
            if position:
                row["position"] = position
            rows.append(row)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"source": SOURCE, "chants": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"{len(rows)} chants for {len({row['key'] for row in rows})} days; none for {len(missing)}:")
    print(" ".join(missing))


if __name__ == "__main__":
    main()
