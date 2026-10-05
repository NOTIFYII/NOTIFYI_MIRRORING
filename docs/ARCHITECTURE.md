# Notifyi 아키텍처

## 1. 현재 목표

Notifyi는 책상 위에서 사용자의 나쁜 자세를 감지하고, 일정 시간 지속될 때만 미리 정한 과장 포즈로 반응하는 탁상용 로봇 프로토타입이다.

현재 실험의 기준은 다음과 같다.

- 정상 자세: 로봇은 시작 시점의 기준 자세를 유지하고 움직이지 않는다.
- 나쁜 자세가 3초 지속: 하나의 고정된 bad_posture 포즈를 실행한다.
- 나쁜 자세가 계속됨: 고정 포즈를 유지한다.
- 사용자가 정상 자세로 돌아옴: 중립으로 복귀하고 잠시 후 토크를 해제한다.
- 다시 나쁜 자세가 3초 지속: 새로운 개입 에피소드로 기록하고 다시 반응한다.
- 실제 모터 구동: 명령에 --move가 있을 때만 활성화한다.

음성, 디스플레이 표정, 바퀴 이동, ROS 2, LLM 판단, 초기 복구 모드는 현재 실행 경로에 포함하지 않는다.

## 2. 런타임 흐름

~~~text
USB 카메라
  -> CameraStream
  -> PoseEstimator / MediaPipe
  -> posture_features
  -> MedianFilter + smoothing
  -> posture.classifier
  -> BehaviorManager
       나쁜 자세 3초 지속 여부 판단
  -> BehaviorExecutor
       고정 bad_posture 생성
  -> ControlLoop
       시작 기준 유지 / 과장 포즈 / 중립 복귀
  -> SafetyGate + SlewLimiter
  -> JointMapper
       자세 포즈 -> 관절 tick
  -> JointWriter
  -> Dynamixel 버스
~~~

제어 루프와 인식 루프는 분리되어 있다. PoseBuffer는 지연 재생 버퍼가 아니라 두 스레드 사이에 최신 관측값 하나를 전달하는 상자다.

## 3. 자세 상태

| 상태 | 조건 | 모터 동작 |
| --- | --- | --- |
| good | 정상 자세가 관측됨 | 시작 기준 자세 유지 |
| bad | 상체·목·어깨선 중 하나라도 기준 초과 | 3초 지속 전까지 시작 기준 유지 |
| intervening | bad가 3초 지속됨 | 고정 과장 포즈 유지 |
| returning | 정상 자세 복귀 또는 관측 중단 | 중립으로 제한된 속도로 복귀 |
| idle | 중립 복귀 완료 | 토크 해제 |
| unknown | 사람 미검출·가림·신뢰도 부족 | 새 개입을 만들지 않음 |

정상 자세를 모터로 따라 하는 미러링은 현재 사용하지 않는다. 사용자의 자세를 그대로 모터 목표로 복사하지 않고, 개입 때만 사전 정의 포즈를 호출한다.

## 4. 현재 하드웨어 매핑

현재 설정은 2XL430-W250 버스 ID 1~8 중 ID 2~7의 6축을 사용한다. 허리 아래/위의 yaw·pitch, 목 아래 roll, 목 yaw를 구동 대상으로 둔다. 2XL 하우징별 A/B축과 실물 ID 두 개의 짝은 아직 확인되지 않았다. 이전 5축 pitch-only 구성은 현재 운용 프로파일이 아니다.

| 관절 | Dynamixel ID | 역할 | 현재 사용 |
| --- | ---: | --- | --- |
| waist_lower_yaw | 2 | 허리 아래 좌우 | 설정상 사용 |
| waist_lower_pitch | 3 | 허리 아래 상하 | 설정상 사용 |
| waist_upper_yaw | 4 | 허리 위 좌우 | 설정상 사용 |
| waist_upper_pitch | 5 | 허리 위 상하 | 설정상 사용 |
| neck_roll | 6 | 목 아래 갸우뚱 | 설정상 사용 |
| neck_yaw | 7 | 목 좌우 | 설정상 사용 |
| 유휴축 | 1, 8 | 구동 대상 아님 | 미사용 |

목표 tick은 config/joints.yaml의 zero_position, direction, min_position, max_position과 config/posture.yaml의 분배 비율로 계산한다. 실제 쓰기 직전에는 반드시 SafetyGate를 통과한다.

## 5. 탑재 카메라와 짐벌

로봇 상단 카메라를 주 실험 대상으로 삼지만 현재 6축 설정에는 `neck_pitch`가 없다. 새 축 배치에서 영상 보정을 확인하지 못했으므로 짐벌 보정은 기본 비활성화다.

- 설정: config/posture.yaml의 camera_gimbal.enabled
- 기본값: 비활성화
- 노트북 웹캠: --no-camera-gimbal
- `camera_gimbal.joint`는 현재 `neck_yaw`로 설정돼 있지만 실물 카메라의 pitch 안정화를 보증하지 않는다. 검증 전 활성화하지 않는다.

짐벌 보정은 아직 카메라 영상 안정화의 완성품이 아니다. 실제 카메라 위치, 렌즈 화각, 링크 유격을 고정한 뒤 영상 흔들림과 자세 판정 오검출을 함께 검증해야 한다.

## 6. 기능 확장 경계

새 기능은 인식이나 모터 쓰기 코드를 직접 늘리기보다 행동 종류를 분리해 추가한다.

| 행동 종류 | 현재 | 향후 담당 |
| --- | --- | --- |
| joint_motion | 사용 | Dynamixel/OpenCR 어댑터 |
| display_expression | 미구현 | 디스플레이 드라이버 |
| voice_output | 미구현 | 스피커·TTS 드라이버 |
| locomotion | 미구현 | 바퀴·모터 드라이버 |

각 행동은 요청, 실행 시작, 완료, 실패, 취소를 별도로 반환해야 한다. 판단 모듈이 모터 버스에 직접 접근하지 않는 구조를 유지한다.

## 7. 자유축 구조로 확장할 때의 경계

이전 5개 pitch 관절 구조는 문서상 과거 프로토타입일 뿐 현재 설정에 별도 런타임 프로파일로 구현돼 있지 않다. 현재 6축 배치도 기구·부호·간섭 검증 전이므로 이후 모터 수나 축 방향을 바꾸면 새 프로파일을 정의해야 한다.

향후 자유축 구조의 흐름은 다음과 같다.

~~~text
사용자 자세 feature
  -> 의미 기반 행동
  -> PosePlanner
  -> MotionPrimitive / keyframe trajectory
  -> RobotModel / JointGroup
  -> 관절별 SafetyGate
  -> 모터 그룹 출력
~~~

행동 요청에는 목표 포즈만 두지 않고 approach, emphasis, hold, recovery, speed, pause, entry, exit를 포함한다. 이를 통해 같은 자세 피드백이라도 관절 수와 기구 배치가 달라져도 표현 강도와 복귀 동작을 조정할 수 있다.

새 프로파일이 확정되기 전까지는 현재 posture_trigger와 고정 모션을 기준선으로 유지한다. 새 동작은 adaptive_mirror 또는 expressive_mirror처럼 별도 프로파일과 로그 이름으로 추가해 기준선 실험과 섞이지 않게 한다.
