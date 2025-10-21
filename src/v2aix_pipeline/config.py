"""
Configuration management for the V2AIX data processing pipeline.

This module provides configuration loading and validation using Pydantic models.
Supports both YAML and JSON configuration files, with command-line overrides.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml
from pydantic import BaseModel, Field, field_validator


class PipelineConfig(BaseModel):
    """Main configuration model for the V2AIX data processing pipeline.

    Attributes:
        input_dir: Directory containing input JSON files
        output_dir: Directory for output files (Parquet/CSV)
        region_bbox: Optional bounding box (min_lon, min_lat, max_lon, max_lat)
        region_polygon_path: Optional path to GeoJSON polygon file for region filtering
        origin: Optional origin point (lon, lat) for coordinate system
        hz: Target sampling frequency in Hz (default: 1)
        sync_tolerance_ms: Time synchronization tolerance in milliseconds (default: 500)
        format: Output format, either 'parquet' or 'csv' (default: 'parquet')
        visualize: Whether to generate visualizations (default: False)
        gap_threshold_s: Gap detection threshold in seconds (default: 5.0)
        use_enu: Use ENU coordinate system instead of UTM (default: True)
        ids_map_path: Optional path to vehicle ID mapping JSON file
        rsu_ids_path: Optional path to RSU metadata JSON file
        metadata_out: Optional path for output metadata JSON file
        sample: Optional limit on number of samples during discovery phase
        workers: Optional number of parallel workers for processing
    """

    input_dir: Path = Field(..., description="Input directory containing JSON files")
    output_dir: Path = Field(..., description="Output directory for processed data")
    region_bbox: Optional[Tuple[float, float, float, float]] = Field(
        default=None,
        description="Region bounding box: (min_lon, min_lat, max_lon, max_lat)"
    )
    region_polygon_path: Optional[Path] = Field(
        default=None,
        description="Path to GeoJSON polygon file for region filtering"
    )
    origin: Optional[Tuple[float, float]] = Field(
        default=None,
        description="Coordinate system origin (lon, lat)"
    )
    hz: int = Field(default=1, ge=1, le=100, description="Target sampling frequency in Hz")
    sync_tolerance_ms: int = Field(
        default=500,
        ge=0,
        description="Time synchronization tolerance in milliseconds"
    )
    format: str = Field(default="parquet", description="Output format: 'parquet' or 'csv'")
    visualize: bool = Field(default=False, description="Generate visualizations")
    gap_threshold_s: float = Field(
        default=5.0,
        ge=0.0,
        description="Gap detection threshold in seconds"
    )
    use_enu: bool = Field(
        default=True,
        description="Use ENU coordinate system instead of UTM"
    )
    ids_map_path: Optional[Path] = Field(
        default=None,
        description="Path to vehicle ID mapping JSON file"
    )
    rsu_ids_path: Optional[Path] = Field(
        default=None,
        description="Path to RSU metadata JSON file"
    )
    metadata_out: Optional[Path] = Field(
        default=None,
        description="Path for output metadata JSON file"
    )
    sample: Optional[int] = Field(
        default=None,
        ge=1,
        description="Limit number of samples during discovery phase"
    )
    workers: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of parallel workers for processing"
    )
    scenario_dirs: Optional[list] = Field(
        default=None,
        description="List of scenario directories to process (relative to input_dir)"
    )

    @field_validator('format')
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate that format is either 'parquet' or 'csv'."""
        if v not in ('parquet', 'csv'):
            raise ValueError(f"format must be 'parquet' or 'csv', got '{v}'")
        return v

    @field_validator('input_dir', 'output_dir', mode='before')
    @classmethod
    def expand_path(cls, v: Any) -> Path:
        """Expand user paths and convert to absolute paths."""
        if v is None:
            return v
        path = Path(v).expanduser().resolve()
        return path

    @field_validator('region_polygon_path', 'ids_map_path', 'rsu_ids_path', 'metadata_out', mode='before')
    @classmethod
    def expand_optional_path(cls, v: Any) -> Optional[Path]:
        """Expand user paths for optional path fields."""
        if v is None:
            return None
        return Path(v).expanduser().resolve()

    @field_validator('region_bbox')
    @classmethod
    def validate_bbox(cls, v: Optional[Tuple[float, float, float, float]]) -> Optional[Tuple[float, float, float, float]]:
        """Validate bounding box coordinates."""
        if v is None:
            return None
        min_lon, min_lat, max_lon, max_lat = v
        if min_lon >= max_lon:
            raise ValueError(f"min_lon ({min_lon}) must be less than max_lon ({max_lon})")
        if min_lat >= max_lat:
            raise ValueError(f"min_lat ({min_lat}) must be less than max_lat ({max_lat})")
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
            raise ValueError(f"Longitude must be in range [-180, 180], got [{min_lon}, {max_lon}]")
        if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            raise ValueError(f"Latitude must be in range [-90, 90], got [{min_lat}, {max_lat}]")
        return v


def load_config(config_path: Path) -> PipelineConfig:
    """Load configuration from a YAML or JSON file.

    Args:
        config_path: Path to the configuration file (.yaml, .yml, or .json)

    Returns:
        Validated PipelineConfig instance

    Raises:
        FileNotFoundError: If config file does not exist
        ValueError: If config file is malformed or contains invalid data

    Examples:
        >>> config = load_config(Path("config.yaml"))
        >>> print(config.input_dir)
    """
    config_path = config_path.expanduser().resolve()

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    # Read file content
    try:
        text = config_path.read_text(encoding='utf-8')
    except Exception as e:
        raise ValueError(f"Failed to read config file {config_path}: {e}")

    # Parse YAML/JSON
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file {config_path}: {e}")

    # Validate data structure
    if not isinstance(data, dict):
        raise ValueError(
            f"Config file must contain a JSON/YAML object (dict), not {type(data).__name__}. "
            f"Found: {data}"
        )

    # Create and validate config
    try:
        return PipelineConfig(**data)
    except Exception as e:
        raise ValueError(f"Invalid configuration in {config_path}: {e}")


def load_identity_map(ids_map_path: Path) -> Dict[str, str]:
    """Load vehicle identity mapping from JSON file.

    The identity map resolves vehicle IDs across different data sources,
    mapping raw IDs to canonical vehicle identifiers.

    Args:
        ids_map_path: Path to JSON file containing ID mapping

    Returns:
        Dictionary mapping raw IDs to canonical vehicle IDs

    Raises:
        FileNotFoundError: If mapping file does not exist
        ValueError: If file is malformed or not a JSON object

    Examples:
        >>> id_map = load_identity_map(Path("ids_map.json"))
        >>> canonical_id = id_map.get(raw_id, raw_id)
    """
    ids_map_path = ids_map_path.expanduser().resolve()

    if not ids_map_path.exists():
        raise FileNotFoundError(f"Identity map file not found: {ids_map_path}")

    try:
        text = ids_map_path.read_text(encoding='utf-8')
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in identity map file {ids_map_path}: {e}")
    except Exception as e:
        raise ValueError(f"Failed to read identity map file {ids_map_path}: {e}")

    if not isinstance(data, dict):
        raise ValueError(
            f"Identity map file must contain a JSON object (dict), not {type(data).__name__}. "
            f"Found: {data}"
        )

    # Ensure all values are strings
    return {str(k): str(v) for k, v in data.items()}


def load_rsu_ids(rsu_ids_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load RSU metadata from JSON file.

    The RSU metadata file contains information about roadside units,
    including their locations and identifiers.

    Args:
        rsu_ids_path: Path to JSON file containing RSU metadata

    Returns:
        Dictionary mapping RSU IDs to their metadata

    Raises:
        FileNotFoundError: If RSU metadata file does not exist
        ValueError: If file is malformed or not a JSON object

    Examples:
        >>> rsu_metadata = load_rsu_ids(Path("rsu_ids.json"))
        >>> rsu_info = rsu_metadata.get("RSU_001", {})
        >>> location = rsu_info.get("location")
    """
    rsu_ids_path = rsu_ids_path.expanduser().resolve()

    if not rsu_ids_path.exists():
        raise FileNotFoundError(f"RSU metadata file not found: {rsu_ids_path}")

    try:
        text = rsu_ids_path.read_text(encoding='utf-8')
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in RSU metadata file {rsu_ids_path}: {e}")
    except Exception as e:
        raise ValueError(f"Failed to read RSU metadata file {rsu_ids_path}: {e}")

    if not isinstance(data, dict):
        raise ValueError(
            f"RSU metadata file must contain a JSON object (dict), not {type(data).__name__}. "
            f"Found: {data}"
        )

    return data
