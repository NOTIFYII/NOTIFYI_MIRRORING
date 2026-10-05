const { test } = require('node:test');
const assert = require('node:assert/strict');
const { straightLineMm } = require('../tools/digital_twin/cable_measure.js');

test('scene displacement is converted to millimetres with the displayed motor scale', () => {
  assert.equal(straightLineMm([0, 0, 0], [3, 4, 0], 20), 100);
  assert.equal(straightLineMm([1, 2, 3], [1, 2, 3], 20), 0);
});

test('invalid coordinates or scale produce no measurement', () => {
  assert.equal(straightLineMm([0, 0, 0], [1, 0, 0], 0), null);
  assert.equal(straightLineMm([0, NaN, 0], [1, 0, 0], 20), null);
});
