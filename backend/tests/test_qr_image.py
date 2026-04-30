"""Unit tests for ``app.services.qr_image.qr_png_data_uri``."""

from __future__ import annotations

import base64
import sys

import pytest

from app.services import qr_image


def test_returns_data_uri_with_png_prefix_for_known_payload() -> None:
    result = qr_image.qr_png_data_uri("hello-world")

    if result is None:
        # ``qrcode`` (or its PIL backend) is not installed in this runtime.
        pytest.skip("qrcode/PIL not available in this environment")

    assert result.startswith("data:image/png;base64,")
    encoded = result.split(",", 1)[1]
    decoded = base64.b64decode(encoded)
    # PNG files always begin with the 8-byte signature \x89PNG\r\n\x1a\n.
    assert decoded.startswith(b"\x89PNG\r\n\x1a\n")


def test_returns_none_when_qrcode_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Hide ``qrcode`` (and any cached submodules) so the import inside
    # qr_png_data_uri raises ImportError, exercising the graceful-degrade
    # branch.
    for name in list(sys.modules):
        if name == "qrcode" or name.startswith("qrcode."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    real_import = (
        __builtins__["__import__"]
        if isinstance(__builtins__, dict)
        else __builtins__.__import__
    )

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "qrcode" or name.startswith("qrcode."):
            raise ImportError("forced for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", _fake_import)

    assert qr_image.qr_png_data_uri("any-payload") is None
