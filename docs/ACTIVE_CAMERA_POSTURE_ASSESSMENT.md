# Notifyi 능동 카메라 기반 상체 자세 평가안

조사·논의 기준: 2026-10-02

**상태: 설계안.** 다각도 능동 관측, `CAMERA_MOVING/SETTLING` 상태, 작업물 기반 필기/독서 구분은 현재 런타임에 구현되지 않았다. 현 `camera_gimbal.enabled`도 false다. 현재 코드의 판정·로그와 혼동하지 않는다.

이 문서는 탁상용 로봇의 위치와 카메라 시점이 달라져도 자세 평가 품질을 유지하고, 카메라 움직임을 이용해 작업상 필요한 숙임과 무의식적인 나쁜 자세를 구분하기 위한 설계안이다.

현재 로봇 카메라는 사용자의 가슴 위 영역을 주로 촬영한다. 골반과 팔이 항상 보이지 않는다는 전제를 두며, 이 문서에서 말하는 자세값은 의학적 신체 각도가 아니라 영상 기반 상체 자세 proxy다.

## 1. 문제 정의

현재 환경에서는 다음 문제가 반복될 수 있다.

- 로봇이 사용자 정면 또는 대각선에 놓이면 한쪽 어깨가 가려진다.
- 카메라 화각이 좁아 골반과 팔이 프레임 밖으로 빠진다.
- 로봇이 이동하거나 카메라를 움직이면 landmark 위치가 함께 바뀐다.
- 고개를 숙이는 작업 자세와 무의식적인 구부정 자세가 비슷하게 보인다.
- 카메라 시점 변화가 실제 자세 변화로 잘못 해석될 수 있다.

따라서 목표는 모든 신체 관절을 복원하는 것이 아니라 다음 세 가지를 안정적으로 구분하는 것이다.

1. 관측 가능한 상체가 정상인지
2. 상체 자세가 일정 시간 무너졌는지
3. 현재 관측이 불충분해 판단을 보류해야 하는지

## 2. 현재 측정 범위

### 신뢰할 수 있는 입력

- 코와 귀를 이용한 머리 위치·방향
- 양쪽 어깨가 보일 때의 어깨선
- 머리 중심과 어깨 중심의 상대 위치
- 어깨와 머리의 시간적 변화
- 각 landmark의 visibility와 추적 안정성

MediaPipe Pose Landmarker는 이미지 landmark와 world landmark를 함께 제공하고 landmark별 visibility도 제공한다. 다만 현재 촬영 범위가 가슴 위로 제한되므로, 보이지 않는 골반을 전제로 한 전체 몸통 각도를 그대로 복원할 수 있다고 가정하지 않는다.

참고:

- [MediaPipe Pose Landmarker 공식 문서](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker)
- [BlazePose 논문](https://arxiv.org/abs/2006.10204)

### 현재 사용할 수 없는 입력

- 골반 중심과 골반선
- 팔과 손의 움직임
- 책·종이·키보드와의 직접적인 관계
- 단안 RGB 카메라로 얻은 신뢰할 수 있는 실제 척추 각도

팔과 작업물이 보이지 않는 상태에서는 필기·독서 의도를 영상만으로 확정할 수 없다. 해당 구분은 실험 조건, 키보드·마우스 활동, 추가 시야 확보 중 하나가 필요하다.

## 3. 자세 feature 재정의

현재처럼 어깨선 하나를 주 지표로 사용하지 않고, 관측 가능한 상체 feature를 조합한다.

| feature | 의미 | 사용 조건 |
| --- | --- | --- |
| neck_flexion_proxy | 머리 중심이 어깨 기준으로 내려가거나 앞으로 벗어난 정도 | 머리와 어깨 일부 |
| shoulder_roll_proxy | 양쪽 어깨선의 좌우 기울기 | 양쪽 어깨 |
| head_offset_proxy | 머리 중심과 어깨 중심의 수평 이격 | 양쪽 어깨 또는 추정 중심 |
| upper_body_compression_proxy | 머리와 어깨 사이 간격의 시간적 감소 | 가슴 위 영상 |
| observation_quality | 현재 자세 판단이 가능한지 | 모든 프레임 |

현재 코드에서 골반이 보이지 않을 때 torso_compression을 머리-어깨 간격으로 대체하는 방식은 실제 몸통 굽힘과 고개 숙임을 구분하지 못한다. 따라서 이 값은 torso_pitch가 아니라 upper_body_compression_proxy로 명명하고, 실제 척추 각도로 해석하지 않는다.

## 4. 부분 landmark 처리

양쪽 어깨가 모두 보여야 전체 측정을 시작하는 방식은 대각선 배치에 취약하다. landmark 가시성에 따라 측정 범위를 줄인다.

| 관측 상태 | 허용 판정 | 행동 |
| --- | --- | --- |
| 양쪽 어깨·머리 안정 | 상체 feature 전체 | 정상적인 자세 평가 |
| 한쪽 어깨·머리 안정 | 목·머리 proxy만 | 낮은 신뢰도, 추가 시점 요청 |
| 머리만 안정 | 목 방향 후보만 | 나쁜 자세 개입 금지 |
| 핵심 landmark 불안정 | 판정 불가 | unknown 기록 |

한쪽 어깨가 안 보였다고 사람 전체를 정상 또는 나쁜 자세로 치환하지 않는다. partial과 unknown을 구분해 기록한다.

## 5. 시점별 카메라 모드

카메라 움직임은 표현 동작이 아니라 판단을 위한 능동 관측으로 사용한다.

| 모드 | 목적 | 주요 feature |
| --- | --- | --- |
| front_observe | 기본 상체 관측 | 머리·양쪽 어깨 |
| diagonal_inspect | 한쪽 가림 보완, 상체 기울기 확인 | 머리·보이는 어깨·상체 외곽 |
| task_inspect | 작업상 필요한 숙임 확인 | 책상·손·작업물 |
| stabilized_observe | 이동 후 최종 판정 | 안정화된 landmark |

권장 흐름은 다음과 같다.

~~~text
front_observe
  -> 신뢰도 충분: 자세 판정
  -> 신뢰도 부족: diagonal_inspect
  -> 작업 자세 의심: task_inspect
  -> 카메라 정지·안정화
  -> 결과 결합
~~~

카메라 이동은 신뢰도가 낮을 때만 수행한다. 계속 사람을 따라 움직이면 카메라 변화와 자세 변화가 섞이고, 로봇 자체가 사용자의 주의를 불필요하게 끌 수 있다.

## 6. 카메라 이동 중 상태 처리

카메라가 움직이는 프레임은 자세 판정에 사용하지 않는다.

~~~text
STABLE
  -> CAMERA_MOVING
  -> SETTLING
  -> STABLE
~~~

- CAMERA_MOVING: landmark와 자세 타이머를 갱신하지 않음
- SETTLING: 0.5~1초 동안 영상 흔들림과 visibility 확인
- STABLE: 일정 프레임 이상 안정된 뒤 자세 판정 재개

카메라 이동 뒤 나쁜 자세 시간이 새로 시작되는지, 기존 timer를 이어갈지는 별도 실험 변수다. 초기에는 안전하게 새 관측 구간으로 시작한다.

## 7. 로봇 위치 변화에 대한 품질 유지

로봇이 사용자 앞·뒤 또는 대각선으로 이동해도 raw pixel 위치를 직접 비교하지 않는다.

다음과 같은 상대 feature를 사용한다.

- 머리 중심과 어깨 중심의 상대 위치
- 몸 크기 대비 머리-어깨 간격
- 어깨선의 기울기
- landmark visibility
- 사람 bounding box 크기
- 카메라 위치와 방향

어깨 폭은 대각선 시점에서 작아질 수 있으므로 유일한 정규화 기준으로 사용하지 않는다. 가능한 경우 어깨 폭, 얼굴 폭, 머리-어깨 거리 등 여러 거리 중 안정적인 값을 선택한다.

카메라 위치별로 다음 상태를 기록한다.

~~~text
robot_pose
camera_pose
person_scale
landmark_visibility
observation_quality
~~~

시점별 feature 분포가 다르면 raw threshold를 하나로 공유하지 않고, 먼저 시점별 품질과 오검출률을 비교한다.

## 8. 작업상 필요한 숙임과 나쁜 자세 구분

가슴 위만 보이는 영상에서는 필기·독서와 무의식적 구부정 자세를 완전히 구분할 수 없다. 따라서 초기 단계에서는 자동 추론보다 조건을 분리한다.

### 실험 조건

~~~text
task_context = typing
task_context = writing
task_context = reading
task_context = free_work
~~~

작업상 필요한 자세에서는 개입하지 않고 다음처럼 기록한다.

~~~text
posture_label: upper_body_compression
task_context: writing
intervention_attempted: false
intervention_suppressed: true
suppression_reason: task_required_posture
~~~

### 향후 자동 구분 신호

- 손·팔이 책상 영역에서 움직이는지
- 키보드·마우스 입력이 발생하는지
- 머리가 작업물 방향으로 향하는지
- 숙임이 짧은지 장시간 지속되는지
- 카메라의 task_inspect에서 작업물이 보이는지
- 최근 개입 후 사용자가 회복했는지

카메라 이동으로 작업물을 확인할 수 없으면, 자동 구분의 확신도를 낮추고 개입을 보류한다.

## 9. 개입 판단 규칙

초기 baseline은 기존 3초 지속 조건을 유지한다. 다만 3초 타이머는 reliable 상태에서만 진행한다.

~~~text
reliable + upper_body_bad 3초 지속
  -> posture_trigger

partial
  -> 추가 관측 요청

camera_moving / settling / unknown
  -> timer 중단 또는 새로 시작

task_required_posture
  -> 개입 억제, 로그만 기록
~~~

개입 이후에는 카메라를 작업 확인 모드에 계속 두지 않고, 사용자의 상체 회복을 확인할 수 있는 안정된 관측 모드로 돌아간다.

## 10. 로그 필드

카메라 시점과 판단 품질을 효과 분석에 연결한다.

- robot_pose
- camera_pose
- camera_mode
- camera_motion_started
- camera_motion_stabilized
- observation_quality
- landmark_visibility_head
- landmark_visibility_left_shoulder
- landmark_visibility_right_shoulder
- person_scale
- task_context
- posture_label
- intervention_attempted
- intervention_suppressed
- suppression_reason
- response_onset_sec
- confirmed_response_time_sec

이 로그가 있어야 개입 효과와 카메라 시점 실패를 구분할 수 있다.

## 11. 검증 실험

### 위치와 시점

- 정면 0도
- 좌측 대각선 30도
- 우측 대각선 30도
- 좌측·우측 대각선 45도
- 기준 거리보다 가까운 위치
- 기준 거리보다 먼 위치

### 자세

- 정상 상체
- 고개만 숙임
- 어깨가 함께 무너짐
- 좌우 기울임
- 잠깐 숙였다 회복
- 3초 이상 지속되는 나쁜 자세

### 작업

- 타이핑
- 필기
- 책 읽기
- 작업 없이 앉아 있기

### 비교 지표

- 양쪽 어깨 검출률
- 부분 landmark fallback 비율
- unknown 비율
- 정상 자세 오검출률
- 나쁜 자세 미검출률
- 작업 자세 오개입률
- 카메라 이동 후 안정화 시간
- 카메라 시점별 회복시간 편차

평가 품질이 같다는 것은 모든 시점에서 raw angle이 같다는 뜻이 아니라, 위치·시점별로 검출 가능성, 오검출률, 미검출률, 회복시간이 허용 범위 안에 있다는 뜻으로 정의한다.

## 12. 구현 순서

1. 골반·팔이 없다는 전제로 feature 이름과 의미를 정리한다.
2. 골반이 없을 때 torso_pitch로 오해하지 않도록 proxy를 분리한다.
3. 양쪽 어깨 필수 조건을 완화하고 partial/unknown을 추가한다.
4. 어깨 폭 단일 정규화를 여러 거리 기반 정규화로 바꾼다.
5. 카메라 이동 중 판정 중단과 안정화 상태를 추가한다.
6. front_observe와 diagonal_inspect를 로그 전용으로 시험한다.
7. task_inspect에서 작업물·손 정보가 실제로 확보되는지 확인한다.
8. 위치·시점별 데이터가 쌓인 뒤에만 개입 여부에 연결한다.

## 13. 보류할 것

- 가슴 위 영상만으로 실제 척추 각도를 산출하는 것
- 카메라가 움직이는 프레임을 그대로 자세 판정에 사용하는 것
- 한쪽 어깨가 안 보인 상황을 정상 자세로 간주하는 것
- 고개 숙임만으로 필기·독서를 확정하는 것
- 시점별 차이를 임계값 조정만으로 해결하는 것
- 신뢰도가 낮은 상태에서 더 과장된 로봇 동작으로 대응하는 것

핵심 원칙은 **보이는 신체만 측정하고, 보이지 않는 신체는 추정으로 채우지 않으며, 애매하면 카메라를 움직여 추가 정보를 얻거나 개입을 보류하는 것**이다.
