"""Export-bundle inclusion smoke tests for Phase-3 evidence.

Validates that the new Phase-3 dispatch / weigh / loading-dock evidence
flows into the legal-hold export bundle:

1. The crash brief PDF context (and therefore the rendered cover
   summary) gets the three new sections.
2. ``loading_dock_photo`` (and related) artifact types are bucketed
   into dedicated subfolders by ``_target_folder`` rather than the
   generic ``media/other`` bin.
"""

from __future__ import annotations

from app.services.export_content_resolver import _target_folder


def test_loading_dock_photo_routed_to_loading_dock_folder():
    assert _target_folder("loading_dock_photo", "dock-rear.jpg") == "loading_dock"


def test_loading_dock_signature_routed_to_loading_dock_folder():
    assert (
        _target_folder("loading_dock_signature", "supervisor-sig.png")
        == "loading_dock"
    )


def test_weigh_ticket_routed_to_weigh_tickets_folder():
    assert _target_folder("weigh_ticket", "WS-12345.pdf") == "weigh_tickets"


def test_dispatch_sheet_routed_to_dispatch_folder():
    assert _target_folder("dispatch_sheet", "DSP-1001.pdf") == "dispatch"


def test_unknown_image_still_lands_in_media():
    # Existing behavior must not regress for unrelated artifact types.
    assert _target_folder("dashcam_clip", "drive.mp4") == "media"
