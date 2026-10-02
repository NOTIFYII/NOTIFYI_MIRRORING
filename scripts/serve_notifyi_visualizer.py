#!/usr/bin/env python3
"""Notifyi Three.js 시각화 서버.

기본은 하드웨어를 건드리지 않는 샘플 모드다.
--hardware 를 붙이면 OpenCR/DYNAMIXEL에서 현재 위치만 읽어
visualizer/index.html의 /api/state로 제공한다. 이 서버는 모터 쓰기를 하지
않지만, 읽는 동안 시리얼 포트를 점유하므로 teleop/main과 동시에 실행하지 않는다.

사용법:
    python scripts/serve_notifyi_visualizer.py
    python scripts/serve_notifyi_visualizer.py --hardware
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.robot.dynamixel_driver import load_joints, load_robot_config, open_bus

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VISUALIZER_ROOT = PROJECT_ROOT / "visualizer"
PRESENT_POSITION = 132
TICKS_PER_REV = 4096


class StateStore:
    def __init__(self, joints):
        self._lock = threading.Lock()
        self._state = {
            "timestamp": "sample",
            "source": "sample",
            "motors": {},
        }
        for name, spec in joints.items():
            motor_id = int(spec["id"])
            self._state["motors"][str(motor_id)] = {
                "id": motor_id,
                "name": name,
                "axis": str(spec.get("input_axis", "unknown")),
                "position": int(spec["zero_position"]),
                "zero": int(spec["zero_position"]),
                "relative_deg": 0.0,
            }

    @staticmethod
    def _relative_ticks(position, zero):
        return (position - zero + TICKS_PER_REV / 2) % TICKS_PER_REV \
            - TICKS_PER_REV / 2

    def update(self, positions, source, error=None):
        with self._lock:
            for key, position in positions.items():
                motor = self._state["motors"].get(str(key))
                if motor is None:
                    continue
                motor["position"] = int(position) % TICKS_PER_REV
                motor["relative_deg"] = round(
                    self._relative_ticks(motor["position"], motor["zero"])
                    * 360.0 / TICKS_PER_REV, 2)
            self._state["timestamp"] = round(time.time(), 3)
            self._state["source"] = source
            if error:
                self._state["error"] = str(error)
            else:
                self._state.pop("error", None)

    def snapshot(self):
        with self._lock:
            return json.loads(json.dumps(self._state))


class HardwarePoller(threading.Thread):
    def __init__(self, store, config, interval=0.1):
        super().__init__(name="notifyi-position-reader", daemon=True)
        self.store = store
        self.config = config
        self.interval = interval
        self.stop_event = threading.Event()

    def run(self):
        try:
            with open_bus(self.config) as (packet, port):
                while not self.stop_event.is_set():
                    positions = {}
                    errors = []
                    for key in self.store.snapshot()["motors"]:
                        motor_id = int(key)
                        value, comm, error = packet.read4ByteTxRx(
                            port, motor_id, PRESENT_POSITION)
                        if comm != 0 or error:
                            errors.append(f"ID {motor_id}")
                            continue
                        positions[motor_id] = value % TICKS_PER_REV
                    self.store.update(
                        positions, "hardware",
                        "위치 읽기 실패: " + ", ".join(errors)
                        if errors else None,
                    )
                    self.stop_event.wait(self.interval)
        except Exception as exc:
            self.store.update({}, "hardware", exc)


class Handler(SimpleHTTPRequestHandler):
    store = None

    def do_GET(self):  # noqa: N802 - stdlib handler API
        if urlparse(self.path).path == "/api/state":
            payload = json.dumps(self.store.snapshot(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        # 기본 access log는 끄고 하드웨어 오류만 API에서 확인한다.
        return


def main():
    parser = argparse.ArgumentParser(description="Notifyi Three.js visualizer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--hardware", action="store_true",
                        help="OpenCR/DYNAMIXEL 현재 위치를 읽기 전용으로 연결")
    args = parser.parse_args()

    joints = load_joints()
    config = load_robot_config()
    store = StateStore(joints)
    if args.hardware:
        HardwarePoller(store, config).start()

    Handler.store = store
    handler = lambda *items: Handler(*items, directory=str(VISUALIZER_ROOT))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    mode = "hardware read-only" if args.hardware else "sample"
    print(f"Notifyi visualizer: http://{args.host}:{args.port} ({mode})")
    print("종료: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
