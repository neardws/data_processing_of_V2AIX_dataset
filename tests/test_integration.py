import sys
import unittest
from pathlib import Path

# Ensure package under src is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from v2aix_pipeline.models import GnssRecord, QualityFlags, TrajectorySample
from v2aix_pipeline.filters import filter_by_bbox
from v2aix_pipeline.parser import parse_gnss_record, parse_v2x_record


class TestFilters(unittest.TestCase):
    """Test geographic filtering"""

    def setUp(self):
        # Create test GNSS records
        self.records = [
            parse_gnss_record({
                "stationID": "veh1",
                "timestamp": 1678901234,
                "latitude": 50.0,
                "longitude": 6.0
            }),
            parse_gnss_record({
                "stationID": "veh2",
                "timestamp": 1678901235,
                "latitude": 50.5,
                "longitude": 6.5
            }),
            parse_gnss_record({
                "stationID": "veh3",
                "timestamp": 1678901236,
                "latitude": 51.0,
                "longitude": 7.0
            }),
        ]

    def test_filter_by_bbox_contain(self):
        # Bbox that contains only the middle record
        bbox = [6.4, 50.4, 6.6, 50.6]  # min_lon, min_lat, max_lon, max_lat

        filtered = filter_by_bbox(self.records, bbox, mode='contain')

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].vehicle_id, "veh2")

    def test_filter_by_bbox_intersect(self):
        # Bbox that intersects with first two records
        bbox = [5.5, 49.5, 6.5, 50.5]

        filtered = filter_by_bbox(self.records, bbox, mode='intersect')

        self.assertGreaterEqual(len(filtered), 1)

    def test_filter_by_bbox_first(self):
        # Any bbox - should return records whose first point is inside
        bbox = [5.9, 49.9, 6.1, 50.1]

        filtered = filter_by_bbox(self.records, bbox, mode='first')

        # Should include veh1 whose first point is at (6.0, 50.0)
        vehicle_ids = [r.vehicle_id for r in filtered]
        self.assertIn("veh1", vehicle_ids)


class TestModels(unittest.TestCase):
    """Test data models"""

    def test_gnss_record_creation(self):
        record = GnssRecord(
            vehicle_id="veh1",
            timestamp_utc_ms=1678901234000,
            latitude_deg=50.0,
            longitude_deg=6.0,
            speed_mps=10.0,
            heading_deg=45.0
        )

        self.assertEqual(record.vehicle_id, "veh1")
        self.assertEqual(record.timestamp_utc_ms, 1678901234000)
        self.assertEqual(record.latitude_deg, 50.0)
        self.assertEqual(record.longitude_deg, 6.0)

    def test_trajectory_sample_with_quality_flags(self):
        sample = TrajectorySample(
            vehicle_id="veh1",
            timestamp_utc_ms=1000,
            lat_deg=50.0,
            lon_deg=6.0,
            x_m=100.0,
            y_m=200.0,
            speed_mps=10.0,
            heading_deg=45.0,
            quality=QualityFlags(gap=True, extrapolated=False, low_speed=False)
        )

        self.assertTrue(sample.quality.gap)
        self.assertFalse(sample.quality.extrapolated)
        self.assertFalse(sample.quality.low_speed)


class TestIntegration(unittest.TestCase):
    """Integration tests for parsing and filtering pipeline"""

    def test_parse_and_filter_pipeline(self):
        """Test a basic data flow from parsing to filtering"""

        # 1. Parse raw JSON to records
        gnss_data = [
            {
                "stationID": "veh1",
                "timestamp": 1678901234,
                "latitude": 50.0,
                "longitude": 6.0,
                "speed": 10.0,
                "heading": 45.0
            },
            {
                "stationID": "veh1",
                "timestamp": 1678901235,
                "latitude": 50.001,
                "longitude": 6.001,
                "speed": 11.0,
                "heading": 46.0
            },
            {
                "stationID": "veh2",
                "timestamp": 1678901236,
                "latitude": 52.0,  # Outside bbox
                "longitude": 8.0,
                "speed": 12.0,
                "heading": 90.0
            },
        ]

        gnss_records = [parse_gnss_record(obj) for obj in gnss_data]
        gnss_records = [r for r in gnss_records if r is not None]

        # Verify parsing
        self.assertEqual(len(gnss_records), 3)
        self.assertEqual(gnss_records[0].vehicle_id, "veh1")

        # 2. Filter by bbox
        bbox = [5.5, 49.5, 6.5, 50.5]
        filtered = filter_by_bbox(gnss_records, bbox, mode='intersect')

        # 3. Verify filtering
        # Should keep veh1 records (50.0, 6.0) and (50.001, 6.001)
        # Should exclude veh2 record (52.0, 8.0)
        self.assertGreaterEqual(len(filtered), 2)
        self.assertLess(len(filtered), len(gnss_records))

        # All filtered records should be within bbox
        for rec in filtered:
            self.assertGreaterEqual(rec.longitude_deg, bbox[0])
            self.assertGreaterEqual(rec.latitude_deg, bbox[1])
            self.assertLessEqual(rec.longitude_deg, bbox[2])
            self.assertLessEqual(rec.latitude_deg, bbox[3])

    def test_v2x_parsing_and_metrics(self):
        """Test V2X message parsing"""

        v2x_data = [
            {
                "stationID": "veh1",
                "messageType": "CAM",
                "tx_timestamp": 1678901234000,
                "rx_timestamp": 1678901234020,
                "payload_bytes": 128
            },
            {
                "stationID": "veh1",
                "messageType": "DENM",
                "timestamp": 1678901235000,
                "payload_bytes": 64
            },
        ]

        v2x_records = [parse_v2x_record(obj, timestamp_unit='milliseconds') for obj in v2x_data]
        v2x_records = [r for r in v2x_records if r is not None]

        # Verify parsing
        self.assertEqual(len(v2x_records), 2)

        # Check CAM record with latency
        cam_record = v2x_records[0]
        self.assertEqual(cam_record.message_type, "CAM")
        self.assertEqual(cam_record.payload_bytes, 128)
        self.assertIsNotNone(cam_record.latency_ms)
        self.assertEqual(cam_record.latency_ms, 20.0)

        # Check DENM record
        denm_record = v2x_records[1]
        self.assertEqual(denm_record.message_type, "DENM")
        self.assertEqual(denm_record.payload_bytes, 64)


if __name__ == "__main__":
    unittest.main()
