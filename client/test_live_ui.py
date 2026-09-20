# -*- coding: utf-8 -*-
"""실시간 배틀 창 검사.

    python client/test_live_ui.py

**창을 진짜로 띄운다.** 화면이 있어야 돌아간다(CI 의 맥·윈도우 잡).
서버는 안 띄운다 - 가짜 api 가 서버와 **같은 엔진**(common/live_battle)을
이 프로세스에서 돌리고, 응답 모양은 server/app/live.py 의 public() 과 같다.

## 무엇을 못 박나

  1. 창이 화면(독·작업표시줄을 뺀 자리) 안에 들어온다. 좁은 화면도.
  2. 눌린 위젯이 없다 - 글자가 잘리면 안 된다.
  3. 기술을 누르면 서버로 가고 **두 번 안 간다**.
  4. 보낸 뒤에는 '상대를 기다리는 중' 이 뜨고 기술 칸이 사라진다.
  5. **교체 단계에서는 고를 쪽만 고른다.** 상대 차례면 기다린다고 말한다.
  6. 끝나면 결과 칸이 뜨고 결과를 봤다고 서버에 알린다.
"""
import io
import json
import os
import sys
import tempfile
import time

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-live"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import random                                               # noqa: E402
import tkinter as tk                                        # noqa: E402

from PIL import Image, ImageDraw                            # noqa: E402

from common import live_battle as LB                        # noqa: E402
from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_live_battle as LUI              # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

# 기술 설명 중 가장 긴 것(68자). 안내 칸이 이만큼은 담아야 한다.
LONGEST_DESC = ("상대의 지닌 물건을 탁 쳐서 떨어뜨려 배틀이 끝날 때까지 사용할 수 "
                "없게 한다. 물건을 가진 상대에게는 데미지를 더 준다.")

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


def mon(dex, species, moves, mid):
    m = P.make_pokemon(dex.get(species), 50, random.Random(mid), shiny_rate=10 ** 9)
    m["id"] = mid
    m["ivs"] = dict((s, 31) for s in P.STATS)
    m["evs"] = dict((s, 0) for s in P.STATS)
    m["nature"] = "HARDY"
    m["held"] = None
    m["moves"] = list(moves)
    return m


class FakeApi(object):
    """서버 대신. 응답 모양은 server/app/live.py 의 public() 과 같다."""

    def __init__(self, dex):
        self.dex = dex
        self.png = fake_sprite()
        self.calls = []
        self.seen = 0
        a = [mon(dex, "SNORLAX", ["TACKLE", "BODYSLAM", "REST", "YAWN"], 1),
             mon(dex, "PIKACHU", ["THUNDERBOLT"], 2)]
        b = [mon(dex, "CHARIZARD", ["FLAMETHROWER", "SLASH"], 3),
             mon(dex, "BLASTOISE", ["SURF"], 4)]
        self.lb = LB.LiveBattle(dex, (1, "나", a), (2, "상대", b),
                                rng=random.Random(4))
        self.events = self.lb.start()
        self.turn = 0
        self.state = "fighting"
        self.auto_foe = True          # 상대가 알아서 고른다

    def match(self):
        out = {"id": 1, "state": self.state, "rev": 1, "turn": self.turn,
               "me": "a", "mine": True, "foeId": 2, "foeName": "상대",
               "level": 50, "turnSec": 30, "inviteSec": 180,
               "battle": self.lb.view("a"),
               "events": self.lb.events_for("a", self.events),
               "deadlineIn": 30}
        if self.state == "done":
            out["result"] = self.lb.result
            out["reason"] = self.lb.reason
            out["outcome"] = self.lb.outcome("a")
        return out

    def live(self):
        self.calls.append("live")
        return {"match": self.match(), "unseen": 0}

    def live_act(self, kind, move="", slot=-1):
        self.calls.append("act:%s" % (move or slot or kind))
        value = move if kind == "move" else (slot if kind == "switch" else None)
        self.lb.choose("a", kind, value)
        if self.auto_foe and self.lb.can_act("b"):
            self.lb.choose("b", *self.lb.auto_choice("b"))
        if self.lb.ready():
            self.events = self.lb.resolve()
            self.turn = self.lb.turn
            if self.lb.over:
                self.state = "done"
        return self.match()

    def live_seen(self):
        self.seen += 1
        return {"ok": True}

    def sprite(self, num, shiny=False):
        return self.png, ".png"


class FakeApp(object):
    def __init__(self, root, api, dex):
        self.root = root
        self.api = api
        self.dex = dex
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


def rest(root, sec=0.35):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def inside(cv, item):
    bb = cv.bbox(item)
    return bb is not None and bb[0] >= -1 and bb[2] <= cv.winfo_width() + 1, bb


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))

    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-300:])
    root.report_callback_exception = on_err
    print("글꼴 %s / 본문 %dpt / 화면 %dx%d"
          % (U.FAMILY, U.FONT[1], root.winfo_screenwidth(), root.winfo_screenheight()))

    print("=== 창 ===")
    api = FakeApi(dex)
    app = FakeApp(root, api, dex)
    w = LUI.LiveBattleWindow(app, api.match())
    pump(root, lambda: not w.busy, timeout=25)
    rest(root, 0.4)
    w.win.update_idletasks()
    sw_, sh_ = root.winfo_screenwidth(), root.winfo_screenheight()
    try:
        ax1, ay1, ax2, ay2 = PLAT.work_area(sw_, sh_)
    except Exception:                                       # noqa: BLE001
        ax1, ay1, ax2, ay2 = 0, 0, sw_, sh_
    chk("창이 화면 안에 들어온다",
        w.win.winfo_width() <= (ax2 - ax1)
        and w.win.winfo_height() <= (ay2 - ay1) + 44,
        (w.win.winfo_width(), w.win.winfo_height()))
    for who in ("me", "foe"):
        ok, bb = inside(w.cv, w.box[who]["name"])
        chk("%s 이름표가 캔버스 안" % who, ok, bb)
    chk("상대 이름이 보인다", "상대" in w.cv.itemcget(w.box["foe"]["who"], "text"),
        w.cv.itemcget(w.box["foe"]["who"], "text"))
    chk("내 쪽은 '나'", "나" in w.cv.itemcget(w.box["me"]["who"], "text"))
    t = " ".join(texts(w.win))
    chk("기술 칸이 뜬다", "PP" in t, t[:150])
    chk("남은 시간이 뜬다", "초" in w.timer.cget("text"), w.timer.cget("text"))
    chk("몇 대 몇인지 뜬다", ":" in w.turn_lbl.cget("text"), w.turn_lbl.cget("text"))
    bad = squeezed(w.win)
    chk("눌린 위젯 없음", not bad, bad[:3])

    # 안내 칸은 기술에 마우스를 올리면 **기술 설명**으로 바뀐다. 기본 안내만
    # 재면 짧아서 늘 통과하지만, 실제로 거기 들어가는 가장 긴 글은 훨씬 길다.
    # 칸 폭이 좁은 윈도우에서는 줄 수가 늘어 눌린다 - 그래서 여기서 잰다.
    keep = w.hint.cget("text")
    w.hint.configure(text=LONGEST_DESC)
    w.win.update_idletasks()
    need, got = w.hint.winfo_reqheight(), w.hint.winfo_height()
    chk("가장 긴 기술 설명도 안 눌린다", need <= got, (need, got))
    w.hint.configure(text=keep)
    w.win.update_idletasks()

    print("=== 고르고 보내기 ===")
    before = len([c for c in api.calls if c.startswith("act")])
    w.use_move("TACKLE")
    w.use_move("TACKLE")
    pump(root, lambda: len([c for c in api.calls if c.startswith("act")]) > before,
         timeout=15)
    rest(root, 0.3)
    chk("한 번만 보낸다",
        len([c for c in api.calls if c.startswith("act")]) == before + 1, api.calls)
    pump(root, lambda: not w.busy, timeout=30)
    rest(root, 0.4)
    chk("턴이 올라간다", w.view["turn"] >= 1, w.view["turn"])

    print("=== 상대를 기다릴 때 ===")
    api.auto_foe = False
    w.sent = False
    w.use_move("TACKLE")
    pump(root, lambda: not w.busy and w.sent, timeout=20)
    rest(root, 0.4)
    t = " ".join(texts(w.win))
    chk("기다린다고 말한다", "기다리는 중" in t, t[:200])
    chk("기술 칸은 사라진다", "PP" not in t, t[:200])
    chk("상대 이름표에 '고름' 이 안 뜬다 (아직)",
        "고름" not in w.cv.itemcget(w.box["foe"]["who"], "text"))
    bad = squeezed(w.win)
    chk("눌린 위젯 없음", not bad, bad[:3])
    # 상대가 고르면 턴이 돈다
    api.lb.choose("b", *api.lb.auto_choice("b"))
    api.events = api.lb.resolve()
    api.turn = api.lb.turn
    if api.lb.over:
        api.state = "done"
    pump(root, lambda: w.view.get("turn") == api.turn or w.busy, timeout=20)
    pump(root, lambda: not w.busy, timeout=30)
    rest(root, 0.4)
    chk("상대가 고르면 이어진다", w.view["turn"] == api.turn, (w.view["turn"], api.turn))
    api.auto_foe = True

    print("=== 교체 단계 ===")
    # 내 포켓몬을 쓰러뜨려 교체 차례로 만든다
    api.lb.a.mon.hp = 0
    api.lb.a.mon.ab["fainted"] = True
    api.lb._settle([])
    api.events = []
    w.sync(api.match())
    w.show_commands()
    rest(root, 0.3)
    t = " ".join(texts(w.win))
    chk("다음 포켓몬을 고르라고 한다", "다음 포켓몬" in t, t[:200])
    chk("기술 칸은 없다", "PP" not in t, t[:200])
    bad = squeezed(w.win)
    chk("눌린 위젯 없음", not bad, bad[:3])
    w.sent = False
    w.do_switch(1)
    pump(root, lambda: not w.busy and not w.view.get("phase") == "switch", timeout=20)
    rest(root, 0.4)
    chk("바뀐다", api.lb.a.slot == 1, api.lb.a.slot)

    print("=== 상대가 고르는 중일 때 ===")
    api.lb.b.mon.hp = 0
    api.lb.b.mon.ab["fainted"] = True
    api.lb._settle([])
    api.events = []
    w.sync(api.match())
    w.show_commands()
    rest(root, 0.3)
    t = " ".join(texts(w.win))
    chk("상대가 고르고 있다고 말한다", "고르고 있습니다" in t, t[:200])
    chk("내가 누를 것은 없다", "PP" not in t and "다음 포켓몬을 고르세요" not in t,
        t[:200])
    api.lb.choose("b", "switch", 1)
    api.events = api.lb.resolve()
    rest(root, 0.3)

    print("=== 끝 ===")
    # 상대를 전멸시킨다
    for f in api.lb.b.team:
        f.hp = 0
    api.lb._settle([])
    api.state = "done"
    api.turn = api.lb.turn
    api.events = [{"t": "over", "result": "a", "text": "이겼다!"}]
    pump(root, lambda: w._result_shown, timeout=30)
    rest(root, 0.5)
    t = " ".join(texts(w.win))
    chk("결과 칸이 뜬다", "승리" in t or "패배" in t or "무승부" in t, t[:200])
    chk("상금·점수가 없다고 알린다", "상금" in t, t[:250])
    chk("결과를 봤다고 알린다", api.seen >= 1, api.seen)
    bad = squeezed(w.win)
    chk("결과 칸에 눌린 위젯 없음", not bad, bad[:3])
    w.close()
    chk("창이 닫힌다", not w.alive)

    print("=== 좁은 화면 ===")
    real_area = PLAT.work_area
    try:
        PLAT.work_area = lambda a, b: (0, 0, 1024, 677)
        api2 = FakeApi(dex)
        app2 = FakeApp(root, api2, dex)
        w2 = LUI.LiveBattleWindow(app2, api2.match())
        pump(root, lambda: not w2.busy, timeout=25)
        rest(root, 0.4)
        w2.win.update_idletasks()
        chk("좁은 화면에도 들어간다", w2.win.winfo_width() <= 1024,
            w2.win.winfo_width())
        for who in ("me", "foe"):
            chk("%s 이름표가 안에" % who, inside(w2.cv, w2.box[who]["name"])[0])
        bad = squeezed(w2.win)
        chk("눌린 위젯 없음", not bad, bad[:3])
        w2.close()
    finally:
        PLAT.work_area = real_area

    rest(root, 0.3)
    chk("콜백에서 터진 곳 없음", not errors, errors[:1])
    try:
        root.destroy()
    except tk.TclError:
        pass
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
