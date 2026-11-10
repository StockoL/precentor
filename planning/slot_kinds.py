"""
What kind of music a slot holds, and for a proper, which one. The kind
decides how a slot is shown and grouped; the proper part says which chant
of the Mass or Office it is, so the day's proper can be found for it.

The set of kinds is fixed here, but any one slot's kind can be changed:
a slot called Introit can hold a hymn and be shown as one.
"""

KIND_CHOICES = [
    ("proper", "Proper"),
    ("ordinary", "Ordinary"),
    ("hymn", "Hymn"),
    ("psalm", "Psalm"),
    ("canticle", "Canticle"),
    ("antiphon", "Antiphon"),
    ("responsory", "Responsory"),
    ("motet", "Motet"),
    ("organ", "Organ"),
    ("other", "Other"),
]

PROPER_PART_CHOICES = [
    ("introit", "Introit"),
    ("gradual", "Gradual"),
    ("alleluia", "Alleluia"),
    ("tract", "Tract"),
    ("alleluia_or_tract", "Alleluia or Tract"),
    ("sequence", "Sequence"),
    ("offertory", "Offertory"),
    ("communion", "Communion"),
    ("magnificat_antiphon", "Magnificat antiphon"),
]

# Well-known slot names, as (kind, proper part). Offertory and Communion on
# their own are the propers, as in the Mass template; "Offertory hymn" and
# "Communion motet" are caught by their last word below.
NAMES = {
    "introit": ("proper", "introit"),
    "gradual": ("proper", "gradual"),
    "alleluia": ("proper", "alleluia"),
    "tract": ("proper", "tract"),
    "alleluia or tract": ("proper", "alleluia_or_tract"),
    "sequence": ("proper", "sequence"),
    "offertory": ("proper", "offertory"),
    "offertory antiphon": ("proper", "offertory"),
    "communion": ("proper", "communion"),
    "communion antiphon": ("proper", "communion"),
    "magnificat antiphon": ("antiphon", "magnificat_antiphon"),
    "kyrie": ("ordinary", ""),
    "gloria": ("ordinary", ""),
    "credo": ("ordinary", ""),
    "sanctus": ("ordinary", ""),
    "sanctus and benedictus": ("ordinary", ""),
    "agnus dei": ("ordinary", ""),
    "mass setting": ("ordinary", ""),
    "magnificat": ("canticle", ""),
    "nunc dimittis": ("canticle", ""),
    "benedictus": ("canticle", ""),
    "te deum": ("canticle", ""),
    "anthem": ("motet", ""),
    "organ": ("organ", ""),
}

# Otherwise the last word decides: "Communion hymn", "Offertory motet",
# "Opening voluntary", "Marian antiphon", "Responsorial psalm".
LAST_WORDS = {
    "hymn": "hymn",
    "hymns": "hymn",
    "psalm": "psalm",
    "psalms": "psalm",
    "antiphon": "antiphon",
    "responsory": "responsory",
    "responsories": "responsory",
    "canticle": "canticle",
    "canticles": "canticle",
    "motet": "motet",
    "anthem": "motet",
    "voluntary": "organ",
    "prelude": "organ",
    "postlude": "organ",
}


def classify(name):
    """A slot name's (kind, proper part), whatever its case and spacing:
    ("proper", "introit") for Introit, ("other", "") for a name it
    doesn't know."""
    name = " ".join(name.split()).lower()
    if name in NAMES:
        return NAMES[name]
    words = name.split()
    if words and words[-1] in LAST_WORDS:
        return LAST_WORDS[words[-1]], ""
    return "other", ""


# Kinds whose music is usually a number in a book or a chant, not a score
# in the library, so the add-piece form offers a reference box first.
REFERENCE_FIRST = {"hymn", "psalm", "antiphon", "responsory"}

# Kinds a day can have several chants of, outside the Mass's propers:
# Palm Sunday's antiphons, hymn and responsory, the Easter Vigil's
# canticles. A slot of one of these kinds is offered the day's chants of it.
MANY_CHANT_KINDS = {"antiphon", "responsory", "hymn", "canticle"}
