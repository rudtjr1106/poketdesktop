/* 모양: 불 · 번개 · 풀 · 가루 · 독 (flame zap leaf powder poison).
   훅 이름 · 인자 · q · a 칸 · 도우미는 fx/core.js 맨 위. 이 파일에는 이 다섯 키만 둔다 (fx/styles/index.js 의 FAMILY_OF).

   그리는 법 (이 집안 공통 - 도우미는 이 파일 안에만 둔다)
     * 불: 불꽃 혀(tongue)를 모아 겹겹이 - 그을린 겉 · 주황 몸(보통 혼합) → 노랑 → 흰 심(빛). 혀 끝은 noise1 로
       흔들리고 한 겹은 한 경로로 칠한다 (겹친 혀가 더 진해지지 않게). 연기는 보통 혼합, 불티는 위로 떠오른다.
       부채꼴 불길은 장판이 지워진 뒤에도 입자로 잠깐 남아 사그라든다.
     * 번개: 씨앗 + 1/20초마다 바뀌는 rng 로 꺾은 선 + 곁가지, 세 겹 긋기 (넓고 옅은 빛 → 밝은 색 → 흰 심).
     * 풀: 잎마다 뒤집히는 폭(cos)으로 팔랑이고, 앞면이 보일 때 끝이 반짝인다. 무리는 느슨하게 돌며 따라온다.
       꽃잎 기술(PETAL · FLOWER · BLOSSOM) · 요정 타입은 꽃잎.
     * 가루: 부드러운 덩이(보통 혼합)가 부풀었다 줄고, 반짝이는 알갱이가 깜박인다. 기술마다 제 색 (POWDER_TINT).
     * 독: 출렁이는 덩이 (닫힌 부드러운 경로) + 윤기 + 겉에서 부풀었다 터지는 거품 + 보라 김.
   지나온 길은 납작한 띠(ribbon) 대신 옅어지는 빛 번짐 (trailGlow) - 띠는 빛줄기처럼 보인다.
   그리는 것은 q.seed · a.seed 와 시각에서 다시 만든다 (Math.random 은 입자에만). a.mem.hit - swing 이 한 번 튀긴 것. */
import {
  A, BODY_R, FALL_H, INK, TAU, WHITE, circle, clamp01, crescent, easeOut, fillPath, hash, line, noise1, ring,
  rng, rnd, smooth, spikes, streak, strokePath,
} from '../core.js';

// ---------------------------------------------------------------- 수
const frac = (v) => v - Math.floor(v);
const SMOKE = '#3a3034';          // 그을린 연기
const SCORCH = '#1a0d06';         // 탄 자리
const PETAL = Object.freeze({ light: '#ffd9ee', dark: '#ff86c2' });
// 가루 기술마다 제 색 (없으면 타입 색)
const POWDER_TINT = Object.freeze({
  SLEEPPOWDER: Object.freeze({ light: '#d9f2ff', dark: '#6fb0e8' }),
  STUNSPORE: Object.freeze({ light: '#fff6a8', dark: '#e2b81c' }),
  POISONPOWDER: Object.freeze({ light: '#f1c6ff', dark: '#a24fd4' }),
  SPORE: Object.freeze({ light: '#f4ffd6', dark: '#9ac25a' }),
  RAGEPOWDER: Object.freeze({ light: '#ffc9b0', dark: '#e2492e' }),
  COTTONSPORE: Object.freeze({ light: '#ffffff', dark: '#cfd6e6' }),
  MAGICPOWDER: Object.freeze({ light: '#f8d6ff', dark: '#c46ee6' }),
});
const PETAL_RE = /PETAL|FLOWER|BLOSSOM|FLORAL/;

// ---------------------------------------------------------------- 색
const MIXED = new Map();
/** '#rrggbb' 둘을 t 만큼 섞는다 (상수 t 만 - 결과를 기억해 둔다). */
function mix(a, b, t) {
  const key = a + b + t;
  let v = MIXED.get(key);
  if (v === undefined) {
    const p = parseInt(a.slice(1), 16), q = parseInt(b.slice(1), 16);
    const ch = (s) => Math.round(((p >> s) & 255) * (1 - t) + ((q >> s) & 255) * t);
    v = '#' + ((1 << 24) | (ch(16) << 16) | (ch(8) << 8) | ch(0)).toString(16).slice(1);
    if (MIXED.size > 512) MIXED.clear();
    MIXED.set(key, v);
  }
  return v;
}

const FIRE_PALS = new WeakMap();
/** 불 색: 흰 심 → hot → mid(밝은 색) → out(어두운 색) → deep(그을린 빨강, 보통 혼합). */
function firePal(c) {
  let P = FIRE_PALS.get(c);
  if (!P) {
    P = { light: c.light, dark: c.dark, hot: mix(c.light, WHITE, 0.55), mid: c.light, out: c.dark,
      deep: mix(c.dark, '#5a0600', 0.5) };
    FIRE_PALS.set(c, P);
  }
  return P;
}

const VENOM_PALS = new WeakMap();
/** 독 · 풀 · 가루가 같이 쓰는 색: light · dark + deep (테두리) + edge (잎 테). */
function deepPal(c) {
  let V = VENOM_PALS.get(c);
  if (!V) {
    V = { light: c.light, dark: c.dark, deep: mix(c.dark, '#12061a', 0.55), edge: mix(c.dark, '#000000', 0.6),
      glint: mix(c.light, WHITE, 0.6) };
    VENOM_PALS.set(c, V);
  }
  return V;
}

const leafPal = (q) => ((typeof q.k === 'string' && PETAL_RE.test(q.k)) || q.ty === 'FAIRY'
  ? (q.ty === 'FAIRY' ? q.c : PETAL) : q.c);
const POWDER_PALS = new WeakMap();
/** 가루 색: 기술마다 제 색 (없으면 타입 색). cloud 는 밝은 쪽으로 섞은 구름 - 풀밭 위에서도 보이게. */
function powderOf(c) {
  let P = POWDER_PALS.get(c);
  if (!P) {
    P = { light: c.light, dark: c.dark, cloud: mix(c.light, WHITE, 0.3) };
    POWDER_PALS.set(c, P);
  }
  return P;
}
const powderPal = (q) => powderOf(typeof q.k === 'string' && Object.prototype.hasOwnProperty.call(POWDER_TINT, q.k)
  ? POWDER_TINT[q.k] : q.c);
const isPetal = (q) => (typeof q.k === 'string' && PETAL_RE.test(q.k)) || q.ty === 'FAIRY';

// ---------------------------------------------------------------- 입자 (풀 하나를 같이 쓴다)
function part(fx, shape, x, y, vx, vy, life, size, end, col, g = 0, drag = 0, layer = 1) {
  const p = fx.spawn(shape, x, y, vx, vy, life, size, col);
  p.size1 = size * end;
  p.g = g;
  p.drag = drag;
  p.layer = layer;
  return p;
}

// ang ± arc/2 쪽으로 n 개 (v0~v1)
function spray(fx, n, shape, x, y, ang, arc, v0, v1, life, size, end, col, g = 0, drag = 0, layer = 1) {
  for (let i = 0; i < n; i++) {
    const a = ang + (Math.random() - 0.5) * arc, v = rnd(v0, v1);
    part(fx, shape, x, y, Math.cos(a) * v, Math.sin(a) * v, life * rnd(0.75, 1.25), size * rnd(0.75, 1.25), end, col, g,
      drag, layer);
  }
}

// ---------------------------------------------------------------- 경로
/** 닫힌 부드러운 선 (점 사이 가운데를 2차 곡선으로). */
function closedSmooth(ctx, xs, ys, n) {
  ctx.beginPath();
  ctx.moveTo((xs[n - 1] + xs[0]) / 2, (ys[n - 1] + ys[0]) / 2);
  for (let i = 0; i < n; i++) {
    const j = i + 1 < n ? i + 1 : 0;
    ctx.quadraticCurveTo(xs[i], ys[i], (xs[i] + xs[j]) / 2, (ys[i] + ys[j]) / 2);
  }
  ctx.closePath();
}

// ---------------------------------------------------------------- 불꽃 혀
// 밑동 (x, y) 에서 (dx, dy) 쪽으로 L, 밑 반폭 W, 끝이 옆으로 s 만큼 휜다. 밑은 둥글다 (앞으로 0.7 W)
function tonguePath(ctx, x, y, dx, dy, L, W, s) {
  const nx = -dy, ny = dx, lx = x + nx * W, ly = y + ny * W;
  ctx.moveTo(lx, ly);
  ctx.quadraticCurveTo(x + dx * L * 0.45 + nx * (W + s * 0.25), y + dy * L * 0.45 + ny * (W + s * 0.25),
    x + dx * L + nx * s, y + dy * L + ny * s);
  ctx.quadraticCurveTo(x + dx * L * 0.4 - nx * (W * 0.9 - s * 0.55), y + dy * L * 0.4 - ny * (W * 0.9 - s * 0.55),
    x - nx * W, y - ny * W);
  ctx.quadraticCurveTo(x - dx * W * 1.4, y - dy * W * 1.4, lx, ly);
  ctx.closePath();
}

// 혀를 모아 두었다가 한 겹씩 한 경로로 칠한다
const TMAX = 64;
const TG = { n: 0, x: new Float64Array(TMAX), y: new Float64Array(TMAX), dx: new Float64Array(TMAX),
  dy: new Float64Array(TMAX), L: new Float64Array(TMAX), W: new Float64Array(TMAX), s: new Float64Array(TMAX) };

function addTongue(x, y, dx, dy, L, W, s) {
  const d = Math.hypot(dx, dy);
  if (TG.n >= TMAX || !(L > 0) || !(W > 0) || !(d > 1e-6)) return;
  const i = TG.n++;
  TG.x[i] = x;
  TG.y[i] = y;
  TG.dx[i] = dx / d;
  TG.dy[i] = dy / d;
  TG.L[i] = L;
  TG.W[i] = W;
  TG.s[i] = s;
}

function tonguePass(ctx, kL, kW, kS) {
  ctx.beginPath();
  for (let i = 0; i < TG.n; i++) tonguePath(ctx, TG.x[i], TG.y[i], TG.dx[i], TG.dy[i], TG.L[i] * kL, TG.W[i] * kW, TG.s[i] * kS);
}

/** 모은 혀: 그을린 겉 → 주황 몸 (보통 혼합) → 노랑 → 흰 심 (빛). 칠하고 비운다. */
function flushTongues(ctx, P, a, hot = 1) {
  if (TG.n && a > 0) {
    ctx.globalCompositeOperation = 'source-over';
    tonguePass(ctx, 1, 1, 1);
    fillPath(ctx, P.deep, 0.5 * a);
    tonguePass(ctx, 0.9, 0.84, 0.92);
    fillPath(ctx, P.out, 0.85 * a);
    ctx.globalCompositeOperation = 'lighter';
    tonguePass(ctx, 0.66, 0.56, 0.7);
    fillPath(ctx, P.mid, 0.8 * a);
    if (hot > 0) {
      tonguePass(ctx, 0.36, 0.28, 0.4);
      fillPath(ctx, WHITE, 0.55 * a * hot);
    }
  }
  TG.n = 0;
}

// 불길이 흐르는 쪽 - 나아가는 반대쪽 + 조금 위 (불은 위로 핥는다). 단위 벡터를 V 에
const V = { x: 0, y: 0 };
function flowOf(ux, uy, up = 0.4) {
  let bx = -ux, by = -uy - up;
  const d = Math.hypot(bx, by) || 1;
  bx /= d;
  by /= d;
  V.x = bx;
  V.y = by;
  return V;
}

/** 불덩이: 머리 (x, y), 불길이 (bx, by) 쪽으로 흐른다, 크기 r, 혀 n 개. 뒤 빛 번짐 · 머리 빛까지. */
function fireball(fx, ctx, P, x, y, bx, by, r, seed, t, a, n = 6, stretch = 1) {
  ctx.globalCompositeOperation = 'lighter';
  streak(fx, ctx, P.out, x + bx * r * 1.6, y + by * r * 1.6, Math.atan2(by, bx), r * 3 * stretch, r * 1.5, 0.5 * a);
  for (let i = 0; i < n; i++) {
    const k = i / n, f1 = noise1(t * 7 + i * 3.1 + seed), f2 = noise1(t * 10 + i * 5.7 + seed * 0.37);
    const tw = (f2 - 0.5) * 0.9, c = Math.cos(tw), s = Math.sin(tw);
    const off = (i % 2 ? 1 : -1) * r * 0.45 * (0.3 + k), d = r * 0.42 * i;
    addTongue(x + bx * d - by * off, y + by * d + bx * off, bx * c - by * s, bx * s + by * c,
      r * (2.6 - 1.2 * k) * (0.7 + 0.6 * f1) * stretch, r * (1.05 - 0.45 * k), (f1 - 0.5) * r * 1.6);
  }
  flushTongues(ctx, P, a);
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.glow(ctx, P.mid, x, y, r * 1.7, 0.55 * a);
  fx.ink.core(ctx, P.hot, x, y, r * 1.0, a);
}

/** 불꽃 고리: (x, y) 둘레 R 에 혀 n 개가 위 · 바깥으로 핥는다 (이웃 혀끼리 겹쳐 끊기지 않는다). h 혀 길이. */
function flameRing(ctx, P, x, y, R, n, h, seed, t, a, out = 0.55) {
  const w = Math.max(3, (TAU * R) / n) * 0.75;
  for (let i = 0; i < n; i++) {
    const th = (i / n) * TAU + seed, cx = Math.cos(th), cy = Math.sin(th), f = noise1(t * 8 + i * 1.9 + seed);
    addTongue(x + cx * R, y + cy * R, cx * out, cy * out * 0.5 - 1, h * (0.45 + 1.1 * f * f + 0.3 * hash(seed + i)), w,
      (noise1(t * 11 + i * 4.3) - 0.5) * h * 0.7);
  }
  flushTongues(ctx, P, a);
}

// ---------------------------------------------------------------- 번개
const ZX = new Float64Array(40), ZY = new Float64Array(40);
const MX = new Float64Array(40), MY = new Float64Array(40);

/** (x0, y0) → (x1, y1) 을 n 마디로 꺾은 선 (경로에 더한다). 마디는 ZX · ZY 에 남는다. R 은 rng. */
function jag(ctx, x0, y0, x1, y1, n, amp, R) {
  const dx = x1 - x0, dy = y1 - y0, d = Math.hypot(dx, dy) || 1, px = -dy / d, py = dx / d;
  const m = Math.max(1, Math.min(n, 38));
  ctx.moveTo(x0, y0);
  ZX[0] = x0;
  ZY[0] = y0;
  for (let i = 1; i <= m; i++) {
    const k = i / m, o = i < m ? (R() - 0.5) * 2 * amp * (0.45 + 0.55 * Math.sin(Math.PI * k)) : 0;
    const x = x0 + dx * k + px * o, y = y0 + dy * k + py * o;
    ctx.lineTo(x, y);
    ZX[i] = x;
    ZY[i] = y;
  }
  return m;
}

/** 번개 한 줄기 + 곁가지 nb 개 (경로에 더한다 - beginPath 는 부르는 쪽). */
function boltTree(ctx, x0, y0, x1, y1, n, amp, R, nb) {
  const m = jag(ctx, x0, y0, x1, y1, n, amp, R);
  if (!nb || m < 2) return;
  for (let i = 0; i <= m; i++) {
    MX[i] = ZX[i];
    MY[i] = ZY[i];
  }
  const L = Math.hypot(x1 - x0, y1 - y0), base = Math.atan2(y1 - y0, x1 - x0);
  for (let b = 0; b < nb; b++) {
    const i = 1 + Math.floor(R() * (m - 1)), a = base + (R() < 0.5 ? -1 : 1) * (0.45 + 0.6 * R());
    const len = L * ((m - i) / m) * (0.3 + 0.4 * R());
    jag(ctx, MX[i], MY[i], MX[i] + Math.cos(a) * len, MY[i] + Math.sin(a) * len, Math.max(2, (n / 2) | 0), amp * 0.6, R);
  }
}

/** 지금 경로를 번개로: 넓고 옅은 빛 → 밝은 색 → 흰 심 (빛 혼합). */
function zapStroke(ctx, c, w, a) {
  ctx.globalCompositeOperation = 'lighter';
  strokePath(ctx, c.dark, w * 3.6, 0.22 * a);
  strokePath(ctx, c.light, w * 1.5, 0.85 * a);
  strokePath(ctx, WHITE, w * 0.6, a);
}

// 1/hz 초마다 바뀌는 rng (같은 시각이면 같은 모양)
const flicker = (seed, t, hz = 20) => rng(Math.floor(seed * 9973) + Math.floor(t * hz) * 7919);

// (x, y) 둘레 R 에서 기어 다니는 작은 번개 n 개 (몸 · 바닥). flat 은 세로 배율 (바닥이면 0.55)
function crawl(ctx, c, x, y, R, n, R0, w, a, flat = 1) {
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const a0 = R0() * TAU, a1 = a0 + (R0() < 0.5 ? -1 : 1) * (0.7 + R0() * 1.1), r0 = R * (0.6 + 0.5 * R0()), r1 = R * (0.6 + 0.5 * R0());
    jag(ctx, x + Math.cos(a0) * r0, y + Math.sin(a0) * r0 * flat, x + Math.cos(a1) * r1, y + Math.sin(a1) * r1 * flat, 4,
      R * 0.28, R0);
  }
  zapStroke(ctx, c, w, a);
}

// ---------------------------------------------------------------- 잎
// 잎 하나 경로: 가운데 (x, y), rot 쪽으로 반길이 L, 반폭 W (뾰족한 끝 · 둥근 배)
function leafShape(ctx, x, y, L, W, rot) {
  const c = Math.cos(rot), s = Math.sin(rot);
  const tx = x + c * L, ty = y + s * L, bx = x - c * L, by = y - s * L;
  ctx.beginPath();
  ctx.moveTo(bx, by);
  ctx.bezierCurveTo(x - c * L * 0.5 - s * W * 1.1, y - s * L * 0.5 + c * W * 1.1, x + c * L * 0.45 - s * W * 0.9,
    y + s * L * 0.45 + c * W * 0.9, tx, ty);
  ctx.bezierCurveTo(x + c * L * 0.45 + s * W * 0.9, y + s * L * 0.45 - c * W * 0.9, x - c * L * 0.5 + s * W * 1.1,
    y - s * L * 0.5 - c * W * 1.1, bx, by);
  ctx.closePath();
}

/** 팔랑이는 잎 (보통 혼합): flip 의 cos 가 폭 - 뒷면은 어둡게, 앞면이 정면일 때 끝이 반짝인다. */
function drawLeaf(fx, ctx, L, x, y, len, rot, flip, a, petal) {
  const k = Math.cos(flip), wid = len * (petal ? 0.62 : 0.42) * (0.16 + 0.84 * Math.abs(k));
  ctx.globalCompositeOperation = 'source-over';
  leafShape(ctx, x, y, len, wid, rot);
  ctx.globalAlpha = A(a);
  ctx.fillStyle = k > 0 ? L.light : L.dark;
  ctx.fill();
  ctx.strokeStyle = L.edge;
  ctx.lineWidth = 1.2;
  ctx.globalAlpha = A(a * 0.7);
  ctx.stroke();
  if (!petal) {                                 // 잎맥
    const c = Math.cos(rot), s = Math.sin(rot);
    ctx.beginPath();
    ctx.moveTo(x - c * len * 0.9, y - s * len * 0.9);
    ctx.lineTo(x + c * len * 0.75, y + s * len * 0.75);
    strokePath(ctx, k > 0 ? L.dark : L.light, 1, a * 0.75);
  }
  const shine = k > 0 ? k ** 6 : 0;
  if (shine > 0.08) {
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.star(ctx, WHITE, x + Math.cos(rot) * len * 0.5, y + Math.sin(rot) * len * 0.5, len * 0.9, shine * a);
  }
}

// ---------------------------------------------------------------- 독
const BX = new Float64Array(24), BY = new Float64Array(24);
/** 출렁이는 덩이 경로. (ux, uy) 쪽이 앞 - st 만큼 뒤로 늘어진다 (날아가는 덩이 · 방울). */
function blobPath(ctx, x, y, r, t, seed, ux, uy, st, n = 10) {
  for (let i = 0; i < n; i++) {
    const th = (i / n) * TAU, cx = Math.cos(th), cy = Math.sin(th);
    const w = 1 + 0.12 * Math.sin(t * 7 + i * 2.3 + seed) + 0.07 * Math.sin(t * 11.3 + i * 4.1 + seed * 1.7);
    const lx = cx * r * w * (cx < 0 ? 1 + st * 1.4 * -cx : 1 + st * 0.15), ly = cy * r * w * (1 - st * 0.25);
    BX[i] = x + ux * lx - uy * ly;
    BY[i] = y + uy * lx + ux * ly;
  }
  closedSmooth(ctx, BX, BY, n);
}

/** 윤기 나는 독 덩이: 짙은 테 → 몸 → 밝은 속 (빛) → 흰 윤기. 빛은 늘 왼쪽 위에서. */
function sludge(ctx, D, x, y, r, t, seed, ux, uy, st, a) {
  ctx.globalCompositeOperation = 'source-over';
  blobPath(ctx, x, y, r * 1.1, t, seed, ux, uy, st);
  fillPath(ctx, D.deep, 0.92 * a);
  blobPath(ctx, x, y, r * 0.9, t * 1.1, seed + 3, ux, uy, st);
  fillPath(ctx, D.dark, a);
  ctx.globalCompositeOperation = 'lighter';
  blobPath(ctx, x - r * 0.12, y - r * 0.16, r * 0.52, t * 1.3, seed + 7, ux, uy, st * 0.5, 8);
  fillPath(ctx, D.light, 0.4 * a);
  ctx.globalCompositeOperation = 'source-over';
  ctx.beginPath();
  ctx.ellipse(x - r * 0.36, y - r * 0.4, r * 0.25, r * 0.12, -0.7, 0, TAU);
  fillPath(ctx, WHITE, 0.85 * a);
  circle(ctx, x + r * 0.05, y - r * 0.58, r * 0.07);
  fillPath(ctx, WHITE, 0.6 * a);
}

/** 겉에서 부풀었다 터지는 거품 n 개 (독 덩이 · 웅덩이). */
function bubbles(ctx, D, x, y, R, n, t, seed, a, flat = 1, rate = 1.6) {
  for (let i = 0; i < n; i++) {
    const p = frac(t * rate + hash(seed + i * 7)), th = hash(seed + i * 13) * TAU + t * 0.7;
    const bx = x + Math.cos(th) * R * 0.75, by = y + Math.sin(th) * R * 0.75 * flat, br = R * (0.1 + 0.2 * p);
    if (p < 0.86) {
      circle(ctx, bx, by, br);
      fillPath(ctx, D.dark, 0.85 * a);
      strokePath(ctx, D.light, 1.3, 0.9 * a);
      circle(ctx, bx - br * 0.35, by - br * 0.35, br * 0.25);
      fillPath(ctx, WHITE, 0.8 * a);
    } else {                                    // 톡 터진다
      const k = (p - 0.86) / 0.14;
      circle(ctx, bx, by, br * (1 + 1.4 * k));
      strokePath(ctx, D.light, 1.4, (1 - k) * a);
    }
  }
}

// ---------------------------------------------------------------- 가루
/** 부푸는 가루 구름 + 깜박이는 알갱이. R0 구름 반지름. */
function pollen(fx, ctx, P, x, y, R0, seed, t, a, n = 6, glitter = 14) {
  ctx.globalCompositeOperation = 'source-over';
  for (let i = 0; i < n; i++) {
    const th = seed + (i * TAU) / n + t * 0.7 * (i % 2 ? 1 : -1), d = R0 * (0.25 + 0.4 * noise1(t * 1.3 + i * 2.1 + seed));
    fx.ink.soft(ctx, P.cloud, x + Math.cos(th) * d, y + Math.sin(th) * d,
      R0 * (0.55 + 0.35 * noise1(t * 1.8 + i * 4.3 + seed)), 0.8 * a);
  }
  ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < n; i += 2) {
    const th = seed * 2 + (i * TAU) / n - t * 0.5, d = R0 * 0.45;
    fx.ink.soft(ctx, P.light, x + Math.cos(th) * d, y + Math.sin(th) * d, R0 * 0.55, 0.25 * a);
  }
  for (let j = 0; j < glitter; j++) {
    const th = hash(seed + j * 3.7) * TAU + t * (0.4 + hash(j) * 0.8), d = R0 * (0.15 + 0.95 * hash(seed + j * 5.3));
    const tw = Math.sin(t * (6 + hash(j * 9.1) * 6) + hash(seed + j) * 40);
    if (tw < 0.15) continue;
    const gx = x + Math.cos(th) * d, gy = y + Math.sin(th) * d * 0.85;
    if (j % 4 === 0) fx.ink.star(ctx, WHITE, gx, gy, 4 + 5 * tw, tw * a);
    else {
      ctx.globalAlpha = A(tw * a);
      ctx.fillStyle = j % 2 ? WHITE : P.light;
      ctx.fillRect(gx - 1.2, gy - 1.2, 2.4, 2.4);
    }
  }
}

// ---------------------------------------------------------------- 부채꼴 (불길 · 구름 · 물보라가 같이 쓴다)
const SX = new Float64Array(48), SY = new Float64Array(48);
// 부채꼴 축의 거리 s 에서 반폭 - 입에서 좁고 멀수록 넓다, noise 로 일렁인다
function halfAt(q, s, t, k, side) {
  return (6 + s * Math.tan(q.h) * 0.8) * k * (0.75 + 0.36 * noise1(s * 0.02 - t * 8 + q.seed + side * 31));
}

/** 불길 몸통 경로: 입 (q.x, q.y) 에서 reach 까지, 폭 배율 k. 가운데 줄도 꿈틀댄다. */
function streamPath(ctx, q, reach, k, t, layer) {
  const M = 10, ca = Math.cos(q.ang), sa = Math.sin(q.ang), tan = Math.tan(q.h);
  let n = 0;
  for (let side = 1; side >= -1; side -= 2) {
    for (let j = 0; j <= M; j++) {
      const jj = side > 0 ? j : M - j, s = (reach * jj) / M;
      const o = (noise1(s * 0.012 - t * 5 + q.seed + layer) - 0.5) * s * tan * 0.5;
      const w = side * halfAt(q, s, t, k, side + layer * 3) + o;
      SX[n] = q.x + ca * s - sa * w;
      SY[n] = q.y + sa * s + ca * w;
      n++;
    }
    if (side > 0) {                             // 둥근 앞머리 (부채꼴 끝 호를 크게 넘지 않게)
      const hw = Math.min(halfAt(q, reach, t, k, layer) * 0.5, q.len * 0.08);
      SX[n] = q.x + ca * (reach + hw);
      SY[n] = q.y + sa * (reach + hw);
      n++;
    }
  }
  closedSmooth(ctx, SX, SY, n);
}

// ---------------------------------------------------------------- 지나온 자리
// 지나온 자리에서 i 째 점이 지금으로부터 몇 초 전인지 0~1 (life 로 나눠)
const ageK = (a, i, now, life) => (now - a.trail.t(i)) / life;

/** 지나온 자리에 옅어지는 빛 번짐 (띠 대신 - 납작한 띠는 빛줄기처럼 보인다). 지금 혼합 그대로. */
function trailGlow(fx, ctx, tr, now, life, col, r0, a, step = 2) {
  for (let i = step; i < tr.n; i += step) {
    const k = (now - tr.t(i)) / life;
    if (!(k < 1)) break;
    fx.ink.glow(ctx, col, tr.x(i), tr.y(i), r0 * (1 - 0.5 * k), a * (1 - k));
  }
}

// ================================================================ 불
const flame = {
  shot(fx, ctx, q) {
    const { x, y, r } = q, P = firePal(q.c), t = fx.clock, b = flowOf(q.ux, q.uy, 0.35), bx = b.x, by = b.y;
    ctx.globalCompositeOperation = 'source-over';
    for (let i = 0; i < 3; i++) {               // 꼬리 끝에서 피어올라 커지며 옅어지는 연기
      const p = frac(q.age * 1.8 + i / 3 + hash(q.seed + i) * 0.2), d = r * (2.4 + 4 * p);
      fx.ink.soft(ctx, SMOKE, x + bx * d, y + by * d - p * r * 1.6, r * (0.7 + 1.2 * p), 0.55 * Math.sin(Math.PI * p));
    }
    ctx.globalCompositeOperation = 'lighter';
    trailGlow(fx, ctx, q.trail, t, 0.16, P.out, r * 1.6, 0.3);   // 지나온 길에 남는 열기
    fireball(fx, ctx, P, x, y, bx, by, r, q.seed, t, 1, 6);
  },
  trail(fx, q) {
    const P = firePal(q.c), r = q.r, b = flowOf(q.ux, q.uy, 0.6);
    for (let i = fx.perSec(24); i > 0; i--) {   // 떠오르는 불티
      const v = rnd(60, 160), a = Math.atan2(b.y, b.x) + rnd(-0.9, 0.9);
      const p = part(fx, 'spark', q.x + rnd(-0.6, 0.6) * r, q.y + rnd(-0.6, 0.6) * r, Math.cos(a) * v, Math.sin(a) * v,
        rnd(0.3, 0.55), rnd(5, 8), 0.5, Math.random() < 0.6 ? P.mid : P.hot, -90, 2.5);
      p.w = 1.6;
    }
    for (let i = fx.perSec(16); i > 0; i--) {   // 뒤로 남는 불꽃 혀
      part(fx, 'wisp', q.x + b.x * r, q.y + b.y * r, b.x * 40 + rnd(-20, 20), b.y * 40 - 30, rnd(0.2, 0.32),
        r * rnd(0.7, 1), 0.3, P.out, -160, 2);
    }
    for (let i = fx.perSec(8); i > 0; i--) {    // 연기
      part(fx, 'smoke', q.x + b.x * r * 2, q.y + b.y * r * 2, rnd(-20, 20), -30, rnd(0.55, 0.8), r * 0.9, 2.4, SMOKE,
        -40, 1.5, 0);
    }
  },
  launch(fx, q) {                               // 입에서 확 터지는 불
    const P = firePal(q.c);
    spray(fx, 7, 'wisp', q.x, q.y, q.ang, 1.4, 60, 180, 0.28, q.r * 1.1, 0.4, P.out, -200, 3);
    spray(fx, 3, 'smoke', q.x, q.y, q.ang + Math.PI, 2.5, 20, 60, 0.6, q.r * 1.2, 2, SMOKE, -50, 2, 0);
  },
  debris: 'flame',
  impact(fx, x, y, ang, c, info) {              // 불덩이가 터진다 - 솟는 불길 · 불티 · 연기 · 그을음
    const P = firePal(c), s = info.s || 1, big = info.why === 'hit' ? 1 : 1.3;
    part(fx, 'glow', x, y, 0, 0, 0.3, 34 * s * big, 2.4, P.out);
    for (let i = Math.round(14 * s * big); i > 0; i--) {    // 몸을 휘감고 솟는 불길
      const a = rnd(0, TAU), d = rnd(0, 22) * s, v = rnd(30, 120);
      part(fx, 'wisp', x + Math.cos(a) * d, y + Math.sin(a) * d * 0.7, Math.cos(a) * v, Math.sin(a) * v * 0.5 - 60,
        rnd(0.35, 0.6), rnd(20, 30) * s, 0.35, i % 3 ? P.out : P.mid, -240, 3);
    }
    spray(fx, Math.round(4 * s), 'wisp', x, y - 6, -Math.PI / 2, 1.2, 40, 120, 0.4, 16 * s, 0.3, P.hot, -200, 3);
    for (let i = Math.round(14 * s); i > 0; i--) {
      const a = ang + rnd(-1.6, 1.6) + (Math.random() < 0.3 ? Math.PI : 0), v = rnd(160, 380);
      part(fx, 'spark', x, y, Math.cos(a) * v, Math.sin(a) * v - 80, rnd(0.35, 0.7), rnd(6, 10), 0.4,
        Math.random() < 0.5 ? P.mid : P.hot, 140, 2.2).w = 2;
    }
    spray(fx, Math.round(4 * big), 'smoke', x, y - 24, -Math.PI / 2, 1.8, 30, 80, 0.95, 22 * s, 2.4, SMOKE, -50, 1.8, 0);
    part(fx, 'smoke', x, y + 10, 0, 0, 1.1, 30 * s * big, 1.1, SCORCH, 0, 0, 0);
  },

  // 화염방사 · 불꽃세례 - 입에서 뿜는 굵은 불길이 일렁이며 넓어진다
  cone(fx, ctx, q) {
    const P = firePal(q.c), t = fx.clock, ca = Math.cos(q.ang), sa = Math.sin(q.ang), tan = Math.tan(q.h);
    if (q.phase === 'mark') {                   // 입 앞의 불씨가 커지고 아지랑이가 앞으로 번진다
      const u = q.u, L = 18 + 46 * u;
      for (let i = 0; i < 3; i++) {
        const tw = (noise1(t * 9 + i * 3 + q.seed) - 0.5) * q.h * 1.2 + (i - 1) * q.h * 0.4;
        const d = q.ang + tw;
        addTongue(q.x + ca * 18, q.y + sa * 18, Math.cos(d), Math.sin(d) - 0.25, L * (0.6 + 0.5 * noise1(t * 7 + i)),
          7 + 6 * u, (noise1(t * 12 + i * 5) - 0.5) * 10);
      }
      flushTongues(ctx, P, 0.5 + 0.5 * u);
      ctx.globalCompositeOperation = 'lighter';
      for (let i = 1; i <= 3; i++) {            // 앞으로 번지는 열기
        const d = q.len * 0.22 * i * (0.4 + 0.6 * u);
        fx.ink.glow(ctx, P.out, q.x + ca * d, q.y + sa * d, 16 + d * Math.tan(q.h) * 0.8, 0.12 + 0.12 * u);
      }
      if (fx.perSec(30 * u)) {
        const d = q.ang + rnd(-q.h, q.h) * 0.6, v = rnd(80, 200);
        part(fx, 'spark', q.x + ca * 20, q.y + sa * 20, Math.cos(d) * v, Math.sin(d) * v - 40, 0.4, 7, 0.4, P.mid, -60, 2).w = 1.5;
      }
      return;
    }
    const e = q.e, reach = q.len * (0.25 + 0.67 * easeOut(clamp01(e / 0.45))), fade = 1 - smooth(clamp01((e - 0.7) / 0.3));
    ctx.globalCompositeOperation = 'source-over';
    for (let i = 0; i < 4; i++) {               // 끝에서 피어오르는 연기
      const p = frac(t * 1.4 + i / 4 + hash(q.seed + i)), s = reach * (0.75 + 0.3 * hash(q.seed + i * 3)), side = (hash(q.seed + i * 7) - 0.5) * 2;
      const hw = s * tan;
      fx.ink.soft(ctx, SMOKE, q.x + ca * s - sa * hw * side, q.y + sa * s + ca * hw * side - p * 50, 26 + 40 * p,
        0.45 * fade * Math.sin(Math.PI * p));
    }
    for (let i = 0; i < 4; i++) {               // 앞머리에서 위로 말려 올라가는 혀
      const side = (i / 3 - 0.5) * 2, s = reach * (0.82 + 0.1 * hash(q.seed + i)), hw = halfAt(q, s, t, 1, 0);
      addTongue(q.x + ca * s - sa * hw * side * 0.55, q.y + sa * s + ca * hw * side * 0.55, ca - side * sa * 0.5,
        sa + side * ca * 0.5 - 0.7,
        Math.min(85, hw * 0.75) * (0.75 + 0.6 * noise1(t * 8 + i * 2.7)), Math.min(26, hw * 0.3),
        (noise1(t * 10 + i) - 0.5) * Math.min(40, hw * 0.5));
    }
    for (let i = 0; i < 10; i++) {              // 옆으로 핥으며 흘러가는 작은 혀
      const side = i % 2 ? 1 : -1, p = frac(t * 1.6 + i / 10 + hash(q.seed + i) * 0.1), s = reach * (0.2 + 0.7 * p);
      const hw = halfAt(q, s, t, 1, side), nx = -sa * side, ny = ca * side;
      addTongue(q.x + ca * s + nx * hw * 0.7, q.y + sa * s + ny * hw * 0.7, nx * 0.8 + ca * 1.2, ny * 0.8 + sa * 1.2 - 0.3,
        Math.min(60, 12 + hw * 0.45) * Math.sin(Math.PI * p), Math.min(16, 4 + hw * 0.14),
        (noise1(t * 12 + i * 3) - 0.5) * 14);
    }
    flushTongues(ctx, P, fade, 0.6);           // 혀 밑동은 몸통이 덮는다 - 삐져나온 끝만 보인다
    ctx.globalCompositeOperation = 'source-over';
    streamPath(ctx, q, reach, 1, t, 0);
    fillPath(ctx, P.deep, 0.6 * fade);
    streamPath(ctx, q, reach * 0.98, 0.88, t * 1.1, 1);
    fillPath(ctx, P.out, 0.75 * fade);
    ctx.globalCompositeOperation = 'lighter';
    streamPath(ctx, q, reach * 0.86, 0.48, t * 1.25, 2);
    fillPath(ctx, P.mid, 0.85 * fade);
    streamPath(ctx, q, reach * 0.5, 0.2, t * 1.4, 3);
    fillPath(ctx, WHITE, 0.6 * fade);
    for (let i = 0; i < 12; i++) {              // 흘러가는 밝은 덩이 - 불길이 흐른다
      const p = frac(t * 2.6 + hash(q.seed + i)), s = p * reach, hw = halfAt(q, s, t, 1, 0);
      const o = (hash(q.seed + i * 5) - 0.5) * 1.4 * hw;
      fx.ink.glow(ctx, i % 3 ? P.out : P.mid, q.x + ca * s - sa * o, q.y + sa * s + ca * o, hw * 0.8 + 6, 0.5 * (1 - p) * fade);
    }
    fx.ink.core(ctx, P.hot, q.x + ca * 16, q.y + sa * 16, 34, fade);
    // 불길을 따라 퍼져 나가는 입자 - 장판이 지워진 뒤에도 잠깐 남아 사그라든다
    for (let i = fx.perSec(260 * fade); i > 0; i--) {
      const s = reach * Math.sqrt(Math.random()), hw = halfAt(q, s, t, 0.7, 0), o = rnd(-1, 1) * hw, v = rnd(180, 420);
      part(fx, 'glow', q.x + ca * s - sa * o, q.y + sa * s + ca * o, ca * v - sa * o, sa * v + ca * o - 40, rnd(0.25, 0.45),
        hw * 0.55 + 6, 1.5, Math.random() < 0.7 ? P.out : P.mid, -90, 2);
    }
    for (let i = fx.perSec(50 * fade); i > 0; i--) {
      const d = q.ang + rnd(-1, 1) * q.h, v = rnd(300, 700);
      part(fx, 'spark', q.x + ca * 20, q.y + sa * 20, Math.cos(d) * v, Math.sin(d) * v, rnd(0.3, 0.5), 8, 0.4, P.hot, -120, 2.5)
        .w = 1.8;
    }
    for (let i = fx.perSec(18 * fade); i > 0; i--) {
      const s = reach * rnd(0.5, 1), o = rnd(-1, 1) * s * tan;
      part(fx, 'smoke', q.x + ca * s - sa * o, q.y + sa * s + ca * o, ca * 60, sa * 60 - 50, rnd(0.6, 0.9), 24, 2.2, SMOKE,
        -30, 1.5, 0);
    }
  },

  // 분연 · 불꽃 터뜨리기 - 바깥으로 번지는 불의 벽
  ring(fx, ctx, q) {
    const P = firePal(q.c), t = fx.clock;
    if (q.phase === 'mark') {                   // 발밑에 불이 차오른다
      const u = q.u;
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.glow(ctx, P.out, q.x, q.y + 10, 40 + q.r * 0.3 * u, 0.25 + 0.35 * u);
      flameRing(ctx, P, q.x, q.y + 12, BODY_R + 4, 9, 14 + 26 * u, q.seed, t, 0.4 + 0.6 * u, 0.25);
      if (fx.perSec(40 * u)) {
        part(fx, 'spark', q.x + rnd(-30, 30), q.y + rnd(0, 20), rnd(-30, 30), rnd(-160, -60), 0.6, 7, 0.4, P.mid, -40, 1).w = 1.5;
      }
      return;
    }
    const { e, rr } = q, a = 1 - smooth(clamp01((e - 0.45) / 0.55));
    ctx.globalCompositeOperation = 'source-over';
    fx.ink.soft(ctx, SCORCH, q.x, q.y, rr * 0.95, 0.4 * a);
    ring(ctx, P.deep, 0.75 * a, 14 + 14 * (1 - e), q.x, q.y, rr);   // 끊기지 않는 불 띠
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, P.out, q.x, q.y, rr * 1.1, 0.4 * a);
    ring(ctx, P.out, 0.85 * a, 9 + 9 * (1 - e), q.x, q.y, rr);
    ring(ctx, P.mid, 0.9 * a, 3 + 4 * (1 - e), q.x, q.y, rr);
    for (let i = 0; i < 10; i++) {              // 안쪽에 남아 타는 땅
      const th = hash(q.seed + i) * TAU, d = rr * (0.3 + 0.6 * hash(q.seed + i * 3));
      fx.ink.glow(ctx, i % 2 ? P.out : P.mid, q.x + Math.cos(th) * d, q.y + Math.sin(th) * d, 10 + 8 * noise1(t * 6 + i), 0.5 * a);
    }
    const n = Math.max(16, Math.min(44, Math.round(rr / 6)));
    flameRing(ctx, P, q.x, q.y, rr, n, 34 + 44 * (1 - e), q.seed, t, a, 0.75);
    for (let i = fx.perSec(140 * a); i > 0; i--) {
      const th = rnd(0, TAU), cx = Math.cos(th), cy = Math.sin(th);
      part(fx, 'wisp', q.x + cx * rr, q.y + cy * rr, cx * 80, cy * 50 - 60, rnd(0.25, 0.4), rnd(12, 18), 0.3, P.out,
        -200, 2);
    }
    for (let i = fx.perSec(60 * a); i > 0; i--) {
      const th = rnd(0, TAU);
      part(fx, 'spark', q.x + Math.cos(th) * rr, q.y + Math.sin(th) * rr, Math.cos(th) * 200, -rnd(80, 260),
        rnd(0.4, 0.7), 8, 0.4, P.hot, 160, 1.5).w = 2;
    }
  },

  // 불꽃의 맹세 · 마그마스톰 - 하늘에서 떨어진 불덩이가 기둥으로 터진다
  tele(fx, ctx, q) {
    const P = firePal(q.c), t = fx.clock;
    if (q.phase === 'mark') {                   // 달아오르는 땅 + 피어오르는 불씨
      const u = q.u;
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.glow(ctx, P.out, q.x, q.y, q.r * (0.6 + 0.5 * u), 0.15 + 0.4 * u);
      for (let i = 0; i < 6; i++) {
        const p = frac(t * 0.9 + hash(q.seed + i)), th = hash(q.seed + i * 3) * TAU, d = q.r * 0.7 * hash(q.seed + i * 5);
        fx.ink.glow(ctx, P.mid, q.x + Math.cos(th) * d, q.y + Math.sin(th) * d * 0.6 - p * 40, 5, u * Math.sin(Math.PI * p));
      }
      return;
    }
    const e = q.e, a = 1 - smooth(clamp01((e - 0.5) / 0.5)), up = easeOut(clamp01(e / 0.35));
    ctx.globalCompositeOperation = 'source-over';
    fx.ink.soft(ctx, SCORCH, q.x, q.y, q.r * 1.1, 0.5 * a);
    for (let i = 0; i < 4; i++) {               // 기둥 위로 피는 연기
      const k = i / 3;
      fx.ink.soft(ctx, SMOKE, q.x + (k - 0.5) * q.r * 0.8, q.y - q.r * (1.2 + 1.2 * up) - k * 20, q.r * (0.5 + 0.4 * up),
        0.45 * a * up);
    }
    for (let i = 0; i < 7; i++) {               // 솟구치는 불기둥 - 가운데가 가장 높다
      const k = (i - 3) / 3, f = noise1(t * 9 + i * 2.3 + q.seed);
      addTongue(q.x + k * q.r * 0.5, q.y + 4, k * 0.25 + (f - 0.5) * 0.3, -1, q.r * (1.1 + 1.6 * up) * (1 - Math.abs(k) * 0.45) *
        (0.75 + 0.5 * f), q.r * (0.3 - 0.08 * Math.abs(k)), (noise1(t * 12 + i) - 0.5) * q.r * 0.5);
    }
    flushTongues(ctx, P, a);
    flameRing(ctx, P, q.x, q.y, q.r * (0.55 + 0.55 * up), 16, 22 * (1 - e) + 8, q.seed, t, a, 0.8);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.core(ctx, P.hot, q.x, q.y - 10, q.r * 1.4 * (1 - e), 1 - e);
  },
  fall(fx, ctx, q, x, y, v) {                   // 하늘에서 떨어지는 불덩이 - 불길은 위로 끌린다
    const P = firePal(q.c), r = q.r * 0.32 * (0.6 + 0.4 * v);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, P.out, x, y - r, r * 3, 0.3 + 0.3 * v);
    fireball(fx, ctx, P, x, y, 0.08, -1, r, q.seed, fx.clock, 0.5 + 0.5 * v, 5, 1.6);
  },

  // 플레어드라이브 · 니트로차지 - 몸이 불덩이가 되어 달린다
  rush(fx, ctx, a) {
    const P = firePal(a.c), t = fx.clock, sd = a.seed * 10;
    if (a.stage === 'wind') {                   // 몸 둘레로 불이 붙는다
      flameRing(ctx, P, a.x, a.y + 14, BODY_R * 0.9, 8, 14 + 30 * a.sk, sd, t, 0.4 + 0.6 * a.sk, 0.2);
      return;
    }
    const fade = a.stage === 'tail' ? 1 - a.sk : 1, now = t;
    ctx.globalCompositeOperation = 'lighter';
    trailGlow(fx, ctx, a.trail, now, 0.28, P.out, BODY_R * 1.8, 0.35 * fade);
    for (let i = 1; i < a.trail.n; i += 2) {    // 지나간 땅에 잠깐 남는 불
      const k = ageK(a, i, now, 0.35);
      if (!(k < 1)) break;
      addTongue(a.trail.x(i), a.trail.y(i) + 16, (noise1(t * 6 + i) - 0.5) * 0.6, -1, 34 * (1 - k) * (0.6 + 0.7 * noise1(t * 9 + i * 2)),
        9 * (1 - k) + 3, (noise1(t * 11 + i) - 0.5) * 12);
    }
    flushTongues(ctx, P, fade);
    const b = flowOf(a.ux, a.uy, 0.25), st = 1 + clamp01(a.speed / 1200) * 0.8;   // 몸은 보이게 - 불길은 몸 뒤로
    fireball(fx, ctx, P, a.x - a.ux * BODY_R * 1.4, a.y - a.uy * BODY_R * 1.4, b.x, b.y, BODY_R * 0.8, sd, t, 0.85 * fade, 6, st);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, P.out, a.x, a.y, BODY_R * 2, 0.45 * fade);
    crescent(ctx, a.x, a.y, BODY_R * 1.25, a.ang - 1.1, a.ang + 1.1, BODY_R * 0.3);   // 앞을 가르는 불 테
    fillPath(ctx, P.mid, 0.7 * fade);
    for (let i = fx.perSec(50 * fade); i > 0; i--) {
      const d = Math.atan2(b.y, b.x) + rnd(-1, 1), v = rnd(80, 220);
      part(fx, 'spark', a.x + rnd(-20, 20), a.y + rnd(-20, 20), Math.cos(d) * v, Math.sin(d) * v, rnd(0.3, 0.5), 7, 0.4,
        P.mid, -100, 2).w = 1.6;
    }
  },
  swing(fx, ctx, a, t) {                        // 앞에서 확 퍼지는 불꽃 부채
    const P = firePal(a.c), e = easeOut(Math.min(1, t * 1.8)), fade = t > 0.5 ? (1 - t) / 0.5 : 1;
    const hx = a.x + a.ux * BODY_R * 0.8, hy = a.y + a.uy * BODY_R * 0.8;
    for (let i = 0; i < 5; i++) {
      const d = a.ang + (i - 2) * 0.42 + (noise1(fx.clock * 8 + i) - 0.5) * 0.2;
      addTongue(hx, hy, Math.cos(d), Math.sin(d) - 0.2, a.reach * (0.5 + 0.6 * e) * (i === 2 ? 1.15 : 0.85), 12 + 6 * e,
        (noise1(fx.clock * 12 + i * 3) - 0.5) * 16);
    }
    flushTongues(ctx, P, fade);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.core(ctx, P.hot, hx + a.ux * 20, hy + a.uy * 20, 40 * (1 - t) + 6, fade);
    if (!a.mem.hit && t > 0.15) {
      a.mem.hit = true;
      flame.impact(fx, a.x + a.ux * a.reach * 0.7, a.y + a.uy * a.reach * 0.7, a.ang, a.c, { why: 'hit', s: 0.8 });
    }
  },
};

// ================================================================ 번개
const zap = {
  shot(fx, ctx, q) {
    const { x, y, r, c } = q, t = fx.clock, R = flicker(q.seed, t, 22);
    ctx.globalCompositeOperation = 'lighter';
    trailGlow(fx, ctx, q.trail, t, 0.12, c.dark, r * 1.5, 0.35);
    fx.ink.glow(ctx, c.dark, x, y, r * 3.4, 0.55);
    ctx.beginPath();                            // 지나온 쪽으로 꺾인 꼬리 번개
    boltTree(ctx, x, y, x - q.ux * r * 5.5, y - q.uy * r * 5.5, 7, r * 0.7, R, 1);
    zapStroke(ctx, c, r * 0.1 + 0.8, 0.75);
    ctx.beginPath();                            // 몸에서 사방으로 튀는 가지 번개 - 1/22초마다 다시
    const n = 3 + Math.floor(R() * 2);
    for (let i = 0; i < n; i++) {
      const a = R() * TAU, L = r * (1.5 + R() * 1.3);
      boltTree(ctx, x + Math.cos(a) * r * 0.3, y + Math.sin(a) * r * 0.3, x + Math.cos(a) * L, y + Math.sin(a) * L, 4,
        r * 0.4, R, R() < 0.5 ? 1 : 0);
    }
    zapStroke(ctx, c, r * 0.08 + 0.7, 1);
    fx.ink.core(ctx, c.light, x, y, r * 1.6, 1);
    fx.ink.star(ctx, WHITE, x, y, r * (1.7 + 0.7 * R()), 0.85);
  },
  trail(fx, q) {
    const c = q.c;
    for (let i = fx.perSec(30); i > 0; i--) {   // 사방으로 튀는 불꽃
      const a = Math.random() * TAU, v = rnd(140, 340);
      part(fx, 'spark', q.x + rnd(-0.5, 0.5) * q.r, q.y + rnd(-0.5, 0.5) * q.r, Math.cos(a) * v, Math.sin(a) * v,
        rnd(0.12, 0.22), rnd(6, 9), 0.4, Math.random() < 0.5 ? WHITE : c.light, 0, 6).w = 1.5;
    }
    if (fx.perSec(8)) {                         // 남는 작은 번개
      const p = part(fx, 'bolt', q.x - q.ux * q.r * 2, q.y - q.uy * q.r * 2, 0, 0, 0.12, q.r * 2, 1, c.light);
      p.rot = Math.random() * TAU;
      p.w = 1.5;
    }
  },
  launch(fx, q) {
    spray(fx, 8, 'spark', q.x, q.y, q.ang, 1.8, 200, 420, 0.18, 9, 0.4, WHITE, 0, 6);
    for (let i = 0; i < 3; i++) {
      const p = part(fx, 'bolt', q.x, q.y, 0, 0, 0.14, q.r * 2.4, 1, q.c.light);
      p.rot = q.ang + rnd(-1.2, 1.2);
      p.w = 2;
    }
  },
  debris: 'zap',
  impact(fx, x, y, ang, c, info) {              // 지직 - 사방으로 튀는 번개 · 불꽃 + 번쩍
    const s = info.s || 1;
    part(fx, 'star', x, y, 0, 0, 0.14, 46 * s, 1.4, WHITE);
    part(fx, 'glow', x, y, 0, 0, 0.25, 40 * s, 2.2, c.dark);
    for (let i = Math.round(9 * s); i > 0; i--) {
      const a = Math.random() * TAU, v = rnd(80, 220), p = part(fx, 'bolt', x, y, Math.cos(a) * v, Math.sin(a) * v,
        rnd(0.16, 0.28), rnd(26, 42) * s, 1.2, Math.random() < 0.3 ? WHITE : c.light, 0, 6);
      p.rot = a;
      p.w = 2.2;
    }
    spray(fx, Math.round(16 * s), 'spark', x, y, ang, 4, 260, 520, 0.24, 10, 0.4, WHITE, 0, 5);
    const w = fx.spawn('ring', x, y, 0, 0, 0.22, 10, c.light);
    w.size1 = 80 * s;
    w.w = 3;
    if (info.why !== 'tele') return;
    // 번개 (내려찍기): 하늘에서 내리친 줄기가 잔상으로 잠깐 남고, 화면이 번쩍
    let px = x + rnd(-40, 40), py = y - FALL_H * 1.5;
    for (let i = 1; i <= 9; i++) {
      const k = i / 9, nx = i < 9 ? x + rnd(-26, 26) * (1 - k * 0.7) : x, ny = py + (y - py) * (1 / (10 - i));
      for (const [col, wd] of [[c.light, 7], [WHITE, 2.5]]) {
        const l = fx.spawn('line', px, py, 0, 0, 0.26, 1, col);
        l.x2 = nx;
        l.y2 = ny;
        l.w = wd;
      }
      px = nx;
      py = ny;
    }
    for (let i = 0; i < 4; i++) {               // 땅을 기는 번개
      const p = part(fx, 'bolt', x, y, 0, 0, 0.3, rnd(50, 90), 1, c.light);
      p.rot = (i / 4) * TAU + rnd(-0.4, 0.4);
      p.w = 2.5;
    }
    spray(fx, 10, 'smoke', x, y, -Math.PI / 2, 2.4, 30, 90, 0.8, 22, 2.2, SMOKE, -40, 2, 1);
    fx.kick(0.08, 0.02, 0.12, WHITE);
  },

  // 번개 (내려찍기) - 표시 동안 땅에 정전기가 기고, 하늘에 빛이 모인다
  tele(fx, ctx, q) {
    const { c } = q, t = fx.clock;
    if (q.phase === 'mark') {
      const u = q.u;
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.glow(ctx, c.dark, q.x, q.y, q.r * (0.4 + 0.5 * u), 0.2 + 0.4 * u);
      crawl(ctx, c, q.x, q.y, q.r * (0.3 + 0.5 * u), 1 + Math.round(2 * u), flicker(q.seed, t, 12), 0.8, 0.3 + 0.5 * u, 0.55);
      return;
    }
    const e = q.e, R = flicker(q.seed, t, 30), on = 0.55 + 0.45 * (hash(Math.floor(t * 30) + q.seed) > 0.3 ? 1 : 0);
    const a = (1 - e) * on, top = q.y - FALL_H * 1.6;
    ctx.globalCompositeOperation = 'source-over';
    fx.ink.soft(ctx, INK, q.x, q.y, q.r * 0.9, 0.5);          // 그을린 자리
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, c.dark, q.x, q.y, q.r * 2.4, 0.6 * (1 - e));
    streak(fx, ctx, c.light, q.x, (q.y + top) / 2, Math.PI / 2, (q.y - top) / 2, 26, 0.35 * a);
    ctx.beginPath();                            // 하늘에서 내리치는 줄기 + 곁가지
    boltTree(ctx, q.x + (R() - 0.5) * 60, top, q.x, q.y, 10, 30, R, 3);
    zapStroke(ctx, c, 3.2 * (1 - 0.5 * e), a);
    ctx.beginPath();                            // 땅으로 퍼지는 번개 (납작하게)
    for (let i = 0; i < 6; i++) {
      const th = (i / 6) * TAU + R() * 0.6, L = q.r * (0.7 + 0.7 * e) * (0.7 + 0.5 * R());
      jag(ctx, q.x, q.y, q.x + Math.cos(th) * L, q.y + Math.sin(th) * L * 0.55, 4, 10, R);
    }
    zapStroke(ctx, c, 1.4, a);
    fx.ink.core(ctx, c.light, q.x, q.y, q.r * 1.5 * (1 - e) + 8, 1 - e);
  },
  fall(fx, ctx, q, x, y, v) {                   // 하늘에 모이는 빛 → 떨어지기 직전 가는 선행 번개
    const { c } = q, t = fx.clock, sy = q.y - FALL_H, R = flicker(q.seed, t, 16);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, c.dark, q.x, sy, q.r * (0.5 + 0.5 * v), 0.3 + 0.4 * v);
    fx.ink.core(ctx, c.light, q.x, sy, q.r * 0.3 * (0.5 + v), 0.4 + 0.6 * v);
    crawl(ctx, c, q.x, sy, q.r * 0.5, 2, R, 0.8, v);
    if (v < 0.5) return;
    const k = ((v - 0.5) / 0.5) ** 1.5;
    ctx.beginPath();
    jag(ctx, q.x, sy, q.x + (R() - 0.5) * 30, sy + (q.y - sy) * k, 6, 18, R);
    zapStroke(ctx, c, 0.6, 0.4 * k + 0.1);
  },

  // 방전 - 몸에서 사방으로 뻗는 번개 + 가장자리를 도는 번개 테
  ring(fx, ctx, q) {
    const { c } = q, t = fx.clock;
    if (q.phase === 'mark') {
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.glow(ctx, c.dark, q.x, q.y, BODY_R * 2, 0.3 + 0.4 * q.u);
      crawl(ctx, c, q.x, q.y, BODY_R + 12, 2 + Math.round(3 * q.u), flicker(q.seed, t, 15), 1.1, 0.5 + 0.5 * q.u);
      return;
    }
    const { e, rr } = q, R = flicker(q.seed, t, 20), a = 1 - smooth(clamp01((e - 0.4) / 0.6));
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, c.dark, q.x, q.y, rr * 1.1, 0.35 * a);
    ctx.beginPath();
    for (let i = 0; i < 8; i++) {
      const th = (i / 8) * TAU + R() * 0.5, L = rr * (0.85 + 0.2 * R());
      boltTree(ctx, q.x + Math.cos(th) * BODY_R, q.y + Math.sin(th) * BODY_R, q.x + Math.cos(th) * L, q.y + Math.sin(th) * L,
        6, 16, R, 1);
    }
    zapStroke(ctx, c, 1.6, a);
    ctx.beginPath();                            // 가장자리 번개 테
    const n = 30;
    for (let i = 0; i <= n; i++) {
      const th = (i / n) * TAU, rj = rr + (i % n ? (R() - 0.5) * 18 : 0);
      ctx.lineTo(q.x + Math.cos(th) * rj, q.y + Math.sin(th) * rj);
    }
    zapStroke(ctx, c, 1.3, a * 0.9);
    fx.ink.core(ctx, c.light, q.x, q.y, 50 * (1 - e) + 10, a);
    for (let i = fx.perSec(80 * a); i > 0; i--) {
      const th = rnd(0, TAU), v = rnd(100, 300);
      part(fx, 'spark', q.x + Math.cos(th) * rr, q.y + Math.sin(th) * rr, Math.cos(th) * v, Math.sin(th) * v, 0.2, 9, 0.4,
        WHITE, 0, 5).w = 1.6;
    }
  },

  // 전기 광선 (전자포 따위) - 꿈틀대는 번개 다발
  beam(fx, ctx, q) {
    const { c } = q, t = fx.clock, R = flicker(q.seed, t, 24), ca = Math.cos(q.ang), sa = Math.sin(q.ang);
    if (q.phase === 'mark') {
      crawl(ctx, c, q.x + ca * 20, q.y + sa * 20, 16 + 10 * q.u, 2, R, 0.8, 0.4 + 0.6 * q.u);
      return;
    }
    const a = 1 - q.e, ex = q.x + ca * q.len, ey = q.y + sa * q.len;
    ctx.globalCompositeOperation = 'lighter';
    streak(fx, ctx, c.dark, (q.x + ex) / 2, (q.y + ey) / 2, q.ang, q.len / 2, q.W * 0.9, 0.5 * a);
    ctx.beginPath();
    for (let i = 0; i < 3; i++) boltTree(ctx, q.x, q.y, ex, ey, 14, q.W * 0.45, R, 2);
    zapStroke(ctx, c, 1.6 + q.W * 0.03, a);
    fx.ink.core(ctx, c.light, q.x, q.y, q.W * 1.2, a);
    fx.ink.core(ctx, c.light, ex, ey, q.W * 1.4, a);
  },

  // 와일드볼트 · 볼트태클 · 스파크 - 번개를 두르고 달린다
  rush(fx, ctx, a) {
    const { c } = a, t = fx.clock, R = flicker(a.seed, t, 20);
    if (a.stage === 'wind') {
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.glow(ctx, c.dark, a.x, a.y, BODY_R * (1.5 + a.sk), 0.3 + 0.4 * a.sk);
      crawl(ctx, c, a.x, a.y, BODY_R + 4, 2 + Math.round(2 * a.sk), R, 0.9, 0.5 + 0.5 * a.sk);
      return;
    }
    const fade = a.stage === 'tail' ? 1 - a.sk : 1, tr = a.trail;
    ctx.globalCompositeOperation = 'lighter';
    trailGlow(fx, ctx, tr, t, 0.22, c.dark, BODY_R * 1.4, 0.35 * fade);   // 지나온 자리의 잔광
    ctx.beginPath();                            // 지나온 자리를 따라 꺾인 번개
    let n = 0;
    for (let i = 0; i < tr.n && ageK(a, i, t, 0.25) < 1; i++) {
      const o = i ? (R() - 0.5) * 30 : 0;
      ctx.lineTo(tr.x(i) - a.uy * o, tr.y(i) + a.ux * o);
      n++;
    }
    if (n > 1) zapStroke(ctx, c, 1.6, fade);
    fx.ink.glow(ctx, c.dark, a.x, a.y, BODY_R * 2.2, 0.4 * fade);
    crawl(ctx, c, a.x, a.y, BODY_R + 6, 3, R, 1, fade);
    for (let i = fx.perSec(60 * fade); i > 0; i--) {
      const th = rnd(0, TAU), v = rnd(120, 320);
      part(fx, 'spark', a.x + Math.cos(th) * BODY_R, a.y + Math.sin(th) * BODY_R, Math.cos(th) * v - a.ux * 200,
        Math.sin(th) * v - a.uy * 200, 0.18, 8, 0.4, Math.random() < 0.5 ? WHITE : c.light, 0, 5).w = 1.5;
    }
  },
  swing(fx, ctx, a, t) {                        // 부딪친 앞에서 터지는 번개 부채
    const { c } = a, R = flicker(a.seed, fx.clock, 24), fade = t > 0.4 ? (1 - t) / 0.6 : 1, e = easeOut(Math.min(1, t * 2));
    const hx = a.x + a.ux * BODY_R, hy = a.y + a.uy * BODY_R;
    ctx.globalCompositeOperation = 'lighter';
    ctx.beginPath();
    for (let i = 0; i < 5; i++) {
      const d = a.ang + (i - 2) * 0.45 + (R() - 0.5) * 0.3, L = a.reach * (0.4 + 0.6 * e) * (0.7 + 0.4 * R());
      boltTree(ctx, hx, hy, hx + Math.cos(d) * L, hy + Math.sin(d) * L, 5, 12, R, 1);
    }
    zapStroke(ctx, c, 1.5, fade);
    fx.ink.core(ctx, c.light, hx, hy, 46 * (1 - t) + 8, fade);
    fx.ink.star(ctx, WHITE, hx, hy, 50 * (1 - t), fade);
    if (!a.mem.hit && t > 0.1) {
      a.mem.hit = true;
      zap.impact(fx, a.x + a.ux * a.reach * 0.7, a.y + a.uy * a.reach * 0.7, a.ang, c, { why: 'hit', s: 0.7 });
    }
  },
};

// ================================================================ 풀 · 꽃잎
// 잎 무리 (탄 · 돌진 · 고리가 같이 쓴다): (x, y) 둘레를 느슨하게 돌며, (ux, uy) 쪽 뒤로 처진다
function flock(fx, ctx, L, x, y, ux, uy, r, n, seed, t, a, petal, lag = 0.55) {
  const px = -uy, py = ux;
  for (let i = 0; i < n; i++) {
    const h1 = hash(seed + i * 7.1), h2 = hash(seed + i * 3.3), h3 = hash(seed + i * 11.7);
    const th = h1 * TAU + t * (5 + 4 * h2) * (i % 2 ? 1 : -1), rho = r * (0.45 + 0.75 * h3);
    const back = r * lag * i + Math.sin(t * 4 + i) * r * 0.2;
    const lx = x - ux * back + px * Math.sin(th) * rho + ux * Math.cos(th) * rho * 0.45;
    const ly = y - uy * back + py * Math.sin(th) * rho + uy * Math.cos(th) * rho * 0.45;
    const rot = h2 * TAU + t * (9 + 8 * h1) * (h3 < 0.5 ? 1 : -1), flip = t * (6 + 5 * h3) + h1 * 9;
    drawLeaf(fx, ctx, L, lx, ly, r * (0.85 + 0.35 * h2) * (petal ? 0.75 : 1), rot, flip, a, petal);
  }
}

// 지나온 쪽으로 감기는 초록 회오리 두 가닥
function swirl(ctx, col, x, y, ux, uy, r, t, seed, a) {
  const px = -uy, py = ux, len = r * 6.5;
  for (let s = 0; s < 2; s++) {
    for (let seg = 0; seg < 3; seg++) {
      ctx.beginPath();
      for (let j = 0; j <= 5; j++) {
        const d = r * 0.4 + ((seg * 5 + j) / 15) * len, k = d / len;
        const off = Math.sin(d / r * 1.3 - t * 15 + s * Math.PI + seed) * r * 0.95 * (1 - k * 0.6);
        ctx.lineTo(x - ux * d + px * off, y - uy * d + py * off);
      }
      strokePath(ctx, col, 2.4 - seg * 0.6, a * (0.5 - seg * 0.15));
    }
  }
}

const leaf = {
  shot(fx, ctx, q) {
    const { x, y, r } = q, petal = isPetal(q), L = deepPal(leafPal(q)), t = fx.clock;
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, L.light, x - q.ux * r, y - q.uy * r, r * 2.8, 0.3);
    swirl(ctx, L.light, x, y, q.ux, q.uy, r, t, q.seed, 1);
    flock(fx, ctx, L, x, y, q.ux, q.uy, r, 3 + Math.floor(hash(q.seed) * 3), q.seed, q.age + q.seed * 0.01, 1, petal);
  },
  trail(fx, q) {
    const L = deepPal(leafPal(q)), petal = isPetal(q);
    for (let i = fx.perSec(7); i > 0; i--) {   // 떨어져 나가 팔랑이는 잎
      const p = part(fx, 'leaf', q.x + rnd(-1, 1) * q.r, q.y + rnd(-1, 1) * q.r, -q.vx * 0.1 + rnd(-40, 40),
        -q.vy * 0.1 + rnd(-40, 40), rnd(0.5, 0.8), rnd(5, 7) * (petal ? 0.8 : 1), 1, Math.random() < 0.6 ? L.light : L.dark, 50, 2.5);
      p.vr = rnd(-14, 14);
      p.rot = Math.random() * TAU;
    }
    for (let i = fx.perSec(14); i > 0; i--) {
      part(fx, 'glow', q.x + rnd(-1, 1) * q.r, q.y + rnd(-1, 1) * q.r, rnd(-20, 20), rnd(-20, 20), rnd(0.3, 0.5), 4, 0.4,
        L.light, 0, 2);
    }
  },
  launch(fx, q) {
    const L = deepPal(leafPal(q));
    for (let i = 0; i < 5; i++) {
      const a = q.ang + rnd(-0.9, 0.9), v = rnd(80, 200);
      const p = part(fx, 'leaf', q.x, q.y, Math.cos(a) * v, Math.sin(a) * v, rnd(0.4, 0.6), 6, 1, L.light, 40, 3);
      p.vr = rnd(-16, 16);
    }
  },
  debris: 'leaf',
  impact(fx, x, y, ang, c, info) {              // 잎이 흩날리고 베인 빛이 번쩍
    const s = info.s || 1, L = deepPal(info.ty === 'FAIRY' || PETAL_RE.test(String(info.k)) ? (info.ty === 'FAIRY' ? c : PETAL) : c);
    for (let i = Math.round(14 * s); i > 0; i--) {
      const a = ang + rnd(-2, 2), v = rnd(120, 300);
      const p = part(fx, 'leaf', x, y, Math.cos(a) * v, Math.sin(a) * v - 60, rnd(0.6, 1), rnd(6, 9), 1,
        Math.random() < 0.6 ? L.light : L.dark, 160, 2.6);
      p.vr = rnd(-18, 18);
      p.rot = Math.random() * TAU;
    }
    for (let i = 0; i < 4; i++) {               // 베인 자국 - 엇갈린 빛줄
      const a = ang + Math.PI / 2 + rnd(-0.6, 0.6), d = rnd(18, 30) * s, p = fx.spawn('line', x - Math.cos(a) * d,
        y - Math.sin(a) * d, 0, 0, 0.16, 1, WHITE);
      p.x2 = x + Math.cos(a) * d;
      p.y2 = y + Math.sin(a) * d;
      p.w = 3;
    }
    part(fx, 'glow', x, y, 0, 0, 0.3, 30 * s, 2.2, L.light);
    const w = fx.spawn('ring', x, y, 0, 0, 0.35, 12, L.light);
    w.size1 = 70 * s;
    w.w = 3;
  },

  // 잎이 부채꼴로 휘몰아친다 (풀 부채꼴은 드물다 - 갤러리 · 타입이 바뀐 기술)
  cone(fx, ctx, q) {
    const L = deepPal(leafPal(q)), petal = isPetal(q), t = fx.clock, ca = Math.cos(q.ang), sa = Math.sin(q.ang);
    const tan = Math.tan(q.h);
    if (q.phase === 'mark') {
      flock(fx, ctx, L, q.x + ca * 34, q.y + sa * 34, ca, sa, 10 + 6 * q.u, 4, q.seed, t, 0.4 + 0.6 * q.u, petal, 0);
      return;
    }
    const reach = q.len * (0.3 + 0.75 * easeOut(clamp01(q.e / 0.5))), a = 1 - smooth(clamp01((q.e - 0.6) / 0.4));
    ctx.globalCompositeOperation = 'lighter';
    streak(fx, ctx, L.light, q.x + ca * reach * 0.5, q.y + sa * reach * 0.5, q.ang, reach * 0.55, reach * tan * 0.6, 0.25 * a);
    for (let i = 0; i < 5; i++) {               // 휘감아 나가는 바람 줄기
      const o = (i / 4 - 0.5) * 1.5, p = frac(t * 1.5 + i * 0.37);
      ctx.beginPath();
      for (let j = 0; j <= 10; j++) {
        const s = 30 + (reach - 30) * (j / 10), w = (o + Math.sin(j * 0.9 - t * 9 + i * 2) * 0.25) * s * tan;
        ctx.lineTo(q.x + ca * s - sa * w, q.y + sa * s + ca * w);
      }
      strokePath(ctx, L.light, 2, 0.45 * a * (0.5 + 0.5 * Math.sin(p * TAU)));
    }
    for (let i = 0; i < 20; i++) {
      const p = frac(t * 1.8 + hash(q.seed + i)), s = 24 + p * (reach - 24), o = (hash(q.seed + i * 5) - 0.5) * 1.8 * s * tan;
      drawLeaf(fx, ctx, L, q.x + ca * s - sa * o, q.y + sa * s + ca * o, 10 + 5 * hash(i), t * 12 + i * 2, t * 9 + i,
        a * Math.sin(Math.PI * clamp01(p * 1.1)), petal);
    }
  },

  // 잎이 둘레를 돌며 퍼진다 - 회오리 호 + 도는 잎
  ring(fx, ctx, q) {
    const L = deepPal(leafPal(q)), petal = isPetal(q), t = fx.clock;
    if (q.phase === 'mark') {
      flock(fx, ctx, L, q.x, q.y, 0, -1, BODY_R * 1.5, 5, q.seed, t, 0.4 + 0.6 * q.u, petal, 0);
      return;
    }
    const a = 1 - smooth(clamp01((q.e - 0.5) / 0.5)), rr = q.rr;
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, L.light, q.x, q.y, rr, 0.22 * a);
    for (let i = 0; i < 6; i++) {               // 도는 바람 호
      const a0 = (i / 6) * TAU + t * 4 + q.seed, R = rr * (0.75 + 0.2 * (i % 2));
      ctx.beginPath();
      ctx.arc(q.x, q.y, R, a0, a0 + 0.7);
      strokePath(ctx, L.light, 2.5, 0.5 * a);
    }
    for (let i = 0; i < 24; i++) {
      const th = (i / 24) * TAU + t * 3 + q.seed, R = rr * (0.8 + 0.25 * hash(q.seed + i));
      drawLeaf(fx, ctx, L, q.x + Math.cos(th) * R, q.y + Math.sin(th) * R, 11 + 4 * hash(i), th + Math.PI / 2 + t * 6,
        t * 8 + i * 1.3, a, petal);
    }
  },

  // 풀의 맹세 - 땅에서 풀잎이 솟는다 (표시 동안엔 새싹만)
  tele(fx, ctx, q) {
    const L = deepPal(leafPal(q)), t = fx.clock, mark = q.phase === 'mark';
    const grow = mark ? 0.18 * q.u : easeOut(clamp01(q.e / 0.25)), a = mark ? 0.7 : 1 - smooth(clamp01((q.e - 0.5) / 0.5));
    ctx.globalCompositeOperation = 'source-over';
    ctx.beginPath();
    for (let i = 0; i < 13; i++) {              // 휘어진 풀잎 (뾰족한 잎몸)
      const th = hash(q.seed + i) * TAU, d = q.r * (0.1 + 0.75 * hash(q.seed + i * 3)), bx = q.x + Math.cos(th) * d;
      const by = q.y + Math.sin(th) * d, h = q.r * (0.9 + 1.0 * hash(i * 5.1)) * grow, w = (mark ? 2.5 : 5) + 3 * hash(i);
      const bend = (hash(q.seed + i * 9) - 0.5) * h * 0.7 + Math.sin(t * 3 + i) * 4;
      ctx.moveTo(bx - w, by);
      ctx.quadraticCurveTo(bx - w * 0.3 + bend * 0.4, by - h * 0.5, bx + bend, by - h);
      ctx.quadraticCurveTo(bx + w * 0.3 + bend * 0.4, by - h * 0.5, bx + w, by);
      ctx.closePath();
    }
    fillPath(ctx, L.dark, a);
    strokePath(ctx, L.edge, 1.2, 0.8 * a);
    ctx.globalCompositeOperation = 'lighter';
    strokePath(ctx, L.light, 1, 0.5 * a);
  },
  fall(fx, ctx, q, x, y, v) {                   // 빙글빙글 내려오는 잎 무리
    const L = deepPal(leafPal(q));
    flock(fx, ctx, L, x, y, 0, 1, q.r * 0.22, 4, q.seed, fx.clock, 0.5 + 0.5 * v, isPetal(q), 0.3);
  },

  // 파워휩 · 우드해머 · 꽃잎댄스 - 잎을 휘감고 달린다
  rush(fx, ctx, a) {
    const L = deepPal(isPetal(a) ? (a.ty === 'FAIRY' ? a.c : PETAL) : a.c), petal = isPetal(a), t = fx.clock;
    if (a.stage === 'wind') {
      flock(fx, ctx, L, a.x, a.y, 0, -1, BODY_R * (1.6 - 0.4 * a.sk), 5, a.seed * 10, t, 0.4 + 0.6 * a.sk, petal, 0);
      return;
    }
    const fade = a.stage === 'tail' ? 1 - a.sk : 1;
    ctx.globalCompositeOperation = 'lighter';
    swirl(ctx, L.light, a.x, a.y, a.ux, a.uy, BODY_R * 0.9, t, a.seed, fade);
    flock(fx, ctx, L, a.x, a.y, a.ux, a.uy, BODY_R * 1.3, 6, a.seed * 10, t, fade, petal, 0.35);
    if (fx.perSec(18 * fade)) {
      const p = part(fx, 'leaf', a.x + rnd(-20, 20), a.y + rnd(-20, 20), -a.ux * 80 + rnd(-30, 30), -a.uy * 80 + rnd(-30, 30),
        0.7, 7, 1, L.light, 40, 2);
      p.vr = rnd(-14, 14);
    }
  },
  swing(fx, ctx, a, t) {                        // 앞을 쓸어 가는 초록 호 + 흩날리는 잎
    const L = deepPal(isPetal(a) ? (a.ty === 'FAIRY' ? a.c : PETAL) : a.c), R = a.reach;
    const e = easeOut(Math.min(1, t * 1.7)), a0 = a.ang - 1.2, a1 = a0 + 2.4 * e, from = Math.max(a0, a1 - 1.3);
    const fade = t > 0.55 ? (1 - t) / 0.45 : 1;
    ctx.globalCompositeOperation = 'source-over';
    crescent(ctx, a.x, a.y, R, from, a1, R * 0.28);
    fillPath(ctx, L.dark, 0.85 * fade);
    ctx.globalCompositeOperation = 'lighter';
    crescent(ctx, a.x, a.y, R * 0.97, from, a1, R * 0.14);
    fillPath(ctx, L.light, 0.8 * fade);
    for (let i = 0; i < 5; i++) {
      const th = from + (a1 - from) * (i / 4);
      drawLeaf(fx, ctx, L, a.x + Math.cos(th) * R, a.y + Math.sin(th) * R, 9, th + Math.PI / 2, fx.clock * 10 + i, fade,
        isPetal(a));
    }
    if (!a.mem.hit && t > 0.2) {
      a.mem.hit = true;
      leaf.impact(fx, a.x + a.ux * R * 0.7, a.y + a.uy * R * 0.7, a.ang, L, { why: 'hit', s: 0.7, ty: a.ty, k: a.k });
    }
  },
};

// ================================================================ 가루
const powder = {
  shot(fx, ctx, q) {
    const P = powderPal(q), r = q.r, t = fx.clock;
    pollen(fx, ctx, P, q.x - q.ux * r * 0.6, q.y - q.uy * r * 0.6, r * 2.6, q.seed, t + q.seed * 0.1, 1, 7, 26);
  },
  trail(fx, q) {
    const P = powderPal(q);
    for (let i = fx.perSec(24); i > 0; i--) {   // 흩날리다 가라앉는 알갱이
      part(fx, 'glow', q.x + rnd(-1.4, 1.4) * q.r, q.y + rnd(-1.4, 1.4) * q.r, rnd(-30, 30) - q.vx * 0.05,
        rnd(-30, 10) - q.vy * 0.05, rnd(0.6, 1), rnd(2.5, 4), 0.6, Math.random() < 0.5 ? P.light : WHITE, 30, 2.5);
    }
    for (let i = fx.perSec(5); i > 0; i--) {
      part(fx, 'star', q.x + rnd(-1.5, 1.5) * q.r, q.y + rnd(-1.5, 1.5) * q.r, 0, 0, rnd(0.25, 0.4), rnd(5, 8), 0.3, WHITE);
    }
    for (let i = fx.perSec(7); i > 0; i--) {    // 뒤에 남는 옅은 구름
      const p = part(fx, 'smoke', q.x - q.ux * q.r, q.y - q.uy * q.r, rnd(-15, 15), rnd(-15, 15), rnd(0.6, 0.9), q.r * 1.4, 2,
        P.cloud, 0, 2, 0);
      p.add = false;
    }
  },
  launch(fx, q) {
    const P = powderPal(q);
    spray(fx, 4, 'smoke', q.x, q.y, q.ang, 1.6, 30, 90, 0.6, q.r * 1.5, 2, P.cloud, 0, 3);
  },
  debris: { shape: 'glow', n: 14, c: 'light', v: 120, life: 0.8, size: 4, drag: 3, up: -20, end: 0.6 },
  impact(fx, x, y, ang, c, info) {              // 가루가 확 퍼져 덮는다
    const s = info.s || 1, P = powderOf(Object.prototype.hasOwnProperty.call(POWDER_TINT, info.k) ? POWDER_TINT[info.k] : c);
    spray(fx, Math.round(10 * s), 'smoke', x, y, 0, TAU, 50, 170, 0.95, 26 * s, 2.5, P.cloud, -10, 3);
    spray(fx, Math.round(6 * s), 'smoke', x, y - 8, 0, TAU, 20, 90, 0.75, 22 * s, 2.2, P.light, -20, 3);
    spray(fx, Math.round(20 * s), 'glow', x, y, 0, TAU, 60, 220, 0.9, 3.5, 0.6, P.light, 30, 3);
    spray(fx, Math.round(6 * s), 'star', x, y, 0, TAU, 40, 160, 0.4, 9, 0.4, WHITE, 0, 4);
  },
  // 솜포자 따위 - 부채꼴로 굴러 나가는 가루 구름
  cone(fx, ctx, q) {
    const P = powderPal(q), t = fx.clock, ca = Math.cos(q.ang), sa = Math.sin(q.ang), tan = Math.tan(q.h);
    if (q.phase === 'mark') {
      pollen(fx, ctx, P, q.x + ca * 30, q.y + sa * 30, 16 + 20 * q.u, q.seed, t, 0.4 + 0.6 * q.u, 4, 6);
      return;
    }
    const reach = q.len * (0.3 + 0.75 * easeOut(clamp01(q.e / 0.5))), a = 1 - smooth(clamp01((q.e - 0.6) / 0.4));
    for (let i = 0; i < 7; i++) {
      const p = frac(t * 0.9 + hash(q.seed + i)), s = 30 + p * (reach - 30), o = (hash(q.seed + i * 5) - 0.5) * 1.4 * s * tan;
      pollen(fx, ctx, P, q.x + ca * s - sa * o, q.y + sa * s + ca * o, 14 + s * tan * 0.55, q.seed + i, t, a *
        Math.sin(Math.PI * clamp01(p * 1.1)), 3, 4);
    }
    for (let i = fx.perSec(60 * a); i > 0; i--) {
      const d = q.ang + rnd(-0.8, 0.8) * q.h, v = rnd(200, 420);
      part(fx, 'glow', q.x + ca * 20, q.y + sa * 20, Math.cos(d) * v, Math.sin(d) * v, rnd(0.6, 0.9), 3.5, 0.6, P.light, 20, 2.5);
    }
  },
};

// ================================================================ 독
const poison = {
  shot(fx, ctx, q) {
    const { x, y, r } = q, D = deepPal(q.c), t = fx.clock;
    ctx.globalCompositeOperation = 'source-over';
    for (let i = 0; i < 3; i++) {               // 뒤에 남는 보라 김
      const p = frac(q.age * 1.5 + i / 3 + hash(q.seed + i) * 0.3), d = r * (1.8 + 3.2 * p);
      fx.ink.soft(ctx, D.dark, x - q.ux * d, y - q.uy * d - p * r, r * (0.8 + 1.1 * p), 0.5 * Math.sin(Math.PI * p));
    }
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, D.dark, x, y, r * 2.6, 0.45);
    for (let i = 0; i < 3; i++) {               // 뒤로 처진 방울
      const d = r * (1.5 + i * 0.75) + Math.sin(t * 9 + i) * r * 0.12, rr = r * (0.42 - i * 0.1);
      const o = Math.sin(t * 7 + i * 2 + q.seed) * r * 0.25;
      sludge(ctx, D, x - q.ux * d - q.uy * o, y - q.uy * d + q.ux * o, rr, t, q.seed + i * 5, q.ux, q.uy, 0.5, 0.95);
    }
    sludge(ctx, D, x, y, r * 1.05, t, q.seed, q.ux, q.uy, clamp01(q.speed / 900) * 0.45, 1);
    bubbles(ctx, D, x, y, r, 3, t, q.seed, 1);
  },
  trail(fx, q) {
    const D = deepPal(q.c);
    for (let i = fx.perSec(14); i > 0; i--) {   // 뚝뚝 떨어지는 방울
      const p = part(fx, 'glow', q.x + rnd(-0.6, 0.6) * q.r, q.y + q.r * 0.5, -q.vx * 0.05, rnd(-40, 20), rnd(0.35, 0.5),
        rnd(3.5, 5), 0.5, D.deep, 520, 1);
      p.add = false;
    }
    for (let i = fx.perSec(8); i > 0; i--) {    // 떠오르는 거품
      part(fx, 'bubble', q.x + rnd(-1, 1) * q.r, q.y + rnd(-1, 1) * q.r, rnd(-20, 20), rnd(-40, -10), rnd(0.4, 0.6), rnd(2.5, 4),
        1.6, D.light, -50, 1);
    }
    for (let i = fx.perSec(7); i > 0; i--) {    // 보라 김
      const p = part(fx, 'smoke', q.x - q.ux * q.r, q.y - q.uy * q.r, rnd(-15, 15), -25, rnd(0.55, 0.8), q.r * 1.1, 2.3,
        D.dark, -30, 1.5, 0);
      p.add = false;
    }
  },
  launch(fx, q) {
    const D = deepPal(q.c);
    for (let i = 0; i < 6; i++) {
      const a = q.ang + rnd(-0.8, 0.8), v = rnd(120, 260), p = part(fx, 'glow', q.x, q.y, Math.cos(a) * v, Math.sin(a) * v - 40,
        0.35, 4.5, 0.6, D.deep, 500, 1);
      p.add = false;
    }
  },
  debris: 'bubble',
  impact(fx, x, y, ang, c, info) {              // 철퍽 - 튀는 방울 · 거품 · 김 · 얼룩
    const s = info.s || 1, D = deepPal(c);
    for (let i = Math.round(16 * s); i > 0; i--) {
      const a = ang + Math.PI + rnd(-2.2, 2.2), v = rnd(140, 330);
      const p = part(fx, 'glow', x, y, Math.cos(a) * v, Math.sin(a) * v - 90, rnd(0.4, 0.65), rnd(4, 7), 0.6,
        Math.random() < 0.7 ? D.deep : D.dark, 620, 1);
      p.add = false;
    }
    spray(fx, Math.round(6 * s), 'glow', x, y, 0, TAU, 80, 220, 0.3, 4, 0.5, D.light, 400, 1);
    spray(fx, Math.round(9 * s), 'bubble', x, y, -Math.PI / 2, 2.6, 30, 120, 0.7, 5, 1.7, D.light, -60, 2);
    for (let i = Math.round(5 * s); i > 0; i--) {
      const p = part(fx, 'smoke', x + rnd(-20, 20), y + rnd(-15, 5), rnd(-30, 30), rnd(-60, -20), rnd(0.7, 1), 24 * s, 2.2,
        D.dark, -30, 1.5);
      p.add = false;
    }
    const st = part(fx, 'smoke', x, y + 12, 0, 0, 1.1, 34 * s, 1.15, D.deep, 0, 0, 0);
    st.add = false;
    const w = fx.spawn('ring', x, y, 0, 0, 0.3, 10, D.light);
    w.size1 = 60 * s;
    w.w = 3;
  },

  // 오물웨이브 - 출렁이는 독 물결이 퍼지며 마루에서 방울이 튄다
  ring(fx, ctx, q) {
    const D = deepPal(q.c), t = fx.clock;
    if (q.phase === 'mark') {                   // 발밑에 끓어오르는 웅덩이
      const u = q.u, pr = BODY_R * (1 + 1.4 * u);
      ctx.globalCompositeOperation = 'source-over';
      blobPath(ctx, q.x, q.y + 10, pr, t, q.seed, 1, 0, 0, 12);
      fillPath(ctx, D.deep, 0.5 + 0.3 * u);
      bubbles(ctx, D, q.x, q.y + 10, pr, 4, t, q.seed, 0.6 + 0.4 * u, 0.6, 1.3);
      return;
    }
    const { e, rr } = q, a = 1 - smooth(clamp01((e - 0.45) / 0.55)), th = 22 + 30 * (1 - e), n = 36;
    ctx.globalCompositeOperation = 'source-over';
    ctx.beginPath();                            // 띠: 바깥 (시계) + 안 (반시계) - 가운데는 빈다
    for (let i = 0; i <= n; i++) {
      const g = (i / n) * TAU, w = rr + Math.sin(g * 5 + t * 6 + q.seed) * 6 + Math.sin(g * 9 - t * 9) * 4;
      ctx.lineTo(q.x + Math.cos(g) * w, q.y + Math.sin(g) * w);
    }
    for (let i = n; i >= 0; i--) {
      const g = (i / n) * TAU, w = Math.max(0, rr - th + Math.sin(g * 4 - t * 5) * 6);
      ctx.lineTo(q.x + Math.cos(g) * w, q.y + Math.sin(g) * w);
    }
    ctx.closePath();
    fillPath(ctx, D.deep, 0.85 * a);
    ctx.beginPath();
    for (let i = 0; i <= n; i++) {
      const g = (i / n) * TAU, w = rr - th * 0.35 + Math.sin(g * 5 + t * 6 + q.seed) * 6;
      ctx.lineTo(q.x + Math.cos(g) * w, q.y + Math.sin(g) * w);
    }
    strokePath(ctx, D.dark, th * 0.55, a);
    ctx.globalCompositeOperation = 'lighter';
    ctx.beginPath();                            // 마루의 윤기
    for (let i = 0; i <= n; i++) {
      const g = (i / n) * TAU, w = rr - 3 + Math.sin(g * 5 + t * 6 + q.seed) * 6;
      ctx.lineTo(q.x + Math.cos(g) * w, q.y + Math.sin(g) * w);
    }
    strokePath(ctx, D.light, 2.5, 0.7 * a);
    ctx.globalCompositeOperation = 'source-over';
    for (let i = 0; i < 14; i++) {              // 물결 위에서 부풀었다 터지는 거품
      const p = frac(t * 2.4 + hash(q.seed + i * 7)), g = hash(q.seed + i * 13) * TAU, w = rr - th * (0.2 + 0.5 * hash(i));
      const bx = q.x + Math.cos(g) * w, by = q.y + Math.sin(g) * w, br = 3 + 6 * p;
      if (p < 0.85) {
        circle(ctx, bx, by, br);
        fillPath(ctx, D.dark, 0.9 * a);
        strokePath(ctx, D.light, 1.3, 0.9 * a);
        circle(ctx, bx - br * 0.35, by - br * 0.35, br * 0.25);
        fillPath(ctx, WHITE, 0.8 * a);
      } else {
        circle(ctx, bx, by, br * (1 + (p - 0.85) * 9));
        strokePath(ctx, D.light, 1.3, ((1 - p) / 0.15) * a);
      }
    }
    for (let i = fx.perSec(150 * a); i > 0; i--) {
      const g = rnd(0, TAU), v = rnd(80, 220), p = part(fx, 'glow', q.x + Math.cos(g) * rr, q.y + Math.sin(g) * rr,
        Math.cos(g) * v, Math.sin(g) * v - 120, rnd(0.35, 0.55), rnd(3.5, 6), 0.6, D.deep, 600, 1);
      p.add = false;
    }
  },

  // 용해액 따위 - 부채꼴로 뿜는 독 물보라 + 김
  cone(fx, ctx, q) {
    const D = deepPal(q.c), t = fx.clock, ca = Math.cos(q.ang), sa = Math.sin(q.ang), tan = Math.tan(q.h);
    if (q.phase === 'mark') {
      sludge(ctx, D, q.x + ca * 26, q.y + sa * 26, 6 + 8 * q.u, t, q.seed, ca, sa, 0.3, 0.5 + 0.5 * q.u);
      return;
    }
    const reach = q.len * (0.3 + 0.75 * easeOut(clamp01(q.e / 0.45))), a = 1 - smooth(clamp01((q.e - 0.6) / 0.4));
    ctx.globalCompositeOperation = 'source-over';
    for (let i = 0; i < 5; i++) {
      const p = frac(t * 1.2 + hash(q.seed + i)), s = reach * (0.3 + 0.7 * p), o = (hash(q.seed + i * 3) - 0.5) * 1.4 * s * tan;
      fx.ink.soft(ctx, D.dark, q.x + ca * s - sa * o, q.y + sa * s + ca * o - p * 30, 24 + s * tan * 0.7, 0.8 * a);
    }
    for (let i = 0; i < 18; i++) {
      const p = frac(t * 2.2 + hash(q.seed + i)), s = 24 + p * (reach - 24), o = (hash(q.seed + i * 5) - 0.5) * 1.6 * s * tan;
      sludge(ctx, D, q.x + ca * s - sa * o, q.y + sa * s + ca * o, 6 + 6 * hash(i * 3.3), t, q.seed + i, ca, sa, 0.6,
        a * Math.sin(Math.PI * clamp01(p * 1.1)));
    }
    for (let i = fx.perSec(90 * a); i > 0; i--) {
      const d = q.ang + rnd(-0.8, 0.8) * q.h, v = rnd(400, 760), p = part(fx, 'glow', q.x + ca * 20, q.y + sa * 20, Math.cos(d) * v,
        Math.sin(d) * v, rnd(0.35, 0.5), rnd(3, 5), 0.6, D.deep, 300, 2);
      p.add = false;
    }
  },

  // 독압정 - 웅덩이에 박힌 윤기 나는 독 마름쇠, 거품이 올라와 터지고 김이 핀다
  haz(fx, ctx, q) {
    const D = deepPal(q.c), r = q.hr, t = fx.clock;
    for (let i = 0; i < 5; i++) {
      const th = hash(q.seed + i) * TAU, d = r * 0.62 * Math.sqrt(hash(q.seed + i + 3));
      const x = q.x + Math.cos(th) * d, y = q.y + Math.sin(th) * d, rot = hash(q.seed + i * 5) * TAU;
      ctx.globalCompositeOperation = 'source-over';
      ctx.beginPath();
      ctx.ellipse(x, y + 4, 16, 8, 0, 0, TAU);
      fillPath(ctx, D.deep, 0.55);
      spikes(ctx, x, y, 13, 4, 0.34, rot);      // 네 갈래 마름쇠 - 어두운 몸 · 밝은 반쪽 · 흰 윤기
      fillPath(ctx, D.dark, 1);
      strokePath(ctx, D.edge, 1.4, 0.95);
      ctx.beginPath();
      for (let k = 0; k < 4; k++) {             // 갈래마다 왼쪽 위 면이 밝다
        const g = rot + (k * Math.PI) / 2, gx = Math.cos(g), gy = Math.sin(g);
        ctx.moveTo(x, y);
        ctx.lineTo(x + gx * 13, y + gy * 13);
        ctx.lineTo(x + Math.cos(g - 0.45) * 4.5, y + Math.sin(g - 0.45) * 4.5);
        ctx.closePath();
      }
      fillPath(ctx, D.light, 0.55);
      circle(ctx, x - 1.5, y - 2, 2.2);
      fillPath(ctx, WHITE, 0.9);
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.glow(ctx, D.light, x, y, 16, 0.16 + 0.12 * Math.sin(t * 3 + i * 1.7));
      const p = frac(t * 0.55 + hash(q.seed + i * 11));      // 웅덩이에서 오르는 거품 하나
      const bx = x + (hash(q.seed + i * 13) - 0.5) * 18, by = y + 3 - p * 18, br = 2 + 3 * p;
      ctx.globalCompositeOperation = 'source-over';
      if (p < 0.85) {
        circle(ctx, bx, by, br);
        fillPath(ctx, D.dark, 0.5);
        strokePath(ctx, D.light, 1.2, 0.85);
      } else {
        circle(ctx, bx, by, br * (1 + (p - 0.85) * 8));
        strokePath(ctx, D.light, 1, (1 - p) / 0.15);
      }
    }
    for (let i = 0; i < 3; i++) {               // 피어오르는 독 김
      const p = frac(t * 0.35 + i / 3 + hash(q.seed + i * 17)), th = hash(q.seed + i * 19) * TAU, d = r * 0.4;
      fx.ink.soft(ctx, D.dark, q.x + Math.cos(th) * d, q.y + Math.sin(th) * d - p * 34, 14 + 16 * p, 0.35 * Math.sin(Math.PI * p));
    }
  },

  // 독찌르기 · 포이즌테일 - 독 김을 끌며 달린다
  rush(fx, ctx, a) {
    const D = deepPal(a.c), t = fx.clock;
    if (a.stage === 'wind') {
      sludge(ctx, D, a.x + a.ux * (BODY_R + 6), a.y + a.uy * (BODY_R + 6), 5 + 6 * a.sk, t, a.seed * 10, a.ux, a.uy, 0.3,
        0.5 + 0.5 * a.sk);
      return;
    }
    const fade = a.stage === 'tail' ? 1 - a.sk : 1, tr = a.trail;
    ctx.globalCompositeOperation = 'source-over';
    for (let i = 1; i < tr.n; i += 2) {         // 지나온 자리에 남는 김
      const k = ageK(a, i, t, 0.4);
      if (!(k < 1)) break;
      fx.ink.soft(ctx, D.dark, tr.x(i), tr.y(i) - k * 20, BODY_R * (0.9 + 1.2 * k), 0.55 * (1 - k) * fade);
    }
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, D.dark, a.x, a.y, BODY_R * 2, 0.4 * fade);
    for (let i = fx.perSec(30 * fade); i > 0; i--) {
      const p = part(fx, 'glow', a.x + rnd(-18, 18), a.y + rnd(-10, 18), -a.ux * 60, rnd(-30, 10), rnd(0.35, 0.5), rnd(3.5, 5),
        0.5, D.deep, 520, 1);
      p.add = false;
    }
  },
  swing(fx, ctx, a, t) {                        // 앞으로 찌르는 독 가시 + 끝에서 튀는 독
    const D = deepPal(a.c), e = easeOut(Math.min(1, t * 2.2)), fade = t > 0.5 ? (1 - t) / 0.5 : 1;
    const L = a.reach * (0.35 + 0.75 * e), x0 = a.x + a.ux * BODY_R * 0.6, y0 = a.y + a.uy * BODY_R * 0.6;
    const tx = a.x + a.ux * L, ty = a.y + a.uy * L, px = -a.uy, py = a.ux, w = 10 * (1 - 0.4 * e) + 4;
    ctx.globalCompositeOperation = 'source-over';
    ctx.beginPath();
    ctx.moveTo(x0 + px * w, y0 + py * w);
    ctx.quadraticCurveTo(x0 + a.ux * L * 0.5 + px * w * 0.7, y0 + a.uy * L * 0.5 + py * w * 0.7, tx, ty);
    ctx.quadraticCurveTo(x0 + a.ux * L * 0.5 - px * w * 0.7, y0 + a.uy * L * 0.5 - py * w * 0.7, x0 - px * w, y0 - py * w);
    ctx.closePath();
    fillPath(ctx, D.dark, fade);
    strokePath(ctx, D.edge, 1.5, fade);
    line(ctx, D.glint, 1.6, x0 + px * w * 0.3, y0 + py * w * 0.3, tx - a.ux * 6, ty - a.uy * 6);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, D.light, tx, ty, 26 * (1 - t) + 6, fade);
    if (!a.mem.hit && t > 0.2) {
      a.mem.hit = true;
      poison.impact(fx, tx, ty, a.ang, a.c, { why: 'hit', s: 0.7 });
    }
  },
};

export default { flame, zap, leaf, powder, poison };
