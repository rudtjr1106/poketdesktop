/* 이펙트 몸 집안 검사 (js/fx/styles/body.js - punch slash bite rock quake web heal buff shield + GENERIC · AURA).

     node --test server/web/action/test/

   무엇을 못 박나
     1. 아홉 모양 × 가진 훅 전부 (+ GENERIC rush · swing, AURA): Fx 가 만든 q · a 로 바로 불러도, Fx 를 거쳐 판을 돌려도
        예외 · NaN 없이, 그리기마다 ctx 를 받은 그대로 돌려놓고, 화면 ctx 에서 그라디언트를 만들지 않는다.
     2. 입자 수: 훅 하나 · 근접 하나가 뿌리는 입자는 정해진 만큼 안, 다 끝나면 0 으로.
     3. 근접 타격 그림 고르기 (swingKind) - 기술 키 · 돌진.
     4. 멈춘 순간 (a.mem.bt) 은 한 번만 - 맞아서 일찍 서면 달림이 끝나기 전에, 안 서면 달림이 끝날 때.
     5. 같은 탄 · 장판 · 시각이면 같은 그림 (Math.random 은 입자에만).
     6. 한 프레임 (2마리 근접 · 몸 집안 탄 20 · 장판 · 입자 400 언저리) 이 3 ms 안. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { Fx, POOL_MAX } from '../js/fx.js';
import { BODY_R, HOOKS, ZONE_KINDS } from '../js/fx/core.js';
import { FAMILIES, hookOf, styleDef } from '../js/fx/styles/index.js';
import body, { AURA, GENERIC, laneHW, swingKind } from '../js/fx/styles/body.js';
import { TYPE_FX } from '../js/consts.js';

const TYPES = Object.keys(TYPE_FX);
const MINE = ['punch', 'slash', 'bite', 'rock', 'quake', 'web', 'heal', 'buff', 'shield'];

// ---------------------------------------------------------------- 가짜 2D ctx (fx-hooks.test.mjs 와 같은 규칙)
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
  'fill', 'fillRect', 'strokeRect', 'clip'];

class RecCtx {
  constructor() {
    this.n = Object.create(null);
    this.trace = null;                // 배열을 주면 부른 이름 · 숫자를 차례로 적는다
    this.strokes = [];                // 긋기마다 그때 색
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
    if (this.trace) this.trace.push(name + args.map((a) => (typeof a === 'number' ? a.toFixed(3) : '')).join(','));
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
  stroke() {
    this.rec('stroke', []);
    this.strokes.push(this.st.strokeStyle);
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

// 훅 하나를 core 처럼 save/restore 로 감싸 부른다
function call(ctx, what, hook, ...args) {
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  hook(...args);
  ctx.restore();
  clean(ctx, what);
}

// 입자 풀에 새로 뿌린 수를 센다
function spawnCounter(fx) {
  const parts = fx.parts, spawn = parts.spawn.bind(parts), box = { n: 0 };
  parts.spawn = (...a) => {
    box.n += 1;
    return spawn(...a);
  };
  return box;
}

const zone = (kind, sty, i = 0, extra = {}) => ({
  id: `zb${kind}${sty}${i}`, o: i % 2 ? 'a' : 'b', k: 'TEST', ty: TYPES[i % TYPES.length], sty, kind,
  x: 800, y: 450, r: 90, ang: 0.4, len: 420, w: 300, t0: 10, t1: 11, ...extra,
});

// 근접 · 돌진 한 번: 준비 → 1초에 1200 u 로 달리다 stopAt 거리에서 선다 (엔진은 상대에게 닿는 자리에서 세운다)
function rushOnce(fx, ctx, world, { sty, k, mk = 'melee', ty = 'NORMAL', ang = 0, len = 220, r = 60, stopAt = 1e9, frames = 40 }) {
  world.at.a.x = 400;
  world.at.a.y = 450;
  fx.event({ e: 'cast', w: 'a', m: 0, k, kind: mk, ty, sty, x: 400, y: 450, ang, len, r }, world);
  const a = fx.anims.at(-1);
  const wind = mk === 'dash' ? 5 : 12, v = mk === 'dash' ? 25 : 20;
  let ran = 0;
  for (let f = 0; f < frames; f++) {
    if (f >= wind && ran < Math.min(len, stopAt)) {
      const d = Math.min(v, Math.min(len, stopAt) - ran);
      ran += d;
      world.at.a.x += Math.cos(ang) * d;
      world.at.a.y += Math.sin(ang) * d;
    }
    frame(fx, ctx, 1 / 60);
  }
  return a;
}

// ---------------------------------------------------------------- 1 · 2 훅 전부
test('몸 집안: 아홉 모양만, 훅 이름은 core.HOOKS 대로', () => {
  assert.deepEqual(Object.keys(body).sort(), [...MINE].sort());
  assert.equal(FAMILIES.body, body);
  for (const k of MINE) {
    for (const name of Object.keys(body[k])) assert.ok(name in HOOKS, `${k}.${name}`);
    assert.equal(typeof body[k].shot, 'function');
  }
  assert.equal(typeof GENERIC.rush, 'function');
  assert.equal(typeof GENERIC.swing, 'function');
  assert.deepEqual(Object.keys(AURA).sort(), ['buff', 'heal', 'shield']);
});

test('아홉 모양 × 가진 훅을 바로 불러도 (Fx 가 만든 q · a) 예외 · NaN 없이, 깨끗하게, 그라디언트 없이', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('b');
  fx.event({ e: 'phase', ph: 'fight' }, world);
  fx.update(0.4);
  const keys = { punch: ['CLOSECOMBAT', 'MACHPUNCH'], slash: ['NIGHTSLASH', 'XSCISSOR', 'SHADOWCLAW'], bite: ['CRUNCH'],
    rock: ['HEADSMASH', 'ACCELEROCK', 'STONEEDGE', 'ROCKSLIDE'], quake: ['STOMPINGTANTRUM', 'EARTHQUAKE'], web: ['STICKYWEB'],
    heal: ['RECOVER'], buff: ['SWORDSDANCE'], shield: ['PROTECT'] };
  let i = 0;
  for (const sty of MINE) {
    for (const k of keys[sty]) {
      for (const ty of [TYPES[i % TYPES.length], 'ELECTRIC']) {
        i += 1;
        const box = spawnCounter(fx);
        const q = fx.shotOf({ id: `pb${sty}${i}`, o: 'a', k, ty, sty, vx: 500, vy: 120, r: 18 }, 600, 420);
        for (const name of Object.keys(HOOKS)) {
          const hook = hookOf(sty, name);
          if (typeof hook !== 'function') continue;
          const what = `${sty}.${name} (${k})`;
          if (name === 'shot') for (const age of [0, 0.2, 0.9]) { q.age = age; call(ctx, what, hook, fx, ctx, q); }
          else if (name === 'trail') hook(fx, q, 1 / 60);
          else if (name === 'launch') hook(fx, q);
          else if (name === 'impact') {
            for (const why of ['hit', 'tele', 'ring', 'cone', 'beam']) {
              hook(fx, 800, 450, 0.5, q.c, { why, k, ty, sty, eff: 2, crit: true, s: 1.35, r: 90, len: 400 });
            }
          } else if (name === 'fall') {
            for (const v of [0, 0.3, 0.75, 1]) call(ctx, what, hook, fx, ctx, fx.zoneOf(zone('tele', sty, i, { k, ty }), 10.9), 800, 300, v);
          } else if (name === 'rush' || name === 'swing') {
            for (const mk of ['melee', 'dash']) {
              fx.event({ e: 'cast', w: 'a', m: 0, k, kind: mk, ty, sty, x: 400, y: 450, ang: 0.3, len: 220, r: mk === 'dash' ? 30 : 60 }, world);
              const a = fx.anims.at(-1);
              if (name === 'rush') for (const stage of ['wind', 'act', 'act', 'tail']) call(ctx, what, hook, fx, ctx, { ...a, stage, sk: 0.5, speed: 1200 });
              else for (const t of [0, 0.2, 0.5, 0.6, 0.8, 0.99]) call(ctx, what, hook, fx, ctx, a, t);
            }
          } else if (ZONE_KINDS.includes(name)) {
            for (const now of [10.1, 10.5, 10.9, 11.0, 11.05, 11.2, 11.5]) {
              call(ctx, `${what} @${now}`, hook, fx, ctx, fx.zoneOf(zone(name, sty, i, { k, ty, t1: name === 'haz' ? 1e9 : 11 }), now));
            }
          }
        }
        assert.ok(box.n < 400, `${sty} (${k}): 한 바퀴에 입자 ${box.n}`);
      }
    }
  }
  assert.equal(ctx.n.createRadialGradient, undefined, '화면 ctx 에서 그라디언트를 만들지 않는다');
  assert.ok(ctx.n.drawImage > 100 && ctx.n.fill > 100 && ctx.n.stroke > 100, '그렸다');
});

test('GENERIC · AURA: 모든 단계 · 때에서 깨끗하게', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('a');
  for (const [k, mk] of [['TACKLE', 'melee'], ['DRAGONCLAW', 'melee'], ['SUPERFANG', 'melee'], ['MEGAKICK', 'melee'],
    ['CUT', 'melee'], ['XSCISSOR', 'melee'], ['QUICKATTACK', 'dash'], [undefined, 'melee']]) {
    fx.event({ e: 'cast', w: 'a', m: 0, k, kind: mk, ty: 'DRAGON', sty: 'zzz', x: 400, y: 450, ang: -2, len: 300, r: 60 }, world);
    const a = fx.anims.at(-1);
    for (const stage of ['wind', 'act', 'tail']) {
      for (const sk of [0, 0.5, 1]) call(ctx, `GENERIC.rush ${k} ${stage}`, GENERIC.rush, fx, ctx, { ...a, stage, sk, speed: 1000 });
    }
    for (const t of [0, 0.1, 0.4, 0.56, 0.7, 0.9, 0.999]) call(ctx, `GENERIC.swing ${k} ${t}`, GENERIC.swing, fx, ctx, a, t);
  }
  const bare = { x: 500, y: 400, ang: 0, ux: 1, uy: 0, c: { light: '#ffffff', dark: '#888888' }, reach: NaN, len: undefined,
    trail: { n: 0 }, mem: {}, stage: 'act', sk: 0.3, speed: NaN, go: null, act: undefined, life: 0.5, seed: undefined, mk: 'melee' };
  call(ctx, 'GENERIC.swing 빈 칸', GENERIC.swing, fx, ctx, bare, 0.7);
  for (const name of Object.keys(AURA)) {
    for (const key of ['', 'SWORDSDANCE']) {
      for (const t of [0, 0.1, 0.5, 0.9, 1]) {
        call(ctx, `AURA.${name} ${t}`, AURA[name], fx, ctx, { x: 600, y: 400, c: { light: '#ffd0a0', dark: '#ff7a2e' }, seed: 2.2, k: key }, t);
      }
    }
  }
  call(ctx, 'AURA 색 없음', AURA.buff, fx, ctx, { x: 1, y: 2, t: 0.5 }, 0.5);
  assert.equal(ctx.n.createRadialGradient, undefined);
});

test('Fx 를 거쳐: 아홉 모양의 탄 · 장판 · 근접 · 돌진 · 맞음, 다 끝나면 입자 0', () => {
  const { fx, sprites } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('a');
  const box = spawnCounter(fx);
  let most = 0;
  MINE.forEach((sty, i) => {
    const ty = TYPES[(i * 5) % TYPES.length], k = 'K' + sty;
    fx.event({ e: 'cast', w: 'a', m: 0, k, kind: 'proj', ty, sty, x: 400, y: 450, ang: 0 }, world);
    for (let f = 0; f < 8; f++) {
      fx.drawProjectile(ctx, { id: `pp${sty}`, o: f % 2 ? 'a' : 'b', k, ty, sty, x: 0, y: 0, vx: 600, vy: -40, r: 16 }, 500 + f * 10, 400 - f);
      clean(ctx, `drawProjectile ${sty}`);
      frame(fx, ctx, 1 / 30);
    }
    fx.event({ e: 'hit', w: 'a', v: 'b', k, ty, dmg: 12, hpr: 500, eff: 2, crit: true, x: 1200, y: 450 }, world);
    for (const kind of ZONE_KINDS) {
      for (const now of [10, 10.4, 10.8, 10.95, 11, 11.05, 11.1, 11.2, 11.3]) {
        fx.drawZone(ctx, zone(kind, sty, i, { k, ty, t1: kind === 'haz' ? 1e9 : 11 }), now);
        clean(ctx, `drawZone ${kind}/${sty}@${now}`);
        frame(fx, ctx, 0.03);
      }
    }
    for (const [mk, stopAt] of [['melee', 150], ['melee', 1e9], ['dash', 300]]) {
      const before = box.n;
      rushOnce(fx, ctx, world, { sty, k, mk, ty, ang: 0.3 * i, stopAt });
      most = Math.max(most, box.n - before);
    }
    assert.ok(fx.counts().particles <= POOL_MAX);
  });
  for (let f = 0; f < 60; f++) frame(fx, ctx, 0.05);
  assert.deepEqual(fx.counts(), { particles: 0, anims: 0, texts: 0 }, '다 사라진다');
  assert.ok(most > 10 && most < 260, '근접 하나가 뿌리는 입자 ' + most);
  assert.equal(ctx.n.createRadialGradient, undefined);
  assert.ok(sprites.every((s) => (s.n.createRadialGradient || 0) <= 1));
});

// ---------------------------------------------------------------- 3 · 4 타격 그림 · 멈춘 순간
test('swingKind: 돌진 · 손톱 · 이빨 · 가위 · 칼 · 주먹 · 나머지 몸통박치기', () => {
  const kind = (k, mk = 'melee') => swingKind({ k, mk });
  assert.equal(kind('QUICKATTACK', 'dash'), 'dash');
  assert.equal(kind('MACHPUNCH', 'dash'), 'dash');
  for (const k of ['SCRATCH', 'DRAGONCLAW', 'SHADOWCLAW', 'CRUSHCLAW', 'METALCLAW', 'FURYSWIPES', 'DIRECLAW']) assert.equal(kind(k), 'claw', k);
  for (const k of ['BITE', 'CRUNCH', 'FIREFANG', 'SUPERFANG', 'BUGBITE', 'JAWLOCK']) assert.equal(kind(k), 'jaw', k);
  for (const k of ['XSCISSOR', 'CROSSPOISON']) assert.equal(kind(k), 'cross', k);
  for (const k of ['SLASH', 'NIGHTSLASH', 'LEAFBLADE', 'CUT', 'SACREDSWORD', 'STONEAXE', 'RAZORSHELL', 'CEASELESSEDGE']) assert.equal(kind(k), 'blade', k);
  for (const k of ['FIREPUNCH', 'MEGAKICK', 'STOMP', 'DRAGONHAMMER', 'POUND', 'KARATECHOP']) assert.equal(kind(k), 'fist', k);
  for (const k of ['TACKLE', 'BODYSLAM', 'TAKEDOWN', 'DOUBLEEDGE', 'GIGAIMPACT', 'TRIPLEAXEL', undefined, 3]) assert.equal(kind(k), 'charge', String(k));
});

test('멈춘 순간은 한 번 - 맞아서 서면 달림이 끝나기 전에, 안 서면 달림이 끝날 때', () => {
  for (const sty of ['punch', 'slash', 'bite', 'rock', 'quake']) {
    const { fx } = newFx();
    const ctx = new RecCtx();
    const world = makeWorld('a');
    const box = spawnCounter(fx);
    const early = rushOnce(fx, ctx, world, { sty, k: 'X', stopAt: 120, frames: 30 });
    assert.ok(early.mem.bt !== undefined, `${sty}: 멈췄다`);
    assert.ok(early.mem.bt < early.mem.tA, `${sty}: 서자마자 (${early.mem.bt} < ${early.mem.tA})`);
    const late = rushOnce(fx, ctx, world, { sty, k: 'X', frames: 30 });
    assert.ok(late.mem.bt >= late.mem.tA - 1e-9, `${sty}: 다 달리고 (${late.mem.bt})`);
    // 한 번 정한 순간은 그대로 - 다시 그려도 터지지 않는다
    const bt = late.mem.bt, n = box.n;
    GENERIC.swing(fx, ctx, late, 0.9);
    assert.equal(late.mem.bt, bt);
    assert.ok(box.n - n < 5, '또 터지지 않는다 ' + (box.n - n));
  }
});

test('준비 동안 갈 길: 상대 것은 빨간 점선, 내 것은 제 색', () => {
  const warn = (you) => {
    const { fx } = newFx();
    const ctx = new RecCtx();
    const world = makeWorld(you);
    fx.event({ e: 'cast', w: 'a', m: 0, k: 'CRUNCH', kind: 'melee', ty: 'DARK', sty: 'bite', x: 400, y: 450, ang: 0, len: 220, r: 60 }, world);
    for (let f = 0; f < 6; f++) frame(fx, ctx, 1 / 60);
    return ctx.strokes.filter((c) => c === '#ff4f5e').length;
  };
  assert.ok(warn('b') > 0, '상대 것');
  assert.equal(warn('a'), 0, '내 것');
});

test('맞는 띠의 반폭: melee r · dash r + 몸 (상대 몸이 닿으면 맞는다)', () => {
  assert.equal(laneHW({ reach: 60 + BODY_R }), 60);
  assert.equal(laneHW({ reach: 30 + 2 * BODY_R }), 30 + BODY_R);
  assert.ok(laneHW({}) > 0 && laneHW({ reach: 0 }) > 0);
});

// ---------------------------------------------------------------- 5 같은 것은 같은 그림
test('같은 탄 · 장판 · 시각이면 같은 그림 (그리는 데 Math.random 을 쓰지 않는다)', () => {
  const trace = (draw) => {
    const { fx } = newFx();
    fx.update(0.37);
    const ctx = new RecCtx();
    ctx.trace = [];
    draw(fx, ctx);
    return ctx.trace.join(' ');
  };
  for (const sty of MINE) {
    const shot = (fx, ctx) => fx.drawProjectile(ctx, { id: 'same', o: 'a', k: 'K', ty: 'ROCK', sty, x: 0, y: 0, vx: 400, vy: 90, r: 16 }, 600, 400);
    assert.equal(trace(shot), trace(shot), sty + ' 탄');
    for (const kind of ZONE_KINDS) {
      for (const now of [10.5, 11.05]) {
        const z = (fx, ctx) => fx.drawZone(ctx, zone(kind, sty, 3, { id: 'same', k: 'STONEEDGE', t1: kind === 'haz' ? 1e9 : 11 }), now);
        assert.equal(trace(z), trace(z), `${sty} ${kind} @${now}`);
      }
    }
  }
});

// ---------------------------------------------------------------- 6 빠르기
class NopCtx {
  constructor() {
    this.globalAlpha = 1;
    this.globalCompositeOperation = 'source-over';
  }
  createRadialGradient() { return { addColorStop() {} }; }
}
for (const name of [...PLAIN, 'stroke', 'save', 'restore', 'translate', 'rotate', 'scale', 'arc', 'ellipse', 'drawImage', 'fillText',
  'strokeText', 'setLineDash']) {
  NopCtx.prototype[name] = function () {};
}

test('한 프레임 (근접 둘 · 몸 집안 탄 20 · 장판 넷 · 입자 400 언저리) 이 3 ms 안', (t) => {
  const fx = new Fx({ canvas: (w, h) => ({ width: w, height: h, getContext: () => new NopCtx() }) });
  const ctx = new NopCtx();
  const world = makeWorld('a');
  const shots = Array.from({ length: 20 }, (_, i) => ({ id: 'bp' + i, o: 'a', k: 'K', ty: TYPES[i % TYPES.length],
    sty: MINE[i % MINE.length], x: 100 + i * 60, y: 200 + (i % 5) * 120, vx: 420, vy: -60, r: 14 + (i % 3) * 4 }));
  const zones = [zone('ring', 'quake', 0, { t0: 0, t1: 1e9, r: 250 }), zone('tele', 'rock', 1, { t0: 0, t1: 1e9, k: 'ROCKSLIDE' }),
    zone('haz', 'web', 2, { t0: 0, t1: 1e9 }), zone('haz', 'rock', 3, { t0: 0, t1: 1e9, k: 'STEALTHROCK' })];
  const keys = ['CLOSECOMBAT', 'NIGHTSLASH', 'CRUNCH', 'HEADSMASH', 'STOMPINGTANTRUM', 'MACHPUNCH'];
  const run = (frames, now0) => {
    let parts = 0;
    const t0 = performance.now();
    for (let f = 0; f < frames; f++) {
      const now = now0 + f / 60, ph = f % 30;
      if (ph === 0) {
        for (const s of ['a', 'b']) {
          const i = (f / 30 + (s === 'b' ? 3 : 0)) % keys.length, k = keys[i];
          world.at[s].x = s === 'a' ? 400 : 1200;
          fx.event({ e: 'cast', w: s, k, kind: k === 'MACHPUNCH' ? 'dash' : 'melee', ty: 'FIGHTING', sty: MINE[i % 5],
            x: world.at[s].x, y: 450, ang: s === 'a' ? 0 : Math.PI, len: 220, r: 60 }, world);
        }
      }
      if (ph >= 12 && ph < 23) {                  // 달린다 - 1초에 1200 u
        world.at.a.x += 20;
        world.at.b.x -= 20;
      }
      if (fx.counts().particles < 400) fx.event({ e: 'hit', w: 'a', v: 'b', ty: 'ROCK', hpr: 500, eff: 2, crit: false, x: 1200, y: 450 }, world);
      fx.update(1 / 60);
      for (const z of zones) fx.drawZone(ctx, z, now);
      fx.drawUnder(ctx);
      shots.forEach((p, i) => fx.drawProjectile(ctx, p, (p.x + now * 300 + i * 40) % 1600, p.y));
      fx.drawOver(ctx);
      parts += fx.counts().particles;
    }
    return { ms: (performance.now() - t0) / frames, parts: parts / frames };
  };
  run(240, 0);                                     // 데우기
  const { ms, parts } = run(1200, 10);
  t.diagnostic(`몸 집안 한 프레임 평균 ${ms.toFixed(3)} ms (입자 평균 ${parts.toFixed(0)}, 탄 20, 장판 4, 근접 2)`);
  assert.ok(parts >= 300, '입자가 400 언저리 (' + parts.toFixed(0) + ')');
  assert.ok(ms < 3, ms.toFixed(3) + ' ms');
});

test('styleDef 는 이 파일의 것을 쓴다 (집안 목록과 같은 객체)', () => {
  for (const k of MINE) assert.equal(styleDef(k), body[k]);
});
