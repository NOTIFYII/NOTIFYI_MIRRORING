from src.perception.motion_observation_gate import MotionObservationGate
from src.main import ControlLoop, load_posture_config
from src.posture.pose_buffer import PoseBuffer
from src.robot.joint_mapper import JointMapper
from src.robot.dynamixel_driver import load_joints
from src.perception.posture_features import PostureAngles
from src.posture.recovery import RecoveryConfirmation


def gate():
    return MotionObservationGate(lambda _, a, b: b - a)


def stable(g):
    for t in (0, 0.1, 0.3, 0.6, 0.7):
        g.update(t, {"body": 0}, {"body": 0}, t)


def test_only_post_settling_captures_allowed():
    g = gate()
    stable(g)
    assert g.reason(0.7, 0.7) == "ready"
    assert g.reason(0.1, 0.7) == "capture_before_stable"


def test_move_during_inference_rejects_pre_move_frame():
    g = gate()
    stable(g)
    g.update(0.8, {"body": 100}, {"body": 0}, 0.8)
    assert g.reason(0.7, 0.9) == "robot_moving"
    for t in (1, 1.1, 1.3, 1.6, 1.7):
        g.update(t, {"body": 100}, {"body": 100}, t)
    assert g.reason(0.7, 1.7) == "capture_before_stable"
    assert g.reason(1.7, 1.7) == "ready"


def test_encoder_movement_and_staleness_block_evaluation():
    g = gate()
    stable(g)
    g.update(0.8, {"body": 0}, {"body": 8}, 0.8)
    assert g.reason(0.8, 0.8) == "robot_moving"
    assert g.reason(1.5, 1.5) == "motor_observation_stale"


def test_control_blocks_good_even_when_fast_recovery_disabled():
    config = load_posture_config()
    config["recovery"]["enabled"] = False
    loop = ControlLoop(PoseBuffer(), JointMapper(load_joints(), config["distribution"]),
                       None, config)
    loop.observation_gate = gate()
    sample = PostureAngles(0.5, 0, 0, 1)
    assert loop._recovery_label(sample, 0.5, "good") == "unknown"


def test_old_confirmation_cannot_trigger_return_after_camera_move():
    config = load_posture_config()
    buffer = PoseBuffer()
    sample = PostureAngles(0.7, 0, 0, 1)
    buffer.push(sample, RecoveryConfirmation(0.7, True, 0.6, 0.7))
    loop = ControlLoop(buffer, JointMapper(load_joints(), config["distribution"]), None, config)
    loop.observation_gate = gate()
    stable(loop.observation_gate)
    assert loop._recovery_label(sample, 0.7, "good") == "good"
    loop.observation_gate.update(0.8, {"body": 100}, {"body": 0}, 0.8)
    assert loop._recovery_label(sample, 0.9, "good") == "unknown"

