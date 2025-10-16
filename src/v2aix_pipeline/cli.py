from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .config import PipelineConfig, load_config
from .discovery import discover_dataset, discovery_dataframe

# Configure logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(prog="v2aix-pipeline", description="V2AIX data processing pipeline")
	parser.add_argument("--config", type=str, help="Path to YAML/JSON config file", default=None)
	parser.add_argument("--input", type=str, help="Input JSON folder", default=None)
	parser.add_argument("--output-dir", type=str, help="Output directory", default=None)
	parser.add_argument("--region-bbox", type=str, help="min_lon,min_lat,max_lon,max_lat", default=None)
	parser.add_argument("--region-polygon", type=str, help="Path to polygon GeoJSON", default=None)
	parser.add_argument("--origin", type=str, help="lon,lat", default=None)
	parser.add_argument("--hz", type=int, default=1)
	parser.add_argument("--sync-tolerance-ms", type=int, default=500)
	parser.add_argument("--format", type=str, default="parquet")
	parser.add_argument("--visualize", action="store_true")
	parser.add_argument("--gap-threshold-s", type=float, default=5.0)
	parser.add_argument("--use-enu", action="store_true")
	parser.add_argument("--ids-map", type=str, default=None)
	parser.add_argument("--rsu-ids", type=str, default=None)
	parser.add_argument("--metadata-out", type=str, default=None)
	parser.add_argument("--sample", type=int, default=None)
	parser.add_argument("--workers", type=int, default=None)
	return parser.parse_args()


def _parse_bbox(bbox_str: str):
	parts = [p.strip() for p in bbox_str.split(",")]
	if len(parts) != 4:
		raise ValueError("--region-bbox must be 'min_lon,min_lat,max_lon,max_lat'")
	return tuple(float(p) for p in parts)  # type: ignore


def _parse_origin(origin_str: str):
	parts = [p.strip() for p in origin_str.split(",")]
	if len(parts) != 2:
		raise ValueError("--origin must be 'lon,lat'")
	return (float(parts[0]), float(parts[1]))


def _config_from_args(args: argparse.Namespace) -> PipelineConfig:
	if args.config:
		return load_config(Path(args.config))
	if not args.input or not args.output_dir:
		raise SystemExit("Either --config or both --input and --output-dir must be provided")
	region_bbox = _parse_bbox(args.region_bbox) if args.region_bbox else None
	origin = _parse_origin(args.origin) if args.origin else None
	return PipelineConfig(
		input_dir=Path(args.input),
		output_dir=Path(args.output_dir),
		region_bbox=region_bbox,
		region_polygon_path=Path(args.region_polygon).expanduser().resolve() if args.region_polygon else None,
		origin=origin,
		hz=args.hz,
		sync_tolerance_ms=args.sync_tolerance_ms,
		format=args.format,
		visualize=args.visualize,
		gap_threshold_s=args.gap_threshold_s,
		use_enu=args.use_enu,
		ids_map_path=Path(args.ids_map).expanduser().resolve() if args.ids_map else None,
		rsu_ids_path=Path(args.rsu_ids).expanduser().resolve() if args.rsu_ids else None,
		metadata_out=Path(args.metadata_out).expanduser().resolve() if args.metadata_out else None,
		sample=args.sample,
		workers=args.workers,
	)


def main() -> None:
	args = _parse_args()
	cfg = _config_from_args(args)

	# Discovery phase
	logger.info("Starting dataset discovery for: %s", cfg.input_dir)
	summary = discover_dataset(cfg.input_dir, sample=cfg.sample)
	logger.info("Discovery complete")

	print("=== V2AIX Dataset Discovery ===")
	print(json.dumps(summary, indent=2))

	try:
		df = discovery_dataframe(summary)
		print("\nSummary Table:")
		print(df.to_string(index=False))
	except ImportError:
		logger.warning("Pandas not available, skipping table display. Install with: pip install pandas")
	except Exception as e:
		logger.error(f"Failed to create summary table: {e}")


if __name__ == "__main__":
	main()

