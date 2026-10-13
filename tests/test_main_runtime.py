"""현재 main의 두 모터 계약과 선택 기능 분리를 하드웨어 없이 검증한다."""
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import main
from src.behavior.behavior_manager import BehaviorManager, BehaviorDecision
from src.behavior.executor import BehaviorExecutor
from src.perception.posture_features import MedianFilter, PostureAngles
from src.posture.classifier import classify
from src.robot.dynamixel_driver import load_joints
from src.robot.joint_mapper import JointMapper
from src.safety.gate import SafetyGate

ROOT = Path(__file__).resolve().parents[1]


def mapping():
    config = main.load_posture_config()
    mapper = JointMapper(load_joints(), config["distribution"])
    return config, mapper, SafetyGate(mapper, config)


def single_turn_mapping():
    config = main.load_posture_config()
    joints = load_joints()
    joints["body_pitch"].update(operating_mode=3, wrap_position=True,
                                min_position=0, max_position=4095)
    mapper = JointMapper(joints, config["distribution"])
    return config, mapper, SafetyGate(mapper, config)


def test_main_import_and_help_do_not_require_optional_modules():
    probe = """
import sys, importlib.abc
class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'pydantic', 'dotenv', 'vosk', 'sounddevice'} or fullname.startswith(('google.genai', 'src.gemini', 'src.audio')):
            raise ImportError('optional dependency used: ' + fullname)
sys.meta_path.insert(0, BlockOptional())
from src.main import main
sys.argv = ['notifyi', '--help']
main()
"""
    result = subprocess.run([sys.executable, "-c", probe], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "--calibrate" not in result.stdout
    assert "voice" not in result.stdout and "mirror" not in result.stdout


def test_body_range_accepts_confirmed_upright_position_with_small_positive_margin():
    _, mapper, _ = mapping()
    assert mapper.within_limits("body_pitch", 40)
    assert mapper.within_limits("body_pitch", 46)
    assert not mapper.within_limits("body_pitch", 47)
    assert mapper.neutral_targets()["body_pitch"] == 1


def test_head_range_accepts_confirmed_posture_and_rejects_outside_30_degrees():
    _, mapper, _ = mapping()
    assert mapper.within_limits("head_pitch", 1121)
    for position in (1022 - 341, 1022 + 341):
        assert mapper.within_limits("head_pitch", position)
    for position in (1022 - 342, 1022 + 342):
        assert not mapper.within_limits("head_pitch", position)
    assert mapper.neutral_targets()["head_pitch"] == 1022


def test_main_yaml_still_maps_only_two_driven_ids():
    config, mapper, gate = mapping()
    assert mapper.joint_ids() == {"body_pitch": 2, "head_pitch": 3}
    assert mapper.neutral_targets() == {"body_pitch": 1, "head_pitch": 1022}
    targets = mapper.to_targets(PostureAngles(0, 30, 2, 1))
    assert targets["body_pitch"] == -340
    assert targets["head_pitch"] > 1022
    assert all(mapper.within_limits(name, value) for name, value in targets.items())
    current = {"body_pitch": -53, "head_pitch": 1022}
    limited = gate.limit_targets(current, mapper.neutral_targets())
    assert limited["body_pitch"] >= -53
    assert all(abs(mapper.position_delta(name, current[name], value))
               <= gate.max_step_ticks + 0.5 for name, value in limited.items())


def test_observed_neck_is_not_clipped_to_two_degree_motor_limit():
    config, mapper, gate = mapping()
    observed = main.filter_observation(
        PostureAngles(time.monotonic(), 0, 20, 1), None, MedianFilter(1),
        config["angles"])
    label = classify(observed).label
    assert label == "forward_head" and observed.neck_pitch_deg == 20
    event = SimpleNamespace(decision=BehaviorDecision("gentle_remind"),
                            posture_label=label)
    action = BehaviorExecutor(config, gate).build(event)
    assert action.pose.neck_pitch_deg == 2
    assert BehaviorExecutor(config, gate).build(
        SimpleNamespace(decision=event.decision, posture_label="unknown")) is None


def test_stale_observation_cannot_satisfy_sustain_timer():
    manager = BehaviorManager(main.load_posture_config())
    now = time.monotonic()
    manager._policy_state.bad_since = now - 10
    manager.update_posture(PostureAngles(now - 10, 25, 20, 1))
    manager._evaluate()
    assert manager.poll_event() is None
    assert manager._policy_state.bad_since is None


def test_single_turn_boundary_jump_is_blocked_before_hardware_write():
    _, _, gate = single_turn_mapping()
    with pytest.raises(ValueError, match="위치 경계"):
        gate.validate_single_turn_transition(
            {"body_pitch": 1, "head_pitch": 1022},
            {"body_pitch": 4080, "head_pitch": 1022})
    gate.validate_single_turn_transition(
        {"body_pitch": 4043, "head_pitch": 1022},
        {"body_pitch": 4026, "head_pitch": 1022})


def test_lost_person_captures_measured_position_instead_of_pending_goal():
    config, mapper, gate = mapping()
    positions = {"body_pitch": -53, "head_pitch": 1022}
    writer = SimpleNamespace(read_positions=lambda: positions)
    loop = main.ControlLoop(None, mapper, writer, config, gate)
    loop.commanded = {"body_pitch": 3900, "head_pitch": 1030}
    loop._capture_hold_position()
    targets, torque = loop._posture_trigger_output(time.monotonic(), False,
                                                   "person_lost_hold")
    assert targets == positions and torque is True


@pytest.mark.parametrize("model_failure", [False, True])
@pytest.mark.parametrize("shutdown_failure", [False, True])
def test_run_exit_or_model_failure_never_homes_or_releases_torque(
        monkeypatch, tmp_path, model_failure, shutdown_failure):
    config = main.load_posture_config()
    config["experiment"]["log_dir"] = str(tmp_path)
    monkeypatch.setattr(main, "load_posture_config", lambda: config)
    motor_calls = []
    writer = SimpleNamespace(
        write_targets=lambda _: motor_calls.append("write"),
        set_torque=lambda _: motor_calls.append("torque"),
        prepare=lambda: motor_calls.append("prepare"))
    @contextmanager
    def fake_bus():
        yield (None, None)
    monkeypatch.setattr(main, "open_bus", fake_bus)
    monkeypatch.setattr(main, "build_writer", lambda *_: writer)
    monkeypatch.setattr(main, "check_pose_within_limits", lambda *_: None)
    @contextmanager
    def fake_camera(*_):
        yield None
    @contextmanager
    def fake_model(*_):
        if model_failure:
            raise RuntimeError("model load failed")
        yield None
    monkeypatch.setattr(main, "CameraStream", fake_camera)
    monkeypatch.setattr(main, "PoseEstimator", fake_model)
    class FakeControl:
        def __init__(self, *_):
            self.ident = None
            self.stop_event = SimpleNamespace(set=lambda: None, is_set=lambda: True)
            self.error = None
            self.safe_stop_reason = None
        def start(self):
            self.ident = 1
        def join(self, **_):
            assert self.ident is not None, "cannot join thread before it is started"
            if shutdown_failure:
                self.error = RuntimeError("hold not confirmed")
        def is_alive(self):
            return False
    monkeypatch.setattr(main, "ControlLoop", FakeControl)
    args = SimpleNamespace(move=True, no_preview=True, condition="posture_trigger",
                           no_correction=True, camera=None, model=None)
    if model_failure:
        with pytest.raises(RuntimeError, match="model load failed"):
            main.run(args)
    elif shutdown_failure:
        with pytest.raises(SystemExit) as exc:
            main.run(args)
        assert exc.value.code == 1
        assert "shutdown_hold_failed" in next(tmp_path.glob("*.jsonl")).read_text()
    else:
        assert main.run(args) == 0
    assert motor_calls == []


@pytest.mark.parametrize("fault", [False, True])
def test_control_thread_exit_holds_measured_position_without_zero_or_torque_off(fault):
    config, mapper, gate = mapping()
    positions = {"body_pitch": 4043, "head_pitch": 1022}
    writes, torques = [], []
    writer = SimpleNamespace(
        read_positions=lambda: positions,
        write_targets=lambda values: writes.append(dict(values)),
        set_torque=lambda value: torques.append(value))
    loop = main.ControlLoop(None, mapper, writer, config, gate)
    loop.commanded = {"body_pitch": 3900, "head_pitch": 1030}
    loop._hardware_initialized = True
    def unfinished_motion():
        if fault:
            raise RuntimeError("camera timeout")
    loop._loop = unfinished_motion
    loop.run()
    assert writes == [positions]
    assert torques == []


def test_boundary_crossing_stops_without_sending_wrapped_goal():
    config, mapper, gate = single_turn_mapping()
    positions = mapper.neutral_targets()
    writes, torques = [], []
    writer = SimpleNamespace(
        prepare=lambda: None,
        read_positions=lambda: positions,
        write_targets=lambda values: writes.append(dict(values)),
        set_torque=lambda value: torques.append(value))
    buffer = SimpleNamespace(latest=lambda: PostureAngles(time.monotonic() - 0.01, 25, 20, 1))
    loop = main.ControlLoop(buffer, mapper, writer, config, gate)
    event = SimpleNamespace(decision=BehaviorDecision("gentle_remind"), posture_label="slouch")
    loop.submit_behavior(BehaviorExecutor(config, gate).build(event))
    loop.run()
    assert "위치 경계" in str(loop.error)
    assert writes == [positions]  # 종료 시 실측 hold만 전송
    assert torques == []
