#!/usr/bin/env python3
"""ID 2만 mode 4로 전환. 기본은 읽기, --apply --supported일 때만 설정 쓴다."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.inspect_motor_coordinates import read_snapshot  # noqa: E402
from src.robot.dynamixel_driver import check, load_joints, open_bus  # noqa: E402


def validate(snapshot, spec):
    if spec.get("id") != 2 or spec.get("operating_mode") != 4 or spec.get("wrap_position", True):
        raise ValueError("body_pitch는 ID 2, operating_mode 4, wrap_position false여야 합니다")
    if (spec.get("zero_position") != 1 or spec.get("min_position") != -340
            or spec.get("max_position") != 46):
        raise ValueError("이 전환 도구는 zero 1 / -340~46 ticks 설정 전용입니다")
    if snapshot["id"] != 2 or snapshot["model_number"] != 1090:
        raise ValueError("ID 2 / 2XL430 전용 도구입니다")
    if snapshot["hardware_error"]:
        raise ValueError("하드웨어 오류가 있어 중단합니다")
    if snapshot["drive_mode"] != 0 or snapshot["homing_offset"] != 0:
        raise ValueError("기존 Drive Mode/Offset이 기준 0과 다릅니다. 자동 변경하지 않습니다")
    if snapshot["operating_mode"] not in (3, 4):
        raise ValueError("현재 모드가 3/4가 아닙니다")
    if not -340 <= snapshot["present_position"] <= 46:
        raise ValueError("현재 연속 위치가 -340~46 밖입니다. 자동 정규화/복귀하지 않습니다")


def apply_transition(packet, port, spec, backup):
    before = read_snapshot(packet, port, 2)
    validate(before, spec)
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open("x", encoding="utf-8") as stream:
        json.dump({"before": before, "yaml_joint": spec,
                   "checked_at": datetime.now(timezone.utc).isoformat()}, stream, indent=2)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    if before["operating_mode"] == 4:
        return before
    # 사용자가 로봇을 지지했다고 명시한 경우에만 ID 2 토크 해제.
    comm, err = packet.write1ByteTxRx(port, 2, 64, 0)
    check(comm, err, packet, "ID 2 토크 해제")
    stopped = read_snapshot(packet, port, 2)
    validate(stopped, spec)
    if stopped["torque_enable"] != 0:
        raise ValueError("토크 해제를 확인하지 못해 모드 쓰기를 중단합니다")
    comm, err = packet.write1ByteTxRx(port, 2, 11, 4)
    check(comm, err, packet, "ID 2 mode 4 전환")
    after = read_snapshot(packet, port, 2)
    validate(after, spec)
    if after["operating_mode"] != 4 or after["torque_enable"] != 0:
        raise ValueError("전환 후 mode 4 / 토크 OFF 확인 실패. 백업과 실물 상태를 확인하세요")
    return after


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--supported", action="store_true", help="토크 해제 시 로봇을 지지하고 있음을 확인")
    parser.add_argument("--backup", type=Path, default=Path("data/motor_mode_backups") /
                        f"id2_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json")
    args = parser.parse_args(argv)
    try:
        if args.apply and not args.supported:
            raise ValueError("실제 전환에는 로봇을 지지한 뒤 --supported를 명시하세요")
        spec = load_joints()["body_pitch"]
        with open_bus() as (packet, port):
            if args.apply:
                print(f"원본 백업 경로: {args.backup}", flush=True)
                result = apply_transition(packet, port, spec, args.backup)
            else:
                result = read_snapshot(packet, port, 2)
                validate(result, spec)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("설정 확인 완료. Goal 쓰기/토크 인가는 하지 않았습니다.")
        if not args.apply:
            print("읽기 전용입니다. 실제 전환은 --apply --supported가 필요합니다.")
        return 0
    except (RuntimeError, ValueError, KeyError, OSError) as exc:
        print(f"전환 중단: {exc}. 자동 복구/토크 인가하지 않습니다. 로봇을 계속 지지하세요.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
