# V2AIX 数据实验使用指南

## 📊 数据文件概览

处理后的数据位于：`output/processed_full/`

| 文件 | 行数 | 大小 | 说明 |
|------|------|------|------|
| **trajectories.parquet** | 5,167,996 | 123 MB | 车辆轨迹数据（1Hz重采样） |
| **v2x_messages.parquet** | 1,099,678 | 6.6 MB | V2X通信消息 |
| **fused_data.parquet** | 5,167,996 | 116 MB | **融合数据（推荐使用）** |

---

## 🚀 快速开始

### 1. 基础数据加载

```python
import pandas as pd

# 加载融合数据（最常用）
fused = pd.read_parquet("output/processed_full/fused_data.parquet")

# 转换时间戳
fused['timestamp'] = pd.to_datetime(fused['timestamp_ms'], unit='ms')

print(f"总记录数: {len(fused):,}")
print(f"车辆数: {fused['vehicle_id'].nunique()}")
print(fused.head())
```

### 2. 数据字段说明

#### trajectories.parquet（轨迹数据）
```python
- timestamp_ms: int64          # 时间戳（毫秒）
- vehicle_id: string           # 车辆ID
- latitude: float64            # 纬度（WGS84）
- longitude: float64           # 经度（WGS84）
- altitude: float64            # 海拔高度（米）
- speed_mps: float64          # 速度（米/秒，可能为空）
- heading_deg: float64        # 航向角（度，可能为空）
- topic: string               # 数据源topic
```

#### v2x_messages.parquet（V2X消息）
```python
- timestamp_ms: int64          # 时间戳（毫秒）
- vehicle_id: string           # 发送车辆ID
- message_type: string         # 消息类型（CAM/DENM/UNKNOWN）
- message_size_bytes: int64    # 消息大小（字节）
- latency_ms: float64         # 延迟（毫秒，可能为空）
- rssi_dbm: float64           # 信号强度（dBm，可能为空）
- topic: string               # 数据源topic
```

#### fused_data.parquet（融合数据，推荐）
```python
- timestamp_ms: int64          # 时间戳（毫秒）
- vehicle_id: string           # 车辆ID
- latitude: float64            # 纬度
- longitude: float64           # 经度
- altitude: float64            # 海拔高度
- speed_mps: float64          # 速度
- heading_deg: float64        # 航向角
- messages_sent: int64        # 该时刻发送的消息数
- total_bytes_sent: int64     # 该时刻发送的总字节数
- avg_latency_ms: float64     # 平均延迟
- message_types: string       # 消息类型列表（逗号分隔）
```

---

## 🧪 典型实验场景

### 场景1: 通信覆盖范围分析

```python
import pandas as pd
import matplotlib.pyplot as plt

fused = pd.read_parquet("output/processed_full/fused_data.parquet")

# 找出有通信活动的区域
active = fused[fused['messages_sent'] > 0]

# 绘制通信热力图
plt.figure(figsize=(12, 8))
plt.scatter(active['longitude'], active['latitude'],
            c=active['messages_sent'], cmap='hot', alpha=0.6, s=1)
plt.colorbar(label='Messages Sent')
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.title('V2X Communication Coverage')
plt.savefig('communication_heatmap.png', dpi=300)
plt.show()
```

### 场景2: 车辆通信行为分析

```python
# 统计每辆车的通信情况
vehicle_stats = fused.groupby('vehicle_id').agg({
    'messages_sent': 'sum',
    'total_bytes_sent': 'sum',
    'latitude': ['min', 'max'],
    'longitude': ['min', 'max']
}).reset_index()

# 计算移动范围
vehicle_stats['mobility_range'] = (
    (vehicle_stats[('latitude', 'max')] - vehicle_stats[('latitude', 'min')])**2 +
    (vehicle_stats[('longitude', 'max')] - vehicle_stats[('longitude', 'min')])**2
) ** 0.5

print(vehicle_stats.describe())
```

### 场景3: 时间模式分析

```python
v2x = pd.read_parquet("output/processed_full/v2x_messages.parquet")
v2x['timestamp'] = pd.to_datetime(v2x['timestamp_ms'], unit='ms')

# 按小时统计消息量
v2x['hour'] = v2x['timestamp'].dt.hour
hourly_msgs = v2x.groupby('hour').size()

# 绘制时间分布
hourly_msgs.plot(kind='bar', figsize=(12, 6))
plt.xlabel('Hour of Day')
plt.ylabel('Number of Messages')
plt.title('V2X Message Temporal Pattern')
plt.savefig('temporal_pattern.png', dpi=300)
plt.show()
```

### 场景4: 消息类型分析

```python
# 消息类型统计
msg_types = v2x.groupby('message_type').agg({
    'message_size_bytes': ['count', 'mean', 'std', 'min', 'max']
})

print("消息类型统计:")
print(msg_types)

# 消息类型分布饼图
v2x['message_type'].value_counts().plot(kind='pie', autopct='%1.1f%%')
plt.title('V2X Message Type Distribution')
plt.savefig('message_type_distribution.png', dpi=300)
plt.show()
```

### 场景5: 空间网格分析

```python
# 创建空间网格（0.001度约110米）
grid_size = 0.001
fused['lat_grid'] = (fused['latitude'] / grid_size).astype(int)
fused['lon_grid'] = (fused['longitude'] / grid_size).astype(int)

# 统计每个网格的通信密度
grid_density = fused.groupby(['lat_grid', 'lon_grid']).agg({
    'messages_sent': 'sum',
    'vehicle_id': 'nunique'
}).reset_index()

# 找出热点区域
hotspots = grid_density.nlargest(10, 'messages_sent')
print("通信热点区域:")
print(hotspots)
```

### 场景6: 轨迹-消息时空关联

```python
# 加载两个数据集
trajectories = pd.read_parquet("output/processed_full/trajectories.parquet")
v2x_messages = pd.read_parquet("output/processed_full/v2x_messages.parquet")

# 按时间戳和车辆ID合并（容差1秒）
merged = pd.merge_asof(
    v2x_messages.sort_values('timestamp_ms'),
    trajectories.sort_values('timestamp_ms'),
    on='timestamp_ms',
    by='vehicle_id',
    direction='nearest',
    tolerance=1000  # 1秒
)

print(f"成功关联的消息数: {len(merged[merged['latitude'].notna()]):,}")
```

---

## 📈 高级分析示例

### 完整分析脚本

运行完整的分析流程：

```bash
python3 data_usage_guide.py
```

这将执行：
- 基础数据统计
- 通信覆盖分析
- 时间模式分析
- 车辆行为分析
- 消息类型分析
- 空间密度分析

### 自定义分析

参考 `data_usage_guide.py` 中的实验函数：
- `experiment_1_communication_coverage()` - 通信覆盖
- `experiment_2_temporal_patterns()` - 时间模式
- `experiment_3_vehicle_behavior()` - 车辆行为
- `experiment_4_message_types()` - 消息类型
- `experiment_5_spatial_temporal_join()` - 时空关联
- `experiment_6_communication_density()` - 空间密度

---

## 💡 使用建议

### 推荐使用 fused_data.parquet

**原因：**
- ✅ 包含完整的轨迹信息
- ✅ 已聚合通信统计（按时间点）
- ✅ 减少了数据关联操作
- ✅ 更适合大多数分析场景

**适合场景：**
- 通信行为与位置关联分析
- 空间通信密度分析
- 车辆移动模式分析
- 时空特征提取

### 何时使用单独文件

**trajectories.parquet：**
- 只关注轨迹数据
- 不需要通信信息
- 轨迹插值/平滑
- 移动模式聚类

**v2x_messages.parquet：**
- 只分析通信层面
- 消息内容分析
- 协议层研究
- 网络性能评估

---

## 🔧 常用工具函数

```python
# 时间范围过滤
def filter_time_range(df, start_time, end_time):
    df['timestamp'] = pd.to_datetime(df['timestamp_ms'], unit='ms')
    return df[(df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)]

# 地理范围过滤
def filter_bbox(df, min_lon, min_lat, max_lon, max_lat):
    return df[
        (df['longitude'] >= min_lon) & (df['longitude'] <= max_lon) &
        (df['latitude'] >= min_lat) & (df['latitude'] <= max_lat)
    ]

# 计算两点距离（简化版）
def haversine_distance(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2
    R = 6371000  # 地球半径（米）
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c
```

---

## 📚 相关文档

- **项目配置**: `config_full_dataset.yaml`
- **处理日志**: `output/process_full.log`
- **完整使用示例**: `data_usage_guide.py`
- **数据集论文**: [V2AIX Dataset (IEEE)](https://ieeexplore.ieee.org/document/10920150)

---

## ❓ 常见问题

**Q: 数据量太大，内存不够怎么办？**
```python
# 使用chunking读取
for chunk in pd.read_parquet('fused_data.parquet', chunksize=100000):
    # 处理chunk
    process(chunk)
```

**Q: 如何只加载特定列？**
```python
df = pd.read_parquet('fused_data.parquet',
                      columns=['timestamp_ms', 'vehicle_id', 'messages_sent'])
```

**Q: 如何导出为CSV？**
```python
df.to_csv('output.csv', index=False)
```

---

**祝实验顺利！** 🎉
