# Notifyi 명령어 모음

아래 명령은 프로젝트 루트에서 실행한다. 가상환경이 `./.venv`에 없으면 실제 경로로 바꾼다.

## 환경

~~~bash
./.venv/bin/python --version
./.venv/bin/python scripts/check_env.py
~~~

## 카메라

~~~bash
ls -l /dev/video*
v4l2-ctl --list-devices
fuser /dev/video0
~~~

카메라 확인에는 v4l2 명령과 src.main dry-run을 사용한다.

## Dynamixel 스캔

~~~bash
./.venv/bin/python scripts/scan_dynamixel.py \
  --port /dev/ttyACM0 --baud 57600 --proto 2.0
~~~

OpenCR 브리지를 쓰는 현 설정의 읽기 전용 스캔이다. 메인 제어와 Wizard를 종료한 뒤 실행한다. 토크나 목표 위치는 변경하지 않는다. ID 2~7이 활성축이며 ID 1·8은 유휴다.

## 토크 해제와 오류 확인

~~~bash
./.venv/bin/python scripts/torque_off.py --ids 5
./.venv/bin/python scripts/torque_off.py --ids 5 --clear-errors
~~~

`5`는 **예시 ID**다. 실제 오류 ID를 스캔으로 확인해 바꾼다. `--clear-errors`는 진단·하중 제거 후 필요할 때만 사용한다. 모터가 구조물을 지탱 중이면 토크 해제로 넘어질 수 있으므로 먼저 지지한다.

## Notifyi 실행

~~~bash
# 인식만
./.venv/bin/python -m src.main --no-preview --no-correction \
  --camera /dev/video0 --no-camera-gimbal

# 모터 포함
./.venv/bin/python -m src.main --no-preview --move \
  --condition posture_trigger \
  --camera /dev/video0 \
  --participant-id P01

# 노트북 웹캠
./.venv/bin/python -m src.main --no-preview --move \
  --condition posture_trigger \
  --camera /dev/video0 \
  --no-camera-gimbal \
  --participant-id P01
~~~

## 테스트와 정적 확인

~~~bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m compileall -q src scripts
git diff --check
~~~

## 로그 요약

~~~bash
./.venv/bin/python scripts/summarize_posture_logs.py \
  --input data/runs \
  --output-dir data/summaries
~~~

결과:

- data/summaries/episodes.csv
- data/summaries/interventions.csv

## 3D 조립판과 상태 표시

~~~bash
./.venv/bin/python tools/digital_twin/serve.py --port 18766
~~~

같은 컴퓨터에서 `http://127.0.0.1:18766/`을 연다. 이 서버는 모터 버스를 열지 않는다. 마지막 수동 스캔 결과는 `--status-file data/connection_status.json`으로 저장할 수 있다. 실시간 모터 연동 계획과 현재 한계는 [디지털 트윈 계획](../tools/digital_twin/DEVELOPMENT_PLAN.md)을 본다.
