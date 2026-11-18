/* DOM 창 셋: 기권 확인 · 결과 · 도움말. 다 키로 닫는다 (Enter · Esc).
   결과 창의 닫기는 창 자체를 닫는다 - 앱이 띄운 창이라 닫힌다. 안 닫히면(그냥 브라우저 탭) 닫아 달라고 적는다. */

/** 끝난 까닭을 내 쪽에서 본 한 줄. */
export function resultText(over, you) {
  const won = over.winner === you;
  const draw = over.winner === 'draw';
  const title = draw ? '무승부' : over.winner ? (won ? '이겼다!' : '졌다') : '판이 접혔다';
  const why = {
    ko: won ? '상대를 모두 쓰러뜨렸다' : '모두 쓰러졌다',
    timeout: '시간이 다 됐다 · 남은 마리 수 → 남은 체력으로 가렸다',
    forfeit: won ? '상대가 기권했다 (나갔다)' : '기권했다',
  }[over.reason] || '기록 없이 끝났다';
  // 기록 없이 접힌 판(winner null)은 진 것이 아니다 - 진 색(빨강)으로 칠하지 않는다
  const mood = draw ? 'draw' : !over.winner ? 'void' : won ? 'win' : 'lose';
  return { title, why: draw && over.reason !== 'timeout' ? '' : why, mood };
}

/** 초 → '2분' · '1분 30초' · '45초' (도움말의 판 길이). */
export function fmtLimit(sec) {
  const n = Math.max(0, Math.round(Number(sec) || 0));
  const m = Math.floor(n / 60);
  const r = n % 60;
  if (!m) return r + '초';
  return r ? m + '분 ' + r + '초' : m + '분';
}

export class Dialogs {
  constructor(doc, onForfeit) {
    this.confirm = doc.getElementById('confirm');
    this.result = doc.getElementById('result');
    this.help = doc.getElementById('help');
    this.onForfeit = onForfeit;
    this.confirm.querySelector('[data-yes]').onclick = () => this.forfeit();
    this.confirm.querySelector('[data-no]').onclick = () => this.hide(this.confirm);
    this.result.querySelector('[data-close]').onclick = () => this.closeWindow();
    this.help.querySelector('[data-close]').onclick = () => this.hide(this.help);
  }

  /** 판 길이를 도움말에 (intro.limits). */
  setLimits(limits) {
    const el = this.help.querySelector('[data-fight]');
    if (el && limits.fight > 0) el.textContent = fmtLimit(limits.fight);
  }

  /** 게임 키를 막는 창이 떠 있나 (도움말은 막지 않는다). */
  blocking() {
    return !this.confirm.hidden || !this.result.hidden;
  }

  hide(e) {
    e.hidden = true;
  }

  askForfeit() {
    if (this.result.hidden) this.confirm.hidden = false;
  }

  forfeit() {
    this.confirm.hidden = true;
    this.onForfeit();
  }

  toggleHelp() {
    this.help.hidden = !this.help.hidden;
  }

  showResult(over, you) {
    const r = resultText(over, you);
    this.confirm.hidden = true;
    this.result.querySelector('[data-title]').textContent = r.title;
    this.result.querySelector('[data-why]').textContent = r.why;
    this.result.dataset.mood = r.mood;
    this.result.hidden = false;
  }

  closeWindow() {
    window.close();
    setTimeout(() => {
      this.result.querySelector('[data-close]').textContent = '이 창을 닫아 주세요';
    }, 300);
  }

  /** 떠 있는 창이 받는 키. 받았으면 true. */
  key(code) {
    const enter = code === 'Enter' || code === 'NumpadEnter';
    if (!this.result.hidden) {
      if (enter || code === 'Escape') this.closeWindow();
      return true;
    }
    if (!this.confirm.hidden) {
      if (enter || code === 'KeyY') this.forfeit();
      else if (code === 'Escape' || code === 'KeyN') this.hide(this.confirm);
      return true;
    }
    if (!this.help.hidden && (code === 'Escape' || enter)) {
      this.hide(this.help);
      return true;
    }
    return false;
  }
}
