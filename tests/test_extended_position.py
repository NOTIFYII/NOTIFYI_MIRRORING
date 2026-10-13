from unittest.mock import patch

import pytest

from src.main import load_posture_config
from src.perception.posture_features import PostureAngles
from src.robot.dynamixel_driver import load_joints
from src.robot.joint_mapper import JointMapper, MappingError
from src.robot import joint_writer as module
from scripts.enable_body_extended_position import apply_transition


def mapper():
    return JointMapper(load_joints(), load_posture_config()["distribution"])


def test_negative_goals_and_linear_deltas_never_wrap():
    m = mapper()
    assert m.to_targets(PostureAngles(0, 30, 2, 1))["body_pitch"] == -340
    assert m.position_delta("body_pitch", 1, -15) == -16
    assert m.normalize_position("body_pitch", -15) == -15
    assert m.clamp_target("body_pitch", 3756) == 46
    assert not m.within_limits("body_pitch", 4097)
    assert not m.within_limits("body_pitch", -341)


def test_extended_mode_rejects_modulo_configuration():
    joints = load_joints()
    joints["body_pitch"]["wrap_position"] = True
    with pytest.raises(MappingError):
        JointMapper(joints, load_posture_config()["distribution"])


class Sync:
    def __init__(self, *args):
        self.payloads = []
    def clearParam(self):
        self.payloads.clear()
    def addParam(self, motor_id, payload):
        self.payloads.append((motor_id, payload))
        return True
    def txPacket(self):
        return module.COMM_SUCCESS


class Packet:
    def __init__(self):
        self.mode = 3
        self.torque = 1
        self.writes = []
    def ping(self, *args):
        return 1090, 0, 0
    def read1ByteTxRx(self, port, motor_id, address):
        return {11: self.mode, 64: self.torque}.get(address, 0), 0, 0
    def read4ByteTxRx(self, port, motor_id, address):
        return {132: 39, 116: 39, 48: 4095}.get(address, 0), 0, 0
    def write1ByteTxRx(self, port, motor_id, address, value):
        self.writes.append((motor_id, address, value))
        if address == 64:
            self.torque = value
        if address == 11:
            self.mode = value
        return 0, 0


def make_writer(monkeypatch):
    monkeypatch.setattr(module, "GroupSyncWrite", Sync)
    monkeypatch.setattr(module, "COMM_SUCCESS", 0)
    packet = Packet()
    m = mapper()
    return module.JointWriter(packet, object(), m.joint_ids(), joint_specs=m.joints), packet


def test_writer_preserves_signed_body_but_normalizes_head(monkeypatch):
    writer, packet = make_writer(monkeypatch)
    packet.read4ByteTxRx = lambda port, motor_id, address: (0xFFFFFFCB, 0, 0)
    assert writer.read_positions() == {"body_pitch": -53, "head_pitch": 4043}
    writer.write_targets({"body_pitch": -340})
    assert writer._sync.payloads == [(2, (-340 & 0xFFFFFFFF).to_bytes(4, "little"))]
    with pytest.raises(module.WriterError):
        writer.write_targets({"body_pitch": 3756})


def test_mode_mismatch_fails_without_writes(monkeypatch):
    writer, packet = make_writer(monkeypatch)
    with pytest.raises(module.WriterError, match="Operating Mode"):
        writer.verify_modes()
    assert packet.writes == []


def test_conversion_backs_up_then_changes_only_id2_and_never_turns_on(tmp_path):
    packet = Packet()
    spec = load_joints()["body_pitch"]
    backup = tmp_path / "backup.json"
    with patch("src.robot.dynamixel_driver.COMM_SUCCESS", 0):
        after = apply_transition(packet, object(), spec, backup)
    assert backup.exists()
    assert after["operating_mode"] == 4 and after["torque_enable"] == 0
    assert packet.writes == [(2, 64, 0), (2, 11, 4)]


def test_existing_backup_prevents_all_writes(tmp_path):
    packet = Packet()
    backup = tmp_path / "backup.json"
    backup.write_text("original")
    with patch("src.robot.dynamixel_driver.COMM_SUCCESS", 0):
        with pytest.raises(FileExistsError):
            apply_transition(packet, object(), load_joints()["body_pitch"], backup)
    assert packet.writes == [] and backup.read_text() == "original"


@pytest.mark.parametrize("position,offset", [(4097, 0), (39, 100)])
def test_unexpected_coordinates_prevent_backup_and_all_writes(tmp_path, position, offset):
    packet = Packet()
    original = packet.read4ByteTxRx
    packet.read4ByteTxRx = lambda port, motor_id, address: (
        (position, 0, 0) if address == 132 else (offset, 0, 0) if address == 20
        else original(port, motor_id, address))
    backup = tmp_path / "backup.json"
    with patch("src.robot.dynamixel_driver.COMM_SUCCESS", 0):
        with pytest.raises(ValueError):
            apply_transition(packet, object(), load_joints()["body_pitch"], backup)
    assert packet.writes == [] and not backup.exists()


def test_drift_after_torque_off_prevents_mode_write(tmp_path):
    packet = Packet()
    original = packet.read4ByteTxRx
    packet.read4ByteTxRx = lambda port, motor_id, address: (
        (100, 0, 0) if address == 132 and packet.torque == 0
        else original(port, motor_id, address))
    with patch("src.robot.dynamixel_driver.COMM_SUCCESS", 0):
        with pytest.raises(ValueError):
            apply_transition(packet, object(), load_joints()["body_pitch"], tmp_path / "backup.json")
    assert packet.writes == [(2, 64, 0)]


def test_mode_match_and_offset_check_do_not_write(monkeypatch):
    writer, packet = make_writer(monkeypatch)
    packet.read1ByteTxRx = lambda port, motor_id, address: (
        (4 if motor_id == 2 else 3) if address == 11 else 0, 0, 0)
    writer.verify_modes()
    assert packet.writes == []
    packet.read4ByteTxRx = lambda *args: (100, 0, 0)
    with pytest.raises(module.WriterError, match="Homing Offset"):
        writer.verify_modes()
    assert packet.writes == []


def test_extended_control_crosses_zero_without_wrapped_goal():
    import time
    from types import SimpleNamespace
    from src.main import ControlLoop
    from src.safety.gate import SafetyGate
    from src.behavior.executor import BehaviorExecutor
    from src.behavior.behavior_manager import BehaviorDecision

    m = mapper()
    config = load_posture_config()
    gate = SafetyGate(m, config)
    positions = m.neutral_targets()
    writes, torques = [], []
    buffer = SimpleNamespace(latest=lambda: PostureAngles(time.monotonic() - 0.01, 25, 20, 1))
    def write(values):
        writes.append(dict(values))
        if values["body_pitch"] < 0:
            loop.stop_event.set()
    writer = SimpleNamespace(prepare=lambda: None, read_positions=lambda: positions,
                             write_targets=write, set_torque=lambda value: torques.append(value))
    loop = ControlLoop(buffer, m, writer, config, gate)
    loop.submit_behavior(BehaviorExecutor(config, gate).build(SimpleNamespace(
        decision=BehaviorDecision("gentle_remind"), posture_label="slouch")))
    loop.run()
    assert loop.error is None
    assert writes[0]["body_pitch"] < 0
    assert all(-340 <= values["body_pitch"] <= 46 for values in writes)
    assert torques == [True]
