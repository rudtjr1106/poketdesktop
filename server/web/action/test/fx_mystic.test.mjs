/* 이펙트 모양 - mystic 집안 (js/fx/styles/mystic.js: psy ghost dark fairy orb beam) 검사.

     node --test server/web/action/test/

   무엇을 못 박나
     1. 집안 파일에는 여섯 키만, 훅은 core.HOOKS 이름만, checkStyle 이 깨끗하다.
     2. 여섯 모양 × 가진 훅 전부 (탄 · 꼬리 · 쏜 순간 · 맞음 · 장판 다섯 꼴의 표시 · 터짐 · 떨어짐 · 근접 · 돌진):
        예외 · NaN 없이, ctx 를 받은 그대로 돌려놓고, 화면 ctx 에서 그라디언트를 만들지 않는다 (훅을 바로 불러도, Fx 를 거쳐도).
     3. 같은 씨앗 · 같은 시각이면 같은 그림 (프레임마다 모양이 튀지 않는다), 씨앗이 다르면 다른 그림.
     4. 입자: 탄 하나가 1초에 흘리는 수 · 맞음 한 번 · 광선 한 번이 정한 만큼을 넘지 않고, 풀을 넘지 않고, 다 사라진다.
     5. 광선: 쏘기 전엔 입으로 모이는 알갱이, 사그라들 무렵 남는 빛을 한 번만, 다 쏜 뒤(e ≥ 1)엔 그리지 않는다.
     6. 근접 · 돌진: 준비 → 달림 → 끝을 다 지나고 입자 수가 정한 만큼, orb 는 부딪는 불티를 한 번만.
     7. 한 프레임 (mystic 탄 20 · 광선 · 고리 · 부채꼴 · 돌진 · 입자 400 언저리) 이 3 ms 안 (가짜 ctx). */
import test from 'node:test';
import assert from 'node:assert/strict';
import { Fx } from '../js/fx.js';
import { HOOKS, POOL_MAX, ZONE_KINDS, checkStyle } from '../js/fx/core.js';
import { FAMILIES, FAMILY_OF, styleDef } from '../js/fx/styles/index.js';
import { TYPE_FX } from '../js/consts.js';

const MINE = ['psy', 'ghost', 'dark', 'fairy', 'orb', 'beam'];
const NATURAL = { psy: 'PSYCHIC', ghost: 'GHOST', dark: 'DARK', fairy: 'FAIRY', orb: 'NORMAL', beam: 'ICE' };
const TYPES = Object.keys(TYPE_FX);
const mystic = FAMILIES.mystic;

// ---------------------------------------------------------------- 가짜 2D ctx (fx-hooks.test.mjs 와 같은 규칙 + 그림 지문)
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
    this.sig = 0;                     // 그림 지문 - 부른 이름 · 숫자 인자를 차례로 섞는다
    this.calls = 0;
    this.stack = [];
    this.st = {
      globalAlpha: 1, globalCompositeOperation: 'source-over', fillStyle: '#000000', strokeStyle: '#000000',
      lineWidth: 1, lineDashOffset: 0, lineCap: 'butt', lineJoin: 'miter', font: '10px sans-serif',
      textAlign: 'start', textBaseline: 'alphabetic', dash: [], moved: false,
    };
  }

  rec(name, args) {
    this.n[name] = (this.n[name] || 0) + 1;
    this.calls++;
    this.sig = (this.sig * 1.37 + name.length) % 1e9;     // 차례를 타는 지문 (대칭인 두 가닥도 갈린다)
    for (const a of args) {
      if (typeof a !== 'number') continue;
      if (!Number.isFinite(a)) throw new TypeError(`${name}: 숫자가 아니다 (${a})`);
      this.sig = (this.sig * 1.37 + a) % 1e9;
    }
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
}
for (const name of PLAIN) RecCtx.prototype[name] = function (...args) { this.rec(name, args); };
for (const [prop, ok] of Object.entries(PROPS)) {
  Object.defineProperty(RecCtx.prototype, prop, {
    get() { return this.st[prop]; },
    set(v) {
      if (!ok(v)) throw new TypeError(`${prop} = ${v}`);
      this.st[prop] = v;
    },
  });
}

// 아무것도 안 하는 ctx (재기용)
class NopCtx {
  constructor() {
    this.globalAlpha = 1;
    this.globalCompositeOperation = 'source-over';
  }
  createRadialGradient() { return { addColorStop() {} }; }
}
for (const name of [...PLAIN, 'save', 'restore', 'translate', 'rotate', 'scale', 'arc', 'ellipse', 'drawImage', 'fillText',
  'strokeText', 'setLineDash']) {
  NopCtx.prototype[name] = function () {};
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
  id: `m${kind}${sty}${i}`, o: i % 2 ? 'a' : 'b', k: 'MYSTIC', ty: NATURAL[sty] || TYPES[i % TYPES.length], sty, kind,
  x: 800, y: 450, r: kind === 'ring' ? 230 : kind === 'cone' ? 440 : 80, ang: 0.4, len: kind === 'beam' ? 900 : 440,
  w: kind === 'beam' ? 56 : kind === 'cone' ? 600 : 0, t0: 10, t1: 11, ...extra,
});

const shotOf = (sty, i, extra = {}) => ({ id: `ms${sty}${i}`, o: 'a', k: 'MYSTIC', ty: NATURAL[sty], sty, x: 0, y: 0,
  vx: 680, vy: -60, r: 16, ...extra });

// 모든 입자 생성을 센다 (fx.spawn · particle · burst · wave 가 다 지나는 풀에서)
function countSpawns(fx) {
  const parts = fx.parts, was = parts.spawn.bind(parts);
  const box = { n: 0 };
  parts.spawn = (...args) => {
    box.n++;
    return was(...args);
  };
  return box;
}

// ---------------------------------------------------------------- 1 목록
test('mystic.js 에는 여섯 키만, 훅은 아는 이름만, checkStyle 이 깨끗하다', () => {
  assert.deepEqual(Object.keys(mystic).sort(), [...MINE].sort());
  for (const sty of MINE) {
    assert.equal(FAMILY_OF[sty], 'mystic');
    assert.deepEqual(checkStyle(sty, mystic[sty]), [], sty);
    for (const name of Object.keys(mystic[sty])) assert.ok(name in HOOKS, `${sty}: 모르는 훅 ${name}`);
    assert.equal(styleDef(sty), mystic[sty]);
  }
  // 고른 그림의 범위: 근접 · 돌진이 있는 다섯 모양은 rush · swing 을, 장판을 쓰는 모양은 그 꼴을 가진다
  for (const sty of ['psy', 'ghost', 'dark', 'fairy', 'orb']) {
    for (const h of ['shot', 'launch', 'impact', 'rush', 'swing', 'ring']) assert.equal(typeof mystic[sty][h], 'function', `${sty}.${h}`);
  }
  for (const sty of ['psy', 'orb']) for (const h of ['tele', 'fall', 'cone']) assert.equal(typeof mystic[sty][h], 'function', `${sty}.${h}`);
  for (const sty of ['dark', 'fairy']) assert.equal(typeof mystic[sty].cone, 'function', `${sty}.cone`);
  assert.equal(typeof mystic.beam.beam, 'function');
});

// ---------------------------------------------------------------- 2 훅을 바로 · Fx 를 거쳐
test('여섯 모양 × 가진 훅 전부를 바로 불러도 예외 · NaN 없이 ctx 를 돌려놓는다 (그라디언트 없이)', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('b');
  fx.event({ e: 'phase', ph: 'fight' }, world);
  fx.update(1 / 60);
  for (const sty of MINE) {
    const def = mystic[sty];
    const q = fx.shotOf(shotOf(sty, 0), 600, 420);
    fx.event({ e: 'cast', w: 'a', k: 'X' + sty, kind: 'melee', ty: NATURAL[sty], sty, x: 400, y: 450, ang: 0, len: 220, r: 60 }, world);
    const a = fx.anims.findLast((v) => v.kind === 'rush');
    const run = (name, ...args) => {
      ctx.save();
      def[name](...args);
      ctx.restore();
      clean(ctx, `${sty}.${name}`);
    };
    for (const name of Object.keys(def)) {
      if (typeof def[name] !== 'function') continue;
      if (name === 'shot') for (const t of [0, 0.37, 1.9]) { fx.clock = t; run(name, fx, ctx, q); }
      else if (name === 'trail') run(name, fx, q, 1 / 60);
      else if (name === 'launch') run(name, fx, q);
      else if (name === 'impact') {
        for (const why of ['hit', 'tele', 'ring', 'cone', 'beam']) {
          for (const s of [0.75, 1, 1.35]) run(name, fx, 800, 450, 0.5, q.c, { why, k: 'X', ty: 'PSYCHIC', sty, eff: 1, crit: s > 1, s, r: why === 'ring' ? 200 : 0, len: 400 });
        }
        run(name, fx, 800, 450, 0.5, q.c, { why: 'ring', k: 'X', ty: 'PSYCHIC', sty, eff: 1, crit: false, s: 1, r: 0, len: 0 });
      } else if (name === 'fall') for (const v of [0, 0.4, 1]) run(name, fx, ctx, fx.zoneOf(zone('tele', sty, 1), 10.9), 800, 300, v);
      else if (name === 'rush') {
        for (const stage of ['wind', 'act', 'tail']) for (const sk of [0, 0.5, 1]) run(name, fx, ctx, { ...a, stage, sk, speed: 1200 });
      } else if (name === 'swing') {
        for (const stage of ['act', 'tail']) for (const t of [0, 0.3, 0.7, 0.99]) run(name, fx, ctx, { ...a, stage, sk: t, mem: {} }, t);
        for (const mk of ['melee', 'dash']) run(name, fx, ctx, { ...a, mk, stage: 'tail', sk: 0.5, mem: {} }, 0.6);
      } else if (ZONE_KINDS.includes(name)) {
        for (const now of [10, 10.2, 10.9, 11, 11.05, 11.15, 11.24, 11.4, 12]) {
          run(name, fx, ctx, fx.zoneOf(zone(name, sty, 2), now));
          run(name, fx, ctx, fx.zoneOf(zone(name, sty, 3, { w: 0, r: 30, len: 60 }), now));   // 작은 장판
        }
      } else assert.fail(`${sty}.${name}: 검사가 모르는 훅`);
    }
  }
  assert.equal(ctx.n.createRadialGradient, undefined, '화면 ctx 에서 그라디언트를 만들지 않는다');
  assert.ok(fx.counts().particles <= POOL_MAX);
});

test('Fx 를 거쳐: 탄 · 장판 다섯 꼴 · 근접 · 돌진 · 맞음이 깨끗하게 돌고, 입자는 다 사라진다', () => {
  const { fx, sprites } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('a');
  MINE.forEach((sty, i) => {
    const ty = NATURAL[sty], k = 'K' + sty;
    fx.event({ e: 'cast', w: 'a', m: 0, k, kind: 'proj', ty, sty, x: 400, y: 450, ang: 0 }, world);
    for (let f = 0; f < 30; f++) {
      fx.drawProjectile(ctx, shotOf(sty, i), 500 + f * 11, 400 - f);
      clean(ctx, `drawProjectile ${sty}`);
      frame(fx, ctx);
    }
    for (const [eff, crit] of [[2, true], [1, false], [0.5, false], [0, false]]) {
      fx.event({ e: 'hit', w: 'a', v: 'b', k, ty, dmg: 12, hpr: 500, eff, crit, x: 1200, y: 450 }, world);
    }
    for (const kind of ZONE_KINDS) {
      for (let f = 0; f <= 80; f++) {
        const now = 9.95 + f * 0.02;
        fx.drawZone(ctx, zone(kind, sty, i, { t1: kind === 'haz' ? 1e9 : 11, o: f % 2 ? 'a' : 'b' }), now);
        clean(ctx, `drawZone ${kind}/${sty}@${now}`);
        frame(fx, ctx, 0.02);
      }
    }
    for (const [mk, len, r] of [['melee', 220, 60], ['dash', 440, 30]]) {
      world.at.a.x = 400;
      fx.event({ e: 'cast', w: 'a', m: 1, k, kind: mk, ty, sty, x: 400, y: 450, ang: 0.3, len, r }, world);
      for (let f = 0; f < 40; f++) {
        if (f > 6 && f < 16) world.at.a.x += 25;
        frame(fx, ctx);
      }
    }
    world.at.a.x = 400;
  });
  assert.ok(fx.counts().particles <= POOL_MAX);
  for (let f = 0; f < 60; f++) frame(fx, ctx, 0.05);
  assert.deepEqual(fx.counts(), { particles: 0, anims: 0, texts: 0 }, '다 사라진다');
  assert.equal(ctx.n.createRadialGradient, undefined);
  assert.ok(sprites.every((s) => (s.n.createRadialGradient || 0) <= 1), '스프라이트는 색마다 한 번');
});

// ---------------------------------------------------------------- 3 같은 씨앗이면 같은 그림
test('같은 씨앗 · 같은 시각이면 같은 그림, 씨앗이 다르면 다른 그림', () => {
  const { fx } = newFx();
  fx.event({ e: 'phase' }, makeWorld('a'));
  fx.update(0.2);
  fx.dt = 0;                                       // 그리는 김에 뿌리는 입자 없이 (그림만 견준다)
  const sig = (q) => {
    const ctx = new RecCtx();
    ctx.save();
    styleDef(q.sty).shot(fx, ctx, q);
    ctx.restore();
    return ctx.sig;
  };
  for (const sty of MINE) {
    const a = fx.shotOf(shotOf(sty, 1, { id: 101 }), 600, 400), b = fx.shotOf(shotOf(sty, 2, { id: 202 }), 600, 400);
    const s1 = sig(a), s2 = sig(a);
    assert.equal(s1, s2, `${sty}: 같은 프레임 두 번 - 같은 그림`);
    assert.notEqual(sig(a), sig(b), `${sty}: 씨앗이 다르면 다르다`);
    fx.clock += 0.05;
    assert.notEqual(sig(a), s1, `${sty}: 시간이 흐르면 움직인다`);
  }
});

// ---------------------------------------------------------------- 4 입자 수
test('입자: 탄 꼬리 · 맞음 · 광선 한 번이 정한 만큼을 넘지 않는다', () => {
  for (const sty of MINE) {
    const { fx } = newFx();
    const ctx = new NopCtx();
    fx.event({ e: 'phase' }, makeWorld('a'));
    const box = countSpawns(fx);
    for (let f = 0; f < 60; f++) {                 // 1초 동안 탄 하나
      fx.update(1 / 60);
      fx.drawProjectile(ctx, shotOf(sty, 0), 300 + f * 11, 400);
    }
    assert.ok(box.n > 5, `${sty}: 꼬리 입자가 나온다 (${box.n})`);
    assert.ok(box.n <= 90, `${sty}: 탄 하나가 1초에 ${box.n} 개 (≤ 90)`);
    box.n = 0;
    const c = { light: '#ffffff', dark: '#808080' };
    styleDef(sty).impact(fx, 800, 450, 0, c, { why: 'hit', k: 'X', ty: 'NORMAL', sty, eff: 2, crit: true, s: 1.35, r: 0, len: 0 });
    assert.ok(box.n > 3 && box.n <= 70, `${sty}: 세게 맞음 한 번 ${box.n} 개 (≤ 70)`);
    box.n = 0;
    styleDef(sty).impact(fx, 800, 450, 0, c, { why: 'ring', k: 'X', ty: 'NORMAL', sty, eff: 1, crit: false, s: 1, r: 230, len: 230 });
    assert.ok(box.n <= 70, `${sty}: 고리 터짐 ${box.n} 개 (≤ 70)`);
    assert.ok(fx.counts().particles <= POOL_MAX);
  }
  // 광선 한 번 (모으기 0.9초 + 쏘기 0.25초 + 남는 빛)
  const { fx } = newFx();
  const ctx = new NopCtx();
  fx.event({ e: 'phase' }, makeWorld('a'));
  const box = countSpawns(fx);
  for (let f = 0; f <= 75; f++) {
    fx.update(1 / 60);
    fx.drawZone(ctx, zone('beam', 'beam', 0, { t0: 10, t1: 10.9 }), 10 + f / 60);
  }
  assert.ok(box.n > 40 && box.n <= 260, `광선 한 번 ${box.n} 개 (≤ 260)`);
});

// ---------------------------------------------------------------- 5 광선
test('광선: 모으는 동안 입으로 빨려 드는 알갱이, 사그라들 무렵 남는 빛을 한 번, 다 쏜 뒤엔 그리지 않는다', () => {
  const { fx } = newFx();
  fx.event({ e: 'phase' }, makeWorld('a'));
  fx.update(1 / 60);
  const ctx = new RecCtx();
  const beam = mystic.beam.beam;
  // 모으기 - 알갱이는 입 밖에서 입 쪽으로 간다
  const q = fx.zoneOf(zone('beam', 'beam', 7), 10.7);
  assert.equal(q.phase, 'mark');
  const before = new Set(fx.parts.all.filter((p) => p.on));
  for (let i = 0; i < 30; i++) {
    ctx.save();
    beam(fx, ctx, q);
    ctx.restore();
  }
  const born = fx.parts.all.filter((p) => p.on && !before.has(p));
  assert.ok(born.length >= 10, '모이는 알갱이 ' + born.length);
  for (const p of born) {
    const dx = q.x - p.x, dy = q.y - p.y;
    assert.ok(Math.hypot(dx, dy) > 30, '입 밖에서 나온다');
    assert.ok(p.vx * dx + p.vy * dy > 0, '입 쪽으로 간다');
  }
  // 쏘기 - 한창일 땐 광선이 제 빛 (남는 빛이 띠를 하얗게 덮지 않게), 사그라들 무렵 남는 빛 (긴 line 둘) 을 한 번만
  const lines = () => fx.parts.all.filter((p) => p.on && p.shape === 'line' && Math.hypot(p.x2 - p.x, p.y2 - p.y) > 800).length;
  const draw = (now) => {
    ctx.save();
    beam(fx, ctx, fx.zoneOf(zone('beam', 'beam', 7), now));
    ctx.restore();
  };
  const f = fx.zoneOf(zone('beam', 'beam', 7), 11.05);
  assert.equal(f.phase, 'fire');
  draw(11.05);
  assert.equal(lines(), 0, '한창일 땐 남는 빛이 없다');
  draw(11.2);
  assert.equal(lines(), 2, '남는 빛 둘');
  for (let i = 0; i < 5; i++) draw(11.22);
  assert.equal(lines(), 2, '두 번 남지 않는다');
  const drew = ctx.calls;
  ctx.save();
  beam(fx, ctx, fx.zoneOf(zone('beam', 'beam', 7), 12));
  ctx.restore();
  assert.equal(ctx.calls - drew, 2, '다 쏜 뒤(e ≥ 1)엔 save/restore 밖에 없다');
  clean(ctx, 'beam');
});

// ---------------------------------------------------------------- 6 근접 · 돌진
test('근접 · 돌진: 준비 → 달림 → 끝, 입자 수가 정한 만큼, orb 는 부딪는 불티를 한 번만', () => {
  for (const sty of ['psy', 'ghost', 'dark', 'fairy', 'orb']) {
    const { fx } = newFx();
    const ctx = new RecCtx();
    const world = makeWorld('a');
    fx.event({ e: 'cast', w: 'a', k: 'T', kind: 'melee', ty: NATURAL[sty], sty, x: 400, y: 450, ang: 0, len: 220, r: 60 }, world);
    const a = fx.anims.find((v) => v.kind === 'rush');
    const box = countSpawns(fx);
    const stages = new Set();
    for (let f = 0; f < 40 && fx.anims.includes(a); f++) {
      if (f > 10 && f < 22) world.at.a.x += 18;
      frame(fx, ctx);
      stages.add(a.stage);
    }
    assert.deepEqual([...stages], ['wind', 'act', 'tail'], sty);
    assert.ok(box.n <= 120, `${sty}: 근접 한 번 ${box.n} 개`);
    if (sty === 'orb') {
      assert.equal(a.mem.boom, true, 'orb 는 끝에서 부딪는다');
    }
  }
  // orb 의 부딪는 불티는 swing 을 몇 번 불러도 한 번
  const { fx } = newFx();
  const ctx = new RecCtx();
  fx.event({ e: 'cast', w: 'a', k: 'T', kind: 'dash', ty: 'NORMAL', sty: 'orb', x: 400, y: 450, ang: 0, len: 440, r: 30 }, makeWorld());
  const a = { ...fx.anims.find((v) => v.kind === 'rush'), stage: 'tail', sk: 0.2, mem: {} };
  const box = countSpawns(fx);
  for (let i = 0; i < 5; i++) {
    ctx.save();
    mystic.orb.swing(fx, ctx, a, 0.7);
    ctx.restore();
  }
  assert.ok(box.n > 0 && box.n <= 20, '불티 한 번 ' + box.n);
});

// ---------------------------------------------------------------- 7 재기
test('한 프레임 (mystic 탄 20 · 광선 · 고리 · 부채꼴 · 돌진 · 입자 400 언저리) 이 3 ms 안', (t) => {
  const fx = new Fx({ canvas: (w, h) => ({ width: w, height: h, getContext: () => new NopCtx() }) });
  const ctx = new NopCtx();
  const world = makeWorld('a');
  const shots = Array.from({ length: 20 }, (_, i) => shotOf(MINE[i % MINE.length], i, { y: 120 + i * 35 }));
  const cyc = (kind, sty, i, now, wind, period) => {
    const n = Math.floor(now / period), t0 = n * period;
    return zone(kind, sty, i * 1000 + n, { t0, t1: t0 + wind });
  };
  const hit = (sty) => ({ e: 'hit', w: 'a', v: 'b', k: 'B' + sty, ty: NATURAL[sty], sty, hpr: 500, eff: 2, crit: false, x: 1200, y: 450 });
  const run = (frames, now0) => {
    let parts = 0;
    const t0 = performance.now();
    for (let f = 0; f < frames; f++) {
      const now = now0 + f / 60;
      world.at.a.x = 400 + Math.sin(now * 3) * 200;
      world.at.b.y = 450 + Math.cos(now) * 200;
      if (f % 30 === 0) fx.event({ e: 'cast', w: 'a', kind: 'melee', ty: 'NORMAL', sty: 'orb', x: 400, y: 450, ang: 0, len: 220, r: 60 }, world);
      if (f % 45 === 0) fx.event({ e: 'cast', w: 'b', kind: 'dash', ty: 'GHOST', sty: 'ghost', x: 1200, y: 450, ang: 3, len: 440, r: 30 }, world);
      if (fx.counts().particles < 400) fx.event(hit(MINE[f % MINE.length]), world);
      fx.update(1 / 60);
      fx.drawZone(ctx, cyc('beam', 'beam', 1, now, 0.9, 1.3), now);
      fx.drawZone(ctx, cyc('ring', 'psy', 2, now, 0.55, 0.9), now);
      fx.drawZone(ctx, cyc('cone', 'fairy', 3, now, 0.6, 1.0), now);
      fx.drawZone(ctx, cyc('tele', 'orb', 4, now, 1.0, 1.4), now);
      fx.drawUnder(ctx);
      shots.forEach((p, i) => fx.drawProjectile(ctx, p, (100 + now * 300 + i * 70) % 1600, p.y));
      fx.drawOver(ctx);
      parts += fx.counts().particles;
    }
    return { ms: (performance.now() - t0) / frames, parts: parts / frames };
  };
  run(240, 0);                                     // 데우기
  const { ms, parts } = run(1200, 10);
  t.diagnostic(`mystic 한 프레임 평균 ${ms.toFixed(3)} ms (입자 평균 ${parts.toFixed(0)}, 탄 20, 장판 4, 돌진 2)`);
  assert.ok(parts >= 300, '입자가 400 언저리 (' + parts.toFixed(0) + ')');
  assert.ok(ms < 3, ms.toFixed(3) + ' ms');
});
