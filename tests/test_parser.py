import sys
import unittest
from pathlib import Path

# Ensure package under src is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from v2aix_pipeline.parser import (
    detect_timestamp_unit,
    normalize_timestamp,
    extract_vehicle_id,
    extract_latitude,
    extract_longitude,
    extract_message_type,
    extract_direction,
    parse_gnss_record,
    parse_v2x_record,
    parse_records,
)
from v2aix_pipeline.models import Direction


class TestTimestampUtilities(unittest.TestCase):
    """Test timestamp detection and normalization"""

    def test_detect_timestamp_unit(self):
        # Seconds (< 10^10)
        self.assertEqual(detect_timestamp_unit(1678901234), 'seconds')

        # Milliseconds (< 10^13)
        self.assertEqual(detect_timestamp_unit(1678901234000), 'milliseconds')

        # Microseconds (>= 10^13)
        self.assertEqual(detect_timestamp_unit(1678901234000000), 'microseconds')

    def test_normalize_timestamp_seconds(self):
        result = normalize_timestamp(1678901234, 'seconds')
        self.assertEqual(result, 1678901234000)

    def test_normalize_timestamp_milliseconds(self):
        result = normalize_timestamp(1678901234000, 'milliseconds')
        self.assertEqual(result, 1678901234000)

    def test_normalize_timestamp_microseconds(self):
        result = normalize_timestamp(1678901234000000, 'microseconds')
        self.assertEqual(result, 1678901234000)

    def test_normalize_timestamp_auto_detect(self):
        # Auto-detect seconds
        self.assertEqual(normalize_timestamp(1678901234), 1678901234000)

        # Auto-detect milliseconds
        self.assertEqual(normalize_timestamp(1678901234000), 1678901234000)

        # Auto-detect microseconds
        self.assertEqual(normalize_timestamp(1678901234000000), 1678901234000)


class TestFieldExtraction(unittest.TestCase):
    """Test field extraction from JSON objects"""

    def test_extract_vehicle_id(self):
        # Test stationID
        obj = {"stationID": "veh123"}
        self.assertEqual(extract_vehicle_id(obj), "veh123")

        # Test station_id
        obj = {"station_id": "veh456"}
        self.assertEqual(extract_vehicle_id(obj), "veh456")

        # Test vehicleID
        obj = {"vehicleID": "veh789"}
        self.assertEqual(extract_vehicle_id(obj), "veh789")

        # Test missing
        obj = {"other_field": "value"}
        self.assertIsNone(extract_vehicle_id(obj))

    def test_extract_coordinates(self):
        # Latitude variants
        self.assertEqual(extract_latitude({"latitude": 50.5}), 50.5)
        self.assertEqual(extract_latitude({"lat": 50.5}), 50.5)
        self.assertEqual(extract_latitude({"latitude_deg": 50.5}), 50.5)

        # Longitude variants
        self.assertEqual(extract_longitude({"longitude": 6.0}), 6.0)
        self.assertEqual(extract_longitude({"lon": 6.0}), 6.0)
        self.assertEqual(extract_longitude({"longitude_deg": 6.0}), 6.0)

    def test_extract_message_type(self):
        # messageType
        self.assertEqual(extract_message_type({"messageType": "CAM"}), "CAM")

        # message_type
        self.assertEqual(extract_message_type({"message_type": "DENM"}), "DENM")

        # msgType
        self.assertEqual(extract_message_type({"msgType": "SPATEM"}), "SPATEM")

        # Missing
        self.assertIsNone(extract_message_type({}))

    def test_extract_direction(self):
        # Valid direction
        obj = {"direction": "uplink_to_rsu"}
        result = extract_direction(obj)
        self.assertEqual(result, Direction.uplink_to_rsu)

        # Invalid direction
        obj = {"direction": "invalid_direction"}
        result = extract_direction(obj)
        self.assertIsNone(result)

        # Missing
        obj = {}
        result = extract_direction(obj)
        self.assertIsNone(result)


class TestGnssRecordParsing(unittest.TestCase):
    """Test GNSS record parsing"""

    def test_parse_gnss_record_basic(self):
        obj = {
            "stationID": "veh1",
            "timestamp": 1678901234,
            "latitude": 50.7753,
            "longitude": 6.0839
        }

        record = parse_gnss_record(obj)

        self.assertIsNotNone(record)
        self.assertEqual(record.vehicle_id, "veh1")
        self.assertEqual(record.timestamp_utc_ms, 1678901234000)
        self.assertEqual(record.latitude_deg, 50.7753)
        self.assertEqual(record.longitude_deg, 6.0839)

    def test_parse_gnss_record_with_optional_fields(self):
        obj = {
            "stationID": "veh2",
            "timestamp": 1678901234000,
            "latitude": 50.7753,
            "longitude": 6.0839,
            "altitude": 120.5,
            "speed": 15.2,
            "heading": 45.0,
            "stationType": "passengerCar"
        }

        record = parse_gnss_record(obj, timestamp_unit='milliseconds')

        self.assertIsNotNone(record)
        self.assertEqual(record.altitude_m, 120.5)
        self.assertEqual(record.speed_mps, 15.2)
        self.assertEqual(record.heading_deg, 45.0)
        self.assertEqual(record.station_type, "passengerCar")

    def test_parse_gnss_record_missing_vehicle_id(self):
        obj = {
            "timestamp": 1678901234,
            "latitude": 50.7753,
            "longitude": 6.0839
        }

        record = parse_gnss_record(obj)
        self.assertIsNone(record)

    def test_parse_gnss_record_missing_coordinates(self):
        obj = {
            "stationID": "veh1",
            "timestamp": 1678901234
        }

        record = parse_gnss_record(obj)
        self.assertIsNone(record)

    def test_parse_gnss_record_missing_timestamp(self):
        obj = {
            "stationID": "veh1",
            "latitude": 50.7753,
            "longitude": 6.0839
        }

        record = parse_gnss_record(obj)
        self.assertIsNone(record)


class TestV2XRecordParsing(unittest.TestCase):
    """Test V2X record parsing"""

    def test_parse_v2x_record_basic(self):
        obj = {
            "stationID": "veh1",
            "messageType": "CAM",
            "timestamp": 1678901234000
        }

        record = parse_v2x_record(obj, timestamp_unit='milliseconds')

        self.assertIsNotNone(record)
        self.assertEqual(record.vehicle_id, "veh1")
        self.assertEqual(record.message_type, "CAM")
        self.assertEqual(record.timestamp_utc_ms, 1678901234000)

    def test_parse_v2x_record_with_latency(self):
        obj = {
            "stationID": "veh1",
            "messageType": "CAM",
            "tx_timestamp": 1678901234000,
            "rx_timestamp": 1678901234020,
            "payload_bytes": 256,
            "direction": "uplink_to_rsu",
            "rsu_id": "RSU-01"
        }

        record = parse_v2x_record(obj, timestamp_unit='milliseconds')

        self.assertIsNotNone(record)
        self.assertEqual(record.tx_timestamp_utc_ms, 1678901234000)
        self.assertEqual(record.rx_timestamp_utc_ms, 1678901234020)
        self.assertEqual(record.latency_ms, 20.0)
        self.assertEqual(record.payload_bytes, 256)
        self.assertEqual(record.direction, Direction.uplink_to_rsu)
        self.assertEqual(record.rsu_id, "RSU-01")

    def test_parse_v2x_record_denm(self):
        obj = {
            "stationID": "veh2",
            "messageType": "DENM",
            "timestamp": 1678901235000,
            "payload_bytes": 128,
            "frame_bytes": 160
        }

        record = parse_v2x_record(obj, timestamp_unit='milliseconds')

        self.assertIsNotNone(record)
        self.assertEqual(record.message_type, "DENM")
        self.assertEqual(record.payload_bytes, 128)
        self.assertEqual(record.frame_bytes, 160)

    def test_parse_v2x_record_missing_vehicle_id(self):
        obj = {
            "messageType": "CAM",
            "timestamp": 1678901234000
        }

        record = parse_v2x_record(obj)
        self.assertIsNone(record)


class TestBatchParsing(unittest.TestCase):
    """Test batch parsing of multiple records"""

    def test_parse_records_mixed(self):
        objects = [
            # GNSS record
            {
                "stationID": "veh1",
                "timestamp": 1678901234,
                "latitude": 50.7753,
                "longitude": 6.0839
            },
            # V2X record (with message_type to distinguish it)
            {
                "stationID": "veh1",
                "messageType": "CAM",
                "tx_timestamp": 1678901234100
            },
            # Another GNSS record
            {
                "stationID": "veh2",
                "timestamp": 1678901235,
                "latitude": 50.7755,
                "longitude": 6.0840
            }
        ]

        gnss_records, v2x_records = parse_records(objects)

        # GNSS records with coordinates
        self.assertEqual(len(gnss_records), 2)
        # V2X records: Note that GNSS records also create V2X records with just vehicle_id
        # since they have a timestamp, which is all that's minimally required
        self.assertGreaterEqual(len(v2x_records), 1)

        # Check first GNSS record
        self.assertEqual(gnss_records[0].vehicle_id, "veh1")
        self.assertEqual(gnss_records[0].latitude_deg, 50.7753)

        # Check V2X record with message type
        v2x_with_msg = [r for r in v2x_records if r.message_type == "CAM"]
        self.assertEqual(len(v2x_with_msg), 1)
        self.assertEqual(v2x_with_msg[0].vehicle_id, "veh1")

    def test_parse_records_empty(self):
        gnss_records, v2x_records = parse_records([])
        self.assertEqual(len(gnss_records), 0)
        self.assertEqual(len(v2x_records), 0)

    def test_parse_records_combined_gnss_and_v2x(self):
        """Test object with both GNSS and V2X fields"""
        objects = [
            {
                "stationID": "veh1",
                "timestamp": 1678901234,
                "latitude": 50.7753,
                "longitude": 6.0839,
                "messageType": "CAM",
                "tx_timestamp": 1678901234100
            }
        ]

        gnss_records, v2x_records = parse_records(objects)

        # Should be parsed as both GNSS and V2X
        self.assertEqual(len(gnss_records), 1)
        self.assertEqual(len(v2x_records), 1)


if __name__ == "__main__":
    unittest.main()
