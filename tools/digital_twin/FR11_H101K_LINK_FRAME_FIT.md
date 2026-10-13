# FR11-H101K / Link Frame / 2XL430 연결 검토

검토일: 2026-10-06. 로봇 제어·모터 설정은 변경하지 않았습니다.

## 결론

**H101K를 사이에 두고 Link Frame을 2XL430 출력축에 연결하는 조립 구조는 타당합니다.** Link Frame을 회전축에 곧바로 끼우는 구조가 아닙니다. 다만 현재 3D 앱에 H101K 연결점·자동 체결·회전 전파를 구현한 것은 아니며, 실물 조립 및 전 구간 회전 간섭 검증은 남아 있습니다.

1. 2XL의 한 축 출력 혼과 반대편 아이들러를 H101K의 양쪽 날개가 지지합니다.
2. H101K 중앙 판을 Link Frame 끝판에 볼트 4개로 연결합니다.
3. Link Frame 반대편은 원래 설명서에서 FR12-S101K 또는 S102K를 통해 다음 모터 본체에 연결합니다. H101K만으로 다음 모터 본체까지 연결된다고 가정하면 안 됩니다.

## 공식 근거 및 확보 자료

- [FR11-H101K 제품 페이지](https://www.robotis.com/shop/item.php?it_id=903-0290-100): XL/XC430용 힌지와 HN11-I101 아이들러 캡 세트입니다. XM/XH430에는 FR12 세트를 사용하도록 구분합니다. 세트에 포함되는 아이들러 부품의 차이를 무시하면 안 됩니다.
- [공식 다운로드센터](https://www.robotis.com/service/downloadpage.php?ca_id=7030)는 **FR12-H101K (FR11-H101K)**를 같은 도면 항목으로 제공하고 있습니다.
- [공식 PDF 다운로드](https://www.robotis.com/service/download.php?no=312): 확보된 파일은 `fr12_h101_k.pdf`, 도면명 FR12-H101-K, 날짜 2026/01/07, mm, FOR REFERENCE ONLY입니다. 로컬 원본: [FR11-FR12-H101K-2026.pdf](assets/FR11-FR12-H101K-2026.pdf).
- [공식 STEP 다운로드](https://www.robotis.com/service/download.php?no=313): 확보된 파일은 `fr12_h101_k.stp`. 로컬 원본: [FR11-FR12-H101K-2026.stp](assets/FR11-FR12-H101K-2026.stp). FR11이라는 별도 파일명으로 위장하지 않고 공용 프레임 형상으로 취급합니다.
- [2XL430 공식 조립 문서](https://emanual.robotis.com/docs/en/dxl/x/2xl430-w250/#frame-assembly): 출력 혼과 아이들러를 이용하는 힌지 조립을 설명하며 H101K 예제를 제공합니다.
- [OpenMANIPULATOR-X 공식 조립 안내](https://emanual.robotis.com/docs/en/platform/openmanipulator_x/assembly/): Link Frame과 H101K 및 S101/S102가 들어가는 구성입니다.
- ROBOTIS 작성 조립 설명서의 [유통사 보관 PDF](https://www.robot-advance.com/pj-openmanipulator-x-robotis-rm-x52-tnm-guide-157.pdf)를 확보해 PDF 6~7페이지를 확인했습니다. 원본: [RM-X52-Assembly-ROBOTIS.pdf](assets/RM-X52-Assembly-ROBOTIS.pdf). 공식 안내의 PDF 링크가 이번 다운로드 시도에서 완료되지 않아 같은 제작자 문서의 보관본을 사용했습니다.

제품 페이지는 2026년 외형 변경에도 설치 방법은 유지된다고 안내합니다. 따라서 구형 조립 설명서와 신형 공용 도면을 함께 참고할 수 있지만, 실제 배송된 구형·신형 형상을 확인해야 합니다. H101K CAD와 PDF의 재배포·상용 이용 권한을 Thingiverse Link Frame의 CC BY 4.0과 동일하다고 가정하지 않습니다.

## 치수 비교

| 연결 부위 | H101K 공용 STEP/PDF | Link Frame 두 STL | 판단 |
| --- | --- | --- | --- |
| 중앙 판 ↔ 프레임 끝판 | X/Z = (±12, ±6) mm, Ø2.6 | Y/Z = (±6, ±12) mm, Ø2.5 | 면을 맞추고 90° 방향 대응 시 24 × 12mm의 홀 4개 중심 일치 |
| 출력 혼 ↔ 날개 | PCD Ø16mm의 Ø2 홀 | 해당 없음 | 모터의 혼과 연결하는 곳이며 Link Frame 체결 홀이 아님 |
| 날개 안쪽 간격 | STEP 기준 38mm, 날개 두께 1.5mm | 해당 없음 | 제공 모터 STEP의 혼·아이들러 면 ±19mm와 배치 후보 구성 가능 |

조립 설명서는 H101K ↔ Link Frame에 **WB-M2.5×8 4개 + NUT-M2.5 4개**를 사용합니다. 반대편 Link Frame ↔ S101/S102에는 WB-M2.5×6을 사용합니다. 이는 RM-X52 원래 구성의 안내이며 2XL에 쓰는 모든 볼트 길이를 일괄적으로 정한 것이 아닙니다.

STL 끝판의 PCD 16mm 위치에서 발견한 Ø1.3~1.9mm의 작은 홀 2개는 주 체결 홀 4개와 다릅니다. 이 홀만 보고 M2.5 체결이 불가능하다고 판단하거나 이 두 점을 자동 체결 앵커로 쓰면 안 됩니다.

## CAD 정지 상태 검사

`link_frame_fit_audit.py`는 STL 끝판의 원형 경계와 STEP 원통면을 추출합니다. OCP + numpy 환경에서 실행합니다.

```sh
python tools/digital_twin/link_frame_fit_audit.py --motor /절대경로/2XL-430.stp
```

모터 배치 검사는 기존 감사 스크립트에 등록된 사용자 제공 STEP의 SHA-256을 확인합니다. 임의의 다른 모터 도면에는 같은 좌표를 적용하지 않습니다.

- A축 후보: H101K의 X축을 모터 Z축에 맞추고, 축 중심 (0,12,0), 중앙 판은 모터 +X 방향으로 둡니다. 모터 전체 STEP과 H101K의 교집합 체적 **0.0mm³**.
- B축 후보: H101K의 X축을 모터 X축에 맞추고, 축 중심 (0,-12,0), 중앙 판은 모터 -Y 방향으로 둡니다. 교집합 체적 **0.0mm³**.

이는 각각의 **정지 상태 배치 후보에서 솔리드가 관통하지 않는다**는 뜻입니다. 볼트·너트·케이블, 두 힌지를 동시에 장착했을 때의 상호 간섭, 프레임까지 포함한 전체 체인, 회전 중 충돌은 검사하지 않았습니다. 모터 STEP도 사용자가 제공한 2XC 파일과 동일하므로 2XL 실물과의 독립 정합 확인이 남아 있습니다.

## 다음 구현에 필요한 구분

- `모터 혼·아이들러 ↔ H101K 날개`와 `H101K 중앙 판 ↔ Link Frame 끝판`을 서로 다른 연결 종류로 정의합니다.
- Link Frame은 두 끝을 독립적으로 연결하고, H101K·S101/S102·본체 체결 부품을 구분합니다.
- 회전 전달은 모터 출력축에서 시작합니다. Link Frame 자체에 새 구동축을 만들지 않습니다.
- 실제 조립 후 볼트 길이·너트 포켓·아이들러 캡·스페이서·케이블 여유를 확인하고 저각도부터 회전 간섭과 하중을 검증합니다. 이 치수 검사로 `max_degree`나 안전 구동 범위를 확정할 수는 없습니다.
