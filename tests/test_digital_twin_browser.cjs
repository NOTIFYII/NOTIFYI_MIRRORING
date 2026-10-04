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
    await page.mouse.move(600, 490);
    await page.mouse.down();
    await page.mouse.move(720, 490, { steps: 8 });
    await page.mouse.up();
    assert.match(await page.locator('#connectedPoseHint').innerText(), /현재 60°/);
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
