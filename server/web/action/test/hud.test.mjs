/* 화면 칸 검사 (js/hud.js · js/render.js · js/pick.js 의 순수 함수).

   무엇을 못 박나
     1. 남은 시간은 m:ss, 올림 (0.2초 남으면 0:01).
     2. 기술 칸: 못 쓰는 기술 · PP 0 은 회색에 까닭, 대기는 0~1 비율. 쓸 기술이 하나도 없으면 발버둥 (엔진의
        Mon.out_of_moves 와 같은 셈) - 네 칸 다 쓸 수 있게 보인다.
     3. 16:9 아레나는 창 가운데에, 남는 곳은 양옆이나 위아래로.
     4. 고르기: 6 중 3 을 고른 순서대로, 다시 누르면 뺀다, 넘치면 안 들어간다.
     5. 결과: 내 쪽에서 본 이겼다 / 졌다 / 무승부와 까닭. 기록 없이 접힌 판은 따로 (진 색이 아니다).
     6~8. 아래 조작 띠 · 누름 (맨 아래). */
import test from 'node:test';
import assert from 'node:assert/strict';
import { fmtClock, slotState, coolFrac, struggleOnly } from '../js/hud.js';
import { fitArena } from '../js/render.js';
import { togglePick } from '../js/pick.js';
import { resultText, fmtLimit } from '../js/dialogs.js';
import { pressVerdict, pressLook, stripLayout, fmtCd, PRESS_FLASH, SHAKE_SEC, REASON_SEC } from '../js/hud.js';
import { SLOT_KEYS, SLOT_ALT, ARENA_W, ARENA_H } from '../js/consts.js';
import { keyAction } from '../js/input.js';

test('남은 시간', () => {
  assert.equal(fmtClock(161), '2:41');
  assert.equal(fmtClock(0.2), '0:01');
  assert.equal(fmtClock(60), '1:00');
  assert.equal(fmtClock(-3), '0:00');
  assert.equal(fmtClock(null), '');
});

test('기술 칸 - 회색과 까닭', () => {
  const mv = { key: 'THUNDERBOLT', kr: '10만볼트', ok: true, why: '', cd: 4, pp: 8 };
  assert.deepEqual(slotState(mv, 0, 8), { grey: false, reason: '', frac: 0 });
  assert.deepEqual(slotState(mv, 2, 8), { grey: false, reason: '', frac: 0.5 });
  assert.deepEqual(slotState(mv, 1, 0), { grey: true, reason: 'PP 없음', frac: 0.25 });
  const bad = { ...mv, key: 'BATONPASS', ok: false, why: '턴제에서만 뜻이 있다' };
  assert.deepEqual(slotState(bad, 0, 8), { grey: true, reason: '턴제에서만 뜻이 있다', frac: 0 });
  assert.equal(slotState({ ...bad, why: '' }, 0, 8).reason, '쓸 수 없다');
  assert.deepEqual(slotState(null, 0, 0), { grey: true, reason: '', frac: 0 });
});

test('발버둥 - 쓸 기술(ok · PP 남음)이 하나도 없을 때만', () => {
  const mv = (ok) => ({ key: 'X', kr: 'X', ok, why: ok ? '' : '턴제에서만 뜻이 있다', cd: 2, pp: 8 });
  assert.equal(struggleOnly([mv(false), mv(false), mv(false), mv(false)], [8, 8, 8, 8]), true, '다 못 쓰는 기술');
  assert.equal(struggleOnly([mv(true), mv(true), mv(true), mv(true)], [0, 0, 0, 0]), true, 'PP 가 다 떨어졌다');
  assert.equal(struggleOnly([mv(false)], [8]), true, '변신만 가진 메타몽');
  assert.equal(struggleOnly([mv(false), mv(true), mv(true)], [8, 0, 1]), false, '하나라도 쓸 수 있으면 아니다');
  assert.equal(struggleOnly([mv(true), null], [3, 0]), false);
});

test('대기 비율', () => {
  assert.equal(coolFrac(0.8, 1.6), 0.5);
  assert.equal(coolFrac(3, 1.6), 1);
  assert.equal(coolFrac(-1, 1.6), 0);
  assert.equal(coolFrac(1, 0), 0);
  assert.equal(coolFrac(undefined, 6), 0);
});

test('아레나 맞추기 - 16:9 를 가운데에', () => {
  assert.deepEqual(fitArena(1600, 900), { s: 1, ox: 0, oy: 0 });
  const wide = fitArena(2000, 900);
  assert.equal(wide.s, 1);
  assert.equal(wide.ox, 200);
  assert.equal(wide.oy, 0);
  const tall = fitArena(800, 900);
  assert.equal(tall.s, 0.5);
  assert.equal(tall.ox, 0);
  assert.equal(tall.oy, 225);
});

test('고르기 - 고른 순서대로, 다시 누르면 뺀다, 넘치면 안 들어간다', () => {
  let sel = [];
  sel = togglePick(sel, 4, 3);
  sel = togglePick(sel, 0, 3);
  sel = togglePick(sel, 2, 3);
  assert.deepEqual(sel, [4, 0, 2]);
  assert.deepEqual(togglePick(sel, 5, 3), [4, 0, 2]);
  assert.deepEqual(togglePick(sel, 0, 3), [4, 2]);
  assert.deepEqual(togglePick([], 1, 2), [1]);
});

test('결과 - 내 쪽에서 본 글', () => {
  assert.deepEqual(resultText({ winner: 'a', reason: 'ko' }, 'a'), { title: '이겼다!', why: '상대를 모두 쓰러뜨렸다', mood: 'win' });
  assert.deepEqual(resultText({ winner: 'a', reason: 'ko' }, 'b'), { title: '졌다', why: '모두 쓰러졌다', mood: 'lose' });
  assert.equal(resultText({ winner: 'b', reason: 'forfeit' }, 'b').why, '상대가 기권했다 (나갔다)');
  assert.equal(resultText({ winner: 'b', reason: 'forfeit' }, 'a').why, '기권했다');
  const draw = resultText({ winner: 'draw', reason: 'timeout' }, 'a');
  assert.equal(draw.title, '무승부');
  assert.match(draw.why, /시간/);
  assert.equal(resultText({ winner: null, reason: 'aborted' }, 'a').title, '판이 접혔다');
  assert.equal(resultText({ winner: null, reason: 'noshow' }, 'a').mood, 'void', '접힌 판은 진 색이 아니다');
  assert.equal(resultText({ winner: null, reason: 'error' }, 'b').mood, 'void');
});

/* ---------------------------------------------------------------- 조작 띠 · 누름 (2026-11-19)
     6. 기본 키는 Z X C V - 칸 차례도 그대로 (한 줄, 가운데). 피하기 Shift 는 Z 왼쪽, 교체 1 2 3 은 V 오른쪽.
        칸은 옛것(236×60)의 1.6~1.8배. 위 체력 칸과 겹치지 않는다.
     7. 누름: 못 쓰는 칸('대기 중' · 'PP 없음' · '못 씀')은 안 보내고 흔든다. 대기가 (왕복을 빼고) 0.25초 안이면 보낸다 -
        서버가 들고 있다가 쓴다. 바로 쓸 수 있으면 (대기 0 · 서 있음) 준비 몸짓을 먼저 그려도 된다.
     8. 누른 칸은 바로 반짝, 못 쓰면 0.3초 흔들리고 까닭이 0.8초 떠 있다. */

test('조작 띠 - Z X C V 한 줄 가운데, 왼쪽 Shift 피하기, 오른쪽 교체 셋', () => {
  assert.deepEqual(SLOT_KEYS, ['Z', 'X', 'C', 'V']);
  assert.deepEqual(SLOT_ALT, ['J', 'K', 'U', 'I']);
  const L = stripLayout(3);
  const ys = new Set([L.dodge, ...L.moves, ...L.cards].map((r) => r.y));
  assert.equal(ys.size, 1, '한 줄');
  for (let m = 1; m < 4; m++) assert.ok(L.moves[m].x > L.moves[m - 1].x + L.moves[m - 1].w, '왼쪽부터 Z X C V, 안 겹친다');
  const mid = (L.moves[0].x + L.moves[3].x + L.moves[3].w) / 2;
  assert.ok(Math.abs(mid - ARENA_W / 2) < 1, '기술 칸은 가운데');
  const area = L.moves[0].w * L.moves[0].h;
  assert.ok(area >= 236 * 60 * 1.6 && area <= 236 * 60 * 1.8, '옛 칸의 1.6~1.8배 (' + (area / (236 * 60)).toFixed(2) + ')');
  assert.ok(L.dodge.x + L.dodge.w < L.moves[0].x, '피하기는 Z 왼쪽');
  assert.ok(L.cards[0].x > L.moves[3].x + L.moves[3].w, '교체는 V 오른쪽');
  for (let j = 1; j < 3; j++) assert.ok(L.cards[j].x > L.cards[j - 1].x + L.cards[j - 1].w);
  assert.ok(L.dodge.x >= 20 && L.cards[2].x + L.cards[2].w <= ARENA_W - 20, '아레나 안 (양옆 20)');
  assert.ok(L.box.y + L.box.h <= ARENA_H - 10 && L.box.y > 100 + 14, '아래 끝 · 위 체력 칸과 안 겹친다');
  assert.equal(stripLayout(1).cards.length, 1);
});

test('키 → 칸: Z X C V (와 J K U I) 가 m0~m3', () => {
  ['KeyZ', 'KeyX', 'KeyC', 'KeyV'].forEach((c, m) => assert.deepEqual(keyAction(c), { act: 'm' + m }));
  ['KeyJ', 'KeyK', 'KeyU', 'KeyI'].forEach((c, m) => assert.deepEqual(keyAction(c), { act: 'm' + m }));
  assert.deepEqual(keyAction('ShiftLeft'), { act: 'dodge' });
});

const MV = (extra = {}) => ({ key: 'EMBER', kr: '불꽃세례', type: 'FIRE', kind: 'proj', ok: true, why: '', cd: 2, pp: 13, ...extra });
const ME = (extra = {}) => ({
  i: 0, st: 'idle', sm: -1, cd: [0, 0, 0, 0], pp: [13, 13, 13, 13], dcd: 0, scd: 0, need: false,
  team: [{ hpr: 1000, ko: false }, { hpr: 500, ko: false }, { hpr: 0, ko: true }], ...extra,
});
const moves4 = [MV(), MV({ kind: 'melee', type: 'FIGHTING' }), MV({ ok: false, why: '턴제에서만 뜻이 있다', kind: 'none' }), MV()];

test('누름 - 쓸 수 있으면 보내고, 바로 쓸 수 있으면 준비 몸짓도', () => {
  const v = pressVerdict('m0', { me: ME(), moves: moves4, age: 0, rtt: 0.05 });
  assert.deepEqual(v, { send: true, ok: true, reason: '', predict: true, kind: 'proj', ty: 'FIRE' });
  assert.equal(pressVerdict('m1', { me: ME({ st: 'walk' }), moves: moves4, age: 0, rtt: 0.05 }).kind, 'melee');
  // 이미 무언가 하고 있으면 보내되 (서버가 들고 있다) 몸짓은 미루지 않는다
  const busy = pressVerdict('m0', { me: ME({ st: 'rec' }), moves: moves4, age: 0, rtt: 0.05 });
  assert.equal(busy.send, true);
  assert.equal(busy.predict, false);
});

test('누름 - 못 쓰는 칸은 안 보내고 까닭 (대기 중 · PP 없음 · 못 씀)', () => {
  const s = (me, extra = {}) => ({ me, moves: moves4, age: 0, rtt: 0.05, ...extra });
  assert.deepEqual(pressVerdict('m2', s(ME())), { send: false, ok: false, reason: '못 씀', predict: false });
  assert.equal(pressVerdict('m0', s(ME({ pp: [0, 13, 13, 13] }))).reason, 'PP 없음');
  assert.equal(pressVerdict('m0', s(ME({ cd: [1.5, 0, 0, 0] }))).reason, '대기 중');
  assert.equal(pressVerdict('m0', s(ME({ cd: [1.5, 0, 0, 0] }))).send, false);
  // 마지막 모습 뒤 흐른 시간을 뺀다
  assert.equal(pressVerdict('m0', s(ME({ cd: [1.5, 0, 0, 0] }), { age: 1.4 })).send, true);
  // 대기가 거의 끝났으면 (왕복을 빼고 0.25초 안) 보낸다 - 몸짓은 안 미룬다
  const soon = pressVerdict('m0', s(ME({ cd: [0.3, 0, 0, 0] }), { rtt: 0.1 }));
  assert.equal(soon.send, true);
  assert.equal(soon.predict, false);
  assert.equal(pressVerdict('m0', s(ME({ cd: [0.45, 0, 0, 0] }), { rtt: 0.1 })).send, false);
  assert.equal(pressVerdict('m0', s(ME({ cd: [0.45, 0, 0, 0] }), { rtt: 0.3 })).send, true, '핑이 크면 그만큼 일찍');
  assert.equal(pressVerdict('m0', s(ME({ cd: [0.3, 0, 0, 0] }), { rtt: null })).send, true, '핑을 모르면 0.1초로');
  assert.equal(pressVerdict('m3', { me: ME(), moves: moves4.slice(0, 3), age: 0, rtt: 0 }).reason, '못 씀', '빈 칸');
  assert.equal(pressVerdict('m0', s(null)).send, false);
  assert.equal(pressVerdict('m0', s(ME({ need: true, st: 'ko' }))).send, false);
});

test('누름 - 발버둥만 남으면 네 칸 다 보낸다 (가장 긴 대기를 같이 쓴다)', () => {
  const dead = [MV(), MV()];
  const me = ME({ pp: [0, 0], cd: [0, 0] });
  const v = pressVerdict('m3', { me, moves: dead, age: 0, rtt: 0.05 });
  assert.equal(v.send, true);
  assert.equal(v.kind, 'melee');
  const cooling = pressVerdict('m3', { me: ME({ pp: [0, 0], cd: [0, 2.5] }), moves: dead, age: 0, rtt: 0.05 });
  assert.deepEqual([cooling.send, cooling.reason], [false, '대기 중']);
});

test('누름 - 피하기 · 교체', () => {
  const s = (me) => ({ me, moves: moves4, age: 0, rtt: 0.05 });
  assert.equal(pressVerdict('dodge', s(ME())).send, true);
  assert.deepEqual([pressVerdict('dodge', s(ME({ dcd: 1.2 }))).send, pressVerdict('dodge', s(ME({ dcd: 1.2 }))).reason], [false, '대기 중']);
  assert.equal(pressVerdict('sw1', s(ME())).send, true);
  assert.equal(pressVerdict('sw0', s(ME())).reason, '나와 있음');
  assert.equal(pressVerdict('sw2', s(ME())).reason, '기절');
  assert.equal(pressVerdict('sw1', s(ME({ scd: 4 }))).reason, '대기 중');
  assert.equal(pressVerdict('sw1', s(ME({ scd: 4, need: true, i: 0, st: 'ko' }))).send, true, '쓰러진 뒤 고르기는 대기가 없다');
  assert.equal(pressVerdict('sw2', { me: ME({ team: [{ hpr: 1, ko: false }] }), moves: moves4, age: 0 }).reason, '없음');
});

test('누른 칸의 모습 - 바로 반짝, 못 쓰면 흔들리고 까닭이 잠깐', () => {
  const ok = { at: 10, ok: true, reason: '' };
  assert.equal(pressLook(ok, 10).flash, 1);
  assert.ok(pressLook(ok, 10 + PRESS_FLASH / 2).flash > 0);
  assert.equal(pressLook(ok, 10 + PRESS_FLASH + 0.01).flash, 0);
  assert.equal(pressLook(ok, 10.05).dx, 0);
  const bad = { at: 10, ok: false, reason: '대기 중' };
  assert.ok(Math.abs(pressLook(bad, 10.03).dx) > 1, '흔들린다');
  assert.equal(pressLook(bad, 10 + SHAKE_SEC + 0.01).dx, 0);
  assert.equal(pressLook(bad, 10.1).reason, '대기 중');
  assert.equal(pressLook(bad, 10.1).reasonA, 1);
  assert.ok(pressLook(bad, 10 + REASON_SEC - 0.1).reasonA < 1);
  assert.equal(pressLook(bad, 10 + REASON_SEC + 0.01).reason, '');
  assert.deepEqual(pressLook(null, 10), { flash: 0, dx: 0, reason: '', reasonA: 0 });
  assert.equal(pressLook(bad, 9).dx, 0, '앞날은 없다');
});

test('대기 글 · 판 길이', () => {
  assert.equal(fmtCd(1.23), '1.3');
  assert.equal(fmtCd(0.04), '0.1');
  assert.equal(fmtCd(12.2), '13');
  assert.equal(fmtCd(0), '');
  assert.equal(fmtCd(-1), '');
  assert.equal(fmtLimit(120), '2분');
  assert.equal(fmtLimit(90), '1분 30초');
  assert.equal(fmtLimit(45), '45초');
});
