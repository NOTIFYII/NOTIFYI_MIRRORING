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

mode 4를 선택하면 단회전용 mapper/writer와 시작 검증도 연속 signed 위치에 맞게
변경해야 한다. 하드웨어 Min/Max Position Limit은 mode 4에서 적용되지 않으므로 모드만
변경해 현재 앱을 실행하지 않는다. 아직 보정 설정 쓰기나 실물 시험은 수행하지 않았다.

공식 근거: [Homing Offset](https://emanual.robotis.com/docs/en/dxl/x/2xl430-w250/#homing-offset20),
[Operating Mode](https://emanual.robotis.com/docs/en/dxl/x/2xl430-w250/#operating-mode11).
