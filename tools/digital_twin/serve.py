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
    """Read the last explicit scan; never open the serial port from this server."""
    try:
        payload = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        checked_at = float(payload["checked_at"])
        now = datetime.now(timezone.utc).timestamp()
        if not math.isfinite(checked_at) or checked_at > now + 2:
            return None
        if payload["port"] != bus["port"] or float(payload["protocol"]) != float(bus["protocol"]):
            return None
        age = max(0.0, now - checked_at)
        ids = sorted({int(item["id"]) for item in payload["results"]
                      if int(item["baudrate"]) == int(bus["baudrate"])})
        return {"checked_at": checked_at, "age_seconds": round(age, 1),
                "fresh": age <= 15, "responding_ids": ids,
                "source": "manual_scan"}
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
            "motor_response": "last_manual_scan" if probe and probe["fresh"] else "unverified",
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
