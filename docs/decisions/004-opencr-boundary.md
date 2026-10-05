# ADR 004: OpenCR과 상위 컴퓨터의 역할을 분리함

## 결정

현재 OpenCR는 `usb_to_dxl` 펌웨어로 노트북 USB와 Dynamixel TTL 버스를 연결하는 브리지다. Python 제어가 모터 패킷과 안전 판단을 담당한다. 향후 별도 펌웨어와 검증을 갖춘 경우에만 OpenCR에 저수준 제어·안전 경계를 이관한다.

## 현재 상태

현재 코드는 Dynamixel SDK를 통한 직렬 버스 제어를 사용한다. 브리지 경로는 `/dev/ttyACM0`, 57600bps, 프로토콜 2.0이다. OpenCR 고유 명령 프로토콜이나 ROS 2 어댑터는 구현하지 않았다.

## 재검토 조건

전원·배선·통신 방식이 확정되면 OpenCR transport를 JointWriter와 별도 어댑터로 구현한다.
