/* 그리기: 캔버스 하나가 창을 채우고, 16:9 아레나(1600×900 단위)를 가운데에 맞춘다 (남는 곳은 어둡게).
   ctx.setTransform 하나로 배율 · 기기 픽셀 비율 · 화면 흔들림을 건다 - 그 밖은 전부 아레나 단위다.

   순서: 바닥 → 장판(fx) → 그림자 → 몸 아래 입자(fx) → 몸(아래에 선 쪽이 앞) → 탄(fx) → 몸 위 입자(fx) → 머리 위 체력.
   몸 가운데가 서버의 (x, y) 다 - 맞는 자리(BODY_R)와 탄 · 장판이 같은 점을 쓴다.

   손맛 (소리 없이 그림만).
     * 기술을 쓰면 꼴에 맞는 몸짓 (sprites.attackPose - Attack · Shoot · Charge 도트, 없으면 procPose). 쓰는 쪽을 본다.
       내 것은 누르자마자 (predict) 준비 몸짓을 먼저 시작하고, 서버의 cast 가 오면 그대로 이어 간다.
     * 맞으면: 두 장쯤 하얗게 → 잠깐 붉게, 맞은 쪽으로 눌렸다 튀어 오른다. 그리고 멈춘다 - fx.hitstop 하나를 같이 본다:
       멈춘 동안 두 몸의 도트 시간(aclock)과 자리(feel.Hold)를 잡아 두고, 풀리면 80ms 동안 진짜 자리로 미끄러진다.
     * 화면 흔들림 · 다가감은 fx 의 것 (shake · zoom). */
import { ARENA_W, ARENA_H, BODY_R, FONT, TYPE_COLOR, STATUS_KR, STATUS_COLOR, UI } from './consts.js';
import { animFor, attackPose, procPose } from './sprites.js';
import { hpColor } from './hud.js';
import { Hold, isChip } from './feel.js';

/** 창 크기에서 아레나 배율과 가운데 자리. */
export function fitArena(cw, ch) {
  const s = Math.min(cw / ARENA_W, ch / ARENA_H);
  return { s, ox: (cw - ARENA_W * s) / 2, oy: (ch - ARENA_H * s) / 2 };
}

// 같은 바닥이 늘 같게 - 정해진 씨앗의 난수
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** 풀 마당 바닥. 아레나 단위로 그린다 (부르는 쪽이 배율을 건다). */
function paintFloor(g) {
  const rnd = rng(20261118);
  g.fillStyle = '#2f5239';
  g.fillRect(0, 0, ARENA_W, ARENA_H);
  for (let x = 0; x < ARENA_W; x += 100) {         // 깎은 잔디 줄무늬
    if ((x / 100) % 2) {
      g.fillStyle = 'rgba(255,255,255,0.025)';
      g.fillRect(x, 0, 100, ARENA_H);
    }
  }
  for (let i = 0; i < 2600; i += 1) {               // 풀잎
    const x = rnd() * ARENA_W;
    const y = rnd() * ARENA_H;
    const h = 4 + rnd() * 7;
    g.strokeStyle = rnd() < 0.5 ? 'rgba(120,190,110,0.16)' : 'rgba(10,30,18,0.22)';
    g.lineWidth = 1.6;
    g.beginPath();
    g.moveTo(x, y);
    g.lineTo(x + (rnd() - 0.5) * 4, y - h);
    g.stroke();
  }
  for (let i = 0; i < 70; i += 1) {                 // 작은 꽃
    g.fillStyle = rnd() < 0.6 ? 'rgba(255,255,240,0.35)' : 'rgba(255,214,90,0.35)';
    g.beginPath();
    g.arc(rnd() * ARENA_W, rnd() * ARENA_H, 2 + rnd() * 1.5, 0, Math.PI * 2);
    g.fill();
  }
  g.strokeStyle = 'rgba(255,255,255,0.09)';         // 마당 금
  g.lineWidth = 3;
  g.strokeRect(40, 40, ARENA_W - 80, ARENA_H - 80);
  g.beginPath();
  g.moveTo(ARENA_W / 2, 40);
  g.lineTo(ARENA_W / 2, ARENA_H - 40);
  g.stroke();
  g.beginPath();
  g.arc(ARENA_W / 2, ARENA_H / 2, 110, 0, Math.PI * 2);
  g.stroke();
  const v = g.createRadialGradient(ARENA_W / 2, ARENA_H / 2, ARENA_H * 0.35, ARENA_W / 2, ARENA_H / 2, ARENA_W * 0.62);
  v.addColorStop(0, 'rgba(6,10,16,0)');
  v.addColorStop(1, 'rgba(6,10,16,0.55)');          // 가장자리를 어둡게
  g.fillStyle = v;
  g.fillRect(0, 0, ARENA_W, ARENA_H);
  g.strokeStyle = 'rgba(0,0,0,0.5)';                // 벽
  g.lineWidth = 8;
  g.strokeRect(4, 4, ARENA_W - 8, ARENA_H - 8);
}

const HURT_SEC = 0.35;
const SPAWN_SEC = 0.3;
const FADE_SEC = 0.6;        // 쓰러지는 동작이 끝난 뒤 사라지기까지
const KO_FLASH_SEC = 0.4;    // 쓰러지는 도트가 없는 종의 번쩍임
const MOVING = 25;           // 이보다 빠르면(u/s) 걷는 그림
const OVERHEAD_MIN_Y = 20;   // 머리 위 막대의 가장 높은 자리 (이름 글씨가 그 위에 온다)

// 맞음
const WHITE_SEC = 0.034;     // 하얗게 (60Hz 두 장)
const RED_SEC = 0.2;         // 그 뒤 붉게 사그라든다
const SQUASH = 0.2;          // 맞은 쪽으로 눌리는 정도 (세기 1 에서)
const SQUASH_DECAY = 0.07;   // 튀어 오르는 시간 상수 (초, 도트 시간)
const SQUASH_FREQ = 38;      // 출렁임 (라디안/초)
const SQUASH_SEC = 0.32;

// 기술 몸짓
const ATTACK_PLAY = 0.45;    // Attack · Shoot 한 바퀴를 이보다 길게 끌지 않는다 (빠르게 돌린다)
const CAST_GRACE = 0.12;     // cast 이벤트가 온 뒤 모습이 아직 준비 전이어도 이만큼은 몸짓을 지킨다 (보간이 반 틱 늦다)
export const PREDICT_SEC = 0.25;    // 누르자마자 시작한 준비 몸짓 - 이 안에 서버가 안 받으면 사그라든다
const PREDICT_WIND = 0.2;    // 예측 몸짓의 준비 진행을 이만큼에 맞춰 채운다 (서버 sp 를 모를 때)
const PREDICT_FADE = 0.12;
const CAST_STATES = new Set(['wind', 'act', 'guard']);

const frozen = (f) => f.st === 'frz' || f.s === 'frz';
const seconds = (durs) => durs.reduce((p, q) => p + q, 0) / 60;
const clamp01 = (v) => (v > 0 ? (v < 1 ? v : 1) : 0);

/** 방향 0~7 → 라디안 (0 아래 · 2 오른쪽 · 4 위 · 6 왼쪽, y 는 아래로). */
export function dirAngle(d) {
  return Math.PI / 2 - (d >= 0 ? d : 0) * Math.PI / 4;
}

/** 맞아 눌린 정도 (0 이면 그대로). tau 맞은 뒤 도트 시간 · k 세기. 처음이 가장 눌리고 출렁이며 돌아온다. */
export function squashAt(tau, k) {
  if (!(tau >= 0) || tau > SQUASH_SEC || !(k > 0)) return 0;
  return SQUASH * k * Math.exp(-tau / SQUASH_DECAY) * Math.cos(tau * SQUASH_FREQ);
}

/** 맞은 몸을 덮는 색: 두 장 하얗게 → 붉게 사그라든다 (지역 초). 없으면 null. */
export function hitWash(since) {
  if (!(since >= 0)) return null;
  if (since < WHITE_SEC) return 'rgba(255,255,255,0.95)';
  const u = (since - WHITE_SEC) / RED_SEC;
  return u < 1 ? 'rgba(255,64,64,' + (0.55 * (1 - u)).toFixed(3) + ')' : null;
}

/** 한 쪽 몸의 그리기 상태 (동작 · 시작 시각 · 바라보는 쪽 · 맞은 때 · 기술 몸짓). now 는 지역 초, ac 는 도트 시간
    (멈춤 동안 서는 시계). */
export class Body {
  constructor() {
    this.i = null;
    this.anim = null;
    this.since = 0;
    this.prev = null;
    this.speed = 0;
    this.right = false;
    this.hurtAt = -Infinity;
    this.koAt = null;
    this.spawnAt = -Infinity;
    this.frozenT = 0;
    this.hit = null;             // {at (지역 초), ac (도트 시간), ang, k}
    this.act = null;             // 기술 몸짓 {m, kind, ang, at (도트 시간), born (지역 초), stage, u, pre, until, fadeAt}
    this.hold = new Hold();
  }

  update(f, x, y, now, dt) {
    if (f.i !== this.i) {
      this.i = f.i;
      this.spawnAt = now;
      this.prev = null;
      this.speed = 0;
      this.act = null;
      this.hold.reset();
    }
    if (this.prev && dt > 0) {
      const v = Math.hypot(x - this.prev.x, y - this.prev.y) / dt;
      this.speed += (v - this.speed) * Math.min(1, dt * 12);
    }
    this.prev = { x, y };
    if (f.d >= 1 && f.d <= 3) this.right = true;
    if (f.d >= 5 && f.d <= 7) this.right = false;
    if (f.st === 'ko') this.koAt ??= now;
    else this.koAt = null;
  }

  /** 서버의 cast (이 쪽). 누르자마자 시작한 같은 칸 몸짓이 있으면 이어 간다 (처음부터 다시 하지 않는다). */
  cast(ev, now, ac) {
    const a = this.act;
    const ang = Number.isFinite(ev.ang) ? ev.ang : a ? a.ang : 0;
    if (a && a.pre && a.m === ev.m && !a.fadeAt) {
      Object.assign(a, { pre: false, kind: ev.kind || a.kind, ang, born: now });
      return;
    }
    this.act = { m: ev.m, kind: ev.kind || 'proj', ang, at: ac, born: now, stage: 'wind', u: 0, pre: false, until: 0, fadeAt: null };
  }

  /** 누르자마자 (내 것). 서버가 PREDICT_SEC 안에 cast 를 보내면 cast() 가 이어받는다. */
  predict(m, kind, ang, now, ac) {
    this.act = { m, kind, ang, at: ac, born: now, stage: 'wind', u: 0, pre: true, until: now + PREDICT_SEC, fadeAt: null };
  }

  /** 기술 몸짓의 단계를 모습(F)에 맞춘다. kindOf(칸) → 꼴 | null (내 기술만 안다). */
  track(f, now, ac, kindOf) {
    const a = this.act;
    if (CAST_STATES.has(f.st) && f.sm >= 0) {
      if (!a || a.m !== f.sm || a.fadeAt) {            // 이벤트 없이 (중간에 들어왔다) - 모습에서 만든다
        this.act = { m: f.sm, kind: kindOf(f.sm) || 'proj', ang: dirAngle(f.d), at: ac, born: now, pre: false, until: 0, fadeAt: null };
      }
      const b = this.act;
      b.pre = false;
      b.stunned = false;
      b.stage = f.st === 'wind' ? 'wind' : 'act';
      b.u = f.sp;
      return;
    }
    if (!a) return;
    if ((f.st === 'stun' || f.hs) && f.sm >= 0 && f.sm === a.m && !a.pre) {   // 맞아 경직 - 하던 기술은 이어진다 (그동안은 아파하는 모습)
      a.stunned = true;
      return;
    }
    if (a.pre) {
      if (a.fadeAt === null && now > a.until) a.fadeAt = now;            // 서버가 안 받았다 - 사그라든다
      if (a.fadeAt !== null && now - a.fadeAt > PREDICT_FADE) this.act = null;
      else a.u = clamp01((now - a.born) / PREDICT_WIND);
      return;
    }
    if (now - a.born < CAST_GRACE && (f.st === 'idle' || f.st === 'walk')) return;   // 보간이 아직 준비 전 모습
    if (f.st === 'rec') a.stage = 'rec';
    else this.act = null;
  }

  /** 이번 장에 쓸 동작과 그 동작의 시각 + 손으로 만든 몸짓 (도트가 없을 때). */
  pose(look, f, now, ac) {
    const hurt = now - this.hurtAt < HURT_SEC || !!f.hs;            // F.hs - 맞아 잠깐 휘청 (엔진이 줄 때)
    const a = this.act;
    const ap = a && !a.stunned && f.st !== 'ko' ? attackPose(look.have, a.kind, a.stage === 'rec' ? null : a.stage) : null;
    let anim = null;
    let loop = true;
    let rate = 1;
    let proc = null;
    if (ap && ap.anim) {
      anim = ap.anim;
      loop = ap.loop;
    } else if (ap) {
      const fade = a.fadeAt !== null ? 1 - clamp01((now - a.fadeAt) / PREDICT_FADE) : 1;
      proc = { ...procPose(ap.proc, a.stage, a.u, ac), fade, ang: a.ang };
    }
    // 회복(rec) 동안은 치던 도트를 끝까지 (끊으면 휘두르다 만다)
    if (!anim && a && a.stage === 'rec' && (this.anim === 'Attack' || this.anim === 'Shoot') && look.sheets[this.anim]) {
      const sh = look.sheets[this.anim];
      if ((ac - this.since) * playRate(sh) < seconds(sh.durs)) anim = this.anim;
      loop = false;
    }
    if (anim) {
      if (anim !== 'Charge') {
        loop = false;
        rate = playRate(look.sheets[anim]);
      }
    } else {
      anim = animFor(look.have, f.st, this.speed > MOVING, hurt);
    }
    if (anim !== this.anim) {
      this.anim = anim;
      this.since = ac;
    }
    if (f.st === 'ko') return { anim, t: now - this.koAt, loop: false, proc: null };
    if (!frozen(f)) this.frozenT = (ac - this.since) * rate;           // 얼면 그 장에서 멈춘다
    const fast = f.st === 'dodge' ? 2 : 1;
    return { anim, t: this.frozenT * fast, loop, proc };
  }
}

/** Attack · Shoot 을 돌리는 빠르기 - 한 바퀴가 ATTACK_PLAY 보다 길면 그만큼 빨리. */
function playRate(sh) {
  if (!sh) return 1;
  return Math.max(1, seconds(sh.durs) / ATTACK_PLAY);
}

function ellipse(ctx, x, y, rx, ry, fill) {
  ctx.beginPath();
  ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
  ctx.fillStyle = fill;
  ctx.fill();
}

export class Renderer {
  constructor(canvas, bank, fx) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.bank = bank;
    this.fx = fx;
    this.bodies = { a: new Body(), b: new Body() };
    this.floor = null;
    this.size = null;
    this.fit = fitArena(1, 1);
    this.ac = 0;                 // 도트 시간 (초) - 멈춤(fx.hitstop) 동안 선다
    this.drawnAt = {};           // 쪽 → 이번 장에 그린 몸 가운데 (멈춤 · 미끄러짐 뒤) - fx 가 따라간다
  }

  /** 창 크기 · 기기 픽셀 비율이 바뀌었으면 캔버스와 바닥을 다시 만든다. */
  resize(win) {
    const dpr = win.devicePixelRatio || 1;
    const w = win.innerWidth;
    const h = win.innerHeight;
    const key = w + 'x' + h + '@' + dpr;
    if (key === this.size) return;
    this.size = key;
    this.dpr = dpr;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    this.fit = fitArena(w, h);
    const k = this.fit.s * dpr;
    this.floor = document.createElement('canvas');
    this.floor.width = Math.max(1, Math.round(ARENA_W * k));
    this.floor.height = Math.max(1, Math.round(ARENA_H * k));
    const g = this.floor.getContext('2d');
    g.scale(k, k);
    paintFloor(g);
  }

  /** 아레나 단위로 그리게 변환을 건다 (흔들림은 아레나 단위). zoom {k, x, y} 면 (x, y) 쪽으로 k 배 다가간다. */
  toArena(shake = { x: 0, y: 0 }, zoom = null) {
    const { s, ox, oy } = this.fit;
    const z = zoom && zoom.k > 1 ? zoom : null;
    const zk = z ? z.k : 1;
    const k = s * this.dpr * zk;
    const tx = ox + shake.x * s + (z ? z.x * s * (1 - zk) : 0);
    const ty = oy + shake.y * s + (z ? z.y * s * (1 - zk) : 0);
    this.ctx.setTransform(k, 0, 0, k, tx * this.dpr, ty * this.dpr);
    this.ctx.imageSmoothingEnabled = false;
  }

  /** 그 쪽 몸을 이번 장에 그린 자리 (멈춤 · 미끄러짐 뒤). 아직 안 그렸으면 null. */
  posOf(side) {
    return this.drawnAt[side] || null;
  }

  /** 서버 이벤트 (그릴 때가 된 것). 맞으면 번쩍 · 눌림, cast 면 몸짓. */
  event(ev, now) {
    const body = this.bodies[ev.e === 'hit' ? ev.v : ev.w];
    if (!body) return;
    if (ev.e === 'cast') {
      body.cast(ev, now, this.ac);
      return;
    }
    if (ev.e !== 'hit') return;
    body.hurtAt = now;
    if (!(ev.eff > 0) && Number.isFinite(ev.eff)) return;             // 막혔다
    const chip = isChip(ev);
    const from = this.drawnAt[ev.w];
    const at = this.drawnAt[ev.v] || (Number.isFinite(ev.x) ? { x: ev.x, y: ev.y } : null);
    const ang = !chip && from && at && (from.x !== at.x || from.y !== at.y) ? Math.atan2(at.y - from.y, at.x - from.x) : Math.PI / 2;
    const pct = Number.isFinite(ev.pct) ? ev.pct : 8;
    const k = chip ? 0.25 : Math.min(1.25, 0.4 + pct / 35 + (ev.eff > 1 || ev.crit ? 0.2 : 0));
    body.hit = { at: now, ac: this.ac, ang, k, chip };
  }

  /** 누르자마자 (내 것) - 준비 몸짓을 먼저. 서버의 cast 가 오면 이어 가고, 안 오면 사그라든다. */
  predict(side, m, kind, ang, now) {
    const body = this.bodies[side];
    if (body) body.predict(m, kind, ang, now, this.ac);
  }

  /** w = {now(지역 초), dt, rt(그릴 판 시각), bodies: [{side, f, mon, x, y, mine, kindOf?}], p(탄), z(장판)} */
  draw(w) {
    const ctx = this.ctx;
    const stopped = this.fx.hitstop.active;
    if (!stopped) this.ac += w.dt;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = UI.ink;
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    this.toArena(this.fx.shake(), this.fx.zoom());
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, ARENA_W, ARENA_H);
    ctx.clip();
    ctx.drawImage(this.floor, 0, 0, ARENA_W, ARENA_H);
    for (const z of w.z) this.fx.drawZone(ctx, z, w.rt);
    const bodies = w.bodies.map((b) => this.prepare(b, w.now, w.dt, stopped)).sort((p, q) => p.y - q.y);
    this.drawnAt = Object.fromEntries(bodies.map((b) => [b.side, { x: b.x, y: b.y }]));
    for (const b of bodies) this.shadow(b);
    this.fx.drawUnder(ctx);
    for (const b of bodies) this.body(b, w.now);
    for (const p of w.p) this.fx.drawProjectile(ctx, p, p.x, p.y);
    this.fx.drawOver(ctx);
    for (const b of bodies) this.overhead(b, w.now);
    ctx.restore();
  }

  prepare(b, now, dt, stopped) {
    const body = this.bodies[b.side];
    body.update(b.f, b.x, b.y, now, dt);
    body.track(b.f, now, this.ac, b.kindOf || (() => null));
    const p = body.hold.at(b.x, b.y, now, stopped);                  // 멈춘 동안은 그 자리, 풀리면 미끄러져 따라간다
    const look = this.bank.look(b.mon);
    const k = look ? look.geo.scale : 1;
    return { ...b, x: p.x, y: p.y, body, look, half: look ? look.geo.h * k / 2 : BODY_R, width: look ? look.geo.w * k : BODY_R * 2 };
  }

  /** 발밑 그림자 (부드러운 타원) + 내 편 · 상대 고리. */
  shadow(b) {
    const ctx = this.ctx;
    if (b.f.st === 'ko') return;
    const fy = b.y + b.half - 2;
    const rx = Math.max(18, Math.min(60, b.width * 0.42));
    const g = ctx.createRadialGradient(b.x, fy, 0, b.x, fy, rx);
    g.addColorStop(0, 'rgba(0,0,0,0.42)');
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.save();
    ctx.translate(b.x, fy);
    ctx.scale(1, 0.36);
    ctx.translate(-b.x, -fy);
    ellipse(ctx, b.x, fy, rx, rx, g);
    ctx.lineWidth = 3;
    ctx.strokeStyle = b.mine ? 'rgba(95,217,122,0.55)' : 'rgba(255,107,107,0.5)';
    ctx.beginPath();
    ctx.arc(b.x, fy, rx + 4, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  body(b, now) {
    const { f, body, look } = b;
    if (f.st === 'hide') return;                                       // 공중 · 땅속
    let alpha = 1;
    let k = 1;
    let wash = null;
    const spawn = (now - body.spawnAt) / SPAWN_SEC;
    if (spawn < 1) {
      k = 0.4 + 0.6 * spawn;
      wash = 'rgba(255,255,255,' + (0.9 * (1 - spawn)).toFixed(3) + ')';
    }
    if (f.st === 'swap') {
      k = 1 - 0.6 * f.sp;
      alpha = 1 - f.sp;
      wash = 'rgba(255,255,255,0.7)';
    }
    if (f.inv && Math.floor(now * 10) % 2) alpha *= 0.45;              // 무적 깜박임
    const hit = body.hit;
    const since = hit ? now - hit.at : Infinity;
    // 두 장 하얗게 → 붉게. 저절로 깎이는 것(독 · 반동)은 하얗게는 안 하고 붉게만
    const struck = hit && !(hit.chip && since < WHITE_SEC) ? hitWash(since) : null;
    if (struck) wash = struck;
    else if (frozen(f)) wash = 'rgba(150,220,255,0.5)';
    if (!look) {
      this.placeholder(b, alpha * k);
      return;
    }
    const pose = body.pose(look, f, now, this.ac);
    let x = b.x;
    let y = b.y;
    const hurt = now - body.hurtAt;
    if (hurt < HURT_SEC && !look.have.has('Hurt')) x += Math.sin(hurt * 70) * 3;   // 아파하는 도트가 없는 종: 흔들림
    const warps = [];
    if (hit) {                                                         // 맞은 쪽으로 눌렸다 튀어 오른다 (도트 시간 - 멈춘 동안 눌린 채)
      const q = squashAt(this.ac - hit.ac, hit.k);
      if (q) warps.push({ ang: hit.ang, a: 1 - q, c: 1 + q * 0.6 });
    }
    if (pose.proc) {                                                   // 도트가 없는 몸짓: 겨눈 쪽으로 내밀고 늘인다
      const p = pose.proc;
      const w = p.fade;
      x += Math.cos(p.ang) * p.push * w + (p.shake ? Math.sin(this.ac * 90) * p.shake * w : 0);
      y += Math.sin(p.ang) * p.push * w;
      warps.push({ ang: p.ang, a: 1 + (p.along - 1) * w, c: 1 + (p.across - 1) * w });
    }
    if (f.st === 'ko') {
      const faint = look.have.has('Faint');
      const len = faint ? seconds(look.sheets.Faint.durs) : KO_FLASH_SEC;
      if (!faint) {                                                    // 쓰러지는 도트가 없는 종: 번쩍이며 흔들린다
        wash = pose.t < len ? 'rgba(255,255,255,0.6)' : null;
        x += Math.sin(pose.t * 60) * 4 * Math.max(0, 1 - pose.t / len);
      }
      alpha *= Math.max(0, 1 - (pose.t - len) / FADE_SEC);
      if (alpha <= 0) return;
    }
    this.bank.draw(this.ctx, look, {
      x, y, d: f.d, anim: pose.anim, t: pose.t, loop: pose.loop, right: body.right, alpha, k, wash, warps,
    });
    if (f.s === 'slp' || f.st === 'sleep') this.zzz(b, now);
    if ((f.c || []).includes('cnf')) this.dizzy(b, now);
  }

  /** 도트를 아직 못 받았거나 끝내 못 받은 종 - 타입 색 공. 멈추지 않고 싸울 수 있게. */
  placeholder(b, alpha) {
    const ctx = this.ctx;
    const color = (b.mon && TYPE_COLOR[(b.mon.types || [])[0]]) || UI.dim;
    ctx.save();
    ctx.globalAlpha *= alpha;
    ellipse(ctx, b.x, b.y, BODY_R, BODY_R, color);
    ctx.lineWidth = 3;
    ctx.strokeStyle = 'rgba(0,0,0,0.45)';
    ctx.stroke();
    ctx.restore();
  }

  zzz(b, now) {
    const ctx = this.ctx;
    ctx.save();
    ctx.font = '800 16px ' + FONT;
    ctx.textAlign = 'center';
    for (let j = 0; j < 3; j += 1) {
      const t = (now * 0.8 + j / 3) % 1;
      ctx.globalAlpha = Math.sin(t * Math.PI);
      ctx.fillStyle = '#dfe6ff';
      ctx.fillText('z', b.x + 14 + t * 16, b.y - b.half - t * 26);
    }
    ctx.restore();
  }

  dizzy(b, now) {
    const ctx = this.ctx;
    for (let j = 0; j < 3; j += 1) {
      const a = now * 4 + j * Math.PI * 2 / 3;
      ellipse(ctx, b.x + Math.cos(a) * 18, b.y - b.half - 6 + Math.sin(a) * 5, 3.5, 3.5, '#ffe680');
    }
  }

  /** 머리 위: 이름 · 체력 막대 · 상태이상. */
  overhead(b, now) {
    const { f, body } = b;
    if (f.st === 'ko' || f.st === 'hide' || now - body.spawnAt < SPAWN_SEC) return;
    const ctx = this.ctx;
    const w = 74;
    const top = Math.max(OVERHEAD_MIN_Y, b.y - b.half - 26);     // 위 벽에 붙어도 아레나 안에
    const x = b.x - w / 2;
    ctx.save();
    ctx.font = '700 13px ' + FONT;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.lineWidth = 3;
    ctx.strokeStyle = 'rgba(8,10,16,0.8)';
    ctx.strokeText(b.mon ? b.mon.kr : '', b.x, top - 2);
    ctx.fillStyle = b.mine ? '#d9ffe2' : '#ffe0e0';
    ctx.fillText(b.mon ? b.mon.kr : '', b.x, top - 2);
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(x - 1, top - 1, w + 2, 8);
    const r = Math.max(0, Math.min(1, f.hpr / 1000));
    ctx.fillStyle = hpColor(r);
    ctx.fillRect(x, top, w * r, 6);
    if (f.s) {
      ctx.font = '700 11px ' + FONT;
      ctx.textBaseline = 'middle';
      const s = STATUS_KR[f.s] || f.s;
      const tw = ctx.measureText(s).width + 8;
      ctx.fillStyle = STATUS_COLOR[f.s] || UI.dim;
      ctx.fillRect(x + w + 4, top - 4, tw, 14);
      ctx.fillStyle = '#10131c';
      ctx.fillText(s, x + w + 4 + tw / 2, top + 3);
    }
    ctx.restore();
  }
}
