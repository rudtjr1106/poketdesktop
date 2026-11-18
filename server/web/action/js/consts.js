/* 액션 배틀 화면이 같이 쓰는 값. 판 상수는 common/action_battle.py 와 같아야 한다. */

export const ARENA_W = 1600;
export const ARENA_H = 900;
export const BODY_R = 26;
export const TEAM = 3;
export const LEVEL = 50;
export const SWITCH_CD = 6;
// 발버둥의 대기 (초) - common/action_moves.kit(dex, 'STRUGGLE')['cd'] 와 같아야 한다. 쓰면 네 칸이 같이 막힌다.
export const STRUGGLE_CD = 3.15;
// 발버둥의 꼴 (몸짓 고르기)
export const STRUGGLE_KIND = 'melee';
// 서버 모습을 이만큼 뒤에서 그린다 (초). 두 모습 사이를 이어 그릴 여유다.
export const INTERP_DELAY = 0.08;

export const FONT = "'Apple SD Gothic Neo','Malgun Gothic',sans-serif";

/* 키 배치 (v1 은 못 바꾼다). event.code - 물리 키 자리라 한글 입력 상태여도 같다.
   기본은 방향키 + Z X C V (기술) · 1 2 3 (교체) - 화면 칸에는 이것만 적는다.
   W A S D · J K U I 도 똑같이 되고, 도움말(H) · 고르기 화면 아래에만 '이것도 된다' 로 적는다.
   피하기(Space · Shift)는 뺐다 (2026-11-19) - 걸어서 비킨다. 두 키는 아무 일도 안 한다. */
export const MOVE_KEYS = {
  KeyW: 'up', KeyA: 'left', KeyS: 'down', KeyD: 'right',
  ArrowUp: 'up', ArrowLeft: 'left', ArrowDown: 'down', ArrowRight: 'right',
};
export const ACT_KEYS = {
  KeyJ: 'm0', KeyK: 'm1', KeyU: 'm2', KeyI: 'm3',
  KeyZ: 'm0', KeyX: 'm1', KeyC: 'm2', KeyV: 'm3',
  Digit1: 'sw0', Digit2: 'sw1', Digit3: 'sw2',
  Numpad1: 'sw0', Numpad2: 'sw1', Numpad3: 'sw2',
};
export const UI_KEYS = { Escape: 'menu', KeyH: 'help', Slash: 'help' };
// 기술 칸에 크게 적는 글자 (기본 벌) 와 같은 일을 하는 다른 벌 (도움말에만)
export const SLOT_KEYS = ['Z', 'X', 'C', 'V'];
export const SLOT_ALT = ['J', 'K', 'U', 'I'];
export const MOVE_HINT = '방향키';
// 엔진이 바쁠 때 · 대기 중에 누른 키를 들고 있는 시간 (common/action_battle.BUFFER_SEC) - 대기가 이만큼(+왕복) 안 남았으면
// 보낸다 (서버가 들고 있다가 쓴다). 그보다 많이 남았으면 안 보내고 칸만 흔든다.
export const PRESS_GRACE = 0.25;

/* 타입 색. TYPE_FX 는 이펙트의 (밝은색, 어두운색) - client/poketdesktop/battle_fx.py 의 것을 옮겼다.
   TYPE_COLOR 는 칸 · 글씨 바탕 (ui_common.TYPE_COLOR). */
export const TYPE_FX = {
  NORMAL: ['#f2f0e4', '#b9b5a0'],
  FIRE: ['#ffd24a', '#ff5b2e'],
  WATER: ['#8ec9ff', '#2f7fd6'],
  ELECTRIC: ['#fff27a', '#f2c400'],
  GRASS: ['#a8e86a', '#3f9e3a'],
  ICE: ['#d8fbff', '#63c8d8'],
  FIGHTING: ['#ff9a7a', '#c33a52'],
  POISON: ['#e5a8ff', '#8f3fbf'],
  GROUND: ['#e8cf9a', '#b07a35'],
  FLYING: ['#e6ecff', '#8fa9de'],
  PSYCHIC: ['#ffb3d9', '#f0537a'],
  BUG: ['#d4f07a', '#7ba316'],
  ROCK: ['#ded0a8', '#9c8248'],
  DARK: ['#8f86a8', '#3a3348'],
  DRAGON: ['#9fb8ff', '#3352c4'],
  STEEL: ['#e0eaf0', '#7f9aa8'],
  FAIRY: ['#ffd6f2', '#e88fd0'],
  GHOST: ['#b9a8e0', '#5a4a8f'],
};
export const DEFAULT_FX = ['#f0f0f0', '#9a9a9a'];

export const TYPE_COLOR = {
  NORMAL: '#9099a1', FIRE: '#ff9d55', WATER: '#5090d6', ELECTRIC: '#f4d23c',
  GRASS: '#63bc5a', ICE: '#73cec0', FIGHTING: '#ce4069', POISON: '#aa6bc8',
  GROUND: '#d97845', FLYING: '#8fa9de', PSYCHIC: '#fa7179', BUG: '#90c12c',
  ROCK: '#c5b78c', GHOST: '#5269ac', DRAGON: '#0b6dc3', DARK: '#5a5465',
  STEEL: '#5a8ea1', FAIRY: '#ec8fe6',
};
export const TYPE_KR = {
  NORMAL: '노말', FIRE: '불꽃', WATER: '물', GRASS: '풀',
  ELECTRIC: '전기', ICE: '얼음', FIGHTING: '격투', POISON: '독',
  GROUND: '땅', FLYING: '비행', PSYCHIC: '에스퍼', BUG: '벌레',
  ROCK: '바위', GHOST: '고스트', DRAGON: '드래곤', DARK: '악',
  STEEL: '강철', FAIRY: '페어리',
};
export const CAT_KR = { physical: '물리', special: '특수', status: '변화' };

// 기술의 꼴 (common/action_moves.KINDS)
export const KIND_KR = {
  proj: '날리기', beam: '광선', melee: '근접', dash: '돌진', burst: '주변 폭발', cone: '부채꼴',
  strike: '내려찍기', leap: '뛰어 찍기', self: '강화', heal: '회복', guard: '방어', counter: '되받기',
  hazard: '설치', status: '상태 걸기', none: '못 씀',
};

// 상태이상 (F.s) · 그 밖의 상태 (F.c)
export const STATUS_KR = { brn: '화상', psn: '독', tox: '맹독', par: '마비', slp: '잠듦', frz: '얼음' };
export const STATUS_COLOR = {
  brn: '#ff7a3d', psn: '#b05ad6', tox: '#8a2fb8', par: '#e8c22a', slp: '#8a94b0', frz: '#6fd3e8',
};
export const COND_KR = { cnf: '혼란', seed: '씨뿌리기', trap: '묶임', flinch: '풀죽음', scr: '장막' };
export const STAT_KR = { atk: '공', def: '방', spa: '특공', spd: '특방', spe: '스핏', acc: '명중', eva: '회피' };

/* 화면 색 - 게임 창의 짙은 남색 바탕, 금색 강조 하나. */
export const UI = {
  ink: '#0b0e15',
  panel: 'rgba(17,21,32,0.82)',
  panelHi: 'rgba(38,45,66,0.92)',
  line: 'rgba(255,255,255,0.10)',
  fg: '#f2f4fb',
  dim: '#a9b1c9',
  faint: '#6f7894',
  gold: '#ffc043',
  me: '#5fd97a',
  foe: '#ff6b6b',
  hpHi: '#5fd97a',
  hpMid: '#f2c400',
  hpLow: '#ff5b4a',
};
