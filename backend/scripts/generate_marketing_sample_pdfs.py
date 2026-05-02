"""Generate the marketing-site sample PDF documents.

Produces three sample PDFs from a single coherent fictitious incident
("Carrier ABC") and writes them into ``frontend/public/samples/`` so the
marketing site can serve them as static assets:

  * adc-sample-executive-brief.pdf      (crash_brief template)
  * adc-sample-insurance-form.pdf       (insurance_form template, partial fill)
  * adc-sample-legal-defense-packet.pdf (legal_defense_packet template)

All data is fictitious; every page is watermarked "SAMPLE — fictitious data,
for demonstration only".

Usage (from repo root)::

    python -m backend.scripts.generate_marketing_sample_pdfs

or, equivalently, from inside ``backend/``::

    PYTHONPATH=. python scripts/generate_marketing_sample_pdfs.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

# Allow ``python scripts/generate_marketing_sample_pdfs.py`` from backend/.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.services.pdf_render import render_pdf  # noqa: E402

REPO_ROOT = _BACKEND_DIR.parent
OUTPUT_DIR = REPO_ROOT / "frontend" / "public" / "samples"


# ---------------------------------------------------------------------------
# Sample data — single coherent fictitious incident
# ---------------------------------------------------------------------------

CARRIER = {
    "name": "Carrier ABC",
    "dot_number": "999999",
    "address": "123 Main St., Emerald City, CA 10000",
    "safety_email": "safety@carrierabc.abc",
}

INCIDENT = {
    "incident_id": "INC-2026-04-17-0042",
    "status": "evidence_capturing",
    "severity": "moderate",
    "created_at_utc": "2026-04-17T14:32:18Z",
    "occurred_at_utc": "2026-04-17T14:31:55Z",
    "location_address": "Interstate 5 NB, mile marker 213, near Yellow Brick, CA",
    "location_lat": "37.7321",
    "location_lng": "-121.4042",
    "weather_road_conditions": "Light rain, wet pavement, daylight, visibility ~3 mi.",
    "police_report_number": "EC-PD-2026-118437",
    "narrative": (
        "While traveling northbound on I-5 in the right lane at approximately "
        "58 mph, the ADC tractor-trailer (Unit 4471) was struck on the rear "
        "passenger-side trailer corner by a passenger sedan attempting to merge "
        "from the right shoulder. The driver maintained lane control, activated "
        "hazards, and brought the unit to a controlled stop on the right shoulder "
        "approximately 0.4 miles north of the impact point. No injuries reported "
        "on scene. Both vehicles were drivable. Emerald City PD responded and "
        "filed report EC-PD-2026-118437. Driver completed the in-app capture "
        "protocol, including 360° photos, document scans, and a recorded "
        "statement, before clearing the scene."
    ),
}

DRIVER = {
    "driver_id": "DRV-CABC-00318",
    "display_name": "Dorothy Gale",
    "phone_e164": "+15555550118",
    "license_number": "D1234567",
    "license_state": "CA",
    "hire_date": "2023-08-14",
    "is_active": True,
}

DRIVER_HISTORY = [
    {
        "incident_id": "INC-2025-09-02-0019",
        "created_at_utc": "2025-09-02T18:11:00Z",
        "status": "closed",
        "severity": "minor",
    },
]

VEHICLE = {
    "unit_number": "4471",
    "vin": "1FUJGLDR8CSBM4471",
    "year": 2022,
    "make": "Freightliner",
    "model": "Cascadia",
    "provider": "Samsara",
}

TRAILER = {
    "adc_trailer_id": "TRL-CABC-22107",
    "vin": "1JJV532D9NL022107",
    "make": "Wabash",
    "model": "DuraPlate",
    "year": 2022,
    "plate": "CA 4Z 81293",
    "last_inspection_at_utc": "2026-03-28T09:14:00Z",
    "source": "tms_sync",
}

DISPATCH_INSTRUCTIONS = [
    {
        "dispatch_id": "DSP-2026-04-17-7781",
        "load_number": "L-778124",
        "dispatched_by": "Glinda Northman",
        "dispatched_at_utc": "2026-04-17T05:42:00Z",
        "pickup_appointment_at_utc": "2026-04-17T08:00:00Z",
        "delivery_appointment_at_utc": "2026-04-17T17:30:00Z",
        "eta_at_utc": "2026-04-17T17:05:00Z",
        "origin_address": "Munchkinland Distribution Center, 4400 Yellow Brick Rd., Munchkinland, CA",
        "destination_address": "Emerald City Logistics Hub, 9 Emerald Plaza, Emerald City, CA",
        "hos_remaining_drive_minutes": 410,
        "hos_remaining_duty_minutes": 530,
        "source": "tms_sync",
        "notes": "Standard dry-van run. No hazmat.",
        "forced_dispatch_flag": False,
    }
]

LOADING_DOCK_REPORTS = [
    {
        "loaded_at_utc": "2026-04-17T07:48:00Z",
        "facility_name": "Munchkinland DC",
        "facility_address": "4400 Yellow Brick Rd., Munchkinland, CA",
        "commodity": "Packaged consumer goods (palletized)",
        "pieces": 22,
        "gross_weight_lb": 41280,
        "net_weight_lb": 28140,
        "seal_number": "S-447188",
        "securement_method": "Load bars (3) + corner protectors",
        "weight_distribution_notes": "Heavier pallets staged over drive axles.",
        "loaded_by": "Boq Underhill",
        "dock_supervisor": "Nessa Thropp",
        "source": "tms_sync",
        "is_overloaded": False,
        "is_improperly_loaded": False,
        "photos": [
            {"artifact_type": "dock_photo", "status": "captured", "artifact_id": "ART-DCK-7781-01"},
            {"artifact_type": "dock_photo", "status": "captured", "artifact_id": "ART-DCK-7781-02"},
        ],
    }
]

WEIGH_STATION_REPORTS = [
    {
        "weighed_at_utc": "2026-04-17T11:14:00Z",
        "station_name": "Cowardly Lion Scale House",
        "station_location": "I-5 NB, mile marker 178, CA",
        "ticket_number": "WS-2026-1144789",
        "gross_weight_lb": 71860,
        "steer_axle_weight_lb": 11240,
        "drive_axle_weight_lb": 33420,
        "trailer_axle_weight_lb": 27200,
        "legal_limit_lb": 80000,
        "result": "passed",
        "inspector_name": "Insp. T. Mann",
        "source": "manual_entry",
        "is_over_legal_limit": False,
        "doc_artifact_id": "ART-WS-7781-01",
    }
]

MAINTENANCE = [
    {
        "performed_at_utc": "2026-04-09T13:30:00Z",
        "asset_kind": "tractor",
        "asset_id": "Unit 4471",
        "vendor": "Tin Man Diesel Service",
        "summary": "B-service: oil & filter, brake adjustment, DOT inspection.",
        "mileage": 184_220,
    },
    {
        "performed_at_utc": "2026-03-28T09:14:00Z",
        "asset_kind": "trailer",
        "asset_id": "TRL-CABC-22107",
        "vendor": "Tin Man Diesel Service",
        "summary": "Annual DOT trailer inspection, all brakes within spec.",
        "mileage": None,
    },
]

ELD_LOGS = [
    {"artifact_type": "eld_log_csv", "status": "captured", "artifact_id": "ART-ELD-7781-01"},
    {"artifact_type": "eld_log_pdf", "status": "captured", "artifact_id": "ART-ELD-7781-02"},
]

SAMSARA_CLIPS = [
    {
        "artifact_type": "dashcam_forward_clip",
        "deep_link": "https://cloud.samsara.com/o/123/fleet/cameras/clip/EX-FWD-7781-01",
        "artifact_id": "ART-CAM-7781-01",
    },
    {
        "artifact_type": "dashcam_inward_clip",
        "deep_link": "https://cloud.samsara.com/o/123/fleet/cameras/clip/EX-INW-7781-02",
        "artifact_id": "ART-CAM-7781-02",
    },
]

# ---------------------------------------------------------------------------
# Insurance-form (realistic partial fill)
# ---------------------------------------------------------------------------

INSURANCE_TEMPLATE = {
    "name": "Commercial Auto FNOL — v3",
    "carrier": "Yellow Brick Mutual Insurance",
    "version": 3,
}

INSURANCE_FIELDS = [
    {"name": "policy_number", "label": "Policy Number",
     "source_path": "org.policies.commercial_auto", "value": "YBM-CA-2026-447188"},
    {"name": "claim_number", "label": "Claim Number (assigned by carrier)",
     "source_path": None, "value": None},  # Intentionally blank — assigned later by carrier
    {"name": "insured_name", "label": "Named Insured",
     "source_path": "org.name", "value": CARRIER["name"]},
    {"name": "insured_dot", "label": "USDOT Number",
     "source_path": "org.dot_number", "value": CARRIER["dot_number"]},
    {"name": "insured_contact", "label": "Insured Contact (Safety)",
     "source_path": "org.safety_email", "value": CARRIER["safety_email"]},
    {"name": "loss_date_utc", "label": "Date / Time of Loss (UTC)",
     "source_path": "incident.occurred_at_utc", "value": INCIDENT["occurred_at_utc"]},
    {"name": "loss_location", "label": "Location of Loss",
     "source_path": "incident.location_address", "value": INCIDENT["location_address"]},
    {"name": "loss_description", "label": "Description of Loss",
     "source_path": "incident.narrative", "value": (
         "Rear passenger-side trailer corner of Unit 4471 was struck by a "
         "merging passenger sedan on I-5 NB near MM 213. Driver maintained "
         "control and stopped safely on the shoulder. No injuries reported."
     )},
    {"name": "driver_name", "label": "Driver Name",
     "source_path": "driver.display_name", "value": DRIVER["display_name"]},
    {"name": "driver_license_number", "label": "Driver License Number",
     "source_path": "driver.license_number", "value": DRIVER["license_number"]},
    {"name": "driver_license_state", "label": "Driver License State",
     "source_path": "driver.license_state", "value": DRIVER["license_state"]},
    {"name": "tractor_unit", "label": "Tractor Unit Number",
     "source_path": "vehicle.unit_number", "value": VEHICLE["unit_number"]},
    {"name": "tractor_vin", "label": "Tractor VIN",
     "source_path": "vehicle.vin", "value": VEHICLE["vin"]},
    {"name": "trailer_id", "label": "Trailer ID",
     "source_path": "trailer.adc_trailer_id", "value": TRAILER["adc_trailer_id"]},
    {"name": "trailer_vin", "label": "Trailer VIN",
     "source_path": "trailer.vin", "value": TRAILER["vin"]},
    {"name": "police_report_number", "label": "Police Report Number",
     "source_path": "incident.police_report_number", "value": INCIDENT["police_report_number"]},
    {"name": "third_party_name", "label": "Third Party — Driver Name",
     "source_path": "third_party.driver_name", "value": "Theodore L. Lyon"},
    {"name": "third_party_vehicle", "label": "Third Party — Vehicle",
     "source_path": "third_party.vehicle", "value": "2019 Honda Civic, CA plate 8XYZ123"},
    {"name": "third_party_insurer", "label": "Third Party — Insurer",
     "source_path": "third_party.insurer", "value": "Scarecrow Casualty Co."},
    {"name": "third_party_policy_number", "label": "Third Party — Policy Number",
     "source_path": "third_party.policy_number", "value": None},  # Awaiting exchange
    {"name": "estimated_damages_usd", "label": "Estimated Damages (USD)",
     "source_path": None, "value": None},  # Pending estimator
    {"name": "injuries_reported", "label": "Injuries Reported",
     "source_path": "incident.injuries_reported", "value": "None reported on scene."},
]

# Required fields that are still blank — used to render the "missing required"
# warning box on the insurance-form template.
INSURANCE_MISSING_REQUIRED = [
    "Claim Number (assigned by carrier)",
    "Third Party — Policy Number",
    "Estimated Damages (USD)",
]

# ---------------------------------------------------------------------------
# Legal defense packet
# ---------------------------------------------------------------------------

EVIDENCE_INVENTORY = [
    {"artifact_id": "ART-CAM-7781-01", "artifact_type": "dashcam_forward_clip",
     "captured_at_utc": "2026-04-17T14:31:50Z", "custodian": "Samsara → ADC Vault"},
    {"artifact_id": "ART-CAM-7781-02", "artifact_type": "dashcam_inward_clip",
     "captured_at_utc": "2026-04-17T14:31:50Z", "custodian": "Samsara → ADC Vault"},
    {"artifact_id": "ART-PHOTO-7781-01", "artifact_type": "scene_photo_360",
     "captured_at_utc": "2026-04-17T14:38:12Z", "custodian": "Driver app → ADC Vault"},
    {"artifact_id": "ART-PHOTO-7781-02", "artifact_type": "damage_photo",
     "captured_at_utc": "2026-04-17T14:39:55Z", "custodian": "Driver app → ADC Vault"},
    {"artifact_id": "ART-DOC-7781-01", "artifact_type": "police_report_scan",
     "captured_at_utc": "2026-04-17T16:02:00Z", "custodian": "Driver app → ADC Vault"},
    {"artifact_id": "ART-ELD-7781-01", "artifact_type": "eld_log_csv",
     "captured_at_utc": "2026-04-17T15:00:00Z", "custodian": "Samsara → ADC Vault"},
    {"artifact_id": "ART-WS-7781-01", "artifact_type": "weigh_station_ticket",
     "captured_at_utc": "2026-04-17T11:14:00Z", "custodian": "Driver app → ADC Vault"},
    {"artifact_id": "ART-STMT-7781-01", "artifact_type": "driver_statement_audio",
     "captured_at_utc": "2026-04-17T15:12:00Z", "custodian": "Driver app → ADC Vault"},
]

# Synthesize a stable SHA-256 short-hash per artifact for display.
for _art in EVIDENCE_INVENTORY:
    _digest = hashlib.sha256(_art["artifact_id"].encode("utf-8")).hexdigest()
    _art["sha256_short"] = _digest[:16]

CHAIN_OF_CUSTODY = [
    {"event_at_utc": "2026-04-17T14:31:50Z", "artifact_id": "ART-CAM-7781-01",
     "action": "captured_by_provider", "actor": "Samsara (Unit 4471)", "notes": "Auto-trigger: harsh-event"},
    {"event_at_utc": "2026-04-17T14:34:02Z", "artifact_id": "ART-CAM-7781-01",
     "action": "ingested_to_vault", "actor": "ADC ingestion job",
     "notes": "SHA-256 verified against provider manifest."},
    {"event_at_utc": "2026-04-17T14:38:12Z", "artifact_id": "ART-PHOTO-7781-01",
     "action": "uploaded_by_driver", "actor": "Dorothy Gale (DRV-CABC-00318)",
     "notes": "360° capture protocol completed."},
    {"event_at_utc": "2026-04-17T14:39:58Z", "artifact_id": "ART-PHOTO-7781-01",
     "action": "ingested_to_vault", "actor": "ADC ingestion job", "notes": None},
    {"event_at_utc": "2026-04-17T15:12:11Z", "artifact_id": "ART-STMT-7781-01",
     "action": "uploaded_by_driver", "actor": "Dorothy Gale (DRV-CABC-00318)",
     "notes": "Driver verbal statement, 4m 18s."},
    {"event_at_utc": "2026-04-17T16:02:30Z", "artifact_id": "ART-DOC-7781-01",
     "action": "uploaded_by_driver", "actor": "Dorothy Gale (DRV-CABC-00318)",
     "notes": "Police report scan."},
    {"event_at_utc": "2026-04-18T09:00:00Z", "artifact_id": "ART-CAM-7781-01",
     "action": "accessed_for_review", "actor": "Glinda Northman (Safety)",
     "notes": "Read-only review; no modification."},
    {"event_at_utc": "2026-04-22T10:14:00Z", "artifact_id": "*",
     "action": "manifest_signed", "actor": "ADC Vault signing service",
     "notes": "Court-defense packet manifest sealed."},
]

TIMELINE = [
    {"event_at_utc": "2026-04-17T05:42:00Z", "description": "Driver dispatched on load L-778124.", "source": "TMS"},
    {"event_at_utc": "2026-04-17T07:48:00Z", "description": "Loading completed at Munchkinland DC.", "source": "Dock"},
    {"event_at_utc": "2026-04-17T11:14:00Z", "description": "Passed weigh station at I-5 MM 178 (71,860 lb).", "source": "Manual"},
    {"event_at_utc": "2026-04-17T14:31:55Z", "description": "Collision: rear-corner impact by merging sedan.", "source": "Samsara"},
    {"event_at_utc": "2026-04-17T14:32:18Z", "description": "Incident opened in ADC; capture protocol started.", "source": "ADC"},
    {"event_at_utc": "2026-04-17T14:38:12Z", "description": "Driver completed 360° photo capture.", "source": "Driver app"},
    {"event_at_utc": "2026-04-17T15:12:11Z", "description": "Driver recorded verbal statement.", "source": "Driver app"},
    {"event_at_utc": "2026-04-17T16:02:30Z", "description": "Police report uploaded.", "source": "Driver app"},
    {"event_at_utc": "2026-04-22T10:14:00Z", "description": "Defense packet manifest sealed.", "source": "ADC"},
]

DRIVER_STATEMENT = {
    "driver_name": DRIVER["display_name"],
    "recorded_at_utc": "2026-04-17T15:12:11Z",
    "method": "In-app audio recording (transcribed)",
    "statement_text": (
        "I was northbound on I-5 in the right lane, going about 58 miles an "
        "hour, with cruise off because of the rain. I saw a silver sedan on "
        "the right shoulder ahead. As I came alongside, the sedan accelerated "
        "and merged into my lane without signaling. The front of the sedan "
        "struck the back right corner of my trailer. I felt the impact, kept "
        "the wheel straight, turned on my hazards, eased off the throttle, "
        "and pulled onto the right shoulder. I checked on the other driver, "
        "called 911, then started the ADC capture steps."
    ),
    "attested_at_utc": "2026-04-17T15:14:02Z",
}

TELEMETRY_HIGHLIGHTS = [
    {"observed_at_utc": "2026-04-17T14:31:50Z", "metric": "Speed", "value": "58 mph", "source": "Samsara GPS"},
    {"observed_at_utc": "2026-04-17T14:31:55Z", "metric": "Lateral acceleration", "value": "0.42 g (right→left)", "source": "Samsara IMU"},
    {"observed_at_utc": "2026-04-17T14:31:56Z", "metric": "Brake pressure", "value": "Service brake applied (firm)", "source": "Samsara CAN"},
    {"observed_at_utc": "2026-04-17T14:32:08Z", "metric": "Speed", "value": "12 mph (decelerating)", "source": "Samsara GPS"},
    {"observed_at_utc": "2026-04-17T14:32:31Z", "metric": "Speed", "value": "0 mph (stopped on shoulder)", "source": "Samsara GPS"},
    {"observed_at_utc": "2026-04-17T14:31:55Z", "metric": "Hazard lights", "value": "ON within 3s of impact", "source": "Samsara CAN"},
]

MEDIA_INVENTORY = [
    {"artifact_id": "ART-CAM-7781-01", "artifact_type": "dashcam_forward_clip",
     "captured_at_utc": "2026-04-17T14:31:50Z",
     "deep_link": "https://cloud.samsara.com/o/123/fleet/cameras/clip/EX-FWD-7781-01"},
    {"artifact_id": "ART-CAM-7781-02", "artifact_type": "dashcam_inward_clip",
     "captured_at_utc": "2026-04-17T14:31:50Z",
     "deep_link": "https://cloud.samsara.com/o/123/fleet/cameras/clip/EX-INW-7781-02"},
    {"artifact_id": "ART-PHOTO-7781-01", "artifact_type": "scene_photo_360",
     "captured_at_utc": "2026-04-17T14:38:12Z", "deep_link": None},
    {"artifact_id": "ART-PHOTO-7781-02", "artifact_type": "damage_photo",
     "captured_at_utc": "2026-04-17T14:39:55Z", "deep_link": None},
]


def _integrity_block() -> dict[str, Any]:
    """Compute a deterministic manifest hash from the evidence inventory."""
    manifest_input = "|".join(
        f"{a['artifact_id']}:{a['sha256_short']}" for a in EVIDENCE_INVENTORY
    )
    manifest_hash = hashlib.sha256(manifest_input.encode("utf-8")).hexdigest()
    return {
        "manifest_sha256": manifest_hash,
        "generated_at_utc": "2026-04-22T10:14:00Z",
        "signed_by": "ADC Vault Signing Service (key: vault-signing-2026-q2)",
        "signature_algorithm": "Ed25519",
        "artifact_count": len(EVIDENCE_INVENTORY),
    }


CASE = {
    "caption": "Lyon v. Carrier ABC, Inc.",
    "court": "Superior Court of California, County of Emerald",
    "docket_number": "EC-CV-2026-004781",
}

PREPARED_BY = {
    "attorney_name": "Hon. Marcus W. Brave",
    "bar_number": "CA-318472",
}

APPENDIX_INDEX = [
    {"label": "Appendix A", "description": "Full Samsara dashcam clips (forward + inward), MP4."},
    {"label": "Appendix B", "description": "ELD daily logs (CSV) for 2026-04-15 through 2026-04-17."},
    {"label": "Appendix C", "description": "Scene + damage photographs (JPG, 14 files)."},
    {"label": "Appendix D", "description": "Emerald City PD report EC-PD-2026-118437 (PDF)."},
    {"label": "Appendix E", "description": "Driver statement audio recording (M4A) and transcript."},
    {"label": "Appendix F", "description": "Tractor & trailer maintenance records (last 90 days)."},
    {"label": "Appendix G", "description": "Weigh-station ticket WS-2026-1144789 (image)."},
]


# ---------------------------------------------------------------------------
# Context builders + render
# ---------------------------------------------------------------------------

def build_executive_brief_context() -> dict[str, Any]:
    return {
        "is_sample": True,
        "subject": f"Initial Executive Brief — Incident {INCIDENT['incident_id']}",
        "incident": INCIDENT,
        "driver": DRIVER,
        "driver_history": DRIVER_HISTORY,
        "vehicle": VEHICLE,
        "trailer": TRAILER,
        "maintenance": MAINTENANCE,
        "maintenance_window_days": 90,
        "eld_logs": ELD_LOGS,
        "samsara_clip_links": SAMSARA_CLIPS,
        "related_event_count": 14,
        "dispatch_instructions": DISPATCH_INSTRUCTIONS,
        "weigh_station_reports": WEIGH_STATION_REPORTS,
        "loading_dock_reports": LOADING_DOCK_REPORTS,
    }


def build_insurance_form_context() -> dict[str, Any]:
    return {
        "is_sample": True,
        "subject": f"Insurance Form — {INSURANCE_TEMPLATE['name']}",
        "incident": INCIDENT,
        "template": INSURANCE_TEMPLATE,
        "filled_at_utc": "2026-04-17T17:48:00Z",
        "fields": INSURANCE_FIELDS,
        "missing_required_fields": INSURANCE_MISSING_REQUIRED,
    }


def build_legal_defense_packet_context() -> dict[str, Any]:
    from app.domain.packet_profiles import get_packet_profile
    profile = get_packet_profile("court_defense_v1")
    return {
        "is_sample": True,
        "subject": f"Legal Defense Packet — {CASE['caption']}",
        "org": CARRIER,
        "incident": INCIDENT,
        "driver": DRIVER,
        "vehicle": VEHICLE,
        "trailer": TRAILER,
        "case": CASE,
        "prepared_by": PREPARED_BY,
        "prepared_at_utc": "2026-04-22T10:14:00Z",
        "profile": {
            "profile_id": profile.profile_id,
            "summary_style": profile.summary_style,
        },
        "evidence_inventory": EVIDENCE_INVENTORY,
        "chain_of_custody": CHAIN_OF_CUSTODY,
        "timeline": TIMELINE,
        "driver_statement": DRIVER_STATEMENT,
        "telemetry_highlights": TELEMETRY_HIGHLIGHTS,
        "media_inventory": MEDIA_INVENTORY,
        "integrity": _integrity_block(),
        "appendix_index": APPENDIX_INDEX,
    }


SAMPLES: tuple[tuple[str, str, str], ...] = (
    ("crash_brief", "adc-sample-executive-brief.pdf", "executive_brief"),
    ("insurance_form", "adc-sample-insurance-form.pdf", "insurance_form"),
    ("legal_defense_packet", "adc-sample-legal-defense-packet.pdf", "legal_defense_packet"),
)

_BUILDERS = {
    "executive_brief": build_executive_brief_context,
    "insurance_form": build_insurance_form_context,
    "legal_defense_packet": build_legal_defense_packet_context,
}


def generate_all(output_dir: Path = OUTPUT_DIR) -> list[Path]:
    """Render and write every sample PDF. Returns the list of files written."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for template_name, file_name, builder_key in SAMPLES:
        ctx = _BUILDERS[builder_key]()
        pdf_bytes = render_pdf(template_name, ctx)
        out_path = output_dir / file_name
        out_path.write_bytes(pdf_bytes)
        size_kb = len(pdf_bytes) / 1024
        try:
            display_path: str = str(out_path.relative_to(REPO_ROOT))
        except ValueError:
            display_path = str(out_path)
        print(f"wrote {display_path} ({size_kb:.1f} KB)")
        written.append(out_path)
    return written


if __name__ == "__main__":
    generate_all()
