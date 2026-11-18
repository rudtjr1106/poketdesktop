/* 키 입력 검사 (js/input.js).

     node --test server/web/action/test/

   무엇을 못 박나
     1. 키는 물리 자리(event.code)로 읽는다. 한글 입력 상태라 key 가 'Process' 여도 같다.
     2. 두 벌(WASD+JKUI · 방향키+ZXCV) 다 된다. 같은 쪽 두 키를 같이 눌러도 한 번만 센다.
     3. 누른 채 들어오는 되풀이(repeat)는 버린다 - 기술이 두 번 나가지 않는다.
     4. 창이 포커스를 잃으면 눌린 키를 비운다 - 계속 걸어가지 않는다.
     5. 이동 보내기는 바뀌면 바로, 움직이는 동안은 0.1초마다, 1초에 60번을 넘지 않는다.
     6. 되풀이는 창 · 고르기 · 메뉴 키에도 가지 않는다 (Esc 를 누르고 있으면 기권 확인이 깜빡이지 않게). 이동 키만 간다.
     7. Cmd · Ctrl · Alt 와 같이 누른 키는 게임 키가 아니다. Cmd 를 누르거나 떼면 눌린 키를 비운다 (맥은 Cmd 를 누른 채
        뗀 키의 keyup 을 안 준다).
     8. 판이 도는 동안 F5 · Ctrl/Cmd+R 은 막는다 (입장권은 한 번만 쓰여 새로 불러오면 못 돌아온다).
     9. 연결이 끊긴 뒤에는 싸우는 중이어도 움직이지 않는다. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { keyAction, InputState, MoveSender, bindInput, canAct, slotOf, teamSlotOf } from '../js/input.js';
import { SLOT_KEYS } from '../js/consts.js';

const ev = (code, extra = {}) => ({
  code, key: extra.key ?? code, repeat: !!extra.repeat,
  metaKey: !!extra.metaKey, ctrlKey: !!extra.ctrlKey, altKey: !!extra.altKey,
});

// 가짜 창 · 문서에 bindInput 을 잇고, 넘어온 키 · 막은 키 · 비운 횟수를 센다
function bound(more = {}) {
  const on = {};
  const fakeTarget = (name) => ({ addEventListener: (t, fn) => { on[name + ':' + t] = fn; } });
  const r = { got: [], ups: [], prevented: [], cleared: 0 };
  bindInput(fakeTarget('win'), Object.assign(fakeTarget('doc'), { hidden: false }), {
    key: (e, a) => { r.got.push(e.code); return !!a; },
    keyup: (e) => { r.ups.push(e.code); },
    clear: () => { r.cleared += 1; },
    ...more,
  });
  r.down = (code, extra = {}) => on['win:keydown']({ ...ev(code, extra), preventDefault: () => { r.prevented.push(code); } });
  r.up = (code, extra = {}) => on['win:keyup'](ev(code, extra));
  return r;
}

test('물리 키 자리로 읽는다 (한글 입력 상태의 Process 키도)', () => {
  assert.deepEqual(keyAction('KeyW'), { move: 'up' });
  assert.deepEqual(keyAction('ArrowLeft'), { move: 'left' });
  assert.deepEqual(keyAction('KeyJ'), { act: 'm0' });
  assert.deepEqual(keyAction('KeyV'), { act: 'm3' });
  assert.deepEqual(keyAction('Space'), { act: 'dodge' });
  assert.deepEqual(keyAction('ShiftRight'), { act: 'dodge' });
  assert.deepEqual(keyAction('Digit2'), { act: 'sw1' });
  assert.deepEqual(keyAction('Numpad3'), { act: 'sw2' });
  assert.deepEqual(keyAction('Escape'), { ui: 'menu' });
  assert.equal(keyAction('KeyQ'), null);
  const s = new InputState();
  assert.deepEqual(s.keydown(ev('KeyW', { key: 'Process' })), { move: 'up' });
  assert.deepEqual(s.vector(), { x: 0, y: -1 });
  assert.deepEqual(s.keydown(ev('KeyU', { key: 'ㅕ' })), { act: 'm2' });
});

test('두 벌 배치 - 기술 네 칸 · 피하기 · 교체가 양쪽에서 같다', () => {
  const pairs = [['KeyJ', 'KeyZ'], ['KeyK', 'KeyX'], ['KeyU', 'KeyC'], ['KeyI', 'KeyV'],
    ['Space', 'ShiftLeft'], ['KeyW', 'ArrowUp'], ['KeyA', 'ArrowLeft'], ['KeyS', 'ArrowDown'], ['KeyD', 'ArrowRight']];
  for (const [a, b] of pairs) assert.deepEqual(keyAction(a), keyAction(b), a + ' = ' + b);
});

test('이동 벡터 - 8방향, 대각선은 길이 1, 반대쪽은 지운다', () => {
  const s = new InputState();
  s.keydown(ev('KeyD'));
  assert.deepEqual(s.vector(), { x: 1, y: 0 });
  s.keydown(ev('KeyS'));
  const v = s.vector();
  assert.ok(Math.abs(Math.hypot(v.x, v.y) - 1) < 1e-9);
  assert.ok(v.x > 0 && v.y > 0);
  s.keydown(ev('KeyA'));
  assert.deepEqual(s.vector(), { x: 0, y: 1 });
  s.keyup(ev('KeyS'));
  s.keyup(ev('KeyA'));
  assert.deepEqual(s.vector(), { x: 1, y: 0 });
});

test('같은 방향 두 키 - 하나를 떼도 계속 간다', () => {
  const s = new InputState();
  s.keydown(ev('KeyW'));
  s.keydown(ev('ArrowUp'));
  s.keyup(ev('KeyW'));
  assert.deepEqual(s.vector(), { x: 0, y: -1 });
  s.keyup(ev('ArrowUp'));
  assert.deepEqual(s.vector(), { x: 0, y: 0 });
});

test('되풀이(repeat) 는 버린다', () => {
  const s = new InputState();
  assert.deepEqual(s.keydown(ev('KeyJ')), { act: 'm0' });
  assert.equal(s.keydown(ev('KeyJ', { repeat: true })), null);
  assert.equal(s.keydown(ev('KeyW', { repeat: true })), null);
});

test('모르는 키는 아무것도 안 한다', () => {
  const s = new InputState();
  assert.equal(s.keydown(ev('KeyQ')), null);
  assert.deepEqual(s.vector(), { x: 0, y: 0 });
});

test('포커스를 잃으면 눌린 키를 비운다', () => {
  const s = new InputState();
  s.keydown(ev('KeyD'));
  s.keydown(ev('ArrowUp'));
  s.clear();
  assert.deepEqual(s.vector(), { x: 0, y: 0 });
});

test('bindInput - blur · 숨김에 키를 비우고, 받은 키만 기본 동작을 막는다', () => {
  const handlers = {};
  const fakeTarget = (name) => ({ addEventListener: (t, fn) => { handlers[name + ':' + t] = fn; } });
  const win = fakeTarget('win');
  const doc = Object.assign(fakeTarget('doc'), { hidden: false });
  const got = [];
  const ups = [];
  let cleared = 0;
  bindInput(win, doc, {
    key: (e, a) => { got.push([e.code, a]); return !!a; },
    keyup: (e) => { ups.push(e.code); },
    clear: () => { cleared += 1; },
  });
  let prevented = 0;
  const down = (code, extra = {}) => handlers['win:keydown']({ ...ev(code, extra), preventDefault: () => { prevented += 1; } });
  down('KeyW', { key: 'Process' });
  down('KeyQ');                               // 모르는 키도 넘긴다 (고르기 화면의 4~6 · Enter)
  assert.deepEqual(got, [['KeyW', { move: 'up' }], ['KeyQ', null]]);
  assert.equal(prevented, 1);
  handlers['win:keyup'](ev('KeyW'));
  assert.deepEqual(ups, ['KeyW']);
  handlers['win:blur']();
  assert.equal(cleared, 1);
  doc.hidden = true;
  handlers['doc:visibilitychange']();
  assert.equal(cleared, 2);
  // 되풀이: 창 · 고르기 · 메뉴 키는 넘기지 않는다 (게임 키면 기본 동작만 막는다), 이동 키는 넘긴다
  got.length = 0;
  prevented = 0;
  down('Escape', { repeat: true });
  down('Digit4', { repeat: true });
  down('Enter', { repeat: true });
  down('KeyJ', { repeat: true });
  assert.deepEqual(got, [], '되풀이한 Esc · 4 · Enter · J 는 키 처리로 가지 않는다');
  assert.equal(prevented, 2, 'Esc · J 는 게임 키라 기본 동작만 막는다');
  down('KeyD', { repeat: true });
  assert.deepEqual(got, [['KeyD', { move: 'right' }]], '되풀이한 이동 키는 간다 (포커스가 돌아온 뒤 다시 든다)');
});

test('Cmd · Ctrl · Alt 와 같이 누른 키는 게임 키가 아니다 - Cmd 를 누르거나 떼면 눌린 키를 비운다', () => {
  const r = bound();
  r.down('KeyH', { metaKey: true });
  r.down('ShiftLeft', { metaKey: true });
  r.down('Digit4', { metaKey: true });        // Cmd+Shift+4 (화면 찍기) - Shift 가 피하기로 가지 않는다
  r.down('KeyJ', { ctrlKey: true });
  r.down('Space', { altKey: true });
  assert.deepEqual(r.got, [], '키 처리로 가지 않는다');
  assert.deepEqual(r.prevented, [], '창 · 브라우저 단축키는 그대로 둔다');
  assert.equal(r.cleared, 3, 'Cmd 를 누른 채 들어온 키마다 비운다');
  r.up('KeyW');
  assert.equal(r.cleared, 3);
  r.up('MetaLeft');
  r.up('MetaRight');
  assert.equal(r.cleared, 5, 'Cmd 를 떼면 비운다');
  assert.deepEqual(r.ups, ['KeyW', 'MetaLeft', 'MetaRight']);
  r.down('KeyH');
  assert.deepEqual(r.got, ['KeyH'], '혼자 누른 H 는 도움말');
});

test('판이 도는 동안 F5 · Ctrl/Cmd+R 은 막는다', () => {
  let live = true;
  const r = bound({ live: () => live });
  r.down('F5');
  r.down('F5', { ctrlKey: true });
  r.down('KeyR', { ctrlKey: true });
  r.down('KeyR', { metaKey: true });
  assert.deepEqual(r.prevented, ['F5', 'F5', 'KeyR', 'KeyR'], '새로고침을 막는다');
  assert.deepEqual(r.got, [], '키 처리로 가지 않는다');
  r.down('KeyR');
  assert.deepEqual(r.got, ['KeyR'], '혼자 누른 R 은 그냥 키');
  live = false;
  r.prevented.length = 0;
  r.down('F5');
  r.down('KeyR', { metaKey: true });
  assert.deepEqual(r.prevented, [], '판이 끝났으면 새로고침을 막지 않는다');
  const plain = bound();                      // live 를 안 주면 막지 않는다
  plain.down('KeyR', { ctrlKey: true });
  assert.deepEqual(plain.prevented, []);
});

test('움직여도 되나 - 싸우는 중 · 안 끝남 · 창이 안 막음 · 연결이 살아 있음', () => {
  const fight = { ph: 'fight' };
  assert.equal(canAct({ snap: fight, over: null, blocking: false, netDone: false }), true);
  assert.equal(canAct({ snap: fight, over: null, blocking: false, netDone: true }), false, '끊긴 뒤에는 못 움직인다');
  assert.equal(canAct({ snap: fight, over: { winner: 'a' }, blocking: false, netDone: false }), false);
  assert.equal(canAct({ snap: fight, over: null, blocking: true, netDone: false }), false);
  assert.equal(canAct({ snap: { ph: 'ready' }, over: null, blocking: false, netDone: false }), false);
  assert.equal(canAct({ snap: null, over: null, blocking: false, netDone: false }), false);
});

test('이동 보내기 - 바뀌면 바로', () => {
  const m = new MoveSender();
  assert.deepEqual(m.poll(1.0, { x: 1, y: 0 }), { x: 1, y: 0 });
  assert.deepEqual(m.poll(1.05, { x: 0, y: 0 }), { x: 0, y: 0 });
});

test('이동 보내기 - 가만히 있으면 안 보낸다, 움직이는 동안은 0.1초마다', () => {
  const m = new MoveSender();
  assert.equal(m.poll(0.5, { x: 0, y: 0 }), null);
  assert.ok(m.poll(1.0, { x: 0, y: 1 }));
  assert.equal(m.poll(1.05, { x: 0, y: 1 }), null);
  assert.deepEqual(m.poll(1.101, { x: 0, y: 1 }), { x: 0, y: 1 });
  m.poll(1.2, { x: 0, y: 0 });
  assert.equal(m.poll(2.0, { x: 0, y: 0 }), null);
});

test('이동 보내기 - 1초에 60번을 넘지 않는다 (미룬 것은 다음에 간다)', () => {
  const m = new MoveSender();
  let sent = 0;
  let last = null;
  for (let i = 0; i < 1000; i += 1) {
    const t = i / 1000;                       // 1ms 마다 방향을 바꾼다
    const v = i % 2 ? { x: 1, y: 0 } : { x: -1, y: 0 };
    const out = m.poll(t, v);
    if (out) { sent += 1; last = out; }
  }
  assert.ok(sent <= 61, '보낸 수 ' + sent);
  assert.ok(sent >= 50, '보낸 수 ' + sent);
  assert.ok(last);
  const out = m.poll(2.0, { x: 0, y: 0 });
  assert.deepEqual(out, { x: 0, y: 0 });
});

test('이동 보내기 - 멈춤은 바로 (포커스를 잃은 창은 그리기가 멈춰 다음 차례가 안 온다)', () => {
  const m = new MoveSender();
  assert.equal(m.stop(1.0), null);            // 서 있었으면 보낼 것이 없다
  m.poll(1.0, { x: 1, y: 0 });
  assert.deepEqual(m.stop(1.001), { x: 0, y: 0 });   // 1/60초 안이어도
  assert.equal(m.stop(1.002), null);
  assert.equal(m.poll(1.5, { x: 0, y: 0 }), null);
});

test('이동 보내기 - reset 뒤에는 다시 처음부터', () => {
  const m = new MoveSender();
  m.poll(1.0, { x: 1, y: 0 });
  m.reset();
  assert.deepEqual(m.poll(1.001, { x: 1, y: 0 }), { x: 1, y: 0 });
});

test('기본 키 Z X C V → 기술 칸 0~3 (칸에 적는 글자도 그 차례)', () => {
  const codes = ['KeyZ', 'KeyX', 'KeyC', 'KeyV'];
  codes.forEach((c, m) => {
    assert.equal(slotOf(keyAction(c).act), m);
    assert.equal('Key' + SLOT_KEYS[m], c, '칸 ' + m + ' 의 글자');
  });
  assert.equal(slotOf('dodge'), -1);
  assert.equal(slotOf('m4'), -1);
  assert.equal(slotOf(undefined), -1);
  assert.equal(teamSlotOf(keyAction('Digit2').act), 1);
  assert.equal(teamSlotOf('m1'), -1);
});
