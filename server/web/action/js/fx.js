/* 이펙트 (액션 배틀).

   서버가 보낸 탄(P) · 장판(Z) · 이벤트를 빛 · 입자 · 글씨로 그린다. 판정과는 상관없다 - 여기서 무엇을 그리든
   맞고 안 맞고는 서버가 정한다. 그래서 보기 좋으면 되는데, 상대가 쓴 장판(표시)만은 **언제 · 어디에** 떨어지는지
   또렷해야 한다: 어떤 바닥에서도 보이는 테두리, t1 쪽으로 차오르는 채움, 떨어지기 직전의 깜박임.

     event(ev, world)        이벤트 하나 (cast · hit · clash · dodge · status · cure · stat · heal · guard · counter ·
                             swap · ko · phase · over). need · txt 는 화면 칸(hud)이 맡는다 - 받기만 하고 그리지 않는다.
     update(dt)              초. 입자 · 움직이는 그림 · 글씨 · 흔들림을 나이 먹인다
     drawProjectile(ctx, p, x, y)   탄 P 를 보간된 자리에
     drawZone(ctx, z, now)   장판 Z (now = 보간된 서버 시각)
     drawUnder / drawOver    몸 아래 · 위
     shake()                 화면 흔들림 {x, y}

   그리는 법.
     * 빛은 가산 혼합("lighter") + 색마다 한 번만 만들어 두는 방사형 그라디언트 그림(스프라이트).
       입자마다 · 프레임마다 그라디언트를 만들지 않는다.
     * 입자는 600개 풀을 돌려 쓴다 - 넘치면 가장 먼저 만든 것부터 덮는다.
     * 좌표는 전부 아레나 단위 (1600×900). 화면 배율은 render 가 setTransform 으로 걸어 두므로 여기서는
       translate · rotate · scale 만 쓰고, 그리기마다 save/restore 로 ctx 를 받은 그대로 돌려놓는다.
     * world 는 이벤트 때 받아 두고, 몸을 따라가는 그림(휘두름 · 방어막 · 잔상)이 그릴 때마다 world.pos 를 다시
       읽는다 - 그래서 world.pos 는 부를 때의 자리를 돌려줘야 몸을 따라간다 (멈춘 자리를 주면 그 자리에 남는다). */
import { TYPE_FX, DEFAULT_FX, FONT, ARENA_W, ARENA_H, STATUS_KR, COND_KR, STAT_KR } from './consts.js';

// ---------------------------------------------------------------- 수치
export const POOL_MAX = 600;
const ANIM_MAX = 48;
const TEXT_MAX = 24;
const MAX_DT = 0.1;              // 탭을 오래 비웠다 돌아와도 입자가 순간이동하지 않게
const SPRITE = 64;               // 스프라이트 한 변 (px) - 그릴 크기는 drawImage 가 늘린다
const TAU = Math.PI * 2;

const SHAKE_MAX = 16;            // 흔들림 최대 (아레나 단위). 세기(trauma 0~1)의 제곱에 비례
const SHAKE_DECAY = 1.6;         // 세기가 1초에 줄어드는 양
const HITSTOP_SLOW = 0.08;       // 맞는 순간 이펙트 시간을 이만큼으로 늦춘다 (판은 서버 것이라 그대로)
const FLASH_DECAY = 1.8;
const FLASH_PAD = 60;            // 흔들려도 가장자리가 비지 않게

const GONE_SEC = 0.15;           // 서버가 지운 탄 · 장판을 이만큼 못 보면 잊는다
const LATE_SEC = 0.15;           // 지워진 표시를 마지막으로 본 때가 t1 을 이만큼 앞뒀으면 떨어진 것으로 친다

const SHOT_R = 12;
const ZONE_R = 60;
const BEAM_LEN = 520;
const BEAM_W = 40;
const BEAM_STEP = 80;            // 광선을 따라 빛 번짐을 찍는 간격
const CONE_HALF = 0.6;           // 폭(w)이 없는 부채꼴의 반각 (라디안)
const FALL_FROM = 0.65;          // 내려찍기 표시가 이만큼 찼을 때부터 떨어지는 것이 보인다
const FALL_H = 320;
const BLINK_FROM = 0.85;         // 표시가 이만큼 차면 테두리가 깜박인다
const RING_SEC = 0.28;
const CONE_SEC = 0.25;
const LAND_SEC = 0.3;
const HAZ_IN = 0.3;

const REACH = 30;                // 근접 휘두름이 몸 앞으로 나가는 거리
const SWING_SEC = 0.26;
const SWING_DELAY = 0.12;        // cast 는 준비를 시작할 때 온다 - 근접 준비(0.14 + 위력/1000 초) 무렵에 휘두른다
const GATHER_SEC = 0.28;         // 날리기 준비 (0.16 + 위력/700 초) 동안 모이는 빛
const IMPACT_SEC = 0.2;
const KO_SEC = 0.8;
const KO_PULL = 0.4;             // 쓰러짐: 이만큼 줄어든 뒤 터진다
const TRAIL_LIFE = 0.26;
const DODGE_TRAIL = 0.22;

const TEXT_LIFT = 64;            // 글씨는 몸 위 이만큼에서 시작한다
const TEXT_GAP = 30;             // 같은 쪽 글씨끼리 적어도 이만큼 띄운다
const TEXT_UP = 70;              // 처음 떠오르는 빠르기 (u/s) - 점점 느려진다
const TEXT_DRAG = 2.5;
const MERGE_SEC = 0.5;           // 같은 말이 이 안에 또 오면 하나로
const POP_K = 0.1;               // 글씨가 커졌다 줄어드는 앞부분 (수명 비율)
const FADE_K = 0.7;              // 이 뒤로 흐려진다
const CONFETTI_N = 90;

const DASH = [14, 10];
const SOLID = [];

// ---------------------------------------------------------------- 색
const WHITE = '#ffffff';
const GOLD = '#ffd447';          // 급소 X · 꽃가루
const INK = '#000000';
const WARN = '#ff4f5e';          // 상대 표시의 테두리
const HURT = '#ff3040';          // 내가 맞았을 때 화면 번쩍
const VOID = '#140f1c';          // 악 구슬 속
const UP = '#ff9a5c';
const DOWN = '#6aa8ff';
const CONFETTI = [GOLD, '#ff6b8b', '#6bd3ff', '#9dff7a', WHITE];

const palette = (light, dark) => Object.freeze({ light, dark });
const COLORS = Object.fromEntries(Object.entries(TYPE_FX).map(([ty, [l, d]]) => [ty, palette(l, d)]));
const PLAIN = palette(...DEFAULT_FX);
const SHINE = palette(WHITE, '#cfe0ff');
const GOLDEN = palette(GOLD, '#ff9a1f');
const HEAL = palette('#b6ffc4', '#38c060');
const DODGE = palette('#e4f4ff', '#7fb4ff');
const BALL = palette(WHITE, '#ff4a4a');
const COUNTER = palette('#ffd0a0', '#ff7a2e');
const SOOT = palette('#5a5266', '#1e1a26');
const SLEEP = palette('#cfe0ff', '#6d86d6');
const DIZZY = palette('#fff3a0', '#e0b020');
const SCREEN = palette('#d8f0ff', '#5aa8e0');

const own = (t, k) => (Object.prototype.hasOwnProperty.call(t, k) ? t[k] : undefined);

const colorsOf = (ty) => own(COLORS, ty) || PLAIN;

// spec 의 색: 'light' · 'dark' 면 그 타입 색, 아니면 적힌 색 그대로
const tone = (which, c) => (which === 'light' ? c.light : which === 'dark' ? c.dark : which);

// ---------------------------------------------------------------- 수학
const clamp01 = (v) => (v > 0 ? (v < 1 ? v : 1) : 0);          // NaN 은 0
const easeOut = (t) => 1 - (1 - t) * (1 - t);
const rnd = (a, b) => a + Math.random() * (b - a);
const num = (v, d = 0) => (Number.isFinite(v) ? v : d);

function hash(n) {
  const s = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
}

// 탄 · 장판 id 에서 뽑는 고정 씨앗 - 같은 장판의 금 · 돌 자리가 프레임마다 바뀌지 않게
function seedOf(id) {
  if (typeof id === 'number') return id;
  let h = 7;
  for (const ch of String(id ?? '')) h = (h * 31 + ch.charCodeAt(0)) % 1000003;
  return h;
}

/** 표시가 찬 정도 0~1: t0 에 0, t1 에 1. 시각이 없으면 0. */
export function charge(z, now) {
  const span = z.t1 - z.t0;
  if (!(span > 0)) return now >= z.t1 ? 1 : 0;
  return clamp01((now - z.t0) / span);
}

// ---------------------------------------------------------------- 도형 (경로만 만든다 - 칠은 부르는 쪽)
const SHARD_PTS = [1.5, 0, 0, 0.42, -0.9, 0, 0, -0.42];
const ARROW_PTS = [1, 0, 0.1, -0.8, 0.1, -0.32, -0.9, -0.32, -0.9, 0.32, 0.1, 0.32, 0.1, 0.8];
const HEX_PTS = [0, 1, 2, 3, 4, 5].flatMap((i) => [Math.cos((i * TAU) / 6), Math.sin((i * TAU) / 6)]);
const ROCK_PTS = [0, 1, 2, 3].map((v) => [0, 1, 2, 3, 4, 5].flatMap((i) => {
  const a = (i * TAU) / 6 + (hash(v * 13 + i) - 0.5) * 0.5, r = 0.72 + hash(v * 7 + i * 3) * 0.38;
  return [Math.cos(a) * r, Math.sin(a) * r];
}));

// 단위 꼭짓점 pts (+x 가 앞) 를 r 배 · rot 만큼 돌려 (x, y) 에
function shape(ctx, pts, x, y, r, rot) {
  const c = Math.cos(rot) * r, s = Math.sin(rot) * r;
  ctx.beginPath();
  for (let i = 0; i < pts.length; i += 2) ctx.lineTo(x + pts[i] * c - pts[i + 1] * s, y + pts[i] * s + pts[i + 1] * c);
  ctx.closePath();
}

// n 갈래 별. inner 가 작을수록 뾰족하다
function spikes(ctx, x, y, r, n, inner, rot) {
  ctx.beginPath();
  for (let i = 0; i < n * 2; i++) {
    const a = rot + (Math.PI * i) / n, rr = i % 2 ? r * inner : r;
    ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
  }
  ctx.closePath();
}

// 초승달: (x, y) 가 원의 중심, a0 → a1 바깥 호, 가운데가 thick 만큼 두껍다
function crescent(ctx, x, y, r, a0, a1, thick) {
  ctx.beginPath();
  for (let i = 0; i <= 10; i++) {
    const a = a0 + ((a1 - a0) * i) / 10;
    ctx.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
  }
  for (let i = 10; i >= 0; i--) {
    const a = a0 + ((a1 - a0) * i) / 10, rr = r - thick * Math.sin((Math.PI * i) / 10);
    ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
  }
  ctx.closePath();
}

// 양 끝이 뾰족하고 가운데가 w 만큼 두꺼운 자국 (급소 X)
function lens(ctx, x1, y1, x2, y2, w) {
  const d = Math.hypot(x2 - x1, y2 - y1) || 1, px = (-(y2 - y1) / d) * w, py = ((x2 - x1) / d) * w;
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(mx + px, my + py);
  ctx.lineTo(x2, y2);
  ctx.lineTo(mx - px, my - py);
  ctx.closePath();
}

function leafPath(ctx, x, y, r, rot) {
  const c = Math.cos(rot) * r, s = Math.sin(rot) * r;
  ctx.beginPath();
  ctx.moveTo(x - c, y - s);
  ctx.quadraticCurveTo(x - s * 0.9, y + c * 0.9, x + c, y + s);
  ctx.quadraticCurveTo(x + s * 0.9, y - c * 0.9, x - c, y - s);
  ctx.closePath();
}

// 지그재그 (번개 · 땅이 갈라진 금). seed 가 같으면 같은 모양
function boltPath(ctx, x, y, len, ang, seed, n = 3) {
  const c = Math.cos(ang), s = Math.sin(ang), jag = (len / n) * 0.6;
  ctx.beginPath();
  ctx.moveTo(x, y);
  for (let i = 1; i <= n; i++) {
    const d = (len * i) / n, o = i < n ? (hash(seed + i) - 0.5) * 2 * jag : 0;
    ctx.lineTo(x + c * d - s * o, y + s * d + c * o);
  }
}

function circle(ctx, x, y, r) {
  ctx.beginPath();
  ctx.arc(x, y, r, 0, TAU);
}

function ring(ctx, col, a, w, x, y, r) {
  circle(ctx, x, y, r);
  ctx.globalAlpha = a;
  ctx.strokeStyle = col;
  ctx.lineWidth = w;
  ctx.stroke();
}

function line(ctx, col, w, x1, y1, x2, y2) {
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.strokeStyle = col;
  ctx.lineWidth = w;
  ctx.stroke();
}

function plus(ctx, col, x, y, s) {
  ctx.fillStyle = col;
  ctx.fillRect(x - s, y - s * 0.3, s * 2, s * 0.6);
  ctx.fillRect(x - s * 0.3, y - s, s * 0.6, s * 2);
}

// (0, 0) 을 가운데로 위아래 이빨 세 개씩 (+x 가 앞). gap 이 0 이면 다문 것
function fangs(ctx, r, gap, edge, a) {
  ctx.globalCompositeOperation = 'source-over';
  ctx.globalAlpha = a;
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
function rgba(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
}

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

// 브라우저면 OffscreenCanvas, 없으면 <canvas>. 둘 다 없으면 (node 검사) 스프라이트 없이 그린다
function defaultCanvas(w, h) {
  if (typeof OffscreenCanvas === 'function') return new OffscreenCanvas(w, h);
  if (typeof document === 'undefined') return null;
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return c;
}

class Ink {
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

  // (x, y) 가운데 반지름 rx × ry 의 빛. 스프라이트가 없으면 옅은 타원으로 대신한다
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

  glow(ctx, hex, x, y, r, a) { this.draw(ctx, 'glow', hex, x, y, r, r, a); }
  core(ctx, hex, x, y, r, a) { this.draw(ctx, 'core', hex, x, y, r, r, a); }
  soft(ctx, hex, x, y, r, a) { this.draw(ctx, 'soft', hex, x, y, r, r, a); }
  star(ctx, hex, x, y, r, a) { this.draw(ctx, 'star', hex, x, y, r, r, a); }
  stretch(ctx, hex, x, y, rx, ry, a) { this.draw(ctx, 'glow', hex, x, y, rx, ry, a); }
}

// ---------------------------------------------------------------- 입자
const NORMAL_BLEND = new Set(['smoke', 'rock', 'leaf']);   // 빛이 아닌 것 - 보통 혼합으로 칠한다

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
// shape · n(개수) · c · v(빠르기) · life · size · g · drag · up(처음 위로) · end(끝 크기 배율) · spin · w · layer
const DEBRIS = {                                // 맞은 자리에 튀는 조각 (타입마다)
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
};
const DEBRIS_OF = {
  FIRE: 'flame', WATER: 'drop', ELECTRIC: 'zap', GRASS: 'leaf', BUG: 'leaf', ICE: 'shard', DRAGON: 'shard',
  ROCK: 'pebble', GROUND: 'pebble', FAIRY: 'star', PSYCHIC: 'star', GHOST: 'wisp', DARK: 'wisp',
  POISON: 'bubble', STEEL: 'glint',
};
const STYLE_DEBRIS = {
  flame: 'flame', jet: 'drop', wave: 'drop', zap: 'zap', leaf: 'leaf', shard: 'shard', rock: 'pebble',
  quake: 'pebble', psy: 'star', fairy: 'star', powder: 'star', ghost: 'wisp', dark: 'wisp', poison: 'bubble',
  web: 'glint',
};
// 모양 키가 먼저, 없으면 타입
const debrisOf = (sty, ty) => DEBRIS[own(STYLE_DEBRIS, sty) || own(DEBRIS_OF, ty) || 'spark'];

const DUST = { shape: 'smoke', n: 6, c: '#cdbf9f', v: 90, life: 0.5, size: 14, end: 1.8, drag: 4, layer: 0 };
const FIZZLE = { shape: 'glow', n: 5, c: 'light', v: 70, life: 0.25, size: 7 };
const MUZZLE = { shape: 'spark', n: 5, c: 'light', v: 260, life: 0.16, size: 8, w: 2, drag: 6 };
const MOTES = { shape: 'glow', n: 10, c: 'light', v: 30, life: 0.8, size: 6, up: -70, drag: 1 };
const PLUSES = { shape: 'plus', n: 6, c: 'light', v: 20, life: 0.8, size: 6, up: -90, drag: 1.5, end: 0.6 };
const PUFF = { shape: 'smoke', n: 10, c: 'dark', v: 60, life: 0.9, size: 22, end: 2, up: -40, drag: 2 };
const ARROW_UP = { shape: 'arrow', n: 4, c: UP, v: 15, life: 0.75, size: 9, up: -150, drag: 1.2, end: 1 };
const ARROW_DOWN = { ...ARROW_UP, c: DOWN, up: 130 };

// 날아가는 탄이 흘리는 꼬리 입자. rate = 1초에 몇 개
const EMIT = {
  orb: { shape: 'glow', rate: 14, c: 'light', v: 24, life: 0.3, size: 6 },
  flame: { shape: 'wisp', rate: 30, c: 'dark', v: 30, life: 0.42, size: 10, g: -140 },
  jet: { shape: 'glow', rate: 24, c: 'light', v: 50, life: 0.3, size: 4, g: 240 },
  zap: { shape: 'bolt', rate: 14, c: 'light', v: 60, life: 0.12, size: 14 },
  leaf: { shape: 'leaf', rate: 10, c: 'light', v: 40, life: 0.6, size: 7, spin: 10, end: 1 },
  shard: { shape: 'star', rate: 14, c: WHITE, v: 24, life: 0.3, size: 8 },
  psy: { shape: 'ring', rate: 7, c: 'light', v: 0, life: 0.35, size: 4, end: 4 },
  rock: { shape: 'smoke', rate: 14, c: 'dark', v: 24, life: 0.45, size: 10, end: 1.6, layer: 0 },
  ghost: { shape: 'wisp', rate: 18, c: 'light', v: 16, life: 0.5, size: 9, g: -60 },
  dark: { shape: 'smoke', rate: 18, c: VOID, v: 20, life: 0.45, size: 12, end: 1.5 },
  fairy: { shape: 'star', rate: 16, c: 'light', v: 36, life: 0.45, size: 7 },
  poison: { shape: 'bubble', rate: 12, c: 'light', v: 24, life: 0.5, size: 4, g: -40, end: 1.2 },
  wind: { shape: 'spark', rate: 18, c: WHITE, v: 30, life: 0.22, size: 8, w: 1.5 },
  sound: { shape: 'ring', rate: 5, c: 'light', v: 0, life: 0.3, size: 6, end: 3, w: 1.5 },
  punch: { shape: 'spark', rate: 12, c: WHITE, v: 40, life: 0.18, size: 8 },
  slash: { shape: 'spark', rate: 14, c: 'light', v: 40, life: 0.2, size: 8 },
  bite: { shape: 'glow', rate: 10, c: 'dark', v: 20, life: 0.3, size: 6 },
  beam: { shape: 'glow', rate: 20, c: 'light', v: 16, life: 0.25, size: 5 },
  wave: { shape: 'glow', rate: 22, c: 'light', v: 50, life: 0.35, size: 5, g: 200 },
  quake: { shape: 'rock', rate: 10, c: 'light', v: 60, life: 0.45, size: 5, g: 300, spin: 8, layer: 0 },
  heal: { shape: 'plus', rate: 8, c: HEAL.light, v: 20, life: 0.45, size: 5, g: -60 },
  buff: { shape: 'glow', rate: 12, c: 'light', v: 20, life: 0.4, size: 6, g: -50 },
  shield: { shape: 'star', rate: 8, c: 'light', v: 20, life: 0.3, size: 7 },
  powder: { shape: 'glow', rate: 22, c: 'light', v: 30, life: 0.7, size: 4, drag: 1.5 },
  web: { shape: 'spark', rate: 6, c: WHITE, v: 30, life: 0.25, size: 6, w: 1 },
};

// ---------------------------------------------------------------- 탄 (모양 키마다)
// q: 탄 하나의 기록 {x, y, ux, uy(나아가는 쪽 단위 벡터), ang, r, c, seed}. drawProjectile 이 save/restore 로 감싸고
// 가산 혼합으로 시작한다 - 여기서 translate · 혼합을 바꿔도 된다.

// 지나온 자리에 옅어지는 잔상
function tail(fx, ctx, q, hex, n, gap, size, a0) {
  for (let i = 1; i <= n; i++) {
    const f = 1 - i / (n + 1);
    fx.ink.glow(ctx, hex, q.x - q.ux * gap * i, q.y - q.uy * gap * i, size * f, a0 * f);
  }
}

// 앞을 보는 초승달 칼날 + 옅은 잔상 둘 (바람 · 베기)
function blades(ctx, q, outer, inner) {
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

const SHOTS = {
  orb(fx, ctx, q) {
    tail(fx, ctx, q, q.c.dark, 5, q.r * 0.9, q.r * 2, 0.5);
    fx.ink.glow(ctx, q.c.light, q.x, q.y, q.r * 2.6, 0.6);
    fx.ink.core(ctx, q.c.light, q.x, q.y, q.r * 1.3, 1);
  },
  flame(fx, ctx, q) {
    const { x, y, r, c } = q;
    tail(fx, ctx, q, c.dark, 6, r * 0.85, r * 2.2, 0.55);
    for (let i = 0; i < 3; i++) {               // 일렁이는 불꽃 혀 - 불은 어느 쪽으로 날아가든 위로 핥는다
      const back = r * (0.5 + i * 0.6), sway = Math.sin(fx.clock * 18 + i * 2.1 + q.seed) * r * 0.3;
      fx.ink.stretch(ctx, i ? c.dark : c.light, x - q.ux * back + sway, y - q.uy * back - r * 0.6,
        r * (0.95 - i * 0.2), r * (1.7 - i * 0.3), 0.75);
    }
    fx.ink.glow(ctx, c.light, x, y, r * 2.4, 0.6);
    fx.ink.core(ctx, c.light, x, y, r * 1.3, 1);
  },
  jet(fx, ctx, q) {                             // 물줄기 - 앞이 굵고 뒤로 가늘게 늘어난다
    const { r, c } = q;
    ctx.translate(q.x, q.y);
    ctx.rotate(q.ang);
    fx.ink.stretch(ctx, c.dark, -r * 1.8, 0, r * 3.2, r * 1.1, 0.7);
    fx.ink.stretch(ctx, c.light, -r * 0.9, 0, r * 2.1, r * 0.75, 0.9);
    fx.ink.core(ctx, c.light, r * 0.2, 0, r * 1.2, 1);
  },
  zap(fx, ctx, q) {
    const { x, y, r, c } = q, flick = q.seed + Math.floor(fx.clock * 24);   // 1초에 24번 모양이 바뀐다
    tail(fx, ctx, q, c.light, 3, r, r * 1.6, 0.4);
    fx.ink.glow(ctx, c.dark, x, y, r * 2.6, 0.5);
    ctx.globalAlpha = 0.9;
    for (let i = 0; i < 3; i++) {
      boltPath(ctx, x, y, r * 2, hash(flick + i) * TAU, flick * 3 + i);
      ctx.strokeStyle = c.light;
      ctx.lineWidth = 2.5;
      ctx.stroke();
      ctx.strokeStyle = WHITE;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
    fx.ink.core(ctx, c.light, x, y, r * 1.2, 1);
  },
  leaf(fx, ctx, q) {                            // 잎 셋이 돌며 날아간다
    const { x, y, r, c } = q;
    tail(fx, ctx, q, c.light, 3, r, r * 1.6, 0.35);
    fx.ink.glow(ctx, c.dark, x, y, r * 2, 0.45);
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1;
    for (let i = 0; i < 3; i++) {
      const a = fx.clock * 10 + q.seed + (i * TAU) / 3;
      leafPath(ctx, x + Math.cos(a) * r * 0.9, y + Math.sin(a) * r * 0.9, r * 0.9, a + Math.PI / 2);
      ctx.fillStyle = i ? c.light : c.dark;
      ctx.fill();
    }
  },
  shard(fx, ctx, q) {                           // 앞을 겨눈 결정 + 끝의 반짝임
    const { x, y, r, c } = q;
    tail(fx, ctx, q, c.light, 4, r * 0.9, r * 1.8, 0.45);
    fx.ink.glow(ctx, c.dark, x, y, r * 2.2, 0.5);
    shape(ctx, SHARD_PTS, x, y, r * 1.3, q.ang);
    ctx.globalAlpha = 1;
    ctx.fillStyle = c.light;
    ctx.fill();
    ctx.strokeStyle = WHITE;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    fx.ink.star(ctx, WHITE, x + q.ux * r * 1.9, y + q.uy * r * 1.9, r * (0.7 + 0.3 * Math.sin(fx.clock * 30)), 1);
  },
  psy(fx, ctx, q) {                             // 퍼져 나가는 염동 고리
    const { x, y, r, c } = q;
    tail(fx, ctx, q, c.dark, 3, r, r * 1.8, 0.4);
    fx.ink.glow(ctx, c.dark, x, y, r * 2.6, 0.45);
    for (let i = 0; i < 3; i++) {
      const ph = (fx.clock * 1.8 + i / 3) % 1;
      ring(ctx, c.light, 1 - ph, 3 * (1 - ph) + 0.5, x, y, r * (0.5 + ph * 1.4));
    }
    fx.ink.core(ctx, c.light, x, y, r * 1.1, 1);
  },
  rock(fx, ctx, q) {                            // 구르는 바위 + 흙먼지 꼬리
    const { x, y, r, c } = q;
    ctx.globalCompositeOperation = 'source-over';
    for (let i = 1; i <= 3; i++) fx.ink.soft(ctx, c.dark, x - q.ux * r * i, y - q.uy * r * i, r * (1.4 - i * 0.2), 0.5 - i * 0.12);
    shape(ctx, ROCK_PTS[q.seed & 3], x, y, r * 1.15, fx.clock * 5 + q.seed);
    ctx.globalAlpha = 1;
    ctx.fillStyle = c.dark;
    ctx.fill();
    ctx.strokeStyle = c.light;
    ctx.lineWidth = 2;
    ctx.stroke();
  },
  ghost(fx, ctx, q) {                           // 흔들리며 끌리는 혼 꼬리
    const { x, y, r, c } = q;
    for (let i = 1; i <= 5; i++) {
      const wv = Math.sin(fx.clock * 8 + i * 0.9 + q.seed) * r * 0.45, back = r * 0.8 * i;
      fx.ink.glow(ctx, c.dark, x - q.ux * back - q.uy * wv, y - q.uy * back + q.ux * wv, r * (1.9 - i * 0.25), 0.6 * (1 - i / 6));
    }
    fx.ink.glow(ctx, c.light, x, y, r * 2.2, 0.5);
    fx.ink.core(ctx, c.light, x, y, r, 0.9);
  },
  dark(fx, ctx, q) {                            // 빛을 먹는 검은 구슬 - 속은 보통 혼합이라야 어둡게 보인다
    const { x, y, r, c } = q;
    fx.ink.glow(ctx, c.light, x, y, r * 2.4, 0.45);
    ctx.globalCompositeOperation = 'source-over';
    for (let i = 1; i <= 3; i++) fx.ink.soft(ctx, VOID, x - q.ux * r * i * 0.9, y - q.uy * r * i * 0.9, r * (1.5 - i * 0.25), 0.6 - i * 0.15);
    circle(ctx, x, y, r * 1.05);
    ctx.globalAlpha = 0.9;
    ctx.fillStyle = VOID;
    ctx.fill();
    ctx.globalAlpha = 0.85;
    ctx.strokeStyle = c.light;
    ctx.lineWidth = 2;
    ctx.stroke();
  },
  fairy(fx, ctx, q) {
    const { x, y, r, c } = q;
    tail(fx, ctx, q, c.light, 4, r * 0.9, r * 1.6, 0.4);
    fx.ink.glow(ctx, c.dark, x, y, r * 2.4, 0.5);
    fx.ink.star(ctx, WHITE, x, y, r * 1.8 * (0.85 + 0.15 * Math.sin(fx.clock * 20 + q.seed)), 1);
    fx.ink.core(ctx, c.light, x, y, r * 0.9, 1);
  },
  poison(fx, ctx, q) {                          // 겉에서 거품이 끓는 독 덩이
    const { x, y, r, c } = q;
    tail(fx, ctx, q, c.dark, 4, r * 0.9, r * 1.8, 0.45);
    fx.ink.glow(ctx, c.dark, x, y, r * 2.4, 0.6);
    fx.ink.core(ctx, c.light, x, y, r * 1.1, 0.9);
    for (let i = 0; i < 3; i++) {
      const a = q.seed + i * 2.1 + fx.clock * 3;
      ring(ctx, c.light, 0.9, 1.5, x + Math.cos(a) * r * 0.8, y + Math.sin(a) * r * 0.8,
        r * 0.35 * (0.6 + 0.4 * Math.sin(fx.clock * 9 + i)));
    }
  },
  wind(fx, ctx, q) { blades(ctx, q, q.c.light, WHITE); },
  sound(fx, ctx, q) {                           // 겹겹이 퍼지는 음파 - 앞으로 볼록한 호 셋
    const { r, c } = q;
    fx.ink.glow(ctx, c.dark, q.x, q.y, r * 1.8, 0.4);
    for (let i = 0; i < 3; i++) {
      const R = r * (1.1 + i * 0.45), back = R + i * r * 0.7;
      ctx.beginPath();
      ctx.arc(q.x - q.ux * back, q.y - q.uy * back, R, q.ang - 0.9, q.ang + 0.9);
      ctx.globalAlpha = 0.9 - i * 0.25;
      ctx.strokeStyle = c.light;
      ctx.lineWidth = 3.5 - i;
      ctx.stroke();
    }
  },
  punch(fx, ctx, q) {                           // 기운을 실은 주먹 - 뒤로 속도선
    const { x, y, r, c } = q;
    ctx.globalAlpha = 0.5;
    for (let i = -2; i <= 2; i++) {
      const ox = -q.uy * i * r * 0.4, oy = q.ux * i * r * 0.4, far = r * (3 - Math.abs(i) * 0.4);
      line(ctx, WHITE, 2, x + ox - q.ux * r * 1.3, y + oy - q.uy * r * 1.3, x + ox - q.ux * far, y + oy - q.uy * far);
    }
    fx.ink.glow(ctx, c.dark, x, y, r * 2.4, 0.6);
    fx.ink.core(ctx, c.light, x, y, r * 1.3, 1);
  },
  slash(fx, ctx, q) { blades(ctx, q, q.c.dark, q.c.light); },
  bite(fx, ctx, q) {                            // 여닫는 이빨 두 줄
    const { r, c } = q;
    fx.ink.glow(ctx, c.light, q.x, q.y, r * 2.6, 0.55);
    ctx.translate(q.x, q.y);
    ctx.rotate(q.ang);
    fangs(ctx, r * 1.5, r * (0.25 + 0.45 * Math.abs(Math.sin(fx.clock * 14 + q.seed))), c.dark, 1);
  },
  beam(fx, ctx, q) {                            // 짧은 광선 탄 - 길쭉한 빛
    const { r, c } = q;
    ctx.translate(q.x, q.y);
    ctx.rotate(q.ang);
    fx.ink.stretch(ctx, c.dark, -r * 2, 0, r * 3.6, r * 0.9, 0.7);
    fx.ink.stretch(ctx, c.light, -r, 0, r * 2.4, r * 0.55, 0.9);
    fx.ink.core(ctx, c.light, 0, 0, r * 0.9, 1);
  },
  wave(fx, ctx, q) {                            // 앞으로 볼록한 두 겹 물마루
    const { r, c } = q;
    fx.ink.glow(ctx, c.dark, q.x, q.y, r * 2, 0.45);
    for (let i = 0; i < 2; i++) {
      const back = r * (0.6 + i * 0.7);
      crescent(ctx, q.x - q.ux * back, q.y - q.uy * back, r * (1.2 + i * 0.4), q.ang - 1, q.ang + 1, r * 0.45);
      ctx.globalAlpha = 0.85 - i * 0.4;
      ctx.fillStyle = i ? c.dark : c.light;
      ctx.fill();
    }
    fx.ink.core(ctx, c.light, q.x, q.y, r * 0.8, 0.8);
  },
  quake(fx, ctx, q) {                           // 땅을 타고 가는 충격 - 흙먼지 + 퍼지는 고리
    const { x, y, r, c } = q;
    ctx.globalCompositeOperation = 'source-over';
    fx.ink.soft(ctx, c.dark, x, y, r * 2.2, 0.55);
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 2; i++) {
      const ph = (fx.clock * 3 + i / 2) % 1;
      ring(ctx, c.light, 0.8 * (1 - ph), 3, x, y, r * (0.4 + ph * 1.6));
    }
    fx.ink.glow(ctx, c.light, x, y, r * 1.2, 0.6);
  },
  heal(fx, ctx, q) {
    const { x, y, r } = q;
    fx.ink.glow(ctx, HEAL.dark, x, y, r * 2.4, 0.55);
    fx.ink.core(ctx, HEAL.light, x, y, r * 1.2, 1);
    ctx.globalAlpha = 1;
    plus(ctx, WHITE, x, y, r * 0.7);
  },
  buff(fx, ctx, q) {                            // 기운 구슬 + 도는 빛 셋
    const { x, y, r, c } = q;
    fx.ink.glow(ctx, c.dark, x, y, r * 2.4, 0.5);
    for (let i = 0; i < 3; i++) {
      const a = fx.clock * 6 + (i * TAU) / 3;
      fx.ink.glow(ctx, c.light, x + Math.cos(a) * r * 1.3, y + Math.sin(a) * r * 1.3, r * 0.6, 0.9);
    }
    fx.ink.core(ctx, c.light, x, y, r * 1.1, 1);
  },
  shield(fx, ctx, q) {
    const { x, y, r, c } = q;
    fx.ink.glow(ctx, c.light, x, y, r * 2.2, 0.45);
    shape(ctx, HEX_PTS, x, y, r * 1.4, fx.clock * 2);
    ctx.globalAlpha = 0.9;
    ctx.strokeStyle = c.light;
    ctx.lineWidth = 2;
    ctx.stroke();
    fx.ink.core(ctx, c.light, x, y, r * 0.9, 1);
  },
  powder(fx, ctx, q) {                          // 흩날리는 가루 구름
    const { x, y, r, c } = q;
    ctx.globalCompositeOperation = 'source-over';
    fx.ink.soft(ctx, c.dark, x, y, r * 2.2, 0.4);
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 7; i++) {
      const a = q.seed + i * 0.9 + fx.clock * 1.5, d = r * (0.3 + hash(q.seed + i) * 0.9);
      fx.ink.glow(ctx, c.light, x + Math.cos(a) * d, y + Math.sin(a) * d, r * 0.7, 0.6);
    }
  },
  web(fx, ctx, q) {                             // 펼쳐지며 날아가는 거미줄
    const { x, y, r } = q, rot = fx.clock * 1.5 + q.seed;
    fx.ink.glow(ctx, q.c.light, x, y, r * 1.8, 0.3);
    ctx.globalAlpha = 0.85;
    ctx.strokeStyle = WHITE;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const a = rot + (i * TAU) / 6;
      ctx.moveTo(x, y);
      ctx.lineTo(x + Math.cos(a) * r * 1.6, y + Math.sin(a) * r * 1.6);
    }
    ctx.stroke();
    shape(ctx, HEX_PTS, x, y, r * 0.8, rot);
    ctx.stroke();
    shape(ctx, HEX_PTS, x, y, r * 1.45, rot);
    ctx.stroke();
  },
};

/** 이펙트 모양 키 (common/action_moves.STYLES 와 같다). 모르는 키는 orb 로 그린다. */
export const STYLES = Object.freeze(Object.keys(SHOTS));

// ---------------------------------------------------------------- 장판 (Z.kind 마다)
// q: 장판 하나의 기록 {z, kind, x, y, r, ang, len, w, c, foe, seed, now, u(찬 정도), since(t1 뒤로 흐른 초)}.
// t0 → t1 은 표시(차오름), t1 뒤는 터지는 모습. drawZone 이 save/restore 로 감싼다.

// 표시 칠하기 - 지금 경로를 칠한다: 바닥은 처음엔 옅고 t1 쪽으로 진해진다
function markFill(ctx, q) {
  ctx.globalCompositeOperation = 'source-over';
  ctx.globalAlpha = 0.12 + 0.2 * q.u;
  ctx.fillStyle = q.c.dark;
  ctx.fill();
}

// 차오르는 부분 - 다 차면 떨어진다
function markCharge(ctx, q) {
  ctx.globalAlpha = 0.2 + 0.35 * q.u;
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

function circleMark(fx, ctx, q) {
  circle(ctx, q.x, q.y, q.r);
  markFill(ctx, q);
  if (q.u > 0) {
    circle(ctx, q.x, q.y, q.r * q.u);
    markCharge(ctx, q);
  }
  circle(ctx, q.x, q.y, q.r);
  markEdge(fx, ctx, q);
}

function wedge(ctx, x, y, R, a, h) {
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.arc(x, y, R, a - h, a + h);
  ctx.closePath();
}

// 부채꼴 반각 - 폭(w)은 끝에서의 너비 (아레나 단위)
const coneHalf = (q) => (q.w > 0 ? Math.atan2(q.w / 2, q.len) : CONE_HALF);

// 내려찍기의 떨어지는 것 (v: 0 하늘 → 1 땅). 그림자가 먼저 진해진다
const FALLERS = {
  rock(fx, ctx, q, x, y, v) {
    fx.ink.stretch(ctx, q.c.light, x, y - q.r * 0.6, q.r * 0.15, q.r * 0.6, 0.5 * v);
    shape(ctx, ROCK_PTS[q.seed & 3], x, y, q.r * 0.4, v * 6 + q.seed);
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1;
    ctx.fillStyle = q.c.dark;
    ctx.fill();
    ctx.strokeStyle = q.c.light;
    ctx.lineWidth = 2;
    ctx.stroke();
  },
  zap(fx, ctx, q, x, y, v) {                    // 번개는 하늘에서 한 줄로 내리친다 - 땅에 닿기 전엔 모이는 빛만
    if (v < 0.7) return FALLERS.orb(fx, ctx, q, q.x, q.y - FALL_H * 0.9, v);
    boltPath(ctx, q.x, q.y - FALL_H * 2, FALL_H * 2, Math.PI / 2, q.seed + Math.floor(fx.clock * 20), 7);
    ctx.globalAlpha = v;
    ctx.strokeStyle = q.c.light;
    ctx.lineWidth = 2 + 3 * v;
    ctx.stroke();
    ctx.strokeStyle = WHITE;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    fx.ink.core(ctx, q.c.light, q.x, q.y, q.r * 0.4 * v, v);
  },
  orb(fx, ctx, q, x, y, v) {
    fx.ink.stretch(ctx, q.c.light, x, y - q.r * 0.5, q.r * 0.18, q.r * 0.7, 0.6 * v + 0.2);
    fx.ink.core(ctx, q.c.light, x, y, q.r * 0.35, 1);
  },
};
FALLERS.quake = FALLERS.rock;

function zoneTele(fx, ctx, q) {
  if (q.u < 1) {
    circleMark(fx, ctx, q);
    if (q.u <= FALL_FROM) return;
    const v = (q.u - FALL_FROM) / (1 - FALL_FROM);
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 0.25 + 0.35 * v;
    ctx.fillStyle = INK;
    ctx.beginPath();
    ctx.ellipse(q.x, q.y, q.r * 0.3 * (0.5 + v), q.r * 0.15 * (0.5 + v), 0, 0, TAU);
    ctx.fill();
    ctx.globalCompositeOperation = 'lighter';
    (own(FALLERS, q.z.sty) || FALLERS.orb)(fx, ctx, q, q.x, q.y - (1 - v) * FALL_H, v);
    return;
  }
  const e = clamp01(q.since / LAND_SEC);       // 떨어진 자리 - 번쩍이고 고리가 퍼진다
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.core(ctx, q.c.light, q.x, q.y, q.r * 1.2 * (1 - e), 1 - e);
  ring(ctx, q.c.light, 1 - e, 2 + 8 * (1 - e), q.x, q.y, q.r * (0.6 + 0.6 * e));
}

// 주변 폭발 고리의 모양 키별 덧그림
const RING_ACCENT = {
  quake(fx, ctx, q, rr, e) {                    // 갈라지는 땅
    for (let i = 0; i < 7; i++) {
      boltPath(ctx, q.x, q.y, rr * (0.6 + 0.4 * hash(q.seed + i + 9)), hash(q.seed + i) * TAU, q.seed + i, 4);
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = 0.5 * (1 - e * 0.5);
      ctx.strokeStyle = INK;
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.globalCompositeOperation = 'lighter';
      ctx.strokeStyle = q.c.light;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  },
  wave(fx, ctx, q, rr, e) {
    ring(ctx, q.c.dark, 0.7 * (1 - e), 6, q.x, q.y, rr * 0.75);
    ring(ctx, q.c.light, 0.5 * (1 - e), 3, q.x, q.y, rr * 0.5);
  },
  zap(fx, ctx, q, rr, e) {
    const flick = q.seed + Math.floor(fx.clock * 24);
    for (let i = 0; i < 6; i++) {
      boltPath(ctx, q.x, q.y, rr, (i * TAU) / 6 + hash(flick + i), flick + i, 4);
      ctx.globalAlpha = 1 - e;
      ctx.strokeStyle = q.c.light;
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  },
  sound(fx, ctx, q, rr, e) {
    ring(ctx, q.c.light, 0.7 * (1 - e), 2, q.x, q.y, rr * 0.8);
    ring(ctx, q.c.light, 0.5 * (1 - e), 2, q.x, q.y, rr * 0.6);
  },
};

function zoneRing(fx, ctx, q) {
  if (q.u < 1) return circleMark(fx, ctx, q);
  const e = clamp01(q.since / RING_SEC), rr = q.r * (0.2 + 0.8 * easeOut(e)), { c } = q;
  ctx.globalCompositeOperation = 'lighter';
  fx.ink.glow(ctx, c.dark, q.x, q.y, rr * 1.1, 0.5 * (1 - e));
  ring(ctx, c.light, 1 - e * 0.7, 4 + 14 * (1 - e), q.x, q.y, rr);
  ring(ctx, WHITE, 0.8 * (1 - e), 1 + 4 * (1 - e), q.x, q.y, rr);
  const accent = own(RING_ACCENT, q.z.sty);
  if (accent) accent(fx, ctx, q, rr, e);
}

function zoneCone(fx, ctx, q) {
  const { x, y, ang, len, c } = q, h = coneHalf(q);
  if (q.u < 1) {
    wedge(ctx, x, y, len, ang, h);
    markFill(ctx, q);
    if (q.u > 0) {
      wedge(ctx, x, y, len * q.u, ang, h);
      markCharge(ctx, q);
    }
    wedge(ctx, x, y, len, ang, h);
    markEdge(fx, ctx, q);
    return;
  }
  const e = clamp01(q.since / CONE_SEC);
  ctx.globalCompositeOperation = 'lighter';
  wedge(ctx, x, y, len, ang, h);
  ctx.globalAlpha = 0.08 + 0.4 * (1 - e);
  ctx.fillStyle = c.dark;
  ctx.fill();
  ctx.globalAlpha = 0.9 * (1 - e);
  for (let i = 0; i < 7; i++) {                 // 부채꼴을 따라 뿜어 나가는 줄기
    const a = ang + (hash(q.seed + i) - 0.5) * 1.8 * h, r0 = len * 0.1, r1 = len * (0.3 + 0.7 * easeOut(e));
    line(ctx, c.light, 2 + 4 * (1 - e), x + Math.cos(a) * r0, y + Math.sin(a) * r0, x + Math.cos(a) * r1, y + Math.sin(a) * r1);
  }
  for (let i = 1; i <= 4; i++) {
    const d = len * 0.25 * i * easeOut(e);
    fx.ink.glow(ctx, c.light, x + Math.cos(ang) * d, y + Math.sin(ang) * d, len * 0.2, 0.5 * (1 - e));
  }
}

function zoneBeam(fx, ctx, q) {
  const { len, c } = q, W = q.w > 0 ? q.w : BEAM_W;
  ctx.translate(q.x, q.y);
  ctx.rotate(q.ang);
  if (q.u < 1) {
    ctx.beginPath();
    ctx.rect(0, -W / 2, len, W);
    markFill(ctx, q);
    if (q.u > 0) {
      ctx.beginPath();
      ctx.rect(0, -W / 2, len * q.u, W);
      markCharge(ctx, q);
    }
    ctx.beginPath();
    ctx.rect(0, -W / 2, len, W);
    markEdge(fx, ctx, q);
    ctx.globalCompositeOperation = 'lighter';  // 겨눈 선 - 쏘기가 다가올수록 빨리 깜박인다
    ctx.globalAlpha = Math.sin(fx.clock * (12 + 40 * q.u)) > 0 ? 0.9 : 0.35;
    line(ctx, WHITE, 1.5, 0, 0, len, 0);
    fx.ink.core(ctx, c.light, 0, 0, 8 + 26 * q.u, 0.5 + 0.5 * q.u);   // 입 앞에 모이는 빛
    return;
  }
  const wv = W * (1 + 0.12 * Math.sin(fx.clock * 55));
  ctx.globalCompositeOperation = 'lighter';
  for (const [col, a, k] of BEAM_BANDS) {
    ctx.globalAlpha = a;
    ctx.fillStyle = tone(col, c);
    ctx.fillRect(0, (-wv * k) / 2, len, wv * k);
  }
  for (let d = 0; d <= len; d += BEAM_STEP) fx.ink.glow(ctx, c.light, d, 0, wv * 0.9, 0.35);
  fx.ink.core(ctx, c.light, 0, 0, wv * 1.2, 1);
  fx.ink.core(ctx, c.light, len, 0, wv * 1.5, 1);
}
const BEAM_BANDS = [['dark', 0.6, 1.3], ['light', 0.85, 0.75], [WHITE, 1, 0.28]];   // 겉 · 속 · 흰 심 (색, 알파, 폭 배율)

// 설치 함정 - 모양 키마다 바닥 무늬
const HAZARDS = {
  rock(fx, ctx, q, r) {                         // 떠 있는 뾰족 돌 (스텔스록)
    for (let i = 0; i < 5; i++) {
      const a = hash(q.seed + i) * TAU, d = r * (0.3 + 0.45 * hash(q.seed + i + 5));
      const x = q.x + Math.cos(a) * d, y = q.y + Math.sin(a) * d + Math.sin(fx.clock * 2 + i) * 3;
      shape(ctx, ROCK_PTS[i & 3], x, y, 10, q.seed + i);
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = 1;
      ctx.fillStyle = q.c.dark;
      ctx.fill();
      ctx.strokeStyle = q.c.light;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.star(ctx, WHITE, x - 3, y - 4, 7, 0.5 + 0.5 * Math.sin(fx.clock * 3 + i * 1.7));
    }
  },
  web(fx, ctx, q, r) {                          // 바닥에 펼친 거미줄 (끈적끈적네트)
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 0.55;
    ctx.strokeStyle = WHITE;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    for (let i = 0; i < 8; i++) {
      const a = q.seed + (i * TAU) / 8;
      ctx.moveTo(q.x, q.y);
      ctx.lineTo(q.x + Math.cos(a) * r, q.y + Math.sin(a) * r);
    }
    ctx.stroke();
    for (let i = 1; i <= 3; i++) {
      spikes(ctx, q.x, q.y, (r * i) / 3, 4, Math.cos(Math.PI / 4), q.seed);
      ctx.stroke();
    }
  },
  poison(fx, ctx, q, r) {                       // 독 가시 + 부글거리는 빛 (독압정)
    for (let i = 0; i < 6; i++) {
      const a = hash(q.seed + i) * TAU, d = r * 0.65 * hash(q.seed + i + 3);
      const x = q.x + Math.cos(a) * d, y = q.y + Math.sin(a) * d;
      shape(ctx, SHARD_PTS, x, y, 7, -Math.PI / 2);
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = 1;
      ctx.fillStyle = q.c.dark;
      ctx.fill();
      ctx.strokeStyle = q.c.light;
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.glow(ctx, q.c.light, x, y, 9, 0.3 + 0.3 * Math.sin(fx.clock * 4 + i));
    }
  },
  spikes(fx, ctx, q, r) {                       // 세 갈래 압정 (압정뿌리기 · 그 밖)
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
};

// 함정 기술 → 무늬. 모양 키는 타입을 따라가서 압정뿌리기(땅)도 rock 이 되므로 기술 키를 먼저 본다 (엔진도 둘을 따로 다룬다)
const HAZ_BY_KEY = { STEALTHROCK: 'rock', SPIKES: 'spikes', TOXICSPIKES: 'poison', STICKYWEB: 'web' };

function zoneHaz(fx, ctx, q) {
  const grow = Number.isFinite(q.z.t0) ? 0.3 + 0.7 * clamp01((q.now - q.z.t0) / HAZ_IN) : 1;
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
  (own(HAZARDS, own(HAZ_BY_KEY, q.z.k)) || own(HAZARDS, q.z.sty) || HAZARDS.spikes)(fx, ctx, q, q.r * grow);
}

const ZONES = { tele: zoneTele, ring: zoneRing, cone: zoneCone, beam: zoneBeam, haz: zoneHaz };

// t1 에 한 번 터지는 입자 (그린 때가 t1 을 넘었을 때, 또는 t1 무렵에 서버가 지웠을 때)
const FIRES = {
  tele(fx, q) {                                 // 떨어진 자리 - 파편 · 먼지 · 그을음
    fx.burst(q.x, q.y, debrisOf(q.z.sty, q.z.ty), q.c, 1.4);
    fx.burst(q.x, q.y, DUST, q.c, 1, 0, TAU, 0, q.r * 0.5);
    fx.spawn('core', q.x, q.y, 0, 0, 0.18, q.r * 0.8, q.c.light).size1 = q.r * 1.4;
    fx.wave(q.x, q.y, q.c.light, q.r * 1.5, 0.35, 6, 0);
    fx.anim('scorch', null, q, 0, q.c, '', 1.2).k = q.r;
    fx.kick(0.18);
  },
  ring(fx, q) {
    fx.burst(q.x, q.y, debrisOf(q.z.sty, q.z.ty), q.c, 1.6, 0, TAU, q.r * 0.85, q.r);
    fx.burst(q.x, q.y, DUST, q.c, 1.4, 0, TAU, q.r * 0.6, q.r);
    fx.kick(0.2);
  },
  cone(fx, q) {
    fx.burst(q.x, q.y, debrisOf(q.z.sty, q.z.ty), q.c, 1.6, q.ang, coneHalf(q) * 2, q.len * 0.2, q.len);
    fx.kick(0.12);
  },
  beam(fx, q) {                                 // 광선을 따라 옆으로 튀는 빛
    const spec = debrisOf(q.z.sty, q.z.ty), cx = Math.cos(q.ang), cy = Math.sin(q.ang);
    for (let i = 0; i < 16; i++) {
      const d = Math.random() * q.len, side = i % 2 ? 1 : -1, v = spec.v * rnd(0.4, 1);
      fx.particle(spec, q.c, q.x + cx * d, q.y + cy * d, -cy * side * v, cx * side * v);
    }
    fx.spawn('core', q.x + cx * q.len, q.y + cy * q.len, 0, 0, 0.25, 50, q.c.light).size1 = 90;
    fx.kick(0.22);
  },
};

// ---------------------------------------------------------------- 움직이는 그림 (anim)
// a: {kind, side(따라갈 쪽, 없으면 그 자리), x, y, ang, c, sty, life, delay, age, k(크기), crit, seed, px, py}
// draw(fx, ctx, a, t) - t 는 0~1 진행. drawUnder/Over 가 하나마다 save/restore 로 감싼다.
const SWINGS = {
  slash(fx, ctx, a, t) {                        // 앞쪽을 가로지르는 초승달 칼자국
    const e = easeOut(Math.min(1, t * 1.7)), a0 = a.ang - 1.25, a1 = a0 + 2.5 * e, from = Math.max(a0, a1 - 1.3);
    const fade = t > 0.55 ? (1 - t) / 0.45 : 1;
    ctx.globalCompositeOperation = 'lighter';
    crescent(ctx, a.x, a.y, 54, from, a1, 16);
    ctx.globalAlpha = 0.8 * fade;
    ctx.fillStyle = a.c.dark;
    ctx.fill();
    crescent(ctx, a.x, a.y, 52, from, a1, 9);
    ctx.globalAlpha = fade;
    ctx.fillStyle = a.c.light;
    ctx.fill();
    crescent(ctx, a.x, a.y, 54, from + (a1 - from) * 0.3, a1, 3);
    ctx.fillStyle = WHITE;
    ctx.fill();
  },
  punch(fx, ctx, a, t) {                        // 앞에서 터지는 주먹 - 모여드는 속도선 + 번쩍
    const hx = a.x + Math.cos(a.ang) * REACH, hy = a.y + Math.sin(a.ang) * REACH, e = easeOut(t);
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = 1 - t;
    for (let i = 0; i < 6; i++) {
      const d = a.ang + Math.PI + (i - 2.5) * 0.28, r0 = 70 * (1 - e) + 18, r1 = r0 + 26;
      line(ctx, WHITE, 2, hx + Math.cos(d) * r0, hy + Math.sin(d) * r0, hx + Math.cos(d) * r1, hy + Math.sin(d) * r1);
    }
    fx.ink.core(ctx, a.c.light, hx, hy, 18 + 26 * e, 1 - t);
    ring(ctx, a.c.light, 1 - t, 1 + 3 * (1 - t), hx, hy, 14 + 34 * e);
  },
  bite(fx, ctx, a, t) {                         // 위아래 이빨이 다문다
    const e = easeOut(Math.min(1, t * 2));
    ctx.translate(a.x + Math.cos(a.ang) * REACH, a.y + Math.sin(a.ang) * REACH);
    ctx.rotate(a.ang);
    if (t > 0.45) {
      ctx.globalCompositeOperation = 'lighter';
      fx.ink.core(ctx, a.c.light, 0, 0, 34 * (1 - t), 1);
    }
    fangs(ctx, 18, 26 * (1 - e) + 1, a.c.dark, t > 0.6 ? (1 - t) / 0.4 : 1);
  },
};

// 지나온 길에 잔상 줄 + 옅은 몸 빛 (돌진 · 피하기 · 뛰어오르기)
function trailTick(fx, a) {
  const p = fx.pos(a.side);
  if (!p) return;
  if (a.px !== null && Math.hypot(p.x - a.px, p.y - a.py) > 2) {
    const l = fx.spawn('line', p.x, p.y, 0, 0, TRAIL_LIFE, 1, a.c.light);
    l.x2 = a.px;
    l.y2 = a.py;
    l.w = 12;
    fx.spawn('glow', p.x, p.y, 0, 0, TRAIL_LIFE, 30, a.c.dark).size1 = 16;
  }
  a.px = p.x;
  a.py = p.y;
}

const ANIMS = {
  charge: { layer: 1, draw(fx, ctx, a, t) {   // 기술 준비 - 줄어드는 고리 + 모이는 빛
    ctx.globalCompositeOperation = 'lighter';
    ring(ctx, a.c.light, 0.25 + 0.6 * t, 2 + 3 * t, a.x, a.y, (64 * (1 - t) + 14) * a.k);
    fx.ink.core(ctx, a.c.light, a.x, a.y, (10 + 24 * t) * a.k, 0.4 + 0.6 * t);
  } },
  swing: { layer: 1, draw(fx, ctx, a, t) { (own(SWINGS, a.sty) || SWINGS.slash)(fx, ctx, a, t); } },
  trail: { layer: 1, tick: trailTick },
  pillar: { layer: 1, draw(fx, ctx, a, t) {   // 강화 · 회복 - 솟는 빛기둥과 발밑 고리
    const s = Math.sin(Math.PI * t);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.stretch(ctx, a.c.light, a.x, a.y - 90, 26 + 12 * (1 - t), 120, 0.55 * s);
    fx.ink.stretch(ctx, WHITE, a.x, a.y - 90, 9, 110, 0.5 * s);
    ring(ctx, a.c.light, 1 - t, 1 + 3 * (1 - t), a.x, a.y, 26 + 30 * t);
  } },
  shield: { layer: 1, draw(fx, ctx, a, t) {   // 육각 막 - 한 변씩 돌며 반짝인다
    const R = 50 * (0.6 + 0.4 * easeOut(Math.min(1, t * 5))), fade = t > 0.7 ? (1 - t) / 0.3 : 1, rot = fx.clock * 0.8;
    ctx.globalCompositeOperation = 'lighter';
    shape(ctx, HEX_PTS, a.x, a.y, R, rot);
    ctx.globalAlpha = 0.16 * fade;
    ctx.fillStyle = a.c.light;
    ctx.fill();
    ctx.globalAlpha = 0.9 * fade;
    ctx.strokeStyle = a.c.light;
    ctx.lineWidth = 3;
    ctx.stroke();
    shape(ctx, HEX_PTS, a.x, a.y, R * 0.82, rot);
    ctx.globalAlpha = 0.35 * fade;
    ctx.strokeStyle = WHITE;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    const e0 = rot + (Math.floor(fx.clock * 6) % 6) * (TAU / 6), e1 = e0 + TAU / 6;
    ctx.globalAlpha = fade;
    line(ctx, WHITE, 4, a.x + Math.cos(e0) * R, a.y + Math.sin(e0) * R, a.x + Math.cos(e1) * R, a.y + Math.sin(e1) * R);
  } },
  counter: { layer: 1, draw(fx, ctx, a, t) {  // 되받기 - 도는 가시 테
    const R = 40 + 18 * easeOut(t);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.glow(ctx, a.c.dark, a.x, a.y, R * 1.3, 0.5 * (1 - t));
    spikes(ctx, a.x, a.y, R, 8, 0.6, fx.clock * 3);
    ctx.globalAlpha = 1 - t;
    ctx.strokeStyle = a.c.light;
    ctx.lineWidth = 3;
    ctx.stroke();
  } },
  impact: { layer: 1, draw(fx, ctx, a, t) {   // 맞는 순간 - 세 겹 별 번쩍, 급소면 금빛 X
    const R = (36 - 20 * t) * a.k;
    ctx.globalCompositeOperation = 'lighter';
    spikes(ctx, a.x, a.y, R, 10, 0.36, a.seed);
    ctx.globalAlpha = 1 - t;
    ctx.fillStyle = a.c.dark;
    ctx.fill();
    spikes(ctx, a.x, a.y, R * 0.72, 8, 0.4, a.seed + 0.3);
    ctx.fillStyle = a.c.light;
    ctx.fill();
    fx.ink.core(ctx, WHITE, a.x, a.y, R * 0.6, 1 - t);
    if (!a.crit) return;
    const L = (34 - 12 * t) * a.k;
    ctx.globalAlpha = 1 - t;
    for (let sg = -1; sg <= 1; sg += 2) {
      lens(ctx, a.x - L, a.y - L * sg * 0.9, a.x + L, a.y + L * sg * 0.9, 6 * (1 - t) + 1);
      ctx.fillStyle = GOLD;
      ctx.fill();
      lens(ctx, a.x - L * 0.8, a.y - L * sg * 0.72, a.x + L * 0.8, a.y + L * sg * 0.72, 2);
      ctx.fillStyle = WHITE;
      ctx.fill();
    }
  } },
  swap: { layer: 1, draw(fx, ctx, a, t) {     // 교체 - 볼에서 나오는 빛
    const s = Math.sin(Math.PI * t);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.stretch(ctx, BALL.dark, a.x, a.y - 110, 30 * (1 - 0.5 * t), 150, 0.6 * s);
    fx.ink.stretch(ctx, WHITE, a.x, a.y - 110, 12, 140, 0.7 * s);
    fx.ink.core(ctx, BALL.dark, a.x, a.y, 40 * (1 - t) + 10, s);
  } },
  ko: { layer: 1, draw(fx, ctx, a, t) {       // 쓰러짐 - 빨려 들듯 줄어드는 검은 고리, 그리고 터진다
    if (t < KO_PULL) {
      ctx.globalCompositeOperation = 'source-over';
      ring(ctx, INK, 0.45, 6, a.x, a.y, 80 * (1 - t / KO_PULL) + 10);
      return;
    }
    const e = (t - KO_PULL) / (1 - KO_PULL);
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.core(ctx, WHITE, a.x, a.y, 60 * (1 - e) + 20, 1 - e);
    ring(ctx, WHITE, 1 - e, 6 * (1 - e) + 1, a.x, a.y, 30 + 110 * e);
  } },
  sky: { layer: 1, draw(fx, ctx, a, t) {      // 하늘로 솟는 빛 (내려찍기 · 뛰어오르기)
    const f = 1 - t;
    ctx.globalCompositeOperation = 'lighter';
    fx.ink.stretch(ctx, a.c.light, a.x, a.y - 260, 18 * f + 4, 280, 0.65 * f);
    fx.ink.core(ctx, a.c.light, a.x, a.y - 10, 26 * f + 4, f);
  } },
  scorch: { layer: 0, draw(fx, ctx, a, t) {   // 떨어진 자리에 잠깐 남는 그을음 (k = 반지름)
    ctx.globalCompositeOperation = 'source-over';
    fx.ink.soft(ctx, INK, a.x, a.y, a.k, 0.4 * (1 - t));
  } },
};

// ---------------------------------------------------------------- 이벤트
// 기술 준비 - 몸으로 모여드는 빛
function gather(fx, side, at, c, life, k = 1) {
  fx.anim('charge', side, at, 0, c, '', life).k = k;
  const n = Math.round(8 * k), d = 70 * k;
  for (let i = 0; i < n; i++) {
    const a = (i / n) * TAU + Math.random() * 0.5, cx = Math.cos(a), cy = Math.sin(a);
    fx.spawn('glow', at.x + cx * d, at.y + cy * d, (-cx * d) / life, (-cy * d) / life, life, 6, c.light).size1 = 2;
  }
}

// 기술의 꼴(kind)마다 쓰는 순간의 그림. 날아가는 탄 · 장판은 서버가 보내므로 여기서는 몸 쪽만
const CAST = {
  proj(fx, ev, at, c) { gather(fx, ev.w, at, c, GATHER_SEC); },
  beam(fx, ev, at, c) { gather(fx, ev.w, at, c, 0.6, 1.4); },
  burst(fx, ev, at, c) {
    gather(fx, ev.w, at, c, 0.3);
    fx.wave(at.x, at.y, c.light, 80, 0.45, 4, 0);
  },
  melee(fx, ev, at, c, ang) {
    fx.anim('swing', ev.w, at, ang, c, ev.sty, SWING_SEC, SWING_DELAY);
    if (!own(SWINGS, ev.sty)) {                 // 불꽃 펀치 같은 것 - 앞에서 그 모양의 조각이 튄다
      fx.burst(at.x + Math.cos(ang) * REACH, at.y + Math.sin(ang) * REACH, debrisOf(ev.sty, ev.ty), c, 0.8, ang, 1.6);
    }
  },
  dash(fx, ev, at, c, ang) {
    fx.anim('trail', ev.w, at, ang, c, ev.sty, 0.45);
    fx.burst(at.x, at.y, DUST, c, 0.8, ang + Math.PI, 1.6);
  },
  leap(fx, ev, at, c, ang) {
    fx.burst(at.x, at.y, DUST, c, 1.2);
    fx.anim('trail', ev.w, at, ang, c, ev.sty, 0.5);
    fx.anim('sky', ev.w, at, ang, c, ev.sty, 0.3);
  },
  strike(fx, ev, at, c, ang) { fx.anim('sky', ev.w, at, ang, c, ev.sty, 0.45); },
  self(fx, ev, at, c) {
    fx.anim('pillar', ev.w, at, 0, c, ev.sty, 0.8);
    fx.burst(at.x, at.y, MOTES, c, 1, 0, TAU, 0, 34);
  },
  heal(fx, ev, at) {
    fx.anim('pillar', ev.w, at, 0, HEAL, ev.sty, 0.8);
    fx.burst(at.x, at.y, PLUSES, HEAL, 1, 0, TAU, 0, 34);
  },
  guard(fx, ev, at, c) { fx.anim('shield', ev.w, at, 0, c, ev.sty, 0.7); },
  counter(fx, ev, at) { fx.anim('counter', ev.w, at, 0, COUNTER, ev.sty, 0.7); },
};
CAST.cone = CAST.proj;
CAST.status = CAST.proj;
CAST.hazard = CAST.proj;

// 상태이상 · 그 밖의 상태가 걸릴 때 (색, 튀는 조각)
const STATUS_LOOK = {
  brn: [COLORS.FIRE, 'flame'], psn: [COLORS.POISON, 'bubble'], tox: [COLORS.POISON, 'bubble'],
  par: [COLORS.ELECTRIC, 'zap'], slp: [SLEEP, 'star'], frz: [COLORS.ICE, 'shard'], cnf: [DIZZY, 'star'],
  seed: [COLORS.GRASS, 'leaf'], trap: [COLORS.GROUND, 'pebble'], flinch: [PLAIN, 'spark'], scr: [SCREEN, 'glint'],
};

function onHit(fx, ev) {
  const at = fx.at(ev, ev.v), c = colorsOf(ev.ty), crit = !!ev.crit, me = fx.mine(ev.v);
  const eff = Number.isFinite(ev.eff) ? ev.eff : 1;
  if (Number.isFinite(ev.dmg)) fx.say(ev.v, at, String(Math.round(ev.dmg)), LOOK.dmg);
  if (eff === 0) {                              // 막혔다 - 작게 튕기기만
    fx.burst(at.x, at.y, FIZZLE, PLAIN, 1);
    fx.say(ev.v, at, '효과가 없다', LOOK.none);
    return;
  }
  const k = eff > 1 ? 1.35 : eff < 1 ? 0.75 : 1;
  const a = fx.anim('impact', null, at, 0, c, '', IMPACT_SEC);
  a.k = k;
  a.crit = crit;
  fx.spawn('core', at.x, at.y, 0, 0, 0.16, 40 * k, c.light).size1 = 70 * k;
  fx.wave(at.x, at.y, c.light, 90 * k, 0.32, 8);
  fx.wave(at.x, at.y, c.dark, 60 * k, 0.4, 5);
  fx.burst(at.x, at.y, debrisOf(null, ev.ty), c, k);
  fx.burst(at.x, at.y, DEBRIS.spark, SHINE, 0.6 * k);
  if (crit) fx.burst(at.x, at.y, DEBRIS.spark, GOLDEN, 1);
  // 세게 맞을수록 · 내가 맞을수록 크게 흔들리고 오래 멈춘다
  fx.kick(0.14 * k + (crit ? 0.1 : 0) + (me ? 0.12 : 0), eff > 1 || crit ? 0.085 : 0.045,
    me ? 0.14 : eff > 1 ? 0.08 : 0, me ? HURT : WHITE);
  if (eff > 1) fx.say(ev.v, at, '효과가 굉장했다!', LOOK.great);
  else if (eff < 1) fx.say(ev.v, at, '효과가 별로인 듯하다…', LOOK.weak);
  if (crit) fx.say(ev.v, at, '급소!', LOOK.crit);
}

// 이긴 쪽 화면에 떨어지는 꽃가루
function confetti(fx) {
  for (let i = 0; i < CONFETTI_N; i++) {
    const p = fx.spawn('shard', rnd(0, ARENA_W), rnd(-80, 0), rnd(-40, 40), rnd(80, 240), rnd(2, 3.2), rnd(5, 9),
      CONFETTI[i % CONFETTI.length]);
    p.add = false;
    p.g = 60;
    p.drag = 0.6;
    p.rot = rnd(0, TAU);
    p.vr = rnd(-8, 8);
    p.size1 = p.size;
  }
}

const ON = {
  cast(fx, ev) {
    const at = fx.at(ev, ev.w), ang = Number.isFinite(ev.ang) ? ev.ang : fx.aim(ev.w, at);
    (own(CAST, ev.kind) || CAST.proj)(fx, ev, at, colorsOf(ev.ty), ang);
  },
  hit: onHit,
  clash(fx, ev) {                               // 힘겨루기 - 흰 섬광 + 흰 · 금 고리
    const at = fx.at(ev, null);
    fx.anim('impact', null, at, 0, SHINE, '', IMPACT_SEC).k = 1.3;
    fx.spawn('core', at.x, at.y, 0, 0, 0.2, 50, WHITE).size1 = 90;
    fx.wave(at.x, at.y, WHITE, 120, 0.35, 8);
    fx.wave(at.x, at.y, GOLD, 80, 0.45, 5);
    fx.burst(at.x, at.y, DEBRIS.spark, SHINE, 1.6);
    fx.burst(at.x, at.y, DEBRIS.spark, GOLDEN, 1);
    fx.kick(0.22, 0.06, 0.08);
  },
  dodge(fx, ev) {
    const at = fx.at(ev, ev.w);
    fx.anim('trail', ev.w, at, 0, DODGE, '', DODGE_TRAIL);
    fx.burst(at.x, at.y, DUST, DODGE, 0.8);
    fx.wave(at.x, at.y, DODGE.light, 46, 0.25, 3);
  },
  status(fx, ev) {
    const at = fx.at(ev, ev.w), [c, debris] = own(STATUS_LOOK, ev.s) || [PLAIN, 'spark'];
    fx.burst(at.x, at.y - 20, DEBRIS[debris], c, 1.2);
    fx.wave(at.x, at.y, c.light, 60, 0.4, 4);
    const kr = own(STATUS_KR, ev.s) || own(COND_KR, ev.s);
    if (kr) fx.say(ev.w, at, kr, LOOK.info, c.light);
  },
  cure(fx, ev) {
    const at = fx.at(ev, ev.w), kr = own(STATUS_KR, ev.s);
    fx.burst(at.x, at.y - 20, DEBRIS.glint, SHINE, 0.8);
    if (kr) fx.say(ev.w, at, kr + ' 나음', LOOK.info);   // 풀죽음 · 묶임은 저절로 풀리는 게 보통이라 조용히
  },
  stat(fx, ev) {
    const d = Number.isFinite(ev.d) ? ev.d : 0;
    if (!d) return;
    const at = fx.at(ev, ev.w), up = d > 0, n = Math.min(3, Math.abs(d));
    for (let i = 0; i < n; i++) fx.burst(at.x, at.y + (up ? 10 : -60), up ? ARROW_UP : ARROW_DOWN, PLAIN, 1, 0, TAU, 0, 34);
    const name = own(STAT_KR, ev.st) || '';
    fx.say(ev.w, at, (name + ' ' + (up ? '▲' : '▼').repeat(n)).trim(), LOOK.info, up ? UP : DOWN);
  },
  heal(fx, ev) {
    const at = fx.at(ev, ev.w);
    fx.burst(at.x, at.y, PLUSES, HEAL, 1, 0, TAU, 0, 36);
    fx.burst(at.x, at.y, MOTES, HEAL, 1, 0, TAU, 0, 40);
    fx.wave(at.x, at.y, HEAL.light, 56, 0.5, 3);
  },
  guard(fx, ev) {                               // 막았다
    const at = fx.at(ev, ev.w);
    fx.anim('shield', ev.w, at, 0, SHINE, '', 0.45);
    fx.burst(at.x, at.y, DEBRIS.glint, SHINE, 0.8);
  },
  counter(fx, ev) {                             // 되받았다
    const at = fx.at(ev, ev.w);
    fx.anim('counter', ev.w, at, 0, COUNTER, '', 0.5);
    fx.burst(at.x, at.y, DEBRIS.spark, COUNTER, 1.4);
    fx.kick(0.12, 0.05);
  },
  swap(fx, ev) {
    const at = fx.at(ev, ev.w);
    fx.anim('swap', ev.w, at, 0, BALL, '', 0.6);
    fx.wave(at.x, at.y, BALL.dark, 70, 0.4, 5);
    fx.burst(at.x, at.y, MOTES, BALL, 1, 0, TAU, 0, 30);
  },
  ko(fx, ev) {
    const at = fx.at(ev, ev.w);
    fx.anim('ko', null, at, 0, PLAIN, '', KO_SEC);
    fx.burst(at.x, at.y, PUFF, SOOT, 1.4, 0, TAU, 0, 30);
    fx.burst(at.x, at.y, DEBRIS.glint, SHINE, 1.2);
    fx.kick(0.4, 0.12, 0.18, fx.mine(ev.w) ? HURT : WHITE);
  },
  phase(fx, ev) {
    if (ev.ph === 'fight') fx.kick(0, 0, 0.12);
  },
  over(fx, ev) {
    fx.kick(0.15, 0, 0.2);
    if (fx.world && ev.winner === fx.world.you) confetti(fx);
  },
};

// ---------------------------------------------------------------- 글씨
// px 글씨 크기 · life 초 · pop 처음 커지는 배율 · merge 같은 말이 잇달아 오면 하나로 (데미지 숫자는 하나씩)
function look(px, fill, edge, life, pop, merge = true) {
  return { font: `800 ${px}px ${FONT}`, fill, edge, lw: Math.max(3, px / 7), life, pop, merge };
}
const LOOK = {
  dmg: look(40, WHITE, '#a3102a', 0.9, 0.7, false),
  great: look(28, GOLD, '#5a2a00', 1.2, 0.5),
  weak: look(24, '#c8d2e6', '#1c2333', 1.1, 0.3),
  none: look(24, '#a6acb8', '#1c2333', 1.1, 0.3),
  crit: look(30, GOLD, '#6a1a00', 1.0, 0.8),
  info: look(22, WHITE, '#141a28', 1.2, 0.25),
};

// ---------------------------------------------------------------- Fx
export class Fx {
  /** opts.canvas(w, h) - 스프라이트 캔버스를 만드는 곳 (검사용). null 이면 스프라이트 없이 그린다. */
  constructor(opts = {}) {
    this.ink = new Ink('canvas' in opts ? opts.canvas : defaultCanvas);
    this.parts = new Particles(POOL_MAX);
    this.anims = [];
    this.texts = [];
    this.textFloor = new Map();                 // tickTexts 가 쓰는 쪽마다 바로 아래 글씨의 y
    this.shots = new Map();                     // 탄 id → 기록 (처음 본 순간 · 사라진 순간을 안다)
    this.zones = new Map();                     // 장판 id → 기록 (t1 에 한 번 터진다)
    this.world = null;
    this.clock = 0;                             // 이펙트 시계 (초) - 깜박임 · 흔들림
    this.dt = 0;                                // 마지막 update 의 dt - 탄 꼬리 입자 수를 맞춘다
    this.trauma = 0;                            // 흔들림 세기 0~1
    this.stop = 0;                              // 남은 멈춤 (초)
    this.flash = 0;
    this.flashColor = WHITE;
  }

  // ------------------------------------------------ 바깥에서 부르는 것
  event(ev, world) {
    if (world) this.world = world;
    const on = ev && own(ON, ev.e);
    if (on) on(this, ev);
  }

  update(dt) {
    dt = dt > 0 ? Math.min(dt, MAX_DT) : 0;
    this.clock += dt;
    this.dt = dt;
    const t = this.stop > 0 ? dt * HITSTOP_SLOW : dt;
    this.stop = Math.max(0, this.stop - dt);
    this.trauma = Math.max(0, this.trauma - dt * SHAKE_DECAY);
    this.flash = Math.max(0, this.flash - dt * FLASH_DECAY);
    this.parts.update(t);
    this.tickAnims(t);
    this.tickTexts(t);
    this.forget();
  }

  drawProjectile(ctx, p, x, y) {
    const q = this.shotOf(p, x, y);
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.lineCap = 'round';
    (own(SHOTS, p.sty) || SHOTS.orb)(this, ctx, q);
    ctx.restore();
    this.trickle(q, own(EMIT, p.sty) || EMIT.orb);
  }

  drawZone(ctx, z, now) {
    const q = this.zoneOf(z, now);
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    (own(ZONES, z.kind) || circleMark)(this, ctx, q);
    ctx.restore();
    const fire = own(FIRES, z.kind);
    if (fire && !q.fired && q.u >= 1) {
      q.fired = true;
      fire(this, q);
    }
  }

  drawUnder(ctx) {
    ctx.save();
    this.parts.draw(ctx, this.ink, 0);
    this.drawAnims(ctx, 0);
    ctx.restore();
  }

  drawOver(ctx) {
    ctx.save();
    this.parts.draw(ctx, this.ink, 1);
    this.drawAnims(ctx, 1);
    this.drawTexts(ctx);
    this.drawFlash(ctx);
    ctx.restore();
  }

  shake() {
    if (this.trauma <= 0) return { x: 0, y: 0 };
    const m = SHAKE_MAX * this.trauma * this.trauma, t = this.clock;
    return {
      x: m * (Math.sin(t * 71) * 0.6 + Math.sin(t * 43 + 1.7) * 0.4),
      y: m * (Math.sin(t * 59 + 0.6) * 0.6 + Math.sin(t * 37 + 2.9) * 0.4),
    };
  }

  /** 지금 살아 있는 것의 수 (검사 · 디버그). */
  counts() {
    return { particles: this.parts.live, anims: this.anims.length, texts: this.texts.length };
  }

  // ------------------------------------------------ 자리
  pos(side) {
    const w = this.world;
    if (!w || typeof w.pos !== 'function' || (side !== 'a' && side !== 'b')) return null;
    const p = w.pos(side);
    return p && Number.isFinite(p.x) && Number.isFinite(p.y) ? p : null;
  }

  // 이벤트가 난 자리: 이벤트의 x, y → 그 쪽 몸 → 아레나 가운데
  at(ev, side) {
    if (Number.isFinite(ev.x) && Number.isFinite(ev.y)) return { x: ev.x, y: ev.y };
    const p = this.pos(side);
    return p ? { x: p.x, y: p.y } : { x: ARENA_W / 2, y: ARENA_H / 2 };
  }

  // 겨눈 쪽을 모르면 상대 쪽
  aim(side, at) {
    const p = this.pos(side === 'a' ? 'b' : 'a');
    return p ? Math.atan2(p.y - at.y, p.x - at.x) : 0;
  }

  mine(side) {
    return !!this.world && side === this.world.you;
  }

  // 누구 것인지 모르면 상대 것으로 친다 (더 잘 보이게)
  foe(side) {
    return !this.mine(side);
  }

  // ------------------------------------------------ 만들기
  spawn(shape, x, y, vx, vy, life, size, color) {
    return this.parts.spawn(shape, x, y, vx, vy, life, size, color);
  }

  // spec 하나를 (x, y) 에서 vx, vy 로
  particle(spec, c, x, y, vx, vy, k = 1) {
    const p = this.parts.spawn(spec.shape, x, y, vx, vy + (spec.up || 0), spec.life * rnd(0.7, 1.3),
      spec.size * rnd(0.7, 1.3) * k, tone(spec.c, c));
    p.color2 = c.dark;
    p.g = spec.g || 0;
    p.drag = spec.drag ?? 3;
    p.rot = Math.atan2(vy, vx);
    p.vr = spec.spin ? rnd(-spec.spin, spec.spin) : 0;
    if (spec.w) p.w = spec.w;
    if (spec.end !== undefined) p.size1 = p.size * spec.end;
    if (spec.layer === 0) p.layer = 0;
    return p;
  }

  // spec.n × k 개를 뿌린다. 방향은 ang ± arc/2, 시작은 가운데에서 r0~r1 떨어진 곳
  burst(x, y, spec, c, k = 1, ang = 0, arc = TAU, r0 = 0, r1 = r0) {
    const n = Math.round(spec.n * k), sp = Math.sqrt(k);
    for (let i = 0; i < n; i++) {
      const a = ang + (Math.random() - 0.5) * arc, d = rnd(r0, r1), v = spec.v * rnd(0.5, 1.2) * sp;
      const cx = Math.cos(a), cy = Math.sin(a);
      this.particle(spec, c, x + cx * d, y + cy * d, cx * v, cy * v, k);
    }
  }

  // 퍼지는 고리 하나
  wave(x, y, col, r1, life, w, layer = 1) {
    const p = this.parts.spawn('ring', x, y, 0, 0, life, r1 * 0.15, col);
    p.size1 = r1;
    p.w = w;
    p.layer = layer;
  }

  anim(kind, side, at, ang, c, sty, life, delay = 0) {
    if (this.anims.length >= ANIM_MAX) this.anims.shift();
    const a = { kind, side, x: at.x, y: at.y, ang, c, sty, life, delay, age: 0, k: 1, crit: false,
      seed: Math.random() * TAU, px: null, py: null };
    this.anims.push(a);
    return a;
  }

  // 새 글씨는 몸 위에 뜬다 (먼저 뜬 것은 tickTexts 가 위로 민다). 같은 말이 잇달아 오면 (여러 번 치는 기술) 있던 것을 다시 튀긴다
  say(side, at, s, look, fill = look.fill) {
    if (look.merge) {
      const same = this.texts.find((t) => t.side === side && t.s === s && t.age < MERGE_SEC);
      if (same) {
        same.age = 0;
        return;
      }
    }
    if (this.texts.length >= TEXT_MAX) this.texts.shift();
    this.texts.push({ s, side, x: at.x, y: at.y - TEXT_LIFT, vy: -TEXT_UP, age: 0, look, fill });
  }

  // 흔들림 · 멈춤 · 화면 번쩍
  kick(shake, stop = 0, flash = 0, color = WHITE) {
    this.trauma = Math.min(1, this.trauma + shake);
    this.stop = Math.max(this.stop, stop);
    if (flash > this.flash) {
      this.flash = flash;
      this.flashColor = color;
    }
  }

  // ------------------------------------------------ 탄 · 장판 기록
  shotOf(p, x, y) {
    let q = p.id != null ? this.shots.get(p.id) : undefined;
    const fresh = !q;
    if (fresh) {
      q = { x, y, ux: 1, uy: 0, ang: 0, r: SHOT_R, c: PLAIN, seed: seedOf(p.id), at: 0 };
      if (p.id != null) this.shots.set(p.id, q);
    }
    const vx = num(p.vx), vy = num(p.vy), v = Math.hypot(vx, vy);
    if (v > 1e-6) {                             // 멈춘 탄은 마지막 방향 그대로
      q.ux = vx / v;
      q.uy = vy / v;
      q.ang = Math.atan2(vy, vx);
    }
    q.x = x;
    q.y = y;
    q.r = p.r > 0 ? p.r : SHOT_R;
    q.c = colorsOf(p.ty);
    q.at = this.clock;
    if (fresh) this.launch(q);
    return q;
  }

  zoneOf(z, now) {
    let q = z.id != null ? this.zones.get(z.id) : undefined;
    if (!q) {
      q = { seed: seedOf(z.id), fired: false };
      if (z.id != null) this.zones.set(z.id, q);
    }
    q.z = z;
    q.kind = z.kind;
    q.x = num(z.x, ARENA_W / 2);
    q.y = num(z.y, ARENA_H / 2);
    q.r = z.r > 0 ? z.r : z.w > 0 ? z.w / 2 : ZONE_R;     // r 이 없으면 w (표시 지름)
    q.ang = num(z.ang);
    q.len = z.len > 0 ? z.len : z.r > 0 ? z.r : BEAM_LEN;
    q.w = z.w > 0 ? z.w : 0;
    q.c = colorsOf(z.ty);
    q.foe = this.foe(z.o);
    q.now = now;
    q.u = charge(z, now);
    q.since = now - z.t1;
    q.at = this.clock;
    return q;
  }

  // 탄이 처음 보인 순간 - 입 앞 번쩍 + 앞으로 튀는 불티
  launch(q) {
    this.spawn('core', q.x, q.y, 0, 0, 0.14, q.r * 1.6, q.c.light).size1 = q.r * 2.6;
    this.burst(q.x, q.y, MUZZLE, q.c, 1, q.ang, 1.2);
  }

  // 날아가는 탄이 흘리는 꼬리 입자. 그리는 김에 흘리고, 수는 update 의 dt 로 맞춘다 (화면 빈도와 상관없이 1초에 rate 개)
  trickle(q, spec) {
    const n = Math.floor(spec.rate * this.dt + Math.random());
    for (let i = 0; i < n; i++) {
      const a = Math.random() * TAU, v = spec.v * Math.random();
      this.particle(spec, q.c, q.x + rnd(-0.5, 0.5) * q.r, q.y + rnd(-0.5, 0.5) * q.r, Math.cos(a) * v, Math.sin(a) * v);
    }
  }

  // 서버가 지운 탄 · 장판을 잊는다. 탄은 작게 흩어지고, t1 무렵에 지워진 표시는 떨어진 것으로 친다
  forget() {
    for (const [id, q] of this.shots) {
      if (this.clock - q.at <= GONE_SEC) continue;
      this.burst(q.x, q.y, FIZZLE, q.c, 1);
      this.shots.delete(id);
    }
    for (const [id, q] of this.zones) {
      if (this.clock - q.at <= GONE_SEC) continue;
      const fire = own(FIRES, q.kind);
      if (fire && !q.fired && q.now >= q.z.t1 - LATE_SEC) fire(this, q);
      this.zones.delete(id);
    }
  }

  // ------------------------------------------------ 나이 먹이기 · 그리기
  tickAnims(dt) {
    let n = 0;
    for (const a of this.anims) {
      a.age += dt;
      if (a.age >= a.delay + a.life) continue;
      const { tick } = ANIMS[a.kind];
      if (tick && a.age >= a.delay) tick(this, a);
      this.anims[n++] = a;
    }
    this.anims.length = n;
  }

  tickTexts(dt) {
    let n = 0;
    const drag = Math.exp(-TEXT_DRAG * dt);
    for (const t of this.texts) {
      t.age += dt;
      if (t.age >= t.look.life) continue;
      t.y += t.vy * dt;
      t.vy *= drag;
      this.texts[n++] = t;
    }
    this.texts.length = n;
    // 같은 쪽 글씨는 새것부터 아래에서 위로, TEXT_GAP 씩 띄운다 (늦게 뜬 것이 빨리 올라와도 겹치지 않게)
    const floor = this.textFloor;
    floor.clear();
    for (let i = n - 1; i >= 0; i--) {
      const t = this.texts[i], below = floor.get(t.side);
      if (below !== undefined && t.y > below - TEXT_GAP) t.y = below - TEXT_GAP;
      floor.set(t.side, t.y);
    }
  }

  drawAnims(ctx, layer) {
    for (const a of this.anims) {
      const { draw, layer: at } = ANIMS[a.kind];
      if (!draw || at !== layer || a.age < a.delay) continue;
      const p = a.side ? this.pos(a.side) : null;   // 몸을 따라간다
      if (p) {
        a.x = p.x;
        a.y = p.y;
      }
      ctx.save();
      draw(this, ctx, a, (a.age - a.delay) / a.life);
      ctx.restore();
    }
  }

  // 데미지 숫자 · 효과 글씨 - 톡 커졌다 줄며 떠오르고, 끝에 흐려진다
  drawTexts(ctx) {
    if (!this.texts.length) return;
    ctx.globalCompositeOperation = 'source-over';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineJoin = 'round';
    for (const t of this.texts) {
      const k = t.age / t.look.life, sc = k < POP_K ? 1 + t.look.pop * (1 - k / POP_K) : 1;
      ctx.save();
      ctx.translate(t.x, t.y);
      ctx.scale(sc, sc);
      ctx.globalAlpha = k < FADE_K ? 1 : (1 - k) / (1 - FADE_K);
      ctx.font = t.look.font;
      ctx.lineWidth = t.look.lw;
      ctx.strokeStyle = t.look.edge;
      ctx.strokeText(t.s, 0, 0);
      ctx.fillStyle = t.fill;
      ctx.fillText(t.s, 0, 0);
      ctx.restore();
    }
  }

  drawFlash(ctx) {
    if (this.flash <= 0) return;
    ctx.globalCompositeOperation = this.flashColor === WHITE ? 'lighter' : 'source-over';
    ctx.globalAlpha = Math.min(1, this.flash);
    ctx.fillStyle = this.flashColor;
    ctx.fillRect(-FLASH_PAD, -FLASH_PAD, ARENA_W + FLASH_PAD * 2, ARENA_H + FLASH_PAD * 2);
  }
}
