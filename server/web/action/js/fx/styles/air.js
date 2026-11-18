/* 모양: 바람 · 소리 · 물 · 결정 (wind sound jet wave shard).
   훅 이름 · 인자 · q · a 칸 · 도우미는 fx/core.js 맨 위. 이 파일에는 이 다섯 키만 둔다 (fx/styles/index.js 의 FAMILY_OF).

   그림 (모양은 q.seed · fx.clock 으로만 움직인다 - 같은 탄은 프레임마다 같은 꼴, 탄마다 조금씩 다르다)
     wind   흰 · 하늘빛 나선 가닥 셋 (굵기 · 꼬임 · 빠르기가 서로 달라 꽈배기로 안 보인다) 이 나아가는 축을 감고 돌며
            꼬리로 가늘어지고, 양옆 흐름선 둘은 바깥으로 불룩하게 흐르다 꼬리에서 말린다 + 머리의 열린 소용돌이 · 앞의
            바람 앞머리 · 아지랑이 띠. 실려 가다 튕겨 나가는 것은 기술 타입마다 (얼음 눈 · 불 불티 · 땅 모래 · 풀 잎 ·
            요정 꽃잎 · 전기 불꽃 · 그 밖은 마른 잎과 먼지). 맞으면 나선 팔이 바깥으로 풀리며 끝에서 바람 줄이 튄다.
            부채꼴은 휘몰아치는 바람줄기 (용 · 폭풍 기술은 회오리 기둥이 쓸고 간다), 고리는 퍼지는 나선,
            내려찍기(폭풍)는 하늘에서 내려와 땅에 닿는 회오리 기둥, 근접 · 돌진은 몸을 감싸는 바람과 바람 칼.
     sound  떨리는 소리 앞머리가 머리에서 태어나 커지며 뒤로 처진다 (앞이 촘촘) + 울림통 + 따라 도는 음표.
            부채꼴 · 고리는 퍼지는 떨리는 소리 벽, 맞으면 물결 고리 셋과 음표.
     jet    눌린 물줄기 - 윤기 나는 머리, 꼬리에서 물방울로 부서진다. 맞으면 물방울 왕관 + 바닥 물결.
            부채꼴은 물줄기 부채, 고리는 사방으로 터지는 물기둥, 내려찍기는 땅에서 솟는 물기둥, 근접은 물을 두른 몸 · 물 호.
     wave   말리는 물마루 - 앞의 흰 거품 줄 · 양 끝이 말린다 · 뒤로 거품 줄 + 맥박 고리. 고리 · 부채꼴은 밀려 나가는
            물마루 (서버 반지름에 딱 닿는다).
     shard  긴 축으로 도는 깎인 결정 (빛 받는 면이 바뀐다) + 냉기 · 눈송이, 맞으면 반짝이는 조각으로 깨진다.
            부채꼴은 바닥에서 솟는 결정 + 몰아치는 눈, 내려찍기는 떨어지는 큰 고드름과 바닥의 서리 무늬,
            근접 · 돌진은 지나간 자리에 돋는 결정 · 깎인 초승달.
   얼음 · 서리는 얼음 타입에서만 (강철 · 벌레 결정은 반짝임 · 불티). */
import {
  A, BODY_R, FALL_H, INK, ROCK_PTS, TAU, WHITE, circle, clamp01, crescent, easeOut, fillPath, hash, leafPath, line,
  noise1, ribbon, ring, rnd, shape, strokePath, streak,
} from '../core.js';

// ---------------------------------------------------------------- 수치
const H3 = 0.55;                 // 높이 → 화면 위쪽 (3/4 시점에서 공중의 것)
const SHOT_MIN = 9;              // 탄 반지름을 이 사이로 (그림 크기)
const SHOT_MAX = 30;
const FIRE_K = 0.7;              // 장판은 서버가 t1 + act 에 지운다 - 터지는 그림은 q.e 가 이만큼일 때 끝나게
const LEAF_COLS = ['#b8d878', '#d6c46a', '#8cc063', '#c9a25a', '#e0d49a'];
const MIST = '#e6f6ff';
const DUSTY = '#b9c4cf';
const FOAM = '#f4fbff';
const CLOUD = '#4a5468';
// 폭풍 기술 - 부채꼴이 회오리 기둥으로 (용 타입 부채꼴 = 회오리도 그렇게)
const STORMS = new Set(['TWISTER', 'BLEAKWINDSTORM', 'SANDSEARSTORM', 'SPRINGTIDESTORM', 'WILDBOLTSTORM', 'HURRICANE']);
// 터지는 장판의 진행 (0~1) - 서버가 지우기 전에 끝난다
const fireK = (q) => clamp01(q.e / FIRE_K);
const sizeOf = (q) => Math.max(SHOT_MIN, Math.min(SHOT_MAX, q.r));

// ---------------------------------------------------------------- 점 버퍼 · 띠 (이 파일만 쓰는 도우미 - 프레임마다 새로 만들지 않는다)
const NMAX = 48;
const PX = new Float64Array(NMAX), PY = new Float64Array(NMAX), PW = new Float64Array(NMAX);
const NX = new Float64Array(NMAX), NY = new Float64Array(NMAX);

/** PX · PY 앞 n 점을 따라 폭 PW × ws 인 띠 경로. 폭 0 인 끝은 뾰족하다. */
function band(ctx, n, ws = 1) {
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const a = i ? i - 1 : 0, b = i < n - 1 ? i + 1 : i;
    const dx = PX[b] - PX[a], dy = PY[b] - PY[a], d = Math.hypot(dx, dy) || 1, w = PW[i] * ws * 0.5;
    NX[i] = (-dy / d) * w;
    NY[i] = (dx / d) * w;
    ctx.lineTo(PX[i] + NX[i], PY[i] + NY[i]);
  }
  for (let i = n - 1; i >= 0; i--) ctx.lineTo(PX[i] - NX[i], PY[i] - NY[i]);
  ctx.closePath();
}

/** PX · PY 앞 n 점을 잇는 선 경로. */
function poly(ctx, n) {
  ctx.beginPath();
  for (let i = 0; i < n; i++) ctx.lineTo(PX[i], PY[i]);
}

/** 띠를 두 겹으로 - 넓고 옅은 빛 + 가는 심. */
function glowBand(ctx, n, halo, ha, core, ca, wide = 2.4) {
  band(ctx, n, wide);
  fillPath(ctx, halo, ha);
  band(ctx, n, 1);
  fillPath(ctx, core, ca);
}

/** (cx, cy) 가운데 R 의 a0 → a1 호를 n 점으로 PX · PY 에. 반지름이 amp 만큼 freq 번 떨린다. PW 는 가운데가 굵은 꼴 × w. */
function arcPts(cx, cy, R, a0, a1, n, amp, freq, ph, w) {
  for (let i = 0; i < n; i++) {
    const k = i / (n - 1), a = a0 + (a1 - a0) * k, rr = Math.max(0, R + Math.sin(k * freq * TAU + ph) * amp);
    PX[i] = cx + Math.cos(a) * rr;
    PY[i] = cy + Math.sin(a) * rr;
    PW[i] = w * Math.sin(Math.PI * k);
  }
}

/** 고리 (온 원) 는 이음매가 없게 PW 를 고른 굵기로. */
function evenW(n, w) {
  for (let j = 0; j < n; j++) PW[j] = w;
}

// 가닥 폭 꼴: 머리(0)에서 peak 까지 굵어지고 꼬리(1)로 가늘어진다
const spindle = (k, peak) => (k < peak ? 0.3 + 0.7 * (k / peak) : Math.pow(Math.max(0, 1 - (k - peak) / (1 - peak)), 1.3));

/** 나선 (cx, cy) 가운데 - 바깥 r0 에서 안 r1 으로 turns 바퀴, 앞(ang) 쪽으로 squash 배 눌린다. 폭은 바깥이 굵다. */
function spiralPts(cx, cy, ang, r0, r1, th0, turns, squash, w, n) {
  const ux = Math.cos(ang), uy = Math.sin(ang);
  for (let j = 0; j < n; j++) {
    const k = j / (n - 1), th = th0 + k * turns * TAU, rad = r0 + (r1 - r0) * k;
    const a = Math.cos(th) * rad * squash, b = Math.sin(th) * rad;
    PX[j] = cx + ux * a - uy * b;
    PY[j] = cy + uy * a + ux * b;
    PW[j] = w * Math.sin(Math.PI * (0.05 + 0.9 * k)) * (1.15 - 0.5 * k) + 0.4;
  }
}

// ---------------------------------------------------------------- 실려 가는 것 (타입마다)
const M_LEAF = 0, M_SNOW = 1, M_EMBER = 2, M_SAND = 3, M_GREEN = 4, M_PETAL = 5, M_SPARK = 6, M_DROP = 7;

function motif(ty) {
  switch (ty) {
    case 'ICE': return M_SNOW;
    case 'FIRE': return M_EMBER;
    case 'GROUND': case 'ROCK': case 'STEEL': return M_SAND;
    case 'GRASS': case 'BUG': return M_GREEN;
    case 'FAIRY': case 'PSYCHIC': return M_PETAL;
    case 'ELECTRIC': return M_SPARK;
    case 'WATER': return M_DROP;
    default: return M_LEAF;
  }
}

/** 바람에 실린 것 하나를 입자로. */
function mote(fx, m, c, x, y, vx, vy, k = 1) {
  let p;
  switch (m) {
    case M_SNOW:
      p = fx.spawn(Math.random() < 0.55 ? 'star' : 'glow', x, y, vx, vy, rnd(0.45, 0.8), rnd(3, 5.5) * k, WHITE);
      p.drag = 1.4;
      p.size1 = p.size * 0.6;
      return p;
    case M_EMBER:
      p = fx.spawn(Math.random() < 0.6 ? 'spark' : 'glow', x, y, vx, vy - 40, rnd(0.35, 0.6), rnd(4, 8) * k, Math.random() < 0.5 ? c.light : c.dark);
      p.w = 1.8;
      p.g = -90;
      p.drag = 1.6;
      return p;
    case M_SAND:
      p = fx.spawn('rock', x, y, vx, vy, rnd(0.4, 0.7), rnd(1.6, 3) * k, c.dark);
      p.color2 = c.light;
      p.vr = rnd(-14, 14);
      p.drag = 1.8;
      p.size1 = p.size;
      return p;
    case M_SPARK:
      p = fx.spawn('bolt', x, y, vx * 0.5, vy * 0.5, rnd(0.12, 0.22), rnd(8, 13) * k, c.light);
      p.w = 1.5;
      p.drag = 3;
      return p;
    case M_DROP:
      p = fx.spawn('glow', x, y, vx, vy, rnd(0.3, 0.5), rnd(2.5, 4) * k, c.light);
      p.g = 380;
      p.drag = 1;
      return p;
    default: {
      const col = m === M_GREEN ? (Math.random() < 0.5 ? c.light : c.dark) : m === M_PETAL ? (Math.random() < 0.6 ? c.light : WHITE)
        : LEAF_COLS[(Math.random() * LEAF_COLS.length) | 0];
      if (m === M_LEAF && Math.random() < 0.3) {               // 먼지 티끌
        p = fx.spawn('glow', x, y, vx, vy, rnd(0.3, 0.55), rnd(2, 3.5) * k, '#e8eefc');
        p.drag = 1.2;
        return p;
      }
      p = fx.spawn('leaf', x, y, vx, vy, rnd(0.5, 0.85), rnd(3.2, 5.2) * k, col);
      p.vr = rnd(-16, 16);
      p.rot = rnd(0, TAU);
      p.drag = 2.2;
      p.g = 40;
      p.size1 = p.size;
      return p;
    }
  }
}

/** 그리는 훅 안에서 실린 것 하나 (입자가 아니라 그 자리에 그린다). */
function glyph(fx, ctx, m, c, x, y, sz, rot, a) {
  switch (m) {
    case M_SNOW: ctx.globalCompositeOperation = 'lighter'; fx.ink.star(ctx, WHITE, x, y, sz * 1.6, a); return;
    case M_EMBER: ctx.globalCompositeOperation = 'lighter'; fx.ink.core(ctx, c.light, x, y, sz * 1.2, a); return;
    case M_SPARK: ctx.globalCompositeOperation = 'lighter'; fx.ink.star(ctx, c.light, x, y, sz * 1.5, a); return;
    case M_DROP: ctx.globalCompositeOperation = 'lighter'; fx.ink.core(ctx, c.light, x, y, sz, a); return;
    case M_SAND:
      ctx.globalCompositeOperation = 'source-over';
      shape(ctx, ROCK_PTS[(rot * 10) & 3], x, y, sz * 0.6, rot);
      fillPath(ctx, c.dark, a);
      return;
    default:
      ctx.globalCompositeOperation = 'source-over';
      leafPath(ctx, x, y, sz, rot);
      fillPath(ctx, m === M_GREEN || m === M_PETAL ? c.light : LEAF_COLS[(rot * 7) & 3], a);
  }
}

// ---------------------------------------------------------------- 입자 도우미
function dot(fx, shp, x, y, vx, vy, life, size, col, g = 0, drag = 0, end = 0.4) {
  const p = fx.spawn(shp, x, y, vx, vy, life, size, col);
  p.g = g;
  p.drag = drag;
  p.size1 = size * end;
  p.rot = Math.atan2(vy, vx);
  return p;
}

/** 늘어난 줄 (spark) - 날아가는 쪽 반대로 꼬리가 선다. */
function streakDot(fx, x, y, vx, vy, life, size, col, w = 2, drag = 3) {
  const p = fx.spawn('spark', x, y, vx, vy, life, size, col);
  p.w = w;
  p.drag = drag;
  p.size1 = size;
  return p;
}

/** 도는 회오리가 바깥으로 풀린다: 나선 팔 arms 개를 마디 줄 (멈춘 'line' 입자) 로 - 안쪽 마디가 먼저 사라져
    소용돌이가 바깥으로 풀려 나가는 것처럼 보인다. 팔 끝에서는 접선 쪽으로 바람 줄이 튄다. dir 은 도는 쪽. */
function whirl(fx, x, y, R, arms, c, k = 1, dir = 1) {
  const n = 7, a0 = Math.random() * TAU;
  for (let arm = 0; arm < arms; arm++) {
    const b = a0 + (arm * TAU) / arms;
    let lx = x + Math.cos(b) * R * 0.18, ly = y + Math.sin(b) * R * 0.18 * 0.8;
    for (let i = 1; i <= n; i++) {
      const kk = i / n, a = b + dir * kk * 2.6, rr = R * (0.18 + 0.82 * kk), nx = x + Math.cos(a) * rr, ny = y + Math.sin(a) * rr * 0.8;
      const p = fx.spawn('line', nx, ny, 0, 0, 0.14 + 0.3 * kk, 1, kk > 0.4 ? WHITE : c.light);
      p.x2 = lx;
      p.y2 = ly;
      p.w = (1.2 + 3.2 * Math.sin(Math.PI * Math.min(1, kk * 1.1))) * k;
      lx = nx;
      ly = ny;
    }
    const a = b + dir * 2.6, tx = -Math.sin(a) * dir, ty = Math.cos(a) * dir, v = rnd(300, 420);   // 팔 끝 - 접선으로 튄다
    streakDot(fx, lx, ly, tx * v, ty * v * 0.8, rnd(0.25, 0.35), 20 * k, WHITE, 2.4 * k, 3);
  }
}

/** 물방울 왕관: 위로 부채꼴로 튀었다 떨어지는 물줄기 · 물방울 + 바닥 물결 하나 (3/4 시점이라 위 = 화면 위). */
function crown(fx, x, y, k, c) {
  const n = Math.round(11 * k), sk = Math.sqrt(k);
  for (let i = 0; i < n; i++) {                 // 왕관의 물줄기 - 날아가는 쪽으로 늘어난다
    const a = -Math.PI / 2 + ((i + 0.5) / n - 0.5) * 2.6 + rnd(-0.12, 0.12), sp = rnd(260, 430) * sk;
    const p = streakDot(fx, x + Math.cos(a) * 12 * k, y + 4, Math.cos(a) * sp, Math.sin(a) * sp, rnd(0.35, 0.5), rnd(10, 15) * k,
      i % 3 ? c.light : WHITE, rnd(2.4, 3.4) * k, 0.6);
    p.g = 1250;
  }
  for (let i = 0; i < 14 * k; i++) {            // 물방울
    const a = -Math.PI / 2 + rnd(-1.3, 1.3), sp = rnd(160, 380) * sk;
    dot(fx, 'core', x + rnd(-12, 12) * k, y + rnd(-4, 4), Math.cos(a) * sp, Math.sin(a) * sp, rnd(0.45, 0.7), rnd(4.5, 6.5) * k,
      i % 3 ? c.light : WHITE, 1150, 0.5, 0.7);
  }
  const m = Math.round(8 * k);
  for (let i = 0; i < m; i++) {                 // 왕관 테 - 둘레에서 솟는 물기둥 (위로 늘어난 빛)
    const a = (i / m) * TAU + rnd(-0.2, 0.2), rx = 34 * k, ry = 12 * k;
    const p = dot(fx, 'wisp', x + Math.cos(a) * rx, y + 6 + Math.sin(a) * ry, Math.cos(a) * 40, -rnd(60, 120), rnd(0.25, 0.35),
      rnd(14, 20) * k, Math.sin(a) > 0 ? WHITE : c.light, 300, 2, 1.2);
    p.layer = Math.sin(a) > 0 ? 1 : 0;          // 앞 반은 몸 위, 뒤 반은 몸 뒤
  }
  fx.wave(x, y + 6, c.light, 75 * k, 0.5, 2.5, 0);
}

/** 거품 · 물안개 몇 덩이 (보통 혼합). */
function foam(fx, x, y, n, r, v) {
  for (let i = 0; i < n; i++) {
    const a = rnd(0, TAU), sp = rnd(0.3, 1) * v;
    const p = dot(fx, 'smoke', x + Math.cos(a) * r * rnd(0, 1), y + Math.sin(a) * r * rnd(0, 0.6), Math.cos(a) * sp, Math.sin(a) * sp * 0.6 - 20,
      rnd(0.4, 0.7), rnd(8, 14), FOAM, 0, 3, 2);
    p.layer = 0;
  }
}

/** 반짝이는 조각으로 깨진다. */
function shatter(fx, x, y, k, c, frosty, ang = 0, arc = TAU) {
  const n = Math.round(12 * k);
  for (let i = 0; i < n; i++) {
    const a = ang + (Math.random() - 0.5) * arc, sp = rnd(140, 360) * Math.sqrt(k);
    const p = dot(fx, 'shard', x, y, Math.cos(a) * sp, Math.sin(a) * sp - 40, rnd(0.35, 0.6), rnd(4, 8) * k, i % 3 ? c.light : WHITE, 420, 2.2, 1);
    p.vr = rnd(-18, 18);
    p.color2 = c.dark;
  }
  for (let i = 0; i < 6 * k; i++) {
    const a = ang + (Math.random() - 0.5) * arc, sp = rnd(80, 240);
    dot(fx, 'star', x, y, Math.cos(a) * sp, Math.sin(a) * sp, rnd(0.25, 0.45), rnd(7, 12) * k, WHITE, 0, 4, 0.3);
  }
  if (frosty) {
    for (let i = 0; i < 5 * k; i++) {
      const a = rnd(0, TAU), sp = rnd(30, 90);
      dot(fx, 'smoke', x, y, Math.cos(a) * sp, Math.sin(a) * sp - 15, rnd(0.5, 0.8), rnd(10, 16) * k, MIST, 0, 2.5, 2.2);
    }
  }
}

// ---------------------------------------------------------------- 결정 하나 (shard)
/** (x, y) 가운데 ang 을 겨눈 길이 L · 폭 W 의 깎인 결정. spin 은 긴 축으로 도는 각 - 등줄이 옆으로 옮겨 가며
    빛 받는 면이 바뀐다. 면은 보통 혼합 (단단한 얼음 · 쇠), 테는 흰 선. */
// 꼭짓점 0 앞 끝 · 1 왼 어깨 · 2 왼 뒤어깨 · 3 뒤 끝 · 4 오른 뒤어깨 · 5 오른 어깨 · 6 · 7 등줄 (앞 · 뒤)
const C_AL = [0.55, 0.12, -0.28, -0.45, -0.28, 0.12, 0.12, -0.28];
const C_OF = [0, -1, -0.85, 0, 0.85, 1, 0, 0];
const CX = new Float64Array(8), CY = new Float64Array(8);
const FACES = [[0, 1, 6], [0, 6, 5], [1, 2, 7, 6], [6, 7, 4, 5], [2, 3, 4, 7]];
const RIM = [0, 1, 2, 3, 4, 5];

function facet(ctx, idx) {
  ctx.beginPath();
  for (let i = 0; i < idx.length; i++) ctx.lineTo(CX[idx[i]], CY[idx[i]]);
  ctx.closePath();
}

function crystal(ctx, x, y, ang, L, W, spin, c, a) {
  if (!(L > 0.5) || !(a > 0)) return;
  const ux = Math.cos(ang), uy = Math.sin(ang), px = -uy, py = ux, hw = W / 2;
  const m = Math.sin(spin) * hw * 0.8, lit = px * -0.6 + py * -0.8 < 0;      // 빛은 왼쪽 위에서
  for (let i = 0; i < 8; i++) {
    const o = i < 6 ? C_OF[i] * hw : i === 6 ? m : m * 0.85;
    CX[i] = x + ux * C_AL[i] * L + px * o;
    CY[i] = y + uy * C_AL[i] * L + py * o;
  }
  ctx.globalCompositeOperation = 'source-over';
  facet(ctx, FACES[0]);
  fillPath(ctx, lit ? WHITE : c.light, a * 0.95);
  facet(ctx, FACES[1]);
  fillPath(ctx, lit ? c.light : WHITE, a * 0.95);
  facet(ctx, FACES[2]);
  fillPath(ctx, lit ? c.light : c.dark, a * 0.92);
  facet(ctx, FACES[3]);
  fillPath(ctx, lit ? c.dark : c.light, a * 0.92);
  facet(ctx, FACES[4]);
  fillPath(ctx, c.dark, a * 0.95);
  facet(ctx, RIM);
  strokePath(ctx, WHITE, Math.max(0.8, W * 0.07), a * 0.85);
  ctx.beginPath();
  ctx.moveTo(CX[0], CY[0]);
  ctx.lineTo(CX[6], CY[6]);
  ctx.lineTo(CX[7], CY[7]);
  strokePath(ctx, WHITE, Math.max(0.6, W * 0.05), a * 0.7);
}

// 서리 무늬 (눈송이 여섯 갈래 + 잔가지) - 내려찍기 표시 아래 바닥이 언다
function frostPattern(ctx, x, y, R, rot, col, a) {
  if (!(R > 1)) return;
  ctx.beginPath();
  for (let i = 0; i < 6; i++) {
    const t = rot + (i * TAU) / 6, cx = Math.cos(t), cy = Math.sin(t);
    ctx.moveTo(x, y);
    ctx.lineTo(x + cx * R, y + cy * R);
    for (let b = 1; b <= 2; b++) {
      const d = R * (0.35 + 0.28 * b), l = R * (0.32 - 0.08 * b), bx = x + cx * d, by = y + cy * d;
      for (let sd = -1; sd <= 1; sd += 2) {
        const tt = t + sd * 0.75;
        ctx.moveTo(bx, by);
        ctx.lineTo(bx + Math.cos(tt) * l, by + Math.sin(tt) * l);
      }
    }
  }
  strokePath(ctx, col, Math.max(1, R * 0.03), a);
}

// ---------------------------------------------------------------- 회오리 기둥 (wind)
/** 바닥 (x, yb) 에서 꼭대기 yt 까지 도는 깔때기. 바닥이 좁고 (r0) 위가 넓다 (r1). a 알파, m 도는 조각. */
function funnel(fx, ctx, x, yb, yt, r0, r1, a, c, seed, m) {
  const H = yb - yt;
  if (!(H > 4) || !(a > 0)) return;
  const t = fx.clock, J = 8;
  const cxOf = (k) => x + Math.sin(k * 2.4 + t * 2.6 + seed) * r1 * 0.22 * k;
  const radOf = (k) => r0 + (r1 - r0) * Math.pow(k, 1.4);
  ctx.globalCompositeOperation = 'source-over';
  fx.ink.soft(ctx, CLOUD, x, yb - H * 0.5, (r0 + r1) * 0.7, a * 0.35);
  ctx.globalCompositeOperation = 'lighter';
  streak(fx, ctx, c.dark, x, yb - H * 0.5, -Math.PI / 2, H * 0.55, (r0 + r1) * 0.55, 0.4 * a);
  // 층층이 도는 고리 - 뒤 반은 어둡게, 앞 반은 밝게
  for (let j = 0; j <= J; j++) {
    const k = j / J, rad = radOf(k), cx = cxOf(k), cy = yb - H * k, ry = rad * 0.3;
    ctx.beginPath();
    ctx.ellipse(cx, cy, rad, ry, 0, Math.PI, TAU);
    strokePath(ctx, c.dark, 1 + 2.5 * k, a * 0.45);
    ctx.beginPath();
    ctx.ellipse(cx, cy, rad, ry, 0, 0, Math.PI);
    strokePath(ctx, c.light, 1.2 + 2.8 * k, a * 0.6);
  }
  // 감아 오르는 흐름선 셋
  const M = 18;
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < M; j++) {
      const k = j / (M - 1), th = k * 10 - t * 13 + (i * TAU) / 3 + seed, rad = radOf(k);
      PX[j] = cxOf(k) + Math.cos(th) * rad;
      PY[j] = yb - H * k + Math.sin(th) * rad * 0.3;
      PW[j] = (1.2 + 4.5 * k) * (0.35 + 0.65 * Math.max(0, Math.sin(th)));
    }
    glowBand(ctx, M, c.light, 0.18 * a, WHITE, 0.7 * a, 2.2);
  }
  fx.ink.glow(ctx, WHITE, x, yb, r0 * 2.2, 0.5 * a);
  // 도는 조각
  for (let d = 0; d < 6; d++) {
    const k = 0.08 + 0.85 * hash(seed + d * 3.7), th = t * (5 + 3 * hash(seed + d)) + d * 1.9, rad = radOf(k) * 1.2;
    const gx = cxOf(k) + Math.cos(th) * rad, gy = yb - H * k + Math.sin(th) * rad * 0.3;
    glyph(fx, ctx, m, c, gx, gy, 3.5 + 2.5 * k, th * 1.3, a * (Math.sin(th) > -0.3 ? 1 : 0.5));
  }
}

// ================================================================ wind
// 나선 가닥마다 [반지름 배, 꼬임 (길이 전체에서 라디안), 도는 빠르기, 길이 배, 알파] - 서로 달라야 꽈배기로 안 보인다
const WIND_STRANDS = [[1.0, 4.2, 11, 1.0, 0.62], [0.65, 6.6, 16, 0.75, 0.38], [1.3, 2.8, 7, 1.15, 0.32]];

/** 흐름선 하나가 꼬리에서 말린다 (바람 그림의 갈고리). 몸 옆 sd 쪽, 앞 al0 → 뒤 al1, 끝에서 cr 반지름으로 감긴다. */
function hook(ctx, x, y, ux, uy, sd, off, al0, al1, cr, spin, w, t, ph) {
  const px = -uy * sd, py = ux * sd, A0 = 9, B = 9;
  for (let j = 0; j < A0; j++) {                  // 바깥으로 불룩하게 흐르는 부분 (살짝 출렁인다)
    const k = j / (A0 - 1), al = al0 + (al1 - al0) * k;
    const o = off * (0.35 + 0.8 * Math.sin(Math.PI * (0.08 + k * 0.84))) + Math.sin(k * 5 + t * 7 + ph) * off * 0.1 - k * cr * 0.5;
    PX[j] = x + ux * al + px * o;
    PY[j] = y + uy * al + py * o;
    PW[j] = w * (0.25 + 0.75 * Math.sin(Math.PI * Math.min(1, 0.2 + k * 0.8)));
  }
  const ex = PX[A0 - 1], ey = PY[A0 - 1], cx = ex - px * cr, cy = ey - py * cr;   // 말리는 가운데 - 안쪽
  const a0 = Math.atan2(ey - cy, ex - cx);
  for (let j = 0; j < B; j++) {                   // 뒤로 가며 안쪽으로 감긴다
    const k = (j + 1) / B, a = a0 - sd * (k * (3.6 + spin)), rr = cr * (1 - 0.75 * k);
    PX[A0 + j] = cx + Math.cos(a) * rr;
    PY[A0 + j] = cy + Math.sin(a) * rr;
    PW[A0 + j] = w * 0.8 * (1 - k) + 0.4;
  }
  return A0 + B;
}

function windShot(fx, ctx, q) {
  const { x, y, ux, uy, c } = q, R = sizeOf(q) * 1.12, t = fx.clock, s = q.seed, px = -uy, py = ux;
  const L = R * 5.2, hx = x + ux * R * 0.55, hy = y + uy * R * 0.55, sh = 0.75 + 0.25 * Math.sin(t * 23 + s);
  ctx.globalCompositeOperation = 'lighter';
  // 공기 덩이 (옅은 하늘빛) + 지나온 길
  streak(fx, ctx, c.dark, x - ux * L * 0.35, y - uy * L * 0.35, q.ang, L * 0.75, R * 1.6, 0.24 * sh);
  streak(fx, ctx, c.light, x - ux * L * 0.15, y - uy * L * 0.15, q.ang, L * 0.4, R * 0.8, 0.12);
  ribbon(ctx, q.trail, t, 0.16, R * 2, R * 0.4, c.light, 0.08);
  // 나선 가닥 셋 - 나아가는 축을 감고 돈다 (높이는 화면 위로). 굵기 · 알파는 앞(높은 쪽)이 세다
  const M = 13;
  for (let i = 0; i < 3; i++) {
    const W = WIND_STRANDS[i], kr = W[0], tw = W[1], ph0 = s * (1.7 + i) + i * 2.3 - t * W[2], wob = s + i * 5.3, Li = L * W[3];
    for (let j = 0; j < M; j++) {
      const k = j / (M - 1), ph = ph0 + k * tw;
      const env = R * kr * (0.25 + 0.9 * Math.sqrt(k)) * (1 - 0.25 * k) + (noise1(k * 2.4 - t * 3.5 + wob) - 0.5) * R * 0.9 * k;
      const o = env * Math.sin(ph), al = R * 0.6 - k * Li;
      PX[j] = x + ux * al + px * o;
      PY[j] = y + uy * al + py * o - env * Math.cos(ph) * H3;
      PW[j] = R * 0.3 * spindle(k, 0.25) * (0.45 + 0.55 * Math.max(0, Math.cos(ph)));
    }
    glowBand(ctx, M, c.light, 0.12, WHITE, W[4], 2.8);
  }
  // 몸 바깥을 흐르다 꼬리에서 말리는 흐름선 둘 (양옆, 길이 · 말림이 서로 다르다)
  for (let sd = -1; sd <= 1; sd += 2) {
    const hs = hash(s + sd), n = hook(ctx, x, y, ux, uy, sd, R * (0.95 + 0.3 * hs), R * 0.1, -L * (0.55 + 0.25 * hs), R * (0.38 + 0.15 * hs),
      Math.sin(t * 4 + s + sd) * 0.6, R * 0.22, t, s + sd);
    glowBand(ctx, n, c.light, 0.1, WHITE, 0.5, 2.6);
  }
  // 머리의 소용돌이 (열린 두 팔 - 고리가 아니라 말림으로 보이게)
  for (let arm = 0; arm < 2; arm++) {
    spiralPts(hx, hy, q.ang, R * (arm ? 0.75 : 1.05), R * 0.12, -t * 17 + s + arm * 2.6, 1.15, 0.7, R * 0.24, 14);
    glowBand(ctx, 14, c.light, 0.14, WHITE, arm ? 0.45 : 0.7, 2.4);
  }
  // 바람 앞머리
  crescent(ctx, hx - ux * R * 0.5, hy - uy * R * 0.5, R * 1.35, q.ang - 1.05, q.ang + 1.05, R * 0.16);
  fillPath(ctx, WHITE, 0.22 * sh);
  fx.ink.glow(ctx, c.light, hx, hy, R * 1.6, 0.25);
  fx.ink.core(ctx, c.light, hx, hy, R * 0.55, 0.45);
  // 실려 가는 것 셋 - 가닥을 따라 돈다
  const m = motif(q.ty);
  for (let i = 0; i < 3; i++) {
    const k = 0.18 + 0.22 * i + 0.08 * Math.sin(t * 2 + i + s), ph = s * 1.7 + i * 2.1 - t * 12 + k * 5.2, env = R * 1.05 * Math.sqrt(k);
    const al = R * 0.6 - k * L, o = env * Math.sin(ph);
    glyph(fx, ctx, m, c, x + ux * al + px * o, y + uy * al + py * o - env * Math.cos(ph) * H3, R * 0.3, t * 9 + i * 2 + s, 0.9);
  }
}

function windTrail(fx, q) {
  const R = sizeOf(q), n = fx.perSec(30), m = motif(q.ty), px = -q.uy, py = q.ux, v = q.speed;
  for (let i = 0; i < n; i++) {
    const back = rnd(0, R * 3.5), side = rnd(-1, 1) * R, x = q.x - q.ux * back + px * side, y = q.y - q.uy * back + py * side;
    const r = Math.random();
    if (r < 0.42) {                             // 실려 가다 옆으로 튕겨 나간다
      const fling = (side >= 0 ? 1 : -1) * rnd(70, 210), f = rnd(0.3, 0.6);
      mote(fx, m, q.c, x, y, q.ux * v * f + px * fling, q.uy * v * f + py * fling - 30);
    } else if (r < 0.85) {                      // 바람 줄
      const f = rnd(0.35, 0.55);
      streakDot(fx, x, y, q.ux * v * f + px * rnd(-40, 40), q.uy * v * f + py * rnd(-40, 40), rnd(0.18, 0.3), rnd(12, 18),
        r < 0.65 ? WHITE : q.c.light, 1.3, 2.5);
    } else {
      dot(fx, 'glow', x, y, px * rnd(-50, 50), py * rnd(-50, 50) - 20, rnd(0.3, 0.55), rnd(2, 3.5), q.c.light, 0, 1);
    }
  }
}

function windLaunch(fx, q) {
  const R = sizeOf(q), px = -q.uy, py = q.ux;
  fx.wave(q.x, q.y, q.c.light, R * 3.2, 0.28, 3);
  for (let i = 0; i < 10; i++) {
    const a = q.ang + rnd(-0.7, 0.7), v = rnd(250, 480);
    streakDot(fx, q.x, q.y, Math.cos(a) * v, Math.sin(a) * v, rnd(0.15, 0.25), rnd(10, 16), i % 3 ? WHITE : q.c.light, 2, 5);
  }
  for (let sd = -1; sd <= 1; sd += 2) {         // 옆으로 밀려나는 먼지
    for (let i = 0; i < 2; i++) {
      const v = rnd(60, 130);
      dot(fx, 'smoke', q.x, q.y, px * sd * v - q.ux * 30, py * sd * v - q.uy * 30, rnd(0.35, 0.5), R * 0.45, DUSTY, 0, 3, 1.8).layer = 0;
    }
  }
}

function windImpact(fx, x, y, ang, c, info) {
  const s = info.s || 1, m = motif(info.ty), why = info.why;
  const big = why === 'tele' ? Math.max(1.4, info.r / 50) : why === 'ring' ? 1.5 : why === 'cone' ? 1.1 : s;
  const dir = Math.random() < 0.5 ? -1 : 1;
  whirl(fx, x, y, 50 * big, why === 'hit' ? 3 : 4, c, Math.min(1.5, big), dir);
  for (let i = 0; i < 7 * big; i++) {           // 튕겨 나가는 것
    const a = rnd(0, TAU), v = rnd(120, 280) * Math.sqrt(big);
    mote(fx, m, c, x, y, Math.cos(a) * v, Math.sin(a) * v - 40, 1.1);
  }
  if (why === 'hit') {                          // 맞은 몸을 꿰뚫고 지나가는 바람
    for (let i = 0; i < 6; i++) {
      const a = ang + rnd(-0.45, 0.45), v = rnd(380, 620), o = rnd(-22, 22);
      streakDot(fx, x - Math.sin(ang) * o, y + Math.cos(ang) * o, Math.cos(a) * v, Math.sin(a) * v, rnd(0.18, 0.28), 18, WHITE, 2, 3);
    }
  }
  if (why === 'tele') {                         // 기둥이 흩어지며 사방으로 먼지
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * TAU, v = rnd(160, 260);
      dot(fx, 'smoke', x + Math.cos(a) * info.r * 0.4, y + Math.sin(a) * info.r * 0.25, Math.cos(a) * v, Math.sin(a) * v * 0.6,
        rnd(0.5, 0.8), 16, '#d8dfe8', 0, 3, 2.4).layer = 0;
    }
  }
  fx.wave(x, y, c.light, 120 * big, 0.45, 1.5);
}

// 부채꼴을 휩쓰는 바람줄기 n 가닥 (f 0~1 진행, a 알파). 가닥마다 자리에 박힌 휜 흐름 길이 있고, 머리가 그 길을
// 따라 미끄러져 나간다 - 끝으로 갈수록 바깥으로 휘며 퍼진다 (지그재그가 아니라 흐르는 곡선)
function gustLines(ctx, q, f, n, a, t, hot = false) {
  const { x, y, ang, len, h, c, seed } = q, M = 16, halo = hot ? c.dark : c.light, core = hot ? c.light : WHITE;
  for (let i = 0; i < n; i++) {
    const hs = hash(seed + i * 3.1), ai = ang + (hs - 0.5) * 1.6 * h, lag = hash(seed + i) * 0.2;
    const head = len * (0.1 + 0.98 * easeOut(clamp01(f * 1.2 - lag))), tl = len * (0.4 + 0.25 * hash(seed + i + 9));
    const bend = (hs - 0.5) * 0.5 + (hash(seed + i + 4) - 0.5) * 0.25, amp = len * 0.012, ph = seed + i * 2.3 - t * 6;
    const ca = Math.cos(ai), sa = Math.sin(ai), wv = 0.6 + 0.5 * hash(seed + i + 5);
    for (let j = 0; j < M; j++) {
      const k = j / (M - 1), d = Math.max(0, head - k * tl), r = d / len;
      const o = bend * len * r * r * 0.5 + Math.sin(r * wv * TAU + ph) * amp * r;
      PX[j] = x + ca * d - sa * o;
      PY[j] = y + sa * d + ca * o;
      PW[j] = (4 + len * 0.018) * spindle(k, 0.18) * (0.6 + 0.4 * r);
    }
    glowBand(ctx, M, halo, (hot ? 0.25 : 0.14) * a, core, (0.4 + 0.35 * hash(seed + i + 7)) * a, 2.2);
  }
}

// 부채꼴 안 시드 자리에 실린 것 (눈 · 불티 · 잎) 이 밖으로 휩쓸려 간다
function coneGlyphs(fx, ctx, q, f, n, a, m) {
  const { x, y, ang, len, h, c, seed } = q, t = fx.clock;
  for (let i = 0; i < n; i++) {
    const ai = ang + (hash(seed + i * 5.3) - 0.5) * 1.9 * h, d = len * ((hash(seed + i * 2.9) + f * 1.3) % 1);
    const fade = Math.sin(Math.PI * (d / len));
    glyph(fx, ctx, m, c, x + Math.cos(ai) * d, y + Math.sin(ai) * d, 4 + 2 * hash(seed + i), t * 8 + i, a * fade);
  }
}

// 부채꼴 · 고리가 터지는 순간 한 번 - 실린 것 · 바람 줄을 뿌린다 (장판이 사라진 뒤에도 날아간다)
function coneBurst(fx, q, m, n, v) {
  const { x, y, ang, len, h, c } = q;
  for (let i = 0; i < n; i++) {
    const a = ang + (Math.random() - 0.5) * 2 * h, d = len * rnd(0.05, 0.9), sp = v * rnd(0.6, 1.2);
    const px = x + Math.cos(a) * d, py = y + Math.sin(a) * d;
    if (i % 3) mote(fx, m, c, px, py, Math.cos(a) * sp, Math.sin(a) * sp, 1.1);
    else streakDot(fx, px, py, Math.cos(a) * sp * 1.4, Math.sin(a) * sp * 1.4, rnd(0.2, 0.35), rnd(14, 22), WHITE, 2, 2.5);
  }
}

function windCone(fx, ctx, q) {
  const t = fx.clock, m = motif(q.ty), storm = q.ty === 'DRAGON' || STORMS.has(q.k);
  const { x, y, ang, len, h, c, seed } = q;
  ctx.globalCompositeOperation = 'lighter';
  if (q.phase === 'mark') {                     // 입 앞에 바람이 모인다
    const u = q.u;
    spiralPts(x, y, ang, BODY_R * (1.6 - 0.4 * u), BODY_R * 0.3, -t * 14 + seed, 1, 0.7, 4 + 4 * u, 14);
    glowBand(ctx, 14, c.light, 0.12 + 0.2 * u, WHITE, 0.25 + 0.4 * u);
    gustLines(ctx, q, 0.15 + 0.2 * ((t * 1.5) % 1), 4, 0.25 * u, t);
    if (storm) {
      for (let i = -1; i <= 1; i += 2) {
        const fx0 = x + Math.cos(ang + i * h * 0.5) * BODY_R * 1.8, fy0 = y + Math.sin(ang + i * h * 0.5) * BODY_R * 1.8;
        funnel(fx, ctx, fx0, fy0, fy0 - (30 + 70 * u), 3, 10 + 16 * u, 0.3 + 0.5 * u, c, seed + i, m);
      }
    }
    const n = fx.perSec(20 + 30 * u);            // 빨려 드는 것
    for (let i = 0; i < n; i++) {
      const a = rnd(0, TAU), d = rnd(60, 110);
      mote(fx, m, c, x + Math.cos(a) * d, y + Math.sin(a) * d, -Math.cos(a) * d * 2.5, -Math.sin(a) * d * 2.5, 0.8);
    }
    return;
  }
  const f = fireK(q), fade = 1 - f * f;
  if (!q.mem.go) {
    q.mem.go = true;
    coneBurst(fx, q, m, m === M_SNOW ? 46 : 30, 520);
    if (m === M_SNOW) coneBurst(fx, q, M_SNOW, 24, 700);
  }
  for (let i = 1; i <= 4; i++) {                // 밀려 나가는 공기 덩이 (옅은 빛 - 평평한 칠 대신)
    const d = len * 0.22 * i * (0.35 + 0.65 * easeOut(f));
    streak(fx, ctx, i & 1 ? c.dark : c.light, x + Math.cos(ang) * d, y + Math.sin(ang) * d, ang, len * 0.2, d * Math.tan(h) * 0.8 + 10, 0.28 * fade);
  }
  gustLines(ctx, q, f, 9, fade, t, m === M_EMBER);   // 열풍은 노랗게 달아오른 줄
  coneGlyphs(fx, ctx, q, f, m === M_SNOW ? 26 : 12, fade, m);
  if (storm) {                                  // 회오리 둘이 부채꼴을 쓸고 나간다
    for (let i = -1; i <= 1; i += 2) {
      const a = ang + i * h * 0.55, d = len * (0.12 + 0.8 * easeOut(clamp01(f * 1.1 - (i > 0 ? 0.15 : 0))));
      const fx0 = x + Math.cos(a) * d, fy0 = y + Math.sin(a) * d;
      funnel(fx, ctx, fx0, fy0, fy0 - 100 - 40 * f, 4, 26 + 10 * f, fade, c, seed + i, m);
    }
  }
}

function windRing(fx, ctx, q) {
  const t = fx.clock, m = motif(q.ty), { x, y, c, seed } = q;
  ctx.globalCompositeOperation = 'lighter';
  if (q.phase === 'mark') {                     // 발밑에서 감아 도는 바람
    const u = q.u;
    for (let arm = 0; arm < 3; arm++) {
      spiralPts(x, y, 0, q.r * (0.3 + 0.35 * u), BODY_R * 0.4, -t * 9 + seed + (arm * TAU) / 3, 0.6, 1, 3 + 5 * u, 14);
      glowBand(ctx, 14, c.light, 0.1 + 0.15 * u, WHITE, 0.2 + 0.35 * u);
    }
    return;
  }
  const f = fireK(q), fade = 1 - f * f, R = q.r * (0.25 + 0.75 * easeOut(f));
  if (!q.mem.go) {
    q.mem.go = true;
    for (let i = 0; i < 34; i++) {
      const a = rnd(0, TAU), d = q.r * rnd(0.1, 0.5), v = rnd(240, 420);
      mote(fx, m, c, x + Math.cos(a) * d, y + Math.sin(a) * d, Math.cos(a) * v - Math.sin(a) * v * 0.6, Math.sin(a) * v + Math.cos(a) * v * 0.6, 1.1);
    }
  }
  fx.ink.glow(ctx, c.dark, x, y, R * 1.05, 0.3 * fade);
  for (let arm = 0; arm < 6; arm++) {           // 바깥으로 퍼지며 도는 나선 팔 (팔마다 길이 · 휨 · 굵기가 다르다)
    const ha = hash(seed + arm * 7.3), th0 = seed + (arm * TAU) / 6 + (ha - 0.5) * 0.6 - t * 6 - f * 3, bend = 1.2 + 0.9 * ha;
    const reach = R * (0.75 + 0.3 * hash(seed + arm)), wa = 0.6 + 0.6 * hash(seed + arm * 3);
    for (let j = 0; j < 14; j++) {
      const k = j / 13, rad = reach * (0.25 + 0.8 * k), th = th0 + k * bend;
      PX[j] = x + Math.cos(th) * rad;
      PY[j] = y + Math.sin(th) * rad;
      PW[j] = (3 + 7 * k) * wa * Math.sin(Math.PI * Math.min(1, k * 1.15));
    }
    glowBand(ctx, 14, c.light, 0.2 * fade, WHITE, (0.4 + 0.3 * ha) * fade);
  }
  ring(ctx, WHITE, 0.7 * fade, 2 + 4 * (1 - f), x, y, R);
  ring(ctx, c.light, 0.4 * fade, 8 * (1 - f) + 1, x, y, R * 0.92);
}

// 폭풍 (내려찍기): 표시 동안 바닥에 바람이 감아 돌고, 하늘에서 회오리가 내려와 (fall) 닿고, 터지면 흩어진다
function windTele(fx, ctx, q) {
  const t = fx.clock, m = motif(q.ty), { x, y, c, seed } = q;
  ctx.globalCompositeOperation = 'lighter';
  if (q.phase === 'mark') {
    const u = q.u;
    for (let arm = 0; arm < 3; arm++) {
      spiralPts(x, y, 0, q.r * (0.5 + 0.45 * u), q.r * 0.08, -t * (6 + 8 * u) + seed + (arm * TAU) / 3, 0.7, 1, 3 + 6 * u, 16);
      glowBand(ctx, 16, c.light, 0.1 + 0.15 * u, WHITE, 0.15 + 0.4 * u);
    }
    for (let d = 0; d < 5; d++) {                // 바닥에서 도는 잎 · 먼지
      const th = t * (3 + 2 * u) + d * 1.3 + seed, rad = q.r * (0.4 + 0.5 * hash(seed + d));
      glyph(fx, ctx, m, c, x + Math.cos(th) * rad, y + Math.sin(th) * rad - 6 * u * d, 4, th * 2, 0.4 + 0.5 * u);
    }
    return;
  }
  const f = fireK(q), fade = 1 - f;              // 기둥이 넓어지며 흩어진다
  funnel(fx, ctx, x, y, y - FALL_H * 1.1, q.r * (0.18 + 0.6 * f), q.r * (1.05 + 0.8 * f), fade, c, seed, m);
  for (let arm = 0; arm < 4; arm++) {
    spiralPts(x, y, 0, q.r * (0.4 + 1.1 * easeOut(f)), q.r * 0.1, -t * 10 + seed + (arm * TAU) / 4, 0.5, 1, 10 * fade + 1, 14);
    glowBand(ctx, 14, c.light, 0.25 * fade, WHITE, 0.7 * fade);
  }
}

function windFall(fx, ctx, q, x, y, v) {
  const m = motif(q.ty), top = q.y - FALL_H * 1.1;
  ctx.globalCompositeOperation = 'source-over';   // 꼭대기 먹구름
  for (let i = 0; i < 4; i++) {
    const a = fx.clock * 0.8 + q.seed + i * 1.6;
    fx.ink.soft(ctx, CLOUD, q.x + Math.cos(a) * q.r * 0.7, top + Math.sin(a) * q.r * 0.18, q.r * (0.9 + 0.2 * i), 0.35 + 0.3 * v);
  }
  funnel(fx, ctx, q.x, Math.max(y, top + 30), top, q.r * 0.16, q.r * 1.05, 0.35 + 0.65 * v, q.c, q.seed, m);
  if (v > 0.6) {                                 // 땅에 닿으려 한다 - 먼지가 인다
    const n = fx.perSec(40 * v);
    for (let i = 0; i < n; i++) {
      const a = rnd(0, TAU), d = q.r * rnd(0.2, 0.5), sp = rnd(80, 160);
      dot(fx, 'smoke', q.x + Math.cos(a) * d, q.y + Math.sin(a) * d * 0.5, -Math.sin(a) * sp, Math.cos(a) * sp * 0.5 - 20,
        rnd(0.4, 0.6), 10, '#d8dfe8', 0, 2, 2).layer = 0;
    }
  }
}

// 근접 · 돌진: 준비 동안 몸 둘레로 빨려 드는 바람, 달리면 몸을 감싸는 흐름선 · 바람 길, 앞은 바람 칼 (swing)
function windRush(fx, ctx, a) {
  const { c } = a, t = fx.clock, s = a.seed, m = motif(a.ty);
  ctx.globalCompositeOperation = 'lighter';
  if (a.stage === 'wind') {
    const k = a.sk;
    for (let arm = 0; arm < 2; arm++) {
      spiralPts(a.x, a.y, a.ang, BODY_R * (2.4 - k), BODY_R * 0.8, -t * 16 + s + arm * Math.PI, 0.7, 0.75, 3 + 4 * k, 14);
      glowBand(ctx, 14, c.light, 0.12 + 0.2 * k, WHITE, 0.25 + 0.5 * k);
    }
    streak(fx, ctx, WHITE, a.x + a.ux * a.reach * 0.8, a.y + a.uy * a.reach * 0.8, a.ang, a.reach * (0.3 + 0.4 * k), 6 + 6 * k, 0.15 + 0.3 * k);
    return;
  }
  const fade = a.stage === 'tail' ? 1 - a.sk : 1, now = t;
  ribbon(ctx, a.trail, now, 0.26, a.reach * 2, a.reach * 0.5, c.dark, 0.1 * fade);     // 맞는 폭 (옅게)
  ribbon(ctx, a.trail, now, 0.2, BODY_R * 1.4, 4, c.light, 0.18 * fade);
  const L = Math.min(a.moved + BODY_R, 210), R = BODY_R * 1.05, M = 12;
  for (let i = 0; i < 4; i++) {                 // 몸을 감싸고 뒤로 흐르는 가닥
    const ph0 = s + (i * TAU) / 4 - t * 14;
    for (let j = 0; j < M; j++) {
      const k = j / (M - 1), ph = ph0 + k * (3.4 + i * 0.9), env = R * (0.95 + 0.8 * k) + (noise1(k * 3 - t * 4 + i * 7) - 0.5) * R * 0.6 * k;
      const al = BODY_R * 0.9 - k * L, o = env * Math.sin(ph);
      PX[j] = a.x + a.ux * al - a.uy * o;
      PY[j] = a.y + a.uy * al + a.ux * o - env * Math.cos(ph) * H3 * 0.6;
      PW[j] = 7 * spindle(k, 0.2) * (0.5 + 0.5 * Math.cos(ph));
    }
    glowBand(ctx, M, c.light, 0.2 * fade, WHITE, 0.65 * fade);
  }
  crescent(ctx, a.x - a.ux * BODY_R * 0.2, a.y - a.uy * BODY_R * 0.2, BODY_R * 1.45, a.ang - 1.2, a.ang + 1.2, BODY_R * 0.3);
  fillPath(ctx, WHITE, 0.4 * fade);
  if (a.stage === 'act') {
    const n = fx.perSec(40);
    for (let i = 0; i < n; i++) {
      const sd = Math.random() < 0.5 ? -1 : 1, v = rnd(90, 220);
      mote(fx, m, c, a.x - a.uy * sd * BODY_R, a.y + a.ux * sd * BODY_R, -a.uy * sd * v - a.ux * 60, a.ux * sd * v - a.uy * 60);
    }
  }
}

function windSwing(fx, ctx, a, t) {
  const { c } = a, R = a.reach, fade = t > 0.55 ? (1 - t) / 0.45 : 1, tt = fx.clock;
  ctx.globalCompositeOperation = 'lighter';
  if (a.mk === 'dash') {                        // 앞으로 뚫는 바람 송곳 (회전하는 나선 둘)
    const L = R * (0.6 + 0.6 * easeOut(Math.min(1, t * 2))), x0 = a.x + a.ux * BODY_R * 0.6, y0 = a.y + a.uy * BODY_R * 0.6;
    for (let i = 0; i < 2; i++) {
      for (let j = 0; j < 14; j++) {
        const k = j / 13, th = k * 9 - tt * 30 + i * Math.PI, rad = BODY_R * 1.1 * (1 - k), al = k * L;
        PX[j] = x0 + a.ux * al - a.uy * Math.sin(th) * rad;
        PY[j] = y0 + a.uy * al + a.ux * Math.sin(th) * rad - Math.cos(th) * rad * H3;
        PW[j] = 3.5 * (1 - k) * (0.5 + 0.5 * Math.cos(th)) + 0.5;
      }
      glowBand(ctx, 14, c.light, 0.2 * fade, WHITE, (i ? 0.5 : 0.8) * fade, 2.8);
    }
    streak(fx, ctx, c.light, x0 + a.ux * L * 0.45, y0 + a.uy * L * 0.45, a.ang, L * 0.55, BODY_R * 0.7, 0.35 * fade);
    fx.ink.star(ctx, WHITE, x0 + a.ux * L, y0 + a.uy * L, 14, fade);
    return;
  }
  const span = 1.25, e = easeOut(Math.min(1, t * 1.7)), a0 = a.ang - span, a1 = a0 + 2 * span * e, from = Math.max(a0, a1 - span * 1.2);
  for (let i = 0; i < 3; i++) {                 // 바람 칼 - 세 겹 흐름선 호 (앞 끝이 굵다)
    const rr = R * (0.82 + 0.12 * i), n = 14;
    for (let j = 0; j < n; j++) {
      const k = j / (n - 1), th = from + (a1 - from) * k, wob = Math.sin(k * 7 + tt * 30 + i) * 3;
      PX[j] = a.x + Math.cos(th) * (rr + wob);
      PY[j] = a.y + Math.sin(th) * (rr + wob);
      PW[j] = (i === 1 ? 11 : 6) * Math.pow(k, 1.5);
    }
    glowBand(ctx, n, c.light, 0.25 * fade, WHITE, (i === 1 ? 0.9 : 0.5) * fade);
  }
  fx.ink.star(ctx, WHITE, a.x + Math.cos(a1) * R * 0.94, a.y + Math.sin(a1) * R * 0.94, 16, fade);
  if (!a.mem.cut && t > 0.25) {                 // 칼끝에서 실린 것이 접선으로 튄다
    a.mem.cut = true;
    const m = motif(a.ty);
    for (let i = 0; i < 12; i++) {
      const th = a0 + 2 * span * rnd(0.2, 1), v = rnd(180, 360);
      mote(fx, m, c, a.x + Math.cos(th) * R, a.y + Math.sin(th) * R, -Math.sin(th) * v + Math.cos(th) * 80, Math.cos(th) * v + Math.sin(th) * 80);
    }
  }
}

// ================================================================ sound
// 음표 (머리 + 기둥 + 꼬리, two 면 둘을 잇는 꼴). s 는 머리 반지름. 어두운 그림자를 깔아 어느 바닥에서도 보인다
function note(ctx, x, y, s, col, a, two) {
  if (!(a > 0.02) || !(s > 0.3)) return;
  ctx.globalCompositeOperation = 'source-over';
  for (let pass = 0; pass < 2; pass++) {
    const ox = pass ? 0 : 1.2, oy = pass ? 0 : 1.5, c = pass ? col : INK, al = pass ? a : a * 0.35;
    const sx = x + ox + s * 0.95, top = y + oy - s * 3.4;
    ctx.globalAlpha = A(al);
    ctx.fillStyle = c;
    for (let h = 0; h <= (two ? 1 : 0); h++) {
      ctx.beginPath();
      ctx.ellipse(x + ox + s * 2.6 * h, y + oy + s * 0.5 * h, s * 1.15, s * 0.8, -0.45, 0, TAU);
      ctx.fill();
    }
    ctx.beginPath();
    ctx.moveTo(sx, y + oy - s * 0.2);
    ctx.lineTo(sx, top);
    if (two) {
      ctx.lineTo(sx + s * 2.6, top + s * 0.5);
      ctx.lineTo(sx + s * 2.6, y + oy + s * 0.3);
    } else ctx.quadraticCurveTo(sx + s * 1.8, top + s * 1.1, sx + s * 1.3, top + s * 2.3);
    strokePath(ctx, c, s * (two ? 0.5 : 0.4), al);
  }
}

/** 음표처럼 떠오르는 입자 둘 (기둥 = 위로 가는 spark, 머리 = 그 밑의 빛) - 같은 빠르기라 같이 간다. */
function noteDot(fx, x, y, col, k = 1) {
  const vx = rnd(-25, 25), vy = -rnd(50, 90), life = rnd(0.5, 0.8), s = 13 * k;
  const stem = fx.spawn('spark', x, y, vx, vy, life, s, col);
  stem.w = 1.6 * k;
  stem.size1 = s;
  const head = fx.spawn('core', x - 2.6 * k, y + s * 0.6, vx, vy, life, 4.2 * k, col);
  head.size1 = head.size;
}

function soundShot(fx, ctx, q) {
  const { x, y, ux, uy, c } = q, R = sizeOf(q), t = fx.clock, s = q.seed, base = hash(s);
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.glow(ctx, c.dark, x, y, R * 2.4, 0.35);
  ribbon(ctx, q.trail, t, 0.14, R * 2.4, R * 0.6, c.dark, 0.14);
  // 소리 앞머리 넷 ")))" - 울림통에서 태어나 앞으로 나가며 커지고 떨다가 사라진다
  for (let i = 0; i < 4; i++) {
    const ph = (t * 2.4 + i / 4 + base) % 1, rad = R * (1.0 + 1.8 * ph), span = 0.62 + 0.2 * ph, back = R * (1.3 - ph);
    const al = Math.pow(1 - ph, 0.5) * Math.min(1, ph * 6);
    arcPts(x - ux * back, y - uy * back, rad, q.ang - span, q.ang + span, 14, R * 0.045 * (0.5 + ph), 2.5, t * 40 + i, R * 0.5 * (1 - ph * 0.35));
    glowBand(ctx, 14, c.light, 0.22 * al, WHITE, 0.9 * al, 2.2);
  }
  const pulse = 0.5 + 0.5 * Math.sin(t * 30 + s);  // 울림통
  fx.ink.core(ctx, c.light, x, y, R * (0.75 + 0.18 * pulse), 0.85);
  ring(ctx, c.light, 0.55, 1.5, x, y, R * (0.9 + 0.3 * pulse));
  for (let i = 0; i < 2; i++) {                 // 따라 도는 음표
    const a = t * 4 + s + i * Math.PI;
    note(ctx, x - ux * R * 1.2 + Math.cos(a) * R * 1.2, y - uy * R * 1.2 + Math.sin(a) * R * 1.4 - R * 0.3, R * 0.36, c.light, 0.9, (i + (s & 1)) & 1);
  }
}

function soundTrail(fx, q) {
  const R = sizeOf(q), n = fx.perSec(16);
  for (let i = 0; i < n; i++) {
    const back = rnd(R, R * 3), x = q.x - q.ux * back + rnd(-R, R) * 0.6, y = q.y - q.uy * back + rnd(-R, R) * 0.6, r = Math.random();
    if (r < 0.4) {                              // 물결 고리
      const p = dot(fx, 'ring', x, y, 0, 0, rnd(0.2, 0.32), R * 0.35, q.c.light, 0, 0, 3);
      p.w = 1.2;
    } else if (r < 0.75) dot(fx, 'star', x, y, rnd(-30, 30), rnd(-50, 0), rnd(0.25, 0.4), rnd(5, 8), q.c.light, 0, 2, 0.3);
    else noteDot(fx, x, y, Math.random() < 0.5 ? q.c.light : WHITE, 0.9);
  }
}

function soundLaunch(fx, q) {
  const R = sizeOf(q);
  fx.wave(q.x, q.y, WHITE, R * 3, 0.22, 3);
  fx.wave(q.x, q.y, q.c.light, R * 4.5, 0.32, 2);
  for (let i = 0; i < 3; i++) noteDot(fx, q.x + rnd(-R, R), q.y - R * 0.5, q.c.light);
}

function soundImpact(fx, x, y, ang, c, info) {
  const s = info.s || 1, k = info.why === 'hit' ? s : 1.4;
  fx.wave(x, y, WHITE, 55 * k, 0.25, 4);         // 같이 시작해 다른 빠르기로 - 물결 셋
  fx.wave(x, y, c.light, 95 * k, 0.4, 3);
  fx.wave(x, y, c.dark, 140 * k, 0.55, 2);
  for (let i = 0; i < 4 * k; i++) noteDot(fx, x + rnd(-30, 30), y + rnd(-25, 10), i % 2 ? WHITE : c.light, 1.1);
  for (let i = 0; i < 8 * k; i++) {
    const a = rnd(0, TAU), v = rnd(120, 260);
    dot(fx, 'star', x, y, Math.cos(a) * v, Math.sin(a) * v, rnd(0.25, 0.4), rnd(7, 11), c.light, 0, 4, 0.3);
  }
}

// 떨리는 소리 벽 (a0 → a1 호) - 넓고 옅은 빛 + 흰 심
function soundFront(ctx, x, y, R, a0, a1, a, c, t, i, n = 30) {
  const full = a1 - a0 > TAU - 0.01, w = 6 + R * 0.035;
  arcPts(x, y, R, a0, a1, n, 1.2 + R * 0.008, full ? 32 : (a1 - a0) * 5, t * 60 + i * 2, w);
  if (full) evenW(n, w * 0.8);                // 고리는 이음매 없이 고른 굵기
  glowBand(ctx, n, c.light, 0.25 * a, WHITE, 0.75 * a, 2.6);
}

function soundCone(fx, ctx, q) {
  const t = fx.clock, { x, y, ang, len, h, c } = q;
  ctx.globalCompositeOperation = 'lighter';
  if (q.phase === 'mark') {                     // 입 앞에서 웅웅 떤다
    for (let i = 0; i < 2; i++) {
      const ph = (t * 2.5 + i * 0.5) % 1;
      soundFront(ctx, x, y, BODY_R * (1.1 + 1.6 * ph), ang - h, ang + h, (0.2 + 0.5 * q.u) * (1 - ph), c, t, i, 12);
    }
    return;
  }
  const f = fireK(q), fade = 1 - f * f;
  if (!q.mem.go) {
    q.mem.go = true;
    for (let i = 0; i < 7; i++) {
      const a = ang + rnd(-h, h) * 0.9, d = len * rnd(0.2, 0.9);
      noteDot(fx, x + Math.cos(a) * d, y + Math.sin(a) * d, i % 2 ? WHITE : c.light, 1.2);
    }
    for (let i = 0; i < 12; i++) {
      const a = ang + rnd(-h, h), v = rnd(500, 800);
      streakDot(fx, x + Math.cos(a) * 30, y + Math.sin(a) * 30, Math.cos(a) * v, Math.sin(a) * v, rnd(0.25, 0.4), 24, c.light, 2.5, 2);
    }
  }
  for (let i = 0; i < 4; i++) {                 // 퍼지는 소리 벽 넷
    const k = clamp01(f * 1.35 - i * 0.12), R = len * easeOut(k);
    if (k <= 0 || k >= 1) continue;
    soundFront(ctx, x, y, R, ang - h, ang + h, (1 - k * 0.7) * fade, c, t, i);
  }
  fx.ink.core(ctx, c.light, x, y, BODY_R * 1.4 * fade, 0.8 * fade);
  for (let i = 0; i < 6; i++) {                 // 벽에 실려 나가는 음표
    const a = ang + (hash(q.seed + i * 3.3) - 0.5) * 1.6 * h, d = len * (0.15 + 0.8 * easeOut(clamp01(f * 1.2 - hash(q.seed + i) * 0.2)));
    note(ctx, x + Math.cos(a) * d, y + Math.sin(a) * d - 10, 4 + 2 * hash(q.seed + i + 1), i % 2 ? WHITE : c.light, fade, i % 3 === 0);
  }
}

function soundRing(fx, ctx, q) {
  const t = fx.clock, { x, y, c } = q;
  ctx.globalCompositeOperation = 'lighter';
  if (q.phase === 'mark') {
    for (let i = 0; i < 2; i++) {
      const ph = (t * 2.5 + i * 0.5) % 1;
      soundFront(ctx, x, y, BODY_R * (1.1 + 1.4 * ph), 0, TAU, (0.15 + 0.4 * q.u) * (1 - ph), c, t, i, 24);
    }
    return;
  }
  const f = fireK(q), fade = 1 - f * f;
  if (!q.mem.go) {
    q.mem.go = true;
    for (let i = 0; i < 8; i++) {
      const a = rnd(0, TAU), d = q.r * rnd(0.3, 0.8);
      noteDot(fx, x + Math.cos(a) * d, y + Math.sin(a) * d, i % 2 ? WHITE : c.light, 1.2);
    }
  }
  fx.ink.glow(ctx, c.dark, x, y, q.r * easeOut(f), 0.35 * fade);
  for (let i = 0; i < 3; i++) {
    const k = clamp01(f * 1.3 - i * 0.15), R = q.r * easeOut(k);
    if (k <= 0 || k >= 1) continue;
    soundFront(ctx, x, y, R, 0, TAU, (1 - k * 0.7) * fade, c, t, i, NMAX);
  }
}

// ================================================================ jet
function jetShot(fx, ctx, q) {
  const { x, y, ux, uy, c } = q, R = sizeOf(q), t = fx.clock, s = q.seed, px = -uy, py = ux;
  const L = R * 5.2, M = 15, hx = x + ux * R * 0.25, hy = y + uy * R * 0.25, cap = R * 0.9;
  const lx = px * -0.6 + py * -0.8 > 0 ? 1 : -1;  // 빛 받는 쪽 (윤기 줄이 그쪽에)
  ctx.globalCompositeOperation = 'lighter';
  streak(fx, ctx, c.dark, x - ux * L * 0.4, y - uy * L * 0.4, q.ang, L * 0.65, R * 1.4, 0.35);
  // 물줄기 몸 - 눌린 물이 맥박치며 뒤로 가늘어지고, 가장자리가 출렁인다. 머리는 둥근 물 앞머리
  for (let j = 0; j < M; j++) {
    const k = Math.pow(j / (M - 1), 1.7), d = k * L, al = R * 0.95 - d, o = Math.sin(k * 9 - t * 40 + s) * R * 0.12 * k;
    PX[j] = x + ux * al + px * o;
    PY[j] = y + uy * al + py * o;
    const head = d < cap ? Math.sqrt(Math.max(0, 1 - Math.pow((cap - d) / cap, 2))) : 1;   // 앞이 둥글다 (앞쪽 점이 촘촘)
    PW[j] = R * 1.8 * head * Math.pow(1 - k, 0.75) * (1 + 0.14 * Math.sin(k * 14 - t * 50 + s)) + 0.3;
  }
  ctx.globalCompositeOperation = 'source-over';
  band(ctx, M, 1);
  fillPath(ctx, c.dark, 0.8);
  band(ctx, M, 0.62);
  fillPath(ctx, c.light, 0.82);
  ctx.globalCompositeOperation = 'lighter';
  band(ctx, M, 1.12);                           // 물 가장자리의 빛 (굴절 테)
  fillPath(ctx, c.light, 0.14);
  fx.ink.glow(ctx, c.light, hx, hy, R * 2, 0.35);
  // 흐르는 결 - 몸 안에서 뒤로 흘러가는 흰 줄 둘
  for (let side = -1; side <= 1; side += 2) {
    ctx.beginPath();
    for (let d = 0; d < 3; d++) {
      const k0 = ((t * 3.5 + d / 3 + side * 0.17 + hash(s)) % 1) * 0.75 + 0.08, k1 = k0 + 0.12;
      const w0 = R * 0.9 * Math.pow(1 - k0, 0.75) * 0.3 * side, w1 = R * 0.9 * Math.pow(1 - k1, 0.75) * 0.3 * side;
      const a0 = R * 0.95 - k0 * L, a1 = R * 0.95 - k1 * L;
      ctx.moveTo(x + ux * a0 + px * w0, y + uy * a0 + py * w0);
      ctx.lineTo(x + ux * a1 + px * w1, y + uy * a1 + py * w1);
    }
    strokePath(ctx, WHITE, Math.max(1, R * 0.1), 0.55);
  }
  for (let j = 0; j < M; j++) {                 // 윤기 줄 - 빛 받는 쪽으로 비켜서
    PX[j] += px * lx * PW[j] * 0.22;
    PY[j] += py * lx * PW[j] * 0.22;
    PW[j] *= 0.16;
  }
  band(ctx, M, 1);
  fillPath(ctx, WHITE, 0.8);
  ctx.beginPath();                              // 앞머리 반짝임
  ctx.ellipse(hx + ux * R * 0.25 + px * lx * R * 0.35, hy + uy * R * 0.25 + py * lx * R * 0.35, R * 0.3, R * 0.16, q.ang, 0, TAU);
  fillPath(ctx, WHITE, 0.9);
  // 꼬리에서 부서지는 물방울
  for (let i = 0; i < 8; i++) {
    const ph = (t * 3 + i / 8 + hash(s + i)) % 1, al = R * 0.2 - L * (0.6 + 0.55 * ph), o = (hash(s + i * 7) - 0.5) * R * 1.8 * (0.3 + ph);
    const dx = x + ux * al + px * o, dy = y + uy * al + py * o, dr = R * (0.12 + 0.12 * hash(s + i * 3)) * (1 - ph * 0.6);
    ctx.globalCompositeOperation = 'source-over';
    circle(ctx, dx, dy, dr);
    fillPath(ctx, c.light, 0.9 * (1 - ph));
    ctx.globalCompositeOperation = 'lighter';
    circle(ctx, dx - dr * 0.3, dy - dr * 0.3, dr * 0.35);
    fillPath(ctx, WHITE, 0.8 * (1 - ph));
  }
}

function jetTrail(fx, q) {
  const R = sizeOf(q), n = fx.perSec(34), px = -q.uy, py = q.ux;
  for (let i = 0; i < n; i++) {
    const back = rnd(R * 0.5, R * 4.5), sd = rnd(-1, 1), x = q.x - q.ux * back + px * sd * R * 0.7, y = q.y - q.uy * back + py * sd * R * 0.7;
    const r = Math.random(), f = rnd(0.2, 0.45), fl = sd * rnd(40, 120);
    if (r < 0.6) {                              // 물방울
      dot(fx, 'glow', x, y, q.ux * q.speed * f + px * fl, q.uy * q.speed * f + py * fl - rnd(20, 80), rnd(0.3, 0.5), rnd(2.5, 4.5),
        r < 0.45 ? q.c.light : WHITE, 520, 1, 0.6);
    } else if (r < 0.85) {                      // 물보라
      dot(fx, 'smoke', x, y, px * fl * 0.5, py * fl * 0.5 - 10, rnd(0.25, 0.45), rnd(5, 9), MIST, 0, 3, 2).layer = 0;
    } else dot(fx, 'bubble', x, y, px * fl * 0.3, -rnd(20, 50), rnd(0.3, 0.5), rnd(2, 3.5), q.c.light, 0, 1, 1.2);
  }
}

function jetLaunch(fx, q) {
  const R = sizeOf(q);
  fx.wave(q.x, q.y, q.c.light, R * 3, 0.25, 3);
  for (let i = 0; i < 12; i++) {
    const a = q.ang + rnd(-0.6, 0.6), v = rnd(200, 420);
    dot(fx, 'glow', q.x, q.y, Math.cos(a) * v, Math.sin(a) * v - 60, rnd(0.25, 0.4), rnd(3, 5), i % 3 ? q.c.light : WHITE, 700, 1.5, 0.6);
  }
  foam(fx, q.x, q.y, 3, R, 60);
}

function jetImpact(fx, x, y, ang, c, info) {
  const s = info.s || 1, k = info.why === 'hit' ? s : info.why === 'tele' ? Math.max(1.3, info.r / 55) : 1.3;
  crown(fx, x, y, k, c);
  foam(fx, x, y, Math.round(5 * k), 20 * k, 70 * k);
  for (let i = 0; i < 8 * k; i++) {             // 맞은 쪽으로 튀어 나가는 물보라
    const a = ang + rnd(-0.9, 0.9), v = rnd(200, 420);
    dot(fx, 'glow', x, y, Math.cos(a) * v, Math.sin(a) * v - 80, rnd(0.3, 0.5), rnd(2.5, 4), c.light, 650, 1.2, 0.6);
  }
}

// 물줄기 하나 (x, y 에서 ang 쪽으로 L, 굵기 w) - 몸 · 밝은 속 · 윤기 줄
function stream(ctx, x, y, ang, L, w, c, a, t, seed) {
  const M = 10, ca = Math.cos(ang), sa = Math.sin(ang);
  for (let j = 0; j < M; j++) {
    const k = j / (M - 1), d = L * k, o = Math.sin(k * 6 - t * 30 + seed) * w * 0.25 * k;
    PX[j] = x + ca * d - sa * o;
    PY[j] = y + sa * d + ca * o;
    PW[j] = w * (0.35 + 0.65 * Math.sin(Math.PI * Math.min(1, 0.15 + k))) * (1 + 0.15 * Math.sin(k * 12 - t * 45 + seed));
  }
  ctx.globalCompositeOperation = 'source-over';
  band(ctx, M, 1);
  fillPath(ctx, c.dark, 0.75 * a);
  band(ctx, M, 0.55);
  fillPath(ctx, c.light, 0.8 * a);
  ctx.globalCompositeOperation = 'lighter';
  band(ctx, M, 0.15);
  fillPath(ctx, WHITE, 0.7 * a);
}

function jetCone(fx, ctx, q) {
  const t = fx.clock, { x, y, ang, len, h, c, seed } = q;
  if (q.phase === 'mark') {                     // 입 앞에 물이 모여 돈다
    ctx.globalCompositeOperation = 'lighter';
    spiralPts(x, y, ang, BODY_R * 1.4, BODY_R * 0.3, -t * 12 + seed, 1, 0.8, 4 + 5 * q.u, 14);
    glowBand(ctx, 14, c.light, 0.15 + 0.2 * q.u, WHITE, 0.3 + 0.4 * q.u);
    return;
  }
  const f = fireK(q), fade = 1 - f * f;
  if (!q.mem.go) {
    q.mem.go = true;
    for (let i = 0; i < 36; i++) {
      const a = ang + rnd(-h, h), v = rnd(350, 650), d = rnd(20, len * 0.5);
      dot(fx, i % 4 ? 'glow' : 'bubble', x + Math.cos(a) * d, y + Math.sin(a) * d, Math.cos(a) * v, Math.sin(a) * v - 60, rnd(0.35, 0.6),
        rnd(3, 5.5), i % 3 ? c.light : WHITE, 420, 1.6, 0.7);
    }
  }
  for (let i = 0; i < 7; i++) {
    const a = ang + (hash(seed + i * 2.7) - 0.5) * 1.8 * h, L = len * (0.15 + 0.85 * easeOut(clamp01(f * 1.3 - hash(seed + i) * 0.25)));
    stream(ctx, x, y, a, L, 12 + len * 0.03, c, fade, t, seed + i);
  }
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.core(ctx, c.light, x, y, BODY_R * 1.3, fade);
}

function jetRing(fx, ctx, q) {
  const t = fx.clock, { x, y, c, seed } = q;
  if (q.phase === 'mark') {                     // 발밑에서 물이 부글거린다
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 3; i++) {
      const ph = (t * 1.6 + i / 3) % 1;
      ring(ctx, c.light, (0.15 + 0.35 * q.u) * (1 - ph), 2, x, y, q.r * 0.6 * q.u * ph + 4);
    }
    return;
  }
  const f = fireK(q), fade = 1 - f * f, R = q.r * easeOut(Math.min(1, f * 1.2));
  if (!q.mem.go) {
    q.mem.go = true;
    for (let i = 0; i < 40; i++) {
      const a = rnd(0, TAU), v = rnd(250, 480);
      dot(fx, 'glow', x + Math.cos(a) * q.r * 0.3, y + Math.sin(a) * q.r * 0.3, Math.cos(a) * v, Math.sin(a) * v - rnd(60, 200), rnd(0.4, 0.65),
        rnd(3, 5.5), i % 3 ? c.light : WHITE, 700, 1.2, 0.7);
    }
    crown(fx, x, y, 1.4, c);
  }
  const n = 9, M = 12, w0 = 13 + q.r * 0.05;
  for (let i = 0; i < n; i++) {                 // 분수 - 가운데서 솟아 고리 위로 떨어지는 물줄기 (3/4 시점의 포물선)
    const th = seed + (i * TAU) / n + (hash(seed + i) - 0.5) * 0.5, Ri = R * (0.8 + 0.2 * hash(seed + i * 3));
    const H = q.r * (0.35 + 0.25 * hash(seed + i * 5)) * (1 - 0.3 * f), ex = Math.cos(th) * Ri, ey = Math.sin(th) * Ri;
    for (let j = 0; j < M; j++) {
      const k = j / (M - 1);
      PX[j] = x + ex * k + Math.sin(k * 7 - t * 30 + i) * 1.5;
      PY[j] = y + ey * k - H * 4 * k * (1 - k);
      PW[j] = w0 * (1 - 0.65 * k) * (1 + 0.15 * Math.sin(k * 11 - t * 40 + i));
    }
    ctx.globalCompositeOperation = 'source-over';
    band(ctx, M, 1);
    fillPath(ctx, c.dark, 0.7 * fade);
    band(ctx, M, 0.55);
    fillPath(ctx, c.light, 0.8 * fade);
    ctx.globalCompositeOperation = 'lighter';
    band(ctx, M, 0.16);
    fillPath(ctx, WHITE, 0.75 * fade);
    fx.ink.glow(ctx, WHITE, x + ex, y + ey, 10 + 6 * hash(seed + i), 0.7 * fade);   // 떨어진 자리 물보라
  }
  fx.ink.glow(ctx, c.light, x, y - q.r * 0.15, q.r * 0.35, 0.6 * fade);
  ctx.globalCompositeOperation = 'lighter';
  arcPts(x, y, R, 0, TAU, 40, 3, 9, t * 8 + seed, 1);
  poly(ctx, 40);
  ctx.closePath();
  strokePath(ctx, WHITE, 2.5, 0.65 * fade);
  const m = fx.perSec(160 * fade);              // 고리에서 튀는 물방울
  for (let i = 0; i < m; i++) {
    const a = rnd(0, TAU), v = rnd(80, 200);
    dot(fx, 'core', x + Math.cos(a) * R, y + Math.sin(a) * R, Math.cos(a) * v, Math.sin(a) * v * 0.6 - rnd(120, 260), rnd(0.35, 0.5),
      rnd(3, 4.5), Math.random() < 0.6 ? c.light : WHITE, 900, 0.6, 0.7);
  }
}

// 물기둥 솟음 (내려찍기): 표시 동안 바닥이 부글거리고, 떨어질 무렵 물이 부풀고, 터지면 솟는다
function jetTele(fx, ctx, q) {
  const t = fx.clock, { x, y, c } = q;
  ctx.globalCompositeOperation = 'lighter';
  if (q.phase === 'mark') {
    for (let i = 0; i < 3; i++) {
      const ph = (t * (1.2 + q.u) + i / 3) % 1;
      ring(ctx, c.light, (0.15 + 0.4 * q.u) * (1 - ph), 2, x, y, q.r * (0.15 + 0.75 * ph) * (0.4 + 0.6 * q.u));
    }
    for (let i = 0; i < 6; i++) {                // 오르는 거품
      const ph = (t * 1.5 + hash(q.seed + i)) % 1, a = hash(q.seed + i * 3) * TAU, d = q.r * 0.6 * hash(q.seed + i * 5);
      ring(ctx, WHITE, 0.7 * q.u * (1 - ph), 1.2, x + Math.cos(a) * d, y + Math.sin(a) * d * 0.6 - ph * 18, 2 + 3 * ph);
    }
    return;
  }
  const f = fireK(q), fade = 1 - f, H = FALL_H * 0.9 * easeOut(Math.min(1, f * 2.2)), w = q.r * (0.75 - 0.3 * f);
  if (!q.mem.go) {
    q.mem.go = true;
    for (let i = 0; i < 40; i++) {               // 솟았다가 비처럼 떨어지는 물
      const a = rnd(-0.5, 0.5) - Math.PI / 2, v = rnd(500, 900);
      dot(fx, 'core', x + rnd(-w, w) * 0.6, y, Math.cos(a) * v * 0.6, Math.sin(a) * v, rnd(0.7, 1.1), rnd(3.5, 6), i % 3 ? c.light : WHITE, 1200, 0.4, 0.7);
    }
    foam(fx, x, y, 8, q.r * 0.6, 120);
  }
  for (let j = 0; j < 10; j++) {                // 물기둥 - 위로 갈수록 가늘고 꼭대기가 부서진다
    const k = j / 9;
    PX[j] = x + Math.sin(k * 5 + t * 20) * w * 0.12;
    PY[j] = y - H * k;
    PW[j] = w * 2 * (1 - 0.55 * k) * (1 + 0.12 * Math.sin(k * 11 - t * 40));
  }
  ctx.globalCompositeOperation = 'source-over';
  band(ctx, 10, 1);
  fillPath(ctx, c.dark, 0.7 * fade);
  band(ctx, 10, 0.6);
  fillPath(ctx, c.light, 0.85 * fade);
  ctx.globalCompositeOperation = 'lighter';
  band(ctx, 10, 0.18);
  fillPath(ctx, WHITE, 0.8 * fade);
  fx.ink.glow(ctx, c.light, x, y - H, w * 1.6, 0.6 * fade);
  ctx.globalCompositeOperation = 'source-over';
  for (let i = 0; i < 7; i++) {                 // 꼭대기에서 부서지는 물보라 (거품 덩이가 벌어진다)
    const a = -Math.PI / 2 + (i - 3) * 0.45, d = w * (0.4 + 0.9 * f) * (0.7 + 0.3 * hash(q.seed + i));
    circle(ctx, x + Math.cos(a) * d, y - H + Math.sin(a) * d * 0.6 + 4, w * (0.28 + 0.12 * Math.sin(t * 20 + i)) * (1 - 0.4 * f));
    fillPath(ctx, i % 2 ? FOAM : c.light, 0.85 * fade);
  }
  ctx.globalCompositeOperation = 'lighter';
  ring(ctx, WHITE, 0.7 * fade, 3, x, y, q.r * (0.5 + 0.6 * f));
}

function jetFall(fx, ctx, q, x, y, v) {            // 떨어지는 것이 없다 - 바닥이 부풀어 오른다
  const { c } = q, r = q.r * (0.25 + 0.35 * v);
  ctx.globalCompositeOperation = 'source-over';
  ctx.beginPath();
  ctx.ellipse(q.x, q.y - r * 0.3 * v, r, r * (0.35 + 0.35 * v), 0, Math.PI, TAU);
  fillPath(ctx, c.dark, 0.5 + 0.3 * v);
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.glow(ctx, c.light, q.x, q.y - r * 0.3, r * 1.4, 0.3 + 0.4 * v);
  const n = fx.perSec(30 * v);
  for (let i = 0; i < n; i++) {
    dot(fx, 'glow', q.x + rnd(-r, r), q.y, rnd(-40, 40), -rnd(120, 260), rnd(0.3, 0.45), rnd(2.5, 4), c.light, 900, 0.5, 0.6);
  }
}

function jetRush(fx, ctx, a) {
  const { c } = a, t = fx.clock;
  if (a.stage === 'wind') {                     // 몸 둘레로 물이 감아 오른다
    ctx.globalCompositeOperation = 'lighter';
    const k = a.sk;
    for (let i = 0; i < 2; i++) {
      for (let j = 0; j < 16; j++) {
        const kk = j / 15, th = kk * TAU * 0.8 - t * 14 + i * Math.PI;
        PX[j] = a.x + Math.cos(th) * BODY_R * 1.3;
        PY[j] = a.y + BODY_R * 0.4 + Math.sin(th) * BODY_R * 0.45 - kk * BODY_R * 1.4 * k;
        PW[j] = (2 + 5 * k) * Math.sin(Math.PI * kk);
      }
      glowBand(ctx, 16, c.light, 0.2, WHITE, 0.4 + 0.4 * k);
    }
    return;
  }
  const fade = a.stage === 'tail' ? 1 - a.sk : 1;
  ctx.globalCompositeOperation = 'source-over';
  ribbon(ctx, a.trail, t, 0.26, a.reach * 2, a.reach * 0.6, c.dark, 0.14 * fade);  // 맞는 폭 - 물길 (옅게)
  ribbon(ctx, a.trail, t, 0.25, BODY_R * 2.2, 6, c.light, 0.45 * fade);
  ctx.globalCompositeOperation = 'lighter';
  ribbon(ctx, a.trail, t, 0.18, BODY_R * 0.6, 2, WHITE, 0.6 * fade);
  for (let sd = -1; sd <= 1; sd += 2) {         // 앞에서 갈라지는 물 (뱃머리 물결)
    for (let j = 0; j < 10; j++) {
      const k = j / 9, al = BODY_R * 1.1 - k * BODY_R * 3.5, o = sd * (BODY_R * 0.9 + k * BODY_R * 1.4 + Math.sin(k * 8 - t * 40) * 3);
      PX[j] = a.x + a.ux * al - a.uy * o;
      PY[j] = a.y + a.uy * al + a.ux * o;
      PW[j] = 8 * spindle(k, 0.25);
    }
    glowBand(ctx, 10, c.light, 0.3 * fade, WHITE, 0.8 * fade);
  }
  if (a.stage === 'act') {
    const n = fx.perSec(70);
    for (let i = 0; i < n; i++) {
      const sd = Math.random() < 0.5 ? -1 : 1, v = rnd(120, 260);
      dot(fx, 'glow', a.x - a.uy * sd * BODY_R, a.y + a.ux * sd * BODY_R, -a.uy * sd * v - a.ux * 50, a.ux * sd * v - a.uy * 50 - rnd(60, 160),
        rnd(0.3, 0.5), rnd(2.5, 4.5), Math.random() < 0.7 ? c.light : WHITE, 800, 1, 0.6);
    }
  }
}

function jetSwing(fx, ctx, a, t) {                 // 물 호 - 몸은 물빛, 앞 가장자리는 흰 거품, 물방울이 흩어진다
  const R = a.reach, span = a.mk === 'dash' ? 0.75 : 1.25, fade = t > 0.55 ? (1 - t) / 0.45 : 1, tt = fx.clock;
  const e = easeOut(Math.min(1, t * 1.7)), a0 = a.ang - span, a1 = a0 + 2 * span * e, from = Math.max(a0, a1 - span * 1.15);
  ctx.globalCompositeOperation = 'source-over';
  crescent(ctx, a.x, a.y, R, from, a1, R * 0.32);
  fillPath(ctx, a.c.dark, 0.7 * fade);
  crescent(ctx, a.x, a.y, R * 0.97, from, a1, R * 0.2);
  fillPath(ctx, a.c.light, 0.85 * fade);
  ctx.globalCompositeOperation = 'lighter';
  arcPts(a.x, a.y, R * 0.99, from + (a1 - from) * 0.15, a1, 14, 2.5, 5, tt * 30, 5);
  glowBand(ctx, 14, a.c.light, 0.3 * fade, WHITE, 0.9 * fade, 2);
  if (!a.mem.cut && t > 0.2) {
    a.mem.cut = true;
    for (let i = 0; i < 22; i++) {
      const th = a0 + 2 * span * rnd(0.15, 1), v = rnd(160, 340), x = a.x + Math.cos(th) * R, y = a.y + Math.sin(th) * R;
      dot(fx, 'glow', x, y, -Math.sin(th) * v + Math.cos(th) * 90, Math.cos(th) * v + Math.sin(th) * 90 - 120, rnd(0.35, 0.55), rnd(3, 5),
        i % 3 ? a.c.light : WHITE, 800, 1, 0.6);
    }
    foam(fx, a.x + Math.cos(a.ang) * R, a.y + Math.sin(a.ang) * R, 3, 16, 60);
  }
}

// ================================================================ wave
// 물마루 하나 (cx, cy 가운데 반지름 R 의 a0 → a1) - 물빛 띠 · 흰 거품 줄 · 거품 덩이 · 양 끝의 말림
function crest(fx, ctx, cx, cy, R, a0, a1, T, c, a, t, seed, n = 18) {
  if (!(R > 2) || !(a > 0.01)) return;
  const full = a1 - a0 > TAU - 0.01;
  arcPts(cx, cy, R - T * 0.35, a0, a1, n, T * (full ? 0.04 : 0.08), full ? 9 : 3, t * 6 + seed, T * 1.1);
  if (full) evenW(n, T * 1.1);
  ctx.globalCompositeOperation = 'source-over';
  band(ctx, n, 1);
  fillPath(ctx, c.dark, 0.7 * a);
  arcPts(cx, cy, R - T * 0.15, a0, a1, n, T * (full ? 0.04 : 0.08), full ? 9 : 3, t * 6 + seed, T * 0.7);
  if (full) evenW(n, T * 0.7);
  band(ctx, n, 1);
  fillPath(ctx, c.light, 0.8 * a);
  ctx.globalCompositeOperation = 'lighter';
  arcPts(cx, cy, R, a0, a1, n, T * 0.1, full ? 16 : (a1 - a0) * 2.2, t * 14 + seed, T * 0.35);   // 앞 거품 줄
  if (full) evenW(n, T * 0.3);
  band(ctx, n, 1);
  fillPath(ctx, WHITE, 0.85 * a);
  ctx.globalCompositeOperation = 'source-over';
  const m = Math.max(3, Math.round((a1 - a0) * R / 18));
  for (let i = 0; i < m; i++) {                 // 거품 덩이 (보글보글 커졌다 작아진다)
    const k = (i + 0.5) / m, th = a0 + (a1 - a0) * k, bob = 0.6 + 0.4 * Math.sin(t * 9 + i * 1.7 + seed);
    const r = T * 0.22 * bob * (full ? 1 : Math.sin(Math.PI * k)) + 0.5, rr = R + T * 0.05;
    circle(ctx, cx + Math.cos(th) * rr, cy + Math.sin(th) * rr, r);
    fillPath(ctx, FOAM, 0.85 * a);
  }
  ctx.globalCompositeOperation = 'lighter';
  // 말리는 입술 - 끝 (호면) 과 마루를 따라 몇 군데, 거품이 바깥으로 말려 넘어간다
  const curls = full ? Math.max(4, Math.round(R / 45)) : 2 + Math.round((a1 - a0) * R / 90);
  for (let i = 0; i < curls; i++) {
    const k = full ? (i + hash(seed + i) * 0.5) / curls : curls > 2 && i > 1 ? (i - 1.5) / (curls - 2) * 0.8 + 0.1 : i;
    const th = a0 + (a1 - a0) * k, ex = cx + Math.cos(th) * (R - T * 0.25), ey = cy + Math.sin(th) * (R - T * 0.25);
    const big = !full && i < 2 ? 0.55 : 0.4;
    spiralPts(ex, ey, th, T * big, T * 0.08, -t * 8 + seed + i * 3, 0.85, 1, T * 0.22, 10);
    glowBand(ctx, 10, c.light, 0.2 * a, WHITE, 0.75 * a, 2);
  }
}

// 물마루 뒤에 남는 거품 줄 (호 하나, 성기게 끊긴다)
function foamLine(ctx, cx, cy, R, a0, a1, a, t, seed, n = 16) {
  if (!(R > 2) || !(a > 0.01)) return;
  arcPts(cx, cy, R, a0, a1, n, 2.5, (a1 - a0) * 2, t * 4 + seed, 1);
  ctx.globalCompositeOperation = 'lighter';
  ctx.beginPath();
  for (let i = 0; i < n - 1; i++) {
    if (hash(seed + i * 1.3) < 0.35) continue;
    ctx.moveTo(PX[i], PY[i]);
    ctx.lineTo(PX[i + 1], PY[i + 1]);
  }
  strokePath(ctx, WHITE, 1.6, a);
}

function waveShot(fx, ctx, q) {
  const { x, y, ux, uy, c } = q, R = sizeOf(q), t = fx.clock, s = q.seed;
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.glow(ctx, c.dark, x - ux * R * 0.8, y - uy * R * 0.8, R * 2.6, 0.4);
  ribbon(ctx, q.trail, t, 0.16, R * 2.6, R * 0.8, c.dark, 0.14);
  for (let i = 0; i < 2; i++) {                 // 맥박 고리 (파동)
    const ph = (t * 2.4 + i * 0.5 + hash(s)) % 1;
    ring(ctx, c.light, 0.45 * (1 - ph), 1.5 + 2 * (1 - ph), x, y, R * (0.5 + 1.6 * ph));
  }
  const back = R * 1.6, cx = x - ux * back, cy = y - uy * back;  // 물마루 - 앞으로 볼록
  ctx.globalCompositeOperation = 'source-over';   // 마루 뒤의 물 덩이
  crescent(ctx, cx, cy, R * 2.0, q.ang - 1.0, q.ang + 1.0, R * 1.5);
  fillPath(ctx, c.dark, 0.35);
  crest(fx, ctx, cx, cy, R * 2.15, q.ang - 1.05, q.ang + 1.05, R * 1.15, c, 1, t, s, 16);
  foamLine(ctx, cx - ux * R * 0.4, cy - uy * R * 0.4, R * 1.5, q.ang - 0.8, q.ang + 0.8, 0.55, t, s, 12);
  foamLine(ctx, cx - ux * R * 1.1, cy - uy * R * 1.1, R * 1.2, q.ang - 0.7, q.ang + 0.7, 0.3, t, s + 5, 10);
  fx.ink.core(ctx, c.light, x - ux * R * 0.2, y - uy * R * 0.2, R * 0.7, 0.55);
}

function waveTrail(fx, q) {
  const R = sizeOf(q), n = fx.perSec(28), px = -q.uy, py = q.ux;
  for (let i = 0; i < n; i++) {
    const sd = Math.random() < 0.5 ? -1 : 1, r = Math.random();
    const x = q.x + q.ux * R * 0.2 + px * sd * R * 1.6, y = q.y + q.uy * R * 0.2 + py * sd * R * 1.6;
    if (r < 0.6) {                              // 물마루 끝에서 튀는 물보라
      const v = rnd(60, 160);
      dot(fx, 'glow', x, y, q.ux * q.speed * 0.4 + px * sd * v, q.uy * q.speed * 0.4 + py * sd * v - rnd(40, 120), rnd(0.3, 0.5), rnd(2.5, 4.5),
        r < 0.4 ? q.c.light : WHITE, 650, 1, 0.6);
    } else {                                    // 뒤에 남는 거품
      const b = rnd(R, R * 3), bx = q.x - q.ux * b + px * rnd(-R, R), by = q.y - q.uy * b + py * rnd(-R, R);
      if (r < 0.75) dot(fx, 'bubble', bx, by, 0, -15, rnd(0.3, 0.5), rnd(2, 3.5), WHITE, 0, 1, 1.3);
      else dot(fx, 'smoke', bx, by, 0, -10, rnd(0.3, 0.45), rnd(4, 6), FOAM, 0, 2, 1.5).layer = 0;
    }
  }
}

function waveLaunch(fx, q) {
  const R = sizeOf(q);
  fx.wave(q.x, q.y, q.c.light, R * 3.5, 0.3, 4);
  foam(fx, q.x, q.y, 4, R, 70);
}

function waveImpact(fx, x, y, ang, c, info) {
  const s = info.s || 1, k = info.why === 'hit' ? s * 1.1 : 1.3;
  crown(fx, x, y, k, c);
  foam(fx, x, y, Math.round(7 * k), 30 * k, 90 * k);
  for (let i = 0; i < 3; i++) fx.wave(x, y, i ? c.light : WHITE, (60 + 40 * i) * k, 0.35 + 0.12 * i, 3 - i * 0.5, 0);
}

// 고리 · 부채꼴: 밀려 나가는 물마루 (서버 반지름에 딱 닿는다) - a0 · a1 이 호의 끝 (고리면 0 → TAU)
function waveFront(fx, ctx, q, x, y, Rmax, a0, a1) {
  const t = fx.clock, { c, seed } = q;
  if (q.phase === 'mark') {                     // 가운데서 물이 차오른다
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 3; i++) {
      const ph = (t * 1.4 + i / 3) % 1, R = (BODY_R + Rmax * 0.35 * q.u) * ph + 6;
      arcPts(x, y, R, a0, a1, 24, 1.5, 4, t * 3 + i, 1);
      poly(ctx, 24);
      strokePath(ctx, c.light, 2, (0.15 + 0.4 * q.u) * (1 - ph));
    }
    return;
  }
  const f = fireK(q), fade = f < 0.75 ? 1 : 1 - (f - 0.75) / 0.25, R = Rmax * easeOut(Math.min(1, f * 1.15));
  const T = Math.max(14, Rmax * 0.2) * (1 - 0.35 * f);
  ctx.globalCompositeOperation = 'source-over';   // 지나간 자리는 젖어 있다
  ctx.beginPath();
  if (a1 - a0 < TAU - 0.01) ctx.moveTo(x, y);
  ctx.arc(x, y, Math.max(0, R - T * 0.5), a0, a1);
  ctx.closePath();
  fillPath(ctx, c.dark, 0.16 * fade);
  foamLine(ctx, x, y, R * 0.72, a0, a1, 0.35 * fade, t, seed + 7, 30);
  crest(fx, ctx, x, y, R, a0, a1, T, c, fade, t, seed, a1 - a0 > 3 ? NMAX : 24);
  const n = fx.perSec(300 * fade);              // 마루에서 앞으로 튀는 물보라
  for (let i = 0; i < n; i++) {
    const th = a0 + (a1 - a0) * Math.random(), v = rnd(120, 280), px = x + Math.cos(th) * R, py = y + Math.sin(th) * R;
    if (i % 3) dot(fx, 'glow', px, py, Math.cos(th) * v, Math.sin(th) * v - rnd(80, 200), rnd(0.35, 0.55), rnd(2.5, 4.5), i % 2 ? c.light : WHITE, 700, 1, 0.6);
    else dot(fx, 'smoke', px, py, Math.cos(th) * v * 0.4, Math.sin(th) * v * 0.4, rnd(0.4, 0.6), rnd(8, 12), FOAM, 0, 2.5, 2).layer = 0;
  }
}

// ================================================================ shard
const frostyOf = (ty) => ty === 'ICE';

function shardShot(fx, ctx, q) {
  const { x, y, ux, uy, c } = q, R = sizeOf(q), t = fx.clock, s = q.seed, px = -uy, py = ux, frosty = frostyOf(q.ty);
  ctx.globalCompositeOperation = 'lighter';
  ribbon(ctx, q.trail, t, 0.2, R * 1.6, R * 0.2, frosty ? MIST : c.light, 0.3);
  streak(fx, ctx, c.light, x - ux * R * 2, y - uy * R * 2, q.ang, R * 3, R * 0.8, 0.35);
  fx.ink.glow(ctx, frosty ? MIST : c.light, x, y, R * 2.2, frosty ? 0.45 : 0.3);
  for (let i = 0; i < 2; i++) {                 // 곁에서 도는 작은 조각
    const a = t * 9 + s + i * Math.PI, o = Math.sin(a) * R * 1.3, hgt = Math.cos(a) * R * 1.3 * H3;
    crystal(ctx, x - ux * R * 0.9 + px * o, y - uy * R * 0.9 + py * o - hgt, q.ang, R * 0.75, R * 0.32, a * 2, c, 0.9);
  }
  crystal(ctx, x, y, q.ang, R * 2.6, R * 1.05, t * 14 + s, c, 1);   // 긴 축으로 돈다
  ctx.globalCompositeOperation = 'lighter';
  const tw = 0.6 + 0.4 * Math.sin(t * 26 + s);
  fx.ink.star(ctx, WHITE, x + ux * R * 1.45, y + uy * R * 1.45, R * (0.8 + 0.5 * tw), 1);
  fx.ink.star(ctx, WHITE, x - ux * R * 0.3 - px * R * 0.3, y - uy * R * 0.3 - py * R * 0.3, R * 0.6 * (1 - tw) + 1, 0.8);
}

function shardTrail(fx, q) {
  const R = sizeOf(q), n = fx.perSec(24), px = -q.uy, py = q.ux, frosty = frostyOf(q.ty);
  for (let i = 0; i < n; i++) {
    const back = rnd(R, R * 3), sd = rnd(-1, 1), x = q.x - q.ux * back + px * sd * R * 0.8, y = q.y - q.uy * back + py * sd * R * 0.8;
    const r = Math.random();
    if (frosty && r < 0.45) dot(fx, 'smoke', x, y, px * sd * 30, py * sd * 30 - 10, rnd(0.35, 0.6), rnd(7, 11), MIST, 0, 2, 2).layer = 0;
    else if (r < 0.8) {                         // 눈송이 · 반짝임
      dot(fx, 'star', x, y, px * sd * rnd(20, 60) + q.ux * q.speed * 0.15, py * sd * rnd(20, 60) + q.uy * q.speed * 0.15 + (frosty ? 20 : 0),
        rnd(0.3, 0.55), rnd(4, 7), frosty || r < 0.6 ? WHITE : q.c.light, frosty ? 30 : 0, 1.5, 0.4);
    } else {                                    // 작은 부스러기
      const p = dot(fx, 'shard', x, y, px * sd * rnd(40, 90), py * sd * rnd(40, 90), rnd(0.25, 0.4), rnd(2.5, 4), q.c.light, 0, 2, 1);
      p.vr = rnd(-20, 20);
    }
  }
}

function shardLaunch(fx, q) {
  const R = sizeOf(q);
  fx.spawn('star', q.x, q.y, 0, 0, 0.18, R * 2.2, WHITE).size1 = R * 0.6;
  shatter(fx, q.x, q.y, 0.45, q.c, frostyOf(q.ty), q.ang, 1.4);
}

function shardImpact(fx, x, y, ang, c, info) {
  const s = info.s || 1, frosty = frostyOf(info.ty), k = info.why === 'hit' ? s : info.why === 'tele' ? 1.6 : 1.2;
  shatter(fx, x, y, k, c, frosty);
  shatter(fx, x, y, 0.5 * k, c, false, ang, 1.2);    // 맞은 쪽으로 더 튄다
  if (frosty) fx.wave(x, y, c.light, 55 * k, 0.5, 6, 0);    // 바닥에 번지는 서리
}

// 바닥에서 솟는 결정 한 무리 - i 마다 시드 자리 · 크기, f 로 돋아난다
function sprout(ctx, x, y, ang, L, W, grow, c, a, seed) {
  if (!(grow > 0)) return;
  crystal(ctx, x, y - L * 0.25 * grow, ang, L * grow, W * grow, seed, c, a);
}

function shardCone(fx, ctx, q) {
  const t = fx.clock, { x, y, ang, len, h, c, seed } = q, frosty = frostyOf(q.ty);
  ctx.globalCompositeOperation = 'lighter';
  if (q.phase === 'mark') {                     // 입 앞에 냉기가 모인다
    fx.ink.glow(ctx, frosty ? MIST : c.light, x + Math.cos(ang) * BODY_R, y + Math.sin(ang) * BODY_R, BODY_R * (1 + q.u), 0.2 + 0.4 * q.u);
    for (let i = 0; i < 4; i++) {
      const a = t * 3 + seed + (i * TAU) / 4;
      fx.ink.star(ctx, WHITE, x + Math.cos(a) * BODY_R * 1.4, y + Math.sin(a) * BODY_R * 0.8, 6 + 6 * q.u, 0.3 + 0.5 * q.u);
    }
    return;
  }
  const f = fireK(q), fade = f < 0.7 ? 1 : 1 - (f - 0.7) / 0.3, scale = len / 380;
  if (!q.mem.go) {
    q.mem.go = true;
    for (let i = 0; i < 40; i++) {               // 몰아치는 눈 · 반짝임
      const a = ang + rnd(-h, h), v = rnd(450, 800), d = rnd(10, len * 0.4);
      const p = dot(fx, frosty ? (i % 3 ? 'star' : 'glow') : i % 2 ? 'star' : 'spark', x + Math.cos(a) * d, y + Math.sin(a) * d,
        Math.cos(a) * v, Math.sin(a) * v, rnd(0.4, 0.7), rnd(3.5, 6), i % 3 ? WHITE : c.light, 0, 1.6, 0.6);
      p.w = 1.6;
    }
  }
  for (let i = 1; i <= 3; i++) {                // 냉기 띠
    const d = len * 0.3 * i * (0.35 + 0.65 * easeOut(f));
    streak(fx, ctx, frosty ? MIST : c.light, x + Math.cos(ang) * d, y + Math.sin(ang) * d, ang, len * 0.25, len * 0.12 * i * Math.tan(h) + 10, 0.32 * fade);
  }
  const n = 18;
  for (let i = 0; i < n; i++) {                 // 가까운 데부터 결정이 솟는다 - 위로 서고 부채꼴 쪽으로 기운다
    const dk = 0.12 + 0.85 * ((i + hash(seed + i * 7.1)) / n), ai = ang + (hash(seed + i * 13.7) - 0.5) * 1.8 * h;
    const grow = clamp01((f * 1.5 - dk) * 4), L = (28 + 30 * hash(seed + i)) * scale * (0.7 + 0.5 * dk);
    const cx = x + Math.cos(ai) * len * dk, cy = y + Math.sin(ai) * len * dk;
    const dx = Math.cos(ai) * 0.45 + (hash(seed + i + 2) - 0.5) * 0.5, dy = -1 + Math.sin(ai) * 0.45;
    sprout(ctx, cx, cy, Math.atan2(dy, dx), L, L * 0.42, grow, c, fade, seed + i);
  }
  ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 18; i++) {                // 몰아치는 눈 줄
    const ai = ang + (hash(seed + i * 4.1) - 0.5) * 1.9 * h, d = len * ((hash(seed + i * 2.3) + f * 1.6) % 1);
    const bx = x + Math.cos(ai) * d, by = y + Math.sin(ai) * d, L = 14 + 10 * hash(seed + i);
    ctx.globalAlpha = A(0.8 * fade * Math.sin(Math.PI * d / len));
    line(ctx, frosty ? WHITE : c.light, 1.6, bx, by, bx - Math.cos(ai) * L, by - Math.sin(ai) * L);
  }
}

function shardRing(fx, ctx, q) {                   // 발밑에서 사방으로 솟는 결정 (서리 고리)
  const t = fx.clock, { x, y, c, seed } = q, frosty = frostyOf(q.ty);
  ctx.globalCompositeOperation = 'lighter';
  if (q.phase === 'mark') {
    frostPattern(ctx, x, y, q.r * 0.8 * q.u, seed, frosty ? WHITE : c.light, 0.15 + 0.35 * q.u);
    return;
  }
  const f = fireK(q), fade = f < 0.7 ? 1 : 1 - (f - 0.7) / 0.3, R = q.r * easeOut(Math.min(1, f * 1.3));
  if (!q.mem.go) {
    q.mem.go = true;
    shatter(fx, x, y, 1.6, c, frosty);
  }
  fx.ink.glow(ctx, frosty ? MIST : c.light, x, y, R, 0.3 * fade);
  for (let i = 0; i < 16; i++) {
    const a = seed + (i * TAU) / 16 + (hash(seed + i) - 0.5) * 0.3, d = R * (0.75 + 0.25 * hash(seed + i * 3));
    const L = (20 + 18 * hash(seed + i * 5)) * (q.r / 200 + 0.5);
    sprout(ctx, x + Math.cos(a) * d, y + Math.sin(a) * d, a - 0.4 * Math.cos(a), L, L * 0.42, clamp01(f * 3), c, fade, seed + i);
  }
  ctx.globalCompositeOperation = 'lighter';
  ring(ctx, WHITE, 0.7 * fade, 2, x, y, R);
  frostPattern(ctx, x, y, R * 0.9, seed, frosty ? WHITE : c.light, 0.4 * fade);
}

// 내려찍기: 바닥에 서리 무늬가 퍼지고, 큰 고드름 (또는 결정) 이 떨어져 박혀 솟는다
function shardTele(fx, ctx, q) {
  const t = fx.clock, { x, y, c, seed } = q, frosty = frostyOf(q.ty);
  ctx.globalCompositeOperation = 'lighter';
  if (q.phase === 'mark') {
    fx.ink.glow(ctx, frosty ? MIST : c.light, x, y, q.r * 0.9 * q.u, 0.25 * q.u);
    frostPattern(ctx, x, y, q.r * 0.85 * easeOut(q.u), seed, frosty ? WHITE : c.light, 0.2 + 0.4 * q.u);
    for (let i = 0; i < 4; i++) {
      const a = seed + i * 1.7, d = q.r * 0.6 * hash(seed + i);
      fx.ink.star(ctx, WHITE, x + Math.cos(a) * d, y + Math.sin(a) * d, 5 + 6 * q.u * (0.5 + 0.5 * Math.sin(t * 12 + i)), 0.6 * q.u);
    }
    return;
  }
  const f = fireK(q), fade = f < 0.6 ? 1 : 1 - (f - 0.6) / 0.4;
  for (let i = 0; i < 9; i++) {                  // 박힌 자리에서 솟는 결정
    const a = seed + (i * TAU) / 9 + hash(seed + i) * 0.4, d = q.r * (0.25 + 0.55 * hash(seed + i * 3)), L = q.r * (0.35 + 0.3 * hash(seed + i * 5));
    sprout(ctx, x + Math.cos(a) * d, y + Math.sin(a) * d * 0.7, -Math.PI / 2 + Math.cos(a) * 0.7, L, L * 0.4, clamp01(f * 4), c, fade, seed + i);
  }
  crystal(ctx, x, y - q.r * 0.45, -Math.PI / 2, q.r * 1.3, q.r * 0.38, seed, c, fade);  // 박힌 고드름
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.star(ctx, WHITE, x, y - q.r * 1.1, q.r * 0.6 * fade, fade);
}

function shardFall(fx, ctx, q, x, y, v) {           // 떨어지는 큰 고드름 - 위로 냉기 꼬리
  const { c } = q, frosty = frostyOf(q.ty), L = q.r * 1.6;
  ctx.globalCompositeOperation = 'lighter';
  streak(fx, ctx, frosty ? MIST : c.light, x, y - L * 1.1, -Math.PI / 2, L * 1.1, L * 0.22, 0.25 + 0.5 * v);
  crystal(ctx, x, y - L * 0.45, Math.PI / 2, L, L * 0.27, fx.clock * 6 + q.seed, c, 0.4 + 0.6 * v);
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.star(ctx, WHITE, x, y, 10 + 8 * v, v);
  const n = fx.perSec(20 * v);
  for (let i = 0; i < n; i++) {
    dot(fx, frosty ? 'smoke' : 'star', x + rnd(-8, 8), y - L * rnd(0.3, 1), rnd(-20, 20), -30, rnd(0.3, 0.5), 7, frosty ? MIST : WHITE, 0, 2, 1.5);
  }
}

function shardRush(fx, ctx, a) {
  const { c } = a, t = fx.clock, frosty = frostyOf(a.ty);
  if (a.stage === 'wind') {                     // 몸 둘레로 결정이 돋는다
    const k = a.sk;
    for (let i = 0; i < 5; i++) {
      const th = a.seed + (i * TAU) / 5 + t * 2, d = BODY_R * 1.25;
      crystal(ctx, a.x + Math.cos(th) * d, a.y + Math.sin(th) * d * 0.7, th, BODY_R * 0.7 * k, BODY_R * 0.28 * k, th + t * 6, c, 0.3 + 0.6 * k);
    }
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, frosty ? MIST : c.light, a.x, a.y, BODY_R * 1.8, 0.25 * k);
    return;
  }
  const fade = a.stage === 'tail' ? 1 - a.sk : 1, tr = a.trail;
  ctx.globalCompositeOperation = frosty ? 'source-over' : 'lighter';
  ribbon(ctx, tr, t, 0.3, a.reach * 2, a.reach * 0.6, frosty ? MIST : c.dark, 0.08 * fade);   // 맞는 폭 - 언 길 (옅게)
  ctx.globalCompositeOperation = 'lighter';
  ribbon(ctx, tr, t, 0.25, BODY_R * 1.5, 3, c.light, 0.3 * fade);
  for (let i = 1; i < tr.n; i++) {               // 지나간 자리에 돋는 결정
    const age = t - tr.t(i);
    if (!(age < 0.45)) break;
    const sd = i % 2 ? 1 : -1, L = (12 + 8 * hash(a.seed + i)) * Math.min(1, age * 10) * (1 - age / 0.45);
    const bx = tr.x(i) - a.uy * sd * BODY_R * 0.8, by = tr.y(i) + a.ux * sd * BODY_R * 0.8;
    crystal(ctx, bx, by - L * 0.3, -Math.PI / 2 + sd * 0.5, L, L * 0.42, a.seed + i, c, fade);
  }
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.star(ctx, WHITE, a.x + a.ux * BODY_R, a.y + a.uy * BODY_R, 12 + 6 * Math.sin(t * 30), fade);
  if (a.stage === 'act') {
    const n = fx.perSec(40);
    for (let i = 0; i < n; i++) {
      const sd = Math.random() < 0.5 ? -1 : 1, v = rnd(80, 200);
      dot(fx, frosty ? 'star' : 'spark', a.x - a.uy * sd * BODY_R, a.y + a.ux * sd * BODY_R, -a.uy * sd * v - a.ux * 120, a.ux * sd * v - a.uy * 120,
        rnd(0.2, 0.4), rnd(5, 9), Math.random() < 0.5 ? WHITE : c.light, 0, 3, 0.5).w = 1.6;
    }
  }
}

function shardSwing(fx, ctx, a, t) {               // 깎인 초승달 - 마디마다 면이 다른 빛
  const R = a.reach, span = a.mk === 'dash' ? 0.7 : 1.2, fade = t > 0.55 ? (1 - t) / 0.45 : 1, c = a.c;
  const e = easeOut(Math.min(1, t * 1.8)), a0 = a.ang - span, a1 = a0 + 2 * span * e, from = Math.max(a0, a1 - span * 1.2);
  const segs = 6, T = R * 0.3;
  ctx.globalCompositeOperation = 'source-over';
  for (let i = 0; i < segs; i++) {
    const k0 = i / segs, k1 = (i + 1) / segs, th0 = from + (a1 - from) * k0, th1 = from + (a1 - from) * k1;
    const w0 = T * Math.sin(Math.PI * Math.min(1, k0 * 0.8 + 0.1)), w1 = T * Math.sin(Math.PI * Math.min(1, k1 * 0.8 + 0.1));
    const o0x = a.x + Math.cos(th0) * R, o0y = a.y + Math.sin(th0) * R, o1x = a.x + Math.cos(th1) * R, o1y = a.y + Math.sin(th1) * R;
    const mid = (th0 + th1) / 2, mr = R - (w0 + w1) * 0.3;
    ctx.beginPath();
    ctx.moveTo(o0x, o0y);
    ctx.lineTo(o1x, o1y);
    ctx.lineTo(a.x + Math.cos(mid) * mr, a.y + Math.sin(mid) * mr);
    ctx.closePath();
    fillPath(ctx, i % 2 ? c.light : WHITE, 0.95 * fade);
    ctx.beginPath();
    ctx.moveTo(a.x + Math.cos(mid) * mr, a.y + Math.sin(mid) * mr);
    ctx.lineTo(o1x, o1y);
    ctx.lineTo(a.x + Math.cos(th1) * (R - w1), a.y + Math.sin(th1) * (R - w1));
    ctx.lineTo(a.x + Math.cos(th0) * (R - w0), a.y + Math.sin(th0) * (R - w0));
    ctx.closePath();
    fillPath(ctx, i % 2 ? c.dark : c.light, 0.9 * fade);
  }
  ctx.globalCompositeOperation = 'lighter';
  arcPts(a.x, a.y, R, from, a1, 12, 0, 1, 0, 3);
  poly(ctx, 12);
  strokePath(ctx, WHITE, 2, 0.9 * fade);
  fx.ink.star(ctx, WHITE, a.x + Math.cos(a1) * R, a.y + Math.sin(a1) * R, 18, fade);
  if (!a.mem.cut && t > 0.25) {
    a.mem.cut = true;
    shatter(fx, a.x + Math.cos(a.ang) * R, a.y + Math.sin(a.ang) * R, 0.9, c, frostyOf(a.ty), a.ang, 1.6);
  }
}

// ---------------------------------------------------------------- 모양
// 맞은 자리 · 장판이 터진 자리 · 근접 끝에 튀는 조각
const WIND_BITS = { shape: 'spark', n: 12, c: '#ffffff', v: 340, life: 0.3, size: 14, w: 2, drag: 4 };
const SOUND_BITS = { shape: 'ring', n: 5, c: 'light', v: 90, life: 0.35, size: 4, end: 3, w: 1.5, drag: 3 };
const FOAM_BITS = { shape: 'glow', n: 14, c: 'light', v: 240, life: 0.45, size: 5, g: 700, drag: 1, up: -160 };

export default {
  wind: {
    shot: windShot, trail: windTrail, launch: windLaunch, impact: windImpact, debris: WIND_BITS,
    cone: windCone, ring: windRing, tele: windTele, fall: windFall, rush: windRush, swing: windSwing,
  },
  sound: {
    shot: soundShot, trail: soundTrail, launch: soundLaunch, impact: soundImpact, debris: SOUND_BITS,
    cone: soundCone, ring: soundRing,
  },
  jet: {
    shot: jetShot, trail: jetTrail, launch: jetLaunch, impact: jetImpact, debris: 'drop',
    cone: jetCone, ring: jetRing, tele: jetTele, fall: jetFall, rush: jetRush, swing: jetSwing,
  },
  wave: {
    shot: waveShot, trail: waveTrail, launch: waveLaunch, impact: waveImpact, debris: FOAM_BITS,
    ring(fx, ctx, q) { waveFront(fx, ctx, q, q.x, q.y, q.r, 0, TAU); },
    cone(fx, ctx, q) { waveFront(fx, ctx, q, q.x, q.y, q.len, q.ang - q.h, q.ang + q.h); },
  },
  shard: {
    shot: shardShot, trail: shardTrail, launch: shardLaunch, impact: shardImpact, debris: 'shard',
    cone: shardCone, ring: shardRing, tele: shardTele, fall: shardFall, rush: shardRush, swing: shardSwing,
  },
};
