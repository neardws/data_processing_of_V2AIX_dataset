"""
JSON data parsing for V2AIX dataset records.

This module converts raw JSON objects into validated Pydantic models,
handling various field naming conventions, timestamp formats, and missing data.
Supports both GNSS pose records and V2X message records.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Direction, GnssRecord, V2XMessageRecord

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Timestamp Utilities
# ============================================================================

def detect_timestamp_unit(timestamp: int | float) -> str:
    """Detect the unit of a timestamp (seconds, milliseconds, or microseconds).

    Args:
        timestamp: Numeric timestamp value

    Returns:
        One of: 'seconds', 'milliseconds', 'microseconds'

    Notes:
        Uses heuristics based on typical Unix timestamp ranges:
        - Seconds: 1000000000 to 9999999999 (2001-2286)
        - Milliseconds: 1000000000000 to 9999999999999
        - Microseconds: > 1000000000000000
    """
    ts_value = int(timestamp)

    if ts_value < 10_000_000_000:  # < 10^10
        return 'seconds'
    elif ts_value < 10_000_000_000_000:  # < 10^13
        return 'milliseconds'
    else:
        return 'microseconds'


def normalize_timestamp(timestamp: int | float, unit: Optional[str] = None) -> int:
    """Normalize a timestamp to milliseconds since Unix epoch.

    Args:
        timestamp: Numeric timestamp value
        unit: Optional explicit unit ('seconds', 'milliseconds', 'microseconds')
              If None, will auto-detect based on magnitude

    Returns:
        Timestamp in milliseconds since Unix epoch (UTC)

    Examples:
        >>> normalize_timestamp(1678901234)  # seconds
        1678901234000
        >>> normalize_timestamp(1678901234000)  # milliseconds
        1678901234000
        >>> normalize_timestamp(1678901234000000)  # microseconds
        1678901234000
    """
    if unit is None:
        unit = detect_timestamp_unit(timestamp)

    ts_value = int(timestamp)

    if unit == 'seconds':
        return ts_value * 1000
    elif unit == 'milliseconds':
        return ts_value
    elif unit == 'microseconds':
        return ts_value // 1000
    else:
        raise ValueError(f"Unknown timestamp unit: {unit}")


# ============================================================================
# Field Extraction Utilities
# ============================================================================

def extract_vehicle_id(obj: Dict[str, Any]) -> Optional[str]:
    """Extract vehicle/station ID from JSON object.

    Tries multiple field naming conventions:
    - stationID, station_id
    - vehicleID, vehicle_id
    - id

    Args:
        obj: JSON object (dict)

    Returns:
        Vehicle ID as string, or None if not found
    """
    for key in ['stationID', 'station_id', 'vehicleID', 'vehicle_id', 'id']:
        if key in obj and obj[key] is not None:
            return str(obj[key])
    return None


def extract_station_type(obj: Dict[str, Any]) -> Optional[str]:
    """Extract station type from JSON object.

    Tries: stationType, station_type

    Args:
        obj: JSON object (dict)

    Returns:
        Station type as string, or None if not found
    """
    for key in ['stationType', 'station_type']:
        if key in obj and obj[key] is not None:
            return str(obj[key])
    return None


def extract_latitude(obj: Dict[str, Any]) -> Optional[float]:
    """Extract latitude from JSON object.

    Tries: latitude, lat, latitude_deg

    Args:
        obj: JSON object (dict)

    Returns:
        Latitude in degrees, or None if not found
    """
    for key in ['latitude', 'lat', 'latitude_deg']:
        if key in obj and obj[key] is not None:
            return float(obj[key])
    return None


def extract_longitude(obj: Dict[str, Any]) -> Optional[float]:
    """Extract longitude from JSON object.

    Tries: longitude, lon, longitude_deg

    Args:
        obj: JSON object (dict)

    Returns:
        Longitude in degrees, or None if not found
    """
    for key in ['longitude', 'lon', 'longitude_deg']:
        if key in obj and obj[key] is not None:
            return float(obj[key])
    return None


def extract_altitude(obj: Dict[str, Any]) -> Optional[float]:
    """Extract altitude from JSON object.

    Tries: altitude, alt, altitude_m

    Args:
        obj: JSON object (dict)

    Returns:
        Altitude in meters, or None if not found
    """
    for key in ['altitude', 'alt', 'altitude_m']:
        if key in obj and obj[key] is not None:
            return float(obj[key])
    return None


def extract_speed(obj: Dict[str, Any]) -> Optional[float]:
    """Extract speed from JSON object.

    Tries: speed, speed_mps, speedMps

    Args:
        obj: JSON object (dict)

    Returns:
        Speed in meters per second, or None if not found
    """
    for key in ['speed', 'speed_mps', 'speedMps']:
        if key in obj and obj[key] is not None:
            return float(obj[key])
    return None


def extract_heading(obj: Dict[str, Any]) -> Optional[float]:
    """Extract heading from JSON object.

    Tries: heading, heading_deg, headingDeg

    Args:
        obj: JSON object (dict)

    Returns:
        Heading in degrees, or None if not found
    """
    for key in ['heading', 'heading_deg', 'headingDeg']:
        if key in obj and obj[key] is not None:
            return float(obj[key])
    return None


def extract_message_type(obj: Dict[str, Any]) -> Optional[str]:
    """Extract V2X message type from JSON object.

    Tries: messageType, message_type, msgType

    Args:
        obj: JSON object (dict)

    Returns:
        Message type (e.g., 'CAM', 'DENM'), or None if not found
    """
    for key in ['messageType', 'message_type', 'msgType']:
        if key in obj and obj[key] is not None:
            return str(obj[key])
    return None


def extract_direction(obj: Dict[str, Any]) -> Optional[Direction]:
    """Extract V2X link direction from JSON object.

    Args:
        obj: JSON object (dict)

    Returns:
        Direction enum value, or None if not found or invalid
    """
    direction_str = obj.get('direction')
    if direction_str is None:
        return None

    try:
        return Direction(direction_str)
    except ValueError:
        logger.warning(f"Invalid direction value: {direction_str}")
        return None


def extract_rsu_id(obj: Dict[str, Any]) -> Optional[str]:
    """Extract RSU ID from JSON object.

    Tries: rsu_id, rsuID, rsuId

    Args:
        obj: JSON object (dict)

    Returns:
        RSU ID as string, or None if not found
    """
    for key in ['rsu_id', 'rsuID', 'rsuId']:
        if key in obj and obj[key] is not None:
            return str(obj[key])
    return None


# ============================================================================
# Record Parsers
# ============================================================================

def parse_gnss_record(
    obj: Dict[str, Any],
    source_file: Optional[Path] = None,
    timestamp_unit: Optional[str] = None
) -> Optional[GnssRecord]:
    """Parse a JSON object into a GnssRecord.

    Args:
        obj: JSON object containing GNSS data
        source_file: Optional path to source JSON file
        timestamp_unit: Optional explicit timestamp unit
                       ('seconds', 'milliseconds', 'microseconds')
                       If None, will auto-detect

    Returns:
        GnssRecord instance, or None if required fields are missing

    Notes:
        Required fields: vehicle_id, timestamp, latitude, longitude
        Optional fields: altitude, speed, heading, station_id, station_type

    Examples:
        >>> obj = {
        ...     "stationID": "vehicle_001",
        ...     "latitude": 50.7753,
        ...     "longitude": 6.0839,
        ...     "timestamp": 1678901234
        ... }
        >>> record = parse_gnss_record(obj)
        >>> record.vehicle_id
        'vehicle_001'
    """
    # Extract required fields
    vehicle_id = extract_vehicle_id(obj)
    if vehicle_id is None:
        logger.debug("Skipping GNSS record: no vehicle ID found")
        return None

    # Extract timestamp
    timestamp_raw = obj.get('timestamp') or obj.get('timestamp_utc_ms')
    if timestamp_raw is None:
        logger.debug(f"Skipping GNSS record for {vehicle_id}: no timestamp found")
        return None

    try:
        timestamp_ms = normalize_timestamp(timestamp_raw, timestamp_unit)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid timestamp for {vehicle_id}: {timestamp_raw} - {e}")
        return None

    # Extract coordinates
    latitude = extract_latitude(obj)
    longitude = extract_longitude(obj)

    if latitude is None or longitude is None:
        logger.debug(f"Skipping GNSS record for {vehicle_id}: missing coordinates")
        return None

    # Extract optional fields
    altitude = extract_altitude(obj)
    speed = extract_speed(obj)
    heading = extract_heading(obj)
    station_id = obj.get('stationID') or obj.get('station_id')
    station_type = extract_station_type(obj)

    # Convert to strings if present
    if station_id is not None:
        station_id = str(station_id)

    # Create record
    try:
        return GnssRecord(
            vehicle_id=vehicle_id,
            timestamp_utc_ms=timestamp_ms,
            latitude_deg=latitude,
            longitude_deg=longitude,
            altitude_m=altitude,
            speed_mps=speed,
            heading_deg=heading,
            station_id=station_id,
            station_type=station_type,
            source_file=source_file
        )
    except Exception as e:
        logger.error(f"Failed to create GnssRecord for {vehicle_id}: {e}")
        return None


def parse_v2x_record(
    obj: Dict[str, Any],
    source_file: Optional[Path] = None,
    timestamp_unit: Optional[str] = None
) -> Optional[V2XMessageRecord]:
    """Parse a JSON object into a V2XMessageRecord.

    Args:
        obj: JSON object containing V2X message data
        source_file: Optional path to source JSON file
        timestamp_unit: Optional explicit timestamp unit
                       If None, will auto-detect

    Returns:
        V2XMessageRecord instance, or None if required fields are missing

    Notes:
        Required field: vehicle_id
        At least one timestamp field should be present

    Examples:
        >>> obj = {
        ...     "stationID": "vehicle_001",
        ...     "messageType": "CAM",
        ...     "tx_timestamp": 1678901234100,
        ...     "rx_timestamp": 1678901234120,
        ...     "payload_bytes": 256
        ... }
        >>> record = parse_v2x_record(obj)
        >>> record.message_type
        'CAM'
    """
    # Extract required fields
    vehicle_id = extract_vehicle_id(obj)
    if vehicle_id is None:
        logger.debug("Skipping V2X record: no vehicle ID found")
        return None

    # Extract timestamps (multiple variants)
    timestamp_raw = obj.get('timestamp') or obj.get('timestamp_utc_ms')
    tx_timestamp_raw = obj.get('tx_timestamp') or obj.get('tx_timestamp_utc_ms')
    rx_timestamp_raw = obj.get('rx_timestamp') or obj.get('rx_timestamp_utc_ms')

    # Normalize timestamps
    timestamp_ms = None
    tx_timestamp_ms = None
    rx_timestamp_ms = None

    try:
        if timestamp_raw is not None:
            timestamp_ms = normalize_timestamp(timestamp_raw, timestamp_unit)
        if tx_timestamp_raw is not None:
            tx_timestamp_ms = normalize_timestamp(tx_timestamp_raw, timestamp_unit)
        if rx_timestamp_raw is not None:
            rx_timestamp_ms = normalize_timestamp(rx_timestamp_raw, timestamp_unit)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid timestamp in V2X record for {vehicle_id}: {e}")

    # Calculate latency if both tx and rx are available
    latency_ms = None
    if tx_timestamp_ms is not None and rx_timestamp_ms is not None:
        latency_ms = float(rx_timestamp_ms - tx_timestamp_ms)

    # Extract message metadata
    message_type = extract_message_type(obj)
    direction = extract_direction(obj)
    rsu_id = extract_rsu_id(obj)
    station_id = obj.get('stationID') or obj.get('station_id')
    station_type = extract_station_type(obj)

    # Convert to strings if present
    if station_id is not None:
        station_id = str(station_id)

    # Extract payload sizes
    payload_bytes = obj.get('payload_bytes')
    frame_bytes = obj.get('frame_bytes')

    # Convert to int if present
    if payload_bytes is not None:
        payload_bytes = int(payload_bytes)
    if frame_bytes is not None:
        frame_bytes = int(frame_bytes)

    # Create record
    try:
        return V2XMessageRecord(
            vehicle_id=vehicle_id,
            station_id=station_id,
            station_type=station_type,
            timestamp_utc_ms=timestamp_ms,
            tx_timestamp_utc_ms=tx_timestamp_ms,
            rx_timestamp_utc_ms=rx_timestamp_ms,
            direction=direction,
            rsu_id=rsu_id,
            message_type=message_type,
            payload_bytes=payload_bytes,
            frame_bytes=frame_bytes,
            latency_ms=latency_ms,
            source_file=source_file
        )
    except Exception as e:
        logger.error(f"Failed to create V2XMessageRecord for {vehicle_id}: {e}")
        return None


# ============================================================================
# Batch Parsing
# ============================================================================

def parse_records(
    objects: List[Dict[str, Any]],
    source_file: Optional[Path] = None,
    timestamp_unit: Optional[str] = None
) -> tuple[List[GnssRecord], List[V2XMessageRecord]]:
    """Parse a list of JSON objects into GNSS and V2X records.

    Automatically detects record type based on available fields.
    Objects with both GNSS and V2X fields will be parsed as both types.

    Args:
        objects: List of JSON objects (dicts)
        source_file: Optional path to source JSON file
        timestamp_unit: Optional explicit timestamp unit

    Returns:
        Tuple of (gnss_records, v2x_records)

    Examples:
        >>> objects = [
        ...     {"stationID": "v1", "latitude": 50.0, "longitude": 6.0, "timestamp": 1678901234},
        ...     {"stationID": "v1", "messageType": "CAM", "tx_timestamp": 1678901234100}
        ... ]
        >>> gnss_records, v2x_records = parse_records(objects)
        >>> len(gnss_records), len(v2x_records)
        (1, 1)
    """
    gnss_records: List[GnssRecord] = []
    v2x_records: List[V2XMessageRecord] = []

    for obj in objects:
        if not isinstance(obj, dict):
            logger.warning(f"Skipping non-dict object: {type(obj)}")
            continue

        # Try parsing as GNSS record
        gnss_record = parse_gnss_record(obj, source_file, timestamp_unit)
        if gnss_record is not None:
            gnss_records.append(gnss_record)

        # Try parsing as V2X record
        v2x_record = parse_v2x_record(obj, source_file, timestamp_unit)
        if v2x_record is not None:
            v2x_records.append(v2x_record)

    logger.info(
        f"Parsed {len(gnss_records)} GNSS records and {len(v2x_records)} V2X records "
        f"from {len(objects)} objects"
    )

    return gnss_records, v2x_records
