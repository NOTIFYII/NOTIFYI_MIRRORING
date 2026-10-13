"""Read-only dashboard snapshots must never confuse old scans with live motors."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.digital_twin import serve


class ConnectionStatusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "connection_status.json"
        self.patcher = patch.object(serve, "STATUS_FILE", self.path)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.bus = {"port": "/dev/ttyACM0", "baudrate": 57600, "protocol": 2.0}

    def save(self, *, age_seconds=0, port="/dev/ttyACM0", baudrate=57600,
             torque_enable=None, present_position=None):
        self.path.write_text(json.dumps({
            "checked_at": time.time() - age_seconds,
            "port": port,
            "protocol": 2.0,
            "results": [{"id": 2, "baudrate": baudrate,
                         "torque_enable": torque_enable,
                         "present_position": present_position,
                         "hw_error": 0},
                        {"id": 3, "baudrate": 1000000}],
        }), encoding="utf-8")

    def test_missing_scan_is_unknown(self):
        self.assertIsNone(serve.recent_motor_probe(self.bus))

    def test_only_configured_baud_counts(self):
        self.save()
        probe = serve.recent_motor_probe(self.bus)
        self.assertTrue(probe["fresh"])
        self.assertEqual(probe["responding_ids"], [2])

    def test_last_scan_torque_and_position_are_per_id_not_live_torque(self):
        self.save(torque_enable=0, present_position=4108)
        probe = serve.recent_motor_probe(self.bus)
        self.assertEqual(probe["motor_states"], [{
            "id": 2, "torque_enable": 0,
            "present_position": 4108, "hw_error": 0,
        }])
        self.assertNotIn("torque_nm", probe["motor_states"][0])

    def test_older_scan_without_detail_is_unknown(self):
        self.save()
        state = serve.recent_motor_probe(self.bus)["motor_states"][0]
        self.assertIsNone(state["torque_enable"])
        self.assertIsNone(state["present_position"])

    def test_workspace_zero_positions_and_unused_ids(self):
        with patch.object(serve.os.path, "exists", return_value=True):
            snapshot = serve.workspace_snapshot()
        zeros = {joint["id"]: joint["zero_position"] for joint in snapshot["joints"]}
        self.assertEqual(zeros, {2: 1, 3: 1022})
        self.assertEqual(snapshot["unused_ids"], [1, 4])

    def test_old_scan_is_not_live(self):
        self.save(age_seconds=30)
        self.assertFalse(serve.recent_motor_probe(self.bus)["fresh"])

    def test_read_only_watch_becomes_stale_and_keeps_source(self):
        payload = {
            "source": "read_only_watch", "checked_at": time.time(),
            "sequence": 4, "interval_seconds": 3,
            "port": self.bus["port"], "protocol": 2.0,
            "results": [{"id": 2, "baudrate": 57600, "present_position": 1034,
                         "torque_enable": 0, "hw_error": 0, "operating_mode": 3,
                         "valid": True}],
        }
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        probe = serve.recent_motor_probe(self.bus)
        self.assertTrue(probe["fresh"])
        self.assertEqual(probe["source"], "read_only_watch")
        self.assertEqual(probe["sequence"], 4)
        self.assertTrue(probe["motor_states"][0]["valid"])
        payload["checked_at"] -= 10
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertFalse(serve.recent_motor_probe(self.bus)["fresh"])

    def test_invalid_watch_metadata_cannot_appear_live(self):
        self.path.write_text(json.dumps({
            "source": "read_only_watch", "checked_at": time.time(),
            "sequence": 1, "interval_seconds": 0,
            "port": self.bus["port"], "protocol": 2.0, "results": [],
        }), encoding="utf-8")
        self.assertIsNone(serve.recent_motor_probe(self.bus))

    def test_other_port_is_not_this_bus(self):
        self.save(port="/dev/ttyUSB0")
        self.assertIsNone(serve.recent_motor_probe(self.bus))

    def test_missing_usb_path_cannot_report_live_motors(self):
        self.save()
        with patch.object(serve.os.path, "exists", return_value=False):
            snapshot = serve.workspace_snapshot()
        self.assertFalse(snapshot["motor_probe"]["fresh"])
        self.assertEqual(snapshot["verification"]["motor_response"], "unverified")


if __name__ == "__main__":
    unittest.main()
