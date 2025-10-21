"""
V2AIX 处理后数据使用指南
=======================

这个脚本展示如何使用处理后的3个Parquet文件进行实验分析。

数据文件概览：
1. trajectories.parquet (5.17M 行) - 车辆轨迹数据
2. v2x_messages.parquet (1.10M 行) - V2X消息数据
3. fused_data.parquet (5.17M 行) - 融合的轨迹+通信数据
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================================
# 1. 数据加载
# ============================================================================

BASE_PATH = Path("/Users/neardws/Documents/data_processing_of_V2AIX_dataset/output/processed_full")

def load_data():
    """加载所有数据文件"""
    trajectories = pd.read_parquet(BASE_PATH / "trajectories.parquet")
    v2x_messages = pd.read_parquet(BASE_PATH / "v2x_messages.parquet")
    fused_data = pd.read_parquet(BASE_PATH / "fused_data.parquet")

    # 转换时间戳为datetime
    trajectories['timestamp'] = pd.to_datetime(trajectories['timestamp_ms'], unit='ms')
    v2x_messages['timestamp'] = pd.to_datetime(v2x_messages['timestamp_ms'], unit='ms')
    fused_data['timestamp'] = pd.to_datetime(fused_data['timestamp_ms'], unit='ms')

    return trajectories, v2x_messages, fused_data


# ============================================================================
# 2. 轨迹数据分析示例
# ============================================================================

def analyze_trajectories(df):
    """分析车辆轨迹数据"""
    print("=== 轨迹数据分析 ===\n")

    # 基本统计
    print(f"总记录数: {len(df):,}")
    print(f"车辆数量: {df['vehicle_id'].nunique()}")
    print(f"时间范围: {df['timestamp'].min()} 到 {df['timestamp'].max()}")
    print(f"持续时间: {df['timestamp'].max() - df['timestamp'].min()}")

    # 地理范围
    print(f"\n地理范围:")
    print(f"  纬度: {df['latitude'].min():.6f} - {df['latitude'].max():.6f}")
    print(f"  经度: {df['longitude'].min():.6f} - {df['longitude'].max():.6f}")
    print(f"  高度: {df['altitude'].min():.1f} - {df['altitude'].max():.1f} 米")

    # 每个车辆的轨迹点数
    points_per_vehicle = df.groupby('vehicle_id').size()
    print(f"\n每辆车的轨迹点数:")
    print(points_per_vehicle.describe())

    return df


# ============================================================================
# 3. V2X消息分析示例
# ============================================================================

def analyze_v2x_messages(df):
    """分析V2X通信数据"""
    print("\n=== V2X消息分析 ===\n")

    # 基本统计
    print(f"总消息数: {len(df):,}")
    print(f"发送消息的车辆数: {df['vehicle_id'].nunique()}")

    # 消息类型分布
    print(f"\n消息类型分布:")
    print(df['message_type'].value_counts())

    # 消息大小统计
    print(f"\n消息大小统计 (字节):")
    print(df['message_size_bytes'].describe())

    # 每个车辆的消息数
    messages_per_vehicle = df.groupby('vehicle_id').size()
    print(f"\n每辆车的消息数:")
    print(messages_per_vehicle.describe())

    # 消息发送时间分布（按小时）
    df['hour'] = df['timestamp'].dt.hour
    hourly_dist = df.groupby('hour').size()
    print(f"\n按小时的消息分布:")
    print(hourly_dist)

    return df


# ============================================================================
# 4. 融合数据分析示例（最常用）
# ============================================================================

def analyze_fused_data(df):
    """分析融合数据 - 结合了轨迹和通信"""
    print("\n=== 融合数据分析 ===\n")

    # 通信活跃的轨迹点
    active_points = df[df['messages_sent'] > 0]
    print(f"总轨迹点数: {len(df):,}")
    print(f"有通信活动的点数: {len(active_points):,} ({len(active_points)/len(df)*100:.2f}%)")

    # 通信统计
    print(f"\n通信统计:")
    print(f"  总发送消息数: {df['messages_sent'].sum():,}")
    print(f"  总发送字节数: {df['total_bytes_sent'].sum():,}")
    print(f"  平均每点发送消息数: {df['messages_sent'].mean():.2f}")

    # 按车辆分析
    vehicle_stats = df.groupby('vehicle_id').agg({
        'messages_sent': 'sum',
        'total_bytes_sent': 'sum',
        'timestamp': ['min', 'max']
    })
    vehicle_stats.columns = ['total_messages', 'total_bytes', 'first_seen', 'last_seen']
    vehicle_stats['duration'] = vehicle_stats['last_seen'] - vehicle_stats['first_seen']

    print(f"\n每辆车的通信统计:")
    print(vehicle_stats.describe())

    return df, active_points


# ============================================================================
# 5. 实验场景示例
# ============================================================================

def experiment_1_communication_coverage(fused_df):
    """实验1: 通信覆盖范围分析"""
    print("\n=== 实验1: 通信覆盖范围 ===\n")

    # 有通信的区域
    comm_active = fused_df[fused_df['messages_sent'] > 0]

    print(f"通信活跃区域:")
    print(f"  纬度范围: {comm_active['latitude'].min():.6f} - {comm_active['latitude'].max():.6f}")
    print(f"  经度范围: {comm_active['longitude'].min():.6f} - {comm_active['longitude'].max():.6f}")

    # 可以绘制热力图
    # plt.figure(figsize=(12, 8))
    # plt.scatter(comm_active['longitude'], comm_active['latitude'],
    #             c=comm_active['messages_sent'], cmap='hot', alpha=0.5)
    # plt.colorbar(label='Messages Sent')
    # plt.xlabel('Longitude')
    # plt.ylabel('Latitude')
    # plt.title('V2X Communication Heatmap')
    # plt.savefig('communication_heatmap.png', dpi=300)


def experiment_2_temporal_patterns(v2x_df):
    """实验2: 时间模式分析"""
    print("\n=== 实验2: 通信时间模式 ===\n")

    # 按小时统计
    v2x_df['hour'] = v2x_df['timestamp'].dt.hour
    hourly = v2x_df.groupby('hour').agg({
        'message_size_bytes': ['count', 'sum', 'mean']
    })

    print("每小时通信统计:")
    print(hourly)

    # 可以绘制时间序列图
    # plt.figure(figsize=(14, 6))
    # hourly['message_size_bytes']['count'].plot(kind='bar')
    # plt.xlabel('Hour of Day')
    # plt.ylabel('Number of Messages')
    # plt.title('V2X Message Distribution by Hour')
    # plt.savefig('temporal_pattern.png', dpi=300)


def experiment_3_vehicle_behavior(fused_df):
    """实验3: 车辆行为分析"""
    print("\n=== 实验3: 车辆通信行为 ===\n")

    # 分析每个车辆的行为模式
    vehicle_behavior = fused_df.groupby('vehicle_id').agg({
        'messages_sent': ['sum', 'mean', 'std'],
        'total_bytes_sent': 'sum',
        'latitude': ['min', 'max'],
        'longitude': ['min', 'max']
    })

    vehicle_behavior.columns = ['_'.join(col).strip() for col in vehicle_behavior.columns]

    # 计算移动范围
    vehicle_behavior['lat_range'] = vehicle_behavior['latitude_max'] - vehicle_behavior['latitude_min']
    vehicle_behavior['lon_range'] = vehicle_behavior['longitude_max'] - vehicle_behavior['longitude_min']

    print("车辆行为统计:")
    print(vehicle_behavior[['messages_sent_sum', 'total_bytes_sent_sum', 'lat_range', 'lon_range']].describe())

    return vehicle_behavior


def experiment_4_message_types(v2x_df):
    """实验4: 消息类型分析"""
    print("\n=== 实验4: V2X消息类型分析 ===\n")

    # 消息类型统计
    msg_type_stats = v2x_df.groupby('message_type').agg({
        'message_size_bytes': ['count', 'mean', 'std', 'min', 'max']
    })

    print("按消息类型统计:")
    print(msg_type_stats)

    # 消息类型随时间变化
    msg_type_temporal = v2x_df.groupby([v2x_df['timestamp'].dt.date, 'message_type']).size()

    return msg_type_stats


# ============================================================================
# 6. 高级分析示例
# ============================================================================

def experiment_5_spatial_temporal_join(trajectories, v2x_messages):
    """实验5: 时空关联分析"""
    print("\n=== 实验5: 轨迹与消息时空关联 ===\n")

    # 合并轨迹和消息（基于时间窗口）
    # 这里是示例逻辑，实际需要根据实验需求调整

    # 找到每条消息对应的位置
    merged = pd.merge_asof(
        v2x_messages.sort_values('timestamp_ms'),
        trajectories.sort_values('timestamp_ms'),
        on='timestamp_ms',
        by='vehicle_id',
        direction='nearest',
        tolerance=1000  # 1秒容差
    )

    print(f"成功关联的消息数: {len(merged[merged['latitude'].notna()]):,}")
    print(f"关联率: {len(merged[merged['latitude'].notna()])/len(v2x_messages)*100:.2f}%")

    return merged


def experiment_6_communication_density(fused_df, grid_size=0.001):
    """实验6: 通信密度分析（网格化）"""
    print(f"\n=== 实验6: 空间网格通信密度 (网格大小: {grid_size}度) ===\n")

    # 创建网格
    fused_df['lat_grid'] = (fused_df['latitude'] / grid_size).astype(int)
    fused_df['lon_grid'] = (fused_df['longitude'] / grid_size).astype(int)

    # 统计每个网格的通信量
    grid_stats = fused_df.groupby(['lat_grid', 'lon_grid']).agg({
        'messages_sent': 'sum',
        'vehicle_id': 'nunique'
    }).reset_index()

    grid_stats.columns = ['lat_grid', 'lon_grid', 'total_messages', 'unique_vehicles']

    print(f"网格数量: {len(grid_stats)}")
    print(f"\n网格通信统计:")
    print(grid_stats[['total_messages', 'unique_vehicles']].describe())

    # 找到热点区域
    hotspots = grid_stats.nlargest(10, 'total_messages')
    print(f"\n通信热点区域 (Top 10):")
    print(hotspots)

    return grid_stats


# ============================================================================
# 7. 主函数 - 运行所有分析
# ============================================================================

def main():
    """主函数 - 执行所有分析"""
    print("开始加载数据...\n")
    trajectories, v2x_messages, fused_data = load_data()
    print("数据加载完成！\n")

    # 基础分析
    analyze_trajectories(trajectories)
    analyze_v2x_messages(v2x_messages)
    fused_data, active_points = analyze_fused_data(fused_data)

    # 实验场景
    print("\n" + "="*60)
    print("开始实验分析")
    print("="*60)

    experiment_1_communication_coverage(fused_data)
    experiment_2_temporal_patterns(v2x_messages)
    vehicle_behavior = experiment_3_vehicle_behavior(fused_data)
    msg_type_stats = experiment_4_message_types(v2x_messages)
    # merged_data = experiment_5_spatial_temporal_join(trajectories, v2x_messages)
    grid_stats = experiment_6_communication_density(fused_data)

    print("\n" + "="*60)
    print("分析完成！")
    print("="*60)


if __name__ == "__main__":
    main()
