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

### SSH 원격 노트북에서 실행할 때

Mac 터미널에서 원격 접속할 때는 포트 포워딩을 포함해야 한다. 기존 SSH 세션을
종료하고 다음처럼 다시 접속한다.

```bash
ssh -L 8765:127.0.0.1:8765 wookmin@172.17.221.147
```

그 SSH 세션 안에서 서버를 실행한다.

```bash
cd ~/Desktop/posture_robot_proto
source .venv/bin/activate
python scripts/serve_notifyi_visualizer.py --hardware
```

브라우저는 Mac에서 열고 다음 주소를 사용한다.

```text
http://127.0.0.1:8765
```

브라우저를 삼성 노트북에서 직접 열 경우에는 SSH 포워딩 없이 같은 노트북에서
동일한 주소를 열면 된다.

시각화 서버가 실행 중에는 `/dev/ttyACM0` 포트를 점유하므로 teleop이나 메인
제어 프로그램을 동시에 실행하지 않는다.

## 단자와 배선 시뮬레이션

화면의 `ID n A/B`는 2XL430-W250의 TTL 단자를, `OpenCR TTL1~3`은 OpenCR의
DYNAMIXEL TTL 포트를 나타낸다. 단자를 한 번 클릭한 다음 다른 단자를 클릭하면
읽기 전용 시뮬레이션 케이블이 추가되고, 왼쪽 `배선 설계` 목록에서 연결을 삭제할
수 있다. 이 연결은 모터나 OpenCR에 실제 명령을 보내지 않는다.

2XL430-W250은 TTL half-duplex 통신을 사용하며 공식 핀 배열은 `1 GND / 2 VDD /
3 DATA`다. OpenCR 1.0에는 DYNAMIXEL용 TTL 포트가 3개 있다. 따라서 시각화에서
TTL 단자끼리만 연결하는 흐름으로 구성했다. 초기 화면의 데이지체인 배선은 현재
구조를 설명하기 위한 예시이므로, 실제 조립 전에는 사용 중인 케이블·포트·전원
분배를 별도로 확인한다.

전원이 켜진 상태에서는 DYNAMIXEL 케이블을 연결하거나 분리하지 않는다. 실제
배선 변경은 전원을 끄고 진행한다.

## 모터 방향과 배치 수정

실제 구조에 맞춰 모터를 세우거나 눕히거나 뒤집으려면
`visualizer/layout.js`의 `MOTOR_LAYOUT`을 수정한다.

```js
3: { orientation: 'lying', position: [0, 0, 0], rotation: [0, 0, 90] },
5: { orientation: 'upside_down', position: [0, 0, 0], rotation: [180, 0, 0] },
```

`rotation`은 도 단위의 `[x, y, z]`, `position`은 부모 브라켓 기준 오프셋이다.
현재 화면의 모터 외형은 2XL430-W250의 공식 치수(36 × 46.5 × 36 mm)와 TTL
커넥터 구조를 기준으로 만든 조립 검토용 모델이며, 실제 CAD 수준의 형상 검증 전에는
브라켓 간섭과 케이블 굽힘 반경을 실물로 확인해야 한다.

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

참고: [2XL430-W250 공식 Connector Information](https://emanual.robotis.com/docs/en/dxl/x/2xl430-w250/),
[OpenCR 1.0 공식 DYNAMIXEL Connector 문서](https://emanual.robotis.com/docs/en/parts/controller/opencr10/)
