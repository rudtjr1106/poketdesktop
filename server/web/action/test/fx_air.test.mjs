/* 바람 · 소리 · 물 · 결정 모양 검사 (js/fx/styles/air.js).

     node --test server/web/action/test/

   무엇을 못 박나
     1. 다섯 키 (wind sound jet wave shard) 와 훅: 꼴마다 그 집안이 맡은 훅이 다 있다 (근접 · 내려찍기 · 장판).
     2. 모든 모양 × 모든 훅 × 여러 타입 · 시각: 기록하는 가짜 ctx 에서 예외 · NaN 없이, 그라디언트 없이, ctx 를 받은
        그대로 돌려놓는다 (Fx 를 거쳐서도, 훅을 바로 불러서도).
     3. 같은 씨앗 · 같은 시각이면 같은 그림 (Math.random 을 바꿔도), 씨앗이 다르면 · 시각이 다르면 다른 그림.
     4. 장판이 터지는 그림은 서버가 지우기 전에 (q.e 0.7) 다 사라진다 - 지울 때 툭 끊기지 않는다.
     5. 물마루 · 소리 벽은 서버 반지름 (고리 r · 부채꼴 len) 을 거품 폭 넘게 넘지 않는다.
     6. 실려 가는 것은 타입마다: 얼음 바람은 눈 (잎 없음), 비행 바람은 잎, 불 바람은 불티. 서리는 얼음 결정만.
     7. 입자 수: 꼬리 · 처음 · 맞음 · 장판 · 돌진마다 정한 수를 넘지 않는다. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { Fx } from '../js/fx.js';
import { HOOKS, ZONE_KINDS, checkStyle } from '../js/fx/core.js';
import { FAMILY_OF, hookOf } from '../js/fx/styles/index.js';
import air from '../js/fx/styles/air.js';
import { TYPE_FX } from '../js/consts.js';

const KEYS = ['wind', 'sound', 'jet', 'wave', 'shard'];
const TYPES = ['FLYING', 'ICE', 'FIRE', 'WATER', 'STEEL', 'GRASS', 'DRAGON', 'GROUND', 'ELECTRIC', 'FAIRY', 'NORMAL', 'BUG'];

// ---------------------------------------------------------------- 기록하는 가짜 2D ctx (fx-hooks.test.mjs 와 같은 규칙)
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
const POINTS = ['moveTo', 'lineTo', 'quadraticCurveTo', 'bezierCurveTo', 'rect', 'fillRect', 'strokeRect'];
const PLAIN = ['beginPath', 'closePath', 'clip'];

class RecCtx {
  constructor() {
    this.n = Object.create(null);
    this.trace = [];                  // 점 · 반지름 (그림이 같은지 견준다)
    this.inks = [];                   // 칠 · 긋기 · 그림마다 그때 알파
    this.pts = [];                    // 경로 점 (x, y) - 반지름 검사
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
    this.trace.push(x, y, r);
    this.pts.push(x, y, r);
  }
  ellipse(x, y, rx, ry, rot, a0, a1) {
    this.rec('ellipse', [x, y, rx, ry, rot, a0, a1]);
    if (rx < 0 || ry < 0) throw new RangeError('IndexSizeError: ellipse 반지름이 음수');
    this.trace.push(x, y, rx, ry);
    this.pts.push(x, y, Math.max(rx, ry));
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
    this.trace.push(...nums);
    this.inks.push(this.st.globalAlpha);
  }
  fill() { this.rec('fill', []); this.inks.push(this.st.globalAlpha); }
  stroke() { this.rec('stroke', []); this.inks.push(this.st.globalAlpha); }
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
for (const name of POINTS) {
  RecCtx.prototype[name] = function (...args) {
    this.rec(name, args);
    this.trace.push(...args);
    for (let i = 0; i + 1 < args.length; i += 2) this.pts.push(args[i], args[i + 1], 0);
  };
}
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

const shotP = (sty, ty, i = 0, extra = {}) => ({ id: `p${sty}${ty}${i}`, o: 'a', k: 'K', ty, sty, vx: 620, vy: -90, r: 15, ...extra });
const zoneZ = (kind, sty, ty, i = 0, extra = {}) => ({
  id: `z${kind}${sty}${ty}${i}`, o: i % 2 ? 'a' : 'b', k: 'K', ty, sty, kind,
  x: 800, y: 450, r: kind === 'tele' ? 75 : kind === 'ring' ? 230 : 360, ang: 0.3, len: 360, w: 360, t0: 10, t1: 10.5, ...extra,
});

// 훅 하나를 save/restore 로 감싸 부른다 (core 가 하듯) - 깨끗하게 돌아와야 한다
function call(ctx, what, fn) {
  ctx.save();
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'lighter';
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  fn();
  ctx.restore();
  clean(ctx, what);
}

// 그림 하나 (훅을 부른 그대로) - 같은 그림인지 견주려고 trace 를 돌려준다
function traceOf(fx, fn) {
  const ctx = new RecCtx();
  call(ctx, 'trace', () => fn(ctx));
  return ctx.trace;
}

function withRandom(seq, fn) {
  const was = Math.random;
  let i = 0;
  Math.random = () => seq[i++ % seq.length];
  try {
    return fn();
  } finally {
    Math.random = was;
  }
}

// 돌진 그림 a 하나를 cast 로 만든다
function rushOf(fx, sty, ty, mk = 'melee') {
  fx.event({ e: 'cast', w: 'a', k: 'K', kind: mk, ty, sty, x: 400, y: 450, ang: 0.2, len: mk === 'dash' ? 420 : 220, r: mk === 'dash' ? 30 : 60 }, makeWorld());
  return fx.anims.find((v) => v.kind === 'rush' && v.sty === sty && v.mk === mk);
}

// ---------------------------------------------------------------- 1 키와 훅
test('air.js: 다섯 키, 집안 목록대로, 훅은 아는 이름 · 맞는 꼴', () => {
  assert.deepEqual(Object.keys(air).sort(), [...KEYS].sort());
  for (const k of KEYS) {
    assert.equal(FAMILY_OF[k], 'air', k);
    assert.deepEqual(checkStyle(k, air[k]), [], k);
    for (const name of Object.keys(air[k])) assert.ok(name in HOOKS, `${k}.${name}`);
    for (const name of ['shot', 'trail', 'launch', 'impact']) assert.equal(typeof air[k][name], 'function', `${k}.${name}`);
    assert.ok(air[k].debris, `${k}.debris`);
    assert.equal(hookOf(k, 'shot'), air[k].shot);
  }
  // 그 꼴의 기술이 있는 모양은 제 그림을 가진다 (폭풍 · 회오리 · 눈보라 · 파도타기 · 하이퍼보이스 · 고드름떨구기 · 아쿠아테일 ...)
  for (const k of ['wind', 'jet', 'shard']) {
    for (const name of ['cone', 'ring', 'tele', 'fall', 'rush', 'swing']) assert.equal(typeof air[k][name], 'function', `${k}.${name}`);
  }
  for (const k of ['sound', 'wave']) for (const name of ['cone', 'ring']) assert.equal(typeof air[k][name], 'function', `${k}.${name}`);
});

// ---------------------------------------------------------------- 2 모든 훅 × 타입 × 시각
test('모든 모양 × 모든 훅 × 여러 타입 · 시각: 예외 · NaN · 그라디언트 없이, ctx 를 돌려놓는다', () => {
  const { fx, sprites } = newFx();
  const ctx = new RecCtx();
  fx.event({ e: 'phase', ph: 'fight' }, makeWorld('a'));
  for (const sty of KEYS) {
    const def = air[sty];
    TYPES.forEach((ty, ti) => {
      fx.update(1 / 60);
      const q = fx.shotOf(shotP(sty, ty, ti), 600 + ti, 420);
      for (let f = 0; f < 3; f++) {
        call(ctx, `${sty}/${ty}.shot`, () => def.shot(fx, ctx, q));
        def.trail(fx, q, 1 / 60);
        fx.update(1 / 60);
      }
      def.launch(fx, q);
      for (const why of ['hit', 'tele', 'ring', 'cone', 'beam']) {
        for (const s of [0.75, 1, 1.35]) def.impact(fx, 800, 450, 0.4, q.c, { why, k: 'K', ty, sty, eff: 1, crit: s > 1, s, r: 75, len: 360 });
      }
      for (const kind of ZONE_KINDS) {
        const hook = def[kind];
        if (!hook) continue;
        for (const now of [9.9, 10, 10.2, 10.45, 10.5, 10.53, 10.6, 10.7, 11, 12]) {
          const z = fx.zoneOf(zoneZ(kind, sty, ty, ti, kind === 'haz' ? { t1: 1e9 } : {}), now);
          call(ctx, `${sty}/${ty}.${kind}@${now}`, () => hook(fx, ctx, z));
        }
      }
      if (def.fall) {
        const z = fx.zoneOf(zoneZ('tele', sty, ty, ti), 10.45);
        for (const v of [0, 0.3, 0.7, 1]) call(ctx, `${sty}.fall@${v}`, () => def.fall(fx, ctx, z, z.x, z.y - (1 - v) * 320, v));
      }
      if (def.rush) {
        for (const mk of ['melee', 'dash']) {
          const a = rushOf(fx, sty, ty, mk);
          for (const stage of ['wind', 'act', 'tail']) {
            for (const sk of [0, 0.5, 1]) call(ctx, `${sty}.rush ${mk}/${stage}`, () => def.rush(fx, ctx, { ...a, stage, sk, speed: 1200, moved: 120 }));
          }
          for (const t of [0, 0.2, 0.5, 0.8, 0.99, 1]) call(ctx, `${sty}.swing ${mk}@${t}`, () => def.swing(fx, ctx, a, t));
        }
      }
    });
  }
  for (let f = 0; f < 120; f++) frame(fx, ctx, 1 / 30);
  assert.equal(ctx.n.createRadialGradient, undefined, '화면 ctx 에서 그라디언트를 만들지 않는다');
  assert.ok(sprites.every((s) => (s.n.createRadialGradient || 0) <= 1), '스프라이트는 색마다 한 번');
});

test('Fx 를 거쳐 (탄 · 장판 다섯 꼴 · 근접 · 돌진 · 맞음) 깨끗하게, 다 사라진다', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('a');
  KEYS.forEach((sty, i) => {
    const ty = TYPES[i * 2];
    fx.event({ e: 'cast', w: 'a', k: 'K' + i, kind: 'proj', ty, sty, x: 400, y: 450, ang: 0 }, world);
    for (let f = 0; f < 8; f++) {
      fx.drawProjectile(ctx, shotP(sty, ty, 50 + i), 500 + f * 12, 420 - f);
      clean(ctx, `drawProjectile ${sty}`);
      frame(fx, ctx, 1 / 30);
    }
    fx.event({ e: 'hit', w: 'a', v: 'b', k: 'K' + i, ty, dmg: 12, hpr: 500, eff: 2, crit: true, x: 1200, y: 450 }, world);
    for (const kind of ZONE_KINDS) {
      for (let f = 0; f <= 50; f++) {
        const now = 10 + f * 0.02;
        if (kind === 'haz' || now < 10.5 + 0.18) fx.drawZone(ctx, zoneZ(kind, sty, ty, 70 + i, kind === 'haz' ? { t1: 1e9 } : {}), now);
        clean(ctx, `drawZone ${kind}/${sty}@${now}`);
        frame(fx, ctx, 0.02);
      }
    }
    for (const [mk, len, r] of [['melee', 220, 60], ['dash', 420, 30]]) {
      world.at.a.x = 400;
      fx.event({ e: 'cast', w: 'a', m: 1, k: 'K' + i, kind: mk, ty, sty, x: 400, y: 450, ang: 0.3, len, r }, world);
      for (let f = 0; f < 36; f++) {
        if (f > 5 && f < 16) world.at.a.x += 25;
        frame(fx, ctx, 1 / 60);
      }
    }
  });
  for (let f = 0; f < 60; f++) frame(fx, ctx, 0.05);
  assert.deepEqual(fx.counts(), { particles: 0, anims: 0, texts: 0 });
  assert.equal(ctx.n.createRadialGradient, undefined);
});

// ---------------------------------------------------------------- 3 고정된 모양 · 움직임 · 탄마다 다름
test('같은 씨앗 · 같은 시각이면 같은 그림 (Math.random 과 상관없이), 씨앗 · 시각이 다르면 다른 그림', () => {
  const draw = (sty, id, clock, rand) => withRandom(rand, () => {
    const { fx } = newFx();
    fx.clock = clock;
    const q = fx.shotOf(shotP(sty, 'ICE', 0, { id }), 600, 400);
    return traceOf(fx, (ctx) => air[sty].shot(fx, ctx, q));
  });
  for (const sty of KEYS) {
    const a = draw(sty, 11, 3.2, [0.1, 0.7]), b = draw(sty, 11, 3.2, [0.9, 0.3, 0.5]);
    assert.ok(a.length > 50, `${sty}: 그린다`);
    assert.deepEqual(a, b, `${sty}: Math.random 으로 모양이 바뀌지 않는다`);
    assert.notDeepEqual(draw(sty, 12, 3.2, [0.5]), a, `${sty}: 탄마다 다르다`);
    assert.notDeepEqual(draw(sty, 11, 3.25, [0.5]), a, `${sty}: 움직인다`);
  }
  // 장판 · 돌진 그림도
  for (const sty of KEYS) {
    for (const kind of ['cone', 'ring', 'tele']) {
      if (!air[sty][kind]) continue;
      for (const now of [10.3, 10.56]) {
        const run = (rand) => withRandom(rand, () => {
          const { fx } = newFx();
          fx.clock = 5;
          const z = fx.zoneOf(zoneZ(kind, sty, 'WATER'), now);
          return traceOf(fx, (ctx) => air[sty][kind](fx, ctx, z));
        });
        assert.deepEqual(run([0.2]), run([0.8, 0.1]), `${sty}.${kind}@${now}`);
      }
    }
    if (!air[sty].swing) continue;
    const run = (rand) => withRandom(rand, () => {
      const { fx } = newFx();
      const a = rushOf(fx, sty, 'STEEL');
      fx.clock = 2;
      a.seed = 1.5;
      return traceOf(fx, (ctx) => {
        air[sty].rush(fx, ctx, { ...a, stage: 'act', sk: 0.4, moved: 100 });
        air[sty].swing(fx, ctx, a, 0.4);
      });
    });
    assert.deepEqual(run([0.3]), run([0.6, 0.9]), `${sty}.rush · swing`);
  }
});

// ---------------------------------------------------------------- 4 서버가 지우기 전에 다 사라진다
test('장판이 터지는 그림은 q.e 0.7 (서버가 지우는 무렵) 에 다 사라진다', () => {
  for (const sty of KEYS) {
    for (const kind of ['cone', 'ring', 'tele']) {
      const hook = air[sty][kind];
      if (!hook) continue;
      const { fx } = newFx();
      const ctx = new RecCtx();
      const fs = { tele: 0.3, ring: 0.28, cone: 0.25 }[kind];
      const early = fx.zoneOf(zoneZ(kind, sty, 'ICE'), 10.5 + fs * 0.2);
      call(ctx, 'early', () => hook(fx, ctx, early));
      assert.ok(ctx.inks.some((a) => a > 0.3), `${sty}.${kind}: 터지는 동안 보인다`);
      const late = new RecCtx();
      const z = fx.zoneOf(zoneZ(kind, sty, 'ICE', 1), 10.5 + fs * 0.71);
      call(late, 'late', () => hook(fx, late, z));
      assert.ok(late.inks.every((a) => a <= 0.02), `${sty}.${kind}: 다 사라진다 (${Math.max(...late.inks)})`);
    }
  }
});

// ---------------------------------------------------------------- 5 서버 반지름
test('물마루 · 소리 벽은 서버 반지름 (고리 r · 부채꼴 len) 을 거품 폭 넘게 넘지 않는다', () => {
  for (const sty of ['wave', 'sound']) {
    for (const kind of ['ring', 'cone']) {
      let far = 0, reach = 0;
      for (let f = 0; f <= 20; f++) {
        const { fx } = newFx();
        const ctx = new RecCtx();
        const z = fx.zoneOf(zoneZ(kind, sty, 'WATER', f), 10.5 + f * 0.01);
        call(ctx, `${sty}.${kind}`, () => air[sty][kind](fx, ctx, z));
        const R = kind === 'ring' ? z.r : z.len;
        for (let i = 0; i < ctx.pts.length; i += 3) {
          const d = Math.hypot(ctx.pts[i] - z.x, ctx.pts[i + 1] - z.y) + ctx.pts[i + 2];
          far = Math.max(far, d / R);
        }
        reach = Math.max(reach, far);
      }
      assert.ok(far <= 1.12, `${sty}.${kind}: 서버 반지름의 ${far.toFixed(3)} 배까지`);
      assert.ok(reach >= 0.85, `${sty}.${kind}: 서버 반지름까지 간다 (${reach.toFixed(3)})`);
    }
  }
});

// ---------------------------------------------------------------- 6 타입마다 실려 가는 것
function spawned(fn) {
  const { fx } = newFx();
  const got = [];
  const sp = fx.spawn.bind(fx);
  fx.spawn = (shape, x, y, vx, vy, life, size, color) => {
    got.push({ shape, color });
    return sp(shape, x, y, vx, vy, life, size, color);
  };
  fn(fx);
  return got;
}

test('바람에 실린 것은 타입마다 (얼음 눈 · 비행 잎 · 불 불티), 서리는 얼음 결정만', () => {
  const windOf = (ty) => spawned((fx) => {
    const q = fx.shotOf(shotP('wind', ty), 600, 400);
    for (let f = 0; f < 240; f++) {
      fx.update(1 / 60);
      air.wind.trail(fx, q, 1 / 60);
    }
    air.wind.impact(fx, 800, 450, 0, q.c, { why: 'hit', ty, s: 1, r: 0, len: 0 });
  });
  const ice = windOf('ICE'), fly = windOf('FLYING'), fire = windOf('FIRE');
  assert.ok(ice.some((p) => p.shape === 'star' && p.color === '#ffffff'), '얼음 바람: 눈');
  assert.ok(!ice.some((p) => p.shape === 'leaf'), '얼음 바람에 잎은 없다');
  assert.ok(fly.some((p) => p.shape === 'leaf'), '비행 바람: 잎');
  assert.ok(fire.some((p) => p.shape === 'spark' && (p.color === TYPE_FX.FIRE[0] || p.color === TYPE_FX.FIRE[1])), '불 바람: 불티');
  assert.ok(!fire.some((p) => p.shape === 'leaf'));
  const mist = (ty) => spawned((fx) => air.shard.impact(fx, 800, 450, 0, { light: '#d8fbff', dark: '#63c8d8' }, { why: 'hit', ty, s: 1 }))
    .filter((p) => p.shape === 'smoke').length;
  assert.ok(mist('ICE') > 0, '얼음 결정은 냉기가 퍼진다');
  assert.equal(mist('STEEL'), 0, '쇠 결정에는 냉기가 없다');
  // 소리는 음표를 그린다 (머리 = 타원)
  const { fx } = newFx();
  const ctx = new RecCtx();
  const q = fx.shotOf(shotP('sound', 'NORMAL'), 600, 400);
  call(ctx, 'sound', () => air.sound.shot(fx, ctx, q));
  assert.ok(ctx.n.ellipse >= 2, '음표 머리');
});

// ---------------------------------------------------------------- 7 입자 수
test('입자 수: 꼬리 · 처음 · 맞음 · 장판 · 돌진마다 정한 수 안', () => {
  const LIMIT = { trail: 60, launch: 30, impact: 90, zone: 220, rush: 120, swing: 40 };
  for (const sty of KEYS) {
    for (const ty of ['FLYING', 'ICE', 'WATER', 'STEEL']) {
      const trail = spawned((fx) => {
        const q = fx.shotOf(shotP(sty, ty), 600, 400);
        for (let f = 0; f < 120; f++) {
          fx.update(1 / 60);
          air[sty].trail(fx, q, 1 / 60);
        }
      }).length / 2;
      assert.ok(trail <= LIMIT.trail + 20, `${sty}/${ty} 꼬리 1초에 ${trail}`);   // + 처음 번쩍 (shotOf 의 launch)
      const launch = spawned((fx) => air[sty].launch(fx, fx.shotOf(shotP(sty, ty), 600, 400))).length;
      assert.ok(launch <= LIMIT.launch * 2, `${sty} launch ${launch}`);
      for (const why of ['hit', 'tele', 'ring', 'cone']) {
        const n = spawned((fx) => air[sty].impact(fx, 800, 450, 0, { light: '#ffffff', dark: '#888888' }, { why, ty, s: 1.35, r: 75, len: 360 })).length;
        assert.ok(n <= LIMIT.impact, `${sty}/${ty} impact ${why} ${n}`);
      }
      for (const kind of ['cone', 'ring', 'tele']) {
        if (!air[sty][kind]) continue;
        const n = spawned((fx) => {
          for (let f = 0; f <= 70; f++) {
            fx.update(1 / 60);
            const now = 10 + f / 60;
            if (now > 10.5 + 0.2) break;                 // 서버가 지운다
            air[sty][kind](fx, new RecCtx(), fx.zoneOf(zoneZ(kind, sty, ty), now));
          }
        }).length;
        assert.ok(n <= LIMIT.zone, `${sty}/${ty} ${kind} ${n}`);
      }
      if (!air[sty].rush) continue;
      const rush = spawned((fx) => {
        const a = rushOf(fx, sty, ty);
        for (let f = 0; f < 60; f++) {
          fx.update(1 / 60);
          air[sty].rush(fx, new RecCtx(), { ...a, stage: 'act', sk: 0.5, moved: 100 });
        }
      }).length;
      assert.ok(rush <= LIMIT.rush, `${sty}/${ty} rush 1초에 ${rush}`);
      const swing = spawned((fx) => {
        const a = rushOf(fx, sty, ty);
        for (let f = 0; f <= 20; f++) air[sty].swing(fx, new RecCtx(), a, f / 20);
      }).length;
      assert.ok(swing <= LIMIT.swing, `${sty}/${ty} swing ${swing}`);
    }
  }
});

// ---------------------------------------------------------------- 8 벤치
// 아무것도 안 하는 ctx - fx 자신의 JS 시간만 잰다 (실제 그리기는 GPU 가 한다)
class NopCtx {
  constructor() {
    Object.assign(this, { globalAlpha: 1, globalCompositeOperation: 'source-over', fillStyle: '#000000',
      strokeStyle: '#000000', lineWidth: 1, lineDashOffset: 0, lineCap: 'butt', lineJoin: 'miter',
      font: '10px sans-serif', textAlign: 'start', textBaseline: 'alphabetic' });
  }
  createRadialGradient() { return { addColorStop() {} }; }
}
for (const name of [...PLAIN, ...POINTS, 'fill', 'stroke', 'save', 'restore', 'translate', 'rotate', 'scale', 'arc', 'ellipse',
  'drawImage', 'fillText', 'strokeText', 'setLineDash']) {
  NopCtx.prototype[name] = function () {};
}

test('한 프레임 (2마리 · 바람 집안 탄 20 · 장판 넷이 표시 → 터짐을 되풀이 · 돌진 · 입자 400 언저리) 이 3 ms 안', (t) => {
  const fx = new Fx({ canvas: (w, h) => ({ width: w, height: h, getContext: () => new NopCtx() }) });
  const ctx = new NopCtx();
  const world = makeWorld('a');
  const shots = Array.from({ length: 20 }, (_, i) => shotP(KEYS[i % KEYS.length], TYPES[i % TYPES.length], i, { y: 300 + i * 20 }));
  // 장판은 1초마다 새로 - 0.5초 표시하고 터져서 0.2초 뒤 사라진다 (터지는 첫 장의 입자도 잰다)
  const zonesAt = (now) => {
    const cyc = Math.floor(now), t1 = cyc + 0.5;
    if (now > t1 + 0.2) return [];
    return [['cone', 'wind', 'DRAGON'], ['ring', 'wave', 'WATER'], ['tele', 'wind', 'FLYING'], ['cone', 'shard', 'ICE']]
      .map(([kind, sty, ty], i) => zoneZ(kind, sty, ty, cyc * 10 + i, { t0: cyc, t1 }));
  };
  const hit = { e: 'hit', w: 'a', v: 'b', k: 'K', ty: 'FLYING', hpr: 500, eff: 2, crit: false, x: 1200, y: 450 };
  const run = (frames, now0) => {
    let parts = 0;
    const t0 = performance.now();
    for (let f = 0; f < frames; f++) {
      const now = now0 + f / 60;
      world.at.a.x = 400 + Math.sin(now) * 200;
      world.at.b.y = 450 + Math.cos(now) * 200;
      if (f % 30 === 0) {
        const sty = ['wind', 'jet', 'shard'][(f / 30) % 3];
        fx.event({ e: 'cast', w: 'a', k: 'K', kind: f % 60 ? 'dash' : 'melee', ty: 'FLYING', sty, x: 400, y: 450, ang: 0, len: 300, r: 60 }, world);
      }
      if (f % 20 === 0) fx.event({ e: 'cast', w: 'a', k: 'K', kind: 'proj', ty: 'FLYING', sty: KEYS[(f / 20) % 5], x: 400, y: 450, ang: 0 }, world);
      if (fx.counts().particles < 400) fx.event(hit, world);
      fx.update(1 / 60);
      const s = fx.shake();
      for (const z of zonesAt(now)) fx.drawZone(ctx, z, now);
      fx.drawUnder(ctx);
      shots.forEach((p, i) => fx.drawProjectile(ctx, p, (p.x + now * 300 + i * 40) % 1600 || 1, p.y + s.y));
      fx.drawOver(ctx);
      parts += fx.counts().particles;
    }
    return { ms: (performance.now() - t0) / frames, parts: parts / frames };
  };
  run(240, 0);                                     // 데우기 (JIT · 스프라이트)
  const { ms, parts } = run(1200, 10);
  t.diagnostic(`바람 집안 한 프레임 평균 ${ms.toFixed(3)} ms (입자 평균 ${parts.toFixed(0)}, 탄 20 - wind sound jet wave shard, 장판 4, 돌진)`);
  assert.ok(parts >= 380, '입자가 400 언저리 (' + parts + ')');
  assert.ok(ms < 3, ms.toFixed(3) + ' ms');
});
