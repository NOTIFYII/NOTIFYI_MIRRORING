#!/usr/bin/env python3
"""2XL430 좌표 진단. 읽기만 하며 토크·EEPROM·Goal을 쓰지 않는다."""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.robot.dynamixel_driver import (  # noqa: E402
    BusError, check, load_joints, load_robot_config, open_bus,
)

FIELDS = {
    "drive_mode": (10, 1),
    "operating_mode": (11, 1),
    "homing_offset": (20, 4),
    "max_position": (48, 4),
    "min_position": (52, 4),
    "torque_enable": (64, 1),
    "hardware_error": (70, 1),
    "goal_position": (116, 4),
    "present_position": (132, 4),
}
SIGNED_FIELDS = {"homing_offset", "goal_position", "present_position"}


def signed32(value):
    return value - (1 << 32) if value & (1 << 31) else value


def read_snapshot(packet, port, motor_id):
    model, comm, error = packet.ping(port, motor_id)
    check(comm, error, packet, f"ID {motor_id} ping")
    if model != 1090:
        raise BusError(f"ID {motor_id}: 예상 모델 2XL430(1090)이 아닙니다: {model}")
    result = {"id": motor_id, "model_number": model}
    for field, (address, size) in FIELDS.items():
        reader = getattr(packet, f"read{size}ByteTxRx")
        value, comm, error = reader(port, motor_id, address)
        check(comm, error, packet, f"ID {motor_id} {field}")
        result[field] = signed32(value) if field in SIGNED_FIELDS else value
    return result


def coordinate_plan(snapshot, spec):
    """설정된 끝점을 계산할 뿐, 실물의 이동 경로를 안전하다고 판정하지 않는다."""
    zero = int(spec["zero_position"])
    lower = math.ceil(float(spec["relative_min_deg"]) * 4096 / 360)
    upper = math.floor(float(spec["relative_max_deg"]) * 4096 / 360)
    start, end = zero + lower, zero + upper
    return {
        "yaml_zero": zero,
        "relative_degrees": [spec["relative_min_deg"], spec["relative_max_deg"]],
        "unwrapped_endpoints": [start, end],
        "modulo_endpoints": [start % 4096, end % 4096],
        "crosses_single_turn_boundary": start < 0 or end > 4095,
        "present_minus_yaml_zero": snapshot["present_position"] - zero,
        "status": "inspection_only_not_approved_for_motion",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", type=int, default=2)
    parser.add_argument("--port")
    parser.add_argument("--baud", type=int)
    parser.add_argument("--output", type=Path,
                        help="읽은 설정을 JSON으로 보관. 기존 파일은 덮어쓰지 않음")
    args = parser.parse_args(argv)
    try:
        if not 0 <= args.id <= 252:
            raise ValueError("ID는 0~252여야 합니다")
        config = load_robot_config()
        if float(config["bus"]["protocol"]) != 2.0:
            raise ValueError("이 진단 도구는 Protocol 2.0 전용입니다")
        joints = load_joints()
        matches = [(name, spec) for name, spec in joints.items()
                   if spec["id"] == args.id]
        if len(matches) != 1:
            raise ValueError("YAML에서 해당 ID의 관절 하나를 확인해야 합니다")
        name, spec = matches[0]
        with open_bus(config, port=args.port, baudrate=args.baud) as (packet, port):
            snapshot = read_snapshot(packet, port, args.id)
        payload = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": "read_only_coordinate_inspection",
            "bus": {**config["bus"],
                    "port": args.port or config["bus"]["port"],
                    "baudrate": args.baud or config["bus"]["baudrate"]},
            "joint": name, "yaml_joint": spec,
            "motor": snapshot, "plan": coordinate_plan(snapshot, spec),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
            print(f"진단 기록 저장: {args.output}")
        print("읽기 완료. 모터 설정·토크·목표 위치는 변경하지 않았습니다.")
        print("운용 프로그램/위자드와 동시에 실행하지 마세요. 결과 확인 전 재구동하지 마세요.")
        return 0
    except (BusError, RuntimeError, ValueError, OSError, KeyError) as exc:
        print(f"좌표 진단 실패: {exc}. 설정 쓰기/이동은 수행하지 않았습니다.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
