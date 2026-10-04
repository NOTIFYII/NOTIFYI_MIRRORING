# Notifyi OpenCR 입출력 적용표

이 문서는 [ROBOTIS-GIT/OpenCR-Hardware](https://github.com/ROBOTIS-GIT/OpenCR-Hardware)의 REVH 회로·레이아웃 자료와 [ROBOTIS OpenCR e-Manual](https://emanual.robotis.com/docs/en/parts/controller/opencr10/)을 기준으로, Notifyi에 실제 연결할 때 필요한 입력·출력을 정리한 문서다.

## 1. Notifyi 현재 연결안

| OpenCR 쪽 | 방향 | Notifyi 연결 | 용도 | 현재 상태 |
| --- | --- | --- | --- | --- |
| Micro-B USB | 양방향 통신/전원 | 삼성 노트북 | Python 제어 프로그램, 펌웨어 업로드, `/dev/ttyACM0` | 사용 중 |
| DYNAMIXEL TTL 3핀 포트 3개 | 양방향 공통 데이터 버스 + 모터 전원 | 2XL430-W250-T ID 2~7 | 위치 읽기, 목표 위치 쓰기, 토크 제어. 포트 3개는 독립 채널이 아님 | 사용 중 |
| OpenCR 전원 입력 | 입력 | 12V SMPS 또는 배터리 | OpenCR와 DYNAMIXEL 버스 전원 | 사용 중 |
| OpenCR 상태 LED | 출력 | 보드 상태 확인 | 전원·USB 통신 표시는 확인 가능하나 LED만으로 고장 종류를 단정할 수 없음 | 펌웨어 동작 확인 전 |
| USER LED 1~4 | 출력 | 실험 상태 표시 | 감지·개입·오류 상태 표시 | 미사용 |
| PUSH SW1/2, DIP SW1/2 | 입력 | 초기화·수동 테스트 | 현장 조작용 | 미사용 |

현재 구조에서는 노트북이 카메라·자세 인식·실험 로그를 담당하고, OpenCR는 USB를 통해 받은 DYNAMIXEL 명령을 모터 버스로 전달하는 하드웨어 경계로 둔다.

## 2. 전원

| 항목 | 방향 | 정식 범위 | Notifyi 적용 |
| --- | --- | --- | --- |
| USB VBUS | 입력 | 5V | 펌웨어 업로드·통신용. 모터 주전원으로 간주하지 않는다. |
| Battery/SMPS 입력 | 입력 | 5~24V | 현재는 12V SMPS를 사용한다. 극성을 확인한 뒤 연결한다. |
| DYNAMIXEL VDD 버스 | 스위치된 전원 출력 | 외부 Battery/SMPS 입력 전압을 스위칭해 공급; 별도의 정전압 12V 출력과 다름 | 2XL430 허용 범위 6.5~12.0V를 모터 단자에서 지켜야 한다. 전원 인가 중 케이블을 꽂거나 빼지 않는다. |
| 12V 출력 | 출력 | 최대 4.5A | 디스플레이 등 12V 장치 후보. 장치별 소비전류 확인 후 사용한다. |
| 5V 출력 | 출력 | 최대 4A | 5V 디스플레이·주변장치 후보. USB 전원과 합산 조건을 확인한다. |
| 3.3V 출력 | 출력 | 800mA | 센서·저전력 GPIO 장치 후보. |

12V와 5V 출력의 총 전력은 55W를 넘기지 않는다. OpenCR 보드가 24V 입력을 받아도 **2XL430 모터에 24V를 공급해도 된다는 뜻은 아니다.** USB만 연결한 상태를 모터 전원 공급 상태로 간주하지 않는다. 모터가 여러 개 움직일 때는 정격전류가 아니라 가속·정지 순간의 전류 여유까지 포함해 SMPS를 선정한다. 현재 12V SMPS 사용 시에도 모터 단자 전압이 12.0V를 초과하지 않는지 실측해야 한다.

## 3. DYNAMIXEL 포트

OpenCR는 TTL DYNAMIXEL 포트 3개와 RS-485 DYNAMIXEL 포트 3개를 제공한다. [공식 핀 배치](https://emanual.robotis.com/assets/images/parts/controller/opencr10/opencr_pinout.png)에서 USB를 오른쪽에 두고 보드를 위에서 보면 아래 긴 변의 **왼쪽 3개가 TTL 3핀**, 바로 오른쪽 3개가 **RS-485 4핀**이다. REVH 회로도에서 TTL 쪽 J15·J16·J17은 같은 `TTL_DATA`와 `DXL_PWR`를 공유한다. 각 헤더를 별도 제어 채널 또는 모터 ID로 해석하지 않는다. 3D 화면의 TTL 1·2·3은 REVH STEP의 `JST_B3B_EH_A` 하우징 외접 범위를 메시 중심으로 변환해 배치했으나, 소켓 개구면·커넥터 삽입 방향은 실측 전이다.

REVH STEP 원본 좌표(mm)에서 TTL 하우징 3개의 외접 범위는 각각 `x=33.9~37.7`, `y=-28.5~-18.5 / -17.8~-7.8 / -7.5~2.5`, `z=-3.2~6.0`이다. Micro‑B USB는 `x=-1.0~7.0`, `y=45.3~50.8`, `z=-0.2~2.7`이다. 브라우저 모델은 전체 메시 중심 `(0.9,-3.7,4.2)` mm를 빼서 표시한다. 이 값은 외형의 범위이며 커넥터 접점·핀 번호의 계측값이 아니다.

### TTL 3핀

| 핀 | 신호 | 방향 | 의미 |
| --- | --- | --- | --- |
| 1 | GND | 전원 기준 | 모터와 OpenCR의 기준 전위 |
| 2 | VDD | 출력 전원 | DYNAMIXEL 전원 |
| 3 | DATA | 양방향 | Half-duplex TTL 통신 |

### RS-485 4핀

| 핀 | 신호 | 방향 | 의미 |
| --- | --- | --- | --- |
| 1 | GND | 전원 기준 | 모터와 OpenCR의 기준 전위 |
| 2 | VDD | 출력 전원 | DYNAMIXEL 전원 |
| 3 | DATA+ | 양방향 | RS-485 차동 통신 |
| 4 | DATA- | 양방향 | RS-485 차동 통신 |

Notifyi의 **2XL430-W250-T는 TTL 모델**이므로 OpenCR의 3핀 TTL 포트에만 연결한다. 4핀 RS-485 포트나 전원 출력 전용 커넥터에는 꽂지 않는다. 모델명 뒤의 통신 타입과 실물 커넥터·보드 인쇄 라벨을 마지막으로 대조한다.

현재 소프트웨어 설정은 다음과 같다.

```yaml
port: /dev/ttyACM0
baudrate: 57600
protocol: 2.0
active_ids: [2, 3, 4, 5, 6, 7]
```

## 4. Arduino 호환 헤더

### 디지털·통신 핀

| Arduino 핀 | 기본 기능 | 하드웨어 매핑 | 방향 | Notifyi 활용 후보 |
| ---: | --- | --- | --- | --- |
| 0 | UART RXD | USART6 RX | 입력 | 외부 UART 수신 |
| 1 | UART TXD | USART6 TX | 출력 | 외부 UART 송신 |
| 2 | GPIO / EXTI0 | GPIO | I/O | 이벤트 입력 |
| 3 | PWM / EXTI1 | TIM3_CH1 | 출력 | 저전력 PWM 장치 |
| 4 | GPIO / EXTI2 | GPIO | I/O | 이벤트 입력 |
| 5 | PWM | TIM1_CH1 | 출력 | 저전력 PWM 장치 |
| 6 | PWM | TIM2_CH3 | 출력 | 저전력 PWM 장치 |
| 7 | GPIO / EXTI3 | GPIO | I/O | 이벤트 입력 |
| 8 | GPIO / EXTI4 | GPIO | I/O | 이벤트 입력 |
| 9 | PWM | TIM9_CH2 | 출력 | 저전력 PWM 장치 |
| 10 | PWM / SPI NSS | TIM11_CH1 / SPI2 NSS | 출력 | SPI 장치 선택 또는 PWM |
| 11 | PWM / SPI MOSI | TIM12_CH2 / SPI2 MOSI | 출력 | SPI 송신 또는 PWM |
| 12 | SPI MISO | SPI2 MISO | 입력 | SPI 수신 |
| 13 | SPI SCK / LED | SPI2 SCK | 출력 | SPI 클럭 또는 상태 LED |
| 14 | I²C SDA | I2C1 SDA | 양방향 | 센서·디스플레이 데이터 |
| 15 | I²C SCL | I2C1 SCL | 출력 | 센서·디스플레이 클럭 |
| 16~21 | ADC A0~A5 | ADC3 채널 | 입력 | 아날로그 센서 6개 |

PWM은 공식 예제 기준 8-bit(0~255)이며, DYNAMIXEL 자체 제어에는 사용하지 않는다. DYNAMIXEL은 전용 버스 포트를 사용한다.

### GPIO 확장 커넥터

| 커넥터 핀 | OpenCR Arduino 핀 | 신호 | 방향 | 적용 |
| ---: | ---: | --- | --- | --- |
| 1 | - | 3.3V | 출력 전원 | 센서 전원 |
| 2 | - | GND | 기준 전위 | 공통 접지 |
| 3~20 | 50~67 | GPIO 1~18 | I/O | 외부 센서·스위치·상태 입력 |

GPIO는 기본적으로 3.3V 논리이며, 공식 문서의 `FT` 표기가 있는 핀만 5V tolerant로 취급한다. 아날로그 모드에서는 5V를 넣지 않는다. 모든 GPIO를 동시에 큰 부하의 전원 출력처럼 사용하지 않는다.

## 5. UART·CAN

| 인터페이스 | OpenCR 노출 | 방향 | Notifyi 적용 |
| --- | --- | --- | --- |
| Serial1 | Arduino 0 RX / 1 TX, USART6 | 양방향 | 외부 보조 MCU 또는 센서 |
| Serial2 | UART1, USART2 | 양방향 | 외부 통신 모듈 |
| Serial4 | UART2, UART8 | 양방향 | 외부 통신 모듈 |
| CAN | 전용 통신 커넥터 | 양방향 | 바퀴용 모터 드라이버 후보 |

노트북과 OpenCR 사이의 현재 통신은 USB CDC를 사용하므로 UART 핀을 중복 사용하지 않는다. 바퀴를 나중에 붙일 때 CAN을 사용하려면 모터 드라이버의 CAN 트랜시버·종단저항·프레임 규격을 먼저 확인한다. 일반 DC 모터를 PWM 핀에 직접 연결하지 않는다.

## 6. 보드 내장 입력·출력

[공식 `usb_to_dxl` 예제 펌웨어](https://github.com/ROBOTIS-GIT/OpenCR/blob/master/arduino/opencr_arduino/opencr/libraries/OpenCR/examples/10.%20Etc/usb_to_dxl/usb_to_dxl.ino)에서 USER1/USER2 LED는 각각 DXL→USB 수신 / USB→DXL 송신 트래픽에 따라 점멸한다. USER2의 빨간불만으로 모터 과부하나 통신 고장을 판정하지 않는다. LD1은 3.3V 전원 표시, LD2는 USB 통신 표시다. 현재 브라우저에서 LED의 **실제 점등 상태를 읽는 경로는 없다**. 이를 표시하려면 별도 카메라 관측 또는 OpenCR 펌웨어의 상태 송신 기능이 필요하다. 아래 ‘Notifyi 활용’은 향후 펌웨어를 바꾸는 경우의 계획이며 현재 `usb_to_dxl` 동작을 뜻하지 않는다.

| 장치 | Arduino 핀 | 방향 | Notifyi 활용 |
| --- | ---: | --- | --- |
| USER1 LED | 22 | 출력 | 자세 감지 상태 |
| USER2 LED | 23 | 출력 | 개입 실행 상태 |
| USER3 LED | 24 | 출력 | 복구/정지 상태 |
| USER4 LED | 25 | 출력 | 통신 오류 상태 |
| DIP SW1/2 | 26/27 | 입력 | 서비스 모드 선택 |
| Battery ADC | 29 | 입력 | 입력 전압 모니터링 |
| Buzzer | 31 | 출력 | 짧은 피드백음 |
| DYNAMIXEL power enable | 32 | 출력 | 모터 버스 전원 제어 |
| PUSH SW1/2 | 34/35 | 입력 | 수동 시작·정지 |
| Status LED | 36 | 출력 | 보드/부트 상태 |
| ICM-20648 IMU | 내부 SPI | 입력 | 보드 기울기·충격 감지 |

## 7. Notifyi에 실제 적용할 순서

현재 `tools/digital_twin/serve.py`는 프로젝트 YAML에서 ID 매핑을 읽고, 실행한 컴퓨터에서 `/dev/ttyACM0` 경로가 존재하는지 검사한다. 별도 수동 `scripts/scan_dynamixel.py --status-file data/connection_status.json` 결과가 있으면 설정된 baud에서 응답한 모터 ID와 검사 시각을 표시한다. 15초가 지난 결과는 **현재 연결됨**으로 표시하지 않는다. USB 장치가 OpenCR인지, 외부 모터 전원이 계속 유지되는지, 현재 관절이 움직이는지는 확인하지 않는다. 메인 `src.main` 실행 중에는 별도 스캔으로 시리얼 포트를 동시에 열지 않는다. 실측 위치를 화면과 동기화하려면 제어 프로그램 한 곳이 `Present Position`을 읽어 별도 읽기 전용 상태 채널로 게시해야 한다. 명령 목표 위치를 실제 이동으로 대체 표시하지 않는다. 하우징별 물리 ID 쌍도 아직 미확정이다.

1. OpenCR 전원만 연결하고 USB로 보드 포트를 확인한다.
2. DYNAMIXEL 전원을 끈 상태에서 모터의 TTL 3핀 커넥터와 보드 긴 변의 TTL 3핀/RS-485 4핀 라벨을 대조한다. 모터 단자 전압이 허용 범위인지 확인한다.
3. 2XL430 한 개만 연결해 ID·baud·protocol 2.0을 읽는다.
4. 현재처럼 `/dev/ttyACM0`, 57600bps에서 read-only 스캔을 먼저 수행한다.
5. ID 2~7을 하나씩 추가하고 각 모터의 전류·온도·통신 응답을 기록한다.
6. OpenCR 3D 모델의 보드 방향과 실제 보드의 USB·DYNAMIXEL·전원 커넥터 방향을 대조한다.
7. 그 다음에야 3D 화면의 케이블과 모터-브라켓-OpenCR 상대 위치를 고정한다.

전원이 들어온 상태에서는 DYNAMIXEL 케이블을 연결하거나 분리하지 않는다. 이상한 냄새·소리·연기·과열이 있으면 즉시 전원을 제거한다.

## 8. 공식 자료

- [OpenCR-Hardware 저장소](https://github.com/ROBOTIS-GIT/OpenCR-Hardware) — REVH STEP/STL, 회로도, PCB 도면, BOM
- [OpenCR 1.0 e-Manual](https://emanual.robotis.com/docs/en/parts/controller/opencr10/) — 사양, 핀맵, 전원, DYNAMIXEL 커넥터
- [OpenCR REVH 3D 모델](https://github.com/ROBOTIS-GIT/OpenCR-Hardware/blob/master/Layout/OpenCR_REVH.step)
- [OpenCR REVH 회로도](https://github.com/ROBOTIS-GIT/OpenCR-Hardware/blob/master/Schematic/OpenCR_REVH.pdf)
- [2XL430-W250-T 공식 사양](https://emanual.robotis.com/docs/en/dxl/x/2xl430-w250/) — TTL 통신, 6.5~12.0V 입력
