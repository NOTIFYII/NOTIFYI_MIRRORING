#!/usr/bin/env python3
"""Publish read-only DYNAMIXEL observations for the local 3D viewer.

Run only while main control, Wizard, and other serial clients are stopped.
This process never enables torque, changes modes, or writes goal positions.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dynamixel_sdk import COMM_SUCCESS, PacketHandler, PortHandler

from scripts.scan_dynamixel import read_field, to_signed32
from src.robot.dynamixel_driver import load_robot_config


def observe_once(packet, port, ids: list[int], baudrate: int) -> list[dict]:
    """Ping configured IDs and read telemetry; never issue a write packet."""
    results = []
    for motor_id in ids:
        try:
            model_number, comm, _error = packet.ping(port, motor_id)
            if comm != COMM_SUCCESS:
                continue
            raw_position = read_field(packet, port, motor_id, "present_position")
            results.append({
                "id": motor_id,
                "baudrate": baudrate,
                "model_number": model_number,
                "present_position": to_signed32(raw_position) if raw_position is not None else None,
                "torque_enable": read_field(packet, port, motor_id, "torque_enable"),
                "hw_error": read_field(packet, port, motor_id, "hw_error"),
                "operating_mode": read_field(packet, port, motor_id, "operating_mode"),
                "valid": raw_position is not None,
            })
        except Exception as exc:
            print(f"ID {motor_id} 읽기 실패: {exc}", file=sys.stderr)
    return results


def publish(path: Path, *, port: str, protocol: float, interval: float,
            sequence: int, results: list[dict]) -> None:
    """Atomically replace the latest observation; older files become stale."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "read_only_watch", "checked_at": time.time(),
        "sequence": sequence, "interval_seconds": interval,
        "port": port, "protocol": protocol, "results": results,
    }
    temporary = path.with_name(f".{path.name}.watch-{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    robot = load_robot_config()
    bus = robot["bus"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=bus["port"])
    parser.add_argument("--baud", type=int, default=bus["baudrate"])
    parser.add_argument("--proto", type=float, default=bus["protocol"], choices=[2.0])
    parser.add_argument("--ids", type=int, nargs="+", default=robot["motors"]["active_ids"])
    parser.add_argument("--interval", type=float, default=3.0, help="seconds, 1-30")
    parser.add_argument("--status-file", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data/connection_status.json")
    parser.add_argument("--confirm-control-stopped", action="store_true",
                        help="required: confirm main control, Wizard, and other serial clients are stopped")
    args = parser.parse_args()
    if not args.confirm_control_stopped:
        parser.error("먼저 메인 제어·Wizard·다른 시리얼 프로그램을 종료한 뒤 --confirm-control-stopped를 지정하세요.")
    if not 1 <= args.interval <= 30:
        parser.error("--interval은 1~30초여야 합니다.")
    if not 1 <= args.baud <= 4_500_000 or not args.ids or any(not 1 <= value <= 252 for value in args.ids) or len(set(args.ids)) != len(args.ids):
        parser.error("baud와 ID 목록을 확인하세요 (ID 1~252, 중복 불가).")

    lock_path = args.status_file.with_suffix(args.status_file.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("이미 읽기 전용 관측기가 실행 중입니다.")
        port = PortHandler(args.port)
        try:
            opened = port.openPort()
        except Exception as exc:
            print(f"포트를 열 수 없습니다: {args.port} ({exc})", file=sys.stderr)
            return 1
        if not opened:
            print(f"포트를 열 수 없습니다: {args.port}", file=sys.stderr)
            return 1
        try:
            if not port.setBaudRate(args.baud):
                print(f"baudrate 설정 실패: {args.baud}", file=sys.stderr)
                return 1
            packet = PacketHandler(args.proto)
            sequence = 0
            print(f"읽기 전용 관측 시작: {args.port} / {args.baud} bps / ID {args.ids}. Ctrl+C로 종료.", flush=True)
            while True:
                started = time.monotonic()
                results = observe_once(packet, port, args.ids, args.baud)
                sequence += 1
                publish(args.status_file, port=args.port, protocol=args.proto,
                        interval=args.interval, sequence=sequence, results=results)
                print(f"#{sequence} 응답 {len(results)}/{len(args.ids)}개", flush=True)
                time.sleep(max(0, args.interval - (time.monotonic() - started)))
        except KeyboardInterrupt:
            print("읽기 전용 관측 종료. 화면은 마지막 값을 잠시 표시한 뒤 오래된 관측으로 전환합니다.")
            return 0
        finally:
            port.closePort()


if __name__ == "__main__":
    sys.exit(main())
