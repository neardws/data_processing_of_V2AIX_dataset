# ⚠️ Vehicle ID 识别问题分析

## 问题现象

处理后的数据显示只有1个车辆（vehicle_id = "unknown"），但实际数据中有多个车辆。

## 根本原因

### 1. V2X消息：部分成功识别

**V2X消息实际识别出了 2,383 个不同的车辆！**

```python
v2x['vehicle_id'].value_counts():
  unknown       570,609 条 (52%)  ❌ 未识别
  2694811063      3,660 条      ✅ 正确识别
  978015530       3,014 条      ✅ 正确识别
  730032975       2,804 条      ✅ 正确识别
  ... (2380 个其他车辆)
```

### 2. GPS轨迹：完全未识别

**所有 5,167,996 条轨迹记录的 vehicle_id 都是 "unknown"！**

原因：代码 `src/v2aix_pipeline/processor.py:120`:
```python
vehicle_id = "unknown"  # 硬编码
```

GPS数据本身不包含车辆ID信息，需要通过其他方式推断。

### 3. 融合阶段：匹配失败

`fuse_trajectory_and_v2x()` 函数通过 `vehicle_id` 匹配轨迹和消息：
```python
matching_msgs = [
    msg for msg in v2x_by_vehicle.get(traj.vehicle_id, [])  # traj.vehicle_id 永远是 "unknown"
    if window_start <= msg.timestamp_ms <= window_end
]
```

**结果**：
- 只有 vehicle_id="unknown" 的V2X消息能匹配到轨迹
- 那些有真实 station_id 的消息（48%）完全被忽略
- 融合数据中只显示1个车辆

---

## 为什么V2X消息有这么多"unknown"？

检查代码 `processor.py:172-184`：

```python
# Determine message type
message_type = "UNKNOWN"
if 'cam' in message:
    message_type = "CAM"
elif 'denm' in message:
    message_type = "DENM"

# Extract vehicle/station ID
vehicle_id = "unknown"
header = message.get('header', {})
if isinstance(header, dict):
    station_id_obj = header.get('station_id', {})
    if isinstance(station_id_obj, dict):
        vehicle_id = str(station_id_obj.get('value', 'unknown'))
```

**可能原因**：
1. `/v2x/raw` topic 的消息没有标准的 header.station_id 结构
2. 只有 `/v2x/cam` 和 `/v2x/denm` 有 station_id
3. 那些 message_type="UNKNOWN" 的消息通常也是 vehicle_id="unknown"

---

## 数据集结构分析

V2AIX数据集的组织方式：
```
json/
├── Mobile/           # 移动车辆数据
│   ├── V2X-only/
│   │   └── Aachen/
│   │       └── joined.json  # 包含多个车辆的混合数据
│   └── ...
└── Stationary/       # 固定RSU数据
    └── ...
```

**关键发现**：
- 单个 `joined.json` 文件包含多个车辆的数据
- 车辆通过 V2X 消息中的 `station_id` 区分
- GPS轨迹本身不带车辆标识

---

## 解决方案

### 方案1: 从文件级别推断车辆ID（简单但不准确）

如果每个文件只包含一辆车：
```python
# 从文件中的V2X消息提取最常见的station_id
def infer_vehicle_id_from_file(data):
    station_ids = []
    for topic in ['/v2x/cam', '/v2x/denm']:
        if topic in data:
            for record in data[topic]:
                msg = record.get('message', {})
                header = msg.get('header', {})
                sid = header.get('station_id', {}).get('value')
                if sid:
                    station_ids.append(sid)

    if station_ids:
        from collections import Counter
        return str(Counter(station_ids).most_common(1)[0][0])
    return "unknown"
```

### 方案2: 时空匹配（推荐）

通过时间和位置匹配GPS轨迹和V2X消息：

1. 提取所有V2X消息的 station_id 和位置（从CAM消息）
2. 对每个GPS轨迹点，找到时空最近的V2X消息
3. 使用该消息的 station_id 作为轨迹的 vehicle_id

```python
def match_trajectory_to_vehicle(traj_point, v2x_messages, max_time_diff_ms=5000):
    """通过时空匹配找到轨迹对应的车辆ID"""
    candidates = []

    for msg in v2x_messages:
        if msg.vehicle_id == "unknown":
            continue

        time_diff = abs(msg.timestamp_ms - traj_point.timestamp_ms)
        if time_diff > max_time_diff_ms:
            continue

        # 如果V2X消息有位置信息（从CAM解析）
        if hasattr(msg, 'latitude') and hasattr(msg, 'longitude'):
            spatial_dist = haversine(
                traj_point.latitude, traj_point.longitude,
                msg.latitude, msg.longitude
            )
            if spatial_dist < 100:  # 100米内
                candidates.append((msg.vehicle_id, time_diff, spatial_dist))

    if candidates:
        # 选择时空距离最近的
        return min(candidates, key=lambda x: (x[1], x[2]))[0]

    return "unknown"
```

### 方案3: 解析V2X消息中的位置信息

CAM消息包含发送车辆的位置：
```json
{
  "cam": {
    "cam_parameters": {
      "basic_container": {
        "reference_position": {
          "latitude": {"value": 507201715},
          "longitude": {"value": 61272556}
        }
      }
    }
  }
}
```

增强 `extract_v2x_from_topic()` 函数，提取位置信息。

---

## 当前数据的实际情况

基于已处理的数据：

| 指标 | 数值 |
|------|------|
| GPS轨迹点 | 5,167,996 条 |
| 有车辆ID的轨迹点 | 0 条 (全是"unknown") |
| V2X消息总数 | 1,099,678 条 |
| 有车辆ID的消息 | 529,069 条 (48%) |
| **实际车辆数** | **2,383 辆** |
| 显示车辆数 | 1 辆 ("unknown") |

**数据利用率**：
- 只有52%的V2X消息参与了融合（那些vehicle_id="unknown"的）
- 48%的有效车辆ID信息被浪费
- 无法区分不同车辆的轨迹

---

## 建议

### 短期方案（使用当前数据）

如果要使用当前已处理的数据进行实验：
1. **使用 v2x_messages.parquet**，其中包含了2383个车辆的数据
2. 按 vehicle_id 过滤，排除 "unknown"
3. 只分析V2X通信层面，不涉及轨迹

### 长期方案（重新处理）

修改处理代码，实现方案2（时空匹配），重新处理数据。

**优先级**：
1. 🔥 修复V2X消息提取（解析/v2x/raw的station_id）
2. 🔥 实现GPS轨迹的车辆ID推断
3. ⭐ 从CAM消息提取位置信息
4. ⭐ 实现时空匹配算法

---

## 需要修改的文件

1. `src/v2aix_pipeline/processor.py`
   - `extract_trajectory_from_topic()` - 添加车辆ID推断
   - `extract_v2x_from_topic()` - 改进station_id提取，添加位置解析
   - `process_json_file()` - 实现文件级别的车辆ID关联

2. `src/v2aix_pipeline/models.py`
   - 为 `V2XMessage` 添加 latitude/longitude 字段

---

**结论**：vehicle_id 都是 "unknown" 是因为处理代码的局限性，而非原始数据问题。原始数据中确实包含2383个不同车辆的station_id信息，需要改进处理逻辑来正确提取和关联。
