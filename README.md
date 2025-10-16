# data_processing_of_V2AIX_dataset

## V2AIX Dataset / Citation

The *etsi_its_messages* package stack was created and used in order to record the [V2AIX Dataset](https://v2aix.ika.rwth-aachen.de). Please consider citing our paper if you are also using the package stack in your own research.

> **V2AIX: A Multi-Modal Real-World Dataset of ETSI ITS V2X Messages in Public Road Traffic**  
> *([IEEE Xplore](https://ieeexplore.ieee.org/document/10920150), [arXiv](https://arxiv.org/abs/2403.10221), [ResearchGate](https://www.researchgate.net/publication/378971373_V2AIX_A_Multi-Modal_Real-World_Dataset_of_ETSI_ITS_V2X_Messages_in_Public_Road_Traffic))*  
>
> [Guido Küppers](https://github.com/gkueppers), [Jean-Pierre Busch](https://github.com/jpbusch) and [Lennart Reiher](https://github.com/lreiher), [Lutz Eckstein](https://www.ika.rwth-aachen.de/en/institute/team/univ-prof-dr-ing-lutz-eckstein.html)  
> [Institute for Automotive Engineering (ika), RWTH Aachen University](https://www.ika.rwth-aachen.de/en/)
>
> <sup>*Abstract* – Connectivity is a main driver for the ongoing megatrend of automated mobility: future Cooperative Intelligent Transport Systems (C-ITS) will connect road vehicles, traffic signals, roadside infrastructure, and even vulnerable road users, sharing data and compute for safer, more efficient, and more comfortable mobility. In terms of communication technology for realizing such vehicle-to-everything (V2X) communication, the WLAN-based peer-to-peer approach (IEEE 802.11p, ITS-G5 in Europe) competes with C-V2X based on cellular technologies (4G and beyond). Irrespective of the underlying communication standard, common message interfaces are crucial for a common understanding between vehicles, especially from different manufacturers. Targeting this issue, the European Telecommunications Standards Institute (ETSI) has been standardizing V2X message formats such as the Cooperative Awareness Message (CAM). In this work, we present V2AIX, a multi-modal real-world dataset of ETSI ITS messages gathered in public road traffic, the first of its kind. Collected in measurement drives and with stationary infrastructure, we have recorded more than 285 000 V2X messages from more than 2380 vehicles and roadside units in public road traffic. Alongside a first analysis of the dataset, we present a way of integrating ETSI ITS V2X messages into the Robot Operating System (ROS). This enables researchers to not only thoroughly analyze real-world V2X data, but to also study and implement standardized V2X messages in ROS-based automated driving applications. The full dataset is publicly available for non-commercial use at https://v2aix.ika.rwth-aachen.de.</sup>

## Installation

```bash
# Install all dependencies
pip install -r requirements.txt

# Or install package in editable mode (recommended)
pip install -e .
```

## Quickstart

### Option 1: Command Line Arguments

Run dataset discovery on V2AIX JSON files:

```bash
# Using installed package
v2aix-pipeline --input /path/to/json_folder --output-dir /tmp/v2aix_out --region-bbox "6.0,50.0,7.0,51.0"

# Or run as Python module (without installation)
python3 -m src.v2aix_pipeline.cli --input /path/to/json_folder --output-dir /tmp/v2aix_out --region-bbox "6.0,50.0,7.0,51.0"

# With sampling for quick testing
python3 -m src.v2aix_pipeline.cli --input /path/to/json_folder --output-dir /tmp/v2aix_out --region-bbox "6.0,50.0,7.0,51.0" --sample 100
```

### Option 2: Configuration File

1. Copy and edit the example configuration:

```bash
cp documents/example_config.yaml my_config.yaml
# Edit my_config.yaml with your paths and parameters
```

2. Run with config file:

```bash
v2aix-pipeline --config my_config.yaml

# Or as Python module
python3 -m src.v2aix_pipeline.cli --config my_config.yaml
```

### Output

The discovery phase will output:
- JSON summary with dataset statistics
- Table showing record counts and unique vehicles
- List of message types found (CAM, DENM, etc.)

Example output:
```
=== V2AIX Dataset Discovery ===
{
  "total_files": 50,
  "gnss_records": 12500,
  "v2x_records": 8300,
  "vehicle_count": 150,
  "message_types": ["CAM", "DENM"]
}
```

## Project Status

**✅ COMPLETE** - All core pipeline modules implemented:

- ✅ **Data models** (Pydantic schemas for all record types)
- ✅ **Configuration management** (YAML/JSON config loading)
- ✅ **Dataset discovery** (scan JSON files, identify vehicles and message types)
- ✅ **Streaming JSON parser** (memory-efficient for large files)
- ✅ **CLI interface** with comprehensive options
- ✅ **Data parser** (convert JSON to validated Pydantic models)
  - Automatic timestamp detection and normalization (seconds/milliseconds/microseconds)
  - Multiple field naming conventions supported
  - GNSS and V2X record parsing
  - Automatic latency calculation
  - Graceful handling of missing fields
- ✅ **Geographic filtering** (filter records by region)
  - Bounding box filtering with 3 modes (intersect/contain/first)
  - GeoJSON polygon filtering
  - Coordinate validation
  - Filter summary statistics
  - Vehicle grouping utilities
- ✅ **Trajectory extraction** (1Hz normalization and quality flagging)
  - Savitzky-Golay smoothing for noise reduction
  - 1Hz resampling with linear interpolation
  - Gap detection and handling
  - Quality flags (gap, extrapolated, low_speed)
  - Per-vehicle trajectory extraction
- ✅ **Coordinate transformation** (WGS84 → ENU/UTM)
  - ENU transformation for small regions (<10 km)
  - UTM transformation with automatic zone detection
  - Multiple origin selection methods (first/centroid/median)
  - Batch transformation with shared origin
- ✅ **V2X metrics** extraction and aggregation
  - Time-window based metric aggregation
  - Message counting by type
  - Latency averaging
  - TX/RX byte totals
- ✅ **Data fusion** (combine trajectories with V2X data)
  - Time-synchronized fusion (configurable tolerance)
  - Per-vehicle and batch fusion
  - Creates FusedRecord with spatial + communication data
- ✅ **Output** (Parquet/CSV export)
  - Trajectory export to Parquet
  - Fused data export to Parquet
  - CSV export option
  - Automatic directory creation
- ✅ **Visualization** (trajectory maps, heatmaps, time series)
  - Trajectory map plotting with quality flags
  - Latency and throughput heatmaps
  - Time series plots for latency and throughput
  - Batch visualization creation

See `documents/example_config.yaml` for all available configuration options.