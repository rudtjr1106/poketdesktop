/* 화면 칸 (캔버스에 그린다, 아레나 단위 1600×900).

     위 왼쪽  내 포켓몬 이름 · 체력 · 상태 · 랭크 · 팀 셋        위 가운데  남은 시간        위 오른쪽  상대 (체력은 비율)
     아래 왼쪽 기술 네 칸 (키 자리대로 2×2: U I / J K)                                 아래 오른쪽 피하기 · 교체 1 2 3
   가운데에는 3 · 2 · 1, 다음 포켓몬 고르기, 서버의 한 줄 알림. 데미지 숫자 · 효과 글씨는 fx 가 그린다.
   대기는 마지막 모습의 남은 초에서 그 뒤 흐른 시간을 빼서 매 장 줄인다. */
import {
  ARENA_W, ARENA_H, LEVEL, DODGE_CD, SWITCH_CD, STRUGGLE_CD, FONT, SLOT_KEYS, TYPE_COLOR, TYPE_KR, KIND_KR,
  STATUS_KR, STATUS_COLOR, COND_KR, STAT_KR, UI,
} from './consts.js';

/** 남은 초 → 'm:ss' (올림). */
export function fmtClock(sec) {
  if (sec === null || sec === undefined) return '';
  const s = Math.max(0, Math.ceil(sec - 1e-9));
  return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
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

// 발버둥 칸 (타입 없음 - 칸 왼쪽 띠는 흐린 색)
const STRUGGLE_MOVE = { kr: '발버둥', type: null, pp: 0 };

const PAD = 20;
const SLOT_W = 236;
const SLOT_H = 60;
const GAP = 8;
// 2×2 칸 자리: 위 줄이 U I (m2 m3), 아래 줄이 J K (m0 m1) - 키보드 자리 그대로
const SLOT_POS = [[0, 1], [1, 1], [0, 0], [1, 0]];
const SIDE_W = 380;
const CARD_W = 150;
const CARD_H = 56;
const TOAST_SEC = 2.4;

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

function chip(ctx, s, x, y, color, fg = '#10131c') {
  ctx.font = font(13);
  const w = ctx.measureText(s).width + 14;
  roundRect(ctx, x, y - 10, w, 20, 5);
  ctx.fillStyle = color;
  ctx.fill();
  text(ctx, s, x + w / 2, y + 0.5, 13, fg, 'center');
  return w + 5;
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

export class Hud {
  constructor(bank) {
    this.bank = bank;
    this.toasts = [];
    this.needSince = null;
    this.fightSince = null;
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

  /** s = {ph, left(남은 초), you, them(상대 쪽), me · foe(F | null), mon(쪽, 칸) → MonView | null, moves(내 기술),
      age(마지막 모습 뒤 흐른 초), names{a,b}, koPick(쓰러진 뒤 고르는 초), now(지역 초), rtt(초 | null),
      status(가운데 알림 | null)} */
  draw(ctx, s) {
    if (s.ph === 'fight' && this.fightSince === null) this.fightSince = s.now;
    if (s.me && s.me.need) this.needSince ??= s.now;
    else this.needSince = null;
    this.drawClock(ctx, s);
    if (s.me) this.drawSide(ctx, s.me, s.mon(s.you, s.me.i), PAD, false, s.names[s.you]);
    if (s.foe) this.drawSide(ctx, s.foe, s.mon(s.them, s.foe.i), ARENA_W - PAD - SIDE_W, true, s.names[s.them]);
    if (s.me && s.ph === 'fight') {
      this.drawMoves(ctx, s);
      this.drawDodge(ctx, s);
      this.drawSwitch(ctx, s);
    }
    this.drawCenter(ctx, s);
    this.drawToasts(ctx, s.now);
    text(ctx, 'Esc 기권 · H 도움말' + (s.rtt !== null ? ' · 핑 ' + Math.round(s.rtt * 1000) + 'ms' : ''),
      ARENA_W / 2, ARENA_H - 16, 13, UI.faint, 'center', 500);
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

  drawMoves(ctx, s) {
    const top = ARENA_H - PAD - 24 - SLOT_H * 2 - GAP;
    const cd = s.me.cd || [];
    const pp = s.me.pp || [];
    // 쓸 기술이 없으면 네 칸 다 발버둥. 서버는 기술이 있는 칸의 대기만 보내지만 발버둥은 네 칸을 같이 막으므로
    // 기술이 없는 칸은 보낸 것 중 가장 긴 대기로 친다
    const struggle = struggleOnly(s.moves, pp);
    for (let m = 0; m < 4; m += 1) {
      const [col, row] = SLOT_POS[m];
      const x = PAD + col * (SLOT_W + GAP);
      const y = top + row * (SLOT_H + GAP);
      if (struggle) {
        const left = (m < cd.length ? cd[m] : Math.max(0, ...cd)) - s.age;
        const st = { grey: false, reason: '쓸 기술 없음 · 반동 피해', frac: coolFrac(left, STRUGGLE_CD) };
        this.drawSlot(ctx, x, y, m, STRUGGLE_MOVE, st, 0, s.me.sm === m);
        continue;
      }
      const move = s.moves[m] || null;
      const st = slotState(move, (cd[m] || 0) - s.age, pp[m]);
      this.drawSlot(ctx, x, y, m, move, st, pp[m], s.me.sm === m);
    }
  }

  drawSlot(ctx, x, y, m, move, st, pp, active) {
    ctx.save();
    if (st.grey) ctx.globalAlpha = 0.5;
    panel(ctx, x, y, SLOT_W, SLOT_H, 10, active ? UI.panelHi : UI.panel);
    if (move) {
      ctx.fillStyle = TYPE_COLOR[move.type] || UI.dim;
      ctx.fillRect(x + 1, y + 10, 4, SLOT_H - 20);
    }
    const cap = { x: x + 10, y: y + 9, w: 42, h: 42, r: 8 };
    roundRect(ctx, cap.x, cap.y, cap.w, cap.h, cap.r);
    ctx.fillStyle = active ? UI.gold : 'rgba(255,255,255,0.12)';
    ctx.fill();
    text(ctx, SLOT_KEYS[m][0], cap.x + 18, cap.y + 19, 22, active ? '#2a1f08' : UI.fg, 'center', 800);
    text(ctx, SLOT_KEYS[m][1], cap.x + 35, cap.y + 34, 11, active ? '#2a1f08' : UI.dim, 'center', 700);
    pie(ctx, cap.x + cap.w / 2, cap.y + cap.h / 2, 40, st.frac, cap);
    if (move) {
      text(ctx, move.kr, x + 62, y + 21, 17, UI.fg);
      if (st.reason) {
        text(ctx, st.reason, x + 62, y + 43, 12, UI.dim, 'left', 500);
      } else {
        text(ctx, (TYPE_KR[move.type] || '') + ' · ' + (KIND_KR[move.kind] || ''), x + 62, y + 43, 12, UI.dim, 'left', 500);
        text(ctx, pp + '/' + move.pp, x + SLOT_W - 12, y + 43, 13, pp <= Math.ceil(move.pp / 4) ? UI.foe : UI.fg, 'right');
      }
    }
    ctx.restore();
  }

  drawDodge(ctx, s) {
    const r = 34;
    const cx = ARENA_W - PAD - r - 4;
    const cy = ARENA_H - PAD - 24 - CARD_H - GAP - r - 6;
    const frac = coolFrac((s.me.dcd || 0) - s.age, DODGE_CD);
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = frac ? UI.panel : 'rgba(255,192,67,0.22)';
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = frac ? UI.line : UI.gold;
    ctx.stroke();
    text(ctx, '피하기', cx, cy - 6, 15, UI.fg, 'center');
    text(ctx, 'Space · Shift', cx, cy + 13, 10, UI.dim, 'center', 600);
    pie(ctx, cx, cy, r, frac, null);
  }

  drawSwitch(ctx, s) {
    const y = ARENA_H - PAD - 24 - CARD_H;
    const team = s.me.team || [];
    const x0 = ARENA_W - PAD - team.length * (CARD_W + GAP) + GAP;
    const frac = coolFrac((s.me.scd || 0) - s.age, SWITCH_CD);
    team.forEach((t, j) => {
      const x = x0 + j * (CARD_W + GAP);
      const cur = j === s.me.i;
      const mon = s.mon(s.you, j);
      ctx.save();
      if (t.ko) ctx.globalAlpha = 0.4;
      panel(ctx, x, y, CARD_W, CARD_H, 10, cur ? UI.panelHi : UI.panel);
      if (cur) {
        roundRect(ctx, x, y, CARD_W, CARD_H, 10);
        ctx.strokeStyle = UI.gold;
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      const look = this.bank.look(mon);
      if (look) this.bank.icon(ctx, look, x + 26, y + CARD_H / 2, 36, s.now);
      text(ctx, String(j + 1), x + 9, y + 12, 12, UI.gold, 'left', 800);
      text(ctx, mon ? mon.kr : '', x + 50, y + 20, 14, UI.fg);
      bar(ctx, x + 50, y + 34, CARD_W - 62, 7, t.hpr / 1000);
      if (!cur && !t.ko) pie(ctx, x + CARD_W / 2, y + CARD_H / 2, CARD_W, frac, { x, y, w: CARD_W, h: CARD_H, r: 10 });
      ctx.restore();
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
