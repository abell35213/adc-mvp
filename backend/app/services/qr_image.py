"""QR-code helpers for printable artifacts.

Generates a PNG QR code as a base64 data URI so it can be inlined into HTML
templates rendered by WeasyPrint without WeasyPrint having to fetch any
external URL.
"""

from __future__ import annotations

import base64
import io
import logging

logger = logging.getLogger(__name__)


def qr_png_data_uri(payload: str, *, box_size: int = 10, border: int = 2) -> str | None:
    """Return ``data:image/png;base64,...`` for ``payload`` or ``None`` on error.

    Returning ``None`` instead of raising lets the calling template degrade
    gracefully (showing the token as text) when the optional ``qrcode``
    dependency or its imaging backend is unavailable in a given runtime.
    """
    try:
        import qrcode  # type: ignore
    except Exception:  # pragma: no cover - dependency missing
        logger.warning("qrcode library not available; QR image will be omitted")
        return None

    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
    except Exception:
        logger.exception(
            "Failed to generate QR PNG for payload of length %d", len(payload)
        )
        return None

    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
