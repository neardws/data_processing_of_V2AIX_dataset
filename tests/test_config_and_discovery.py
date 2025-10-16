import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

# Ensure package under src is importable without install
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from v2aix_pipeline.config import load_config, PipelineConfig, load_identity_map, load_rsu_ids
from v2aix_pipeline.discovery import discover_dataset


class TestConfigAndDiscovery(unittest.TestCase):
	def setUp(self):
		self.tmpdir = tempfile.TemporaryDirectory()
		self.root = Path(self.tmpdir.name)
		(self.root / "in").mkdir(parents=True, exist_ok=True)
		(self.root / "out").mkdir(parents=True, exist_ok=True)

		# Create sample JSON array file (GNSS + V2X)
		array_path = self.root / "in" / "array.json"
		array_data = [
			{"stationID": "veh1", "latitude": 50.0, "longitude": 6.0},
			{"stationID": "veh2", "message_type": "CAM", "payload_bytes": 120},
		]
		array_path.write_text(json.dumps(array_data), encoding="utf-8")

		# Create sample JSON lines file
		lines_path = self.root / "in" / "lines.json"
		with lines_path.open("w", encoding="utf-8") as f:
			f.write(json.dumps({"stationID": "veh1", "lat": 50.0001, "lon": 6.0001}) + "\n")
			f.write(json.dumps({"stationID": "veh1", "message_type": "DENM", "payload_bytes": 64}) + "\n")

		# YAML config
		self.yaml_cfg = self.root / "config.yaml"
		yaml_text = (
			"input_dir: " + str((self.root / "in").as_posix()) + "\n"
			"output_dir: " + str((self.root / "out").as_posix()) + "\n"
			"region_bbox: [6.0, 50.0, 6.1, 50.1]\n"
			"hz: 1\n"
			"sync_tolerance_ms: 500\n"
			"format: parquet\n"
		)
		self.yaml_cfg.write_text(yaml_text, encoding="utf-8")

		# JSON config
		self.json_cfg = self.root / "config.json"
		json_cfg_data = {
			"input_dir": str((self.root / "in").as_posix()),
			"output_dir": str((self.root / "out").as_posix()),
			"hz": 1,
		}
		self.json_cfg.write_text(json.dumps(json_cfg_data), encoding="utf-8")

		# Identity map
		self.ids_map = self.root / "ids_map.json"
		self.ids_map.write_text(json.dumps({"vehX": "veh1"}), encoding="utf-8")

		# RSU ids
		self.rsu_ids = self.root / "rsu_ids.json"
		self.rsu_ids.write_text(json.dumps({"RSU-1": {"location": {"lat": 50.0, "lon": 6.0}}}), encoding="utf-8")

	def tearDown(self):
		self.tmpdir.cleanup()

	def test_load_config_yaml(self):
		cfg = load_config(self.yaml_cfg)
		self.assertIsInstance(cfg, PipelineConfig)
		self.assertTrue(cfg.input_dir.exists())
		self.assertTrue(cfg.output_dir.exists())
		self.assertEqual(cfg.hz, 1)

	def test_load_config_json(self):
		cfg = load_config(self.json_cfg)
		self.assertIsInstance(cfg, PipelineConfig)
		self.assertTrue(cfg.input_dir.exists())
		self.assertTrue(cfg.output_dir.exists())
		self.assertEqual(cfg.hz, 1)

	def test_identity_and_rsu_maps(self):
		ids = load_identity_map(self.ids_map)
		rsu = load_rsu_ids(self.rsu_ids)
		self.assertEqual(ids.get("vehX"), "veh1")
		self.assertIn("RSU-1", rsu)

	def test_discover_dataset(self):
		summary = discover_dataset(self.root / "in", sample=10)
		self.assertEqual(summary.get("num_json_files"), 2)
		self.assertGreaterEqual(summary.get("estimated_gnss_records", 0), 1)
		self.assertGreaterEqual(summary.get("estimated_v2x_records", 0), 1)
		self.assertGreaterEqual(summary.get("unique_vehicle_ids", 0), 1)


if __name__ == "__main__":
	unittest.main()

