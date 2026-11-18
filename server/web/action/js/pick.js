/* 고르기 화면 (DOM): 내 팀 6마리 중 3마리를 고른 순서대로. 1~6 으로 고르고(다시 누르면 뺀다) Enter 로 낸다.
   안 고르고 시간이 다 되면 서버가 앞 3마리를 낸다. 상대 팀은 종 · 타입만 보인다. */
import { TEAM, TYPE_COLOR, TYPE_KR, KIND_KR, CAT_KR } from './consts.js';

/** 고른 칸 목록에 i 를 넣거나 뺀다 (고른 순서를 지킨다). max 를 넘으면 그대로. */
export function togglePick(sel, i, max) {
  if (sel.includes(i)) return sel.filter((j) => j !== i);
  return sel.length < max ? [...sel, i] : sel;
}

const DIGITS = /^(?:Digit|Numpad)([1-6])$/;

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function typeChips(types) {
  const box = el('div', 'types');
  for (const t of types || []) {
    const c = el('span', 'type', TYPE_KR[t] || t);
    c.style.background = TYPE_COLOR[t] || '#666';
    box.append(c);
  }
  return box;
}

/** 기술 한 줄 설명: 분류 · 꼴 (예: '특수 · 날리기'). */
function moveLine(mv) {
  return [CAT_KR[mv.cat], KIND_KR[mv.kind]].filter(Boolean).join(' · ');
}

const ICON = 72;             // 그림 칸 (CSS 픽셀)

export class PickScreen {
  constructor(root, bank, onPick) {
    this.root = root;
    this.bank = bank;
    this.onPick = onPick;
    this.sel = [];
    this.sent = false;
    this.team = [];
    this.need = 0;
    this.icons = [];
  }

  isOpen() {
    return !this.root.hidden;
  }

  open(mine, foe) {
    this.team = mine;
    this.need = Math.min(TEAM, mine.length);
    this.sel = [];
    this.sent = false;
    this.icons = [];
    const mineBox = this.root.querySelector('[data-mine]');
    const foeBox = this.root.querySelector('[data-foe]');
    mineBox.replaceChildren(...mine.map((m, i) => this.card(m, i)));
    foeBox.replaceChildren(...foe.map((m) => this.foeCard(m)));
    this.root.querySelector('[data-go]').onclick = () => this.submit();
    this.root.hidden = false;
    this.refresh();
  }

  close() {
    this.root.hidden = true;
    this.icons = [];
  }

  icon(mon, size) {
    const c = el('canvas', 'icon');
    const dpr = window.devicePixelRatio || 1;
    c.width = Math.round(size * dpr);
    c.height = Math.round(size * dpr);
    c.style.width = size + 'px';
    c.style.height = size + 'px';
    this.icons.push({ c, mon, size, dpr });
    return c;
  }

  card(m, i) {
    const b = el('button', 'card mine');
    b.type = 'button';
    b.tabIndex = -1;                       // 키는 창 전체가 받는다 (포커스를 두지 않는다)
    b.onclick = () => this.toggle(i);
    const head = el('div', 'card-head');
    head.append(el('span', 'key', String(i + 1)), el('span', 'order'));
    const name = el('div', 'name', m.kr);
    const moves = el('ul', 'moves');
    for (const mv of m.moves || []) {
      const li = el('li', mv.ok ? '' : 'off');
      const dot = el('i');
      dot.style.background = TYPE_COLOR[mv.type] || '#666';
      li.append(dot, el('span', 'mv', mv.kr), el('span', 'kind', mv.ok ? moveLine(mv) : mv.why));
      moves.append(li);
    }
    b.append(head, this.icon(m, ICON), name, typeChips(m.types), el('div', 'item', m.item ? '도구 · ' + m.item : ''), moves);
    return b;
  }

  foeCard(m) {
    const d = el('div', 'card foe');
    d.append(this.icon(m, 56), el('div', 'name', m.kr), typeChips(m.types));
    return d;
  }

  toggle(i) {
    if (this.sent || i >= this.team.length) return;
    this.sel = togglePick(this.sel, i, this.need);
    this.refresh();
  }

  submit() {
    if (this.sent || this.sel.length !== this.need) return;
    this.sent = true;
    this.onPick(this.sel.slice());
    this.refresh();
  }

  /** 고르기 화면이 받는 키. 받았으면 true. */
  key(code) {
    const m = DIGITS.exec(code);
    if (m) {
      this.toggle(Number(m[1]) - 1);
      return true;
    }
    if (code === 'Enter' || code === 'NumpadEnter') {
      this.submit();
      return true;
    }
    if (code === 'Backspace') {
      if (!this.sent) this.sel = this.sel.slice(0, -1);
      this.refresh();
      return true;
    }
    return false;
  }

  refresh() {
    this.root.querySelectorAll('.card.mine').forEach((b, i) => {
      const at = this.sel.indexOf(i);
      b.classList.toggle('on', at >= 0);
      b.querySelector('.order').textContent = at >= 0 ? at + 1 + '번째' : '';
    });
    const go = this.root.querySelector('[data-go]');
    go.disabled = this.sent || this.sel.length !== this.need;
    go.textContent = this.sent ? '냈다' : '나가기 (Enter)';
  }

  /** 매 장: 남은 초 · 상대가 골랐나 · 그림 (서 있는 모습이 숨쉰다). */
  tick(now, left, foeDone) {
    this.root.querySelector('[data-timer]').textContent = String(Math.max(0, Math.ceil(left)));
    const status = this.sent ? (foeDone ? '둘 다 골랐다' : '상대를 기다리는 중…')
      : this.sel.length + ' / ' + this.need + ' 골랐다' + (foeDone ? ' · 상대는 골랐다' : '');
    this.root.querySelector('[data-status]').textContent = status;
    for (const ic of this.icons) {
      const look = this.bank.look(ic.mon);
      if (!look) continue;
      const g = ic.c.getContext('2d');
      g.setTransform(ic.dpr, 0, 0, ic.dpr, 0, 0);
      g.imageSmoothingEnabled = false;
      g.clearRect(0, 0, ic.size, ic.size);
      this.bank.icon(g, look, ic.size / 2, ic.size / 2, ic.size * 0.8, now);
    }
  }
}
