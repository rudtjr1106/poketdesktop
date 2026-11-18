/* 액션 배틀 화면의 시작.

   주소 조각(#m=..&t=..)에서 입장권을 읽자마자 지우고, /ws/action 을 열어 첫 메시지로 보낸다. 판정은 전부 서버가
   한다 - 화면은 누른 키만 보내고, 받은 모습을 80ms 뒤에서 이어 그린다 (내 이동만 먼저). 게임 시계는 서버 것이고
   rAF 는 그리기만 한다.

   누른 것은 바로 보인다: 칸이 눌리고 (못 쓰면 흔들리고 안 보낸다), 쓸 수 있는 기술이면 서버를 기다리지 않고 준비
   몸짓 · 빛을 먼저 시작한다 (서버의 cast 가 오면 이어 가고, 0.25초 안에 안 오면 사그라든다). 내 쪽 이벤트(쓰기 ·
   교체 · 내 상태)는 80ms 를 기다리지 않는다 (SnapBuffer). */
import { Fx } from './fx.js';
import { parseFragment, wsUrl, closeReason, Net } from './net.js';
import { Clock, SnapBuffer, Predictor } from './interp.js';
import { InputState, MoveSender, bindInput, canAct, keyAction, slotOf } from './input.js';
import { SpriteBank, dirOf } from './sprites.js';
import { Renderer, PREDICT_SEC } from './render.js';
import { Hud, pressVerdict } from './hud.js';
import { HpTracker } from './feel.js';
import { STRUGGLE_KIND } from './consts.js';
import { PickScreen } from './pick.js';
import { Dialogs } from './dialogs.js';

const OVER_DELAY = 1.2;      // 쓰러지는 모습을 보고 결과 창을 띄운다 (초)
const DEFAULT_RTT = 0.1;     // 핑이 오기 전의 왕복 어림 (초)
const ZERO = { x: 0, y: 0 };
const clockNow = () => performance.now() / 1000;

class Game {
  constructor() {
    this.canvas = document.getElementById('stage');
    this.bank = new SpriteBank();
    this.fx = new Fx();
    this.renderer = new Renderer(this.canvas, this.bank, this.fx);
    this.hud = new Hud(this.bank);
    this.pick = new PickScreen(document.getElementById('pick'), this.bank, (slots) => this.send({ t: 'pick', slots }));
    this.dialogs = new Dialogs(document, () => this.send({ t: 'ff' }));
    this.keys = new InputState();
    this.mover = new MoveSender();
    this.clock = new Clock();
    this.buffer = new SnapBuffer();
    this.predictor = new Predictor();
    this.hp = new HpTracker();       // 맞은 비율 (상대는 hpr 만 온다)
    this.pre = null;                 // 누르자마자 시작한 준비 몸짓 {m, ang, until}
    this.net = null;
    this.intro = null;
    this.you = null;
    this.them = null;
    this.snap = null;
    this.snapAt = 0;
    this.seq = 0;
    this.status = '연결 중…';
    this.over = null;
    this.overAt = 0;
    this.closedAt = null;        // 소켓이 닫힌 때 - 시계 · 대기가 거기서 멈춘다
    this.resultShown = false;
    this.drawn = {};             // 쪽 → 이번 장에 그린 몸 가운데
    // fx 는 이 world 를 들고 있다가 그릴 때마다 pos 를 다시 묻는다 (몸을 따라가는 그림) - 그래서 한 벌을 계속 쓴다.
    // 몸이 멈춤(hitstop) · 미끄러짐으로 그려진 자리를 따라간다
    this.world = { pos: (side) => this.renderer.posOf(side) || this.drawn[side] || null, now: 0, you: null };
    this.fx.world = this.world;      // 첫 이벤트 전에도 (누르자마자 빛이 몸을 따라가게)
    this.last = clockNow();
    bindInput(window, document, {
      key: (e, a) => this.onKey(e, a),
      keyup: (e) => this.onKeyUp(e),
      clear: () => this.release(),
      live: () => this.live(),
    });
    // 판 도중 창을 닫거나 새로 불러오려 하면 한 번 묻는다 (입장권은 한 번만 쓰여 새로 불러오면 못 돌아온다)
    window.addEventListener('beforeunload', (e) => {
      if (!this.live()) return;
      e.preventDefault();
      e.returnValue = true;
    });
    // 단추를 눌러도 포커스가 가지 않게 - 키는 창 전체가 받는다
    document.addEventListener('mousedown', (e) => {
      if (e.target.closest('button')) e.preventDefault();
    });
    requestAnimationFrame((ts) => this.frame(ts));
  }

  connect(ticket) {
    this.net = new Net(wsUrl(location), ticket, {
      message: (m) => this.onMessage(m),
      close: (code) => this.onClose(code),
    });
  }

  send(obj) {
    if (this.net) this.net.send(obj);
  }

  /* ------------------------------------------------------------ 서버에서 */

  onMessage(m) {
    const now = clockNow();
    if (m.t === 'hello') this.onHello(m);
    else if (m.t === 'wait') this.status = '상대를 기다리는 중…';
    else if (m.t === 'pong') this.clock.pong(m.c, now);
    else if (m.t === 's') this.onSnap(m, now);
    else if (m.t === 'over') this.onOver(m, now);
  }

  onHello(m) {
    this.intro = m;
    this.you = m.you;
    this.them = m.you === 'a' ? 'b' : 'a';
    this.world.you = m.you;
    this.buffer.setYou(m.you);
    this.status = null;
    this.dialogs.setLimits(m.limits || {});
  }

  onSnap(s, now) {
    if (!this.intro) return;
    const phase = this.snap ? this.snap.ph : null;
    this.snap = s;
    this.snapAt = now;
    this.status = null;
    this.clock.snap(s.ts, now);
    this.hp.annotate(s);             // hit 에 pct (최대 체력의 몇 %) - 받은 차례대로
    this.buffer.push(s);
    const me = s.f && s.f[this.you];
    if (me) this.predictor.server(me, s.ack, now, this.clock.rtt ?? DEFAULT_RTT);
    if (s.ph !== phase) this.onPhase(s.ph);
  }

  onPhase(ph) {
    if (ph === 'pick') this.pick.open(this.intro.teams[this.you], this.intro.teams[this.them]);
    else this.pick.close();
    if (ph === 'fight') this.mover.reset();
  }

  onOver(m, now) {
    if (this.over) return;
    this.over = m;
    this.overAt = now;
    this.status = null;          // 접힌 판(winner null)이 '상대를 기다리는 중…' 을 결과 뒤에 남기지 않게
    this.keys.clear();
  }

  onClose(code) {
    this.closedAt = clockNow();
    this.keys.clear();
    if (this.over) return;
    this.pick.close();
    this.status = closeReason(code);
  }

  /* ------------------------------------------------------------ 키 */

  canAct() {
    return canAct({ snap: this.snap, over: this.over, blocking: this.dialogs.blocking(), netDone: !this.net || this.net.done });
  }

  /** 판이 돌고 있다 (고르기 · 준비 · 싸움, 안 끝났고 연결이 살아 있다) - 새로고침 · 창 닫기를 막거나 묻는다. */
  live() {
    const ph = this.snap ? this.snap.ph : null;
    return !!this.net && !this.net.done && !this.over && (ph === 'pick' || ph === 'ready' || ph === 'fight');
  }

  onKey(e, a) {
    if (this.dialogs.key(e.code)) return true;
    if (this.pick.isOpen() && this.pick.key(e.code)) return true;
    if (!a) return false;
    if (a.ui === 'menu') {
      if (!this.over && this.net) this.dialogs.askForfeit();
    } else if (a.ui === 'help') {
      this.dialogs.toggleHelp();
    } else {
      const fresh = this.keys.keydown(e);
      if (fresh && fresh.act && this.canAct()) this.act(fresh.act);
    }
    return true;
  }

  /** 동작 키 하나: 칸을 바로 누르고, 쓸 수 있어 보이면 보낸다. 바로 쓸 수 있는 기술이면 준비 몸짓을 먼저. */
  act(k) {
    const now = clockNow();
    const st = this.hudState(now);
    const v = pressVerdict(k, { me: st.me, moves: st.moves, age: st.age, rtt: this.clock.rtt });
    this.hud.press(k, v, now);
    if (!v.send) return;
    this.send({ t: 'act', s: (this.seq += 1), k });
    if (v.predict) this.prewind(slotOf(k), v.kind, v.ty, now);
  }

  /** 누르자마자 준비 몸짓 · 빛 (서버가 받기 전). 근접 · 돌진은 누르는 쪽, 그 밖은 상대 쪽을 겨눈다 (엔진 _aim). */
  prewind(m, kind, ty, now) {
    const me = this.drawn[this.you];
    if (m < 0 || !me) return;
    const v = this.keys.vector();
    const foe = this.drawn[this.them];
    const rush = kind === 'melee' || kind === 'dash';
    const ang = rush && (v.x || v.y) ? Math.atan2(v.y, v.x) : foe ? Math.atan2(foe.y - me.y, foe.x - me.x) : Math.PI / 2;
    this.pre = { m, ang, until: now + PREDICT_SEC };
    this.renderer.predict(this.you, m, kind || STRUGGLE_KIND, ang, now);
    this.fx.prewind(this.you, ty);
  }

  onKeyUp(e) {
    this.keys.keyup(e);
    const a = keyAction(e.code);
    if (a && a.act) this.hud.release(a.act);
  }

  /** 이동 의도: 바뀌면 바로, 움직이는 동안은 0.1초마다 (MoveSender). 싸울 때가 아니면 멈춤으로 친다. */
  sendMove(now) {
    const v = this.mover.poll(now, this.canAct() ? this.keys.vector() : ZERO);
    if (v) this.sendIntent(v, now);
  }

  /** 창이 포커스를 잃었다: 눌린 키를 비우고, 걷고 있었으면 멈춤을 바로 보낸다 (숨은 창은 rAF 가 돌지 않는다). */
  release() {
    this.keys.clear();
    this.hud.releaseAll();
    const now = clockNow();
    const v = this.mover.stop(now);
    if (v) this.sendIntent(v, now);
  }

  sendIntent(v, now) {
    this.seq += 1;
    this.send({ t: 'in', s: this.seq, x: v.x, y: v.y });
    this.predictor.input(this.seq, v.x, v.y, now);
  }

  /* ------------------------------------------------------------ 누가 나와 있나 */

  /** 그 쪽이 고른 순서 j 번째의 MonView. F.team[j].slot 이 intro 팀의 원래 칸이다 (고른 순서는 서버만 안다). */
  mon(side, j) {
    const f = this.snap && this.snap.f && this.snap.f[side];
    const t = f && f.team && f.team[j];
    return (t && this.intro.teams[side][t.slot]) || null;
  }

  /** 내 몸: 상태는 가장 새 모습, 자리는 먼저 그린 것, 서 있거나 걸을 때는 누른 쪽을 바로 본다. */
  myBody(now) {
    const f = this.snap.f[this.you];
    if (!f) return null;
    // 끊긴 뒤에는 서버가 마지막에 준 자리 (먼저 굴린 걸음은 서버가 모른다)
    const p = this.snap.ph === 'fight' && this.predictor.ready() && !this.net.done ? this.predictor.pos(now) : f;
    const v = this.canAct() ? this.keys.vector() : ZERO;
    const flip = (f.c || []).includes('cnf') ? -1 : 1;
    const free = f.st === 'idle' || f.st === 'walk';
    // 누르자마자 준비 몸짓 중이면 겨눈 쪽을 본다 (서버가 받으면 서버의 d 가 같은 쪽)
    if (this.pre && now > this.pre.until) this.pre = null;
    const d = free && this.pre ? dirOf(Math.cos(this.pre.ang), Math.sin(this.pre.ang)) : dirOf(v.x * flip, v.y * flip);
    if (!free) this.pre = null;
    const face = d >= 0 && free ? { ...f, d } : f;
    const mon = this.mon(this.you, f.i);
    const kindOf = (m) => {
      const mv = mon && mon.moves && mon.moves[m];
      return mv && mv.kind !== 'none' ? mv.kind : STRUGGLE_KIND;
    };
    return { side: this.you, f: face, mon, x: p.x, y: p.y, mine: true, kindOf };
  }

  /** 이번 장에 그릴 것. 그릴 판 시각까지 온 이벤트를 fx · 몸 · 칸에 나눠 준다. */
  scene(now, dt) {
    const empty = { now, dt, rt: 0, bodies: [], p: [], z: [] };
    if (!this.snap || !this.clock.ready()) return empty;
    const rt = this.clock.render(now);
    const view = this.buffer.at(rt);
    const bodies = [];
    const mine = this.myBody(now);
    if (mine) bodies.push(mine);
    const foe = view.f[this.them];
    if (foe) bodies.push({ side: this.them, f: foe, mon: this.mon(this.them, foe.i), x: foe.x, y: foe.y, mine: false });
    this.drawn = Object.fromEntries(bodies.map((b) => [b.side, { x: b.x, y: b.y }]));
    this.world.now = rt;
    const nameOf = (side, i) => (this.mon(side, i) || { kr: '포켓몬' }).kr;
    for (const ev of this.buffer.events(rt)) {
      this.fx.event(ev, this.world);
      this.renderer.event(ev, now);
      this.hud.event(ev, now, nameOf);
    }
    return { now, dt, rt, bodies, p: view.p, z: view.z };
  }

  hudState(now) {
    const s = this.snap;
    const until = this.over ? this.overAt : (this.closedAt ?? now);   // 끝나거나 끊기면 시계 · 대기가 멈춘다
    const age = s ? Math.max(0, until - this.snapAt) : 0;
    const me = (s && s.f && s.f[this.you]) || null;
    const myMon = me ? this.mon(this.you, me.i) : null;
    return {
      ph: s ? s.ph : null,
      left: s ? s.pt - age : null,
      you: this.you,
      them: this.them,
      me,
      foe: (s && s.f && s.f[this.them]) || null,
      mon: (side, i) => this.mon(side, i),
      moves: myMon ? myMon.moves : [],
      age,
      names: (this.intro && this.intro.names) || {},
      koPick: this.intro ? this.intro.limits.koPick : 0,
      now,
      rtt: this.clock.rtt,
      status: this.status,
      bodies: Object.values(this.renderer.drawnAt),
    };
  }

  /* ------------------------------------------------------------ 한 장 */

  frame(ts) {
    const now = ts / 1000;
    const dt = Math.min(0.1, Math.max(0, now - this.last));
    this.last = now;
    this.renderer.resize(window);
    this.clock.tick(dt);
    this.predictor.tick(dt);
    this.sendMove(now);
    const scene = this.scene(now, dt);
    this.fx.update(dt);
    this.renderer.draw(scene);
    this.renderer.toArena();
    this.hud.draw(this.renderer.ctx, this.hudState(now));
    if (this.pick.isOpen()) this.pick.tick(now, this.snap.pt - (now - this.snapAt), !!(this.snap.pick || {})[this.them]);
    if (this.over && !this.resultShown && now - this.overAt >= OVER_DELAY) {
      this.resultShown = true;
      this.dialogs.showResult(this.over, this.you);
    }
    requestAnimationFrame((t) => this.frame(t));
  }
}

const frag = parseFragment(location.hash);
history.replaceState(null, '', location.pathname + location.search);   // 입장권을 주소에 남기지 않는다
const game = new Game();
if (frag) game.connect(frag.t);
else game.status = '입장권이 없습니다. 앱에서 액션 배틀을 다시 열어 주세요.';
