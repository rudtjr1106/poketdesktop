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

   파일 나눔.
     fx.js                   이 Fx (이벤트 · 움직이는 그림 · 글씨 · 흔들림) - 바깥은 이 파일만 부른다
     fx/core.js              같이 쓰는 것 (색 · 도형 · 빛 스프라이트 · 입자 풀 · spec · BASE) + **모양 훅 설명**
     fx/zones.js             장판 표시 (테두리 · 차오름 · 점선) 와 t1 에 터지는 입자
     fx/styles/*.js          모양 키(sty)마다의 그림 - 집안(air · fire · mystic · body) 하나에 파일 하나
     fx/styles/index.js      모양 키 → 집안 목록 · 훅 고르기

   그리는 법.
     * 빛은 가산 혼합("lighter") + 색마다 한 번만 만들어 두는 방사형 그라디언트 그림(스프라이트).
       입자마다 · 프레임마다 그라디언트를 만들지 않는다.
     * 입자는 600개 풀을 돌려 쓴다 - 넘치면 가장 먼저 만든 것부터 덮는다.
     * 좌표는 전부 아레나 단위 (1600×900). 화면 배율은 render 가 setTransform 으로 걸어 두므로 여기서는
       translate · rotate · scale 만 쓰고, 그리기마다 save/restore 로 ctx 를 받은 그대로 돌려놓는다.
     * world 는 이벤트 때 받아 두고, 몸을 따라가는 그림(돌진 · 방어막 · 잔상)이 그릴 때마다 world.pos 를 다시
       읽는다 - 그래서 world.pos 는 부를 때의 자리를 돌려줘야 몸을 따라간다 (멈춘 자리를 주면 그 자리에 남는다).

   근접 · 돌진 (cast kind 'melee' · 'dash'). 엔진이 쓰는 순간의 이동 방향(없으면 상대 쪽)으로 len 만큼 달리며 길 위를
   친다 - cast 의 len (달리는 길이) · r (몸 밖 맞는 반폭) 이 오면 쓰고, 없으면 200 · 60. 여기서는 'rush' 그림이 준비 +
   달리는 동안 몸(world.pos)을 따라가며 모양의 rush · swing 훅을 부른다 (없으면 body.js 의 GENERIC). */
import { ARENA_W, ARENA_H, BODY_R, FONT, STATUS_KR, COND_KR, STAT_KR } from './consts.js';
import {
  ARROW_DOWN, ARROW_UP, BALL, COLORS, CONFETTI, COUNTER, DEBRIS, DIZZY, DODGE, DOWN, DUST, FIZZLE, GOLD, GOLDEN, HEAL,
  HEX_PTS, HURT, INK, Ink, MOTES, MUZZLE, PLAIN, PLUSES, POOL_MAX, PUFF, Particles, SCREEN, SHINE, SHOT_R, SLEEP, SOOT,
  TAU, Trail, UP, WHITE, ZONE_R, BEAM_LEN, clamp01, colorsOf, debrisSpec, defaultCanvas, easeOut, lens, line, num, own,
  ring, rnd, seedOf, shape, spikes, tone,
} from './fx/core.js';
import { FIRES, paintZone, shapeZone } from './fx/zones.js';
import { STYLE_KEYS, hookOf, styleDef } from './fx/styles/index.js';
import { AURA } from './fx/styles/body.js';

export { POOL_MAX, Particles };

/** 이펙트 모양 키 (common/action_moves.STYLES 와 같다). 모르는 키는 orb 로 그린다. */
export const STYLES = STYLE_KEYS;

/** 표시가 찬 정도 0~1: t0 에 0, t1 에 1. 시각이 없으면 0. */
export function charge(z, now) {
  const span = z.t1 - z.t0;
  if (!(span > 0)) return now >= z.t1 ? 1 : 0;
  return clamp01((now - z.t0) / span);
}

// ---------------------------------------------------------------- 수치
const ANIM_MAX = 48;
const TEXT_MAX = 24;
const MAX_DT = 0.1;              // 탭을 오래 비웠다 돌아와도 입자가 순간이동하지 않게

const SHAKE_MAX = 16;            // 흔들림 최대 (아레나 단위). 세기(trauma 0~1)의 제곱에 비례
const SHAKE_DECAY = 1.6;         // 세기가 1초에 줄어드는 양
const HITSTOP_SLOW = 0.08;       // 맞는 순간 이펙트 시간을 이만큼으로 늦춘다 (판은 서버 것이라 그대로)
const FLASH_DECAY = 1.8;
const FLASH_PAD = 60;            // 흔들려도 가장자리가 비지 않게

const GONE_SEC = 0.15;           // 서버가 지운 탄 · 장판을 이만큼 못 보면 잊는다
const LATE_SEC = 0.15;           // 지워진 표시를 마지막으로 본 때가 t1 을 이만큼 앞뒀으면 떨어진 것으로 친다

const GATHER_SEC = 0.28;         // 날리기 준비 (0.16 + 위력/700 초) 동안 모이는 빛
const IMPACT_SEC = 0.2;
const KO_SEC = 0.8;
const KO_PULL = 0.4;             // 쓰러짐: 이만큼 줄어든 뒤 터진다
const TRAIL_LIFE = 0.26;
const DODGE_TRAIL = 0.22;

// 근접 · 돌진. cast 는 준비를 시작할 때 온다 - 몸이 빨라지는 때를 재서 달리기 시작으로 본다 (못 재면 준비 어림 뒤)
const RUSH_LEN = 200;            // cast 에 len 이 없을 때
const RUSH_R = 60;               // cast 에 r 이 없을 때
const MELEE_WIND = 0.2;          // 근접 준비 (0.14 + 위력/1000 초) 어림
const MELEE_ACT = 0.18;          // 근접으로 달리는 시간 어림
const DASH_WIND = 0.08;
const DASH_V = 1500;             // 돌진 빠르기 (u/s) - 달리는 시간 = len / 이것
const RUSH_TAIL = 0.14;          // 다 달린 뒤 그림이 사그라드는 시간
const RUSH_V = 500;              // 이보다 빠르면 (u/s) 달리기 시작한 것으로 본다
const RUSH_GAP = 8;              // 지나온 자리 점 간격
const STY_MAX = 32;              // (쪽, 기술) → 모양 키를 기억하는 수

const TEXT_LIFT = 64;            // 글씨는 몸 위 이만큼에서 시작한다
const TEXT_GAP = 30;             // 같은 쪽 글씨끼리 적어도 이만큼 띄운다
const TEXT_UP = 70;              // 처음 떠오르는 빠르기 (u/s) - 점점 느려진다
const TEXT_DRAG = 2.5;
const MERGE_SEC = 0.5;           // 같은 말이 이 안에 또 오면 하나로
const POP_K = 0.1;               // 글씨가 커졌다 줄어드는 앞부분 (수명 비율)
const FADE_K = 0.7;              // 이 뒤로 흐려진다
const CONFETTI_N = 90;

// 모양 훅 하나를 깨끗한 ctx 로 (알파 1 · 빛 혼합 · 둥근 끝) 부르고 돌려놓는다
function hooked(ctx, hook, ...args) {
  if (!hook) return;
  ctx.save();
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'lighter';
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  hook(...args);
  ctx.restore();
}

// ---------------------------------------------------------------- 근접 · 돌진 (rush)
// cast 하나 → 'rush' 그림 하나. 칸은 fx/core.js 맨 위의 'a (돌진)'.
function startRush(fx, ev, at, c, ang, mk) {
  const dash = mk === 'dash', len = ev.len > 0 ? ev.len : RUSH_LEN, r = ev.r > 0 ? ev.r : RUSH_R;
  const wind = dash ? DASH_WIND : MELEE_WIND, act = dash ? len / DASH_V : MELEE_ACT;
  const a = fx.anim('rush', ev.w, at, ang, c, ev.sty, wind + act + RUSH_TAIL);
  Object.assign(a, {
    mk, x0: at.x, y0: at.y, ux: Math.cos(ang), uy: Math.sin(ang), len, r, reach: r + (dash ? 2 : 1) * BODY_R,
    ty: ev.ty, k: ev.k, wind, act, go: null, landed: false, speed: 0, moved: 0, stage: 'wind', sk: 0, t: 0,
    trail: new Trail(24), mem: {},
  });
  a.trail.push(at.x, at.y, fx.clock, 0);
}

function rushTick(fx, a) {
  const p = fx.pos(a.side);
  if (p) {
    if (a.px !== null && fx.dt > 0) a.speed += (Math.hypot(p.x - a.px, p.y - a.py) / fx.dt - a.speed) * 0.5;
    a.px = p.x;
    a.py = p.y;
    a.x = p.x;
    a.y = p.y;
    a.moved = Math.hypot(p.x - a.x0, p.y - a.y0);
    a.trail.push(p.x, p.y, fx.clock, RUSH_GAP);
  }
  if (a.go === null && (a.age >= a.wind || (a.age > 0.03 && a.speed > RUSH_V))) {
    a.go = a.age;
    a.life = a.go + a.act + RUSH_TAIL;
    fx.burst(a.x, a.y, DUST, a.c, 0.8, a.ang + Math.PI, 1.6);   // 박차는 발밑 먼지
  }
  if (a.go === null) {
    a.stage = 'wind';
    a.sk = clamp01(a.age / a.wind);
  } else if (a.age < a.go + a.act) {
    a.stage = 'act';
    a.sk = clamp01((a.age - a.go) / a.act);
  } else {
    a.stage = 'tail';
    a.sk = clamp01((a.age - a.go - a.act) / RUSH_TAIL);
    if (!a.landed) {                            // 다 달렸다 - 제 swing 이 없는 모양은 앞에서 그 모양의 조각이 튄다
      a.landed = true;
      const def = styleDef(a.sty);
      if (!def.swing) {
        fx.burst(a.x + a.ux * a.reach * 0.6, a.y + a.uy * a.reach * 0.6, debrisSpec(def, a.ty), a.c, 0.8, a.ang, 1.6);
      }
    }
  }
  a.t = clamp01(a.age / a.life);
}

function rushDraw(fx, ctx, a) {
  hooked(ctx, hookOf(a.sty, 'rush'), fx, ctx, a);
  if (a.go === null) return;
  const t = (a.age - a.go) / (a.act + RUSH_TAIL);
  if (t >= 0 && t < 1) hooked(ctx, hookOf(a.sty, 'swing'), fx, ctx, a, t);
}

// ---------------------------------------------------------------- 움직이는 그림 (anim)
// a: {kind, side(따라갈 쪽, 없으면 그 자리), x, y, ang, c, sty, life, delay, age, k(크기), crit, seed, px, py}
// draw(fx, ctx, a, t) - t 는 0~1 진행. drawUnder/Over 가 하나마다 save/restore 로 감싼다.

// 지나온 길에 잔상 줄 + 옅은 몸 빛 (피하기 · 뛰어오르기)
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
  rush: { layer: 1, tick: rushTick, draw: rushDraw },
  trail: { layer: 1, tick: trailTick },
  // 회복 · 강화 · 방어의 몸에 두르는 그림 (body.js AURA). a.aura = 'heal' | 'buff' | 'shield', a.k = 기술 키 (칼춤의 칼)
  aura: { layer: 1, draw(fx, ctx, a, t) { AURA[a.aura](fx, ctx, a, t); } },
  shield: { layer: 1, draw(fx, ctx, a, t) {   // 막았다 - 맞는 순간 잠깐 비치는 육각 막 (방어 기술 자체는 aura)
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
/** 몸에 두르는 그림 하나 (몸을 따라간다). k 칸에 기술 키를 둔다 - aura 그림은 크기 배율로 k 를 안 쓴다. */
function aura(fx, ev, at, c, which, life) {
  const a = fx.anim('aura', ev.w, at, 0, c, ev.sty, life);
  a.aura = which;
  a.k = String(ev.k || '');
  return a;
}

const CAST = {
  proj(fx, ev, at, c) { gather(fx, ev.w, at, c, GATHER_SEC); },
  beam(fx, ev, at, c) { gather(fx, ev.w, at, c, 0.6, 1.4); },
  burst(fx, ev, at, c) {
    gather(fx, ev.w, at, c, 0.3);
    fx.wave(at.x, at.y, c.light, 80, 0.45, 4, 0);
  },
  melee(fx, ev, at, c, ang) { startRush(fx, ev, at, c, ang, 'melee'); },
  dash(fx, ev, at, c, ang) { startRush(fx, ev, at, c, ang, 'dash'); },
  leap(fx, ev, at, c, ang) {
    fx.burst(at.x, at.y, DUST, c, 1.2);
    fx.anim('trail', ev.w, at, ang, c, ev.sty, 0.5);
    fx.anim('sky', ev.w, at, ang, c, ev.sty, 0.3);
  },
  strike(fx, ev, at, c, ang) { fx.anim('sky', ev.w, at, ang, c, ev.sty, 0.45); },
  self(fx, ev, at, c) {
    aura(fx, ev, at, c, 'buff', 0.9);
    fx.burst(at.x, at.y, MOTES, c, 1, 0, TAU, 0, 34);
  },
  heal(fx, ev, at) {
    aura(fx, ev, at, HEAL, 'heal', 0.9);
    fx.burst(at.x, at.y, PLUSES, HEAL, 1, 0, TAU, 0, 34);
  },
  guard(fx, ev, at, c) { aura(fx, ev, at, c, 'shield', 0.8); },
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
  fx.burst(at.x, at.y, debrisSpec(null, ev.ty), c, k);
  fx.burst(at.x, at.y, DEBRIS.spark, SHINE, 0.6 * k);
  if (crit) fx.burst(at.x, at.y, DEBRIS.spark, GOLDEN, 1);
  // 세게 맞을수록 · 내가 맞을수록 크게 흔들리고 오래 멈춘다
  fx.kick(0.14 * k + (crit ? 0.1 : 0) + (me ? 0.12 : 0), eff > 1 || crit ? 0.085 : 0.045,
    me ? 0.14 : eff > 1 ? 0.08 : 0, me ? HURT : WHITE);
  if (eff > 1) fx.say(ev.v, at, '효과가 굉장했다!', LOOK.great);
  else if (eff < 1) fx.say(ev.v, at, '효과가 별로인 듯하다…', LOOK.weak);
  if (crit) fx.say(ev.v, at, '급소!', LOOK.crit);
  // 모양의 덧그림 - hit 에는 sty 가 없으므로 cast 때 기억한 (쪽, 기술) 의 것
  const sty = typeof ev.sty === 'string' ? ev.sty : fx.styOf(ev.w, ev.k);
  const hook = sty !== undefined ? styleDef(sty).impact : null;
  if (hook) {
    const from = fx.pos(ev.w), ang = from ? Math.atan2(at.y - from.y, at.x - from.x) : 0;
    hook(fx, at.x, at.y, Number.isFinite(ang) ? ang : 0, c,
      { why: 'hit', k: ev.k, ty: ev.ty, sty, eff, crit, s: k, r: 0, len: 0 });
  }
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
    fx.remember(ev.w, ev.k, ev.sty);
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
    this.stys = new Map();                      // '쪽:기술' → 모양 키 (hit 에는 sty 가 없다)
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
    const q = this.shotOf(p, x, y), def = styleDef(p.sty);
    ctx.save();
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'lighter';
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    def.shot(this, ctx, q);
    ctx.restore();
    if (def.trail) def.trail(this, q, this.dt);
    else this.trickle(q, hookOf(p.sty, 'emit'));
  }

  drawZone(ctx, z, now) {
    const q = this.zoneOf(z, now);
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    paintZone(this, ctx, q);
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

  // (쪽, 기술) 의 모양 키 - cast 때 적어 두고 hit 때 읽는다
  remember(side, k, sty) {
    if (typeof k !== 'string' || typeof sty !== 'string') return;
    if (this.stys.size >= STY_MAX) this.stys.clear();
    this.stys.set(side + ':' + k, sty);
  }

  styOf(side, k) {
    return this.stys.get(side + ':' + k);
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

  /** 1초에 rate 개를 뿌리려면 이번 장에 몇 개 (화면 빈도와 상관없이). */
  perSec(rate) {
    return Math.floor(rate * this.dt + Math.random());
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

  // ------------------------------------------------ 탄 · 장판 기록 (칸은 fx/core.js 맨 위)
  shotOf(p, x, y) {
    let q = p.id != null ? this.shots.get(p.id) : undefined;
    const fresh = !q;
    if (fresh) {
      q = { id: p.id, x, y, vx: 0, vy: 0, speed: 0, ux: 1, uy: 0, ang: 0, r: SHOT_R, c: PLAIN, seed: seedOf(p.id),
        born: this.clock, age: 0, at: 0, trail: new Trail(16), mem: {} };
      if (p.id != null) this.shots.set(p.id, q);
    }
    const vx = num(p.vx), vy = num(p.vy), v = Math.hypot(vx, vy);
    if (v > 1e-6) {                             // 멈춘 탄은 마지막 방향 그대로
      q.ux = vx / v;
      q.uy = vy / v;
      q.ang = Math.atan2(vy, vx);
    }
    q.x = num(x, q.x);
    q.y = num(y, q.y);
    q.vx = vx;
    q.vy = vy;
    q.speed = v;
    q.r = p.r > 0 ? p.r : SHOT_R;
    q.c = colorsOf(p.ty);
    q.k = p.k;
    q.ty = p.ty;
    q.sty = p.sty;
    q.o = p.o;
    q.foe = this.foe(p.o);
    q.age = this.clock - q.born;
    q.at = this.clock;
    q.trail.push(q.x, q.y, this.clock, 6);
    if (fresh) this.launch(q);
    return q;
  }

  zoneOf(z, now) {
    let q = z.id != null ? this.zones.get(z.id) : undefined;
    if (!q) {
      q = { id: z.id, seed: seedOf(z.id), fired: false, born: this.clock, mem: {} };
      if (z.id != null) this.zones.set(z.id, q);
    }
    q.z = z;
    q.kind = z.kind;
    q.k = z.k;
    q.ty = z.ty;
    q.sty = z.sty;
    q.o = z.o;
    q.x = num(z.x, ARENA_W / 2);
    q.y = num(z.y, ARENA_H / 2);
    q.r = z.r > 0 ? z.r : z.w > 0 ? z.w / 2 : ZONE_R;     // r 이 없으면 w (표시 지름)
    q.ang = num(z.ang);
    q.len = z.len > 0 ? z.len : z.r > 0 ? z.r : BEAM_LEN;
    q.w = z.w > 0 ? z.w : 0;
    q.t0 = z.t0;
    q.t1 = z.t1;
    q.c = colorsOf(z.ty);
    q.foe = this.foe(z.o);
    q.now = now;
    q.u = charge(z, now);
    q.since = num(now - z.t1, -1);
    q.age = this.clock - q.born;
    q.at = this.clock;
    shapeZone(q);
    return q;
  }

  // 탄이 처음 보인 순간 - 입 앞 번쩍 + 앞으로 튀는 불티 (+ 모양의 launch)
  launch(q) {
    this.spawn('core', q.x, q.y, 0, 0, 0.14, q.r * 1.6, q.c.light).size1 = q.r * 2.6;
    this.burst(q.x, q.y, MUZZLE, q.c, 1, q.ang, 1.2);
    const hook = styleDef(q.sty).launch;
    if (hook) hook(this, q);
  }

  // 날아가는 탄이 흘리는 꼬리 입자. 그리는 김에 흘리고, 수는 update 의 dt 로 맞춘다 (화면 빈도와 상관없이 1초에 rate 개)
  trickle(q, spec) {
    const n = this.perSec(spec.rate);
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
      if (a.age >= a.delay + a.life) continue;   // tick 이 수명을 줄였을 수 있다 (돌진)
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
