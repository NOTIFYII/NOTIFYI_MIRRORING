# 현재 설정 기준
최신 main의 두 구동 모터 설정을 사용한다. 머리 운용 범위는 사용자 확인에 따라 ±30°로 확장했다.

| 항목 | body_pitch | head_pitch |
| --- | --- | --- |
| 모터 ID | 2 | 3 |
| 역할 | 몸통 앞뒤 | 머리 앞뒤 |
| zero_position | 1 ticks | 1022 ticks |
| direction | -1 (키보드 s) | +1 (키보드 w) |
| zero 기준 위치 범위 | -30°~+4° | -30°~+30° |
| operating_mode | 4 (확장 위치) | 3 (단회전, 기본값) |
| 소프트웨어 절대 한계 | -340~46 ticks | 0~4095 및 상대 범위 |
| wrap_position | false | true |

버스는 OpenCR USB 브리지, /dev/ttyACM0, 57600 bps, Protocol 2.0이다. 연결 ID는 1~4, 구동 ID는 2·3, 미구동 ID는 1·4이다. 2XL430 하우징의 두 축을 두 구동 ID와 혼동하지 않는다.

- config/robot.yaml: 연결 버스와 활성 ID.
- config/joints.yaml: 관절의 zero·방향·절대/상대 제한.
- config/posture.yaml: 인식·정책·고정 포즈·안전 제한.

몸통은 zero 1에서 앞으로 30°를 -340 ticks로 계산한다. mode 4에서 현재·목표 위치를 signed 연속 좌표로 읽고 쓰며 modulo로 3756으로 바꾸지 않는다. 현재 40 ticks(약 +3.4°)는 사용자 확인 정상 자세로 허용한다. 정수 상대 경계는 안쪽으로 반올림한다. 시작 실측이 범위 밖이면 자동 복귀하거나 한 바퀴를 제거하지 않고 중단한다. 머리는 기존 단회전 좌표를 유지한다.

앱은 모드를 자동 변경하지 않는다. 시작 시 모든 관절의 실제 모드와 YAML 일치를 검사하고, 몸통 Drive Mode 0 / Homing Offset 0도 확인한다. 실제 ID 2는 별도 전환 도구로 mode 4로 바꿔야 한다. mode 4에서는 모터 EEPROM Min/Max Position Limit이 적용되지 않으므로 mapper·gate·writer에서 소프트웨어 한계를 적용한다. 단회전 머리축의 경계 점프 차단은 유지한다. [공식 Goal Position 설명](https://emanual.robotis.com/docs/en/dxl/x/2xl430-w250/#goal-position116)

머리 관절 운용 범위는 ±30°이며, zero 1022 기준 정수 목표 범위는 681~1363 ticks다. 현재 1121 ticks(약 +8.7°)도 허용한다. 고정 피드백 목표와 angles.max_neck_pitch_deg는 기존 2°를 유지하므로 범위 확장이 곧 30° 동작을 의미하지 않는다. 관측은 필터링 후 그대로 분류하고, BehaviorExecutor→SafetyGate→JointMapper에서 모터 출력을 제한한다.

correction.sustain_seconds는 3초 그대로다. echo.delay_sec와 echo.buffer_seconds는 main YAML에 남아 있지만 현재 실행에서는 읽지 않는다. 지연 미러링 경로를 분리했으므로 control_hz만 제어 주기로 사용한다. YAML의 사람 이탈 후 복귀 관련 옛 주석도 이번에는 값을 보존하기 위해 수정하지 않았다. 현재 동작은 감지 손실 시 위치 유지다.

camera_gimbal은 false다. 탑재 카메라의 실제 회전축·광축 검증 전 활성화하지 않는다. 머리 ±30°는 사용자 확인 범위이며 자동 하중·간섭 검증 결과가 아니다.
