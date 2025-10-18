"""
Dataset discovery and statistics gathering for V2AIX JSON files.

This module scans directories for JSON files, identifies record types,
and extracts dataset statistics including vehicle counts and message types.
Supports both JSON arrays and JSON Lines format, with optional streaming
for memory-efficient processing of large files.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Set

# Optional ijson for streaming large JSON arrays
try:
    import ijson
    HAS_IJSON = True
except ImportError:
    HAS_IJSON = False

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_SAMPLE_PER_FILE = 100


def _iter_json_objects(
    json_path: Path,
    sample: Optional[int] = None
) -> Generator[Dict[str, Any], None, None]:
    """Iterate over JSON objects from a file.

    Supports three formats:
    1. JSON array: [...] - uses ijson streaming if available, otherwise loads entire file
    2. JSON Lines: one object per line
    3. Single JSON object: {...} - yields once

    Args:
        json_path: Path to JSON file
        sample: Optional limit on number of objects to yield

    Yields:
        Dictionary objects from the JSON file

    Notes:
        - For large JSON arrays, install ijson for memory-efficient streaming
        - JSON Lines format is always memory-efficient (line-by-line reading)
        - Malformed lines in JSON Lines format are logged and skipped
    """
    count = 0
    max_count = sample or float('inf')

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            # Peek at first character to determine format
            first_char = f.read(1)
            f.seek(0)

            if first_char == '[':
                # JSON array format - try streaming with ijson
                if HAS_IJSON:
                    logger.debug(f"Using ijson streaming parser for {json_path.name}")
                    try:
                        parser = ijson.items(f, "item")
                        for obj in parser:
                            if isinstance(obj, dict):
                                yield obj
                                count += 1
                                if count >= max_count:
                                    return
                        return
                    except (ijson.JSONError, ijson.IncompleteJSONError) as e:
                        logger.warning(f"ijson streaming failed for {json_path.name}, falling back to json.loads: {e}")
                        f.seek(0)
                else:
                    logger.debug(f"ijson not available, using json.loads for {json_path.name}")

                # Fallback: load entire array
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        for obj in data:
                            if isinstance(obj, dict):
                                yield obj
                                count += 1
                                if count >= max_count:
                                    return
                    elif isinstance(data, dict):
                        yield data
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON array in {json_path}: {e}")

            elif first_char == '{':
                # Could be single object or JSON Lines
                f.seek(0)
                first_line = f.readline()
                f.seek(0)

                # Try parsing first line as complete object (JSON Lines format)
                try:
                    obj = json.loads(first_line)
                    if isinstance(obj, dict):
                        # JSON Lines format
                        logger.debug(f"Detected JSON Lines format in {json_path.name}")
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                obj = json.loads(line)
                                if isinstance(obj, dict):
                                    yield obj
                                    count += 1
                                    if count >= max_count:
                                        return
                            except json.JSONDecodeError as e:
                                logger.warning(f"Skipping malformed JSON line in {json_path}: {e}")
                        return
                except json.JSONDecodeError:
                    pass

                # Single JSON object - could be V2AIX topic-based format
                f.seek(0)
                try:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Check if this is V2AIX topic-based format (keys like "/gps/...", "/v2x/...")
                        if any(key.startswith('/') for key in data.keys()):
                            logger.debug(f"Detected V2AIX topic-based format in {json_path.name}")
                            # Iterate through each topic's records
                            for topic, records in data.items():
                                if isinstance(records, list):
                                    for record in records:
                                        if isinstance(record, dict):
                                            # Flatten the structure: merge 'message' field if it exists
                                            if 'message' in record and isinstance(record['message'], dict):
                                                # Create flattened object with both top-level and message fields
                                                flattened = {**record['message'],
                                                           'recording_timestamp_nsec': record.get('recording_timestamp_nsec'),
                                                           '_topic': topic}
                                                yield flattened
                                            else:
                                                # Add topic information
                                                record['_topic'] = topic
                                                yield record
                                            count += 1
                                            if count >= max_count:
                                                return
                        else:
                            # Regular single JSON object
                            yield data
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON object in {json_path}: {e}")

    except Exception as e:
        logger.error(f"Error reading {json_path}: {e}")


def _extract_ids_and_types(obj: Dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract vehicle/station ID, station type, and message type from a JSON object.

    Supports multiple field naming conventions from different data sources,
    including deeply nested V2AIX CAM/DENM structures.

    Args:
        obj: JSON object (dict)

    Returns:
        Tuple of (vehicle_id, station_type, message_type)
        - vehicle_id: Extracted from various station ID fields
        - station_type: Extracted from stationType or station_type
        - message_type: Detected from message structure (CAM, DENM, etc.)

    Notes:
        All returned values are strings or None if field not found.
    """
    vehicle_id = None
    station_type = None
    message_type = None

    # Extract vehicle/station ID - try multiple field names and nested paths
    # Direct fields
    vehicle_id = (
        obj.get("stationID") or
        obj.get("station_id") or
        obj.get("vehicleID") or
        obj.get("vehicle_id") or
        obj.get("id")
    )

    # V2AIX nested structure: header.station_id.value
    if not vehicle_id and "header" in obj and isinstance(obj["header"], dict):
        header = obj["header"]
        station_id_obj = header.get("station_id")
        if isinstance(station_id_obj, dict) and "value" in station_id_obj:
            vehicle_id = station_id_obj["value"]

    if vehicle_id is not None:
        vehicle_id = str(vehicle_id)

    # Extract station type - try direct and nested paths
    station_type = obj.get("stationType") or obj.get("station_type")

    # V2AIX CAM structure: cam.cam_parameters.basic_container.station_type.value
    if not station_type and "cam" in obj and isinstance(obj["cam"], dict):
        cam = obj["cam"]
        if "cam_parameters" in cam and isinstance(cam["cam_parameters"], dict):
            cam_params = cam["cam_parameters"]
            if "basic_container" in cam_params and isinstance(cam_params["basic_container"], dict):
                basic = cam_params["basic_container"]
                station_type_obj = basic.get("station_type")
                if isinstance(station_type_obj, dict) and "value" in station_type_obj:
                    station_type = station_type_obj["value"]

    if station_type is not None:
        station_type = str(station_type)

    # Extract/detect message type
    message_type = (
        obj.get("messageType") or
        obj.get("message_type") or
        obj.get("msgType")
    )

    # Detect from V2AIX message structure
    if not message_type:
        if "cam" in obj:
            message_type = "CAM"
        elif "denm" in obj:
            message_type = "DENM"
        elif "header" in obj and isinstance(obj["header"], dict):
            # Try to get from header.message_id
            msg_id = obj["header"].get("message_id")
            if msg_id == 2:
                message_type = "CAM"
            elif msg_id == 1:
                message_type = "DENM"

    if message_type is not None:
        message_type = str(message_type)

    return vehicle_id, station_type, message_type


def _is_gnss_like(obj: Dict[str, Any]) -> bool:
    """Check if object looks like a GNSS pose record.

    Args:
        obj: JSON object to check

    Returns:
        True if object contains GNSS-like fields (latitude/longitude)
    """
    return (
        "latitude" in obj or "lat" in obj or
        "longitude" in obj or "lon" in obj or
        "latitude_deg" in obj or "longitude_deg" in obj
    )


def _is_v2x_like(obj: Dict[str, Any]) -> bool:
    """Check if object looks like a V2X message record.

    Args:
        obj: JSON object to check

    Returns:
        True if object contains V2X-like fields (message type, timestamps)
    """
    return (
        "messageType" in obj or "message_type" in obj or "msgType" in obj or
        "tx_timestamp" in obj or "rx_timestamp" in obj or
        "direction" in obj or "rsu_id" in obj or
        # V2AIX format indicators
        "cam" in obj or "denm" in obj or
        ("header" in obj and isinstance(obj.get("header"), dict) and "message_id" in obj["header"])
    )


def discover_dataset(
    input_dir: Path,
    sample: Optional[int] = None
) -> Dict[str, Any]:
    """Discover and analyze V2AIX dataset structure and contents.

    Recursively scans input directory for JSON files, identifies record types,
    and gathers statistics including vehicle counts, message types, and file counts.

    Args:
        input_dir: Root directory containing JSON files
        sample: Optional limit on objects to sample per file (for large datasets)

    Returns:
        Dictionary containing:
        - total_files: Number of JSON files found
        - gnss_records: Count of GNSS pose records
        - v2x_records: Count of V2X message records
        - other_records: Count of unclassified records
        - unique_vehicles: Set of unique vehicle/station IDs
        - message_types: Set of V2X message types found
        - sample_limit: Sample limit used (if any)

    Raises:
        FileNotFoundError: If input_dir does not exist
        PermissionError: If input_dir is not readable

    Examples:
        >>> summary = discover_dataset(Path("/data/v2aix"), sample=100)
        >>> print(f"Found {len(summary['unique_vehicles'])} vehicles")
        >>> print(f"Message types: {summary['message_types']}")
    """
    input_dir = input_dir.expanduser().resolve()

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    if not input_dir.is_dir():
        raise ValueError(f"Input path is not a directory: {input_dir}")

    # Find all JSON files
    json_files = list(input_dir.rglob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files in {input_dir}")

    if sample is not None:
        logger.info(f"Sampling up to {sample} objects per file")

    # Initialize counters
    gnss_count = 0
    v2x_count = 0
    other_count = 0
    unique_vehicles: Set[str] = set()
    message_types: Set[str] = set()

    # Process each file
    for json_path in json_files:
        logger.debug(f"Processing {json_path.name}")

        for obj in _iter_json_objects(json_path, sample=sample):
            # Extract identifiers
            vehicle_id, station_type, message_type = _extract_ids_and_types(obj)

            # Track unique vehicles
            if vehicle_id:
                unique_vehicles.add(vehicle_id)

            # Track message types
            if message_type:
                message_types.add(message_type)

            # Classify record type
            if _is_gnss_like(obj):
                gnss_count += 1
            elif _is_v2x_like(obj):
                v2x_count += 1
            else:
                other_count += 1

    # Compile summary
    summary = {
        "total_files": len(json_files),
        "gnss_records": gnss_count,
        "v2x_records": v2x_count,
        "other_records": other_count,
        "unique_vehicles": sorted(list(unique_vehicles)),
        "vehicle_count": len(unique_vehicles),
        "message_types": sorted(list(message_types)),
        "sample_limit": sample,
    }

    logger.info(
        f"Discovery complete: {len(unique_vehicles)} unique vehicles, "
        f"{gnss_count} GNSS records, {v2x_count} V2X records"
    )

    return summary


def discovery_dataframe(summary: Dict[str, Any]):
    """Convert discovery summary to a pandas DataFrame for display.

    Args:
        summary: Dictionary returned by discover_dataset()

    Returns:
        pandas DataFrame with summary statistics

    Raises:
        ImportError: If pandas is not installed

    Examples:
        >>> summary = discover_dataset(Path("/data/v2aix"))
        >>> df = discovery_dataframe(summary)
        >>> print(df.to_string(index=False))
    """
    import pandas as pd

    data = {
        "Metric": [
            "Total JSON Files",
            "GNSS Records",
            "V2X Message Records",
            "Other Records",
            "Unique Vehicles",
            "Message Types",
            "Sample Limit"
        ],
        "Value": [
            summary["total_files"],
            summary["gnss_records"],
            summary["v2x_records"],
            summary["other_records"],
            summary["vehicle_count"],
            len(summary["message_types"]),
            summary["sample_limit"] if summary["sample_limit"] else "None"
        ]
    }

    return pd.DataFrame(data)
