/* 포켓몬 도트 (서버 /api/anim · /api/sprite).

   바탕화면에서 걷던 8방향 도트를 그대로 쓴다 (client/poketdesktop/sprites.py · walk_cache.py 와 같은 약속).
     - 시트: 가로 = 프레임, 세로 = 방향. 방향이 몇 번째 줄인지는 meta.rowmap 이 알려 준다 (출처마다 다르다).
     - 지속시간은 1/60초 틱.
     - 동작마다 칸 크기가 다르다. 칸 한가운데를 같은 자리에 두고, 배율은 걷기에서 정한 하나만 쓴다
       (동작마다 맞추면 공격할 때만 작아진다).
     - 걷는 도트가 없는 종은 배틀 도트(/api/sprite) 첫 장. 배틀 도트는 왼쪽을 본다.
     - 이로치가 고른 색(tint)은 받은 시트의 색조를 돌려 만든다 (PIL HSV 8비트 셈 그대로 - client sprite_tint).
     - 기술을 쓸 때는 SpriteCollab 의 Attack (근접 · 돌진) · Shoot (날리기 · 부채꼴 · 상태 걸기 · 광선 쏘는 순간) ·
       Charge (광선 · 내려찍기 · 강화 · 회복 · 방어의 준비) 를 쓴다. 없는 종(걷기만 있는 출처)은 손으로 만든 몸짓
       (앞으로 내밀기 · 누르기/늘이기, procPose) 으로 대신한다. */

// 방향 0~7 의 이름 - 서버 F.d 순서이자 도트 rowmap 의 열쇠
const DIR_KEYS = ['down', 'downright', 'right', 'upright', 'up', 'upleft', 'left', 'downleft'];
// 대각선 그림이 없는 시트(4방향)에서 대신 쓸 옆 방향
const DIAG_ALT = { 1: 2, 3: 2, 5: 6, 7: 6 };
// 걷기 말고 받아 쓰는 동작 (모든 종에 있지는 않다). 뒤의 셋은 기술 쓰는 몸짓 (서버 main.ANIM_NAMES 에 있는 것)
const ANIMS = ['Idle', 'Hurt', 'Faint', 'Sleep', 'Attack', 'Charge', 'Shoot'];
// 걷기밖에 없는 출처 - 다른 동작을 묻지 않는다 (서버도 ok:false 를 준다)
const WALK_ONLY = ['follow', 'ow'];
const HUES = [45, 90, 135, 180, 225, 270, 315];

// 몸 높이를 이만큼(아레나 단위)에 맞춘다 - 맞는 자리(BODY_R 26)가 모든 종에 같다
const TARGET_H = 72;
const MIN_SCALE = 0.3;
const MAX_SCALE = 4;

/** 움직이는 방향 → 0~7 (0 아래 · 2 오른쪽 · 4 위 · 6 왼쪽). 멈춰 있으면 −1. */
export function dirOf(vx, vy) {
  if (!vx && !vy) return -1;
  const deg = Math.atan2(vy, vx) * 180 / Math.PI;
  return ((Math.round((90 - deg) / 45) % 8) + 8) % 8;
}

/** 방향 d 를 그릴 시트 줄. 4방향 시트는 대각선을 옆 방향으로, 줄이 모자라면(잠자기 1줄) 0줄. */
export function rowFor(sheet, d) {
  const rows = Math.max(1, sheet.rows || 8);
  const dir = d >= 0 ? d : 0;
  const pick = (dd) => (sheet.rowmap ? sheet.rowmap[DIR_KEYS[dd]] : dd);
  const alt = DIAG_ALT[dir] !== undefined ? pick(DIAG_ALT[dir]) : undefined;
  let r = pick(dir);
  if (r === undefined) r = alt;
  if (r === undefined) r = 0;
  if (r >= rows) r = alt !== undefined && alt < rows ? alt : 0;
  return r;
}

/** t 초에 보일 프레임 (durs 는 1/60초 틱). loop 가 아니면 끝 장에서 멈춘다. */
export function frameAt(durs, t, loop = true) {
  if (!durs.length) return 0;
  const total = durs.reduce((a, b) => a + b, 0);
  let tick = Math.max(0, t) * 60;
  if (loop) tick %= total;
  for (let i = 0; i < durs.length; i += 1) {
    if (tick < durs[i]) return i;
    tick -= durs[i];
  }
  return durs.length - 1;
}

/** 이 포켓몬을 그릴 도트: 이로치 시트를 쓰나, 색조를 몇 도 돌리나 (common/tint.skin + split). */
export function skinOf(mon) {
  if (!mon || !mon.shiny) return { shiny: false, hue: 0 };
  const t = mon.tint;
  if (!t) return { shiny: true, hue: 0 };
  if (t === 'normal') return { shiny: false, hue: 0 };
  const m = /^([sn])(\d{3})$/.exec(t);
  if (!m || !HUES.includes(Number(m[2]))) return { shiny: true, hue: 0 };   // 모르는 값은 이로치 색 그대로
  return { shiny: m[1] === 's', hue: Number(m[2]) };
}

const f32 = Math.fround;
const clip8 = (v) => (v <= 0 ? 0 : v >= 255 ? 255 : v);

// PIL libImaging/Convert.c rgb2hsv_row - float 자리는 fround 로 맞춘다
function rgb2hsv(r, g, b) {
  const maxc = Math.max(r, g, b);
  const minc = Math.min(r, g, b);
  if (maxc === minc) return [0, 0, maxc];
  const cr = f32(maxc - minc);
  const s = f32(cr / maxc);
  const rc = f32((maxc - r) / cr);
  const gc = f32((maxc - g) / cr);
  const bc = f32((maxc - b) / cr);
  let h;
  if (r === maxc) h = f32(bc - gc);
  else if (g === maxc) h = f32(2.0 + rc - bc);
  else h = f32(4.0 + gc - rc);
  h = f32((h / 6.0 + 1.0) % 1.0);
  return [clip8(Math.trunc(h * 255.0)), clip8(Math.trunc(s * 255.0)), maxc];
}

// C round() - 반올림은 0 에서 먼 쪽 (값은 늘 0 이상)
const cround = (v) => Math.floor(v + 0.5);

// PIL libImaging/Convert.c hsv2rgb
function hsv2rgb(h, s, v) {
  if (s === 0) return [v, v, v];
  const i = Math.floor(h * 6.0 / 255.0);
  const f = f32(h * 6.0 / 255.0 - i);
  const fs = f32(f * s);
  const p = clip8(cround(v * (1.0 - s / 255.0)));
  const q = clip8(cround(v * (1.0 - fs / 255.0)));
  const t = clip8(cround(v * (1.0 - s / 255.0 + fs / 255.0)));
  switch (i % 6) {
    case 0: return [v, t, p];
    case 1: return [q, v, p];
    case 2: return [p, v, t];
    case 3: return [p, q, v];
    case 4: return [t, p, v];
    default: return [v, p, q];
  }
}

/** RGBA 바이트의 색조를 hue 도 돌린다 (알파는 그대로). client sprite_tint.shift 와 같은 값. */
export function tintPixels(data, hue) {
  const off = Math.round(hue / 360 * 256) % 256;
  if (!off) return;
  for (let i = 0; i < data.length; i += 4) {
    const [h, s, v] = rgb2hsv(data[i], data[i + 1], data[i + 2]);
    const rgb = hsv2rgb((h + off) % 256, s, v);
    data[i] = rgb[0];
    data[i + 1] = rgb[1];
    data[i + 2] = rgb[2];
  }
}

/** 시트의 모든 칸을 겹쳐 본 그림 상자 (칸 기준 {l, t, r, b}, r · b 는 끝 다음). 다 비었으면 null. */
export function cellBox(data, width, height, fw, fh) {
  const w = Math.floor(width / fw) * fw;
  const h = Math.floor(height / fh) * fh;
  let l = Infinity; let t = Infinity; let r = -1; let b = -1;
  for (let y = 0; y < h; y += 1) {
    const cy = y % fh;
    for (let x = 0; x < w; x += 1) {
      if (!data[(y * width + x) * 4 + 3]) continue;
      const cx = x % fw;
      if (cx < l) l = cx;
      if (cx > r) r = cx;
      if (cy < t) t = cy;
      if (cy > b) b = cy;
    }
  }
  return r < 0 ? null : { l, t, r: r + 1, b: b + 1 };
}

/** 걷기 시트의 그림 상자로 한 종의 크기와 기준점을 정한다.
    cx · cy = 칸 한가운데에서 몸 가운데까지 (시트 픽셀), w · h = 몸 크기, scale = 아레나 단위 / 시트 픽셀. */
export function lookGeometry(box, fw, fh) {
  const w = Math.max(1, box.r - box.l);
  const h = Math.max(1, box.b - box.t);
  return {
    cx: (box.l + box.r) / 2 - fw / 2,
    cy: (box.t + box.b) / 2 - fh / 2,
    w,
    h,
    scale: Math.min(MAX_SCALE, Math.max(MIN_SCALE, TARGET_H / h)),
  };
}

/** 몸 가운데를 (x, y) 에 둘 때 fw × fh 칸이 놓일 자리 (아레나 단위). 칸 크기가 달라도 칸 한가운데는 같은 곳. */
export function placeCell(geo, fw, fh, x, y) {
  const s = geo.scale;
  return { x: x - (fw / 2 + geo.cx) * s, y: y - (fh / 2 + geo.cy) * s, w: fw * s, h: fh * s };
}

export function animUrl(num, name, shiny, ext = 'json') {
  return '/api/anim/' + num + '/' + name + '.' + ext + (shiny ? '?shiny=true' : '');
}

export function spriteUrl(num, shiny) {
  return '/api/sprite/' + num + (shiny ? '?shiny=true' : '');
}

function usableMeta(m) {
  return !!(m && m.ok && m.frameW > 0 && m.frameH > 0 && Array.isArray(m.durations) && m.durations.length);
}

async function sheetInfo(getJson, num, name, shiny) {
  let m = null;
  try {
    m = await getJson(animUrl(num, name, shiny));
  } catch {
    return null;                 // 끊김 - 이번 판은 없는 것으로 친다
  }
  // 이로치 시트는 meta.shiny 가 있어야 믿는다 - 옛 서버는 ?shiny 를 모르고 보통 시트를 준다
  if (!usableMeta(m) || (shiny && !m.shiny)) return null;
  return { png: animUrl(num, name, shiny, 'png'), meta: m };
}

/** 이 종 · 색으로 쓸 시트들을 고른다. {walk, anims, hue, still}.
    walk 가 null 이면 배틀 도트(still)로 그린다. 이로치 시트가 없으면 기본 시트를 색조를 돌리지 않고 쓴다
    (이로치 색조를 기본 색에 입히면 엉뚱한 색이 된다 - walk_cache._ensure_tinted 와 같다). */
export async function resolveLook(num, skin, getJson) {
  let shiny = skin.shiny;
  let hue = skin.hue;
  let walk = shiny ? await sheetInfo(getJson, num, 'Walk', true) : null;
  if (!walk) {
    if (shiny) hue = 0;
    shiny = false;
    walk = await sheetInfo(getJson, num, 'Walk', false);
  }
  const anims = {};
  if (walk && !WALK_ONLY.includes(walk.meta.src)) {
    const got = await Promise.all(ANIMS.map((name) => sheetInfo(getJson, num, name, shiny)));
    ANIMS.forEach((name, i) => {
      if (got[i]) anims[name] = got[i];
    });
  }
  return { walk, anims, hue: walk ? hue : skin.hue, still: spriteUrl(num, skin.shiny) };
}

/** 상태에 맞는 동작. 없는 동작은 있는 것으로 대신한다 (끝내 걷기). */
export function animFor(have, st, moving, hurt) {
  const first = (...names) => names.find((n) => have.has(n)) || 'Walk';
  if (st === 'ko') return first('Faint');
  if (hurt || st === 'stun') return first('Hurt');
  if (st === 'sleep') return first('Sleep', 'Idle');
  if (moving || st === 'walk' || st === 'dodge') return 'Walk';
  return first('Idle');
}

// 기술의 꼴 → [준비 동안, 발동 동안] 몸짓. 없는 시트는 FALLBACK 차례로, 끝내 없으면 손으로 만든 몸짓 (PROC)
const POSE = {
  melee: ['Attack', 'Attack'], dash: ['Attack', 'Attack'], leap: ['Charge', 'Attack'], burst: ['Charge', 'Attack'],
  counter: ['Charge', 'Attack'],
  proj: ['Shoot', 'Shoot'], cone: ['Shoot', 'Shoot'], status: ['Shoot', 'Shoot'], hazard: ['Shoot', 'Shoot'],
  beam: ['Charge', 'Shoot'], strike: ['Charge', 'Shoot'],
  self: ['Charge', 'Charge'], heal: ['Charge', 'Charge'], guard: ['Charge', 'Charge'],
};
const FALLBACK = { Attack: ['Attack', 'Shoot'], Shoot: ['Shoot', 'Attack'], Charge: ['Charge'] };
const PROC = { Attack: 'lunge', Shoot: 'shoot', Charge: 'charge' };

/** 기술 쓰는 몸짓. stage 'wind' 준비 · 'act' 발동 (그 밖은 null). 모르는 꼴은 날리기로.
    {anim: 시트 이름 | null (없으면 proc 로 그린다), loop: 준비 모으기(Charge)만 돈다, proc: 'lunge' | 'shoot' | 'charge'} */
export function attackPose(have, kind, stage) {
  if (stage !== 'wind' && stage !== 'act') return null;
  const pair = POSE[kind] || POSE.proj;
  const want = stage === 'wind' ? pair[0] : pair[1];
  const anim = FALLBACK[want].find((n) => have.has(n)) || null;
  return { anim, loop: anim === 'Charge', proc: PROC[want] };
}

const easeOut = (u) => 1 - (1 - u) * (1 - u);
const unit = (u) => (u > 0 ? (u < 1 ? u : 1) : 0);

/** 도트가 없을 때 손으로 만드는 몸짓. u 그 단계 진행 0~1 · t 초 (모으는 떨림).
    {push: 겨눈 쪽으로 옮김 (아레나 단위, 뒤로 빼면 음수), along · across: 겨눈 쪽 · 그 옆으로 늘이는 배율, shake: 떨림 폭} */
export function procPose(proc, stage, u, t = 0) {
  u = unit(u);
  if (proc === 'charge') {
    const b = Math.sin(t * 20) * 0.035;
    return { push: 0, along: 1 - 0.06 * u + b, across: 1 + 0.04 * u - b, shake: 1 + 1.5 * u };
  }
  if (proc === 'lunge') {
    if (stage === 'wind') return { push: -9 * easeOut(u), along: 1 - 0.14 * u, across: 1 + 0.08 * u, shake: 0 };
    return { push: 14 * Math.sin(Math.PI * unit(u * 1.25)), along: 1.16 - 0.16 * u, across: 0.92 + 0.08 * u, shake: 0 };
  }
  if (stage === 'wind') return { push: -5 * u, along: 1 - 0.1 * u, across: 1 + 0.06 * u, shake: 0 };
  return { push: -7 * (1 - u), along: 1.12 - 0.12 * u, across: 0.94 + 0.06 * u, shake: 0 };
}

/* ---------------------------------------------------------------- 브라우저에서 받고 그리기 */

async function fetchJson(url) {
  const r = await fetch(url);
  return r.ok ? r.json() : null;
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(url));
    img.src = url;
  });
}

/** 그림을 캔버스로 옮긴다 (색조를 돌리고, 픽셀을 읽을 수 있게). 움직이는 GIF 는 첫 장이 된다. */
function toCanvas(img, hue) {
  const c = document.createElement('canvas');
  c.width = img.naturalWidth || img.width;
  c.height = img.naturalHeight || img.height;
  const g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(img, 0, 0);
  if (hue) {
    const d = g.getImageData(0, 0, c.width, c.height);
    tintPixels(d.data, hue);
    g.putImageData(d, 0, 0);
  }
  return c;
}

function pixels(c) {
  return c.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, c.width, c.height).data;
}

function toSheet(img, meta, hue) {
  const c = toCanvas(img, hue);
  const fw = meta.frameW;
  const fh = meta.frameH;
  const cols = Math.max(1, Math.min(meta.durations.length, Math.floor(c.width / fw)));
  const rows = Math.max(1, Math.min(meta.rows || 8, Math.floor(c.height / fh)));
  return { img: c, fw, fh, rows, rowmap: meta.rowmap || null, durs: meta.durations.slice(0, cols) };
}

async function sheetLook(info, load) {
  const walkImg = await load(info.walk.png).catch(() => null);
  if (!walkImg) return null;
  const walk = toSheet(walkImg, info.walk.meta, info.hue);
  const box = cellBox(pixels(walk.img), walk.img.width, walk.img.height, walk.fw, walk.fh);
  if (!box) return null;
  const sheets = { Walk: walk };
  await Promise.all(Object.entries(info.anims).map(async ([name, a]) => {
    const img = await load(a.png).catch(() => null);
    if (img) sheets[name] = toSheet(img, a.meta, info.hue);
  }));
  return { geo: lookGeometry(box, walk.fw, walk.fh), sheets, have: new Set(Object.keys(sheets)), still: false };
}

async function stillLook(info, load) {
  const c = toCanvas(await load(info.still), info.hue);
  const box = cellBox(pixels(c), c.width, c.height, c.width, c.height) || { l: 0, t: 0, r: c.width, b: c.height };
  const sheet = { img: c, fw: c.width, fh: c.height, rows: 1, rowmap: null, durs: [60] };
  return { geo: lookGeometry(box, c.width, c.height), sheets: { Walk: sheet }, have: new Set(['Walk']), still: true };
}

/** 종 · 색마다 한 번 받아 들고 있는다. look() 은 다 받기 전이나 끝내 못 받았으면 null (그리는 쪽이 대신 그린다). */
export class SpriteBank {
  constructor(getJson = fetchJson, load = loadImage) {
    this.getJson = getJson;
    this.load = load;
    this.looks = new Map();
    this.scratch = null;
  }

  look(mon) {
    if (!mon || !mon.num) return null;
    const skin = skinOf(mon);
    const key = mon.num + ':' + (skin.shiny ? 's' : 'n') + skin.hue;
    let e = this.looks.get(key);
    if (!e) {
      e = { ready: false };
      this.looks.set(key, e);
      // 끝내 못 받은 종은 ready 가 되지 않는다 - 그리는 쪽이 타입 색 공으로 대신 그린다
      this.build(mon.num, skin).then((look) => Object.assign(e, look, { ready: true }), () => {});
    }
    return e.ready ? e : null;
  }

  async build(num, skin) {
    const info = await resolveLook(num, skin, this.getJson);
    return (info.walk && await sheetLook(info, this.load)) || stillLook(info, this.load);
  }

  /** 몸 하나. o = {x, y, d, anim, t, loop, right, alpha, k(크기 배율), wash: 덮을 색 | null,
      warps: [{ang, a, c}] - 몸 가운데를 두고 ang 쪽으로 a 배 · 그 옆으로 c 배 (맞아 눌림 · 기술 몸짓)}.
      (x, y) 가 몸 가운데. 배틀 도트(still)는 right 면 뒤집는다. */
  draw(ctx, look, o) {
    const sh = look.sheets[o.anim] || look.sheets.Walk;
    const f = frameAt(sh.durs, o.t, o.loop !== false);
    const row = rowFor(sh, o.d);
    const geo = o.k && o.k !== 1 ? { ...look.geo, scale: look.geo.scale * o.k } : look.geo;
    const r = placeCell(geo, sh.fw, sh.fh, o.x, o.y);
    const src = o.wash ? this.washed(sh, f, row, o.wash) : sh.img;
    const sx = o.wash ? 0 : f * sh.fw;
    const sy = o.wash ? 0 : row * sh.fh;
    ctx.save();
    ctx.globalAlpha *= o.alpha ?? 1;
    for (const w of o.warps || []) {
      ctx.translate(o.x, o.y);
      ctx.rotate(w.ang);
      ctx.scale(w.a, w.c);
      ctx.rotate(-w.ang);
      ctx.translate(-o.x, -o.y);
    }
    if (look.still && o.right) {
      ctx.translate(2 * o.x, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(src, sx, sy, sh.fw, sh.fh, r.x, r.y, r.w, r.h);
    ctx.restore();
  }

  /** 한 칸을 색으로 덮은 것 (맞아서 번쩍 · 얼음). 칸 모양(알파)만 남긴다. */
  washed(sh, f, row, color) {
    if (!this.scratch) this.scratch = document.createElement('canvas');
    const c = this.scratch;
    if (c.width < sh.fw || c.height < sh.fh) {
      c.width = Math.max(c.width, sh.fw);
      c.height = Math.max(c.height, sh.fh);
    }
    const g = c.getContext('2d');
    g.globalCompositeOperation = 'source-over';
    g.clearRect(0, 0, c.width, c.height);
    g.drawImage(sh.img, f * sh.fw, row * sh.fh, sh.fw, sh.fh, 0, 0, sh.fw, sh.fh);
    g.globalCompositeOperation = 'source-atop';
    g.fillStyle = color;
    g.fillRect(0, 0, sh.fw, sh.fh);
    return c;
  }

  /** 작은 얼굴 그림 (고르기 칸 · 팀 칸): 아래를 보고 선 모습을 size 칸 가운데에. */
  icon(ctx, look, cx, cy, size, t = 0) {
    const k = size / Math.max(look.geo.w, look.geo.h) / look.geo.scale;
    this.draw(ctx, look, { x: cx, y: cy, d: 0, anim: look.have.has('Idle') ? 'Idle' : 'Walk', t, k });
  }
}
