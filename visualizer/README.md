# Notifyi Joint Studio

사진 샘플의 세로 모터 컬럼을 참고한 Three.js 기반 6축 시각화 틀이다.
브라우저에서 관절 움직임을 확인할 수 있지만, 현재 UI는 모터에 명령을 보내지 않는
읽기 전용 구조다.

## 배포 페이지

`visualizer/`는 GitHub Pages로 배포할 수 있는 정적 페이지다. `minwook` 브랜치에
변경사항을 push하면 `.github/workflows/deploy-visualizer.yml`이 자동으로 배포한다.

저장소가 `NOTIFYII/NOTIFYI_MIRRORING`이라면 배포 주소는 보통 다음 형식이다.

```text
https://notifyii.github.io/NOTIFYI_MIRRORING/
```

배포 페이지에서는 샘플 모드와 3D 조작만 사용할 수 있다. 브라우저가 GitHub Pages에서
노트북의 `/dev/ttyACM0`에 직접 접근할 수 없기 때문에 실제 모터 위치 읽기는 아래의
로컬 Python 서버를 실행하고 `http://127.0.0.1:8765`로 접속할 때 사용한다.

## 샘플 모드

하드웨어 없이 실행한다.

```bash
cd ~/posture_robot_proto
source .venv/bin/activate
python scripts/serve_notifyi_visualizer.py
```

브라우저에서 `http://127.0.0.1:8765`를 연다. 왼쪽 슬라이더로 ID 2~7의
pitch/yaw/roll을 조정할 수 있다.

## 실제 위치 읽기

OpenCR과 모터를 연결한 상태에서 다음을 실행한다.

```bash
python scripts/serve_notifyi_visualizer.py --hardware
```

브라우저의 `실시간 읽기`를 누르면 Python 서버가 DYNAMIXEL Present Position만
읽어서 `/api/state`로 제공한다. 서버는 모터에 쓰기 명령을 보내지 않는다.

시각화 서버가 실행 중에는 `/dev/ttyACM0` 포트를 점유하므로 teleop이나 메인
제어 프로그램을 동시에 실행하지 않는다.

## 현재 축

| ID | 축 |
| ---: | --- |
| 2 | 허리 아래 yaw |
| 3 | 허리 아래 pitch |
| 4 | 허리 위 yaw |
| 5 | 허리 위 pitch |
| 6 | 목 아래 roll |
| 7 | 목 yaw |

현재 zero와 방향은 `config/joints.yaml`을 기준으로 한다. 브라우저에서
`현재를 zero로 기록`을 눌러도 파일이나 모터 EEPROM은 변경하지 않는다.
