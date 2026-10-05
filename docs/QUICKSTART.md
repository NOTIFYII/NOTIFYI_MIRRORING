# Notifyi 빠른 시작

## 대상

삼성 노트북에서 로봇 카메라 또는 USB 웹캠으로 Notifyi 자세 반응 프로토타입을 실행하는 절차다.

## 1. 프로젝트 준비

~~~bash
cd ~/Desktop/posture_robot_proto
./.venv/bin/python --version
~~~

삼성 노트북의 실제 폴더가 다르면 경로를 바꾼다. 이후 예시의 `./.venv/bin/python`은 프로젝트 가상환경을 직접 지정하므로 셸에서 `python` 명령이 없어도 실행된다. 코드를 업데이트하는 절차는 Git 인증/작업 트리 상태를 확인한 뒤 별도로 수행한다.

## 2. 환경 점검

~~~bash
./.venv/bin/python scripts/check_env.py
~~~

check_env.py에서 카메라와 모터 버스가 모두 연결되지 않아도, 현재 테스트 단계에서는 실패 원인을 확인하는 용도로 사용할 수 있다. 실제 모터 구동 전에는 Dynamixel 스캔을 별도로 통과해야 한다.

## 3. 카메라 확인

~~~bash
ls -l /dev/video*
v4l2-ctl --list-devices
~~~

장치 경로를 확인한 뒤 실행 명령의 camera 값을 실제 경로로 바꾼다.

## 4. 모터 읽기 전용 확인

~~~bash
./.venv/bin/python scripts/scan_dynamixel.py \
  --port /dev/ttyACM0 \
  --baud 57600 --proto 2.0
~~~

OpenCR `usb_to_dxl` 브리지를 쓰는 현 설정이다. 활성 ID **2~7** 모두 응답하고 위치 제어 모드·hardware error 0인지 확인한다. ID 1·8은 유휴다. 스캔 전에는 메인 제어와 Dynamixel Wizard 등 포트를 쓰는 프로그램을 종료한다. 새 기구의 부호·브라켓 간섭이 미검증이면 스캔이 정상이어도 구동하지 않는다.

## 5. dry-run

모터에 명령을 쓰지 않고 카메라와 자세 판정만 확인한다.

~~~bash
./.venv/bin/python -m src.main --no-preview \
  --condition posture_trigger \
  --camera /dev/video0 \
  --no-camera-gimbal
~~~

노트북 웹캠은 로봇과 함께 움직이지 않으므로 no-camera-gimbal을 사용한다.

## 6. 실제 실행

기구를 안정적으로 지지하고 ID 매핑·부호·운용 범위·케이블/브라켓 간섭까지 확인했을 때만 실행한다. 현재 3D 예제는 ±30° 간섭이 있으므로 그대로 구동 테스트에 사용하지 않는다.

~~~bash
./.venv/bin/python -m src.main --no-preview --move \
  --condition posture_trigger \
  --camera /dev/video0 \
  --participant-id P01
~~~

로봇 탑재 카메라가 아니라 노트북 웹캠을 사용하면 no-camera-gimbal을 추가한다.

## 7. 종료

프리뷰 모드에서는 q 또는 Esc를 누른다. 헤드리스 모드에서는 SIGINT로 종료한다.

종료 후 토크 해제와 중립 복귀 메시지를 확인한다. 오류가 발생하면 다시 실행하기 전에 TROUBLESHOOTING.md의 안전 절차를 따른다.
