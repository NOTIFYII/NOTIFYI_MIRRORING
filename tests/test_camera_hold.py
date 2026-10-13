from types import SimpleNamespace

import pytest

from src.main import ControlLoop, load_posture_config
from src.robot.joint_mapper import JointMapper
from src.robot.dynamixel_driver import load_joints
from src.robot import joint_writer as module
from src.perception.posture_features import PostureAngles
from src.safety.gate import SafetyGate


def setup():
    config = load_posture_config()
    mapper = JointMapper(load_joints(), config["distribution"])
    return config, mapper, SafetyGate(mapper, config)


def test_observation_margin_does_not_expand_motion_goals():
    _, mapper, _ = setup()
    assert mapper.within_observation_limits("body_pitch", -347)
    assert not mapper.within_limits("body_pitch", -347)
    assert mapper.clamp_target("body_pitch", -347) == -340
    assert not mapper.within_observation_limits("body_pitch", -353)


def test_camera_head_s_follows_body_s_and_overrides_two_degree_pose():
    config, mapper, gate = setup()
    loop = ControlLoop(None, mapper, None, config, gate)
    targets = loop._targets_for_pose(PostureAngles(0, 30, 2, 1))
    assert targets == {"body_pitch": -340, "head_pitch": 681}
    assert loop._coupled_camera_targets(mapper.neutral_targets()) == mapper.neutral_targets()
    halfway = loop._coupled_camera_targets({"body_pitch": -170, "head_pitch": 1022})
    assert halfway["head_pitch"] == 851


def test_camera_follow_uses_each_slew_limited_step():
    config, mapper, gate = setup()
    loop = ControlLoop(None, mapper, None, config, gate)
    current = mapper.neutral_targets()
    desired = loop._targets_for_pose(PostureAngles(0, 30, 2, 1))
    for _ in range(30):
        body_limited = gate.limit_targets(current, desired)
        limited = gate.limit_targets(current, loop._coupled_camera_targets(body_limited))
        assert limited["head_pitch"] - 1022 == limited["body_pitch"] - 1
        assert all(abs(mapper.position_delta(name, current[name], target)) <= gate.max_step_ticks + 0.5
                   for name, target in limited.items())
        current = limited
    assert current == desired


class Sync:
    def __init__(self, *args):
        self.payloads = []
    def clearParam(self):
        self.payloads.clear()
    def addParam(self, motor_id, payload):
        self.payloads.append((motor_id, payload))
        return True
    def txPacket(self):
        return 0


class Packet:
    def __init__(self, body=-347):
        self.body = body
    def read4ByteTxRx(self, port, motor_id, address):
        return (self.body & 0xFFFFFFFF) if motor_id == 2 else 1052, 0, 0
    def getTxRxResult(self, code):
        return "no packet"
    def getRxPacketError(self, code):
        return "hardware error"


def writer(monkeypatch, body=-347):
    monkeypatch.setattr(module, "COMM_SUCCESS", 0)
    monkeypatch.setattr(module, "GroupSyncWrite", Sync)
    _, mapper, _ = setup()
    return module.JointWriter(Packet(body), object(), mapper.joint_ids(), joint_specs=mapper.joints)


def test_fresh_measured_hold_accepts_small_error_but_normal_goal_does_not(monkeypatch):
    w = writer(monkeypatch)
    with pytest.raises(module.WriterError):
        w.write_targets({"body_pitch": -347})
    measured = w.hold_current_positions()
    assert measured["body_pitch"] == -347
    assert w._sync.payloads[0] == (2, (-347 & 0xFFFFFFFF).to_bytes(4, "little"))
    w._packet.body = -353
    w._sync.payloads.clear()
    with pytest.raises(module.WriterError, match="허용 오차"):
        w.hold_current_positions()
    assert w._sync.payloads == []


def test_single_missing_packet_is_retried_but_hardware_error_is_not(monkeypatch):
    w = writer(monkeypatch)
    original = w._packet.read4ByteTxRx
    calls = []
    def read(port, motor_id, address):
        calls.append(motor_id)
        if calls == [2]:
            return 0, 1, 0
        return original(port, motor_id, address)
    w._packet.read4ByteTxRx = read
    assert w.read_positions()["body_pitch"] == -347
    assert calls == [2, 2, 3]
    calls.clear()
    def fault(*args):
        calls.append(2)
        return 0, 0, 0x80
    w._packet.read4ByteTxRx = fault
    with pytest.raises(module.WriterError, match="hardware error"):
        w.read_positions()
    assert calls == [2]


@pytest.mark.parametrize("loop_once", [False, True])
def test_startup_and_shutdown_hold_do_not_clamp_observed_position(monkeypatch, loop_once):
    config, mapper, gate = setup()
    w = writer(monkeypatch)
    writes = []
    original = w._send_targets
    def send(targets):
        writes.append(dict(targets))
        original(targets)
    w._send_targets = send
    w.prepare = lambda: None
    w.set_torque = lambda enabled: None
    buffer = SimpleNamespace(latest=lambda: None)
    loop = ControlLoop(buffer, mapper, w, config, gate)
    # 종료 플래그로 초기화와 finally의 유지 명령만 실행한다.
    if not loop_once:
        loop.stop_event.set()
    else:
        def one_iteration():
            loop.stop_event.set()
            return None
        buffer.latest = one_iteration
    loop.run()
    assert loop.error is None
    assert all(targets["body_pitch"] == -347 for targets in writes)
    assert len(writes) == 2
