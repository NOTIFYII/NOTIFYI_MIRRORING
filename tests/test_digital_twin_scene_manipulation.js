const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const geometry = require('../tools/digital_twin/scene_manipulation.js');
const { rayFromCamera, intersectPlane, axisParameter, signedRotation, worldYRange } = geometry;
const identity = () => [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
const near = (actual, expected) => assert.ok(Math.abs(actual-expected) < 1e-9, `${actual} != ${expected}`);
const nearPoint = (actual, expected) => { assert.ok(actual); actual.forEach((value,i) => near(value,expected[i])); };
const dot = (a,b) => a.reduce((sum,value,i) => sum+value*b[i],0);
const normalize = a => a.map(value => value/Math.hypot(...a));
const cross = (a,b) => [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
function camera(eye, target, width, height) {
  const back = normalize(eye.map((value,i) => value-target[i]));
  const right = normalize(cross([0,1,0],back)), up = cross(back,right);
  const view = [right[0],up[0],back[0],0,right[1],up[1],back[1],0,right[2],up[2],back[2],0,
    -dot(right,eye),-dot(up,eye),-dot(back,eye),1];
  const f = 1/Math.tan(Math.PI/8), near = .01, far = 100;
  const proj = [f/(width/height),0,0,0,0,f,0,0,0,0,(far+near)/(near-far),-1,0,0,2*far*near/(near-far),0];
  return { view,proj,eye };
}
function project(frame, point, width, height) {
  const v = frame.view, p = frame.proj;
  const camera = [0,1,2].map(row => v[row]*point[0]+v[row+4]*point[1]+v[row+8]*point[2]+v[row+12]);
  return [(p[0]*camera[0]/-camera[2]-p[8]+1)*width/2,
    (1-(p[5]*camera[1]/-camera[2]-p[9]))*height/2];
}

test('perspective rays round trip points on XY, XZ and YZ planes with a rotated camera', () => {
  const width = 960, height = 640, frame = camera([5,6,8],[1,.5,-1],width,height);
  for (const [point,normal] of [[[2,-1,0],[0,0,1]],[[2,0,-3],[0,1,0]],[[0,2,-1],[1,0,0]]]) {
    const pixel = project(frame,point,width,height);
    const ray = rayFromCamera(frame,width,height,...pixel);
    nearPoint(ray.origin,frame.eye);
    near(Math.hypot(...ray.direction),1);
    nearPoint(intersectPlane(ray,point,normal),point);
  }
  frame.proj[8] = .2; frame.proj[9] = -.15;
  const point = [2,0,-3];
  nearPoint(intersectPlane(rayFromCamera(frame,width,height,...project(frame,point,width,height)),point,[0,1,0]),point);
});

test('plane intersections guard near parallel rays and reject intersections behind origin', () => {
  assert.equal(intersectPlane({origin:[0,1,0],direction:[1,1e-10,0]},[0,0,0],[0,10,0]),null);
  assert.equal(intersectPlane({origin:[0,1,0],direction:[0,1,0]},[0,0,0],[0,1,0]),null);
  nearPoint(intersectPlane({origin:[0,1,0],direction:[0,-4,0]},[0,0,0],[0,2,0]),[0,0,0]);
  nearPoint(intersectPlane({origin:[1,0,2],direction:[0,-1,0]},[0,0,0],[0,1,0]),[1,0,2]);
});

test('axis parameters measure signed displacements with normalized axes and skew rays', () => {
  for (const axis of [[1,0,0],[0,1,0],[0,0,1]]) {
    const pivot = [2,3,4], perpendicular = axis[0] ? [0,0,1] : [1,0,0];
    for (const displacement of [-3,0,4]) {
      const origin = pivot.map((value,i) => value+axis[i]*displacement+perpendicular[i]*5);
      near(axisParameter({origin,direction:perpendicular.map(value => -value*2)},pivot,axis.map(value => value*7)),displacement);
    }
  }
  near(axisParameter({origin:[3,2,5],direction:[0,0,-1]},[0,0,0],[1,0,0]),3);
  assert.equal(axisParameter({origin:[0,0,1],direction:[1,0,1e-6]},[0,0,0],[1,0,0]),null);
  assert.equal(axisParameter({origin:[0,0,1],direction:[1,0,0]},[0,0,0],[1,0,0]),null);
  assert.equal(axisParameter({origin:[0,0,1],direction:[0,0,1]},[0,0,0],[1,0,0]),null);
});

test('signed rotations follow right-hand rule, project axial components and use radians', () => {
  near(signedRotation([1,0,0],[0,1,0],[0,0,1]),Math.PI/2);
  near(signedRotation([1,0,0],[0,-1,0],[0,0,1]),-Math.PI/2);
  near(signedRotation([1,0,4],[0,2,-3],[0,0,10]),Math.PI/2);
  near(signedRotation([0,1,0],[0,0,1],[1,0,0]),Math.PI/2);
  near(signedRotation([0,0,1],[1,0,0],[0,1,0]),Math.PI/2);
  near(signedRotation([1,0,0],[1,0,0],[0,0,1]),0);
  near(Math.abs(signedRotation([1,0,0],[-1,0,0],[0,0,1])),Math.PI);
  assert.equal(signedRotation([0,0,1],[1,0,0],[0,0,1]),null);
});

test('world Y range scans actual mesh vertices under 90 and non-90 degree transforms', () => {
  const verts = new Float32Array([0,0,0,2,0,0,0,1,0]);
  const model = identity(); model[1] = 1; model[5] = 0; model[0] = 0; model[4] = -1; model[13] = -3;
  assert.deepEqual(worldYRange(verts,model),{min:-3,max:-1});
  const angle = -Math.PI/4;
  model[0] = Math.cos(angle); model[1] = Math.sin(angle);
  model[4] = -Math.sin(angle); model[5] = Math.cos(angle); model[13] = 5;
  const range = worldYRange(verts,model);
  near(range.min,5-Math.SQRT2); near(range.max,5+Math.SQRT1_2);
  // The absent AABB corner (2,1,0) must not inflate the maximum.
  model[1] = Math.SQRT1_2;
  near(worldYRange(verts,model).max,5+Math.SQRT2);
  model[9] = -2;
  assert.deepEqual(worldYRange([0,0,3,0,0,-2],model),{min:-1,max:9});
  assert.deepEqual(Array.from(verts),[0,0,0,2,0,0,0,1,0]);
});

test('all utilities reject non-finite and malformed inputs without throwing', () => {
  const frame = camera([5,6,8],[0,0,0],800,600), ray = {origin:[0,0,1],direction:[0,0,-1]};
  for (const bad of [NaN,Infinity,-Infinity,'1',undefined]) {
    assert.equal(rayFromCamera(frame,800,600,bad,0),null);
    assert.equal(intersectPlane(ray,[bad,0,0],[0,0,1]),null);
    assert.equal(axisParameter(ray,[0,0,0],[bad,1,0]),null);
    assert.equal(signedRotation([bad,0,0],[0,1,0],[0,0,1]),null);
    assert.equal(worldYRange([0,bad,0],identity()),null);
    const model = identity(); model[0] = bad;
    assert.equal(worldYRange([0,0,0],model),null);
  }
  assert.equal(rayFromCamera(frame,0,600,0,0),null);
  assert.equal(rayFromCamera({...frame,proj:identity()},800,600,0,0),null);
  assert.equal(rayFromCamera({...frame,view:[]},800,600,0,0),null);
  assert.equal(rayFromCamera(null,800,600,0,0),null);
  assert.equal(intersectPlane(null,[0,0,0],[0,1,0]),null);
  assert.equal(intersectPlane({...ray,direction:[0,0,0]},[0,0,0],[0,1,0]),null);
  assert.equal(axisParameter(ray,[0,0,0],[0,0,0]),null);
  assert.equal(signedRotation([1,0,0],[0,1,0],[0,0,0]),null);
  assert.equal(worldYRange([],identity()),null);
  assert.equal(worldYRange([0,0],identity()),null);
  assert.equal(worldYRange([0,0,0],[]),null);
  const projective = identity(); projective[3] = 1;
  assert.equal(worldYRange([0,0,0],projective),null);
  const overflow = identity(); overflow[5] = 1e308;
  assert.equal(worldYRange([0,1e308,0],overflow),null);
});

test('UMD browser export exposes the same five utilities', () => {
  const context = {};
  vm.runInNewContext(fs.readFileSync(require.resolve('../tools/digital_twin/scene_manipulation.js'),'utf8'),context);
  assert.deepEqual(Object.keys(context.NotifyiSceneManipulation).sort(),Object.keys(geometry).sort());
  assert.equal(context.NotifyiSceneManipulation.signedRotation([1,0,0],[0,1,0],[0,0,1]),Math.PI/2);
});
