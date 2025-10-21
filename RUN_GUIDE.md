# V2AIX数据处理 - 改进版运行指南

## 🎯 改进内容

1. ✅ **车辆轨迹通过车辆ID唯一标识** - 从V2X消息推断station_id
2. ✅ **V2X信息包含发送/接收节点ID** - sender_id和receiver_id
3. ✅ **记录传输量和传输时延** - message_size_bytes和latency_ms
4. ✅ **只处理指定的scenarios目录** - 避免重复和多车混合

---

## 🚀 快速开始

### 1. 验证环境

```bash
# 确保已安装依赖
pip install -r requirements.txt

# 或者
pip install -e .
```

### 2. 检查配置文件

配置文件位于: `config_scenarios_only.yaml`

```yaml
input_dir: /Users/neardws/Documents/data_processing_of_V2AIX_dataset/json
output_dir: /Users/neardws/Documents/data_processing_of_V2AIX_dataset/output/processed_scenarios

scenario_dirs:
  - Mobile/V2X-only/Aachen/scenarios
  - Mobile/V2X-only/Highway/scenarios
  - Mobile/V2X-only/Rural/scenarios
  - Stationary/V2X-only/Aachen-Heinrichsallee/scenarios
  - Stationary/V2X-only/Aachen-Monheimsallee/scenarios
  - Stationary/V2X-only/Aachen-Ponttor/scenarios
  - Stationary/V2X-only/Aachen-Theaterstrasse/scenarios
```

### 3. 运行处理

#### 方法A: 使用测试脚本（推荐第一次测试）

```bash
python3 test_improved_processor.py
```

#### 方法B: 使用CLI

```bash
v2aix-pipeline --config config_scenarios_only.yaml
```

#### 方法C: Python代码

```python
from pathlib import Path
from v2aix_pipeline.config import load_config
from v2aix_pipeline.processor import process_dataset

# 加载配置
cfg = load_config(Path("config_scenarios_only.yaml"))

# 处理数据
stats = process_dataset(
    input_dir=cfg.input_dir,
    output_dir=cfg.output_dir,
    output_format=cfg.format,
    scenario_dirs=cfg.scenario_dirs
)

print(f"识别车辆数: {stats['unique_vehicles']}")
```

---

## 📊 预期输出

### 文件结构

```
output/processed_scenarios/
├── trajectories.parquet      # 车辆轨迹（带vehicle_id）
├── v2x_messages.parquet       # V2X消息（带sender_id/receiver_id）
├── fused_data.parquet         # 融合数据
└── metadata.json              # 处理元数据
```

### 数据字段

#### trajectories.parquet
- `vehicle_id` ⭐ 车辆ID（推断自V2X消息）
- `timestamp_ms`
- `latitude`, `longitude`, `altitude`
- `speed_mps`, `heading_deg`

#### v2x_messages.parquet
- `sender_id` ⭐ 发送节点ID
- `receiver_id` ⭐ 接收节点ID
- `message_size_bytes` ⭐ 传输量
- `latency_ms` ⭐ 传输时延
- `timestamp_ms`
- `vehicle_id`, `message_type`

---

## 📈 预期改进效果

| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| 处理文件数 | 2,227 | ~1,819 |
| GPS轨迹有vehicle_id | 0% | **~83%** |
| V2X消息有sender_id | 48% | **~90%** |
| V2X消息有receiver_id | 0% | **~30%** |
| 车辆可唯一标识 | ❌ | ✅ |
| 通信链路可追踪 | ❌ | ✅ |

---

## 💡 数据使用示例

### 示例1: 查看车辆轨迹

```python
import pandas as pd

traj = pd.read_parquet("output/processed_scenarios/trajectories.parquet")

# 按车辆分组
for vehicle_id in traj['vehicle_id'].unique():
    if vehicle_id == "unknown":
        continue

    vehicle_traj = traj[traj['vehicle_id'] == vehicle_id]
    print(f"车辆 {vehicle_id}:")
    print(f"  轨迹点数: {len(vehicle_traj)}")
    print(f"  时间跨度: {vehicle_traj['timestamp_ms'].max() - vehicle_traj['timestamp_ms'].min()} ms")
```

### 示例2: 分析通信链路

```python
v2x = pd.read_parquet("output/processed_scenarios/v2x_messages.parquet")

# 通信链路统计
links = v2x.groupby(['sender_id', 'receiver_id']).agg({
    'message_size_bytes': ['count', 'sum'],
    'latency_ms': 'mean'
}).reset_index()

print("通信链路:")
print(links)
```

### 示例3: 车辆通信行为

```python
fused = pd.read_parquet("output/processed_scenarios/fused_data.parquet")

# 每个车辆的通信统计
comm_stats = fused.groupby('vehicle_id').agg({
    'messages_sent': 'sum',
    'total_bytes_sent': 'sum'
})

print("车辆通信统计:")
print(comm_stats)
```

---

## ⚠️ 注意事项

1. **处理时间**: 根据文件数量，可能需要几分钟到几十分钟
2. **内存需求**: 建议至少8GB可用内存
3. **Unknown车辆**: 约17%的文件可能无法推断vehicle_id（多车混合）
4. **Receiver ID**: 可能为None（取决于数据中是否有接收方标识）

---

## 🔧 故障排除

### 问题1: ModuleNotFoundError

```bash
# 安装项目依赖
pip install -r requirements.txt
```

### 问题2: 配置文件路径错误

检查`config_scenarios_only.yaml`中的路径是否正确：
```bash
ls /Users/neardws/Documents/data_processing_of_V2AIX_dataset/json
```

### 问题3: 处理速度慢

可以先测试处理少量文件：
```yaml
# 修改配置，只处理一个scenarios目录
scenario_dirs:
  - Mobile/V2X-only/Aachen/scenarios  # 只有5个文件
```

---

## 📞 获取帮助

查看详细改进说明：
- `IMPROVEMENTS_SUMMARY.md` - 完整改进总结
- `FILE_STRUCTURE_ANALYSIS.md` - 数据集结构分析
- `SOLUTION_COMPLETE.md` - 完整解决方案

---

## ✅ 检查清单

处理前请确认：

- [ ] Python 3.9+ 已安装
- [ ] 依赖包已安装 (`pip install -r requirements.txt`)
- [ ] 配置文件路径正确
- [ ] JSON数据目录存在
- [ ] 输出目录有写权限

处理完成后验证：

- [ ] 输出目录包含3个parquet文件
- [ ] trajectories.parquet 有 vehicle_id 字段
- [ ] v2x_messages.parquet 有 sender_id 和 receiver_id 字段
- [ ] 统计信息中 unique_vehicles > 1

---

**准备就绪！运行 `python3 test_improved_processor.py` 开始处理。** 🚀
