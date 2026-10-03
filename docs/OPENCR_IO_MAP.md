# Notifyi OpenCR 입출력 적용표

이 문서는 [ROBOTIS-GIT/OpenCR-Hardware](https://github.com/ROBOTIS-GIT/OpenCR-Hardware)의 REVH 회로·레이아웃 자료와 [ROBOTIS OpenCR e-Manual](https://emanual.robotis.com/docs/en/parts/controller/opencr10/)을 기준으로, Notifyi에 실제 연결할 때 필요한 입력·출력을 정리한 문서다.

## 1. Notifyi 현재 연결안

| OpenCR 쪽 | 방향 | Notifyi 연결 | 용도 | 현재 상태 |
| --- | --- | --- | --- | --- |
| Micro-B USB | 양방향 통신/전원 | 삼성 노트북 | Python 제어 프로그램, 펌웨어 업로드, `/dev/ttyACM0` | 사용 중 |
| DYNAMIXEL TTL 포트 | 양방향 통신 + 모터 전원 | 2XL430-W250 ID 2~7 | 위치 읽기, 목표 위치 쓰기, 토크 제어 | 사용 중 |
| OpenCR 전원 입력 | 입력 | 12V SMPS 또는 배터리 | OpenCR와 DYNAMIXEL 버스 전원 | 사용 중 |
| OpenCR 상태 LED | 출력 | 보드 상태 확인 | 통신/부트/오류 확인 | 사용 중 |
| USER LED 1~4 | 출력 | 실험 상태 표시 | 감지·개입·오류 상태 표시 | 미사용 |
| PUSH SW1/2, DIP SW1/2 | 입력 | 초기화·수동 테스트 | 현장 조작용 | 미사용 |

현재 구조에서는 노트북이 카메라·자세 인식·실험 로그를 담당하고, OpenCR는 USB를 통해 받은 DYNAMIXEL 명령을 모터 버스로 전달하는 하드웨어 경계로 둔다.

## 2. 전원

| 항목 | 방향 | 정식 범위 | Notifyi 적용 |
| --- | --- | --- | --- |
| USB VBUS | 입력 | 5V | 펌웨어 업로드·통신용. 모터 주전원으로 간주하지 않는다. |
| Battery/SMPS 입력 | 입력 | 5~24V | 현재는 12V SMPS를 사용한다. 극성을 확인한 뒤 연결한다. |
| DYNAMIXEL 버스 | 출력 | 입력 전원에 따라 공급 | 2XL430 여러 개를 연결한다. 전원 인가 중 케이블을 꽂거나 빼지 않는다. |
| 12V 출력 | 출력 | 최대 4.5A | 디스플레이 등 12V 장치 후보. 장치별 소비전류 확인 후 사용한다. |
| 5V 출력 | 출력 | 최대 4A | 5V 디스플레이·주변장치 후보. USB 전원과 합산 조건을 확인한다. |
| 3.3V 출력 | 출력 | 800mA | 센서·저전력 GPIO 장치 후보. |

12V와 5V 출력의 총 전력은 55W를 넘기지 않는다. 모터가 여러 개 움직일 때는 정격전류가 아니라 가속·정지 순간의 전류 여유까지 포함해 SMPS를 선정한다.

## 3. DYNAMIXEL 포트

OpenCR는 TTL DYNAMIXEL 포트 3개와 RS-485 DYNAMIXEL 포트 3개를 제공한다. 커넥터 종류는 통신 방식에 따라 다르다.

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

Notifyi의 현재 2XL430-W250 버스는 실제 모터 커넥터와 OpenCR 보드의 TTL/RS-485 라벨을 먼저 대조한 뒤 한 종류의 포트로 통일한다. TTL 모터를 RS-485 포트에 바로 꽂지 않는다.

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

1. OpenCR 전원만 연결하고 USB로 보드 포트를 확인한다.
2. DYNAMIXEL 전원을 끈 상태에서 모터 버스의 커넥터 종류와 TTL/RS-485 라벨을 확인한다.
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
