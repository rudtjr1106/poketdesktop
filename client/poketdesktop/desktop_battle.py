# -*- coding: utf-8 -*-
"""바탕화면에서 그대로 벌어지는 배틀.

따로 창을 띄우지 않는다. 이미 돌아다니고 있던 내 포켓몬 한 마리가
야생 포켓몬 쪽으로 걸어가서, 둘이 알아서 싸운다.

플레이어가 하는 건 두 가지뿐이다.
    야생 포켓몬 왼쪽 클릭   배틀을 건다
    야생 포켓몬 오른쪽 클릭  몬스터볼을 던진다

체력바도 기술 버튼도 없다. 기술은 서버가 알아서 고른다.
무슨 일이 벌어지는지는 도트의 움직임과 이펙트, 그리고 급소/효과 같은
짧은 글씨로만 보여준다.
"""
from common.korean import natural

from . import battle_fx as FX
from . import config
from . import evolve_fx
from .fx_layer import FloatText, FxLayer
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
        self.app.notify(intro or "배틀 시작!")
        self.approach()

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
