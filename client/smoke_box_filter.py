# -*- coding: utf-8 -*-
"""포켓몬 관리 창의 거르기·지닌 도구 칸 — 진짜 Tk 로 확인.

    python client/smoke_box_filter.py

서버 없이 돈다. app 과 api 를 흉내 내고 창을 실제로 띄운 뒤, 타입 칩과
이름 칸이 목록을 정말로 줄이는지, 지닌 도구가 상세 칸에 뜨는지,
도구 고르기 창이 가방의 지닐 수 있는 것만 보여주는지 본다.
"""
import json
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-smoke-box-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_box                             # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, n=8):
    for _ in range(n):
        root.update()


def mon(dex, num, pid, on=False, nickname=None, held=None):
    sp = dex.get(num)
    m = {"id": pid, "species": sp["internal"], "num": num, "level": 20,
         "nickname": nickname, "onDesktop": on, "gender": "M",
         "ivs": {}, "evs": {}, "moves": [], "exp": 0, "nature": "HARDY"}
    m["info"] = dex.describe(dict(m, exp=P.exp_for_level(sp.get("growth", "medium"), 20)))
    m["info"]["name"] = nickname or sp["kr"]
    if held:
        m["held"] = held
        m["heldKr"] = {"LEFTOVERS": "먹다남은음식", "ORANBERRY": "오랭열매"}[held]
        m["heldDesc"] = "지니게 하면 조금씩 회복된다."
    return m


class FakeApi(object):
    def __init__(self, mons):
        self.mons = mons
        self.calls = []

    def pokemon(self):
        return self.mons

    def shop(self):
        return {"money": 0, "bag": {"ORANBERRY": 2, "POKEBALL": 5, "FIRESTONE": 1},
                "items": [
                    {"id": "ORANBERRY", "kr": "오랭열매", "cat": "held", "holdable": True,
                     "desc": "HP를 10만큼 회복한다.", "effect": {"kind": "held"}},
                    {"id": "POKEBALL", "kr": "몬스터볼", "cat": "ball", "holdable": False,
                     "effect": {"kind": "ball"}},
                    {"id": "FIRESTONE", "kr": "불꽃의돌", "cat": "stone", "holdable": False,
                     "effect": {"kind": "stone"}},
                    {"id": "LEFTOVERS", "kr": "먹다남은음식", "cat": "held", "holdable": True,
                     "desc": "조금씩 회복", "effect": {"kind": "held"}},
                ]}

    def hold(self, pid, item):
        self.calls.append(("hold", pid, item))
        return {"ok": True}

    def unhold(self, pid):
        self.calls.append(("unhold", pid))
        return {"ok": True}


class FakeApp(object):
    def __init__(self, root, dex, mons):
        self.root = root
        self.dex = dex
        self.api = FakeApi(mons)
        self.balls = 5
        self.box_window = None
        self.synced = 0

    def request_sync(self):
        self.synced += 1


def main():
    with open(os.path.join(HERE, "..", "server", "data", "pokedex.json"),
              encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()

    mons = [mon(dex, 4, 1, on=True, nickname="불꽃이", held="LEFTOVERS"),
            mon(dex, 7, 2, on=True), mon(dex, 25, 3, on=True),
            mon(dex, 1, 4), mon(dex, 133, 5, nickname="이브"), mon(dex, 6, 6)]
    app = FakeApp(root, dex, mons)
    win = ui_box.BoxWindow(root, app)
    # run_async 가 딴 스레드로 목록을 받아온다 - 조금 기다린다
    import time
    end = time.time() + 4
    while time.time() < end and not getattr(win, "mons", None):
        root.update()
        time.sleep(0.02)
    settle(root)

    print("-- 목록과 칩")
    chk("여섯 마리가 다 그려진다", len(win.rows) == 6, len(win.rows))
    chk("갖고 있는 타입만 칩으로 (전체 + 7타입)", len(win._chips) == 8,
        sorted(k for k in win._chips if k))
    chk("표시 수 표기는 다 보일 땐 없다", "표시" not in win.count.cget("text"),
        win.count.cget("text"))

    print("-- 타입 칩")
    win._set_type("FIRE")
    settle(root)
    chk("불꽃만 남는다 (파이리·리자몽)", sorted(win.rows) == [1, 6], sorted(win.rows))
    chk("표시 수가 적힌다", "표시 2마리" in win.count.cget("text"), win.count.cget("text"))
    win._set_type("FIRE")            # 같은 칩을 다시 누르면 풀린다
    settle(root)
    chk("다시 누르면 전부", len(win.rows) == 6, len(win.rows))

    print("-- 이름 찾기")
    win.f_query.set("이브")
    settle(root)
    chk("별명으로 찾는다", sorted(win.rows) == [5], sorted(win.rows))
    win.f_query.set("파이리")
    settle(root)
    chk("별명이 있어도 종 이름으로 찾힌다", sorted(win.rows) == [1], sorted(win.rows))
    win.f_query.set("없는이름")
    settle(root)
    chk("없으면 빈 목록 + 안내", len(win.rows) == 0)
    win.f_query.set("")
    settle(root)
    chk("지우면 전부", len(win.rows) == 6)

    print("-- 지닌 도구 칸")
    win.select(1)
    settle(root)
    chk("지닌 도구 이름이 뜬다", "먹다남은음식" in win.d_held.cget("text"),
        win.d_held.cget("text"))
    chk("벗기기 단추가 산다", win.btn_unhold.enabled is True)
    win.select(2)
    settle(root)
    chk("없는 애는 '없음'", win.d_held.cget("text").startswith("없음"), win.d_held.cget("text"))
    chk("벗기기 단추가 죽는다", win.btn_unhold.enabled is False)

    print("-- 도구 고르기 창")
    win.select(2)
    picker = ui_box.HeldPicker(win, win.current())
    end = time.time() + 4
    while time.time() < end and len(picker.inner.winfo_children()) == 0:
        root.update()
        time.sleep(0.02)
    settle(root)
    names = [w.winfo_children()[0].winfo_children()[-2].cget("text")
             for w in picker.inner.winfo_children() if w.winfo_children()]
    # 줄마다 [아이콘?, 이름, 개수] 순이라 뒤에서 두 번째가 이름이다
    chk("가진 것 중 지닐 수 있는 것만 (오랭열매)", any("오랭열매" in n for n in names), names)
    chk("몬스터볼·불꽃의돌은 안 나온다", not any(("몬스터볼" in n) or ("불꽃의돌" in n) for n in names), names)
    chk("안 가진 먹다남은음식도 안 나온다", not any("먹다남은음식" in n for n in names), names)
    picker.pick({"id": "ORANBERRY", "kr": "오랭열매"})
    end = time.time() + 4
    while time.time() < end and not app.api.calls:
        root.update()
        time.sleep(0.02)
    settle(root)
    chk("고르면 hold 를 부른다", app.api.calls[:1] == [("hold", 2, "ORANBERRY")], app.api.calls)

    print("-- 벗기기")
    win.select(1)
    settle(root)
    win.do_unhold()
    end = time.time() + 4
    while time.time() < end and len(app.api.calls) < 2:
        root.update()
        time.sleep(0.02)
    chk("벗기기가 unhold 를 부른다", ("unhold", 1) in app.api.calls, app.api.calls)

    try:
        win.close()
        root.destroy()
    except Exception:                                       # noqa: BLE001
        pass
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
