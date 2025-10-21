# 数据集文件组织结构分析报告

## 🎯 核心发现

您的观察**完全正确**！V2AIX 数据集的组织结构如下：

### 文件层次结构

```
json/
├── Mobile/
│   ├── V2X-only/
│   │   ├── Aachen/
│   │   │   ├── joined.json          ← 包含多个车辆/场景的合并文件
│   │   │   └── scenarios/           ← 按单车单次行程分割
│   │   │       ├── 2024-01-21T18-06-39Z.json  (1辆车: 1421989417)
│   │   │       ├── 2024-02-21T12-56-15Z.json  (1辆车: 1052926332)
│   │   │       └── ...
│   │   ├── Highway/scenarios/       (329个文件)
│   │   └── Rural/scenarios/         (2个文件)
│   └── V2X-with-Sensor-Context/
│       └── ...
└── Stationary/
    ├── V2X-only/
    │   ├── Aachen-Ponttor/scenarios/     (720个文件)
    │   ├── Aachen-Theaterstrasse/scenarios/ (529个文件)
    │   └── ...
    └── V2X-with-Sensor-Context/
        └── A44-Jackerath/scenarios/      (315个文件)

总计:
  - 13 个 joined.json 文件
  - 2,214 个 scenarios/*.json 文件
  - 合计 2,227 个文件 ✓ (与日志一致)
```

---

## 📊 数据关系验证

### 示例：Aachen 区域

| 项目 | joined.json | scenarios 合计 | 关系 |
|------|-------------|----------------|------|
| GPS记录 | 18,520 | 2,459 | joined ⊃ scenarios |
| V2X消息 | 844 | 844 | ✓ 完全匹配 |
| 车辆数 | 5辆 | 5辆 | ✓ 一致 |

**结论**：
- `joined.json` 包含**完整的原始采集数据**
- `scenarios/` 是从joined.json中**提取的特定场景**
- scenarios 可能不包含所有时间段的数据（特别是GPS）

---

## 🎲 抽样统计结果

随机抽取30个 scenario 文件分析：

| 车辆数 | 文件数 | 占比 | 说明 |
|--------|--------|------|------|
| **1辆车** | **25** | **83.3%** | ✓ 大多数 |
| 0辆车 | 1 | 3.3% | 无V2X消息 |
| 3-5辆车 | 4 | 13.3% | 多车同时出现 |

**分布特征**：
- ✅ **Mobile** scenarios: 基本都是1辆车（单次行程）
- ⚠️ **Stationary** scenarios: 偶尔多辆车（RSU观测到路过的多辆车）

---

## 🔍 当前处理流程的问题

### 问题1: 同时处理两种文件

```python
json_files = list(input_dir.rglob("*.json"))  # 找到所有JSON
# 结果: 2,227 = 13 (joined) + 2,214 (scenarios)
```

**影响**：
- 同一条数据可能被处理两次（重复）
- joined.json 中的GPS轨迹无法区分车辆（多车混合）
- scenarios 中的GPS轨迹理论上更容易关联到车辆

### 问题2: GPS轨迹缺少车辆ID

当前代码 (processor.py:120):
```python
vehicle_id = "unknown"  # 硬编码
```

**改进方案**（针对scenarios文件）：
```python
# 从文件中V2X消息的主要station_id推断车辆ID
def infer_vehicle_id_from_file(data):
    station_ids = []

    for topic in ['/v2x/cam', '/v2x/denm']:
        if topic not in data:
            continue
        for record in data[topic]:
            msg = record.get('message', {})
            header = msg.get('header', {})
            station_id_obj = header.get('station_id', {})
            if isinstance(station_id_obj, dict):
                sid = station_id_obj.get('value')
                if sid:
                    station_ids.append(sid)

    if not station_ids:
        return "unknown"

    # 返回最常见的station_id（占比>80%则认为是单车文件）
    from collections import Counter
    counts = Counter(station_ids)
    most_common_id, most_common_count = counts.most_common(1)[0]

    if most_common_count / len(station_ids) > 0.8:
        return str(most_common_id)

    return "unknown"  # 多车混合，无法确定
```

---

## 💡 推荐处理策略

### 方案A: 只处理 scenarios 文件（推荐）

```python
# 修改 processor.py 的文件查找逻辑
def find_json_files(input_dir: Path, prefer_scenarios: bool = True):
    if prefer_scenarios:
        # 只处理 scenarios 目录下的文件
        scenario_files = list(input_dir.rglob("scenarios/*.json"))
        return scenario_files
    else:
        # 排除 scenarios，只处理 joined.json
        all_files = list(input_dir.rglob("*.json"))
        return [f for f in all_files if "scenarios" not in f.parts]
```

**优点**：
- ✅ 83%的文件是单车，可以直接推断vehicle_id
- ✅ 避免数据重复处理
- ✅ 文件已经预分割，便于并行处理
- ✅ 更好的车辆级别分析

**缺点**：
- ⚠️ 可能丢失一些不属于特定场景的GPS数据
- ⚠️ 仍有17%的文件包含多辆车（主要是Stationary）

---

### 方案B: 智能混合策略

```python
def find_json_files_smart(input_dir: Path):
    files = []

    for subdir in input_dir.rglob("*"):
        if not subdir.is_dir():
            continue

        # Mobile: 优先 scenarios
        if "Mobile" in subdir.parts:
            scenarios_dir = subdir / "scenarios"
            if scenarios_dir.exists():
                files.extend(scenarios_dir.glob("*.json"))
            else:
                # 如果没有scenarios，使用joined.json
                joined = subdir / "joined.json"
                if joined.exists():
                    files.append(joined)

        # Stationary: 使用 joined.json（RSU观测多车）
        elif "Stationary" in subdir.parts:
            joined = subdir / "joined.json"
            if joined.exists():
                files.append(joined)

    return files
```

---

### 方案C: 完整数据处理

如果需要**所有原始数据**：

```python
def find_json_files_complete(input_dir: Path):
    # 只处理 joined.json，不处理 scenarios
    joined_files = list(input_dir.rglob("joined.json"))
    return joined_files
```

**优点**：包含完整数据
**缺点**：需要更复杂的车辆ID推断（时空匹配）

---

## 🛠️ 代码改进建议

### 1. 添加文件选择配置

在 `config.yaml` 中添加：
```yaml
file_selection:
  mode: "scenarios"  # 可选: "scenarios", "joined", "smart", "all"
  mobile_strategy: "scenarios"
  stationary_strategy: "joined"
```

### 2. 改进车辆ID推断

修改 `extract_trajectory_from_topic()`:
```python
def extract_trajectory_from_topic(
    data: Dict[str, Any],
    topic: str,
    inferred_vehicle_id: str = None  # 新增参数
) -> List[TrajectoryPoint]:
    ...
    # 使用推断的车辆ID
    vehicle_id = inferred_vehicle_id if inferred_vehicle_id else "unknown"
    ...
```

### 3. 文件级别的车辆ID推断

修改 `process_json_file()`:
```python
def process_json_file(json_path: Path) -> Tuple[List[TrajectoryPoint], List[V2XMessage]]:
    ...
    # 首先从V2X消息推断主要车辆ID
    inferred_vehicle_id = infer_vehicle_id_from_file(data)

    # 处理GPS轨迹时使用推断的ID
    for topic in ['/gps/cohda_mk5/fix', '/gnss', ...]:
        traj = extract_trajectory_from_topic(data, topic, inferred_vehicle_id)
        trajectories.extend(traj)
    ...
```

---

## 📈 预期改进效果

| 指标 | 当前 | 改进后 (方案A) |
|------|------|----------------|
| 处理文件数 | 2,227 | 2,214 |
| GPS轨迹有ID | 0% | ~83% |
| V2X消息有ID | 48% | ~90% |
| 可识别车辆数 | 2,382 | ~2,500+ |
| 融合数据质量 | 低（只匹配unknown） | 高（大部分能正确匹配） |

---

## 🎯 实施步骤

### 快速改进（推荐）

1. **修改文件查找逻辑**
   ```bash
   # 编辑 src/v2aix_pipeline/processor.py
   # 将 input_dir.rglob("*.json")
   # 改为 input_dir.rglob("scenarios/*.json")
   ```

2. **添加车辆ID推断**
   ```python
   # 在 process_json_file() 开头添加
   inferred_vehicle_id = infer_vehicle_id_from_file(data)
   ```

3. **传递车辆ID到GPS处理**
   ```python
   # 修改 extract_trajectory_from_topic() 使用推断的ID
   ```

4. **重新处理数据**
   ```bash
   v2aix-pipeline --config config_full_dataset.yaml
   ```

### 完整改进

参考 `VEHICLE_ID_ISSUE.md` 中的方案2（时空匹配）

---

## 📋 总结

| 问题 | 验证结果 |
|------|----------|
| scenarios文件对应单独车辆？ | ✅ 是的（83%） |
| 应该只处理scenarios？ | ✅ 推荐 |
| joined.json包含更多数据？ | ✅ 是的 |
| 当前处理有重复？ | ✅ 存在潜在重复 |

**您的判断完全正确！** 🎯

处理 scenarios 文件而不是 joined.json 可以显著改善车辆ID识别，这是解决当前vehicle_id问题的最直接和有效的方法。
