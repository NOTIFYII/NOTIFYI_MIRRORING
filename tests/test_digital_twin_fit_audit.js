const { test } = require('node:test');
const assert = require('node:assert/strict');
const { assess } = require('../tools/digital_twin/fit_audit.js');

const motors = [{ id: 'motor-1' }, { id: 'motor-2' }, { id: 'motor-3' }];
const bracket = (face, axis = 'A', rootSide = 'plate') => ({
  id: 'bracket-1', rootSide,
  mates: { plate: { motorId: 'motor-1', face }, fork: { motorId: 'motor-2', axis } },
});

test('known +Z/A reference reports only the scoped STEP findings', () => {
  const audit = assess(bracket('front'), motors);
  assert.equal(audit.holes.status, 'limited');
  assert.equal(audit.static.status, 'limited');
  assert.equal(audit.sweep.status, 'interference');
  assert.match(audit.sweep.detail, /±30°/);
  assert.equal(audit.wiring.status, 'unverified');
});

test('a different axis or root orientation does not inherit the reference sweep', () => {
  for (const candidate of [bracket('front', 'B'), bracket('front', 'A', 'fork'), bracket('right')]) {
    const audit = assess(candidate, motors);
    assert.equal(audit.sweep.status, 'unverified');
    assert.equal(audit.static.status, 'unverified');
  }
});

test('unsupported case face is invalid while incomplete or missing motors are unverified', () => {
  assert.equal(assess(bracket('top'), motors).holes.status, 'invalid');
  assert.equal(assess({ id: 'bracket-1', rootSide: 'plate', mates: { fork: null, plate: null } }, motors).sweep.status, 'unverified');
  assert.equal(assess(bracket('front'), [{ id: 'motor-1' }]).sweep.status, 'unverified');
});
