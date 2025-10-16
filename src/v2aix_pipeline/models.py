from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field


class Direction(str, Enum):
	uplink_to_rsu = "uplink_to_rsu"
	downlink_from_rsu = "downlink_from_rsu"
	v2v = "v2v"


class QualityFlags(BaseModel):
	gap: bool = Field(False, description="True if sample is within or adjacent to a long gap")
	extrapolated: bool = Field(False, description="True if value extrapolated beyond observed window")
	low_speed: bool = Field(False, description="True if speed below threshold where heading unreliable")


class GnssRecord(BaseModel):
	vehicle_id: str
	timestamp_utc_ms: int
	latitude_deg: float
	longitude_deg: float
	altitude_m: Optional[float] = None
	speed_mps: Optional[float] = None
	heading_deg: Optional[float] = None
	station_id: Optional[str] = Field(default=None, description="Original stationID if present")
	station_type: Optional[str] = Field(default=None, description="Original stationType if present")
	source_file: Optional[Path] = None


class V2XMessageRecord(BaseModel):
	vehicle_id: str
	# Optional raw identity/context
	station_id: Optional[str] = None
	station_type: Optional[str] = None
	# Event timing
	timestamp_utc_ms: Optional[int] = Field(default=None, description="Generic event time if single timestamp provided")
	tx_timestamp_utc_ms: Optional[int] = None
	rx_timestamp_utc_ms: Optional[int] = None
	# Link semantics
	direction: Optional[Direction] = None
	rsu_id: Optional[str] = None
	message_type: Optional[str] = None
	# Sizes and metrics
	payload_bytes: Optional[int] = None
	frame_bytes: Optional[int] = None
	latency_ms: Optional[float] = Field(default=None, description="rx - tx when both available and clocks comparable")
	source_file: Optional[Path] = None


class TrajectorySample(BaseModel):
	vehicle_id: str
	timestamp_utc_ms: int
	# Geodetic (post-smoothing)
	lat_deg: float
	lon_deg: float
	alt_m: Optional[float] = None
	# Local planar coordinates
	x_m: float
	y_m: float
	speed_mps: Optional[float] = None
	heading_deg: Optional[float] = None
	quality: QualityFlags = Field(default_factory=QualityFlags)


class FusedRecord(BaseModel):
	vehicle_id: str
	timestamp_utc_ms: int
	x_m: float
	y_m: float
	tx_bytes: int = 0
	rx_bytes: int = 0
	avg_latency_ms: Optional[float] = None
	msg_counts: Dict[str, int] = Field(default_factory=dict)


class DatasetMetadata(BaseModel):
	# Coordinate reference information
	crs: str = Field("ENU", description="Coordinate reference system for x/y (ENU or UTM EPSG code)")
	origin_lat_deg: float
	origin_lon_deg: float
	origin_alt_m: float = 0.0
	# Processing parameters
	hz: int = 1
	gap_threshold_s: float = 5.0
	sync_tolerance_ms: int = 500
	# Provenance
	input_dir: Path
	output_dir: Path
	notes: Optional[str] = None
