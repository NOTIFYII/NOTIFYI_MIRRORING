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
    assert.equal(await page.locator('#partY').inputValue(), '0.58');
    await page.locator('.part-row[data-key=opencr] .part-name').click();
    assert.equal(await page.locator('#partY').inputValue(), '0.03');
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
    assert.equal(await page.locator('#partY').inputValue(), '0.58');
    await page.locator('.part-row[data-key=opencr] .part-name').click();
    assert.equal(await page.locator('#partY').inputValue(), '0.03');
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
