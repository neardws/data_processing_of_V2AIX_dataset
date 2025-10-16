"""
Trajectory extraction and normalization for V2AIX GNSS records.

This module processes raw GNSS records into standardized 1Hz trajectories,
including smoothing, interpolation, gap detection, and quality flagging.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter

from .models import GnssRecord, QualityFlags, TrajectorySample

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TARGET_HZ = 1
DEFAULT_GAP_THRESHOLD_S = 5.0
DEFAULT_LOW_SPEED_THRESHOLD_MPS = 1.0  # Below this, heading is unreliable
DEFAULT_SAVGOL_WINDOW = 7  # Must be odd
DEFAULT_SAVGOL_POLYORDER = 2


# ============================================================================
# Trajectory Preparation
# ============================================================================

def sort_records_by_time(records: List[GnssRecord]) -> List[GnssRecord]:
    """Sort GNSS records by timestamp.

    Args:
        records: List of GNSS records

    Returns:
        Sorted list (ascending by timestamp)
    """
    return sorted(records, key=lambda r: r.timestamp_utc_ms)


def group_records_by_vehicle(
    records: List[GnssRecord]
) -> Dict[str, List[GnssRecord]]:
    """Group GNSS records by vehicle ID.

    Args:
        records: List of GNSS records

    Returns:
        Dictionary mapping vehicle_id to sorted list of records
    """
    from collections import defaultdict
    grouped: Dict[str, List[GnssRecord]] = defaultdict(list)

    for rec in records:
        grouped[rec.vehicle_id].append(rec)

    # Sort each vehicle's records by time
    for vehicle_id in grouped:
        grouped[vehicle_id] = sort_records_by_time(grouped[vehicle_id])

    return dict(grouped)


# ============================================================================
# Gap Detection
# ============================================================================

def detect_gaps(
    timestamps_ms: np.ndarray,
    gap_threshold_s: float = DEFAULT_GAP_THRESHOLD_S
) -> List[Tuple[int, int]]:
    """Detect gaps in timestamp sequence.

    Args:
        timestamps_ms: Array of timestamps in milliseconds
        gap_threshold_s: Gap threshold in seconds

    Returns:
        List of (start_idx, end_idx) tuples indicating gap positions

    Notes:
        A gap is detected when consecutive timestamps are separated
        by more than gap_threshold_s seconds.

    Examples:
        >>> timestamps = np.array([1000, 2000, 8000, 9000])
        >>> gaps = detect_gaps(timestamps, gap_threshold_s=5.0)
        >>> gaps
        [(1, 2)]  # Gap between index 1 and 2 (2000 to 8000 = 6s)
    """
    if len(timestamps_ms) < 2:
        return []

    # Calculate time differences in seconds
    time_diffs_s = np.diff(timestamps_ms) / 1000.0

    # Find gaps
    gap_indices = np.where(time_diffs_s > gap_threshold_s)[0]

    # Convert to (start, end) tuples
    gaps = [(int(idx), int(idx + 1)) for idx in gap_indices]

    return gaps


def create_gap_flags(
    n_samples: int,
    gaps: List[Tuple[int, int]]
) -> np.ndarray:
    """Create boolean array flagging samples near gaps.

    Args:
        n_samples: Total number of samples
        gaps: List of (start_idx, end_idx) gap positions

    Returns:
        Boolean array where True indicates sample is near a gap

    Notes:
        Samples at gap boundaries are flagged as they may be
        less reliable due to interpolation across gaps.
    """
    flags = np.zeros(n_samples, dtype=bool)

    for start_idx, end_idx in gaps:
        # Flag samples at gap boundaries
        if start_idx >= 0:
            flags[start_idx] = True
        if end_idx < n_samples:
            flags[end_idx] = True

    return flags


# ============================================================================
# Smoothing
# ============================================================================

def smooth_trajectory(
    values: np.ndarray,
    window_length: int = DEFAULT_SAVGOL_WINDOW,
    polyorder: int = DEFAULT_SAVGOL_POLYORDER,
    gaps: Optional[List[Tuple[int, int]]] = None
) -> np.ndarray:
    """Smooth trajectory using Savitzky-Golay filter.

    Args:
        values: Array of values to smooth (lat, lon, or alt)
        window_length: Window length for filter (must be odd)
        polyorder: Polynomial order for filter
        gaps: Optional list of gap positions to avoid smoothing across

    Returns:
        Smoothed array

    Notes:
        - If gaps are provided, smoothing is applied separately to
          continuous segments between gaps
        - Window length must be odd and >= polyorder + 2
        - For short segments, no smoothing is applied

    Examples:
        >>> values = np.array([1.0, 2.0, 1.5, 2.5, 2.0, 3.0])
        >>> smoothed = smooth_trajectory(values, window_length=5, polyorder=2)
    """
    if len(values) < window_length:
        logger.debug(
            f"Trajectory too short for smoothing "
            f"({len(values)} < {window_length}), returning original"
        )
        return values.copy()

    # Ensure window_length is odd
    if window_length % 2 == 0:
        window_length += 1
        logger.debug(f"Adjusted window_length to {window_length} (must be odd)")

    # If no gaps, smooth entire trajectory
    if not gaps:
        try:
            return savgol_filter(values, window_length, polyorder, mode='interp')
        except Exception as e:
            logger.warning(f"Savitzky-Golay filter failed: {e}, returning original")
            return values.copy()

    # Smooth segments between gaps
    smoothed = values.copy()
    segment_starts = [0] + [end for _, end in gaps]
    segment_ends = [start for start, _ in gaps] + [len(values)]

    for start, end in zip(segment_starts, segment_ends):
        segment = values[start:end]
        segment_length = len(segment)

        if segment_length >= window_length:
            try:
                smoothed[start:end] = savgol_filter(
                    segment, window_length, polyorder, mode='interp'
                )
            except Exception as e:
                logger.debug(f"Smoothing failed for segment [{start}:{end}]: {e}")
        else:
            logger.debug(
                f"Segment [{start}:{end}] too short for smoothing "
                f"({segment_length} < {window_length})"
            )

    return smoothed


# ============================================================================
# Resampling
# ============================================================================

def resample_to_1hz(
    timestamps_ms: np.ndarray,
    values: np.ndarray,
    gaps: Optional[List[Tuple[int, int]]] = None,
    gap_threshold_s: float = DEFAULT_GAP_THRESHOLD_S
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Resample trajectory to 1Hz using linear interpolation.

    Args:
        timestamps_ms: Original timestamps in milliseconds
        values: Original values (lat, lon, alt, speed, or heading)
        gaps: Optional list of gap positions
        gap_threshold_s: Gap threshold in seconds

    Returns:
        Tuple of (resampled_timestamps_ms, resampled_values, extrapolated_flags)
        - resampled_timestamps_ms: 1Hz grid timestamps
        - resampled_values: Interpolated values at 1Hz
        - extrapolated_flags: Boolean array indicating extrapolated samples

    Notes:
        - Creates 1Hz grid from first to last timestamp
        - Uses linear interpolation for values
        - Does NOT interpolate across gaps > gap_threshold_s
        - Marks extrapolated values with flags

    Examples:
        >>> timestamps = np.array([0, 1500, 3000])  # Irregular spacing
        >>> values = np.array([10.0, 15.0, 20.0])
        >>> ts_1hz, vals_1hz, extrap = resample_to_1hz(timestamps, values)
        >>> len(ts_1hz)
        4  # 0, 1000, 2000, 3000 ms
    """
    if len(timestamps_ms) < 2:
        logger.warning("Need at least 2 points for resampling")
        return timestamps_ms.copy(), values.copy(), np.zeros(len(timestamps_ms), dtype=bool)

    # Create 1Hz grid
    start_ms = timestamps_ms[0]
    end_ms = timestamps_ms[-1]
    grid_1hz_ms = np.arange(start_ms, end_ms + 1000, 1000)  # 1Hz = 1000ms

    # Detect gaps if not provided
    if gaps is None:
        gaps = detect_gaps(timestamps_ms, gap_threshold_s)

    # Create interpolator
    # Use 'linear' for most values, but handle gaps
    interpolator = interp1d(
        timestamps_ms,
        values,
        kind='linear',
        bounds_error=False,
        fill_value=np.nan  # NaN for out-of-bounds
    )

    # Interpolate
    resampled_values = interpolator(grid_1hz_ms)

    # Mark extrapolated points (outside original range)
    extrapolated = np.zeros(len(grid_1hz_ms), dtype=bool)
    extrapolated[grid_1hz_ms < timestamps_ms[0]] = True
    extrapolated[grid_1hz_ms > timestamps_ms[-1]] = True

    # Set values across gaps to NaN
    if gaps:
        for start_idx, end_idx in gaps:
            gap_start_ms = timestamps_ms[start_idx]
            gap_end_ms = timestamps_ms[end_idx]

            # Find grid points within gap
            in_gap = (grid_1hz_ms > gap_start_ms) & (grid_1hz_ms < gap_end_ms)
            resampled_values[in_gap] = np.nan

    return grid_1hz_ms, resampled_values, extrapolated


# ============================================================================
# Quality Flags
# ============================================================================

def create_quality_flags(
    gap_flags: np.ndarray,
    extrapolated_flags: np.ndarray,
    speeds_mps: Optional[np.ndarray] = None,
    low_speed_threshold: float = DEFAULT_LOW_SPEED_THRESHOLD_MPS
) -> List[QualityFlags]:
    """Create QualityFlags for each trajectory sample.

    Args:
        gap_flags: Boolean array indicating samples near gaps
        extrapolated_flags: Boolean array indicating extrapolated samples
        speeds_mps: Optional array of speeds in m/s
        low_speed_threshold: Speed below which heading is unreliable

    Returns:
        List of QualityFlags objects

    Examples:
        >>> gap_flags = np.array([False, True, False])
        >>> extrap_flags = np.array([False, False, True])
        >>> speeds = np.array([5.0, 0.5, 3.0])
        >>> flags = create_quality_flags(gap_flags, extrap_flags, speeds)
        >>> flags[1].low_speed
        True
    """
    n_samples = len(gap_flags)
    quality_flags = []

    for i in range(n_samples):
        low_speed = False
        if speeds_mps is not None and i < len(speeds_mps):
            if not np.isnan(speeds_mps[i]):
                low_speed = speeds_mps[i] < low_speed_threshold

        quality_flags.append(
            QualityFlags(
                gap=bool(gap_flags[i]),
                extrapolated=bool(extrapolated_flags[i]),
                low_speed=low_speed
            )
        )

    return quality_flags


# ============================================================================
# Main Trajectory Extraction
# ============================================================================

def extract_trajectory(
    records: List[GnssRecord],
    vehicle_id: str,
    target_hz: int = DEFAULT_TARGET_HZ,
    gap_threshold_s: float = DEFAULT_GAP_THRESHOLD_S,
    apply_smoothing: bool = True,
    smoothing_window: int = DEFAULT_SAVGOL_WINDOW,
    low_speed_threshold: float = DEFAULT_LOW_SPEED_THRESHOLD_MPS
) -> List[TrajectorySample]:
    """Extract and normalize trajectory from GNSS records.

    Args:
        records: List of GNSS records for a single vehicle
        vehicle_id: Vehicle identifier
        target_hz: Target sampling frequency (default: 1Hz)
        gap_threshold_s: Gap detection threshold in seconds
        apply_smoothing: Whether to apply Savitzky-Golay smoothing
        smoothing_window: Window length for smoothing filter
        low_speed_threshold: Speed threshold for low_speed flag

    Returns:
        List of TrajectorySample objects at target_hz frequency

    Notes:
        Processing pipeline:
        1. Sort records by timestamp
        2. Detect gaps
        3. Smooth lat/lon/alt (optional)
        4. Resample to target_hz
        5. Create quality flags
        6. Build TrajectorySample objects

        Note: x_m and y_m are set to 0.0 (coordinate transformation happens later)

    Examples:
        >>> gnss_records = [...]  # List of GnssRecord
        >>> trajectory = extract_trajectory(
        ...     gnss_records,
        ...     vehicle_id='vehicle_001',
        ...     target_hz=1,
        ...     gap_threshold_s=5.0
        ... )
        >>> len(trajectory)
        120  # 2 minutes at 1Hz
    """
    if not records:
        logger.warning(f"No records for vehicle {vehicle_id}")
        return []

    # Step 1: Sort by time
    sorted_records = sort_records_by_time(records)

    # Step 2: Extract arrays
    timestamps_ms = np.array([r.timestamp_utc_ms for r in sorted_records])
    lats = np.array([r.latitude_deg for r in sorted_records])
    lons = np.array([r.longitude_deg for r in sorted_records])
    alts = np.array([r.altitude_m if r.altitude_m is not None else np.nan
                     for r in sorted_records])
    speeds = np.array([r.speed_mps if r.speed_mps is not None else np.nan
                       for r in sorted_records])
    headings = np.array([r.heading_deg if r.heading_deg is not None else np.nan
                         for r in sorted_records])

    # Step 3: Detect gaps
    gaps = detect_gaps(timestamps_ms, gap_threshold_s)

    if gaps:
        logger.debug(f"Vehicle {vehicle_id}: detected {len(gaps)} gaps")

    # Step 4: Smooth (if enabled)
    if apply_smoothing:
        lats = smooth_trajectory(lats, smoothing_window, gaps=gaps)
        lons = smooth_trajectory(lons, smoothing_window, gaps=gaps)
        # Don't smooth altitude if mostly NaN
        if not np.all(np.isnan(alts)):
            alts = smooth_trajectory(alts, smoothing_window, gaps=gaps)

    # Step 5: Resample to target Hz
    # Currently only supports 1Hz
    if target_hz != 1:
        logger.warning(f"Only 1Hz resampling supported, using 1Hz instead of {target_hz}Hz")

    grid_ts_ms, resampled_lats, extrap_lats = resample_to_1hz(
        timestamps_ms, lats, gaps, gap_threshold_s
    )
    _, resampled_lons, extrap_lons = resample_to_1hz(
        timestamps_ms, lons, gaps, gap_threshold_s
    )
    _, resampled_alts, _ = resample_to_1hz(
        timestamps_ms, alts, gaps, gap_threshold_s
    )
    _, resampled_speeds, _ = resample_to_1hz(
        timestamps_ms, speeds, gaps, gap_threshold_s
    )
    _, resampled_headings, _ = resample_to_1hz(
        timestamps_ms, headings, gaps, gap_threshold_s
    )

    # Combine extrapolation flags
    extrapolated_flags = extrap_lats | extrap_lons

    # Step 6: Create gap flags for resampled grid
    # Map original gaps to resampled grid
    gap_flags = np.zeros(len(grid_ts_ms), dtype=bool)
    if gaps:
        for start_idx, end_idx in gaps:
            gap_start_ms = timestamps_ms[start_idx]
            gap_end_ms = timestamps_ms[end_idx]
            # Flag samples near gap
            near_gap = (
                (grid_ts_ms >= gap_start_ms - 1000) &
                (grid_ts_ms <= gap_end_ms + 1000)
            )
            gap_flags |= near_gap

    # Step 7: Create quality flags
    quality_flags = create_quality_flags(
        gap_flags,
        extrapolated_flags,
        resampled_speeds,
        low_speed_threshold
    )

    # Step 8: Build TrajectorySample objects
    trajectory = []
    for i in range(len(grid_ts_ms)):
        # Skip NaN values (from gaps or extrapolation)
        if np.isnan(resampled_lats[i]) or np.isnan(resampled_lons[i]):
            continue

        sample = TrajectorySample(
            vehicle_id=vehicle_id,
            timestamp_utc_ms=int(grid_ts_ms[i]),
            lat_deg=float(resampled_lats[i]),
            lon_deg=float(resampled_lons[i]),
            alt_m=float(resampled_alts[i]) if not np.isnan(resampled_alts[i]) else None,
            x_m=0.0,  # Will be set by coordinate transformation
            y_m=0.0,  # Will be set by coordinate transformation
            speed_mps=float(resampled_speeds[i]) if not np.isnan(resampled_speeds[i]) else None,
            heading_deg=float(resampled_headings[i]) if not np.isnan(resampled_headings[i]) else None,
            quality=quality_flags[i]
        )
        trajectory.append(sample)

    logger.info(
        f"Vehicle {vehicle_id}: extracted {len(trajectory)} trajectory samples "
        f"({len(sorted_records)} original records)"
    )

    return trajectory


def extract_all_trajectories(
    records: List[GnssRecord],
    **kwargs
) -> Dict[str, List[TrajectorySample]]:
    """Extract trajectories for all vehicles in dataset.

    Args:
        records: List of GNSS records (possibly from multiple vehicles)
        **kwargs: Additional arguments passed to extract_trajectory()

    Returns:
        Dictionary mapping vehicle_id to list of TrajectorySample

    Examples:
        >>> all_trajectories = extract_all_trajectories(
        ...     all_gnss_records,
        ...     gap_threshold_s=5.0,
        ...     apply_smoothing=True
        ... )
        >>> len(all_trajectories)
        150  # 150 vehicles
    """
    # Group by vehicle
    by_vehicle = group_records_by_vehicle(records)

    trajectories = {}
    for vehicle_id, vehicle_records in by_vehicle.items():
        traj = extract_trajectory(vehicle_records, vehicle_id, **kwargs)
        if traj:
            trajectories[vehicle_id] = traj

    logger.info(
        f"Extracted trajectories for {len(trajectories)} vehicles "
        f"from {len(records)} GNSS records"
    )

    return trajectories
