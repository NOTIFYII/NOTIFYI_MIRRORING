const { test } = require('node:test');
const assert = require('node:assert/strict');
const { build, toCsv } = require('../tools/digital_twin/assembly_bom.js');

test('assembly count distinguishes parts in scene from completed connections', () => {
  const rows = build({
    motor: [{}, {}],
    bracket: [{ mates: { fork: { motorId: 'motor-1' }, plate: { motorId: 'motor-2' } } }, { mates: { fork: null, plate: null } }],
    connector: [{ connection: { a: {}, b: {} } }, { connection: null }],
    opencr: [{}], laptop: [{}],
  });
  assert.deepEqual(rows.map(row => [row.key, row.count, row.connected]), [
    ['motor', 2, null], ['bracket', 2, 1], ['connector', 2, 1], ['opencr', 1, null], ['laptop', 1, null],
  ]);
  assert.match(toCsv(rows), /^\ufeff"부품","화면 수량","양쪽 연결 완료 수량"/);
  assert.match(toCsv(rows), /"EF25-F14 브라켓","2","1"/);
});
