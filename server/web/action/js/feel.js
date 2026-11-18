/* 손맛 - 맞는 순간의 멈춤 · 몸 자리 잡아 두기 · 맞은 비율 · 이어 맞은 숫자 합치기.

   멈춤(hitstop) 은 하나다: fx 가 HitStop 을 만들어 맞을 때마다 kick 하고 update 로 줄인다. render 는 같은 것을 읽어
   몸 도트를 멈추고 자리를 잡아 둔다 - 이펙트 시간과 몸이 같은 길이로 멈춘다. 판 시계는 서버 것이라 그리기만 멈춘다.
   멈춤이 풀리면 잡아 둔 자리에서 진짜 자리로 CATCHUP_SEC 동안 미끄러진다 (한 번에 옮기지 않는다).

   상대의 정확한 체력은 오지 않는다 - 맞은 비율은 hpr(0~1000) 이 줄어든 만큼이다. 스냅샷이 오는 차례대로
   이벤트를 보며 쪽 · 칸마다 마지막 hpr 을 들고 있다가 hit 에 pct(최대 체력의 %) 를 적어 둔다. */

export const STOP_MIN = 0.05;        // 멈춤 (초) - 약하게 맞아도
export const STOP_MAX = 0.11;        // 세게 · 급소 · 쓰러짐
const STOP_FULL_PCT = 25;            // 최대 체력의 이만큼(%)을 깎으면 데미지 몫은 다 찬다
const STOP_UNKNOWN_PCT = 8;          // 비율을 모를 때 어림
export const CATCHUP_SEC = 0.08;     // 멈춤이 풀린 뒤 진짜 자리까지
const CATCHUP_SNAP = 200;            // 이보다 멀면 (교체 · 순간 이동) 미끄러지지 않고 바로
export const MERGE_SEC = 0.6;        // 이 안에 또 맞으면 숫자 하나로 합친다

const clamp01 = (v) => (v > 0 ? (v < 1 ? v : 1) : 0);
const smooth = (t) => t * t * (3 - 2 * t);

/** 한 번 맞을 때의 멈춤 (초). pct 최대 체력의 % · eff 상성 · crit 급소 · ko 쓰러뜨렸나. 막혔으면(eff 0) 0. */
export function hitstopSec({ pct, eff = 1, crit = false, ko = false } = {}) {
  if (ko) return STOP_MAX;
  if (!(eff > 0)) return 0;
  const p = Number.isFinite(pct) ? pct : STOP_UNKNOWN_PCT;
  const v = STOP_MIN + 0.03 * clamp01(p / STOP_FULL_PCT) + (eff > 1 ? 0.015 : 0) + (crit ? 0.015 : 0);
  return Math.min(STOP_MAX, v);
}

/** 반동 · 독 · 화상 · 씨뿌리기 같은 저절로 깎이는 것 - 멈추지 않는다 (2초마다 화면이 서면 거슬린다). */
export function isChip(ev) {
  return !!ev && (ev.w === ev.v || ev.k === 'seed' || ev.k === 'brn' || ev.k === 'psn' || ev.k === 'tox');
}

/** 그리기 멈춤 하나 (fx · render 가 같이 본다). */
export class HitStop {
  constructor() {
    this.left = 0;
  }

  /** 더 긴 쪽으로 (짧은 것이 긴 것을 끊지 않는다). */
  kick(sec) {
    if (sec > this.left) this.left = sec;
  }

  update(dt) {
    this.left = Math.max(0, this.left - (dt > 0 ? dt : 0));
  }

  get active() {
    return this.left > 0;
  }
}

/** 몸 하나의 그릴 자리. 멈춘 동안은 멈춘 순간의 자리, 풀리면 거기서 진짜 자리로 미끄러진다. */
export class Hold {
  constructor() {
    this.reset();
  }

  reset() {
    this.held = null;
    this.off = null;
    this.offAt = 0;
    this.last = null;
  }

  /** (x, y) 진짜 자리 · now 지역 초 · stopped 멈춤 중. 돌려준 자리를 그린다. */
  at(x, y, now, stopped) {
    if (stopped) {
      if (!this.held) this.held = this.last ? { x: this.last.x, y: this.last.y } : { x, y };
      this.last = { x: this.held.x, y: this.held.y };
      return this.last;
    }
    if (this.held) {
      const dx = this.held.x - x;
      const dy = this.held.y - y;
      this.off = Math.hypot(dx, dy) < CATCHUP_SNAP ? { x: dx, y: dy } : null;
      this.offAt = now;
      this.held = null;
    }
    let px = x;
    let py = y;
    if (this.off) {
      const u = (now - this.offAt) / CATCHUP_SEC;
      if (u >= 1) {
        this.off = null;
      } else {
        const k = 1 - smooth(clamp01(u));
        px += this.off.x * k;
        py += this.off.y * k;
      }
    }
    this.last = { x: px, y: py };
    return this.last;
  }
}

/** 쪽 · 칸마다 마지막 hpr 을 들고, 스냅샷의 hit 에 pct (최대 체력의 몇 %를 잃었나) 를 적는다.
    스냅샷은 받은 차례대로 넣는다 (그리는 때가 아니라). 교체 · 회복도 따라간다. */
export class HpTracker {
  constructor() {
    this.sides = { a: { i: 0, hpr: [] }, b: { i: 0, hpr: [] } };
  }

  side(w) {
    return this.sides[w] || null;
  }

  annotate(s) {
    for (const ev of (s && s.ev) || []) {
      if (!ev) continue;
      if (ev.e === 'swap') {
        const t = this.side(ev.w);
        if (t && Number.isInteger(ev.to)) t.i = ev.to;
      } else if (ev.e === 'hit' && Number.isFinite(ev.hpr)) {
        const t = this.side(ev.v);
        if (!t) continue;
        const prev = t.hpr[t.i];
        const before = Number.isFinite(prev) ? prev : 1000;
        ev.pct = Math.max(0, before - ev.hpr) / 10;
        t.hpr[t.i] = ev.hpr;
      } else if (ev.e === 'heal' && Number.isFinite(ev.hpr)) {
        const t = this.side(ev.w);
        if (t) t.hpr[t.i] = ev.hpr;
      }
    }
    for (const w of ['a', 'b']) {
      const f = s && s.f && s.f[w];
      if (!f) continue;
      const t = this.sides[w];
      if (Number.isInteger(f.i)) t.i = f.i;
      (f.team || []).forEach((m, j) => {
        if (m && Number.isFinite(m.hpr)) t.hpr[j] = m.hpr;
      });
      if (Number.isFinite(f.hpr)) t.hpr[t.i] = f.hpr;
    }
    return s;
  }
}

/** 데미지 숫자 글. 비율은 반올림하되 깎였으면 적어도 1%. */
export function damageLabel(value, unit) {
  if (unit === '%') return Math.max(1, Math.round(value)) + '%';
  return String(Math.max(0, Math.round(value)));
}

/** 이어 맞은 숫자 합치기: list 에서 같은 쪽 · 같은 단위의 숫자가 MERGE_SEC 안에 있으면 그것을 돌려준다. */
export function mergeTarget(list, side, unit) {
  for (let i = list.length - 1; i >= 0; i--) {
    const t = list[i];
    if (t.num && t.side === side && t.unit === unit && t.age < MERGE_SEC) return t;
  }
  return null;
}
