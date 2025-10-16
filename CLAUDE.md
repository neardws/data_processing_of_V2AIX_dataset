# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a data processing pipeline for the V2AIX Dataset - a multi-modal real-world dataset of ETSI ITS V2X messages collected from public road traffic. The pipeline processes JSON files containing V2X messages (CAM, DENM), GNSS poses, and coordinate transformations into structured formats (Parquet or CSV).

**Citation**: V2AIX: A Multi-Modal Real-World Dataset of ETSI ITS V2X Messages in Public Road Traffic ([IEEE](https://ieeexplore.ieee.org/document/10920150), [arXiv](https://arxiv.org/abs/2403.10221))

## Key Commands

### Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Or install as package in development mode
pip install -e .
```

### Running the Pipeline
```bash
# Using the CLI entry point
v2aix-pipeline --input <json_dir> --output-dir <output_dir> [options]

# Using config file
v2aix-pipeline --config config.yaml

# Command line options
--input <path>              # Input JSON folder
--output-dir <path>         # Output directory
--region-bbox <bbox>        # Filter region: min_lon,min_lat,max_lon,max_lat
--region-polygon <geojson>  # Filter region using GeoJSON polygon
--origin <lon,lat>          # Override coordinate system origin
--hz <int>                  # Resampling frequency (default: 1)
--sync-tolerance-ms <int>   # Time sync tolerance (default: 500)
--format <format>           # Output format: parquet or csv (default: parquet)
--visualize                 # Generate visualizations
--gap-threshold-s <float>   # Gap detection threshold (default: 5.0)
--use-enu                   # Use ENU coordinate system
--sample <int>              # Limit samples during discovery phase
--workers <int>             # Number of parallel workers
```

## Architecture

### Core Components

**src/v2aix_pipeline/**

- **models.py**: Pydantic data models defining the schema for the entire pipeline
  - `GnssRecord`: Raw GNSS position data from vehicles
  - `V2XMessageRecord`: V2X message metadata (CAM, DENM) with timing and link information
  - `TrajectorySample`: Derived 1Hz trajectory with quality flags
  - `FusedRecord`: Combined trajectory + communications data
  - `Direction`: Enum for V2X link semantics (uplink_to_rsu, downlink_from_rsu, v2v)
  - `QualityFlags`: Data quality indicators (gap, extrapolated, low_speed)
  - `DatasetMetadata`: Processing provenance and parameters

- **config.py**: Configuration management using Pydantic
  - `PipelineConfig`: Main configuration model with validation
  - `load_config()`: Loads YAML/JSON config files
  - `load_identity_map()`: Vehicle ID mapping for identity resolution
  - `load_rsu_ids()`: RSU metadata and location information

- **discovery.py**: Dataset inspection and statistics gathering
  - `discover_dataset()`: Scans JSON files, counts records, extracts vehicle IDs
  - Supports both JSON arrays and JSON Lines format
  - Sampling capability for large datasets
  - Returns summary statistics as dictionary

- **cli.py**: Command-line interface
  - Argument parsing with fallback to config file
  - Orchestrates discovery phase
  - Entry point: `v2aix-pipeline` command

### Data Flow

1. **Input**: JSON files from V2AIX dataset containing:
   - GNSS poses (lat/lon/alt, speed, heading)
   - V2X messages (CAM, DENM with station IDs, timestamps)
   - Coordinate transformations

2. **Discovery Phase** (currently implemented):
   - Scans input directory recursively for JSON files
   - Identifies record types (GNSS vs V2X)
   - Counts unique vehicle IDs
   - Provides dataset statistics

3. **Processing Pipeline** (to be implemented):
   - Load and normalize records into data models
   - Filter by geographic region (bbox or polygon)
   - Transform coordinates to local ENU/UTM frame
   - Resample to target frequency (default 1Hz)
   - Apply quality flags (gaps, extrapolation)
   - Fuse trajectory and V2X data
   - Export to Parquet/CSV

### Coordinate Systems

- **Input**: WGS84 (EPSG:4326) geodetic coordinates
- **Output**: Local planar coordinates
  - ENU (East-North-Up) for small regions
  - UTM for large geographic extents
- **Origin**: First valid point in region or user-specified
- All interpolation/smoothing performed in planar coordinates, not lat/lon

### Time Synchronization

- Input timestamps auto-detected (seconds/milliseconds/microseconds)
- Normalized to milliseconds since epoch
- Configurable clock offset per data source
- Fusion tolerance: ±500ms (default) around trajectory grid time

## Configuration

Configuration can be provided via YAML/JSON file or command-line arguments:

```yaml
input_dir: /path/to/json/files
output_dir: /path/to/output
region_bbox: [min_lon, min_lat, max_lon, max_lat]  # Optional
region_polygon_path: /path/to/polygon.geojson       # Optional
origin: [lon, lat]                                  # Optional
hz: 1
sync_tolerance_ms: 500
format: parquet
visualize: false
gap_threshold_s: 5.0
use_enu: true
ids_map_path: /path/to/ids_map.json                # Optional
rsu_ids_path: /path/to/rsu_ids.json                # Optional
metadata_out: /path/to/metadata.json               # Optional
sample: 100                                         # Optional
workers: 4                                          # Optional
```

## Development Notes

- Python 3.9+ required
- Uses Pydantic v2 for data validation
- Geospatial processing: pyproj, shapely, pymap3d
- Data handling: pandas, numpy, pyarrow
- Visualization: matplotlib, seaborn

### Code Structure Principles

- All record types are defined as Pydantic models for validation
- Configuration uses Pydantic with validators for type safety
- Path handling: always expand user paths and resolve to absolute
- JSON parsing: supports both JSON arrays and JSON Lines format
- Error handling: FileNotFoundError for missing config/data files
