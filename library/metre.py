"""
A hymn's or a tune's metre, the syllables in each line of a verse, written
one way so that two can be compared. Books write the same metre as "88 88",
"8.8.8.8" or "LM"; all of those become "8.8.8.8". A match is necessary for a
tune to fit a text but not enough (stresses, refrains and repeats matter
too), so the app only ever says "same metre", never "fits".
"""

import re

# The short names, as books print them. A trailing D doubles the verse.
NAMES = {
    "LM": "8.8.8.8",
    "CM": "8.6.8.6",
    "SM": "6.6.8.6",
}

# Lines are rarely longer than this, so "10" and "11" are counts of their
# own, while "87" in "87 87" is an 8 and a 7.
TWO_DIGIT = {str(n) for n in range(10, 15)}


def normalise(metre):
    """
    The metre written one way: "88 88" and "LM" give "8.8.8.8", "LMD" and
    "LM D" give "8.8.8.8 D", "10 10 10 10" gives "10.10.10.10". Anything
    else, such as "Irregular", is kept as typed, and blank stays blank.
    """
    text = " ".join(metre.split())
    if not text:
        return ""
    upper = text.upper().replace(" ", "")
    doubled = upper.endswith("D") and len(upper) > 1
    core = upper[:-1] if doubled else upper
    if core in NAMES:
        return NAMES[core] + (" D" if doubled else "")
    counts = []
    for token in re.split(r"[.\s,]+", text.upper().removesuffix("D").strip()):
        if not token.isdigit():
            return text
        counts.extend([token] if token in TWO_DIGIT else list(token))
    return ".".join(counts) + (" D" if doubled else "")
