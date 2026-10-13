# Notifyi
탁상용 자세 피드백 로봇의 두 모터 프로토타입이다. 카메라에서 나쁜 자세가 3초 지속되면 정해진 구부정한 포즈를 실행하고, 정상 자세가 다시 관측되면 중립으로 복귀한다.

현재 기준은 main의 두 모터 YAML이다. 몸통 ID 2와 머리 ID 3만 구동하며, 연결된 ID 1·4는 구동하지 않는다. zero는 각각 1 / 1022 ticks, 상대 운용 범위는 몸통 -30°~0° / 머리 ±30°다. 머리 범위는 사용자 확인에 따라 확장했으며 고정 피드백 목표는 기존 2°를 유지한다. 버스는 OpenCR USB 브리지, /dev/ttyACM0, 57600 bps, Protocol 2.0이다.

사람 미감지 시 진행 중인 목표를 실측 위치로 바꿔 유지한다. 시작·감지 손실·종료 때 zero로 자동 초기화하지 않는다. 토크는 자동 해제하지 않으므로 종료 후 상태를 확인해야 한다. 이 동작은 실물에서 아직 재검증되지 않았다.

## 실행
Raspberry Pi 3 B+에서는 Python 3.12 + MediaPipe 0.10.13 환경을 사용한다. 이 조합의 모델 초기화는 해당 Pi에서 확인됐으며 실제 사람 감지·모터 동작 검증은 별도다.

```bash
cd ~/notiFYI
.venv-mp-test/bin/uv pip install --python .venv-mp-pi3/bin/python -r requirements.txt
.venv-mp-pi3/bin/python -m src.main --no-preview --condition posture_trigger
```

위 명령은 모터 없는 검사다. SSH에서는 --no-preview가 필요하다. 실제 구동 옵션은 --move이며, 최신 코드의 감지·목표 유지와 실물 초기 위치를 확인한 뒤 사용한다. 자세 입력에서 모터 허용 각도는 적용하지 않고, 고정 모션 출력에만 적용한다.

Gemini API 키·마이크·스피커·사용자별 캘리브레이션은 현재 실행에 필요하지 않다. voice/mirror 조건과 --calibrate는 활성 CLI에서 분리했다. 자세 반응 방식의 이름은 여전히 posture_trigger다.

## 파일 구조
```text
config/                 두 모터 설정 (main YAML 유지)
src/                    인식·자세 정책·고정 행동·모터·안전·로그
scripts/                현재 검사/설정 도구
tests/                  활성 런타임 회귀 테스트
docs/                   실행·설정·구조·코드 리뷰
legacy/                 옛 Gemini/음성/캘리브레이션/실험 및 의존성
models/pose/            자세 모델
data/runs/              로컬 JSONL 로그
```

전체 안내는 [docs](docs/README.md), 자세한 트리는 [실행 구조](docs/ARCHITECTURE.md), 발견과 수정 내역은 [main 코드 리뷰](docs/MAIN_CODE_REVIEW.md)에 정리했다. 보관 기능은 [legacy 안내](legacy/README.md)를 참고한다.

3D 모델링 작업은 별도 minwook 작업 공간에 보관한다. main에는 3D 폴더와 관련 테스트를 포함하지 않는다.

## 검증
```bash
python -m pytest tests -q
```

테스트는 모터를 연결하지 않고 수행한다. 상대 제한·위치 경계·감지 손실·선택 의존성 분리·종료 처리를 검증하며, 실물 하중과 전도 안정성은 검증하지 않는다.
