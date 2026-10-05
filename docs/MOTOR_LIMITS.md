# Notifyi 모터 한계와 기준 위치

현재 값은 [`config/joints.yaml`](../config/joints.yaml)의 **설정값**이다. 새 조립의 실측 기계 한계나 안전한 다축 가동 범위를 증명하지 않는다. 2XL 하우징별 A/B축↔ID 쌍도 아직 검증 전이다.

## 용어

- `zero_position`: 현재 조립에서 기준으로 기록한 tick. 모터 절대 원점이나 자동 기립 목표가 아니다.
- `min_position/max_position`: 현재 모두 0~4095. 모터의 한 바퀴 위치 숫자 범위이지 실측 기구 끝각이 아니다.
- `relative_min_deg/relative_max_deg`: zero에서 허용하는 **잠정 소프트 제한**. 최종 목표는 JointMapper와 SafetyGate가 제한한다.
- `direction`: 입력 의미축의 양의 방향과 모터 tick 방향의 관계. 현 설정값 중 일부는 실물 단축 시험 전이다.
- `wrap_position`: zero가 0/4095 경계 부근일 때 최단 tick 차이로 처리한다. 단순 숫자 비교로 한계를 판정하지 않는다.

## 현재 6축 설정

| 관절 | ID | zero tick | 상대 제한(도) | direction | 검증 상태 |
| --- | ---: | ---: | ---: | ---: | --- |
| waist_lower_yaw | 2 | 1034 | −45~+45 | +1 | 현 설정, 기구 검증 전 |
| waist_lower_pitch | 3 | 3059 | −21.1~+12 | −1 | 앞쪽 목표 2819 tick 부근을 참고한 잠정값 |
| waist_upper_yaw | 4 | 2040 | −45~+45 | +1 | 현 설정, 기구 검증 전 |
| waist_upper_pitch | 5 | 12 | −12~+12 | +1 | 0/4095 경계 감김, 과거 과부하·전도 주의 |
| neck_roll | 6 | 38 | −12~+12 | +1 | 0/4095 경계 감김, 기구 검증 전 |
| neck_yaw | 7 | 3039 | −12~+12 | +1 | 현 설정, 기구 검증 전 |

ID 1·8은 버스에 있어도 현재 구동 대상이 아니다. ID 5·6의 원시 스캔값이 4095를 조금 넘더라도 위치 제어 기준값은 4096 tick 한 바퀴로 정규화한다. 원시값, 동작 모드, 토크 상태를 함께 기록해야 전원 재인가·모드 변경 이후의 값을 올바르게 해석할 수 있다. [ROBOTIS 2XL430 제어표](https://emanual.robotis.com/docs/en/dxl/x/2xl430-w250/)는 Present Position 리셋 조건을 별도로 설명한다.

## 개입 포즈와 실제 목표

현재 `config/posture.yaml`의 고정 `bad_posture` 요청은 torso pitch 60°, torso yaw 18°, neck yaw 18°, neck roll 12°다. torso pitch는 ID 3·5에 0.5씩, torso yaw는 ID 2·4에 0.5씩 분배된다. 요청값은 각 관절의 `direction`, 상대 제한 및 안전 게이트를 통과하므로 실제 명령 tick과 같지 않다. 설정에 있는 `neck_pitch_deg: 35`는 현 `distribution`에 대응 관절이 없어 현재 6축에서 독립적인 목 숙임 명령으로 구현된 것이 아니다.

3D 조립판의 A/B축 ±90°는 **화면 미리보기**다. [CAD 검토](../tools/digital_twin/CAD_FIT_AUDIT.md)에서 현 예제 조립은 ±30° 간섭이 확인됐다. 따라서 미리보기 각도나 소프트 제한만 보고 실물을 돌리지 않는다.

## 점검·변경 절차

메인 제어·Wizard를 중지하고, 삼성 노트북의 프로젝트 루트에서 읽기 전용으로 확인한다.

~~~bash
./.venv/bin/python scripts/scan_dynamixel.py --port /dev/ttyACM0 --baud 57600 --proto 2.0
~~~

활성 ID 2~7 모두의 위치 제어 모드·오류 0·현재 위치를 확인한다. zero·부호·상대 범위를 바꿀 때는 설정 diff, 매핑/안전 테스트, 토크 없는 수동 가동 범위, 지지한 상태의 저속·소각 단축 시험, 브라켓/케이블 간섭을 차례로 확인한다. 구조물을 지탱하는 관절은 토크 해제 시 넘어질 수 있다. 한 축에서 통과한 범위를 다축 동시 구동의 안전 범위로 확대 해석하지 않는다.
