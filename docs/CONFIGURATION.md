# 현재 설정 기준
세 YAML은 이번 정리에서 변경하지 않았다. 최신 main의 두 구동 모터 설정을 그대로 사용한다.

| 항목 | body_pitch | head_pitch |
| --- | --- | --- |
| 모터 ID | 2 | 3 |
| 역할 | 몸통 앞뒤 | 머리 앞뒤 |
| zero_position | 1 ticks | 1022 ticks |
| direction | -1 (키보드 s) | +1 (키보드 w) |
| zero 기준 위치 범위 | -30°~0° | -2°~+2° |
| wrap_position | true | true |

버스는 OpenCR USB 브리지, /dev/ttyACM0, 57600 bps, Protocol 2.0이다. 연결 ID는 1~4, 구동 ID는 2·3, 미구동 ID는 1·4이다. 2XL430 하우징의 두 축을 두 구동 ID와 혼동하지 않는다.

- config/robot.yaml: 연결 버스와 활성 ID.
- config/joints.yaml: 관절의 zero·방향·절대/상대 제한.
- config/posture.yaml: 인식·정책·고정 포즈·안전 제한.

zero=1 부근의 몸통은 4095→0 경계에 걸린다. 매핑과 목표 변화량은 짧은 원주 방향 차이를 사용하고, 상대 범위를 적용한다. 상대 각도 경계는 정수 tick에서 바깥으로 반올림하지 않는다. 시작 실측이 상대 범위 밖이면 자동으로 움직여 맞추지 않고 실행을 중단한다.

숫자의 최단 원주 차이가 실제 모터의 짧은 회전을 보장하지는 않는다. 현재 Position Control(mode 3)의 Goal 범위는 0~4095이며 Extended Position(mode 4)과 다르다. 실제로 0/4095를 넘는 큰 숫자 점프는 하드웨어 쓰기 전에 차단한다. zero/기계 배치·Homing Offset·모터 모드 중 무엇을 사용할지는 실물로 별도 결정해야 한다. 이번 작업에서는 EEPROM이나 모드를 바꾸지 않는다. [ROBOTIS 공식 제어 모드·Goal Position 설명](https://emanual.robotis.com/docs/en/dxl/x/2xl430-w250/#goal-position116)

머리 ±2°는 출력 허용 범위다. 사람이 목을 20° 숙였다는 관측까지 2°로 잘라서는 안 된다. 관측은 필터링 후 그대로 분류하고, BehaviorExecutor→SafetyGate→JointMapper에서 모터 출력을 제한한다.

correction.sustain_seconds는 3초 그대로다. echo.delay_sec와 echo.buffer_seconds는 main YAML에 남아 있지만 현재 실행에서는 읽지 않는다. 지연 미러링 경로를 분리했으므로 control_hz만 제어 주기로 사용한다. YAML의 사람 이탈 후 복귀 관련 옛 주석도 이번에는 값을 보존하기 위해 수정하지 않았다. 현재 동작은 감지 손실 시 위치 유지다.

camera_gimbal은 false다. 탑재 카메라의 실제 회전축·광축 검증 전 활성화하지 않는다. 목 이동 범위를 넓히는 일도 이 코드 정리에 포함되지 않는다.
