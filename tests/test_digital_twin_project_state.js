const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const project = require('../tools/digital_twin/project_state.js');

function example() {
  const part = (key, index) => ({ id:`${key}-${index}`, pos:[index, 0, 0], rot:[0, 0, 0] });
  return {
    motor:[1, 2, 3].map(index => ({ ...part('motor', index), joints:{ A:0, B:0 } })),
    bracket:[1, 2].map(index => ({ ...part('bracket', index), mates:{ fork:null, plate:null } })),
    connector:[{ ...part('connector', 1), connection:null }],
    opencr:[part('opencr', 1)],
    laptop:[part('laptop', 1)]
  };
}

test('three-motor chain and rotations survive JSON round trip without runtime/hardware state', () => {
  const parts = example();
  parts.motor[0].joints.A = 45;
  parts.motor[0].axisIds = { A:2, B:3 };
  parts.motor[1].axisIds = { A:4, B:5 };
  parts.motor[1].rot = [90, 0, 0];
  parts.motor[0].assemblyRotation = [1, 2, 3];
  parts.motor[0].hardwareError = '0x20';
  parts.bracket[0].mates = { fork:{ motorId:'motor-1', axis:'A' }, plate:{ motorId:'motor-2', face:'front' } };
  parts.bracket[1].mates = { fork:{ motorId:'motor-2', axis:'B' }, plate:{ motorId:'motor-3', face:'right' } };
  parts.connector[0].connection = {
    a:{ key:'motor', id:'motor-1', anchor:0, kind:'ttl' },
    b:{ key:'opencr', id:'opencr-1', anchor:1, kind:'ttl' }
  };
  const restored = project.decode(project.encode(parts));
  assert.equal(restored.parts.motor[0].joints.A, 45);
  assert.deepEqual(restored.parts.motor[0].axisIds, { A:2, B:3 });
  assert.equal(restored.parts.bracket[1].mates.plate.motorId, 'motor-3');
  assert.equal(restored.parts.connector[0].connection.b.anchor, 1);
  assert.equal('hardwareError' in restored.parts.motor[0], false);
  assert.equal('assemblyRotation' in restored.parts.motor[0], false);
});

test('older saved projects load with unassigned axes', () => {
  const old = project.capture(example());
  old.parts.motor.forEach(motor => { delete motor.axisIds; });
  old.parts.bracket.forEach(bracket => { delete bracket.rootSide; });
  assert.deepEqual(project.validate(old).parts.motor[0].axisIds, { A:null, B:null });
  assert.equal(project.validate(old).parts.bracket[0].rootSide, 'fork');
});

test('version 1 scene positions migrate to desk surface Y=0 only once', () => {
  const old = project.capture(example());
  old.version = 1;
  old.parts.motor[0].pos[1] = -1;
  old.parts.opencr[0].pos[1] = -1.55;
  const migrated = project.validate(old);
  assert.equal(migrated.version, 2);
  assert.ok(Math.abs(migrated.parts.motor[0].pos[1] - .58) < 1e-10);
  assert.ok(Math.abs(migrated.parts.opencr[0].pos[1] - .03) < 1e-10);
  assert.deepEqual(project.decode(JSON.stringify(migrated)).parts.motor[0].pos, migrated.parts.motor[0].pos);
});

test('plate-root bracket supports lower case to upper shaft and preserves the direction', () => {
  const parts = example();
  parts.bracket[0].rootSide = 'plate';
  parts.bracket[0].mates = { plate:{ motorId:'motor-1', face:'top' }, fork:{ motorId:'motor-2', axis:'A' } };
  const saved = project.decode(project.encode(parts));
  assert.equal(saved.parts.bracket[0].rootSide, 'plate');
  assert.equal(saved.parts.bracket[0].mates.plate.face, 'top');
  assert.equal(saved.parts.bracket[0].mates.fork.motorId, 'motor-2');
});

test('plate-root may be assembled plate-first, but duplicate child and reverse cycles fail', () => {
  const parts = example();
  parts.bracket[0].rootSide = 'plate';
  parts.bracket[0].mates.plate = { motorId:'motor-1', face:'top' };
  assert.equal(project.capture(parts).parts.bracket[0].mates.fork, null);
  parts.bracket[0].mates.fork = { motorId:'motor-2', axis:'A' };
  parts.bracket[1].rootSide = 'plate';
  parts.bracket[1].mates = { plate:{ motorId:'motor-3', face:'top' }, fork:{ motorId:'motor-2', axis:'B' } };
  assert.throws(() => project.capture(parts), /중복/);
  parts.bracket[1].mates = { plate:{ motorId:'motor-2', face:'top' }, fork:{ motorId:'motor-1', axis:'B' } };
  assert.throws(() => project.capture(parts), /순환/);
});

test('one physical ID cannot be assigned to two axes', () => {
  const parts = example();
  parts.motor[0].axisIds = { A:2, B:3 };
  parts.motor[1].axisIds = { A:2, B:null };
  assert.throws(() => project.capture(parts), /중복/);
});

test('unsupported version and malformed JSON are rejected', () => {
  assert.throws(() => project.decode('{'), /JSON/);
  assert.throws(() => project.decode(fs.readFileSync(path.join(__dirname, 'fixtures/invalid_digital_twin.json'), 'utf8')), /형식/);
  const document = project.capture(example());
  document.version = 99;
  assert.throws(() => project.validate(document), /버전/);
});

test('duplicate shafts and cyclic motor chains are rejected', () => {
  const parts = example();
  parts.bracket[0].mates = { fork:{ motorId:'motor-1', axis:'A' }, plate:{ motorId:'motor-2', face:'front' } };
  parts.bracket[1].mates = { fork:{ motorId:'motor-1', axis:'A' }, plate:{ motorId:'motor-3', face:'front' } };
  assert.throws(() => project.capture(parts), /중복/);
  parts.bracket[1].mates = { fork:{ motorId:'motor-2', axis:'A' }, plate:{ motorId:'motor-1', face:'front' } };
  assert.throws(() => project.capture(parts), /순환/);
});

test('orphan plate, missing motor and invalid coordinates are rejected', () => {
  const parts = example();
  parts.bracket[0].mates.plate = { motorId:'motor-2', face:'front' };
  assert.throws(() => project.capture(parts), /포크가 없는/);
  parts.bracket[0].mates.fork = { motorId:'motor-99', axis:'A' };
  assert.throws(() => project.capture(parts), /존재하지/);
  parts.bracket[0].mates = { fork:null, plate:null };
  parts.motor[0].pos[0] = Infinity;
  assert.throws(() => project.capture(parts), /위치/);
});

test('duplicate or impossible cable ports are rejected', () => {
  const parts = example();
  parts.connector[0].connection = {
    a:{ key:'motor', id:'motor-1', anchor:0, kind:'ttl' },
    b:{ key:'motor', id:'motor-1', anchor:1, kind:'ttl' }
  };
  assert.throws(() => project.capture(parts), /같은 장치/);
  parts.connector[0].connection.b = { key:'motor', id:'motor-2', anchor:5, kind:'ttl' };
  assert.throws(() => project.capture(parts), /연결점/);
});
