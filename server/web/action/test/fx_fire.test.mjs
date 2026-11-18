/* 불 집안 모양 검사 (js/fx/styles/fire.js - flame zap leaf powder poison).

     node --test server/web/action/test/

   무엇을 못 박나
     1. 다섯 키 · 훅 이름 · 값 (core.checkStyle), 불 집안 파일에는 이 다섯만.
     2. 모양마다 가진 훅을 전부 (탄 · 꼬리 · 처음 · 맞음 · 장판 다섯 꼴의 표시 · 터짐 · 내려찍기 · 돌진 · 휘두름) 모든 타입 색 ·
        여러 시각으로 직접 불러도 예외 · NaN 없이, 혼합은 둘만, 알파 0~1, ctx 를 받은 그대로 돌려놓는다. 그라디언트는 없다.
     3. Fx 를 거쳐 끝까지 돌리면 입자는 풀(600) 안이고 다 사라진다. 탄 하나 · 장판 하나가 내는 입자 수는 정해진 만큼.
     4. 그림은 씨앗 + 시각으로만 정해진다 (같으면 같은 그림, 씨앗이 다르면 다른 그림, 번개는 시각이 바뀌면 다시 꺾인다).
     5. 색: 가루는 기술마다 제 색, 꽃잎 기술 · 요정 타입은 꽃잎, 스프라이트 색은 늘지 않는다.
     6. 번개 내려찍기는 줄기 잔상 + 화면 번쩍, 그냥 맞음은 번쩍이지 않는다. 휘두름의 튀는 입자는 돌진 하나에 한 번.
     7. 한 프레임 (2마리 · 이 집안 탄 20 · 장판 · 입자 400) 이 3 ms 안. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { Fx } from '../js/fx.js';
import { HOOKS, POOL_MAX, ZONE_KINDS, checkStyle } from '../js/fx/core.js';
import { FAMILIES, FAMILY_OF, styleDef } from '../js/fx/styles/index.js';
import fire from '../js/fx/styles/fire.js';
import { TYPE_FX } from '../js/consts.js';

const KEYS = ['flame', 'zap', 'leaf', 'powder', 'poison'];
const TYPES = Object.keys(TYPE_FX);

// ---------------------------------------------------------------- 가짜 2D ctx (fx-hooks.test.mjs 와 같은 규칙 + 부른 차례 기록)
const COLOR = /^(#[0-9a-f]{6}|rgba?\([\d.,\s]+\))$/i;
const okStyle = (v) => (typeof v === 'string' && COLOR.test(v)) || (!!v && typeof v.addColorStop === 'function');
const PROPS = {
  globalAlpha: (v) => Number.isFinite(v) && v >= 0 && v <= 1,
  globalCompositeOperation: (v) => v === 'source-over' || v === 'lighter',
  fillStyle: okStyle,
  strokeStyle: okStyle,
  lineWidth: (v) => Number.isFinite(v) && v > 0,
  lineDashOffset: Number.isFinite,
  lineCap: (v) => ['butt', 'round', 'square'].includes(v),
  lineJoin: (v) => ['miter', 'round', 'bevel'].includes(v),
  font: (v) => typeof v === 'string' && /\d+px /.test(v),
  textAlign: (v) => ['start', 'end', 'left', 'right', 'center'].includes(v),
  textBaseline: (v) => ['top', 'hanging', 'middle', 'alphabetic', 'ideographic', 'bottom'].includes(v),
};
const PLAIN = ['beginPath', 'closePath', 'moveTo', 'lineTo', 'quadraticCurveTo', 'bezierCurveTo', 'rect',
  'fill', 'stroke', 'fillRect', 'strokeRect', 'clip'];

class RecCtx {
  constructor() {
    this.n = Object.create(null);
    this.trace = null;                // 배열을 주면 (이름 + 숫자) 를 차례로 적는다
    this.fills = new Set();           // 칠한 색
    this.stack = [];
    this.st = {
      globalAlpha: 1, globalCompositeOperation: 'source-over', fillStyle: '#000000', strokeStyle: '#000000',
      lineWidth: 1, lineDashOffset: 0, lineCap: 'butt', lineJoin: 'miter', font: '10px sans-serif',
      textAlign: 'start', textBaseline: 'alphabetic', dash: [], moved: false,
    };
  }

  rec(name, args) {
    this.n[name] = (this.n[name] || 0) + 1;
    for (const a of args) if (typeof a === 'number' && !Number.isFinite(a)) throw new TypeError(`${name}: 숫자가 아니다 (${a})`);
    if (this.trace) this.trace.push(name + args.filter((a) => typeof a === 'number').map((a) => a.toFixed(3)).join(','));
  }

  save() { this.rec('save', []); this.stack.push({ ...this.st, dash: this.st.dash.slice() }); }
  restore() {
    this.rec('restore', []);
    if (!this.stack.length) throw new Error('restore 가 save 보다 많다');
    this.st = this.stack.pop();
  }
  arc(x, y, r, a0, a1) {
    this.rec('arc', [x, y, r, a0, a1]);
    if (r < 0) throw new RangeError('IndexSizeError: arc 반지름이 음수');
  }
  ellipse(x, y, rx, ry, rot, a0, a1) {
    this.rec('ellipse', [x, y, rx, ry, rot, a0, a1]);
    if (rx < 0 || ry < 0) throw new RangeError('IndexSizeError: ellipse 반지름이 음수');
  }
  createRadialGradient(...a) {
    this.rec('createRadialGradient', a);
    return { addColorStop(at, col) {
      if (!(at >= 0 && at <= 1) || !COLOR.test(col)) throw new TypeError(`addColorStop(${at}, ${col})`);
    } };
  }
  drawImage(img, ...nums) {
    this.rec('drawImage', nums);
    if (!img || !(img.width > 0)) throw new TypeError('drawImage: 그림이 아니다');
  }
  fill() {
    this.rec('fill', []);
    this.fills.add(this.st.fillStyle);
  }
  fillRect(...a) {
    this.rec('fillRect', a);
    this.fills.add(this.st.fillStyle);
  }
  translate(x, y) { this.rec('translate', [x, y]); this.st.moved = true; }
  rotate(r) { this.rec('rotate', [r]); this.st.moved = true; }
  scale(x, y) { this.rec('scale', [x, y]); this.st.moved = true; }
  fillText(s, x, y) { this.rec('fillText', [x, y]); }
  strokeText(s, x, y) { this.rec('strokeText', [x, y]); }
  setLineDash(a) {
    this.rec('setLineDash', []);
    if (!Array.isArray(a) || a.some((v) => !Number.isFinite(v) || v < 0)) throw new TypeError('setLineDash');
    this.st.dash = a.slice();
  }
  setTransform() { throw new Error('fx 가 화면 배율(setTransform)을 덮어쓴다'); }
  resetTransform() { throw new Error('fx 가 화면 배율(resetTransform)을 덮어쓴다'); }
  transform() { throw new Error('fx 는 transform 을 쓰지 않는다'); }
  createLinearGradient() { throw new Error('fx 는 선형 그라디언트를 만들지 않는다'); }
  createPattern() { throw new Error('fx 는 무늬를 만들지 않는다'); }
}
for (const name of PLAIN) if (!RecCtx.prototype[name]) RecCtx.prototype[name] = function (...args) { this.rec(name, args); };
for (const [prop, ok] of Object.entries(PROPS)) {
  Object.defineProperty(RecCtx.prototype, prop, {
    get() { return this.st[prop]; },
    set(v) {
      if (!ok(v)) throw new TypeError(`${prop} = ${v}`);
      this.st[prop] = v;
    },
  });
}

function newFx() {
  const sprites = [];
  const fx = new Fx({ canvas: (w, h) => {
    const ctx = new RecCtx();
    sprites.push(ctx);
    return { width: w, height: h, getContext: () => ctx };
  } });
  return { fx, sprites };
}

function clean(ctx, what) {
  assert.equal(ctx.stack.length, 0, what + ': save/restore 짝');
  assert.equal(ctx.globalAlpha, 1, what + ': globalAlpha');
  assert.equal(ctx.globalCompositeOperation, 'source-over', what + ': 혼합');
  assert.deepEqual(ctx.st.dash, [], what + ': 점선');
  assert.equal(ctx.st.moved, false, what + ': 옮기기');
}

function makeWorld(you = 'a') {
  const at = { a: { x: 400, y: 450 }, b: { x: 1200, y: 450 } };
  return { pos: (s) => at[s], now: 10, you, at };
}

function frame(fx, ctx, dt = 1 / 60) {
  fx.update(dt);
  fx.drawUnder(ctx);
  clean(ctx, 'drawUnder');
  fx.drawOver(ctx);
  clean(ctx, 'drawOver');
}

const zone = (kind, sty, i = 0, extra = {}) => ({
  id: `z${kind}${sty}${i}`, o: i % 2 ? 'a' : 'b', k: 'TEST', ty: TYPES[i % TYPES.length], sty, kind,
  x: 800, y: 450, r: 90, ang: 0.4, len: 520, w: 60, t0: 10, t1: 11, ...extra,
});

// 훅 하나를 core 처럼 save/restore 로 감싸 부르고 깨끗한지 본다
function call(ctx, what, hook, ...args) {
  ctx.save();
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'lighter';
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  hook(...args);
  ctx.restore();
  clean(ctx, what);
}

// ---------------------------------------------------------------- 1
test('불 집안: 다섯 키, 훅 이름 · 값이 바르고, 이 파일에는 이 다섯만', () => {
  assert.deepEqual(Object.keys(fire).sort(), [...KEYS].sort());
  assert.equal(FAMILIES.fire, fire);
  for (const k of KEYS) {
    assert.equal(FAMILY_OF[k], 'fire', k);
    assert.equal(styleDef(k), fire[k], `${k} 는 index 가 이 파일 것을 고른다`);
    assert.deepEqual(checkStyle(k, fire[k]), [], k);
    for (const name of Object.keys(fire[k])) assert.ok(name in HOOKS, `${k}.${name}`);
    for (const name of ['shot', 'trail', 'launch', 'impact']) assert.equal(typeof fire[k][name], 'function', `${k}.${name}`);
  }
  // 이 집안이 맡는 장판 · 돌진 (기술 목록에서 쓰는 곳)
  for (const [k, hooks] of Object.entries({
    flame: ['cone', 'ring', 'tele', 'fall', 'rush', 'swing'],
    zap: ['ring', 'tele', 'fall', 'beam', 'rush', 'swing'],
    leaf: ['cone', 'ring', 'tele', 'fall', 'rush', 'swing'],
    powder: ['cone'],
    poison: ['cone', 'ring', 'haz', 'rush', 'swing'],
  })) for (const h of hooks) assert.equal(typeof fire[k][h], 'function', `${k}.${h}`);
});

// ---------------------------------------------------------------- 2
test('모든 키 × 모든 훅 × 모든 타입 색 × 여러 시각: 예외 · NaN 없이 깨끗하게, 그라디언트 없이', () => {
  const { fx, sprites } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('b');
  fx.event({ e: 'phase', ph: 'fight' }, world);
  let n = 0;
  for (const k of KEYS) {
    const def = fire[k];
    TYPES.forEach((ty, i) => {
      const key = ['TEST', 'SLEEPPOWDER', 'PETALDANCE', 'TOXICSPIKES', 'STUNSPORE'][i % 5];
      for (const r of [6, 14, 30]) {
        const q = fx.shotOf({ id: `${k}${ty}${r}`, o: i % 2 ? 'a' : 'b', k: key, ty, sty: k, vx: 500 - i * 60, vy: 120 - i * 20, r },
          600 + i, 420);
        for (let f = 0; f < 3; f++) {
          fx.update(1 / 30);
          fx.shotOf({ id: `${k}${ty}${r}`, o: 'a', k: key, ty, sty: k, vx: 500, vy: 120, r }, 610 + f * 17, 424 + f * 4);
          call(ctx, `${k}.shot`, def.shot, fx, ctx, q);
          def.trail(fx, q, 1 / 30);
        }
        def.launch(fx, q);
      }
      for (const why of ['hit', 'tele', 'ring', 'cone', 'beam']) {
        for (const s of [0.75, 1, 1.35]) {
          def.impact(fx, 800, 450, i * 0.7, fx.shotOf({ id: 'c' + ty, ty, sty: k, vx: 1, vy: 0 }, 0, 0).c,
            { why, k: key, ty, sty: k, eff: 1, crit: false, s, r: 90, len: 300 });
        }
      }
      for (const kind of ZONE_KINDS) {
        if (!def[kind]) continue;
        for (const now of [9.9, 10, 10.3, 10.8, 10.99, 11, 11.05, 11.12, 11.25, 11.4, 13]) {
          for (const extra of [{}, { w: 0 }, { r: 8, len: 20, w: 400 }]) {
            const q = fx.zoneOf(zone(kind, k, i, { k: key, t1: kind === 'haz' ? 1e9 : 11, ...extra }), now);
            call(ctx, `${k}.${kind}@${now}`, def[kind], fx, ctx, q);
            n++;
          }
        }
      }
      if (def.fall) {
        for (const v of [0, 0.2, 0.5, 0.75, 1]) {
          const q = fx.zoneOf(zone('tele', k, i, { k: key }), 10.9);
          call(ctx, `${k}.fall`, def.fall, fx, ctx, q, q.x, q.y - 200 * (1 - v), v);
        }
      }
      fx.update(1 / 60);
    });
    // 돌진: Fx 가 만든 a 로 세 단계 · 휘두름 여러 시각
    fx.event({ e: 'cast', w: 'a', k: 'PETALDANCE', kind: 'melee', ty: 'GRASS', sty: k, x: 400, y: 450, ang: 0.3, len: 220, r: 60 }, world);
    const a = fx.anims.findLast((v) => v.kind === 'rush');
    for (let f = 0; f < 8; f++) {
      world.at.a.x += 25;
      fx.update(1 / 60);
    }
    for (const stage of ['wind', 'act', 'tail']) {
      for (const sk of [0, 0.5, 1]) if (def.rush) call(ctx, `${k}.rush`, def.rush, fx, ctx, { ...a, stage, sk, speed: 1200 });
    }
    if (def.swing) for (const t of [0, 0.1, 0.3, 0.6, 0.99]) call(ctx, `${k}.swing`, def.swing, fx, ctx, a, t);
    world.at.a.x = 400;
    for (let f = 0; f < 4; f++) frame(fx, ctx, 0.05);
  }
  assert.ok(n > 500, '장판 훅을 불렀다 (' + n + ')');
  assert.ok(ctx.n.drawImage > 1000 && ctx.n.fill > 1000 && ctx.n.stroke > 300, JSON.stringify(ctx.n));
  assert.equal(ctx.n.createRadialGradient, undefined, '화면 ctx 에서 그라디언트를 만들지 않는다');
  assert.ok(sprites.every((s) => (s.n.createRadialGradient || 0) <= 1), '스프라이트 하나에 그라디언트 하나');
  for (let f = 0; f < 60; f++) frame(fx, ctx, 0.05);
  assert.deepEqual(fx.counts(), { particles: 0, anims: 0, texts: 0 }, '다 사라진다');
});

// ---------------------------------------------------------------- 3
// 탄 · 장판 · 돌진을 Fx 로 sec 동안 그리며 살아 있는 입자 수의 가장 큰 값
function peak(sty, what, sec = 1.5) {
  const { fx } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('a');
  let most = 0;
  if (what === 'rush') fx.event({ e: 'cast', w: 'a', k: 'X', kind: 'melee', ty: 'FIRE', sty, x: 400, y: 450, ang: 0, len: 220, r: 60 }, world);
  for (let f = 0, now = 10; f < sec * 60; f++, now += 1 / 60) {
    if (what === 'shot') fx.drawProjectile(ctx, { id: 'p', o: 'a', k: 'X', ty: 'FIRE', sty, vx: 680, vy: 0, r: 16 }, 300 + f * 11, 450);
    else if (what === 'rush') {
      if (f > 10 && f < 22) world.at.a.x += 18;
    } else fx.drawZone(ctx, zone(what, sty, 0, { t0: 10, t1: 10.4, w: 300, len: 360, r: 230 }), Math.min(now, 10.62));
    frame(fx, ctx);
    most = Math.max(most, fx.counts().particles);
  }
  return most;
}

test('입자 수는 정해진 만큼 - 탄 하나 · 장판 하나 · 돌진 하나', () => {
  for (const k of KEYS) {
    const shot = peak(k, 'shot');
    assert.ok(shot > 3 && shot <= 45, `${k} 탄 하나 ${shot}`);
    for (const kind of ['cone', 'ring']) {
      if (!fire[k][kind]) continue;
      const z = peak(k, kind);
      assert.ok(z <= 160, `${k}.${kind} 하나 ${z}`);
    }
    if (fire[k].rush) {
      const r = peak(k, 'rush');
      assert.ok(r <= 90, `${k} 돌진 하나 ${r}`);
    }
  }
});

test('Fx 를 거쳐 끝까지: 입자는 풀 안이고, 다 사라진다', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('a');
  for (let f = 0; f < 120; f++) {
    KEYS.forEach((k, i) => {
      for (let j = 0; j < 4; j++) {
        fx.drawProjectile(ctx, { id: `${k}${j}`, o: 'a', k: 'X', ty: TYPES[(i + j) % TYPES.length], sty: k, vx: 600, vy: j * 40 - 60, r: 15 },
          200 + ((f * 10 + j * 90) % 1200), 300 + j * 80);
      }
      for (const kind of ZONE_KINDS) fx.drawZone(ctx, zone(kind, k, i, { t0: 10, t1: 10.5 + (f % 40) / 60, id: `${kind}${k}${f >> 5}` }), 10 + f / 60);
    });
    if (f % 20 === 0) fx.event({ e: 'hit', w: 'a', v: 'b', k: 'X', ty: 'POISON', sty: KEYS[f % 5], hpr: 1, eff: 2, crit: true, x: 1200, y: 450 }, world);
    frame(fx, ctx);
    assert.ok(fx.counts().particles <= POOL_MAX);
  }
  for (let f = 0; f < 50; f++) frame(fx, ctx, 0.05);
  assert.equal(fx.counts().particles, 0);
});

// ---------------------------------------------------------------- 4
function shotTrace(k, id, clock, extra = {}) {
  const { fx } = newFx();
  fx.clock = clock;                     // update 는 한 번에 0.1초까지라 시계를 바로 맞춘다
  const q = fx.shotOf({ id, o: 'a', k: 'X', ty: 'GRASS', sty: k, vx: 600, vy: -50, r: 16, ...extra }, 500, 400);
  const ctx = new RecCtx();
  ctx.trace = [];
  call(ctx, k, fire[k].shot, fx, ctx, q);
  return ctx.trace.join(' ');
}

test('그림은 씨앗 + 시각으로만: 같으면 같고, 씨앗이 다르면 다르고, 시간이 흐르면 움직인다', () => {
  for (const k of KEYS) {
    const a = shotTrace(k, 77, 3.2), b = shotTrace(k, 77, 3.2);
    assert.equal(a, b, `${k}: 같은 씨앗 · 시각이면 같은 그림 (Math.random 을 쓰지 않는다)`);
    assert.notEqual(a, shotTrace(k, 78, 3.2), `${k}: 씨앗이 다르면 다른 그림`);
    assert.notEqual(a, shotTrace(k, 77, 3.35), `${k}: 시간이 흐르면 움직인다`);
  }
  // 번개는 1/20초쯤마다 다시 꺾인다 - 같은 마디 안이면 같고, 다음 마디면 다르다
  const { fx } = newFx();
  const ctx = new RecCtx();
  const draw = (clock) => {
    fx.clock = clock;
    ctx.trace = [];
    call(ctx, 'zap.ring', fire.zap.ring, fx, ctx, fx.zoneOf(zone('ring', 'zap', 0), 11.05));
    return ctx.trace.filter((s) => s.startsWith('lineTo')).join(' ');
  };
  assert.equal(draw(5.001), draw(5.002));
  assert.notEqual(draw(5.001), draw(5.08));
});

// ---------------------------------------------------------------- 5
test('색: 가루는 기술마다 제 색, 꽃잎 기술 · 요정 타입은 꽃잎, 스프라이트 색은 늘지 않는다', () => {
  const fillsOf = (k, key, ty) => {
    const { fx } = newFx();
    const ctx = new RecCtx();
    const q = fx.shotOf({ id: 1, o: 'a', k: key, ty, sty: k, vx: 600, vy: 0, r: 16 }, 500, 400);
    call(ctx, k, fire[k].shot, fx, ctx, q);
    return { fills: ctx.fills, soft: [...fx.ink.cache.soft.keys()] };
  };
  assert.ok(fillsOf('powder', 'SLEEPPOWDER', 'GRASS').soft.includes('#d9f2ff'), '잠가루는 푸른 구름');
  assert.ok(fillsOf('powder', 'STUNSPORE', 'GRASS').soft.includes('#fff6a8'), '저리가루는 노란 구름');
  assert.ok(fillsOf('powder', 'GALLERY', 'GRASS').soft.includes(TYPE_FX.GRASS[0]), '모르는 기술은 타입 색');
  assert.ok(!fillsOf('powder', 'SLEEPPOWDER', 'GRASS').soft.includes(TYPE_FX.GRASS[0]), '기술 색이 타입 색보다 먼저');
  assert.ok(fillsOf('leaf', 'PETALDANCE', 'GRASS').fills.has('#ffd9ee'), '꽃잎댄스는 분홍 꽃잎');
  assert.ok(fillsOf('leaf', 'X', 'FAIRY').fills.has(TYPE_FX.FAIRY[0]), '요정 타입은 제 색 꽃잎');
  assert.ok(fillsOf('leaf', 'RAZORLEAF', 'GRASS').fills.has(TYPE_FX.GRASS[0]), '그냥 잎은 풀 색');
  // 몇 판을 돌려도 새 스프라이트 (색) 가 생기지 않는다
  const { fx, sprites } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('a');
  const round = () => {
    KEYS.forEach((k, i) => {
      fx.event({ e: 'cast', w: 'a', k: 'X', kind: i % 2 ? 'melee' : 'dash', ty: 'FIRE', sty: k, x: 400, y: 450, ang: 0, len: 300, r: 40 }, world);
      for (let f = 0; f < 30; f++) {
        if (f > 4 && f < 16) world.at.a.x += 20;
        fx.drawProjectile(ctx, { id: 'p' + k, o: 'a', k: 'SLEEPPOWDER', ty: 'FIRE', sty: k, vx: 600, vy: 0, r: 16 }, 300 + f * 10, 450);
        for (const kind of ZONE_KINDS) fx.drawZone(ctx, zone(kind, k, 2, { ty: 'FIRE', k: 'PETALDANCE' }), 10.6 + f * 0.02);
        frame(fx, ctx);
      }
      world.at.a.x = 400;
    });
  };
  round();
  round();
  const made = sprites.length;
  round();
  round();
  assert.equal(sprites.length, made, '한 번 만든 색만 쓴다');
});

// ---------------------------------------------------------------- 6
test('번개 내려찍기는 줄기 잔상 + 화면 번쩍, 그냥 맞음은 번쩍이지 않는다', () => {
  const run = (why) => {
    const { fx } = newFx();
    fx.update(0.5);
    fire.zap.impact(fx, 800, 450, 0, { light: TYPE_FX.ELECTRIC[0], dark: TYPE_FX.ELECTRIC[1] },
      { why, k: 'THUNDER', ty: 'ELECTRIC', sty: 'zap', eff: 1, crit: false, s: 1, r: 75, len: 0 });
    const lines = fx.parts.all.filter((p) => p.on && p.shape === 'line');
    return { lines, flash: fx.flash };
  };
  const strike = run('tele');
  assert.ok(strike.lines.length >= 10, '줄기 잔상 ' + strike.lines.length);
  assert.ok(strike.lines.some((p) => p.y < 450 - 300), '하늘에서부터');
  assert.ok(strike.lines.some((p) => p.y2 === 450 && p.x2 === 800), '표시 한가운데까지');
  assert.ok(strike.flash > 0.1);
  const hit = run('hit');
  assert.equal(hit.lines.length, 0);
  assert.equal(hit.flash, 0);
});

test('휘두름의 튀는 입자는 돌진 하나에 한 번', () => {
  for (const k of KEYS) {
    if (!fire[k].swing) continue;
    const { fx } = newFx();
    const ctx = new RecCtx();
    fx.event({ e: 'cast', w: 'a', k: 'X', kind: 'melee', ty: 'FIRE', sty: k, x: 400, y: 450, ang: 0, len: 220, r: 60 }, makeWorld());
    const a = fx.anims.find((v) => v.kind === 'rush');
    call(ctx, k, fire[k].swing, fx, ctx, a, 0.05);
    const before = fx.counts().particles;
    call(ctx, k, fire[k].swing, fx, ctx, a, 0.5);
    const once = fx.counts().particles;
    assert.ok(once > before, `${k}: 튄다`);
    call(ctx, k, fire[k].swing, fx, ctx, a, 0.7);
    call(ctx, k, fire[k].swing, fx, ctx, a, 0.9);
    assert.equal(fx.counts().particles, once, `${k}: 한 번만`);
  }
});

test('독압정 (haz) 은 독 가시 - 기술 키 TOXICSPIKES 가 이 그림을 쓴다', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  ctx.trace = [];
  fx.drawZone(ctx, zone('haz', 'rock', 0, { id: 'zh', k: 'TOXICSPIKES', ty: 'POISON', t0: 9, t1: 1e9 }), 10);
  clean(ctx, 'haz');
  const mine = new RecCtx();
  mine.trace = [];
  fx.drawZone(mine, zone('haz', 'poison', 0, { id: 'zh', k: 'TEST', ty: 'POISON', t0: 9, t1: 1e9 }), 10);
  assert.equal(ctx.trace.join(' '), mine.trace.join(' '));
  assert.ok(ctx.fills.has(TYPE_FX.POISON[1]), '독 색 가시');
});

// ---------------------------------------------------------------- 7 벤치
class NopCtx {
  constructor() {
    Object.assign(this, { globalAlpha: 1, globalCompositeOperation: 'source-over', fillStyle: '#000000',
      strokeStyle: '#000000', lineWidth: 1, lineDashOffset: 0, lineCap: 'butt', lineJoin: 'miter',
      font: '10px sans-serif', textAlign: 'start', textBaseline: 'alphabetic' });
  }
  createRadialGradient() { return { addColorStop() {} }; }
}
for (const name of [...PLAIN, 'save', 'restore', 'translate', 'rotate', 'scale', 'arc', 'ellipse', 'drawImage', 'fillText',
  'strokeText', 'setLineDash']) {
  NopCtx.prototype[name] = function () {};
}

test('한 프레임 (2마리 · 이 집안 탄 20 · 장판 · 입자 400) 이 3 ms 안', (t) => {
  const fx = new Fx({ canvas: (w, h) => ({ width: w, height: h, getContext: () => new NopCtx() }) });
  const ctx = new NopCtx();
  const world = makeWorld('a');
  const shots = Array.from({ length: 20 }, (_, i) => ({ id: 'p' + i, o: 'a', k: i % 2 ? 'SLEEPPOWDER' : 'X',
    ty: TYPES[i % TYPES.length], sty: KEYS[i % KEYS.length], x: 500, y: 300 + i * 20, vx: 600, vy: -40, r: 16 }));
  const zones = [zone('cone', 'flame', 0, { t0: 0, t1: 1e9 }), zone('ring', 'zap', 1, { t0: 0, t1: 0 }),
    zone('haz', 'poison', 2, { k: 'TOXICSPIKES', t0: 0, t1: 1e9 }), zone('tele', 'zap', 3, { t0: 0, t1: 1e9 })];
  const hit = { e: 'hit', w: 'a', v: 'b', ty: 'FIRE', hpr: 500, eff: 2, crit: false, x: 1200, y: 450 };
  const run = (frames, now0) => {
    let parts = 0;
    const t0 = performance.now();
    for (let f = 0; f < frames; f++) {
      const now = now0 + f / 60;
      world.at.a.x = 400 + Math.sin(now) * 200;
      world.at.b.y = 450 + Math.cos(now) * 200;
      if (f % 30 === 0) fx.event({ e: 'cast', w: 'a', kind: 'melee', ty: 'FIRE', sty: KEYS[(f / 30) % 5], x: 400, y: 450, ang: 0 }, world);
      if (fx.counts().particles < 400) fx.event(hit, world);
      fx.update(1 / 60);
      for (const z of zones) fx.drawZone(ctx, z, now);
      fx.drawUnder(ctx);
      shots.forEach((p, i) => fx.drawProjectile(ctx, p, (p.x + now * 300 + i * 40) % 1600, p.y));
      fx.drawOver(ctx);
      parts += fx.counts().particles;
    }
    return { ms: (performance.now() - t0) / frames, parts: parts / frames };
  };
  run(240, 0);
  const { ms, parts } = run(1200, 10);
  t.diagnostic(`한 프레임 평균 ${ms.toFixed(3)} ms (입자 평균 ${parts.toFixed(0)}, 탄 20 - flame zap leaf powder poison, 장판 ${zones.length})`);
  assert.ok(parts >= 380, '입자가 400 언저리 (' + parts + ')');
  assert.ok(ms < 3, ms.toFixed(3) + ' ms');
});
