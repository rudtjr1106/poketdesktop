# -*- coding: utf-8 -*-
"""포켓몬 관리 창의 거르기·지닌 도구 칸 — 진짜 Tk 로 확인.

    python client/smoke_box_filter.py

서버 없이 돈다. app 과 api 를 흉내 내고 창을 실제로 띄운 뒤,
  · 타입 드롭다운과 이름 칸이 **PC 박스만** 줄이는지 (파티는 늘 보인다)
  · 지닌 도구가 상세 칸에 뜨는지
  · 도구 고르기 창이 가방의 지닐 수 있는 것만 보여주는지
를 본다. 드롭다운 자체는 안 연다 - 윈도우에서는 tk.Menu 가 모달이라
검사가 멈추고, 맥에서는 PopupMenu 창이 뜬다. 줄 목록(_type_rows)만 본다.
"""
import json
import os
import sys
import tempfile
import time

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


def wait_for(root, cond, secs=4):
    end = time.time() + secs
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.02)


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

    # 파티: 파이리(별명·지닌 도구)·꼬부기·피카츄   박스: 이상해씨·이브이(별명)·리자몽
    mons = [mon(dex, 4, 1, on=True, nickname="불꽃이", held="LEFTOVERS"),
            mon(dex, 7, 2, on=True), mon(dex, 25, 3, on=True),
            mon(dex, 1, 4), mon(dex, 133, 5, nickname="이브"), mon(dex, 6, 6)]
    app = FakeApp(root, dex, mons)
    win = ui_box.BoxWindow(root, app)
    wait_for(root, lambda: getattr(win, "mons", None))
    settle(root)

    print("-- 목록과 드롭다운")
    chk("여섯 마리가 다 그려진다", len(win.rows) == 6, len(win.rows))
    chk("드롭다운에는 **박스에 있는** 타입만 (풀·독·노말·불꽃·비행)",
        set(win.type_choices) == {"GRASS", "POISON", "NORMAL", "FIRE", "FLYING"},
        win.type_choices)
    rows = win._type_rows()
    chk("첫 줄은 '전체' 이고 지금 골라져 있다",
        rows[0]["text"] == "전체" and rows[0]["checked"] is True, rows[0])
    chk("구분선 다음에 타입들", rows[1] is None and len(rows) == 2 + len(win.type_choices), len(rows))
    chk("단추 글씨", "전체" in win.btn_type.label.cget("text"), win.btn_type.label.cget("text"))

    print("-- 타입 (박스에만 걸린다)")
    win._set_type("FIRE")
    settle(root)
    chk("파티 셋은 그대로 + 박스는 리자몽만", sorted(win.rows) == [1, 2, 3, 6], sorted(win.rows))
    chk("단추 글씨가 바뀐다", "불꽃" in win.btn_type.label.cget("text"), win.btn_type.label.cget("text"))
    chk("드롭다운에서 불꽃이 체크", next(r for r in win._type_rows() if r and r["text"] == "불꽃")["checked"])
    win._set_type("GRASS")
    settle(root)
    chk("풀이면 박스는 이상해씨만", sorted(win.rows) == [1, 2, 3, 4], sorted(win.rows))
    win._set_type(None)
    settle(root)
    chk("전체로 돌리면 여섯", len(win.rows) == 6, len(win.rows))

    print("-- 이름 찾기 (박스에만 걸린다)")
    win.f_query.set("이브")
    settle(root)
    chk("별명으로 찾는다 (파티 셋 + 이브)", sorted(win.rows) == [1, 2, 3, 5], sorted(win.rows))
    win.f_query.set("파이리")
    settle(root)
    chk("파이리는 파티라 박스에서는 안 나오고 파티는 그대로", sorted(win.rows) == [1, 2, 3], sorted(win.rows))
    win.f_query.set("리자몽")
    settle(root)
    chk("종 이름으로 박스에서 찾는다", sorted(win.rows) == [1, 2, 3, 6], sorted(win.rows))
    win.f_query.set("없는이름")
    settle(root)
    chk("아무것도 안 맞아도 파티는 남는다", sorted(win.rows) == [1, 2, 3], sorted(win.rows))
    win.f_query.set("")
    settle(root)
    chk("지우면 전부", len(win.rows) == 6)

    print("-- 타입 + 이름")
    win._set_type("FIRE")
    win.f_query.set("이브")
    settle(root)
    chk("둘 다 걸면 박스는 비고 파티만", sorted(win.rows) == [1, 2, 3], sorted(win.rows))
    win._set_type(None)
    win.f_query.set("")
    settle(root)

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
    wait_for(root, lambda: len(picker.inner.winfo_children()) > 0)
    settle(root)
    names = [w.winfo_children()[0].winfo_children()[-2].cget("text")
             for w in picker.inner.winfo_children() if w.winfo_children()]
    # 줄마다 [아이콘?, 이름, 개수] 순이라 뒤에서 두 번째가 이름이다
    chk("가진 것 중 지닐 수 있는 것만 (오랭열매)", any("오랭열매" in n for n in names), names)
    chk("몬스터볼·불꽃의돌은 안 나온다", not any(("몬스터볼" in n) or ("불꽃의돌" in n) for n in names), names)
    chk("안 가진 먹다남은음식도 안 나온다", not any("먹다남은음식" in n for n in names), names)
    picker.pick({"id": "ORANBERRY", "kr": "오랭열매"})
    wait_for(root, lambda: app.api.calls)
    settle(root)
    chk("고르면 hold 를 부른다", app.api.calls[:1] == [("hold", 2, "ORANBERRY")], app.api.calls)

    print("-- 벗기기")
    win.select(1)
    settle(root)
    win.do_unhold()
    wait_for(root, lambda: len(app.api.calls) >= 2)
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
