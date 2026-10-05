/* Counts only modeled parts. Fasteners, spacers, and real stock are unknown. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.NotifyiAssemblyBom = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const entries = [
    ['motor', '2XL-430 모터 하우징'],
    ['bracket', 'EF25-F14 브라켓'],
    ['connector', 'DXL TTL 3P 케이블'],
    ['opencr', 'OpenCR REVH'],
    ['laptop', '노트북 (화면 프록시)'],
  ];
  function build(parts) {
    return entries.map(([key, label]) => {
      const items = parts[key] || [];
      const connected = key === 'bracket'
        ? items.filter(item => item.mates?.fork && item.mates?.plate).length
        : key === 'connector'
          ? items.filter(item => item.connection).length
          : null;
      return { key, label, count: items.length, connected };
    });
  }
  function toCsv(rows) {
    const cells = [['부품', '화면 수량', '양쪽 연결 완료 수량'], ...rows.map(row => [row.label, row.count, row.connected ?? ''])];
    return '\ufeff' + cells.map(row => row.map(value => `"${String(value).replaceAll('"', '""')}"`).join(',')).join('\r\n') + '\r\n';
  }
  return { build, toCsv };
});
