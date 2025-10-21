# Vehicle ID 问题总结与解决方案

## 🔍 问题发现

您提出的问题**完全正确**！vehicle_id 都是 "unknown" 确实是处理时的问题。

## 📊 实际数据情况

经过深入分析，真实情况是：

| 数据文件 | vehicle_id 识别情况 | 实际车辆数 |
|----------|---------------------|-----------|
| **trajectories.parquet** | ❌ 100% 是 "unknown" | 0 辆可识别 |
| **v2x_messages.parquet** | ✅ 48% 有station_id<br>❌ 52% 是 "unknown" | **2,382 辆** |
| **fused_data.parquet** | ❌ 100% 是 "unknown" | 1 辆 (融合失败) |

**实际车辆数**: 数据集中有 **2,382 辆不同的车辆**，但由于处理问题，只有48%的V2X消息被正确标识。

## 🐛 根本原因

### 问题1: GPS轨迹没有车辆ID

代码 `src/v2aix_pipeline/processor.py:120` 硬编码：
```python
vehicle_id = "unknown"  # 所有GPS轨迹都是unknown
```

**原因**: GPS数据本身不包含车辆ID，处理代码没有实现ID推断逻辑。

### 问题2: 部分V2X消息无法提取station_id

代码 `processor.py:172-184` 只从 CAM/DENM 消息的 header 中提取 station_id：
```python
vehicle_id = "unknown"
header = message.get('header', {})
if isinstance(header, dict):
    station_id_obj = header.get('station_id', {})
    if isinstance(station_id_obj, dict):
        vehicle_id = str(station_id_obj.get('value', 'unknown'))
```

**结果**:
- `/v2x/cam` 和 `/v2x/denm` ✅ 能提取 (48%)
- `/v2x/raw` ❌ 无法提取 (52%)

### 问题3: 融合阶段匹配失败

`fuse_trajectory_and_v2x()` 通过 vehicle_id 匹配：
```python
matching_msgs = [
    msg for msg in v2x_by_vehicle.get(traj.vehicle_id, [])  # traj.vehicle_id = "unknown"
    ...
]
```

由于GPS轨迹的vehicle_id都是"unknown"，只能匹配到vehicle_id也是"unknown"的V2X消息，导致：
- 48%有正确station_id的消息无法匹配
- 最终显示只有1个车辆

## 💡 变通方案（使用当前数据）

已为您创建了变通脚本：`workaround_analysis.py`

```bash
python3 workaround_analysis.py
```

**关键发现**（基于有效数据）:
- **实际识别出 2,382 辆车**
- 最活跃的车辆发送了 3,660 条消息
- 识别出 32,701 个有通信活动的空间网格
- 通信高峰时段: 14:00-17:00

**新生成的数据文件**:
1. `v2x_messages_valid.parquet` - 529,069条有车辆ID的消息（推荐使用）
2. `spatial_hotspots.csv` - 32,701个通信热点区域
3. `vehicle_statistics.csv` - 2,382辆车的通信统计

## 📋 可以做的实验（当前数据）

### ✅ 可以做（不需要完整vehicle_id）

1. **V2X消息分析** - 使用 `v2x_messages_valid.parquet`
   - 2,382辆车的通信行为
   - 消息类型分布（CAM: 526k, DENM: 2.7k）
   - 时间模式分析

2. **空间热点分析** - 使用 `fused_data.parquet`
   - 通信密度分布
   - 热点区域识别
   - 地理覆盖范围

3. **时间序列分析**
   - 每小时/每日消息量
   - 通信活跃时段

4. **消息特征分析**
   - 消息大小分布
   - 发送频率

### ❌ 不能做（需要完整vehicle_id）

1. ❌ 单个车辆的完整轨迹追踪
2. ❌ 车辆间交互分析（V2V）
3. ❌ 车辆移动模式与通信关系
4. ❌ 车辆级别的时空特征提取

## 🔧 长期解决方案

详见 `VEHICLE_ID_ISSUE.md`，需要修改处理代码：

### 方案1: 从文件级别推断
- 从同一文件的V2X消息中提取最常见的station_id
- 应用到该文件的所有GPS轨迹

### 方案2: 时空匹配（推荐）
- 从CAM消息中提取位置信息
- 通过时空邻近性匹配GPS轨迹和station_id

### 方案3: 改进V2X提取
- 解析 `/v2x/raw` 消息中的station_id
- 从ETSI ITS消息的二进制数据中提取

## 📖 相关文档

| 文件 | 说明 |
|------|------|
| `VEHICLE_ID_ISSUE.md` | 详细的问题分析和解决方案 |
| `workaround_analysis.py` | 变通方案分析脚本（已运行） |
| `v2x_messages_valid.parquet` | 有效的V2X消息（推荐使用）|
| `vehicle_statistics.csv` | 2,382辆车的统计数据 |
| `spatial_hotspots.csv` | 通信热点区域 |

## 🎯 建议

### 短期（使用当前数据）

```python
import pandas as pd

# 使用有效的V2X消息
v2x = pd.read_parquet("output/processed_full/v2x_messages_valid.parquet")

# 分析某个特定车辆
vehicle_data = v2x[v2x['vehicle_id'] == '2694811063']  # 最活跃的车
print(f"该车辆发送了 {len(vehicle_data)} 条消息")

# 或分析所有车辆的统计
stats = pd.read_csv("output/processed_full/vehicle_statistics.csv")
print(stats.describe())
```

### 长期（重新处理数据）

1. 修改 `src/v2aix_pipeline/processor.py`
2. 实现车辆ID关联逻辑
3. 重新运行处理流程：
```bash
v2aix-pipeline --config config_full_dataset.yaml
```

---

**总结**: 您的观察非常敏锐！确实是处理代码的问题，不是数据本身的问题。数据集中有2,382辆车，但只有48%的数据被正确识别。使用变通方案可以进行部分实验，但完整的车辆级分析需要改进处理代码后重新处理。
