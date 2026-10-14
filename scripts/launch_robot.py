#!/usr/bin/env python3
"""실행 아이콘/서비스 진입점. 기본은 인식 전용, --move를 선택해야 모터 구동."""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--move", action="store_true")
    parser.add_argument("--takeover-service", action="store_true",
                        help="아이콘 실행 전 같은 사용자의 인식 전용 notifyi-observe 서비스 종료")
    parser.add_argument("--wait-camera-sec", type=float, default=0,
                        help="부팅 때 설정된 USB 카메라 장치가 나타날 때까지 기다리는 최대 시간")
    return parser.parse_args(argv)


def command(args):
    result = [sys.executable, "-m", "src.main", "--condition", "posture_trigger"]
    if not args.preview:
        result.append("--no-preview")
    if args.move:
        result.append("--move")
    return result


def main(argv=None):
    args = arguments(argv)
    if not 0 <= args.wait_camera_sec <= 60:
        raise SystemExit("카메라 대기는 0~60초여야 합니다")
    if args.takeover_service:
        try:
            active = subprocess.run(["systemctl", "--user", "is-active", "--quiet", "notifyi-observe.service"],
                                    timeout=10, check=False)
            if active.returncode == 0:
                subprocess.run(["systemctl", "--user", "stop", "notifyi-observe.service"],
                               timeout=30, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"자동 서비스 종료를 확인하지 못했습니다: {exc}", file=sys.stderr)
            return 1
    os.chdir(ROOT)
    if args.wait_camera_sec:
        import yaml
        config = yaml.safe_load((ROOT / "config/posture.yaml").read_text(encoding="utf-8"))
        source = str(config["perception"]["camera"])
        device = Path(source if source.startswith("/dev/video") else f"/dev/video{source}")
        deadline = time.monotonic() + args.wait_camera_sec
        while not device.exists():
            if time.monotonic() >= deadline:
                print(f"카메라 장치 대기 시간 초과: {device}", file=sys.stderr)
                return 1
            time.sleep(0.25)
    os.execv(sys.executable, command(args))


if __name__ == "__main__":
    sys.exit(main())
