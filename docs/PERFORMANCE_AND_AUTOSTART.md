# Pi 3 B+ 반응 지연과 실행 자동화

2026-10-14, `minwook` 작업. 최신 `main`의 두 축 제어를 기반으로 했다.
모터 범위·카메라 머리 보정 방향·3초 개입 조건은 변경하지 않았다.

## 반응 지연 개선

- 카메라는 전용 스레드가 읽고 최신 프레임 하나만 보관한다. 처리 중 쌓인 프레임을
  전부 순서대로 추론하지 않는다. 같은 프레임은 두 번 반환하지 않는다.
- 관측 시각은 앱이 프레임을 읽은 시각을 사용한다. 이는 센서의 실제 노출 시각이
  아니므로 드라이버 내부 지연까지 정확하게 측정하는 값은 아니다.
- 판단 주기 1초→0.1초, 중앙값 필터 7→3프레임. 나쁜 자세 3초 지속은 그대로다.
- 해상도 640×480, lite 모델은 유지했다. Pi 3 추론 성능 향상이나 정확도는 아직
  실측하지 않았다. 필터 축소로 오검출이 늘어나는지 비교해야 한다.
- `[PERF]`와 JSONL `runtime_performance`는 약 5초마다 캡처 대기·추론·처리 시점
  프레임 나이의 중앙값 및 처리 FPS를 기록한다. 영상·사진은 기록하지 않는다.
- 모델 초기화 약 20초와 실행 중 반응 지연은 별개다. 실행 아이콘으로 다시 시작해도
  모델은 새로 준비하므로 초기 로딩이 사라지는 것은 아니다.
- 전원/발열 점검: `vcgencmd measure_temp`, `vcgencmd get_throttled`.

비교하려면 `perception.latest_frame_only: false`, `angles.median_window: 7`,
`correction.check_interval_sec: 1.0`으로 이전 방식과 비교한다. 실물 모터 없이
인식·로그부터 시험한다. 모델/카메라 준비와 종료 시 기존 안전 정책을 유지한다.

## Pi 성능 비교 명령

`[PERF] 2.14 fps / 추론 461.8ms / 프레임 나이 497.2ms`에서는 추론이 주요 병목이다.
이를 모델 스레드 수 조정만으로 해결한다고 가정하지 않는다. MediaPipe Tasks Python
BaseOptions에는 `num_threads` 인자가 없다. `cv2.setNumThreads`는 OpenCV 전처리 등의
병렬화 제어이지 MediaPipe 추론 스레드 수를 강제로 설정하는 기능이 아니다.

앱·프리뷰·motion 등 카메라 사용 프로그램과 인식 전용 자동 서비스를 종료한 후:

```bash
cd ~/notiFYI
.venv-mp-pi3/bin/python scripts/benchmark_pi_runtime.py --camera /dev/video0 --seconds 12
```

비교 항목은 기본 설정, OpenCV 1스레드, CPU 2코어 사용 범위, 추론 입력 480폭,
320폭이다. 각 항목은 별도 프로세스에서 실행해 라이브러리 초기화가 서로 영향을 주지
않게 한다. 코어 사용 범위는 cv2/MediaPipe import 전 자식 프로세스에만 적용한다.
CPU 코어 제한은 추론 스레드 수 설정과 다른 시험이다.

원본 카메라는 모든 시험에서 설정된 640×480 그대로 사용하고 추론 입력만 종횡비를
유지해 축소한다. 모델은 lite다. 준비 시간과 최소 3프레임 워밍업은 FPS 집계에서
제외한다. 마지막에 기본 설정을 다시 측정해 발열·시간 경과 영향을 살펴본다.
각 측정 중 같은 자리에서 정상 자세를 유지한다. 센서 촬영 시각 기반 지연은 아니다.
환경별 모델 준비를 포함해 전체 시험은 수 분 걸릴 수 있다.

출력 JSON은 `data/runtime_benchmarks/`에 저장한다. 원본 영상이나 프레임은 저장하지
않는다. FPS, 추론 p50/p95, 프레임 나이, 유효 자세 검출률, 목·몸통 지표 흔들림,
실제 OpenCV 스레드 수·CPU 코어 범위, 전원/발열 상태를 기록한다. 가만히 앉은 시험의
검출률·흔들림은 정확도 또는 자세 변화 반응시간 자체를 증명하지 않는다.

검출 표본이 10개 미만이면 품질 판단을 보류한다. `vcgencmd`를 사용할 수 없으면
해당 상태는 null로 표시한다. YAML, 모터 모드, Goal, 토크는 변경하지 않는다.
현재 켜져 있는 토크를 해제하는 도구도 아니므로 로봇 상태는 별도로 확인한다.
빠른 조건을 찾더라도 움직이는 자세·오검출·회복 반응은 추가 시험한 뒤 기본 설정을
변경한다. Pi에서의 실제 비교 결과는 아직 확보하지 않았다.

참고: [MediaPipe BaseOptions](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/BaseOptions),
[OpenCV 스레드 API](https://docs.opencv.org/4.10.0/db/de0/group__core__utils.html).

## 실행 아이콘 설치

라즈베리파이 사용자 `notifyi`의 터미널에서:

```bash
cd ~/notiFYI
.venv-mp-pi3/bin/python scripts/install_launchers.py
```

사용자 앱 메뉴에 **Notifyi 카메라 확인**이 등록된다. 메뉴의 실행 아이콘을 바탕화면에
추가/즐겨찾기하면 매번 명령을 입력할 필요가 없다. 기본 실행은 인식 전용 프리뷰다.
아이콘 우클릭의 **로봇 구동 — 모터가 움직입니다**를 직접 선택해야 `--move`가 붙는다.
데스크톱 환경이 추가 액션을 지원하지 않으면 터미널 수동 실행을 사용한다.
아이콘은 콘솔도 열어 오류를 보여준다. 프리뷰는 Pi의 그래픽 데스크톱 세션에서만 열린다.

실행은 고정된 환경 `.venv-mp-pi3`의 Python으로 설치된다. 가상환경을 활성화할 필요 없다.
자동 인식 서비스가 켜져 있으면 아이콘이 그 서비스를 먼저 정지해 카메라 중복 점유를
피한다. 실행 잠금은 같은 계정의 앱 중복 실행을 거부한다. 다른 사용자·motion·위자드·
다른 모터 도구의 실행을 막는 기능은 아니므로 별도로 종료해야 한다.

## 자동 실행: 부팅/로그인 시 인식만

```bash
.venv-mp-pi3/bin/python scripts/install_launchers.py --enable-service
```

사용자 로그인 시 `notifyi-observe.service`가 인식만 실행한다. 즉시 시작하지는 않는다.
로그인하지 않아도 부팅 시 사용자 서비스를 실행하려면 별도로 한 번 설정한다:

```bash
sudo loginctl enable-linger notifyi
```

서비스는 카메라 장치를 최대 30초 기다린 뒤 헤드리스 인식을 시작한다. `--move`를
넣지 않고 자동 재시작도 하지 않는다(`Restart=no`). 카메라 점유·장치 오류 시 실패로
남기므로 원인을 먼저 확인한다. 부팅 시 모터 토크를 자동 해제하는 기능도 아니다.
이전에 켜져 있던 토크는 별도로 확인해야 한다. 인식 서비스는 앱을 나가도 계속 실행된다.

```bash
systemctl --user status notifyi-observe.service
journalctl --user -u notifyi-observe.service -n 40 --no-pager
systemctl --user stop notifyi-observe.service
systemctl --user disable notifyi-observe.service
```

서비스만 중지한 후 아이콘으로 구동했다가 끝내면 자동 인식은 자동 재개하지 않는다.
물리 버튼으로 같은 프로세스의 구동을 승인하는 기능은 아직 없다. 버튼 핀·배선과
비상 정지 방식을 확인한 뒤 별도로 설계한다. 자동 서비스/아이콘 설치는 Pi에서 별도
수행해야 하며, 개발 머신에서는 실제 설치나 모터 구동을 하지 않았다.

## 브랜치 보존

이전 `minwook`의 3D 작업과 커밋은 `codex/minwook-backup-20261014`에 보관했다.
현재 `minwook`은 `main`의 `a837f3e`부터 새로 작업한다. `main`에는 이 변경을 넣지 않는다.
개인 문서 `docs/private/`는 그대로 유지하고 공유 대상에서 제외한다.

참고: [systemd 공식 서비스 설명](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml),
[Raspberry Pi 전원/발열 문서](https://www.raspberrypi.com/documentation/computers/config_txt.html).
