"""설정된 관절 목표를 한 패킷으로 동시에 쓴다(현재 구동 ID 2·3).

축마다 따로 쓰면 지령 시각이 조금씩 어긋난다. 직렬 체인에서는 그 차이가
불필요한 흔들림으로 나타나므로 GroupSyncWrite 를 쓴다.
"""

import math

from src.robot.joint_mapper import TICKS_PER_DEG

try:
    from dynamixel_sdk import COMM_SUCCESS, GroupSyncWrite
except ImportError:  # dry-run과 하드웨어 없는 테스트는 SDK 없이도 가능해야 한다.
    COMM_SUCCESS = None
    GroupSyncWrite = None

ADDR_TORQUE_ENABLE = 64
ADDR_GOAL_POSITION = 116
ADDR_PROFILE_ACCEL = 108
ADDR_PROFILE_VELOCITY = 112
GOAL_POSITION_BYTES = 4
POSITION_TICKS_PER_REV = 4096


class WriterError(RuntimeError):
    pass


class JointWriter:
    """joint 이름 -> ID 매핑을 받아 목표 위치를 동시에 쓴다."""

    def __init__(self, packet, port, joint_ids,
                 profile_velocity=40, profile_acceleration=20, joint_specs=None):
        if GroupSyncWrite is None:
            raise WriterError(
                "dynamixel_sdk 를 찾을 수 없습니다. "
                "requirements.txt 를 설치한 환경에서 --move 를 사용하세요.")
        self._packet = packet
        self._port = port
        self._joint_ids = dict(joint_ids)
        self._joint_specs = joint_specs or {}
        self._profile_velocity = profile_velocity
        self._profile_acceleration = profile_acceleration
        self._sync = GroupSyncWrite(port, packet, ADDR_GOAL_POSITION,
                                    GOAL_POSITION_BYTES)
        # 버스 오류는 관절마다 발생할 수 있다. 전체를 하나의 bool로
        # 기억하면 부분 성공 뒤의 토크 해제를 건너뛸 수 있다.
        self._torque_state = {name: False for name in self._joint_ids}

    @property
    def torque_on(self):
        return bool(self._torque_state) and all(
            state is True for state in self._torque_state.values())

    @property
    def torque_states(self):
        """관절별 토크 상태. True/False/None(확인 불가)."""
        return dict(self._torque_state)

    def _write1(self, motor_id, addr, value, what):
        comm, err = self._packet.write1ByteTxRx(self._port, motor_id, addr, value)
        if comm != COMM_SUCCESS:
            raise WriterError(f"ID {motor_id} {what}: "
                              f"{self._packet.getTxRxResult(comm)}")
        if err:
            raise WriterError(f"ID {motor_id} {what}: "
                              f"{self._packet.getRxPacketError(err)}")

    def _write4(self, motor_id, addr, value, what):
        comm, err = self._packet.write4ByteTxRx(self._port, motor_id, addr,
                                                value & 0xFFFFFFFF)
        if comm != COMM_SUCCESS:
            raise WriterError(f"ID {motor_id} {what}: "
                              f"{self._packet.getTxRxResult(comm)}")
        if err:
            raise WriterError(f"ID {motor_id} {what}: "
                              f"{self._packet.getRxPacketError(err)}")

    def prepare(self):
        """프로파일 값을 안전한 값으로 낮춘다. 토크는 아직 걸지 않는다."""
        for motor_id in self._joint_ids.values():
            self._write4(motor_id, ADDR_PROFILE_ACCEL,
                         self._profile_acceleration, "Profile Acceleration")
            self._write4(motor_id, ADDR_PROFILE_VELOCITY,
                         self._profile_velocity, "Profile Velocity")

    def verify_modes(self):
        """설정 불일치면 RAM 쓰기·토크 조작 전에 중단한다."""
        for name, spec in self._joint_specs.items():
            motor_id = self._joint_ids[name]
            value, comm, err = self._packet.read1ByteTxRx(self._port, motor_id, 11)
            if comm != COMM_SUCCESS or err or value != spec.get("operating_mode", 3):
                raise WriterError(f"ID {motor_id}: Operating Mode 불일치/읽기 실패. 설정={spec.get('operating_mode', 3)}, 실물={value}. 모드 전환 도구로 확인하세요")
            if value == 4:
                for address, size, expected, label in ((10, 1, 0, "Drive Mode"), (20, 4, 0, "Homing Offset")):
                    actual, comm, err = getattr(self._packet, f"read{size}ByteTxRx")(self._port, motor_id, address)
                    if comm != COMM_SUCCESS or err or actual != expected:
                        raise WriterError(f"ID {motor_id}: {label}가 기준 {expected}와 다릅니다. 읽은 값={actual}")

    def set_torque(self, enabled):
        if all(state is enabled for state in self._torque_state.values()):
            return
        errors = []
        for name, motor_id in self._joint_ids.items():
            if self._torque_state[name] is enabled:
                continue
            try:
                self._write1(motor_id, ADDR_TORQUE_ENABLE, 1 if enabled else 0,
                             "토크 인가" if enabled else "토크 해제")
            except WriterError as exc:
                self._torque_state[name] = None
                errors.append(str(exc))
            else:
                self._torque_state[name] = enabled
        if errors:
            raise WriterError("; ".join(errors))

    def write_targets(self, targets):
        """{관절 이름: tick} 을 한 번에 내보낸다."""
        for name, ticks in targets.items():
            spec = self._joint_specs.get(name)
            if spec and spec.get("operating_mode", 3) == 4:
                low = max(spec["min_position"], spec["zero_position"] + math.ceil(spec["relative_min_deg"] * TICKS_PER_DEG))
                high = min(spec["max_position"], spec["zero_position"] + math.floor(spec["relative_max_deg"] * TICKS_PER_DEG))
                if not math.isfinite(ticks) or not low <= ticks <= high:
                    raise WriterError(f"{name}: 확장 위치 목표가 소프트웨어 한계 밖입니다: {ticks}")
        self._sync.clearParam()
        for name, ticks in targets.items():
            motor_id = self._joint_ids.get(name)
            if motor_id is None:
                continue
            value = int(ticks) & 0xFFFFFFFF
            payload = bytes([value & 0xFF, (value >> 8) & 0xFF,
                             (value >> 16) & 0xFF, (value >> 24) & 0xFF])
            if not self._sync.addParam(motor_id, payload):
                raise WriterError(f"ID {motor_id} sync write 파라미터 추가 실패")
        comm = self._sync.txPacket()
        if comm != COMM_SUCCESS:
            raise WriterError(f"sync write 실패: "
                              f"{self._packet.getTxRxResult(comm)}")

    def read_positions(self):
        """{관절 이름: 현재 tick}."""
        positions = {}
        for name, motor_id in self._joint_ids.items():
            value, comm, err = self._packet.read4ByteTxRx(self._port, motor_id,
                                                          132)
            if comm != COMM_SUCCESS or err:
                continue
            # 몸통 mode 4는 signed 연속 좌표를 그대로 보존한다.
            # 기존 mode 3의 단회전 정규화는 머리축에만 적용한다.
            if self._joint_specs.get(name, {}).get("operating_mode", 3) == 4:
                positions[name] = value - (1 << 32) if value >= (1 << 31) else value
            else:
                positions[name] = value % POSITION_TICKS_PER_REV
        missing = set(self._joint_ids) - set(positions)
        if missing:
            raise WriterError(f"현재 위치를 읽지 못한 관절: {sorted(missing)}")
        return positions
