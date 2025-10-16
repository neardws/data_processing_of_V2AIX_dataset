"""
Visualization utilities for V2AIX trajectories and metrics.

This module provides basic plotting functions for trajectory maps,
heatmaps, and time series analysis.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .models import FusedRecord, TrajectorySample

logger = logging.getLogger(__name__)


# ============================================================================
# Trajectory Map Plotting
# ============================================================================

def plot_trajectory_map(
    trajectories_by_vehicle: Dict[str, List[TrajectorySample]],
    output_path: Optional[Path] = None,
    title: str = "Vehicle Trajectories",
    figsize: tuple = (12, 10),
    show_quality: bool = True
) -> None:
    """Plot vehicle trajectories on a 2D map.

    Args:
        trajectories_by_vehicle: Dict mapping vehicle_id to trajectory samples
        output_path: Optional path to save figure
        title: Plot title
        figsize: Figure size (width, height)
        show_quality: If True, color-code by quality flags

    Notes:
        - Requires x_m and y_m to be set (after coordinate transformation)
        - Each vehicle gets a different color
        - Quality flags shown with marker styles if enabled
    """
    if not trajectories_by_vehicle:
        logger.warning("No trajectories to plot")
        return

    fig, ax = plt.subplots(figsize=figsize)

    # Use a color palette with enough colors
    colors = sns.color_palette("husl", len(trajectories_by_vehicle))

    for idx, (vehicle_id, trajectory) in enumerate(trajectories_by_vehicle.items()):
        if not trajectory:
            continue

        x_values = [t.x_m for t in trajectory]
        y_values = [t.y_m for t in trajectory]

        if show_quality:
            # Separate by quality
            normal_x, normal_y = [], []
            gap_x, gap_y = [], []
            low_speed_x, low_speed_y = [], []

            for t in trajectory:
                if t.quality.gap:
                    gap_x.append(t.x_m)
                    gap_y.append(t.y_m)
                elif t.quality.low_speed:
                    low_speed_x.append(t.x_m)
                    low_speed_y.append(t.y_m)
                else:
                    normal_x.append(t.x_m)
                    normal_y.append(t.y_m)

            # Plot with different markers
            if normal_x:
                ax.plot(normal_x, normal_y, '-', color=colors[idx], alpha=0.6, linewidth=1)
                ax.scatter(normal_x, normal_y, c=[colors[idx]], s=10, alpha=0.7, label=vehicle_id)
            if gap_x:
                ax.scatter(gap_x, gap_y, c=[colors[idx]], s=30, marker='x', alpha=0.9)
            if low_speed_x:
                ax.scatter(low_speed_x, low_speed_y, c=[colors[idx]], s=15, marker='^', alpha=0.7)
        else:
            # Simple line plot
            ax.plot(x_values, y_values, '-o', color=colors[idx], alpha=0.6,
                   linewidth=1, markersize=4, label=vehicle_id)

    ax.set_xlabel("X (meters)")
    ax.set_ylabel("Y (meters)")
    ax.set_title(title)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    # Legend only if not too many vehicles
    if len(trajectories_by_vehicle) <= 20:
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)

    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        logger.info(f"Saved trajectory map to {output_path}")
    else:
        plt.show()

    plt.close()


# ============================================================================
# Heatmap Plotting
# ============================================================================

def plot_latency_heatmap(
    fused_records: List[FusedRecord],
    output_path: Optional[Path] = None,
    title: str = "Average Latency Heatmap",
    figsize: tuple = (12, 10),
    grid_size: int = 50
) -> None:
    """Plot 2D heatmap of average latency across space.

    Args:
        fused_records: List of fused records with x_m, y_m, avg_latency_ms
        output_path: Optional path to save figure
        title: Plot title
        figsize: Figure size
        grid_size: Number of grid cells per dimension

    Notes:
        - Requires fused records with valid x_m, y_m, avg_latency_ms
        - Uses 2D binning to aggregate latency values
    """
    if not fused_records:
        logger.warning("No fused records to plot")
        return

    # Extract data
    x_values = [r.x_m for r in fused_records if r.avg_latency_ms is not None]
    y_values = [r.y_m for r in fused_records if r.avg_latency_ms is not None]
    latencies = [r.avg_latency_ms for r in fused_records if r.avg_latency_ms is not None]

    if len(x_values) == 0:
        logger.warning("No latency data available")
        return

    # Create 2D histogram
    fig, ax = plt.subplots(figsize=figsize)

    # Bin the data
    x_bins = np.linspace(min(x_values), max(x_values), grid_size)
    y_bins = np.linspace(min(y_values), max(y_values), grid_size)

    # Calculate average latency in each bin
    latency_grid = np.full((grid_size - 1, grid_size - 1), np.nan)

    for i in range(grid_size - 1):
        for j in range(grid_size - 1):
            mask = (
                (np.array(x_values) >= x_bins[i]) &
                (np.array(x_values) < x_bins[i + 1]) &
                (np.array(y_values) >= y_bins[j]) &
                (np.array(y_values) < y_bins[j + 1])
            )
            if np.any(mask):
                latency_grid[j, i] = np.mean(np.array(latencies)[mask])

    # Plot heatmap
    im = ax.imshow(
        latency_grid,
        extent=[x_bins[0], x_bins[-1], y_bins[0], y_bins[-1]],
        origin='lower',
        aspect='equal',
        cmap='YlOrRd',
        interpolation='bilinear'
    )

    plt.colorbar(im, ax=ax, label='Average Latency (ms)')
    ax.set_xlabel("X (meters)")
    ax.set_ylabel("Y (meters)")
    ax.set_title(title)

    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        logger.info(f"Saved latency heatmap to {output_path}")
    else:
        plt.show()

    plt.close()


def plot_throughput_heatmap(
    fused_records: List[FusedRecord],
    output_path: Optional[Path] = None,
    title: str = "Total Throughput Heatmap",
    figsize: tuple = (12, 10),
    grid_size: int = 50
) -> None:
    """Plot 2D heatmap of total throughput (tx + rx bytes) across space.

    Args:
        fused_records: List of fused records
        output_path: Optional path to save figure
        title: Plot title
        figsize: Figure size
        grid_size: Number of grid cells per dimension
    """
    if not fused_records:
        logger.warning("No fused records to plot")
        return

    # Extract data
    x_values = [r.x_m for r in fused_records]
    y_values = [r.y_m for r in fused_records]
    throughput = [r.tx_bytes + r.rx_bytes for r in fused_records]

    # Create 2D histogram
    fig, ax = plt.subplots(figsize=figsize)

    # Bin the data
    x_bins = np.linspace(min(x_values), max(x_values), grid_size)
    y_bins = np.linspace(min(y_values), max(y_values), grid_size)

    # Calculate total throughput in each bin
    throughput_grid = np.zeros((grid_size - 1, grid_size - 1))

    for i in range(grid_size - 1):
        for j in range(grid_size - 1):
            mask = (
                (np.array(x_values) >= x_bins[i]) &
                (np.array(x_values) < x_bins[i + 1]) &
                (np.array(y_values) >= y_bins[j]) &
                (np.array(y_values) < y_bins[j + 1])
            )
            if np.any(mask):
                throughput_grid[j, i] = np.sum(np.array(throughput)[mask])

    # Plot heatmap
    im = ax.imshow(
        throughput_grid,
        extent=[x_bins[0], x_bins[-1], y_bins[0], y_bins[-1]],
        origin='lower',
        aspect='equal',
        cmap='Blues',
        interpolation='bilinear'
    )

    plt.colorbar(im, ax=ax, label='Total Throughput (bytes)')
    ax.set_xlabel("X (meters)")
    ax.set_ylabel("Y (meters)")
    ax.set_title(title)

    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        logger.info(f"Saved throughput heatmap to {output_path}")
    else:
        plt.show()

    plt.close()


# ============================================================================
# Time Series Plotting
# ============================================================================

def plot_latency_time_series(
    fused_records: List[FusedRecord],
    vehicle_id: Optional[str] = None,
    output_path: Optional[Path] = None,
    title: str = "Latency Over Time",
    figsize: tuple = (14, 6)
) -> None:
    """Plot latency time series for one or all vehicles.

    Args:
        fused_records: List of fused records
        vehicle_id: Optional specific vehicle ID (if None, plot all)
        output_path: Optional path to save figure
        title: Plot title
        figsize: Figure size
    """
    if not fused_records:
        logger.warning("No fused records to plot")
        return

    fig, ax = plt.subplots(figsize=figsize)

    if vehicle_id:
        # Plot single vehicle
        vehicle_records = [r for r in fused_records if r.vehicle_id == vehicle_id]
        if not vehicle_records:
            logger.warning(f"No records found for vehicle {vehicle_id}")
            return

        timestamps = [r.timestamp_utc_ms / 1000.0 for r in vehicle_records]  # Convert to seconds
        latencies = [r.avg_latency_ms if r.avg_latency_ms is not None else np.nan
                    for r in vehicle_records]

        ax.plot(timestamps, latencies, '-o', markersize=3, alpha=0.7)
        ax.set_title(f"{title} - {vehicle_id}")
    else:
        # Plot all vehicles
        vehicles = set(r.vehicle_id for r in fused_records)
        colors = sns.color_palette("husl", len(vehicles))

        for idx, vid in enumerate(sorted(vehicles)):
            vehicle_records = [r for r in fused_records if r.vehicle_id == vid]
            timestamps = [r.timestamp_utc_ms / 1000.0 for r in vehicle_records]
            latencies = [r.avg_latency_ms if r.avg_latency_ms is not None else np.nan
                        for r in vehicle_records]

            ax.plot(timestamps, latencies, '-', color=colors[idx], alpha=0.5,
                   linewidth=1, label=vid if len(vehicles) <= 10 else None)

        ax.set_title(title)
        if len(vehicles) <= 10:
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)

    ax.set_xlabel("Time (seconds since epoch)")
    ax.set_ylabel("Average Latency (ms)")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        logger.info(f"Saved latency time series to {output_path}")
    else:
        plt.show()

    plt.close()


def plot_throughput_time_series(
    fused_records: List[FusedRecord],
    vehicle_id: Optional[str] = None,
    output_path: Optional[Path] = None,
    title: str = "Throughput Over Time",
    figsize: tuple = (14, 6)
) -> None:
    """Plot throughput time series for one or all vehicles.

    Args:
        fused_records: List of fused records
        vehicle_id: Optional specific vehicle ID (if None, plot all)
        output_path: Optional path to save figure
        title: Plot title
        figsize: Figure size
    """
    if not fused_records:
        logger.warning("No fused records to plot")
        return

    fig, ax = plt.subplots(figsize=figsize)

    if vehicle_id:
        # Plot single vehicle
        vehicle_records = [r for r in fused_records if r.vehicle_id == vehicle_id]
        if not vehicle_records:
            logger.warning(f"No records found for vehicle {vehicle_id}")
            return

        timestamps = [r.timestamp_utc_ms / 1000.0 for r in vehicle_records]
        tx_bytes = [r.tx_bytes for r in vehicle_records]
        rx_bytes = [r.rx_bytes for r in vehicle_records]

        ax.plot(timestamps, tx_bytes, '-o', markersize=3, alpha=0.7, label='TX')
        ax.plot(timestamps, rx_bytes, '-s', markersize=3, alpha=0.7, label='RX')
        ax.set_title(f"{title} - {vehicle_id}")
        ax.legend()
    else:
        # Plot aggregate throughput
        df = pd.DataFrame([
            {
                'timestamp': r.timestamp_utc_ms / 1000.0,
                'tx_bytes': r.tx_bytes,
                'rx_bytes': r.rx_bytes
            }
            for r in fused_records
        ])

        # Group by time bins (1 second)
        df['time_bin'] = (df['timestamp'] // 1).astype(int)
        agg = df.groupby('time_bin').sum()

        ax.plot(agg.index, agg['tx_bytes'], '-', alpha=0.7, label='Total TX', linewidth=2)
        ax.plot(agg.index, agg['rx_bytes'], '-', alpha=0.7, label='Total RX', linewidth=2)
        ax.set_title(title)
        ax.legend()

    ax.set_xlabel("Time (seconds since epoch)")
    ax.set_ylabel("Bytes")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        logger.info(f"Saved throughput time series to {output_path}")
    else:
        plt.show()

    plt.close()


# ============================================================================
# Batch Visualization
# ============================================================================

def create_all_visualizations(
    trajectories_by_vehicle: Dict[str, List[TrajectorySample]],
    fused_records: List[FusedRecord],
    output_dir: Path
) -> None:
    """Create all standard visualizations and save to output directory.

    Args:
        trajectories_by_vehicle: Dict mapping vehicle_id to trajectory samples
        fused_records: List of fused records
        output_dir: Directory to save all plots

    Notes:
        Creates:
        - trajectory_map.png
        - latency_heatmap.png
        - throughput_heatmap.png
        - latency_time_series.png
        - throughput_time_series.png
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Creating visualizations in {output_dir}")

    # Trajectory map
    if trajectories_by_vehicle:
        plot_trajectory_map(
            trajectories_by_vehicle,
            output_path=output_dir / "trajectory_map.png",
            show_quality=True
        )

    # Heatmaps
    if fused_records:
        plot_latency_heatmap(
            fused_records,
            output_path=output_dir / "latency_heatmap.png"
        )

        plot_throughput_heatmap(
            fused_records,
            output_path=output_dir / "throughput_heatmap.png"
        )

        # Time series
        plot_latency_time_series(
            fused_records,
            output_path=output_dir / "latency_time_series.png"
        )

        plot_throughput_time_series(
            fused_records,
            output_path=output_dir / "throughput_time_series.png"
        )

    logger.info("All visualizations created successfully")
