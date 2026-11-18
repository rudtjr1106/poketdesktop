/* 화면 칸 (캔버스에 그린다, 아레나 단위 1600×900).

     위 왼쪽  내 포켓몬 이름 · 체력 · 상태 · 랭크 · 팀 셋        위 가운데  남은 시간        위 오른쪽  상대 (체력은 비율)
     아래 한 줄 (조작 띠)   [Shift 피하기] [Z] [X] [C] [V] 기술 네 칸 (가운데) [1] [2] [3] 교체
     아래 왼쪽 구석  이동 키 · Esc 기권 · H 도움말 · 핑
   가운데에는 3 · 2 · 1, 다음 포켓몬 고르기, 서버의 한 줄 알림. 데미지 숫자 · 효과 글씨는 fx 가 그린다.
   대기는 마지막 모습의 남은 초에서 그 뒤 흐른 시간을 빼서 매 장 줄인다.

   키를 누르면 그 칸이 바로 눌린다 (서버를 기다리지 않는다). 못 쓰는 칸은 흔들리고 까닭이 위에 뜬다 - 그런 키는
   보내지도 않는다 (pressVerdict). 대기가 거의 끝났으면 보낸다 - 서버가 잠깐 들고 있다가 쓴다. */
import {
  ARENA_W, ARENA_H, LEVEL, DODGE_CD, SWITCH_CD, STRUGGLE_CD, FONT, SLOT_KEYS, DODGE_KEY, MOVE_HINT, PRESS_GRACE,
  TYPE_COLOR, TYPE_KR, KIND_KR, STATUS_KR, STATUS_COLOR, COND_KR, STAT_KR, UI,
} from './consts.js';
import { slotOf, teamSlotOf } from './input.js';

/** 남은 초 → 'm:ss' (올림). */
export function fmtClock(sec) {
  if (sec === null || sec === undefined) return '';
  const s = Math.max(0, Math.ceil(sec - 1e-9));
  return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
}

/** 대기 남은 초 → 칸에 적는 글 ('1.2' · '12'). 다 됐으면 ''. */
export function fmtCd(sec) {
  if (!(sec > 0)) return '';
  return sec < 10 ? (Math.ceil(sec * 10 - 1e-9) / 10).toFixed(1) : String(Math.ceil(sec - 1e-9));
}

/** 대기 남은 비율 0~1. */
export function coolFrac(left, total) {
  if (!(total > 0) || !(left > 0)) return 0;
  return Math.min(1, left / total);
}

/** 기술 칸 하나: 회색인가, 까닭, 대기 비율. */
export function slotState(move, cdLeft, ppLeft) {
  if (!move) return { grey: true, reason: '', frac: 0 };
  const frac = coolFrac(cdLeft, move.cd);
  if (!move.ok) return { grey: true, reason: move.why || '쓸 수 없다', frac };
  if (ppLeft <= 0) return { grey: true, reason: 'PP 없음', frac };
  return { grey: false, reason: '', frac };
}

/** 쓸 기술(ok 이고 PP 가 남은 것)이 하나도 없다 → 어느 기술 키든 발버둥이 나간다 (엔진 Mon.out_of_moves 와 같은 셈). */
export function struggleOnly(moves, pp) {
  return !moves.some((mv, i) => mv && mv.ok && pp[i] > 0);
}

const DEFAULT_RTT = 0.1;
const NO = (reason) => ({ send: false, ok: false, reason, predict: false });

/** 키 하나를 눌렀다 - 보낼까, 칸을 어떻게 보일까.
    s = {me (내 F | null), moves (내 기술 MonView), age (마지막 모습 뒤 초), rtt (초 | null)}.
    → {send, ok (눌린 칸이 반짝 / 아니면 흔들림), reason ('대기 중' · 'PP 없음' · '못 씀' …), predict (누르자마자 준비 몸짓을
    그려도 되나 - 대기 0 · PP 있음 · 서 있거나 걷는 중), kind, ty}.
    대기가 (왕복을 빼고) PRESS_GRACE 안이면 보낸다 - 서버가 그만큼 들고 있다가 쓴다. 판정은 서버가 한다. */
export function pressVerdict(act, s) {
  const me = s.me;
  if (!me) return NO('');
  const rtt = Number.isFinite(s.rtt) ? s.rtt : DEFAULT_RTT;
  const left = (v) => Math.max(0, (Number(v) || 0) - (s.age || 0));
  const soon = (l) => l - rtt <= PRESS_GRACE;
  const free = (me.st === 'idle' || me.st === 'walk') && !me.need;
  const m = slotOf(act);
  if (m >= 0) {
    if (me.need) return NO('교체 먼저');
    const cd = me.cd || [];
    const pp = me.pp || [];
    const moves = s.moves || [];
    if (struggleOnly(moves, pp)) {
      const l = left(m < cd.length ? cd[m] : Math.max(0, ...cd));
      if (!soon(l)) return NO('대기 중');
      return { send: true, ok: true, reason: '', predict: l <= 0 && free, kind: 'melee', ty: 'NORMAL' };
    }
    const move = moves[m];
    if (!move || !move.ok || move.kind === 'none') return NO('못 씀');
    if (!(pp[m] > 0)) return NO('PP 없음');
    const l = left(cd[m]);
    if (!soon(l)) return NO('대기 중');
    return { send: true, ok: true, reason: '', predict: l <= 0 && free, kind: move.kind, ty: move.type };
  }
  if (act === 'dodge') {
    if (me.need) return NO('교체 먼저');
    return soon(left(me.dcd)) ? { send: true, ok: true, reason: '', predict: false } : NO('대기 중');
  }
  const j = teamSlotOf(act);
  if (j >= 0) {
    const t = (me.team || [])[j];
    if (!t) return NO('없음');
    if (t.ko) return NO('기절');
    if (j === me.i) return NO('나와 있음');
    if (!me.need && !soon(left(me.scd))) return NO('대기 중');
    return { send: true, ok: true, reason: '', predict: false };
  }
  return { send: true, ok: true, reason: '', predict: false };
}

export const PRESS_FLASH = 0.16;     // 눌린 칸이 반짝이는 시간
export const SHAKE_SEC = 0.3;        // 못 쓰는 칸이 흔들리는 시간
export const REASON_SEC = 0.8;       // 까닭 글씨가 떠 있는 시간 (끝 0.25초에 흐려진다)

/** 누른 뒤 칸의 모습. p = {at, ok, reason} | null. → {flash 0~1, dx 흔들림 (아레나 단위), reason, reasonA 0~1}. */
export function pressLook(p, now) {
  const none = { flash: 0, dx: 0, reason: '', reasonA: 0 };
  if (!p) return none;
  const age = now - p.at;
  if (!(age >= 0)) return none;
  if (p.ok) return { ...none, flash: age < PRESS_FLASH ? 1 - age / PRESS_FLASH : 0 };
  const dx = age < SHAKE_SEC ? Math.sin(age * 55) * 7 * (1 - age / SHAKE_SEC) : 0;
  const reasonA = age < REASON_SEC ? Math.min(1, (REASON_SEC - age) / 0.25) : 0;
  return { flash: 0, dx, reason: reasonA > 0 ? p.reason : '', reasonA };
}

// 발버둥 칸 (타입 없음 - 칸 위 띠는 흐린 색)
const STRUGGLE_MOVE = { kr: '발버둥', type: null, pp: 0, kind: 'melee' };

const PAD = 20;
const SIDE_W = 380;
const TOAST_SEC = 2.4;
const READY_FLASH = 0.3;     // 대기가 끝난 칸이 반짝이는 시간

/* 아래 조작 띠. 기술 네 칸이 가운데, 왼쪽에 피하기 (Shift 는 Z 왼쪽 키), 오른쪽에 교체 셋. */
const SLOT_W = 206;
const SLOT_H = 116;
const SLOT_GAP = 10;
const STRIP_GAP = 12;
const STRIP_Y = ARENA_H - 14 - SLOT_H;
const DODGE_W = 116;
const CARD_W = 108;
const CARD_GAP = 8;
const MOVES_W = SLOT_W * 4 + SLOT_GAP * 3;
const MOVES_X = (ARENA_W - MOVES_W) / 2;

/** 조작 띠의 칸 자리 (아레나 단위). 기술 칸 m 0~3 (Z X C V 차례) · 피하기 · 교체 칸 j 0~2. */
export function stripLayout(team = 3) {
  const moves = [0, 1, 2, 3].map((m) => ({ x: MOVES_X + m * (SLOT_W + SLOT_GAP), y: STRIP_Y, w: SLOT_W, h: SLOT_H }));
  const dodge = { x: MOVES_X - STRIP_GAP - DODGE_W, y: STRIP_Y, w: DODGE_W, h: SLOT_H };
  const x0 = MOVES_X + MOVES_W + STRIP_GAP;
  const cards = Array.from({ length: team }, (_, j) => ({ x: x0 + j * (CARD_W + CARD_GAP), y: STRIP_Y, w: CARD_W, h: SLOT_H }));
  const all = [dodge, ...moves, ...cards];
  const box = { x: dodge.x, y: STRIP_Y, w: Math.max(...all.map((r) => r.x + r.w)) - dodge.x, h: SLOT_H };
  return { moves, dodge, cards, box };
}

function font(size, weight = 700) {
  return weight + ' ' + size + 'px ' + FONT;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
}

function panel(ctx, x, y, w, h, r = 10, fill = UI.panel) {
  roundRect(ctx, x, y, w, h, r);
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.strokeStyle = UI.line;
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

function text(ctx, s, x, y, size, color = UI.fg, align = 'left', weight = 700) {
  ctx.font = font(size, weight);
  ctx.textAlign = align;
  ctx.textBaseline = 'middle';
  ctx.fillStyle = color;
  ctx.fillText(s, x, y);
}

/** 폭 maxW 에 들어가게 글자 크기를 줄여 쓴다 (min 까지, 그래도 넘치면 그대로). */
function fitText(ctx, s, x, y, maxW, size, min, color, align = 'left', weight = 800) {
  let px = size;
  ctx.font = font(px, weight);
  while (px > min && ctx.measureText(s).width > maxW) {
    px -= 1;
    ctx.font = font(px, weight);
  }
  text(ctx, s, x, y, px, color, align, weight);
}

/** 테두리 글씨 (아레나 위에 바로 쓰는 큰 글씨). */
function outlined(ctx, s, x, y, size, color) {
  ctx.font = font(size, 800);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.lineJoin = 'round';
  ctx.lineWidth = size / 7;
  ctx.strokeStyle = 'rgba(8,10,16,0.85)';
  ctx.strokeText(s, x, y);
  ctx.fillStyle = color;
  ctx.fillText(s, x, y);
}

export function hpColor(r) {
  return r > 0.5 ? UI.hpHi : r > 0.2 ? UI.hpMid : UI.hpLow;
}

function bar(ctx, x, y, w, h, ratio) {
  roundRect(ctx, x, y, w, h, h / 2);
  ctx.fillStyle = 'rgba(0,0,0,0.55)';
  ctx.fill();
  const r = Math.max(0, Math.min(1, ratio));
  if (r > 0) {
    roundRect(ctx, x, y, Math.max(h, w * r), h, h / 2);
    ctx.fillStyle = hpColor(r);
    ctx.fill();
  }
}

/** 한 칸을 대기 비율만큼 시계 방향으로 어둡게 (12시부터). */
function pie(ctx, cx, cy, r, frac, clip) {
  if (frac <= 0) return;
  ctx.save();
  if (clip) {
    roundRect(ctx, clip.x, clip.y, clip.w, clip.h, clip.r);
    ctx.clip();
  }
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * frac);
  ctx.closePath();
  ctx.fillStyle = 'rgba(4,6,12,0.68)';
  ctx.fill();
  ctx.restore();
}

/** 칸 전체를 덮는 대기 (가운데에서 시계 방향) + 칸 테두리 반짝 (눌림 · 대기 끝). */
function sweep(ctx, r, frac) {
  pie(ctx, r.x + r.w / 2, r.y + r.h / 2, Math.hypot(r.w, r.h), frac, { ...r, r: 12 });
}

function glowEdge(ctx, r, color, a, width = 3) {
  if (!(a > 0)) return;
  ctx.save();
  ctx.globalAlpha *= Math.min(1, a);
  roundRect(ctx, r.x, r.y, r.w, r.h, 12);
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.stroke();
  ctx.restore();
}

/** 키 글자 자리 (네모). pressed 면 눌려 내려가고 밝아진다. flash (누른 순간) 면 금색으로 번쩍. */
function keyCap(ctx, x, y, w, h, label, size, { active = false, pressed = false, flash = 0, dim = false } = {}) {
  const down = pressed ? 2 : 0;
  roundRect(ctx, x, y + 3, w, h, 10);
  ctx.fillStyle = 'rgba(0,0,0,0.45)';                 // 키 밑면
  ctx.fill();
  roundRect(ctx, x, y + down, w, h, 10);
  ctx.fillStyle = active ? UI.gold : pressed ? 'rgba(255,255,255,0.34)' : 'rgba(255,255,255,0.14)';
  ctx.fill();
  if (flash > 0) {
    ctx.save();
    ctx.globalAlpha *= Math.min(1, flash);
    ctx.fillStyle = UI.gold;
    ctx.fill();
    ctx.restore();
  }
  const ink = active || flash > 0.35 ? '#2a1f08' : dim ? UI.dim : UI.fg;
  text(ctx, label, x + w / 2, y + h / 2 + down + 1, size, ink, 'center', 800);
}

function chip(ctx, s, x, y, color, fg = '#10131c') {
  ctx.font = font(13);
  const w = ctx.measureText(s).width + 14;
  roundRect(ctx, x, y - 10, w, 20, 5);
  ctx.fillStyle = color;
  ctx.fill();
  text(ctx, s, x + w / 2, y + 0.5, 13, fg, 'center');
  return w + 5;
}

/** 칸 위에 뜨는 까닭 ('대기 중' · 'PP 없음' · '못 씀'). */
function reasonTag(ctx, s, cx, y, a) {
  if (!s || !(a > 0)) return;
  ctx.save();
  ctx.globalAlpha *= a;
  ctx.font = font(15, 800);
  const w = ctx.measureText(s).width + 20;
  roundRect(ctx, cx - w / 2, y - 15, w, 28, 8);
  ctx.fillStyle = 'rgba(40,10,14,0.92)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,107,107,0.8)';
  ctx.lineWidth = 1.5;
  ctx.stroke();
  text(ctx, s, cx, y, 15, '#ffd0d0', 'center', 800);
  ctx.restore();
}

/** 상태이상 · 혼란 같은 것 · 랭크를 한 줄로. */
function badges(ctx, f, x, y, maxX) {
  let cx = x;
  const add = (s, color, fg) => {
    if (cx < maxX) cx += chip(ctx, s, cx, y, color, fg);
  };
  if (f.s) add(STATUS_KR[f.s] || f.s, STATUS_COLOR[f.s] || UI.dim);
  for (const c of f.c || []) add(COND_KR[c] || c, 'rgba(255,255,255,0.16)', UI.fg);
  for (const [k, v] of Object.entries(f.stg || {})) {
    if (v) add((STAT_KR[k] || k) + (v > 0 ? '+' : '−') + Math.abs(v), v > 0 ? '#3f9e5a' : '#b8434d', '#fff');
  }
}

function teamDots(ctx, f, x, y) {
  (f.team || []).forEach((m, j) => {
    ctx.beginPath();
    ctx.arc(x + j * 18, y, 6.5, 0, Math.PI * 2);
    ctx.fillStyle = m.ko ? '#3a4058' : hpColor(m.hpr / 1000);
    ctx.fill();
    if (j === f.i) {
      ctx.lineWidth = 2;
      ctx.strokeStyle = UI.gold;
      ctx.stroke();
    }
  });
}

const behind = (r, p, pad) => p && p.x > r.x - pad && p.x < r.x + r.w + pad && p.y > r.y - pad * 1.6 && p.y < r.y + r.h + pad;

export class Hud {
  constructor(bank) {
    this.bank = bank;
    this.toasts = [];
    this.needSince = null;
    this.fightSince = null;
    this.presses = {};           // 동작 ('m0' · 'dodge' · 'sw1' …) → {at, ok, reason}
    this.held = new Set();       // 누르고 있는 동작 키
    this.cool = {};              // 칸 → 지난 장의 대기 비율 (끝나는 순간 반짝)
    this.readyAt = {};
  }

  /** 서버 이벤트 (그릴 때가 된 것). 한 줄 알림만 여기서 받는다. */
  event(ev, now, nameOf) {
    if (ev.e === 'txt' && ev.msg) this.toast(ev.msg, now);
    else if (ev.e === 'ko') this.toast(nameOf(ev.w, ev.i) + ' 쓰러졌다!', now);
  }

  toast(msg, now) {
    this.toasts.push({ msg, at: now });
    if (this.toasts.length > 4) this.toasts.shift();
  }

  /** 키를 눌렀다 (보내기 전에 바로). v = pressVerdict 의 것. */
  press(act, v, now) {
    this.presses[act] = { at: now, ok: !!v.ok, reason: v.reason || '' };
    this.held.add(act);
  }

  release(act) {
    this.held.delete(act);
  }

  releaseAll() {
    this.held.clear();
  }

  /** s = {ph, left(남은 초), you, them(상대 쪽), me · foe(F | null), mon(쪽, 칸) → MonView | null, moves(내 기술),
      age(마지막 모습 뒤 흐른 초), names{a,b}, koPick(쓰러진 뒤 고르는 초), now(지역 초), rtt(초 | null),
      status(가운데 알림 | null), bodies([{x, y}] 그린 몸 자리 - 띠 뒤에 있으면 띠를 옅게)} */
  draw(ctx, s) {
    if (s.ph === 'fight' && this.fightSince === null) this.fightSince = s.now;
    if (s.me && s.me.need) this.needSince ??= s.now;
    else this.needSince = null;
    this.drawClock(ctx, s);
    if (s.me) this.drawSide(ctx, s.me, s.mon(s.you, s.me.i), PAD, false, s.names[s.you]);
    if (s.foe) this.drawSide(ctx, s.foe, s.mon(s.them, s.foe.i), ARENA_W - PAD - SIDE_W, true, s.names[s.them]);
    if (s.me && s.ph === 'fight') this.drawStrip(ctx, s);
    this.drawCenter(ctx, s);
    this.drawToasts(ctx, s.now);
    this.drawHints(ctx, s);
  }

  drawHints(ctx, s) {
    const x = PAD + 2;
    const y = ARENA_H - 70;
    text(ctx, '이동  ' + MOVE_HINT, x, y, 14, UI.dim, 'left', 700);
    text(ctx, 'Esc 기권 · H 도움말', x, y + 22, 13, UI.faint, 'left', 500);
    if (s.rtt !== null && s.rtt !== undefined) text(ctx, '핑 ' + Math.round(s.rtt * 1000) + 'ms', x, y + 42, 13, UI.faint, 'left', 500);
  }

  drawClock(ctx, s) {
    const label = s.ph === 'fight' ? fmtClock(s.left) : s.ph === 'ready' ? '준비' : s.ph === 'pick' ? '고르기' : '';
    if (!label) return;
    panel(ctx, ARENA_W / 2 - 64, 14, 128, 50, 12);
    const low = s.ph === 'fight' && s.left <= 30;
    text(ctx, label, ARENA_W / 2, 40, s.ph === 'fight' ? 30 : 22, low ? UI.foe : UI.fg, 'center', 800);
  }

  drawSide(ctx, f, mon, x, right, owner) {
    const w = SIDE_W;
    const y = 14;
    panel(ctx, x, y, w, 86, 12);
    const near = right ? x + w - 16 : x + 16;
    const far = right ? x + 16 : x + w - 16;
    const align = right ? 'right' : 'left';
    const away = right ? 'left' : 'right';
    text(ctx, (mon ? mon.kr : '') + '  Lv.' + LEVEL, near, y + 22, 20, UI.fg, align);
    text(ctx, owner, far, y + 22, 13, right ? UI.foe : UI.me, away, 600);
    bar(ctx, x + 16, y + 40, w - 32, 12, f.hpr / 1000);
    const hpText = f.hp !== undefined ? f.hp + ' / ' + f.mhp : Math.ceil(f.hpr / 10) + '%';
    text(ctx, hpText, near, y + 68, 14, UI.dim, align, 600);
    badges(ctx, f, right ? x + 76 : x + 110, y + 68, right ? x + w - 110 : x + w - 76);
    teamDots(ctx, f, right ? x + 22 : x + w - 58, y + 68);
  }

  /** 대기 비율이 0 이 되는 순간을 적어 둔다 (그 칸이 반짝). */
  cooled(id, frac, now) {
    if (this.cool[id] > 0 && !(frac > 0)) this.readyAt[id] = now;
    this.cool[id] = frac;
    const age = now - (this.readyAt[id] ?? -Infinity);
    return age < READY_FLASH ? 1 - age / READY_FLASH : 0;
  }

  /** 아래 조작 띠 한 줄: 피하기 · 기술 넷 · 교체 셋. 몸이 띠 뒤에 있으면 옅게. */
  drawStrip(ctx, s) {
    const team = s.me.team || [];
    const L = stripLayout(team.length);
    ctx.save();
    if ((s.bodies || []).some((p) => behind(L.box, p, 30))) ctx.globalAlpha = 0.45;
    this.drawDodge(ctx, s, L.dodge);
    this.drawMoves(ctx, s, L.moves);
    this.drawSwitch(ctx, s, L.cards);
    ctx.restore();
  }

  drawMoves(ctx, s, rects) {
    const cd = s.me.cd || [];
    const pp = s.me.pp || [];
    const casting = s.me.st === 'wind' || s.me.st === 'act' || s.me.st === 'guard';
    // 쓸 기술이 없으면 네 칸 다 발버둥. 서버는 기술이 있는 칸의 대기만 보내지만 발버둥은 네 칸을 같이 막으므로
    // 기술이 없는 칸은 보낸 것 중 가장 긴 대기로 친다
    const struggle = struggleOnly(s.moves, pp);
    for (let m = 0; m < 4; m += 1) {
      const r = rects[m];
      const active = casting && s.me.sm === m;
      if (struggle) {
        const left = (m < cd.length ? cd[m] : Math.max(0, ...cd)) - s.age;
        const st = { grey: false, reason: '쓸 기술 없음 · 반동 피해', frac: coolFrac(left, STRUGGLE_CD), left };
        this.drawSlot(ctx, s, r, m, STRUGGLE_MOVE, st, 0, active);
        continue;
      }
      const move = s.moves[m] || null;
      const left = (cd[m] || 0) - s.age;
      const st = { ...slotState(move, left, pp[m]), left };
      this.drawSlot(ctx, s, r, m, move, st, pp[m], active);
    }
  }

  drawSlot(ctx, s, r0, m, move, st, pp, active) {
    const id = 'm' + m;
    const look = pressLook(this.presses[id], s.now);
    const pressed = this.held.has(id);
    const r = { ...r0, x: r0.x + look.dx };
    const ready = this.cooled(id, st.grey ? 0 : st.frac, s.now);
    const type = move && move.type ? TYPE_COLOR[move.type] || UI.dim : 'rgba(255,255,255,0.25)';
    ctx.save();
    if (st.grey) ctx.globalAlpha *= 0.5;
    panel(ctx, r.x, r.y, r.w, r.h, 12, active ? UI.panelHi : UI.panel);
    ctx.save();
    roundRect(ctx, r.x, r.y, r.w, r.h, 12);
    ctx.clip();
    ctx.globalAlpha *= 0.1;
    ctx.fillStyle = type;
    ctx.fillRect(r.x, r.y, r.w, r.h);                  // 타입 색을 옅게
    ctx.globalAlpha /= 0.1;
    ctx.fillStyle = type;
    ctx.fillRect(r.x, r.y, r.w, 6);                    // 위 띠
    ctx.restore();
    const cooling = !st.grey && st.frac > 0;
    const cap = { x: r.x + 12, y: r.y + 18, w: 56, h: 56 };
    keyCap(ctx, cap.x, cap.y, cap.w, cap.h, cooling ? '' : SLOT_KEYS[m], 34, { active, pressed, flash: look.flash, dim: st.grey });
    if (move) {
      fitText(ctx, move.kr, r.x + 80, r.y + 34, r.w - 90, 21, 14, UI.fg);
      if (st.reason) {
        fitText(ctx, st.reason, r.x + 80, r.y + 60, r.w - 90, 13, 10, st.grey ? '#ff9d9d' : UI.dim, 'left', 700);
      } else {
        fitText(ctx, (TYPE_KR[move.type] || '') + ' · ' + (KIND_KR[move.kind] || ''), r.x + 80, r.y + 60, r.w - 90, 13, 10,
          UI.dim, 'left', 600);
      }
      if (move.pp) {
        const low = pp <= Math.ceil(move.pp / 4);
        text(ctx, 'PP ' + pp + '/' + move.pp, r.x + 14, r.y + r.h - 18, 14, pp <= 0 ? '#ff9d9d' : low ? UI.foe : UI.dim, 'left', 700);
      }
      if (move.cd && !cooling) text(ctx, '대기 ' + fmtCd(move.cd) + '초', r.x + r.w - 12, r.y + r.h - 18, 12, UI.faint, 'right', 600);
    }
    if (cooling) {
      sweep(ctx, r, st.frac);
      text(ctx, fmtCd(st.left), cap.x + cap.w / 2, cap.y + cap.h / 2 + 1, 24, UI.gold, 'center', 800);
      text(ctx, SLOT_KEYS[m], cap.x + cap.w - 8, cap.y + 10, 12, UI.dim, 'center', 800);
      text(ctx, fmtCd(st.left) + '초', r.x + r.w - 12, r.y + r.h - 18, 15, UI.gold, 'right', 800);
    }
    if (active) glowEdge(ctx, r, UI.gold, 1, 3);
    glowEdge(ctx, r, '#ffffff', Math.max(look.flash, ready) * 0.9, 3);
    ctx.restore();
    reasonTag(ctx, look.reason, r0.x + r0.w / 2, r0.y - 18, look.reasonA);
  }

  drawDodge(ctx, s, r0) {
    const look = pressLook(this.presses.dodge, s.now);
    const r = { ...r0, x: r0.x + look.dx };
    const left = (s.me.dcd || 0) - s.age;
    const frac = coolFrac(left, DODGE_CD);
    const ready = this.cooled('dodge', frac, s.now);
    panel(ctx, r.x, r.y, r.w, r.h, 12, UI.panel);
    keyCap(ctx, r.x + 12, r.y + 18, r.w - 24, 40, DODGE_KEY, 19, { pressed: this.held.has('dodge'), flash: look.flash });
    text(ctx, '피하기', r.x + r.w / 2, r.y + 78, 17, UI.fg, 'center', 800);
    text(ctx, '무적 0.2초', r.x + r.w / 2, r.y + 98, 11, UI.faint, 'center', 600);
    if (frac > 0) {
      sweep(ctx, r, frac);
      text(ctx, fmtCd(left), r.x + r.w / 2, r.y + 38, 24, UI.gold, 'center', 800);
    } else {
      glowEdge(ctx, r, UI.gold, 0.45, 2);
    }
    glowEdge(ctx, r, '#ffffff', Math.max(look.flash, ready) * 0.9, 3);
    reasonTag(ctx, look.reason, r0.x + r0.w / 2, r0.y - 18, look.reasonA);
  }

  drawSwitch(ctx, s, rects) {
    const team = s.me.team || [];
    const left = (s.me.scd || 0) - s.age;
    const frac = coolFrac(left, SWITCH_CD);
    const need = !!s.me.need;
    team.forEach((t, j) => {
      const id = 'sw' + j;
      const look = pressLook(this.presses[id], s.now);
      const r = { ...rects[j], x: rects[j].x + look.dx };
      const cur = j === s.me.i;
      const mon = s.mon(s.you, j);
      ctx.save();
      if (t.ko) ctx.globalAlpha *= 0.4;
      panel(ctx, r.x, r.y, r.w, r.h, 12, cur ? UI.panelHi : UI.panel);
      const look2 = this.bank.look(mon);
      if (look2) this.bank.icon(ctx, look2, r.x + r.w / 2, r.y + 44, 50, s.now);
      keyCap(ctx, r.x + 8, r.y + 8, 26, 26, String(j + 1), 15, { pressed: this.held.has(id), flash: look.flash, active: cur });
      fitText(ctx, mon ? mon.kr : '', r.x + r.w / 2, r.y + 82, r.w - 14, 14, 10, UI.fg, 'center', 700);
      bar(ctx, r.x + 10, r.y + 97, r.w - 20, 8, t.hpr / 1000);
      if (cur) glowEdge(ctx, r, UI.gold, 1, 2.5);
      else if (need && !t.ko) glowEdge(ctx, r, UI.gold, 0.55 + 0.45 * Math.sin(s.now * 8), 3);
      if (!cur && !t.ko && !need && frac > 0) {
        sweep(ctx, r, frac);
        text(ctx, fmtCd(left), r.x + r.w / 2, r.y + 44, 22, UI.gold, 'center', 800);
      }
      if (t.ko) text(ctx, '기절', r.x + r.w / 2, r.y + 44, 16, '#ff9d9d', 'center', 800);
      glowEdge(ctx, r, '#ffffff', look.flash * 0.9, 3);
      ctx.restore();
      reasonTag(ctx, look.reason, rects[j].x + rects[j].w / 2, rects[j].y - 18, look.reasonA);
    });
  }

  drawCenter(ctx, s) {
    const cx = ARENA_W / 2;
    if (s.status) {
      panel(ctx, cx - 300, ARENA_H / 2 - 44, 600, 88, 16);
      text(ctx, s.status, cx, ARENA_H / 2, 22, UI.fg, 'center');
      return;
    }
    if (s.ph === 'ready') {
      const n = Math.max(1, Math.ceil(s.left));
      const k = 1 + (Math.ceil(s.left) - s.left) * 0.25;
      outlined(ctx, String(n), cx, ARENA_H / 2 - 20, 150 * k, UI.gold);
      return;
    }
    if (s.ph === 'fight' && s.now - this.fightSince < 0.9) {
      outlined(ctx, '시작!', cx, ARENA_H / 2 - 20, 110, UI.gold);
    }
    if (this.needSince !== null) {
      const left = Math.max(0, s.koPick - (s.now - this.needSince));
      panel(ctx, cx - 280, 250, 560, 74, 14, 'rgba(42,31,8,0.88)');
      text(ctx, '다음 포켓몬을 고르세요 · 1 · 2 · 3', cx, 276, 22, UI.gold, 'center', 800);
      text(ctx, Math.ceil(left) + '초 안에 안 고르면 앞에서부터 나간다', cx, 304, 13, UI.dim, 'center', 600);
    }
  }

  drawToasts(ctx, now) {
    this.toasts = this.toasts.filter((t) => now - t.at < TOAST_SEC);
    this.toasts.forEach((t, j) => {
      const age = now - t.at;
      ctx.save();
      ctx.globalAlpha = Math.min(1, (TOAST_SEC - age) / 0.4) * Math.min(1, age / 0.12);
      outlined(ctx, t.msg, ARENA_W / 2, 100 + j * 30, 20, UI.fg);
      ctx.restore();
    });
  }
}
