/* 서버 모습 이어 그리기 · 내 이동 먼저 그리기.

   서버는 30번/초 판을 굴려 모습(스냅샷)을 보낸다. 받은 대로 그리면 뚝뚝 끊기므로 조금(80ms) 뒤의 시각을
   그리면서 양옆 두 모습 사이를 곧게 잇는다. 내 포켓몬만은 누른 순간 움직여야 손맛이 나므로, 서버가 아직
   모르는 입력을 F.spd 로 먼저 굴려 그리고, 서버가 받았다고(ack) 하면 그 자리에서 남은 입력을 다시 굴린다. */
import { ARENA_W, ARENA_H, BODY_R, INTERP_DELAY } from './consts.js';

const lerp = (a, b, t) => a + (b - a) * t;

/** 몸이 벽을 넘지 않게 (아레나 가장자리에서 몸 반지름만큼 안쪽). */
export function clampArena(x, y) {
  return {
    x: Math.min(ARENA_W - BODY_R, Math.max(BODY_R, x)),
    y: Math.min(ARENA_H - BODY_R, Math.max(BODY_R, y)),
  };
}

const CLOCK_WINDOW = 3;      // 이만큼(초) 지난 표본은 버린다
const CLOCK_SNAP = 0.25;     // 이보다 크게 어긋나면 바로 맞춘다
const CLOCK_EASE = 4;        // 조금 어긋나면 1초에 이 비율로 따라간다
const CLOCK_STARVE = 5;      // 여유(delay)보다 늦은 모습이 이만큼 잇따르면 옛 표본을 버린다 (30번/초로 약 0.16초)

/** 서버 시계 어림.

   모습의 ts(판 시각)와 받은 지역 시각의 차 가운데 **가장 큰 것**(가장 빨리 온 모습)을 기준으로 한다 - 늦게 온
   모습에 맞추면 그리는 시각이 들쭉날쭉하다. 핑(png/pong)은 왕복 시간만 잰다 (내 이동을 다시 굴릴 때 쓴다).
   서버가 밀린 틱을 버리면(action_ws 의 CATCHUP) ts − 받은 때가 그 뒤로 줄곧 낮다. 그때 옛 최댓값을 CLOCK_WINDOW
   동안 들고 있으면 그리는 시각이 가장 새 모습을 앞질러 이어 그리기가 굶는다 - 여유보다 늦은 모습이 CLOCK_STARVE 번
   잇따르면 옛 표본을 버린다. 여유 안의 흔들림은 세지 않는다. */
export class Clock {
  constructor(delay = INTERP_DELAY) {
    this.delay = delay;
    this.samples = [];
    this.offset = null;
    this.target = null;
    this.rtt = null;
    this.starve = 0;             // 여유보다 늦게 온 모습이 몇 번 잇따랐나
  }

  snap(ts, recv) {
    const v = ts - recv;
    this.samples.push({ recv, v });
    while (this.samples[0].recv < recv - CLOCK_WINDOW) this.samples.shift();
    this.starve = this.target !== null && this.target - v > this.delay ? this.starve + 1 : 0;
    if (this.starve >= CLOCK_STARVE) {
      this.samples = this.samples.slice(-1);
      this.starve = 0;
    }
    this.target = Math.max(...this.samples.map((s) => s.v));
    if (this.offset === null || Math.abs(this.target - this.offset) > CLOCK_SNAP) this.offset = this.target;
  }

  tick(dt) {
    if (this.offset !== null) this.offset += (this.target - this.offset) * Math.min(1, dt * CLOCK_EASE);
  }

  ready() {
    return this.offset !== null;
  }

  /** 지금 서버 판 시각 (가장 새 모습 기준). */
  now(local) {
    return local + this.offset;
  }

  /** 그릴 판 시각 - 이어 그릴 여유만큼 뒤. */
  render(local) {
    return this.now(local) - this.delay;
  }

  /** png 에 실어 보낸 c 가 돌아왔다. */
  pong(c, recv) {
    const r = recv - c;
    if (!(r >= 0)) return;
    this.rtt = this.rtt === null ? r : this.rtt * 0.75 + r * 0.25;
  }
}

const KEEP = 1.0;            // 가장 새 모습보다 이만큼 지난 모습은 버린다 (초)
const EXTRAPOLATE = 0.15;    // 다음 모습이 없을 때 탄을 속도대로 더 보내는 한도 (초)
const EVENT_CAP = 600;       // 그리기가 멈춘 동안(숨긴 창) 쌓이는 이벤트 한도

function fighterAt(f0, f1, t) {
  const base = (t < 0.5 ? f0 : f1) ?? null;
  if (!f0 || !f1 || f0.i !== f1.i) return base;       // 교체로 다른 포켓몬이면 잇지 않는다
  return {
    ...base,
    x: lerp(f0.x, f1.x, t),
    y: lerp(f0.y, f1.y, t),
    sp: f0.st === f1.st ? lerp(f0.sp, f1.sp, t) : base.sp,
  };
}

function projectilesAt(p0 = [], p1 = [], t, since) {
  const next = new Map(p1.map((p) => [p.id, p]));
  return p0.map((p) => {
    const q = next.get(p.id);
    if (q && q !== p) return { ...p, x: lerp(p.x, q.x, t), y: lerp(p.y, q.y, t) };
    const dt = Math.min(since, EXTRAPOLATE);           // 다음 모습에 없다 (터졌거나 아직 안 왔다)
    return { ...p, x: p.x + p.vx * dt, y: p.y + p.vy * dt };
  });
}

function viewAt(s0, s1, t, since) {
  const near = t < 0.5 ? s0 : s1;
  return {
    ts: lerp(s0.ts, s1.ts, t),
    ph: near.ph,
    f: { a: fighterAt(s0.f?.a, s1.f?.a, t), b: fighterAt(s0.f?.b, s1.f?.b, t) },
    p: projectilesAt(s0.p, s1.p, t, since),
    z: near.z || [],
  };
}

/** 받은 모습을 시각 순으로 들고 있다가, 그릴 시각의 모습을 이어서 준다. 이벤트는 그 시각이 되어야 내준다. */
export class SnapBuffer {
  constructor() {
    this.list = [];
    this.queue = [];
  }

  push(s) {
    for (const e of s.ev || []) this.queue.push({ ts: s.ts, e });
    if (this.queue.length > EVENT_CAP) this.queue.splice(0, this.queue.length - EVENT_CAP);
    const last = this.latest();
    if (last && s.ts <= last.ts) return;
    this.list.push(s);
    while (this.list.length > 2 && this.list[1].ts <= s.ts - KEEP) this.list.shift();
  }

  latest() {
    return this.list[this.list.length - 1] || null;
  }

  size() {
    return this.list.length;
  }

  /** 판 시각 rt 의 모습. 범위 밖이면 가까운 끝 것 (탄만 속도대로 조금 더). */
  at(rt) {
    const L = this.list;
    if (!L.length) return null;
    let i = L.length - 1;
    while (i > 0 && L[i].ts > rt) i -= 1;
    const s0 = L[i];
    const s1 = L[i + 1];
    if (!s1 || rt <= s0.ts) return viewAt(s0, s0, 0, Math.max(0, rt - s0.ts));
    const t = (rt - s0.ts) / (s1.ts - s0.ts);
    return viewAt(s0, s1, t, rt - s0.ts);
  }

  /** 판 시각 rt 까지 온 이벤트 (한 번만). */
  events(rt) {
    let n = 0;
    while (n < this.queue.length && this.queue[n].ts <= rt) n += 1;
    return this.queue.splice(0, n).map((q) => q.e);
  }
}

const SMOOTH = 0.1;          // 서버와의 어긋남을 줄이는 시간 상수 (초)
const SNAP_DIST = 150;       // 이보다 멀면 바로 옮긴다 (교체 · 순간 이동)
const MAX_PENDING = 120;     // ack 가 안 와도 이보다 많이 쌓지 않는다
// 마음대로 걷는 때. 그 밖(기술 준비 · 발동 · 피하기 · 잠듦 · 교체 …)에는 서버가 몸을 옮기거나 세우므로
// 가장 새 서버 자리를 따른다 - 꼴마다 다른 이동 배율을 화면이 따로 들고 있지 않는다.
const FREE_STATES = new Set(['idle', 'walk']);

const movable = (f) => f.spd > 0 && FREE_STATES.has(f.st);

function advance(p, v, k, dt) {
  return clampArena(p.x + v.x * k * dt, p.y + v.y * k * dt);
}

/** 내 포켓몬 먼저 그리기.

   입력 i 는 지역 시각 t_i 에 보내 왕복의 반 뒤에 서버에 닿는다. 그래서 받은 모습(서버가 만든 때 = 받은 때 − 왕복의
   반)에는 지역 시각 '받은 때 − 왕복' 까지의 입력이 들어 있다고 본다. 그 시각부터 지금까지를, 그때의 의도와 그 뒤의
   입력으로 다시 굴린다 (ack 로 앞뒤를 묶는다 - 받은 입력보다 앞, 안 받은 입력보다 뒤). 다시 굴린 자리가 보이던 자리와
   다르면 그 차이를 잠깐 동안 줄여 간다 - 한 번에 옮기면 튄다. */
export class Predictor {
  constructor() {
    this.inputs = [];                                   // 서버가 아직 안 받은 이동 의도 {seq, x, y, t}
    this.base = { seq: 0, x: 0, y: 0, t: -Infinity };    // 서버가 받은 마지막 의도
    this.srv = null;
    this.err = { x: 0, y: 0 };
  }

  input(seq, x, y, t) {
    this.inputs.push({ seq, x, y, t });
    if (this.inputs.length > MAX_PENDING) this.base = this.inputs.shift();
  }

  pending() {
    return this.inputs.length;
  }

  /** 내 F 를 받았다. ack = 서버가 받은 가장 큰 seq, recv = 받은 지역 시각. */
  server(f, ack, recv, rtt) {
    const before = this.srv ? this.pos(recv) : null;
    while (this.inputs.length && this.inputs[0].seq <= ack) this.base = this.inputs.shift();
    this.srv = {
      x: f.x, y: f.y, recv, rtt,
      k: (f.spd || 0) * ((f.c || []).includes('cnf') ? -1 : 1),     // 혼란이면 반대로 간다
      free: movable(f),
    };
    const after = this.raw(recv);
    const dx = before ? before.x - after.x : 0;
    const dy = before ? before.y - after.y : 0;
    this.err = Math.hypot(dx, dy) < SNAP_DIST ? { x: dx, y: dy } : { x: 0, y: 0 };
  }

  tick(dt) {
    const k = Math.exp(-dt / SMOOTH);
    this.err.x *= k;
    this.err.y *= k;
  }

  ready() {
    return this.srv !== null;
  }

  /** 보일 자리 (지역 시각 now). */
  pos(now) {
    const r = this.raw(now);
    return { x: r.x + this.err.x, y: r.y + this.err.y };
  }

  raw(now) {
    const s = this.srv;
    if (!s.free) return { x: s.x, y: s.y };
    const first = this.inputs.length ? this.inputs[0].t : Infinity;
    let t = Math.min(Math.max(s.recv - s.rtt, this.base.t), first);
    let p = { x: s.x, y: s.y };
    let v = this.base;
    for (const next of this.inputs) {
      if (next.t > now) break;
      p = advance(p, v, s.k, Math.max(0, next.t - t));
      t = Math.max(t, next.t);
      v = next;
    }
    return advance(p, v, s.k, Math.max(0, now - t));
  }
}
