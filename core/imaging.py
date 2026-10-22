import io

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

# ~4:1 banner slot, wide enough for a small crest-plus-text graphic or a
# standalone wide banner. A tunable starting point, not a fixed decision —
# adjust here (and in static/src/js/crest-crop.js's matching constants) if
# the design needs a different slot once real content is in front of us.
TARGET_SIZE = (1600, 400)
MIN_SIZE = (800, 200)
# A logo keeps its own shape, fitted inside this box.
LOGO_MAX_SIZE = (600, 600)
LOGO_MIN_SIDE = 150
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}


def _open_image(uploaded_file):
    """The upload as a Pillow image, once it's known to be a real PNG,
    JPEG or WebP, in a mode that can be saved as one."""
    uploaded_file.seek(0)
    try:
        Image.open(uploaded_file).verify()
    except (UnidentifiedImageError, OSError):
        raise ValidationError("That file doesn't look like a valid image.")

    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    if image.format not in ALLOWED_FORMATS:
        raise ValidationError(
            "Please upload a PNG, JPEG, or WebP image "
            "(SVG and other formats aren't supported)."
        )
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")
    return image


def _encode(image):
    """PNG when there's transparency to keep, otherwise a JPEG."""
    buffer = io.BytesIO()
    save_format = "PNG" if image.mode == "RGBA" else "JPEG"
    image.save(buffer, format=save_format, quality=90)
    extension = "png" if save_format == "PNG" else "jpg"
    return ContentFile(buffer.getvalue(), name=f"crest.{extension}")


def process_crest_image(uploaded_file, target_size=TARGET_SIZE):
    """
    Validates format/resolution and normalises a crest upload to exactly
    target_size, regardless of whether it arrived already cropped by
    crest-crop.js (a cheap no-op resize) or raw via the no-JS fallback
    (centre-cropped to the target aspect ratio here). This is the single
    source of truth for what a saved crest looks like.
    """
    image = _open_image(uploaded_file)
    if image.width < MIN_SIZE[0] or image.height < MIN_SIZE[1]:
        raise ValidationError(
            f"Image is too small — please upload at least "
            f"{MIN_SIZE[0]}×{MIN_SIZE[1]}px."
        )

    target_ratio = target_size[0] / target_size[1]
    width, height = image.size
    current_ratio = width / height
    if abs(current_ratio - target_ratio) > 0.01:
        if current_ratio > target_ratio:
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            image = image.crop((left, 0, left + new_width, height))
        else:
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            image = image.crop((0, top, width, top + new_height))

    if image.size != target_size:
        image = image.resize(target_size, Image.LANCZOS)

    return _encode(image)


def process_logo_image(uploaded_file, max_size=LOGO_MAX_SIZE):
    """
    A logo shown beside the church's name keeps its own shape, since
    logos are seldom exactly square and cropping would cut into them. A
    large one is scaled down to fit inside max_size; a small one is left
    as it is rather than blown up.
    """
    image = _open_image(uploaded_file)
    if min(image.size) < LOGO_MIN_SIDE:
        raise ValidationError(
            f"This image is too small. Choose one at least {LOGO_MIN_SIDE}px on its shorter side."
        )
    image.thumbnail(max_size, Image.LANCZOS)
    return _encode(image)
