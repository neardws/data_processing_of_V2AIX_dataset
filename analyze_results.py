#!/usr/bin/env python3
"""
Analyze processed V2AIX data and generate reports.
"""

import pandas as pd
import sys
from pathlib import Path


def analyze_data(data_dir: str):
    """Analyze processed V2AIX data."""
    data_path = Path(data_dir)

    print("=" * 80)
    print("V2AIX Data Analysis Report")
    print("=" * 80)
    print()

    # Load data
    print("Loading data files...")
    traj_df = pd.read_parquet(data_path / 'trajectories.parquet')
    v2x_df = pd.read_parquet(data_path / 'v2x_messages.parquet')
    fused_df = pd.read_parquet(data_path / 'fused_data.parquet')
    print("✓ Data loaded successfully")
    print()

    # === Trajectory Analysis ===
    print("=" * 80)
    print("TRAJECTORY ANALYSIS")
    print("=" * 80)
    print(f"Total trajectory points: {len(traj_df):,}")
    print(f"Unique vehicles: {traj_df['vehicle_id'].nunique()}")
    print(f"Time span: {(traj_df['timestamp_ms'].max() - traj_df['timestamp_ms'].min()) / 1000 / 60:.1f} minutes")
    print()

    # Show first few rows
    print("Sample trajectory data:")
    print(traj_df[['timestamp_ms', 'vehicle_id', 'latitude', 'longitude', 'topic']].head(10))
    print()

    # === V2X Communication Analysis ===
    print("=" * 80)
    print("V2X COMMUNICATION ANALYSIS")
    print("=" * 80)
    print(f"Total V2X messages: {len(v2x_df):,}")
    print(f"Unique vehicles: {v2x_df['vehicle_id'].nunique()}")
    print()

    # Message types
    print("Message types:")
    msg_types = v2x_df['message_type'].value_counts()
    for msg_type, count in msg_types.items():
        print(f"  - {msg_type}: {count:,} messages")
    print()

    # Data volume statistics
    print("Data volume statistics:")
    print(f"  - Total bytes sent: {v2x_df['message_size_bytes'].sum():,} bytes ({v2x_df['message_size_bytes'].sum() / 1024 / 1024:.2f} MB)")
    print(f"  - Average message size: {v2x_df['message_size_bytes'].mean():.1f} bytes")
    print(f"  - Min message size: {v2x_df['message_size_bytes'].min():,} bytes")
    print(f"  - Max message size: {v2x_df['message_size_bytes'].max():,} bytes")
    print()

    # Messages per vehicle
    print("Messages per vehicle:")
    msgs_per_vehicle = v2x_df.groupby('vehicle_id').size()
    print(f"  - Mean: {msgs_per_vehicle.mean():.1f} messages")
    print(f"  - Median: {msgs_per_vehicle.median():.0f} messages")
    print(f"  - Max: {msgs_per_vehicle.max():,} messages")
    print()

    # Show sample V2X data
    print("Sample V2X messages:")
    print(v2x_df[['timestamp_ms', 'vehicle_id', 'message_type', 'message_size_bytes', 'topic']].head(10))
    print()

    # === Fused Data Analysis ===
    print("=" * 80)
    print("FUSED DATA ANALYSIS (Trajectory + V2X)")
    print("=" * 80)
    print(f"Total fused data points: {len(fused_df):,}")
    print()

    # Points with V2X activity
    points_with_v2x = fused_df[fused_df['messages_sent'] > 0]
    print(f"Points with V2X activity: {len(points_with_v2x):,} ({len(points_with_v2x)/len(fused_df)*100:.1f}%)")
    print()

    # V2X activity statistics
    print("V2X activity at trajectory points:")
    print(f"  - Total messages sent: {fused_df['messages_sent'].sum():,}")
    print(f"  - Total bytes sent: {fused_df['total_bytes_sent'].sum():,} bytes")
    print(f"  - Avg messages per active point: {points_with_v2x['messages_sent'].mean():.2f}")
    print(f"  - Avg bytes per active point: {points_with_v2x['total_bytes_sent'].mean():.1f} bytes")
    print()

    # Show sample fused data
    print("Sample fused data (with V2X activity):")
    sample_fused = points_with_v2x[['timestamp_ms', 'vehicle_id', 'latitude', 'longitude',
                                     'messages_sent', 'total_bytes_sent', 'message_types']].head(10)
    print(sample_fused.to_string(index=False))
    print()

    # === Per-Vehicle Statistics ===
    print("=" * 80)
    print("PER-VEHICLE STATISTICS")
    print("=" * 80)

    vehicle_stats = fused_df.groupby('vehicle_id').agg({
        'timestamp_ms': ['count', 'min', 'max'],
        'messages_sent': 'sum',
        'total_bytes_sent': 'sum'
    })

    vehicle_stats.columns = ['_'.join(col).strip() for col in vehicle_stats.columns.values]
    vehicle_stats['duration_min'] = (vehicle_stats['timestamp_ms_max'] - vehicle_stats['timestamp_ms_min']) / 1000 / 60
    vehicle_stats['data_rate_kbps'] = (vehicle_stats['total_bytes_sent_sum'] * 8 / 1000) / (vehicle_stats['duration_min'] * 60)

    print(vehicle_stats[['timestamp_ms_count', 'duration_min', 'messages_sent_sum',
                         'total_bytes_sent_sum', 'data_rate_kbps']])
    print()

    # === Summary ===
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✓ Processed {len(traj_df):,} trajectory points from {traj_df['vehicle_id'].nunique()} vehicle(s)")
    print(f"✓ Captured {len(v2x_df):,} V2X messages")
    print(f"✓ Total data transmitted: {v2x_df['message_size_bytes'].sum() / 1024 / 1024:.2f} MB")
    print(f"✓ Fused {len(fused_df):,} trajectory-communication data points")
    print("=" * 80)
    print()

    # Save summary statistics to CSV
    summary_path = data_path / 'analysis_summary.csv'
    vehicle_stats.to_csv(summary_path)
    print(f"✓ Detailed statistics saved to: {summary_path}")
    print()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 analyze_results.py <data_directory>")
        print("Example: python3 analyze_results.py output/processed_aachen")
        sys.exit(1)

    analyze_data(sys.argv[1])
