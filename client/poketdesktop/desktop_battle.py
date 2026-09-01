# -*- coding: utf-8 -*-
"""바탕화면에서 그대로 벌어지는 배틀.

따로 창을 띄우지 않는다. 이미 돌아다니고 있던 내 포켓몬 한 마리가
야생 포켓몬 쪽으로 걸어가서, 둘이 알아서 싸운다.

플레이어가 하는 건 두 가지뿐이다.
    야생 포켓몬 왼쪽 클릭   배틀을 건다
    야생 포켓몬 오른쪽 클릭  몬스터볼을 던진다

기술 버튼은 없다. 무슨 기술을 쓸지는 서버가 알아서 고른다.
도트 위에 작은 체력바만 띄우고, 나머지는 도트의 움직임과 이펙트,
급소/효과 같은 짧은 글씨로 보여준다.
"""
from common.korean import natural

from . import battle_fx as FX
from . import config
from . import evolve_fx
from .fx_layer import FloatText, FxLayer, HpBar
from .ui_common import run_async

APPROACH_GAP = 96          # 붙어 서는 간격 (가로)
WALK_MS = 22               # 다가가는 속도
TURN_GAP = 620             # 한 턴 끝나고 다음 턴까지
RESULT_MS = 1100


class DesktopBattle(object):
    """배틀 한 판을 바탕화면 위에서 진행한다."""

    def __init__(self, app, battle, intro=None):
        self.app = app
        self.root = app.root
        self.b = battle
        self.closed = False
        self.busy = False
        self.jobs = []
        self.fx = None
        self.texts = []
        self.layer = None
        self.mine = None        # 내 도트 (Pet)
        self.foe = None         # 야생 도트 (WildPet)
        self.bars = None        # 체력바 (내 것, 상대 것)
        self.bar_job = None
        self.saved_home = None

        self.setup(intro)

    # ---------------- 준비 ----------------
    def setup(self, intro):
        ov = self.app.overlay
        wild = self.app.wild
        if not ov or not wild or not wild.pet:
            return self.abort("야생 포켓몬이 사라졌습니다.")
        self.foe = wild.pet
        self.mine = ov.pets.get(self.b["me"]["id"])
        if self.mine is None:
            # 파티 선두가 아직 화면에 없으면 목록을 맞춘 뒤 다시 시도
            self.app.request_sync()
            return self.retry_setup(intro, 1)
        self.begin(intro)

    def retry_setup(self, intro, tries):
        if self.closed:
            return
        if tries > 6:
            return self.abort("싸울 포켓몬을 화면에서 찾지 못했습니다.")

        def again():
            pet = self.app.overlay.pets.get(self.b["me"]["id"])
            if pet is None:
                return self.retry_setup(intro, tries + 1)
            self.mine = pet
            self.begin(intro)
        self.after(500, again)

    def begin(self, intro):
        self.layer = FxLayer(self.root, self.app.overlay.area())
        self.mine.battling = True
        self.foe.battling = True
        self.saved_home = (self.mine.x, self.mine.y)
        # 야생 쪽은 '야생 OO Lv.5' 이름표가 도트 바로 위에 붙어 있어서
        # 체력바를 그 위로 올려야 겹치지 않는다.
        self.bars = (HpBar(self.layer), HpBar(self.layer, lift=18))
        self.sync_bars(snap=True)
        self.tick_bars()
        self.app.notify(intro or "배틀 시작!")
        self.approach()

    # ---------------- 체력바 ----------------
    def sync_bars(self, snap=False):
        """서버가 알려준 체력을 바에 반영한다."""
        if not self.bars:
            return
        for bar, side in zip(self.bars, ("me", "foe")):
            d = (self.b or {}).get(side) or {}
            bar.set(d.get("hp", 0), d.get("maxhp", 1))
            if snap:
                bar.shown = bar.ratio

    def tick_bars(self):
        """도트를 따라다니게 매 프레임 다시 그린다.

        포켓몬이 걸어다니고 기술을 쓰며 움직이므로, 바도 같이 움직여야
        누구 체력인지 헷갈리지 않는다.
        """
        if self.closed or not self.bars or not self.layer:
            return
        # 포켓몬 창도 '항상 위' 라서 그냥 두면 체력바가 그 뒤로 숨는다.
        # 자주 올릴 필요는 없어서 몇 프레임에 한 번만 올린다.
        self._bar_n = getattr(self, "_bar_n", 0) + 1
        if self._bar_n % 15 == 1:
            self.layer.raise_above()
        for bar, pet in zip(self.bars, (self.mine, self.foe)):
            bar.ease()
            if pet is None:
                bar.clear()
                continue
            try:
                bar.draw(int(pet.x) + pet.fw // 2, int(pet.y))
            except Exception:                              # noqa: BLE001
                pass
        self.bar_job = self.root.after(33, self.tick_bars)

    def apply_hp(self, ev):
        """이벤트에 담긴 체력을 그 자리에서 바에 반영한다.

        예전에는 한 턴이 통째로 끝난 뒤에야 서버가 준 최종 체력으로
        맞췄다. 그래서 내가 할퀴고 상대가 울음소리까지 쓴 다음에야 상대
        체력이 줄어드는 것처럼 보였다. 맞는 순간 줄어야 무엇 때문에
        줄었는지 알 수 있다.

        누구 체력인지는 이벤트마다 다르다.
          hit                맞은 쪽 = target
          chip/heal/recoil   그걸 겪는 쪽 = who
        """
        if not self.bars or "hp" not in ev:
            return
        side = ev.get("target") if ev.get("t") == "hit" else ev.get("who")
        if side == "me":
            bar = self.bars[0]
        elif side == "foe":
            bar = self.bars[1]
        else:
            return
        bar.set(ev["hp"], ev.get("maxhp") or 1)

    def clear_bars(self):
        if self.bar_job:
            try:
                self.root.after_cancel(self.bar_job)
            except Exception:                              # noqa: BLE001
                pass
            self.bar_job = None
        for bar in (self.bars or ()):
            bar.clear()
        self.bars = None

    def abort(self, msg):
        self.app.notify(msg)
        self.finish_cleanup()

    # ---------------- 다가가기 ----------------
    def approach(self):
        """내 포켓몬이 야생 옆으로 걸어간다."""
        if self.closed or not self.mine or not self.foe:
            return
        fx, fy = self.foe.x, self.foe.y
        # 야생의 왼쪽에 설지 오른쪽에 설지, 가까운 쪽으로
        left = self.mine.x <= fx
        tx = fx - APPROACH_GAP if left else fx + self.foe.fw + APPROACH_GAP \
            - self.mine.fw
        ty = fy + (self.foe.fh - self.mine.fh)
        x1, y1, x2, y2 = self.app.overlay.area()
        m = self.app.overlay.settings["areaMargin"]
        tx = max(x1 + m, min(tx, x2 - self.mine.fw - m))
        ty = max(y1 + m, min(ty, y2 - self.mine.fh - m))

        sx, sy = self.mine.x, self.mine.y
        steps = max(8, int(max(abs(tx - sx), abs(ty - sy)) / 6))
        self.mine.face_towards(fx)
        self.foe.face_towards(tx)

        def go(i):
            if self.closed:
                return
            if i > steps:
                self.mine.x, self.mine.y = tx, ty
                self.mine.place()
                return self.after(320, self.next_turn)
            t = i / float(steps)
            self.mine.x = sx + (tx - sx) * t
            self.mine.y = sy + (ty - sy) * t
            self.mine.place()
            self.after(WALK_MS, lambda: go(i + 1))
        go(1)

    # ---------------- 턴 진행 ----------------
    def next_turn(self):
        if self.closed or self.busy or not self.b or self.b.get("over"):
            return
        self.busy = True

        def done(r, err):
            self.busy = False
            if self.closed:
                return
            if err:
                return self.abort(getattr(err, "message", str(err)))
            self.play(r.get("events") or [], r)
        run_async(self.root,
                  lambda: self.app.api.battle_move(self.b["id"], ""), done)

    def play(self, events, result):
        q = list(events)

        def nxt():
            if self.closed:
                return
            if not q:
                return self.turn_done(result)
            self.render(q.pop(0), nxt)
        nxt()

    def render(self, ev, done):
        t = ev.get("t")
        who = ev.get("who")
        self.apply_hp(ev)
        src = self.mine if who == "me" else self.foe
        dst = self.foe if who == "me" else self.mine

        if t == "move" and src and dst:
            move = self.find_move(ev)
            self.fx = FX.Effect(self, move, self.center(src), self.center(dst),
                                lambda: self.after(140, done), who=who)
            return self.fx.play()
        if t == "hit":
            side = self.mine if ev.get("target") == "me" else self.foe
            if side:
                if ev.get("crit"):
                    self.float_over(side, "급소!", "#ffd447")
                eff = ev.get("eff", 1)
                if eff and eff > 1:
                    self.float_over(side, "효과가 굉장하다!", "#7bffa0")
                elif eff and eff < 1:
                    self.float_over(side, "효과가 별로...", "#b0b0c0")
                return self.shake(side, done)
        if t in ("ailment", "status"):
            side = self.mine if who == "me" else self.foe
            if side and t == "ailment":
                self.float_over(side, ev.get("text", "").split(" 은(는) ")[-1]
                                .replace(" 상태가 되었다!", ""), "#ff9d55")
        if t == "faint":
            side = self.mine if who == "me" else self.foe
            if side:
                return self.faint(side, done)
        if t == "immune":
            side = self.mine if who == "me" else self.foe
            if side:
                self.float_over(side, "효과가 없다...", "#9a9ab0")
        self.after(220, done)

    def turn_done(self, result):
        if self.closed:
            return
        b = result.get("battle")
        if b:
            self.b = b
            self.sync_bars()
        if not b or not b.get("over"):
            return self.after(TURN_GAP, self.next_turn)
        self.show_result(result)

    # ---------------- 결과 ----------------
    def show_result(self, result):
        b = result.get("battle") or {}
        res = b.get("result")
        if res == "won":
            msgs = []
            for e in (result.get("exp") or []):
                if e.get("leveledUp"):
                    msgs.append("%s 레벨 %d!" % (e["name"], e["level"]))
                # 기술을 배운 건 반드시 알린다. 네 개가 차면 오래된 것이
                # 밀려나는데, 말없이 사라지면 아끼던 기술이 없어진 걸
                # 한참 뒤에야 알게 된다.
                learned = e.get("learned") or []
                forgot = e.get("forgot") or []
                if learned:
                    line = "%s 은(는) %s 을(를) 배웠다!" % (
                        e["name"], ", ".join(learned))
                    if forgot:
                        # 네 개가 차면 오래된 것이 밀려난다. 무엇이 사라졌는지
                        # 같이 알려야 나중에 "왜 없지?" 가 되지 않는다.
                        line += "  (%s 을(를) 잊었다)" % ", ".join(forgot)
                    msgs.append(natural(line))
            main = next((e for e in (result.get("exp") or [])
                         if not e.get("shared")), None)
            if main and self.mine:
                self.float_over(self.mine, "+%d exp" % main["gained"], "#7bffa0")
            head = natural("%s 을(를) 쓰러뜨렸다!"
                           % b.get("foe", {}).get("name", "야생"))
            if msgs:
                head += "  " + " ".join(msgs)
            drop = result.get("drop")
            if drop:
                head += "  " + natural("%s 을(를) 주웠다!" % drop["kr"])
                if self.mine:
                    self.float_over(self.mine, drop["kr"], "#ffd447")
            self.app.notify(head)
        elif res == "lost":
            party = result.get("party") or []
            if result.get("canSwitch") and party:
                return self.switch_to(party[0])
            self.app.notify("%s 은(는) 쓰러졌다..." % self.b["me"]["name"])
        elif res == "fled":
            self.app.notify("야생 포켓몬이 떠나버렸다.")
        # 진화는 배틀 정리가 끝난 뒤에 한다. 배틀이 남아 있는 동안 종을
        # 바꾸면 서버가 들고 있는 배틀 스냅샷과 어긋난다.
        # 어느 포켓몬이 진화했는지 id 로 들고 간다. 같은 종이 파티에 둘 있으면
        # 종 이름으로는 누가 진화했는지 가릴 수 없다.
        evolves = [dict(e["evolve"], pokemonId=e.get("id"))
                   for e in (result.get("exp") or []) if e.get("evolve")]
        self.pending_evolve = evolves
        self.after(RESULT_MS, self.finish_cleanup)

    def switch_to(self, mon):
        """쓰러지면 다음 포켓몬이 자동으로 나온다."""
        self.busy = True

        def done(r, err):
            self.busy = False
            if self.closed:
                return
            if err:
                return self.abort(getattr(err, "message", str(err)))
            self.b = r["battle"]
            self.app.notify("가라, %s!" % self.b["me"]["name"])
            # 쓰러진 도트는 원래 자리로, 새 포켓몬이 앞으로 나선다
            if self.mine:
                self.mine.battling = False
                self.mine.win.deiconify()
                if self.saved_home:
                    self.mine.x, self.mine.y = self.saved_home
                    self.mine.place()
            self.mine = self.app.overlay.pets.get(self.b["me"]["id"])
            if not self.mine:
                return self.abort("다음 포켓몬을 화면에서 찾지 못했습니다.")
            self.mine.battling = True
            self.saved_home = (self.mine.x, self.mine.y)
            self.after(300, self.approach)
        run_async(self.root,
                  lambda: self.app.api.battle_switch(self.b["id"], mon["id"]), done)

    # ---------------- 몬스터볼 ----------------
    def throw_ball(self):
        """배틀 중에 오른쪽 클릭. 체력을 깎아뒀으면 훨씬 잘 잡힌다."""
        if self.closed or self.busy:
            return
        if self.app.balls <= 0:
            return self.app.notify("몬스터볼이 없습니다.")
        self.busy = True

        def done(r, err):
            self.busy = False
            if self.closed:
                return
            if err:
                return self.app.notify(getattr(err, "message", str(err)))
            self.app.balls = r.get("balls", self.app.balls)
            self.app.refresh_tray()
            self.app.wild.play_catch(r, on_done=lambda: self.after_ball(r))
        run_async(self.root, lambda: self.app.api.battle_ball(self.b["id"]), done)

    def after_ball(self, r):
        if self.closed:
            return
        if r.get("caught"):
            self.app.notify(r.get("message") or "잡았다!")
            self.foe = None
            return self.after(500, self.finish_cleanup)
        b = r.get("battle")
        if b:
            self.b = b
        self.app.notify(r.get("message") or "놓쳤다!")
        self.play(r.get("events") or [], r or {})

    # ---------------- 연출 도구 ----------------
    def center(self, pet):
        """이펙트 레이어 기준 좌표. battle_fx 가 이 좌표로 그린다."""
        sx = pet.x + pet.fw / 2.0
        sy = pet.y + pet.fh / 2.0
        return self.layer.to_local(sx, sy) if self.layer else (sx, sy)

    @property
    def cv(self):
        return self.layer.cv if self.layer else None

    def to_local(self, x, y):
        return self.layer.to_local(x, y)

    def float_over(self, pet, text, color):
        if not self.layer or not text:
            return
        t = FloatText(self.layer, pet.x + pet.fw / 2.0, pet.y - 6, text, color)
        self.texts.append(t)

    def find_move(self, ev):
        name = ev.get("move")
        dex = self.app.dex
        if dex and name:
            for m in (dex.moves or {}).values():
                if m.get("kr") == name:
                    return m
        return {"type": ev.get("moveType") or "NORMAL",
                "cat": ev.get("cat") or "physical", "flags": []}

    def lunge(self, who, done):
        """battle_fx 가 접촉기에서 부른다. 도트가 상대 쪽으로 달려든다."""
        pet = self.mine if who == "me" else self.foe
        other = self.foe if who == "me" else self.mine
        if not pet or not other:
            return done()
        hx, hy = pet.x, pet.y
        dx = 26 if other.x > pet.x else -26
        n = 5

        def go(i):
            if self.closed:
                return
            if i > n * 2:
                pet.x, pet.y = hx, hy
                pet.place()
                return self.after(80, done)
            k = i if i <= n else n * 2 - i
            pet.x = hx + dx * k / float(n)
            pet.place()
            self.after(22, lambda: go(i + 1))
        go(1)

    def shake(self, pet, done):
        hx = pet.x
        seq = [-7, 7, -5, 5, -3, 3, 0]

        def go(i):
            if self.closed:
                return
            if i >= len(seq):
                pet.x = hx
                pet.place()
                return done()
            pet.x = hx + seq[i]
            pet.place()
            self.after(30, lambda: go(i + 1))
        go(0)

    def faint(self, pet, done):
        hy = pet.y

        def go(i):
            if self.closed:
                return
            if i > 10:
                try:
                    pet.win.withdraw()
                    if pet.badge_win:
                        pet.badge_win.withdraw()
                except Exception:
                    pass
                pet.y = hy
                return self.after(240, done)
            pet.y = hy + i * 6
            pet.place()
            self.after(26, lambda: go(i + 1))
        go(1)

    def after(self, ms, fn):
        if self.closed:
            return
        j = self.root.after(ms, fn)
        self.jobs.append(j)
        return j

    # ---------------- 정리 ----------------
    def finish_cleanup(self):
        if self.closed:
            return
        self.closed = True
        self.clear_bars()
        evolves = getattr(self, "pending_evolve", None) or []
        if evolves:
            self.root.after(400, lambda: play_evolutions(self.app, evolves))
        if self.fx:
            self.fx.stop()
        for t in self.texts:
            t.stop()
        self.texts = []
        for j in self.jobs:
            try:
                self.root.after_cancel(j)
            except Exception:
                pass
        self.jobs = []
        if self.layer:
            self.layer.destroy()
            self.layer = None
        # 내 포켓몬은 원래 자리로 돌려보내고 다시 돌아다니게 한다
        if self.mine:
            self.mine.battling = False
            try:
                self.mine.win.deiconify()
            except Exception:
                pass
            if self.saved_home:
                self.mine.x, self.mine.y = self.saved_home
                self.mine.clamp()
                self.mine.place()
        self.app.battle = None
        self.app.request_sync()
        if self.app.wild:
            self.app.wild.check()
        config.log("배틀 종료")

    def close(self):
        self.finish_cleanup()


def play_evolutions(app, infos):
    """진화 연출을 차례로 재생한다.

    학습장치로 파티 전원이 경험치를 받으므로 한 판에 두 마리가 같이
    진화할 수 있다. 겹쳐서 틀면 뒤죽박죽이 되니 하나씩 이어서 튼다.
    """
    rest = list(infos)
    if not rest:
        app.request_sync()
        return
    info = rest.pop(0)
    ov = getattr(app, "overlay", None)
    pet = (getattr(ov, "pets", {}) or {}).get(info.get("pokemonId")) if ov else None
    text = natural("%s 은(는) %s 으로(로) 진화했다!"
                   % (info["fromKr"], info["toKr"]))
    if pet is None:
        # 바탕화면에 없으면(박스에 있으면) 글로만 알린다
        app.notify("축하합니다! " + text)
        return play_evolutions(app, rest)
    evolve_fx.play(app, pet, info,
                   on_done=lambda: play_evolutions(app, rest))
