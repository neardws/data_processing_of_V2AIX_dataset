# Task 3: Parser Module - 完成报告

## 🎉 完成日期
2025年10月16日

## ✅ 任务目标
实现数据解析模块，将原始JSON对象转换为验证过的Pydantic模型。

---

## 📦 实现内容

### 模块: `src/v2aix_pipeline/parser.py` (约550行)

#### 1. **时间戳工具** (Timestamp Utilities)

**`detect_timestamp_unit(timestamp)`**
- 自动检测时间戳单位（秒/毫秒/微秒）
- 基于数值大小的启发式算法
- 支持Unix时间戳范围 (2001-2286年)

**`normalize_timestamp(timestamp, unit)`**
- 将所有时间戳标准化为毫秒（UTC）
- 支持显式单位指定或自动检测
- 处理秒 (×1000)、毫秒 (不变)、微秒 (÷1000)

```python
# 示例
normalize_timestamp(1678901234)       # 秒 → 1678901234000
normalize_timestamp(1678901234000)    # 毫秒 → 1678901234000
normalize_timestamp(1678901234000000) # 微秒 → 1678901234000
```

#### 2. **字段提取工具** (Field Extraction Utilities)

支持多种字段命名约定的提取函数：

| 功能 | 支持的字段名 |
|------|-------------|
| `extract_vehicle_id()` | stationID, station_id, vehicleID, vehicle_id, id |
| `extract_latitude()` | latitude, lat, latitude_deg |
| `extract_longitude()` | longitude, lon, longitude_deg |
| `extract_altitude()` | altitude, alt, altitude_m |
| `extract_speed()` | speed, speed_mps, speedMps |
| `extract_heading()` | heading, heading_deg, headingDeg |
| `extract_message_type()` | messageType, message_type, msgType |
| `extract_direction()` | direction (转换为Direction枚举) |
| `extract_rsu_id()` | rsu_id, rsuID, rsuId |
| `extract_station_type()` | stationType, station_type |

**特性**:
- 自动尝试多个字段名变体
- 类型转换（字符串、浮点数、整数）
- 返回None表示字段缺失

#### 3. **GNSS记录解析器**

**`parse_gnss_record(obj, source_file, timestamp_unit)`**

解析JSON对象为`GnssRecord` Pydantic模型。

**必需字段**:
- vehicle_id (来自多个来源)
- timestamp
- latitude
- longitude

**可选字段**:
- altitude, speed, heading
- station_id, station_type
- source_file

**行为**:
- 缺少必需字段返回`None`
- 记录调试日志说明跳过原因
- 捕获并记录Pydantic验证错误

#### 4. **V2X消息解析器**

**`parse_v2x_record(obj, source_file, timestamp_unit)`**

解析JSON对象为`V2XMessageRecord` Pydantic模型。

**必需字段**:
- vehicle_id

**可选字段（但至少应有一个时间戳）**:
- timestamp, tx_timestamp, rx_timestamp
- message_type
- direction (uplink_to_rsu, downlink_from_rsu, v2v)
- rsu_id
- payload_bytes, frame_bytes
- station_id, station_type

**自动计算**:
- **latency_ms**: 如果tx和rx时间戳都存在，自动计算 `latency = rx - tx`

**行为**:
- 比GNSS解析更宽松（只需vehicle_id）
- 允许所有可选字段为None

#### 5. **批量解析**

**`parse_records(objects, source_file, timestamp_unit)`**

批量解析JSON对象列表。

**特性**:
- 自动检测记录类型
- 一个对象可以同时作为GNSS和V2X解析（如果包含两者的字段）
- 返回元组 `(gnss_records, v2x_records)`
- 跳过非字典对象
- 记录INFO级别的汇总日志

---

## 🧪 测试结果

### 单元测试覆盖

✅ **测试1**: 时间戳单位检测
- 秒: 1678901234 → 'seconds'
- 毫秒: 1678901234000 → 'milliseconds'
- 微秒: 1678901234000000 → 'microseconds'

✅ **测试2**: 时间戳标准化
- 所有格式正确转换为毫秒

✅ **测试3**: GNSS记录解析
- 所有字段正确提取
- 时间戳自动标准化
- source_file正确关联

✅ **测试4**: V2X记录解析
- 消息类型、方向、RSU ID正确
- 延迟自动计算 (20ms示例通过)
- 载荷大小正确

✅ **测试5**: 缺失字段处理
- 无坐标的GNSS → None
- 无vehicle_id的记录 → None
- 优雅降级

✅ **测试6**: 替代字段名
- lat/lon vs latitude/longitude ✓
- vehicle_id vs stationID ✓

✅ **测试7**: 延迟计算
- tx=1000, rx=1050 → latency=50.0ms ✓

✅ **测试8**: 时间戳自动检测
- 秒和毫秒时间戳统一为相同值 ✓

### 集成测试

使用 `/tmp/v2aix_test_data` 的真实测试文件：

```
Total GNSS records: 3
Total V2X records: 6

Sample GNSS record:
  Vehicle: vehicle_001
  Position: (50.7753, 6.0839)
  Timestamp: 1678901234000
  Speed: 13.89 m/s
  Source: gnss_data.json

Sample V2X record:
  Vehicle: vehicle_001
  Message type: CAM
  Direction: uplink_to_rsu
  Latency: 20.0 ms
  Payload: 256 bytes
```

✅ **所有8项单元测试通过**
✅ **集成测试通过**

---

## 🎯 功能特性

### 1. **鲁棒性**
- ✅ 多种字段命名约定
- ✅ 自动类型转换
- ✅ 优雅的错误处理
- ✅ 详细的日志记录

### 2. **灵活性**
- ✅ 可选的显式时间戳单位
- ✅ 支持不完整的记录
- ✅ 同一对象可解析为多种类型

### 3. **自动化**
- ✅ 时间戳单位自动检测
- ✅ 延迟自动计算
- ✅ 批量类型识别

### 4. **性能**
- ✅ 最小化字段访问
- ✅ 早期返回（缺失必需字段）
- ✅ 高效的字典查找

---

## 📊 代码统计

| 指标 | 数值 |
|------|------|
| 总行数 | ~550 |
| 函数数量 | 17 |
| 提取工具 | 10 |
| 解析器 | 3 (GNSS, V2X, batch) |
| 时间戳工具 | 2 |
| 文档字符串覆盖率 | 100% |
| 类型提示覆盖率 | 100% |

---

## 🔌 API 使用示例

### 基本使用

```python
from src.v2aix_pipeline import parser

# 解析单个GNSS记录
gnss_obj = {
    'stationID': 'vehicle_001',
    'latitude': 50.7753,
    'longitude': 6.0839,
    'timestamp': 1678901234
}
gnss_record = parser.parse_gnss_record(gnss_obj)
print(f"Vehicle at ({gnss_record.latitude_deg}, {gnss_record.longitude_deg})")

# 解析单个V2X记录
v2x_obj = {
    'stationID': 'vehicle_002',
    'messageType': 'CAM',
    'tx_timestamp': 1678901234100,
    'rx_timestamp': 1678901234120
}
v2x_record = parser.parse_v2x_record(v2x_obj)
print(f"Latency: {v2x_record.latency_ms}ms")

# 批量解析
objects = [gnss_obj, v2x_obj]
gnss_records, v2x_records = parser.parse_records(objects)
print(f"Parsed {len(gnss_records)} GNSS + {len(v2x_records)} V2X records")
```

### 与discovery集成

```python
from pathlib import Path
from src.v2aix_pipeline import discovery, parser

# 使用discovery迭代JSON对象
json_file = Path('/path/to/data.json')
all_gnss = []
all_v2x = []

for obj in discovery._iter_json_objects(json_file):
    gnss_recs, v2x_recs = parser.parse_records([obj], source_file=json_file)
    all_gnss.extend(gnss_recs)
    all_v2x.extend(v2x_recs)

print(f"Total: {len(all_gnss)} GNSS, {len(all_v2x)} V2X")
```

---

## 📝 设计决策

### 1. **为什么支持多种字段名？**
V2AIX数据集可能来自不同来源，使用不同的命名约定。支持多种名称提高了兼容性。

### 2. **为什么允许对象同时解析为GNSS和V2X？**
某些记录可能同时包含位置和通信数据。分别解析允许下游处理灵活处理这两种信息。

### 3. **为什么自动检测时间戳单位？**
简化用户使用。大多数情况下，数值大小可以可靠地指示单位。仍支持显式指定以处理边缘情况。

### 4. **为什么返回None而不是抛出异常？**
批量处理场景中，跳过无效记录比停止整个流程更实用。日志记录提供调试所需的可见性。

---

## 🔗 与其他模块的集成

### 输入
- **discovery.py**: 使用`_iter_json_objects()`迭代JSON数据
- **config.py**: 未来可能使用时间戳偏移配置

### 输出
- **models.py**: 生成验证过的`GnssRecord`和`V2XMessageRecord`实例
- **filters.py** (待实现): 将消费这些记录进行地理过滤
- **trajectory.py** (待实现): 将使用GNSS记录生成轨迹

---

## ⚠️ 已知限制

1. **时间戳检测假设**
   - 假设Unix时间戳（2001-2286年范围）
   - 其他纪元需要显式单位指定

2. **无数据验证**
   - 不检查坐标范围（-90≤lat≤90, -180≤lon≤180）
   - Pydantic模型应添加validators

3. **无时钟偏移处理**
   - 未实现每车辆/RSU的时钟偏移
   - 延迟计算假设时钟同步

---

## 🚀 未来增强

### 短期
- [ ] 在models.py中添加坐标范围验证
- [ ] 支持时钟偏移配置
- [ ] 添加更多字段别名

### 中期
- [ ] 性能分析和优化
- [ ] 支持自定义字段映射
- [ ] 模式检测和警告

### 长期
- [ ] 插件系统用于自定义解析器
- [ ] 数据质量评分
- [ ] 自动模式推断

---

## 📈 性能指标

基于 `/tmp/v2aix_test_data` 测试：

| 操作 | 记录数 | 时间 | 速率 |
|------|--------|------|------|
| GNSS解析 | 3 | <1ms | >3000/s |
| V2X解析 | 6 | <1ms | >6000/s |
| 批量解析 | 6 obj → 9 records | <1ms | >9000/s |

*注: 微基准测试，实际性能取决于记录复杂度和I/O*

---

## 🎓 经验教训

### 成功因素
1. **全面的字段提取器**: 避免重复代码
2. **清晰的职责分离**: 时间戳/字段/记录级别
3. **详细的文档字符串**: 加速开发和调试
4. **渐进式测试**: 每个工具独立测试，然后集成

### 技术选择
- ✅ **Optional返回**: 比异常更适合批量处理
- ✅ **日志而不是print**: 可配置的调试输出
- ✅ **类型提示**: 捕获IDE中的错误
- ✅ **Pydantic集成**: 免费的验证和序列化

---

## 📚 相关文档

- `CLAUDE.md` - 项目架构概述
- `documents/data_contracts.md` - 数据模型规范
- `src/v2aix_pipeline/models.py` - Pydantic模型定义
- `src/v2aix_pipeline/discovery.py` - JSON迭代工具

---

## ✅ 验收标准

- [x] 将JSON对象解析为GnssRecord
- [x] 将JSON对象解析为V2XMessageRecord
- [x] 时间戳标准化（秒/毫秒/微秒）
- [x] 支持多种字段命名约定
- [x] 优雅处理缺失字段
- [x] 自动延迟计算
- [x] 批量解析功能
- [x] 全面的单元测试
- [x] 与discovery模块集成测试
- [x] 100%文档覆盖
- [x] 100%类型提示

---

## 🎯 下一个任务

**Task 4**: 实现 `filters.py` - 地理区域过滤

**功能**:
- 边界框 (bbox) 过滤
- GeoJSON多边形过滤
- 集成shapely进行几何运算
- 过滤GnssRecord列表

**预计工作量**: 3-4小时
**依赖**: shapely, pyproj (已在requirements.txt中)

---

**报告生成时间**: 2025年10月16日 20:15
**作者**: Claude Code
**状态**: ✅ Task 3 完成
