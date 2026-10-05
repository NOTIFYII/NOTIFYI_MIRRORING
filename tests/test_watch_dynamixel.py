"""The watch publisher reads bus telemetry and writes only a local status file."""

import json
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from dynamixel_sdk import COMM_SUCCESS

from scripts import watch_dynamixel


class FakePacket:
    def ping(self, _port, motor_id):
        return (1090, COMM_SUCCESS, 0) if motor_id == 2 else (0, -1, 0)

    def read4ByteTxRx(self, _port, _motor_id, address):
        self_address = 132
        assert address == self_address
        return 0xFFFFFFFF, COMM_SUCCESS, 0

    def read1ByteTxRx(self, _port, _motor_id, address):
        return {64: 0, 70: 0, 11: 3}[address], COMM_SUCCESS, 0

    def read2ByteTxRx(self, _port, _motor_id, _address):
        raise AssertionError("이번 관측기는 2바이트 필드를 읽지 않아야 합니다")


class WatchTests(unittest.TestCase):
    def test_without_confirmation_never_opens_serial_port(self):
        with redirect_stderr(io.StringIO()), patch("sys.argv", ["watch_dynamixel.py"]), patch.object(
            watch_dynamixel, "PortHandler", side_effect=AssertionError("serial port opened")
        ):
            with self.assertRaises(SystemExit) as stopped:
                watch_dynamixel.main()
        self.assertEqual(stopped.exception.code, 2)

    def test_observe_only_responding_ids_and_preserve_signed_position(self):
        results = watch_dynamixel.observe_once(FakePacket(), object(), [2, 3], 57600)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], 2)
        self.assertEqual(results[0]["present_position"], -1)
        self.assertEqual(results[0]["torque_enable"], 0)
        self.assertTrue(results[0]["valid"])

    def test_publish_atomic_snapshot_with_sequence(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "connection_status.json"
            watch_dynamixel.publish(target, port="/dev/ttyACM0", protocol=2.0,
                                    interval=3.0, sequence=2, results=[])
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["source"], "read_only_watch")
            self.assertEqual(payload["sequence"], 2)
            self.assertEqual(payload["results"], [])


if __name__ == "__main__":
    unittest.main()
