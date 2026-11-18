/* 도트 검사 (js/sprites.js).

   무엇을 못 박나
     1. 방향 0~7 은 서버 순서(아래부터 시계 반대로 돈다 - 도트 rowmap 과 같다).
     2. 4방향 시트(followers · GBA 풍)는 대각선을 옆 방향으로, 줄이 모자란 시트(잠자기 1줄)는 0줄로.
     3. 프레임 시간은 1/60초 틱이다.
     4. 이로치 색: tint 는 이로치만, 's090' 은 이로치 도트를 · 'n090' 은 기본 도트를 돌린다.
        색조 돌리기는 PIL 의 HSV 8비트 셈과 한 값도 다르지 않다 (client sprite_tint 와 같은 색).
     5. 걷는 도트가 없는 종(ok:false · 받기 실패 · retry)은 배틀 도트 첫 장으로. 이로치 시트가 없으면 기본 시트를
        색 돌리지 않고. 걷기밖에 없는 출처는 다른 동작을 묻지 않는다. 멈추지 않는다.
     6. 동작마다 칸 크기가 달라도 칸 한가운데를 같은 자리에 둔다 (몸이 튀지 않는다). */
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  dirOf, rowFor, frameAt, skinOf, tintPixels, cellBox, lookGeometry, placeCell,
  animUrl, spriteUrl, resolveLook, animFor,
} from '../js/sprites.js';

const PMD = { down: 0, downright: 1, right: 2, upright: 3, up: 4, upleft: 5, left: 6, downleft: 7 };
const FOLLOW = { down: 0, left: 1, right: 2, up: 3 };

test('방향 - 서버 순서 0 아래 · 2 오른쪽 · 4 위 · 6 왼쪽', () => {
  const want = [[0, 1, 0], [1, 1, 1], [1, 0, 2], [1, -1, 3], [0, -1, 4], [-1, -1, 5], [-1, 0, 6], [-1, 1, 7]];
  for (const [x, y, d] of want) assert.equal(dirOf(x, y), d, x + ',' + y);
  assert.equal(dirOf(0, 0), -1);
  assert.equal(dirOf(-1, 1e-9), 6);           // 정왼쪽 근처 (atan2 가 180 을 줄 수 있다)
  assert.equal(dirOf(-1, -1e-9), 6);
});

test('시트 줄 - 8방향 PMD 그대로', () => {
  const m = { rows: 8, rowmap: PMD };
  for (let d = 0; d < 8; d += 1) assert.equal(rowFor(m, d), d);
});

test('시트 줄 - 4방향 시트는 대각선을 옆으로', () => {
  const m = { rows: 4, rowmap: FOLLOW };
  assert.deepEqual([0, 1, 2, 3, 4, 5, 6, 7].map((d) => rowFor(m, d)), [0, 2, 2, 2, 3, 1, 1, 1]);
});

test('시트 줄 - 줄이 모자라면 (잠자기 1줄 · 짧은 시트) 0줄', () => {
  assert.deepEqual([0, 3, 6].map((d) => rowFor({ rows: 1, rowmap: PMD }, d)), [0, 0, 0]);
  assert.equal(rowFor({ rows: 4, rowmap: PMD }, 6), 0);
  assert.equal(rowFor({ rows: 4, rowmap: PMD }, 3), 3);
  assert.equal(rowFor({ rows: 8 }, 5), 5);    // rowmap 이 없으면 서버 순서
  assert.equal(rowFor({ rows: 8, rowmap: PMD }, -1), 0);
});

test('프레임 - 1/60초 틱, 돌거나 끝에서 멈춘다', () => {
  const durs = [6, 6, 12];                    // 0.1 · 0.1 · 0.2 초
  assert.equal(frameAt(durs, 0), 0);
  assert.equal(frameAt(durs, 0.15), 1);
  assert.equal(frameAt(durs, 0.25), 2);
  assert.equal(frameAt(durs, 0.45), 0);       // 0.4초에 한 바퀴
  assert.equal(frameAt(durs, 5, false), 2);
  assert.equal(frameAt([], 1), 0);
});

test('skin - tint 는 이로치만', () => {
  assert.deepEqual(skinOf({ shiny: false }), { shiny: false, hue: 0 });
  assert.deepEqual(skinOf({ shiny: true }), { shiny: true, hue: 0 });
  assert.deepEqual(skinOf({ shiny: true, tint: 's090' }), { shiny: true, hue: 90 });
  assert.deepEqual(skinOf({ shiny: true, tint: 'n135' }), { shiny: false, hue: 135 });
  assert.deepEqual(skinOf({ shiny: true, tint: 'normal' }), { shiny: false, hue: 0 });
  assert.deepEqual(skinOf({ shiny: true, tint: 's091' }), { shiny: true, hue: 0 });
  assert.deepEqual(skinOf({ shiny: false, tint: 's090' }), { shiny: false, hue: 0 });
  assert.deepEqual(skinOf(null), { shiny: false, hue: 0 });
});

// PIL 로 구한 값 (client/poketdesktop/sprite_tint.shift - Pillow 12)
const TINT_IN = [[255, 0, 0, 255], [12, 200, 80, 255], [240, 236, 231, 255], [0, 0, 0, 255], [37, 99, 201, 128],
  [255, 128, 0, 255], [90, 60, 200, 255], [1, 2, 3, 255], [200, 0, 200, 0], [128, 255, 0, 255], [17, 170, 169, 255],
  [250, 248, 61, 255]];
const TINT_OUT = {
  45: [[255, 192, 0, 255], [13, 180, 200, 255], [238, 240, 232, 255], [0, 0, 0, 255], [95, 37, 201, 128], [192, 255, 0, 255],
    [195, 60, 200, 255], [1, 1, 3, 255], [200, 0, 52, 0], [0, 255, 60, 255], [17, 57, 170, 255], [110, 250, 62, 255]],
  90: [[126, 255, 0, 255], [13, 39, 200, 255], [232, 240, 232, 255], [0, 0, 0, 255], [201, 37, 184, 128], [0, 255, 0, 255],
    [200, 60, 100, 255], [3, 1, 3, 255], [200, 94, 0, 0], [0, 255, 252, 255], [93, 17, 170, 255], [62, 250, 155, 255]],
  180: [[0, 252, 255, 255], [200, 13, 132, 255], [232, 235, 240, 255], [0, 0, 0, 255], [201, 133, 37, 128], [0, 126, 255, 255],
    [172, 200, 60, 255], [3, 2, 1, 255], [5, 200, 0, 0], [126, 0, 255, 255], [170, 17, 17, 255], [62, 62, 250, 255]],
  315: [[255, 0, 186, 255], [88, 200, 13, 255], [240, 232, 233, 255], [0, 0, 0, 255], [37, 201, 176, 128], [255, 0, 60, 255],
    [60, 136, 200, 255], [1, 3, 2, 255], [47, 0, 200, 0], [255, 186, 0, 255], [17, 170, 53, 255], [250, 106, 62, 255]],
};

test('색조 돌리기 - PIL HSV 8비트 셈과 같다', () => {
  for (const hue of Object.keys(TINT_OUT)) {
    const data = new Uint8ClampedArray(TINT_IN.flat());
    tintPixels(data, Number(hue));
    const got = [];
    for (let i = 0; i < data.length; i += 4) got.push([...data.slice(i, i + 4)]);
    assert.deepEqual(got, TINT_OUT[hue], 'hue ' + hue);
  }
  const same = new Uint8ClampedArray(TINT_IN.flat());
  tintPixels(same, 0);
  assert.deepEqual([...same], TINT_IN.flat());
});

test('칸 안 그림 상자 - 모든 칸을 합친 것, 칸 기준', () => {
  // 시트 8x8 = 4x4 칸 2x2. (0,0) 칸의 (1,1) 과 (1,1) 칸의 (2,3) 만 칠했다.
  const w = 8;
  const data = new Uint8ClampedArray(8 * 8 * 4);
  const put = (x, y) => { data[(y * w + x) * 4 + 3] = 255; };
  put(1, 1);
  put(4 + 2, 4 + 3);
  assert.deepEqual(cellBox(data, w, 8, 4, 4), { l: 1, t: 1, r: 3, b: 4 });
  assert.equal(cellBox(new Uint8ClampedArray(8 * 8 * 4), w, 8, 4, 4), null);
});

test('자리 - 동작마다 칸 크기가 달라도 칸 한가운데는 같은 자리', () => {
  const geo = lookGeometry({ l: 10, t: 8, r: 30, b: 36 }, 40, 40);
  assert.equal(geo.cx, 0);
  assert.equal(geo.cy, 2);
  assert.ok(geo.scale > 1 && Math.abs(geo.h * geo.scale - 72) < 1e-9);
  const walk = placeCell(geo, 40, 40, 500, 300);
  const idle = placeCell(geo, 64, 56, 500, 300);
  const mid = (r) => [r.x + r.w / 2, r.y + r.h / 2];
  assert.deepEqual(mid(walk), mid(idle));
  // 몸 가운데(그림 상자의 가운데)가 (500, 300) 에 온다
  assert.ok(Math.abs(walk.x + (10 + 30) / 2 * geo.scale - 500) < 1e-9);
  assert.ok(Math.abs(walk.y + (8 + 36) / 2 * geo.scale - 300) < 1e-9);
});

test('자리 - 아주 작거나 큰 그림도 배율은 정해진 범위', () => {
  assert.ok(lookGeometry({ l: 0, t: 0, r: 4, b: 4 }, 8, 8).scale <= 4);
  assert.ok(lookGeometry({ l: 0, t: 0, r: 200, b: 200 }, 200, 200).scale >= 0.3);
});

test('주소 - 이로치는 서버의 shiny 쿼리', () => {
  assert.equal(animUrl(25, 'Walk', false), '/api/anim/25/Walk.json');
  assert.equal(animUrl(25, 'Hurt', true), '/api/anim/25/Hurt.json?shiny=true');
  assert.equal(animUrl(25, 'Walk', true, 'png'), '/api/anim/25/Walk.png?shiny=true');
  assert.equal(spriteUrl(6, true), '/api/sprite/6?shiny=true');
  assert.equal(spriteUrl(6, false), '/api/sprite/6');
});

const meta = (extra = {}) => ({ ok: true, frameW: 32, frameH: 40, durations: [8, 8], frames: 2, rows: 8, rowmap: PMD, src: 'pmd', ...extra });

function fakeServer(table) {
  const asked = [];
  const getJson = async (url) => {
    asked.push(url);
    const v = table[url];
    if (v instanceof Error) throw v;
    return v === undefined ? { ok: false } : v;
  };
  return { asked, getJson };
}

test('도트 고르기 - 보통: 걷기 + 있는 동작만', async () => {
  const s = fakeServer({
    '/api/anim/25/Walk.json': meta(),
    '/api/anim/25/Idle.json': meta({ frameW: 48 }),
    '/api/anim/25/Hurt.json': { ok: false },
    '/api/anim/25/Faint.json': meta(),
    '/api/anim/25/Sleep.json': new Error('끊김'),
  });
  const look = await resolveLook(25, { shiny: false, hue: 0 }, s.getJson);
  assert.equal(look.walk.png, '/api/anim/25/Walk.png');
  assert.equal(look.walk.meta.frameW, 32);
  assert.deepEqual(Object.keys(look.anims).sort(), ['Faint', 'Idle']);
  assert.equal(look.anims.Idle.png, '/api/anim/25/Idle.png');
  assert.equal(look.hue, 0);
  assert.equal(look.still, '/api/sprite/25');
});

test('도트 고르기 - 걷는 도트가 없는 종 (ok:false · retry · 받기 실패 · 깨진 메타)은 배틀 도트', async () => {
  for (const bad of [{ ok: false }, { ok: false, retry: true }, new Error('x'), { ok: true, frameW: 0, frameH: 40, durations: [8] },
    { ok: true, frameW: 32, frameH: 40, durations: [] }, null]) {
    const s = fakeServer({ '/api/anim/1000/Walk.json': bad });
    const look = await resolveLook(1000, { shiny: false, hue: 0 }, s.getJson);
    assert.equal(look.walk, null);
    assert.deepEqual(look.anims, {});
    assert.equal(look.still, '/api/sprite/1000');
    assert.deepEqual(s.asked, ['/api/anim/1000/Walk.json'], '다른 동작은 묻지 않는다');
  }
});

test('도트 고르기 - 이로치 시트', async () => {
  const s = fakeServer({
    '/api/anim/6/Walk.json?shiny=true': meta({ shiny: true }),
    '/api/anim/6/Idle.json?shiny=true': meta({ shiny: true }),
    '/api/anim/6/Idle.json': meta(),
  });
  const look = await resolveLook(6, { shiny: true, hue: 90 }, s.getJson);
  assert.equal(look.walk.png, '/api/anim/6/Walk.png?shiny=true');
  assert.equal(look.anims.Idle.png, '/api/anim/6/Idle.png?shiny=true');
  assert.equal(look.hue, 90);
  assert.equal(look.still, '/api/sprite/6?shiny=true');
});

test('도트 고르기 - 이로치 시트가 없으면 (옛 서버의 shiny 표시 없는 것도) 기본 시트를 색 돌리지 않고', async () => {
  for (const shinyMeta of [{ ok: false }, meta()]) {
    const s = fakeServer({
      '/api/anim/6/Walk.json?shiny=true': shinyMeta,
      '/api/anim/6/Walk.json': meta(),
      '/api/anim/6/Idle.json': meta(),
    });
    const look = await resolveLook(6, { shiny: true, hue: 90 }, s.getJson);
    assert.equal(look.walk.png, '/api/anim/6/Walk.png');
    assert.equal(look.anims.Idle.png, '/api/anim/6/Idle.png');
    assert.equal(look.hue, 0);
  }
});

test('도트 고르기 - 이로치 걷기의 다른 동작에 이로치가 없으면 그 동작은 쓰지 않는다 (색이 섞인다)', async () => {
  const s = fakeServer({
    '/api/anim/6/Walk.json?shiny=true': meta({ shiny: true }),
    '/api/anim/6/Idle.json?shiny=true': { ok: false },
    '/api/anim/6/Idle.json': meta(),
  });
  const look = await resolveLook(6, { shiny: true, hue: 0 }, s.getJson);
  assert.equal(look.anims.Idle, undefined);
});

test('도트 고르기 - 걷기밖에 없는 출처(follow · ow)는 다른 동작을 묻지 않는다', async () => {
  for (const src of ['follow', 'ow']) {
    const s = fakeServer({ '/api/anim/1001/Walk.json': meta({ src, rows: 4, rowmap: FOLLOW }) });
    const look = await resolveLook(1001, { shiny: false, hue: 0 }, s.getJson);
    assert.ok(look.walk);
    assert.deepEqual(s.asked, ['/api/anim/1001/Walk.json']);
  }
});

test('동작 고르기 - 없는 동작은 있는 것으로 대신', () => {
  const all = new Set(['Walk', 'Idle', 'Hurt', 'Faint', 'Sleep']);
  const walkOnly = new Set(['Walk']);
  assert.equal(animFor(all, 'walk', true, false), 'Walk');
  assert.equal(animFor(all, 'idle', false, false), 'Idle');
  assert.equal(animFor(walkOnly, 'idle', false, false), 'Walk');
  assert.equal(animFor(all, 'idle', false, true), 'Hurt');
  assert.equal(animFor(walkOnly, 'idle', false, true), 'Walk');
  assert.equal(animFor(all, 'sleep', false, false), 'Sleep');
  assert.equal(animFor(new Set(['Walk', 'Idle']), 'sleep', false, false), 'Idle');
  assert.equal(animFor(all, 'ko', false, false), 'Faint');
  assert.equal(animFor(walkOnly, 'ko', false, false), 'Walk');
  assert.equal(animFor(all, 'stun', false, false), 'Hurt');
});
