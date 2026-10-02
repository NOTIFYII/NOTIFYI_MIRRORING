#!/usr/bin/env python3
"""POSTIC 디지털 트윈 서버.

OpenCR(USB) → Python WebSocket 브리지.
- 실시간 모터 위치 읽기 (폴링)
- 모터 목표 위치 쓰기 (AI / 수동)
- joints.yaml 구동 범위 업데이트
- 모터 장착 방향(orientation) 설정 저장/로드
"""

import asyncio
import json
import logging
import math
import os
import signal
import sys
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
ROBOT_YAML = CONFIG_DIR / "robot.yaml"
JOINTS_YAML = CONFIG_DIR / "joints.yaml"
ORIENTATION_FILE = CONFIG_DIR / "motor_orientations.json"

WS_HOST = "127.0.0.1"
WS_PORT = 8765
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8766

TICKS_PER_REV = 4096
TICKS_PER_DEG = TICKS_PER_REV / 360.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("twin")

# ─── SDK 임포트 (없으면 모의 모드) ───────────────────────────────────────────
try:
    from dynamixel_sdk import (
        PacketHandler,
        PortHandler,
        GroupSyncRead,
        GroupSyncWrite,
        COMM_SUCCESS,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    log.warning("dynamixel_sdk 없음 → 시뮬레이션(모의) 모드로 실행합니다.")

ADDR_PRESENT_POSITION = 132
ADDR_GOAL_POSITION = 116
ADDR_TORQUE_ENABLE = 64
LEN_POSITION = 4


# ─── 설정 로드 ─────────────────────────────────────────────────────────────
def load_robot_yaml():
    return yaml.safe_load(ROBOT_YAML.read_text()) or {}


def load_joints_yaml():
    raw = yaml.safe_load(JOINTS_YAML.read_text()) or {}
    return raw.get("joints") or {}


def load_orientations():
    """motor_orientations.json 로드. 없으면 기본값(normal) 반환."""
    if ORIENTATION_FILE.exists():
        try:
            return json.loads(ORIENTATION_FILE.read_text())
        except Exception:
            pass
    return {}


def save_orientations(data: dict):
    ORIENTATION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def save_joints_yaml(joints: dict):
    """joints.yaml 의 joints 섹션만 교체한다."""
    raw = yaml.safe_load(JOINTS_YAML.read_text()) or {}
    raw["joints"] = joints
    # 헤더 주석 보존을 위해 읽어서 joints: 이하를 교체하는 방식 사용
    JOINTS_YAML.write_text(yaml.dump(raw, allow_unicode=True, sort_keys=False))


# ─── 모의 버스 ────────────────────────────────────────────────────────────
class MockBus:
    """dynamixel_sdk 없을 때 쓰는 가짜 버스."""

    def __init__(self, active_ids):
        self._pos = {mid: 2048 for mid in active_ids}
        self._t = time.time()

    def read_positions(self):
        """시간에 따라 살짝 흔들리는 모의 위치."""
        t = time.time() - self._t
        return {mid: int(2048 + 100 * math.sin(t + mid * 0.7))
                for mid in self._pos}

    def write_position(self, motor_id, pos):
        self._pos[motor_id] = int(pos)

    def close(self):
        pass


# ─── 실제 버스 ───────────────────────────────────────────────────────────
class DynamixelBus:
    def __init__(self, port, baudrate, protocol, active_ids):
        self._ids = list(active_ids)
        handler = PortHandler(port)
        packet = PacketHandler(float(protocol))
        if not handler.openPort():
            raise RuntimeError(f"포트 열기 실패: {port}")
        if not handler.setBaudRate(baudrate):
            raise RuntimeError(f"baudrate 설정 실패: {baudrate}")
        self._port = handler
        self._packet = packet
        self._sync_read = GroupSyncRead(
            handler, packet, ADDR_PRESENT_POSITION, LEN_POSITION)
        for mid in self._ids:
            self._sync_read.addParam(mid)

    def read_positions(self):
        result = {}
        comm = self._sync_read.txRxPacket()
        if comm != COMM_SUCCESS:
            return {}
        for mid in self._ids:
            if self._sync_read.isAvailable(mid, ADDR_PRESENT_POSITION, LEN_POSITION):
                result[mid] = self._sync_read.getData(
                    mid, ADDR_PRESENT_POSITION, LEN_POSITION)
        return result

    def write_position(self, motor_id, pos):
        data = [
            (pos >> 0) & 0xFF,
            (pos >> 8) & 0xFF,
            (pos >> 16) & 0xFF,
            (pos >> 24) & 0xFF,
        ]
        self._packet.write4ByteTxRx(
            self._port, motor_id, ADDR_GOAL_POSITION, pos)

    def enable_torque(self, motor_id, on: bool):
        self._packet.write1ByteTxRx(
            self._port, motor_id, ADDR_TORQUE_ENABLE, 1 if on else 0)

    def close(self):
        self._port.closePort()


# ─── 트윈 상태 ────────────────────────────────────────────────────────────
class TwinState:
    def __init__(self):
        self.joints = load_joints_yaml()
        self.orientations = load_orientations()
        self.positions: dict[int, int] = {}
        self.lock = threading.Lock()
        self._bus = None
        self._running = False
        self._poll_thread: threading.Thread | None = None
        self._clients: set = set()

    # --- 버스 연결 ---
    def connect(self):
        cfg = load_robot_yaml()
        bus_cfg = cfg.get("bus", {})
        active = list((cfg.get("motors") or {}).get("active_ids") or [])
        if SDK_AVAILABLE:
            try:
                self._bus = DynamixelBus(
                    bus_cfg["port"], bus_cfg["baudrate"],
                    bus_cfg["protocol"], active)
                log.info("OpenCR 연결 성공: %s", bus_cfg["port"])
                return True
            except Exception as e:
                log.warning("OpenCR 연결 실패(%s) → 시뮬레이션 모드", e)
        self._bus = MockBus(active)
        log.info("시뮬레이션 모드로 실행 중")
        return False

    def start_polling(self, push_fn, hz=20):
        """백그라운드 스레드에서 모터 위치를 읽어 push_fn 으로 브로드캐스트."""
        self._running = True

        def _loop():
            interval = 1.0 / hz
            while self._running:
                start = time.perf_counter()
                try:
                    pos = self._bus.read_positions()
                    with self.lock:
                        self.positions = pos
                    push_fn(pos)
                except Exception as e:
                    log.debug("poll error: %s", e)
                elapsed = time.perf_counter() - start
                time.sleep(max(0, interval - elapsed))

        self._poll_thread = threading.Thread(target=_loop, daemon=True)
        self._poll_thread.start()

    def stop(self):
        self._running = False
        if self._bus:
            self._bus.close()

    # --- 설정 업데이트 ---
    def update_joint_limits(self, joint_name: str, rel_min: float, rel_max: float):
        if joint_name not in self.joints:
            return False, f"관절 없음: {joint_name}"
        if rel_min >= rel_max:
            return False, "min >= max"
        with self.lock:
            self.joints[joint_name]["relative_min_deg"] = round(rel_min, 1)
            self.joints[joint_name]["relative_max_deg"] = round(rel_max, 1)
        save_joints_yaml(self.joints)
        log.info("범위 업데이트: %s [%s, %s]°", joint_name, rel_min, rel_max)
        return True, "ok"

    def update_orientation(self, motor_id: int, orientation: str):
        """orientation: 'normal' | 'inverted' | 'sideways_cw' | 'sideways_ccw'"""
        self.orientations[str(motor_id)] = orientation
        save_orientations(self.orientations)
        return True, "ok"

    def set_goal_position(self, motor_id: int, position: int):
        position = max(0, min(4095, position))
        if self._bus:
            self._bus.write_position(motor_id, position)
        return True, position

    def snapshot(self):
        """클라이언트로 보낼 전체 상태 스냅샷."""
        with self.lock:
            positions = dict(self.positions)
        joints_info = {}
        for name, spec in self.joints.items():
            jid = spec.get("id")
            zero = spec.get("zero_position", 2048)
            cur = positions.get(jid, zero)
            # 0~4095 → 각도 변환
            delta_ticks = cur - zero
            if abs(delta_ticks) > TICKS_PER_REV / 2:
                delta_ticks = delta_ticks - math.copysign(TICKS_PER_REV, delta_ticks)
            deg = delta_ticks / TICKS_PER_DEG
            joints_info[name] = {
                "id": jid,
                "current_position": cur,
                "current_deg": round(deg, 2),
                "zero_position": zero,
                "min_position": spec.get("min_position", 0),
                "max_position": spec.get("max_position", 4095),
                "relative_min_deg": spec.get("relative_min_deg", -180),
                "relative_max_deg": spec.get("relative_max_deg", 180),
                "direction": spec.get("direction", 1),
                "group": spec.get("group", "torso"),
                "input_axis": spec.get("input_axis", ""),
                "orientation": self.orientations.get(str(jid), "normal"),
            }
        return joints_info


# ─── WebSocket 핸들러 ─────────────────────────────────────────────────────
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

state = TwinState()
_ws_clients: set = set()
_loop: asyncio.AbstractEventLoop | None = None


def push_positions(positions: dict):
    """폴링 스레드에서 비동기 루프로 브로드캐스트."""
    if _loop is None or not _ws_clients:
        return
    msg = json.dumps({"type": "positions", "data": positions})
    asyncio.run_coroutine_threadsafe(_broadcast(msg), _loop)


async def _broadcast(msg: str):
    dead = set()
    for ws in list(_ws_clients):
        try:
            await ws.send(msg)
        except Exception:
            dead.add(ws)
    _ws_clients -= dead


async def ws_handler(websocket):
    _ws_clients.add(websocket)
    log.info("클라이언트 연결: %s", websocket.remote_address)
    try:
        # 연결 즉시 전체 스냅샷 전송
        await websocket.send(json.dumps({
            "type": "snapshot",
            "data": state.snapshot()
        }))
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await handle_message(websocket, msg)
    except Exception as e:
        log.debug("ws 연결 종료: %s", e)
    finally:
        _ws_clients.discard(websocket)


async def handle_message(ws, msg: dict):
    action = msg.get("action")

    if action == "get_snapshot":
        await ws.send(json.dumps({
            "type": "snapshot",
            "data": state.snapshot()
        }))

    elif action == "set_goal":
        mid = int(msg["motor_id"])
        pos = int(msg["position"])
        ok, result = state.set_goal_position(mid, pos)
        await ws.send(json.dumps({
            "type": "ack",
            "action": "set_goal",
            "motor_id": mid,
            "position": result,
            "ok": ok,
        }))

    elif action == "set_limits":
        name = msg["joint_name"]
        ok, result = state.update_joint_limits(
            name, float(msg["min_deg"]), float(msg["max_deg"]))
        # 변경 후 전체 스냅샷 브로드캐스트
        await _broadcast(json.dumps({
            "type": "snapshot",
            "data": state.snapshot()
        }))
        await ws.send(json.dumps({
            "type": "ack", "action": "set_limits", "ok": ok, "msg": result}))

    elif action == "set_orientation":
        mid = int(msg["motor_id"])
        ori = msg["orientation"]
        ok, _ = state.update_orientation(mid, ori)
        await _broadcast(json.dumps({
            "type": "snapshot",
            "data": state.snapshot()
        }))
        await ws.send(json.dumps({
            "type": "ack", "action": "set_orientation",
            "motor_id": mid, "orientation": ori, "ok": ok}))

    elif action == "reload":
        with state.lock:
            state.joints = load_joints_yaml()
            state.orientations = load_orientations()
        await ws.send(json.dumps({
            "type": "snapshot",
            "data": state.snapshot()
        }))


# ─── HTTP 서버 (정적 파일) ────────────────────────────────────────────────
class CORSHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # HTTP 로그 억제


def start_http():
    server = HTTPServer((HTTP_HOST, HTTP_PORT), CORSHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    log.info("HTTP 서버: http://%s:%d/twin.html", HTTP_HOST, HTTP_PORT)


# ─── 메인 ────────────────────────────────────────────────────────────────
async def main():
    global _loop
    _loop = asyncio.get_running_loop()

    state.connect()
    state.start_polling(push_positions, hz=20)
    start_http()

    if not WEBSOCKETS_AVAILABLE:
        log.error("websockets 패키지가 없습니다: pip install websockets")
        return

    import websockets as ws_lib
    async with ws_lib.serve(ws_handler, WS_HOST, WS_PORT):
        log.info("WebSocket 서버: ws://%s:%d", WS_HOST, WS_PORT)
        log.info("브라우저에서 http://%s:%d/twin.html 로 접속하세요", HTTP_HOST, HTTP_PORT)
        await asyncio.Future()  # 무한 대기


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        state.stop()
        log.info("종료")
