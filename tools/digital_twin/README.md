# Notifyi 디지털 트윈 v0.2

첨부된 `2XC-430.stp`와 `2XC-430.igs`를 비교한 뒤, 실제 솔리드가 읽힌 STEP를 기준으로 `assets/2XC-430.step.stl`을 만들었다. 추가로 `EF25-F14.stp`를 1개 브라켓 자산으로 변환하고, [ROBOTIS 공식 OpenCR-Hardware](https://github.com/ROBOTIS-GIT/OpenCR-Hardware)의 `OpenCR_REVH.stl`을 추가했다. 현재는 5개 모터 조립을 붙이지 않고 모터 1개·브라켓 1개·OpenCR 1개의 실제 3D 메시, 카메라 뷰, 참고 배치만 검증한다.

## 실행

3D 메시를 브라우저의 WebGL로 읽기 때문에 로컬 정적 서버로 여는 것을 권장한다.

```bash
cd tools/digital_twin
python3 -m http.server 18766
```

그 다음 브라우저에서 다음 주소를 연다.

`http://127.0.0.1:18766/`

이 서버는 외부에 공개하지 않는 로컬 파일 서버다. 포트가 이미 사용 중이면 `18767` 같은 다른 포트를 사용한다.

## 할 수 있는 것

- 실제 STEP에서 변환한 단일 2XL-430 메시 표시
- 실제 STEP에서 변환한 EF25-F14 브라켓 1개 표시
- ROBOTIS 공식 OpenCR REVH 보드 메시 표시
- 마우스 드래그로 3D 회전, 휠로 확대·축소
- 정면·측면·상면 카메라
- 모델 Z축 회전과 자동 회전
- 브라켓 표시/숨김 및 X 위치 조절
- 기존 2D 조립 스키매틱은 `assembly-2d.html`에서 별도 확인

## 포맷 비교 결과

- `2XC-430.stp`: 29 solids, 47 shells, 3,103 faces. 외형 bounding box 약 `40.90 × 46.50 × 40.90 mm`.
- `2XC-430.igs`: 23 roots, 0 solids, surface only. 외형 기준 자산으로는 STEP보다 부적합.
- `EF25-F14.stp`: 1 solid, 768 faces. 외형 bounding box 약 `24.01 × 29.57 × 44.01 mm`.
- `OpenCR_REVH.step`: 68 solids, 10,311 faces. 표시에는 공식 저장소의 STL을 사용한다.

따라서 디지털 트윈 기준 포맷은 STEP로 선택했다. STL은 브라우저가 직접 읽을 수 있도록 변환한 표시용 메시이며, 원본 CAD의 파라메트릭 정보는 보존하지 않는다.

## 현재 범위와 한계

현재 페이지는 실제 모델의 형상 확인을 위한 시뮬레이션 전용이다. 출력축이 실제 로봇에서 어느 방향을 기준으로 회전하는지, 혼·브라켓이 어느 홀 패턴에 결합되는지는 아직 매핑하지 않았다. 화면의 브라켓 위치는 조립 확정 전 참고 배치다. 모델 방향을 확정한 뒤 다음 순서로 확장한다.

1. 출력축·혼·브라켓·OpenCR 기준축 표시
2. 브라켓 홀 패턴과 실제 연결면 정합
3. OpenCR 전원·DYNAMIXEL·USB 포트의 보드 방향 정합
4. 실제 ID 하나의 ticks를 read-only로 연결
5. 한 축의 실제 회전과 3D 모델 회전 비교
6. 검증 후에만 ID 2~7 조립 및 OpenCR 배선 추가

OpenCR의 입력·출력과 Notifyi 연결안은 [`docs/OPENCR_IO_MAP.md`](../../docs/OPENCR_IO_MAP.md)에 정리했다.

현재 브라우저는 모터에 명령을 보내지 않는다. 실제 연결 단계에서도 먼저 read-only로 두고, 쓰기 명령은 별도 안전 게이트 뒤에 둔다.
