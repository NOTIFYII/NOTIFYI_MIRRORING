# Notifyi 디지털 트윈 v0

첨부된 `2XL-430.dwg`를 로컬에서 `LibreDWG`로 읽어 `assets/2XL-430-model.svg`로 변환하고, 현재 Notifyi의 ID 2–7 축과 OpenCR 배선 구조를 한 화면에서 확인할 수 있게 만든 안전한 로컬 시뮬레이터다.

## 실행

서버 없이 `index.html`을 브라우저로 열어도 된다.

```bash
open tools/digital_twin/index.html
```

또는 브라우저에서 다음 파일을 직접 연다.

`tools/digital_twin/index.html`

## 할 수 있는 것

- ID 2–7 관절을 클릭해 선택
- 슬라이더 또는 `A/D`, 방향키로 선택 축의 시뮬레이션 각도 변경
- 6축의 동작 재생
- 실제 DWG에서 추출된 CAD 도면 확대·축소
- OpenCR–모터 버스 케이블 구조 확인

## 현재 범위와 한계

이번 DWG는 3D solid 모델이 아니라 도면·치수 위주의 2D 엔티티로 판독됐다. 따라서 왼쪽은 조립과 축 동작을 위한 파라메트릭 스키매틱이고, 오른쪽은 실제 DWG 원본을 변환한 CAD 참고 뷰다. 임의로 3D 형상을 만들어 실제 제품과 같다고 가정하지 않았다.

현재 브라우저는 모터에 명령을 보내지 않는다. 실제 연결 단계에서는 다음 어댑터를 별도로 추가한다.

1. 원격 노트북의 `scan_dynamixel.py` 결과를 JSON으로 내보내기
2. ID별 ticks·온도·전압·토크 상태를 디지털 트윈에 표시
3. 명시적인 `simulation` / `hardware read-only` 모드 분리
4. 쓰기 명령은 안전 게이트와 별도 확인을 통과한 경우에만 허용

3D 조립까지 진행하려면 같은 부품의 STEP/IGES/OBJ/glTF 파일이 필요하다. DWG에서 3D solid가 포함된 파일을 받으면 이 폴더의 CAD 자산을 교체해 실제 외형에 더 가깝게 확장할 수 있다.
