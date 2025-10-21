#!/usr/bin/env python3
"""
变通方案：使用当前数据分析V2X通信（忽略vehicle_id问题）

由于当前数据的vehicle_id识别不完整，这个脚本展示如何
在不依赖vehicle_id的情况下进行有意义的分析。
"""

import pandas as pd
from pathlib import Path

BASE_PATH = Path("output/processed_full")

print("="*70)
print("V2X数据分析 - 变通方案（忽略vehicle_id问题）")
print("="*70)

# ============================================================================
# 方案1: 只分析有效的V2X消息（排除unknown）
# ============================================================================

print("\n[方案1] 分析有station_id的V2X消息...")

v2x = pd.read_parquet(BASE_PATH / "v2x_messages.parquet")
v2x['timestamp'] = pd.to_datetime(v2x['timestamp_ms'], unit='ms')

# 过滤出有效的车辆ID
valid_v2x = v2x[v2x['vehicle_id'] != 'unknown'].copy()

print(f"  原始V2X消息: {len(v2x):,}")
print(f"  有效消息: {len(valid_v2x):,} ({len(valid_v2x)/len(v2x)*100:.1f}%)")
print(f"  实际车辆数: {valid_v2x['vehicle_id'].nunique()}")

# 分析每个车辆的通信行为
vehicle_stats = valid_v2x.groupby('vehicle_id').agg({
    'message_size_bytes': ['count', 'sum', 'mean'],
    'timestamp_ms': ['min', 'max']
}).reset_index()

vehicle_stats.columns = ['vehicle_id', 'msg_count', 'total_bytes', 'avg_size', 'first_seen', 'last_seen']
vehicle_stats['duration_hours'] = (vehicle_stats['last_seen'] - vehicle_stats['first_seen']) / (1000 * 3600)

print(f"\n车辆通信统计（有效车辆）:")
print(vehicle_stats[['msg_count', 'total_bytes', 'duration_hours']].describe())

# Top 10活跃车辆
print(f"\n最活跃的10辆车:")
top10 = vehicle_stats.nlargest(10, 'msg_count')[['vehicle_id', 'msg_count', 'total_bytes', 'duration_hours']]
print(top10.to_string())

# ============================================================================
# 方案2: 空间聚类分析（不依赖vehicle_id）
# ============================================================================

print("\n\n[方案2] 基于位置的聚类分析（不使用vehicle_id）...")

fused = pd.read_parquet(BASE_PATH / "fused_data.parquet")
fused['timestamp'] = pd.to_datetime(fused['timestamp_ms'], unit='ms')

# 创建空间网格
grid_size = 0.001  # 约110米
fused['lat_grid'] = (fused['latitude'] / grid_size).astype(int)
fused['lon_grid'] = (fused['longitude'] / grid_size).astype(int)

# 统计每个网格的活动
grid_stats = fused.groupby(['lat_grid', 'lon_grid']).agg({
    'messages_sent': 'sum',
    'total_bytes_sent': 'sum',
    'timestamp_ms': 'count'
}).reset_index()

grid_stats.columns = ['lat_grid', 'lon_grid', 'total_messages', 'total_bytes', 'num_samples']

# 只看有通信活动的网格
active_grids = grid_stats[grid_stats['total_messages'] > 0]

print(f"  总网格数: {len(grid_stats):,}")
print(f"  有通信活动的网格: {len(active_grids):,}")
print(f"  平均每网格消息数: {active_grids['total_messages'].mean():.1f}")

# 热点区域
print(f"\n通信热点区域（Top 10）:")
hotspots = active_grids.nlargest(10, 'total_messages')
print(hotspots.to_string())

# ============================================================================
# 方案3: 时间模式分析（不依赖vehicle_id）
# ============================================================================

print("\n\n[方案3] 时间模式分析...")

v2x['hour'] = v2x['timestamp'].dt.hour
v2x['date'] = v2x['timestamp'].dt.date

# 按小时统计
hourly = v2x.groupby('hour').agg({
    'message_size_bytes': ['count', 'sum']
}).reset_index()
hourly.columns = ['hour', 'msg_count', 'total_bytes']

print(f"\n每小时消息分布:")
print(hourly.to_string())

# 按日期统计
daily = v2x.groupby('date').agg({
    'message_size_bytes': ['count', 'sum']
}).reset_index()
daily.columns = ['date', 'msg_count', 'total_bytes']

print(f"\n每日消息量:")
print(daily.head(10).to_string())

# ============================================================================
# 方案4: 消息类型分析
# ============================================================================

print("\n\n[方案4] 消息类型分析...")

msg_type_stats = v2x.groupby('message_type').agg({
    'message_size_bytes': ['count', 'mean', 'std', 'min', 'max']
}).reset_index()

print(f"\n消息类型统计:")
print(msg_type_stats.to_string())

# ============================================================================
# 方案5: 导出有效数据用于后续分析
# ============================================================================

print("\n\n[方案5] 导出有效数据...")

# 只保存有vehicle_id的数据
valid_v2x.to_parquet(BASE_PATH / "v2x_messages_valid.parquet", index=False)
print(f"  ✓ 导出有效V2X消息到: {BASE_PATH / 'v2x_messages_valid.parquet'}")
print(f"    ({len(valid_v2x):,} 条记录, {valid_v2x['vehicle_id'].nunique()} 辆车)")

# 导出活跃网格数据
active_grids.to_csv(BASE_PATH / "spatial_hotspots.csv", index=False)
print(f"  ✓ 导出空间热点数据到: {BASE_PATH / 'spatial_hotspots.csv'}")

# 导出车辆统计
vehicle_stats.to_csv(BASE_PATH / "vehicle_statistics.csv", index=False)
print(f"  ✓ 导出车辆统计到: {BASE_PATH / 'vehicle_statistics.csv'}")

print("\n" + "="*70)
print("分析完成！")
print("="*70)

print("\n💡 使用建议:")
print("  1. 使用 v2x_messages_valid.parquet 进行车辆级别的分析")
print("  2. 使用 spatial_hotspots.csv 进行空间分析")
print("  3. 使用 vehicle_statistics.csv 了解各车辆的通信行为")
print("  4. trajectories 和 fused_data 可用于整体时空分析（不区分车辆）")

print("\n⚠️  局限性:")
print("  - 无法追踪单个车辆的完整轨迹")
print("  - 无法做车辆间的交互分析（V2V）")
print("  - 建议按 VEHICLE_ID_ISSUE.md 中的方案改进处理代码后重新处理")
