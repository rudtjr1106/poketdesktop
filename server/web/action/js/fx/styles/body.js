/* 모양: 몸으로 치는 것 · 땅 · 기운 (punch slash bite rock quake web heal buff shield)
   + GENERIC: 근접 · 돌진(rush · swing)의 기본 그림 - 제 rush · swing 이 없는 모든 모양이 쓴다 (불꽃 · 번개의 몸통박치기도).
   + AURA: 회복 · 강화 · 방어를 쓸 때 몸에 두르는 그림. fx.js 의 pillar · shield 그림은 아직 모양을 보지 않는다 -
     이어 붙이면 AURA[sty](fx, ctx, a, t) (a = 그 anim, t 0~1) 를 부르면 된다.
   훅 이름 · 인자 · q · a 칸 · 도우미는 fx/core.js 맨 위. 기본 내보내기에는 이 아홉 키만 둔다 (fx/styles/index.js 의 FAMILY_OF).

   근접 · 돌진 (a)
     rush   준비: 달려갈 길 (길이 a.len · 폭 = 맞는 띠) 을 옅게 미리 보이고 웅크린다 (상대 것은 장판처럼 빨간 점선).
            달림: 쓸고 간 띠 · 몸 잔상 · 속도선 · 박차는 흙먼지. 끝: 다 같이 사그라든다.
     swing  기술 키로 고른다 (swingKind) - 할퀴기 류 세 줄 손톱자국 · 물기 류 다무는 큰 턱 · 펀치 · 킥 류 주먹 충격 고리 ·
            베기 류 초승달 · 가위 류 X · 돌진은 빛줄기와 멈춘 자리 터짐 · 나머지(몸통박치기 류)는 앞으로 퍼지는 어깨 충격파.
            모두 a.c 로 물든다. 멈춘 순간 (달림이 끝났거나 맞아서 섰다) 을 한 번 재서 (a.mem.bt) 터뜨린다.

   여기서만 쓰는 도우미 (core 에 없는 것): 띠 · 활 · 칼자국(gash) · 칼날 호(sabre) · 주먹 · 턱 · 돌 · 금 · 거미줄 경로. */
import {
  BODY_R, FALL_H, GOLD, HEAL, HEX_PTS, INK, SOLID, TAU, UP, WARN, WHITE, clamp01, crescent, easeIn, easeOut, fillPath, hash,
  line, noise1, num, palette, ribbon, ring, rng, shape, smooth, spikes, streak, strokePath, wedge,
} from '../core.js';

const PI = Math.PI;
const DIRT = palette('#dccba4', '#8a7350');      // 흙먼지 · 자갈 (타입과 상관없이 땅 색)
const SILK = '#f4f8ff';
const GHOST_LIFE = 0.26;         // 돌진 잔상이 남는 시간
const LANE_N = 6;                // 쓸고 간 띠를 이만큼 마디로 (앞이 진하다)
const LANE_DASH = [16, 12];

// ---------------------------------------------------------------- 입자 spec
const KICK = { shape: 'smoke', n: 7, c: 'light', v: 130, life: 0.55, size: 15, end: 2.2, drag: 4, layer: 0 };
const DUSTLET = { shape: 'smoke', n: 1, c: 'light', v: 1, life: 0.4, size: 8, end: 2.2, drag: 3, layer: 0 };
const GRIT = { shape: 'rock', n: 7, c: 'light', v: 230, life: 0.5, size: 3.2, g: 650, drag: 1.5, spin: 12, end: 1, layer: 0 };
const SPARK = { shape: 'spark', n: 12, c: 'light', v: 440, life: 0.28, size: 13, w: 2.6, drag: 5 };
const FLARE = { shape: 'spark', n: 8, c: WHITE, v: 380, life: 0.22, size: 11, w: 2, drag: 6 };
const GLINT = { shape: 'star', n: 5, c: WHITE, v: 110, life: 0.32, size: 13, drag: 5 };
const CHIP = { shape: 'rock', n: 10, c: 'light', v: 250, life: 0.6, size: 6, g: 800, drag: 1, spin: 12, end: 1 };
const CHUNK = { shape: 'rock', n: 1, c: 'light', v: 1, life: 0.75, size: 8, g: 1150, drag: 0.4, spin: 9, end: 1 };
const CLOUD = { shape: 'smoke', n: 8, c: 'light', v: 80, life: 0.9, size: 26, end: 2.2, drag: 3, up: -20, layer: 0 };
const WISP = { shape: 'glow', n: 1, c: 'light', v: 1, life: 0.3, size: 7, drag: 3 };
const SHRED = { shape: 'shard', n: 10, c: 'light', v: 300, life: 0.35, size: 8, drag: 5 };
const RUBBLE = { shape: 'rock', n: 1, c: 'light', v: 1, life: 0.9, size: 18, drag: 8, spin: 1, end: 0.9, layer: 0 };
const SPLINTER = { shape: 'shard', n: 1, c: 'light', v: 1, life: 0.5, size: 9, g: 900, drag: 1 };

const memOf = (a) => a.mem || (a.mem = {});
const earthy = (a) => a.sty === 'rock' || a.sty === 'quake' || a.ty === 'GROUND' || a.ty === 'ROCK';

// ---------------------------------------------------------------- 경로 도우미
/** (x0, y0) → (x1, y1) 를 가운데로 반폭 hw 인 띠. */
function band(ctx, x0, y0, x1, y1, hw) {
  const dx = x1 - x0, dy = y1 - y0, d = Math.hypot(dx, dy) || 1, nx = (-dy / d) * hw, ny = (dx / d) * hw;
  ctx.beginPath();
  ctx.moveTo(x0 + nx, y0 + ny);
  ctx.lineTo(x1 + nx, y1 + ny);
  ctx.lineTo(x1 - nx, y1 - ny);
  ctx.lineTo(x0 - nx, y0 - ny);
  ctx.closePath();
}

/** 앞(ux, uy)으로 볼록한 활 - (x, y) 가 꼭짓점, back 만큼 뒤에서 양옆 half. */
function bow(ctx, x, y, ux, uy, back, half) {
  const px = -uy * half, py = ux * half, bx = x - ux * back, by = y - uy * back;
  ctx.beginPath();
  ctx.moveTo(bx + px, by + py);
  ctx.quadraticCurveTo(x + ux * back * 0.9, y + uy * back * 0.9, bx - px, by - py);
}

const QP = { x: 0, y: 0, tx: 1, ty: 0 };
// 2차 곡선 위 s 의 점과 접선 (QP 에 적는다)
function qpt(x0, y0, cx, cy, x1, y1, s) {
  const u = 1 - s;
  QP.x = u * u * x0 + 2 * u * s * cx + s * s * x1;
  QP.y = u * u * y0 + 2 * u * s * cy + s * s * y1;
  const tx = 2 * u * (cx - x0) + 2 * s * (x1 - cx), ty = 2 * u * (cy - y0) + 2 * s * (y1 - cy), d = Math.hypot(tx, ty) || 1;
  QP.tx = tx / d;
  QP.ty = ty / d;
  return QP;
}

const GASH_N = 12;
const GX = new Float64Array(GASH_N + 1);
const GY = new Float64Array(GASH_N + 1);
const GW = new Float64Array(GASH_N + 1);
const GNX = new Float64Array(GASH_N + 1);
const GNY = new Float64Array(GASH_N + 1);
/** 칼자국 - (x0, y0) → (x1, y1) 를 옆으로 bend 만큼 휜 곡선, 가운데가 w 만큼 두껍고 양 끝이 뾰족하다.
    e (0~1) 만큼만 그어진다 - 머리도 뾰족하게. */
function gash(ctx, x0, y0, x1, y1, bend, w, e) {
  ctx.beginPath();
  if (!(e > 0.01)) return;
  e = e < 1 ? e : 1;
  const dx = x1 - x0, dy = y1 - y0, d = Math.hypot(dx, dy) || 1;
  const cx = (x0 + x1) / 2 - (dy / d) * bend, cy = (y0 + y1) / 2 + (dx / d) * bend;
  for (let i = 0; i <= GASH_N; i++) {
    const s = (e * i) / GASH_N, p = qpt(x0, y0, cx, cy, x1, y1, s);
    GX[i] = p.x;
    GY[i] = p.y;
    GNX[i] = -p.ty;
    GNY[i] = p.tx;
    GW[i] = w * Math.sin(PI * s) * Math.min(1, (e - s) / 0.12);
  }
  ctx.moveTo(GX[0], GY[0]);
  for (let i = 1; i <= GASH_N; i++) ctx.lineTo(GX[i] + GNX[i] * GW[i], GY[i] + GNY[i] * GW[i]);
  for (let i = GASH_N - 1; i > 0; i--) ctx.lineTo(GX[i] - GNX[i] * GW[i], GY[i] - GNY[i] * GW[i]);
  ctx.closePath();
}

/** 칼날 호 - (x, y) 가운데 반지름 R, 꼬리 a0 → 머리 a1. 머리 쪽이 두껍고 (최대 thick) 양 끝이 뾰족하다. */
function sabre(ctx, x, y, R, a0, a1, thick) {
  const N = 14;
  ctx.beginPath();
  for (let i = 0; i <= N; i++) {
    const a = a0 + ((a1 - a0) * i) / N;
    ctx.lineTo(x + Math.cos(a) * R, y + Math.sin(a) * R);
  }
  for (let i = N; i >= 0; i--) {
    const s = i / N, a = a0 + (a1 - a0) * s, r = Math.max(0, R - thick * Math.sin((PI * (s + s * s)) / 2));
    ctx.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
  }
  ctx.closePath();
}

/** 둥근 네모 경로. */
function rrect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

// 칠하고 테를 두른다 (보통 혼합)
function solid(ctx, fill, edge, w, a) {
  fillPath(ctx, fill, a);
  strokePath(ctx, edge, w, a);
}

/** 위에서 본 주먹 하나 - 손목 · 손등 · 앞으로 말린 손가락 마디 넷 · 엄지 · 마디 빛. (x, y) 가운데, ang 쪽으로, 반 길이 s. */
function drawFist(fx, ctx, x, y, ang, s, c, a) {
  if (!(a > 0.01)) return;
  const w = Math.max(1.2, s * 0.09);
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(ang);
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.glow(ctx, c.dark, 0, 0, s * 2.1, 0.6 * a);
  ctx.globalCompositeOperation = 'source-over';
  rrect(ctx, -1.2 * s, -0.36 * s, 0.6 * s, 0.72 * s, 0.12 * s);         // 손목
  solid(ctx, c.dark, INK, w, 0.9 * a);
  rrect(ctx, -0.78 * s, -0.64 * s, 1.1 * s, 1.28 * s, 0.32 * s);        // 손등
  solid(ctx, c.light, c.dark, w, a);
  for (let i = 0; i < 4; i++) {                                         // 손가락 마디
    ctx.beginPath();
    ctx.ellipse(0.4 * s, (-0.48 + i * 0.32) * s, 0.27 * s, 0.17 * s, 0, 0, TAU);
    solid(ctx, c.light, c.dark, w, a);
  }
  ctx.beginPath();                                                      // 엄지 - 아래 마디들을 가로지른다
  ctx.ellipse(0.02 * s, 0.5 * s, 0.44 * s, 0.17 * s, -0.3, 0, TAU);
  solid(ctx, c.light, c.dark, w, a);
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.glow(ctx, WHITE, 0.45 * s, -0.15 * s, s * 0.55, 0.5 * a);
  ctx.restore();
}

/** 턱 하나 (+x 가 앞, 경첩이 (0, 0)). sg -1 위턱 · 1 아래턱. */
function jawPath(ctx, R, sg) {
  ctx.beginPath();
  ctx.moveTo(-0.18 * R, 0);
  ctx.quadraticCurveTo(0.12 * R, sg * 0.66 * R, R, sg * 0.14 * R);
  ctx.quadraticCurveTo(0.55 * R, sg * 0.3 * R, 0, sg * 0.1 * R);
  ctx.closePath();
}

const FANG_AT = [0.3, 0.46, 0.6, 0.76, 0.9];
const FANG_H = [0.1, 0.12, 0.13, 0.24, 0.14];
// 잇몸 선 (뒤 (0, sg·0.1R) → 앞 (R, sg·0.14R)) 을 따라 이빨 다섯 - 넷째가 송곳니
function teethPath(ctx, R, sg) {
  ctx.beginPath();
  for (let i = 0; i < FANG_AT.length; i++) {
    const p = qpt(0, sg * 0.1 * R, 0.55 * R, sg * 0.3 * R, R, sg * 0.14 * R, FANG_AT[i]), h = FANG_H[i] * R;
    const w = (i === 3 ? 0.075 : 0.055) * R;
    ctx.moveTo(p.x - w, p.y + sg * 0.01 * R);
    ctx.lineTo(p.x + w, p.y + sg * 0.01 * R);
    ctx.lineTo(p.x + w * 0.2, p.y - sg * h);
    ctx.closePath();
  }
}

/** 송곳니 끝 (턱 좌표). */
function fangTip(R, sg) {
  const p = qpt(0, sg * 0.1 * R, 0.55 * R, sg * 0.3 * R, R, sg * 0.14 * R, FANG_AT[3]);
  return { x: p.x + 0.015 * R, y: p.y - sg * FANG_H[3] * R };
}

// 돌 (불규칙한 여덟 꼭짓점) - 단위 반지름, 모양 여섯 가지
const ROCKS = Array.from({ length: 6 }, (_, v) => {
  const out = [];
  for (let i = 0; i < 8; i++) {
    const a = (i * TAU) / 8 + (hash(v * 31 + i * 7) - 0.5) * 0.55, r = 0.74 + hash(v * 17 + i * 5) * 0.32;
    out.push(Math.cos(a) * r, Math.sin(a) * r);
  }
  return out;
});
// 뾰족 돌 (+x 가 끝) - 윗면 (빛 받는 쪽)
const STONE = [1.3, 0, 0.35, 0.5, -0.65, 0.42, -0.95, -0.05, -0.3, -0.55, 0.45, -0.42];
const STONE_TOP = [1.3, 0, 0.45, -0.42, -0.3, -0.55, -0.95, -0.05, 0.1, 0.05];

/** 구르는 돌 하나 - 어두운 몸 · 왼쪽 위 밝은 면 · 테 · 금. v 는 모양 씨앗. */
function rockAt(ctx, x, y, r, rot, v, c, a) {
  if (!(r > 0.5) || !(a > 0.01)) return;
  const P = ROCKS[Math.abs(Math.floor(num(v))) % ROCKS.length];
  ctx.globalCompositeOperation = 'source-over';
  shape(ctx, P, x, y, r, rot);
  fillPath(ctx, c.dark, a);
  shape(ctx, P, x - r * 0.15, y - r * 0.2, r * 0.64, rot);
  fillPath(ctx, c.light, 0.8 * a);
  shape(ctx, P, x, y, r, rot);
  strokePath(ctx, INK, Math.max(1, r * 0.1), 0.5 * a);
  ctx.beginPath();
  ctx.moveTo(x + Math.cos(rot + 2) * r * 0.1, y + Math.sin(rot + 2) * r * 0.1);
  ctx.lineTo(x + Math.cos(rot + 2.5) * r * 0.75, y + Math.sin(rot + 2.5) * r * 0.75);
  strokePath(ctx, INK, Math.max(0.8, r * 0.06), 0.35 * a);
}

/** 뾰족 돌 - 윗면이 밝은 결정. */
function stoneAt(ctx, x, y, r, rot, c, a) {
  ctx.globalCompositeOperation = 'source-over';
  shape(ctx, STONE, x, y, r, rot);
  fillPath(ctx, c.dark, a);
  shape(ctx, STONE_TOP, x, y, r, rot);
  fillPath(ctx, c.light, 0.85 * a);
  shape(ctx, STONE, x, y, r, rot);
  strokePath(ctx, INK, Math.max(1, r * 0.09), 0.55 * a);
}

/** 땅에서 솟는 돌 가시 ((x, y) 가 밑동, 높이 h, 밑 반폭 w). 왼쪽 면이 밝다. */
function spireAt(ctx, x, y, h, w, c, a) {
  if (!(h > 1)) return;
  ctx.globalCompositeOperation = 'source-over';
  ctx.beginPath();
  ctx.moveTo(x - w, y);
  ctx.lineTo(x + w * 0.12, y - h);
  ctx.lineTo(x + w, y - w * 0.1);
  ctx.lineTo(x + w * 0.15, y + w * 0.28);
  ctx.closePath();
  fillPath(ctx, c.dark, a);
  strokePath(ctx, INK, 1.5, 0.55 * a);
  ctx.beginPath();
  ctx.moveTo(x - w, y);
  ctx.lineTo(x + w * 0.12, y - h);
  ctx.lineTo(x + w * 0.15, y + w * 0.28);
  ctx.closePath();
  fillPath(ctx, c.light, 0.85 * a);
}

/** 땅 금 - 씨앗마다 한 번 만든다. 단위 반지름 1, 점마다 가운데에서의 거리 rs. 큰 금 n 개 + 곁가지. */
function makeCracks(seed, n) {
  const rnd = rng(seed * 7 + 3), out = [];
  for (let i = 0; i < n; i++) {
    const a0 = ((i + rnd() * 0.7) / n) * TAU, segs = 6, xs = [], ys = [], rs = [];
    let a = a0;
    for (let j = 0; j <= segs; j++) {
      const r = j === 0 ? 0.05 : 0.05 + ((0.95 * j) / segs) * (0.82 + 0.18 * rnd());
      a = a0 + (rnd() - 0.5) * 0.42;
      xs.push(Math.cos(a) * r);
      ys.push(Math.sin(a) * r);
      rs.push(r);
    }
    out.push({ xs, ys, rs, main: true });
    const k = 2 + Math.floor(rnd() * 3), b = a0 + (rnd() < 0.5 ? -1 : 1) * (0.5 + rnd() * 0.4);
    const bx = [xs[k]], by = [ys[k]], br = [rs[k]];
    for (let j = 1; j <= 3; j++) {
      const r = rs[k] + j * 0.09, ba = b + (rnd() - 0.5) * 0.5;
      bx.push(xs[k] + Math.cos(ba) * j * 0.09);
      by.push(ys[k] + Math.sin(ba) * j * 0.09);
      br.push(r);
    }
    out.push({ xs: bx, ys: by, rs: br, main: false });
  }
  return out;
}

// 금 경로 - 가운데에서 P (단위 반지름) 까지만. main 이 같은 것끼리 한 경로
function crackPath(ctx, cracks, main, x, y, S, P) {
  ctx.beginPath();
  for (const cr of cracks) {
    if (cr.main !== main || cr.rs[0] >= P) continue;
    ctx.moveTo(x + cr.xs[0] * S, y + cr.ys[0] * S);
    for (let j = 1; j < cr.xs.length; j++) {
      const r0 = cr.rs[j - 1], r1 = cr.rs[j];
      if (r1 <= P) {
        ctx.lineTo(x + cr.xs[j] * S, y + cr.ys[j] * S);
        continue;
      }
      const f = r1 > r0 ? (P - r0) / (r1 - r0) : 0;
      ctx.lineTo(x + (cr.xs[j - 1] + (cr.xs[j] - cr.xs[j - 1]) * f) * S, y + (cr.ys[j - 1] + (cr.ys[j] - cr.ys[j - 1]) * f) * S);
      break;
    }
  }
}

/** 갈라진 땅 - 어두운 틈 (보통 혼합) 위에 속에서 새는 빛 (glow 0~1). */
function cracks(ctx, list, x, y, S, P, c, a, glow) {
  if (!(P > 0.06) || !(a > 0.01)) return;
  ctx.globalCompositeOperation = 'source-over';
  crackPath(ctx, list, true, x, y, S, P);
  strokePath(ctx, INK, 5, 0.55 * a);
  crackPath(ctx, list, false, x, y, S, P);
  strokePath(ctx, INK, 3, 0.45 * a);
  if (!(glow > 0.01)) return;
  ctx.globalCompositeOperation = 'lighter';
  crackPath(ctx, list, true, x, y, S, P);
  strokePath(ctx, c.light, 2, glow * a);
  crackPath(ctx, list, false, x, y, S, P);
  strokePath(ctx, c.light, 1.2, 0.7 * glow * a);
}

/** 들썩이는 자갈 (땅이 떨린다) - 원 안 n 개, 세기 k. */
function pebbles(ctx, q, n, R, k, t) {
  if (!(k > 0.01)) return;
  for (let i = 0; i < n; i++) {
    const a = hash(q.seed + i * 3) * TAU, d = R * Math.sqrt(hash(q.seed + i * 3 + 1));
    const hop = Math.abs(Math.sin(t * (30 + i * 3) + i)) * 3 * k;
    rockAt(ctx, q.x + Math.cos(a) * d, q.y + Math.sin(a) * d - hop, 3 + 2.5 * hash(q.seed + i), i + t * 2 * k, i, q.c, 0.4 + 0.5 * k);
  }
}

const WEB_PX = new Float64Array(16);
const WEB_PY = new Float64Array(16);
/** 거미줄 - 바퀴살 n 개 + 안으로 처진 둘레 rings 겹. sag 0~1 (둘레가 가운데로 처지는 정도). */
function webPath(ctx, x, y, R, n, rings, seed, rot, sag) {
  n = Math.min(n, 15);
  ctx.beginPath();
  for (let j = 0; j < n; j++) {
    const a = rot + ((j + (hash(seed + j) - 0.5) * 0.35) * TAU) / n;
    WEB_PX[j] = Math.cos(a);
    WEB_PY[j] = Math.sin(a);
    ctx.moveTo(x, y);
    ctx.lineTo(x + WEB_PX[j] * R, y + WEB_PY[j] * R);
  }
  for (let k = 1; k <= rings; k++) {
    const rr = R * (0.14 + (0.86 * k) / rings);
    let px = 0, py = 0;
    for (let j = 0; j <= n; j++) {
      const i = j % n, r1 = rr * (0.92 + 0.08 * hash(seed + i * 13 + k)), cx = x + WEB_PX[i] * r1, cy = y + WEB_PY[i] * r1;
      if (j === 0) ctx.moveTo(cx, cy);
      else ctx.quadraticCurveTo(x + ((px + cx) / 2 - x) * (1 - sag), y + ((py + cy) / 2 - y) * (1 - sag), cx, cy);
      px = cx;
      py = cy;
    }
  }
}

// ---------------------------------------------------------------- 입자 도우미
/** 한 점에서 퍼지는 충격 선 (선 입자 - 안쪽 끝이 바깥으로 따라가며 짧아진다). */
function rays(fx, x, y, ang, arc, n, r0, r1, col, life, w) {
  for (let i = 0; i < n; i++) {
    const d = ang + (n > 1 ? i / (n - 1) - 0.5 : 0) * arc + (Math.random() - 0.5) * 0.18, cx = Math.cos(d), cy = Math.sin(d);
    const v = ((r1 - r0) / life) * 1.1, p = fx.spawn('line', x + cx * r0, y + cy * r0, cx * v, cy * v, life, 1, col);
    p.x2 = x + cx * r1;
    p.y2 = y + cy * r1;
    p.w = w;
  }
}

/** 남는 자국 선 하나 (선 입자, 제자리). */
function scar(fx, x0, y0, x1, y1, col, life, w, layer = 1) {
  const p = fx.spawn('line', x0, y0, 0, 0, life, 1, col);
  p.x2 = x1;
  p.y2 = y1;
  p.w = w;
  p.layer = layer;
}

/** 위로 솟았다 떨어지는 덩이 (위에서 비스듬히 본 땅) - 원 r0~r1 사이에서 n 개. */
function heave(fx, x, y, c, n, r0, r1, up) {
  for (let i = 0; i < n; i++) {
    const a = Math.random() * TAU, d = r0 + (r1 - r0) * Math.random(), v = 60 + 140 * Math.random();
    fx.particle(CHUNK, c, x + Math.cos(a) * d, y + Math.sin(a) * d, Math.cos(a) * v, Math.sin(a) * v - up * (0.6 + 0.6 * Math.random()));
  }
}

// ---------------------------------------------------------------- 근접 · 돌진: 달리는 동안 (rush)
/** 맞는 띠의 반폭 - 상대 몸이 이 띠에 닿으면 맞는다 (몸 가운데 사이 reach − 상대 몸 반지름). */
export const laneHW = (a) => Math.max(BODY_R * 0.8, num(a.reach, 86) - BODY_R);

// 상대 것인가 (장판 표시처럼 상대 돌진의 갈 길은 빨간 점선) - fx.foe 가 없으면 내 것으로 친다
const foeOf = (fx, a) => typeof fx.foe === 'function' && (a.side === 'a' || a.side === 'b') && !!fx.foe(a.side);

// 준비 - 갈 길을 미리 보이고 웅크린다
function windUp(fx, ctx, a) {
  const k = smooth(clamp01(a.sk)), hw = laneHW(a), c = a.c, L = num(a.len, 200) + hw;
  const px = -a.uy, py = a.ux, x1 = a.x + a.ux * L, y1 = a.y + a.uy * L;
  band(ctx, a.x, a.y, x1, y1, hw);
  fillPath(ctx, c.dark, 0.02 + 0.06 * k);
  ctx.setLineDash(LANE_DASH);
  ctx.lineDashOffset = -fx.clock * 240;
  ctx.beginPath();
  for (let s = -1; s <= 1; s += 2) {
    ctx.moveTo(a.x + px * hw * s, a.y + py * hw * s);
    ctx.lineTo(x1 + px * hw * s, y1 + py * hw * s);
  }
  if (foeOf(fx, a)) {
    ctx.globalCompositeOperation = 'source-over';
    strokePath(ctx, WARN, 2, 0.7 * k);
    ctx.globalCompositeOperation = 'lighter';
  } else strokePath(ctx, c.light, 2, 0.45 * k);
  ctx.setLineDash(SOLID);
  for (let i = 0; i < 3; i++) {                 // 길 위로 흐르는 꺾쇠
    const f = (fx.clock * 2.4 + i / 3) % 1, d = BODY_R + f * (L - BODY_R);
    bow(ctx, a.x + a.ux * d, a.y + a.uy * d, a.ux, a.uy, hw * 0.35, hw * 0.55);
    strokePath(ctx, c.light, 3, 0.55 * k * Math.sin(PI * f));
  }
  ring(ctx, c.light, 0.15 + 0.55 * k, 1.5 + 2.5 * k, a.x, a.y, BODY_R * (2 - 0.85 * k));   // 조여드는 고리
  streak(fx, ctx, c.light, a.x + a.ux * BODY_R * 1.3, a.y + a.uy * BODY_R * 1.3, a.ang, BODY_R * (0.5 + 1.3 * k), 5 + 8 * k, 0.2 + 0.5 * k);
  for (let i = fx.perSec(24); i > 0; i--) {     // 뒷발이 땅을 긁는다
    const o = (Math.random() - 0.5) * BODY_R * 1.4, bx = a.x - a.ux * BODY_R * 0.6, by = a.y - a.uy * BODY_R * 0.6 + BODY_R;
    fx.particle(DUSTLET, DIRT, bx + px * o, by + py * o, -a.ux * 60 + px * o * 2, -a.uy * 60 + py * o * 2);
  }
}

// 박차는 순간 - 발밑 흙먼지 · 자갈 · 땅 고리 · 긁힌 자국
function kickOff(fx, a, x, y) {
  const back = a.ang + PI, fy = y + BODY_R * 0.7, dash = a.mk === 'dash';
  fx.burst(x, fy, KICK, DIRT, dash ? 0.8 : 1.1, back, 1.6, 0, BODY_R * 0.6);
  fx.burst(x, fy, GRIT, DIRT, earthy(a) ? 1.8 : 1, back, 1.4);
  fx.wave(x, fy, DIRT.light, BODY_R * 2.8, 0.34, 4, 0);
  for (let s = -1; s <= 1; s += 2) {
    const ox = -a.uy * s * BODY_R * 0.45, oy = a.ux * s * BODY_R * 0.45;
    scar(fx, x + ox, fy + oy, x + ox - a.ux * BODY_R * 1.4, fy + oy - a.uy * BODY_R * 1.4, DIRT.dark, 0.6, 3, 0);
  }
}

// 쓸고 간 띠 (= 맞는 폭) - 앞이 진하고 뒤로 옅다 + 가장자리 선 + 몸 자국
function lane(fx, ctx, a, m, fade) {
  const hw = laneHW(a), c = a.c, ux = a.ux, uy = a.uy, px = -uy, py = ux;
  const d = Math.max(0, (a.x - m.sx) * ux + (a.y - m.sy) * uy);
  if (d > 2) {
    const sx = a.x - ux * d, sy = a.y - uy * d;
    for (let i = 0; i < LANE_N; i++) {
      const f0 = i / LANE_N, f1 = (i + 1) / LANE_N;
      band(ctx, sx + ux * d * f0, sy + uy * d * f0, sx + ux * d * f1, sy + uy * d * f1, hw);
      fillPath(ctx, c.dark, (0.03 + 0.2 * f1 * f1) * fade);
    }
    for (let i = 0; i < 3; i++) {
      const f0 = i / 3, f1 = (i + 1) / 3;
      ctx.beginPath();
      for (let s = -1; s <= 1; s += 2) {
        ctx.moveTo(sx + ux * d * f0 + px * hw * s, sy + uy * d * f0 + py * hw * s);
        ctx.lineTo(sx + ux * d * f1 + px * hw * s, sy + uy * d * f1 + py * hw * s);
      }
      strokePath(ctx, c.light, 2, (0.08 + 0.5 * f1 * f1) * fade);
    }
  }
  ribbon(ctx, a.trail, fx.clock, 0.24, BODY_R * 2, 6, c.light, 0.28 * fade);
  ribbon(ctx, a.trail, fx.clock, 0.16, 10, 1, WHITE, 0.5 * fade);
}

// 몸 잔상 - 지나온 자리에 옅어지는 몸 크기 빛 (돌진은 더 촘촘하고 희다)
function ghosts(fx, ctx, a, fade) {
  const tr = a.trail, now = fx.clock, dash = a.mk === 'dash', step = dash ? 3 : 4, c = a.c;
  for (let i = step; i < tr.n; i += step) {
    const k = (now - tr.t(i)) / GHOST_LIFE;
    if (!(k < 1)) break;
    const x = tr.x(i), y = tr.y(i), f = (1 - k) * fade;
    fx.ink.stretch(ctx, c.dark, x, y, BODY_R * 1.15, BODY_R * 1.45, 0.5 * f);
    ctx.beginPath();
    ctx.ellipse(x, y, BODY_R * (0.95 + 0.15 * k), BODY_R * (1.2 + 0.15 * k), 0, 0, TAU);
    strokePath(ctx, c.light, 2.5 * f + 0.5, 0.55 * f);
    if (dash) fx.ink.stretch(ctx, WHITE, x, y, BODY_R * 0.6, BODY_R * 0.9, 0.35 * f);
  }
}

// 속도선 - 몸 둘레 뒤로 (1초에 24번 자리를 바꾼다)
function speedLines(ctx, a, now, fade) {
  const v = clamp01(num(a.speed) / 900) * fade;
  if (v < 0.05) return;
  const hw = laneHW(a), px = -a.uy, py = a.ux, flick = Math.floor(now * 24), seed = Math.floor(num(a.seed) * 1000);
  for (let pass = 0; pass < 2; pass++) {
    ctx.beginPath();
    for (let i = pass; i < 10; i += 2) {
      const h1 = hash(seed + i * 7 + flick), h2 = hash(seed + i * 13 + flick * 3);
      const o = (h1 - 0.5) * 2 * hw * 0.95, back = BODY_R * 0.5 + h2 * BODY_R * 1.6, L = (40 + 120 * v) * (0.55 + 0.45 * h2);
      const x = a.x + px * o - a.ux * back, y = a.y + py * o - a.uy * back;
      ctx.moveTo(x, y);
      ctx.lineTo(x - a.ux * L, y - a.uy * L);
    }
    strokePath(ctx, pass ? a.c.light : WHITE, pass ? 2.5 : 1.8, 0.75 * v);
  }
}

// 달리는 동안 발밑에서 이는 흙먼지
function dustTrail(fx, a) {
  if (!(a.speed > 300)) return;
  const px = -a.uy, py = a.ux;
  for (let i = fx.perSec(a.mk === 'dash' ? 70 : 50); i > 0; i--) {
    const s = Math.random() < 0.5 ? -1 : 1, o = s * BODY_R * (0.3 + 0.5 * Math.random());
    const x = a.x - a.ux * BODY_R * 0.6 + px * o, y = a.y - a.uy * BODY_R * 0.6 + py * o + BODY_R * 0.9;
    fx.particle(DUSTLET, DIRT, x, y, px * s * 70 - a.ux * 40, py * s * 70 - a.uy * 40);
  }
}

function rush(fx, ctx, a) {
  const m = memOf(a);
  if (a.stage === 'wind') {
    m.sx = a.x;                                 // 마지막으로 서 있던 곳 = 달리기 시작
    m.sy = a.y;
    m.slow = 0;
    windUp(fx, ctx, a);
    return;
  }
  if (m.lx !== undefined && fx.dt > 0) {        // 이번 장에 몸이 움직인 빠르기 - 두 장 잇달아 느리면 섰다 (beat)
    m.slow = Math.hypot(a.x - m.lx, a.y - m.ly) / fx.dt < 120 ? (m.slow || 0) + 1 : 0;
  }
  m.lx = a.x;
  m.ly = a.y;
  if (m.sx === undefined) {
    m.sx = num(a.x0, a.x);
    m.sy = num(a.y0, a.y);
  }
  if (!m.kicked) {
    m.kicked = true;
    kickOff(fx, a, m.sx, m.sy);
  }
  const fade = a.stage === 'tail' ? 1 - clamp01(a.sk) : 1;
  lane(fx, ctx, a, m, fade);
  ghosts(fx, ctx, a, fade);
  speedLines(ctx, a, fx.clock, fade);
  if (a.stage === 'act') dustTrail(fx, a);
}

// ---------------------------------------------------------------- 근접 · 돌진: 앞쪽 타격 (swing)
const CLAW_K = /CLAW|SCRATCH|SWIPE|RAKE/;
const FANG_K = /FANG|BITE|CRUNCH|JAW|CHOMP/;
const CROSS_K = /SCISSOR|CROSSPOISON/;
const BLADE_K = /SLASH|BLADE|CUT|SWORD|CLEAVE|STONEAXE|CEASELESSEDGE|SLICE|RAZORSHELL/;
const FIST_K = /PUNCH|FIST|HAMMER|KICK|STOMP|PALM|CHOP|SLAP|POUND|UPPERCUT/;

/** 타격 그림 이름 - 돌진이면 'dash', 아니면 기술 키로 claw · jaw · cross · blade · fist, 나머지 'charge'. */
export function swingKind(a) {
  if (a.mk === 'dash') return 'dash';
  const k = typeof a.k === 'string' ? a.k : '';
  if (CLAW_K.test(k)) return 'claw';
  if (FANG_K.test(k)) return 'jaw';
  if (CROSS_K.test(k)) return 'cross';
  if (BLADE_K.test(k)) return 'blade';
  if (FIST_K.test(k)) return 'fist';
  return 'charge';
}

/** 때: m.tA (달림이 끝나는 t), m.bt (멈춘 순간 - 한 번 정하면 그대로), m.bk (그 뒤 진행 0~1, 앞이면 -1).
    멈춘 순간 = 달림이 끝났거나, 달린 뒤 섰다 (엔진은 상대에게 닿는 자리에서 세운다 · 벽). 처음 멈춘 프레임이면 true. */
function beat(a, t, m) {
  const act = num(a.act, 0.18), span = a.go !== null && a.go !== undefined && a.life > a.go ? a.life - a.go : act + 0.14;
  const tA = clamp01(act / span) || 0.55;
  const ran = m.sx === undefined ? num(a.moved) : Math.hypot(a.x - m.sx, a.y - m.sy);
  let first = false;
  const stopped = m.slow === undefined ? num(a.speed) < 160 : m.slow >= 2;
  if (m.bt === undefined && (t >= tA || (t > 0.05 && stopped && ran > BODY_R))) {
    m.bt = t;
    first = true;
  }
  m.tA = tA;
  m.bk = m.bt === undefined ? -1 : clamp01((t - m.bt) / Math.max(0.05, 1 - m.bt));
  return first;
}

const fadeOut = (m, from) => (m.bk < 0 ? 1 : 1 - smooth(clamp01((m.bk - from) / (1 - from))));

// 몸통박치기 류 - 달리는 동안 앞에서 눌리는 공기, 멈추면 앞으로 퍼지는 충격파 부채꼴 + 터지는 별
function chargeArt(fx, ctx, a, t, m, boom) {
  const hw = laneHW(a), c = a.c, ux = a.ux, uy = a.uy, fx0 = a.x + ux * (BODY_R + 4), fy0 = a.y + uy * (BODY_R + 4);
  if (boom) {
    fx.burst(fx0, fy0, SPARK, c, 1.1, a.ang, 1.5);
    fx.burst(fx0, fy0, FLARE, c, 1, a.ang, 2.4);
    fx.burst(fx0, fy0 + BODY_R * 0.6, KICK, DIRT, 0.7, a.ang, 2.6);
    fx.wave(fx0, fy0, c.light, hw * 1.8, 0.32, 7);
    rays(fx, fx0, fy0, a.ang, 2, 7, hw * 0.4, hw * 1.6, WHITE, 0.2, 3);
    fx.spawn('core', fx0 + ux * hw * 0.45, fy0 + uy * hw * 0.45, 0, 0, 0.12, hw * 0.3, c.light).size1 = hw * 0.8;
  }
  if (m.bk < 0) {
    const k = clamp01(t / 0.12) * clamp01(0.3 + num(a.speed) / 900);
    for (let i = 0; i < 3; i++) {
      const f = (fx.clock * 6 + i / 3) % 1, d = BODY_R * 0.7 + f * hw * 0.8;
      bow(ctx, a.x + ux * d, a.y + uy * d, ux, uy, hw * (0.3 + 0.25 * f), hw * (0.55 + 0.45 * f));
      strokePath(ctx, i ? c.light : WHITE, 4 * (1 - f) + 1, 0.85 * k * (1 - f));
    }
    streak(fx, ctx, c.light, fx0 + ux * 6, fy0 + uy * 6, a.ang + PI / 2, hw * 0.75, 12, 0.55 * k);
    streak(fx, ctx, WHITE, fx0, fy0, a.ang + PI / 2, hw * 0.45, 5, 0.6 * k);
    ctx.beginPath();
    for (let s = -1; s <= 1; s += 2) {          // 어깨에서 옆으로 갈라지는 바람
      const px = -uy * s * hw, py = ux * s * hw;
      ctx.moveTo(fx0 + px * 0.3, fy0 + py * 0.3);
      ctx.quadraticCurveTo(fx0 - ux * 8 + px * 0.8, fy0 - uy * 8 + py * 0.8, fx0 - ux * hw * 1.1 + px * 0.95, fy0 - uy * hw * 1.1 + py * 0.95);
    }
    strokePath(ctx, WHITE, 2, 0.5 * k);
    return;
  }
  const k = m.bk, e = easeOut(k), f = 1 - k, R = BODY_R + hw * 2 * e;
  wedge(ctx, a.x, a.y, R, a.ang, 0.85);
  fillPath(ctx, c.dark, 0.35 * f);
  wedge(ctx, a.x, a.y, R * 0.8, a.ang, 0.6);
  fillPath(ctx, c.light, 0.22 * f);
  for (let i = 0; i < 3; i++) {                 // 앞으로 밀려 나가는 충격파 테 셋
    const r = BODY_R + hw * 2 * easeOut(clamp01(k * (1 + i * 0.35))) * (1 - i * 0.22);
    ctx.beginPath();
    ctx.arc(a.x, a.y, r, a.ang - 0.85 + i * 0.12, a.ang + 0.85 - i * 0.12);
    strokePath(ctx, i ? c.light : WHITE, (6 - i * 1.5) * f + 1, f * (1 - i * 0.2));
  }
  ctx.globalCompositeOperation = 'source-over';   // 부딪친 자리 별 - 빛이 아니라 또렷한 만화 별
  spikes(ctx, fx0, fy0, hw * (0.4 + 0.3 * e), 9, 0.4, num(a.seed));
  solid(ctx, c.light, c.dark, 2, f);
  spikes(ctx, fx0, fy0, hw * (0.2 + 0.16 * e), 7, 0.48, num(a.seed) + 0.4);
  fillPath(ctx, WHITE, f);
}

// 칼자국 세 겹 (그림자 · 겉빛 · 속빛 · 흰 심)
function gashLayers(ctx, x0, y0, x1, y1, bend, W, e, c, f) {
  ctx.globalCompositeOperation = 'source-over';
  gash(ctx, x0 + 2, y0 + 3, x1 + 2, y1 + 3, bend, W * 1.2, e);
  fillPath(ctx, INK, 0.3 * f);
  ctx.globalCompositeOperation = 'lighter';
  gash(ctx, x0, y0, x1, y1, bend, W * 1.6, e);
  fillPath(ctx, c.dark, 0.55 * f);
  gash(ctx, x0, y0, x1, y1, bend, W, e);
  fillPath(ctx, c.light, 0.95 * f);
  gash(ctx, x0, y0, x1, y1, bend, W * 0.36, e);
  fillPath(ctx, WHITE, f);
}

// 할퀴기 류 - 달리는 동안 앞으로 뻗은 발톱 셋, 멈추면 비스듬한 세 줄 손톱자국이 차례로 그어진다
function clawArt(fx, ctx, a, t, m, boom) {
  const hw = laneHW(a), c = a.c, ux = a.ux, uy = a.uy, px = -uy, py = ux, dir = num(a.seed) % 2 < 1 ? 1 : -1;
  if (m.bk < 0) {
    const k = easeOut(clamp01(t / Math.max(0.05, m.tA)));
    const bx = a.x + ux * BODY_R * 0.8, by = a.y + uy * BODY_R * 0.8;
    for (let i = -1; i <= 1; i++) {
      const sx = bx + px * i * hw * 0.24, sy = by + py * i * hw * 0.24, L = hw * (0.3 + 0.35 * k);
      gash(ctx, sx, sy, sx + ux * L + px * i * hw * 0.08, sy + uy * L + py * i * hw * 0.08, -dir * L * 0.25, hw * 0.07, 1);
      fillPath(ctx, c.light, 0.85);
      gash(ctx, sx, sy, sx + ux * L + px * i * hw * 0.08, sy + uy * L + py * i * hw * 0.08, -dir * L * 0.25, hw * 0.025, 1);
      fillPath(ctx, WHITE, 0.9);
    }
    fx.ink.star(ctx, WHITE, bx + ux * hw * (0.3 + 0.35 * k), by + uy * hw * (0.3 + 0.35 * k), 16, 0.4 + 0.5 * Math.abs(Math.sin(fx.clock * 30)));
    return;
  }
  const cx0 = a.x + ux * (BODY_R + hw * 0.55), cy0 = a.y + uy * (BODY_R + hw * 0.55);
  const ma = a.ang + dir * (PI / 2 - 0.5), mx = Math.cos(ma), my = Math.sin(ma), nx = -my, ny = mx;
  const L = hw * 2.4, gap = hw * 0.4, W = hw * 0.085, f = fadeOut(m, 0.55);
  for (let i = 0; i < 3; i++) {
    const e = easeOut(clamp01((m.bk - i * 0.09) / 0.35));
    if (e <= 0) continue;
    const o = (i - 1) * gap, cx = cx0 + nx * o, cy = cy0 + ny * o;
    const x0 = cx - (mx * L) / 2, y0 = cy - (my * L) / 2, x1 = cx + (mx * L) / 2, y1 = cy + (my * L) / 2, bend = L * 0.1 * dir;
    gashLayers(ctx, x0, y0, x1, y1, bend, W, e, c, f);
    if (e < 1) {                                // 긋는 끝에서 튀는 불티
      const dx = x1 - x0, dy = y1 - y0, d = Math.hypot(dx, dy) || 1;
      const p = qpt(x0, y0, (x0 + x1) / 2 - (dy / d) * bend, (y0 + y1) / 2 + (dx / d) * bend, x1, y1, e);
      for (let j = fx.perSec(150); j > 0; j--) {
        const v = 200 + 200 * Math.random(), sp = (Math.random() - 0.5) * 0.9;
        fx.particle(SPARK, c, p.x, p.y, (p.tx + -p.ty * sp) * v, (p.ty + p.tx * sp) * v, 0.6);
      }
    }
    if (m.bk >= 0.5 && !m.scar) {               // 다 그은 자국은 잠깐 남는다
      if (i === 2) m.scar = true;
      scar(fx, x0 + mx * L * 0.12, y0 + my * L * 0.12, x1 - mx * L * 0.12, y1 - my * L * 0.12, c.light, 0.35, W * 0.6);
      fx.spawn('star', x1, y1, mx * 60, my * 60, 0.25, 12, WHITE);
    }
  }
  if (boom) {
    fx.wave(cx0, cy0, c.light, hw * 1.4, 0.25, 4);
    fx.burst(cx0, cy0, FLARE, c, 0.8, ma, 1.2);
  }
}

// 물기 류 - 달리는 동안 크게 벌린 턱, 멈추면 콱 다물고 송곳니가 번쩍
function jawArt(fx, ctx, a, t, m, boom) {
  const hw = laneHW(a), c = a.c, R = hw * 1.2 + BODY_R * 0.35;
  const hx = a.x + a.ux * BODY_R * 0.15, hy = a.y + a.uy * BODY_R * 0.15;
  let open, s = 1;
  const f = fadeOut(m, 0.45);
  if (m.bk < 0) {
    const k = easeOut(clamp01(t / Math.max(0.05, m.tA)));
    open = 0.25 + 0.7 * k;
    s = 0.65 + 0.35 * k;
  } else {
    const k = clamp01(m.bk / 0.15);
    open = 0.95 * (1 - easeIn(k));
    s = 1 + (k >= 1 ? 0.05 * Math.sin(m.bk * 60) * (1 - m.bk) : 0.06 * k);
  }
  ctx.save();
  ctx.translate(hx, hy);
  ctx.rotate(a.ang);
  ctx.scale(s, s);
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.glow(ctx, c.dark, R * 0.55, 0, R, 0.55 * f);
  for (let sg = -1; sg <= 1; sg += 2) {
    ctx.save();
    ctx.rotate(sg * open);
    ctx.globalCompositeOperation = 'source-over';
    jawPath(ctx, R, sg);
    fillPath(ctx, c.dark, 0.9 * f);
    strokePath(ctx, c.light, 3, f);
    teethPath(ctx, R, sg);
    fillPath(ctx, WHITE, f);
    strokePath(ctx, c.dark, 1.2, 0.8 * f);
    if (m.bk >= 0 && m.bk < 0.6) {              // 다문 순간 송곳니 반짝
      const tip = fangTip(R, sg);
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.star(ctx, WHITE, tip.x, tip.y, R * 0.28 * (1 - m.bk), 1 - m.bk / 0.6);
    }
    ctx.restore();
  }
  if (m.bk >= 0 && m.bk < 0.4) {
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.core(ctx, c.light, R * 0.75, 0, R * 0.6 * (1 - m.bk / 0.4), 1 - m.bk / 0.4);
  }
  ctx.restore();
  if (boom) {
    const bx = hx + a.ux * R * 0.75, by = hy + a.uy * R * 0.75;
    fx.burst(bx, by, SPARK, c, 0.6, a.ang + PI / 2, 0.9);
    fx.burst(bx, by, SPARK, c, 0.6, a.ang - PI / 2, 0.9);
    fx.burst(bx, by, GLINT, c, 0.8);
    fx.wave(bx, by, c.light, R * 1.1, 0.25, 5);
  }
}

// 펀치 · 킥 류 - 달리는 동안 앞장선 주먹, 멈추면 주먹 축을 감싼 충격 고리 셋 + 터지는 별
function fistArt(fx, ctx, a, t, m, boom) {
  const hw = laneHW(a), c = a.c, ux = a.ux, uy = a.uy, s = hw * 0.42 + 4;
  const lunge = m.bk < 0 ? easeOut(clamp01(t / Math.max(0.05, m.tA))) : 1;
  const d = BODY_R + s * (0.3 + 0.8 * lunge), x = a.x + ux * d, y = a.y + uy * d, f = fadeOut(m, 0.35);
  const ix = x + ux * s * 0.8, iy = y + uy * s * 0.8;
  if (m.bk < 0) {
    ctx.beginPath();                            // 주먹 뒤 속도선
    for (let i = -2; i <= 2; i++) {
      const o = i * s * 0.32, L = s * (1.6 - Math.abs(i) * 0.25) * (0.5 + 0.5 * lunge);
      const bx = x - ux * s * 1.1 - uy * o, by = y - uy * s * 1.1 + ux * o;
      ctx.moveTo(bx, by);
      ctx.lineTo(bx - ux * L, by - uy * L);
    }
    strokePath(ctx, WHITE, 2, 0.7);
    bow(ctx, ix + ux * 6, iy + uy * 6, ux, uy, s * 0.5, s * 1.1);
    strokePath(ctx, c.light, 3, 0.7 * lunge);
  }
  drawFist(fx, ctx, x, y, a.ang, s, c, f);
  if (m.bk >= 0) {
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 3; i++) {
      const k = clamp01((m.bk - i * 0.12) / 0.6);
      if (k <= 0 || k >= 1) continue;
      const R = hw * (0.35 + 1.15 * easeOut(k)), cx = ix + ux * hw * 0.5 * k, cy = iy + uy * hw * 0.5 * k;
      ctx.beginPath();
      ctx.ellipse(cx, cy, R * 0.36, R, a.ang, 0, TAU);
      strokePath(ctx, i ? c.light : WHITE, 6 * (1 - k) + 1, 0.9 * (1 - k));
    }
    const e = easeOut(clamp01(m.bk / 0.4)), g = 1 - smooth(m.bk), sx = ix + ux * hw * 0.25, sy = iy + uy * hw * 0.25;
    ctx.globalCompositeOperation = 'source-over';
    spikes(ctx, sx, sy, hw * (0.4 + 0.45 * e), 9, 0.42, num(a.seed));
    solid(ctx, c.light, c.dark, 2, g);
    spikes(ctx, sx, sy, hw * (0.2 + 0.22 * e), 7, 0.5, num(a.seed) + 0.3);
    fillPath(ctx, WHITE, g);
  }
  if (boom) {
    rays(fx, ix, iy, a.ang, TAU, 8, hw * 0.4, hw * 1.4, WHITE, 0.2, 2.5);
    fx.burst(ix, iy, SPARK, c, 0.8, a.ang, 1.8);
    fx.wave(ix, iy, c.light, hw * 1.6, 0.3, 5);
  }
}

// 베기 류 - 몸 둘레를 크게 휘두르는 초승달 (뒤따르는 둘째 날 + 날 끝 불티)
function bladeArt(fx, ctx, a, t, m, boom) {
  const c = a.c, R = num(a.reach, 86) * 1.08, dir = num(a.seed) % 2 < 1 ? 1 : -1, span = a.mk === 'dash' ? 0.9 : 1.35;
  const sw = clamp01(t / (m.tA * 0.85 + 0.1)), e = easeOut(sw), f = t < m.tA ? 1 : 1 - smooth(clamp01((t - m.tA) / (1 - m.tA)));
  const a0 = a.ang - dir * span, head = a0 + dir * 2 * span * e, tl = head - dir * Math.min(2 * span * e, 1.8);
  if (e > 0.02) {
    sabre(ctx, a.x, a.y, R, tl, head, R * 0.36);
    fillPath(ctx, c.dark, 0.55 * f);
    sabre(ctx, a.x, a.y, R * 0.985, tl, head, R * 0.24);
    fillPath(ctx, c.light, 0.9 * f);
    sabre(ctx, a.x, a.y, R, tl + dir * 0.3 * e, head, R * 0.07);
    fillPath(ctx, WHITE, f);
  }
  const e2 = easeOut(clamp01((sw - 0.18) / 0.82)), h2 = a0 + dir * 2 * span * e2, t2 = h2 - dir * Math.min(2 * span * e2, 1.2);
  if (e2 > 0.02) {
    sabre(ctx, a.x, a.y, R * 1.22, t2, h2, R * 0.12);
    fillPath(ctx, c.light, 0.45 * f);
  }
  const hx = a.x + Math.cos(head) * R * 0.9, hy = a.y + Math.sin(head) * R * 0.9;
  if (e > 0.02 && e < 0.98) {
    fx.ink.star(ctx, WHITE, hx, hy, 20, 0.9 * f);
    for (let j = fx.perSec(110); j > 0; j--) {
      const ta = head + (dir * PI) / 2 + (Math.random() - 0.5) * 0.6, v = 160 + 220 * Math.random();
      fx.particle(SPARK, c, hx, hy, Math.cos(ta) * v, Math.sin(ta) * v, 0.6);
    }
  }
  if (boom) fx.burst(hx, hy, GLINT, c, 0.8);
}

// 가위 류 (시저크로스 · 크로스포이즌) - 앞에서 엇갈리는 두 칼자국
function crossArt(fx, ctx, a, t, m, boom) {
  const hw = laneHW(a), c = a.c, ux = a.ux, uy = a.uy;
  const cx = a.x + ux * (BODY_R + hw * 0.55), cy = a.y + uy * (BODY_R + hw * 0.55), L = hw * 2.3, W = hw * 0.15;
  const span = Math.max(0.05, m.tA * 0.7 + 0.05), f = t < m.tA ? 1 : 1 - smooth(clamp01((t - m.tA) / (1 - m.tA)));
  for (let i = 0; i < 2; i++) {
    const e = easeOut(clamp01((t - i * 0.1) / span)), sa = a.ang + (i ? 1 : -1) * (PI / 2 - 0.62);
    const mx = Math.cos(sa) * (i ? -1 : 1), my = Math.sin(sa) * (i ? -1 : 1);
    gashLayers(ctx, cx - (mx * L) / 2, cy - (my * L) / 2, cx + (mx * L) / 2, cy + (my * L) / 2, L * 0.08 * (i ? 1 : -1), W, e, c, f);
  }
  const both = clamp01((t - 0.1) / span);
  if (both >= 1) fx.ink.star(ctx, WHITE, cx, cy, hw * 0.7 * f, f);
  if (boom) {
    fx.burst(cx, cy, FLARE, c, 1);
    fx.wave(cx, cy, c.light, hw * 1.3, 0.25, 4);
  }
}

// 돌진 - 지나온 길 전체가 빛줄기, 앞을 찌르는 빛 창 + 몸을 감싼 소닉 고리, 멈춘 자리에서 터진다
function dashArt(fx, ctx, a, t, m, boom) {
  const c = a.c, ux = a.ux, uy = a.uy, hw = laneHW(a);
  const sx = m.sx === undefined ? num(a.x0, a.x) : m.sx, sy = m.sy === undefined ? num(a.y0, a.y) : m.sy;
  const d = Math.max(0, (a.x - sx) * ux + (a.y - sy) * uy), f = fadeOut(m, 0);
  if (d > 4) {
    const mx = a.x - (ux * d) / 2, my = a.y - (uy * d) / 2;
    streak(fx, ctx, c.dark, mx, my, a.ang, d / 2 + BODY_R, BODY_R * 0.9, 0.5 * f);
    streak(fx, ctx, c.light, mx, my, a.ang, d / 2 + BODY_R * 0.5, BODY_R * 0.42, 0.8 * f);
    streak(fx, ctx, WHITE, mx, my, a.ang, d / 2, 4, 0.9 * f);
  }
  if (m.bk < 0) {
    streak(fx, ctx, c.light, a.x + ux * BODY_R * 1.7, a.y + uy * BODY_R * 1.7, a.ang, BODY_R * 1.9, 12, 0.6);
    streak(fx, ctx, WHITE, a.x + ux * BODY_R * 1.5, a.y + uy * BODY_R * 1.5, a.ang, BODY_R * 1.4, 4, 0.9);
    for (let i = 0; i < 2; i++) {
      const ph = (fx.clock * 7 + i / 2) % 1, R = BODY_R * (1.1 + 0.6 * ph), bx = a.x - ux * ph * BODY_R * 2.5, by = a.y - uy * ph * BODY_R * 2.5;
      ctx.beginPath();
      ctx.ellipse(bx, by, R * 0.35, R, a.ang, 0, TAU);
      strokePath(ctx, c.light, 3 * (1 - ph) + 0.5, 0.75 * (1 - ph));
    }
    return;
  }
  const k = m.bk, e = easeOut(k);
  fx.ink.core(ctx, c.light, a.x + ux * BODY_R, a.y + uy * BODY_R, BODY_R * (1.8 - e), 1 - k);
  for (let i = 0; i < 2; i++) {
    const R = BODY_R * (1 + 1.6 * e) * (1 + 0.3 * i), cx = a.x + ux * (BODY_R + e * hw * (1 + i * 0.5)), cy = a.y + uy * (BODY_R + e * hw * (1 + i * 0.5));
    ctx.beginPath();
    ctx.ellipse(cx, cy, R * 0.35, R, a.ang, 0, TAU);
    strokePath(ctx, i ? c.light : WHITE, 5 * (1 - k) + 0.5, 1 - k);
  }
  if (boom) {
    const bx = a.x + ux * BODY_R, by = a.y + uy * BODY_R;
    fx.burst(bx, by, SPARK, c, 1.2, a.ang, 1.1);
    fx.burst(bx, by, GLINT, c, 1);
    fx.wave(bx, by, c.light, BODY_R * 3.5, 0.3, 5);
    fx.spawn('core', bx, by, 0, 0, 0.14, BODY_R, c.light).size1 = BODY_R * 2.2;
  }
}

const SWINGS = { charge: chargeArt, claw: clawArt, jaw: jawArt, fist: fistArt, blade: bladeArt, cross: crossArt, dash: dashArt };

function swingAs(fx, ctx, a, t, kind) {
  const m = memOf(a), boom = beat(a, t, m);
  (SWINGS[kind] || chargeArt)(fx, ctx, a, t, m, boom);
  return boom;
}

/** 근접 · 돌진의 기본 그림. 모양에 rush · swing 이 없으면 이것을 쓴다 (다른 집안 파일도 불러 덧그릴 수 있다). */
export const GENERIC = Object.freeze({
  rush,
  swing(fx, ctx, a, t) {
    const m = memOf(a);
    swingAs(fx, ctx, a, t, m.kind || (m.kind = swingKind(a)));
  },
});

// ---------------------------------------------------------------- 탄 도우미
// 탄 뒤 속도선 (씨앗 + 1초에 20번 바뀐다)
function shotLines(ctx, q, n, spread, len, col, w, a, now) {
  const flick = Math.floor(now * 20);
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const h = hash(q.seed + i * 11 + flick), o = (i / Math.max(1, n - 1) - 0.5) * 2 * spread, back = q.r * (1 + h);
    const L = len * (0.6 + 0.4 * h), x = q.x - q.ux * back - q.uy * o, y = q.y - q.uy * back + q.ux * o;
    ctx.moveTo(x, y);
    ctx.lineTo(x - q.ux * L, y - q.uy * L);
  }
  strokePath(ctx, col, w, a);
}

// 탄 앞 공기 활 (1초에 f 번 앞으로 밀려 나간다)
function shotBows(ctx, q, n, col, f, now) {
  for (let i = 0; i < n; i++) {
    const ph = (now * f + i / n) % 1, d = q.r * (0.9 + ph * 1.4);
    bow(ctx, q.x + q.ux * d, q.y + q.uy * d, q.ux, q.uy, q.r * (0.5 + 0.3 * ph), q.r * (0.9 + 0.8 * ph));
    strokePath(ctx, col, 3 * (1 - ph) + 0.8, 0.8 * (1 - ph));
  }
}

// ---------------------------------------------------------------- 모양 훅
export default {
  punch: {
    shot(fx, ctx, q) {                          // 기운을 두른 주먹이 날아간다 - 기운 띠 · 속도선 · 앞 공기 활
      const { x, y, r, c } = q, now = fx.clock, s = r * 1.15;
      ribbon(ctx, q.trail, now, 0.2, r * 2.4, 2, c.dark, 0.5);
      ribbon(ctx, q.trail, now, 0.12, r * 0.8, 1, WHITE, 0.55);
      shotLines(ctx, q, 5, r * 0.8, r * 3, WHITE, 2, 0.7, now);
      shotBows(ctx, q, 2, c.light, 4, now);
      fx.ink.glow(ctx, c.dark, x, y, r * 2.8, 0.55);
      for (let i = 0; i < 3; i++) {             // 둘레를 도는 기운 갈래
        const a = q.age * 9 + (i * TAU) / 3 + q.seed;
        fx.ink.glow(ctx, c.light, x + Math.cos(a) * r * 1.1, y + Math.sin(a) * r * 1.1, r * 0.55, 0.6);
      }
      drawFist(fx, ctx, x, y, q.ang + Math.sin(q.age * 16 + q.seed) * 0.08, s, c, 1);
    },
    trail(fx, q) {
      for (let i = fx.perSec(18); i > 0; i--) {
        const a = Math.random() * TAU;
        fx.particle(WISP, q.c, q.x + Math.cos(a) * q.r, q.y + Math.sin(a) * q.r, -q.vx * 0.15 + Math.cos(a) * 40, -q.vy * 0.15 + Math.sin(a) * 40);
      }
    },
    launch(fx, q) {
      fx.wave(q.x, q.y, q.c.light, q.r * 4, 0.25, 5);
      rays(fx, q.x, q.y, q.ang, 1.4, 5, q.r, q.r * 4, WHITE, 0.16, 2);
    },
    impact(fx, x, y, ang, c, info) {           // 만화 같은 터짐 - 큰 별 · 둘레로 퍼지는 충격 선 · 고리 둘
      const s = num(info && info.s, 1);
      fx.spawn('star', x, y, 0, 0, 0.18, 24 * s, WHITE).size1 = 46 * s;
      rays(fx, x, y, ang, TAU, 9, 26 * s, 84 * s, c.light, 0.22, 3);
      fx.wave(x, y, c.light, 120 * s, 0.3, 6);
      fx.wave(x, y, c.dark, 80 * s, 0.24, 4);
      fx.burst(x, y, SPARK, c, s, ang, 1.6);
    },
    swing(fx, ctx, a, t) {                      // 주먹 (마하펀치 · 불릿펀치 같은 돌진은 빛줄기 끝에 주먹)
      if (a.mk !== 'dash') {
        swingAs(fx, ctx, a, t, 'fist');
        return;
      }
      const boom = swingAs(fx, ctx, a, t, 'dash'), m = memOf(a);
      fistArt(fx, ctx, a, t, m, boom);
    },
  },

  slash: {
    shot(fx, ctx, q) {                          // 날아가는 초승달 칼날 - 굴러가듯 기울고, 잔상 둘 · 양 끝 반짝
      const { x, y, r, c } = q, now = fx.clock, R = r * 1.9, roll = Math.cos(q.age * 10 + q.seed);
      ribbon(ctx, q.trail, now, 0.16, r * 1.8, 1, c.light, 0.3);
      streak(fx, ctx, c.dark, x - q.ux * r * 0.6, y - q.uy * r * 0.6, q.ang + PI / 2, R * 1.1, r * 0.9, 0.5);
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(q.ang);
      ctx.scale(1, 0.7 + 0.3 * Math.abs(roll));
      for (let i = 2; i >= 1; i--) {
        crescent(ctx, -R * 0.55 - r * i * 1.1, 0, R, -1.15, 1.15, R * 0.42);
        fillPath(ctx, c.light, 0.35 / i);
      }
      crescent(ctx, -R * 0.55, 0, R, -1.2, 1.2, R * 0.5);
      fillPath(ctx, c.dark, 0.7);
      crescent(ctx, -R * 0.55, 0, R * 0.98, -1.1, 1.1, R * 0.32);
      fillPath(ctx, c.light, 1);
      crescent(ctx, -R * 0.55, 0, R, -1, 1, R * 0.1);
      fillPath(ctx, WHITE, 1);
      const tw = Math.sin(now * 25 + q.seed);
      fx.ink.star(ctx, WHITE, -R * 0.55 + Math.cos(1.1) * R, Math.sin(1.1) * R, r * 0.9, 0.4 + 0.5 * Math.max(0, tw));
      fx.ink.star(ctx, WHITE, -R * 0.55 + Math.cos(1.1) * R, -Math.sin(1.1) * R, r * 0.9, 0.4 + 0.5 * Math.max(0, -tw));
      ctx.restore();
    },
    emit: { shape: 'spark', rate: 16, c: 'light', v: 50, life: 0.2, size: 8, w: 1.5 },
    launch(fx, q) { fx.spawn('star', q.x, q.y, 0, 0, 0.18, q.r * 1.5, WHITE).size1 = q.r * 2.5; },
    debris: SHRED,
    impact(fx, x, y, ang, c, info) {           // 맞은 자리를 가로지르는 칼자국 (빛 선 둘) + 양쪽으로 튀는 불티
      const s = num(info && info.s, 1), cut = ang + PI / 2 + (Math.random() - 0.5) * 0.9, L = 70 * s;
      const dx = Math.cos(cut) * L, dy = Math.sin(cut) * L;
      scar(fx, x - dx, y - dy, x + dx, y + dy, c.light, 0.3, 12 * s);
      scar(fx, x - dx * 0.9, y - dy * 0.9, x + dx * 0.9, y + dy * 0.9, WHITE, 0.22, 4 * s);
      fx.burst(x, y, SPARK, c, 0.6 * s, cut, 0.5);
      fx.burst(x, y, SPARK, c, 0.6 * s, cut + PI, 0.5);
      fx.spawn('star', x + dx, y + dy, 0, 0, 0.25, 16, WHITE);
      fx.spawn('star', x - dx, y - dy, 0, 0, 0.25, 16, WHITE);
    },
    cone(fx, ctx, q) {                          // 에어컷터 · 잎날가르기 - 칼날 여럿이 부채꼴을 따라 날아간다
      const { x, y, ang, len, h, c } = q;
      if (q.phase === 'mark') {                 // 표시 동안: 부채꼴 안에서 칼바람이 깜박인다
        for (let i = 0; i < 6; i++) {
          const a = ang + (hash(q.seed + i) - 0.5) * 1.8 * h, d = len * (0.25 + 0.65 * hash(q.seed + i + 9));
          const fl = Math.max(0, Math.sin(fx.clock * 9 + i * 2.1)) * q.u;
          if (fl < 0.05) continue;
          ctx.save();
          ctx.translate(x + Math.cos(a) * d, y + Math.sin(a) * d);
          ctx.rotate(a + 0.6);
          crescent(ctx, -len * 0.03, 0, len * 0.05, -1, 1, len * 0.018);
          fillPath(ctx, WHITE, 0.6 * fl);
          ctx.restore();
        }
        return;
      }
      const e = q.e;
      for (let i = 0; i < 7; i++) {
        const hh = hash(q.seed + i + 7), a = ang + ((i + 0.5) / 7 - 0.5) * 2 * h * 0.9 + (hash(q.seed + i) - 0.5) * 0.12;
        const d = len * (0.12 + 0.88 * easeOut(clamp01(e * 1.2 - hh * 0.2))), R = len * 0.08 * (0.8 + 0.5 * hh);
        const bx = x + Math.cos(a) * d, by = y + Math.sin(a) * d, f = 1 - e * e;
        streak(fx, ctx, c.light, bx - Math.cos(a) * d * 0.25, by - Math.sin(a) * d * 0.25, a, d * 0.25, R * 0.4, 0.4 * f);
        ctx.save();
        ctx.translate(bx, by);
        ctx.rotate(a + Math.sin(e * 8 + i) * 0.3);
        crescent(ctx, -R * 0.55, 0, R, -1.15, 1.15, R * 0.48);
        fillPath(ctx, c.dark, 0.7 * f);
        crescent(ctx, -R * 0.55, 0, R * 0.97, -1.05, 1.05, R * 0.3);
        fillPath(ctx, c.light, f);
        crescent(ctx, -R * 0.55, 0, R, -0.9, 0.9, R * 0.09);
        fillPath(ctx, WHITE, f);
        ctx.restore();
      }
    },
    swing(fx, ctx, a, t) {                      // 가위 류는 X, 할퀴기 류는 세 줄, 나머지는 크게 휘두르는 초승달
      const k = typeof a.k === 'string' ? a.k : '';
      swingAs(fx, ctx, a, t, CROSS_K.test(k) ? 'cross' : CLAW_K.test(k) ? 'claw' : 'blade');
    },
  },

  bite: {
    shot(fx, ctx, q) {                          // 여닫는 턱이 날아간다
      const { r, c } = q, R = r * 1.8, open = 0.15 + 0.5 * Math.abs(Math.sin(fx.clock * 12 + q.seed));
      ribbon(ctx, q.trail, fx.clock, 0.16, r * 1.6, 1, c.dark, 0.4);
      fx.ink.glow(ctx, c.dark, q.x, q.y, r * 2.4, 0.5);
      ctx.translate(q.x - q.ux * R * 0.45, q.y - q.uy * R * 0.45);
      ctx.rotate(q.ang);
      for (let sg = -1; sg <= 1; sg += 2) {
        ctx.save();
        ctx.rotate(sg * open);
        ctx.globalCompositeOperation = 'source-over';
        jawPath(ctx, R, sg);
        fillPath(ctx, c.dark, 0.9);
        strokePath(ctx, c.light, 2, 1);
        teethPath(ctx, R, sg);
        fillPath(ctx, WHITE, 1);
        ctx.restore();
      }
    },
    emit: { shape: 'glow', rate: 10, c: 'dark', v: 20, life: 0.3, size: 6 },
    impact(fx, x, y, ang, c, info) {           // 이빨 자국 - 위아래 줄로 박히는 반짝임
      const s = num(info && info.s, 1), px = -Math.sin(ang), py = Math.cos(ang);
      for (let sg = -1; sg <= 1; sg += 2) {
        for (let i = -1; i <= 1; i++) {
          const bx = x + Math.cos(ang) * i * 14 * s + px * sg * 16 * s, by = y + Math.sin(ang) * i * 14 * s + py * sg * 16 * s;
          fx.spawn('star', bx, by, -px * sg * 30, -py * sg * 30, 0.3, (i ? 9 : 12) * s, WHITE);
        }
      }
      fx.burst(x, y, SPARK, c, 0.8 * s, ang + PI / 2, 0.8);
      fx.burst(x, y, SPARK, c, 0.8 * s, ang - PI / 2, 0.8);
      fx.wave(x, y, c.light, 70 * s, 0.25, 4);
    },
    swing(fx, ctx, a, t) { swingAs(fx, ctx, a, t, 'jaw'); },
  },

  rock: {
    shot(fx, ctx, q) {                          // 굴러가는 바위 - 흙먼지 꼬리 · 땅 그림자 · 맞바람
      const { x, y, r, c } = q, spin = (q.seed % 2 ? 1 : -1) * (5 + 4 * hash(q.seed)), rot = q.age * spin + q.seed;
      ctx.globalCompositeOperation = 'source-over';
      for (let i = 1; i <= 4; i++) {
        const back = r * (0.8 + i * 0.75), wob = (noise1(q.age * 6 + i * 3.1 + q.seed) - 0.5) * r * 0.9;
        fx.ink.soft(ctx, DIRT.light, x - q.ux * back - q.uy * wob, y - q.uy * back + q.ux * wob, r * (0.9 + i * 0.3), 0.5 - i * 0.09);
      }
      ctx.beginPath();
      ctx.ellipse(x + 3, y + r * 1.25, r * 0.95, r * 0.32, 0, 0, TAU);
      fillPath(ctx, INK, 0.25);
      rockAt(ctx, x, y, r * 1.15, rot, q.seed, c, 1);
      ctx.globalCompositeOperation = 'lighter';
      bow(ctx, x + q.ux * r * 1.3, y + q.uy * r * 1.3, q.ux, q.uy, r * 0.5, r * 0.9);
      strokePath(ctx, WHITE, 1.5, 0.35);
    },
    trail(fx, q) {                              // 흙먼지 (몸 아래) + 떨어지는 부스러기
      for (let i = fx.perSec(20); i > 0; i--) {
        fx.particle(DUSTLET, DIRT, q.x - q.ux * q.r + (Math.random() - 0.5) * q.r, q.y - q.uy * q.r + (Math.random() - 0.5) * q.r,
          -q.vx * 0.1 + (Math.random() - 0.5) * 40, -q.vy * 0.1 + (Math.random() - 0.5) * 40, 1.4);
      }
      for (let i = fx.perSec(6); i > 0; i--) {
        fx.particle(CHIP, q.c, q.x, q.y, -q.vx * 0.2 + (Math.random() - 0.5) * 80, -q.vy * 0.2 - 120 * Math.random(), 0.5);
      }
    },
    launch(fx, q) {
      fx.burst(q.x, q.y, KICK, DIRT, 0.6, q.ang + PI, 1.6);
      fx.burst(q.x, q.y, GRIT, DIRT, 0.8, q.ang, 1.2);
    },
    debris: 'pebble',
    impact(fx, x, y, ang, c, info) {           // 바위가 깨진다 - 덩이 · 부스러기 · 흙먼지 (떨어진 바위 · 다이아스톰은 더 크게)
      const why = info && info.why, s = num(info && info.s, 1), R = num(info && info.r);
      if (why === 'tele') {                    // 무더기는 표시가 사라진 뒤에도 잠깐 남는다
        const stone = /STONEEDGE|ARROWS/.test(String(info.k));
        for (let i = 0; i < (stone ? 8 : 4); i++) {
          const a = Math.random() * TAU, d = R * 0.55 * Math.sqrt(Math.random()), px = x + Math.cos(a) * d, py = y + Math.sin(a) * d;
          if (stone) fx.particle(SPLINTER, c, px, py, Math.cos(a) * 60, -260 - 200 * Math.random(), 1.2);
          else fx.particle(RUBBLE, c, px, py, Math.cos(a) * 30, Math.sin(a) * 30, 0.8 + 0.5 * Math.random());
        }
        heave(fx, x, y, c, 12, R * 0.2, R * 0.9, 300);
        fx.burst(x, y, CLOUD, DIRT, 1.2, 0, TAU, R * 0.3, R * 0.9);
        return;
      }
      if (why === 'ring') {
        fx.burst(x, y, SHRED, c, 2, 0, TAU, R * 0.6, R);
        return;
      }
      if (why === 'cone') {
        fx.burst(x, y, CLOUD, DIRT, 0.8, ang, 1.2);
        return;
      }
      fx.burst(x, y, CHIP, c, 1.2 * s, ang, 2.2);
      fx.burst(x, y, KICK, DIRT, 0.8 * s, ang, 2.6);
      fx.wave(x, y, DIRT.light, 80 * s, 0.3, 5);
    },
    fall(fx, ctx, q, x, y, v) {                 // 스톤샤워: 바위 여럿이 차례로 · 스톤에지: 뾰족 돌이 끝부터 떨어진다
      const stone = /STONEEDGE|ARROWS/.test(String(q.k)), n = stone ? 4 : 3;
      for (let i = 0; i < n; i++) {
        const di = i * 0.16, vi = clamp01((v - di) / (1 - di));
        if (vi <= 0) continue;
        const a = hash(q.seed + i * 5) * TAU, d = q.r * 0.5 * Math.sqrt(hash(q.seed + i * 5 + 1));
        const gx = q.x + Math.cos(a) * d, gy = q.y + Math.sin(a) * d, ry = gy - (1 - vi) * FALL_H * 1.1, sz = q.r * (stone ? 0.32 : 0.36) * (0.8 + 0.4 * hash(q.seed + i));
        ctx.globalCompositeOperation = 'source-over';
        ctx.beginPath();
        ctx.ellipse(gx, gy, sz * (0.4 + 0.5 * vi), sz * (0.15 + 0.2 * vi), 0, 0, TAU);
        fillPath(ctx, INK, 0.3 * vi);
        ctx.globalCompositeOperation = 'lighter';
        fx.ink.stretch(ctx, q.c.light, gx, ry - sz * 1.6, sz * 0.4, sz * 1.8, 0.35 * vi);
        if (stone) stoneAt(ctx, gx, ry, sz, PI / 2 + Math.sin(vi * 3 + i) * 0.15, q.c, 1);
        else rockAt(ctx, gx, ry, sz, vi * 7 + i, q.seed + i, q.c, 1);
      }
    },
    tele(fx, ctx, q) {                          // 표시: 땅이 들썩인다. 떨어지면: 바위 무더기 · 금 · 흙먼지 (스톤에지는 돌 가시가 솟는다)
      const m = q.mem;
      if (q.phase === 'mark') {
        pebbles(ctx, q, 7, q.r * 0.85, q.u, fx.clock);
        return;
      }
      const e = q.e, f = 1 - e, cr = m.cracks || (m.cracks = makeCracks(q.seed, 6));
      cracks(ctx, cr, q.x, q.y, q.r * 1.1, 0.3 + 0.7 * easeOut(Math.min(1, e * 2)), q.c, f, 0.4 * f);
      ctx.globalCompositeOperation = 'source-over';
      for (let i = 0; i < 12; i++) {            // 흙먼지 고리
        const a = (i / 12) * TAU + q.seed, d = q.r * (0.5 + 0.5 * easeOut(e));
        fx.ink.soft(ctx, DIRT.light, q.x + Math.cos(a) * d, q.y + Math.sin(a) * d, q.r * (0.25 + 0.2 * e), 0.5 * f);
      }
      if (/STONEEDGE/.test(String(q.k))) {
        const g = easeOut(Math.min(1, e * 3));
        for (let i = 0; i < 7; i++) {
          const a = hash(q.seed + i * 7) * TAU, d = q.r * 0.75 * Math.sqrt(hash(q.seed + i * 7 + 2));
          spireAt(ctx, q.x + Math.cos(a) * d, q.y + Math.sin(a) * d, q.r * (0.5 + 0.45 * hash(q.seed + i)) * g, q.r * 0.13, q.c, f);
        }
        return;
      }
      for (let i = 0; i < 4; i++) {
        const a = hash(q.seed + i * 5) * TAU, d = q.r * 0.5 * Math.sqrt(hash(q.seed + i * 5 + 1)), sz = q.r * 0.36 * (0.8 + 0.4 * hash(q.seed + i));
        const bounce = Math.sin(Math.min(1, e * 2.5) * PI) * sz * 0.4;
        rockAt(ctx, q.x + Math.cos(a) * d, q.y + Math.sin(a) * d - bounce, sz, 7 + i, q.seed + i, q.c, f);
      }
    },
    haz(fx, ctx, q) {                           // 스텔스록 - 둥둥 떠서 천천히 도는 뾰족 돌 (땅 그림자 · 반짝임)
      const r = q.hr, t = fx.clock;
      for (let i = 0; i < 5; i++) {
        const a = hash(q.seed + i) * TAU + t * 0.15, d = r * (0.25 + 0.5 * hash(q.seed + i + 5)), sz = 11 + 5 * hash(q.seed + i + 9);
        const gx = q.x + Math.cos(a) * d, gy = q.y + Math.sin(a) * d, lift = 12 + 4 * Math.sin(t * 2.2 + i * 1.7);
        ctx.globalCompositeOperation = 'source-over';
        ctx.beginPath();
        ctx.ellipse(gx, gy + 4, sz * 0.9, sz * 0.32, 0, 0, TAU);
        fillPath(ctx, INK, 0.25);
        stoneAt(ctx, gx, gy - lift, sz, -PI / 2 + Math.sin(t * 1.3 + i) * 0.5, q.c, 1);
        ctx.globalCompositeOperation = 'lighter';
        fx.ink.star(ctx, WHITE, gx - sz * 0.15, gy - lift - sz * 0.7, 9, 0.2 + 0.6 * Math.max(0, Math.sin(t * 3 + i * 1.7)));
      }
    },
    ring(fx, ctx, q) {                          // 다이아스톰 - 표시 동안 둘레에 뜨는 돌, 터지면 결정이 바깥으로
      const { c } = q;
      if (q.phase === 'mark') {
        for (let i = 0; i < 8; i++) {
          const a = (i / 8) * TAU + fx.clock * 1.5 + q.seed, d = BODY_R * 1.8 + q.r * 0.15 * q.u;
          stoneAt(ctx, q.x + Math.cos(a) * d, q.y + Math.sin(a) * d - 10 * q.u, 6 + 4 * q.u, a, c, 0.4 + 0.6 * q.u);
        }
        return;
      }
      const e = q.e, f = 1 - e;
      ring(ctx, c.light, 0.6 * f, 3 + 8 * f, q.x, q.y, q.rr);
      for (let i = 0; i < 12; i++) {
        const a = (i / 12) * TAU + q.seed, d = q.rr * (0.9 + 0.15 * hash(q.seed + i)), x = q.x + Math.cos(a) * d, y = q.y + Math.sin(a) * d;
        stoneAt(ctx, x, y, 9 + 5 * hash(q.seed + i + 3), a + e * 6, c, f);
        ctx.globalCompositeOperation = 'lighter';
        if (i % 3 === 0) fx.ink.star(ctx, WHITE, x, y, 14, f);
      }
    },
    cone(fx, ctx, q) {                          // 모래뿌리기 · 타르샷 - 부채꼴로 흩뿌리는 모래 구름과 알갱이
      const { x, y, ang, len, h, c } = q;
      if (q.phase === 'mark') {                 // 발밑에서 맴도는 모래
        ctx.beginPath();
        for (let i = 0; i < 12; i++) {
          const a = (i / 12) * TAU + fx.clock * 4, d = BODY_R * (1 + 0.4 * hash(q.seed + i));
          const gx = x + Math.cos(a) * d, gy = y + Math.sin(a) * d;
          ctx.moveTo(gx, gy);
          ctx.lineTo(gx - Math.sin(a) * 5, gy + Math.cos(a) * 5);
        }
        strokePath(ctx, c.light, 2.5, 0.7 * q.u);
        return;
      }
      const e = q.e, f = 1 - e;
      ctx.globalCompositeOperation = 'source-over';
      for (let i = 0; i < 9; i++) {
        const hh = hash(q.seed + i + 20), a = ang + (hash(q.seed + i) - 0.5) * 1.7 * h, d = len * (0.12 + 0.88 * easeOut(e) * (0.55 + 0.45 * hh));
        fx.ink.soft(ctx, c.light, x + Math.cos(a) * d, y + Math.sin(a) * d, len * (0.08 + 0.1 * e) * (0.7 + 0.6 * hh), 0.75 * f);
      }
      ctx.globalCompositeOperation = 'lighter';
      ctx.beginPath();
      for (let i = 0; i < 36; i++) {
        const a = ang + (hash(q.seed + i * 3) - 0.5) * 2 * h, d = len * clamp01(e * (0.6 + 0.7 * hash(q.seed + i * 3 + 1)));
        if (d < 8) continue;
        ctx.moveTo(x + Math.cos(a) * (d - 7), y + Math.sin(a) * (d - 7));
        ctx.lineTo(x + Math.cos(a) * d, y + Math.sin(a) * d);
      }
      strokePath(ctx, c.light, 2.2, 0.9 * f);
    },
    swing(fx, ctx, a, t) {                      // 박치기 · 드릴 · 구르기 - 기본 + 멈춘 자리에서 바위 조각
      const m = memOf(a), boom = swingAs(fx, ctx, a, t, m.kind || (m.kind = swingKind(a)));
      if (!boom) return;
      const bx = a.x + a.ux * BODY_R * 1.2, by = a.y + a.uy * BODY_R * 1.2;
      fx.burst(bx, by, CHIP, a.c, 1.4, a.ang, 2);
      fx.burst(bx, by + BODY_R * 0.5, KICK, DIRT, 0.8, a.ang, 2.4);
    },
  },

  quake: {
    shot(fx, ctx, q) {                          // 땅을 타고 달리는 충격 - 지나온 길이 갈라지고, 앞에서 흙이 들썩인다
      const { x, y, r, c } = q, tr = q.trail;
      if (tr.n >= 2) {
        ctx.beginPath();
        ctx.moveTo(tr.x(0), tr.y(0));
        for (let i = 1; i < tr.n; i++) {
          const o = (hash(q.seed + i * 7) - 0.5) * r * 0.8;
          ctx.lineTo(tr.x(i) - q.uy * o, tr.y(i) + q.ux * o);
        }
        ctx.globalCompositeOperation = 'source-over';
        strokePath(ctx, INK, 4, 0.45);
        ctx.globalCompositeOperation = 'lighter';
        strokePath(ctx, c.light, 1.5, 0.6);
      }
      ctx.globalCompositeOperation = 'source-over';
      fx.ink.soft(ctx, DIRT.light, x, y, r * 2.2, 0.6);
      for (let i = 0; i < 3; i++) {
        const a = q.age * 7 + (i * TAU) / 3 + q.seed, hop = Math.abs(Math.sin(q.age * 25 + i * 2)) * r * 0.5;
        rockAt(ctx, x + Math.cos(a) * r * 0.7, y + Math.sin(a) * r * 0.5 - hop, r * 0.35, a, i, c, 1);
      }
      ctx.globalCompositeOperation = 'lighter';
      for (let i = 0; i < 2; i++) {
        const ph = (fx.clock * 3 + i / 2) % 1;
        ring(ctx, c.light, 0.7 * (1 - ph), 2.5, x, y, r * (0.5 + ph * 1.6));
      }
    },
    trail(fx, q) {
      for (let i = fx.perSec(14); i > 0; i--) {
        fx.particle(CHIP, q.c, q.x, q.y, (Math.random() - 0.5) * 120, -150 - 100 * Math.random(), 0.6);
      }
      for (let i = fx.perSec(16); i > 0; i--) fx.particle(DUSTLET, DIRT, q.x, q.y + q.r * 0.5, (Math.random() - 0.5) * 60, 0, 1.6);
    },
    debris: 'pebble',
    fall(fx, ctx, q, x, y, v) {                 // 대지의힘 · 땅가르기: 하늘에서 오지 않는다 - 땅 밑에서 빛이 차오른다
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.glow(ctx, q.c.light, q.x, q.y, q.r * (0.5 + 0.5 * v), 0.25 + 0.35 * v);
      const cr = q.mem.cracks || (q.mem.cracks = makeCracks(q.seed, 7));
      cracks(ctx, cr, q.x, q.y, q.r, 0.25 + 0.5 * v, q.c, 1, 0.5 + 0.5 * v);
    },
    tele(fx, ctx, q) {                          // 땅이 터진다 - 금 · 금에서 솟는 빛기둥 · 흙먼지
      const cr = q.mem.cracks || (q.mem.cracks = makeCracks(q.seed, 7));
      if (q.phase === 'mark') {
        pebbles(ctx, q, 8, q.r * 0.9, q.u, fx.clock);
        cracks(ctx, cr, q.x, q.y, q.r, 0.1 + 0.25 * q.u, q.c, q.u, q.u * 0.6);
        return;
      }
      const e = q.e, f = 1 - e;
      cracks(ctx, cr, q.x, q.y, q.r * 1.15, 0.5 + 0.5 * easeOut(Math.min(1, e * 2)), q.c, f, f);
      ctx.globalCompositeOperation = 'lighter';
      for (let i = 0; i < 5; i++) {
        const k = cr[i * 2], j = Math.min(4, k.xs.length - 1), px = q.x + k.xs[j] * q.r, py = q.y + k.ys[j] * q.r;
        const hgt = q.r * (0.6 + 0.8 * hash(q.seed + i)) * easeOut(Math.min(1, e * 3));
        fx.ink.stretch(ctx, q.c.light, px, py - hgt / 2, 8 + 6 * f, hgt / 2 + 4, 0.7 * f);
        fx.ink.stretch(ctx, WHITE, px, py - hgt / 2, 3, hgt / 2, 0.6 * f);
      }
      fx.ink.core(ctx, q.c.light, q.x, q.y, q.r * 0.6 * f, f);
      ctx.globalCompositeOperation = 'source-over';
      for (let i = 0; i < 10; i++) {
        const a = (i / 10) * TAU + q.seed, d = q.r * (0.6 + 0.5 * easeOut(e));
        fx.ink.soft(ctx, DIRT.light, q.x + Math.cos(a) * d, q.y + Math.sin(a) * d, q.r * 0.3, 0.5 * f);
      }
    },
    ring(fx, ctx, q) {                          // 지진 · 땅고르기 - 떨리던 땅에서 금이 바깥으로 내달리고 흙먼지 물결이 퍼진다
      const cr = q.mem.cracks || (q.mem.cracks = makeCracks(q.seed, 9));
      if (q.phase === 'mark') {
        pebbles(ctx, q, 12, q.r * 0.9, q.u, fx.clock);
        cracks(ctx, cr, q.x, q.y, q.r, 0.08 + 0.3 * q.u * q.u, q.c, 0.4 + 0.6 * q.u, 0.3 * q.u);
        return;
      }
      const e = q.e, f = 1 - e;
      cracks(ctx, cr, q.x, q.y, q.r, Math.max(0.2, q.rr / q.r), q.c, 1 - 0.5 * e, f);
      ctx.globalCompositeOperation = 'source-over';
      for (let i = 0; i < 18; i++) {            // 흙먼지 물결 (지금 고리 자리)
        const a = (i / 18) * TAU + q.seed, d = q.rr * (0.92 + 0.12 * hash(q.seed + i));
        fx.ink.soft(ctx, DIRT.light, q.x + Math.cos(a) * d, q.y + Math.sin(a) * d, q.r * (0.13 + 0.1 * e), 0.6 * f);
      }
      for (let i = 0; i < 10; i++) {            // 안쪽 둘째 물결
        const a = (i / 10) * TAU + q.seed + 0.3, d = q.rr * 0.55;
        fx.ink.soft(ctx, DIRT.light, q.x + Math.cos(a) * d, q.y + Math.sin(a) * d, q.r * 0.12, 0.35 * f);
      }
      ctx.globalCompositeOperation = 'lighter';
      ring(ctx, q.c.light, 0.7 * f, 2 + 4 * f, q.x, q.y, q.rr);
    },
    impact(fx, x, y, ang, c, info) {           // 덩이가 솟았다 떨어진다
      const why = info && info.why, R = num(info && info.r), s = num(info && info.s, 1);
      if (why === 'ring') {
        heave(fx, x, y, c, 18, R * 0.25, R, 380);
        fx.burst(x, y, CLOUD, DIRT, 1.6, 0, TAU, R * 0.5, R);
        fx.burst(x, y, CLOUD, DIRT, 0.8, 0, TAU, R * 0.15, R * 0.5);
        return;
      }
      if (why === 'tele') {
        heave(fx, x, y, c, 16, 0, R * 0.8, 460);
        fx.burst(x, y, CLOUD, DIRT, 1, 0, TAU, R * 0.3, R);
        return;
      }
      heave(fx, x, y, c, Math.round(6 * s), 0, 30 * s, 300);
      fx.burst(x, y, KICK, DIRT, 0.8 * s);
    },
    swing(fx, ctx, a, t) {                      // 짓밟기 · 10만마력 - 어깨 충격파 + 멈춘 자리에서 앞으로 땅이 갈라진다
      const m = memOf(a), boom = swingAs(fx, ctx, a, t, a.mk === 'dash' ? 'dash' : 'charge');
      if (m.bk < 0) return;
      const hw = laneHW(a), cx = a.x + a.ux * BODY_R, cy = a.y + a.uy * BODY_R;
      const cr = m.cracks || (m.cracks = makeCracks(Math.floor(num(a.seed) * 1000), 7));
      if (m.cx === undefined) {
        m.cx = cx;
        m.cy = cy;
      }
      cracks(ctx, cr, m.cx, m.cy, hw * 1.8, 0.2 + 0.8 * easeOut(m.bk), a.c, 1 - m.bk, 1 - m.bk);
      if (boom) {
        heave(fx, cx, cy, a.c, 8, 0, hw, 320);
        fx.burst(cx, cy, CLOUD, DIRT, 0.8, 0, TAU, 0, hw * 0.6);
      }
    },
  },

  web: {
    shot(fx, ctx, q) {                          // 펼쳐지며 도는 거미줄 그물 + 뒤로 끌리는 실
      const { x, y, r, c } = q, open = 0.45 + 0.55 * easeOut(Math.min(1, q.age * 3)), R = r * 2 * open;
      ribbon(ctx, q.trail, fx.clock, 0.4, 3, 0.6, SILK, 0.7);
      fx.ink.glow(ctx, c.light, x, y, R * 1.2, 0.3);
      ctx.globalCompositeOperation = 'source-over';
      webPath(ctx, x, y, R, 8, 3, q.seed, q.age * 2.2 + q.seed, 0.25);
      strokePath(ctx, INK, 2.6, 0.25);
      strokePath(ctx, SILK, 1.2, 0.9);
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.star(ctx, WHITE, x, y, r * 0.8, 0.7);
    },
    emit: { shape: 'spark', rate: 6, c: WHITE, v: 30, life: 0.25, size: 6, w: 1 },
    launch(fx, q) { rays(fx, q.x, q.y, q.ang, 1, 5, q.r * 0.5, q.r * 3, SILK, 0.25, 1.2); },
    debris: 'glint',
    impact(fx, x, y, ang, c, info) {           // 실이 감긴다 - 몸 둘레를 도는 실 몇 가닥 + 반짝임
      const s = num(info && info.s, 1);
      for (let i = 0; i < 6; i++) {
        const a0 = Math.random() * TAU, a1 = a0 + 1 + Math.random(), r = (22 + 14 * Math.random()) * s;
        scar(fx, x + Math.cos(a0) * r, y + Math.sin(a0) * r * 0.8, x + Math.cos(a1) * r, y + Math.sin(a1) * r * 0.8, SILK, 0.6, 1.5);
      }
      fx.burst(x, y, GLINT, c, 0.8 * s);
      fx.wave(x, y, SILK, 60 * s, 0.3, 2);
    },
    cone(fx, ctx, q) {                          // 실뿜기 · 일렉트릭네트 - 실 가닥이 뻗어 나가 끝에서 그물이 된다
      const { x, y, ang, len, h, c } = q, zap = q.ty === 'ELECTRIC';
      const n = 9, mark = q.phase === 'mark', e = mark ? 0 : q.e;
      const reach = mark ? 0.25 * q.u : easeOut(Math.min(1, e * 1.6)), f = mark ? q.u : 1 - smooth(Math.max(0, e - 0.4) / 0.6);
      if (!(reach > 0.01)) return;
      const fl = zap && !mark ? 0.6 + 0.4 * Math.sin(fx.clock * 60) : 1;
      ctx.beginPath();
      for (let i = 0; i < n; i++) {             // 가닥 (조금 처진 곡선)
        const a = ang + (i / (n - 1) - 0.5) * 2 * h * 0.92 + (hash(q.seed + i) - 0.5) * 0.06, L = len * reach * (0.85 + 0.15 * hash(q.seed + i + 3));
        const sag = len * 0.04 * (hash(q.seed + i + 5) - 0.5);
        quadTo(ctx, x, y, x + Math.cos(a) * L * 0.5 - Math.sin(a) * sag, y + Math.sin(a) * L * 0.5 + Math.cos(a) * sag, x + Math.cos(a) * L, y + Math.sin(a) * L);
      }
      if (!mark) {                              // 가로실 - 가닥이 지나간 둘레만 (가운데로 처진다)
        for (const k of [0.4, 0.62, 0.8, 0.95]) {
          if (reach < k) continue;
          for (let i = 0; i < n - 1; i++) {
            const a0 = ang + (i / (n - 1) - 0.5) * 2 * h * 0.92, a1 = ang + ((i + 1) / (n - 1) - 0.5) * 2 * h * 0.92, R = len * k;
            const am = (a0 + a1) / 2;
            ctx.moveTo(x + Math.cos(a0) * R, y + Math.sin(a0) * R);
            ctx.quadraticCurveTo(x + Math.cos(am) * R * 0.94, y + Math.sin(am) * R * 0.94, x + Math.cos(a1) * R, y + Math.sin(a1) * R);
          }
        }
      }
      ctx.globalCompositeOperation = 'lighter';
      strokePath(ctx, c.light, 4, 0.3 * f * fl);
      ctx.globalCompositeOperation = 'source-over';
      strokePath(ctx, zap ? c.light : SILK, 1.4, 0.85 * f * fl);
      ctx.globalCompositeOperation = 'lighter';
      for (let i = 0; i < n; i += 2) {          // 가닥 끝 반짝
        const a = ang + (i / (n - 1) - 0.5) * 2 * h * 0.92, L = len * reach;
        fx.ink.star(ctx, WHITE, x + Math.cos(a) * L, y + Math.sin(a) * L, 10, 0.7 * f);
      }
    },
    haz(fx, ctx, q) {                           // 끈적끈적네트 - 바닥에 펼친 둥근 거미줄 (그림자 · 은빛 실 · 이슬 반짝)
      const r = q.hr * (1 + 0.015 * Math.sin(fx.clock * 1.5)), rot = q.seed * 0.37;
      ctx.globalCompositeOperation = 'source-over';
      webPath(ctx, q.x + 2, q.y + 3, r, 11, 6, q.seed, rot, 0.12);
      strokePath(ctx, INK, 2.4, 0.22);
      webPath(ctx, q.x, q.y, r, 11, 6, q.seed, rot, 0.12);
      strokePath(ctx, SILK, 1.1, 0.62);
      ctx.globalCompositeOperation = 'lighter';
      for (let i = 0; i < 6; i++) {
        const a = rot + hash(q.seed + i * 3) * TAU, d = r * (0.3 + 0.6 * hash(q.seed + i * 3 + 1));
        fx.ink.star(ctx, q.c.light, q.x + Math.cos(a) * d, q.y + Math.sin(a) * d, 8, 0.15 + 0.7 * Math.max(0, Math.sin(fx.clock * 2.5 + i * 1.3)));
      }
    },
  },

  heal: {
    shot(fx, ctx, q) {                          // 생기 구슬 - 초록 빛 · 맥박치는 흰 십자 · 둘레를 도는 잎빛
      const { x, y, r } = q, pulse = 1 + 0.12 * Math.sin(fx.clock * 10 + q.seed);
      fx.ink.glow(ctx, HEAL.dark, x, y, r * 2.6 * pulse, 0.55);
      for (let i = 0; i < 3; i++) {
        const a = q.age * 5 + (i * TAU) / 3;
        fx.ink.glow(ctx, HEAL.light, x + Math.cos(a) * r * 1.3, y + Math.sin(a) * r * 1.3, r * 0.5, 0.8);
      }
      fx.ink.core(ctx, HEAL.light, x, y, r * 1.2, 1);
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = 1;
      ctx.fillStyle = WHITE;
      ctx.fillRect(x - r * 0.65 * pulse, y - r * 0.2, r * 1.3 * pulse, r * 0.4);
      ctx.fillRect(x - r * 0.2, y - r * 0.65 * pulse, r * 0.4, r * 1.3 * pulse);
    },
    emit: { shape: 'plus', rate: 10, c: HEAL.light, v: 20, life: 0.5, size: 5, g: -60 },
  },

  buff: {
    shot(fx, ctx, q) {                          // 기운 구슬 - 도는 기운 호 셋 + 흰 심
      const { x, y, r, c } = q;
      fx.ink.glow(ctx, c.dark, x, y, r * 2.6, 0.5);
      for (let i = 0; i < 3; i++) {
        const a = fx.clock * 7 + (i * TAU) / 3;
        ctx.beginPath();
        ctx.arc(x, y, r * 1.35, a, a + 1.4);
        strokePath(ctx, c.light, 3, 0.85);
      }
      fx.ink.core(ctx, c.light, x, y, r * 1.1, 1);
    },
    emit: { shape: 'arrow', rate: 8, c: UP, v: 15, life: 0.5, size: 7, up: -90, end: 1 },
  },

  shield: {
    shot(fx, ctx, q) {                          // 벌집 막 - 도는 육각 · 안쪽 칸 · 테를 도는 빛
      const { x, y, r, c } = q, rot = fx.clock * 1.5;
      fx.ink.glow(ctx, c.light, x, y, r * 2.4, 0.45);
      shape(ctx, HEX_PTS, x, y, r * 1.5, rot);
      fillPath(ctx, c.light, 0.15);
      strokePath(ctx, c.light, 2.5, 0.95);
      for (let i = 0; i < 6; i++) {
        const a = rot + (i * TAU) / 6;
        shape(ctx, HEX_PTS, x + Math.cos(a) * r * 0.75, y + Math.sin(a) * r * 0.75, r * 0.4, rot);
        strokePath(ctx, WHITE, 1, 0.45);
      }
      const e0 = rot + (Math.floor(fx.clock * 8) % 6) * (TAU / 6);
      ctx.globalAlpha = 1;
      line(ctx, WHITE, 3, x + Math.cos(e0) * r * 1.5, y + Math.sin(e0) * r * 1.5, x + Math.cos(e0 + TAU / 6) * r * 1.5, y + Math.sin(e0 + TAU / 6) * r * 1.5);
    },
    emit: { shape: 'star', rate: 8, c: 'light', v: 20, life: 0.3, size: 7 },
  },
};

// 2차 곡선 한 가닥 (경로에 더한다)
function quadTo(ctx, x0, y0, cx, cy, x1, y1) {
  ctx.moveTo(x0, y0);
  ctx.quadraticCurveTo(cx, cy, x1, y1);
}

// ---------------------------------------------------------------- 몸에 두르는 그림 (AURA) - 그리기만 한다 (입자 없음, 씨앗으로 고정)
const SWORD = [1, 0, 0.62, 0.07, -0.42, 0.07, -0.42, -0.07, 0.62, -0.07];

/** 회복 · 강화 · 방어 - a = {x, y, c, seed, k?, sty?}, t 0~1 (fx.js 의 pillar · shield anim 이 부르게 된다). */
export const AURA = Object.freeze({
  /** 회복 (HP 회복 · 날개쉬기 · 광합성): 발밑에서 번지는 고리 · 솟는 초록 빛 알갱이와 십자 · 반짝임 · 부드러운 맥박. */
  heal(fx, ctx, a, t) {
    const s = Math.sin(PI * clamp01(t)), c = HEAL, fy = a.y + BODY_R * 1.1, seed = Math.floor(num(a.seed) * 100);
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 2; i++) {
      const k = (t * 1.6 + i * 0.5) % 1;
      ctx.beginPath();
      ctx.ellipse(a.x, fy, BODY_R * (0.8 + 1.8 * k), BODY_R * (0.3 + 0.6 * k), 0, 0, TAU);
      strokePath(ctx, c.light, 3 * (1 - k) + 0.5, 0.8 * (1 - k) * s);
    }
    fx.ink.stretch(ctx, c.dark, a.x, a.y - BODY_R * 0.4, BODY_R * (1.3 + 0.1 * Math.sin(t * 30)), BODY_R * 2.2, 0.35 * s);
    for (let i = 0; i < 12; i++) {
      const ph = (t * 1.4 + hash(seed + i)) % 1, x = a.x + (hash(seed + i + 40) - 0.5) * BODY_R * 2.6 + Math.sin(ph * 9 + i) * 5;
      const y = fy - ph * BODY_R * 3.6, al = Math.sin(PI * ph) * s;
      if (i % 3) fx.ink.glow(ctx, c.light, x, y, 5 + 3 * hash(seed + i + 7), al);
      else {
        ctx.globalAlpha = clamp01(al);
        ctx.fillStyle = WHITE;
        ctx.fillRect(x - 5, y - 1.5, 10, 3);
        ctx.fillRect(x - 1.5, y - 5, 3, 10);
      }
    }
    for (let i = 0; i < 4; i++) {
      const a2 = hash(seed + i * 9) * TAU, d = BODY_R * (0.6 + 0.8 * hash(seed + i * 9 + 1));
      fx.ink.star(ctx, WHITE, a.x + Math.cos(a2) * d, a.y + Math.sin(a2) * d * 1.3 - BODY_R * 0.3, 10, s * Math.max(0, Math.sin(t * 20 + i * 2)));
    }
  },
  /** 강화 (칼춤 · 용의춤 · 나쁜음모 · 벌크업): 몸을 도는 기운 띠 · 솟는 화살 · 발밑 고리. 칼춤은 칼 넷이 몸을 돈다. */
  buff(fx, ctx, a, t) {
    const s = Math.sin(PI * clamp01(t)), c = a.c || HEAL, seed = Math.floor(num(a.seed) * 100), fy = a.y + BODY_R * 1.1;
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.stretch(ctx, c.dark, a.x, a.y - BODY_R * 0.3, BODY_R * 1.4, BODY_R * 2.1, 0.4 * s);
    for (let i = 0; i < 3; i++) {               // 몸을 감아 오르는 기운 띠 (앞쪽 반만 진하게)
      const y = fy - BODY_R * (0.4 + i * 0.9) - t * BODY_R * 0.6, rot = t * 14 + i * 2.1;
      for (let half = 0; half < 2; half++) {
        ctx.beginPath();
        ctx.ellipse(a.x, y, BODY_R * (1.4 - i * 0.2), BODY_R * 0.4, 0, rot + half * PI, rot + half * PI + 2);
        strokePath(ctx, half ? c.light : WHITE, half ? 3 : 2, (half ? 0.9 : 0.35) * s);
      }
    }
    for (let i = 0; i < 6; i++) {               // 솟는 화살
      const ph = (t * 1.5 + hash(seed + i)) % 1, x = a.x + (hash(seed + i + 20) - 0.5) * BODY_R * 2.4, y = fy - ph * BODY_R * 3.4;
      ctx.globalCompositeOperation = 'source-over';
      shape(ctx, [1, 0, 0.1, -0.8, 0.1, -0.32, -0.9, -0.32, -0.9, 0.32, 0.1, 0.32, 0.1, 0.8], x, y, 8, -PI / 2);
      fillPath(ctx, UP, Math.sin(PI * ph) * s);
    }
    ctx.globalCompositeOperation = 'lighter';
    if (/SWORDSDANCE/.test(String(a.k))) {      // 칼 넷이 몸을 돌다 끝에 위를 겨눈다
      for (let i = 0; i < 4; i++) {
        const ang = t * 9 + (i * TAU) / 4, rx = a.x + Math.cos(ang) * BODY_R * 1.7, ry = a.y + Math.sin(ang) * BODY_R * 0.7 - BODY_R * 0.4;
        const tip = -PI / 2 + (1 - smooth(clamp01(t * 1.5))) * (ang + PI / 2);
        shape(ctx, SWORD, rx, ry, BODY_R * 1.1, tip);
        fillPath(ctx, '#e8f0ff', 0.9 * s);
        strokePath(ctx, '#7f9aa8', 1.2, s);
        line(ctx, GOLD, 3, rx + Math.cos(tip + PI / 2) * 7 - Math.cos(tip) * 5, ry + Math.sin(tip + PI / 2) * 7 - Math.sin(tip) * 5,
          rx - Math.cos(tip + PI / 2) * 7 - Math.cos(tip) * 5, ry - Math.sin(tip + PI / 2) * 7 - Math.sin(tip) * 5);
      }
    }
    ctx.beginPath();
    ctx.ellipse(a.x, fy, BODY_R * (1.2 + 0.6 * t), BODY_R * (0.45 + 0.2 * t), 0, 0, TAU);
    strokePath(ctx, c.light, 3, 0.8 * s);
  },
  /** 방어 (방어 · 판별 · 버티기): 벌집 육각 돔 - 칸마다 반짝임이 훑고 지나가고, 테에서 물결이 퍼진다. */
  shield(fx, ctx, a, t) {
    const c = a.c || HEAL, fade = clamp01(t < 0.15 ? t / 0.15 : t > 0.75 ? (1 - t) / 0.25 : 1), R = BODY_R * 2.1 * (0.7 + 0.3 * easeOut(clamp01(t * 6)));
    const cell = R / 3.2, sweep = (t * 2.5) % 1;
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, c.light, a.x, a.y, R * 1.1, 0.25 * fade);
    ctx.beginPath();
    for (let row = -3; row <= 3; row++) {        // 벌집 칸 (돔 안의 것만)
      for (let col = -3; col <= 3; col++) {
        const cx = a.x + (col + (row & 1 ? 0.5 : 0)) * cell * 1.73, cy = a.y + row * cell * 1.5;
        if (Math.hypot(cx - a.x, cy - a.y) > R - cell * 0.8) continue;
        hexAt(ctx, cx, cy, cell * 0.95);
      }
    }
    strokePath(ctx, c.light, 1.2, 0.45 * fade);
    for (let row = -3; row <= 3; row++) {        // 훑고 지나가는 반짝임 (위에서 아래로)
      const cy = a.y + row * cell * 1.5, k = 1 - Math.abs((cy - (a.y - R + sweep * 2 * R)) / (cell * 2));
      if (k <= 0) continue;
      for (let col = -3; col <= 3; col++) {
        const cx = a.x + (col + (row & 1 ? 0.5 : 0)) * cell * 1.73;
        if (Math.hypot(cx - a.x, cy - a.y) > R - cell * 0.8) continue;
        ctx.beginPath();
        hexAt(ctx, cx, cy, cell * 0.95);
        fillPath(ctx, c.light, 0.3 * k * fade);
      }
    }
    circleStroke(ctx, a.x, a.y, R, c.light, 3, 0.9 * fade);
    circleStroke(ctx, a.x, a.y, R * 0.97, WHITE, 1.2, 0.6 * fade);
    for (let i = 0; i < 2; i++) {                // 테에서 퍼지는 물결
      const k = (t * 3 + i / 2) % 1;
      circleStroke(ctx, a.x, a.y, R * (1 + 0.35 * k), c.light, 2 * (1 - k) + 0.5, 0.5 * (1 - k) * fade);
    }
    fx.ink.star(ctx, WHITE, a.x - R * 0.45, a.y - R * 0.55, 14, fade * Math.max(0, Math.sin(t * 25)));
  },
});


function hexAt(ctx, x, y, r) {
  for (let i = 0; i < 6; i++) {
    const px = x + HEX_PTS[i * 2] * r, py = y + HEX_PTS[i * 2 + 1] * r;
    if (i) ctx.lineTo(px, py);
    else ctx.moveTo(px, py);
  }
  ctx.closePath();
}

function circleStroke(ctx, x, y, r, col, w, a) {
  ctx.beginPath();
  ctx.arc(x, y, r > 0 ? r : 0, 0, TAU);
  strokePath(ctx, col, w, a);
}
