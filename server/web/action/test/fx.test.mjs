/* 이펙트 검사 (js/fx.js).

     node --test server/web/action/test/

   가짜 2D ctx 는 브라우저가 던지는 곳(음수 반지름)에서 똑같이 던지고, fx 가 하면 안 되는 일
   (화면 배율 setTransform 덮어쓰기 · NaN 좌표 · 0~1 밖 알파 · 빈 색)도 던진다.

   무엇을 못 박나
     1. 모양 키(STYLES)는 계획의 25개 그대로, 모르는 키는 orb 로 그린다.
     2. 모든 모양 키 × 모든 꼴 × 모든 장판 꼴이 예외 없이 그려진다.
     3. 그리고 나면 ctx 상태(save 짝 · 알파 · 혼합 · 점선)가 받은 그대로다.
     4. 그라디언트는 색마다 한 번 - 화면 ctx 에서는 아예 만들지 않는다.
     5. update 가 입자를 나이 먹여 지운다. 풀은 600 을 넘지 않고, 넘치면 가장 먼저 만든 것부터 덮는다.
     6. 계획의 모든 이벤트를 받는다 (world 가 없어도, 칸이 빠져도). 옛 서버의 dodge (피하기는 뺐다) 는 그리지 않고 넘긴다.
     7. 맞음: 효과 굉장 · 별로 · 없음 · 급소 글씨와 데미지 숫자.
     8. 표시(tele)는 t1 쪽으로 차오르고, 떨어지면 먼지가 한 번 인다. 설치 함정은 기술마다 제 무늬 (압정뿌리기는
        모양 키가 rock 이어도 압정, 스텔스록만 떠 있는 돌).
     9. 화면 흔들림은 0 으로 줄어든다.
    10. 한 프레임 (2마리 · 탄 20 · 입자 400) 이 3 ms 안. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { Fx, Particles, STYLES, POOL_MAX, charge } from '../js/fx.js';
import { TYPE_FX } from '../js/consts.js';
import { HitStop } from '../js/feel.js';

// 계획 (design-notes/2026-11-18-action-battle-plan.md) 의 STYLES · KINDS · Z.kind
const PLAN_STYLES = ['orb', 'flame', 'jet', 'zap', 'leaf', 'shard', 'psy', 'rock', 'ghost', 'dark', 'fairy',
  'poison', 'wind', 'sound', 'punch', 'slash', 'bite', 'beam', 'wave', 'quake', 'heal', 'buff', 'shield',
  'powder', 'web'];
const KINDS = ['proj', 'beam', 'melee', 'dash', 'burst', 'cone', 'strike', 'leap', 'self', 'heal', 'guard',
  'counter', 'hazard', 'status'];
const ZONE_KINDS = ['tele', 'haz', 'ring', 'cone', 'beam'];
const TYPES = Object.keys(TYPE_FX);

// ---------------------------------------------------------------- 가짜 2D ctx
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
  'fill', 'stroke', 'fillRect', 'strokeRect', 'rotate', 'scale', 'clip'];

class RecCtx {
  constructor() {
    this.n = Object.create(null);     // 부른 횟수
    this.trace = null;                // 배열을 주면 부른 이름을 차례로 적는다
    this.texts = [];
    this.radii = [];
    this.shifts = [];                 // translate 자리
    this.stack = [];
    this.st = {
      globalAlpha: 1, globalCompositeOperation: 'source-over', fillStyle: '#000000', strokeStyle: '#000000',
      lineWidth: 1, lineDashOffset: 0, lineCap: 'butt', lineJoin: 'miter', font: '10px sans-serif',
      textAlign: 'start', textBaseline: 'alphabetic', dash: [],
    };
  }

  rec(name, args) {
    this.n[name] = (this.n[name] || 0) + 1;
    if (this.trace) this.trace.push(name);
    for (const a of args) if (typeof a === 'number' && !Number.isFinite(a)) throw new TypeError(`${name}: 숫자가 아니다 (${a})`);
  }

  save() { this.rec('save', []); this.stack.push({ ...this.st, dash: this.st.dash.slice() }); }
  restore() {
    this.rec('restore', []);
    if (!this.stack.length) throw new Error('restore 가 save 보다 많다');
    this.st = this.stack.pop();
  }
  arc(x, y, r, a0, a1, ccw) {
    this.rec('arc', [x, y, r, a0, a1]);
    if (r < 0) throw new RangeError('IndexSizeError: arc 반지름이 음수');
    this.radii.push(r);
  }
  ellipse(x, y, rx, ry, rot, a0, a1) {
    this.rec('ellipse', [x, y, rx, ry, rot, a0, a1]);
    if (rx < 0 || ry < 0) throw new RangeError('IndexSizeError: ellipse 반지름이 음수');
  }
  createRadialGradient(x0, y0, r0, x1, y1, r1) {
    this.rec('createRadialGradient', [x0, y0, r0, x1, y1, r1]);
    if (r0 < 0 || r1 < 0) throw new RangeError('IndexSizeError: 그라디언트 반지름이 음수');
    return { addColorStop(at, col) {
      if (!(at >= 0 && at <= 1) || !COLOR.test(col)) throw new TypeError(`addColorStop(${at}, ${col})`);
    } };
  }
  drawImage(img, ...nums) {
    this.rec('drawImage', nums);
    if (!img || !(img.width > 0)) throw new TypeError('drawImage: 그림이 아니다');
  }
  translate(x, y) { this.rec('translate', [x, y]); this.shifts.push([x, y]); }
  fillText(s, x, y) { this.rec('fillText', [x, y]); this.texts.push(String(s)); }
  strokeText(s, x, y) { this.rec('strokeText', [x, y]); }
  setLineDash(a) {
    this.rec('setLineDash', []);
    if (!Array.isArray(a) || a.some((v) => !Number.isFinite(v) || v < 0)) throw new TypeError('setLineDash');
    this.st.dash = a.slice();
  }
  setTransform() { throw new Error('fx 가 화면 배율(setTransform)을 덮어쓴다'); }
  resetTransform() { throw new Error('fx 가 화면 배율(resetTransform)을 덮어쓴다'); }
  transform() { throw new Error('fx 는 transform 을 쓰지 않는다'); }
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

// 스프라이트 캔버스를 만드는 곳. 만든 ctx 를 sprites 에 모은다
function canvasMaker(sprites) {
  return (w, h) => {
    const ctx = new RecCtx();
    sprites.push(ctx);
    return { width: w, height: h, getContext: () => ctx };
  };
}

function newFx() {
  const sprites = [];
  return { fx: new Fx({ canvas: canvasMaker(sprites) }), sprites };
}

// 그리기 하나가 ctx 를 받은 그대로 돌려놓았나
function clean(ctx, what) {
  assert.equal(ctx.stack.length, 0, what + ': save/restore 짝');
  assert.equal(ctx.globalAlpha, 1, what + ': globalAlpha');
  assert.equal(ctx.globalCompositeOperation, 'source-over', what + ': 혼합');
  assert.deepEqual(ctx.st.dash, [], what + ': 점선');
}

function makeWorld(you = 'a') {
  const at = { a: { x: 400, y: 450 }, b: { x: 1200, y: 450 } };
  return { pos: (s) => at[s], now: 10, you, at };
}

// 한 프레임: 나이 먹이고 아래 · 위를 그린다
function frame(fx, ctx, dt = 1 / 60) {
  fx.update(dt);
  fx.drawUnder(ctx);
  clean(ctx, 'drawUnder');
  fx.drawOver(ctx);
  clean(ctx, 'drawOver');
}

const shot = (sty, i = 0, extra = {}) => ({
  id: 'p' + i, o: 'a', k: 'TEST', ty: TYPES[i % TYPES.length], sty,
  x: 500 + i, y: 400, vx: 420, vy: -60, r: 14, ...extra,
});
const zone = (kind, sty, i = 0, extra = {}) => ({
  id: 'z' + kind + i, o: i % 2 ? 'a' : 'b', k: 'TEST', ty: TYPES[i % TYPES.length], sty, kind,
  x: 800, y: 450, r: 90, ang: 0.4, len: 520, w: 60, t0: 10, t1: 11, ...extra,
});

// 계획의 이벤트 전부 (칸 이름도 계획 그대로)
const EVENTS = [
  { e: 'cast', w: 'a', m: 0, k: 'FLAMETHROWER', kind: 'proj', ty: 'FIRE', sty: 'flame', x: 400, y: 450, ang: 0 },
  { e: 'hit', w: 'a', v: 'b', k: 'FLAMETHROWER', ty: 'FIRE', hpr: 640, eff: 2, crit: true, x: 1200, y: 450 },
  { e: 'hit', w: 'b', v: 'a', k: 'TACKLE', ty: 'NORMAL', dmg: 37, hpr: 800, eff: 1, crit: false, x: 400, y: 450 },
  { e: 'hit', w: 'a', v: 'b', k: 'VINEWHIP', ty: 'GRASS', hpr: 600, eff: 0.5, crit: false, x: 1200, y: 450 },
  { e: 'hit', w: 'a', v: 'b', k: 'SHADOWBALL', ty: 'GHOST', hpr: 600, eff: 0, crit: false, x: 1200, y: 450 },
  { e: 'clash', x: 800, y: 450, k1: 'SHADOWBALL', k2: 'FLAMETHROWER' },
  ...['brn', 'psn', 'tox', 'par', 'slp', 'frz', 'cnf', 'seed', 'trap', 'flinch', 'scr', 'zzz'].map((s) => ({ e: 'status', w: 'b', s })),
  { e: 'cure', w: 'b', s: 'brn' },
  { e: 'cure', w: 'b', s: 'flinch' },
  { e: 'stat', w: 'a', st: 'atk', d: 2 },
  { e: 'stat', w: 'b', st: 'spe', d: -1 },
  { e: 'stat', w: 'b', st: 'zzz', d: -6 },
  { e: 'heal', w: 'a', hpr: 900 },
  { e: 'guard', w: 'b' },
  { e: 'counter', w: 'b' },
  { e: 'swap', w: 'a', fr: 0, to: 2 },
  { e: 'ko', w: 'b', i: 1 },
  { e: 'need', w: 'b' },
  { e: 'phase', ph: 'ready' },
  { e: 'phase', ph: 'fight' },
  { e: 'over', winner: 'a', reason: 'ko' },
  { e: 'over', winner: 'draw', reason: 'timeout' },
  { e: 'txt', w: 'a', msg: '방어가 풀렸다' },
];

// ---------------------------------------------------------------- 검사
test('모양 키는 계획의 25개 그대로 (common/action_moves.STYLES 와 같은 차례)', () => {
  assert.deepEqual([...STYLES], PLAN_STYLES);
});

test('모든 모양 키 × 모든 꼴: 쓰기 · 탄 · 입자가 예외 없이 그려진다', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld();
  let i = 0;
  for (const sty of [...PLAN_STYLES, 'zzz', undefined]) {
    for (const kind of [...KINDS, 'none', 'zzz']) {
      const ty = TYPES[i % TYPES.length];
      fx.event({ e: 'cast', w: i % 2 ? 'b' : 'a', m: i % 4, k: 'TEST', kind, ty, sty, x: 400, y: 450, ang: i * 0.7 }, world);
      for (let f = 0; f < 6; f++) {
        world.at.a.x += 9;                        // 따라가는 이펙트 (휘두름 · 잔상) 가 움직이는 자리를 읽는다
        fx.drawProjectile(ctx, shot(sty, i, { vx: f === 0 ? 0 : 420, vy: f === 0 ? 0 : -60 }), 500 + f * 7, 400);
        clean(ctx, `drawProjectile ${sty}/${kind}`);
        frame(fx, ctx, 0.05);
      }
      world.at.a.x = 400;
      i++;
    }
  }
  assert.ok(ctx.n.drawImage > 1000, '빛 스프라이트를 그렸다');
  assert.ok(ctx.n.fill > 100 && ctx.n.stroke > 100, '모양을 그렸다');
});

test('모르는 모양 키는 orb 와 똑같이 그린다', () => {
  const draw = (sty) => {
    const { fx } = newFx();
    const ctx = new RecCtx();
    ctx.trace = [];
    fx.drawProjectile(ctx, shot(sty), 500, 400);
    return ctx.trace;
  };
  assert.deepEqual(draw('zzz'), draw('orb'));
  assert.deepEqual(draw(undefined), draw('orb'));
  assert.notDeepEqual(draw('flame'), draw('orb'));
});

test('모든 장판 꼴 × 모양 키 × 시각이 예외 없이 그려진다', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  fx.event({ e: 'phase', ph: 'fight' }, makeWorld('a'));
  let i = 0;
  for (const kind of [...ZONE_KINDS, 'zzz']) {
    for (const sty of [...PLAN_STYLES, 'zzz']) {
      for (const now of [9.9, 10, 10.5, 10.9, 10.99, 11, 11.2, 13]) {
        fx.drawZone(ctx, zone(kind, sty, i), now);
        clean(ctx, `drawZone ${kind}/${sty}@${now}`);
      }
      frame(fx, ctx, 0.02);
      i++;
    }
  }
  // 칸이 빠지거나 시각이 겹친 장판
  for (const kind of ZONE_KINDS) {
    fx.drawZone(ctx, { id: 'bare-' + kind, kind }, 0);
    fx.drawZone(ctx, zone(kind, 'orb', 0, { id: 'flat-' + kind, t0: 5, t1: 5, r: 0, len: 0, w: 0 }), 5);
    clean(ctx, 'drawZone 빈 칸 ' + kind);
  }
  for (let f = 0; f < 30; f++) frame(fx, ctx, 0.05);
});

test('표시(tele)는 t1 쪽으로 차오른다', () => {
  const z = { t0: 10, t1: 12 };
  assert.equal(charge(z, 9), 0);
  assert.equal(charge(z, 10), 0);
  assert.equal(charge(z, 11), 0.5);
  assert.equal(charge(z, 12), 1);
  assert.equal(charge(z, 99), 1);
  assert.equal(charge({ t0: 5, t1: 5 }, 5), 1);
  assert.equal(charge({}, 3), 0);
  assert.equal(charge(z, NaN), 0);
  // 차오르는 원의 반지름이 r × 진행
  const { fx } = newFx();
  for (const u of [0.25, 0.5, 0.9]) {
    const ctx = new RecCtx();
    fx.drawZone(ctx, zone('tele', 'rock', 0, { t0: 10, t1: 11, r: 80 }), 10 + u);
    assert.ok(ctx.radii.some((r) => Math.abs(r - 80 * u) < 1e-9), `진행 ${u} 의 원 (${ctx.radii})`);
    assert.ok(ctx.radii.includes(80), '테두리는 처음부터 다 보인다');
  }
});

test('표시가 떨어지면 먼지가 한 번 인다', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  fx.drawZone(ctx, zone('tele', 'rock', 0), 10.95);
  assert.equal(fx.counts().particles, 0, '떨어지기 전에는 입자가 없다');
  for (let f = 0; f < 3; f++) fx.update(0.1);      // 서버가 장판을 지웠다 - 더 그리지 않는다
  assert.ok(fx.counts().particles > 5, '떨어진 자리에 먼지 · 파편');
  const far = newFx().fx;                          // t1 한참 전에 지워진 표시(취소)는 떨어지지 않는다
  far.drawZone(ctx, zone('tele', 'rock', 0), 10.3);
  for (let f = 0; f < 3; f++) far.update(0.1);
  assert.equal(far.counts().particles, 0);
  const fx2 = newFx().fx;                          // 떨어진 뒤에 그려도 한 번만
  fx2.drawZone(ctx, zone('beam', 'beam', 1), 11.05);
  const once = fx2.counts().particles;
  assert.ok(once > 0);
  fx2.drawZone(ctx, zone('beam', 'beam', 1), 11.1);
  fx2.drawZone(ctx, zone('beam', 'beam', 1), 11.15);
  assert.equal(fx2.counts().particles, once);
  for (let f = 0; f < 3; f++) fx2.update(0.1);
  assert.ok(fx2.counts().particles <= once, '지워질 때 또 터지지 않는다');
});

test('설치 함정 무늬는 기술 키로 먼저 고른다 - 압정뿌리기(sty rock)는 압정, 스텔스록은 돌', () => {
  // 같은 장판(같은 id · 자리 · 색)을 k · sty 만 바꿔 그린다. 반짝임(star)은 돌 무늬만 쓴다
  const draw = (k, sty) => {
    const { fx } = newFx();
    let stars = 0;
    const star = fx.ink.star.bind(fx.ink);
    fx.ink.star = (...a) => { stars += 1; star(...a); };
    const ctx = new RecCtx();
    ctx.trace = [];
    fx.drawZone(ctx, zone('haz', sty, 0, { id: 'zh', k, t0: 0, t1: 1e9 }), 10);
    clean(ctx, 'haz ' + k);
    return { stars, trace: ctx.trace.join(' ') };
  };
  const spikes = draw('TEST', 'zzz');         // 모르는 모양 키는 압정 무늬
  const rock = draw('TEST', 'rock');
  assert.equal(spikes.stars, 0);
  assert.ok(rock.stars > 0, '돌 무늬는 반짝인다');
  const sp = draw('SPIKES', 'rock');
  assert.equal(sp.stars, 0, '압정뿌리기는 돌처럼 반짝이지 않는다');
  assert.equal(sp.trace, spikes.trace, '압정뿌리기는 압정 무늬로 그린다');
  const sr = draw('STEALTHROCK', 'rock');
  assert.equal(sr.stars, rock.stars, '스텔스록은 돌 무늬 그대로');
  assert.equal(sr.trace, rock.trace);
  assert.equal(draw('TOXICSPIKES', 'rock').trace, draw('TEST', 'poison').trace, '독압정은 독 가시');
  assert.equal(draw('STICKYWEB', 'rock').trace, draw('TEST', 'web').trace, '끈적끈적네트는 거미줄');
  assert.equal(draw('__proto__', 'rock').trace, rock.trace, '이상한 키는 모양 키로');
});

// 씨앗이 같으면 같은 차례 (mulberry32). 입자는 Math.random 으로 고르므로, 어느 (모양, 색) 스프라이트가 몇째 판에서
// 처음 나오는지가 돌릴 때마다 달라 검사가 가끔 깨졌다 - 씨앗을 박아 둔다
function seeded(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

test('그라디언트는 색마다 한 번 - 화면 ctx 에서는 만들지 않는다', () => {
  const random = Math.random;
  Math.random = seeded(20261118);
  try {
    const { fx, sprites } = newFx();
    const ctx = new RecCtx();
    const world = makeWorld();
    const round = () => {
      for (const ev of EVENTS) fx.event(ev, world);
      for (let f = 0; f < 20; f++) {
        PLAN_STYLES.forEach((sty, i) => fx.drawProjectile(ctx, shot(sty, i), 500, 400));
        ZONE_KINDS.forEach((kind, i) => fx.drawZone(ctx, zone(kind, PLAN_STYLES[i * 3], i), 10.5 + f * 0.05));
        frame(fx, ctx);
      }
    };
    const grads = () => sprites.reduce((n, s) => n + (s.n.createRadialGradient || 0), 0);
    for (let r = 0; r < 3; r++) round();     // 나올 (모양, 색) 이 다 나오게 몇 판 먼저
    const made = grads();
    assert.ok(made > 0, '스프라이트를 만들었다');
    round();
    round();
    assert.equal(grads(), made, '한 번 만든 색은 다시 만들지 않는다');
    assert.ok(sprites.every((s) => (s.n.createRadialGradient || 0) <= 1), '스프라이트 하나에 그라디언트 하나');
    assert.equal(ctx.n.createRadialGradient, undefined, '화면 ctx 에서 그라디언트를 만들지 않는다');
    assert.equal(ctx.n.createLinearGradient, undefined);
  } finally {
    Math.random = random;
  }
});

test('스프라이트를 못 만드는 곳에서도 그린다', () => {
  const fx = new Fx({ canvas: null });
  const ctx = new RecCtx();
  const world = makeWorld();
  for (const ev of EVENTS) fx.event(ev, world);
  for (let f = 0; f < 10; f++) {
    PLAN_STYLES.forEach((sty, i) => fx.drawProjectile(ctx, shot(sty, i), 500, 400));
    ZONE_KINDS.forEach((kind, i) => fx.drawZone(ctx, zone(kind, 'orb', i), 10.5 + f * 0.1));
    frame(fx, ctx);
  }
  assert.equal(ctx.n.drawImage, undefined);
  assert.ok(ctx.n.fill > 0);
  // 기본 (브라우저가 아닌 node) - OffscreenCanvas · document 가 없으면 스프라이트 없이
  const plain = new Fx();
  plain.event(EVENTS[1], world);
  frame(plain, ctx);
});

test('update 가 입자를 나이 먹여 지운다', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld();
  for (const ev of EVENTS) fx.event(ev, world);
  const start = fx.counts();
  assert.ok(start.particles > 50 && start.anims > 0 && start.texts > 0, JSON.stringify(start));
  for (let f = 0; f < 6; f++) frame(fx, ctx, 0.1);   // 쓰러짐의 멈춤(0.12초)이 지나도록
  assert.ok(fx.counts().particles < start.particles, '줄어든다');
  for (let f = 0; f < 40; f++) frame(fx, ctx, 0.1);
  assert.deepEqual(fx.counts(), { particles: 0, anims: 0, texts: 0 });
  fx.update(-1);                                   // 이상한 dt 는 0 으로
  fx.update(NaN);
  assert.deepEqual(fx.counts(), { particles: 0, anims: 0, texts: 0 });
});

test(`입자 풀은 ${POOL_MAX} 을 넘지 않는다`, () => {
  assert.equal(POOL_MAX, 600);
  const { fx } = newFx();
  const world = makeWorld();
  for (let i = 0; i < 300; i++) fx.event(EVENTS[1 + (i % 4)], world);
  assert.equal(fx.counts().particles, POOL_MAX);
  assert.ok(fx.counts().texts <= 24 && fx.counts().anims <= 48, JSON.stringify(fx.counts()));
});

test('풀이 넘치면 가장 먼저 만든 것부터 덮는다', () => {
  const pool = new Particles(4);
  for (let i = 1; i <= 4; i++) pool.spawn('glow', 0, 0, 0, 0, 10, i, '#ffffff');
  assert.equal(pool.live, 4);
  pool.spawn('glow', 0, 0, 0, 0, 10, 5, '#ffffff');
  assert.equal(pool.live, 4);
  assert.deepEqual(pool.all.filter((p) => p.on).map((p) => p.size).sort(), [2, 3, 4, 5]);
  pool.update(11);
  assert.equal(pool.live, 0);
});

test('계획의 모든 이벤트를 받는다 (world 가 없어도 · 칸이 빠져도)', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld('b');
  for (const ev of EVENTS) {
    fx.event(ev, world);
    frame(fx, ctx);
  }
  for (const ev of EVENTS) fx.event(ev);           // world 없음
  for (const ev of EVENTS) fx.event({ e: ev.e });  // 칸 없음
  fx.event({ e: 'zzz' }, world);
  fx.event({}, world);
  fx.event(null, world);
  fx.event({ e: 'cast', w: 'a', kind: 'melee' }, { pos: () => undefined, now: 0, you: 'a' });
  for (let f = 0; f < 60; f++) frame(fx, ctx, 0.05);
});

test('옛 서버의 dodge 이벤트는 던지지 않고 넘긴다 (피하기는 뺐다 - 2026-11-19)', () => {
  const { fx } = newFx();
  const ctx = new RecCtx();
  const world = makeWorld();
  fx.event({ e: 'dodge', w: 'a' }, world);
  fx.event({ e: 'dodge', w: 'b', x: 1200, y: 450 }, world);
  fx.event({ e: 'dodge' });
  assert.deepEqual(fx.counts(), { particles: 0, anims: 0, texts: 0 }, '아무것도 그리지 않는다');
  assert.equal(fx.hitstop.active, false, '멈추지도 않는다');
  frame(fx, ctx);
  assert.deepEqual(fx.shake(), { x: 0, y: 0 }, '흔들지도 않는다');
});

test('맞음: 효과 글씨 · 급소 · 데미지 숫자', () => {
  const said = (ev, you = 'a') => {
    const { fx } = newFx();
    const ctx = new RecCtx();
    fx.event(ev, makeWorld(you));
    fx.update(0.02);
    fx.drawOver(ctx);
    return ctx.texts;
  };
  const hit = { e: 'hit', w: 'a', v: 'b', k: 'X', ty: 'FIRE', hpr: 500, eff: 1, crit: false, x: 1200, y: 450 };
  assert.deepEqual(said(hit), []);
  assert.deepEqual(said({ ...hit, eff: 2 }), ['효과가 굉장했다!']);
  assert.deepEqual(said({ ...hit, eff: 4, crit: true }), ['효과가 굉장했다!', '급소!']);
  assert.deepEqual(said({ ...hit, eff: 0.5 }), ['효과가 별로인 듯하다…']);
  assert.deepEqual(said({ ...hit, eff: 0 }), ['효과가 없다']);
  assert.deepEqual(said({ ...hit, v: 'a', dmg: 37, crit: true }), ['37', '급소!']);
});

test('글씨: 같은 말 · 잇단 숫자는 하나로, 다른 글씨는 겹치지 않게 쌓는다', () => {
  const { fx } = newFx();
  const world = makeWorld('b');
  const hit = { e: 'hit', w: 'a', v: 'b', ty: 'FIRE', hpr: 500, eff: 2, crit: false, dmg: 10, x: 1200, y: 450 };
  for (let i = 0; i < 3; i++) {
    fx.event(hit, world);
    fx.update(0.05);
  }
  assert.equal(fx.counts().texts, 2, '여러 번 친 숫자는 하나 (10 → 20 → 30) + 효과 글씨 하나');
  assert.ok(fx.texts.some((t) => t.num && t.s === '30' && t.hits === 3), JSON.stringify(fx.texts.map((t) => t.s)));
  // 떨어져 맞으면 (합치는 때가 지나면) 숫자가 따로 뜨고, 서로 겹치지 않게 쌓인다
  for (let i = 0; i < 3; i++) {
    for (let f = 0; f < 40; f++) fx.update(1 / 60);
    fx.event({ ...hit, eff: [1, 0.5, 2][i] }, world);
  }
  assert.ok(fx.texts.filter((t) => t.num).length >= 2, '숫자가 따로');
  for (let f = 0; f < 60; f++) {
    fx.update(1 / 60);
    const ctx = new RecCtx();
    fx.drawOver(ctx);
    const ys = ctx.shifts.map(([, y]) => y).sort((p, q) => p - q);
    assert.equal(ys.length, fx.counts().texts);
    for (let i = 1; i < ys.length; i++) assert.ok(ys[i] - ys[i - 1] >= 30 - 1e-9, `겹친다: ${ys}`);
  }
});

test('데미지 숫자: 상대가 맞으면 %, 내가 맞으면 정확한 수 - 상성으로 색 · 크기, 급소는 띠', () => {
  const nums = (ev, you) => {
    const { fx } = newFx();
    fx.event(ev, makeWorld(you));
    return fx.texts.filter((t) => t.num);
  };
  const hit = { e: 'hit', w: 'a', v: 'b', k: 'X', ty: 'FIRE', hpr: 500, eff: 1, crit: false, x: 1200, y: 450 };
  // 때린 쪽(a): 상대 체력은 비율만 - main 이 적은 pct 로 '%'
  const mine = nums({ ...hit, pct: 12.4 }, 'a');
  assert.deepEqual(mine.map((t) => t.s), ['12%']);
  assert.equal(nums({ ...hit, pct: 0.2 }, 'a')[0].s, '1%', '깎였으면 적어도 1%');
  assert.deepEqual(nums({ ...hit, dmg: 33 }, 'a'), [], '상대의 정확한 데미지는 (와도) 안 쓴다');
  // 맞은 쪽(b): 정확한 데미지
  assert.deepEqual(nums({ ...hit, dmg: 33, pct: 12 }, 'b').map((t) => t.s), ['33']);
  // 상성: 굉장 크고 주황 금색 · 별로 작고 회색
  const [great] = nums({ ...hit, pct: 30, eff: 2 }, 'a');
  const [plain] = nums({ ...hit, pct: 30 }, 'a');
  const [weak] = nums({ ...hit, pct: 30, eff: 0.5 }, 'a');
  assert.ok(great.look.px > plain.look.px && plain.look.px > weak.look.px);
  assert.notEqual(great.fill, plain.fill);
  assert.notEqual(weak.fill, plain.fill);
  // 급소: 숫자에 '급소!' 띠가 붙는다 (따로 뜨는 글씨가 아니다)
  const { fx } = newFx();
  fx.event({ ...hit, pct: 20, crit: true }, makeWorld('a'));
  fx.update(0.02);
  const ctx = new RecCtx();
  fx.drawOver(ctx);
  assert.deepEqual(ctx.texts, ['20%', '급소!']);
  assert.equal(fx.counts().texts, 1);
  // 막혔으면 숫자 없음
  assert.deepEqual(nums({ ...hit, pct: 10, eff: 0 }, 'a'), []);
});

test('맞음: 멈춤은 render 와 같은 하나 (feel.hitstopSec) - 세게 · 급소 · 효과 굉장일수록 길게, 저절로 깎이는 것은 안 멈춘다', () => {
  const stopOf = (ev, you = 'a') => {
    const { fx } = newFx();
    fx.event(ev, makeWorld(you));
    return fx.hitstop.left;
  };
  const hit = { e: 'hit', w: 'a', v: 'b', k: 'X', ty: 'FIRE', hpr: 500, eff: 1, crit: false, x: 1200, y: 450 };
  const small = stopOf({ ...hit, pct: 3 }), big = stopOf({ ...hit, pct: 30 }), crit = stopOf({ ...hit, pct: 30, eff: 2, crit: true });
  assert.ok(small >= 0.05 - 1e-9 && small < big && big < crit && crit <= 0.11 + 1e-9, [small, big, crit].join(' '));
  assert.equal(stopOf({ ...hit, pct: 30, eff: 0 }), 0, '막혔다');
  assert.equal(stopOf({ ...hit, w: 'b', v: 'b', k: 'LIFEORB', pct: 10 }), 0, '반동');
  assert.equal(stopOf({ ...hit, w: 'b', v: 'b', k: 'brn', pct: 6 }), 0, '화상');
  assert.equal(stopOf({ e: 'ko', w: 'b', i: 0 }), 0.11, '쓰러뜨리면 가장 길게');
  // 넘겨받은 멈춤을 쓴다 (render 와 하나)
  const shared = new HitStop();
  const fx = new Fx({ canvas: null, hitstop: shared });
  fx.event({ ...hit, pct: 20 }, makeWorld('a'));
  assert.ok(shared.active && shared.left === fx.hitstop.left);
  fx.update(0.2);
  assert.equal(shared.active, false);
});

test('맞음: 내가 맞으면 크게, 내가 때리면 작게 흔들린다 · 급소 · 효과 굉장 · 쓰러짐은 화면이 살짝 다가간다', () => {
  const peak = (ev, you) => {
    const { fx } = newFx();
    fx.event(ev, makeWorld(you));
    let m = 0, z = 1;
    for (let f = 0; f < 30; f++) {
      fx.update(1 / 60);
      const s = fx.shake();
      m = Math.max(m, Math.hypot(s.x, s.y));
      z = Math.max(z, fx.zoom().k);
    }
    return { shake: m, zoom: z };
  };
  const hit = { e: 'hit', w: 'a', v: 'b', k: 'X', ty: 'FIRE', hpr: 500, eff: 1, crit: false, pct: 15, x: 1200, y: 450 };
  const dealt = peak(hit, 'a'), taken = peak({ ...hit, w: 'b', v: 'a', dmg: 40 }, 'a');
  assert.ok(taken.shake > dealt.shake * 2, `맞으면 ${taken.shake} · 때리면 ${dealt.shake}`);
  assert.equal(dealt.zoom, 1, '보통 맞음은 다가가지 않는다');
  const crit = peak({ ...hit, crit: true }, 'a').zoom, ko = peak({ e: 'ko', w: 'b', i: 0, x: 1200, y: 450 }, 'a').zoom;
  assert.ok(crit > 1 && crit <= 1.03 + 1e-9, String(crit));
  assert.ok(ko > 1 && ko <= 1.03 + 1e-9, String(ko));
  const { fx } = newFx();
  fx.event({ ...hit, eff: 2 }, makeWorld('a'));
  for (let f = 0; f < 40; f++) fx.update(1 / 60);
  assert.equal(fx.zoom().k, 1, '돌아온다');
});

test('누르자마자 준비 빛: cast 가 오면 넘겨받고 (두 번 모이지 않게), 안 오면 0.25초 뒤 사그라든다', () => {
  const { fx } = newFx();
  const world = makeWorld('a');
  fx.event({ e: 'phase', ph: 'fight' }, world);
  fx.prewind('a', 'FIRE');
  assert.equal(fx.anims.filter((a) => a.kind === 'pre').length, 1);
  for (let f = 0; f < 6; f++) fx.update(1 / 60);
  fx.event({ e: 'cast', w: 'a', m: 0, k: 'EMBER', kind: 'proj', ty: 'FIRE', sty: 'flame', x: 400, y: 450, ang: 0 }, world);
  const charge = fx.anims.find((a) => a.kind === 'charge');
  assert.ok(charge && charge.age > 0.05, '준비 빛이 처음부터 다시 시작하지 않는다 (' + (charge && charge.age) + ')');
  fx.update(1 / 60);
  assert.equal(fx.anims.filter((a) => a.kind === 'pre').length, 0, '누르자마자 빛은 끝난다');
  // 안 오면
  const lone = newFx().fx;
  lone.event({ e: 'phase', ph: 'fight' }, world);
  lone.prewind('a', 'WATER');
  for (let f = 0; f < 12; f++) lone.update(1 / 60);
  assert.equal(lone.anims.filter((a) => a.kind === 'pre').length, 1, '0.25초 안');
  for (let f = 0; f < 20; f++) lone.update(1 / 60);
  assert.equal(lone.anims.filter((a) => a.kind === 'pre').length, 0, '사그라든다');
  const ctx = new RecCtx();
  lone.prewind('b', 'ZZZ');
  frame(lone, ctx);
});

test('능력 랭크: 단계만큼 화살이 늘고 크기는 그대로', () => {
  const arrows = (d) => {
    const { fx } = newFx();
    fx.event({ e: 'stat', w: 'a', st: 'atk', d }, makeWorld());
    return fx.parts.all.filter((p) => p.on && p.shape === 'arrow');
  };
  assert.equal(arrows(1).length, 4);
  assert.equal(arrows(3).length, 12);
  assert.equal(arrows(6).length, 12, '세 단계까지만');
  assert.ok(arrows(3).every((p) => p.size <= 9 * 1.3 + 1e-9));
  assert.ok(arrows(-2).every((p) => p.vy > 0), '내려가면 아래로');
});

test('화면 흔들림은 0 으로 줄어든다', () => {
  const { fx } = newFx();
  assert.deepEqual(fx.shake(), { x: 0, y: 0 });
  fx.event({ e: 'hit', w: 'b', v: 'a', ty: 'ROCK', dmg: 80, hpr: 100, eff: 2, crit: true, x: 400, y: 450 }, makeWorld('a'));
  fx.event({ e: 'ko', w: 'a', i: 0 }, makeWorld('a'));
  let peak = 0;
  for (let f = 0; f < 20; f++) {
    fx.update(1 / 60);
    const s = fx.shake();
    peak = Math.max(peak, Math.hypot(s.x, s.y));
    assert.ok(Number.isFinite(s.x) && Number.isFinite(s.y));
  }
  assert.ok(peak > 2, '흔들린다 (' + peak + ')');
  for (let f = 0; f < 30; f++) fx.update(0.1);
  assert.deepEqual(fx.shake(), { x: 0, y: 0 });
});

// ---------------------------------------------------------------- 벤치
// 아무것도 안 하는 ctx - fx 자신의 JS 시간만 잰다 (실제 그리기는 GPU 가 한다)
class NopCtx {
  constructor() {
    Object.assign(this, { globalAlpha: 1, globalCompositeOperation: 'source-over', fillStyle: '#000000',
      strokeStyle: '#000000', lineWidth: 1, lineDashOffset: 0, lineCap: 'butt', lineJoin: 'miter',
      font: '10px sans-serif', textAlign: 'start', textBaseline: 'alphabetic' });
  }
  createRadialGradient() { return { addColorStop() {} }; }
}
for (const name of [...PLAIN, 'save', 'restore', 'translate', 'arc', 'ellipse', 'drawImage', 'fillText', 'strokeText', 'setLineDash']) {
  NopCtx.prototype[name] = function () {};
}

test('한 프레임 (2마리 · 탄 20 · 입자 400) 이 3 ms 안', (t) => {
  const fx = new Fx({ canvas: (w, h) => ({ width: w, height: h, getContext: () => new NopCtx() }) });
  const ctx = new NopCtx();
  const world = makeWorld('a');
  const shots = Array.from({ length: 20 }, (_, i) => shot(PLAN_STYLES[i % PLAN_STYLES.length], i));
  const zones = [zone('tele', 'rock', 0, { t0: 0, t1: 1e9 }), zone('beam', 'beam', 1, { t0: 0, t1: 0 }),
    zone('haz', 'rock', 2, { t0: 0, t1: 1e9 }), zone('cone', 'wind', 3, { t0: 0, t1: 1e9 })];
  const hit = { e: 'hit', w: 'a', v: 'b', ty: 'FIRE', hpr: 500, eff: 2, crit: false, x: 1200, y: 450 };
  const run = (frames, now0) => {
    let parts = 0;
    const t0 = performance.now();
    for (let f = 0; f < frames; f++) {
      const now = now0 + f / 60;
      world.at.a.x = 400 + Math.sin(now) * 200;
      world.at.b.y = 450 + Math.cos(now) * 200;
      if (f % 30 === 0) fx.event({ e: 'cast', w: 'a', kind: 'melee', ty: 'FIGHTING', sty: 'punch', x: 400, y: 450, ang: 0 }, world);
      if (f % 45 === 0) fx.event({ e: 'cast', w: 'b', kind: 'guard', ty: 'NORMAL', sty: 'shield', x: 1200, y: 450, ang: 3 }, world);
      if (fx.counts().particles < 400) fx.event(hit, world);
      fx.update(1 / 60);
      const s = fx.shake();
      for (const z of zones) fx.drawZone(ctx, z, now);
      fx.drawUnder(ctx);
      shots.forEach((p, i) => fx.drawProjectile(ctx, p, (p.x + now * 300 + i * 40) % 1600, p.y + s.y));
      fx.drawOver(ctx);
      parts += fx.counts().particles;
    }
    return { ms: (performance.now() - t0) / frames, parts: parts / frames };
  };
  run(240, 0);                                     // 데우기 (JIT · 스프라이트)
  const { ms, parts } = run(1200, 10);
  t.diagnostic(`한 프레임 평균 ${ms.toFixed(3)} ms (입자 평균 ${parts.toFixed(0)}, 탄 20, 장판 ${zones.length})`);
  assert.ok(parts >= 380, '입자가 400 언저리 (' + parts + ')');
  assert.ok(ms < 3, ms.toFixed(3) + ' ms');
});
