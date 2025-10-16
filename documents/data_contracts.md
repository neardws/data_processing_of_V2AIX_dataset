# Data Contracts and I/O Conventions

## Normalized Records

### GNSS record
- vehicle_id: string
- timestamp_utc_ms: int (UTC ms since epoch)
- latitude_deg: float
- longitude_deg: float
- altitude_m: float | null
- speed_mps: float | null
- heading_deg: float | null
- station_id: string | null (original)
- station_type: string | null (original)
- source_file: path | null

### V2X message record
- vehicle_id: string
- station_id: string | null
- station_type: string | null
- timestamp_utc_ms: int | null (generic event time if only one timestamp recorded)
- tx_timestamp_utc_ms: int | null
- rx_timestamp_utc_ms: int | null
- direction: {uplink_to_rsu, downlink_from_rsu, v2v} | null
- rsu_id: string | null
- message_type: string | null (CAM, DENM, ...)
- payload_bytes: int | null
- frame_bytes: int | null
- latency_ms: float | null (rx - tx when both available)
- source_file: path | null

### Derived 1 Hz trajectory sample
- vehicle_id: string
- timestamp_utc_ms: int (aligned grid)
- lat_deg, lon_deg, alt_m: floats (post-smoothing)
- x_m, y_m: floats (local planar frame)
- speed_mps: float | null
- heading_deg: float | null
- quality: {gap, extrapolated, low_speed}

### Fused record (trajectory + comms)
- vehicle_id: string
- timestamp_utc_ms: int (trajectory grid)
- x_m, y_m: float
- tx_bytes: int
- rx_bytes: int
- avg_latency_ms: float | null
- msg_counts: map<string,int>

## Coordinate System
- Source: WGS84 (EPSG:4326)
- Local: ENU around origin (lat0, lon0, h0) unless spanning large extents, then UTM.
- Origin: first point within selected region by default; configurable override.
- All smoothing and interpolation are performed in ENU, not in lat/lon.

## Time and Synchronization
- Autodetect timestamp units (s/ms/us) and normalize to ms.
- Optional per-source clock offset in config.
- Fusion tolerance: default ±500 ms around trajectory grid time.

## File Formats
- Inputs: JSON files provided by V2AIX dataset.
- Outputs: Parquet (default) or CSV.
- Metadata: `metadata.json` describing CRS, origin, parameters, and counts.

## Config Files
- Pipeline config (YAML/JSON): paths, region selection, parameters.
- Identity map JSON: maps GNSS IDs to V2X IDs when they differ.
- RSU IDs JSON: RSU identifiers and optional metadata (e.g., positions).

## Quality Flags
- gap: true when gap between raw samples > gap_threshold_s and interpolation avoided.
- extrapolated: true when outside observed window; should be rare or disabled.
- low_speed: true when speed < threshold (e.g., 0.5 m/s) making heading unreliable.

