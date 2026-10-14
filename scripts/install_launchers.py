#!/usr/bin/env python3
"""현재 Pi 경로/가상환경에 맞는 실행 아이콘과 인식 전용 user service 설치."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def render(python, root):
    # Desktop Exec와 systemd ExecStart의 공통 double-quote 안전 인코딩.
    def quote(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
    entry = f"{quote(python)} {quote(root / 'scripts/launch_robot.py')}"
    desktop = f"""[Desktop Entry]
Type=Application
Name=Notifyi 카메라 확인
Comment=인식 전용 실행. 모터를 켜지 않습니다.
Exec={entry} --preview --takeover-service
Icon=camera-web
Terminal=true
Actions=Move;

[Desktop Action Move]
Name=로봇 구동 — 모터가 움직입니다
Exec={entry} --move --preview --takeover-service
"""
    unit = f"""[Unit]
Description=Notifyi posture observation only (no motor control)

[Service]
Type=simple
WorkingDirectory={quote(root)}
ExecStart={entry} --wait-camera-sec 30
Environment=PYTHONUNBUFFERED=1
Restart=no
TimeoutStopSec=40

[Install]
WantedBy=default.target
"""
    return desktop, unit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-service", action="store_true",
                        help="로그인 시 인식만 자동 실행. 즉시 시작하거나 모터를 켜지 않음")
    args = parser.parse_args(argv)
    if not sys.platform.startswith("linux"):
        sys.exit("실행 아이콘/서비스 설치는 라즈베리파이 Linux에서 실행하세요")
    desktop, unit = render(Path(sys.executable).absolute(), ROOT)
    # 사용자 영역만 쓰며 sudo/모터/카메라에는 접근하지 않는다.
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    for path, content in ((data_home / "applications/notifyi.desktop", desktop),
                          (config_home / "systemd/user/notifyi-observe.service", unit)):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") != content:
            backup = path.with_name(path.name + ".backup")
            if backup.exists():
                sys.exit(f"기존 백업이 있어 설치 중단: {backup}. 파일을 먼저 확인하세요")
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(content, encoding="utf-8")
        print(f"설치: {path}")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    if args.enable_service:
        subprocess.run(["systemctl", "--user", "enable", "notifyi-observe.service"], check=True)
        print("다음 사용자 로그인부터 인식 전용 자동 실행. 부팅 직후 실행은 별도 linger 설정 필요.")
    else:
        print("메뉴에서 'Notifyi 카메라 확인'을 실행하세요. 기존 서비스 enable 상태는 바꾸지 않습니다.")
    print("아이콘 우클릭의 로봇 구동은 명시적 모터 실행입니다. 지지·안전 상태를 먼저 확인하세요.")


if __name__ == "__main__":
    main()
