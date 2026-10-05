"""Local, read-only viewer for the Notifyi assembly workspace.

This process never opens the serial port. A device node existing is not proof
that the connected board is OpenCR or that any motor is powered or moving.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import socket

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = Path(__file__).resolve().parent
STATUS_FILE = REPO_ROOT / "data/connection_status.json"


def recent_motor_probe(bus: dict) -> dict | None:
    """Read a manual scan or watch snapshot; never open the serial port here."""
    try:
        payload = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        checked_at = float(payload["checked_at"])
        now = datetime.now(timezone.utc).timestamp()
        if not math.isfinite(checked_at) or checked_at > now + 2:
            return None
        if payload["port"] != bus["port"] or float(payload["protocol"]) != float(bus["protocol"]):
            return None
        source = payload.get("source", "manual_scan")
        if source not in ("manual_scan", "read_only_watch"):
            return None
        if source == "read_only_watch":
            interval = float(payload["interval_seconds"])
            sequence = payload["sequence"]
            if not math.isfinite(interval) or not 1 <= interval <= 30 or type(sequence) is not int or sequence < 1:
                return None
            freshness_limit = min(15.0, max(5.0, 2 * interval + 2))
        else:
            freshness_limit = 15.0
        age = max(0.0, now - checked_at)
        matching = [item for item in payload["results"]
                    if int(item["baudrate"]) == int(bus["baudrate"])]
        ids = sorted({int(item["id"]) for item in matching})
        motor_states = []
        for item in matching:
            torque = item.get("torque_enable")
            position = item.get("present_position")
            error = item.get("hw_error")
            state = {
                "id": int(item["id"]),
                "torque_enable": torque if type(torque) is int and torque in (0, 1) else None,
                "present_position": position if type(position) is int else None,
                "hw_error": error if type(error) is int and 0 <= error <= 255 else None,
            }
            if source == "read_only_watch":
                mode = item.get("operating_mode")
                state["operating_mode"] = mode if type(mode) is int else None
                state["valid"] = item.get("valid") is True and state["present_position"] is not None
            motor_states.append(state)
        return {"checked_at": checked_at, "age_seconds": round(age, 1),
                "fresh": age <= freshness_limit, "responding_ids": ids,
                "motor_states": motor_states,
                "source": source,
                "sequence": payload["sequence"] if source == "read_only_watch" else None}
    except (OSError, KeyError, ValueError, TypeError, OverflowError):
        return None


def workspace_snapshot() -> dict:
    robot = yaml.safe_load((REPO_ROOT / "config/robot.yaml").read_text(encoding="utf-8"))
    joints = yaml.safe_load((REPO_ROOT / "config/joints.yaml").read_text(encoding="utf-8"))
    bus = robot["bus"]
    roles = {unit["driven"]: unit["role"] for unit in joints["structure"]["units"]}
    mapped = [
        {
            "id": entry["id"],
            "name": name,
            "label": f"{roles.get(entry['id'], '미분류')} · {name.rsplit('_', 1)[-1]}",
            "zero_position": entry["zero_position"],
            "direction": entry["direction"],
        }
        for name, entry in joints["joints"].items()
    ]
    port_present = os.path.exists(bus["port"])
    probe = recent_motor_probe(bus)
    if probe and not port_present:
        probe["fresh"] = False
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "bus": bus,
        "port_present": port_present,
        "active_ids": robot["motors"]["active_ids"],
        "unused_ids": robot["motors"]["unused_ids"],
        "joints": mapped,
        "motor_probe": probe,
        "verification": {
            "board_identity": "unverified",
            "motor_power": "unverified",
            "motor_response": probe["source"] if probe and probe["fresh"] else "unverified",
            "motor_motion": "unverified",
            "leds": "unverified",
        },
    }


class ViewerHandler(SimpleHTTPRequestHandler):
    def log_message(self, message, *args):
        if args and "/api/workspace" in str(args[0]):
            return
        super().log_message(message, *args)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/workspace":
            try:
                body = json.dumps(workspace_snapshot(), ensure_ascii=False).encode("utf-8")
            except (OSError, KeyError, ValueError, yaml.YAMLError) as exc:
                self.send_error(500, f"Workspace configuration error: {exc}")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18766)
    args = parser.parse_args()
    handler = partial(ViewerHandler, directory=str(WEB_ROOT))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Notifyi viewer: http://127.0.0.1:{args.port}/")
        server.serve_forever()


if __name__ == "__main__":
    main()
