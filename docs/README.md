# Notifyi 문서 안내

최신 코드/하드웨어 설정을 확인할 때는 이 문서와 아래 **현재 구현** 문서부터 읽는다. 코드는 `config/robot.yaml`, `config/joints.yaml`, `config/posture.yaml`이 실제 실행값의 기준이며, 문서는 실물 안전 검증을 대신하지 않는다.

## 현재 구현·운영

| 목적 | 문서 | 상태 |
| --- | --- | --- |
| 첫 실행·장비 점검 | [QUICKSTART.md](QUICKSTART.md), [COMMANDS.md](COMMANDS.md) | 현 OpenCR 브리지·ID 2~7 기준 |
| 연결·전원·핀 | [HARDWARE_WIRING.md](HARDWARE_WIRING.md), [OPENCR_IO_MAP.md](OPENCR_IO_MAP.md) | 실제 데이지체인/전원 분배는 현장 확인 필요 |
| 축 설정·안전 | [CONFIGURATION.md](CONFIGURATION.md), [MOTOR_LIMITS.md](MOTOR_LIMITS.md), [SAFETY_RUNBOOK.md](SAFETY_RUNBOOK.md) | zero/상대각은 잠정 설정, 실측 안전각 아님 |
| 동작·문제 해결 | [ARCHITECTURE.md](ARCHITECTURE.md), [STATE_MACHINE.md](STATE_MACHINE.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md), [INITIALIZATION_AND_RECOVERY.md](INITIALIZATION_AND_RECOVERY.md) | 자동 기립/복구 없음 |
| 3D 조립·상태 확인 | [디지털 트윈 사용법](../tools/digital_twin/README.md), [CAD 검사](../tools/digital_twin/CAD_FIT_AUDIT.md) | 화면 조립/수동 스캔, 실시간 모터 구동 없음 |
| 실물 동기화 후속 개발 | [디지털 트윈 개발 계획](../tools/digital_twin/DEVELOPMENT_PLAN.md) | 계획. 읽기 전용 동기화부터 |
| 인식·실험·로그 | [PERCEPTION_AND_CAMERA.md](PERCEPTION_AND_CAMERA.md), [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md), [EXPERIMENT_LOGGING.md](EXPERIMENT_LOGGING.md), [LOG_SCHEMA.md](LOG_SCHEMA.md), [ANALYSIS_GUIDE.md](ANALYSIS_GUIDE.md) | 현재 프로토타입과 평가 정의 |

현재 하드웨어 설정은 `/dev/ttyACM0`, 57600bps, 프로토콜 2.0, 전체 ID 1~8 중 활성 2~7이다. OpenCR는 `usb_to_dxl` 브리지이고, ROS 2·OpenCR 자체 안전 제어·자동 복구는 현 실행에 없다. 카메라 짐벌 보정은 기본 비활성화다. 브라우저 조립의 ±90°는 실물 운용 범위가 아니다.

## 설계안·조사 자료

- [ACTIVE_CAMERA_POSTURE_ASSESSMENT.md](ACTIVE_CAMERA_POSTURE_ASSESSMENT.md): 능동 카메라·부분 landmark 처리 제안. 현 런타임 기능 아님.
- [CAMERA_MOUNTING.md](CAMERA_MOUNTING.md): 장착·영상 검증 체크리스트. 보정 기능 실물 검증 전.
- [BENCHMARK_DESKTOP_ROBOTS.md](BENCHMARK_DESKTOP_ROBOTS.md), [DESKTOP_ROBOT_DESIGN_RESEARCH.md](DESKTOP_ROBOT_DESIGN_RESEARCH.md): 조사 당시의 벤치마크/디자인 참고 자료. 현재 제품 사양 아님.
- [LEROBOT_INTEGRATION.md](LEROBOT_INTEGRATION.md): 학습·데이터 인터페이스 검토. 현재 LeRobot 런타임 미사용.
- [API_AND_MODULES.md](API_AND_MODULES.md): 현재 모듈과 자유축 확장 제안을 구분한다.
- [decisions/](decisions/): 선택한 방향과 재검토 조건. 오래된 결정의 하드웨어 수치는 현재 설정 파일과 대조한다.

문서에 나온 *계획*, *후속*, *예시*는 구현·실물 검증 완료를 뜻하지 않는다. 모터 명령 전에 ID 매핑, 기구 간섭, 토크 해제 시 낙하 위험을 별도로 확인한다.
