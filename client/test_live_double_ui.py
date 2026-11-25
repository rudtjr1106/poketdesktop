# -*- coding: utf-8 -*-
"""더블배틀 창 검사 (독도, 2026-11-25).

    python client/test_live_double_ui.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 - 가짜 api 가 서버와 **같은 엔진**(common/double_battle)을 이 프로세스에서
돌리고, 응답 모양은 server/app/live.py 의 public() 과 같다.

무엇을 못 박나:
  1. 실시간 배틀 판의 형식이 double 이면 앱이 더블 창을 연다 (싱글이면 지금 창 그대로).
  2. 네 자리에 포켓몬이 서고 이름표 넷이 채워진다. 상대의 0번은 내 오른쪽에 선다.
  3. 포켓몬마다 차례로 고른다: 기술 -> (고를 대상이 둘 이상이면) 대상. **둘 다 정해야 한 번에 간다** (두 번 안 간다).
     대상이 필요 없는 기술(나 · 상대 둘 다)은 묻지 않는다. [되돌리기] 로 앞의 것을 다시 고른다.
  4. 보낸 뒤에는 '기다리는 중' 이 뜬다. 상대가 고르면 턴이 재생되고 체력이 맞는다.
  5. 교체: 나와 있지 않은 포켓몬만, 둘이 같은 포켓몬으로는 못 바꾼다.
  6. 쓰러진 자리는 그 자리마다 다음 포켓몬을 고른다. 내가 고를 것이 없으면 기다린다고 말한다.
  7. 끝나면 결과 칸이 뜨고 결과를 봤다고 서버에 알린다. 글자가 잘린 위젯이 없다.
"""
import io
import json
import os
import random
import sys
import tempfile
import time

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-live-double"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image, ImageDraw                            # noqa: E402

from common import double_battle as DB                      # noqa: E402
from common import live_battle as LB                        # noqa: E402
from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_live_double as DUI              # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0
DATA = os.path.join(ROOT, "server", "data")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def fake_sprite():
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((20, 14, 76, 90), fill=(90, 160, 230, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def mon(dex, species, moves, mid, level=50):
    m = P.make_pokemon(dex.get(species), 100, random.Random(mid), shiny_rate=10 ** 9)
    m["id"] = mid
    m["ivs"] = dict((s, 31) for s in P.STATS)
    m["evs"] = dict((s, 0) for s in P.STATS)
    m["nature"] = "HARDY"
    m["held"] = None
    m["moves"] = list(moves)
    return LB.leveled(m, level)


class FakeApi(object):
    """서버 대신. 응답 모양은 server/app/live.py 의 public() 과 같다 (fmt = double)."""

    def __init__(self, dex, a=None, b=None):
        self.dex = dex
        self.png = fake_sprite()
        self.calls = []
        self.sent = []
        self.seen = 0
        a = a or [mon(dex, "SNORLAX", ["TACKLE", "EARTHQUAKE", "PROTECT", "SWIFT"], 1),
                  mon(dex, "PIKACHU", ["THUNDERBOLT", "TACKLE"], 2),
                  mon(dex, "MILTANK", ["TACKLE"], 3), mon(dex, "BLISSEY", ["TACKLE"], 4)]
        b = b or [mon(dex, "CHARIZARD", ["TACKLE"], 5), mon(dex, "BLASTOISE", ["TACKLE"], 6),
                  mon(dex, "VENUSAUR", ["TACKLE"], 7)]
        self.lb = DB.DoubleBattle(dex, (1, "나", a), (2, "상대", b), rng=random.Random(4))
        self.events = self.lb.start()
        self.state = "fighting"
        self.auto_foe = True
        self.rev = 1

    def match(self):
        out = {"id": 1, "state": self.state, "rev": self.rev, "turn": self.lb.turn, "step": self.lb.step,
               "me": "a", "mine": True, "foeId": 2, "foeName": "상대", "level": 50, "turnSec": 45,
               "inviteSec": 180, "kind": "champion", "fmt": "double",
               "battle": self.lb.view("a"), "events": self.lb.events_for("a", self.events), "deadlineIn": 45}
        if self.state == "done":
            out["result"], out["reason"], out["outcome"] = self.lb.result, self.lb.reason, self.lb.outcome("a")
        return out

    def _advance(self):
        if self.auto_foe and self.lb.can_act("b") and self.lb.side("b").picks is None:
            self.lb.choose("b", "picks", self.lb.auto_choice("b")[1])
        if self.lb.ready():
            self.events = self.lb.resolve()
            if self.lb.over:
                self.state = "done"
        self.rev += 1

    def live(self):
        self.calls.append("live")
        return {"match": self.match(), "unseen": 0}

    def live_act2(self, picks):
        self.calls.append("act2")
        self.sent.append([dict(p) for p in picks])
        self.lb.choose("a", "picks", picks)
        self._advance()
        return self.match()

    def live_act(self, kind, move="", slot=-1, **_kw):
        self.calls.append("act:%s" % kind)
        self.lb.choose("a", kind, None)
        self._advance()
        return self.match()

    def foe_moves(self):
        """상대가 (따로) 골랐다 - 다음 폴링에 턴이 넘어온다."""
        self.lb.choose("b", "picks", self.lb.auto_choice("b")[1])
        self._advance()

    def live_seen(self):
        self.seen += 1
        return {"ok": True}

    def sprite(self, num, shiny=False, back=False):
        return self.png, ".png"


class FakeApp(object):
    def __init__(self, root, api, dex):
        self.root, self.api, self.dex = root, api, dex
        self.settings = {}
        self.live_battle = None
        self.notes = []

    def notify(self, m):
        self.notes.append(m)

    def request_sync(self):
        pass


def pump(root, cond, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return False


def rest(root, sec=0.3):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def labels(win):
    return " | ".join(texts(win.left))


def click(win, text):
    """아래 칸에서 그 글자가 든 칸을 누른다. 눌렀으면 True."""
    def walk(w):
        for c in w.winfo_children():
            yield c
            for x in walk(c):
                yield x
    for w in walk(win.left):
        try:
            t = w.cget("text")
        except tk.TclError:
            continue
        if isinstance(t, str) and text in t and w.bind("<Button-1>"):
            w.event_generate("<Button-1>", x=2, y=2)
            return True
    return False


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda *a: errors.append(a)
    DUI.STEP_MS = 30
    DUI.FX_ON = False
    DUI.POLL_MS = 150

    print("=== 앱이 형식을 보고 창을 고른다 ===")
    from poketdesktop import app as APP
    api = FakeApi(dex)
    app = FakeApp(root, api, dex)
    win = APP.App.open_live_battle(app, api.match())
    chk("fmt=double 이면 더블 창", isinstance(win, DUI.DoubleBattleWindow) and app.live_battle is win, type(win))
    chk("  한 번 더 불러도 같은 창", APP.App.open_live_battle(app, api.match()) is win)

    print("=== 장면 ===")
    pump(root, lambda: not win.busy and all(win.anims.get(k) for k in DUI.KEYS), 15)
    chk("네 자리에 포켓몬이 선다", all(win.shown.get(k) for k in DUI.KEYS) and all(win.anims.get(k) for k in DUI.KEYS),
        [k for k in DUI.KEYS if not win.anims.get(k)])
    names = dict((k, win.cv.itemcget(win.box[k]["name"], "text")) for k in DUI.KEYS)
    chk("이름표 넷", names["me0"].startswith("잠만보") and names["me1"].startswith("피카츄")
        and names["foe0"].startswith("리자몽") and names["foe1"].startswith("거북왕"), names)
    x = dict((k, win.cv.coords(win.sprite[k])[0]) for k in DUI.KEYS)
    chk("상대의 0번이 내 오른쪽 · 내 0번이 왼쪽", x["foe0"] > x["foe1"] > x["me1"] > x["me0"], x)
    chk("내 체력은 숫자로, 상대는 %로", "/" in win.cv.itemcget(win.box["me0"]["hp"], "text")
        and win.cv.itemcget(win.box["foe0"]["hp"], "text") == "100%")
    root.update_idletasks()
    sq = squeezed(win.win)
    chk("눌린 위젯이 없다 (기술 칸)", not sq, sq[:3])

    print("=== 고르기 ===")
    chk("첫 포켓몬의 차례 (1/2)", "잠만보의 행동" in labels(win) and "(1/2)" in labels(win), labels(win)[:80])
    chk("  되돌릴 것이 없다 · 교체는 된다", not win.undo_btn.enabled and win.switch_btn.enabled)
    click(win, "몸통박치기")
    root.update()
    chk("'고른 하나' 기술은 대상을 묻는다 (상대 둘 · 아군)", "누구에게" in labels(win) and win.await_target is not None
        and not api.sent, labels(win)[:60])
    win.undo()
    root.update()
    chk("  [되돌리기] 로 기술을 다시 고른다", win.await_target is None and "잠만보의 행동" in labels(win))
    click(win, "몸통박치기")
    root.update()
    win._pick_move(win.await_target, "foe1")
    root.update()
    chk("하나를 정하면 다음 포켓몬의 차례 (2/2) - 아직 안 보낸다", "피카츄의 행동" in labels(win) and "(2/2)" in labels(win)
        and not api.sent and len(win.picks) == 1, labels(win)[:60])
    win.undo()
    root.update()
    chk("  [되돌리기] 로 앞 포켓몬 것을 다시 고른다", "잠만보의 행동" in labels(win) and not win.picks)
    click(win, "방어")
    root.update()
    chk("대상을 고를 것이 없는 기술(나에게 쓰는 것)은 묻지 않는다", "피카츄의 행동" in labels(win)
        and win.picks == [{"pos": 0, "kind": "move", "move": "PROTECT", "target": None}], win.picks)
    api.auto_foe = False
    click(win, "10만볼트")
    root.update()
    win._pick_move(win.await_target, "foe0")
    pump(root, lambda: bool(api.sent) and win._panel == ("sent",), 5)
    chk("둘 다 정하면 한 번에 간다", api.sent == [[{"pos": 0, "kind": "move", "move": "PROTECT", "target": None},
                                            {"pos": 1, "kind": "move", "move": "THUNDERBOLT", "target": "foe0"}]],
        api.sent)
    chk("  보낸 뒤에는 기다린다고 말한다", "기다리는 중" in labels(win) and win.sent, labels(win)[:60])
    rest(root, 0.5)
    chk("  두 번 안 간다", api.calls.count("act2") == 1, api.calls)
    hp0 = api.lb.mon("b", 0).hp
    api.foe_moves()
    pump(root, lambda: win.view.get("turn") == 1 and not win.busy, 15)
    chk("상대가 고르면 턴이 재생된다", win.view.get("turn") == 1 and api.lb.turn == 1, win.view.get("turn"))
    chk("  체력이 서버와 맞는다", all((win.shown.get(k) or {}).get("hp") == api.lb.mon("a" if k[:2] == "me" else "b",
                                                                              int(k[-1])).hp
                                for k in DUI.KEYS if win.shown.get(k)) and api.lb.mon("b", 0).hp < hp0)
    chk("  다시 내 차례 - 고르던 것은 비어 있다", "잠만보의 행동" in labels(win) and not win.picks and not win.sent)

    print("=== 교체 ===")
    api.auto_foe = True
    win.open_switch()
    root.update()
    chk("교체 칸: 나와 있지 않은 포켓몬만", "누구로 바꿀까" in labels(win) and win.switching, labels(win)[:60])
    win.do_switch(0, 2)
    root.update()
    chk("  정하면 다음 포켓몬의 차례", "피카츄의 행동" in labels(win) and win.picks == [{"pos": 0, "kind": "switch", "slot": 2}])
    win.open_switch()
    root.update()
    cells = [w for w in win.left.winfo_children()[-1].winfo_children()]
    free = [i for i, c in enumerate(cells) if str(c.cget("cursor")) == "hand2"]
    chk("  둘이 같은 포켓몬으로는 못 바꾼다 (남은 것은 3번뿐)", free == [3], free)
    win.undo()
    root.update()
    click(win, "몸통박치기")
    root.update()
    win._pick_move(win.await_target, "foe0")
    pump(root, lambda: win.view.get("turn") == 2 and not win.busy, 15)
    chk("교체가 돌았다", (win.view["me"]["active"] == [2, 1]) and win.cv.itemcget(win.box["me0"]["name"], "text").startswith("밀탱크"),
        win.view["me"]["active"])
    win.close()
    chk("닫으면 앱의 걸이가 비워진다", app.live_battle is None and not win.alive)

    print("=== 쓰러진 자리 ===")
    weak = [mon(dex, "PIDGEY", ["TACKLE"], 11, level=3), mon(dex, "RATTATA", ["TACKLE"], 12, level=3),
            mon(dex, "MILTANK", ["TACKLE"], 13), mon(dex, "BLISSEY", ["TACKLE"], 14)]
    strong = [mon(dex, "GOLEM", ["SWIFT"], 15, level=100), mon(dex, "SNORLAX", ["TACKLE"], 16, level=100)]
    api = FakeApi(dex, a=weak, b=strong)
    app = FakeApp(root, api, dex)
    win = DUI.DoubleBattleWindow(app, api.match())
    pump(root, lambda: not win.busy, 15)
    click(win, "몸통박치기")
    root.update()
    win._pick_move(win.await_target, "foe0")
    root.update()
    click(win, "몸통박치기")
    root.update()
    win._pick_move(win.await_target, "foe0")
    pump(root, lambda: win.view.get("phase") == "switch" and not win.busy, 15)
    chk("둘 다 쓰러지면 자리마다 다음을 고른다", win.view["me"]["need"] == [0, 1] and "누구를 낼까" in labels(win), labels(win)[:60])
    win.do_switch(0, 2)
    root.update()
    chk("  첫 자리를 정하면 둘째 자리를 묻는다 (아직 안 보낸다)", "누구를 낼까" in labels(win) and len(api.sent) == 1)
    win.do_switch(1, 3)
    pump(root, lambda: win.view.get("phase") == "choose" and not win.busy, 15)
    chk("  둘 다 정하면 간다", api.sent[-1] == [{"pos": 0, "kind": "switch", "slot": 2}, {"pos": 1, "kind": "switch", "slot": 3}]
        and win.view["me"]["active"] == [2, 3], api.sent[-1])
    chk("  새 포켓몬이 그 자리에 선다", win.cv.itemcget(win.box["me0"]["name"], "text").startswith("밀탱크")
        and win.cv.itemcget(win.box["me1"]["name"], "text").startswith("해피너스"))
    win.close()

    api = FakeApi(dex, a=strong, b=weak)
    app = FakeApp(root, api, dex)
    win = DUI.DoubleBattleWindow(app, api.match())
    pump(root, lambda: not win.busy, 15)
    api.auto_foe = False
    click(win, "스피드스타")
    root.update()
    chk("상대 둘 다 때리는 기술도 대상을 안 묻는다", len(win.picks) == 1 and win.await_target is None, win.picks)
    click(win, "몸통박치기")
    root.update()
    win._pick_move(win.await_target, "foe0")
    rest(root, 0.3)
    api.foe_moves()
    pump(root, lambda: win.view.get("phase") == "switch" and not win.busy, 15)
    chk("상대만 고를 차례면 기다린다고 말한다", "다음 포켓몬을 고르고 있습니다" in labels(win)
        and not win.view.get("canAct"), labels(win)[:60])
    chk("  빈 자리는 이름표가 비고 도트가 없다", win.shown.get("foe0") is None and win.shown.get("foe1") is None
        and win.cv.itemcget(win.box["foe0"]["name"], "text") == "")
    api.foe_moves()                                # 상대가 다음 둘을 냈다
    pump(root, lambda: win.view.get("phase") == "choose" and not win.busy and win.shown.get("foe0"), 15)
    chk("상대가 내보내면 다시 내 차례", "의 행동" in labels(win) and win.shown["foe0"]["name"] == "밀탱크", labels(win)[:60])

    print("=== 끝 ===")
    api.auto_foe = True
    for _ in range(40):
        if api.state == "done":
            break
        if win.view.get("canAct") and not win.busy and not win.sent:
            act = win._current()
            if act is None:
                rest(root, 0.05)
                continue
            m = act["moves"][0]
            win._pick_move(m, (m.get("targets") or [None])[0] if m.get("aim") == "one" else None)
        pump(root, lambda: not win.busy and (api.state == "done" or (win.view.get("canAct") and not win.sent)), 15)
    pump(root, lambda: win._result_shown, 15)
    chk("끝나면 결과 칸이 뜬다", win._result_shown and "승리" in labels(win), labels(win)[:60])
    pump(root, lambda: api.seen >= 1, 5)
    chk("  결과를 봤다고 서버에 알린다 (한 번)", api.seen == 1, api.seen)
    root.update_idletasks()
    sq = squeezed(win.win)
    chk("  눌린 위젯이 없다 (결과 칸)", not sq, sq[:3])
    win.close()
    chk("오류 없이 돌았다", not errors, errors[:1])

    print("\n%d OK, %d FAIL" % (OK, FAIL))
    root.destroy()
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
