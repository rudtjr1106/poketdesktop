/* 화면 칸 검사 (js/hud.js · js/render.js · js/pick.js 의 순수 함수).

   무엇을 못 박나
     1. 남은 시간은 m:ss, 올림 (0.2초 남으면 0:01).
     2. 기술 칸: 못 쓰는 기술 · PP 0 은 회색에 까닭, 대기는 0~1 비율. 쓸 기술이 하나도 없으면 발버둥 (엔진의
        Mon.out_of_moves 와 같은 셈) - 네 칸 다 쓸 수 있게 보인다.
     3. 16:9 아레나는 창 가운데에, 남는 곳은 양옆이나 위아래로.
     4. 고르기: 6 중 3 을 고른 순서대로, 다시 누르면 뺀다, 넘치면 안 들어간다.
     5. 결과: 내 쪽에서 본 이겼다 / 졌다 / 무승부와 까닭. 기록 없이 접힌 판은 따로 (진 색이 아니다). */
import test from 'node:test';
import assert from 'node:assert/strict';
import { fmtClock, slotState, coolFrac, struggleOnly } from '../js/hud.js';
import { fitArena } from '../js/render.js';
import { togglePick } from '../js/pick.js';
import { resultText } from '../js/dialogs.js';

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
