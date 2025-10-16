"""
Data fusion and output for V2AIX pipeline.

Combines trajectories with V2X metrics and exports to Parquet/CSV.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .models import FusedRecord, TrajectorySample, V2XMessageRecord

logger = logging.getLogger(__name__)


# ============================================================================
# V2X Metrics Aggregation
# ============================================================================

def aggregate_v2x_metrics(
    v2x_records: List[V2XMessageRecord],
    timestamp_ms: int,
    sync_tolerance_ms: int = 500
) -> Dict[str, any]:
    """Aggregate V2X metrics around a timestamp.

    Args:
        v2x_records: List of V2X message records
        timestamp_ms: Center timestamp in milliseconds
        sync_tolerance_ms: Time window (±tolerance) for aggregation

    Returns:
        Dictionary with aggregated metrics:
        - tx_bytes: Total transmitted bytes
        - rx_bytes: Total received bytes
        - msg_counts: Dict of message_type -> count
        - avg_latency_ms: Average latency (if available)
    """
    window_start = timestamp_ms - sync_tolerance_ms
    window_end = timestamp_ms + sync_tolerance_ms

    tx_bytes = 0
    rx_bytes = 0
    msg_counts = defaultdict(int)
    latencies = []

    for rec in v2x_records:
        # Check if record is in time window
        rec_time = rec.timestamp_utc_ms or rec.tx_timestamp_utc_ms or rec.rx_timestamp_utc_ms
        if rec_time is None:
            continue
        if not (window_start <= rec_time <= window_end):
            continue

        # Aggregate payload
        if rec.payload_bytes is not None:
            if rec.direction and 'uplink' in str(rec.direction):
                tx_bytes += rec.payload_bytes
            elif rec.direction and 'downlink' in str(rec.direction):
                rx_bytes += rec.payload_bytes

        # Count messages
        if rec.message_type:
            msg_counts[rec.message_type] += 1

        # Collect latencies
        if rec.latency_ms is not None:
            latencies.append(rec.latency_ms)

    avg_latency = sum(latencies) / len(latencies) if latencies else None

    return {
        'tx_bytes': tx_bytes,
        'rx_bytes': rx_bytes,
        'msg_counts': dict(msg_counts),
        'avg_latency_ms': avg_latency
    }


# ============================================================================
# Data Fusion
# ============================================================================

def fuse_trajectory_with_v2x(
    trajectory: List[TrajectorySample],
    v2x_records: List[V2XMessageRecord],
    sync_tolerance_ms: int = 500
) -> List[FusedRecord]:
    """Fuse trajectory samples with V2X metrics.

    Args:
        trajectory: List of trajectory samples (1Hz)
        v2x_records: List of V2X message records
        sync_tolerance_ms: Time synchronization tolerance

    Returns:
        List of FusedRecord objects
    """
    # Group V2X records by vehicle
    v2x_by_vehicle = defaultdict(list)
    for rec in v2x_records:
        v2x_by_vehicle[rec.vehicle_id].append(rec)

    fused = []
    for sample in trajectory:
        vehicle_v2x = v2x_by_vehicle.get(sample.vehicle_id, [])

        # Aggregate V2X metrics around this timestamp
        metrics = aggregate_v2x_metrics(
            vehicle_v2x,
            sample.timestamp_utc_ms,
            sync_tolerance_ms
        )

        fused_rec = FusedRecord(
            vehicle_id=sample.vehicle_id,
            timestamp_utc_ms=sample.timestamp_utc_ms,
            x_m=sample.x_m,
            y_m=sample.y_m,
            tx_bytes=metrics['tx_bytes'],
            rx_bytes=metrics['rx_bytes'],
            avg_latency_ms=metrics['avg_latency_ms'],
            msg_counts=metrics['msg_counts']
        )
        fused.append(fused_rec)

    logger.info(f"Fused {len(fused)} trajectory samples with V2X metrics")
    return fused


def fuse_all(
    trajectories_by_vehicle: Dict[str, List[TrajectorySample]],
    v2x_records: List[V2XMessageRecord],
    sync_tolerance_ms: int = 500
) -> List[FusedRecord]:
    """Fuse all vehicle trajectories with V2X data.

    Args:
        trajectories_by_vehicle: Dict of vehicle_id -> trajectory samples
        v2x_records: All V2X message records
        sync_tolerance_ms: Time synchronization tolerance

    Returns:
        List of all fused records
    """
    all_fused = []
    for vehicle_id, trajectory in trajectories_by_vehicle.items():
        fused = fuse_trajectory_with_v2x(trajectory, v2x_records, sync_tolerance_ms)
        all_fused.extend(fused)

    logger.info(f"Total fused records: {len(all_fused)} from {len(trajectories_by_vehicle)} vehicles")
    return all_fused


# ============================================================================
# Export Functions
# ============================================================================

def export_trajectories_to_parquet(
    trajectories: List[TrajectorySample],
    output_path: Path
) -> None:
    """Export trajectories to Parquet file.

    Args:
        trajectories: List of trajectory samples
        output_path: Output file path (.parquet)
    """
    if not trajectories:
        logger.warning("No trajectories to export")
        return

    # Convert to DataFrame
    data = {
        'vehicle_id': [t.vehicle_id for t in trajectories],
        'timestamp_utc_ms': [t.timestamp_utc_ms for t in trajectories],
        'lat_deg': [t.lat_deg for t in trajectories],
        'lon_deg': [t.lon_deg for t in trajectories],
        'alt_m': [t.alt_m for t in trajectories],
        'x_m': [t.x_m for t in trajectories],
        'y_m': [t.y_m for t in trajectories],
        'speed_mps': [t.speed_mps for t in trajectories],
        'heading_deg': [t.heading_deg for t in trajectories],
        'quality_gap': [t.quality.gap for t in trajectories],
        'quality_extrapolated': [t.quality.extrapolated for t in trajectories],
        'quality_low_speed': [t.quality.low_speed for t in trajectories]
    }
    df = pd.DataFrame(data)

    # Export
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info(f"Exported {len(trajectories)} trajectory samples to {output_path}")


def export_fused_to_parquet(
    fused_records: List[FusedRecord],
    output_path: Path
) -> None:
    """Export fused records to Parquet file.

    Args:
        fused_records: List of fused records
        output_path: Output file path (.parquet)
    """
    if not fused_records:
        logger.warning("No fused records to export")
        return

    # Convert to DataFrame
    data = {
        'vehicle_id': [r.vehicle_id for r in fused_records],
        'timestamp_utc_ms': [r.timestamp_utc_ms for r in fused_records],
        'x_m': [r.x_m for r in fused_records],
        'y_m': [r.y_m for r in fused_records],
        'tx_bytes': [r.tx_bytes for r in fused_records],
        'rx_bytes': [r.rx_bytes for r in fused_records],
        'avg_latency_ms': [r.avg_latency_ms for r in fused_records]
    }

    # Handle msg_counts dict
    all_msg_types = set()
    for r in fused_records:
        all_msg_types.update(r.msg_counts.keys())

    for msg_type in sorted(all_msg_types):
        data[f'msg_count_{msg_type}'] = [r.msg_counts.get(msg_type, 0) for r in fused_records]

    df = pd.DataFrame(data)

    # Export
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info(f"Exported {len(fused_records)} fused records to {output_path}")


def export_to_csv(
    trajectories: Optional[List[TrajectorySample]] = None,
    fused_records: Optional[List[FusedRecord]] = None,
    output_dir: Path = Path('.')
) -> None:
    """Export data to CSV files.

    Args:
        trajectories: Optional trajectory samples
        fused_records: Optional fused records
        output_dir: Output directory
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if trajectories:
        data = {
            'vehicle_id': [t.vehicle_id for t in trajectories],
            'timestamp_utc_ms': [t.timestamp_utc_ms for t in trajectories],
            'lat_deg': [t.lat_deg for t in trajectories],
            'lon_deg': [t.lon_deg for t in trajectories],
            'x_m': [t.x_m for t in trajectories],
            'y_m': [t.y_m for t in trajectories],
        }
        df = pd.DataFrame(data)
        csv_path = output_dir / 'trajectories.csv'
        df.to_csv(csv_path, index=False)
        logger.info(f"Exported trajectories to {csv_path}")

    if fused_records:
        data = {
            'vehicle_id': [r.vehicle_id for r in fused_records],
            'timestamp_utc_ms': [r.timestamp_utc_ms for r in fused_records],
            'x_m': [r.x_m for r in fused_records],
            'y_m': [r.y_m for r in fused_records],
            'tx_bytes': [r.tx_bytes for r in fused_records],
            'rx_bytes': [r.rx_bytes for r in fused_records]
        }
        df = pd.DataFrame(data)
        csv_path = output_dir / 'fused.csv'
        df.to_csv(csv_path, index=False)
        logger.info(f"Exported fused data to {csv_path}")
