#!/usr/bin/env python3
"""
快速示例：加载并分析V2AIX处理后的数据
运行: python3 quick_example.py
"""

import pandas as pd
from pathlib import Path

# 数据路径
BASE_PATH = Path("output/processed_full")

print("="*60)
print("V2AIX 数据快速分析示例")
print("="*60)

# 1. 加载融合数据（推荐使用）
print("\n[1/5] 加载融合数据...")
fused = pd.read_parquet(BASE_PATH / "fused_data.parquet")
fused['timestamp'] = pd.to_datetime(fused['timestamp_ms'], unit='ms')

print(f"✓ 加载成功！共 {len(fused):,} 条记录")
print(f"  - 时间范围: {fused['timestamp'].min()} 至 {fused['timestamp'].max()}")
print(f"  - 车辆数量: {fused['vehicle_id'].nunique()}")

# 2. 基础统计
print("\n[2/5] 基础统计信息...")
print(f"  - 地理范围:")
print(f"    纬度: {fused['latitude'].min():.6f} - {fused['latitude'].max():.6f}")
print(f"    经度: {fused['longitude'].min():.6f} - {fused['longitude'].max():.6f}")
print(f"  - 通信统计:")
print(f"    总消息数: {fused['messages_sent'].sum():,}")
print(f"    总字节数: {fused['total_bytes_sent'].sum():,}")

# 3. 通信活跃度
print("\n[3/5] 通信活跃度分析...")
active = fused[fused['messages_sent'] > 0]
print(f"  - 有通信活动的记录: {len(active):,} ({len(active)/len(fused)*100:.2f}%)")
print(f"  - 平均每个活跃点发送消息数: {active['messages_sent'].mean():.2f}")

# 4. 车辆行为
print("\n[4/5] 车辆行为分析...")
vehicle_stats = fused.groupby('vehicle_id').agg({
    'timestamp_ms': ['min', 'max'],
    'messages_sent': 'sum',
    'total_bytes_sent': 'sum'
})

vehicle_stats.columns = ['first_seen_ms', 'last_seen_ms', 'total_msgs', 'total_bytes']
vehicle_stats['duration_hours'] = (vehicle_stats['last_seen_ms'] - vehicle_stats['first_seen_ms']) / (1000 * 3600)

print(f"  - 活跃时长统计（小时）:")
print(f"    平均: {vehicle_stats['duration_hours'].mean():.2f}")
print(f"    最长: {vehicle_stats['duration_hours'].max():.2f}")
print(f"  - 每车消息数统计:")
print(f"    平均: {vehicle_stats['total_msgs'].mean():.0f}")
print(f"    最多: {vehicle_stats['total_msgs'].max():.0f}")

# 5. Top车辆
print("\n[5/5] 通信最活跃的车辆 (Top 5)...")
top_vehicles = vehicle_stats.nlargest(5, 'total_msgs')[['total_msgs', 'total_bytes', 'duration_hours']]
print(top_vehicles.to_string())

# 6. 数据预览
print("\n" + "="*60)
print("数据样本 (前3条有通信活动的记录):")
print("="*60)
sample = active.head(3)[['timestamp', 'vehicle_id', 'latitude', 'longitude', 'messages_sent', 'total_bytes_sent']]
print(sample.to_string())

print("\n" + "="*60)
print("分析完成！")
print("="*60)
print("\n📖 查看详细使用指南: EXPERIMENTS_README.md")
print("🔬 运行完整分析: python3 data_usage_guide.py")
