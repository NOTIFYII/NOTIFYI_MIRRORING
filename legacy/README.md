# 보관 코드
현재 main의 실행 경로에서 제외한 과거 실험·미구현 파일이다. 참고와 복원용으로 남겨두며, 현재 로봇에 바로 실행하는 명령 목록이 아니다.

| 보관 위치 | 내용 | 활성 런타임에서 제외한 이유 |
| --- | --- | --- |
| src/gemini | API 클라이언트·프롬프트 placeholder | 현재 고정 모션 실험은 로컬 정책 사용 |
| src/audio | STT placeholder·TTS 큐 | 현재 음성 하드웨어/조건 미사용 |
| src/perception | 사용자 캘리브레이션 | 사용자별 calibration 없이 운영 |
| src/offline_pipeline.py | 독립 mock 정책 | 현행 분류/정책과 다른 중복 구현 |
| src/robot/arm_poses.py, src/experiment | 빈 스텁 | 활성 호출 없음 |
| scripts | 옛 음성·골반 신호·카메라 실험 | 현재 상체/두 모터 설정과 다른 전제 |
| docs | 옛 YEGAM 흐름·초기복구 계획 | 현재 실행 구조와 하드웨어가 다름 |
| tests | TTS 단위 테스트 | 활성 설치에서 제외 |

voice_motor.py는 import 또는 실행 시 즉시 종료하도록 막았다. 예전 속도 제어 ID 1·2와 현재 위치 제어 ID 2·3은 다르다. 빈 run_prototype.sh/check_camera.py 역시 구현된 도구가 아니다.

현재 앱은 legacy를 import하지 않는다. 보관된 Gemini 실험을 복원할 때만 legacy/requirements.txt를 별도 환경에 설치하고 코드를 다시 검토한다. legacy는 setuptools 배포 대상과 기본 pytest testpaths에서 제외된다. Git에 추적되던 생성 .pyc 파일 네 개는 삭제했고 소스는 이 폴더에 남겼다.
