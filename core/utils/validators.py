import re

# utils/validators.py
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_hex_color(value):
    """Validate hex color codes."""
    if not re.match(r"^#[0-9a-fA-F]{6}$", value):
        raise ValidationError(_("Enter a valid hex color code (e.g., #dc2626)"))


def validate_slug_format(value):
    """Validate slug format."""
    if not re.match(r"^[-\w]+$", value):
        raise ValidationError(_("Slug can only contain letters, numbers, and hyphens."))


def validate_cloudinary_url(value):
    """Validate Cloudinary URL format."""
    if not value.startswith(
        ("https://res.cloudinary.com/", "https://cloudinary-a.akamaihd.net/")
    ):
        raise ValidationError(_("Please provide a valid Cloudinary URL."))


def validate_social_media_url(platform, value):
    """Validate social media URLs."""
    patterns = {
        "facebook": r"https?://(www\.)?facebook\.com/.+",
        "twitter": r"https?://(www\.)?twitter\.com/.+",
        "linkedin": r"https?://(www\.)?linkedin\.com/.+",
        "youtube": r"https?://(www\.)?youtube\.com/.+",
        "instagram": r"https?://(www\.)?instagram\.com/.+",
    }

    pattern = patterns.get(platform.lower())
    if pattern and not re.match(pattern, value):
        raise ValidationError(_(f"Please provide a valid {platform.title()} URL."))
