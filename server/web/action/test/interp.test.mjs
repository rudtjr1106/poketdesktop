/* 이어 그리기 · 내 이동 먼저 그리기 검사 (js/interp.js).

   무엇을 못 박나
     1. 시계: 서버 모습이 가장 빨리 온 것을 기준으로 서버 시각을 어림하고, 80ms 뒤를 그린다. 서버가 밀린 시간을
        버려(CATCHUP) 모습이 줄곧 늦게 오면 옛 기준을 곧 버린다 - 그리는 시각이 가장 새 모습을 앞질러 3초 동안
        굶지 않게. 80ms 안의 흔들림은 기준을 안 바꾼다.
     2. 스냅샷 사이는 곧게 이어 그린다. 교체로 다른 포켓몬이 나오면 잇지 않는다.
     3. 탄은 같은 id 끼리 잇고, 다음 모습에 없으면 속도대로 조금만 더 간다.
     4. 이벤트는 그 모습을 그리는 때가 되어야 나온다 (한 번만).
     5. 내 이동: 누른 순간부터 F.spd 로 먼저 움직이고, ack 를 받으면 서버 자리에서 아직 안 받은 입력을
        다시 굴린다. 서버와 같은 길이면 튀지 않는다. 벽에 막힌다. 혼란이면 반대로 간다.
     6. 내 쪽 이벤트 (쓰기 · 피하기 · 교체 · 내 상태 · 랭크) 는 받자마자 나온다 - 내 몸은 가장 새 모습으로 그리니까.
        상대 것 · 맞음 · 쓰러짐은 80ms 뒤 그대로. 상대 기술에 맞아 걸린 상태는 그 hit 와 같이 (먼저 걸리지 않게). */
import test from 'node:test';
import assert from 'node:assert/strict';
import { Clock, SnapBuffer, Predictor, clampArena, ownEvent } from '../js/interp.js';

const near = (a, b, eps = 1e-6) => Math.abs(a - b) <= eps;
const F = (x, y, extra = {}) => ({ i: 0, x, y, d: 0, st: 'idle', sm: -1, sp: 0, s: null, c: [], hpr: 1000, ...extra });
const snap = (ts, a, b, extra = {}) => ({ t: 's', n: Math.round(ts * 30), ts, ph: 'fight', pt: 100, ack: 0, f: { a, b }, p: [], z: [], ev: [], ...extra });

test('시계 - 가장 빨리 온 모습 기준, 80ms 뒤를 그린다', () => {
  const c = new Clock();
  // 서버 시각 10.0 이 지역 시각 100.05, 10.033 이 100.1(늦음), 10.066 이 100.116
  c.snap(10.0, 100.05);
  c.snap(10.033, 100.1);
  c.snap(10.066, 100.116);
  assert.ok(near(c.now(100.2), 10.066 - 100.116 + 100.2, 1e-9));
  assert.ok(near(c.render(100.2), c.now(100.2) - 0.08, 1e-9));
});

test('시계 - 크게 어긋나면 바로 맞추고, 조금이면 천천히 따라간다', () => {
  const c = new Clock();
  c.snap(10, 100);
  assert.ok(near(c.now(100), 10));
  c.snap(20, 100.5);                          // 서버가 10초 앞섰다 (다시 시작 같은 것)
  assert.ok(near(c.now(100.5), 20));
  c.snap(20.53, 101);                         // 30ms 빨리 왔다
  assert.ok(c.now(101) < 20.53 + 1e-9);
  for (let i = 0; i < 60; i += 1) c.tick(1 / 60);
  assert.ok(near(c.now(101), 20.53, 0.01));
});

// 30번/초 모습을 지역 시각 t0 부터 sec 초 동안 (ts = 지역 시각 + v). 매 장 tick 도 같이
function feed(c, t0, sec, v, late = () => 0) {
  let t = t0;
  for (let i = 0; i < Math.round(sec * 30); i += 1) {
    t = t0 + i / 30;
    c.tick(1 / 30);
    c.snap(t + v, t + late(i));
  }
  return t;
}

test('시계 - 서버가 밀린 시간을 버리면(모습이 줄곧 늦게 온다) 옛 기준을 곧 버린다', () => {
  const c = new Clock();
  let t = feed(c, 100, 3, 0);                 // 3초 동안 ts = 지역 시각 (v = 0)
  assert.ok(near(c.render(t), t - 0.08, 1e-9));
  // 서버가 0.3초 멈췄다가 판 시각은 0.166초만 갔다 (CATCHUP 넘침) - 그 뒤로 v 는 0.134 낮은 채
  const drop = t + 0.3;
  let latest = null;
  for (let i = 0; i <= 9; i += 1) {           // 떨어진 뒤 0.3초 (30번/초)
    const now = drop + i / 30;
    if (i) c.tick(1 / 30);
    latest = now - 0.134;
    c.snap(latest, now);
  }
  const now = drop + 0.3;
  c.tick(1 / 30);
  assert.ok(c.render(now) <= latest + 1 / 30 + 1e-9,
    '0.3초 안에 그리는 시각이 가장 새 모습(+1틱) 안으로 (그린 ' + c.render(now).toFixed(3) + ', 새 모습 ' + latest.toFixed(3) + ')');
});

test('시계 - 80ms 안의 흔들림 · 가끔 늦는 모습은 기준을 안 바꾼다', () => {
  const c = new Clock();
  const t = feed(c, 100, 3, 0, (i) => (i % 2 ? 0.07 : 0));            // 하나 걸러 70ms 늦게
  assert.ok(near(c.now(t), t, 1e-6), '가장 빨리 온 것 기준');
  const c2 = new Clock();
  const t2 = feed(c2, 100, 3, 0, (i) => (i % 5 === 4 ? 0 : 0.12));    // 다섯에 넷이 120ms 늦어도 하나는 제때
  assert.ok(near(c2.now(t2), t2, 1e-6), '넷까지는 늦어도 기준을 지킨다');
});

test('시계 - 핑 왕복 시간', () => {
  const c = new Clock();
  c.pong(5.0, 5.12);
  assert.ok(near(c.rtt, 0.12));
  c.pong(6.0, 6.02);
  assert.ok(c.rtt < 0.12 && c.rtt > 0.02);
  c.pong(7.0, 6.9);                           // 거꾸로 온 것은 버린다
  assert.ok(c.rtt > 0);
});

test('스냅샷 보간 - 두 모습 사이를 곧게', () => {
  const b = new SnapBuffer();
  b.push(snap(1.0, F(100, 100), F(800, 400)));
  b.push(snap(1.1, F(200, 300, { sp: 1 }), F(800, 400)));
  const v = b.at(1.05);
  assert.ok(near(v.f.a.x, 150) && near(v.f.a.y, 200));
  assert.ok(near(v.f.a.sp, 0.5));
  assert.ok(near(v.f.b.x, 800));
  assert.equal(b.at(0.5).f.a.x, 100);         // 처음보다 앞이면 처음 것
  assert.equal(b.at(9).f.a.x, 200);           // 끝보다 뒤면 끝 것 (몸은 더 안 간다)
});

test('스냅샷 보간 - 교체로 다른 포켓몬이면 잇지 않는다', () => {
  const b = new SnapBuffer();
  b.push(snap(1.0, F(100, 100, { i: 0 }), F(800, 400)));
  b.push(snap(1.1, F(300, 300, { i: 1 }), F(800, 400)));
  assert.equal(b.at(1.04).f.a.x, 100);
  assert.equal(b.at(1.06).f.a.x, 300);
});

test('스냅샷 보간 - 상대가 아직 없으면 (고르기) null 그대로', () => {
  const b = new SnapBuffer();
  b.push(snap(1.0, null, null, { ph: 'pick' }));
  b.push(snap(1.1, null, null, { ph: 'pick' }));
  const v = b.at(1.05);
  assert.equal(v.f.a, null);
  assert.equal(v.ph, 'pick');
});

test('탄 - 같은 id 끼리 잇고, 사라진 것은 속도대로 조금만', () => {
  const b = new SnapBuffer();
  const p = (id, x, vx) => ({ id, o: 'a', k: 'EMBER', ty: 'FIRE', sty: 'flame', x, y: 100, vx, vy: 0, r: 10 });
  b.push(snap(1.0, F(0, 0), F(0, 0), { p: [p(1, 100, 600), p(2, 500, 600)] }));
  b.push(snap(1.1, F(0, 0), F(0, 0), { p: [p(1, 160, 600), p(3, 900, 0)] }));
  const v = b.at(1.05);
  const byId = Object.fromEntries(v.p.map((q) => [q.id, q]));
  assert.ok(near(byId[1].x, 130));
  assert.ok(near(byId[2].x, 530));            // 다음 모습에 없다: 속도대로
  assert.equal(byId[3], undefined);           // 아직 안 나온 것
  const end = b.at(2.0);                      // 끝 뒤 0.9초 - 0.15초까지만 더 간다
  assert.ok(near(end.p[0].x, 160 + 600 * 0.15));
});

test('이벤트 - 그릴 때가 되어야 나오고, 한 번만', () => {
  const b = new SnapBuffer();
  b.push(snap(1.0, F(0, 0), F(0, 0), { ev: [{ e: 'cast', w: 'a' }] }));
  b.push(snap(1.1, F(0, 0), F(0, 0), { ev: [{ e: 'hit', v: 'b' }, { e: 'txt', w: 'b', msg: '' }] }));
  assert.deepEqual(b.events(0.9), []);
  assert.deepEqual(b.events(1.05).map((e) => e.e), ['cast']);
  assert.deepEqual(b.events(1.05), []);
  assert.deepEqual(b.events(5).map((e) => e.e), ['hit', 'txt']);
});

test('오래된 모습은 버린다 (1초 넘게 지난 것)', () => {
  const b = new SnapBuffer();
  for (let i = 0; i < 100; i += 1) b.push(snap(i / 30, F(i, 0), F(0, 0)));
  assert.ok(b.size() <= 32);
  assert.equal(b.latest().f.a.x, 99);
});

test('아레나 벽 - 몸 반지름만큼 안쪽', () => {
  assert.deepEqual(clampArena(-50, 2000), { x: 26, y: 900 - 26 });
  assert.deepEqual(clampArena(800, 450), { x: 800, y: 450 });
});

test('예측 - 누른 순간부터 F.spd 로 먼저 간다', () => {
  const pr = new Predictor();
  pr.server(F(400, 400, { spd: 200 }), 0, 10.0, 0.1);
  pr.input(1, 1, 0, 10.0);
  const p = pr.pos(10.5);
  assert.ok(near(p.x, 500) && near(p.y, 400));
});

test('예측 - ack 를 받으면 서버 자리에서 안 받은 입력만 다시 굴린다 (같은 길이면 튀지 않는다)', () => {
  const pr = new Predictor();
  pr.server(F(400, 400, { spd: 200 }), 0, 10.0, 0.1);
  pr.input(1, 1, 0, 10.0);                    // 오른쪽
  pr.input(2, 0, 1, 10.5);                    // 아래
  const before = pr.pos(10.6);
  assert.ok(near(before.x, 500) && near(before.y, 420));
  // 서버는 10.0+0.05 에 1번을 받아 0.45초 오른쪽으로 갔다 (아직 2번은 모른다).
  // 지역 시각 10.55 에 받았다. 서버가 2번을 받은 것은 그보다 뒤.
  pr.server(F(490, 400, { spd: 200 }), 1, 10.55, 0.1);
  const after = pr.pos(10.6);
  assert.ok(near(after.x, before.x, 1e-6) && near(after.y, before.y, 1e-6), JSON.stringify(after));
});

test('예측 - 서버와 어긋나면 서버 쪽으로 부드럽게 붙는다', () => {
  const pr = new Predictor();
  pr.server(F(400, 400, { spd: 200 }), 0, 10.0, 0.1);
  pr.input(1, 1, 0, 10.0);
  // 서버는 막혀서(다른 몸 등) 거의 못 갔다
  pr.server(F(410, 400, { spd: 200 }), 1, 10.5, 0.1);
  const right = 410 + 200 * 0.1;              // 받은 때 - 왕복 = 10.4 부터 다시 굴린다
  const shown = pr.pos(10.5);
  assert.ok(near(shown.x, 500), '처음에는 보이던 자리 그대로 ' + shown.x);
  for (let i = 0; i < 60; i += 1) pr.tick(1 / 60);
  const later = pr.pos(10.5);
  assert.ok(Math.abs(later.x - right) < 1, '1초 뒤에는 서버 쪽 ' + later.x);
});

test('예측 - 너무 멀면 바로 옮긴다 (교체 · 순간 이동)', () => {
  const pr = new Predictor();
  pr.server(F(400, 400, { spd: 200 }), 0, 10.0, 0.1);
  pr.server(F(1200, 700, { spd: 200 }), 0, 10.1, 0.1);
  assert.deepEqual(pr.pos(10.1), { x: 1200, y: 700 });
});

test('예측 - 벽에 막힌다', () => {
  const pr = new Predictor();
  pr.server(F(1500, 400, { spd: 300 }), 0, 10.0, 0.1);
  pr.input(1, 1, 0, 10.0);
  assert.equal(pr.pos(12).x, 1600 - 26);
});

test('예측 - 혼란이면 반대로 간다', () => {
  const pr = new Predictor();
  pr.server(F(800, 400, { spd: 200, c: ['cnf'] }), 0, 10.0, 0.1);
  pr.input(1, 1, 0, 10.0);
  assert.ok(near(pr.pos(10.5).x, 700));
});

test('예측 - 마음대로 걷는 때(서 있기 · 걷기)가 아니면 서버 자리 그대로 (기술 · 피하기 · 잠듦 · 교체 …)', () => {
  const held = ['wind', 'act', 'rec', 'guard', 'dodge', 'stun', 'sleep', 'frz', 'swap', 'ko', 'hide'];
  for (const extra of [...held.map((st) => ({ st })), { spd: 0 }]) {
    const pr = new Predictor();
    pr.server(F(800, 400, { spd: 200, ...extra }), 0, 10.0, 0.1);
    pr.input(1, 1, 0, 10.0);
    assert.deepEqual(pr.pos(10.5), { x: 800, y: 400 }, JSON.stringify(extra));
  }
  const walking = new Predictor();
  walking.server(F(800, 400, { spd: 200, st: 'walk' }), 0, 10.0, 0.1);
  walking.input(1, 1, 0, 10.0);
  assert.ok(near(walking.pos(10.5).x, 900));
});

test('예측 - 쌓인 입력은 받은 만큼 버린다', () => {
  const pr = new Predictor();
  pr.server(F(800, 400, { spd: 200 }), 0, 10.0, 0.1);
  for (let s = 1; s <= 10; s += 1) pr.input(s, s % 2, 0, 10 + s / 100);
  assert.equal(pr.pending(), 10);
  pr.server(F(800, 400, { spd: 200 }), 7, 10.2, 0.1);
  assert.equal(pr.pending(), 3);
});

test('내 쪽 이벤트는 받자마자, 상대 것 · 맞음은 그릴 때가 되어야', () => {
  const b = new SnapBuffer('a');
  b.push(snap(1.0, F(0, 0), F(0, 0), { ev: [
    { e: 'cast', w: 'a', m: 0 }, { e: 'cast', w: 'b', m: 1 }, { e: 'dodge', w: 'a' }, { e: 'hit', w: 'a', v: 'b' },
    { e: 'stat', w: 'a', st: 'atk', d: 2 }, { e: 'swap', w: 'b', fr: 0, to: 1 }, { e: 'ko', w: 'a', i: 0 },
  ] }));
  // 그릴 시각이 아직 한참 앞이어도
  assert.deepEqual(b.events(0.5).map((e) => e.e + ':' + e.w), ['cast:a', 'dodge:a', 'stat:a']);
  assert.deepEqual(b.events(0.6), [], '한 번만');
  assert.deepEqual(b.events(1.0).map((e) => e.e + ':' + e.w), ['cast:b', 'hit:a', 'swap:b', 'ko:a']);
});

test('상대 기술에 맞아 걸린 내 상태는 그 hit 와 같이 (먼저 나오지 않는다)', () => {
  const b = new SnapBuffer('a');
  b.push(snap(2.0, F(0, 0), F(0, 0), { ev: [
    { e: 'hit', w: 'b', v: 'a', dmg: 20 }, { e: 'status', w: 'a', s: 'brn' }, { e: 'stat', w: 'a', st: 'def', d: -1 },
  ] }));
  assert.deepEqual(b.events(1.9), []);
  assert.deepEqual(b.events(2.0).map((e) => e.e), ['hit', 'status', 'stat']);
  // 내가 건 것 (잠듦 · 칼춤) 은 바로
  b.push(snap(2.1, F(0, 0), F(0, 0), { ev: [{ e: 'status', w: 'a', s: 'slp' }, { e: 'stat', w: 'a', st: 'atk', d: 2 }] }));
  assert.deepEqual(b.events(1.9).map((e) => e.e), ['status', 'stat']);
});

test('나를 모르면 (hello 전) 다 뒤 시각에 · ownEvent 규칙', () => {
  const b = new SnapBuffer();
  b.push(snap(1.0, F(0, 0), F(0, 0), { ev: [{ e: 'cast', w: 'a' }] }));
  assert.deepEqual(b.events(0.5), []);
  b.setYou('a');
  b.push(snap(1.1, F(0, 0), F(0, 0), { ev: [{ e: 'cast', w: 'a' }] }));
  assert.deepEqual(b.events(0.5).map((e) => e.e), ['cast']);
  assert.equal(ownEvent({ e: 'cast', w: 'a' }, 'a'), true);
  assert.equal(ownEvent({ e: 'cast', w: 'b' }, 'a'), false);
  assert.equal(ownEvent({ e: 'hit', w: 'a', v: 'b' }, 'a'), false, '맞음은 상대 몸과 같이');
  assert.equal(ownEvent({ e: 'ko', w: 'a' }, 'a'), false);
  assert.equal(ownEvent({ e: 'heal', w: 'a' }, 'a', true), true, '회복은 맞음과 상관없이');
  assert.equal(ownEvent({ e: 'status', w: 'a' }, 'a', true), false);
  assert.equal(ownEvent(null, 'a'), false);
  assert.equal(ownEvent({ e: 'cast', w: 'a' }, null), false);
});
