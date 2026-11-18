/* 손맛 검사 (js/feel.js · render.js 의 순수 함수).

   무엇을 못 박나
     1. 멈춤(hitstop) 은 50~110ms, 데미지 % · 효과 굉장 · 급소로 길어지고, 쓰러뜨리면 가장 길다. 막히면 0.
        멈춤은 하나다 - 짧은 것이 긴 것을 끊지 않고, dt 만큼 줄어든다.
     2. 멈춘 동안 몸은 멈춘 순간의 자리에 있다가, 풀리면 80ms 동안 진짜 자리로 미끄러진다 - 한 장에 크게 뛰지 않는다.
        교체처럼 먼 곳이면 바로 옮긴다.
     3. 상대가 맞은 비율 = hpr(0~1000) 이 줄어든 만큼 (상대의 정확한 체력은 오지 않는다). 여러 번 치는 기술은 hit 마다,
        교체하면 그 칸의 hpr 로, 회복하면 거기서부터.
     4. 맞은 몸: 두 장 하얗게 → 붉게 사그라든다. 맞은 쪽으로 눌렸다 출렁이며 돌아온다.
     5. 누르자마자 그린 준비 몸짓은 서버의 cast 가 오면 그대로 이어 가고 (다시 시작하지 않는다), 0.25초 안에 안 오면
        사그라든다. 휘청(F.hs · stun) 은 아파하는 모습. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  hitstopSec, isChip, HitStop, Hold, HpTracker, damageLabel, mergeTarget, STOP_MIN, STOP_MAX, CATCHUP_SEC, MERGE_SEC,
} from '../js/feel.js';
import { squashAt, hitWash, dirAngle, Body, PREDICT_SEC } from '../js/render.js';

const near = (a, b, eps = 1e-9) => Math.abs(a - b) <= eps;

test('멈춤 길이 - 50~110ms, 세게 · 효과 굉장 · 급소일수록 길게', () => {
  assert.equal(hitstopSec({ pct: 0 }), STOP_MIN);
  assert.ok(near(STOP_MIN, 0.05) && near(STOP_MAX, 0.11));
  const a = hitstopSec({ pct: 5 });
  const b = hitstopSec({ pct: 20 });
  const c = hitstopSec({ pct: 20, eff: 2 });
  const d = hitstopSec({ pct: 20, eff: 2, crit: true });
  assert.ok(a < b && b < c && c < d, [a, b, c, d].join(' '));
  assert.equal(hitstopSec({ pct: 90, eff: 4, crit: true }), STOP_MAX, '넘지 않는다');
  assert.equal(hitstopSec({ pct: 10, eff: 0 }), 0, '막혔다');
  assert.equal(hitstopSec({ ko: true }), STOP_MAX);
  assert.ok(hitstopSec({ eff: 0.5 }) >= STOP_MIN, '비율을 몰라도');
  assert.ok(hitstopSec() >= STOP_MIN);
});

test('저절로 깎이는 것 (반동 · 독 · 화상 · 씨뿌리기) 은 멈추지 않는다', () => {
  assert.equal(isChip({ e: 'hit', w: 'a', v: 'a', k: 'DOUBLEEDGE' }), true);
  assert.equal(isChip({ e: 'hit', w: 'b', v: 'a', k: 'seed' }), true);
  assert.equal(isChip({ e: 'hit', w: 'a', v: 'a', k: 'brn' }), true);
  assert.equal(isChip({ e: 'hit', w: 'b', v: 'a', k: 'TACKLE' }), false);
});

test('HitStop - 하나, 긴 쪽으로, dt 만큼 준다', () => {
  const h = new HitStop();
  assert.equal(h.active, false);
  h.kick(0.08);
  h.kick(0.05);
  assert.equal(h.left, 0.08, '짧은 것이 긴 것을 끊지 않는다');
  h.update(0.03);
  assert.ok(near(h.left, 0.05) && h.active);
  h.update(-1);
  h.update(NaN);
  assert.ok(near(h.left, 0.05));
  h.update(0.1);
  assert.equal(h.active, false);
  assert.equal(h.left, 0);
});

test('Hold - 멈춘 동안 그 자리, 풀리면 80ms 동안 미끄러져 따라간다 (뛰지 않는다)', () => {
  const h = new Hold();
  const dt = 1 / 60;
  let t = 0;
  let x = 100;
  let drawn = h.at(x, 0, t, false);
  assert.equal(drawn.x, 100);
  // 걷는 중 (300 u/s) 에 멈춤 0.1초
  const v = 300;
  const path = [drawn.x];
  for (let i = 0; i < 6; i++) {
    t += dt;
    x += v * dt;
    drawn = h.at(x, 0, t, true);
    path.push(drawn.x);
  }
  assert.ok(path.slice(1).every((p) => p === path[1]), '멈춘 동안 그 자리');
  assert.equal(path[1], path[0], '멈춘 순간의 자리 (마지막으로 그린 곳)');
  // 풀린다 - 한 장에 움직이는 거리가 '진짜 걸음 + 따라잡기' 를 크게 넘지 않는다
  let prev = drawn.x;
  let maxStep = 0;
  for (let i = 0; i < 12; i++) {
    t += dt;
    x += v * dt;
    drawn = h.at(x, 0, t, false);
    maxStep = Math.max(maxStep, drawn.x - prev);
    prev = drawn.x;
  }
  const behind = 6 * v * dt;                      // 멈춘 동안 뒤처진 거리
  assert.ok(maxStep < v * dt + behind * 0.4, '한 장에 크게 뛰지 않는다 (' + maxStep.toFixed(2) + ')');
  assert.ok(near(drawn.x, x), 'CATCHUP_SEC 뒤에는 진짜 자리');
  assert.ok(CATCHUP_SEC <= 0.08 + 1e-9);
  // 교체처럼 멀면 바로
  const s = new Hold();
  s.at(0, 0, 0, false);
  s.at(0, 0, 0.01, true);
  assert.equal(s.at(900, 0, 0.02, false).x, 900);
  // 멈춘 자리에서 다시 멈추면 그 자리 그대로 (끊김 없이)
  const r = new Hold();
  r.at(0, 0, 0, false);
  r.at(10, 0, 0.02, true);
  const mid = r.at(50, 0, 0.05, false);
  const again = r.at(60, 0, 0.06, true);
  assert.deepEqual(again, mid);
});

const F = (i, hpr, team) => ({ i, hpr, team: team.map((h) => ({ hpr: h, ko: h === 0 })) });
const snap = (ev, fa, fb) => ({ t: 's', ev, f: { a: fa, b: fb } });

test('맞은 비율 - hpr 이 줄어든 만큼 (최대 체력의 %)', () => {
  const hp = new HpTracker();
  hp.annotate(snap([], F(0, 1000, [1000, 1000, 1000]), F(0, 1000, [1000, 1000, 1000])));
  const hit = { e: 'hit', w: 'a', v: 'b', hpr: 873, eff: 1 };
  hp.annotate(snap([hit], F(0, 1000, [1000, 1000, 1000]), F(0, 873, [873, 1000, 1000])));
  assert.ok(near(hit.pct, 12.7));
  assert.equal(hit.dmg, undefined, '정확한 데미지는 만들지 않는다');
});

test('맞은 비율 - 여러 번 치는 기술은 hit 마다, 한 모습에 여럿이 와도', () => {
  const hp = new HpTracker();
  hp.annotate(snap([], F(0, 1000, [1000]), F(0, 1000, [1000, 1000])));
  const hits = [940, 880, 815].map((h) => ({ e: 'hit', w: 'a', v: 'b', hpr: h, eff: 1 }));
  hp.annotate(snap(hits.slice(0, 2), F(0, 1000, [1000]), F(0, 880, [880, 1000])));
  hp.annotate(snap(hits.slice(2), F(0, 1000, [1000]), F(0, 815, [815, 1000])));
  assert.deepEqual(hits.map((h) => h.pct), [6, 6, 6.5]);
  // 합치면 처음부터 줄어든 만큼
  assert.ok(near(hits.reduce((a, h) => a + h.pct, 0), 18.5));
});

test('맞은 비율 - 교체하면 그 칸의 체력에서, 회복하면 거기서부터', () => {
  const hp = new HpTracker();
  hp.annotate(snap([], F(0, 1000, [1000]), F(0, 400, [400, 700, 1000])));
  // 상대가 둘째로 바꾸고 같은 모습에서 맞았다
  const hit = { e: 'hit', w: 'a', v: 'b', hpr: 600, eff: 1 };
  hp.annotate(snap([{ e: 'swap', w: 'b', fr: 0, to: 1 }, hit], F(0, 1000, [1000]), F(1, 600, [400, 600, 1000])));
  assert.ok(near(hit.pct, 10), String(hit.pct));
  // 회복 뒤 맞음
  const hit2 = { e: 'hit', w: 'a', v: 'b', hpr: 850, eff: 1 };
  hp.annotate(snap([{ e: 'heal', w: 'b', hpr: 950 }, hit2], F(0, 1000, [1000]), F(1, 850, [400, 850, 1000])));
  assert.ok(near(hit2.pct, 10), String(hit2.pct));
  // 내가 맞은 것도 적는다 (멈춤 길이에 쓴다)
  const mine = { e: 'hit', w: 'b', v: 'a', hpr: 750, dmg: 30, eff: 2 };
  hp.annotate(snap([mine], F(0, 750, [750]), F(1, 850, [400, 850, 1000])));
  assert.ok(near(mine.pct, 25));
  // 모르는 쪽 · 깨진 이벤트는 넘어간다
  hp.annotate({ ev: [null, { e: 'hit', v: 'z', hpr: 1 }, { e: 'hit', v: 'a' }], f: {} });
  hp.annotate({});
});

test('데미지 숫자 글 · 이어 맞은 숫자 합치기', () => {
  assert.equal(damageLabel(12.4, '%'), '12%');
  assert.equal(damageLabel(0.3, '%'), '1%', '깎였으면 적어도 1%');
  assert.equal(damageLabel(37, ''), '37');
  const list = [
    { num: true, side: 'b', unit: '%', age: 0.1, s: 'x' },
    { num: false, side: 'b', unit: '%', age: 0.1 },
    { num: true, side: 'a', unit: '', age: 0.1 },
  ];
  assert.equal(mergeTarget(list, 'b', '%'), list[0]);
  assert.equal(mergeTarget(list, 'a', '%'), null, '단위가 다르면 따로');
  assert.equal(mergeTarget(list, 'a', ''), list[2]);
  list[0].age = MERGE_SEC + 0.01;
  assert.equal(mergeTarget(list, 'b', '%'), null, '오래된 것과는 합치지 않는다');
});

test('맞은 몸 - 두 장 하얗게 → 붉게 사그라든다', () => {
  assert.match(hitWash(0), /^rgba\(255,255,255/);
  assert.match(hitWash(0.02), /^rgba\(255,255,255/);
  assert.match(hitWash(0.05), /^rgba\(255,64,64/);
  const a1 = Number(/,([\d.]+)\)$/.exec(hitWash(0.06))[1]);
  const a2 = Number(/,([\d.]+)\)$/.exec(hitWash(0.15))[1]);
  assert.ok(a1 > a2 && a2 > 0);
  assert.equal(hitWash(0.5), null);
  assert.equal(hitWash(-1), null);
  assert.equal(hitWash(NaN), null);
});

test('맞은 몸 - 처음 가장 눌리고 출렁이며 돌아온다 (도트 시간)', () => {
  const k = 1;
  assert.ok(squashAt(0, k) > 0.15, '처음이 가장 눌린다');
  assert.ok(Math.abs(squashAt(0.1, k)) < squashAt(0, k));
  assert.ok(squashAt(0.08, k) < 0, '튀어 오른다 (반대로)');
  assert.equal(squashAt(1, k), 0);
  assert.equal(squashAt(-0.1, k), 0);
  assert.ok(squashAt(0, 0.5) < squashAt(0, 1), '세기에 비례');
  assert.equal(squashAt(0, 0), 0);
});

test('방향 → 라디안 (0 아래 · 2 오른쪽 · 4 위 · 6 왼쪽)', () => {
  assert.ok(near(dirAngle(0), Math.PI / 2));
  assert.ok(near(dirAngle(2), 0));
  assert.ok(near(dirAngle(4), -Math.PI / 2));
  assert.ok(near(Math.cos(dirAngle(6)), -1));
  assert.ok(near(dirAngle(-1), Math.PI / 2));
});

/* 누르자마자 몸짓 (render Body). */

const FB = (st, sm = -1, sp = 0, extra = {}) => ({ i: 0, x: 0, y: 0, d: 2, st, sm, sp, ...extra });
const have = new Set(['Walk', 'Idle', 'Attack', 'Shoot', 'Charge']);
const LOOK = { have, sheets: { Walk: { durs: [8] }, Idle: { durs: [8] }, Attack: { durs: [6, 6, 6, 6] }, Shoot: { durs: [4, 4] },
  Charge: { durs: [6, 6] } } };

test('누르자마자 몸짓 - 서버의 cast 가 오면 그대로 이어 간다 (처음부터 다시 하지 않는다)', () => {
  const b = new Body();
  b.update(FB('idle'), 0, 0, 10, 1 / 60);
  b.predict(1, 'melee', 0.5, 10, 100);
  b.track(FB('idle'), 10.02, 100.02, () => null);
  let p = b.pose(LOOK, FB('idle'), 10.02, 100.02);
  assert.equal(p.anim, 'Attack', '서버가 받기 전에 벌써 친다');
  const since = b.since;
  // 0.08초 뒤 서버의 cast (같은 칸) + 준비 모습
  b.cast({ e: 'cast', w: 'a', m: 1, kind: 'melee', ang: 0.6 }, 10.08, 100.08);
  b.track(FB('wind', 1, 0.3), 10.09, 100.09, () => 'melee');
  p = b.pose(LOOK, FB('wind', 1, 0.3), 10.09, 100.09);
  assert.equal(p.anim, 'Attack');
  assert.equal(b.since, since, '같은 동작을 이어 간다');
  assert.ok(p.t > 0.05, '처음부터 다시가 아니다 (' + p.t + ')');
  assert.equal(b.act.ang, 0.6, '서버가 겨눈 쪽');
  assert.equal(b.act.pre, false);
});

test('누르자마자 몸짓 - 0.25초 안에 cast 가 안 오면 사그라든다', () => {
  const b = new Body();
  b.update(FB('idle'), 0, 0, 10, 1 / 60);
  b.predict(0, 'heal', 0, 10, 50);
  const walkOnly = { have: new Set(['Walk']), sheets: { Walk: { durs: [8] } } };
  b.track(FB('idle'), 10.1, 50.1, () => null);
  assert.ok(b.pose(walkOnly, FB('idle'), 10.1, 50.1).proc, '도트가 없으면 손으로 만든 몸짓');
  b.track(FB('idle'), 10 + PREDICT_SEC + 0.01, 50.3, () => null);
  const fading = b.pose(walkOnly, FB('idle'), 10 + PREDICT_SEC + 0.05, 50.3);
  assert.ok(fading.proc && fading.proc.fade < 1 && fading.proc.fade > 0, '흐려진다');
  b.track(FB('idle'), 10.6, 50.6, () => null);
  assert.equal(b.act, null, '끝');
  assert.equal(b.pose(walkOnly, FB('idle'), 10.6, 50.6).proc, null);
});

test('기술 몸짓 - 이벤트 없이 모습만 와도 (중간에 들어옴), 다른 칸이면 새로, 회복 동안 치던 것을 끝까지', () => {
  const b = new Body();
  b.update(FB('wind', 2, 0.5), 0, 0, 10, 1 / 60);
  b.track(FB('wind', 2, 0.5), 10, 10, (m) => (m === 2 ? 'beam' : null));
  assert.equal(b.pose(LOOK, FB('wind', 2, 0.5), 10, 10).anim, 'Charge');
  b.track(FB('act', 2, 0.1), 10.5, 10.5, () => 'beam');
  assert.equal(b.pose(LOOK, FB('act', 2, 0.1), 10.5, 10.5).anim, 'Shoot', '광선: 모았다가 쏜다');
  b.track(FB('rec', 2, 0.1), 10.55, 10.55, () => 'beam');
  assert.equal(b.pose(LOOK, FB('rec', 2, 0.1), 10.55, 10.55).anim, 'Shoot', '회복 동안 쏘던 것을 끝까지');
  b.track(FB('rec', 2, 0.9), 11.5, 11.5, () => 'beam');
  assert.equal(b.pose(LOOK, FB('rec', 2, 0.9), 11.5, 11.5).anim, 'Idle', '다 쏘면 서기');
  b.track(FB('idle'), 11.6, 11.6, () => null);
  assert.equal(b.act, null);
  // 휘청 (F.hs · stun) 은 아파하는 모습
  const hurt = { have: new Set(['Walk', 'Idle', 'Hurt']), sheets: { Walk: { durs: [8] }, Idle: { durs: [8] }, Hurt: { durs: [8] } } };
  assert.equal(b.pose(hurt, FB('idle', -1, 0, { hs: true }), 12, 12).anim, 'Hurt');
  assert.equal(b.pose(hurt, FB('stun'), 12.1, 12.1).anim, 'Hurt');
});

test('기술 몸짓 - 준비 중에 맞아 경직 (st stun, sm 그대로) 이면 아파하다가 하던 기술을 이어 간다 (꼴을 잃지 않는다)', () => {
  const b = new Body();
  const hurt = { have: new Set(['Walk', 'Idle', 'Hurt', 'Charge', 'Shoot']),
    sheets: { Walk: { durs: [8] }, Idle: { durs: [8] }, Hurt: { durs: [8] }, Charge: { durs: [6, 6] }, Shoot: { durs: [4, 4] } } };
  b.update(FB('wind', 1, 0.1), 0, 0, 10, 1 / 60);
  b.cast({ e: 'cast', w: 'b', m: 1, kind: 'beam', ang: 3 }, 10, 10);
  b.track(FB('wind', 1, 0.1), 10, 10, () => null);
  assert.equal(b.pose(hurt, FB('wind', 1, 0.1), 10, 10).anim, 'Charge');
  b.track(FB('stun', 1, 0.5), 10.2, 10.2, () => null);
  assert.equal(b.pose(hurt, FB('stun', 1, 0.5), 10.2, 10.2).anim, 'Hurt', '경직 동안 아파한다');
  b.track(FB('wind', 1, 0.4), 10.4, 10.4, () => null);
  assert.equal(b.act.kind, 'beam', '상대 기술의 꼴 (cast 로만 안다) 을 잃지 않는다');
  assert.equal(b.pose(hurt, FB('wind', 1, 0.4), 10.4, 10.4).anim, 'Charge');
});
