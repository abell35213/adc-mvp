"""Evidence type definitions."""

from enum import Enum


class EvidenceType(str, Enum):
    """Types of evidence that can be collected."""

    ELD_LOG = "eld_log"
    GPS_TRAIL = "gps_trail"
    SAFETY_EVENT = "safety_event"
    VEHICLE_STATE = "vehicle_state"
    DASH_CAM_VIDEO = "dash_cam_video"
    DRIVER_STATEMENT = "driver_statement"
    POLICE_REPORT = "police_report"
    PHOTO = "photo"
