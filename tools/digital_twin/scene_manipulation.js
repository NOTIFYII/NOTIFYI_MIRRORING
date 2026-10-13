/* Pure scene geometry. Column-major matrices; screen coordinates in CSS pixels.
 * Invalid, degenerate, parallel, or behind-camera results return null.
 * Rays are { origin, direction }; angles are radians; Y ranges are { min, max }.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.NotifyiSceneManipulation = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const EPSILON = 1e-8;
  function finiteArray(value, length) {
    if (!value || value.length !== length) return false;
    for (let i = 0; i < length; i++) if (!Number.isFinite(value[i])) return false;
    return true;
  }
  function dot(a, b) { return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]; }
  function subtract(a, b) { return a.map((value, i) => value - b[i]); }
  function unit(value) {
    if (!finiteArray(value, 3)) return null;
    const length = Math.hypot(...value);
    if (!Number.isFinite(length) || length <= EPSILON) return null;
    return Array.from(value, component => component / length);
  }
  function validRay(ray) { return ray && finiteArray(ray.origin, 3) && unit(ray.direction); }

  // Rigid lookAt view and standard perspective projection, including off-center frusta.
  function rayFromCamera(frame, width, height, x, y) {
    if (!frame || !finiteArray(frame.view, 16) || !finiteArray(frame.proj, 16)
        || !finiteArray(frame.eye, 3) || ![width,height,x,y].every(Number.isFinite)
        || width <= 0 || height <= 0) return null;
    const v = frame.view, p = frame.proj;
    if (Math.abs(p[0]) <= EPSILON || Math.abs(p[5]) <= EPSILON || p[11] !== -1
        || p[15] !== 0 || [1,2,3,4,6,7,12,13].some(i => p[i] !== 0)) return null;
    const right = [v[0],v[4],v[8]], up = [v[1],v[5],v[9]], back = [v[2],v[6],v[10]];
    if ([right,up,back].some(basis => Math.abs(dot(basis,basis)-1) > 1e-5)
        || Math.abs(dot(right,up)) > 1e-5 || Math.abs(dot(right,back)) > 1e-5
        || Math.abs(dot(up,back)) > 1e-5 || v[3] !== 0 || v[7] !== 0
        || v[11] !== 0 || v[15] !== 1) return null;
    const cameraX = (2*x/width - 1 + p[8])/p[0];
    const cameraY = (1 - 2*y/height + p[9])/p[5];
    const direction = unit(right.map((value,i) => value*cameraX + up[i]*cameraY - back[i]));
    return direction ? { origin:Array.from(frame.eye), direction } : null;
  }

  function intersectPlane(ray, point, normal) {
    const direction = validRay(ray), n = unit(normal);
    if (!direction || !n || !finiteArray(point, 3)) return null;
    const denominator = dot(direction,n);
    if (Math.abs(denominator) <= EPSILON) return null;
    const t = dot(subtract(Array.from(point),ray.origin),n)/denominator;
    if (!Number.isFinite(t) || t < 0) return null;
    const hit = Array.from(ray.origin, (value,i) => value + t*direction[i]);
    return finiteArray(hit,3) ? hit : null;
  }

  // Signed world distance on the normalized axis at its closest approach to the ray.
  function axisParameter(ray, pivot, axis) {
    const direction = validRay(ray), a = unit(axis);
    if (!direction || !a || !finiteArray(pivot,3)) return null;
    const b = dot(direction,a), denominator = 1-b*b;
    if (denominator <= EPSILON) return null;
    const offset = subtract(Array.from(ray.origin),pivot);
    const d = dot(a,offset), e = dot(direction,offset);
    const parameter = (d-b*e)/denominator;
    const t = b*parameter-e;
    return Number.isFinite(parameter) && Number.isFinite(t) && t >= 0 ? parameter : null;
  }

  // Project onto the axis-normal plane, then apply the right-hand rule in [-PI, PI].
  function signedRotation(from, to, axis) {
    const a = unit(axis);
    if (!a || !finiteArray(from,3) || !finiteArray(to,3)) return null;
    const project = vector => unit(Array.from(vector, (value,i) => value-a[i]*dot(vector,a)));
    const f = project(from), t = project(to);
    if (!f || !t) return null;
    const cross = [f[1]*t[2]-f[2]*t[1],f[2]*t[0]-f[0]*t[2],f[0]*t[1]-f[1]*t[0]];
    return Math.atan2(dot(a,cross),dot(f,t));
  }

  // Exact extrema for a triangle mesh under an affine model, without temporary vertices.
  function worldYRange(verts, model) {
    if (!verts || !Number.isInteger(verts.length) || verts.length === 0 || verts.length%3
        || !finiteArray(model,16) || model[3] !== 0 || model[7] !== 0
        || model[11] !== 0 || model[15] !== 1) return null;
    let min = Infinity, max = -Infinity;
    for (let i = 0; i < verts.length; i += 3) {
      const x = verts[i], y = verts[i+1], z = verts[i+2];
      if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) return null;
      const worldY = model[1]*x + model[5]*y + model[9]*z + model[13];
      if (!Number.isFinite(worldY)) return null;
      if (worldY < min) min = worldY;
      if (worldY > max) max = worldY;
    }
    return { min, max };
  }
  return { rayFromCamera, intersectPlane, axisParameter, signedRotation, worldYRange };
});
