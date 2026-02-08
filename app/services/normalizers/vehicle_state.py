"""Vehicle state normalizer."""


def normalize_vehicle_state(raw: dict) -> dict:
    """Normalize a raw vehicle state record into a standard format."""
    return {
        "vehicle_id": raw.get("vehicleId"),
        "speed": raw.get("speed"),
        "odometer": raw.get("odometer"),
        "fuel_level": raw.get("fuelLevel"),
        "engine_state": raw.get("engineState"),
        "timestamp": raw.get("time"),
    }
