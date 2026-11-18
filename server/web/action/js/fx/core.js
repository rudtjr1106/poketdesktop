/* 이펙트 바탕 - fx.js 와 모양 파일(fx/styles/*.js)이 같이 쓰는 것: 색 · 수학 · 도형 · 빛 스프라이트 · 입자 풀 ·
   뿌리는 법(spec) · 지나온 자리(Trail) · 장판 기본 그림(BASE) · 모양 훅 검사(checkStyle).

   ================================================================ 모양 훅 (fx/styles/*.js 가 지키는 것)

   모양 키(sty) 하나 = 아래 이름만 가진 객체. shot 만 꼭 있고 나머지는 없어도 된다. 어느 파일이 어느 키를 맡는지는
   fx/styles/index.js 의 FAMILY_OF 한 곳에만 적는다. 모르는 키는 orb 로 그린다. 훅은 this 없이 부른다 (fx = Fx).

     shot(fx, ctx, q)                탄 몸통. 꼭 있어야 한다.
     emit                            (값) 날아가는 동안 흘리는 꼬리 입자 spec + rate (1초에 몇 개). 없으면 orb 것.
     trail(fx, q, dt)                있으면 emit 대신 부른다 - 탄을 그릴 때마다 한 번 (dt = 이번 장 초). 입자만 뿌린다.
     launch(fx, q)                   탄이 처음 보인 순간. core 의 입 앞 번쩍 + 불티 다음에 더한다.
     debris                          (값) 맞은 자리 · 장판이 터진 자리 · 근접 끝에 튀는 조각 - DEBRIS 의 이름 또는 spec.
                                     없으면 기술 타입의 것 (DEBRIS_OF), 그것도 없으면 'spark'.
     impact(fx, x, y, ang, c, info)  맞은 자리 · 장판이 터진 자리에 더한다 (core 의 번쩍 · 고리 · 조각 · 흔들림 다음).
                                     ang = 맞은 쪽으로 들어온 방향 (라디안). info = {why: 'hit'|'tele'|'ring'|'cone'|'beam',
                                     k, ty, sty, eff, crit, s (세기 배율: 효과 굉장 1.35 · 별로 0.75 · 장판 1), r, len}
     cone · ring · beam · tele · haz (fx, ctx, q)
                                     그 꼴 장판의 몸통 그림 - 아래 '장판'. 없으면 BASE.<꼴>.
     fall(fx, ctx, q, x, y, v)       내려찍기(tele) 표시 위로 떨어지는 것. (x, y) 지금 자리, v 0 하늘 → 1 땅. 없으면 BASE.fall.
     rush(fx, ctx, a)                근접 · 돌진 하는 동안 몸을 따라가는 그림 (잔상 · 속도선 · 쓸고 간 폭).
                                     없으면 GENERIC.rush (fx/styles/body.js).
     swing(fx, ctx, a, t)            근접 · 돌진의 앞쪽 타격 그림 (t 0~1, 움직이기 시작한 때부터 act + RUSH_TAIL 동안).
                                     없으면 GENERIC.swing (fx/styles/body.js).

   바꾸는 훅 · 더하는 훅
     shot · trail · cone · ring · beam · tele · haz · fall · rush · swing 은 기본을 **바꾼다** - 기본 위에 덧그리려면 훅 안에서
     BASE.x(fx, ctx, q) (이 파일) · GENERIC.x(fx, ctx, a, t) (body.js) 를 먼저 부른다. launch · impact 는 기본 다음에 **더한다**.

   지키는 것
     * 좌표는 아레나 단위 (1600×900, 0 라디안 = 오른쪽, y 는 아래로). setTransform · resetTransform · transform 금지 (화면 배율이
       깨진다). translate · rotate · scale 은 된다 - 그리는 훅마다 core 가 save/restore 로 감싸고, globalAlpha 1 ·
       'lighter' · lineCap/lineJoin 'round' 로 시작해 준다.
     * 혼합은 'source-over' (연기 · 돌 · 그을음처럼 빛이 아닌 것) 과 'lighter' (빛) 둘만. 알파는 A(a) 로 0~1 에 가둔다.
       좌표 · 반지름 · 굵기에 NaN 이 없게 (굵기는 0 보다 크게).
     * 화면 ctx 에서 그라디언트를 만들지 않는다 (createRadialGradient · createLinearGradient 금지) - 빛은 fx.ink 의
       스프라이트 (색마다 한 번 만든다): fx.ink.glow · core · soft · star · stretch, 돌린 빛은 streak().
     * 입자는 fx.spawn · fx.particle · fx.burst · fx.wave · fx.trickle 로 (600개 풀을 돌려 쓴다). 그리는 훅 안에서
       뿌릴 때는 fx.perSec(rate) 개씩 - 화면 빈도와 상관없이 1초에 rate 개.
     * 장판 표시(바닥 칠 · 차오름 · 테두리 · 상대 빨간 점선 · 깜박임 · 광선 겨눈 선 · 내려찍기 그림자)는 core 가 그린다.
       표시 동안(q.phase 'mark') 훅은 바닥 칠 위, 차오름 · 테두리 아래에 그려진다 - 훅이 무엇을 하든 표시는 보인다.
       t1 뒤(q.phase 'fire')는 훅이 다 그린다. 함정(haz)은 바닥 칠 · 점선 테두리 위에 그린다.
     * 같은 탄 · 장판이 프레임마다 같은 모양이 되게 Math.random 대신 q.seed 와 hash · rng · noise1 · noise2 를 쓴다.
     * 훅 객체마다 q.mem / a.mem ({}) 에 제 것을 적어 둬도 된다 (탄 · 장판 · 돌진 하나가 사는 동안 남는다).

   q (탄) - drawProjectile 이 만든다
     id · k (기술 키) · ty (타입) · sty · o (쏜 쪽 'a'|'b') · foe (상대 것) · x · y · vx · vy (u/s) · speed · ux · uy (나아가는
     쪽 단위 벡터) · ang · r (반지름) · c {light, dark} · seed (id 에서 고정) · born (처음 본 fx.clock) · age (그 뒤 초) ·
     trail (지나온 자리 Trail - 0 이 지금 자리) · mem
   q (장판) - drawZone 이 만든다
     z (서버 것 그대로) · id · kind · k · ty · sty · o · foe · x · y · r · ang · len · w · c · seed · now (서버 시각) · t0 · t1 ·
     u (차오름 0~1) · since (t1 뒤 초, 앞이면 음수) · phase ('mark' | 'fire') · e (터지는 진행 0~1, 꼴마다 FIRE_SEC) ·
     h (부채꼴 반각) · W (광선 폭) · rr (고리의 지금 반지름) · grow (함정이 깔리는 진행 0.3~1) · hr (함정 무늬 반지름) ·
     born · age · mem
   a (돌진) - cast 의 kind 'melee' · 'dash' 가 만든다 (몸을 따라간다)
     mk ('melee'|'dash') · side · x · y (지금 몸 - 매 장 world.pos) · x0 · y0 (시작) · ang · ux · uy · len (돌진 길이) ·
     r (몸 밖 맞는 반폭) · reach (몸 가운데에서 맞는 거리: melee r + BODY_R, dash r + 2·BODY_R) · c · ty · sty · k · seed ·
     age · life · t (전체 0~1) · stage ('wind' 준비 | 'act' 달림 | 'tail' 끝) · sk (그 단계 진행 0~1) · go (움직이기 시작한
     나이, 아직이면 null) · speed (재 본 빠르기 u/s) · moved (시작에서 간 거리) · trail · mem

   fx (Fx) 에서 훅이 쓰는 것
     fx.clock (이펙트 시계 초) · fx.dt (이번 장) · fx.ink · fx.spawn(shape, x, y, vx, vy, life, size, color) → 입자 ·
     fx.particle(spec, c, x, y, vx, vy, k) · fx.burst(x, y, spec, c, k, ang, arc, r0, r1) · fx.wave(x, y, col, r1, life, w, layer) ·
     fx.trickle(q, spec) · fx.perSec(rate) · fx.kick(shake, stop, flash, color) · fx.pos(side) */
import { TYPE_FX, DEFAULT_FX, BODY_R } from '../consts.js';

// ---------------------------------------------------------------- 수치
export const POOL_MAX = 600;
export const SPRITE = 64;               // 스프라이트 한 변 (px) - 그릴 크기는 drawImage 가 늘린다
export const TAU = Math.PI * 2;
export { BODY_R };

export const SHOT_R = 12;
export const ZONE_R = 60;
export const BEAM_LEN = 520;
export const BEAM_W = 40;
export const BEAM_STEP = 80;            // 광선을 따라 빛 번짐을 찍는 간격
export const CONE_HALF = 0.6;           // 폭(w)이 없는 부채꼴의 반각 (라디안)
export const FALL_FROM = 0.65;          // 내려찍기 표시가 이만큼 찼을 때부터 떨어지는 것이 보인다
export const FALL_H = 320;
export const HAZ_IN = 0.3;              // 함정이 깔리는 시간
// 장판이 t1 뒤 터지는 모습의 길이 (q.e 가 0 → 1)
export const FIRE_SEC = Object.freeze({ tele: 0.3, ring: 0.28, cone: 0.25, beam: 0.25, haz: 0.3 });

export const DASH = [14, 10];
export const SOLID = [];

// ---------------------------------------------------------------- 색
export const WHITE = '#ffffff';
export const GOLD = '#ffd447';          // 급소 X · 꽃가루
export const INK = '#000000';
export const WARN = '#ff4f5e';          // 상대 표시의 테두리
export const HURT = '#ff3040';          // 내가 맞았을 때 화면 번쩍
export const VOID = '#140f1c';          // 악 구슬 속
export const UP = '#ff9a5c';
export const DOWN = '#6aa8ff';
export const CONFETTI = [GOLD, '#ff6b8b', '#6bd3ff', '#9dff7a', WHITE];

export const palette = (light, dark) => Object.freeze({ light, dark });
export const COLORS = Object.freeze(Object.fromEntries(Object.entries(TYPE_FX).map(([ty, [l, d]]) => [ty, palette(l, d)])));
export const PLAIN = palette(...DEFAULT_FX);
export const SHINE = palette(WHITE, '#cfe0ff');
export const GOLDEN = palette(GOLD, '#ff9a1f');
export const HEAL = palette('#b6ffc4', '#38c060');
export const BALL = palette(WHITE, '#ff4a4a');
export const COUNTER = palette('#ffd0a0', '#ff7a2e');
export const SOOT = palette('#5a5266', '#1e1a26');
export const SLEEP = palette('#cfe0ff', '#6d86d6');
export const DIZZY = palette('#fff3a0', '#e0b020');
export const SCREEN = palette('#d8f0ff', '#5aa8e0');

export const own = (t, k) => (t && Object.prototype.hasOwnProperty.call(t, k) ? t[k] : undefined);

/** 타입 → 색 {light, dark}. 모르면 회색. */
export const colorsOf = (ty) => own(COLORS, ty) || PLAIN;

/** spec 의 색: 'light' · 'dark' 면 그 타입 색, 아니면 적힌 색 그대로. */
export const tone = (which, c) => (which === 'light' ? c.light : which === 'dark' ? c.dark : which);

/** '#rrggbb' + 알파 → 'rgba(…)'. */
export function rgba(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
}

// ---------------------------------------------------------------- 수학
export const clamp01 = (v) => (v > 0 ? (v < 1 ? v : 1) : 0);          // NaN 은 0
/** 알파를 0~1 에 가둔다 (NaN 은 0) - ctx.globalAlpha = A(…). */
export const A = clamp01;
export const lerp = (a, b, t) => a + (b - a) * t;
export const easeOut = (t) => 1 - (1 - t) * (1 - t);
export const easeIn = (t) => t * t;
export const smooth = (t) => t * t * (3 - 2 * t);                      // 0~1 → 0~1, 양 끝이 부드럽다
export const rnd = (a, b) => a + Math.random() * (b - a);
export const num = (v, d = 0) => (Number.isFinite(v) ? v : d);

/** n → 0~1 고정 난수 (같은 n 이면 같은 값). */
export function hash(n) {
  const s = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
}

/** (x, y) → 0~1 고정 난수. */
export function hash2(x, y) {
  const s = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453;
  return s - Math.floor(s);
}

/** 씨앗 → 0~1 난수 생성기 (mulberry32). 같은 씨앗이면 같은 차례 - 프레임마다 새로 만들어 같은 모양을 얻는다. */
export function rng(seed) {
  let a = Math.floor(num(seed)) >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** 1차원 값 노이즈 0~1 (정수마다 고정 값, 사이는 부드럽게). */
export function noise1(x) {
  const i = Math.floor(x), f = smooth(x - i);
  return lerp(hash(i), hash(i + 1), f);
}

/** 2차원 값 노이즈 0~1. */
export function noise2(x, y) {
  const ix = Math.floor(x), iy = Math.floor(y), fx = smooth(x - ix), fy = smooth(y - iy);
  const a = hash2(ix, iy), b = hash2(ix + 1, iy), c = hash2(ix, iy + 1), d = hash2(ix + 1, iy + 1);
  return lerp(lerp(a, b, fx), lerp(c, d, fx), fy);
}

/** 탄 · 장판 id 에서 뽑는 고정 씨앗 - 같은 장판의 금 · 돌 자리가 프레임마다 바뀌지 않게. */
export function seedOf(id) {
  if (typeof id === 'number') return id;
  let h = 7;
  for (const ch of String(id ?? '')) h = (h * 31 + ch.charCodeAt(0)) % 1000003;
  return h;
}

// ---------------------------------------------------------------- 도형 (경로만 만든다 - 칠은 부르는 쪽)
export const SHARD_PTS = [1.5, 0, 0, 0.42, -0.9, 0, 0, -0.42];
export const ARROW_PTS = [1, 0, 0.1, -0.8, 0.1, -0.32, -0.9, -0.32, -0.9, 0.32, 0.1, 0.32, 0.1, 0.8];
export const HEX_PTS = [0, 1, 2, 3, 4, 5].flatMap((i) => [Math.cos((i * TAU) / 6), Math.sin((i * TAU) / 6)]);
export const ROCK_PTS = [0, 1, 2, 3].map((v) => [0, 1, 2, 3, 4, 5].flatMap((i) => {
  const a = (i * TAU) / 6 + (hash(v * 13 + i) - 0.5) * 0.5, r = 0.72 + hash(v * 7 + i * 3) * 0.38;
  return [Math.cos(a) * r, Math.sin(a) * r];
}));

/** 단위 꼭짓점 pts (+x 가 앞) 를 r 배 · rot 만큼 돌려 (x, y) 에. */
export function shape(ctx, pts, x, y, r, rot) {
  const c = Math.cos(rot) * r, s = Math.sin(rot) * r;
  ctx.beginPath();
  for (let i = 0; i < pts.length; i += 2) ctx.lineTo(x + pts[i] * c - pts[i + 1] * s, y + pts[i] * s + pts[i + 1] * c);
  ctx.closePath();
}

/** n 갈래 별. inner 가 작을수록 뾰족하다. */
export function spikes(ctx, x, y, r, n, inner, rot) {
  ctx.beginPath();
  for (let i = 0; i < n * 2; i++) {
    const a = rot + (Math.PI * i) / n, rr = i % 2 ? r * inner : r;
    ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
  }
  ctx.closePath();
}

/** 초승달: (x, y) 가 원의 중심, a0 → a1 바깥 호, 가운데가 thick 만큼 두껍다. */
export function crescent(ctx, x, y, r, a0, a1, thick) {
  ctx.beginPath();
  for (let i = 0; i <= 10; i++) {
    const a = a0 + ((a1 - a0) * i) / 10;
    ctx.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
  }
  for (let i = 10; i >= 0; i--) {
    const a = a0 + ((a1 - a0) * i) / 10, rr = Math.max(0, r - thick * Math.sin((Math.PI * i) / 10));
    ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
  }
  ctx.closePath();
}

/** 양 끝이 뾰족하고 가운데가 w 만큼 두꺼운 자국 (급소 X). */
export function lens(ctx, x1, y1, x2, y2, w) {
  const d = Math.hypot(x2 - x1, y2 - y1) || 1, px = (-(y2 - y1) / d) * w, py = ((x2 - x1) / d) * w;
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(mx + px, my + py);
  ctx.lineTo(x2, y2);
  ctx.lineTo(mx - px, my - py);
  ctx.closePath();
}

/** 잎 하나 (rot 쪽으로 길쭉). */
export function leafPath(ctx, x, y, r, rot) {
  const c = Math.cos(rot) * r, s = Math.sin(rot) * r;
  ctx.beginPath();
  ctx.moveTo(x - c, y - s);
  ctx.quadraticCurveTo(x - s * 0.9, y + c * 0.9, x + c, y + s);
  ctx.quadraticCurveTo(x + s * 0.9, y - c * 0.9, x - c, y - s);
  ctx.closePath();
}

/** 지그재그 (번개 · 땅이 갈라진 금). seed 가 같으면 같은 모양. */
export function boltPath(ctx, x, y, len, ang, seed, n = 3) {
  const c = Math.cos(ang), s = Math.sin(ang), jag = (len / n) * 0.6;
  ctx.beginPath();
  ctx.moveTo(x, y);
  for (let i = 1; i <= n; i++) {
    const d = (len * i) / n, o = i < n ? (hash(seed + i) - 0.5) * 2 * jag : 0;
    ctx.lineTo(x + c * d - s * o, y + s * d + c * o);
  }
}

export function circle(ctx, x, y, r) {
  ctx.beginPath();
  ctx.arc(x, y, r > 0 ? r : 0, 0, TAU);
}

/** 부채꼴 (x, y) 에서 a 쪽으로 반지름 R, 반각 h. */
export function wedge(ctx, x, y, R, a, h) {
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.arc(x, y, R > 0 ? R : 0, a - h, a + h);
  ctx.closePath();
}

/** 2차 곡선 경로 (x0, y0) → 조절점 (cx, cy) → (x1, y1). */
export function quad(ctx, x0, y0, cx, cy, x1, y1) {
  ctx.beginPath();
  ctx.moveTo(x0, y0);
  ctx.quadraticCurveTo(cx, cy, x1, y1);
}

/** 3차 곡선 경로. */
export function bezier(ctx, x0, y0, c1x, c1y, c2x, c2y, x1, y1) {
  ctx.beginPath();
  ctx.moveTo(x0, y0);
  ctx.bezierCurveTo(c1x, c1y, c2x, c2y, x1, y1);
}

/** 점들을 부드럽게 잇는 경로 (가운데 점끼리 2차 곡선). xs · ys 는 배열, n 개만. */
export function smoothPath(ctx, xs, ys, n = xs.length) {
  ctx.beginPath();
  if (n < 1) return;
  ctx.moveTo(xs[0], ys[0]);
  if (n === 2) ctx.lineTo(xs[1], ys[1]);
  for (let i = 1; i < n - 1; i++) {
    ctx.quadraticCurveTo(xs[i], ys[i], (xs[i] + xs[i + 1]) / 2, (ys[i] + ys[i + 1]) / 2);
  }
  if (n > 2) ctx.lineTo(xs[n - 1], ys[n - 1]);
}

/** (x0, y0) → (x1, y1) 를 따라 옆으로 출렁이는 선 경로. amp 진폭, waves 물결 수, phase 0~1 이 한 바퀴. */
export function wavy(ctx, x0, y0, x1, y1, amp, waves, phase = 0, steps = 16) {
  const dx = x1 - x0, dy = y1 - y0, d = Math.hypot(dx, dy) || 1, px = -dy / d, py = dx / d;
  ctx.beginPath();
  for (let i = 0; i <= steps; i++) {
    const k = i / steps, o = Math.sin((k * waves + phase) * TAU) * amp * Math.sin(Math.PI * k);
    ctx.lineTo(x0 + dx * k + px * o, y0 + dy * k + py * o);
  }
}

/** 지금 경로를 칠 · 긋기 (알파 · 굵기를 안전하게). */
export function fillPath(ctx, col, a) {
  ctx.globalAlpha = A(a);
  ctx.fillStyle = col;
  ctx.fill();
}

export function strokePath(ctx, col, w, a) {
  ctx.globalAlpha = A(a);
  ctx.strokeStyle = col;
  ctx.lineWidth = w > 0.1 ? w : 0.1;
  ctx.stroke();
}

export function ring(ctx, col, a, w, x, y, r) {
  circle(ctx, x, y, r);
  strokePath(ctx, col, w, a);
}

export function line(ctx, col, w, x1, y1, x2, y2) {
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.strokeStyle = col;
  ctx.lineWidth = w > 0.1 ? w : 0.1;
  ctx.stroke();
}

export function plus(ctx, col, x, y, s) {
  ctx.fillStyle = col;
  ctx.fillRect(x - s, y - s * 0.3, s * 2, s * 0.6);
  ctx.fillRect(x - s * 0.3, y - s, s * 0.6, s * 2);
}

/** (0, 0) 을 가운데로 위아래 이빨 세 개씩 (+x 가 앞). gap 이 0 이면 다문 것. */
export function fangs(ctx, r, gap, edge, a) {
  ctx.globalCompositeOperation = 'source-over';
  ctx.globalAlpha = A(a);
  ctx.fillStyle = WHITE;
  ctx.strokeStyle = edge;
  ctx.lineWidth = 1.5;
  for (let side = -1; side <= 1; side += 2) {
    ctx.beginPath();
    for (let i = -1; i <= 1; i++) {
      const x = i * r * 0.55, root = side * (gap + r * 0.5);
      ctx.moveTo(x - r * 0.22, root);
      ctx.lineTo(x + r * 0.22, root);
      ctx.lineTo(x, side * gap);
      ctx.closePath();
    }
    ctx.fill();
    ctx.stroke();
  }
}

// ---------------------------------------------------------------- 빛 스프라이트
// 스프라이트마다 방사형 그라디언트 멈춤점 [자리, 색]
const RECIPES = {
  glow: (hex) => [[0, rgba(hex, 1)], [0.3, rgba(hex, 0.5)], [0.65, rgba(hex, 0.14)], [1, rgba(hex, 0)]],
  core: (hex) => [[0, rgba(WHITE, 1)], [0.2, rgba(WHITE, 0.9)], [0.45, rgba(hex, 0.7)], [1, rgba(hex, 0)]],
  soft: (hex) => [[0, rgba(hex, 0.6)], [0.5, rgba(hex, 0.28)], [1, rgba(hex, 0)]],
  star: (hex) => [[0, rgba(WHITE, 1)], [0.12, rgba(hex, 0.8)], [0.4, rgba(hex, 0)], [1, rgba(hex, 0)]],
};

function paintSprite(g, kind, hex) {
  const h = SPRITE / 2, grad = g.createRadialGradient(h, h, 0, h, h, h);
  for (const [at, col] of RECIPES[kind](hex)) grad.addColorStop(at, col);
  g.fillStyle = grad;
  g.fillRect(0, 0, SPRITE, SPRITE);
  if (kind === 'star') {                        // 네 갈래 반짝임
    spikes(g, h, h, h, 4, 0.09, -Math.PI / 2);
    g.fillStyle = hex;
    g.fill();
    spikes(g, h, h, h * 0.6, 4, 0.12, -Math.PI / 2);
    g.fillStyle = WHITE;
    g.fill();
  }
}

/** 브라우저면 OffscreenCanvas, 없으면 <canvas>. 둘 다 없으면 (node 검사) null - 스프라이트 없이 그린다. */
export function defaultCanvas(w, h) {
  if (typeof OffscreenCanvas === 'function') return new OffscreenCanvas(w, h);
  if (typeof document === 'undefined') return null;
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return c;
}

/** 빛 스프라이트 묶음 - (종류, 색) 마다 한 번 만든다. 그리는 쪽은 가산 혼합('lighter')을 걸어 두고 부른다. */
export class Ink {
  constructor(make) {
    this.make = make;
    this.cache = { glow: new Map(), core: new Map(), soft: new Map(), star: new Map() };
  }

  sprite(kind, hex) {
    const map = this.cache[kind];
    let s = map.get(hex);
    if (s === undefined) {
      s = this.build(kind, hex);
      map.set(hex, s);
    }
    return s;
  }

  build(kind, hex) {
    const cv = this.make ? this.make(SPRITE, SPRITE) : null;
    const g = cv && cv.getContext('2d');
    if (!g) return null;
    paintSprite(g, kind, hex);
    return cv;
  }

  /** (x, y) 가운데 반지름 rx × ry 의 빛. 스프라이트가 없으면 옅은 타원으로 대신한다. */
  draw(ctx, kind, hex, x, y, rx, ry, a) {
    if (!(a > 0) || !(rx > 0) || !(ry > 0)) return;
    ctx.globalAlpha = a < 1 ? a : 1;
    const s = this.sprite(kind, hex);
    if (s) {
      ctx.drawImage(s, x - rx, y - ry, rx * 2, ry * 2);
      return;
    }
    ctx.globalAlpha *= 0.45;
    ctx.fillStyle = hex;
    ctx.beginPath();
    ctx.ellipse(x, y, rx * 0.5, ry * 0.5, 0, 0, TAU);
    ctx.fill();
  }

  glow(ctx, hex, x, y, r, a) { this.draw(ctx, 'glow', hex, x, y, r, r, a); }       // 부드러운 빛 번짐
  core(ctx, hex, x, y, r, a) { this.draw(ctx, 'core', hex, x, y, r, r, a); }       // 흰 심이 있는 빛
  soft(ctx, hex, x, y, r, a) { this.draw(ctx, 'soft', hex, x, y, r, r, a); }       // 연기 · 그을음 (보통 혼합으로)
  star(ctx, hex, x, y, r, a) { this.draw(ctx, 'star', hex, x, y, r, r, a); }       // 네 갈래 반짝임
  stretch(ctx, hex, x, y, rx, ry, a) { this.draw(ctx, 'glow', hex, x, y, rx, ry, a); }   // 가로세로 늘린 빛
}

/** ang 쪽으로 늘린 빛 (rx 는 길이 쪽 반지름, ry 는 폭 쪽). (x, y) 가 가운데. */
export function streak(fx, ctx, hex, x, y, ang, rx, ry, a, kind = 'glow') {
  if (!(a > 0) || !(rx > 0) || !(ry > 0)) return;
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(ang);
  fx.ink.draw(ctx, kind, hex, 0, 0, rx, ry, a);
  ctx.restore();
}

// ---------------------------------------------------------------- 입자
const NORMAL_BLEND = new Set(['smoke', 'rock', 'leaf']);   // 빛이 아닌 것 - 보통 혼합으로 칠한다
/** 입자 모양 (spec.shape). */
export const SHAPES = Object.freeze(['glow', 'core', 'smoke', 'star', 'wisp', 'spark', 'line', 'bolt', 'ring', 'bubble',
  'shard', 'arrow', 'leaf', 'plus', 'rock']);

class Particle {
  constructor() {
    this.reset('glow', 0, 0, 0, 0, 1, 1, WHITE);
    this.on = false;
  }

  reset(shape, x, y, vx, vy, life, size, color) {
    this.on = true;
    this.shape = shape;
    this.add = !NORMAL_BLEND.has(shape);
    this.layer = 1;                             // 0 몸 아래 · 1 몸 위
    this.x = x;
    this.y = y;
    this.x2 = x;                                // 'line' 의 다른 끝
    this.y2 = y;
    this.vx = vx;
    this.vy = vy;
    this.g = 0;                                 // 아래로 당기는 힘 (u/s²), 음수면 떠오른다
    this.drag = 0;                              // 1초에 속도가 e^-drag 배
    this.age = 0;
    this.life = life > 0 ? life : 0.01;
    this.size = size;
    this.size1 = size * 0.4;                    // 끝날 때 크기
    this.w = 2;
    this.rot = 0;
    this.vr = 0;
    this.seed = Math.random() * 1000;
    this.color = color;
    this.color2 = color;
  }
}

/** 입자 풀. 미리 만든 max 개를 돌려 쓰고, 넘치면 가장 먼저 만든 것부터 덮는다. */
export class Particles {
  constructor(max = POOL_MAX) {
    this.all = Array.from({ length: max }, () => new Particle());
    this.next = 0;
    this.live = 0;
  }

  spawn(shape, x, y, vx, vy, life, size, color) {
    const p = this.all[this.next];
    this.next = (this.next + 1) % this.all.length;
    if (!p.on) this.live++;
    p.reset(shape, x, y, vx, vy, life, size, color);
    return p;
  }

  update(dt) {
    if (!(dt > 0)) return;
    for (const p of this.all) {
      if (!p.on) continue;
      p.age += dt;
      if (p.age >= p.life) {
        p.on = false;
        this.live--;
        continue;
      }
      if (p.drag) {
        const f = Math.exp(-p.drag * dt);
        p.vx *= f;
        p.vy *= f;
      }
      p.vy += p.g * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.rot += p.vr * dt;
    }
  }

  // 보통 혼합 것을 먼저 깔고 빛을 얹는다
  draw(ctx, ink, layer) {
    if (!this.live) return;
    ctx.lineCap = 'round';
    ctx.globalCompositeOperation = 'source-over';
    this.pass(ctx, ink, layer, false);
    ctx.globalCompositeOperation = 'lighter';
    this.pass(ctx, ink, layer, true);
  }

  pass(ctx, ink, layer, add) {
    for (const p of this.all) if (p.on && p.layer === layer && p.add === add) drawParticle(ctx, ink, p);
  }
}

function drawParticle(ctx, ink, p) {
  const k = p.age / p.life, a = 1 - k * k, s = p.size + (p.size1 - p.size) * k;
  switch (p.shape) {
    case 'glow': ink.glow(ctx, p.color, p.x, p.y, s, a); return;
    case 'core': ink.core(ctx, p.color, p.x, p.y, s, a); return;
    case 'smoke': ink.soft(ctx, p.color, p.x, p.y, s, a); return;
    case 'star': ink.star(ctx, p.color, p.x, p.y, s, a); return;
    case 'wisp': ink.stretch(ctx, p.color, p.x, p.y - s * 0.5, s * 0.55, s * 1.3, a); return;   // 위로 핥는 불꽃 혀
    default: break;
  }
  ctx.globalAlpha = a;
  switch (p.shape) {
    case 'spark': {                             // 날아가는 쪽으로 늘어난 불티
      const v = Math.hypot(p.vx, p.vy);
      const ux = v > 1 ? p.vx / v : Math.cos(p.rot), uy = v > 1 ? p.vy / v : Math.sin(p.rot);
      const len = Math.max(s * 0.6, Math.min(s * 3, v * 0.06));
      line(ctx, p.color, p.w * (1 - k) + 0.5, p.x, p.y, p.x - ux * len, p.y - uy * len);
      return;
    }
    case 'line': line(ctx, p.color, p.w * (1 - k) + 0.5, p.x, p.y, p.x2, p.y2); return;
    case 'bolt':                                // 1초에 30번 모양이 바뀌는 지직거림
      boltPath(ctx, p.x, p.y, s, p.rot, p.seed + Math.floor(p.age * 30));
      ctx.strokeStyle = p.color;
      ctx.lineWidth = p.w;
      ctx.stroke();
      return;
    case 'ring': ring(ctx, p.color, a, p.w * (1 - k) + 0.5, p.x, p.y, s); return;
    case 'bubble': ring(ctx, p.color, a, 1.5, p.x, p.y, s); return;
    case 'shard': shape(ctx, SHARD_PTS, p.x, p.y, s, p.rot); break;
    case 'arrow': shape(ctx, ARROW_PTS, p.x, p.y, s, p.vy < 0 ? -Math.PI / 2 : Math.PI / 2); break;
    case 'leaf': leafPath(ctx, p.x, p.y, s, p.rot); break;
    case 'plus': plus(ctx, p.color, p.x, p.y, s); return;
    case 'rock':
      shape(ctx, ROCK_PTS[p.seed & 3], p.x, p.y, s, p.rot);
      ctx.fillStyle = p.color2;
      ctx.fill();
      ctx.strokeStyle = p.color;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      return;
    default: return;
  }
  ctx.fillStyle = p.color;
  ctx.fill();
}

// ---------------------------------------------------------------- 뿌리는 법 (spec)
// shape · n(개수) · c ('light' | 'dark' | '#색') · v(빠르기) · life · size · g · drag · up(처음 위로) · end(끝 크기 배율) ·
// spin · w · layer (0 몸 아래). 꼬리 입자(emit)는 n 대신 rate (1초에 몇 개).
export const DEBRIS = Object.freeze({           // 맞은 자리에 튀는 조각
  flame: { shape: 'wisp', n: 10, c: 'light', v: 150, life: 0.45, size: 12, g: -180 },
  drop: { shape: 'glow', n: 12, c: 'light', v: 230, life: 0.4, size: 6, g: 520, drag: 1 },
  zap: { shape: 'bolt', n: 8, c: 'light', v: 240, life: 0.2, size: 20, drag: 6 },
  leaf: { shape: 'leaf', n: 8, c: 'light', v: 170, life: 0.6, size: 8, g: 60, spin: 12, end: 1 },
  shard: { shape: 'shard', n: 9, c: 'light', v: 260, life: 0.35, size: 7, drag: 5 },
  pebble: { shape: 'rock', n: 8, c: 'light', v: 220, life: 0.5, size: 6, g: 600, drag: 1, spin: 8, end: 1 },
  star: { shape: 'star', n: 9, c: 'light', v: 180, life: 0.45, size: 10, drag: 4 },
  wisp: { shape: 'wisp', n: 9, c: 'light', v: 110, life: 0.55, size: 11, g: -90, drag: 2 },
  bubble: { shape: 'bubble', n: 9, c: 'light', v: 140, life: 0.5, size: 6, g: -60, end: 1.2 },
  glint: { shape: 'star', n: 8, c: WHITE, v: 220, life: 0.3, size: 11, drag: 6 },
  spark: { shape: 'spark', n: 10, c: 'light', v: 320, life: 0.28, size: 10, w: 2.5, drag: 5 },
});
// 모양 키에 debris 가 없을 때 기술 타입으로
export const DEBRIS_OF = Object.freeze({
  FIRE: 'flame', WATER: 'drop', ELECTRIC: 'zap', GRASS: 'leaf', BUG: 'leaf', ICE: 'shard', DRAGON: 'shard',
  ROCK: 'pebble', GROUND: 'pebble', FAIRY: 'star', PSYCHIC: 'star', GHOST: 'wisp', DARK: 'wisp',
  POISON: 'bubble', STEEL: 'glint',
});

export const DUST = { shape: 'smoke', n: 6, c: '#cdbf9f', v: 90, life: 0.5, size: 14, end: 1.8, drag: 4, layer: 0 };
export const FIZZLE = { shape: 'glow', n: 5, c: 'light', v: 70, life: 0.25, size: 7 };
export const MUZZLE = { shape: 'spark', n: 5, c: 'light', v: 260, life: 0.16, size: 8, w: 2, drag: 6 };
export const MOTES = { shape: 'glow', n: 10, c: 'light', v: 30, life: 0.8, size: 6, up: -70, drag: 1 };
export const PLUSES = { shape: 'plus', n: 6, c: 'light', v: 20, life: 0.8, size: 6, up: -90, drag: 1.5, end: 0.6 };
export const PUFF = { shape: 'smoke', n: 10, c: 'dark', v: 60, life: 0.9, size: 22, end: 2, up: -40, drag: 2 };
export const ARROW_UP = { shape: 'arrow', n: 4, c: UP, v: 15, life: 0.75, size: 9, up: -150, drag: 1.2, end: 1 };
export const ARROW_DOWN = { ...ARROW_UP, c: DOWN, up: 130 };

// ---------------------------------------------------------------- 지나온 자리
/** 지나온 자리 (고리 버퍼). 0 이 가장 새것 (지금 자리). push 는 앞 점에서 gap 보다 멀어졌을 때만 새 점을 박고,
    아니면 맨 앞 점만 옮긴다 - 그래서 점 사이가 고르다. core 가 탄 · 돌진마다 하나씩 두고 매 장 밀어 넣는다. */
export class Trail {
  constructor(max = 20) {
    this.max = max;
    this.xs = new Float64Array(max);
    this.ys = new Float64Array(max);
    this.ts = new Float64Array(max);
    this.head = 0;
    this.n = 0;
  }

  push(x, y, t, gap = 6) {
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(t)) return;
    if (this.n >= 2) {
      const i1 = this.idx(1);
      if (Math.hypot(x - this.xs[i1], y - this.ys[i1]) < gap) {
        const i0 = this.head;
        this.xs[i0] = x;
        this.ys[i0] = y;
        this.ts[i0] = t;
        return;
      }
    }
    this.head = (this.head + 1) % this.max;
    this.xs[this.head] = x;
    this.ys[this.head] = y;
    this.ts[this.head] = t;
    if (this.n < this.max) this.n++;
  }

  clear() { this.n = 0; }
  idx(i) { return (this.head - i + this.max * 2) % this.max; }
  x(i) { return this.xs[this.idx(i)]; }
  y(i) { return this.ys[this.idx(i)]; }
  t(i) { return this.ts[this.idx(i)]; }
}

/** 지나온 자리를 따라 끝이 가늘어지는 띠. now - t 가 life 보다 오래된 점은 뺀다. 머리 폭 w0 → 꼬리 폭 w1,
    알파는 머리 a → 꼬리 0. 이음매마다 칠을 따로 한다 (그라디언트 없이 옅어지게). 지금 혼합 그대로 칠한다. */
export function ribbon(ctx, tr, now, life, w0, w1, col, a) {
  if (!tr || tr.n < 2 || !(life > 0) || !(a > 0)) return;
  ctx.fillStyle = col;
  let px = tr.x(0), py = tr.y(0), pw = w0 / 2;
  for (let i = 1; i < tr.n; i++) {
    const k = (now - tr.t(i)) / life;
    if (!(k < 1)) break;
    const x = tr.x(i), y = tr.y(i), w = (w0 + (w1 - w0) * clamp01(k)) / 2;
    const dx = x - px, dy = y - py, d = Math.hypot(dx, dy);
    if (d > 0.01) {
      const nx = -dy / d, ny = dx / d;
      ctx.beginPath();
      ctx.moveTo(px + nx * pw, py + ny * pw);
      ctx.lineTo(x + nx * w, y + ny * w);
      ctx.lineTo(x - nx * w, y - ny * w);
      ctx.lineTo(px - nx * pw, py - ny * pw);
      ctx.closePath();
      ctx.globalAlpha = A(a * (1 - clamp01(k)));
      ctx.fill();
    }
    px = x;
    py = y;
    pw = w;
  }
}

// ---------------------------------------------------------------- 탄 그림 도우미
/** 지나온 자리에 옅어지는 잔상 (나아가는 반대쪽으로 gap 간격 n 개). */
export function tail(fx, ctx, q, hex, n, gap, size, a0) {
  for (let i = 1; i <= n; i++) {
    const f = 1 - i / (n + 1);
    fx.ink.glow(ctx, hex, q.x - q.ux * gap * i, q.y - q.uy * gap * i, size * f, a0 * f);
  }
}

/** 앞을 보는 초승달 칼날 + 옅은 잔상 둘 (바람 · 베기). */
export function blades(ctx, q, outer, inner) {
  const { r } = q;
  for (let i = 2; i >= 0; i--) {
    const back = r * (1.2 + i * 0.9);
    crescent(ctx, q.x - q.ux * back, q.y - q.uy * back, r * 1.7, q.ang - 1.1, q.ang + 1.1, r * 0.55);
    ctx.globalAlpha = i ? 0.35 / i : 0.85;
    ctx.fillStyle = outer;
    ctx.fill();
  }
  crescent(ctx, q.x - q.ux * r * 1.2, q.y - q.uy * r * 1.2, r * 1.7, q.ang - 0.9, q.ang + 0.9, r * 0.25);
  ctx.globalAlpha = 1;
  ctx.fillStyle = inner;
  ctx.fill();
}

// ---------------------------------------------------------------- 장판 기본 그림 (BASE)
// 모양 훅이 없을 때 그리는 것 - 훅 안에서 불러 그 위에 덧그려도 된다. 표시(테두리 · 차오름)는 여기 없다 (core 몫).
const BEAM_BANDS = [['dark', 0.6, 1.3], ['light', 0.85, 0.75], [WHITE, 1, 0.28]];   // 겉 · 속 · 흰 심 (색, 알파, 폭 배율)

export const BASE = Object.freeze({
  /** 떨어진 자리 - 번쩍이고 고리가 퍼진다. */
  tele(fx, ctx, q) {
    if (q.phase !== 'fire') return;
    const e = q.e;
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.core(ctx, q.c.light, q.x, q.y, q.r * 1.2 * (1 - e), 1 - e);
    ring(ctx, q.c.light, 1 - e, 2 + 8 * (1 - e), q.x, q.y, q.r * (0.6 + 0.6 * e));
  },
  /** 내 둘레로 퍼지는 고리. */
  ring(fx, ctx, q) {
    if (q.phase !== 'fire') return;
    const { e, rr, c } = q;
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, c.dark, q.x, q.y, rr * 1.1, 0.5 * (1 - e));
    ring(ctx, c.light, 1 - e * 0.7, 4 + 14 * (1 - e), q.x, q.y, rr);
    ring(ctx, WHITE, 0.8 * (1 - e), 1 + 4 * (1 - e), q.x, q.y, rr);
  },
  /** 부채꼴을 따라 뿜어 나가는 줄기. */
  cone(fx, ctx, q) {
    if (q.phase !== 'fire') return;
    const { x, y, ang, len, c, h, e } = q;
    ctx.globalCompositeOperation = 'lighter';
    wedge(ctx, x, y, len, ang, h);
    ctx.globalAlpha = 0.08 + 0.4 * (1 - e);
    ctx.fillStyle = c.dark;
    ctx.fill();
    ctx.globalAlpha = 0.9 * (1 - e);
    for (let i = 0; i < 7; i++) {
      const a = ang + (hash(q.seed + i) - 0.5) * 1.8 * h, r0 = len * 0.1, r1 = len * (0.3 + 0.7 * easeOut(e));
      line(ctx, c.light, 2 + 4 * (1 - e), x + Math.cos(a) * r0, y + Math.sin(a) * r0, x + Math.cos(a) * r1, y + Math.sin(a) * r1);
    }
    for (let i = 1; i <= 4; i++) {
      const d = len * 0.25 * i * easeOut(e);
      fx.ink.glow(ctx, c.light, x + Math.cos(ang) * d, y + Math.sin(ang) * d, len * 0.2, 0.5 * (1 - e));
    }
  },
  /** 한 줄을 한꺼번에 - 세 겹 띠 + 빛 번짐 + 양 끝 번쩍. */
  beam(fx, ctx, q) {
    if (q.phase !== 'fire') return;
    const { len, c } = q, wv = q.W * (1 + 0.12 * Math.sin(fx.clock * 55));
    ctx.translate(q.x, q.y);
    ctx.rotate(q.ang);
    ctx.globalCompositeOperation = 'lighter';
    for (const [col, a, k] of BEAM_BANDS) {
      ctx.globalAlpha = a;
      ctx.fillStyle = tone(col, c);
      ctx.fillRect(0, (-wv * k) / 2, len, wv * k);
    }
    for (let d = 0; d <= len; d += BEAM_STEP) fx.ink.glow(ctx, c.light, d, 0, wv * 0.9, 0.35);
    fx.ink.core(ctx, c.light, 0, 0, wv * 1.2, 1);
    fx.ink.core(ctx, c.light, len, 0, wv * 1.5, 1);
  },
  /** 세 갈래 압정 (압정뿌리기 · 무늬가 없는 함정). 반지름은 q.hr. */
  haz(fx, ctx, q) {
    const r = q.hr;
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1;
    ctx.fillStyle = q.c.dark;
    ctx.strokeStyle = q.c.light;
    ctx.lineWidth = 1.2;
    for (let i = 0; i < 6; i++) {
      const a = hash(q.seed + i) * TAU, d = r * 0.7 * hash(q.seed + i + 7);
      spikes(ctx, q.x + Math.cos(a) * d, q.y + Math.sin(a) * d, 8, 3, 0.35, q.seed + i);
      ctx.fill();
      ctx.stroke();
    }
  },
  /** 내려찍기의 떨어지는 빛 덩이. */
  fall(fx, ctx, q, x, y, v) {
    fx.ink.stretch(ctx, q.c.light, x, y - q.r * 0.5, q.r * 0.18, q.r * 0.7, 0.6 * v + 0.2);
    fx.ink.core(ctx, q.c.light, x, y, q.r * 0.35, 1);
  },
});

// ---------------------------------------------------------------- 모양 훅 검사
/** 훅 이름 → 'fn' (함수) · 'emit' (꼬리 spec) · 'debris' (조각 이름 또는 spec). 이 밖의 이름은 쓰지 않는다. */
export const HOOKS = Object.freeze({
  shot: 'fn', emit: 'emit', trail: 'fn', launch: 'fn', debris: 'debris', impact: 'fn',
  cone: 'fn', ring: 'fn', beam: 'fn', tele: 'fn', haz: 'fn', fall: 'fn', rush: 'fn', swing: 'fn',
});
/** 장판 꼴 (Z.kind) - 같은 이름의 훅이 그 꼴의 몸통을 그린다. */
export const ZONE_KINDS = Object.freeze(['tele', 'haz', 'ring', 'cone', 'beam']);

function specProblems(spec, need) {
  if (!spec || typeof spec !== 'object') return ['spec 이 객체가 아니다'];
  const out = [];
  if (!SHAPES.includes(spec.shape)) out.push(`모르는 입자 모양 ${spec.shape}`);
  if (!(spec[need] > 0)) out.push(`${need} 가 양수가 아니다`);
  for (const k of ['life', 'size']) if (!(spec[k] > 0)) out.push(`${k} 가 양수가 아니다`);
  if (!(Number.isFinite(spec.v) && spec.v >= 0)) out.push('v 가 0 이상이 아니다');
  if (typeof spec.c !== 'string' || !(spec.c === 'light' || spec.c === 'dark' || /^#[0-9a-f]{6}$/i.test(spec.c))) {
    out.push(`색 ${spec.c} 은 'light' · 'dark' · '#rrggbb' 가 아니다`);
  }
  return out;
}

/** 모양 하나의 문제 목록 (없으면 []). 검사가 모든 모양 파일에 부른다. */
export function checkStyle(key, def) {
  if (!def || typeof def !== 'object') return [`${key}: 객체가 아니다`];
  const out = [];
  if (typeof def.shot !== 'function') out.push(`${key}: shot 이 없다`);
  for (const [name, v] of Object.entries(def)) {
    const kind = own(HOOKS, name);
    if (!kind) out.push(`${key}: 모르는 훅 ${name}`);
    else if (kind === 'fn' && typeof v !== 'function') out.push(`${key}.${name}: 함수가 아니다`);
    else if (kind === 'emit') out.push(...specProblems(v, 'rate').map((s) => `${key}.emit: ${s}`));
    else if (kind === 'debris' && !(typeof v === 'string' ? own(DEBRIS, v) : !specProblems(v, 'n').length)) {
      out.push(`${key}.debris: DEBRIS 이름도 spec 도 아니다`);
    }
  }
  return out;
}

/** 조각 spec: 모양의 debris → 타입 → spark. */
export function debrisSpec(def, ty) {
  const d = def && def.debris;
  if (d && typeof d === 'object') return d;
  return own(DEBRIS, d) || DEBRIS[own(DEBRIS_OF, ty) || 'spark'];
}
