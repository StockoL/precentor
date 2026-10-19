import re

from django.core.exceptions import ValidationError

# One note in scientific pitch notation: a letter, an optional sharp or
# flat, and an octave number, where C4 is middle C.
NOTE = r"([A-Ga-g])([#b♯♭]?)(\d)"
# Two notes, low to high, joined by a hyphen or a dash, spaces allowed.
RANGE = re.compile(rf"^\s*{NOTE}\s*[-–—]\s*{NOTE}\s*$")

SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ACCIDENTALS = {"": 0, "#": 1, "♯": 1, "b": -1, "♭": -1}
TIDY_ACCIDENTAL = {"": "", "#": "#", "♯": "#", "b": "b", "♭": "b"}

EXAMPLE = "A3–E5"


def _pitch(letter, accidental, octave):
    """Semitones above C0, so two notes can be compared."""
    return int(octave) * 12 + SEMITONES[letter.upper()] + ACCIDENTALS[accidental]


def validate_vocal_range(value):
    """A range from low to high in note names, such as A3–E5."""
    match = RANGE.match(value)
    if not match:
        raise ValidationError(
            f"Enter the lowest and highest notes, such as {EXAMPLE}.", code="format"
        )
    low, high = match.group(1, 2, 3), match.group(4, 5, 6)
    if _pitch(*low) > _pitch(*high):
        raise ValidationError(
            f"Put the lower note first, as in {EXAMPLE}.", code="order"
        )


def tidy_vocal_range(value):
    """The stored form: capital letters, # or b, and an en dash, so
    'a3 - e5' is kept as 'A3–E5'. Assumes the value has validated."""
    match = RANGE.match(value)
    if not match:
        return value
    letter1, acc1, oct1, letter2, acc2, oct2 = match.groups()
    return (
        f"{letter1.upper()}{TIDY_ACCIDENTAL[acc1]}{oct1}"
        f"–{letter2.upper()}{TIDY_ACCIDENTAL[acc2]}{oct2}"
    )
