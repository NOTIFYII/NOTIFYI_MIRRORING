/* Read-only scene measurement. Socket locations are visual anchors, not verified contacts. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.NotifyiCableMeasure = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function straightLineMm(first, second, motorRadiusMm) {
    if (!Array.isArray(first) || !Array.isArray(second) || first.length !== 3 || second.length !== 3 ||
        !first.every(Number.isFinite) || !second.every(Number.isFinite) ||
        !Number.isFinite(motorRadiusMm) || motorRadiusMm <= 0) return null;
    return Math.hypot(...first.map((value, index) => value - second[index])) * motorRadiusMm;
  }
  return { straightLineMm };
});
