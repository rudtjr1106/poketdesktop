/* 이펙트 모양 훅 검사 (js/fx/core.js · js/fx/styles/*.js · js/fx/zones.js).

     node --test server/web/action/test/

   무엇을 못 박나
     1. 모양 키 목록: 25개가 한 집안에만, 집안 파일에는 제 키만, 훅 이름 · 값은 core.HOOKS 대로 (checkFamilies).
     2. 검사기(checkStyle)가 모르는 훅 · 함수 아닌 훅 · 깨진 spec 을 잡는다.
     3. 모든 모양 × 모든 훅 × 모든 장판 꼴: Fx 를 거쳐 모양마다 가진 훅이 한 번 이상 불리고, 예외 · NaN 없이,
        그리기마다 ctx 를 받은 그대로 돌려놓고, 화면 ctx 에서 그라디언트를 만들지 않는다.
     4. 훅이 ctx 를 어지럽혀도 (알파 0 · 점선 · 옮기기 · 혼합) 장판 표시(테두리 · 빨간 점선)는 그대로 그려진다.
     5. 근접 · 돌진(rush): cast 의 len · r 을 쓰고 (없으면 200 · 60), 몸을 따라가며 준비 → 달림 → 끝, 빠르기를 재서
        달리기 시작을 안다. 맞는 거리 reach 는 melee r + BODY_R · dash r + 2·BODY_R.
     6. impact 훅: hit 에는 cast 때 기억한 (쪽, 기술) 의 모양이, 장판이 터질 때는 why = 꼴로.
     7. 도우미: noise · rng · hash2 범위와 고정, Trail 간격 · 고리, ribbon · A(). */
import test from 'node:test';
import assert from 'node:assert/strict';
import { Fx, STYLES } from '../js/fx.js';
import {
  A, BASE, BODY_R, DEBRIS, HOOKS, Trail, ZONE_KINDS, checkStyle, hash2, noise1, noise2, ribbon, rng,
} from '../js/fx/core.js';
import { FAMILIES, FAMILY_OF, STYLE_KEYS, checkFamilies, hookOf, styleDef } from '../js/fx/styles/index.js';
import { GENERIC } from '../js/fx/styles/body.js';
import { TYPE_FX } from '../js/consts.js';

const TYPES = Object.keys(TYPE_FX);
const PLAN_STYLES = ['orb', 'flame', 'jet', 'zap', 'leaf', 'shard', 'psy', 'rock', 'ghost', 'dark', 'fairy',
  'poison', 'wind', 'sound', 'punch', 'slash', 'bite', 'beam', 'wave', 'quake', 'heal', 'buff', 'shield',
  'powder', 'web'];

// ---------------------------------------------------------------- 가짜 2D ctx (fx.test.mjs 와 같은 규칙 + 긋기 상태 기록)
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
    this.strokes = [];                // 긋기마다 그때 상태
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
    const { strokeStyle, globalAlpha, globalCompositeOperation, lineWidth, dash, moved } = this.st;
    this.strokes.push({ strokeStyle, globalAlpha, globalCompositeOperation, lineWidth, dash: dash.slice(), moved });
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

const zone = (kind, sty, i = 0, extra = {}) => ({
  id: `z${kind}${sty}${i}`, o: i % 2 ? 'a' : 'b', k: 'TEST', ty: TYPES[i % TYPES.length], sty, kind,
  x: 800, y: 450, r: 90, ang: 0.4, len: 520, w: 60, t0: 10, t1: 11, ...extra,
});

// ---------------------------------------------------------------- 1 · 2 목록 · 검사기
test('모양 키 목록: 25개가 한 집안에만, 집안 파일에는 제 키만, 훅은 아는 이름만', () => {
  assert.deepEqual([...STYLE_KEYS], PLAN_STYLES);
  assert.deepEqual([...STYLES], PLAN_STYLES, 'fx.js 의 STYLES 도 같다');
  assert.deepEqual(checkFamilies(), []);
  assert.deepEqual(Object.keys(FAMILY_OF).sort(), [...PLAN_STYLES].sort());
  const seen = new Map();
  for (const [fam, defs] of Object.entries(FAMILIES)) {
    for (const k of Object.keys(defs)) {
      assert.equal(seen.get(k), undefined, `${k} 가 ${seen.get(k)} 와 ${fam} 둘에 있다`);
      seen.set(k, fam);
      assert.equal(FAMILY_OF[k], fam, `${fam}.js 의 ${k}`);
      for (const name of Object.keys(defs[k])) assert.ok(name in HOOKS, `${fam}.${k}: 모르는 훅 ${name}`);
      assert.equal(typeof defs[k].shot, 'function', `${k}.shot`);
    }
  }
  assert.equal(seen.size, 25);
  assert.deepEqual(Object.keys(FAMILIES).sort(), ['air', 'body', 'fire', 'mystic']);
  assert.deepEqual([...ZONE_KINDS].sort(), ['beam', 'cone', 'haz', 'ring', 'tele']);
  for (const z of ZONE_KINDS) assert.equal(HOOKS[z], 'fn', `장판 꼴 ${z} 는 훅 이름이다`);
});

test('검사기는 모르는 훅 · 함수 아닌 훅 · 깨진 spec · 없는 shot 을 잡는다', () => {
  const shot = () => {};
  assert.deepEqual(checkStyle('ok', { shot, emit: { shape: 'glow', rate: 5, c: 'light', v: 0, life: 0.3, size: 4 },
    debris: 'spark', ring: shot }), []);
  assert.deepEqual(checkStyle('ok2', { shot, debris: { shape: 'star', n: 4, c: '#ffffff', v: 10, life: 0.2, size: 3 } }), []);
  const bad = (def) => checkStyle('x', def);
  assert.ok(bad({}).some((s) => s.includes('shot')), 'shot 이 없다');
  assert.ok(bad({ shot, swoosh: shot }).some((s) => s.includes('swoosh')), '모르는 훅');
  assert.ok(bad({ shot, cone: 3 }).some((s) => s.includes('cone')), '함수가 아닌 훅');
  assert.ok(bad({ shot, emit: { shape: 'blob', rate: 1, c: 'light', v: 1, life: 1, size: 1 } }).length, '모르는 입자 모양');
  assert.ok(bad({ shot, emit: { shape: 'glow', c: 'light', v: 1, life: 1, size: 1 } }).length, 'rate 가 없다');
  assert.ok(bad({ shot, emit: { shape: 'glow', rate: 1, c: 'red', v: 1, life: 1, size: 1 } }).length, '색 이름');
  assert.ok(bad({ shot, debris: 'confetti' }).length, '없는 조각 이름');
  assert.ok(bad(null).length);
  for (const name of Object.keys(DEBRIS)) assert.deepEqual(bad({ shot, debris: name }), []);
});

test('훅 고르기: 없으면 기본 (shot · emit 은 orb, 장판 · fall 은 BASE, rush · swing 은 GENERIC), 모르는 키는 orb', () => {
  const orb = FAMILIES.mystic.orb;
  assert.equal(styleDef('zzz'), orb);
  assert.equal(styleDef(undefined), orb);
  assert.equal(styleDef('__proto__'), orb);
  assert.equal(styleDef('toString'), orb);
  assert.equal(hookOf('zzz', 'shot'), orb.shot);
  assert.equal(hookOf('heal', 'emit'), FAMILIES.body.heal.emit);
  for (const sty of PLAN_STYLES) {
    const def = styleDef(sty);
    assert.equal(hookOf(sty, 'emit'), def.emit || orb.emit);
    for (const z of ZONE_KINDS) assert.equal(hookOf(sty, z), def[z] || BASE[z], `${sty}.${z}`);
    assert.equal(hookOf(sty, 'fall'), def.fall || BASE.fall);
    assert.equal(hookOf(sty, 'rush'), def.rush || GENERIC.rush);
    assert.equal(hookOf(sty, 'swing'), def.swing || GENERIC.swing);
    assert.equal(hookOf(sty, 'launch'), def.launch || null, '더하는 훅은 기본이 없다');
    assert.equal(hookOf(sty, 'impact'), def.impact || null);
  }
});

// ---------------------------------------------------------------- 3 모든 모양 × 모든 훅 × 모든 장판 꼴
// 집안 파일의 훅을 세는 것으로 바꿔 끼우고 (끝나면 되돌린다) Fx 로 돌린다
function counting(extra = {}) {
  const calls = new Map(), undo = [];
  for (const defs of Object.values(FAMILIES)) {
    for (const [k, def] of Object.entries(defs)) {
      for (const [name, fn] of Object.entries({ ...def, ...(extra[k] || {}) })) {
        if (typeof fn !== 'function') continue;
        const had = Object.prototype.hasOwnProperty.call(def, name), was = def[name];
        def[name] = function (...args) {
          calls.set(`${k}.${name}`, (calls.get(`${k}.${name}`) || 0) + 1);
          return fn.apply(this, args);
        };
        undo.push(() => { if (had) def[name] = was; else delete def[name]; });
      }
    }
  }
  return { calls, restore: () => undo.forEach((f) => f()) };
}

// 모든 훅을 한 번씩 부르게 하는 판: 탄 · 장판 다섯 꼴 (표시 · 터짐 · 함정) · 근접 · 돌진 · 맞음
function exercise(fx, ctx, world, sty, i) {
  const ty = TYPES[i % TYPES.length];
  const k = 'K' + i;
  fx.event({ e: 'cast', w: 'a', m: 0, k, kind: 'proj', ty, sty, x: 400, y: 450, ang: 0 }, world);
  for (let f = 0; f < 4; f++) {
    fx.drawProjectile(ctx, { id: `p${sty}${i}`, o: f % 2 ? 'a' : 'b', k, ty, sty, x: 0, y: 0, vx: 600, vy: -40, r: 14 },
      500 + f * 10, 400 - f);
    clean(ctx, `drawProjectile ${sty}`);
    frame(fx, ctx, 1 / 30);
  }
  fx.event({ e: 'hit', w: 'a', v: 'b', k, ty, dmg: 12, hpr: 500, eff: 2, crit: true, x: 1200, y: 450 }, world);
  fx.event({ e: 'hit', w: 'a', v: 'b', k: 'other', ty, sty, dmg: 12, hpr: 500, eff: 0.5, crit: false, x: 1200, y: 450 }, world);
  for (const kind of ZONE_KINDS) {
    for (const now of [9.9, 10, 10.4, 10.8, 10.95, 11, 11.1, 11.3, 12]) {
      fx.drawZone(ctx, zone(kind, sty, i, { t1: kind === 'haz' ? 1e9 : 11 }), now);
      clean(ctx, `drawZone ${kind}/${sty}@${now}`);
      frame(fx, ctx, 0.03);
    }
  }
  for (const [mk, len, r] of [['melee', 220, 60], ['dash', 420, 30], ['melee', undefined, undefined]]) {
    world.at.a.x = 400;
    fx.event({ e: 'cast', w: 'a', m: 1, k, kind: mk, ty, sty, x: 400, y: 450, ang: 0.3, len, r }, world);
    for (let f = 0; f < 30; f++) {
      if (f > 6 && f < 14) world.at.a.x += 30;             // 1초에 900 u - 달린다
      frame(fx, ctx, 1 / 60);
    }
  }
  world.at.a.x = 400;
}

test('모든 모양 × 모든 훅 × 모든 장판 꼴: 가진 훅이 다 불리고, 깨끗하게, 그라디언트 없이', () => {
  // 덧 훅이 있는 모양이 아직 없으면 (impact · launch · trail) 검사용으로 하나씩 달아 본다
  const probe = {};
  for (const sty of PLAN_STYLES) {
    const d = styleDef(sty);
    probe[sty] = {
      ...(d.impact ? {} : { impact(fx, x, y, ang, c, info) { assert.ok(Number.isFinite(x + y + ang) && c.light && info.why); } }),
      ...(d.launch ? {} : { launch(fx, q) { assert.ok(q.c.light && Number.isFinite(q.ang)); } }),
    };
  }
  const { calls, restore } = counting(probe);
  try {
    const { fx, sprites } = newFx();
    const ctx = new RecCtx();
    const world = makeWorld('a');
    PLAN_STYLES.forEach((sty, i) => exercise(fx, ctx, world, sty, i));
    exercise(fx, ctx, world, 'zzz', 99);
    for (let f = 0; f < 40; f++) frame(fx, ctx, 0.05);
    assert.deepEqual(fx.counts(), { particles: 0, anims: 0, texts: 0 }, '다 사라진다');
    for (const sty of PLAN_STYLES) {
      const def = styleDef(sty);
      for (const name of Object.keys(def)) {
        if (typeof def[name] !== 'function') continue;
        assert.ok(calls.get(`${sty}.${name}`) > 0, `${sty}.${name} 가 한 번도 불리지 않았다`);
      }
    }
    assert.ok(calls.get('orb.shot') > 4, '모르는 키(zzz)도 orb 로');
    assert.equal(ctx.n.createRadialGradient, undefined, '화면 ctx 에서 그라디언트를 만들지 않는다');
    assert.ok(sprites.every((s) => (s.n.createRadialGradient || 0) <= 1));
  } finally {
    restore();
  }
});

test('훅을 하나씩 직접 불러도 (Fx 가 만든 q · a 로) 예외 · NaN 없이 ctx 를 돌려놓는다', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('b');
  fx.event({ e: 'phase', ph: 'fight' }, world);
  const q = fx.shotOf({ id: 'pq', o: 'a', k: 'X', ty: 'FLYING', sty: 'wind', vx: 500, vy: 100, r: 16 }, 600, 420);
  fx.event({ e: 'cast', w: 'a', k: 'X', kind: 'melee', ty: 'DRAGON', sty: 'slash', x: 400, y: 450, ang: 0, len: 200, r: 60 }, world);
  const a = fx.anims.find((v) => v.kind === 'rush');
  for (const sty of [...PLAN_STYLES, 'zzz']) {
    const def = styleDef(sty);
    for (const name of Object.keys(HOOKS)) {
      const hook = hookOf(sty, name);
      if (typeof hook !== 'function') continue;
      const run = (...args) => {
        ctx.save();
        hook(...args);
        ctx.restore();
        clean(ctx, `${sty}.${name}`);
      };
      if (name === 'shot') run(fx, ctx, q);
      else if (name === 'trail') run(fx, q, 1 / 60);
      else if (name === 'launch') run(fx, q);
      else if (name === 'impact') run(fx, 800, 450, 0.5, q.c, { why: 'hit', k: 'X', ty: 'FIRE', sty, eff: 1, crit: false, s: 1, r: 0, len: 0 });
      else if (name === 'fall') for (const v of [0, 0.5, 0.75, 1]) run(fx, ctx, fx.zoneOf(zone('tele', sty, 1), 10.9), 800, 300, v);
      else if (name === 'rush') for (const stage of ['wind', 'act', 'tail']) run(fx, ctx, { ...a, stage, sk: 0.5, speed: 1200 });
      else if (name === 'swing') for (const t of [0, 0.3, 0.7, 0.99]) run(fx, ctx, a, t);
      else if (ZONE_KINDS.includes(name)) {
        for (const now of [10.2, 10.9, 11.05, 11.4]) run(fx, ctx, fx.zoneOf(zone(name, sty, 2), now));
      }
      assert.ok(def, sty);
    }
  }
  assert.equal(ctx.n.createRadialGradient, undefined);
});

// ---------------------------------------------------------------- 4 표시는 훅이 가릴 수 없다
test('훅이 ctx 를 어지럽혀도 장판 표시(테두리 · 상대 빨간 점선)는 그대로', () => {
  const hostile = (fx, ctx) => {          // 돌려놓지 않고 다 바꾼다
    ctx.globalAlpha = 0;
    ctx.globalCompositeOperation = 'lighter';
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 0.2;
    ctx.setLineDash([1, 50]);
    ctx.lineDashOffset = 7;
    ctx.translate(300, -200);
    ctx.scale(0.1, 0.1);
    ctx.rotate(1);
  };
  const orb = FAMILIES.mystic.orb, undo = [];
  for (const z of ZONE_KINDS) {
    const had = Object.prototype.hasOwnProperty.call(orb, z), was = orb[z];
    orb[z] = hostile;
    undo.push(() => { if (had) orb[z] = was; else delete orb[z]; });
  }
  try {
    for (const kind of ['tele', 'ring', 'cone', 'beam']) {
      const { fx } = newFx();
      fx.event({ e: 'phase', ph: 'ready' }, makeWorld('a'));
      const ctx = new RecCtx();
      fx.drawZone(ctx, zone(kind, 'zzz', 0, { o: 'b' }), 10.5);    // 상대 것, 표시 중
      clean(ctx, kind);
      const edge = ctx.strokes.find((s) => s.strokeStyle === '#ff4f5e');
      assert.ok(edge, `${kind}: 빨간 테두리`);
      assert.equal(edge.globalAlpha, 1, `${kind}: 테두리 알파`);
      assert.equal(edge.globalCompositeOperation, 'source-over');
      assert.deepEqual(edge.dash, []);
      assert.equal(edge.moved, false, `${kind}: 테두리는 옮겨지지 않은 자리에`);
      assert.ok(edge.lineWidth >= 3);
      const dashed = ctx.strokes.find((s) => s.dash.length && s.dash[0] === 14);
      assert.ok(dashed && dashed.globalAlpha === 1 && !dashed.moved, `${kind}: 도는 점선`);
    }
    const { fx } = newFx();                // 함정도 점선 테두리는 훅 앞에 그린다
    fx.event({ e: 'phase', ph: 'ready' }, makeWorld('a'));
    const ctx = new RecCtx();
    fx.drawZone(ctx, zone('haz', 'zzz', 0, { o: 'b', t0: 9, t1: 1e9 }), 10);
    clean(ctx, 'haz');
    const edge = ctx.strokes.find((s) => s.strokeStyle === '#ff4f5e');
    assert.ok(edge && edge.globalAlpha === 0.6 && !edge.moved);
  } finally {
    undo.forEach((f) => f());
  }
});

// ---------------------------------------------------------------- 5 근접 · 돌진
test('근접 · 돌진: cast 의 len · r (없으면 200 · 60), reach, 몸을 따라 준비 → 달림 → 끝', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('a');
  const seen = [];
  const slash = FAMILIES.body.slash, had = slash.rush;
  slash.rush = (f, c, a) => seen.push({ stage: a.stage, sk: a.sk, x: a.x, n: a.trail.n, speed: a.speed, reach: a.reach });
  try {
    fx.event({ e: 'cast', w: 'a', k: 'SLASH', kind: 'melee', ty: 'NORMAL', sty: 'slash', x: 400, y: 450, ang: 0, len: 240, r: 60 }, world);
    const a = fx.anims.find((v) => v.kind === 'rush');
    assert.ok(a, '돌진 그림');
    assert.equal(a.mk, 'melee');
    assert.equal(a.len, 240);
    assert.equal(a.r, 60);
    assert.equal(a.reach, 60 + BODY_R);
    assert.equal(a.side, 'a');
    // 준비 (거의 서 있다) → 1초에 1200 u 로 달린다 → 멈춘다
    for (let f = 0; f < 5; f++) frame(fx, ctx, 1 / 60);
    assert.equal(a.stage, 'wind');
    assert.equal(a.go, null);
    for (let f = 0; f < 6; f++) {
      world.at.a.x += 20;
      frame(fx, ctx, 1 / 60);
    }
    assert.notEqual(a.go, null, '빨라진 것을 재서 달리기 시작을 안다');
    assert.ok(a.go < 0.2, '준비 어림(0.2초)보다 먼저 - ' + a.go);
    assert.equal(a.x, world.at.a.x, '몸을 따라간다');
    assert.ok(a.moved > 100);
    assert.ok(a.trail.n >= 5, '지나온 자리');
    assert.equal(a.trail.x(0), world.at.a.x, '0 이 지금 자리');
    for (let f = 0; f < 40 && fx.anims.includes(a); f++) frame(fx, ctx, 1 / 60);
    assert.ok(!fx.anims.includes(a), '끝나면 사라진다');
    const stages = [...new Set(seen.map((s) => s.stage))];
    assert.deepEqual(stages, ['wind', 'act', 'tail']);
    assert.ok(seen.some((s) => s.speed > 900), '빠르기를 잰다');
    assert.ok(seen.every((s) => s.reach === 60 + BODY_R && s.sk >= 0 && s.sk <= 1));
  } finally {
    if (had) slash.rush = had;
    else delete slash.rush;
  }
  // len · r 이 없는 cast (엔진이 보내기 전) · 돌진 (reach r + 2·BODY_R, 달리는 시간 len/1500)
  fx.event({ e: 'cast', w: 'b', k: 'TACKLE', kind: 'melee', ty: 'NORMAL', sty: 'orb', x: 1200, y: 450, ang: Math.PI }, world);
  const m = fx.anims.at(-1);
  assert.equal(m.len, 200);
  assert.equal(m.r, 60);
  fx.event({ e: 'cast', w: 'b', k: 'QUICKATTACK', kind: 'dash', ty: 'NORMAL', sty: 'orb', x: 1200, y: 450, ang: 2, len: 450, r: 30 }, world);
  const d = fx.anims.at(-1);
  assert.equal(d.mk, 'dash');
  assert.equal(d.reach, 30 + 2 * BODY_R);
  assert.ok(Math.abs(d.act - 450 / 1500) < 1e-9);
  assert.ok(Math.abs(d.ux - Math.cos(2)) < 1e-9 && Math.abs(d.uy - Math.sin(2)) < 1e-9, '각도는 라디안 그대로');
  // 몸이 안 움직여도 (벽 · 바로 앞 상대) 준비 어림 뒤에 시작하고 끝난다
  for (let f = 0; f < 60; f++) frame(fx, ctx, 1 / 60);
  assert.equal(fx.counts().anims, 0);
});

test('근접: 제 swing 이 없는 모양은 다 달린 뒤 앞에서 그 모양의 조각이 튄다', () => {
  const shapesAfter = (sty) => {
    const { fx } = newFx();
    const ctx = new RecCtx();
    fx.event({ e: 'cast', w: 'a', k: 'X', kind: 'melee', ty: 'FIRE', sty, x: 400, y: 450, ang: 0 }, makeWorld());
    for (let f = 0; f < 30; f++) frame(fx, ctx, 1 / 60);
    return new Set(fx.parts.all.filter((p) => p.on).map((p) => p.shape));
  };
  assert.ok(shapesAfter('flame').has('wisp'), '불꽃 조각');
  assert.ok(!shapesAfter('slash').has('wisp'), '베기는 제 swing 이 있다');
});

// ---------------------------------------------------------------- 6 impact
test('impact: hit 은 cast 때 기억한 모양으로, 장판은 터질 때 why = 꼴', () => {
  const got = [];
  const flame = FAMILIES.fire.flame, had = flame.impact;
  flame.impact = (fx, x, y, ang, c, info) => got.push({ x, y, ang, light: c.light, ...info });
  try {
    const { fx } = newFx();
    const world = makeWorld('a');
    fx.event({ e: 'hit', w: 'a', v: 'b', k: 'FLAMETHROWER', ty: 'FIRE', hpr: 1, eff: 2, crit: false, x: 1200, y: 450 }, world);
    assert.equal(got.length, 0, 'cast 를 못 봤으면 모른다');
    fx.event({ e: 'cast', w: 'a', k: 'FLAMETHROWER', kind: 'proj', ty: 'FIRE', sty: 'flame', x: 400, y: 450, ang: 0 }, world);
    fx.event({ e: 'hit', w: 'a', v: 'b', k: 'FLAMETHROWER', ty: 'FIRE', hpr: 1, eff: 2, crit: true, x: 1200, y: 450 }, world);
    assert.equal(got.length, 1);
    assert.equal(got[0].why, 'hit');
    assert.equal(got[0].sty, 'flame');
    assert.equal(got[0].crit, true);
    assert.equal(got[0].s, 1.35);
    assert.ok(Math.abs(got[0].ang) < 1e-9, '쏜 쪽에서 맞은 쪽으로 (오른쪽)');
    fx.event({ e: 'hit', w: 'b', v: 'a', k: 'FLAMETHROWER', ty: 'FIRE', hpr: 1, eff: 1, x: 400, y: 450 }, world);
    assert.equal(got.length, 1, '다른 쪽의 같은 기술은 따로');
    fx.event({ e: 'hit', w: 'b', v: 'a', k: 'EMBER', ty: 'FIRE', sty: 'flame', hpr: 1, eff: 1, x: 400, y: 450 }, world);
    assert.equal(got.length, 2, 'hit 에 sty 가 오면 그것');
    fx.event({ e: 'hit', w: 'a', v: 'b', k: 'FLAMETHROWER', ty: 'FIRE', hpr: 1, eff: 0, x: 1200, y: 450 }, world);
    assert.equal(got.length, 2, '효과가 없으면 부르지 않는다');
    const ctx = new RecCtx();
    for (const kind of ['tele', 'ring', 'cone', 'beam']) {
      fx.drawZone(ctx, zone(kind, 'flame', 3, { ty: 'FIRE' }), 11.05);
      fx.drawZone(ctx, zone(kind, 'flame', 3, { ty: 'FIRE' }), 11.1);
    }
    assert.deepEqual(got.slice(2).map((g) => g.why), ['tele', 'ring', 'cone', 'beam'], '장판마다 한 번');
    assert.ok(got.every((g) => Number.isFinite(g.x) && Number.isFinite(g.y) && g.light === TYPE_FX.FIRE[0]));
  } finally {
    if (had) flame.impact = had;
    else delete flame.impact;
  }
});

test('탄 q · 장판 q 의 칸', () => {
  const { fx } = newFx();
  fx.event({ e: 'phase' }, makeWorld('a'));
  fx.update(0.5);
  const q = fx.shotOf({ id: 7, o: 'b', k: 'GUST', ty: 'FLYING', sty: 'wind', vx: 300, vy: 400, r: 18 }, 100, 200);
  fx.update(0.1);                          // update 는 한 번에 0.1초까지 - 0.15초 넘게 안 그리면 잊는다
  fx.shotOf({ id: 7, o: 'b', k: 'GUST', ty: 'FLYING', sty: 'wind', vx: 300, vy: 400, r: 18 }, 137, 250);
  fx.update(0.1);
  fx.shotOf({ id: 7, o: 'b', k: 'GUST', ty: 'FLYING', sty: 'wind', vx: 300, vy: 400, r: 18 }, 175, 300);
  assert.equal(q.k, 'GUST');
  assert.equal(q.ty, 'FLYING');
  assert.equal(q.sty, 'wind');
  assert.equal(q.foe, true);
  assert.equal(q.vx, 300);
  assert.equal(q.speed, 500);
  assert.ok(Math.abs(q.ang - Math.atan2(400, 300)) < 1e-12);
  assert.ok(Math.abs(q.age - 0.2) < 1e-9);
  assert.equal(q.seed, 7);
  assert.deepEqual(q.c, { light: TYPE_FX.FLYING[0], dark: TYPE_FX.FLYING[1] });
  assert.equal(q.trail.n, 3);
  assert.equal(q.trail.x(0), 175);
  assert.equal(q.trail.x(2), 100);
  assert.deepEqual(q.mem, {});
  const z = fx.zoneOf(zone('cone', 'wind', 0, { o: 'a', w: 400, len: 300 }), 10.5);
  assert.equal(z.phase, 'mark');
  assert.equal(z.u, 0.5);
  assert.equal(z.foe, false);
  assert.ok(Math.abs(z.h - Math.atan2(200, 300)) < 1e-12);
  const f = fx.zoneOf(zone('ring', 'wind', 0), 11.14);
  assert.equal(f.phase, 'fire');
  assert.ok(Math.abs(f.e - 0.5) < 1e-9, '고리는 0.28초 동안 터진다');
  assert.ok(f.rr > f.r * 0.2 && f.rr < f.r);
});

// ---------------------------------------------------------------- 7 도우미
test('도우미: noise · rng · hash2 · A', () => {
  for (let i = 0; i < 500; i++) {
    const x = i * 0.137 - 20, y = i * 0.071 + 3;
    for (const v of [noise1(x), noise2(x, y), hash2(x, y)]) assert.ok(v >= 0 && v < 1, String(v));
    assert.ok(Math.abs(noise1(x + 0.001) - noise1(x)) < 0.01, '이어진다');
    assert.ok(Math.abs(noise2(x, y + 0.001) - noise2(x, y)) < 0.01);
  }
  assert.equal(noise1(3), noise1(3));
  const a = rng(42), b = rng(42), c = rng(43);
  const sa = [a(), a(), a()], sb = [b(), b(), b()];
  assert.deepEqual(sa, sb, '같은 씨앗이면 같은 차례');
  assert.notDeepEqual(sa, [c(), c(), c()]);
  assert.ok(sa.every((v) => v >= 0 && v < 1));
  assert.equal(rng(NaN)(), rng(0)());
  assert.equal(A(NaN), 0);
  assert.equal(A(-1), 0);
  assert.equal(A(2), 1);
  assert.equal(A(0.25), 0.25);
});

test('Trail: gap 보다 멀어져야 새 점, 아니면 맨 앞만 옮기고, 넘치면 오래된 것부터', () => {
  const tr = new Trail(4);
  tr.push(0, 0, 0, 10);
  tr.push(3, 0, 0.1, 10);
  assert.equal(tr.n, 2);
  tr.push(6, 0, 0.2, 10);                 // 1번 점(0,0)에서 6 - 맨 앞만 옮긴다
  assert.equal(tr.n, 2);
  assert.equal(tr.x(0), 6);
  assert.equal(tr.t(0), 0.2);
  tr.push(12, 0, 0.3, 10);                // 1번 점에서 12 - 새 점
  assert.equal(tr.n, 3);
  assert.deepEqual([tr.x(0), tr.x(1), tr.x(2)], [12, 6, 0]);
  for (let i = 1; i <= 5; i++) tr.push(12 + i * 20, 0, 0.3 + i * 0.1, 10);
  assert.equal(tr.n, 4, '넘치지 않는다');
  assert.deepEqual([tr.x(0), tr.x(1), tr.x(2), tr.x(3)], [112, 92, 72, 52]);
  tr.push(NaN, 0, 1);
  assert.equal(tr.x(0), 112, 'NaN 은 버린다');
  tr.clear();
  assert.equal(tr.n, 0);
});

test('ribbon: 오래된 점은 빼고, 꼬리로 갈수록 옅어진다 (그라디언트 없이)', () => {
  const tr = new Trail(16);
  for (let i = 0; i < 10; i++) tr.push(100 + i * 20, 200 + i * 3, i * 0.05, 4);
  const alphas = [];
  const ctx = new RecCtx();
  const fill = ctx.fill.bind(ctx);
  ctx.fill = () => { alphas.push(ctx.globalAlpha); fill(); };
  ribbon(ctx, tr, 0.45, 0.2, 40, 4, '#ffffff', 0.8);
  assert.ok(alphas.length >= 2 && alphas.length <= 4, '0.2초 안의 점만 (' + alphas.length + ')');
  for (let i = 1; i < alphas.length; i++) assert.ok(alphas[i] < alphas[i - 1], '옅어진다');
  assert.ok(alphas.every((v) => v > 0 && v <= 0.8));
  ribbon(ctx, tr, 0.45, 0, 40, 4, '#ffffff', 0.8);
  ribbon(ctx, new Trail(4), 0, 1, 40, 4, '#ffffff', 0.8);
  ribbon(ctx, null, 0, 1, 40, 4, '#ffffff', 0.8);
  assert.equal(alphas.length <= 4, true, '빈 것 · 수명 0 은 그리지 않는다');
  assert.equal(ctx.n.createRadialGradient, undefined);
});
