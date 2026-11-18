/* 모양 키 → 집안 (파일) 목록. 키 하나는 한 집안 파일에만 있다 - 그림을 고칠 사람이 서로 다른 파일만 만지게.

     air.js     바람 · 소리 · 물 · 결정      wind sound jet wave shard
     fire.js    불 · 번개 · 풀 · 가루 · 독   flame zap leaf powder poison
     mystic.js  에스퍼 · 혼 · 어둠 · 요정    psy ghost dark fairy orb beam
     body.js    몸으로 치는 것 · 땅 · 기운   punch slash bite rock quake web heal buff shield
                (+ GENERIC: 모든 모양의 근접 · 돌진 기본 그림 rush · swing)

   훅을 고르는 법: 모양에 그 훅이 있으면 그것, 없으면 기본 (shot · emit 은 orb 것, 장판 · fall 은 core 의 BASE,
   rush · swing 은 body 의 GENERIC). 모르는 모양 키는 orb 로 친다. */
import { BASE, checkStyle, own } from '../core.js';
import air from './air.js';
import fire from './fire.js';
import mystic from './mystic.js';
import body, { GENERIC } from './body.js';

export const FAMILIES = Object.freeze({ air, fire, mystic, body });

/** 모양 키 (common/action_moves.STYLES 와 같은 차례 - 검사가 못 박는다). */
export const STYLE_KEYS = Object.freeze(['orb', 'flame', 'jet', 'zap', 'leaf', 'shard', 'psy', 'rock', 'ghost', 'dark',
  'fairy', 'poison', 'wind', 'sound', 'punch', 'slash', 'bite', 'beam', 'wave', 'quake', 'heal', 'buff', 'shield',
  'powder', 'web']);

/** 모양 키 → 집안. 여기 한 곳에만 적는다. */
export const FAMILY_OF = Object.freeze({
  wind: 'air', sound: 'air', jet: 'air', wave: 'air', shard: 'air',
  flame: 'fire', zap: 'fire', leaf: 'fire', powder: 'fire', poison: 'fire',
  psy: 'mystic', ghost: 'mystic', dark: 'mystic', fairy: 'mystic', orb: 'mystic', beam: 'mystic',
  punch: 'body', slash: 'body', bite: 'body', rock: 'body', quake: 'body', web: 'body', heal: 'body', buff: 'body',
  shield: 'body',
});

const DEFS = Object.fromEntries(STYLE_KEYS.map((k) => [k, own(FAMILIES[FAMILY_OF[k]], k)]));
const FALLBACK = { ...BASE, rush: GENERIC.rush, swing: GENERIC.swing };

/** 모양 키 → 그 모양 (모르면 orb). */
export function styleDef(key) {
  return own(DEFS, key) || DEFS.orb;
}

/** 모양 키의 훅 하나 (없으면 기본, 기본도 없으면 null). emit 은 값이라 여기서 orb 것으로 채운다. */
export function hookOf(key, name) {
  const def = styleDef(key);
  return own(def, name) || own(FALLBACK, name) || (name === 'emit' || name === 'shot' ? DEFS.orb[name] : null);
}

/** 목록 검사 - 문제 목록 (없으면 []): 키마다 한 집안 · 집안 파일에는 제 키만 · 훅 이름과 값 (core.checkStyle). */
export function checkFamilies() {
  const out = [];
  for (const k of STYLE_KEYS) if (!own(FAMILY_OF, k)) out.push(`${k}: FAMILY_OF 에 없다`);
  for (const [k, fam] of Object.entries(FAMILY_OF)) {
    if (!STYLE_KEYS.includes(k)) out.push(`${k}: STYLE_KEYS 에 없는 키`);
    if (!own(FAMILIES, fam)) out.push(`${k}: 집안 ${fam} 이 없다`);
    else if (!own(FAMILIES[fam], k)) out.push(`${k}: ${fam}.js 에 없다`);
  }
  for (const [fam, defs] of Object.entries(FAMILIES)) {
    for (const [k, def] of Object.entries(defs)) {
      if (own(FAMILY_OF, k) !== fam) out.push(`${fam}.js 의 ${k}: 이 집안 키가 아니다`);
      out.push(...checkStyle(k, def));
    }
  }
  return out;
}
