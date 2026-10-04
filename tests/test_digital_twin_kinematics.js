const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// Exercise the same transform functions that the browser uses, without WebGL or motors.
const source = fs.readFileSync(path.join(__dirname, '../tools/digital_twin/workspace.js'), 'utf8');
function functionSource(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `${name} missing`);
  const open = source.indexOf('{', start);
  let depth = 0;
  for (let index = open; index < source.length; index += 1) {
    if (source[index] === '{') depth += 1;
    if (source[index] === '}' && --depth === 0) return source.slice(start, index + 1);
  }
  throw new Error(`${name} unterminated`);
}
const names = [
  'mul', 'translate', 'scale', 'rx', 'ry', 'rz', 'eulerRotation', 'partRotation',
  'partModel', 'transformPoint', 'rotateVector', 'inverseRotation', 'findPart',
  'bracketRoot', 'bracketChild', 'incomingBracketFor', 'outgoingBracketsFor',
  'connectedJointFor',
  'forkBracketsFor', 'plateBracketFor', 'wouldCreateCycle', 'portsFor',
  'mechanicalPortInUse', 'validPortPair',
  'alignBracketToMotor', 'alignCaseMotorToBracket', 'alignBracketToCaseMotor',
  'alignForkMotorToBracket', 'updateMatedParts'
];
const constants = source.slice(source.indexOf('const axisMounts='), source.indexOf('function portsFor('));
const makeScene = new Function('parts', `
  const identity=()=>[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
  const state={motor:{radius:23.25},parts};
  ${names.map(functionSource).join('\n')}
  ${constants}
  return {state,updateMatedParts,partModel,transformPoint,bracketPivot,bracketPlate,axisMounts,connectionPorts,mechanicalPortInUse,validPortPair,connectedJointFor};
`);
const near = (actual, expected, message) => assert.ok(Math.abs(actual - expected) < 1e-8, `${message}: ${actual} != ${expected}`);
const nearPoint = (actual, expected, message) => actual.forEach((value, index) => near(value, expected[index], `${message}[${index}]`));
function motor(id) { return {id,key:'motor',pos:[0,0,0],rot:[0,0,0],joints:{A:0,B:0},assemblyRotation:null}; }
function bracket(rootSide, fork, plate) { return {id:'bracket-1',key:'bracket',pos:[0,0,0],rot:[0,0,0],rootSide,mates:{fork,plate},assemblyRotation:null}; }

test('plate-root: lower case remains fixed while upper shaft motor rotates around fork pivot', () => {
  const lower=motor('motor-1'),upper=motor('motor-2');
  const link=bracket('plate',{motorId:upper.id,axis:'A'},{motorId:lower.id,face:'front'});
  const scene=makeScene({motor:[lower,upper],bracket:[link]});
  scene.updateMatedParts();
  const bracketPosition=[...link.pos],initialRotation=[...upper.assemblyRotation];
  assert.ok(upper.pos[2]>lower.pos[2], 'shaft motor should sit outside the +Z case face');
  const plateWorld=scene.transformPoint(scene.partModel(link),scene.bracketPlate);
  const faceWorld=scene.transformPoint(scene.partModel(lower),scene.connectionPorts.motor[6].point);
  assert.ok(Math.hypot(...plateWorld.map((value,index)=>value-faceWorld[index]))<0.03,
    'bracket plate must sit at the +Z case face with a 0.5 mm spacer');
  nearPoint(scene.transformPoint(scene.partModel(link),scene.bracketPivot),
    scene.transformPoint(scene.partModel(upper),scene.axisMounts.A.center), 'shaft/pivot');
  upper.joints.A=30;
  scene.updateMatedParts();
  nearPoint(lower.pos,[0,0,0],'lower case');
  nearPoint(link.pos,bracketPosition,'fixed bracket');
  nearPoint(scene.transformPoint(scene.partModel(link),scene.bracketPlate),plateWorld,'plate remains on fixed case');
  assert.notDeepEqual(upper.assemblyRotation,initialRotation);
  nearPoint(scene.transformPoint(scene.partModel(link),scene.bracketPivot),
    scene.transformPoint(scene.partModel(upper),scene.axisMounts.A.center), 'shaft/pivot after rotation');
});

test('connected motor pose can be laid flat after assembly without breaking mates', () => {
  const lower=motor('motor-1'),upper=motor('motor-2');
  const link=bracket('plate',{motorId:upper.id,axis:'A'},{motorId:lower.id,face:'front'});
  const scene=makeScene({motor:[lower,upper],bracket:[link]});
  scene.updateMatedParts();
  const connection=scene.connectedJointFor(upper);
  assert.equal(connection.motor,upper);
  assert.equal(connection.axis,'A');
  assert.equal(scene.connectedJointFor(lower),null);
  connection.motor.joints[connection.axis]=90;
  scene.updateMatedParts();
  nearPoint(scene.transformPoint(scene.partModel(link),scene.bracketPivot),
    scene.transformPoint(scene.partModel(upper),scene.axisMounts.A.center),'fork pivot at 90 degrees');
  assert.deepEqual(link.mates,{fork:{motorId:upper.id,axis:'A'},plate:{motorId:lower.id,face:'front'}});
});

test('legacy fork-root pose is driven by the parent motor axis', () => {
  const parent=motor('motor-1'),child=motor('motor-2');
  const link=bracket('fork',{motorId:parent.id,axis:'B'},{motorId:child.id,face:'right'});
  const scene=makeScene({motor:[parent,child],bracket:[link]});
  scene.updateMatedParts();
  const control=scene.connectedJointFor(child);
  assert.equal(control.motor,parent);
  assert.equal(control.axis,'B');
  const initial=[...child.pos];
  control.motor.joints.B=-90;
  scene.updateMatedParts();
  assert.notDeepEqual(child.pos,initial);
});

test('legacy fork-root: rotating the shaft moves the plate-mounted child', () => {
  const lower=motor('motor-1'),upper=motor('motor-2');
  const link=bracket('fork',{motorId:lower.id,axis:'A'},{motorId:upper.id,face:'front'});
  const scene=makeScene({motor:[lower,upper],bracket:[link]});
  scene.updateMatedParts();
  const initial=[...upper.pos];
  lower.joints.A=30;
  scene.updateMatedParts();
  nearPoint(lower.pos,[0,0,0],'shaft-root lower motor');
  assert.notDeepEqual(upper.pos,initial);
});

test('plate-root permits plate-first connection and then another motor shaft', () => {
  const lower=motor('motor-1'),upper=motor('motor-2');
  const link=bracket('plate',null,null);
  const scene=makeScene({motor:[lower,upper],bracket:[link]});
  const port=(key,id,anchor)=>({key,id,anchor,kind:'mechanical'});
  assert.equal(scene.validPortPair(port('motor',lower.id,6),port('bracket',link.id,1)),true);
  assert.equal(scene.validPortPair(port('motor',lower.id,10),port('bracket',link.id,1)),false,'+Y top has no plate holes');
  link.mates.plate={motorId:lower.id,face:'front'};
  assert.equal(scene.validPortPair(port('motor',upper.id,2),port('bracket',link.id,0)),true);
  assert.equal(scene.validPortPair(port('motor',lower.id,2),port('bracket',link.id,0)),false);
});

test('one fork reserves both horn and idler of one axis, leaving the other axis free', () => {
  const lower=motor('motor-1'),upper=motor('motor-2');
  const link=bracket('plate',{motorId:upper.id,axis:'A'},{motorId:lower.id,face:'front'});
  const scene=makeScene({motor:[lower,upper],bracket:[link]});
  const port=(anchor)=>({key:'motor',id:upper.id,anchor,kind:'mechanical'});
  assert.equal(scene.mechanicalPortInUse(port(2)),true,'A horn is occupied');
  assert.equal(scene.mechanicalPortInUse(port(3)),true,'A idler is occupied by the same fork');
  assert.equal(scene.mechanicalPortInUse(port(4)),false,'B horn is still available');
  assert.equal(scene.mechanicalPortInUse(port(5)),false,'B idler is still available');
  const other={...bracket('plate',null,null),id:'bracket-2'};
  scene.state.parts.bracket.push(other);
  assert.equal(scene.validPortPair(port(3),{key:'bracket',id:other.id,anchor:0,kind:'mechanical'}),false);
  assert.equal(scene.validPortPair(port(5),{key:'bracket',id:other.id,anchor:0,kind:'mechanical'}),true);
});

test('plate-root chain carries a third motor while keeping its lower support fixed', () => {
  const base=motor('motor-1'),middle=motor('motor-2'),top=motor('motor-3');
  const first=bracket('plate',{motorId:middle.id,axis:'A'},{motorId:base.id,face:'front'});
  const second={...bracket('plate',{motorId:top.id,axis:'B'},{motorId:middle.id,face:'right'}),id:'bracket-2'};
  const scene=makeScene({motor:[base,middle,top],bracket:[first,second]});
  scene.updateMatedParts();
  const initialTop=[...top.pos];
  middle.joints.A=25;
  scene.updateMatedParts();
  nearPoint(base.pos,[0,0,0],'fixed base');
  assert.notDeepEqual(top.pos,initialTop);
});
