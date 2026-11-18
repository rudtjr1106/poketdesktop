/* 키 입력.

   키는 event.code(물리 키 자리)로 읽는다 - 한글 입력 상태에서 key 가 'Process' · 'ㅈ' 여도 자리는 같다.
   누른 채 들어오는 되풀이(repeat)는 새 동작으로 치지 않는다. 창이 포커스를 잃으면 눌린 키를 비운다 -
   keyup 이 다른 창으로 가 버려서 계속 걸어가는 일이 없게. */
import { MOVE_KEYS, ACT_KEYS, UI_KEYS } from './consts.js';

const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

/** 키 자리 하나가 하는 일. {move} · {act} · {ui} 또는 null. */
export function keyAction(code) {
  if (has(MOVE_KEYS, code)) return { move: MOVE_KEYS[code] };
  if (has(ACT_KEYS, code)) return { act: ACT_KEYS[code] };
  if (has(UI_KEYS, code)) return { ui: UI_KEYS[code] };
  return null;
}

/** 누르고 있는 이동 키. 같은 방향 키 두 개(W 와 ↑)는 따로 들고 있다가 둘 다 떼야 선다. */
export class InputState {
  constructor() {
    this.held = new Set();
  }

  /** 새로 누른 동작. 되풀이면 null (이동 키는 들고만 있는다 - 포커스가 돌아온 뒤 계속 누르고 있던 것). */
  keydown(e) {
    const a = keyAction(e.code);
    if (a && a.move) this.held.add(e.code);
    return e.repeat ? null : a;
  }

  keyup(e) {
    this.held.delete(e.code);
  }

  clear() {
    this.held.clear();
  }

  /** 이동 의도 (−1~1). 반대쪽 키는 서로 지우고, 대각선은 길이 1. */
  vector() {
    const dirs = new Set([...this.held].map((c) => MOVE_KEYS[c]));
    let x = (dirs.has('right') ? 1 : 0) - (dirs.has('left') ? 1 : 0);
    let y = (dirs.has('down') ? 1 : 0) - (dirs.has('up') ? 1 : 0);
    if (x && y) {
      x *= Math.SQRT1_2;
      y *= Math.SQRT1_2;
    }
    return { x, y };
  }
}

/** 이동 의도를 언제 보낼지. 바뀌면 바로, 움직이는 동안은 keepAlive 마다, 그래도 minGap 보다 자주는 안 보낸다. */
export class MoveSender {
  constructor(minGap = 1 / 60, keepAlive = 0.1) {
    this.minGap = minGap;
    this.keepAlive = keepAlive;
    this.reset();
  }

  reset() {
    this.last = { x: 0, y: 0 };
    this.lastT = -Infinity;
  }

  /** 지금 보낼 의도 (보낼 것이 없으면 null). 미룬 것은 다음 poll 에 간다. */
  poll(now, vec) {
    const changed = vec.x !== this.last.x || vec.y !== this.last.y;
    const moving = vec.x !== 0 || vec.y !== 0;
    if (!changed && !(moving && now - this.lastT >= this.keepAlive)) return null;
    if (now - this.lastT < this.minGap) return null;
    this.last = { x: vec.x, y: vec.y };
    this.lastT = now;
    return this.last;
  }

  /** 멈춤을 minGap 을 기다리지 않고 (걷고 있었을 때만). 숨은 창은 그리기(poll)가 멈춰서 미룰 수 없다. */
  stop(now) {
    if (this.last.x === 0 && this.last.y === 0) return null;
    this.last = { x: 0, y: 0 };
    this.lastT = now;
    return this.last;
  }
}

/** 판에서 움직여도 되나: 싸우는 중이고, 안 끝났고, 기권 확인 · 결과 창이 안 막고, 연결이 살아 있다.
    끊긴 뒤에도 움직이게 두면 서버는 모르는 걸음을 화면만 걸어간다. */
export function canAct({ snap, over, blocking, netDone }) {
  return !!snap && snap.ph === 'fight' && !over && !blocking && !netDone;
}

const isReload = (e) => e.code === 'F5' || (e.code === 'KeyR' && (e.ctrlKey || e.metaKey));
const isCmd = (code) => code === 'MetaLeft' || code === 'MetaRight';

/** 창에 키를 잇는다. handlers.key(e, 동작|null) 이 참을 돌려주면 그 키의 기본 동작(스크롤 등)을 막는다.
    handlers.live() 가 참이면(판이 도는 중) F5 · Ctrl/Cmd+R 새로고침을 막는다 - 입장권은 한 번만 쓰여 다시 못 들어온다.
    Cmd · Ctrl · Alt 와 같이 누른 키는 창 · 브라우저 단축키로 두고 넘기지 않는다. 맥은 Cmd 를 누른 채 뗀 키의 keyup 을
    안 주므로 Cmd 를 누르거나 떼면 눌린 키를 비운다. 되풀이는 이동 키만 넘긴다 (포커스가 돌아온 뒤 계속 누르고 있던
    것을 다시 든다) - Esc · 1~6 · Enter 를 누르고 있어도 창 · 고르기가 깜빡이지 않게. */
export function bindInput(win, doc, handlers) {
  win.addEventListener('keydown', (e) => {
    if (isReload(e) && handlers.live && handlers.live()) {
      e.preventDefault();
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) {
      if (e.metaKey) handlers.clear();
      return;
    }
    const a = keyAction(e.code);
    if (e.repeat && !(a && a.move)) {
      if (a) e.preventDefault();
      return;
    }
    if (handlers.key(e, a)) e.preventDefault();
  });
  win.addEventListener('keyup', (e) => {
    handlers.keyup(e);
    if (isCmd(e.code)) handlers.clear();
  });
  win.addEventListener('blur', () => handlers.clear());
  doc.addEventListener('visibilitychange', () => {
    if (doc.hidden) handlers.clear();
  });
}
