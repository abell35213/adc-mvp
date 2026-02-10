"""Phone number normalization to E.164 format."""

import re


_DIGITS_RE = re.compile(r"\D")


def normalize_phone(raw: str) -> str:
    """Normalize a phone string to E.164 format (e.g. +15551234567).

    Accepts formats like:
      (555) 123-4567
      555-123-4567
      5551234567
      +1 555 123 4567
      15551234567

    Raises ValueError for invalid numbers.
    """
    digits = _DIGITS_RE.sub("", raw.strip())

    if len(digits) == 10:
        # US number without country code
        digits = "1" + digits
    elif len(digits) == 11 and digits.startswith("1"):
        # US number with country code
        pass
    else:
        raise ValueError("Invalid phone number")

    return f"+{digits}"
