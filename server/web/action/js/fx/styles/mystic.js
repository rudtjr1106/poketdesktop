/* 모양: 에스퍼 · 혼 · 어둠 · 요정 · 빛 구슬 · 광선 (psy ghost dark fairy orb beam).
   orb 는 모르는 모양 키의 대신이기도 하다 - 여기 훅을 더하면 모르는 키도 그것을 쓴다.
   훅 이름 · 인자 · q 칸 · 도우미는 fx/core.js 맨 위. 이 파일에는 이 여섯 키만 둔다 (fx/styles/index.js 의 FAMILY_OF).

     psy    일그러지며 퍼지는 분홍 · 보라 고리 + 감아 도는 글자 반짝이 (사이코키네시스 · 사이코쇼크 · 신통력 · 미래예지)
     ghost  연기 위의 보랏빛 혼불 - 뒤로 끌리는 촉수, 어둡게 꺼진 심, 깜박이는 두 눈 (섀도볼 · 병상첨병 · 야습)
     dark   검보라 연기 + 빈 속 + 감아 도는 날카로운 초승달 (나이트버스트 · 탁쳐서떨구기 · 기습)
     fairy  달빛 초승달 + 도는 별 · 하트 + 반짝임 (문포스 · 매지컬샤인 · 드레인키스 · 애교부리기)
     orb    늘어난 빛 덩이 + 팽이처럼 도는 고리 + 속도선 (스피드스타 · 몸통박치기 · 용성군 · 대폭발 · 모르는 키)
     beam   겹 띠 광선 - 지직거리는 흰 심, 흐르는 덩이, 감기는 두 가닥, 옆 · 끝 불티, 모이는 빛, 남는 빛 (파괴광선 · 냉동빔)

   색: 풀밭 위에 밝은 색을 빛(lighter)으로 얹으면 하얗게 바래고, 옅게 깐 색은 잿빛이 된다. 그래서 그 원소의 색은
   보통 혼합으로 또렷이 칠하고 (분홍 고리 · 짙은 보라 혼불 · 파스텔 별), 빛은 번짐 · 흰 심 · 반짝임에만 쓴다.
   혼 · 악의 연기는 보통 혼합으로 먼저 깔고 그 위에 빛을 얹어야 보랏빛이 보랏빛으로 보인다.

   여기서만 쓰는 도우미 (core 에 없는 것): 끝이 가는 띠(taper) · 일그러진 고리(wobble · wobbleArc) · 혼불 덩이(wispBlob) ·
   하트 · 기운 궤도(orbit) · 입자 하나(dot) · 부드러운 꼬리(softTail) · 돌진 폭의 가장자리(laneEdges) · 어둡게 누른 색(shade) ·
   고리 둘레에서 뿌리기(rim). 입자는 Math.random (core 와 같다), 그림 모양은 q.seed + hash · noise. */
import {
  A, BODY_R, TAU, VOID, WHITE, circle, clamp01, crescent, easeOut, fillPath, hash, noise1, ribbon, ring as halo, rnd,
  smooth, spikes, streak, strokePath, wedge,
} from '../core.js';

// ---------------------------------------------------------------- 색 (타입 색 위에 얹는 덧빛)
const PSY_V = '#b58cff';          // 에스퍼 보라
const SMOKE = '#1b1328';          // 혼 · 악 연기 - 보통 혼합으로 칠해야 어둡다
const EDGE = '#a46bff';           // 악의 날
const EYE = '#f1e8ff';            // 혼의 눈
const MOON = '#fff7e8';           // 달빛
const HEART = '#ff8fcf';
const PASTEL = ['#fff3b0', '#bfe9ff', '#ffc9ec', '#dccbff', '#c9ffe4'];

// ---------------------------------------------------------------- 뿌리는 법
const PSY_GLINT = { shape: 'star', n: 10, c: 'light', v: 210, life: 0.5, size: 10, drag: 4 };
const GHOST_PUFF = { shape: 'smoke', n: 9, c: SMOKE, v: 90, life: 0.6, size: 18, end: 2.2, drag: 3 };
const GHOST_FIRE = { shape: 'wisp', n: 10, c: 'light', v: 120, life: 0.6, size: 12, g: -120, drag: 2 };
const DARK_PUFF = { shape: 'smoke', n: 12, c: VOID, v: 150, life: 0.55, size: 20, end: 2.4, drag: 3.5 };
const DARK_SHARD = { shape: 'shard', n: 9, c: EDGE, v: 280, life: 0.35, size: 8, drag: 5, spin: 10 };
const FAIRY_STAR = { shape: 'star', n: 12, c: 'dark', v: 200, life: 0.6, size: 11, drag: 3.5 };
const ORB_SPARK = { shape: 'spark', n: 12, c: WHITE, v: 380, life: 0.26, size: 12, w: 2.5, drag: 5 };
const BEAM_SPRAY = { shape: 'spark', n: 14, c: 'light', v: 420, life: 0.3, size: 12, w: 2.4, drag: 4.5 };

// ---------------------------------------------------------------- 도우미 (이 파일만)
const N_MAX = 64;
const XS = new Float64Array(N_MAX), YS = new Float64Array(N_MAX), WS = new Float64Array(N_MAX);
const P = { x: 0, y: 0 };

/** XS · YS 가운데 줄 n 점과 WS 반폭으로 만든 띠 경로 (끝이 가는 혀 · 촉수). */
function taper(ctx, n) {
  ctx.beginPath();
  for (let i = 0; i < n; i++) edge(ctx, i, n, 1);
  for (let i = n - 1; i >= 0; i--) edge(ctx, i, n, -1);
  ctx.closePath();
}

function edge(ctx, i, n, sg) {
  const a = i > 0 ? i - 1 : 0, b = i < n - 1 ? i + 1 : n - 1;
  const dx = XS[b] - XS[a], dy = YS[b] - YS[a], d = Math.hypot(dx, dy) || 1, w = WS[i] * sg;
  ctx.lineTo(XS[i] - (dy / d) * w, YS[i] + (dx / d) * w);
}

/** 일그러진 고리 경로 - 반지름이 k 겹으로 출렁인다 (amp 는 비율). */
function wobble(ctx, x, y, r, amp, k, ph, n = 30) {
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const a = (i / n) * TAU, rr = r * (1 + amp * Math.sin(k * a + ph) + amp * 0.5 * Math.sin((k + 2) * a - ph * 1.3));
    ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
  }
  ctx.closePath();
}

/** a0 → a1 일그러진 호 (열린 경로). */
function wobbleArc(ctx, x, y, r, a0, a1, amp, k, ph, n = 20) {
  ctx.beginPath();
  for (let i = 0; i <= n; i++) {
    const f = i / n, a = a0 + (a1 - a0) * f, rr = r * (1 + amp * Math.sin(k * f * TAU + ph));
    ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
  }
}

/** 혼불 덩이 - 둘레가 back 쪽으로 핥아 올라가며 일렁인다. */
function wispBlob(ctx, x, y, R, back, t, s, n = 22) {
  for (let i = 0; i < n; i++) {
    const a = (i / n) * TAU, to = Math.cos(a - back);
    const lick = to > 0 ? to * to * (0.7 + 0.9 * noise1(t * 7 + i * 1.7 + s)) : 0;
    const rr = R * (1 + 0.16 * Math.sin(a * 5 + t * 13 + s) + lick);
    XS[i] = x + Math.cos(a) * rr;
    YS[i] = y + Math.sin(a) * rr;
  }
  ctx.beginPath();                                  // 점 사이 가운데를 2차 곡선으로 - 둥글게 일렁인다
  ctx.moveTo((XS[n - 1] + XS[0]) / 2, (YS[n - 1] + YS[0]) / 2);
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    ctx.quadraticCurveTo(XS[i], YS[i], (XS[i] + XS[j]) / 2, (YS[i] + YS[j]) / 2);
  }
  ctx.closePath();
}

/** 하트 (rot 0 이면 뾰족한 끝이 아래). */
function heart(ctx, x, y, s, rot) {
  const c = Math.cos(rot) * s, n = Math.sin(rot) * s;
  const X = (u, v) => x + u * c - v * n, Y = (u, v) => y + u * n + v * c;
  ctx.beginPath();
  ctx.moveTo(X(0, 0.85), Y(0, 0.85));
  ctx.bezierCurveTo(X(-0.25, 0.6), Y(-0.25, 0.6), X(-1, 0.2), Y(-1, 0.2), X(-0.95, -0.3), Y(-0.95, -0.3));
  ctx.bezierCurveTo(X(-0.9, -0.85), Y(-0.9, -0.85), X(-0.2, -0.85), Y(-0.2, -0.85), X(0, -0.4), Y(0, -0.4));
  ctx.bezierCurveTo(X(0.2, -0.85), Y(0.2, -0.85), X(0.9, -0.85), Y(0.9, -0.85), X(0.95, -0.3), Y(0.95, -0.3));
  ctx.bezierCurveTo(X(1, 0.2), Y(1, 0.2), X(0.25, 0.6), Y(0.25, 0.6), X(0, 0.85), Y(0, 0.85));
  ctx.closePath();
}

const star5 = (ctx, x, y, r, rot) => spikes(ctx, x, y, r, 5, 0.45, rot);

/** 기운 타원 궤도 위의 점 → P. */
function orbit(x, y, a, rx, ry, tilt) {
  const ox = Math.cos(a) * rx, oy = Math.sin(a) * ry, c = Math.cos(tilt), s = Math.sin(tilt);
  P.x = x + ox * c - oy * s;
  P.y = y + ox * s + oy * c;
  return P;
}

/** 입자 하나 + 자주 바꾸는 칸 (끝 크기 배율 · 끌림 · 무게). */
function dot(fx, shape, x, y, vx, vy, life, size, col, end = 0.4, drag = 0, g = 0) {
  const p = fx.spawn(shape, x, y, vx, vy, life, size, col);
  p.size1 = size * end;
  p.drag = drag;
  p.g = g;
  return p;
}

/** 지나온 자리를 따라 옅어지는 빛 번짐 (딱딱한 띠 대신 부드러운 꼬리). life 초 안의 점만, 한 점 걸러. */
function softTail(fx, ctx, q, col, life, r0, a0) {
  const tr = q.trail, now = fx.clock;
  for (let i = 1; i < tr.n; i += 2) {
    const k = (now - tr.t(i)) / life;
    if (!(k < 1)) break;
    fx.ink.glow(ctx, col, tr.x(i), tr.y(i), r0 * (1 - 0.6 * k), a0 * (1 - k));
  }
}

/** 지금 자리에서 퍼지는 보통 혼합 고리 (어두운 충격파). */
function darkWave(fx, x, y, col, r1, life, w) {
  const p = dot(fx, 'ring', x, y, 0, 0, life, r1 * 0.15, col, 1);
  p.size1 = r1;
  p.w = w;
  p.add = false;
}

/** 둘레에서 가운데로 빨려 드는 빛 (life 초에 닿는다). */
function implode(fx, x, y, col, d, n, life) {
  for (let i = 0; i < n; i++) {
    const a = (i / n) * TAU + rnd(0, 0.5), cx = Math.cos(a), cy = Math.sin(a);
    dot(fx, 'glow', x + cx * d, y + cy * d, (-cx * d) / life, (-cy * d) / life, life, rnd(5, 8), col, 0.3);
  }
}

/** 고리 장판이 터질 때 - 가운데는 쓴 쪽 몸이라 둘레 n 곳에서 바깥으로 뿌린다. */
function rim(fx, x, y, R, spec, c, k, n = 8) {
  const r = R > 0 ? R : 60;
  for (let i = 0; i < n; i++) {
    const a = (i / n) * TAU + rnd(0, 0.4);
    fx.burst(x + Math.cos(a) * r * 0.9, y + Math.sin(a) * r * 0.9, spec, c, k, a, 1.2);
  }
}

/** x, y 를 가로지르는 날 (line 입자) - ang 쪽 길이 L. */
function slash(fx, x, y, ang, L, col, w, life) {
  const cx = Math.cos(ang) * L * 0.5, cy = Math.sin(ang) * L * 0.5;
  const p = fx.spawn('line', x - cx, y - cy, 0, 0, life, 1, col);
  p.x2 = x + cx;
  p.y2 = y + cy;
  p.w = w;
}

// 파스텔을 차례로 돌려 고른다 - 다섯 빛이 금방 다 나와 스프라이트가 처음 몇 번에 다 만들어진다
let pastelI = 0;
const pastel = () => PASTEL[(pastelI = (pastelI + 1) % PASTEL.length)];

// 어둡게 누른 색 '#rrggbb' (k 0 검정 ~ 1 그대로) - 색마다 한 번 셈한다
const SHADE = new Map();
function shade(hex, k) {
  const key = hex + k;
  let v = SHADE.get(key);
  if (v === undefined) {
    const n = parseInt(hex.slice(1), 16), ch = (sh) => Math.round(((n >> sh) & 255) * k);
    v = '#' + ((1 << 24) | (ch(16) << 16) | (ch(8) << 8) | ch(0)).toString(16).slice(1);
    SHADE.set(key, v);
  }
  return v;
}

// ---------------------------------------------------------------- 근접 · 돌진 공통
const fadeOf = (a) => (a.stage === 'tail' ? 1 - a.sk : 1);

// 쓸고 간 폭 (= 맞는 범위, 반폭 a.reach) - 옅은 속 + 또렷한 두 가장자리 (옅게 깐 색은 풀밭 위에서 잿빛이 되므로
// 색은 가장자리에 싣는다) + 몸 폭 빛 띠
function lanes(fx, ctx, a, outer, inner, ao, ai) {
  ctx.globalCompositeOperation = 'source-over';
  ribbon(ctx, a.trail, fx.clock, 0.3, a.reach * 2, a.reach * 0.7, outer, ao * 0.6);
  laneEdges(ctx, a.trail, fx.clock, 0.3, a.reach * 2, a.reach * 0.7, outer, Math.min(1, ao * 3.5), 2.5);
  ctx.globalCompositeOperation = 'lighter';
  ribbon(ctx, a.trail, fx.clock, 0.2, BODY_R * 1.3, 3, inner, ai);
}

// ribbon 과 같은 폭 · 나이로 두 가장자리만 긋는다 (마디마다 옅어진다)
function laneEdges(ctx, tr, now, life, w0, w1, col, a, lw) {
  if (!tr || tr.n < 2) return;
  ctx.strokeStyle = col;
  ctx.lineWidth = lw;
  let px = tr.x(0), py = tr.y(0), pw = w0 / 2;
  for (let i = 1; i < tr.n; i++) {
    const k = (now - tr.t(i)) / life;
    if (!(k < 1)) break;
    const x = tr.x(i), y = tr.y(i), w = (w0 + (w1 - w0) * clamp01(k)) / 2, dx = x - px, dy = y - py, d = Math.hypot(dx, dy);
    if (d > 0.01) {
      const nx = -dy / d, ny = dx / d;
      ctx.globalAlpha = A(a * (1 - clamp01(k)));
      ctx.beginPath();
      ctx.moveTo(px + nx * pw, py + ny * pw);
      ctx.lineTo(x + nx * w, y + ny * w);
      ctx.moveTo(px - nx * pw, py - ny * pw);
      ctx.lineTo(x - nx * w, y - ny * w);
      ctx.stroke();
    }
    px = x;
    py = y;
    pw = w;
  }
}

// 준비: 갈 쪽으로 뻗는 빛
function windUp(fx, ctx, a, col) {
  const k = a.sk, d = a.reach * (0.45 + 0.35 * k);
  streak(fx, ctx, col, a.x + a.ux * d, a.y + a.uy * d, a.ang, a.reach * (0.25 + 0.45 * k), 6 + 10 * k, 0.15 + 0.4 * k);
}

// 몸 둘레 양옆으로 뒤로 흐르는 속도선 (빠를수록 진하다)
function speedLines(fx, ctx, a, col, fade) {
  const v = clamp01(a.speed / 900) * fade;
  if (v < 0.05) return;
  const px = -a.uy, py = a.ux, flick = Math.floor(fx.clock * 30);
  ctx.globalAlpha = A(0.7 * v);
  ctx.strokeStyle = col;
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < 7; i++) {
    const o = (hash(a.seed + i * 7 + flick) - 0.5) * 1.8 * a.reach, back = BODY_R * 0.6 + hash(a.seed + i + flick) * 40;
    const L = 30 + 80 * v, x = a.x + px * o - a.ux * back, y = a.y + py * o - a.uy * back;
    ctx.moveTo(x, y);
    ctx.lineTo(x - a.ux * L, y - a.uy * L);
  }
  ctx.stroke();
}

// 휘두르는 호의 지금 범위 → SW (from · to). dir 1 이면 반시계 → 시계, -1 이면 거꾸로
const SW = { from: 0, to: 0, fade: 1 };
function sweep(a, t, span, dir = 1, speed = 1.7) {
  const e = easeOut(Math.min(1, t * speed)), a0 = a.ang - span * dir, a1 = a0 + 2 * span * e * dir;
  SW.to = a1;
  SW.from = dir > 0 ? Math.max(a0, a1 - span * 1.15) : Math.min(a0, a1 + span * 1.15);
  SW.fade = t > 0.55 ? (1 - t) / 0.45 : 1;
  return SW;
}

// ================================================================ psy
const psy = {
  shot(fx, ctx, q) {
    const { x, y, r, c, ux, uy } = q, t = fx.clock, s = q.seed, sp = hash(s), pulse = 1 + 0.12 * Math.sin(t * 14 + s);
    softTail(fx, ctx, q, c.dark, 0.22, r * 1.8, 0.4);
    ribbon(ctx, q.trail, t, 0.14, r * 0.5, 1, PSY_V, 0.5);
    fx.ink.glow(ctx, c.dark, x, y, r * 3.2, 0.4 + 0.12 * Math.sin(t * 11 + s));
    fx.ink.glow(ctx, PSY_V, x - ux * r * 0.8, y - uy * r * 0.8, r * 2.4, 0.35);
    // 색이 살게 보통 혼합: 분홍 몸 + 퍼지며 뒤로 처지는 일그러진 고리 넷 (분홍 · 보라가 조금 어긋나 일렁인다)
    ctx.globalCompositeOperation = 'source-over';
    wobble(ctx, x, y, r * 0.95 * pulse, 0.08, 3, -t * 9 + s, 20);
    fillPath(ctx, c.dark, 0.6);
    for (let i = 0; i < 4; i++) {
      const ph = (q.age * 2.6 + i / 4 + sp) % 1, f = 1 - ph, R = r * (0.6 + 1.9 * ph);
      const cx = x - ux * ph * r * 1.4, cy = y - uy * ph * r * 1.4, wob = t * 6 + i * 1.9 + s, amp = 0.06 + 0.1 * ph;
      wobble(ctx, cx + 1.5, cy - 1, R, amp, 3, wob);
      strokePath(ctx, PSY_V, 1 + 2.4 * f, 0.85 * f);
      wobble(ctx, cx - 1, cy + 1, R, amp, 3, wob + 0.5);
      strokePath(ctx, c.dark, 1 + 2.6 * f, 0.9 * f);
    }
    ctx.globalCompositeOperation = 'lighter';
    // 감아 도는 글자 반짝이 - 기운 궤도, 앞으로 올 때 커진다
    const tilt = sp * TAU, dir = hash(s + 3) < 0.5 ? -1 : 1;
    for (let i = 0; i < 3; i++) {
      const a = dir * t * 4.5 + (i * TAU) / 3 + s, near = 0.55 + 0.45 * Math.sin(a), g = orbit(x, y, a, r * 1.8, r * 0.7, tilt);
      fx.ink.glow(ctx, PSY_V, g.x, g.y, r * 0.8, 0.6 * near);
      spikes(ctx, g.x, g.y, r * (0.26 + 0.14 * near), 4, 0.3, a * 1.5);
      fillPath(ctx, WHITE, 0.55 + 0.45 * near);
      circle(ctx, g.x, g.y, r * 0.42 * near + 0.5);
      strokePath(ctx, c.light, 1, 0.5 * near);
    }
    wobble(ctx, x, y, r * 0.6 * pulse, 0.1, 3, t * 7 + s, 18);
    strokePath(ctx, c.light, 1.5, 0.8);
    fx.ink.core(ctx, c.light, x, y, r * 0.75 * pulse, 0.9);
    fx.ink.glow(ctx, WHITE, x, y, r * 0.3, 0.8);
  },
  trail(fx, q) {
    const { x, y, r, c } = q;
    for (let n = fx.perSec(8); n > 0; n--) {         // 뒤에 남아 퍼지는 고리 (색이 살게 보통 혼합)
      const p = dot(fx, 'ring', x - q.ux * r, y - q.uy * r, -q.ux * 20, -q.uy * 20, rnd(0.3, 0.45), r * 0.7,
        Math.random() < 0.5 ? PSY_V : c.dark, rnd(2.2, 3));
      p.w = 2;
      p.add = false;
    }
    for (let n = fx.perSec(16); n > 0; n--) {        // 반짝이 가루
      const a = rnd(0, TAU), v = rnd(20, 60);
      dot(fx, 'star', x + Math.cos(a) * r * 1.2, y + Math.sin(a) * r * 1.2, Math.cos(a) * v - q.vx * 0.05,
        Math.sin(a) * v - q.vy * 0.05, rnd(0.3, 0.5), rnd(4, 8), Math.random() < 0.6 ? c.light : PSY_V, 0.4, 2);
    }
  },
  launch(fx, q) {
    fx.wave(q.x, q.y, PSY_V, q.r * 4, 0.35, 4);
    fx.wave(q.x, q.y, q.c.light, q.r * 2.6, 0.28, 2.5);
  },
  debris: PSY_GLINT,
  impact(fx, x, y, ang, c, info) {                  // 빨려 들었다가 겹겹이 퍼진다
    const s = info.s || 1;
    if (info.why === 'ring') {
      rim(fx, x, y, info.r, PSY_GLINT, c, 0.2);
      return;
    }
    implode(fx, x, y, PSY_V, 90 * s, 10, 0.22);
    fx.wave(x, y, PSY_V, 120 * s, 0.5, 6);
    fx.wave(x, y, c.light, 80 * s, 0.38, 4);
    const p = dot(fx, 'ring', x, y, 0, 0, 0.65, 16, c.dark, 1);
    p.size1 = 150 * s;
    p.w = 2;
    fx.burst(x, y, PSY_GLINT, c, 0.6 * s);
  },
  tele(fx, ctx, q) {
    const { x, y, r, c } = q, t = fx.clock;
    if (q.phase === 'mark') {                       // 바닥에 도는 염동 문양 - 찰수록 빨리 돈다
      const u = q.u, rot = t * (0.8 + 2.5 * u) + q.seed;
      fx.ink.glow(ctx, PSY_V, x, y, r * 1.1, 0.15 + 0.25 * u);
      wobble(ctx, x, y, r * 0.82, 0.03, 4, t * 3);
      strokePath(ctx, PSY_V, 2, 0.35 + 0.4 * u);
      circle(ctx, x, y, r * 0.55);
      strokePath(ctx, c.light, 1.5, 0.3 + 0.4 * u);
      for (let i = 0; i < 6; i++) {
        const a = rot + (i * TAU) / 6;
        spikes(ctx, x + Math.cos(a) * r * 0.68, y + Math.sin(a) * r * 0.68, r * 0.09, 4, 0.3, a);
        fillPath(ctx, WHITE, 0.4 + 0.5 * u);
      }
      return;
    }
    const e = q.e, f = 1 - e;                        // 떨어진 자리 - 일그러진 고리가 겹겹이
    fx.ink.glow(ctx, c.dark, x, y, r * 1.8, 0.6 * f);
    fx.ink.core(ctx, c.light, x, y, r * (0.5 + 0.6 * e), f);
    for (let i = 0; i < 3; i++) {
      const k = clamp01(e * 1.4 - i * 0.18);
      if (k <= 0 || k >= 1) continue;
      wobble(ctx, x, y, r * (0.3 + 1.2 * easeOut(k)), 0.08 * (1 - k) + 0.03, 3 + i, t * 8 + i);
      ctx.globalCompositeOperation = 'source-over';
      strokePath(ctx, i % 2 ? PSY_V : c.dark, 2 + 8 * (1 - k), 0.9 * (1 - k));
      ctx.globalCompositeOperation = 'lighter';
      strokePath(ctx, c.light, 1.5, 0.8 * (1 - k));
    }
  },
  fall(fx, ctx, q, x, y, v) {                       // 내려오는 염동 구슬 - 고리 둘이 감싸 돈다
    const r = q.r * 0.3, t = fx.clock;
    fx.ink.stretch(ctx, PSY_V, x, y - r * 2.2, r * 0.5, r * 2.6, 0.35 + 0.4 * v);
    fx.ink.glow(ctx, q.c.dark, x, y, r * 2.4, 0.5);
    for (let i = 0; i < 2; i++) {
      ctx.beginPath();
      ctx.ellipse(x, y, r * 1.6, Math.abs(Math.sin(t * 5 + i * 1.6)) * r * 1.6 + 0.5, i * 1.2 + t, 0, TAU);
      strokePath(ctx, i ? PSY_V : q.c.light, 1.5, 0.8);
    }
    fx.ink.core(ctx, q.c.light, x, y, r, 1);
  },
  ring(fx, ctx, q) {
    const { x, y, r, c } = q, t = fx.clock;
    if (q.phase === 'mark') {                       // 안쪽에서 일렁이는 옅은 고리
      for (let i = 0; i < 2; i++) {
        const ph = (t * 0.9 + i / 2) % 1;
        wobble(ctx, x, y, r * (0.25 + 0.7 * ph), 0.05, 3, t * 4 + i);
        strokePath(ctx, i ? PSY_V : c.light, 2, 0.4 * q.u * (1 - ph));
      }
      return;
    }
    const { rr, e } = q, f = 1 - e, amp = 0.05 * f + 0.01;
    fx.ink.glow(ctx, c.dark, x, y, rr * 1.15, 0.35 * f);
    ctx.globalCompositeOperation = 'source-over';   // 분홍 · 보라가 어긋난 굵은 물결 + 안쪽 잔물결 둘
    wobble(ctx, x + 3, y - 2, rr, amp, 4, t * 9);
    strokePath(ctx, PSY_V, rr * 0.1 * f + 1, 0.75 * f);
    wobble(ctx, x - 3, y + 2, rr, amp, 4, t * 9 + 0.6);
    strokePath(ctx, c.dark, rr * 0.08 * f + 1, 0.85 * f);
    for (let k = 1; k < 3; k++) {
      wobble(ctx, x, y, rr * (1 - k * 0.17), amp * 1.5, 3 + k, t * 7 + k * 2);
      strokePath(ctx, k === 1 ? c.dark : PSY_V, rr * 0.03 * f + 1, 0.6 * f);
    }
    ctx.globalCompositeOperation = 'lighter';
    wobble(ctx, x, y, rr, amp, 4, t * 9 + 0.3);
    strokePath(ctx, c.light, 2 * f + 0.5, 0.8 * f);
    for (let i = 0; i < 8; i++) {                    // 고리 위의 글자
      const a = t * 2 + (i * TAU) / 8, gx = x + Math.cos(a) * rr, gy = y + Math.sin(a) * rr;
      fx.ink.glow(ctx, PSY_V, gx, gy, 16, 0.7 * f);
      spikes(ctx, gx, gy, 9, 4, 0.3, a);
      fillPath(ctx, WHITE, f);
    }
  },
  cone(fx, ctx, q) {
    const { x, y, len, ang, h, c } = q, t = fx.clock;
    if (q.phase === 'mark') {                       // 앞으로 흘러가는 옅은 물결
      for (let i = 0; i < 2; i++) {
        const ph = (t * 0.8 + i / 2) % 1;
        wobbleArc(ctx, x, y, len * (0.15 + 0.8 * ph), ang - h, ang + h, 0.05, 1.5, t * 5 + i);
        strokePath(ctx, PSY_V, 2, 0.45 * q.u * (1 - ph));
      }
      return;
    }
    const e = q.e, f = 1 - e;
    wedge(ctx, x, y, len * easeOut(e), ang, h);
    ctx.globalCompositeOperation = 'source-over';
    fillPath(ctx, c.dark, 0.3 * f);
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 4; i++) {
      const k = clamp01(e * 1.5 - i * 0.15);
      if (k <= 0 || k >= 1) continue;
      wobbleArc(ctx, x, y, len * (0.15 + 0.85 * k), ang - h, ang + h, 0.05, 1.5, t * 10 + i);
      ctx.globalCompositeOperation = 'source-over';
      strokePath(ctx, i % 2 ? PSY_V : c.dark, 3 + 8 * (1 - k), 0.9 * (1 - k * 0.7));
      ctx.globalCompositeOperation = 'lighter';
      strokePath(ctx, c.light, 1.5, 0.8 * (1 - k));
    }
  },
  rush(fx, ctx, a) {
    const { c } = a;
    if (a.stage === 'wind') {                       // 몸을 감싸며 좁아지는 고리
      windUp(fx, ctx, a, PSY_V);
      wobble(ctx, a.x, a.y, BODY_R * (2.2 - 0.9 * a.sk), 0.06, 3, fx.clock * 8);
      strokePath(ctx, c.light, 2, 0.3 + 0.5 * a.sk);
      return;
    }
    const fade = fadeOf(a);
    lanes(fx, ctx, a, c.dark, PSY_V, 0.22 * fade, 0.45 * fade);
    for (let n = fx.perSec(18 * fade); n > 0; n--) {
      const p = dot(fx, 'ring', a.x, a.y, 0, 0, 0.35, BODY_R * 0.9, Math.random() < 0.5 ? PSY_V : c.dark, 2);
      p.w = 2;
      p.add = false;
    }
    fx.ink.glow(ctx, PSY_V, a.x, a.y, BODY_R * 1.8, 0.35 * fade);
  },
  swing(fx, ctx, a, t) {                            // 앞으로 밀려 나가는 염동 물결 (반지름 = 맞는 거리)
    const R = a.reach, span = a.mk === 'dash' ? 0.6 : 0.95;
    for (let i = 0; i < 3; i++) {
      const k = clamp01(t * 1.6 - i * 0.2);
      if (k <= 0 || k >= 1) continue;
      wobbleArc(ctx, a.x, a.y, R * (0.6 + 0.6 * easeOut(k)), a.ang - span, a.ang + span, 0.06, 1.5, fx.clock * 10 + i);
      ctx.globalCompositeOperation = 'source-over';
      strokePath(ctx, i % 2 ? PSY_V : a.c.dark, 3 + 7 * (1 - k), 0.9 * (1 - k));
      ctx.globalCompositeOperation = 'lighter';
      strokePath(ctx, a.c.light, 1.5, 0.8 * (1 - k));
    }
    fx.ink.glow(ctx, PSY_V, a.x + a.ux * R * 0.7, a.y + a.uy * R * 0.7, R * 0.8, 0.45 * (1 - t));
  },
};

// ================================================================ ghost
// 촉수 하나 → XS · YS · WS (n 점). 뒤로 갈수록 크게 흔들리고 끝이 살짝 떠오른다
function tendril(q, k, t, n) {
  const { x, y, r, ux, uy } = q, px = -uy, py = ux, spread = (k - 1) * r * 0.5, L = r * (3 + 0.9 * hash(q.seed + k));
  for (let i = 0; i < n; i++) {
    const f = i / (n - 1), d = r * 0.4 + L * f;
    const o = spread * (0.6 + f) + Math.sin(f * 5 - t * 9 + k * 2.1 + q.seed) * r * 0.45 * f;
    XS[i] = x - ux * d + px * o;
    YS[i] = y - uy * d + py * o - f * f * r * 0.7;
    WS[i] = r * 0.42 * (1 - f) + 0.5;
  }
}

const ghost = {
  shot(fx, ctx, q) {
    const { x, y, r, c, ux, uy } = q, t = fx.clock, s = q.seed;
    const bx = -ux, by = -uy - 0.5, back = Math.atan2(by, bx), deep = shade(c.dark, 0.45);   // 불은 뒤 + 위로 핥는다
    fx.ink.glow(ctx, c.dark, x, y, r * 3, 0.45);    // 0 보랏빛 기운
    ctx.globalCompositeOperation = 'source-over';    // 1 연기 - 뒤로 처지며 부푼다
    for (let i = 1; i <= 4; i++) {
      const d = r * 0.85 * i, w = Math.sin(t * 5 + i * 1.3 + s) * r * 0.35;
      fx.ink.soft(ctx, SMOKE, x - ux * d - uy * w, y - uy * d + ux * w - i * 2, r * (1.1 + 0.3 * i), 0.8 - i * 0.12);
    }
    for (let k = 0; k < 3; k++) {                    // 2 촉수 셋 - 짙은 보라 몸 + 빛나는 테
      tendril(q, k, t, 10);
      taper(ctx, 10);
      ctx.globalCompositeOperation = 'source-over';
      fillPath(ctx, deep, 0.75);
      ctx.globalCompositeOperation = 'lighter';
      strokePath(ctx, k === 1 ? c.light : c.dark, 1.2, 0.6);
    }
    ctx.globalCompositeOperation = 'source-over';    // 3 혼불 - 짙은 겉불 · 빛나는 테 · 보랏빛 속불
    wispBlob(ctx, x, y, r * 1.3, back, t, s);
    fillPath(ctx, deep, 0.9);
    ctx.globalCompositeOperation = 'lighter';
    strokePath(ctx, c.light, 1.6, 0.75);
    wispBlob(ctx, x, y, r * 0.95, back, t + 0.4, s + 5);
    fillPath(ctx, c.dark, 0.7);
    ctx.globalCompositeOperation = 'source-over';    // 4 어둡게 꺼진 심 + 두 눈 (가끔 깜박인다)
    fx.ink.soft(ctx, SMOKE, x, y, r * 0.9, 0.95);
    const open = clamp01((noise1(t * 2.2 + s) - 0.12) * 5);
    if (open < 0.05) return;
    ctx.globalCompositeOperation = 'lighter';
    for (let sg = -1; sg <= 1; sg += 2) {
      const ex = x + sg * r * 0.3 + ux * r * 0.15, ey = y - r * 0.1 + uy * r * 0.15;
      fx.ink.glow(ctx, c.light, ex, ey, r * 0.5, 0.6 * open);
      ctx.beginPath();
      ctx.ellipse(ex, ey, r * 0.12, r * 0.22 * open, -sg * 0.4, 0, TAU);
      fillPath(ctx, EYE, 0.9);
    }
  },
  trail(fx, q) {
    const { x, y, r, c } = q, k = r / 14;
    for (let n = fx.perSec(16); n > 0; n--) {        // 피어오르는 혼불
      dot(fx, 'wisp', x + rnd(-0.6, 0.6) * r, y + rnd(-0.6, 0.6) * r, -q.ux * 30 + rnd(-15, 15), -q.uy * 30 - 20,
        rnd(0.35, 0.55), rnd(5, 8) * k, c.dark, 0.3, 1.5, -90);
    }
    for (let n = fx.perSec(14); n > 0; n--) {        // 검은 연기 (몸 아래 층)
      dot(fx, 'smoke', x - q.ux * r + rnd(-0.5, 0.5) * r, y - q.uy * r + rnd(-0.5, 0.5) * r, rnd(-20, 20), rnd(-30, -5),
        rnd(0.45, 0.7), r * rnd(0.8, 1.1), SMOKE, 2, 2).layer = 0;
    }
  },
  launch(fx, q) { fx.burst(q.x, q.y, GHOST_PUFF, q.c, 0.6, q.ang + Math.PI, 2.4); },
  debris: 'wisp',
  impact(fx, x, y, ang, c, info) {                  // 검은 연기가 터지고 혼불이 맴돌며 솟는다
    const s = info.s || 1;
    if (info.why === 'ring') {
      rim(fx, x, y, info.r, GHOST_PUFF, c, 0.2);
      rim(fx, x, y, info.r, GHOST_FIRE, c, 0.25);
      return;
    }
    fx.burst(x, y, GHOST_PUFF, c, 1.2 * s);
    fx.burst(x, y, GHOST_FIRE, c, s, -Math.PI / 2, 2.4);
    for (let i = 0, n = Math.round(9 * s); i < n; i++) {
      const a = (i / n) * TAU, cx = Math.cos(a), cy = Math.sin(a), v = rnd(70, 130);
      dot(fx, 'wisp', x + cx * 18, y + cy * 18, (-cy + cx * 0.6) * v, (cx + cy * 0.6) * v, rnd(0.4, 0.6), rnd(8, 12),
        c.light, 0.4, 1.5, -60);
    }
    darkWave(fx, x, y, SMOKE, 110 * s, 0.45, 10);
    fx.wave(x, y, c.light, 90 * s, 0.4, 4);
  },
  ring(fx, ctx, q) {
    const { x, y, r, c } = q, t = fx.clock;
    if (q.phase === 'mark') {                       // 안을 맴도는 혼불 - 찰수록 빨리
      for (let i = 0; i < 5; i++) {
        const a = t * (1 + 2 * q.u) + (i * TAU) / 5 + q.seed;
        fx.ink.stretch(ctx, c.light, x + Math.cos(a) * r * 0.6, y + Math.sin(a) * r * 0.6 - 6, 6, 14, 0.2 + 0.4 * q.u);
      }
      return;
    }
    const { rr, e } = q, f = 1 - e, deep = shade(c.dark, 0.45);
    ctx.globalCompositeOperation = 'source-over';   // 검은 연기 띠 - 그 위라야 보랏빛이 보랏빛으로 보인다
    for (let i = 0; i < 16; i++) {
      const a = (i * TAU) / 16 + q.seed;
      fx.ink.soft(ctx, SMOKE, x + Math.cos(a) * rr, y + Math.sin(a) * rr, rr * 0.3, f);
    }
    halo(ctx, deep, 0.85 * f, rr * 0.11 * f + 1, x, y, rr);
    ctx.globalCompositeOperation = 'lighter';
    halo(ctx, c.dark, 0.9 * f, rr * 0.04 * f + 1, x, y, rr);
    for (let i = 0; i < 18; i++) {                   // 고리를 따라 위로 핥는 혼불
      const a = (i * TAU) / 18 + q.seed, L = rr * 0.26 * (0.5 + 0.9 * noise1(t * 6 + i * 1.3));
      const fx0 = x + Math.cos(a) * rr, fy0 = y + Math.sin(a) * rr;
      fx.ink.stretch(ctx, c.dark, fx0, fy0 - L * 0.8, L * 0.4, L * 1.1, f);
      fx.ink.stretch(ctx, c.light, fx0, fy0 - L * 0.4, L * 0.16, L * 0.5, 0.8 * f);
    }
    halo(ctx, c.light, 0.6 * f, 1.5, x, y, rr);
  },
  rush(fx, ctx, a) {
    const { c } = a, now = fx.clock;
    if (a.stage === 'wind') {                       // 몸이 그림자로 가라앉는다
      windUp(fx, ctx, a, c.light);
      ctx.globalCompositeOperation = 'source-over';
      fx.ink.soft(ctx, SMOKE, a.x, a.y + 6, BODY_R * (1.6 + 0.4 * a.sk), 0.3 + 0.4 * a.sk);
      return;
    }
    const fade = fadeOf(a);
    ctx.globalCompositeOperation = 'source-over';   // 그림자 띠 + 지나온 자리에 남는 그림자 몸
    ribbon(ctx, a.trail, now, 0.32, a.reach * 1.7, a.reach * 0.6, shade(c.dark, 0.35), 0.35 * fade);
    for (let i = 2; i < a.trail.n; i += 2) {
      const k = (now - a.trail.t(i)) / 0.32;
      if (!(k < 1)) break;
      fx.ink.soft(ctx, SMOKE, a.trail.x(i), a.trail.y(i), BODY_R * (1.5 + 0.6 * k), 0.85 * (1 - k) * fade);
    }
    ctx.globalCompositeOperation = 'lighter';
    ribbon(ctx, a.trail, now, 0.2, BODY_R * 1.2, 3, c.dark, 0.55 * fade);
    for (let n = fx.perSec(30 * fade); n > 0; n--) {
      dot(fx, 'wisp', a.x + rnd(-1, 1) * BODY_R, a.y + rnd(-1, 1) * BODY_R, -a.ux * 40, -a.uy * 40 - 20, rnd(0.3, 0.5),
        rnd(8, 12), Math.random() < 0.5 ? c.light : c.dark, 0.3, 1.5, -80);
    }
  },
  swing(fx, ctx, a, t) {                            // 보랏빛 혼불 초승달 - 바깥 가장자리를 혼불이 핥는다
    const R = a.reach, w = sweep(a, t, a.mk === 'dash' ? 0.8 : 1.25), { from, to, fade } = w;
    ctx.globalCompositeOperation = 'source-over';
    crescent(ctx, a.x, a.y, R * 1.05, from, to, R * 0.4);
    fillPath(ctx, SMOKE, 0.55 * fade);
    ctx.globalCompositeOperation = 'lighter';
    crescent(ctx, a.x, a.y, R, from, to, R * 0.28);
    fillPath(ctx, a.c.dark, 0.85 * fade);
    crescent(ctx, a.x, a.y, R * 0.97, from + (to - from) * 0.2, to, R * 0.12);
    fillPath(ctx, a.c.light, fade);
    for (let i = 0; i < 7; i++) {
      const aa = from + ((to - from) * (i + 0.5)) / 7, L = R * 0.2 * (0.6 + 0.8 * noise1(fx.clock * 8 + i * 1.7));
      streak(fx, ctx, a.c.light, a.x + Math.cos(aa) * (R + L * 0.6), a.y + Math.sin(aa) * (R + L * 0.6), aa, L, 4, 0.7 * fade);
    }
  },
};

// ================================================================ dark
const dark = {
  shot(fx, ctx, q) {
    const { x, y, r, c, ux, uy } = q, t = fx.clock, s = q.seed, spin = hash(s) < 0.5 ? -1 : 1;
    fx.ink.glow(ctx, EDGE, x, y, r * 2.6, 0.3);     // 1 연기를 뒤에서 비추는 보랏빛
    ctx.globalCompositeOperation = 'source-over';    // 2 검보라 연기 - 굽이치며 꼬리로 (겹쳐서 짙게)
    for (let i = 0; i < 7; i++) {
      const d = r * (0.2 + 0.6 * i), w = (noise1(t * 3 + i * 0.7 + s) - 0.5) * r * (0.6 + 0.25 * i);
      const R = r * (1.2 + 0.18 * i + 0.15 * Math.sin(t * 7 + i * 2 + s));
      fx.ink.soft(ctx, i % 2 ? VOID : SMOKE, x - ux * d - uy * w, y - uy * d + ux * w, R, 0.95 - i * 0.11);
    }
    fx.ink.soft(ctx, VOID, x, y, r * 2, 0.9);
    wobble(ctx, x, y, r * 0.95, 0.05, 5, t * 6 + s, 20);   // 3 빈 속
    fillPath(ctx, VOID, 1);
    ctx.globalCompositeOperation = 'lighter';
    strokePath(ctx, EDGE, 1.6, 0.9);
    for (let i = 0; i < 3; i++) {                    // 4 감아 도는 날카로운 초승달 셋 (보통 혼합 보라 + 흰 날)
      const a = spin * t * 7 + (i * TAU) / 3 + s, R = r * (1.55 + 0.1 * Math.sin(t * 9 + i));
      crescent(ctx, x, y, R, a, a + spin * 1.7, r * 0.42);
      ctx.globalCompositeOperation = 'source-over';
      fillPath(ctx, EDGE, 0.9);
      ctx.globalCompositeOperation = 'lighter';
      crescent(ctx, x, y, R, a + spin * 0.6, a + spin * 1.7, r * 0.12);
      fillPath(ctx, WHITE, 0.7);
    }
    spikes(ctx, x, y, r * 1.25, 9, 0.7, -spin * t * 4 + s);   // 5 가시 테 - 거꾸로 돈다
    strokePath(ctx, EDGE, 1, 0.6);
  },
  trail(fx, q) {
    const { x, y, r } = q;
    for (let n = fx.perSec(26); n > 0; n--) {        // 검은 연기 (몸 아래 층)
      dot(fx, 'smoke', x - q.ux * r * 0.8 + rnd(-0.5, 0.5) * r, y - q.uy * r * 0.8 + rnd(-0.5, 0.5) * r, rnd(-25, 25),
        rnd(-25, 25), rnd(0.5, 0.75), r * rnd(1, 1.3), Math.random() < 0.5 ? VOID : SMOKE, 2, 2).layer = 0;
    }
    for (let n = fx.perSec(7); n > 0; n--) {         // 떨어져 나가는 날 조각
      const a = q.ang + Math.PI + rnd(-1.4, 1.4), v = rnd(50, 110);
      const p = dot(fx, 'shard', x, y, Math.cos(a) * v, Math.sin(a) * v, rnd(0.25, 0.4), rnd(4, 6), EDGE, 1, 2);
      p.rot = a;
      p.vr = rnd(-10, 10);
    }
  },
  launch(fx, q) {
    fx.burst(q.x, q.y, DARK_PUFF, q.c, 0.5, q.ang + Math.PI, 2);
    slash(fx, q.x, q.y, q.ang + Math.PI / 2, q.r * 4, EDGE, 4, 0.18);
  },
  debris: DARK_SHARD,
  impact(fx, x, y, ang, c, info) {                  // 연기가 터지고 날이 엇갈린다
    const s = info.s || 1;
    if (info.why === 'ring') {
      rim(fx, x, y, info.r, DARK_PUFF, c, 0.15);
      rim(fx, x, y, info.r, DARK_SHARD, c, 0.25);
      return;
    }
    fx.burst(x, y, DARK_PUFF, c, 1.2 * s);
    for (let i = 0; i < 3; i++) {
      const a = ang + Math.PI / 2 + (i - 1) * 0.7 + rnd(-0.2, 0.2), L = 75 * s * rnd(0.8, 1.2);
      slash(fx, x, y, a, L, EDGE, 7, 0.3);
      slash(fx, x, y, a, L * 0.85, WHITE, 2, 0.22);
    }
    fx.burst(x, y, DARK_SHARD, c, 0.8 * s);
    darkWave(fx, x, y, VOID, 100 * s, 0.4, 12);
  },
  ring(fx, ctx, q) {
    const { x, y, r } = q, t = fx.clock;
    if (q.phase === 'mark') {                       // 안을 맴도는 검은 연기 + 옅은 날
      ctx.globalCompositeOperation = 'source-over';
      for (let i = 0; i < 6; i++) {
        const a = t * (0.8 + 1.5 * q.u) + (i * TAU) / 6 + q.seed;
        fx.ink.soft(ctx, SMOKE, x + Math.cos(a) * r * 0.5, y + Math.sin(a) * r * 0.5, r * 0.3, 0.2 + 0.3 * q.u);
      }
      ctx.globalCompositeOperation = 'lighter';
      const a = -t * 3 + q.seed;
      crescent(ctx, x, y, r * 0.7, a, a + 1.4, r * 0.08);
      fillPath(ctx, EDGE, 0.2 + 0.4 * q.u);
      return;
    }
    const { rr, e } = q, f = 1 - e;
    ctx.globalCompositeOperation = 'source-over';   // 검은 연기 물결 (겹쳐서 짙게)
    for (let i = 0; i < 16; i++) {
      const a = (i * TAU) / 16 + q.seed, d = rr * (0.82 + 0.12 * Math.sin(i * 2.3 + t * 5));
      fx.ink.soft(ctx, i % 2 ? VOID : SMOKE, x + Math.cos(a) * d, y + Math.sin(a) * d, rr * 0.26, 0.9 * f);
    }
    for (let i = 0; i < 6; i++) {                    // 고리를 따라 도는 날 - 보통 혼합 보라 + 흰 날
      const a = t * 5 + (i * TAU) / 6 + q.seed;
      crescent(ctx, x, y, rr, a, a + 0.8, rr * 0.12 * f + 2);
      ctx.globalCompositeOperation = 'source-over';
      fillPath(ctx, EDGE, 0.95 * f);
      ctx.globalCompositeOperation = 'lighter';
      crescent(ctx, x, y, rr, a + 0.3, a + 0.8, rr * 0.035 + 1);
      fillPath(ctx, WHITE, 0.8 * f);
    }
  },
  cone(fx, ctx, q) {
    const { x, y, len, ang, h } = q, t = fx.clock;
    if (q.phase === 'mark') {
      for (let i = 0; i < 2; i++) {
        const ph = (t * 0.8 + i / 2) % 1;
        crescent(ctx, x, y, len * (0.2 + 0.75 * ph), ang - h, ang + h, 6);
        fillPath(ctx, EDGE, 0.35 * q.u * (1 - ph));
      }
      return;
    }
    const e = q.e, f = 1 - e;
    ctx.globalCompositeOperation = 'source-over';
    for (let i = 0; i < 10; i++) {
      const d = len * (0.15 + 0.8 * hash(q.seed + i)) * easeOut(e), a = ang + (hash(q.seed + i + 9) - 0.5) * 1.6 * h;
      fx.ink.soft(ctx, i % 2 ? VOID : SMOKE, x + Math.cos(a) * d, y + Math.sin(a) * d, len * 0.15, 0.85 * f);
    }
    for (let i = 0; i < 3; i++) {                    // 퍼지는 날카로운 호 - 보통 혼합 보라 + 흰 날
      const k = clamp01(e * 1.6 - i * 0.2);
      if (k <= 0 || k >= 1) continue;
      const R = len * (0.2 + 0.8 * easeOut(k));
      crescent(ctx, x, y, R, ang - h, ang + h, len * 0.08 * (1 - k) + 2);
      ctx.globalCompositeOperation = 'source-over';
      fillPath(ctx, EDGE, 0.9 * (1 - k));
      ctx.globalCompositeOperation = 'lighter';
      crescent(ctx, x, y, R, ang - h * 0.7, ang + h * 0.7, 2);
      fillPath(ctx, WHITE, 0.7 * (1 - k));
    }
  },
  rush(fx, ctx, a) {
    const now = fx.clock;
    if (a.stage === 'wind') {
      windUp(fx, ctx, a, EDGE);
      ctx.globalCompositeOperation = 'source-over';
      fx.ink.soft(ctx, VOID, a.x, a.y, BODY_R * (1.5 + 0.5 * a.sk), 0.3 + 0.4 * a.sk);
      return;
    }
    const fade = fadeOf(a);
    ctx.globalCompositeOperation = 'source-over';   // 검은 연기 띠
    ribbon(ctx, a.trail, now, 0.32, a.reach * 1.6, a.reach * 0.6, VOID, 0.4 * fade);
    ctx.globalCompositeOperation = 'lighter';
    ribbon(ctx, a.trail, now, 0.2, BODY_R * 1.2, 2, EDGE, 0.6 * fade);
    speedLines(fx, ctx, a, EDGE, fade);
    for (let n = fx.perSec(26 * fade); n > 0; n--) {
      dot(fx, 'smoke', a.x + rnd(-1, 1) * BODY_R, a.y + rnd(-1, 1) * BODY_R, rnd(-20, 20), rnd(-20, 20), rnd(0.4, 0.6),
        BODY_R * rnd(0.7, 1), VOID, 2, 2).layer = 0;
    }
  },
  swing(fx, ctx, a, t) {                            // 어둠을 가르는 날 - 검은 그림자 · 보라 날 · 흰 실선, 뒤이어 엇갈린 날
    const R = a.reach;
    for (let j = 0; j < 2; j++) {
      const tt = t - j * 0.18;
      if (tt <= 0) continue;
      const { from, to, fade } = sweep(a, tt, (a.mk === 'dash' ? 0.75 : 1.3) * (1 - j * 0.25), j ? -1 : 1, 2);
      const rr = R * (1 - j * 0.12);
      ctx.globalCompositeOperation = 'source-over';
      crescent(ctx, a.x, a.y, rr * 1.06, from, to, rr * 0.42);
      fillPath(ctx, VOID, 0.6 * fade);
      ctx.globalCompositeOperation = 'lighter';
      crescent(ctx, a.x, a.y, rr, from, to, rr * 0.22);
      fillPath(ctx, EDGE, 0.95 * fade);
      crescent(ctx, a.x, a.y, rr, from + (to - from) * 0.3, to, rr * 0.05);
      fillPath(ctx, WHITE, fade);
    }
  },
};

// ================================================================ fairy
const fairy = {
  shot(fx, ctx, q) {
    const { x, y, r, c, ux, uy } = q, t = fx.clock, s = q.seed;
    fx.ink.glow(ctx, c.dark, x, y, r * 3.2, 0.3);
    softTail(fx, ctx, q, c.dark, 0.3, r * 1.6, 0.35);
    ctx.globalCompositeOperation = 'source-over';    // 색이 살게 보통 혼합: 분홍 달무리
    circle(ctx, x, y, r * 1.45);
    fillPath(ctx, c.dark, 0.35);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, MOON, x, y, r * 1.8, 0.4 + 0.1 * Math.sin(t * 6 + s));
    const face = q.ang + Math.sin(q.age * 3 + s) * 0.25;   // 달 - 볼록한 쪽이 앞, 분홍 테
    crescent(ctx, x, y, r * 1.15, face - 1.9, face + 1.9, r * 1.05);
    ctx.globalCompositeOperation = 'source-over';
    fillPath(ctx, MOON, 0.95);
    strokePath(ctx, c.dark, 1.5, 0.9);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.core(ctx, c.light, x + ux * r * 0.45, y + uy * r * 0.45, r * 0.8, 0.7);
    const tilt = hash(s) * TAU, i0 = Math.floor(hash(s + 1) * 5);   // 감아 도는 별 넷 (보통 혼합 파스텔 + 흰 반짝)
    for (let i = 0; i < 4; i++) {
      const a = t * 3.2 + (i * TAU) / 4 + s, near = 0.55 + 0.45 * Math.sin(a), g = orbit(x, y, a, r * 1.9, r * 0.85, tilt);
      star5(ctx, g.x, g.y, r * 0.34 * (0.7 + 0.5 * near), t * 4 + i);
      ctx.globalCompositeOperation = 'source-over';
      fillPath(ctx, PASTEL[(i + i0) % 5], 0.7 + 0.3 * near);
      strokePath(ctx, c.dark, 1, 0.8);
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.star(ctx, WHITE, g.x, g.y, r * 0.6 * near, 0.6);
    }
    const sw = Math.sin(t * 4 + s), hx = x - ux * r * 1.9 - uy * sw * r * 0.4, hy = y - uy * r * 1.9 + ux * sw * r * 0.4;
    fx.ink.glow(ctx, HEART, hx, hy, r * 0.9, 0.4);  // 뒤를 따라오는 하트
    heart(ctx, hx, hy, r * 0.45, sw * 0.3);
    ctx.globalCompositeOperation = 'source-over';
    fillPath(ctx, HEART, 0.95);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, WHITE, hx - r * 0.15, hy - r * 0.15, r * 0.18, 0.8);
    const tick = Math.floor(t * 12);                // 반짝임 - 1/12초마다 자리가 바뀐다
    for (let i = 0; i < 3; i++) {
      const h1 = hash(s + tick * 3 + i), h2 = hash(s + tick * 7 + i * 5);
      fx.ink.star(ctx, WHITE, x + (h1 - 0.5) * r * 4, y + (h2 - 0.5) * r * 4, r * (0.5 + 0.5 * h1), 0.9);
    }
  },
  trail(fx, q) {
    const { x, y, r, c } = q;
    for (let n = fx.perSec(20); n > 0; n--) {        // 파스텔 별 가루 (보통 혼합이라야 색이 남는다)
      const a = rnd(0, TAU), v = rnd(15, 50);
      dot(fx, 'star', x + Math.cos(a) * r, y + Math.sin(a) * r, Math.cos(a) * v, Math.sin(a) * v - 15, rnd(0.4, 0.7),
        rnd(6, 10), Math.random() < 0.4 ? c.dark : pastel(), 0.3, 2, -20).add = false;
    }
    for (let n = fx.perSec(8); n > 0; n--) {
      dot(fx, 'glow', x + rnd(-1, 1) * r, y + rnd(-1, 1) * r, 0, -25, rnd(0.4, 0.6), rnd(3, 5), c.light, 0.5, 1);
    }
  },
  launch(fx, q) {
    fx.wave(q.x, q.y, q.c.dark, q.r * 3.5, 0.35, 3);
    fx.burst(q.x, q.y, FAIRY_STAR, q.c, 0.5, q.ang, 1.6);
  },
  debris: FAIRY_STAR,
  impact(fx, x, y, ang, c, info) {                  // 달빛 번쩍 + 파스텔 별이 흩어진다
    const s = info.s || 1;
    if (info.why === 'ring') {
      rim(fx, x, y, info.r, FAIRY_STAR, c, 0.25);
      return;
    }
    dot(fx, 'core', x, y, 0, 0, 0.22, 40 * s, MOON, 2.2);
    fx.wave(x, y, c.dark, 100 * s, 0.45, 5);
    fx.wave(x, y, MOON, 70 * s, 0.35, 3);
    for (let i = 0, n = Math.round(14 * s); i < n; i++) {
      const a = rnd(0, TAU), v = rnd(120, 260);
      dot(fx, 'star', x, y, Math.cos(a) * v, Math.sin(a) * v, rnd(0.45, 0.7), rnd(8, 13), pastel(), 0.3, 3.5, 40).add = false;
    }
    for (let i = 0; i < 6; i++) dot(fx, 'glow', x + rnd(-30, 30), y + rnd(-30, 30), 0, rnd(-60, -30), rnd(0.5, 0.8), 5, c.light, 0.5, 1);
  },
  ring(fx, ctx, q) {
    const { x, y, r, c } = q, t = fx.clock;
    if (q.phase === 'mark') {                       // 안에서 반짝이는 별
      const tick = Math.floor(t * 6);
      for (let i = 0; i < 8; i++) {
        const a = hash(q.seed + i) * TAU, d = r * 0.85 * Math.sqrt(hash(q.seed + i * 3 + 1)), tw = hash(q.seed + i + tick * 9);
        fx.ink.star(ctx, PASTEL[i % 5], x + Math.cos(a) * d, y + Math.sin(a) * d, 8 + 10 * tw, (0.2 + 0.5 * tw) * q.u);
      }
      return;
    }
    const { rr, e } = q, f = 1 - e;
    fx.ink.glow(ctx, c.dark, x, y, rr * 1.1, 0.4 * f);
    fx.ink.glow(ctx, MOON, x, y, rr * 0.6, 0.3 * f);
    ctx.globalCompositeOperation = 'source-over';   // 분홍 물결 (보통 혼합이라야 분홍이다) + 파스텔 별
    halo(ctx, c.dark, 0.7 * f, rr * 0.09 * f + 1, x, y, rr);
    halo(ctx, c.dark, 0.35 * f, rr * 0.05 * f + 1, x, y, rr * 0.86);
    for (let i = 0; i < 14; i++) {                   // 고리를 따라 도는 별
      const a = t * 1.5 + (i * TAU) / 14, sx = x + Math.cos(a) * rr, sy = y + Math.sin(a) * rr;
      star5(ctx, sx, sy, 13 * (1 + 0.3 * Math.sin(t * 9 + i)), t * 3 + i);
      fillPath(ctx, PASTEL[i % 5], f);
      strokePath(ctx, c.dark, 1, f);
    }
    ctx.globalCompositeOperation = 'lighter';
    halo(ctx, WHITE, 0.8 * f, 2 * f + 0.5, x, y, rr);
    for (let i = 0; i < 14; i += 2) {
      const a = t * 1.5 + (i * TAU) / 14;
      fx.ink.star(ctx, WHITE, x + Math.cos(a) * rr, y + Math.sin(a) * rr, 18, 0.8 * f);
    }
  },
  cone(fx, ctx, q) {
    const { x, y, len, ang, h, c } = q, t = fx.clock;
    if (q.phase === 'mark') {                       // 옅게 떠가는 하트
      for (let i = 0; i < 3; i++) {
        const ph = (t * 0.5 + i / 3) % 1, a = ang + (hash(q.seed + i) - 0.5) * 1.4 * h, d = len * (0.15 + 0.75 * ph);
        heart(ctx, x + Math.cos(a) * d, y + Math.sin(a) * d - ph * 10, 9, Math.sin(t * 3 + i) * 0.3);
        fillPath(ctx, HEART, 0.4 * q.u * (1 - ph));
      }
      return;
    }
    const e = q.e, f = 1 - e;
    wedge(ctx, x, y, len * easeOut(e), ang, h);
    ctx.globalCompositeOperation = 'source-over';
    fillPath(ctx, c.dark, 0.3 * f);
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 8; i++) {                    // 부채꼴을 따라 퍼지는 하트 + 별
      const a = ang + (hash(q.seed + i) - 0.5) * 1.6 * h, sp = 0.55 + 0.45 * hash(q.seed + i + 20);
      const d = len * (0.1 + 0.85 * sp * easeOut(e)), hx = x + Math.cos(a) * d, hy = y + Math.sin(a) * d - e * 14;
      if (i % 2) {
        fx.ink.glow(ctx, HEART, hx, hy, 24, 0.45 * f);
        heart(ctx, hx, hy, 10 + 6 * e, Math.sin(t * 4 + i) * 0.35);
        ctx.globalCompositeOperation = 'source-over';
        fillPath(ctx, HEART, f);
        strokePath(ctx, WHITE, 1, 0.7 * f);
      } else {
        star5(ctx, hx, hy, 9 + 3 * e, t * 5 + i);
        ctx.globalCompositeOperation = 'source-over';
        fillPath(ctx, PASTEL[i % 5], f);
        strokePath(ctx, c.dark, 1, f);
      }
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.star(ctx, WHITE, hx + 6, hy - 6, 12, 0.7 * f);
    }
  },
  rush(fx, ctx, a) {
    const { c } = a;
    if (a.stage === 'wind') {
      windUp(fx, ctx, a, c.light);
      fx.ink.star(ctx, WHITE, a.x, a.y - BODY_R, 10 + 12 * a.sk, 0.4 + 0.5 * a.sk);
      return;
    }
    const fade = fadeOf(a);
    lanes(fx, ctx, a, c.dark, MOON, 0.24 * fade, 0.45 * fade);
    for (let n = fx.perSec(40 * fade); n > 0; n--) {
      dot(fx, 'star', a.x + rnd(-1, 1) * BODY_R, a.y + rnd(-1, 1) * BODY_R, rnd(-30, 30), rnd(-40, 0), rnd(0.35, 0.6),
        rnd(7, 11), Math.random() < 0.4 ? c.dark : pastel(), 0.3, 2).add = false;
    }
  },
  swing(fx, ctx, a, t) {                            // 분홍 초승달 + 호를 따라 남는 별, 끝에 하트가 떠오른다
    const R = a.reach, { from, to, fade } = sweep(a, t, a.mk === 'dash' ? 0.7 : 1.2);
    crescent(ctx, a.x, a.y, R, from, to, R * 0.28);
    ctx.globalCompositeOperation = 'source-over';
    fillPath(ctx, a.c.dark, 0.85 * fade);
    ctx.globalCompositeOperation = 'lighter';
    crescent(ctx, a.x, a.y, R * 0.97, from + (to - from) * 0.25, to, R * 0.1);
    fillPath(ctx, MOON, fade);
    for (let i = 0; i < 5; i++) {
      const aa = from + ((to - from) * (i + 0.5)) / 5, rr = R * (0.85 + 0.3 * hash(a.seed + i));
      const sx = a.x + Math.cos(aa) * rr, sy = a.y + Math.sin(aa) * rr;
      star5(ctx, sx, sy, 6 + 4 * hash(a.seed + i * 3), fx.clock * 4 + i);
      ctx.globalCompositeOperation = 'source-over';
      fillPath(ctx, PASTEL[i % 5], fade);
      strokePath(ctx, a.c.dark, 1, fade);
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.star(ctx, WHITE, sx, sy, 12, 0.8 * fade);
    }
    if (a.stage !== 'tail') return;
    const k = a.sk, hx = a.x + a.ux * R * 0.8, hy = a.y + a.uy * R * 0.8 - 30 * k;
    ctx.globalCompositeOperation = 'source-over';
    for (let sg = -1; sg <= 1; sg += 2) {
      heart(ctx, hx + sg * 14, hy - (sg + 1) * 4, 9 + 4 * k, sg * 0.3);
      fillPath(ctx, HEART, 1 - k);
    }
  },
};

// ================================================================ orb
const orb = {
  shot(fx, ctx, q) {
    const { x, y, r, c, ux, uy, ang } = q, t = fx.clock, s = q.seed;
    ribbon(ctx, q.trail, t, 0.12, r * 1.1, 1, c.light, 0.25);
    streak(fx, ctx, c.dark, x - ux * r * 1.7, y - uy * r * 1.7, ang, r * 3.4, r, 0.55);   // 늘어난 빛 (움직임 흐림)
    streak(fx, ctx, c.light, x - ux * r * 0.9, y - uy * r * 0.9, ang, r * 2.2, r * 0.55, 0.75);
    const tick = Math.floor(t * 20), px = -uy, py = ux;  // 속도선 - 1/20초마다 바뀐다
    ctx.globalAlpha = 0.6;
    ctx.strokeStyle = WHITE;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < 5; i++) {
      const o = (hash(s + tick * 5 + i) - 0.5) * r * 2.4, b0 = r * (1.1 + hash(s + i + tick) * 0.6);
      const b1 = b0 + r * (1.2 + 2.4 * hash(s + i * 3 + tick));
      ctx.moveTo(x + px * o - ux * b0, y + py * o - uy * b0);
      ctx.lineTo(x + px * o - ux * b1, y + py * o - uy * b1);
    }
    ctx.stroke();
    fx.ink.glow(ctx, c.dark, x, y, r * 2.4, 0.55);
    for (let i = 0; i < 2; i++) {                    // 팽이처럼 도는 고리 둘
      const sp = t * (7 + i * 2.5) + s + i;
      ctx.beginPath();
      ctx.ellipse(x, y, r * 1.5, Math.abs(Math.cos(sp)) * r * 1.5 + 0.5, ang + i * Math.PI / 2 + Math.sin(t * 2 + s) * 0.3, 0, TAU);
      strokePath(ctx, i ? WHITE : c.light, 1.3, 0.65);
    }
    fx.ink.core(ctx, c.light, x, y, r * 1.3, 1);
    fx.ink.glow(ctx, WHITE, x, y, r * 0.55, 0.9);
  },
  trail(fx, q) {
    const { x, y, r, c } = q;
    for (let n = fx.perSec(22); n > 0; n--) {        // 뒤로 흩날리는 불티
      const o = rnd(-0.8, 0.8) * r, v = rnd(60, 140);
      const p = dot(fx, 'spark', x - q.ux * r - q.uy * o, y - q.uy * r + q.ux * o, -q.ux * v + rnd(-30, 30),
        -q.uy * v + rnd(-30, 30), rnd(0.18, 0.28), 8, Math.random() < 0.5 ? WHITE : c.light, 0.4, 3);
      p.w = 1.5;
    }
    for (let n = fx.perSec(10); n > 0; n--) dot(fx, 'glow', x, y, rnd(-20, 20), rnd(-20, 20), 0.25, r * 0.5, c.light);
  },
  launch(fx, q) {
    fx.wave(q.x, q.y, WHITE, q.r * 3, 0.22, 3);
    fx.burst(q.x, q.y, ORB_SPARK, q.c, 0.4, q.ang, 1);
  },
  impact(fx, x, y, ang, c, info) {                  // 앞쪽으로 퍼지는 불티 + 흰 충격 고리 + 반짝
    const s = info.s || 1;
    fx.burst(x, y, ORB_SPARK, c, s, ang, 2.6);
    fx.wave(x, y, WHITE, 70 * s, 0.25, 4);
    for (let i = 0; i < 4; i++) dot(fx, 'star', x + rnd(-24, 24), y + rnd(-24, 24), 0, 0, rnd(0.2, 0.35), rnd(12, 20), WHITE, 0.2);
  },
  cone(fx, ctx, q) {                                // 스피드스타 - 꼬리를 끄는 별이 부채꼴로
    const { x, y, len, ang, h, c } = q, t = fx.clock;
    if (q.phase === 'mark') {
      for (let i = 0; i < 5; i++) {
        const a = ang + (hash(q.seed + i) - 0.5) * 1.7 * h, ph = (t * 0.9 + hash(q.seed + i + 5)) % 1, d = len * ph;
        streak(fx, ctx, c.light, x + Math.cos(a) * d, y + Math.sin(a) * d, a, len * 0.08, 3, 0.4 * q.u * (1 - ph));
      }
      return;
    }
    const e = q.e, f = 1 - e;
    wedge(ctx, x, y, len * easeOut(e), ang, h);
    fillPath(ctx, c.dark, 0.18 * f);
    for (let i = 0; i < 9; i++) {
      const a = ang + (hash(q.seed + i) - 0.5) * 1.8 * h, sp = 0.6 + 0.5 * hash(q.seed + i + 20);
      const d = len * Math.min(1, 0.1 + easeOut(e) * sp), sx = x + Math.cos(a) * d, sy = y + Math.sin(a) * d;
      streak(fx, ctx, c.light, sx - Math.cos(a) * len * 0.07, sy - Math.sin(a) * len * 0.07, a, len * 0.08, 4, 0.6 * f);
      star5(ctx, sx, sy, 9 + 4 * hash(q.seed + i * 7), t * 8 + i);
      fillPath(ctx, i % 3 ? c.light : WHITE, f);
      fx.ink.star(ctx, WHITE, sx, sy, 14, 0.8 * f);
    }
  },
  ring(fx, ctx, q) {                                // 대폭발 - 불덩이 · 튀는 빛줄기 · 연기 고리
    const { x, y, r, c } = q, t = fx.clock;
    if (q.phase === 'mark') {                       // 가운데로 몰려든다 - 곧 터진다
      const u = q.u, ph = (t * 2.2) % 1;
      fx.ink.glow(ctx, c.light, x, y, r * (0.2 + 0.25 * u), 0.3 + 0.5 * u);
      halo(ctx, c.light, ph * u * 0.6, 2, x, y, r * (1 - ph) * 0.9 + 1);
      return;
    }
    const { rr, e } = q, f = 1 - e;
    ctx.globalCompositeOperation = 'source-over';
    for (let i = 0; i < 12; i++) {
      const a = (i * TAU) / 12 + q.seed;
      fx.ink.soft(ctx, c.dark, x + Math.cos(a) * rr * 0.85, y + Math.sin(a) * rr * 0.85, rr * 0.3, 0.35 * f);
    }
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.core(ctx, c.light, x, y, rr * (1.1 - 0.4 * e), f);
    fx.ink.glow(ctx, WHITE, x, y, rr * 0.6 * f + 1, f);
    ctx.globalAlpha = A(f);
    ctx.strokeStyle = WHITE;
    ctx.lineWidth = 3 * f + 0.5;
    ctx.beginPath();
    for (let i = 0; i < 14; i++) {
      const a = hash(q.seed + i) * TAU, d0 = rr * 0.4, d1 = rr * (0.9 + 0.3 * hash(q.seed + i + 3));
      ctx.moveTo(x + Math.cos(a) * d0, y + Math.sin(a) * d0);
      ctx.lineTo(x + Math.cos(a) * d1, y + Math.sin(a) * d1);
    }
    ctx.stroke();
    halo(ctx, c.light, f, 10 * f + 1, x, y, rr);
    halo(ctx, WHITE, 0.8 * f, 3 * f + 0.5, x, y, rr);
  },
  tele(fx, ctx, q) {
    const { x, y, r, c } = q;
    if (q.phase === 'mark') {
      fx.ink.glow(ctx, c.light, x, y, r * 0.9, 0.1 + 0.25 * q.u);
      return;
    }
    const e = q.e, f = 1 - e;                        // 떨어진 자리 - 패인 그늘 · 번쩍 · 사방 빛줄기 · 고리
    ctx.globalCompositeOperation = 'source-over';
    fx.ink.soft(ctx, c.dark, x, y, r * 1.1, 0.5 * f);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.core(ctx, c.light, x, y, r * (1.2 - 0.5 * e), f);
    ctx.globalAlpha = A(f);
    ctx.strokeStyle = WHITE;
    ctx.lineWidth = 2.5 * f + 0.5;
    ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const a = (i * TAU) / 10 + q.seed, d0 = r * 0.3, d1 = r * (0.6 + 0.9 * easeOut(e));
      ctx.moveTo(x + Math.cos(a) * d0, y + Math.sin(a) * d0);
      ctx.lineTo(x + Math.cos(a) * d1, y + Math.sin(a) * d1);
    }
    ctx.stroke();
    halo(ctx, c.light, f, 8 * f + 1, x, y, r * (0.5 + 0.8 * e));
  },
  fall(fx, ctx, q, x, y, v) {                       // 꼬리를 끄는 유성
    const r = q.r * 0.32, t = fx.clock;
    fx.ink.stretch(ctx, q.c.dark, x, y - r * 3, r * 0.9, r * 3.6, 0.5 + 0.3 * v);
    fx.ink.stretch(ctx, q.c.light, x, y - r * 1.8, r * 0.45, r * 2.4, 0.8);
    ctx.beginPath();
    ctx.ellipse(x, y, r * 1.5, Math.abs(Math.cos(t * 8)) * r * 1.5 + 0.5, t * 2, 0, TAU);
    strokePath(ctx, WHITE, 1.5, 0.7);
    fx.ink.core(ctx, q.c.light, x, y, r * 1.2, 1);
    for (let n = fx.perSec(30); n > 0; n--) {
      dot(fx, 'spark', x + rnd(-r, r), y, rnd(-30, 30), rnd(-160, -80), rnd(0.15, 0.25), 8, q.c.light, 0.4, 3).w = 1.5;
    }
  },
  rush(fx, ctx, a) {
    const { c } = a, now = fx.clock;
    if (a.stage === 'wind') {                       // 몸에 모이는 빛 + 갈 쪽으로 뻗는 빛
      windUp(fx, ctx, a, c.light);
      fx.ink.glow(ctx, c.light, a.x, a.y, BODY_R * (1.2 + 0.6 * a.sk), 0.25 + 0.35 * a.sk);
      return;
    }
    const fade = fadeOf(a);
    lanes(fx, ctx, a, c.dark, c.light, 0.22 * fade, 0.5 * fade);
    for (let i = 3; i < a.trail.n; i += 3) {          // 잔상 - 몸 크기 고리가 지나온 자리에 남는다
      const k = (now - a.trail.t(i)) / 0.28;
      if (!(k < 1)) break;
      fx.ink.glow(ctx, c.dark, a.trail.x(i), a.trail.y(i), BODY_R * 1.3, 0.3 * (1 - k) * fade);
      halo(ctx, c.light, 0.5 * (1 - k) * fade, 2, a.trail.x(i), a.trail.y(i), BODY_R * (1 + 0.3 * k));
    }
    speedLines(fx, ctx, a, WHITE, fade);
    const v = clamp01(a.speed / 900) * fade;        // 몸 앞에 눌린 공기
    streak(fx, ctx, WHITE, a.x + a.ux * BODY_R * 1.1, a.y + a.uy * BODY_R * 1.1, a.ang + Math.PI / 2, BODY_R, 6, 0.5 * v);
  },
  swing(fx, ctx, a, t) {                            // 달리는 동안 앞의 충격파, 끝에 부딪는 번쩍 + 불티
    const k = a.reach / 86, hx = a.x + a.ux * (BODY_R + 8), hy = a.y + a.uy * (BODY_R + 8);
    if (a.stage !== 'tail') {
      const e = easeOut(clamp01(t * 2));
      ctx.beginPath();
      ctx.ellipse(hx, hy, (6 + 6 * e) * k, (18 + 22 * e) * k, a.ang, -Math.PI / 2, Math.PI / 2);
      strokePath(ctx, WHITE, 3, 0.8);
      fx.ink.glow(ctx, a.c.light, hx, hy, 30 * k, 0.5);
      return;
    }
    const e = easeOut(a.sk), f = 1 - a.sk;
    if (!a.mem.boom) {
      a.mem.boom = true;
      fx.burst(hx, hy, ORB_SPARK, a.c, 0.9, a.ang, 2);
    }
    fx.ink.core(ctx, a.c.light, hx, hy, (16 + 30 * e) * k, f);
    ctx.beginPath();
    ctx.ellipse(hx + a.ux * 14 * e * k, hy + a.uy * 14 * e * k, (8 + 14 * e) * k, (22 + 50 * e) * k, a.ang, 0, TAU);
    strokePath(ctx, WHITE, 1 + 5 * f, f);
    ctx.globalAlpha = A(f);
    ctx.strokeStyle = a.c.light;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < 7; i++) {
      const d = a.ang + (i - 3) * 0.32, r0 = (20 + 30 * e) * k, r1 = r0 + 26 * k * f;
      ctx.moveTo(hx + Math.cos(d) * r0, hy + Math.sin(d) * r0);
      ctx.lineTo(hx + Math.cos(d) * r1, hy + Math.sin(d) * r1);
    }
    ctx.stroke();
  },
};

// ================================================================ beam
// 감기는 두 가닥 (광선 틀 안 - +x 가 앞)
function helix(ctx, L, amp, ph, col, w, a) {
  const steps = Math.min(N_MAX - 1, Math.max(8, Math.round(L / 18)));
  for (let k = 0; k < 2; k++) {
    ctx.beginPath();
    for (let i = 0; i <= steps; i++) {
      const d = (L * i) / steps;
      ctx.lineTo(d, Math.sin(d * 0.035 - ph + k * Math.PI) * amp * Math.min(1, d / 40 + 0.3));
    }
    strokePath(ctx, col, w, a);
  }
}

// 광선을 따라 흐르는 덩이 넷의 자리 (0~1) - ph 는 흐름 위상
const PULSE_N = 4;
const pulseAt = (ph, i) => (ph + i / PULSE_N) % 1;

// 띠 - 가장자리가 흐르며 일렁이고, 입 쪽은 좁게 시작하고, 흐르는 덩이 자리가 부푼다
function edgeBand(ctx, L, hw, t, s, ph) {
  const n = Math.min(N_MAX - 1, Math.max(12, Math.round(L / 22)));
  for (let i = 0; i <= n; i++) {
    const d = (L * i) / n, k = Math.min(1, d / 60 + 0.45);
    let bulge = 0;
    for (let j = 0; j < PULSE_N; j++) {
      const z = (d - pulseAt(ph, j) * L) / 45;
      bulge += Math.exp(-z * z);
    }
    WS[i] = hw * k * (1 + 0.35 * bulge);
  }
  ctx.beginPath();
  for (let i = 0; i <= n; i++) {
    const d = (L * i) / n;
    ctx.lineTo(d, -WS[i] * (1 + 0.12 * Math.sin(d * 0.045 - t * 38 + s)));
  }
  for (let i = n; i >= 0; i--) {
    const d = (L * i) / n;
    ctx.lineTo(d, WS[i] * (1 + 0.12 * Math.sin(d * 0.05 - t * 41 + s + 2)));
  }
  ctx.closePath();
}

// 쏘기 전 - 입으로 모이는 빛 (표시 아래)
function beamCharge(fx, ctx, q) {
  const { x, y, c, u, ang } = q, t = fx.clock, s = q.seed, R = 12 + 30 * u;
  for (let n = fx.perSec(30 + 90 * u); n > 0; n--) {   // 빨려 드는 알갱이 - 수명 끝에 입에 닿는다
    const a = ang + rnd(-2.4, 2.4), d = rnd(70, 130) * (0.7 + 0.5 * u), life = rnd(0.2, 0.32);
    dot(fx, 'glow', x + Math.cos(a) * d, y + Math.sin(a) * d, (-Math.cos(a) * d) / life, (-Math.sin(a) * d) / life, life,
      rnd(4, 7), Math.random() < 0.3 ? WHITE : c.light, 0.3);
  }
  const tick = Math.floor(t * 15);                 // 빨려 드는 선 - 1/15초마다 자리가 바뀐다
  ctx.globalAlpha = A(0.25 + 0.5 * u);
  ctx.strokeStyle = c.light;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let i = 0; i < 8; i++) {
    const a = ang + (hash(s + tick * 8 + i) - 0.5) * 4.6, d0 = R * (2.2 + 2 * hash(s + tick + i * 3)), d1 = d0 * 0.55;
    ctx.moveTo(x + Math.cos(a) * d0, y + Math.sin(a) * d0);
    ctx.lineTo(x + Math.cos(a) * d1, y + Math.sin(a) * d1);
  }
  ctx.stroke();
  for (let i = 0; i < 2; i++) {                    // 좁아지는 고리 둘
    const ph = (t * 2.4 + i / 2) % 1;
    halo(ctx, c.light, ph * (0.3 + 0.5 * u), 1 + 2 * ph, x, y, R * (3.2 - 2.4 * ph));
  }
  fx.ink.glow(ctx, c.dark, x, y, R * 2.4, 0.35 + 0.4 * u);
  fx.ink.core(ctx, c.light, x, y, R * (0.9 + 0.1 * Math.sin(t * 30)), 0.5 + 0.5 * u);
  streak(fx, ctx, WHITE, x, y, t * 2 + s, R * 1.8, R * 1.8, 0.5 * u, 'star');
  const cs = Math.cos(ang), sn = Math.sin(ang);    // 길 위로 이는 옅은 반짝임
  for (let i = 0; i < 5; i++) {
    const d = q.len * hash(s + tick * 5 + i + 40), tw = hash(s + tick + i * 9);
    fx.ink.star(ctx, c.light, x + cs * d, y + sn * d, 6 + 8 * tw, 0.35 * u * tw);
  }
}

// 사그라들 무렵 한 번 - 광선 자리에 남는 빛 (훅이 사라진 뒤에도 잠깐) + 떠오르는 알갱이
function afterglow(fx, q) {
  const { x, y, len, ang, c, W } = q, cs = Math.cos(ang), sn = Math.sin(ang), ex = x + cs * len, ey = y + sn * len;
  const a = fx.spawn('line', x, y, 0, 0, 0.6, 1, c.dark);
  a.x2 = ex;
  a.y2 = ey;
  a.w = W * 0.6;
  const b = fx.spawn('line', x, y, 0, 0, 0.45, 1, c.light);
  b.x2 = ex;
  b.y2 = ey;
  b.w = W * 0.2;
  for (let i = 0; i < 18; i++) {
    const d = Math.random() * len, o = rnd(-0.5, 0.5) * W, v = rnd(-40, 40);
    dot(fx, 'glow', x + cs * d - sn * o, y + sn * d + cs * o, -sn * v, cs * v, rnd(0.5, 0.9), rnd(5, 10), c.light, 0.3, 1.5, -25);
  }
}

// 옆 가장자리 · 끝에서 튀는 불티 (아레나 좌표)
function beamSparks(fx, q, L, wv, cs, sn, env) {
  const { x, y, c } = q;
  for (let n = fx.perSec(120 * env); n > 0; n--) {
    const d = Math.random() * L, sg = Math.random() < 0.5 ? -1 : 1, o = sg * wv * 0.45, vo = sg * rnd(120, 300), vd = rnd(60, 260);
    dot(fx, 'spark', x + cs * d - sn * o, y + sn * d + cs * o, cs * vd - sn * vo, sn * vd + cs * vo, rnd(0.15, 0.3),
      rnd(6, 10), Math.random() < 0.4 ? WHITE : c.light, 0.4, 4).w = 1.8;
  }
  for (let n = fx.perSec(90 * env); n > 0; n--) {
    const a = q.ang + Math.PI + rnd(-1.3, 1.3), v = rnd(200, 480);
    dot(fx, 'spark', x + cs * L, y + sn * L, Math.cos(a) * v, Math.sin(a) * v, rnd(0.15, 0.32), rnd(8, 12),
      Math.random() < 0.5 ? WHITE : c.light, 0.4, 3.5).w = 2.2;
  }
}

// 쏘는 동안 (q.e 0 → 1) - 뻗고, 버티고, 가늘어지며 사라진다
function beamFire(fx, ctx, q) {
  const { x, y, len, ang, c, e, W } = q, t = fx.clock, s = q.seed;
  if (!(e < 1)) return;
  if (!q.mem.lit && e >= 0.7) {                     // 사그라들 무렵 한 번 - 광선이 꺼진 자리에 남는다
    q.mem.lit = true;
    afterglow(fx, q);
  }
  const open = smooth(clamp01(e / 0.12)), close = e > 0.5 ? 1 - smooth((e - 0.5) / 0.5) : 1, env = open * close;
  const L = len * easeOut(clamp01(e / 0.1)) + 1, fl = 0.9 + 0.1 * Math.sin(t * 70) + 0.15 * (noise1(t * 40 + s) - 0.5);
  const wv = W * (0.3 + 0.7 * env) * fl, cs = Math.cos(ang), sn = Math.sin(ang);
  beamSparks(fx, q, L, wv, cs, sn, env);
  ctx.translate(x, y);
  ctx.rotate(ang);
  const ph = t * 2.6 + hash(s);
  for (let d = 0; d <= L; d += 70) fx.ink.glow(ctx, c.dark, d, 0, wv * 1.5, 0.3 * close);   // 1 빛 번짐
  edgeBand(ctx, L, wv * 0.85, t, s, ph);          // 2 겉 띠 - 보통 혼합으로 타입 색을 살리고 빛을 한 겹 더
  ctx.globalCompositeOperation = 'source-over';
  fillPath(ctx, c.dark, 0.65 * close);
  strokePath(ctx, shade(c.dark, 0.6), 1.5, 0.6 * close);
  ctx.globalCompositeOperation = 'lighter';
  fillPath(ctx, c.dark, 0.3 * close);
  edgeBand(ctx, L, wv * 0.32, t * 1.3, s + 3, ph); // 3 속 띠 - 옅은 타입 색 (흰 심과 갈린다)
  ctx.globalCompositeOperation = 'source-over';
  fillPath(ctx, c.light, 0.75 * close);
  ctx.globalCompositeOperation = 'lighter';
  helix(ctx, L, wv * 0.55, t * 30, c.light, 1.5, 0.7 * close);   // 4 감기는 두 가닥
  for (let i = 0; i < PULSE_N; i++) {              // 5 입에서 끝으로 흐르는 덩이 (띠가 부푼 자리) + 두른 고리
    const d = pulseAt(ph, i) * L;
    fx.ink.stretch(ctx, WHITE, d, 0, wv * 1.1, wv * 0.4, 0.5 * close);
    ctx.beginPath();
    ctx.ellipse(d, 0, wv * 0.12 + 0.5, wv * 0.7, 0, 0, TAU);
    strokePath(ctx, c.light, 2, 0.7 * close);
  }
  ctx.globalAlpha = A(close);                      // 6 흰 심 - 지직거린다
  ctx.fillStyle = WHITE;
  ctx.fillRect(0, -wv * 0.07 * fl, L, wv * 0.14 * fl);
  fx.ink.core(ctx, c.light, 0, 0, wv * 1.5, close);   // 7 입 · 끝 번쩍
  fx.ink.star(ctx, WHITE, 0, 0, wv * 2.4, 0.9 * close);
  fx.ink.glow(ctx, c.dark, L, 0, wv * 2.6, 0.6 * close);
  spikes(ctx, L, 0, wv * 1.1, 7, 0.4, t * 25);
  fillPath(ctx, c.light, 0.7 * close);
  fx.ink.core(ctx, WHITE, L, 0, wv * 1.2, close);
}

const beam = {
  shot(fx, ctx, q) {                                // 짧은 빛살 - 겹 띠 + 감기는 두 가닥 + 밝은 머리
    const { r, c } = q, t = fx.clock, L = r * 4.5;
    ribbon(ctx, q.trail, t, 0.12, r * 1.4, 1, c.dark, 0.5);
    ctx.translate(q.x, q.y);
    ctx.rotate(q.ang);
    fx.ink.stretch(ctx, c.dark, -L * 0.5, 0, L * 0.75, r * 1.1, 0.6);
    fx.ink.stretch(ctx, c.light, -L * 0.4, 0, L * 0.55, r * 0.6, 0.85);
    ctx.globalAlpha = 0.95;
    ctx.fillStyle = WHITE;
    ctx.fillRect(-L * 0.8, -r * 0.14, L * 0.8 + r * 0.6, r * 0.28);
    ctx.translate(-L, 0);
    helix(ctx, L, r * 0.5, t * 30 + q.seed, c.light, 1.2, 0.6);
    ctx.translate(L, 0);
    fx.ink.core(ctx, c.light, 0, 0, r * 1.2, 1);
    fx.ink.star(ctx, WHITE, 0, 0, r * 2.2, 0.7 + 0.3 * Math.sin(t * 40 + q.seed));
  },
  trail(fx, q) {
    for (let n = fx.perSec(24); n > 0; n--) {
      const o = rnd(-0.6, 0.6) * q.r, sg = o > 0 ? 1 : -1, v = rnd(40, 120);
      dot(fx, 'spark', q.x - q.uy * o, q.y + q.ux * o, -q.uy * sg * v - q.ux * 40, q.ux * sg * v - q.uy * 40, rnd(0.12, 0.22), 7,
        Math.random() < 0.5 ? WHITE : q.c.light, 0.4, 4).w = 1.5;
    }
  },
  launch(fx, q) {
    dot(fx, 'star', q.x, q.y, 0, 0, 0.16, q.r * 3, WHITE, 0.4);
    fx.burst(q.x, q.y, BEAM_SPRAY, q.c, 0.4, q.ang, 0.8);
  },
  debris: BEAM_SPRAY,
  impact(fx, x, y, ang, c, info) {                  // 맞은 면 - 번쩍 + 뒤 · 옆으로 뿜는 불티 + 고리
    const s = info.s || 1;
    dot(fx, 'core', x, y, 0, 0, 0.25, 30 * s, WHITE, 2.6);
    fx.burst(x, y, BEAM_SPRAY, c, s, ang + Math.PI, 2.4);
    fx.wave(x, y, c.light, 90 * s, 0.35, 5);
  },
  beam(fx, ctx, q) {
    if (q.phase === 'mark') beamCharge(fx, ctx, q);
    else beamFire(fx, ctx, q);
  },
};

export default { orb, psy, ghost, dark, fairy, beam };
