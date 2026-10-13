from unittest.mock import patch

import pytest

from scripts.inspect_motor_coordinates import (
    FIELDS, coordinate_plan, read_snapshot, signed32,
)
from src.robot.dynamixel_driver import BusError


class ReadOnlyPacket:
    def __init__(self, model=1090):
        self.model = model
        self.reads = []

    def ping(self, port, motor_id):
        return self.model, 0, 0

    def read1ByteTxRx(self, port, motor_id, address):
        self.reads.append(address)
        return 3 if address == 11 else 0, 0, 0

    def read4ByteTxRx(self, port, motor_id, address):
        self.reads.append(address)
        return 0xFFFFFFFF if address == 20 else 40, 0, 0


def test_signed_offsets_and_positions():
    assert signed32(0xFFFFFFFF) == -1
    assert signed32(0x80000000) == -(1 << 31)
    assert signed32(40) == 40


def test_snapshot_uses_only_ping_and_reads_with_signed_offset():
    packet = ReadOnlyPacket()
    with patch("src.robot.dynamixel_driver.COMM_SUCCESS", 0):
        result = read_snapshot(packet, object(), 2)
    assert result["homing_offset"] == -1
    assert result["present_position"] == 40
    assert set(packet.reads) == {address for address, _ in FIELDS.values()}


def test_unknown_model_is_rejected_before_register_reads():
    packet = ReadOnlyPacket(1060)
    with patch("src.robot.dynamixel_driver.COMM_SUCCESS", 0):
        with pytest.raises(BusError):
            read_snapshot(packet, object(), 2)
    assert packet.reads == []


def test_body_plan_exposes_crossing_without_approving_motion():
    plan = coordinate_plan({"present_position": 40}, {
        "zero_position": 1, "relative_min_deg": -30, "relative_max_deg": 4,
    })
    assert plan["unwrapped_endpoints"] == [-340, 46]
    assert plan["modulo_endpoints"] == [3756, 46]
    assert plan["crosses_single_turn_boundary"]
    assert plan["status"] == "inspection_only_not_approved_for_motion"


def test_head_plan_stays_inside_single_turn():
    plan = coordinate_plan({"present_position": 1121}, {
        "zero_position": 1022, "relative_min_deg": -30, "relative_max_deg": 30,
    })
    assert plan["unwrapped_endpoints"] == [681, 1363]
    assert not plan["crosses_single_turn_boundary"]
