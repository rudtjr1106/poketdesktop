/* 연결 검사 (js/net.js).

   무엇을 못 박나
     1. 입장권은 주소 조각(#m=..&t=..)에서만 읽는다. 없거나 깨졌으면 null.
     2. 소켓 주소에 입장권이 없다 (쿼리 · 조각 모두). https 면 wss.
     3. 연결되면 **첫 메시지**가 auth 다. 그 뒤에 쌓인 것을 보낸다.
     4. 서버가 닫은 까닭(4401 · 4409 · 4429)을 한국어로. 그냥 끊겼으면(1006 · 1011 · 1001) 앱에서 돌아가는 길을 적는다.
        4409 는 끝난 판만이 아니다 - 다른 창에서 다시 들어와도 옛 창이 받는다. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { parseFragment, wsUrl, closeReason, Net } from '../js/net.js';

test('주소 조각에서 판 번호와 입장권', () => {
  assert.deepEqual(parseFragment('#m=12&t=abc-DEF_9'), { m: '12', t: 'abc-DEF_9' });
  assert.deepEqual(parseFragment('#t=x%2By&m=3'), { m: '3', t: 'x+y' });
  assert.equal(parseFragment(''), null);
  assert.equal(parseFragment('#m=12'), null);
  assert.equal(parseFragment('#t=abc'), null);
});

test('소켓 주소 - 같은 호스트 /ws/action, 입장권 없이', () => {
  assert.equal(wsUrl({ protocol: 'https:', host: 'poket.example:8443' }), 'wss://poket.example:8443/ws/action');
  assert.equal(wsUrl({ protocol: 'http:', host: '127.0.0.1:8000' }), 'ws://127.0.0.1:8000/ws/action');
});

test('닫힌 까닭', () => {
  assert.match(closeReason(4401), /입장권/);
  assert.match(closeReason(4409), /끝났/);
  assert.match(closeReason(4409), /다른 창/);
  assert.match(closeReason(4429), /많/);
  for (const code of [1006, 1011, 1001, 1000, undefined]) {
    assert.match(closeReason(code), /끊겼/, String(code));
    assert.match(closeReason(code), /15초 안에 앱의 친구 탭에서 '돌아가기'/, String(code));
  }
});

class FakeSocket {
  constructor(url) { this.url = url; this.sent = []; this.readyState = 0; FakeSocket.last = this; }
  send(s) { this.sent.push(s); }
  close() { this.readyState = 3; }
  open() { this.readyState = 1; this.onopen(); }
  recv(obj) { this.onmessage({ data: typeof obj === 'string' ? obj : JSON.stringify(obj) }); }
}

test('첫 메시지는 auth, 그 앞에 보낸 것은 뒤로 미룬다', () => {
  const got = [];
  const net = new Net('ws://h/ws/action', 'TICKET', { message: (m) => got.push(m), close: () => {} }, FakeSocket);
  net.send({ t: 'png', c: 1 });
  const ws = FakeSocket.last;
  assert.equal(ws.url, 'ws://h/ws/action');
  assert.deepEqual(ws.sent, []);
  ws.open();
  assert.deepEqual(ws.sent.map((s) => JSON.parse(s)), [{ t: 'auth', ticket: 'TICKET' }, { t: 'png', c: 1 }]);
  ws.recv({ t: 'hello', you: 'a' });
  ws.recv('pong');                            // 글자 pong 은 넘긴다
  ws.recv('{깨진');
  assert.deepEqual(got, [{ t: 'hello', you: 'a' }]);
  net.close();
  net.send({ t: 'in' });
  assert.equal(ws.sent.length, 2);
});

test('닫히면 까닭 코드를 넘긴다 (다시 붙지 않는다)', () => {
  let closed = null;
  new Net('ws://h/ws/action', 'T', { message: () => {}, close: (code) => { closed = code; } }, FakeSocket);
  const ws = FakeSocket.last;
  ws.open();
  ws.onclose({ code: 4409 });
  assert.equal(closed, 4409);
});
