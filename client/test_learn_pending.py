# -*- coding: utf-8 -*-
"""배틀 뒤 '기술 배우기' — 인터넷이 느리거나 끊겨도 말없이 끝나지 않는다.

    python client/test_learn_pending.py

**창을 진짜로 띄운다**(기다림 창). CI 의 맥·윈도우 잡에서 돈다.

사용자 제보: 인터넷이 느리면 기술이 그냥 안 배워지고 끝난다. 전에는 무엇을 버릴지
고르면 창이 닫히고 요청은 뒤에서 돌았다. 15초에 끊기면 로그에만 적고 끝났다.

  1. 보내는 동안 기다림 창이 떠 있고, 끝나면 사라진다.
  2. 답이 끊겼는데 서버는 배웠다 -> 확인해서 배웠다고 알린다 (다시 묻지 않는다).
  3. 정말 못 배웠다 -> 다시 시도할지 묻는다. 예면 다시 보낸다.
  4. 아니오면 그대로 남겨 두고, 기술 떠올리기에서 무료로 배울 수 있다고 알린다.
  5. 확인조차 안 되면(인터넷이 끊겼다) 그렇게 알린다. 창이 꼬이지 않는다.
"""
import json
import os
import sys
import tempfile
import threading
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-learn-pending-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import app as APP                         # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_learn                           # noqa: E402
from poketdesktop.api import ApiError                       # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Api(object):
    def __init__(self):
        self.mon = {"id": 65, "species": "PILOSWINE", "level": 46,
                    "moves": ["ICEFANG", "ICYWIND", "FLAIL", "ICESHARD"],
                    "pending": ["TAKEDOWN"], "info": {"name": "메꾸리"}}
        self.calls = []
        self.hold = threading.Event()
        self.hold.set()
        self.net = []               # 차례로 쓴다: "drop" / "late" / None
        self.check_fails = False

    def reset(self):
        self.mon["moves"] = ["ICEFANG", "ICYWIND", "FLAIL", "ICESHARD"]
        self.mon["pending"] = ["TAKEDOWN"]
        del self.calls[:]

    def pokemon(self):
        self.calls.append("pokemon")
        # 보낸 **뒤의** 확인만 실패하게 한다. 처음 목록부터 실패하면 창이 안 떠서
        # 사용자가 한 일이 없다 (기다리던 기술은 남고 다음 배틀 뒤에 다시 묻는다).
        if self.check_fails and any(c[0] == "learn" for c in self.calls if isinstance(c, tuple)):
            raise ApiError("서버에 연결할 수 없습니다.")
        return [json.loads(json.dumps(self.mon))]

    def learn_pending(self, pokemon, move, forget="", skip=False):
        self.calls.append(("learn", pokemon, move, forget, skip))
        self.hold.wait(10)
        mode = self.net.pop(0) if self.net else None
        if mode == "drop":
            raise ApiError("서버 응답이 없습니다. 잠시 후 다시 시도해 주세요.")
        self.mon["moves"] = [move if m == forget else m for m in self.mon["moves"]]
        self.mon["pending"] = [m for m in self.mon["pending"] if m != move]
        if mode == "late":
            raise ApiError("서버 응답이 없습니다. 잠시 후 다시 시도해 주세요.")
        return {"ok": True, "moves": self.mon["moves"], "pending": self.mon["pending"],
                "message": "메꾸리는 바둥바둥을 잊고 돌진을 배웠다!"}


class Stub(object):
    """App 에서 배우기 흐름만 떼어 온다."""
    want_learn = APP.App.want_learn
    _ask_learn = APP.App._ask_learn
    _ask_one = APP.App._ask_one
    _send_learn = APP.App._send_learn
    _learn_next = APP.App._learn_next
    _learn_failed = APP.App._learn_failed

    def __init__(self, root, dex):
        self.root, self.api, self.dex = root, Api(), dex
        self._learn_queue, self._learn_asking, self._quitting = [], False, False
        self.battle = self.arena = self.gym_battle = None
        self.notes = []

    def notify(self, m):
        self.notes.append(m)

    def sync(self):
        pass


def pump(root, cond, secs=8):
    end = time.time() + secs
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.02)
    return cond()


def popups(root, title):
    return [w for w in root.winfo_children()
            if isinstance(w, tk.Toplevel) and w.winfo_exists() and w.title() == title]


def main():
    with open(os.path.join(HERE, "..", "server", "data", "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    app = Stub(root, dex)
    api = app.api
    asked = []
    real_forget, real_confirm = ui_learn.ask_forget, APP.confirm
    ui_learn.ask_forget = lambda *a, **k: "FLAIL"
    APP.confirm = lambda *a, **k: asked.append(a[2]) or asked_answer[0]
    asked_answer = [True]

    def done():
        return not app._learn_asking and not app._learn_queue

    try:
        print("=== 1. 보내는 동안 기다림 창")
        api.hold.clear()
        app.want_learn(65, "메꾸리")
        pump(root, lambda: ("learn", 65, "TAKEDOWN", "FLAIL", False) in api.calls)
        root.update()
        chk("'기술을 배우는 중' 창이 떠 있다", bool(popups(root, "기술을 배우는 중")))
        chk("  아직 알리지 않았다", not app.notes, app.notes)
        api.hold.set()
        pump(root, done)
        root.update()
        chk("끝나면 창이 사라진다", not popups(root, "기술을 배우는 중"))
        chk("  배웠다고 알린다", any("배웠다" in n for n in app.notes), app.notes)

        print("\n=== 2. 답이 끊겼는데 서버는 배웠다")
        api.reset()
        app.notes[:] = []
        api.net = ["late"]
        app.want_learn(65, "메꾸리")
        pump(root, done)
        root.update()
        chk("서버에 다시 확인한다", "pokemon" in api.calls[1:], api.calls)
        chk("  배웠다고 알린다", any("배웠다" in n for n in app.notes), app.notes)
        chk("  다시 시도할지 묻지 않는다", not asked, asked)
        chk("  한 번만 보냈다", len([c for c in api.calls if c[0] == "learn"]) == 1, api.calls)
        chk("  기다림 창이 남지 않는다",
            not popups(root, "기술을 배우는 중") and not popups(root, "결과를 확인하는 중"))

        print("\n=== 3. 정말 못 배웠다 -> 다시 시도 (예)")
        api.reset()
        app.notes[:] = []
        api.net = ["drop"]
        asked_answer[0] = True
        app.want_learn(65, "메꾸리")
        pump(root, done)
        root.update()
        chk("다시 시도할지 묻는다", len(asked) == 1 and "돌진" in asked[0], asked)
        chk("  예면 다시 보낸다", len([c for c in api.calls if c[0] == "learn"]) == 2, api.calls)
        chk("  두 번째에 배웠다", "TAKEDOWN" in api.mon["moves"] and any("배웠다" in n for n in app.notes),
            (api.mon, app.notes))

        print("\n=== 4. 정말 못 배웠다 -> 아니오")
        api.reset()
        app.notes[:] = []
        asked[:] = []
        api.net = ["drop"]
        asked_answer[0] = False
        app.want_learn(65, "메꾸리")
        pump(root, done)
        root.update()
        chk("묻는다", len(asked) == 1, asked)
        chk("  기다리는 기술은 그대로 남는다", api.mon["pending"] == ["TAKEDOWN"], api.mon)
        chk("  떠올리기에서 무료로 배울 수 있다고 알린다",
            any("기술 떠올리기" in n and "무료" in n for n in app.notes), app.notes)
        chk("  흐름이 끝났다 (다음 포켓몬을 물을 수 있다)", done())

        print("\n=== 5. 확인조차 안 된다 (인터넷이 끊겼다)")
        api.reset()
        app.notes[:] = []
        asked[:] = []
        api.net = ["drop"]
        api.check_fails = True
        app.want_learn(65, "메꾸리")
        pump(root, done)
        root.update()
        chk("다시 시도를 묻지 않고 알린다", not asked and any("인터넷" in n for n in app.notes),
            (asked, app.notes))
        chk("  떠올리기에서 배울 수 있다고 알린다", any("기술 떠올리기" in n for n in app.notes), app.notes)
        chk("  흐름이 끝났다", done())
        chk("  기다림 창이 남지 않는다",
            not popups(root, "기술을 배우는 중") and not popups(root, "결과를 확인하는 중"))
    finally:
        ui_learn.ask_forget, APP.confirm = real_forget, real_confirm
        try:
            root.destroy()
        except Exception:                                   # noqa: BLE001
            pass

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
