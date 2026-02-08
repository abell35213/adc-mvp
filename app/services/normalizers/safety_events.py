"""Safety events normalizer."""


def normalize_safety_event(raw: dict) -> dict:
    """Normalize a raw safety event into a standard format."""
    return {
        "event_type": raw.get("safetyEventType"),
        "severity": raw.get("severity"),
        "timestamp": raw.get("time"),
        "vehicle_id": raw.get("vehicleId"),
        "driver_id": raw.get("driverId"),
        "location": {
            "latitude": raw.get("latitude"),
            "longitude": raw.get("longitude"),
        },
    }
