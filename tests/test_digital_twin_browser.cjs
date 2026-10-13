const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('node:path');
const { readFile } = require('node:fs/promises');

let chromium;
try {
  ({ chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright'));
} catch {
  throw new Error('Playwright를 찾지 못했습니다. PLAYWRIGHT_MODULE에 설치된 playwright 경로를 지정하세요.');
}

const root = path.resolve(__dirname, '../tools/digital_twin');
const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.stl': 'model/stl' };
let server;
let browser;
let origin;

before(async () => {
  server = http.createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      const target = path.resolve(root, `.${pathname === '/' ? '/index.html' : pathname}`);
      if (!target.startsWith(`${root}${path.sep}`)) {
        response.writeHead(403).end();
        return;
      }
      const body = await readFile(target);
      response.writeHead(200, { 'content-type': mime[path.extname(target)] || 'application/octet-stream' }).end(body);
    } catch {
      response.writeHead(404).end();
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({ headless: true });
});

after(async () => {
  await browser?.close();
  if (server) await new Promise(resolve => server.close(resolve));
});

async function freshPage() {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.goto(origin);
  await page.locator('#statusDot.live').waitFor();
  return { context, page };
}

test('공식 Link Frame 둘을 추가하고 배치·회전·저장한 뒤 마지막 부품도 삭제한다', async () => {
  const { context, page } = await freshPage();
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  try {
    for(const key of ['linkLong','linkShort']){
      const row=page.locator(`.part-row[data-key=${key}]`);
      assert.equal(await row.locator('.part-name').innerText(),`Link Frame · ${key==='linkLong'?'Short':'Long'}`);
      assert.equal(await row.locator('[data-action=select]').isEnabled(),false);
      await row.locator('[data-action=add]').click();
      assert.equal(await row.locator('.part-count').innerText(),'1');
      assert.equal(await page.locator('#linkFrameInfo').isVisible(),true);
      await page.locator('.placement-angle-row[data-placement-axis=X] [data-placement-angle="90"]').click();
      await page.locator('[data-assembly-tool=place]').click();
      await page.locator('#focusPartBtn').click();
      const info=await page.evaluate(key=>({
        triangles:partMesh(state.parts[key][0]).n,
        rot:state.parts[key][0].rot,
        ports:portsFor(state.parts[key][0]).length
      }),key);
      assert.ok(info.triangles>70000);
      assert.deepEqual(info.rot,[90,0,0]);
      assert.equal(info.ports,0);
    }
    await page.evaluate(()=>{state.parts.linkShort[0].pos[0]=3;draw();});
    await page.waitForFunction(()=>JSON.parse(localStorage.getItem(PROJECT_STORAGE_KEY))?.parts.linkShort[0]?.pos[0]===3);
    await page.reload();await page.locator('#statusDot.live').waitFor();
    assert.deepEqual(await page.evaluate(()=>state.parts.linkShort[0].rot),[90,0,0]);
    assert.equal(await page.evaluate(()=>state.parts.linkShort[0].pos[0]),3);
    assert.equal(await page.evaluate(()=>NotifyiAssemblyBom.build(state.parts).find(row=>row.key==='linkLong').count),1);
    await page.locator('.part-row[data-key=linkLong] [data-action=select]').click();
    await page.locator('[data-assembly-tool=place]').click();
    await page.locator('#focusPartBtn').click();
    if(process.env.LINK_FRAME_SCREENSHOT)await page.screenshot({path:process.env.LINK_FRAME_SCREENSHOT});
    await page.locator('.part-row[data-key=linkLong] [data-action=remove]').click();
    assert.equal(await page.evaluate(()=>state.selectedKey),'motor');
    assert.equal(await page.locator('.part-row[data-key=linkLong] .part-count').innerText(),'0');
    await page.locator('#undoBtn').click();
    assert.equal(await page.locator('.part-row[data-key=linkLong] .part-count').innerText(),'1');
    assert.deepEqual(errors,[]);
  } finally {await context.close();}
});

test('체결 후 상대 모터를 눕혔다가 되돌린다', async () => {
  const { context, page } = await freshPage();
  try {
    await page.locator('#exampleAssemblyBtn').click();
    await page.locator('[data-workspace-mode=motion]').click();
    await page.locator('.part-row[data-key=motor] [data-action=instance]').nth(1).click();
    assert.equal(await page.locator('#connectedPose').isVisible(), true);
    await page.getByRole('button', { name: '+90° 눕혀보기' }).click();
    assert.match(await page.locator('#connectedPoseHint').innerText(), /현재 90°/);
    await page.getByRole('button', { name: '0°', exact: true }).click();
    assert.match(await page.locator('#connectedPoseHint').innerText(), /현재 0°/);
    await page.waitForFunction(() => pickPart(600, 490 - document.getElementById('gl').getBoundingClientRect().top)?.id === 'motor-2');
    await page.mouse.move(600, 490);
    await page.mouse.down();
    await page.mouse.move(720, 490, { steps: 8 });
    await page.mouse.up();
    assert.match(await page.locator('#connectedPoseHint').innerText(), /현재 60°/);
  } finally {
    await context.close();
  }
});

test('체결 예제는 부분 확인과 회전 간섭을 함께 알리고 실제 안전 범위로 오인시키지 않는다', async () => {
  const { context, page } = await freshPage();
  try {
    await page.waitForFunction(() => document.querySelector('#fitAudit')?.dataset.verdict === 'unverified');
    assert.equal(await page.locator('#fitAudit').getAttribute('data-verdict'), 'unverified');
    await page.locator('#exampleAssemblyBtn').click();
    assert.equal(await page.locator('#fitAudit').getAttribute('data-verdict'), 'interference');
    assert.match(await page.locator('#fitAudit').innerText(), /±30°/);
    await page.locator('#fitAuditDetails').evaluate(node => { node.open = true; });
    assert.match(await page.locator('#fitAuditList').innerText(), /브라켓 #1/);
    assert.match(await page.locator('#fitAuditList').innerText(), /배선 여유: 미검증/);
    await page.locator('[data-workspace-mode=motion]').click();
    assert.match(await page.locator('.joint-preview-note').innerText(), /실물 ID별 허용각/);
  } finally {
    await context.close();
  }
});

test('부품 수량표는 화면 수량과 연결 완료 수량을 구분한다', async () => {
  const { context, page } = await freshPage();
  try {
    await page.locator('#exampleAssemblyBtn').click();
    await page.locator('#assemblyBom').evaluate(node => { node.open = true; });
    const rows = await page.locator('#assemblyBomList tbody tr').evaluateAll(nodes => nodes.map(node => Array.from(node.querySelectorAll('td'), cell => cell.textContent)));
    assert.ok(rows.some(row => row[0] === '2XL-430 모터 하우징' && row[1] === '2'), JSON.stringify(rows));
    assert.ok(rows.some(row => row[0] === 'EF25-F14 브라켓' && row[1] === '1' && row[2] === '1'));
    assert.ok(rows.some(row => row[0] === 'DXL TTL 3P 케이블' && row[1] === '1' && row[2] === '0'));
  } finally {
    await context.close();
  }
});

test('읽기 전용 모터 관측이 끊기면 같은 tick도 오래된 값으로 표시한다', async () => {
  const { context, page } = await freshPage();
  try {
    let fresh = true;
    await page.route('**/api/workspace', route => route.fulfill({ json: {
      host: 'samsung', bus: { port: '/dev/ttyACM0', baudrate: 57600, protocol: 2.0 },
      port_present: true, active_ids: [2], unused_ids: [], joints: [{ id: 2, name: 'waist', label: '허리', zero_position: 1034 }],
      motor_probe: { source: 'read_only_watch', sequence: 7, checked_at: Date.now() / 1000,
        age_seconds: fresh ? 1 : 12, fresh, responding_ids: [2],
        motor_states: [{ id: 2, torque_enable: 0, present_position: 1040, hw_error: 0, valid: true }] },
    } }));
    await page.evaluate(() => loadWorkspaceStatus());
    assert.match(await page.locator('#jointMap').innerText(), /읽기 전용 관측 #7/);
    fresh = false;
    await page.evaluate(() => loadWorkspaceStatus());
    assert.match(await page.locator('#jointMap').innerText(), /관측 중단.*현재 상태 아님/);
    assert.match(await page.locator('#jointMap').innerText(), /1040 ticks/);
  } finally {
    await context.close();
  }
});

test('좁은 화면에서 작업 도구와 부품 목록이 겹치지 않는다', async () => {
  const { context, page } = await freshPage();
  try {
    await page.setViewportSize({ width:390, height:844 });
    const layout = await page.evaluate(() => {
      const toolbar=document.querySelector('.stage-panel .panel-head').getBoundingClientRect();
      const parts=document.querySelector('aside.panel').getBoundingClientRect();
      return { toolbarBottom:toolbar.bottom,partsTop:parts.top,toolbarHeight:toolbar.height };
    });
    assert.ok(layout.toolbarBottom <= layout.partsTop, JSON.stringify(layout));
    assert.ok(layout.toolbarHeight <= 60, JSON.stringify(layout));
    await page.locator('[data-workspace-mode=motion]').click();
    await page.locator('.part-row[data-key=motor] .part-name').click();
    assert.equal(await page.locator('.joint-preview-note').isVisible(), true);
  } finally {
    await context.close();
  }
});

test('OpenCR TTL 포트 둘에 모터를 각각 연결하면 케이블이 자동 추가된다', async () => {
  const { context, page } = await freshPage();
  try {
    await page.locator('.part-row[data-key=motor] [data-action=add]').click();
    await page.locator('[data-workspace-mode=wiring]').click();
    assert.equal(await page.locator('#cameraView').inputValue(), 'sockets');
    await page.locator('.part-row[data-key=motor] [data-action=instance]').first().click();
    await page.locator('.interface-region[data-key=motor]').first().click();
    await page.locator('.interface-region[data-key=opencr]').first().click();
    await page.locator('.part-row[data-key=motor] [data-action=instance]').nth(1).click();
    await page.locator('.interface-region[data-key=motor]').first().click();
    await page.locator('.interface-region[data-key=opencr]').first().click();
    assert.equal(await page.locator('.part-row[data-key=connector] .part-count').innerText(), '2');
    assert.match(await page.locator('#connectionChecks').innerText(), /화면 배선 · 2개 연결/);
    await page.locator('.cable-measurements').evaluate(node => { node.open = true; });
    assert.match(await page.locator('#cableMeasurements').innerText(), /케이블 #1.*직선거리 약 [\d.]+ mm/);
    assert.match(await page.locator('#cableMeasurements').innerText(), /케이블 #2.*직선거리 약 [\d.]+ mm/);
  } finally {
    await context.close();
  }
});

test('OpenCR→모터→모터 데이지체인에 케이블 둘을 연결한다', async () => {
  const { context, page } = await freshPage();
  try {
    await page.locator('.part-row[data-key=motor] [data-action=add]').click();
    await page.locator('[data-workspace-mode=wiring]').click();
    await page.locator('.part-row[data-key=motor] [data-action=instance]').first().click();
    await page.locator('.interface-region[data-key=motor]').first().click();
    await page.locator('.interface-region[data-key=opencr]').first().click();
    await page.locator('.part-row[data-key=motor] [data-action=instance]').first().click();
    await page.locator('.interface-region[data-key=motor]:not(.occupied)').click();
    await page.locator('.interface-region[data-key=motor][data-id=motor-2]').first().click();
    assert.equal(await page.locator('.part-row[data-key=connector] .part-count').innerText(), '2');
    assert.match(await page.locator('#connectionChecks').innerText(), /화면 배선 · 2개 연결/);
  } finally {
    await context.close();
  }
});

test('로컬 자동 저장과 JSON 내보내기·불러오기가 작업을 보존한다', async () => {
  const { context, page } = await freshPage();
  try {
    await page.locator('.part-row[data-key=motor] [data-action=add]').click();
    assert.equal(await page.locator('.part-row[data-key=motor] .part-count').innerText(), '2');
    await page.locator('[data-workspace-mode=status]').click();
    await page.locator('#projectStatus').getByText(/자동 저장됨/).waitFor();

    await page.reload();
    await page.locator('#statusDot.live').waitFor();
    assert.equal(await page.locator('.part-row[data-key=motor] .part-count').innerText(), '2');

    await page.locator('[data-workspace-mode=status]').click();
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#exportProjectBtn').click();
    const download = await downloadPromise;
    const exported = await readFile(await download.path());

    await page.locator('[data-workspace-mode=assembly]').click();
    await page.locator('.part-row[data-key=motor] [data-action=remove]').click();
    assert.equal(await page.locator('.part-row[data-key=motor] .part-count').innerText(), '1');
    await page.locator('[data-workspace-mode=status]').click();
    await page.locator('#projectFile').setInputFiles({ name: 'saved-assembly.json', mimeType: 'application/json', buffer: exported });
    await page.locator('#projectStatus').getByText(/자동 저장됨/).waitFor();
    assert.equal(await page.locator('.part-row[data-key=motor] .part-count').innerText(), '2');

    await page.reload();
    await page.locator('#statusDot.live').waitFor();
    assert.equal(await page.locator('.part-row[data-key=motor] .part-count').innerText(), '2');
  } finally {
    await context.close();
  }
});

test('조립 도구에서 체결 윤곽과 이동·회전 핸들이 겹치지 않는다', async () => {
  const { context, page } = await freshPage();
  try {
    await page.locator('.interface-region[data-key=motor]').first().waitFor();
    assert.equal(await page.locator('[data-assembly-tool=connect]').getAttribute('aria-pressed'), 'true');
    assert.equal(await page.locator('#gizmoOverlay .gizmo-axis, #gizmoOverlay .gizmo-rotate').count(), 0);
    assert.ok(await page.locator('.interface-region[data-key=motor]').count() > 0);
    assert.equal(await page.locator('.interface-region[data-key=motor][data-anchor="6"], .interface-region[data-key=motor][data-anchor="7"], .interface-region[data-key=motor][data-anchor="8"], .interface-region[data-key=motor][data-anchor="9"]').count(), 0);

    await page.locator('[data-assembly-tool=place]').click();
    assert.equal(await page.locator('#portOverlay .interface-region').count(), 0);
    assert.ok(await page.locator('#gizmoOverlay .gizmo-axis, #gizmoOverlay .gizmo-rotate').count() > 0);

    await page.locator('[data-assembly-tool=connect]').click();
    assert.equal(await page.locator('#gizmoOverlay .gizmo-axis, #gizmoOverlay .gizmo-rotate').count(), 0);
    assert.ok(await page.locator('.interface-region[data-key=motor]').count() > 0);

    await page.locator('.part-row[data-key=bracket] .part-name').click();
    await page.locator('.interface-region[data-key=bracket][data-anchor="1"]').click();
    const motorAnchors = await page.locator('.interface-region[data-key=motor]').evaluateAll(nodes => nodes.map(node => Number(node.dataset.anchor)));
    assert.ok(motorAnchors.length > 0);
    assert.ok(motorAnchors.every(anchor => anchor >= 6 && anchor <= 9));
  } finally {
    await context.close();
  }
});

test('책상 윗면 Y=0 좌표와 이전 브라우저 배치를 함께 보존한다', async () => {
  const { context, page } = await freshPage();
  try {
    assert.equal(await page.locator('#partY').inputValue(), '1');
    assert.equal(await page.evaluate(()=>NotifyiSceneManipulation.worldYRange(state.desk[0].mesh.verts,identity()).max),0);
    const initial=await page.evaluate(()=>Object.values(state.parts).flat().map(part=>({id:part.id,y:part.pos[1],bottom:groupBottom(placementGroup(part))})));
    assert.ok(initial.every(part=>Math.abs(part.bottom)<1e-8));
    await page.locator('.part-row[data-key=opencr] .part-name').click();
    const opencrY=await page.locator('#partY').inputValue();
    assert.ok(Number(opencrY)>.4);
    await page.waitForFunction(() => localStorage.getItem('notifyi.digitalTwin.project.v2') !== null);
    await page.evaluate(() => {
      const current = JSON.parse(localStorage.getItem('notifyi.digitalTwin.project.v2'));
      current.version = 1;
      for (const parts of Object.values(current.parts)) {
        for (const part of parts) part.pos[1] -= 1.58;
      }
      localStorage.setItem('notifyi.digitalTwin.project.v1', JSON.stringify(current));
      localStorage.removeItem('notifyi.digitalTwin.project.v2');
    });
    await page.reload();
    await page.locator('#statusDot.live').waitFor();
    assert.equal(await page.locator('#partY').inputValue(), '1');
    await page.locator('.part-row[data-key=opencr] .part-name').click();
    assert.ok(Math.abs(Number(await page.locator('#partY').inputValue())-Number(opencrY))<1e-10);
    assert.ok(await page.evaluate(() => localStorage.getItem('notifyi.digitalTwin.project.v1') !== null));
  } finally {
    await context.close();
  }
});

test('본체 배치 각도는 빠른 선택과 직접 입력을 사용하고 모터 관절 각도와 분리된다', async () => {
  const { context, page } = await freshPage();
  try {
    await page.locator('.part-row[data-key=motor] .part-name').click();
    const x = page.locator('.placement-angle-row[data-placement-axis="X"]');
    const y = page.locator('.placement-angle-row[data-placement-axis="Y"]');
    const z = page.locator('.placement-angle-row[data-placement-axis="Z"]');
    await x.locator('[data-placement-angle="90"]').click();
    await y.locator('[data-placement-angle="-90"]').click();
    assert.equal(await x.locator('[data-placement-angle="90"]').getAttribute('aria-pressed'), 'true');
    assert.equal(await y.locator('[data-placement-angle="-90"]').getAttribute('aria-pressed'), 'true');
    assert.equal(await z.locator('[data-placement-angle="0"]').getAttribute('aria-pressed'), 'true');
    await z.locator('[data-placement-custom]').click();
    await z.locator('.placement-custom input').fill('37.5');
    await z.locator('.placement-custom input').press('Tab');
    assert.equal(await z.locator('[data-placement-custom]').getAttribute('aria-pressed'), 'true');
    assert.deepEqual(await page.evaluate(() => ({ rot:state.parts.motor[0].rot, joints:state.parts.motor[0].joints })),
      { rot:[90,-90,37.5], joints:{ A:0, B:0 } });
    await page.reload();
    await page.locator('#statusDot.live').waitFor();
    await page.locator('.part-row[data-key=motor] .part-name').click();
    assert.equal(await z.locator('.placement-custom input').inputValue(), '37.5');
    await page.locator('[data-workspace-mode=motion]').click();
    assert.equal(await page.locator('#placementRotation').isVisible(), false);
    assert.deepEqual(await page.evaluate(() => state.parts.motor[0].joints), { A:0, B:0 });
  } finally {
    await context.close();
  }
});

test('기존 저장본의 묻힌 조립체는 전체 높이 맞춤으로 복구하고 실행 취소할 수 있다',async()=>{
  const {context,page}=await freshPage();
  try{
    await page.locator('#exampleAssemblyBtn').click();
    const before=await page.evaluate(()=>{
      state.parts.motor[0].pos[1]-=2;draw();
      return {poses:state.parts.motor.map(part=>[...part.pos]),mates:JSON.stringify(state.parts.bracket[0].mates),bottom:groupBottom(placementGroup(state.parts.motor[0]))};
    });
    assert.ok(before.bottom< -1);
    await page.waitForFunction(()=>JSON.parse(localStorage.getItem(PROJECT_STORAGE_KEY))?.parts.motor[0]?.pos[1]===state.parts.motor[0].pos[1]);
    await page.reload();await page.locator('#statusDot.live').waitFor();
    assert.ok(await page.evaluate(()=>groupBottom(placementGroup(state.parts.motor[0])))< -1,'restore must not silently rewrite saved poses');
    await page.locator('[data-assembly-tool=place]').click();
    await page.locator('#groundAllBtn').click();
    const after=await page.evaluate(()=>({poses:state.parts.motor.map(part=>[...part.pos]),mates:JSON.stringify(state.parts.bracket[0].mates),bottom:groupBottom(placementGroup(state.parts.motor[0]))}));
    assert.equal(after.mates,before.mates);
    assert.ok(Math.abs(after.bottom)<1e-8);
    for(let axis=0;axis<3;axis++)assert.ok(Math.abs((after.poses[1][axis]-after.poses[0][axis])-(before.poses[1][axis]-before.poses[0][axis]))<1e-8);
    await page.locator('#undoBtn').click();
    assert.ok(Math.abs(await page.evaluate(()=>groupBottom(placementGroup(state.parts.motor[0])))-before.bottom)<1e-8);
  }finally{await context.close();}
});

test('부품 몸체를 책상 평면에서 드래그하고 Esc 취소·실행 취소·저장을 지원한다',async()=>{
  const {context,page}=await freshPage();
  try{
    await page.locator('[data-assembly-tool=place]').click();
    await page.locator('#focusPartBtn').click();
    const start=await page.evaluate(()=>{
      const part=state.parts.motor[0],rect=canvas.getBoundingClientRect();
      for(const local of [[-12,-15,19],[12,-15,19],[-19,-15,0],[0,-15,19],[0,-15,-19],[19,-15,0]]){
        const [x,y]=projectPoint(partModel(part),local);
        if(pickPart(x,y)?.id!==part.id)continue;
        if(document.elementFromPoint(rect.left+x,rect.top+y)!==canvas)continue;
        return {x:rect.left+x,y:rect.top+y,pos:[...part.pos],yaw:state.yaw,pitch:state.pitch};
      }
      throw new Error('No visible body pick area');
    });
    await page.mouse.move(start.x,start.y);await page.mouse.down();
    await page.mouse.move(start.x+65,start.y+20,{steps:5});
    const moved=await page.evaluate(()=>({pos:[...state.parts.motor[0].pos],yaw:state.yaw,pitch:state.pitch}));
    assert.notDeepEqual(moved.pos,start.pos);assert.equal(moved.pos[1],start.pos[1]);
    assert.equal(moved.yaw,start.yaw);assert.equal(moved.pitch,start.pitch);
    await page.mouse.move(start.x,start.y,{steps:5});
    const returned=await page.evaluate(()=>state.parts.motor[0].pos);
    returned.forEach((value,i)=>assert.ok(Math.abs(value-start.pos[i])<1e-8,'returning the cursor to its start must restore exact displacement'));
    await page.mouse.move(start.x+65,start.y+20,{steps:5});
    await page.keyboard.press('Escape');await page.mouse.up();
    assert.deepEqual(await page.evaluate(()=>state.parts.motor[0].pos),start.pos);
    await page.mouse.move(start.x,start.y);await page.mouse.down();
    await page.mouse.move(start.x+65,start.y+20,{steps:5});await page.mouse.up();
    await page.waitForFunction(()=>JSON.parse(localStorage.getItem(PROJECT_STORAGE_KEY))?.parts.motor[0]?.pos[0]!==0);
    await page.locator('#undoBtn').click();
    assert.deepEqual(await page.evaluate(()=>state.parts.motor[0].pos),start.pos);
    await page.locator('#redoBtn').click();
    assert.notDeepEqual(await page.evaluate(()=>state.parts.motor[0].pos),start.pos);
  }finally{await context.close();}
});

test('사각 평면 핸들과 회전 링은 실제 3D 평면·축을 기준으로 조작한다',async()=>{
  const {context,page}=await freshPage();
  try{
    await page.locator('[data-assembly-tool=place]').click();await page.locator('#focusPartBtn').click();
    const plane=page.locator('.gizmo-plane[data-gizmo-plane="1"]');
    assert.ok(await plane.isVisible());
    const box=await plane.boundingBox(),before=await page.evaluate(()=>({pos:[...state.parts.motor[0].pos],joints:{...state.parts.motor[0].joints}}));
    await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();
    await page.mouse.move(box.x+box.width/2+45,box.y+box.height/2+15,{steps:4});await page.mouse.up();
    const after=await page.evaluate(()=>state.parts.motor[0].pos);
    assert.notEqual(after[0],before.pos[0]);assert.notEqual(after[2],before.pos[2]);assert.equal(after[1],before.pos[1]);
    await page.locator('#directRotateBtn').click();
    const points=await page.evaluate(()=>{
      const part=state.parts.motor[0],radius=gizmoRadius()*(.85+1*.16),rect=canvas.getBoundingClientRect();
      return [Math.PI*.25,Math.PI*.45].map(angle=>{
        const p=projectWorldPoint([part.pos[0]+radius*Math.sin(angle),part.pos[1],part.pos[2]+radius*Math.cos(angle)]);
        return {x:p[0]+rect.left,y:p[1]+rect.top};
      });
    });
    // Target the actual ring hit region; body movement is disabled in rotation mode.
    await page.mouse.move(points[0].x,points[0].y);await page.mouse.down();
    assert.equal(await page.evaluate(()=>state.drag?.kind),'gizmo');
    assert.equal(await page.evaluate(()=>state.drag?.axis),1);
    await page.mouse.move(points[1].x,points[1].y,{steps:8});await page.mouse.up();
    const rotation=await page.evaluate(()=>({rot:state.parts.motor[0].rot,joints:state.parts.motor[0].joints,bottom:groupBottom(placementGroup(state.parts.motor[0]))}));
    assert.ok(Math.abs(rotation.rot[1]-36)<1,'right-hand Y ring should rotate 36 degrees');
    assert.deepEqual(rotation.joints,before.joints);assert.ok(Math.abs(rotation.bottom)<1e-8);
    if(process.env.PLACEMENT_SCREENSHOT)await page.screenshot({path:process.env.PLACEMENT_SCREENSHOT});
  }finally{await context.close();}
});

test('좁은 화면에서도 배치 도구가 부품 목록을 가리지 않고 평면 핸들의 키보드 포커스가 유지된다',async()=>{
  const {context,page}=await freshPage();
  try{
    await page.locator('[data-assembly-tool=place]').click();
    const center=await page.locator('.gizmo-center').boundingBox();
    await page.mouse.move(center.x+center.width/2,center.y+center.height/2);await page.mouse.down();
    await page.mouse.move(center.x+center.width/2+30,center.y+center.height/2+10,{steps:3});await page.mouse.up();
    assert.match(await page.locator('#transformReadout').innerText(),/Esc/);
    for(const width of [390,768,980]){
      await page.setViewportSize({width,height:844});
      const toolbar=await page.locator('#placementToolbar').boundingBox(),list=await page.locator('aside.panel').boundingBox();
      assert.ok(toolbar.y+toolbar.height<=list.y,`${width}px placement toolbar and parts list must not overlap`);
      assert.ok(toolbar.x>=0&&toolbar.x+toolbar.width<=width);
      assert.equal(await page.locator('#directMoveBtn').evaluate(button=>{const rect=button.getBoundingClientRect();return document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2)===button;}),true,'button center must not be covered by another panel');
    }
    await page.setViewportSize({width:1440,height:900});await page.locator('#focusPartBtn').click();
    const handle=page.getByRole('button',{name:'책상과 나란히 XZ 이동',exact:true});
    await handle.focus();const x=await page.evaluate(()=>state.parts.motor[0].pos[0]);
    await page.keyboard.press('ArrowRight');await page.keyboard.press('ArrowRight');
    assert.ok(Math.abs(await page.evaluate(()=>state.parts.motor[0].pos[0])-x-.2)<1e-8);
    assert.equal(await handle.evaluate(element=>element===document.activeElement),true);
  }finally{await context.close();}
});

test('기울어진 부품에서도 회전 링 방향키는 같은 월드 축을 사용한다',async()=>{
  const {context,page}=await freshPage();
  try{
    await page.locator('[data-assembly-tool=place]').click();await page.locator('#focusPartBtn').click();
    await page.evaluate(()=>{setPlacementAngle(state.parts.motor[0],2,90);draw();});
    await page.locator('#directRotateBtn').click();
    const before=await page.evaluate(()=>eulerRotation(state.parts.motor[0].rot));
    await page.getByRole('button',{name:'X축으로 회전',exact:true}).focus();await page.keyboard.press('ArrowRight');
    const result=await page.evaluate(before=>({actual:eulerRotation(state.parts.motor[0].rot),expected:mul(rx(5*Math.PI/180),before),bottom:groupBottom(placementGroup(state.parts.motor[0]))}),before);
    result.actual.forEach((value,i)=>assert.ok(Math.abs(value-result.expected[i])<1e-8));
    assert.ok(Math.abs(result.bottom)<1e-8);
    assert.equal(await page.locator('#gizmoOverlay').evaluate(element=>getComputedStyle(element).touchAction),'none');
  }finally{await context.close();}
});
