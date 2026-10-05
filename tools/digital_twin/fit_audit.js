/* Scope the supplied STEP audit to each bracket; never infer a safe operating range. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.NotifyiFitAudit = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const result = (status, detail) => ({ status, detail });

  function assess(bracket, motors) {
    const plate = bracket.mates?.plate;
    const fork = bracket.mates?.fork;
    const motorIds = new Set(motors.map(motor => motor.id));
    const plateValid = plate && motorIds.has(plate.motorId);
    const forkValid = fork && motorIds.has(fork.motorId);
    const complete = plateValid && forkValid && plate.motorId !== fork.motorId;
    const invalidFace = plateValid && ['top', 'bottom'].includes(plate.face);
    const reference = complete && bracket.rootSide === 'plate' && plate.face === 'front' && fork.axis === 'A';

    return {
      id: bracket.id,
      plateMotorId: plateValid ? plate.motorId : null,
      forkMotorId: forkValid ? fork.motorId : null,
      holes: invalidFace
        ? result('invalid', '윗면·아랫면 판 체결 홀 패턴 없음')
        : plateValid && plate.face === 'front'
          ? result('limited', '+Z면 판 홀 4개 중심 정렬만 STEP에서 확인')
          : result('unverified', plateValid ? '이 체결면의 홀 정렬 미검증' : '본체 판 미연결'),
      static: reference
        ? result('limited', '참조 배치 0°·판 간격 0.5 mm에서 일부 본체의 체적 중첩 미검출')
        : result('unverified', '현재 배치의 정적 체적 간섭 미검증'),
      sweep: reference
        ? result('interference', '참조 배치 A축 ±30°에서 브라켓·모터 본체 간섭 확인')
        : result('unverified', complete ? '이 축·체결 방향의 회전 경로 미검증' : '두 모터 체결 후 검토 필요'),
      wiring: result('unverified', '케이블 길이·굽힘·가동 여유 미검증'),
    };
  }

  return { assess };
});
