#!/usr/bin/env python3
"""카메라로 본 나쁜 자세에만 미리 정한 동작으로 반응한다.

정상 자세에서는 로봇을 중립에 두고 움직이지 않는다. 나쁜 자세가 정책에
정해진 시간 이상 지속될 때만 미리 정의된 고정 포즈를 실행하고, 사용자가
정상 자세로 돌아오면 중립으로 복귀한다.

기본은 모터를 건드리지 않는다. 실제로 움직이려면 --move 를 붙인다.

    .venv-mp-pi3/bin/python -m src.main              # 프리뷰만
    .venv-mp-pi3/bin/python -m src.main --move       # 로봇 구동
"""

import argparse
import os
import sys
import threading
import time
from contextlib import ExitStack
from pathlib import Path

import cv2
import yaml

from src.camera.camera_stream import CameraError, CameraStream  # noqa: E402
from src.perception.pose_estimator import (  # noqa: E402
    PoseEstimator, draw_angle_bar, draw_overlay, draw_skeleton,
)
from src.perception.posture_features import (  # noqa: E402
    MedianFilter, PostureAngles, extract_angles, smooth, person_confidence,
)
from src.perception.motion_observation_gate import MotionObservationGate
from src.perception.side_observation import side_candidate
from src.posture.pose_buffer import PoseBuffer  # noqa: E402
from src.posture.recovery import RecoveryDetector  # noqa: E402
from src.posture.classifier import classify  # noqa: E402
from src.robot.dynamixel_driver import (  # noqa: E402
    BusError, PROJECT_ROOT, describe_hardware_error, install_signal_guards,
    load_joints, open_bus, ping_all, read_hardware_error,
)
from src.robot.joint_mapper import JointMapper, MappingError, TICKS_PER_DEG  # noqa: E402
from src.robot.joint_writer import JointWriter, WriterError  # noqa: E402
from src.behavior.behavior_manager import BehaviorManager
from src.behavior.executor import BehaviorExecutor  # noqa: E402
from src.safety.supervisor import (  # noqa: E402
    STATE_SAFE_STOP, STATE_TRACKING, IdlePolicy,
)
from src.safety.gate import SafetyGate  # noqa: E402
from src.safety.health import HealthMonitor, SafeStopRequested  # noqa: E402
from src.telemetry.event_log import EventLogger  # noqa: E402
from src.telemetry.response_tracker import ResponseTracker  # noqa: E402
from src.telemetry.performance import PerformanceWindow  # noqa: E402
from src.telemetry.recovery_latency import RecoveryLatency  # noqa: E402
from src.runtime.instance import AlreadyRunning, instance_lock  # noqa: E402

POSTURE_CONFIG = PROJECT_ROOT / "config" / "posture.yaml"


def load_posture_config(path=POSTURE_CONFIG):
    if not Path(path).exists():
        raise FileNotFoundError(f"설정 파일이 없습니다: {path}")
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def filter_observation(sample, previous, median, angles_config):
    """관측 지표를 필터링한다. 모터 허용 각도는 여기서 적용하지 않는다."""
    return smooth(previous, median.apply(sample),
                  angles_config["smoothing_alpha"],
                  angles_config.get("neck_smoothing_alpha"))


class ControlLoop(threading.Thread):
    """고정 주기로 중립 또는 고정 개입 포즈를 모터에 쓰는 스레드."""

    def __init__(self, buffer, mapper, writer, config, safety_gate=None, recovery_latency=None):
        super().__init__(name="control", daemon=True)
        echo = config["echo"]
        motion = config["motion"]
        self.buffer = buffer
        self.mapper = mapper
        self.motion_enabled = True
        self._hardware_initialized = False
        self._holding_position = False
        self._output_is_hold = False
        recovery_config = config.get("recovery") or {}
        self._fast_recovery = bool(recovery_config.get("enabled", False))
        self._recovery_max_age = float(recovery_config.get("max_age_sec", 1.0))
        self.writer = writer
        self.recovery_latency = recovery_latency
        self.period = 1.0 / echo["control_hz"]
        self.safety_gate = safety_gate or SafetyGate(mapper, config)
        distance_fn = getattr(self.mapper, "position_delta", None)
        if distance_fn is None:
            distance_fn = lambda name, current, target: target - current
        self.observation_gate = (MotionObservationGate(
            distance_fn, **config.get("motion_observation", {}))
            if writer is not None else None)
        self.policy = IdlePolicy(
            motion["return_to_neutral_sec"], motion["idle_release_sec"],
            grace_seconds=motion.get("person_lost_grace_sec", 0.5),
            distance_fn=distance_fn)
        self.neutral = mapper.neutral_targets()
        self._rest_targets = dict(self.neutral)
        self.stop_event = threading.Event()
        self.error = None

        self.state = "starting"
        self.commanded = dict(self.neutral)
        self.measured_positions = None
        self.measured_at = None
        self._next_position_read = 0.0
        self._position_read_period = 0.2
        self._position_max_age = 0.5
        self._max_observation_age = float(
            ((config.get("safety") or {}).get("health") or {}).get(
                "camera_timeout_sec", 2.0))
        self.last_targets = dict(self.neutral)
        self._was_person_visible = False
        # 준비 전 객체 생성 시각을 정상 제어 heartbeat로 사용하지 않는다.
        self.heartbeat_at = None
        self.control_phase = "waiting_for_start"
        self.safe_stop_reason = None
        self._behavior_lock = threading.Lock()
        self._behavior_action = None
        self._behavior_started_at = None
        self._behavior_returning = False
        self._behavior_return_started_at = None
        self._behavior_settled_at = None
        self._behavior_release_sec = motion["idle_release_sec"]
        self._behavior_released = False
        camera_gimbal = config.get("camera_gimbal") or {}
        self._camera_gimbal_enabled = bool(camera_gimbal.get("enabled", False))
        self._camera_gimbal_joint = camera_gimbal.get(
            "joint", getattr(mapper, "neck_joint", "neck_pitch"))
        self._camera_body_joint = camera_gimbal.get("body_joint")
        self._camera_tick_ratio = float(camera_gimbal.get("tick_ratio", 1.0))
        if self._camera_tick_ratio not in (-1.0, 1.0):
            raise MappingError("camera_gimbal.tick_ratio는 -1 또는 1이어야 합니다")
        if self._camera_gimbal_enabled and self._camera_body_joint:
            if self._camera_body_joint not in mapper.joints or self._camera_gimbal_joint not in mapper.joints:
                raise MappingError("카메라 보정 관절이 설정에 없습니다")

    def _coupled_camera_targets(self, targets):
        result = dict(targets)
        if not self._camera_gimbal_enabled or not self._camera_body_joint:
            return result
        body, head = self._camera_body_joint, self._camera_gimbal_joint
        delta = self.mapper.position_delta(body, self.neutral[body], result[body])
        result[head] = self.mapper.clamp_target(
            head, self.neutral[head] + self._camera_tick_ratio * delta)
        return result

    def _recovery_label(self, sample, now, label):
        if (self.observation_gate is not None and sample is not None
                and self.observation_gate.reason(sample.timestamp, now) != "ready"):
            return "unknown"
        if not self._fast_recovery:
            return label
        confirmation = getattr(self.buffer, "latest_recovery", lambda: None)()
        with self._behavior_lock:
            started = self._behavior_started_at
        if (confirmation is not None and sample is not None and confirmation.confirmed
                and confirmation.timestamp == sample.timestamp
                and 0 <= now - confirmation.timestamp <= self._recovery_max_age
                and (started is None or confirmation.first_capture_at >= started)):
            return "good"
        return "unknown" if label == "good" else label

    def _targets_for_pose(self, pose):
        """고정 포즈를 만들고 탑재 카메라 관절은 역회전으로 보정한다."""
        targets = dict(self.mapper.to_targets(pose))
        if not self._camera_gimbal_enabled:
            return targets
        if self._camera_body_joint:
            return self._coupled_camera_targets(targets)

        joint = self._camera_gimbal_joint
        joints = getattr(self.mapper, "joints", {})
        spec = joints.get(joint)
        if spec is None or joint not in targets:
            return targets
        reference = self._rest_targets.get(joint, self.neutral.get(joint))
        if reference is None:
            return targets

        torso_delta_deg = 0.0
        for name, body_spec in joints.items():
            if name == joint or name not in targets:
                continue
            previous = self._rest_targets.get(name)
            direction = float(body_spec.get("direction", 1))
            if previous is None or direction == 0:
                continue
            torso_delta_deg += (
                (targets[name] - previous) / (TICKS_PER_DEG * direction))

        neck_direction = float(spec.get("direction", 1))
        raw = reference - neck_direction * torso_delta_deg * TICKS_PER_DEG
        targets[joint] = int(round(max(
            spec["min_position"], min(spec["max_position"], raw))))
        return targets

    def submit_behavior(self, action):
        """고정된 행동을 다음 제어 tick부터 재생한다."""
        if action is None:
            return False
        with self._behavior_lock:
            self._behavior_action = action
            self._behavior_started_at = time.monotonic()
            if self.recovery_latency is not None:
                self.recovery_latency.start(self._behavior_started_at)
            self._behavior_returning = False
            self._behavior_return_started_at = None
            self._behavior_settled_at = None
            self._behavior_released = False
        return True

    def safe_stop(self, reason):
        """제어를 중지하고 제어 스레드의 실측 위치 유지 경로로 보낸다."""
        self.safe_stop_reason = str(reason)
        self.state = STATE_SAFE_STOP
        with self._behavior_lock:
            self._behavior_action = None
            self._behavior_started_at = None
            self._behavior_returning = False
            self._behavior_return_started_at = None
            self._behavior_settled_at = None
            self._behavior_released = False
        self.stop_event.set()

    def _behavior_pose(self, now):
        with self._behavior_lock:
            action = self._behavior_action
            started = self._behavior_started_at
            if action is None or started is None:
                return None
            # 과장 포즈는 사용자가 정상 자세로 돌아올 때까지 유지한다.
            if (not getattr(action, "hold_until_good", False)
                    and now - started >= action.duration_sec):
                self._behavior_action = None
                self._behavior_started_at = None
                self._behavior_returning = True
                self._behavior_return_started_at = now
                self._behavior_settled_at = None
                return None
            return action.pose

    def _cancel_behavior(self, now):
        """정상 자세가 확인되면 고정 포즈를 중단하고 복귀한다."""
        with self._behavior_lock:
            if self._behavior_action is not None:
                self._behavior_action = None
                self._behavior_started_at = None
                self._behavior_returning = True
                self._behavior_return_started_at = now
                self._behavior_settled_at = None
                if self.recovery_latency is not None:
                    baseline = (self.measured_positions if self.measured_at is not None
                                and now - self.measured_at <= self._position_max_age else None)
                    self.recovery_latency.return_requested(time.monotonic(), baseline, self.neutral)

    def _at_neutral(self, now=None):
        if self.writer is not None and self.motion_enabled:
            if (self.measured_positions is None or self.measured_at is None
                    or (now is not None
                        and now - self.measured_at > self._position_max_age)):
                return False
            positions = self.measured_positions
        else:
            positions = self.commanded
        distance_fn = getattr(self.mapper, "position_delta", None)
        if distance_fn is None:
            distance_fn = lambda name, current, target: target - current
        return all(
            name in positions
            and abs(distance_fn(name, positions[name], value)) <= 15
            for name, value in self.neutral.items())

    def _capture_hold_position(self, allow_outside_limits=False):
        """감지 손실 순간의 실측 위치를 새 목표로 잡아 진행 중인 이동을 멈춘다."""
        if self.writer is None:
            return
        holder = getattr(self.writer, "hold_current_positions", None)
        positions = holder() if callable(holder) else self.writer.read_positions()
        self._holding_position = callable(holder)
        if set(positions) != set(self.mapper.joints):
            raise WriterError("감지 손실 시 모든 관절의 위치를 확인하지 못했습니다")
        for name, position in positions.items():
            observed_limits = getattr(self.mapper, "within_observation_limits", self.mapper.within_limits)
            if not allow_outside_limits and not observed_limits(name, position):
                raise WriterError(f"{name}: 감지 손실 시 실측 위치가 운용 범위 밖입니다")
        self.measured_positions = dict(positions)
        self.measured_at = time.monotonic()
        self.commanded = dict(positions)

    def _posture_trigger_output(self, now, person_visible, state,
                                posture_label="unknown"):
        """반응 모드의 목표와 토크 상태를 계산한다.

        대기 중에는 시작 시점의 기준 자세를 토크로 유지하고, 이벤트가 있을
        때만 고정 포즈로 이동한다. 정상 자세가 확인되면 중립으로 복귀하며
        토크는 유지한다. 사람 미감지 시 목표를 유지하고 자동 복귀하지 않는다.
        """
        self._output_is_hold = False
        if not person_visible:
            self._output_is_hold = True
            # 미감지를 zero 복귀 신호로 취급하지 않는다. 현재 목표를 유지해
            # 카메라 가림/프레임 누락 때 로봇이 갑자기 움직이지 않게 한다.
            with self._behavior_lock:
                if self._behavior_returning:
                    self._behavior_return_started_at = now
                    self._behavior_settled_at = None
            return dict(self.commanded), True

        behavior_pose = self._behavior_pose(now)
        if behavior_pose is not None:
            if (state == STATE_TRACKING
                    and posture_label != "good"):
                return self._targets_for_pose(behavior_pose), True
            # 정상 자세가 확인된 경우에만 개입을 끝내고 중립으로 복귀한다.
            self._cancel_behavior(now)

        with self._behavior_lock:
            returning = self._behavior_returning
            started = self._behavior_return_started_at

        if returning:
            if self._at_neutral(now):
                if self._behavior_settled_at is None:
                    self._behavior_settled_at = now
                if now - self._behavior_settled_at >= self._behavior_release_sec:
                    with self._behavior_lock:
                        self._behavior_returning = False
                        self._behavior_return_started_at = None
                        self._behavior_settled_at = None
                        self._behavior_released = True
                    return dict(self.commanded), True
            else:
                self._behavior_settled_at = None
            if (started is not None
                    and now - started >= self.policy.return_seconds
                    and not self._at_neutral(now)):
                raise WriterError(
                    "개입 후 중립 복귀 시간 초과: "
                    "실측 위치가 중립에 도달하지 않았습니다")
            return dict(self.neutral), True

        with self._behavior_lock:
            released = self._behavior_released
        if released:
            # 한 번 중립 복귀를 끝낸 뒤에는 다음 tick에서 시작 기준 자세로
            # 되돌아가지 않고, 중립을 유지한 채 토크를 유지한다.
            return dict(self.neutral), True

        # 평상시에는 사용자의 자세를 따라가지 않고 시작 시점의 기준 자세를
        # 유지한다. 토크를 풀면 세로 컬럼이 자중으로 무너질 수 있다.
        self._output_is_hold = True
        return dict(self._rest_targets), True

    def run(self):
        try:
            self._loop()
        except Exception as exc:                      # 스레드 밖으로 전달
            self.error = exc
            self.safe_stop(f"control_error: {exc}")
        finally:
            if self.writer is not None and self._hardware_initialized:
                try:
                    # 유일한 버스 소유자인 제어 스레드에서 진행 중인 이동을
                    # 실측 위치 Goal로 멈춘다. zero 이동/토크 해제는 하지 않는다.
                    self._capture_hold_position(allow_outside_limits=True)
                    if not self._holding_position:
                        self.writer.write_targets(self.commanded)
                except Exception as exc:
                    if self.error is None:
                        self.error = exc
                    self.safe_stop(f"stop_hold_failed: {exc}")
                    print(f"정지 위치 유지 명령 실패: {exc}. 모터 상태를 확인하세요.",
                          file=sys.stderr)

    def _loop(self):
        self.control_phase = "hardware_prepare"
        if self.writer is not None and self.motion_enabled:
            self.writer.prepare()
            self.control_phase = "initial_position_read"
            self.commanded = self.writer.read_positions()
            if callable(getattr(self.writer, "hold_current_positions", None)):
                self.control_phase = "initial_position_hold"
                self._capture_hold_position()
            self._rest_targets = dict(self.commanded)
            self._hardware_initialized = True
            self.measured_positions = dict(self.commanded)
            self.measured_at = time.monotonic()
            self._next_position_read = self.measured_at + self._position_read_period

        next_tick = time.monotonic()
        while not self.stop_event.is_set():
            now = time.monotonic()
            self.control_phase = "running"
            self.heartbeat_at = now
            # 반응 모드는 지연된 샘플이 아니라 최신 관측값만 사용한다.
            played = self.buffer.latest()
            person_visible = (
                played is not None and played.valid
                and 0 <= now - played.timestamp <= self._max_observation_age)
            posture_label = (classify(played).label
                             if person_visible else "unknown")
            if person_visible:
                posture_label = self._recovery_label(played, now, posture_label)
            if self._was_person_visible and not person_visible:
                self._capture_hold_position()
            self._was_person_visible = person_visible

            if (self.writer is not None and self.motion_enabled
                    and now >= self._next_position_read):
                self.measured_positions = self.writer.read_positions()
                self.measured_at = time.monotonic()
                if self.recovery_latency is not None:
                    self.recovery_latency.motion_observed(self.measured_at, self.measured_positions)
                self._next_position_read = (
                    self.measured_at + self._position_read_period)
            current = (self.measured_positions
                       if self.writer is not None and self.motion_enabled
                       else self.commanded)

            state, torque = self.policy.update(now, person_visible,
                                               current, self.neutral)
            self.state = state
            desired, torque_enabled = self._posture_trigger_output(
                now, person_visible, state, posture_label)

            # 일반 추적, 행동 재생, 중립 복귀 모두 같은 관문을 통과한다.
            if self._output_is_hold and self._holding_position:
                limited = dict(self.commanded)
            else:
                limited = self.safety_gate.limit_targets(self.commanded, desired)
                if not self._output_is_hold:
                    limited = self.safety_gate.limit_targets(
                        self.commanded, self._coupled_camera_targets(limited))
                self._holding_position = False
            if self.writer is not None:
                validate_transition = getattr(
                    self.safety_gate, "validate_single_turn_transition", None)
                if validate_transition is not None:
                    validate_transition(self.commanded, limited)
            previous_command = dict(self.commanded)
            if self.observation_gate is not None:
                # Mark movement before the hardware write, not after inference.
                self.observation_gate.update(time.monotonic(), limited,
                                             self.measured_positions, self.measured_at)
            self.commanded = limited
            self.last_targets = limited

            if self.writer is not None and self.motion_enabled:
                if not torque_enabled:
                    self.writer.set_torque(False)
                else:
                    # 토크 ON 전에 현재 목표를 써 저장된 이전 Goal로 튀지 않게 한다.
                    if not (self._output_is_hold and self._holding_position):
                        self.writer.write_targets(limited)
                        if (self.recovery_latency is not None and self._behavior_returning
                                and limited != previous_command):
                            self.recovery_latency.command_sent(time.monotonic())
                    self.writer.set_torque(True)

            next_tick += self.period
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_tick = time.monotonic()


def build_writer(stack, mapper, config):
    """모터 버스를 열고 JointWriter 를 만든다. 실패하면 예외."""
    packet, port = stack
    present = ping_all(packet, port)
    joint_ids = mapper.joint_ids()
    missing = [i for i in joint_ids.values() if i not in present]
    if missing:
        raise BusError(f"ID {missing} 가 버스에 없습니다. 응답: {sorted(present)}")

    for name, motor_id in joint_ids.items():
        fault = read_hardware_error(packet, port, motor_id)
        if fault:
            raise BusError(
                f"{name} (ID {motor_id}) 하드웨어 에러 0x{fault:02X} "
                f"({describe_hardware_error(fault)}). "
                "scripts/torque_off.py --clear-errors 로 해제하세요.")

    motion = config["motion"]
    writer = JointWriter(packet, port, joint_ids,
                       profile_velocity=motion["profile_velocity"],
                       profile_acceleration=motion["profile_acceleration"],
                       joint_specs=mapper.joints)
    writer.verify_modes()
    return writer


def check_pose_within_limits(writer, mapper):
    """접힌 자세에서 토크를 걸면 아래 단이 과부하로 죽는다."""
    joints = mapper.joints
    positions = writer.read_positions()
    folded = []
    for name, spec in joints.items():
        position = positions.get(name)
        if position is None or not mapper.within_observation_limits(name, position):
            folded.append(f"  {name} 현재 {position}, 운용 범위 "
                          f"zero {spec['zero_position']}, 상대 "
                          f"{spec.get('relative_min_deg', '-')}~"
                          f"{spec.get('relative_max_deg', '-')}도")
    if folded:
        raise BusError("현재 자세가 운용 범위를 벗어나 있습니다.\n"
                       + "\n".join(folded)
                       + "\n손으로 컬럼을 세운 뒤 다시 실행하세요.")


def print_status_line(now, status_mark, control, measured, played, fps,
                      condition="posture_trigger"):
    """헤드리스 모드에서 0.5초마다 상태를 한 줄로 찍는다."""
    if now - status_mark < 0.5:
        return status_mark
    measured_state = classify(measured) if measured else None
    measured_text = (
        "torso {:+5.1f} neck {:+5.1f} shoulder {:+5.1f} {}".format(
            measured.torso_pitch_deg, measured.neck_pitch_deg,
            measured.lateral_tilt_deg, measured_state.label)
        if measured else "사람 없음            ")
    played_text = (
        "torso {:+5.1f} neck {:+5.1f} shoulder {:+5.1f}".format(
            played.torso_pitch_deg, played.neck_pitch_deg,
            played.lateral_tilt_deg)
        if played and played.valid else "대기                 ")
    targets = control.last_targets
    played_label = "관측" if condition == "posture_trigger" else "재생"
    print(f"[{control.state:<9}] fps {fps:4.1f} | "
          f"측정 {measured_text} | {played_label} {played_text} | "
          f"목표 {targets}", flush=True)
    return now


def draw_preview(frame, control, measured, played, echo, angles_config,
                 landmarks, writer, fps, condition="posture_trigger"):
    """프리뷰 창에 스켈레톤과 오버레이를 그린다."""
    draw_skeleton(frame, landmarks)
    played_label = "관측" if condition == "posture_trigger" else "재생"
    lines = [
        f"state {control.state}   fps {fps:4.1f}   "
        f"control {echo['control_hz']}Hz",
        ("측정  torso {:+6.1f}  neck {:+6.1f}".format(
            measured.torso_pitch_deg, measured.neck_pitch_deg)
         if measured else "측정  사람을 찾는 중"),
        ("어깨  lateral {:+6.1f}  상태 {}".format(
            measured.lateral_tilt_deg, classify(measured).label)
         if measured else "어깨  측정 대기"),
        (f"{played_label}  torso {played.torso_pitch_deg:+6.1f}  "
         f"neck {played.neck_pitch_deg:+6.1f}"
         if played and played.valid else f"{played_label}  대기"),
        "모터  " + ("구동" if writer else "dry-run"),
    ]
    draw_overlay(frame, lines)
    if measured:
        draw_angle_bar(frame, "torso", measured.torso_pitch_deg,
                       angles_config["max_torso_pitch_deg"], 0)
        draw_angle_bar(frame, "neck", measured.neck_pitch_deg,
                       angles_config["max_neck_pitch_deg"], 1)


def run(args):
    install_signal_guards()

    if (sys.platform.startswith("linux") and not args.no_preview
            and not os.environ.get("DISPLAY")
            and not os.environ.get("WAYLAND_DISPLAY")):
        sys.exit("현재 세션에 디스플레이가 없습니다. SSH에서는 --no-preview를 사용하세요.")

    config = load_posture_config()
    perception = config["perception"]
    angles_config = config["angles"]
    echo = config["echo"]

    joints = load_joints()
    if not joints:
        sys.exit("config/joints.yaml 에 joints 가 없습니다.")
    try:
        mapper = JointMapper(joints, config["distribution"])
    except MappingError as exc:
        sys.exit(f"관절 매핑 설정 오류: {exc}")

    buffer = PoseBuffer()
    recovery_config = config.get("recovery") or {}
    recovery_detector = RecoveryDetector(**{key: value for key, value in recovery_config.items() if key != "enabled"})
    median = MedianFilter(angles_config["median_window"])
    experiment = config.get("experiment") or {}
    condition = args.condition or experiment.get("condition", "posture_trigger")

    writer = None
    control = None
    previous = None
    frames = 0
    fps = 0.0
    fps_mark = time.monotonic()
    status_mark = 0.0

    behavior = None
    safety_gate = SafetyGate(mapper, config)
    health = HealthMonitor(config)
    intervention_config = config.get("intervention") or {}
    max_event_age_sec = float(
        intervention_config.get("max_event_age_sec", 0.75))
    try:
        executor = BehaviorExecutor(config, safety_gate, condition)
    except ValueError as exc:
        sys.exit(str(exc))

    event_logger = None
    response_tracker = None
    log_dir = Path(experiment.get("log_dir", "data/runs"))
    if not log_dir.is_absolute():
        log_dir = PROJECT_ROOT / log_dir
    event_logger = EventLogger(log_dir, condition=condition)
    performance = PerformanceWindow((config.get("telemetry") or {}).get("performance_interval_sec", 5.0))
    recovery_latency = RecoveryLatency()
    event_logger.record("recovery_policy", method="raw_two_frame" if recovery_config.get("enabled", False) else "filtered",
                        settings=recovery_config, bad_sustain_sec=config["correction"]["sustain_seconds"])
    response_tracker = ResponseTracker(
        event_logger,
        response_timeout_sec=float(experiment.get("response_timeout_sec", 15.0)),
    )
    stack = ExitStack()
    web_preview = None
    observation_reason = None
    observation_since = None
    side_log_at = 0.0
    try:
        if getattr(args, "web_preview", False):
            from src.camera.web_preview import WebPreview
            try:
                web_preview = WebPreview(
                    args.web_preview_port, args.web_preview_fps).__enter__()
            except (OSError, ValueError) as exc:
                sys.exit(f"웹 프리뷰 시작 실패: {exc}")
            print(f"웹 프리뷰: http://127.0.0.1:{web_preview.port}/ (SSH 터널 사용)")
        if args.move:
            packet, port = stack.enter_context(open_bus())
            writer = build_writer((packet, port), mapper, config)
            check_pose_within_limits(writer, mapper)

        control = ControlLoop(buffer, mapper, writer, config, safety_gate, recovery_latency)

        # 교정 판단 스레드 (--no-correction 이면 비활성)
        behavior = None
        if not args.no_correction:
            behavior = BehaviorManager(config, condition=condition)
            behavior.start()
            print(f"자세 반응 모드 활성. 조건={condition}, "
                  "나쁜 자세가 지속될 때만 고정 모션을 실행합니다 "
                  "(--no-correction 으로 끌 수 있음).")

        source = args.camera or perception.get("camera",
                                               perception.get("camera_index", 0))
        with CameraStream(source, perception["width"],
                          perception["height"], perception.get("latest_frame_only", True)) as camera, \
                PoseEstimator(args.model
                              or perception.get("model")) as estimator:
            # 모델/카메라 준비가 성공한 뒤에만 모터 제어를 시작한다.
            control.start()
            print("자세 반응 시작. 프리뷰 창에서 q 또는 Esc 로 종료합니다.")
            print("사용자별 캘리브레이션 없이 실행합니다. "
                  "카메라 위치를 고정하고 오검출을 확인하세요.")
            if writer is None:
                print("dry-run 입니다. 모터는 움직이지 않습니다 (--move 로 구동).")

            start = time.monotonic()
            health.start(start)
            while not control.stop_event.is_set():
                capture_mark = time.monotonic()
                frame = camera.read()
                now = time.monotonic()
                captured_at = getattr(camera, "last_captured_at", None) or now
                capture_wait_ms = (now - capture_mark) * 1000
                if frame is None:
                    reason = health.check(now, control.heartbeat_at,
                                          getattr(control, "control_phase", None))
                    if reason:
                        control.safe_stop(reason)
                        raise SafeStopRequested(reason)
                    continue
                health.record_frame(now)
                reason = health.check(now, control.heartbeat_at,
                                      getattr(control, "control_phase", None))
                if reason:
                    control.safe_stop(reason)
                    raise SafeStopRequested(reason)
                inference_mark = time.monotonic()
                landmarks, world = estimator.detect(frame,
                                                    max(0, (captured_at - start) * 1000.0))
                finished_at = time.monotonic()
                report = performance.observe(finished_at, capture_wait_ms,
                                              (finished_at - inference_mark) * 1000,
                                              (finished_at - captured_at) * 1000)
                if report:
                    event_logger.record("runtime_performance", **report)
                    if args.no_preview:
                        print(f"[PERF] {report['processed_fps']} fps | 추론 {report['inference_ms']}ms | 프레임 지연 {report['frame_age_ms']}ms", flush=True)

                measured = None
                raw_measured = None
                if landmarks and world:
                    measured = extract_angles(
                        world, landmarks, captured_at,
                        perception["min_visibility"],
                        perception["invert_torso"],
                        perception["invert_neck"])

                gate = getattr(control, "observation_gate", None)
                diagnostic_raw = measured  # display/log only when evaluation is excluded
                reason = gate.reason(captured_at, time.monotonic()) if gate else "ready"
                if reason == "ready" and measured is None:
                    reason = "landmarks_unavailable"
                if reason != observation_reason:
                    event_logger.record("observation_quality", timestamp=time.monotonic(),
                                        captured_at=captured_at, reason=reason,
                                        previous_reason=observation_reason,
                                        previous_sampled_duration_sec=(
                                            round(finished_at - observation_since, 4)
                                            if observation_since is not None else None),
                                        evaluation_allowed=reason == "ready")
                    print(f"[OBSERVATION] {reason}", flush=True)
                    observation_reason = reason
                    observation_since = finished_at
                if reason != "ready":
                    measured = None

                if measured is not None:
                    raw_measured = measured
                    # 순서가 중요하다. 중앙값으로 튀는 값을 먼저 버리고,
                    # 운용 범위 안으로 자르고 부드럽게 한다.
                    measured = filter_observation(
                        measured, previous, median, angles_config)
                    previous = measured
                    filtered_at = time.monotonic()
                    confirmation = recovery_detector.update(raw_measured, filtered_at)
                    recovery_latency.observe(captured_at, finished_at, time.monotonic(),
                                             classify(raw_measured).label, classify(measured).label)
                    if recovery_config.get("enabled", False):
                        recovery_latency.recovery_confirmed(confirmation, filtered_at)
                    buffer.push(measured, confirmation)
                else:
                    previous = None
                    median.reset()
                    recovery_latency.observe(captured_at, finished_at, time.monotonic(), "unknown", "unknown")
                    missing = PostureAngles(captured_at, 0.0, 0.0, 0.0)
                    confirmation = recovery_detector.update(missing, time.monotonic())
                    # Keep person presence for safety without allowing posture decisions.
                    presence = person_confidence(landmarks, perception["min_visibility"])
                    buffer.push(PostureAngles(captured_at, 0.0, 0.0, presence,
                                              posture_evaluable=False), confirmation)

                # 교정 판단 스레드에는 인식 실패도 unknown으로 전달한다.
                # 실패 프레임을 생략하면 이전 나쁜 자세가 보이지 않은
                # 시간까지 지속된 것으로 오인할 수 있다.
                observed = measured or PostureAngles(captured_at, 0.0, 0.0, 0.0)
                recovery_observed = (raw_measured if recovery_config.get("enabled", False)
                                     and confirmation.confirmed else observed)
                if (recovery_config.get("enabled", False) and not confirmation.confirmed
                        and classify(observed).label == "good"):
                    recovery_observed = PostureAngles(captured_at, 0.0, 0.0, 0.0)
                if finished_at - side_log_at >= 0.5:
                    event_logger.record("side_view_candidate", captured_at=captured_at,
                                        evaluation_reason=reason,
                                        raw_label=classify(diagnostic_raw).label if diagnostic_raw else "unknown",
                                        filtered_label=classify(observed).label,
                                        decision_label=classify(recovery_observed).label,
                                        recovery_confirmed=confirmation.confirmed,
                                        **side_candidate(landmarks, frame.shape[1], frame.shape[0],
                                                         perception["min_visibility"]))
                    side_log_at = finished_at
                if behavior is not None:
                    behavior.update_posture(recovery_observed)
                if response_tracker is not None:
                    response_tracker.update(time.monotonic(), classify(recovery_observed).label,
                                            observation_reason=(reason if reason != "ready"
                                                                else "waiting_recovery_confirmation"))

                # 교정 이벤트 소비
                if behavior is not None:
                    event = behavior.poll_event()
                    if event:
                        action = None
                        event_now = time.monotonic()
                        current_posture = classify(recovery_observed)
                        age = event_now - event.timestamp
                        event_is_current = (
                            observed.valid
                            and age >= 0.0
                            and age <= max_event_age_sec
                            and current_posture.label == event.posture_label
                        )
                        if event_is_current:
                            action = executor.build(event)
                            if action is not None:
                                delivered = False
                                simulated = False
                                if action.pose is not None:
                                    if writer is None:
                                        simulated = True
                                    else:
                                        delivered = control.submit_behavior(action)
                                if delivered and response_tracker is not None:
                                    applied_at = time.monotonic()
                                    response_tracker.intervention(
                                        applied_at, event.posture_label,
                                        action.behavior)
                                elif simulated and event_logger is not None:
                                    event_logger.record(
                                        "intervention_simulated",
                                        timestamp=time.monotonic(),
                                        posture=event.posture_label,
                                        behavior=action.behavior,
                                    )
                                elif not delivered and event_logger is not None:
                                    event_logger.record(
                                        "intervention_skipped",
                                        timestamp=time.monotonic(),
                                        posture=event.posture_label,
                                        reason="delivery_failed",
                                    )
                            else:
                                # 실행기가 행동을 만들지 못한 경우도 실제
                                # 개입이 아니므로 다음 감지를 허용한다.
                                behavior.rearm_after_skipped_event()
                        else:
                            if event_logger is not None:
                                reason = ("person_lost" if not observed.valid
                                          else "posture_changed" if
                                          current_posture.label != event.posture_label
                                          else "event_expired")
                                event_logger.record(
                                    "intervention_skipped",
                                    timestamp=event_now,
                                    posture=event.posture_label,
                                    reason=reason,
                                    event_age_sec=round(age, 4),
                                )
                            behavior.rearm_after_skipped_event()
                        d = event.decision
                        action_name = action.behavior if action else "ignore"
                        print(f"[자세반응] [{d.action}] "
                              f"(행동: {action_name}, 강도: {event.urgency})")

                frames += 1
                recovery_latency.flush(event_logger, print_summary=args.no_preview)
                if now - fps_mark >= 1.0:
                    fps = frames / (now - fps_mark)
                    frames = 0
                    fps_mark = now

                played = measured

                if web_preview is not None and web_preview.ready():
                    preview_frame = frame.copy()
                    draw_preview(preview_frame, control, measured, played, echo,
                                 angles_config, landmarks, writer, fps, condition)
                    cv2.putText(preview_frame, f"evaluation: {reason}", (10, 140),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)
                    raw_label = classify(diagnostic_raw).label if diagnostic_raw else "unknown"
                    cv2.putText(preview_frame,
                                f"raw: {raw_label} | decision: {classify(recovery_observed).label} | recovery: {confirmation.confirmed}",
                                (10, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 255), 1)
                    web_preview.submit(preview_frame)

                if args.no_preview:
                    status_mark = print_status_line(
                        now, status_mark, control, measured, played, fps,
                        condition)
                else:
                    draw_preview(frame, control, measured, played, echo,
                                 angles_config, landmarks, writer, fps,
                                 condition)
                    cv2.imshow("Posture Robot", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), 27):
                        break

                if control.error:
                    raise SafeStopRequested(
                        f"control_error: {control.error}")
        if control.error:
            raise SafeStopRequested(f"control_error: {control.error}")
        if control.safe_stop_reason:
            raise SafeStopRequested(control.safe_stop_reason)
        return 0
    except SafeStopRequested as exc:
        if event_logger is not None:
            event_logger.record("safe_stop", reason=str(exc))
        print(f"[SAFE_STOP] {exc}", file=sys.stderr)
        return 1
    except (BusError, CameraError, WriterError) as exc:
        sys.exit(str(exc))
    except KeyboardInterrupt:
        print("\n중단됨")
        return 0
    finally:
        shutdown_failed = False
        if behavior is not None:
            behavior.stop()
            if behavior.ident is not None:
                behavior.join(timeout=1.0)
        if control is not None:
            control.stop_event.set()
            if control.ident is not None:
                control.join(timeout=2.0)
                if control.is_alive():
                    shutdown_failed = True
                    print("제어 스레드 정지 위치 유지가 끝나지 않았습니다. "
                          "모터 상태를 확인하세요.", file=sys.stderr)
                elif control.error is not None:
                    shutdown_failed = True
                    if event_logger is not None:
                        event_logger.record(
                            "shutdown_hold_failed", reason=str(control.error))
        if writer is not None and control is not None and control.ident is not None:
            # 종료 시 실측 위치 hold는 제어 스레드가 수행한다.
            print("자동 zero 복귀·토크 해제를 생략했습니다. "
                  "로봇을 지지한 뒤 모터 상태를 확인하세요.", file=sys.stderr)
        if response_tracker is not None:
            response_tracker.close()
        if event_logger is not None:
            recovery_latency.close(time.monotonic())
            recovery_latency.flush(event_logger, print_summary=args.no_preview)
            event_logger.close()
        # 제어 스레드가 아직 버스를 쓰고 있으면 메인에서 포트를 닫지 않는다.
        if web_preview is not None:
            web_preview.__exit__(None, None, None)
        if not (control is not None and control.ident is not None and control.is_alive()):
            stack.close()
        cv2.destroyAllWindows()
        if shutdown_failed and sys.exc_info()[0] is None:
            raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="자세 반응 로봇 루프")
    parser.add_argument("--move", action="store_true",
                        help="실제로 모터를 구동한다. 없으면 프리뷰만")
    parser.add_argument("--model",
                        help="lite / full / heavy 또는 .task 경로")
    parser.add_argument("--camera",
                        help="카메라 장치 경로 또는 인덱스. "
                             "생략하면 config/posture.yaml 의 perception.camera")
    parser.add_argument("--no-preview", action="store_true",
                        help="창을 띄우지 않는다 (헤드리스)")
    parser.add_argument("--web-preview", action="store_true",
                        help="SSH 터널용 읽기 전용 웹 프리뷰 (127.0.0.1)")
    parser.add_argument("--web-preview-port", type=int, default=8765)
    parser.add_argument("--web-preview-fps", type=float, default=2.0,
                        help="웹 프리뷰 최대 FPS (0 초과~5 이하, 기본 2)")
    parser.add_argument("--no-correction", action="store_true",
                        help="자세 반응/교정 판단을 끈다")
    parser.add_argument("--condition",
                        choices=("posture_trigger",),
                        help="실험 개입 조건. 생략하면 config/posture.yaml 사용")
    args = parser.parse_args()
    try:
        with instance_lock():
            return run(args)
    except AlreadyRunning as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
