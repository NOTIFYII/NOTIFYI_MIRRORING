from types import SimpleNamespace

import pytest

from src.main import ControlLoop, load_posture_config
from src.perception.posture_features import PostureAngles
from src.posture.pose_buffer import PoseBuffer
from src.posture.recovery import RecoveryDetector
from src.robot.dynamixel_driver import load_joints
from src.robot.joint_mapper import JointMapper
from src.telemetry.recovery_latency import RecoveryLatency


def sample(stamp, torso=0, confidence=1):
    return PostureAngles(stamp, torso, 0, confidence)


def test_requires_two_unique_frames_and_time_span():
    detector = RecoveryDetector()
    assert not detector.update(sample(1), 1.5).confirmed
    assert not detector.update(sample(1), 1.5).confirmed
    assert not detector.update(sample(1.1), 1.6).confirmed
    assert detector.update(sample(1.6), 2.1).confirmed


@pytest.mark.parametrize("middle", [sample(1.5, torso=30), sample(1.5, confidence=0), sample(1.5, confidence=0.2)])
def test_bad_unknown_and_low_confidence_break_consecutive_frames(middle):
    detector = RecoveryDetector()
    detector.update(sample(1), 1.4)
    assert not detector.update(middle, 1.9).confirmed
    assert not detector.update(sample(2), 2.4).confirmed
    assert detector.update(sample(2.5), 2.9).confirmed


def test_stale_future_and_long_gap_are_not_recovery():
    detector = RecoveryDetector()
    assert not detector.update(sample(1), 3).confirmed
    assert not detector.update(sample(4), 3).confirmed
    assert not detector.update(sample(5), 5.5).confirmed
    assert not detector.update(sample(7), 7.5).confirmed


def test_control_requires_confirmation_even_when_filtered_frame_is_good():
    config = load_posture_config()
    mapper = JointMapper(load_joints(), config["distribution"])
    buffer = PoseBuffer()
    loop = ControlLoop(buffer, mapper, None, config)
    loop.submit_behavior(SimpleNamespace(pose=sample(0, torso=30), duration_sec=1, hold_until_good=True))
    loop._behavior_started_at = 1
    detector = RecoveryDetector()
    first = sample(2)
    buffer.push(first, detector.update(first, 2.5))
    assert loop._recovery_label(first, 2.5, "good") == "unknown"
    loop._posture_trigger_output(2.5, True, "tracking", "unknown")
    assert loop._behavior_action is not None
    second = sample(2.5)
    confirmation = detector.update(second, 3)
    buffer.push(second, confirmation)
    assert loop._recovery_label(second, 3, "slouch") == "good"
    assert loop._recovery_label(second, 4, "good") == "unknown"
    # 샘플 시각이 다르면 다른 프레임의 회복 확인을 사용하지 않는다.
    assert loop._recovery_label(first, 3, "good") == "unknown"
    loop._posture_trigger_output(3, True, "tracking", "good")
    assert loop._behavior_action is None and loop._behavior_returning


def test_pre_intervention_confirmation_cannot_cancel_new_action():
    config = load_posture_config()
    mapper = JointMapper(load_joints(), config["distribution"])
    buffer = PoseBuffer()
    loop = ControlLoop(buffer, mapper, None, config)
    loop._behavior_started_at = 2.2
    detector = RecoveryDetector()
    detector.update(sample(2), 2.4)
    current = sample(2.5)
    buffer.push(current, detector.update(current, 2.9))
    assert loop._recovery_label(current, 3, "slouch") == "slouch"
    current = sample(3)
    buffer.push(current, detector.update(current, 3.4))
    assert loop._recovery_label(current, 3.4, "slouch") == "good"


def test_fast_latency_has_distinct_name_from_filtered_baseline():
    tracker = RecoveryLatency()
    detector = RecoveryDetector()
    tracker.observe(1, 1.5, 1.51, "slouch", "slouch")
    detector.update(sample(1, torso=30), 1.5)
    first = sample(2)
    tracker.observe(2, 2.5, 2.51, "good", "slouch")
    detector.update(first, 2.51)
    second = sample(2.5)
    tracker.observe(2.5, 3, 3.01, "good", "slouch")
    confirmation = detector.update(second, 3.01)
    tracker.recovery_confirmed(confirmation, 3.01)
    rows = []
    tracker.flush(SimpleNamespace(record=lambda event, **fields: rows.append((event, fields))))
    assert len(rows) == 1 and rows[0][0] == "fast_recovery_latency"
    assert rows[0][1]["capture_to_recovery_ms"] == 1010


def test_bad_sustain_and_motor_limits_are_unchanged():
    config = load_posture_config()
    assert config["correction"]["sustain_seconds"] == 3
    joints = load_joints()
    assert joints["body_pitch"]["min_position"] == -340
    assert joints["body_pitch"]["max_position"] == 46


def test_higher_fps_can_confirm_after_minimum_span_not_only_two_frame_interval():
    detector = RecoveryDetector()
    result = None
    for index in range(5):
        stamp = 1 + index * 0.1
        result = detector.update(sample(stamp), stamp + 0.1)
    assert result.confirmed
    assert result.first_capture_at >= 1


def test_disabling_fast_recovery_restores_filtered_behavior():
    config = load_posture_config()
    config["recovery"]["enabled"] = False
    mapper = JointMapper(load_joints(), config["distribution"])
    loop = ControlLoop(PoseBuffer(), mapper, None, config)
    assert loop._recovery_label(sample(1), 1.5, "good") == "good"
