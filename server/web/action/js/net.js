/* 서버와 잇기 (/ws/action).

   입장권은 페이지 주소의 조각(#m=..&t=..)으로만 온다 - 조각은 서버 · 프록시 기록에 남지 않는다. 페이지는 읽자마자
   지우고(main), 소켓에는 **첫 메시지**로만 보낸다 (주소 쿼리 · 헤더에 싣지 않는다). 끊기면 다시 붙지 않는다 -
   입장권은 한 번만 쓰인다. 붙어 있는 동안 1초마다 핑(png)을 보내 왕복 시간을 잰다. */

const PING_EVERY = 1000;     // ms

/** '#m=12&t=abc' → {m, t}. 둘 중 하나라도 없으면 null. */
export function parseFragment(hash) {
  const q = new URLSearchParams(String(hash || '').replace(/^#/, ''));
  const m = q.get('m');
  const t = q.get('t');
  return m && t ? { m, t } : null;
}

export function wsUrl(loc) {
  return (loc.protocol === 'https:' ? 'wss://' : 'ws://') + loc.host + '/ws/action';
}

const CLOSE_KR = {
  4401: '입장권이 맞지 않습니다. 앱에서 다시 열어 주세요.',
  4409: '이 판은 끝났거나 다른 창에서 이어 하고 있습니다.',     // 서버는 새 창이 자리를 가져가도 옛 창을 4409 로 닫는다
  4429: '판이 너무 많거나 입력이 너무 많아 끊었습니다.',
};
// 그 밖(1006 끊김 · 1011 서버 오류 · 1001 떠남 …): 서버는 ACTION_GRACE(15초) 동안 자리를 잡아 둔다 - 이 창은 다시
// 못 붙으니(입장권은 한 번) 앱에서 새 입장권으로 들어오는 길을 적는다. 단추 이름은 앱(친구 탭)의 것과 같아야 한다.
const DROPPED = '연결이 끊겼습니다. 15초 안에 앱의 친구 탭에서 \'돌아가기\'를 누르면 이어 합니다.';

export function closeReason(code) {
  return CLOSE_KR[code] || DROPPED;
}

/** 소켓 하나. handlers.message(서버 메시지 객체) · handlers.close(닫는 코드). */
export class Net {
  constructor(url, ticket, handlers, Socket = globalThis.WebSocket) {
    this.handlers = handlers;
    this.queue = [];
    this.open = false;
    this.done = false;
    this.ping = 0;
    this.ws = new Socket(url);
    this.ws.onopen = () => {
      this.ws.send(JSON.stringify({ t: 'auth', ticket }));
      this.open = true;
      for (const s of this.queue.splice(0)) this.ws.send(s);
      this.ping = setInterval(() => this.send({ t: 'png', c: performance.now() / 1000 }), PING_EVERY);
    };
    this.ws.onmessage = (ev) => this.receive(ev.data);
    this.ws.onclose = (ev) => this.closed(ev.code);
  }

  receive(data) {
    if (typeof data !== 'string' || data === 'pong') return;
    let msg;
    try {
      msg = JSON.parse(data);
    } catch {
      return;
    }
    if (msg && typeof msg === 'object') this.handlers.message(msg);
  }

  send(obj) {
    if (this.done) return;
    const s = JSON.stringify(obj);
    if (this.open) this.ws.send(s);
    else this.queue.push(s);
  }

  closed(code) {
    if (this.done) return;
    this.done = true;
    clearInterval(this.ping);
    this.handlers.close(code);
  }

  close() {
    this.done = true;
    clearInterval(this.ping);
    this.ws.close();
  }
}
