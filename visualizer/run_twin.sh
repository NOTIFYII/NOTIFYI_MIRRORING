#!/usr/bin/env bash
# POSTIC 디지털 트윈 실행 스크립트
# 사용법: ./visualizer/run_twin.sh [--sim]
#   --sim : OpenCR 없이 시뮬레이션 모드 강제

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  POSTIC Digital Twin — 2XL430-W250"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Python 환경 감지
if [ -d "$HOME/dynamixel-venv" ]; then
  PYTHON="$HOME/dynamixel-venv/bin/python"
  echo "✓ dynamixel-venv 사용"
elif command -v python3 &>/dev/null; then
  PYTHON="python3"
  echo "✓ 시스템 python3 사용"
else
  echo "✗ Python 을 찾을 수 없습니다"
  exit 1
fi

# websockets 확인 및 설치
if ! $PYTHON -c "import websockets" 2>/dev/null; then
  echo "→ websockets 설치 중..."
  $PYTHON -m pip install --quiet websockets
fi

# 서버 시작
echo ""
echo "▶ 서버 시작 중..."
echo "  3D 뷰어: http://127.0.0.1:8766/twin.html"
echo "  WebSocket: ws://127.0.0.1:8765"
echo "  Ctrl+C 로 종료"
echo ""

cd "$SCRIPT_DIR"
exec $PYTHON digital_twin_server.py "$@"
