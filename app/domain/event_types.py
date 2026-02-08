"""Event type definitions."""

from enum import Enum


class EventType(str, Enum):
    """Types of events tracked in the system."""

    HARSH_BRAKING = "harsh_braking"
    HARSH_ACCELERATION = "harsh_acceleration"
    SPEEDING = "speeding"
    COLLISION = "collision"
    LANE_DEPARTURE = "lane_departure"
    DISTRACTED_DRIVING = "distracted_driving"
    ELD_VIOLATION = "eld_violation"
    GPS_UPDATE = "gps_update"
