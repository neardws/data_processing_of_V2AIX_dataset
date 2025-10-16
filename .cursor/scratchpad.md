## Background and Motivation
The goal is to build a reproducible data processing pipeline for the V2AIX Dataset that extracts, filters, and analyzes vehicle trajectories and their corresponding V2X communication metrics. This enables spatial-temporal analysis of vehicle movement with synchronized communication performance, supporting research on connectivity and mobility.

## Key Challenges and Analysis
- Data heterogeneity: JSON messages may contain different schemas for GNSS and V2X events; robust parsing is required.
- Time alignment: Synchronizing GNSS trajectories with V2X transmission timestamps requires careful handling of time bases and possible clock drift.
- Irregular sampling: GNSS updates and messages may be irregular; interpolation to a 1 Hz trajectory must be accurate and traceable.
- Coordinate transforms: Convert geodetic (lat, lon, alt) to a local planar frame reliably; choose EPSG and origin consistently.
- Vehicle identification: Consistent vehicle IDs across GNSS and V2X logs; handle missing/ambiguous IDs.
- Performance: Efficient processing for potentially large JSON folders.
- Validation: Define objective success checks and test cases before implementation (TDD).

## High-level Task Breakdown
1. Define data contracts and I/O conventions
   - Success: Document JSON schemas (fields used), timestamp units (ms/us/s), ID fields, folder structure, and outputs (CSV/Parquet), plus coordinate reference (EPSG, origin definition).
2. Implement dataset discovery and config loader
   - Success: CLI accepts input folder path and outputs discovery summary (counts of vehicles, GNSS points, message counts). Config file (YAML/JSON) read successfully.
3. Parser: GNSS and V2X messages → normalized in-memory model
   - Success: Unit tests load sample files and produce normalized records with expected fields and types; graceful handling of missing fields.
4. Vehicle filtering by geographic region
   - Success: Given polygon or bounding box, vehicles whose trajectories intersect the region are listed; test with synthetic data.
5. Trajectory extraction and 1 Hz normalization
   - Success: For selected vehicles, produce time-indexed 1 Hz trajectories via smoothing + interpolation; tests verify continuity, bounds, and sample count.
6. Coordinate mapping to local planar frame
   - Success: Lat/Lon mapped to (x, y) in meters using chosen EPSG and origin at first region GNSS point; tests verify known conversions.
7. V2X metrics extraction per vehicle and timestamp
   - Success: Extract per-event data volume (bytes) and latency (ms), aggregate by vehicle and timestamp; tests verify aggregation and units.
8. Data fusion on timestamp
   - Success: Join per-vehicle 1 Hz trajectory with communication metrics using time sync (nearest neighbor or exact match tolerance); tests confirm alignment quality.
9. Outputs and visualization
   - Success: Write normalized trajectories and fused metrics to Parquet/CSV; generate sample trajectory plots and heatmaps; CLI prints summary.
10. Performance and robustness pass
   - Success: Run on a representative subset quickly; handles malformed files with warnings not crashes.

## Project Status Board
- [ ] Define data contracts and I/O conventions
- [ ] Implement dataset discovery and config loader
- [ ] Parser: GNSS and V2X messages → normalized model
- [ ] Vehicle filtering by geographic region
- [ ] Trajectory extraction and 1 Hz normalization
- [ ] Coordinate mapping to local planar frame
- [ ] V2X metrics extraction per vehicle and timestamp
- [ ] Data fusion on timestamp
- [ ] Outputs and visualization
- [ ] Performance and robustness pass

## Current Status / Progress Tracking
- Planner initialized the high-level plan and success criteria.

## Executor's Feedback or Assistance Requests
- None yet. Executor will request sample file names and field examples if schemas differ from assumptions.

## Test Strategy (TDD)
- Unit tests per module using small synthetic fixtures.
- Golden-tests: expected CSV/Parquet outputs from tiny sample data.
- Property tests for interpolation monotonicity and time alignment tolerance.

## Assumptions
- Input JSON folder contains GNSS trajectories and V2X message logs with consistent vehicle IDs and timestamps in UTC.
- Coordinate system will use WGS84 (EPSG:4326) → local metric frame via pyproj (e.g., UTM or custom ENU with first point as origin).

## Risks and Mitigations
- Clock offsets: add configuration for allowed sync tolerance and optional offset estimation.
- Large files: stream parse and chunked processing; optional Parquet intermediate outputs.
- Missing data: robust interpolation with gaps flagged when exceeding threshold.

## Lessons
- Record any deviations from assumptions (e.g., timestamp units) as discovered during execution.

## Proposed Data Contracts (Initial)
- GNSS record (normalized):
  - vehicle_id: string
  - timestamp_utc_ms: int (UTC milliseconds since epoch)
  - latitude_deg: float
  - longitude_deg: float
  - altitude_m: float | null
  - speed_mps: float | null
  - heading_deg: float | null

- V2X message record (normalized):
  - vehicle_id: string
  - timestamp_utc_ms: int (event time; if tx/rx both exist, store both)
  - direction: enum { uplink_to_rsu, downlink_from_rsu, v2v }
  - rsu_id: string | null
  - message_type: string (e.g., CAM, DENM, MAPEM, SPATEM, etc.)
  - payload_bytes: int (application payload size)
  - frame_bytes: int | null (if available)
  - tx_timestamp_utc_ms: int | null
  - rx_timestamp_utc_ms: int | null
  - latency_ms: float | null (rx - tx when both available)

- Derived 1 Hz trajectory sample:
  - vehicle_id: string
  - timestamp_utc_ms: int (aligned to 1 Hz grid)
  - lat_deg, lon_deg, alt_m: floats (post-smoothing)
  - x_m, y_m: floats (local planar frame)
  - speed_mps: float | null
  - heading_deg: float | null

- Fused record:
  - vehicle_id: string
  - timestamp_utc_ms: int (trajectory grid time)
  - x_m, y_m: float
  - tx_bytes: int (sum in [t-0.5s, t+0.5s])
  - rx_bytes: int (sum in [t-0.5s, t+0.5s])
  - avg_latency_ms: float | null (mean over events in the window)
  - msg_counts: dict {type -> count} | simplified columns per major types

## Coordinate System Decision
- Source CRS: WGS84 (EPSG:4326).
- Local planar CRS: UTM zone determined by region centroid (automatic with pyproj), then translate so that chosen origin maps to (0, 0).
- Origin: first GNSS point inside the selected region (lat0, lon0). After projecting to (X0, Y0), subtract (X0, Y0) from all projected points to yield (x_m, y_m).
- Alternative: If region spans multiple UTM zones or is very small, consider ENU around (lat0, lon0). Start with UTM for simplicity.

## CLI Interface (Initial)
- Command: v2aix-pipeline
- Args:
  - --input /path/to/json_folder (required)
  - --region-bbox "min_lon,min_lat,max_lon,max_lat" or --region-polygon /path/to/polygon.geojson (one required)
  - --origin "lon,lat" (optional; defaults to first point in region)
  - --hz 1 (target sampling frequency)
  - --sync-tolerance-ms 500 (for fusing comm events to trajectory grid)
  - --output-dir /path/to/output (required)
  - --format parquet|csv (default parquet)
  - --visualize (flag; produce plots)
  - --config /path/to/config.yaml (optional overrides)

## Interpolation & Smoothing Policy
- Smoothing: optional Savitzky–Golay (window length odd, e.g., 7; polyorder 2) on lat/lon separately in time domain; guard against large gaps.
- Interpolation to 1 Hz: build a regular time grid between first and last GNSS timestamps; linear interpolation for lat, lon, alt, speed, heading when gaps <= gap_threshold_s (e.g., 5 s). Mark missing when larger.
- Gap handling: if consecutive samples gap > gap_threshold_s, do not interpolate across; create break or NaNs and flag segment.

## Outputs
- trajectories.parquet (or .csv): rows = vehicle_id, timestamp_utc_ms, lat/lon/alt, x_m, y_m, speed_mps, heading_deg.
- v2x_metrics.parquet: rows = vehicle_id, timestamp_utc_ms (event), direction, message_type, rsu_id, payload_bytes, frame_bytes, latency_ms.
- fused.parquet: rows = per-vehicle per-second with x_m, y_m, tx_bytes, rx_bytes, avg_latency_ms, counts by type.
- visualize/: PNGs for trajectory maps and latency/throughput time series; optional heatmaps of latency over space.
