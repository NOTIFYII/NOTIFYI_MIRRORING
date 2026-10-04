/* Portable, hardware-independent assembly project format. */
(function (root) {
  'use strict';

  const FORMAT = 'notifyi-digital-twin';
  const VERSION = 1;
  const TYPES = ['motor', 'bracket', 'connector', 'opencr', 'laptop'];
  const FACES = new Set(['front', 'back', 'right', 'left', 'top', 'bottom']);
  const TTL_PORTS = { motor: 2, opencr: 3 };

  function invalid(message) { throw new Error(message); }
  function object(value, name) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) invalid(`${name} 형식이 잘못됐습니다.`);
    return value;
  }
  function number(value, name, limit) {
    if (typeof value !== 'number' || !Number.isFinite(value) || Math.abs(value) > limit) invalid(`${name} 값이 올바르지 않습니다.`);
    return value;
  }
  function vector(value, name, limit) {
    if (!Array.isArray(value) || value.length !== 3) invalid(`${name} 형식이 잘못됐습니다.`);
    return value.map((entry, index) => number(entry, `${name}[${index}]`, limit));
  }
  function motorId(value, ids) {
    if (typeof value !== 'string' || !ids.has(value)) invalid('연결 대상 모터가 존재하지 않습니다.');
    return value;
  }
  function cableEnd(value, ids) {
    const end = object(value, '케이블 끝');
    if (!(end.key in TTL_PORTS) || !ids[end.key].has(end.id) || end.kind !== 'ttl'
        || !Number.isInteger(end.anchor) || end.anchor < 0 || end.anchor >= TTL_PORTS[end.key]) {
      invalid('케이블 연결점이 올바르지 않습니다.');
    }
    return { key:end.key, id:end.id, anchor:end.anchor, kind:'ttl' };
  }
  function endpointKey(end) { return `${end.key}:${end.id}:${end.anchor}`; }

  function validate(document) {
    const source = object(document, '프로젝트');
    if (source.format !== FORMAT || source.version !== VERSION) invalid('지원하지 않는 프로젝트 형식 또는 버전입니다.');
    const input = object(source.parts, '부품 목록');
    const parts = {};
    for (const key of TYPES) {
      const list = input[key];
      if (!Array.isArray(list) || list.length < 1 || list.length > 64) invalid(`${key} 개수는 1~64개여야 합니다.`);
      parts[key] = list.map((item, index) => {
        const part = object(item, `${key} #${index + 1}`), id = `${key}-${index + 1}`;
        if (part.id !== id) invalid(`${key} ID 순서가 올바르지 않습니다.`);
        return { id, pos:vector(part.pos, `${id} 위치`, 100), rot:vector(part.rot, `${id} 회전`, 360) };
      });
    }
    const ids = Object.fromEntries(TYPES.map(key => [key, new Set(parts[key].map(part => part.id))]));
    const assignedAxisIds = new Set();
    parts.motor.forEach((part, index) => {
      const joints = object(input.motor[index].joints, `${part.id} 축`);
      part.joints = { A:number(joints.A, `${part.id} A축`, 90), B:number(joints.B, `${part.id} B축`, 90) };
      const axisIds = input.motor[index].axisIds == null ? { A:null, B:null }
        : object(input.motor[index].axisIds, `${part.id} 실물 ID 배정`);
      part.axisIds = {};
      for (const axis of ['A', 'B']) {
        const id = axisIds[axis] ?? null;
        if (id !== null && (!Number.isInteger(id) || id < 1 || id > 252 || assignedAxisIds.has(id))) {
          invalid('실물 모터 ID는 1~252 범위에서 축마다 중복 없이 배정해야 합니다.');
        }
        if (id !== null) assignedAxisIds.add(id);
        part.axisIds[axis] = id;
      }
    });
    const usedShafts = new Set(), usedCases = new Set(), usedChildren = new Set(), parents = new Map();
    parts.bracket.forEach((part, index) => {
      const mates = object(input.bracket[index].mates, `${part.id} 결합`);
      const rootSide = input.bracket[index].rootSide ?? 'fork';
      if (rootSide !== 'fork' && rootSide !== 'plate') invalid('브라켓 기준면이 올바르지 않습니다.');
      let fork = null, plate = null;
      if (mates.fork != null) {
        const data = object(mates.fork, `${part.id} 포크`);
        const parent = motorId(data.motorId, ids.motor);
        if (data.axis !== 'A' && data.axis !== 'B') invalid('포크 축이 올바르지 않습니다.');
        const shaft = `${parent}:${data.axis}`;
        if (usedShafts.has(shaft)) invalid('하나의 축에 브라켓이 중복 연결됐습니다.');
        usedShafts.add(shaft);
        fork = { motorId:parent, axis:data.axis };
      }
      if (mates.plate != null) {
        if (!fork && rootSide === 'fork') invalid('포크가 없는 브라켓에 판이 연결됐습니다.');
        const data = object(mates.plate, `${part.id} 판`);
        const caseMotor = motorId(data.motorId, ids.motor);
        const mount = `${caseMotor}:${data.face}`;
        if (!FACES.has(data.face) || (fork && caseMotor === fork.motorId) || usedCases.has(mount)) invalid('브라켓 판 연결이 올바르지 않습니다.');
        usedCases.add(mount);
        plate = { motorId:caseMotor, face:data.face };
      }
      if (fork && plate) {
        const parent = rootSide === 'plate' ? plate.motorId : fork.motorId;
        const child = rootSide === 'plate' ? fork.motorId : plate.motorId;
        if (usedChildren.has(child)) invalid('한 모터에 상위 브라켓이 중복 연결됐습니다.');
        usedChildren.add(child);
        parents.set(child, parent);
      }
      part.rootSide = rootSide;
      part.mates = { fork, plate };
    });
    for (const motor of ids.motor) {
      const seen = new Set();
      let cursor = motor;
      while (cursor) {
        if (seen.has(cursor)) invalid('모터 결합에 순환 연결이 있습니다.');
        seen.add(cursor);
        cursor = parents.get(cursor);
      }
    }
    const occupiedPorts = new Set();
    parts.connector.forEach((part, index) => {
      const connection = input.connector[index].connection;
      if (connection == null) { part.connection = null; return; }
      const data = object(connection, `${part.id} 연결`);
      const a = cableEnd(data.a, ids), b = cableEnd(data.b, ids);
      if (a.key === 'opencr' && b.key === 'opencr') invalid('OpenCR 포트끼리 케이블을 연결할 수 없습니다.');
      const aKey = endpointKey(a), bKey = endpointKey(b);
      if (aKey === bKey || (a.key === b.key && a.id === b.id)
          || occupiedPorts.has(aKey) || occupiedPorts.has(bKey)) invalid('케이블 연결점이 중복되거나 같은 장치에 연결됐습니다.');
      occupiedPorts.add(aKey); occupiedPorts.add(bKey);
      part.connection = { a, b };
    });
    return { format:FORMAT, version:VERSION, parts };
  }

  function capture(parts) {
    const output = {};
    for (const key of TYPES) {
      output[key] = parts[key].map(part => {
        const item = { id:part.id, pos:[...part.pos], rot:[...part.rot] };
        if (key === 'motor') {
          item.joints = { A:part.joints.A, B:part.joints.B };
          item.axisIds = { A:part.axisIds?.A ?? null, B:part.axisIds?.B ?? null };
        }
        if (key === 'bracket') {
          item.rootSide = part.rootSide ?? 'fork';
          item.mates = {
            fork:part.mates.fork ? { ...part.mates.fork } : null,
            plate:part.mates.plate ? { ...part.mates.plate } : null
          };
        }
        if (key === 'connector') item.connection = part.connection ? {
          a:{ ...part.connection.a }, b:{ ...part.connection.b }
        } : null;
        return item;
      });
    }
    return validate({ format:FORMAT, version:VERSION, parts:output });
  }
  function decode(text) {
    if (typeof text !== 'string' || text.length > 1_000_000) invalid('프로젝트 파일이 너무 크거나 읽을 수 없습니다.');
    let document;
    try { document = JSON.parse(text); } catch { invalid('올바른 JSON 파일이 아닙니다.'); }
    return validate(document);
  }
  function encode(parts) { return JSON.stringify(capture(parts), null, 2); }

  const api = { FORMAT, VERSION, validate, capture, decode, encode };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.NotifyiProjectState = api;
})(typeof window !== 'undefined' ? window : globalThis);
