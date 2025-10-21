# 🎯 V2AIX数据实验快速指南

## 📦 您的数据概况

基于对 `output/processed_full/` 的分析：

| 指标 | 数值 |
|------|------|
| **总记录数** | 5,167,996 条 |
| **V2X消息总数** | 17,742,937 条 |
| **数据大小** | 245 MB (Parquet格式) |
| **时间跨度** | 2024-01-06 至 2024-02-25 (50天) |
| **车辆数量** | 1 辆（标记为unknown，可能需要ID映射） |
| **通信活跃率** | 26.67% 的轨迹点有通信活动 |
| **数据传输量** | 29.7 GB |

---

## 🚀 3步开始实验

### Step 1: 快速查看数据
```bash
python3 quick_example.py
```

### Step 2: 加载数据进行分析
```python
import pandas as pd

# 最简单的方式 - 加载融合数据
df = pd.read_parquet("output/processed_full/fused_data.parquet")
df['timestamp'] = pd.to_datetime(df['timestamp_ms'], unit='ms')

# 查看数据
print(df.head())
print(df.columns)
```

### Step 3: 开始你的实验

选择实验类型：

#### A. 空间分析（位置相关）
```python
# 通信热力图
active = df[df['messages_sent'] > 0]
import matplotlib.pyplot as plt

plt.scatter(active['longitude'], active['latitude'],
            c=active['messages_sent'], cmap='hot', alpha=0.6)
plt.colorbar(label='Messages')
plt.show()
```

#### B. 时间分析（时序相关）
```python
# 按小时统计消息量
df['hour'] = df['timestamp'].dt.hour
hourly = df.groupby('hour')['messages_sent'].sum()
hourly.plot(kind='bar')
plt.show()
```

#### C. 通信特征分析
```python
# 消息类型分布
v2x = pd.read_parquet("output/processed_full/v2x_messages.parquet")
print(v2x['message_type'].value_counts())

# 消息大小分布
print(v2x['message_size_bytes'].describe())
```

---

## 📊 推荐实验方向

### 1. 通信覆盖与密度
- **问题**: 哪些区域通信最活跃？
- **数据**: `fused_data.parquet`
- **字段**: `latitude`, `longitude`, `messages_sent`
- **方法**: 空间网格聚合、热力图可视化

### 2. 时间模式挖掘
- **问题**: 通信活动的时间规律？
- **数据**: `v2x_messages.parquet` 或 `fused_data.parquet`
- **字段**: `timestamp_ms`, `message_type`
- **方法**: 时间序列分析、周期性检测

### 3. 车辆移动与通信关系
- **问题**: 移动速度如何影响通信？
- **数据**: `fused_data.parquet`
- **字段**: `speed_mps`, `messages_sent`, `total_bytes_sent`
- **方法**: 相关性分析、速度分段统计

### 4. 消息特征分析
- **问题**: 不同消息类型的特征？
- **数据**: `v2x_messages.parquet`
- **字段**: `message_type`, `message_size_bytes`, `latency_ms`
- **方法**: 分组统计、分布分析

### 5. 网络性能评估
- **问题**: 延迟、吞吐量如何变化？
- **数据**: `v2x_messages.parquet`
- **字段**: `latency_ms`, `rssi_dbm`, `message_size_bytes`
- **方法**: 时间序列分析、性能指标计算

### 6. 空间网格分析
- **问题**: 热点区域识别？
- **数据**: `fused_data.parquet`
- **字段**: `latitude`, `longitude`, `messages_sent`
- **方法**: 网格化、聚类分析

---

## 📁 文件使用建议

### 🌟 优先使用: `fused_data.parquet`
**适用场景**（90%的实验）:
- ✅ 位置与通信关联分析
- ✅ 时空特征提取
- ✅ 热点区域识别
- ✅ 车辆行为分析
- ✅ 通信密度分析

**优势**:
- 数据已预聚合，无需额外join
- 包含完整的位置和通信信息
- 查询效率高

### 📍 特定场景: `trajectories.parquet`
**适用场景**:
- 只关注轨迹数据
- 移动模式聚类
- 路径规划研究
- 轨迹预测

### 📡 特定场景: `v2x_messages.parquet`
**适用场景**:
- 通信协议研究
- 消息内容分析
- 网络层性能评估
- 细粒度消息统计

---

## 🛠️ 常用代码片段

### 加载数据
```python
import pandas as pd

df = pd.read_parquet("output/processed_full/fused_data.parquet")
df['timestamp'] = pd.to_datetime(df['timestamp_ms'], unit='ms')
```

### 时间范围过滤
```python
# 过滤特定日期范围
mask = (df['timestamp'] >= '2024-01-10') & (df['timestamp'] <= '2024-01-20')
subset = df[mask]
```

### 地理范围过滤
```python
# 过滤特定区域（bbox）
subset = df[
    (df['latitude'] >= 50.7) & (df['latitude'] <= 50.8) &
    (df['longitude'] >= 6.0) & (df['longitude'] <= 6.2)
]
```

### 只加载特定列（节省内存）
```python
df = pd.read_parquet("output/processed_full/fused_data.parquet",
                      columns=['timestamp_ms', 'latitude', 'longitude', 'messages_sent'])
```

### 分块处理大数据
```python
for chunk in pd.read_parquet("output/processed_full/fused_data.parquet",
                               chunksize=100000):
    # 处理每个chunk
    process(chunk)
```

### 导出子集为CSV
```python
subset.to_csv("export.csv", index=False)
```

---

## 📖 完整资源

| 文件 | 说明 |
|------|------|
| `EXPERIMENTS_README.md` | 📚 详细使用指南（必读） |
| `quick_example.py` | ⚡ 快速示例（立即运行） |
| `data_usage_guide.py` | 🔬 完整分析脚本（6个实验场景） |
| `config_full_dataset.yaml` | ⚙️ 数据处理配置 |
| `output/process_full.log` | 📝 处理日志 |

---

## 💡 实用技巧

### 1. 数据质量检查
```python
# 检查缺失值
print(df.isnull().sum())

# 检查数据范围
print(df.describe())

# 检查时间连续性
df['time_diff'] = df['timestamp'].diff()
print(df['time_diff'].describe())
```

### 2. 性能优化
```python
# 使用分类数据类型节省内存
df['vehicle_id'] = df['vehicle_id'].astype('category')

# 只读取需要的行数
df = pd.read_parquet("...", nrows=1000)
```

### 3. 数据可视化
```python
import matplotlib.pyplot as plt
import seaborn as sns

# 设置样式
sns.set_style("whitegrid")

# 创建子图
fig, axes = plt.subplots(2, 2, figsize=(15, 10))
# 绘图...
```

---

## ❓ 常见问题

**Q: 为什么vehicle_id都是"unknown"？**
A: 可能需要使用ID映射文件。检查是否有 `ids_map.json` 或在配置中指定 `ids_map_path`。

**Q: 数据量太大怎么办？**
A: 使用分块读取、只加载需要的列、或先进行地理/时间范围过滤。

**Q: 如何可视化地理数据？**
A: 使用 matplotlib scatter plot，或考虑 folium/plotly 等交互式地图库。

**Q: 延迟和信号强度字段为空？**
A: 这些字段在某些数据源中可能不可用，使用前需要检查 `notna()`。

---

## 🎓 下一步

1. ✅ 运行 `python3 quick_example.py` 了解数据
2. 📖 阅读 `EXPERIMENTS_README.md` 学习详细用法
3. 🔬 选择一个实验方向开始分析
4. 📊 参考 `data_usage_guide.py` 中的函数
5. 💬 根据需要调整分析方法

---

**祝实验顺利！** 🚀

如有问题，请参考：
- V2AIX论文: https://ieeexplore.ieee.org/document/10920150
- arXiv: https://arxiv.org/abs/2403.10221
