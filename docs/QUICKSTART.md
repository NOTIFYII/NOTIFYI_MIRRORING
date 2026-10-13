# Raspberry Pi 3 B+ 실행
실물 경로는 ~/notiFYI다. Python 3.13 + MediaPipe 1.x에서는 libmediapipe.so의 AES 기능 검사에서 SIGILL이 재현됐다. Python 3.12 + MediaPipe 0.10.13 모델 초기화는 실물 Pi에서 통과했다. requirements.txt는 그 버전을 유지하며 Gemini·음성 의존성을 설치하지 않는다.

기존에 만든 .venv-mp-pi3 환경을 사용한다. 활성화된 쉘에 (.venv)가 표시되어도 아래 명령은 지정한 Python 3.12 환경을 사용한다.

```bash
cd ~/notiFYI
.venv-mp-pi3/bin/python --version
.venv-mp-test/bin/uv pip install --python .venv-mp-pi3/bin/python -r requirements.txt
.venv-mp-pi3/bin/python -m src.main --no-preview --condition posture_trigger
```

처음 설정하는 환경에서는 uv로 Python 3.12 환경을 만들 수 있다.

```bash
uv python install 3.12
uv venv --python 3.12 .venv-mp-pi3
uv pip install --python .venv-mp-pi3/bin/python -r requirements.txt
```

SSH에서는 --no-preview를 사용한다. 그래픽 데스크톱 세션에서만 해당 옵션을 빼 프리뷰를 띄운다. 디스플레이 없는 Linux 세션에서는 모델·모터 초기화 전에 오류로 종료한다.

```bash
.venv-mp-pi3/bin/python scripts/check_env.py
.venv-mp-pi3/bin/python scripts/scan_dynamixel.py --port /dev/ttyACM0 --baud 57600 --proto 2.0
```

check_env와 scan은 토크를 켜거나 목표 위치를 쓰지 않는다. 환경 검사의 성공은 자세 인식 정확도나 모터 하중 검증의 성공을 뜻하지 않는다.

모터 없는 실행에서 사람이 보일 때 측정값이 나오고, 가림 시 person_lost_hold와 목표 유지가 확인된 뒤에만 실제 구동을 검토한다. 사용자가 목 ID 3의 실측 1121이 정상 자세이고 zero 기준 ±30° 이동이 가능함을 확인해 운용 범위를 확장했다. zero는 1022로 유지하며, 범위 밖 위치의 시작은 여전히 거부한다. 몸통 경계 점프 차단과 시작 시 자동 초기화 금지는 그대로다.

실제 구동 옵션은 --move다. 이번 변경의 실물 모터 테스트는 수행하지 않았다. 앱은 종료할 때 토크를 자동으로 풀지 않으므로 종료 후 토크 상태를 스캔해 확인한다. 로봇을 지지한 뒤 수동 해제가 필요한 경우:

```bash
.venv-mp-pi3/bin/python scripts/torque_off.py --ids 2 3
```

카메라 장치가 바쁘면 sudo fuser -v /dev/video0로 사용 프로세스를 확인한다. 이 Pi에서는 motion 서비스의 카메라 점유가 이전에 확인됐다.
