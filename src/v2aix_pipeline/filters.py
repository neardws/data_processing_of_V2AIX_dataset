"""
Geographic filtering for V2AIX dataset records.

This module provides functions to filter GNSS records by geographic region,
supporting both bounding box and polygon-based filtering. Uses shapely for
efficient geometric operations.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import Point, Polygon, box

from .models import GnssRecord

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Type Definitions
# ============================================================================

# Bounding box: (min_lon, min_lat, max_lon, max_lat)
BBox = Tuple[float, float, float, float]


# ============================================================================
# Coordinate Validation
# ============================================================================

def validate_coordinates(lat: float, lon: float) -> bool:
    """Validate latitude and longitude values.

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees

    Returns:
        True if coordinates are valid, False otherwise

    Notes:
        Valid ranges:
        - Latitude: -90 to +90 degrees
        - Longitude: -180 to +180 degrees
    """
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def validate_bbox(bbox: BBox) -> bool:
    """Validate a bounding box.

    Args:
        bbox: Tuple of (min_lon, min_lat, max_lon, max_lat)

    Returns:
        True if bounding box is valid, False otherwise

    Notes:
        Checks:
        - All coordinates in valid range
        - min_lon < max_lon
        - min_lat < max_lat
    """
    min_lon, min_lat, max_lon, max_lat = bbox

    # Check coordinate ranges
    if not validate_coordinates(min_lat, min_lon):
        logger.warning(f"Invalid min coordinates: ({min_lat}, {min_lon})")
        return False
    if not validate_coordinates(max_lat, max_lon):
        logger.warning(f"Invalid max coordinates: ({max_lat}, {max_lon})")
        return False

    # Check min < max
    if min_lon >= max_lon:
        logger.warning(f"min_lon ({min_lon}) >= max_lon ({max_lon})")
        return False
    if min_lat >= max_lat:
        logger.warning(f"min_lat ({min_lat}) >= max_lat ({max_lat})")
        return False

    return True


# ============================================================================
# GeoJSON Loading
# ============================================================================

def load_geojson_polygon(geojson_path: Path) -> Optional[Polygon]:
    """Load a polygon from a GeoJSON file.

    Args:
        geojson_path: Path to GeoJSON file

    Returns:
        Shapely Polygon object, or None if loading fails

    Raises:
        FileNotFoundError: If GeoJSON file does not exist
        ValueError: If GeoJSON format is invalid

    Notes:
        Supports GeoJSON Feature or FeatureCollection with:
        - Polygon geometry
        - MultiPolygon geometry (uses first polygon)

        Coordinates should be in [lon, lat] format (GeoJSON standard)

    Examples:
        >>> polygon = load_geojson_polygon(Path("region.geojson"))
        >>> point = Point(6.5, 50.5)
        >>> point.within(polygon)
        True
    """
    geojson_path = geojson_path.expanduser().resolve()

    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON file not found: {geojson_path}")

    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {geojson_path}: {e}")

    # Handle different GeoJSON structures
    geometry = None

    if data.get('type') == 'FeatureCollection':
        # Extract first feature's geometry
        features = data.get('features', [])
        if not features:
            raise ValueError(f"FeatureCollection has no features in {geojson_path}")
        geometry = features[0].get('geometry')

    elif data.get('type') == 'Feature':
        # Extract feature's geometry
        geometry = data.get('geometry')

    elif data.get('type') in ('Polygon', 'MultiPolygon'):
        # Direct geometry
        geometry = data

    else:
        raise ValueError(
            f"Unsupported GeoJSON type: {data.get('type')}. "
            f"Expected Feature, FeatureCollection, Polygon, or MultiPolygon"
        )

    if geometry is None:
        raise ValueError(f"No geometry found in {geojson_path}")

    # Convert to Shapely Polygon
    geom_type = geometry.get('type')
    coordinates = geometry.get('coordinates')

    if geom_type == 'Polygon':
        # Polygon: coordinates is [exterior, hole1, hole2, ...]
        # We use only the exterior ring
        if not coordinates or not coordinates[0]:
            raise ValueError(f"Empty Polygon coordinates in {geojson_path}")
        return Polygon(coordinates[0])

    elif geom_type == 'MultiPolygon':
        # MultiPolygon: coordinates is [[polygon1], [polygon2], ...]
        # Use the first polygon
        if not coordinates or not coordinates[0] or not coordinates[0][0]:
            raise ValueError(f"Empty MultiPolygon coordinates in {geojson_path}")
        logger.warning(f"MultiPolygon detected, using first polygon only")
        return Polygon(coordinates[0][0])

    else:
        raise ValueError(
            f"Unsupported geometry type: {geom_type}. "
            f"Expected Polygon or MultiPolygon"
        )


# ============================================================================
# Filtering Functions
# ============================================================================

def filter_by_bbox(
    records: List[GnssRecord],
    bbox: BBox,
    mode: str = 'intersect'
) -> List[GnssRecord]:
    """Filter GNSS records by bounding box.

    Args:
        records: List of GNSS records to filter
        bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat)
        mode: Filtering mode:
              - 'intersect': Include if any point in bbox (default)
              - 'contain': Include only if ALL points in bbox (per vehicle)
              - 'first': Include if first point in bbox (per vehicle)

    Returns:
        Filtered list of GNSS records

    Notes:
        Mode behaviors:
        - 'intersect': Keep vehicles that pass through the region
        - 'contain': Keep only vehicles entirely within the region
        - 'first': Keep vehicles that start in the region

    Examples:
        >>> bbox = (6.0, 50.0, 7.0, 51.0)  # Aachen region
        >>> filtered = filter_by_bbox(all_records, bbox, mode='intersect')
        >>> len(filtered) < len(all_records)
        True
    """
    if not validate_bbox(bbox):
        raise ValueError(f"Invalid bounding box: {bbox}")

    min_lon, min_lat, max_lon, max_lat = bbox

    if mode == 'intersect':
        # Simple: any point in bbox
        filtered = [
            rec for rec in records
            if (min_lon <= rec.longitude_deg <= max_lon and
                min_lat <= rec.latitude_deg <= max_lat)
        ]
        logger.info(
            f"Bbox filter (intersect): {len(filtered)}/{len(records)} records kept"
        )
        return filtered

    elif mode == 'contain':
        # Complex: group by vehicle, keep only if ALL points in bbox
        from collections import defaultdict
        by_vehicle: Dict[str, List[GnssRecord]] = defaultdict(list)

        for rec in records:
            by_vehicle[rec.vehicle_id].append(rec)

        filtered = []
        for vehicle_id, vehicle_records in by_vehicle.items():
            # Check if all points are in bbox
            all_in_bbox = all(
                min_lon <= rec.longitude_deg <= max_lon and
                min_lat <= rec.latitude_deg <= max_lat
                for rec in vehicle_records
            )
            if all_in_bbox:
                filtered.extend(vehicle_records)

        logger.info(
            f"Bbox filter (contain): {len(filtered)}/{len(records)} records kept "
            f"({len(filtered) // len(by_vehicle) if by_vehicle else 0} vehicles)"
        )
        return filtered

    elif mode == 'first':
        # Group by vehicle, keep if first point in bbox
        from collections import defaultdict
        by_vehicle: Dict[str, List[GnssRecord]] = defaultdict(list)

        for rec in records:
            by_vehicle[rec.vehicle_id].append(rec)

        filtered = []
        for vehicle_id, vehicle_records in by_vehicle.items():
            # Sort by timestamp and check first point
            sorted_records = sorted(vehicle_records, key=lambda r: r.timestamp_utc_ms)
            first = sorted_records[0]

            if (min_lon <= first.longitude_deg <= max_lon and
                min_lat <= first.latitude_deg <= max_lat):
                filtered.extend(vehicle_records)

        logger.info(
            f"Bbox filter (first): {len(filtered)}/{len(records)} records kept"
        )
        return filtered

    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'intersect', 'contain', or 'first'")


def filter_by_polygon(
    records: List[GnssRecord],
    polygon: Polygon,
    mode: str = 'intersect'
) -> List[GnssRecord]:
    """Filter GNSS records by polygon.

    Args:
        records: List of GNSS records to filter
        polygon: Shapely Polygon object defining the region
        mode: Filtering mode (same as filter_by_bbox):
              - 'intersect': Include if any point in polygon (default)
              - 'contain': Include only if ALL points in polygon (per vehicle)
              - 'first': Include if first point in polygon (per vehicle)

    Returns:
        Filtered list of GNSS records

    Examples:
        >>> polygon = Polygon([(6.0, 50.0), (7.0, 50.0), (7.0, 51.0), (6.0, 51.0)])
        >>> filtered = filter_by_polygon(all_records, polygon)
    """
    if mode == 'intersect':
        # Simple: any point in polygon
        filtered = [
            rec for rec in records
            if polygon.contains(Point(rec.longitude_deg, rec.latitude_deg))
        ]
        logger.info(
            f"Polygon filter (intersect): {len(filtered)}/{len(records)} records kept"
        )
        return filtered

    elif mode == 'contain':
        # Group by vehicle, keep only if ALL points in polygon
        from collections import defaultdict
        by_vehicle: Dict[str, List[GnssRecord]] = defaultdict(list)

        for rec in records:
            by_vehicle[rec.vehicle_id].append(rec)

        filtered = []
        for vehicle_id, vehicle_records in by_vehicle.items():
            # Check if all points are in polygon
            all_in_polygon = all(
                polygon.contains(Point(rec.longitude_deg, rec.latitude_deg))
                for rec in vehicle_records
            )
            if all_in_polygon:
                filtered.extend(vehicle_records)

        logger.info(
            f"Polygon filter (contain): {len(filtered)}/{len(records)} records kept"
        )
        return filtered

    elif mode == 'first':
        # Group by vehicle, keep if first point in polygon
        from collections import defaultdict
        by_vehicle: Dict[str, List[GnssRecord]] = defaultdict(list)

        for rec in records:
            by_vehicle[rec.vehicle_id].append(rec)

        filtered = []
        for vehicle_id, vehicle_records in by_vehicle.items():
            # Sort by timestamp and check first point
            sorted_records = sorted(vehicle_records, key=lambda r: r.timestamp_utc_ms)
            first = sorted_records[0]

            if polygon.contains(Point(first.longitude_deg, first.latitude_deg)):
                filtered.extend(vehicle_records)

        logger.info(
            f"Polygon filter (first): {len(filtered)}/{len(records)} records kept"
        )
        return filtered

    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'intersect', 'contain', or 'first'")


def filter_by_polygon_file(
    records: List[GnssRecord],
    geojson_path: Path,
    mode: str = 'intersect'
) -> List[GnssRecord]:
    """Filter GNSS records by polygon from GeoJSON file.

    Convenience function combining load_geojson_polygon and filter_by_polygon.

    Args:
        records: List of GNSS records to filter
        geojson_path: Path to GeoJSON file containing polygon
        mode: Filtering mode ('intersect', 'contain', or 'first')

    Returns:
        Filtered list of GNSS records

    Raises:
        FileNotFoundError: If GeoJSON file does not exist
        ValueError: If GeoJSON format is invalid

    Examples:
        >>> filtered = filter_by_polygon_file(
        ...     all_records,
        ...     Path("region.geojson"),
        ...     mode='intersect'
        ... )
    """
    polygon = load_geojson_polygon(geojson_path)
    return filter_by_polygon(records, polygon, mode=mode)


# ============================================================================
# Utility Functions
# ============================================================================

def get_bbox_from_records(records: List[GnssRecord]) -> BBox:
    """Calculate bounding box from a list of GNSS records.

    Args:
        records: List of GNSS records

    Returns:
        Bounding box as (min_lon, min_lat, max_lon, max_lat)

    Raises:
        ValueError: If records list is empty

    Examples:
        >>> bbox = get_bbox_from_records(all_records)
        >>> print(f"Region: {bbox}")
        Region: (6.0, 50.0, 7.0, 51.0)
    """
    if not records:
        raise ValueError("Cannot calculate bbox from empty records list")

    lats = [rec.latitude_deg for rec in records]
    lons = [rec.longitude_deg for rec in records]

    return (min(lons), min(lats), max(lons), max(lats))


def get_unique_vehicles(records: List[GnssRecord]) -> List[str]:
    """Get list of unique vehicle IDs from GNSS records.

    Args:
        records: List of GNSS records

    Returns:
        Sorted list of unique vehicle IDs

    Examples:
        >>> vehicles = get_unique_vehicles(filtered_records)
        >>> print(f"Found {len(vehicles)} vehicles")
        Found 150 vehicles
    """
    return sorted(list(set(rec.vehicle_id for rec in records)))


def group_by_vehicle(records: List[GnssRecord]) -> Dict[str, List[GnssRecord]]:
    """Group GNSS records by vehicle ID.

    Args:
        records: List of GNSS records

    Returns:
        Dictionary mapping vehicle_id to list of records

    Examples:
        >>> by_vehicle = group_by_vehicle(all_records)
        >>> vehicle_001_records = by_vehicle['vehicle_001']
        >>> print(f"Vehicle 001 has {len(vehicle_001_records)} records")
    """
    from collections import defaultdict
    grouped: Dict[str, List[GnssRecord]] = defaultdict(list)

    for rec in records:
        grouped[rec.vehicle_id].append(rec)

    return dict(grouped)


def filter_summary(
    original: List[GnssRecord],
    filtered: List[GnssRecord]
) -> Dict[str, Any]:
    """Generate summary statistics for filtering operation.

    Args:
        original: Original list of GNSS records
        filtered: Filtered list of GNSS records

    Returns:
        Dictionary with summary statistics

    Examples:
        >>> summary = filter_summary(all_records, filtered_records)
        >>> print(summary)
        {
            'original_count': 10000,
            'filtered_count': 3500,
            'reduction_pct': 65.0,
            'original_vehicles': 150,
            'filtered_vehicles': 75,
            'vehicle_retention_pct': 50.0
        }
    """
    original_vehicles = get_unique_vehicles(original)
    filtered_vehicles = get_unique_vehicles(filtered)

    reduction_pct = 0.0
    if len(original) > 0:
        reduction_pct = 100.0 * (1.0 - len(filtered) / len(original))

    vehicle_retention_pct = 0.0
    if len(original_vehicles) > 0:
        vehicle_retention_pct = 100.0 * len(filtered_vehicles) / len(original_vehicles)

    return {
        'original_count': len(original),
        'filtered_count': len(filtered),
        'reduction_pct': round(reduction_pct, 2),
        'original_vehicles': len(original_vehicles),
        'filtered_vehicles': len(filtered_vehicles),
        'vehicle_retention_pct': round(vehicle_retention_pct, 2),
        'original_bbox': get_bbox_from_records(original) if original else None,
        'filtered_bbox': get_bbox_from_records(filtered) if filtered else None
    }
