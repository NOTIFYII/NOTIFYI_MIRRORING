# 몸통 좌표 경계 진단

몸통 zero는 1 ticks다. −30°~+4°의 비정규화 끝점은 −340~46 ticks이며,
단회전 숫자로 바꾸면 3756~46이므로 0/4095 경계 차단이 발생한다.
정상 시작 자세 40 ticks를 허용하는 일과 이동 경로 검증은 별개다.

## 먼저 읽기만 수행

앱·위자드·다른 스캔을 종료하고 로봇을 지지한다. 토크를 끄지도 켜지도 않는다.

```bash
cd ~/notiFYI
.venv-mp-pi3/bin/python scripts/inspect_motor_coordinates.py --id 2 --output data/motor_coordinates_id2.json
```

모델 번호, Drive Mode, Operating Mode, Homing Offset, 위치 한계, Torque Enable,
Hardware Error, Goal Position, Present Position과 YAML을 함께 기록한다.
32-bit 오프셋·위치는 부호 있게 표시한다. 기존 기록은 덮어쓰지 않으며 다시 보관하려면
다른 출력 파일명을 지정하거나 `--output` 없이 화면에서 확인한다.
통신 실패·다른 모델은 중단하며 쓰기·재부팅·이동 기능은 없다.

## 결과 이후 결정할 것

1. 실제 mode 3인지, 기존 오프셋이나 역방향 설정이 있는지 확인한다.
2. 기계적 기준 재배치, Homing Offset 사용, 확장 위치 모드의 연속 좌표 중 적합한 방식을 결정한다.
3. 설정 변경 전 원본을 보관하고 토크 해제 시 자중으로 무너지지 않게 지지한다.
4. 새 좌표를 읽어 YAML과 일치시킨 뒤 작은 단일 축 움직임부터 경로·전원 재인가 후 위치를 확인한다.

Homing Offset은 Present Position에 더해지는 값이며 mode 3 유효 범위는 ±1024다.
이를 바꿨다는 사실만으로 경계 통과가 안전해지는 것은 아니다. YAML zero만 바꾸거나
차단을 끄거나 `%4096`만 적용해 실행하지 않는다.

## 현재 구현된 ID 2 전환 절차

진단에서 ID 2 / 2XL430, mode 3, Drive Mode 0, Offset 0, 현재 39 ticks가 확인됐다.
몸통 mapper/writer는 mode 4 signed 연속 좌표로 수정했고 앱 시작 시 실제 모드를 확인한다.
몸통 소프트웨어 한계는 -340~46 ticks이며 머리 ID 3은 mode 3과 zero 1022를 유지한다.
실제 전환·움직임·하중은 아직 시험하지 않았다.

1. 앱과 위자드를 종료하고 로봇을 물리적으로 지지한다.
2. 기본 읽기 명령으로 전환 조건을 확인한다.
3. 지원 조건이 맞으면 명시적 apply로 원본 백업 후 ID 2만 토크를 끄고 mode 4를 쓴다.

```bash
.venv-mp-pi3/bin/python scripts/enable_body_extended_position.py
.venv-mp-pi3/bin/python scripts/enable_body_extended_position.py --apply --supported
```

원본은 `data/motor_mode_backups/`에 시각별 JSON으로 보관하며 기존 파일은 덮어쓰지 않는다.
토크 해제 후 위치가 운용 범위 밖으로 움직이면 mode 쓰기를 중단한다. 전환 후 모드·오류·
현재 위치·토크 OFF를 다시 확인한다. ID 3/1/4, Homing Offset, 위치 한계, Goal Position은
쓰지 않으며 토크를 자동으로 다시 켜지 않는다. 이미 mode 4면 백업·확인만 한다.
실패 시 설정 일부가 적용됐을 수 있으므로 자동 롤백하지 않고 백업과 실제 상태를 확인한다.

전환 결과 mode 4 / torque 0 / present_position -340~46을 확인한 뒤에만 앱 구동을 검토한다.
앱이 모델을 준비하고 토크를 켜기 전까지 로봇을 계속 지지한다. 기존 키보드/범위 학습 등
단회전 전용 도구는 ID 2 mode 4 동작 검증용으로 사용하지 않는다.

mode 4에서는 하드웨어 Min/Max Position Limit이 적용되지 않는다. mapper·gate·writer에서
소프트웨어 제한을 적용하지만 물리적 하중·전도를 보장하지 않는다. 전원 재인가/재부팅 후
현재 위치가 단회전 절대값으로 돌아갈 수 있다. 실측이 예를 들어 4043이면 -53으로 자동
해석하지 않고 시작을 거부한다. 한 바퀴 정보 복원은 별도 실물 검증이 필요하다.

공식 근거: [Homing Offset](https://emanual.robotis.com/docs/en/dxl/x/2xl430-w250/#homing-offset20),
[Operating Mode](https://emanual.robotis.com/docs/en/dxl/x/2xl430-w250/#operating-mode11).
