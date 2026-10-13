# 활성 실행 구조
카메라 → PoseEstimator → filter_observation → classify → BehaviorManager → BehaviorExecutor → SafetyGate → JointMapper → ControlLoop → JointWriter.

BehaviorManager는 로컬 3초 지속 규칙으로 이벤트를 만든다. Gemini·STT·TTS·저장된 사용자 캘리브레이션을 현재 실행 경로에서 import하지 않는다. CLI 조건은 posture_trigger 하나다.

모델과 카메라 준비 후 제어 스레드를 시작한다. 처음 읽은 실측 위치를 대기 기준으로 잡고 목표를 쓴 뒤 토크를 켠다. 처음부터 사람이 보이지 않으면 zero로 이동하지 않는다. 감지 손실 시 진행 중인 목표를 실측 위치로 바꿔 유지한다. 오래된 관측으로 지속시간을 채우거나 행동을 실행하지 않는다. 정상 자세가 다시 관측되면 고정 개입 포즈에서 zero로 복귀할 수 있으나, 토크는 자동으로 풀지 않는다. 종료나 오류에서도 추가 zero 이동·자동 토크 해제를 하지 않는다.

토크 유지에는 지속 부하가 있으므로 이것을 과부하 보호 기능으로 해석하지 않는다. 하드웨어 오류·통신 실패 시 위치 및 토크 상태가 불확실할 수 있다. 수동 토크 해제는 로봇을 지지한 상태에서 별도 도구로 한다.

```text
config/                  main 기준 두 모터 YAML (변경 없음)
src/
  main.py                실행 CLI·카메라 루프·모터 제어
  camera/                USB 카메라 입력
  perception/            모델·상체 지표·필터
  posture/               분류·3초 정책·최신 관측 저장
  behavior/              로컬 이벤트·고정 포즈
  robot/                 버스·관절 매핑·출력
  safety/                출력 제한·감지 손실 상태·watchdog
  telemetry/             JSONL 실험 로그
scripts/                 현재 환경/카메라/모델/모터 검사 도구
tests/                   활성 코드와 안전 경로의 하드웨어 없는 테스트
docs/                    현재 기준 문서
legacy/
  src/                   Gemini·음성·캘리브레이션·옛 mock
  scripts/               옛 음성/카메라/신호 측정 실험
  tests/                 보관된 TTS 테스트
  docs/                  옛 YEGAM 흐름·복구 계획
  requirements.txt       보관 기능 전용 의존성
models/pose/             별도 자세 모델 자산
data/runs/               실행 로그 (git 제외)
```

tests의 예전 다섯 관절 mock은 범용 매핑 회귀 테스트의 입력이며 실제 하드웨어 설정이 아니다. 현재 실물 계약은 test_main_runtime.py에서 main YAML로 별도 확인한다.

3D 모델링 폴더는 별도 minwook 작업 공간에 남겨두며 main에는 포함하지 않는다.
