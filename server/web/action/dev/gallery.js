/* 이펙트 갤러리 - 모양 키마다 가짜 판을 끝없이 돌려 이펙트를 본다 (서버 · 네트워크 없이).

     dev/fx-gallery.html?style=wind&type=FLYING&slow=0.25&mode=rush

     style   그 모양만 크게 (없으면 25개 전부 칸칸이 - 칸을 누르면 그 모양만)
     type    색을 고르는 기술 타입 (없으면 그 모양의 흔한 타입)
     slow    시간 배율 (0.25 = 4배 느리게)
     mode    proj · cone · ring · beam · tele · haz · rush · impact · all (기본 all: 차례로 돈다)
     at      그 판 시각(초)까지 1/60초씩 돌리고 멈춘다 - 같은 장면을 다시 보거나 그림을 견줄 때
     zoom    (style 하나일 때만) 확대 배율 - cx · cy (판 단위, 기본 가운데) 를 화면 가운데에 둔다. 스크린샷으로 자세히 볼 때

   키: Space 멈춤 · 다시, → (또는 .) 멈춘 채 1/60초 앞으로.

   칸마다 Fx 하나와 가짜 판(Sim) 하나. 판은 게임처럼 cast → 탄 · 장판(t0 → t1) · 근접 · 돌진(len · r) → hit(eff · crit)
   이벤트를 내고, 그리는 차례도 render.js 와 같다 (바닥 → 장판 → 그림자 → 몸 아래 → 몸 → 탄 → 몸 위). */
import { Fx, STYLES } from '../js/fx.js';
import { BODY_R, TYPE_FX } from '../js/consts.js';
import { checkFamilies } from '../js/fx/styles/index.js';

// ---------------------------------------------------------------- 주소
const Q = new URLSearchParams(location.search);
const MODES = ['proj', 'cone', 'ring', 'beam', 'tele', 'haz', 'rush', 'impact'];
const MODE = MODES.includes(Q.get('mode')) ? Q.get('mode') : 'all';
const SLOW = Math.min(4, Math.max(0.02, Number(Q.get('slow')) || 1));
const ONE = Q.get('style');
const TYPE = Object.prototype.hasOwnProperty.call(TYPE_FX, Q.get('type')) ? Q.get('type') : null;
const AT = Math.min(120, Math.max(0, Number(Q.get('at')) || 0));
const ZOOM = ONE ? Math.min(8, Math.max(1, Number(Q.get('zoom')) || 1)) : 1;
const num = (v, d) => (v !== null && v !== '' && Number.isFinite(Number(v)) ? Number(v) : d);
const STEP = 1 / 60;

// 모양마다 흔한 타입 (common/action_moves.TYPE_STYLE 를 거꾸로 + 몸짓 모양)
const NATURAL = {
  orb: 'NORMAL', flame: 'FIRE', jet: 'WATER', zap: 'ELECTRIC', leaf: 'GRASS', shard: 'ICE', psy: 'PSYCHIC',
  rock: 'ROCK', ghost: 'GHOST', dark: 'DARK', fairy: 'FAIRY', poison: 'POISON', wind: 'FLYING', sound: 'NORMAL',
  punch: 'FIGHTING', slash: 'NORMAL', bite: 'DARK', beam: 'NORMAL', wave: 'WATER', quake: 'GROUND', heal: 'NORMAL',
  buff: 'NORMAL', shield: 'NORMAL', powder: 'GRASS', web: 'BUG',
};

// ---------------------------------------------------------------- 가짜 판
const W = 1000;                  // 칸 하나의 판 (아레나 단위) - 게임 아레나(1600×900)의 한 조각
const H = 560;
const HOME = { a: { x: 250, y: 300 }, b: { x: 730, y: 270 } };
const SCENE_SEC = { proj: 2.6, cone: 2.2, ring: 2.0, beam: 2.4, tele: 2.4, haz: 2.8, rush: 3.4, impact: 2.8 };
const SHOT_V = 680;
const EFFS = [[1, false], [2, false], [0.5, false], [1, true], [2, true], [0, false]];
const other = (s) => (s === 'a' ? 'b' : 'a');
const clampX = (x) => Math.min(W - BODY_R, Math.max(BODY_R, x));
const clampY = (y) => Math.min(H - BODY_R, Math.max(BODY_R, y));

class Sim {
  constructor(sty, ty) {
    this.sty = sty;
    this.ty = ty;
    this.now = 10;
    this.f = { a: { ...HOME.a, move: null, kb: null }, b: { ...HOME.b, move: null, kb: null } };
    this.p = [];
    this.z = [];
    this.todo = [];
    this.out = [];
    this.ids = 0;
    this.hits = 0;
    this.n = -1;                 // 몇째 장면
    this.scene = '';
    this.end = this.now;
    this.k = 'GALLERY_' + String(sty).toUpperCase();
  }

  // 장면이 끝나면 다음 것 - 쓰는 쪽은 한 바퀴마다 바뀐다 (내 것 · 상대 것 표시가 둘 다 보이게)
  next() {
    this.n += 1;
    this.scene = MODE === 'all' ? MODES[this.n % MODES.length] : MODE;
    const lap = MODE === 'all' ? Math.floor(this.n / MODES.length) : this.n;
    this.who = lap % 2 ? 'b' : 'a';
    this.lap = lap;
    this.end = this.now + SCENE_SEC[this.scene];
    this.z = this.z.filter((z) => z.kind !== 'haz');
    SCRIPT[this.scene](this, this.who, other(this.who));
  }

  at(dt, fn) { this.todo.push({ t: this.now + dt, fn }); }
  emit(ev) { this.out.push(ev); }
  id() { this.ids += 1; return this.ids; }
  aim(w, v) { return Math.atan2(this.f[v].y - this.f[w].y, this.f[v].x - this.f[w].x); }

  cast(w, kind, extra = {}) {
    const f = this.f[w], ang = extra.ang ?? this.aim(w, other(w));
    this.emit({ e: 'cast', w, m: 0, k: this.k, kind, ty: this.ty, sty: this.sty, x: f.x, y: f.y, ang, ...extra });
    return ang;
  }

  hit(w, v) {
    const [eff, crit] = EFFS[this.hits % EFFS.length], f = this.f[v];
    this.hits += 1;
    // 게임처럼: 맞은 쪽이 나(a)면 정확한 데미지, 상대(b)면 main 이 hpr 로 적는 pct (최대 체력의 %)
    const dmg = Math.round(20 + 40 * eff);
    this.emit({ e: 'hit', w, v, k: this.k, ty: this.ty, ...(v === 'a' ? { dmg } : {}), pct: dmg / 4, hpr: 600, eff, crit,
      x: f.x, y: f.y });
  }

  zone(w, kind, geo, wind, act) {
    const z = { id: 'z' + this.id(), o: w, k: this.k, ty: this.ty, sty: this.sty, kind, x: 0, y: 0, r: 0, ang: 0, len: 0, w: 0,
      t0: this.now, t1: this.now + wind, until: this.now + wind + act, ...geo };
    this.z.push(z);
    return z;
  }

  shoot(w, ang, r = 16) {
    const f = this.f[w];
    this.p.push({ id: 'p' + this.id(), o: w, k: this.k, ty: this.ty, sty: this.sty, x: f.x + Math.cos(ang) * 30,
      y: f.y + Math.sin(ang) * 30, vx: Math.cos(ang) * SHOT_V, vy: Math.sin(ang) * SHOT_V, r });
  }

  // 엔진의 근접 · 돌진: 준비 동안 서 있다가 ang 쪽으로 len 을 act 동안 달린다. 상대가 길에서 reach 안이면 맞고 멈춘다
  rush(w, mk, ang, len, r, wind, act) {
    const f = this.f[w];
    this.cast(w, mk, { ang, len, r });
    f.move = { kind: 'rush', t0: this.now, wind, act, ang, len, reach: r + (mk === 'dash' ? 2 : 1) * BODY_R, sx: f.x, sy: f.y, done: false };
  }

  // 상대에게서 gap 만큼 떨어진 곳까지 sec 동안 걸어간다
  walk(w, v, gap, sec) {
    const f = this.f[w], t = this.f[v], d = Math.hypot(t.x - f.x, t.y - f.y) || 1, go = Math.max(0, d - gap);
    f.move = { kind: 'walk', vx: ((t.x - f.x) / d) * (go / sec), vy: ((t.y - f.y) / d) * (go / sec), until: this.now + sec };
  }

  step(dt) {
    this.now += dt;
    this.todo.sort((p, q) => p.t - q.t);
    while (this.todo.length && this.todo[0].t <= this.now) this.todo.shift().fn();
    for (const s of ['a', 'b']) this.moveFighter(s, dt);
    for (const p of this.p) {
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      const v = this.f[other(p.o)];
      if (Math.hypot(p.x - v.x, p.y - v.y) <= BODY_R + p.r) {
        p.gone = true;
        this.hit(p.o, other(p.o));
      } else if (p.x < -40 || p.x > W + 40 || p.y < -40 || p.y > H + 40) p.gone = true;
    }
    this.p = this.p.filter((p) => !p.gone);
    this.z = this.z.filter((z) => z.until > this.now);
    if (this.now >= this.end && !this.p.length && !this.todo.length) this.next();
    const out = this.out;
    this.out = [];
    return out;
  }

  moveFighter(s, dt) {
    const f = this.f[s], m = f.move;
    if (f.kb) {                                   // 맞고 밀려남 (45 u 를 0.12초)
      const k = Math.min(dt, f.kb.left);
      f.x = clampX(f.x + f.kb.ux * (45 / 0.12) * k);
      f.y = clampY(f.y + f.kb.uy * (45 / 0.12) * k);
      f.kb.left -= k;
      if (f.kb.left <= 0) f.kb = null;
      return;
    }
    if (m && m.kind === 'rush' && !m.done) {
      const t = this.now - m.t0 - m.wind;
      if (t < 0) return;
      const d = Math.min(m.len, (m.len * t) / m.act), ux = Math.cos(m.ang), uy = Math.sin(m.ang);
      f.x = clampX(m.sx + ux * d);
      f.y = clampY(m.sy + uy * d);
      const v = this.f[other(s)], seg = segDist(v.x, v.y, m.sx, m.sy, f.x, f.y);
      if (seg <= m.reach) {
        m.done = true;
        this.hit(s, other(s));
        v.kb = { ux, uy, left: 0.12 };
      } else if (d >= m.len) m.done = true;
      if (m.done) f.move = { kind: 'rest', until: this.now + 0.35 };
      return;
    }
    if (m && m.kind === 'walk') {
      f.x = clampX(f.x + m.vx * dt);
      f.y = clampY(f.y + m.vy * dt);
      if (this.now >= m.until) f.move = { kind: 'rest', until: this.now + 0.1 };
      return;
    }
    if (m && m.kind === 'rest') {
      if (this.now >= m.until) f.move = null;
      return;
    }
    const home = HOME[s], hx = home.x + Math.sin(this.now * 1.3 + (s === 'a' ? 0 : 2)) * 14;   // 제자리로 걸어가며 살짝 흔들린다
    const hy = home.y + Math.cos(this.now * 0.9 + (s === 'a' ? 1 : 0)) * 10;
    const dx = hx - f.x, dy = hy - f.y, d = Math.hypot(dx, dy), v = Math.min(d, 300 * dt);
    if (d > 0.01) {
      f.x += (dx / d) * v;
      f.y += (dy / d) * v;
    }
  }
}

function segDist(px, py, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
  const t = l2 > 0 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) : 0;
  return Math.hypot(px - ax - dx * t, py - ay - dy * t);
}

// 장면마다 할 일 (sim, 쓰는 쪽, 맞는 쪽)
const SCRIPT = {
  proj(s, w, v) {                                // 한 발 → 부채꼴 세 발
    s.cast(w, 'proj');
    s.at(0.25, () => s.shoot(w, s.aim(w, v)));
    s.at(1.2, () => s.cast(w, 'proj'));
    s.at(1.45, () => { const a = s.aim(w, v); for (const d of [-0.18, 0, 0.18]) s.shoot(w, a + d, 13); });
  },
  cone(s, w, v) {
    const f = s.f[w], ang = s.cast(w, 'cone'), len = 440;
    s.zone(w, 'cone', { x: f.x, y: f.y, r: len, len, ang, w: 2 * len * Math.tan((35 * Math.PI) / 180) }, 0.6, 0.18);
    s.at(0.62, () => s.hit(w, v));
  },
  ring(s, w, v) {
    const f = s.f[w];
    s.cast(w, 'burst');
    s.zone(w, 'ring', { x: f.x, y: f.y, r: 230 }, 0.55, 0.2);
  },
  beam(s, w, v) {
    const f = s.f[w], ang = s.cast(w, 'beam');
    s.zone(w, 'beam', { x: f.x, y: f.y, ang, len: 900, w: 56 }, 0.9, 0.25);
    s.at(0.93, () => s.hit(w, v));
  },
  tele(s, w, v) {
    const t = s.f[v];
    s.cast(w, 'strike');
    s.zone(w, 'tele', { x: t.x, y: t.y, r: 75 }, 1.0, 0.15);
    s.at(1.0, () => s.hit(w, v));
  },
  haz(s, w, v) {
    const t = s.f[v];
    s.cast(w, 'hazard');
    s.at(0.4, () => {
      for (const [dx, dy] of [[-110, 60], [0, -90], [110, 70]]) {
        s.zone(w, 'haz', { x: clampX(t.x + dx), y: clampY(t.y + dy), r: 60, t1: s.now + 60 }, 0, 0).until = s.end + 0.01;
      }
    });
  },
  rush(s, w, v) {                               // 다가가서 근접 (상대 쪽 · 비스듬히 번갈아) → 물러나서 돌진
    const side = s.lap % 2 ? 0.55 : 0;
    s.walk(w, v, 250, 0.45);
    s.at(0.5, () => s.rush(w, 'melee', s.aim(w, v) + side, 220, 60, 0.2, 0.18));
    s.at(1.7, () => s.rush(w, 'dash', s.aim(w, v) - side, 440, 30, 0.08, 440 / 1500));
  },
  impact(s, w, v) {
    s.cast(w, 'proj');
    for (let i = 0; i < 5; i++) s.at(0.3 + i * 0.4, () => s.hit(w, v));
    s.at(2.3, () => {
      const a = s.f.a, b = s.f.b;
      s.emit({ e: 'clash', x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, k1: s.k, k2: s.k });
    });
  },
};

// ---------------------------------------------------------------- 칸
class Cell {
  constructor(sty) {
    this.sty = sty;
    this.ty = TYPE || NATURAL[sty] || 'NORMAL';
    this.fx = new Fx();
    this.sim = new Sim(sty, this.ty);
    this.world = { pos: (s) => this.sim.f[s], now: this.sim.now, you: 'a' };
    this.sim.next();
  }

  tick(dt) {
    for (const ev of this.sim.step(dt)) this.fx.event(ev, this.world);
    this.world.now = this.sim.now;
    this.fx.update(dt);
  }
}

// ---------------------------------------------------------------- 바닥 (render.js 와 비슷한 풀 마당 - 한 번 그려 둔다)
function makeFloor() {
  const c = document.createElement('canvas');
  c.width = W;
  c.height = H;
  const g = c.getContext('2d');
  let seed = 20261118;
  const rnd = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  g.fillStyle = '#2f5239';
  g.fillRect(0, 0, W, H);
  for (let x = 0; x < W; x += 100) {
    if ((x / 100) % 2) {
      g.fillStyle = 'rgba(255,255,255,0.025)';
      g.fillRect(x, 0, 100, H);
    }
  }
  g.lineWidth = 1.6;
  for (let i = 0; i < 1000; i += 1) {
    const x = rnd() * W, y = rnd() * H, h = 4 + rnd() * 7;
    g.strokeStyle = rnd() < 0.5 ? 'rgba(120,190,110,0.16)' : 'rgba(10,30,18,0.22)';
    g.beginPath();
    g.moveTo(x, y);
    g.lineTo(x + (rnd() - 0.5) * 4, y - h);
    g.stroke();
  }
  g.strokeStyle = 'rgba(255,255,255,0.09)';
  g.lineWidth = 3;
  g.strokeRect(30, 30, W - 60, H - 60);
  const v = g.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, W * 0.62);
  v.addColorStop(0, 'rgba(6,10,16,0)');
  v.addColorStop(1, 'rgba(6,10,16,0.55)');
  g.fillStyle = v;
  g.fillRect(0, 0, W, H);
  g.strokeStyle = 'rgba(0,0,0,0.5)';
  g.lineWidth = 8;
  g.strokeRect(4, 4, W - 8, H - 8);
  return c;
}

// ---------------------------------------------------------------- 그리기
const cv = document.getElementById('cv');
const ctx = cv.getContext('2d');
const cap = document.getElementById('cap');
const FLOOR = makeFloor();
const keys = ONE ? [ONE] : [...STYLES];
const cells = keys.map((k) => new Cell(k));
const FONT = "'Apple SD Gothic Neo','Malgun Gothic',sans-serif";
let layout = [];

// 칸 수 n 을 창에 가장 크게 - 열 수를 바꿔 보며 칸이 가장 큰 것
function fit(n, vw, vh) {
  let best = null;
  for (let cols = 1; cols <= n; cols++) {
    const rows = Math.ceil(n / cols), s = Math.min(vw / cols / W, vh / rows / H);
    if (!best || s > best.s) best = { cols, rows, s };
  }
  const cw = W * best.s, ch = H * best.s, ox = (vw - cw * best.cols) / 2, oy = (vh - ch * best.rows) / 2;
  return cells.map((cell, i) => ({ cell, x: ox + (i % best.cols) * cw, y: oy + Math.floor(i / best.cols) * ch, s: best.s, w: cw, h: ch }));
}

function resize() {
  const dpr = window.devicePixelRatio || 1;
  cv.width = Math.round(innerWidth * dpr);
  cv.height = Math.round(innerHeight * dpr);
  layout = fit(cells.length, innerWidth, innerHeight);
}

function body(g, f, side) {
  g.globalAlpha = 0.35;
  g.fillStyle = '#000000';
  g.beginPath();
  g.ellipse(f.x, f.y + BODY_R * 0.8, BODY_R * 0.9, BODY_R * 0.35, 0, 0, Math.PI * 2);
  g.fill();
  g.globalAlpha = 0.92;
  g.fillStyle = side === 'a' ? '#3f9e5a' : '#b8434b';
  g.beginPath();
  g.arc(f.x, f.y, BODY_R, 0, Math.PI * 2);
  g.fill();
  g.globalAlpha = 1;
  g.lineWidth = 2.5;
  g.strokeStyle = side === 'a' ? '#5fd97a' : '#ff6b6b';
  g.stroke();
}

function name(g, f, side) {
  g.font = `700 20px ${FONT}`;
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.lineWidth = 4;
  g.strokeStyle = 'rgba(0,0,0,0.7)';
  const s = side === 'a' ? '나' : '상대';
  g.strokeText(s, f.x, f.y - BODY_R - 16);
  g.fillStyle = side === 'a' ? '#c8ffd4' : '#ffd0d0';
  g.fillText(s, f.x, f.y - BODY_R - 16);
}

function drawCell(L, dpr) {
  const { cell, s } = L, { fx, sim } = cell, sh = fx.shake(), zm = fx.zoom();
  ctx.save();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.beginPath();
  ctx.rect(L.x + 1, L.y + 1, L.w - 2, L.h - 2);
  ctx.clip();
  const k = s * ZOOM;                              // 확대하면 (cx, cy) 가 칸 가운데에 온다
  const ox = ZOOM > 1 ? L.x + L.w / 2 - num(Q.get('cx'), W / 2) * k : L.x;
  const oy = ZOOM > 1 ? L.y + L.h / 2 - num(Q.get('cy'), H / 2) * k : L.y;
  ctx.setTransform(dpr * k, 0, 0, dpr * k, dpr * (ox + sh.x * k), dpr * (oy + sh.y * k));
  if (zm.k > 1) {                                  // 급소 · 효과 굉장 · 쓰러짐에 살짝 다가간다 (render.toArena 와 같은 셈)
    ctx.translate(zm.x, zm.y);
    ctx.scale(zm.k, zm.k);
    ctx.translate(-zm.x, -zm.y);
  }
  ctx.drawImage(FLOOR, 0, 0, W, H);
  for (const z of sim.z) fx.drawZone(ctx, z, sim.now);
  fx.drawUnder(ctx);
  body(ctx, sim.f.a, 'a');
  body(ctx, sim.f.b, 'b');
  for (const p of sim.p) fx.drawProjectile(ctx, p, p.x, p.y);
  fx.drawOver(ctx);
  name(ctx, sim.f.a, 'a');
  name(ctx, sim.f.b, 'b');
  ctx.restore();
  // 칸 이름 (화면 단위)
  ctx.save();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const px = ONE ? 16 : Math.max(11, Math.min(15, L.w / 22));
  ctx.font = `700 ${px}px ${FONT}`;
  ctx.textBaseline = 'top';
  ctx.textAlign = 'left';
  const label = `${cell.sty} · ${cell.ty}`, sub = `${sim.scene}${sim.who === 'b' ? ' (상대 것)' : ''}`;
  const tw = Math.max(ctx.measureText(label).width, ctx.measureText(sub).width) + 12;
  ctx.fillStyle = 'rgba(11,14,21,0.72)';
  ctx.fillRect(L.x + 6, L.y + (ONE ? 64 : 6), tw, px * 2.4 + 6);
  ctx.fillStyle = '#ffc043';
  ctx.fillText(label, L.x + 12, L.y + (ONE ? 67 : 9));
  ctx.fillStyle = '#a9b1c9';
  ctx.fillText(sub, L.x + 12, L.y + (ONE ? 67 : 9) + px * 1.2);
  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.lineWidth = 1;
  ctx.strokeRect(L.x + 0.5, L.y + 0.5, L.w - 1, L.h - 1);
  ctx.restore();
}

function caption() {
  const probs = checkFamilies();
  const parts = [`<b>이펙트 갤러리</b> <span class="dim">· style=</span>${ONE || '전부 (' + cells.length + ')'}`,
    `<span class="dim">· mode=</span>${MODE}`, `<span class="dim">· type=</span>${TYPE || '모양마다 흔한 것'}`,
    `<span class="dim">· slow=</span>${SLOW}`, paused ? '<b>멈춤</b> <span class="dim">(Space 다시 · → 한 장)</span>' : ''];
  const help = ONE ? ' <a href="?' + keep({ style: null }) + '">← 전부</a>'
    : ' <span class="dim">칸을 누르면 그 모양만</span>';
  cap.innerHTML = parts.join(' ') + help + '<br><span class="dim">?style=wind &amp;type=FLYING &amp;slow=0.25 &amp;mode='
    + MODES.join('|') + '|all &amp;at=1.2 · Space 멈춤</span>' + (probs.length ? '<div class="bad">' + probs.join('\n') + '</div>' : '');
}

function keep(change) {
  const p = new URLSearchParams(location.search);
  for (const [k, v] of Object.entries(change)) {
    if (v === null) p.delete(k);
    else p.set(k, v);
  }
  return p.toString();
}

cv.addEventListener('click', (e) => {
  if (ONE) return;
  const L = layout.find((c) => e.clientX >= c.x && e.clientX < c.x + c.w && e.clientY >= c.y && e.clientY < c.y + c.h);
  if (L) location.search = keep({ style: L.cell.sty });
});

let last = performance.now();
let paused = AT > 0;
let nudge = 0;                                   // 멈춘 채 앞으로 갈 장 수

/** at= 까지 미리 돌린다. 그리기도 장마다 같이 한다 - 탄 꼬리 · 흘리는 입자 · 처음 번쩍임은 그리는 훅이 뿌리므로,
 *  돌리기만 하면 멈춘 장면에 그것들이 없다 (창이 숨어 있으면 requestAnimationFrame 이 안 돌아서 이 장면만 남는다). */
function preroll() {
  const dpr = window.devicePixelRatio || 1;
  for (let t = 0; t < AT; t += STEP) {
    for (const L of layout) {
      L.cell.tick(STEP);
      drawCell(L, dpr);
    }
  }
}

window.addEventListener('keydown', (e) => {
  if (e.code === 'Space') {
    paused = !paused;
    caption();
  } else if (e.code === 'ArrowRight' || e.code === 'Period') nudge += 1;
  else return;
  e.preventDefault();
});

function frame(ts) {
  let dt = Math.min(0.1, Math.max(0, (ts - last) / 1000)) * SLOW;
  last = ts;
  if (paused) {
    dt = nudge > 0 ? STEP : 0;
    nudge = Math.max(0, nudge - 1);
  }
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'source-over';
  ctx.fillStyle = '#0b0e15';
  ctx.fillRect(0, 0, cv.width, cv.height);
  for (const L of layout) {
    L.cell.tick(dt);
    drawCell(L, dpr);
  }
  requestAnimationFrame(frame);
}

window.addEventListener('resize', resize);
resize();
if (AT > 0) preroll();
caption();
requestAnimationFrame(frame);
