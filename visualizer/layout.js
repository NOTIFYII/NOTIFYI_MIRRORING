// Notifyi 모터 배치 원본.
//
// rotation은 라디안이 아니라 도(deg)로 적는다.
// position은 해당 관절의 부모 기준 오프셋이다. 모터를 세우거나 눕히거나
// 뒤집고 싶을 때 이 파일의 rotation만 먼저 바꿔서 확인한다.
//
// 예시:
//   rotation: [0, 0, 90]  -> 모터를 Z축 기준으로 눕힘
//   rotation: [180, 0, 0]  -> 모터를 뒤집음
//   position: [0.12, 0, 0] -> 부모에서 오른쪽으로 이동

export const MOTOR_LAYOUT = {
  2: { orientation: 'standing', position: [0, 0, 0], rotation: [0, 0, 0] },
  3: { orientation: 'lying', position: [0, 0, 0], rotation: [0, 0, 90] },
  4: { orientation: 'standing', position: [0, 0, 0], rotation: [0, 0, 0] },
  5: { orientation: 'upside_down', position: [0, 0, 0], rotation: [180, 0, 0] },
  6: { orientation: 'lying', position: [0, 0, 0], rotation: [0, 90, 0] },
  7: { orientation: 'standing', position: [0, 0, 0], rotation: [0, 0, 0] },
};

export const MODEL_REFERENCE = {
  name: 'DYNAMIXEL 2XL430-W250',
  dimensions_mm: { width: 36, height: 46.5, depth: 36 },
  communication: 'TTL half-duplex',
  connector: 'JST EHR-03 / B3B-EH-A',
  pins: ['GND', 'VDD', 'DATA'],
};
