# Notifyi 문제 해결

## 공통 원칙

모터가 이상하게 움직이거나 과부하가 의심되면 실행을 반복하지 않는다. 로봇이 토크에 기대어 서 있다면 **먼저 구조물을 지지**하고, 정지·토크/전원 처리 후 전원·배선·현재 위치·hardware error를 확인한다. 토크를 무작정 해제하면 넘어질 수 있다.

## 카메라를 열 수 없음

확인:

~~~bash
ls -l /dev/video*
v4l2-ctl --list-devices
fuser /dev/video0
~~~

조치:

1. 다른 카메라 프로그램을 종료한다.
2. 실행 명령의 camera 경로를 실제 장치로 바꾼다.
3. 카메라 권한과 USB 연결을 확인한다.
4. 프리뷰 창을 사용하는 환경에서 먼저 dry-run으로 확인한다.

카메라가 노트북에 있는데 /dev/video0이 아니라면 장치 번호가 달라질 수 있다.

## 사람을 인식하지 못함

- 얼굴과 상체가 프레임 안에 있는지 확인한다.
- 카메라가 너무 낮거나 위에 있지 않은지 확인한다.
- 역광과 강한 그림자를 줄인다.
- 카메라 해상도는 우선 640 x 480으로 고정한다.
- 자세가 계속 unknown이면 짐벌이 움직이는 동안 판정하고 있지 않은지 확인한다.

현재 시스템은 unknown을 good이나 bad로 바꾸지 않는다. 인식이 끊긴 상태에서 개입하지 않는 것은 정상 동작이다.

## 모터 ID가 누락됨

~~~bash
./.venv/bin/python scripts/scan_dynamixel.py \
  --port /dev/ttyACM0 --baud 57600 --proto 2.0
~~~

먼저 메인 제어·Dynamixel Wizard가 포트를 사용 중인지 확인한다. 그다음 OpenCR USB·외부 12V 전원·TTL 3핀 데이지체인·57600bps를 확인한다. 현재 메인 제어에 필요한 ID는 **2~7**, 유휴 ID는 1·8이다. `/dev/ttyACM0`가 다른 번호로 바뀌었으면 장치 경로를 다시 찾는다.

## 특정 ID가 응답하지 않거나 과부하임

1. 모터에 토크를 계속 걸지 않는다.
2. 로봇의 하중을 손으로 줄인다.
3. 스캔으로 hardware error와 현재 위치를 확인한다.
4. 실제 오류 ID와 하중을 확인한 후 `torque_off.py`를 사용한다.

~~~bash
./.venv/bin/python scripts/torque_off.py --ids 5
./.venv/bin/python scripts/torque_off.py --ids 5 --clear-errors
~~~

`5`는 예시이므로 오류 ID로 바꾼다. 오류가 계속되면 재부팅 전에 기구적 걸림, 케이블, 브라켓 간섭을 확인한다. 구조물이 쓰러질 위험이 있으면 토크 해제 전 지지한다.

## 모터는 응답하지만 움직이지 않음

- 실행 명령에 move가 있는지 확인한다.
- 대상 모터가 위치 제어 모드인지 확인한다.
- 활성 ID 2~7의 `direction`과 물리 A/B축 매핑을 확인한다.
- 현재 위치가 운용 범위 안인지 확인한다.
- 대상이 유휴축 ID 1·8인지 확인한다.
- safe stop이 발생했는지 터미널의 SAFE_STOP 메시지를 확인한다.

## 실행 직후 고꾸라짐

메인에는 자동 기립/복구가 없다. 토크 인가 전 하부 관절과 지지 구조를 확인하고, 손으로 안전하게 기준 자세에 세운 뒤 스캔한다. 새 조립의 부호·간섭을 단축 시험하기 전에는 `--move`를 실행하지 않는다. `zero_position`으로 자동 복구된다고 가정하지 않는다.

## 로그가 없음

로그 경로는 config/posture.yaml의 experiment.log_dir이다. 기본값은 data/runs다.

~~~bash
ls -l data/runs
python scripts/summarize_posture_logs.py \
  --input data/runs \
  --output-dir data/summaries
~~~

로그 디스크 오류는 로봇 제어를 중단시키지 않도록 설계되어 있으므로, 로그 파일 권한도 별도로 확인한다.
