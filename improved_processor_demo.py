#!/usr/bin/env python3
"""
改进的V2AIX数据处理器 - 解决vehicle_id识别问题

主要改进:
1. 只处理 scenarios/*.json 文件（避免重复）
2. 从文件中的V2X消息推断车辆ID
3. 将推断的ID应用到GPS轨迹
"""

from pathlib import Path
from collections import Counter
import json
from typing import Optional, Dict, Any
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from v2aix_pipeline.processor import (
    TrajectoryPoint, V2XMessage, process_dataset,
    extract_v2x_from_topic
)


def infer_vehicle_id_from_data(data: Dict[str, Any]) -> Optional[str]:
    """
    从JSON数据中推断主要的车辆ID

    策略:
    - 统计所有V2X消息中的station_id
    - 如果某个ID占比>80%,认为是单车文件
    - 否则返回None (多车混合)

    Args:
        data: JSON数据字典

    Returns:
        推断的车辆ID,如果无法确定则返回None
    """
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
        return None

    # 统计最常见的station_id
    id_counts = Counter(station_ids)
    most_common_id, most_common_count = id_counts.most_common(1)[0]

    # 如果某个ID占比>80%,认为是单车文件
    if most_common_count / len(station_ids) > 0.8:
        return str(most_common_id)

    # 多车混合,无法确定
    return None


def extract_trajectory_with_vehicle_id(
    data: Dict[str, Any],
    topic: str,
    vehicle_id: str
) -> list:
    """
    提取GPS轨迹并使用指定的车辆ID

    Args:
        data: JSON数据
        topic: GPS topic名称
        vehicle_id: 推断或指定的车辆ID

    Returns:
        TrajectoryPoint列表
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

        # 提取时间戳
        timestamp_ns = record.get('recording_timestamp_nsec')
        if timestamp_ns is None:
            continue
        timestamp_ms = int(timestamp_ns / 1_000_000)

        # 提取消息内容
        message = record.get('message', {})
        if not isinstance(message, dict):
            continue

        # 提取位置
        lat = message.get('latitude')
        lon = message.get('longitude')
        if lat is None or lon is None:
            continue

        alt = message.get('altitude')

        # 使用推断的车辆ID
        point = TrajectoryPoint(
            timestamp_ms=timestamp_ms,
            vehicle_id=vehicle_id,  # 使用推断的ID而不是"unknown"
            latitude=lat,
            longitude=lon,
            altitude=alt,
            speed_mps=None,
            heading_deg=None,
            topic=topic
        )
        trajectories.append(point)

    return trajectories


def process_scenario_file(json_path: Path) -> tuple:
    """
    处理单个scenario文件,带车辆ID推断

    Args:
        json_path: JSON文件路径

    Returns:
        (trajectories, v2x_messages) 元组
    """
    trajectories = []
    v2x_messages = []

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            print(f"⚠️  {json_path.name}: 非预期的JSON结构")
            return trajectories, v2x_messages

        # 步骤1: 推断车辆ID
        inferred_id = infer_vehicle_id_from_data(data)

        if inferred_id:
            vehicle_id = inferred_id
            print(f"✓ {json_path.name}: 推断车辆ID = {vehicle_id}")
        else:
            vehicle_id = "unknown"
            # 检查是否有多个车辆
            station_ids = set()
            for topic in ['/v2x/cam', '/v2x/denm']:
                if topic in data:
                    for rec in data[topic]:
                        msg = rec.get('message', {})
                        if isinstance(msg, dict):
                            h = msg.get('header', {})
                            if isinstance(h, dict):
                                sid_obj = h.get('station_id', {})
                                if isinstance(sid_obj, dict):
                                    sid = sid_obj.get('value')
                                    if sid:
                                        station_ids.add(sid)

            if len(station_ids) > 1:
                print(f"⚡ {json_path.name}: 多车混合 ({len(station_ids)}辆车)")
            else:
                print(f"⚠️  {json_path.name}: 无法推断车辆ID")

        # 步骤2: 处理GPS轨迹（使用推断的ID）
        for topic in ['/gps/cohda_mk5/fix', '/gnss', '/fix']:
            if topic in data:
                traj = extract_trajectory_with_vehicle_id(data, topic, vehicle_id)
                trajectories.extend(traj)

        # 步骤3: 处理V2X消息（使用原有逻辑）
        for topic in ['/v2x/cam', '/v2x/denm', '/v2x/raw']:
            if topic in data:
                msgs = extract_v2x_from_topic(data, topic)
                v2x_messages.extend(msgs)

    except Exception as e:
        print(f"❌ {json_path.name}: 错误 - {e}")

    return trajectories, v2x_messages


def find_scenario_files(input_dir: Path) -> list:
    """
    只查找scenarios目录下的JSON文件

    Args:
        input_dir: 输入根目录

    Returns:
        scenario文件路径列表
    """
    scenario_files = list(input_dir.rglob("scenarios/*.json"))
    return sorted(scenario_files)


def main():
    """主函数"""
    print("="*70)
    print("改进的V2AIX数据处理器")
    print("="*70)
    print("\n改进点:")
    print("  1. 只处理 scenarios/*.json 文件")
    print("  2. 从V2X消息推断车辆ID")
    print("  3. 将ID应用到GPS轨迹")
    print()

    # 配置
    input_dir = Path("/Users/neardws/Documents/data_processing_of_V2AIX_dataset/json")
    output_dir = Path("/Users/neardws/Documents/data_processing_of_V2AIX_dataset/output/processed_scenarios")

    # 查找文件
    scenario_files = find_scenario_files(input_dir)

    print(f"找到 {len(scenario_files)} 个scenario文件")
    print(f"输出目录: {output_dir}")
    print()

    response = input("是否继续处理? (y/n): ")
    if response.lower() != 'y':
        print("取消处理")
        return

    # 这里可以调用改进后的处理流程
    # 为了演示,只处理前10个文件
    print("\n开始处理 (演示模式: 前10个文件)...")
    print("-"*70)

    all_trajectories = []
    all_v2x_messages = []

    for i, json_file in enumerate(scenario_files[:10], 1):
        print(f"\n[{i}/10] ", end="")
        traj, msgs = process_scenario_file(json_file)
        all_trajectories.extend(traj)
        all_v2x_messages.extend(msgs)

    print("\n" + "="*70)
    print("处理完成 (演示)")
    print("="*70)
    print(f"总轨迹点数: {len(all_trajectories)}")
    print(f"总V2X消息: {len(all_v2x_messages)}")

    # 统计有ID的轨迹
    with_id = [t for t in all_trajectories if t.vehicle_id != "unknown"]
    print(f"有车辆ID的轨迹: {len(with_id)} ({len(with_id)/len(all_trajectories)*100:.1f}%)")

    # 统计车辆数
    vehicle_ids = set(t.vehicle_id for t in all_trajectories)
    print(f"识别出的车辆数: {len(vehicle_ids)}")
    print(f"车辆ID列表: {sorted(vehicle_ids)}")


if __name__ == "__main__":
    main()
