/* 그리기: 캔버스 하나가 창을 채우고, 16:9 아레나(1600×900 단위)를 가운데에 맞춘다 (남는 곳은 어둡게).
   ctx.setTransform 하나로 배율 · 기기 픽셀 비율 · 화면 흔들림을 건다 - 그 밖은 전부 아레나 단위다.

   순서: 바닥 → 장판(fx) → 그림자 → 몸 아래 입자(fx) → 몸(아래에 선 쪽이 앞) → 탄(fx) → 몸 위 입자(fx) → 머리 위 체력.
   몸 가운데가 서버의 (x, y) 다 - 맞는 자리(BODY_R)와 탄 · 장판이 같은 점을 쓴다. */
import { ARENA_W, ARENA_H, BODY_R, FONT, TYPE_COLOR, STATUS_KR, STATUS_COLOR, UI } from './consts.js';
import { animFor } from './sprites.js';
import { hpColor } from './hud.js';

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
const FLASH_SEC = 0.12;
const SPAWN_SEC = 0.3;
const FADE_SEC = 0.6;        // 쓰러지는 동작이 끝난 뒤 사라지기까지
const KO_FLASH_SEC = 0.4;    // 쓰러지는 도트가 없는 종의 번쩍임
const MOVING = 25;           // 이보다 빠르면(u/s) 걷는 그림
const OVERHEAD_MIN_Y = 20;   // 머리 위 막대의 가장 높은 자리 (이름 글씨가 그 위에 온다)

const frozen = (f) => f.st === 'frz' || f.s === 'frz';
const seconds = (durs) => durs.reduce((p, q) => p + q, 0) / 60;

/** 한 쪽 몸의 그리기 상태 (동작 · 시작 시각 · 바라보는 쪽 · 맞은 때). 시각은 지역 초. */
class Body {
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
  }

  update(f, x, y, now, dt) {
    if (f.i !== this.i) {
      this.i = f.i;
      this.spawnAt = now;
      this.prev = null;
      this.speed = 0;
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

  /** 이번 장에 쓸 동작과 그 동작의 시각. */
  pose(look, f, now) {
    const hurt = now - this.hurtAt < HURT_SEC;
    const anim = animFor(look.have, f.st, this.speed > MOVING, hurt);
    if (anim !== this.anim) {
      this.anim = anim;
      this.since = now;
    }
    if (f.st === 'ko') return { anim, t: now - this.koAt, loop: false };
    if (!frozen(f)) this.frozenT = now - this.since;                // 얼면 그 장에서 멈춘다
    const fast = f.st === 'dodge' ? 2 : 1;
    return { anim, t: this.frozenT * fast, loop: true };
  }
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

  /** 아레나 단위로 그리게 변환을 건다 (흔들림은 아레나 단위). */
  toArena(shake = { x: 0, y: 0 }) {
    const { s, ox, oy } = this.fit;
    const k = s * this.dpr;
    this.ctx.setTransform(k, 0, 0, k, (ox + shake.x * s) * this.dpr, (oy + shake.y * s) * this.dpr);
    this.ctx.imageSmoothingEnabled = false;
  }

  /** 맞은 쪽 몸을 아파하게. */
  event(ev, now) {
    if (ev.e === 'hit' && this.bodies[ev.v]) this.bodies[ev.v].hurtAt = now;
  }

  /** w = {now(지역 초), dt, rt(그릴 판 시각), bodies: [{side, f, mon, x, y, mine}], p(탄), z(장판)} */
  draw(w) {
    const ctx = this.ctx;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = UI.ink;
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    this.toArena(this.fx.shake());
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, ARENA_W, ARENA_H);
    ctx.clip();
    ctx.drawImage(this.floor, 0, 0, ARENA_W, ARENA_H);
    for (const z of w.z) this.fx.drawZone(ctx, z, w.rt);
    const bodies = w.bodies.map((b) => this.prepare(b, w.now, w.dt)).sort((p, q) => p.y - q.y);
    for (const b of bodies) this.shadow(b);
    this.fx.drawUnder(ctx);
    for (const b of bodies) this.body(b, w.now);
    for (const p of w.p) this.fx.drawProjectile(ctx, p, p.x, p.y);
    this.fx.drawOver(ctx);
    for (const b of bodies) this.overhead(b, w.now);
    ctx.restore();
  }

  prepare(b, now, dt) {
    const body = this.bodies[b.side];
    body.update(b.f, b.x, b.y, now, dt);
    const look = this.bank.look(b.mon);
    const k = look ? look.geo.scale : 1;
    return { ...b, body, look, half: look ? look.geo.h * k / 2 : BODY_R, width: look ? look.geo.w * k : BODY_R * 2 };
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
    const hurt = now - body.hurtAt;
    if (hurt < FLASH_SEC) wash = 'rgba(255,255,255,0.85)';
    else if (frozen(f)) wash = 'rgba(150,220,255,0.5)';
    if (!look) {
      this.placeholder(b, alpha * k);
      return;
    }
    const pose = body.pose(look, f, now);
    let x = b.x;
    if (hurt < HURT_SEC && !look.have.has('Hurt')) x += Math.sin(hurt * 70) * 3;   // 아파하는 도트가 없는 종: 흔들림
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
    this.bank.draw(this.ctx, look, { x, y: b.y, d: f.d, anim: pose.anim, t: pose.t, loop: pose.loop, right: body.right, alpha, k, wash });
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
