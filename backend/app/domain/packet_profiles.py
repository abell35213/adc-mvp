"""Packet profile definitions for export generation behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PacketProfile:
    profile_id: str
    export_type: str
    include_media_default: bool
    include_raw_telemetry_default: bool
    include_driver_statement_default: bool
    inventory_mode: str
    required_sections: tuple[str, ...]
    optional_sections: tuple[str, ...]
    summary_style: str

    def default_options(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "include_media": self.include_media_default,
            "include_raw_telemetry": self.include_raw_telemetry_default,
            "include_driver_statement": self.include_driver_statement_default,
            "inventory_mode": self.inventory_mode,
        }


PACKET_PROFILES: dict[str, PacketProfile] = {
    "court_defense_v1": PacketProfile(
        profile_id="court_defense_v1",
        export_type="court_defense",
        include_media_default=True,
        include_raw_telemetry_default=True,
        include_driver_statement_default=True,
        inventory_mode="full",
        required_sections=(
            "incident_summary",
            "evidence_inventory",
            "chain_of_custody",
            "timeline",
            "driver_statement",
            "integrity",
        ),
        optional_sections=("media", "raw_telemetry"),
        summary_style="litigation_full",
    ),
    "insurer_packet_v1": PacketProfile(
        profile_id="insurer_packet_v1",
        export_type="insurer_packet",
        include_media_default=True,
        include_raw_telemetry_default=False,
        include_driver_statement_default=True,
        inventory_mode="condensed",
        required_sections=(
            "incident_summary",
            "claim_bundle",
            "evidence_inventory",
            "chain_of_custody",
            "integrity",
        ),
        optional_sections=("media", "timeline", "driver_statement", "raw_telemetry"),
        summary_style="claim_focused",
    ),
    # Scaffolded profiles (future implementation).
    "internal_review_v1": PacketProfile(
        profile_id="internal_review_v1",
        export_type="internal_review",
        include_media_default=True,
        include_raw_telemetry_default=True,
        include_driver_statement_default=True,
        inventory_mode="full",
        required_sections=("incident_summary", "evidence_inventory", "chain_of_custody", "integrity"),
        optional_sections=("media", "timeline", "driver_statement", "raw_telemetry"),
        summary_style="internal_review",
    ),
    "compliance_audit_v1": PacketProfile(
        profile_id="compliance_audit_v1",
        export_type="compliance_audit",
        include_media_default=False,
        include_raw_telemetry_default=True,
        include_driver_statement_default=False,
        inventory_mode="full",
        required_sections=("incident_summary", "evidence_inventory", "chain_of_custody", "integrity"),
        optional_sections=("media", "timeline", "driver_statement", "raw_telemetry"),
        summary_style="compliance_audit",
    ),
}


DEFAULT_PROFILE_BY_EXPORT_TYPE: dict[str, str] = {
    "court_defense": "court_defense_v1",
    "insurer_packet": "insurer_packet_v1",
    "internal_review": "internal_review_v1",
    "compliance_audit": "compliance_audit_v1",
}


def get_packet_profile(profile_id: str) -> PacketProfile:
    profile = PACKET_PROFILES.get(profile_id)
    if profile is None:
        raise ValueError(f"Unknown packet profile '{profile_id}'")
    return profile


def get_default_packet_profile(export_type: str) -> PacketProfile:
    try:
        profile_id = DEFAULT_PROFILE_BY_EXPORT_TYPE[export_type]
    except KeyError as exc:
        raise ValueError(f"No default profile configured for export_type '{export_type}'") from exc
    return get_packet_profile(profile_id)
