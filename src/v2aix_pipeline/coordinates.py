"""
Coordinate transformation for V2AIX trajectories.

This module transforms geodetic coordinates (WGS84 lat/lon/alt) to local
planar coordinates (ENU or UTM) for trajectory analysis and visualization.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np
import pymap3d as pm
from pyproj import CRS, Transformer

from .models import TrajectorySample

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Origin Selection
# ============================================================================

def select_origin_from_trajectories(
    trajectories: List[TrajectorySample],
    method: str = 'first'
) -> Tuple[float, float, float]:
    """Select origin point from trajectories.

    Args:
        trajectories: List of trajectory samples
        method: Selection method:
                - 'first': Use first sample's position
                - 'centroid': Use centroid of all positions
                - 'median': Use median lat/lon

    Returns:
        Tuple of (lat_deg, lon_deg, alt_m) for origin point

    Raises:
        ValueError: If trajectories list is empty

    Examples:
        >>> origin = select_origin_from_trajectories(samples, method='centroid')
        >>> print(f"Origin: {origin}")
        (50.7753, 6.0839, 200.0)
    """
    if not trajectories:
        raise ValueError("Cannot select origin from empty trajectory list")

    lats = np.array([t.lat_deg for t in trajectories])
    lons = np.array([t.lon_deg for t in trajectories])
    alts = np.array([t.alt_m if t.alt_m is not None else 0.0 for t in trajectories])

    if method == 'first':
        origin = (float(lats[0]), float(lons[0]), float(alts[0]))
        logger.info(f"Selected first point as origin: {origin}")

    elif method == 'centroid':
        origin = (float(np.mean(lats)), float(np.mean(lons)), float(np.mean(alts)))
        logger.info(f"Selected centroid as origin: {origin}")

    elif method == 'median':
        origin = (float(np.median(lats)), float(np.median(lons)), float(np.median(alts)))
        logger.info(f"Selected median as origin: {origin}")

    else:
        raise ValueError(f"Unknown origin selection method: {method}")

    return origin


# ============================================================================
# ENU Transformation
# ============================================================================

def transform_to_enu(
    trajectories: List[TrajectorySample],
    origin_lat: float,
    origin_lon: float,
    origin_alt: float = 0.0,
    in_place: bool = True
) -> List[TrajectorySample]:
    """Transform trajectories to ENU (East-North-Up) coordinates.

    Args:
        trajectories: List of trajectory samples with lat/lon
        origin_lat: Origin latitude in degrees
        origin_lon: Origin longitude in degrees
        origin_alt: Origin altitude in meters (default: 0.0)
        in_place: If True, modify samples in place; if False, create copies

    Returns:
        List of trajectory samples with x_m and y_m set to ENU coordinates

    Notes:
        - ENU is a local tangent plane coordinate system
        - X-axis points East, Y-axis points North, Z-axis points Up
        - Best for small regions (< 10 km)
        - Uses pymap3d for transformation

    Examples:
        >>> origin = (50.0, 6.0, 0.0)
        >>> transformed = transform_to_enu(samples, *origin)
        >>> print(f"Position: ({transformed[0].x_m:.2f}, {transformed[0].y_m:.2f})")
        Position: (123.45, 678.90)
    """
    if not in_place:
        # Create copies
        trajectories = [
            TrajectorySample(
                vehicle_id=t.vehicle_id,
                timestamp_utc_ms=t.timestamp_utc_ms,
                lat_deg=t.lat_deg,
                lon_deg=t.lon_deg,
                alt_m=t.alt_m,
                x_m=t.x_m,
                y_m=t.y_m,
                speed_mps=t.speed_mps,
                heading_deg=t.heading_deg,
                quality=t.quality
            )
            for t in trajectories
        ]

    # Transform each sample
    for sample in trajectories:
        alt = sample.alt_m if sample.alt_m is not None else 0.0

        # Convert to ENU using pymap3d
        e, n, u = pm.geodetic2enu(
            sample.lat_deg,
            sample.lon_deg,
            alt,
            origin_lat,
            origin_lon,
            origin_alt
        )

        sample.x_m = float(e)  # East
        sample.y_m = float(n)  # North
        # Note: We don't update alt_m (it remains geodetic altitude)

    logger.info(
        f"Transformed {len(trajectories)} samples to ENU "
        f"(origin: {origin_lat:.6f}, {origin_lon:.6f}, {origin_alt:.2f}m)"
    )

    return trajectories


# ============================================================================
# UTM Transformation
# ============================================================================

def determine_utm_zone(lon: float, lat: float) -> int:
    """Determine UTM zone number from longitude and latitude.

    Args:
        lon: Longitude in degrees
        lat: Latitude in degrees

    Returns:
        UTM zone number (1-60)

    Notes:
        - UTM zones are 6 degrees wide
        - Special cases for Norway and Svalbard are NOT handled
        - Returns standard zone based on longitude only

    Examples:
        >>> zone = determine_utm_zone(6.0, 50.0)
        >>> zone
        32
    """
    zone = int((lon + 180) / 6) + 1
    return zone


def create_utm_transformer(
    lon: float,
    lat: float,
    inverse: bool = False
) -> Transformer:
    """Create a pyproj Transformer for UTM conversion.

    Args:
        lon: Reference longitude for zone determination
        lat: Reference latitude for hemisphere determination
        inverse: If True, create transformer for UTM→WGS84; else WGS84→UTM

    Returns:
        pyproj Transformer object

    Examples:
        >>> transformer = create_utm_transformer(6.0, 50.0)
        >>> x, y = transformer.transform(50.0, 6.0)
    """
    zone = determine_utm_zone(lon, lat)
    hemisphere = 'north' if lat >= 0 else 'south'

    # Create CRS objects
    wgs84 = CRS.from_epsg(4326)  # WGS84
    utm = CRS.from_dict({
        'proj': 'utm',
        'zone': zone,
        'south': hemisphere == 'south'
    })

    if inverse:
        transformer = Transformer.from_crs(utm, wgs84, always_xy=True)
    else:
        transformer = Transformer.from_crs(wgs84, utm, always_xy=True)

    logger.debug(f"Created UTM transformer for zone {zone}{hemisphere[0].upper()}")

    return transformer


def transform_to_utm(
    trajectories: List[TrajectorySample],
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
    in_place: bool = True
) -> List[TrajectorySample]:
    """Transform trajectories to UTM coordinates.

    Args:
        trajectories: List of trajectory samples with lat/lon
        origin_lat: Optional origin latitude for zero point
        origin_lon: Optional origin longitude for zero point
        in_place: If True, modify samples in place; if False, create copies

    Returns:
        List of trajectory samples with x_m and y_m set to UTM coordinates

    Notes:
        - UTM zone determined from first sample (or origin if provided)
        - If origin provided, coordinates are relative to origin (x=0, y=0 at origin)
        - If origin not provided, coordinates are absolute UTM values
        - Best for larger regions (> 10 km) or when spanning multiple degrees

    Examples:
        >>> transformed = transform_to_utm(samples, origin_lat=50.0, origin_lon=6.0)
        >>> print(f"Relative position: ({transformed[0].x_m:.2f}, {transformed[0].y_m:.2f})")
    """
    if not trajectories:
        logger.warning("Empty trajectory list for UTM transformation")
        return []

    if not in_place:
        # Create copies
        trajectories = [
            TrajectorySample(
                vehicle_id=t.vehicle_id,
                timestamp_utc_ms=t.timestamp_utc_ms,
                lat_deg=t.lat_deg,
                lon_deg=t.lon_deg,
                alt_m=t.alt_m,
                x_m=t.x_m,
                y_m=t.y_m,
                speed_mps=t.speed_mps,
                heading_deg=t.heading_deg,
                quality=t.quality
            )
            for t in trajectories
        ]

    # Determine reference point for zone
    if origin_lat is not None and origin_lon is not None:
        ref_lat, ref_lon = origin_lat, origin_lon
    else:
        ref_lat, ref_lon = trajectories[0].lat_deg, trajectories[0].lon_deg

    # Create transformer
    transformer = create_utm_transformer(ref_lon, ref_lat)

    # Calculate origin offset if specified
    origin_x, origin_y = 0.0, 0.0
    if origin_lat is not None and origin_lon is not None:
        origin_x, origin_y = transformer.transform(origin_lon, origin_lat)
        logger.debug(f"UTM origin offset: ({origin_x:.2f}, {origin_y:.2f})")

    # Transform each sample
    for sample in trajectories:
        x, y = transformer.transform(sample.lon_deg, sample.lat_deg)
        sample.x_m = float(x - origin_x)
        sample.y_m = float(y - origin_y)

    logger.info(
        f"Transformed {len(trajectories)} samples to UTM "
        f"(zone {determine_utm_zone(ref_lon, ref_lat)}, "
        f"origin offset: {origin_x:.2f}, {origin_y:.2f})"
    )

    return trajectories


# ============================================================================
# High-Level Interface
# ============================================================================

def transform_trajectories(
    trajectories: List[TrajectorySample],
    use_enu: bool = True,
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
    origin_alt: Optional[float] = None,
    auto_select_origin: str = 'first',
    in_place: bool = True
) -> Tuple[List[TrajectorySample], Tuple[float, float, float]]:
    """Transform trajectories to local planar coordinates.

    High-level function that automatically selects transformation method
    and origin point if not specified.

    Args:
        trajectories: List of trajectory samples
        use_enu: If True, use ENU; if False, use UTM
        origin_lat: Optional origin latitude (auto-selected if None)
        origin_lon: Optional origin longitude (auto-selected if None)
        origin_alt: Optional origin altitude (default: 0.0 if None)
        auto_select_origin: Method for auto origin selection ('first', 'centroid', 'median')
        in_place: If True, modify samples in place

    Returns:
        Tuple of (transformed_trajectories, (origin_lat, origin_lon, origin_alt))

    Examples:
        >>> samples, origin = transform_trajectories(
        ...     all_samples,
        ...     use_enu=True,
        ...     auto_select_origin='centroid'
        ... )
        >>> print(f"Used origin: {origin}")
        (50.7753, 6.0839, 200.0)
    """
    if not trajectories:
        logger.warning("Empty trajectory list for transformation")
        return [], (0.0, 0.0, 0.0)

    # Auto-select origin if not provided
    if origin_lat is None or origin_lon is None:
        auto_lat, auto_lon, auto_alt = select_origin_from_trajectories(
            trajectories,
            method=auto_select_origin
        )
        origin_lat = origin_lat or auto_lat
        origin_lon = origin_lon or auto_lon
        origin_alt = origin_alt or auto_alt
    else:
        origin_alt = origin_alt or 0.0

    # Transform based on method
    if use_enu:
        transformed = transform_to_enu(
            trajectories,
            origin_lat,
            origin_lon,
            origin_alt,
            in_place=in_place
        )
    else:
        transformed = transform_to_utm(
            trajectories,
            origin_lat,
            origin_lon,
            in_place=in_place
        )

    origin = (origin_lat, origin_lon, origin_alt)
    return transformed, origin


def apply_transformation_to_all(
    trajectories_by_vehicle: dict[str, List[TrajectorySample]],
    **kwargs
) -> Tuple[dict[str, List[TrajectorySample]], Tuple[float, float, float]]:
    """Apply coordinate transformation to all vehicles.

    Args:
        trajectories_by_vehicle: Dict mapping vehicle_id to trajectory samples
        **kwargs: Arguments passed to transform_trajectories()

    Returns:
        Tuple of (transformed_trajectories_dict, origin)

    Notes:
        - All vehicles use the same origin point
        - Origin is auto-selected from all trajectories combined

    Examples:
        >>> all_trajs = {
        ...     'v1': [sample1, sample2],
        ...     'v2': [sample3, sample4]
        ... }
        >>> transformed, origin = apply_transformation_to_all(
        ...     all_trajs,
        ...     use_enu=True
        ... )
    """
    # Flatten all trajectories for origin selection
    all_samples = []
    for vehicle_samples in trajectories_by_vehicle.values():
        all_samples.extend(vehicle_samples)

    if not all_samples:
        logger.warning("No trajectories to transform")
        return {}, (0.0, 0.0, 0.0)

    # Get origin from all samples
    _, origin = transform_trajectories(
        all_samples,
        in_place=False,  # Don't transform yet, just get origin
        **kwargs
    )

    # Now transform each vehicle's trajectory with the same origin
    transformed_dict = {}
    for vehicle_id, vehicle_samples in trajectories_by_vehicle.items():
        transformed, _ = transform_trajectories(
            vehicle_samples,
            origin_lat=origin[0],
            origin_lon=origin[1],
            origin_alt=origin[2],
            in_place=True,
            **{k: v for k, v in kwargs.items() if k not in ['origin_lat', 'origin_lon', 'origin_alt']}
        )
        transformed_dict[vehicle_id] = transformed

    logger.info(
        f"Applied coordinate transformation to {len(transformed_dict)} vehicles "
        f"using origin {origin}"
    )

    return transformed_dict, origin
