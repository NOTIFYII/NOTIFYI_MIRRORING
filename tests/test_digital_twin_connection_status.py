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

    def save(self, *, age_seconds=0, port="/dev/ttyACM0", baudrate=57600):
        self.path.write_text(json.dumps({
            "checked_at": time.time() - age_seconds,
            "port": port,
            "protocol": 2.0,
            "results": [{"id": 2, "baudrate": baudrate},
                        {"id": 3, "baudrate": 1000000}],
        }), encoding="utf-8")

    def test_missing_scan_is_unknown(self):
        self.assertIsNone(serve.recent_motor_probe(self.bus))

    def test_only_configured_baud_counts(self):
        self.save()
        probe = serve.recent_motor_probe(self.bus)
        self.assertTrue(probe["fresh"])
        self.assertEqual(probe["responding_ids"], [2])

    def test_old_scan_is_not_live(self):
        self.save(age_seconds=30)
        self.assertFalse(serve.recent_motor_probe(self.bus)["fresh"])

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
