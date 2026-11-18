/* 장판 (Z.kind 마다) - 표시는 여기서, 몸통은 모양 훅이.

   표시(t0 → t1)는 언제 · 어디에 떨어지는지 또렷해야 한다: 어떤 바닥에서도 보이는 테두리, t1 쪽으로 차오르는 채움,
   상대 것이면 빨간 테 + 도는 점선, 떨어지기 직전 깜박임. 이것은 모양과 상관없이 여기서 그린다.
   차례 (q.phase 'mark'): 바닥 칠 → 모양 훅 (save/restore) → 차오름 → 테두리 → 꼴마다 덧 (광선 겨눈 선 · 내려찍기 그림자 + fall).
   t1 뒤 (q.phase 'fire'): 모양 훅만. 함정(haz): 바닥 칠 · 점선 테두리 → 모양 훅.
   FIRES 는 t1 에 한 번 터지는 입자 (조각 · 먼지 · 흔들림) + 모양의 impact. */
import {
  A, BASE, BEAM_W, CONE_HALF, DASH, DUST, FALL_FROM, FALL_H, FIRE_SEC, HAZ_IN, INK, SOLID, TAU, WARN, WHITE,
  circle, clamp01, debrisSpec, easeOut, line, own, rnd, wedge,
} from './core.js';
import { hookOf, styleDef } from './styles/index.js';

const BLINK_FROM = 0.85;         // 표시가 이만큼 차면 테두리가 깜박인다

// 함정 기술 → 무늬 모양 키. 압정뿌리기(땅)는 모양 키가 rock 이라 기술 키를 먼저 본다 (엔진도 둘을 따로 다룬다)
const HAZ_BY_KEY = { STEALTHROCK: 'rock', SPIKES: '', TOXICSPIKES: 'poison', STICKYWEB: 'web' };

/** 부채꼴 반각 - 폭(w)은 끝에서의 너비 (아레나 단위). */
export const coneHalf = (q) => (q.w > 0 ? Math.atan2(q.w / 2, q.len) : CONE_HALF);

/** 그리기 전에 꼴마다 정해지는 칸 (drawZone 이 zoneOf 다음에 부른다). */
export function shapeZone(q) {
  q.phase = q.u < 1 ? 'mark' : 'fire';
  q.e = clamp01(q.since / (own(FIRE_SEC, q.kind) || 0.3));
  q.h = coneHalf(q);
  q.W = q.w > 0 ? q.w : BEAM_W;
  q.rr = q.r * (0.2 + 0.8 * easeOut(q.e));
  q.grow = Number.isFinite(q.t0) ? 0.3 + 0.7 * clamp01((q.now - q.t0) / HAZ_IN) : 1;
  q.hr = q.r * q.grow;
}

// ---------------------------------------------------------------- 표시
// 바닥은 처음엔 옅고 t1 쪽으로 진해진다
function markFill(ctx, q) {
  ctx.globalCompositeOperation = 'source-over';
  ctx.globalAlpha = A(0.12 + 0.2 * q.u);
  ctx.fillStyle = q.c.dark;
  ctx.fill();
}

// 차오르는 부분 - 다 차면 떨어진다
function markCharge(ctx, q) {
  ctx.globalCompositeOperation = 'source-over';
  ctx.globalAlpha = A(0.2 + 0.35 * q.u);
  ctx.fillStyle = q.c.light;
  ctx.fill();
}

// 테두리 - 어떤 바닥에서도 보이게 어두운 받침을 깔고, 상대 것은 빨간 테 + 도는 점선, 떨어지기 직전엔 깜박인다
function markEdge(fx, ctx, q) {
  ctx.globalCompositeOperation = 'source-over';
  ctx.globalAlpha = 0.5;
  ctx.strokeStyle = INK;
  ctx.lineWidth = 6;
  ctx.stroke();
  const blink = q.u > BLINK_FROM && Math.sin(fx.clock * 40) > 0;
  ctx.globalAlpha = 1;
  ctx.lineWidth = q.foe ? 3 : 2;
  ctx.strokeStyle = blink ? WHITE : q.foe ? WARN : q.c.light;
  ctx.stroke();
  if (!q.foe) return;
  ctx.setLineDash(DASH);
  ctx.lineDashOffset = -fx.clock * 60;
  ctx.strokeStyle = q.c.light;
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.setLineDash(SOLID);
}

// 광선 띠 (x, y 에서 ang 쪽으로 len × k, 폭 W) - 아레나 좌표로 바로
function beamPath(ctx, q, k) {
  const c = Math.cos(q.ang), s = Math.sin(q.ang), hw = q.W / 2, L = q.len * k;
  ctx.beginPath();
  ctx.moveTo(q.x + s * hw, q.y - c * hw);
  ctx.lineTo(q.x + c * L + s * hw, q.y + s * L - c * hw);
  ctx.lineTo(q.x + c * L - s * hw, q.y + s * L + c * hw);
  ctx.lineTo(q.x - s * hw, q.y + c * hw);
  ctx.closePath();
}

// 꼴마다: 표시 경로 (k = 0~1 차오른 만큼) · 테두리 위에 더 그리는 것
const KINDS = {
  tele: {
    path: (ctx, q, k) => circle(ctx, q.x, q.y, q.r * k),
    over(fx, ctx, q) {                          // 그림자가 먼저 진해지고, 그 위로 떨어진다
      if (q.u <= FALL_FROM) return;
      const v = (q.u - FALL_FROM) / (1 - FALL_FROM);
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = A(0.25 + 0.35 * v);
      ctx.fillStyle = INK;
      ctx.beginPath();
      ctx.ellipse(q.x, q.y, q.r * 0.3 * (0.5 + v), q.r * 0.15 * (0.5 + v), 0, 0, TAU);
      ctx.fill();
      paint(fx, ctx, q, hookOf(q.sty, 'fall'), q.x, q.y - (1 - v) * FALL_H, v);
    },
  },
  ring: { path: (ctx, q, k) => circle(ctx, q.x, q.y, q.r * k) },
  cone: { path: (ctx, q, k) => wedge(ctx, q.x, q.y, q.len * k, q.ang, q.h) },
  beam: {
    path: beamPath,
    over(fx, ctx, q) {                          // 겨눈 선 - 쏘기가 다가올수록 빨리 깜박인다 + 입 앞에 모이는 빛
      const ex = q.x + Math.cos(q.ang) * q.len, ey = q.y + Math.sin(q.ang) * q.len;
      ctx.globalCompositeOperation = 'lighter';
      ctx.globalAlpha = Math.sin(fx.clock * (12 + 40 * q.u)) > 0 ? 0.9 : 0.35;
      line(ctx, WHITE, 1.5, q.x, q.y, ex, ey);
      fx.ink.core(ctx, q.c.light, q.x, q.y, 8 + 26 * q.u, 0.5 + 0.5 * q.u);
    },
  },
};

// 모양 훅 하나를 깨끗한 ctx 로 (알파 1 · 빛 혼합 · 둥근 끝) 부르고 돌려놓는다 - 훅이 무엇을 바꿔도 표시는 그대로다
function paint(fx, ctx, q, hook, ...more) {
  if (!hook) return;
  ctx.save();
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'lighter';
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  hook(fx, ctx, q, ...more);
  ctx.restore();
}

// 모르는 꼴 - 원 표시만
function plainMark(fx, ctx, q) {
  circle(ctx, q.x, q.y, q.r);
  markFill(ctx, q);
  if (q.u > 0) {
    circle(ctx, q.x, q.y, q.r * q.u);
    markCharge(ctx, q);
  }
  circle(ctx, q.x, q.y, q.r);
  markEdge(fx, ctx, q);
}

function hazHook(q) {
  const by = own(HAZ_BY_KEY, q.k);
  if (by === '') return BASE.haz;
  return hookOf(by || q.sty, 'haz');
}

/** 장판 하나 (drawZone 이 save/restore 로 감싼다). */
export function paintZone(fx, ctx, q) {
  if (q.kind === 'haz') {
    circle(ctx, q.x, q.y, q.r);
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 0.14;
    ctx.fillStyle = q.c.dark;
    ctx.fill();
    ctx.setLineDash(DASH);
    ctx.globalAlpha = 0.6;
    ctx.strokeStyle = q.foe ? WARN : q.c.light;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.setLineDash(SOLID);
    paint(fx, ctx, q, hazHook(q));
    return;
  }
  const K = own(KINDS, q.kind);
  if (!K) {
    plainMark(fx, ctx, q);
    return;
  }
  const art = hookOf(q.sty, q.kind);
  if (q.phase === 'fire') {
    paint(fx, ctx, q, art);
    return;
  }
  K.path(ctx, q, 1);
  markFill(ctx, q);
  paint(fx, ctx, q, art);
  if (q.u > 0) {
    K.path(ctx, q, q.u);
    markCharge(ctx, q);
  }
  K.path(ctx, q, 1);
  markEdge(fx, ctx, q);
  if (K.over) K.over(fx, ctx, q);
}

// ---------------------------------------------------------------- t1 에 한 번 터지는 입자
function impact(fx, q, x, y, ang) {
  const hook = styleDef(q.sty).impact;
  if (hook) hook(fx, x, y, ang, q.c, { why: q.kind, k: q.k, ty: q.ty, sty: q.sty, eff: 1, crit: false, s: 1, r: q.r, len: q.len });
}

/** 그린 때가 t1 을 넘었을 때, 또는 t1 무렵에 서버가 지웠을 때 부른다. */
export const FIRES = {
  tele(fx, q) {                                 // 떨어진 자리 - 파편 · 먼지 · 그을음
    fx.burst(q.x, q.y, debrisSpec(styleDef(q.sty), q.ty), q.c, 1.4);
    fx.burst(q.x, q.y, DUST, q.c, 1, 0, TAU, 0, q.r * 0.5);
    fx.spawn('core', q.x, q.y, 0, 0, 0.18, q.r * 0.8, q.c.light).size1 = q.r * 1.4;
    fx.wave(q.x, q.y, q.c.light, q.r * 1.5, 0.35, 6, 0);
    fx.anim('scorch', null, q, 0, q.c, '', 1.2).k = q.r;
    fx.kick(0.18);
    impact(fx, q, q.x, q.y, Math.PI / 2);
  },
  ring(fx, q) {
    fx.burst(q.x, q.y, debrisSpec(styleDef(q.sty), q.ty), q.c, 1.6, 0, TAU, q.r * 0.85, q.r);
    fx.burst(q.x, q.y, DUST, q.c, 1.4, 0, TAU, q.r * 0.6, q.r);
    fx.kick(0.2);
    impact(fx, q, q.x, q.y, 0);
  },
  cone(fx, q) {
    fx.burst(q.x, q.y, debrisSpec(styleDef(q.sty), q.ty), q.c, 1.6, q.ang, coneHalf(q) * 2, q.len * 0.2, q.len);
    fx.kick(0.12);
    impact(fx, q, q.x + Math.cos(q.ang) * q.len * 0.6, q.y + Math.sin(q.ang) * q.len * 0.6, q.ang);
  },
  beam(fx, q) {                                 // 광선을 따라 옆으로 튀는 빛
    const spec = debrisSpec(styleDef(q.sty), q.ty), cx = Math.cos(q.ang), cy = Math.sin(q.ang);
    for (let i = 0; i < 16; i++) {
      const d = Math.random() * q.len, side = i % 2 ? 1 : -1, v = spec.v * rnd(0.4, 1);
      fx.particle(spec, q.c, q.x + cx * d, q.y + cy * d, -cy * side * v, cx * side * v);
    }
    fx.spawn('core', q.x + cx * q.len, q.y + cy * q.len, 0, 0, 0.25, 50, q.c.light).size1 = 90;
    fx.kick(0.22);
    impact(fx, q, q.x + cx * q.len, q.y + cy * q.len, q.ang);
  },
};
