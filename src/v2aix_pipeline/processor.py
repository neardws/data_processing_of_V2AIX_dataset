"""
V2AIX Dataset Processor - Extract trajectories and V2X communication metrics.

This module processes V2AIX JSON files to extract:
1. Vehicle trajectories (position, speed, heading)
2. V2X communication metrics (data volume, latency, message counts)
3. Fused trajectory-communication data
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryPoint:
    """Single trajectory point with position and kinematics."""
    timestamp_ms: int
    vehicle_id: str
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    speed_mps: Optional[float] = None
    heading_deg: Optional[float] = None
    topic: str = ""


@dataclass
class V2XMessage:
    """Single V2X message with communication metrics."""
    timestamp_ms: int
    vehicle_id: str
    message_type: str  # CAM, DENM, etc.
    message_size_bytes: int
    # Node IDs for communication link
    sender_id: Optional[str] = None  # 发送节点ID
    receiver_id: Optional[str] = None  # 接收节点ID
    # Communication metrics
    latency_ms: Optional[float] = None
    rssi_dbm: Optional[float] = None
    topic: str = ""


@dataclass
class FusedData:
    """Fused trajectory and V2X communication data."""
    timestamp_ms: int
    vehicle_id: str
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    speed_mps: Optional[float] = None
    heading_deg: Optional[float] = None
    # V2X metrics at this timestamp
    messages_sent: int = 0
    total_bytes_sent: int = 0
    avg_latency_ms: Optional[float] = None
    message_types: str = ""


def infer_vehicle_id_from_data(data: Dict[str, Any]) -> str:
    """
    从JSON数据中推断主要的车辆ID

    策略:
    - 统计所有V2X消息中的station_id
    - 如果某个ID占比>80%,认为是单车文件
    - 否则返回"unknown" (多车混合)

    Args:
        data: JSON数据字典

    Returns:
        推断的车辆ID,如果无法确定则返回"unknown"
    """
    from collections import Counter

    station_ids = []

    # 从V2X消息中收集station_id
    for topic in ['/v2x/cam', '/v2x/denm']:
        if topic not in data:
            continue

        records = data[topic]
        if not isinstance(records, list):
            continue

        for record in records:
            if not isinstance(record, dict):
                continue

            msg = record.get('message', {})
            if not isinstance(msg, dict):
                continue

            header = msg.get('header', {})
            if not isinstance(header, dict):
                continue

            station_id_obj = header.get('station_id', {})
            if isinstance(station_id_obj, dict):
                sid = station_id_obj.get('value')
                if sid:
                    station_ids.append(sid)

    if not station_ids:
        return "unknown"

    # 统计最常见的station_id
    id_counts = Counter(station_ids)
    most_common_id, most_common_count = id_counts.most_common(1)[0]

    # 如果某个ID占比>80%,认为是单车文件
    if most_common_count / len(station_ids) > 0.8:
        return str(most_common_id)

    # 多车混合,无法确定主车辆
    logger.debug(f"Multiple vehicles detected: {len(id_counts)} unique IDs")
    return "unknown"


def extract_trajectory_from_topic(data: Dict[str, Any], topic: str, vehicle_id: str = "unknown") -> List[TrajectoryPoint]:
    """Extract trajectory points from a GPS topic.

    Args:
        data: Full JSON data dict
        topic: Topic name (e.g., '/gps/cohda_mk5/fix')

    Returns:
        List of TrajectoryPoint objects
    """
    trajectories = []

    if topic not in data:
        return trajectories

    records = data[topic]
    if not isinstance(records, list):
        return trajectories

    for record in records:
        if not isinstance(record, dict):
            continue

        # Extract timestamp
        timestamp_ns = record.get('recording_timestamp_nsec')
        if timestamp_ns is None:
            continue
        timestamp_ms = int(timestamp_ns / 1_000_000)

        # Extract message content
        message = record.get('message', {})
        if not isinstance(message, dict):
            continue

        # Extract position
        lat = message.get('latitude')
        lon = message.get('longitude')
        if lat is None or lon is None:
            continue

        alt = message.get('altitude')

        # Extract speed (from header stamp or direct field)
        speed = None
        header = message.get('header', {})
        if isinstance(header, dict):
            stamp = header.get('stamp', {})
            # Note: speed might be in a different field, this is a placeholder

        # Extract heading (might be in orientation or separate field)
        heading = None

        # Use provided vehicle_id instead of hardcoded "unknown"
        # vehicle_id parameter should be inferred from V2X messages in the same file

        point = TrajectoryPoint(
            timestamp_ms=timestamp_ms,
            vehicle_id=vehicle_id,
            latitude=lat,
            longitude=lon,
            altitude=alt,
            speed_mps=speed,
            heading_deg=heading,
            topic=topic
        )
        trajectories.append(point)

    return trajectories


def extract_v2x_from_topic(data: Dict[str, Any], topic: str) -> List[V2XMessage]:
    """Extract V2X messages from a V2X topic.

    Args:
        data: Full JSON data dict
        topic: Topic name (e.g., '/v2x/cam', '/v2x/denm')

    Returns:
        List of V2XMessage objects
    """
    messages = []

    if topic not in data:
        return messages

    records = data[topic]
    if not isinstance(records, list):
        return messages

    for record in records:
        if not isinstance(record, dict):
            continue

        # Extract timestamp
        timestamp_ns = record.get('recording_timestamp_nsec')
        if timestamp_ns is None:
            continue
        timestamp_ms = int(timestamp_ns / 1_000_000)

        # Extract message content
        message = record.get('message', {})
        if not isinstance(message, dict):
            continue

        # Determine message type
        message_type = "UNKNOWN"
        if 'cam' in message:
            message_type = "CAM"
        elif 'denm' in message:
            message_type = "DENM"

        # Extract sender ID (vehicle/station ID from message header)
        sender_id = "unknown"
        vehicle_id = "unknown"
        header = message.get('header', {})
        if isinstance(header, dict):
            station_id_obj = header.get('station_id', {})
            if isinstance(station_id_obj, dict):
                sid = station_id_obj.get('value')
                if sid:
                    sender_id = str(sid)
                    vehicle_id = str(sid)

        # Extract receiver ID
        # For ROS messages, receiver might be indicated by frame_id or address
        receiver_id = None

        # Try to get receiver from ROS message header (if present)
        if isinstance(header, dict):
            # Check frame_id (might indicate RSU or receiver)
            frame_id = header.get('frame_id')
            if frame_id and isinstance(frame_id, str):
                # frame_id might be an IP address or RSU identifier
                if frame_id != sender_id and frame_id != '':
                    receiver_id = frame_id

        # Try to get receiver from v2x/raw message address field
        address = message.get('address')
        if address:
            if isinstance(address, str):
                receiver_id = address
            elif isinstance(address, dict):
                # Might have nested structure
                addr_value = address.get('value') or address.get('address')
                if addr_value:
                    receiver_id = str(addr_value)

        # Calculate message size (approximate from JSON serialization)
        message_size = len(json.dumps(message))

        # Extract latency (if available - difference between tx and rx)
        latency = None

        # Extract RSSI (if available)
        rssi = None

        msg = V2XMessage(
            timestamp_ms=timestamp_ms,
            vehicle_id=vehicle_id,
            message_type=message_type,
            message_size_bytes=message_size,
            sender_id=sender_id,
            receiver_id=receiver_id,
            latency_ms=latency,
            rssi_dbm=rssi,
            topic=topic
        )
        messages.append(msg)

    return messages


def process_json_file(json_path: Path) -> Tuple[List[TrajectoryPoint], List[V2XMessage]]:
    """Process a single JSON file to extract trajectories and V2X messages.

    Args:
        json_path: Path to JSON file

    Returns:
        Tuple of (trajectory_points, v2x_messages)
    """
    trajectories = []
    v2x_messages = []

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            logger.warning(f"Unexpected JSON structure in {json_path.name}")
            return trajectories, v2x_messages

        # Step 1: Infer vehicle ID from V2X messages in this file
        inferred_vehicle_id = infer_vehicle_id_from_data(data)
        if inferred_vehicle_id != "unknown":
            logger.debug(f"{json_path.name}: Inferred vehicle_id = {inferred_vehicle_id}")

        # Process each topic
        for topic, records in data.items():
            if not isinstance(topic, str) or not topic.startswith('/'):
                continue

            # GPS topics - use inferred vehicle_id
            if '/gps' in topic or '/gnss' in topic or '/fix' in topic:
                traj = extract_trajectory_from_topic(data, topic, inferred_vehicle_id)
                trajectories.extend(traj)
                logger.debug(f"Extracted {len(traj)} trajectory points from {topic}")

            # V2X topics
            elif '/v2x' in topic or '/cam' in topic or '/denm' in topic:
                msgs = extract_v2x_from_topic(data, topic)
                v2x_messages.extend(msgs)
                logger.debug(f"Extracted {len(msgs)} V2X messages from {topic}")

    except Exception as e:
        logger.error(f"Error processing {json_path}: {e}")

    return trajectories, v2x_messages


def fuse_trajectory_and_v2x(
    trajectories: List[TrajectoryPoint],
    v2x_messages: List[V2XMessage],
    time_window_ms: int = 1000
) -> List[FusedData]:
    """Fuse trajectory and V2X data by timestamp.

    Args:
        trajectories: List of trajectory points
        v2x_messages: List of V2X messages
        time_window_ms: Time window for fusion (default 1000ms = 1Hz)

    Returns:
        List of FusedData objects
    """
    if not trajectories:
        return []

    # Sort by timestamp
    trajectories = sorted(trajectories, key=lambda x: x.timestamp_ms)
    v2x_messages = sorted(v2x_messages, key=lambda x: x.timestamp_ms)

    # Group V2X messages by vehicle and time window
    v2x_by_vehicle = defaultdict(list)
    for msg in v2x_messages:
        v2x_by_vehicle[msg.vehicle_id].append(msg)

    fused = []

    # For each trajectory point, find matching V2X messages
    for traj in trajectories:
        # Find V2X messages in time window
        window_start = traj.timestamp_ms - time_window_ms // 2
        window_end = traj.timestamp_ms + time_window_ms // 2

        matching_msgs = [
            msg for msg in v2x_by_vehicle.get(traj.vehicle_id, [])
            if window_start <= msg.timestamp_ms <= window_end
        ]

        # Compute V2X metrics
        messages_sent = len(matching_msgs)
        total_bytes = sum(msg.message_size_bytes for msg in matching_msgs)

        latencies = [msg.latency_ms for msg in matching_msgs if msg.latency_ms is not None]
        avg_latency = np.mean(latencies) if latencies else None

        message_types = ','.join(sorted(set(msg.message_type for msg in matching_msgs)))

        fused_point = FusedData(
            timestamp_ms=traj.timestamp_ms,
            vehicle_id=traj.vehicle_id,
            latitude=traj.latitude,
            longitude=traj.longitude,
            altitude=traj.altitude,
            speed_mps=traj.speed_mps,
            heading_deg=traj.heading_deg,
            messages_sent=messages_sent,
            total_bytes_sent=total_bytes,
            avg_latency_ms=avg_latency,
            message_types=message_types
        )
        fused.append(fused_point)

    return fused


def find_scenario_files(input_dir: Path, scenario_dirs: list = None) -> list:
    """
    查找指定scenarios目录下的所有JSON文件

    Args:
        input_dir: 输入根目录
        scenario_dirs: 指定的scenarios目录列表（相对于input_dir）
                      如果为None,则查找所有scenarios目录

    Returns:
        JSON文件路径列表
    """
    json_files = []

    if scenario_dirs is None:
        # 查找所有scenarios目录
        json_files = list(input_dir.rglob("scenarios/*.json"))
    else:
        # 只查找指定的scenarios目录
        for scenario_dir in scenario_dirs:
            full_path = input_dir / scenario_dir
            if full_path.exists() and full_path.is_dir():
                files = list(full_path.glob("*.json"))
                json_files.extend(files)
                logger.info(f"Found {len(files)} files in {scenario_dir}")
            else:
                logger.warning(f"Scenario directory not found: {scenario_dir}")

    return sorted(json_files)


def process_dataset(
    input_dir: Path,
    output_dir: Path,
    output_format: str = 'parquet',
    scenario_dirs: list = None
) -> Dict[str, Any]:
    """Process entire dataset to extract trajectories and V2X metrics.

    Args:
        input_dir: Input directory with JSON files
        output_dir: Output directory for results
        output_format: Output format ('parquet' or 'csv')
        scenario_dirs: List of scenario directories to process (relative to input_dir)
                      If None, process all scenarios directories

    Returns:
        Summary statistics
    """
    input_dir = input_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find JSON files using find_scenario_files
    json_files = find_scenario_files(input_dir, scenario_dirs)
    logger.info(f"Processing {len(json_files)} JSON files from {input_dir}")

    all_trajectories = []
    all_v2x_messages = []

    # Process each file
    for i, json_path in enumerate(json_files, 1):
        if i % 100 == 0:
            logger.info(f"Processing file {i}/{len(json_files)}: {json_path.name}")

        traj, msgs = process_json_file(json_path)
        all_trajectories.extend(traj)
        all_v2x_messages.extend(msgs)

    logger.info(f"Extracted {len(all_trajectories)} trajectory points")
    logger.info(f"Extracted {len(all_v2x_messages)} V2X messages")

    # Fuse data
    logger.info("Fusing trajectory and V2X data...")
    fused_data = fuse_trajectory_and_v2x(all_trajectories, all_v2x_messages)
    logger.info(f"Created {len(fused_data)} fused data points")

    # Convert to DataFrames
    traj_df = pd.DataFrame([asdict(t) for t in all_trajectories])
    v2x_df = pd.DataFrame([asdict(m) for m in all_v2x_messages])
    fused_df = pd.DataFrame([asdict(f) for f in fused_data])

    # Save outputs
    if output_format == 'parquet':
        traj_df.to_parquet(output_dir / 'trajectories.parquet', index=False)
        v2x_df.to_parquet(output_dir / 'v2x_messages.parquet', index=False)
        fused_df.to_parquet(output_dir / 'fused_data.parquet', index=False)
    else:
        traj_df.to_csv(output_dir / 'trajectories.csv', index=False)
        v2x_df.to_csv(output_dir / 'v2x_messages.csv', index=False)
        fused_df.to_csv(output_dir / 'fused_data.csv', index=False)

    logger.info(f"Saved results to {output_dir}")

    # Compute statistics
    stats = {
        'total_files': len(json_files),
        'trajectory_points': len(all_trajectories),
        'v2x_messages': len(all_v2x_messages),
        'fused_points': len(fused_data),
        'unique_vehicles': len(set(t.vehicle_id for t in all_trajectories)),
        'total_bytes_sent': int(v2x_df['message_size_bytes'].sum()) if len(v2x_df) > 0 else 0,
        'avg_message_size': float(v2x_df['message_size_bytes'].mean()) if len(v2x_df) > 0 else 0,
    }

    return stats
