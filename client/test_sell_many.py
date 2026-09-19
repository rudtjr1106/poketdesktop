# -*- coding: utf-8 -*-
"""가방에서 여러 도구를 한 번에 팔기. 진짜 Tk 로 확인한다.

    python client/test_sell_many.py

전에는 한 번에 한 개씩만 팔렸다. 별가루가 서른 개면 서른 번을 눌러야 했다.

  1. 파는 창에는 **팔 수 있는 것만** 나온다 (값이 붙어 있고, 가방에 있고,
     몬스터볼이 아닌 것). 비싼 것부터.
  2. +/− · '전부' · '전부 고르기' · '고른 것 지우기' 로 개수를 정한다.
     가진 수를 넘지 않고 0 아래로도 안 간다. 합계가 계속 보인다.
  3. 아무것도 안 고르고 '팔기' 를 누르면 창을 닫지 않고 고르라고 적는다.
  4. 가방은 확인 창을 거친 뒤 **한 번만** 서버에 보낸다. 그만두면 안 보낸다.
"""
import os
import sys
import tempfile
import types

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-sell-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_bag, ui_box, ui_common as U, ui_sell  # noqa: E402

OK = FAIL = 0

ITEMS = [
    {"id": "STARDUST", "kr": "별가루", "cat": "etc", "sell": 1000, "cost": 2000},
    {"id": "PEARL", "kr": "진주", "cat": "etc", "sell": 700, "cost": 1400},
    {"id": "POKEBALL", "kr": "몬스터볼", "cat": "ball", "sell": 100, "cost": 200},
    {"id": "TM_LIKE", "kr": "못파는것", "cat": "etc", "sell": 0, "cost": 0},
    {"id": "NOTINBAG", "kr": "가방에없음", "cat": "etc", "sell": 500, "cost": 1000},
]
BAG = {"STARDUST": 3, "PEARL": 5, "POKEBALL": 9, "TM_LIKE": 1}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)

    print("=== 어떤 것이 나오나")
    lines = ui_sell.sellable(ITEMS, BAG)
    ids = [it["id"] for it, _have, _price in lines]
    chk("값이 있고 가방에 있는 것만", ids == ["PEARL", "STARDUST"], ids)
    chk("  몬스터볼은 빠진다 (이게 없으면 게임이 안 돈다)", "POKEBALL" not in ids)
    chk("  못 파는 것도 빠진다", "TM_LIKE" not in ids)
    chk("  가방에 없는 것도 빠진다", "NOTINBAG" not in ids)
    chk("비싼 것부터 (진주 3,500원 > 별가루 3,000원)", ids[0] == "PEARL", ids)

    print("\n=== 개수 고르기")
    d = ui_sell.SellMany(root, root, ITEMS, BAG, money=1234)
    root.update()
    chk("두 줄이 있다", len(d.rows) == 2, list(d.rows))
    chk("처음에는 고른 것이 없다", "고른 것이 없습니다" in d.total.cget("text"),
        d.total.cget("text"))
    chk("가진 돈을 적는다", "1,234" in d.hint.cget("text"), d.hint.cget("text"))
    d._add("STARDUST", 1)
    d._add("STARDUST", 1)
    root.update()
    chk("+ 두 번이면 두 개", d.pick.get("STARDUST") == 2, d.pick)
    chk("  합계가 보인다 (1,000 x 2)", "2,000원" in d.total.cget("text"),
        d.total.cget("text"))
    chk("  단추에도 값이 붙는다", "2,000원" in d.ok_btn.label.cget("text"),
        d.ok_btn.label.cget("text"))
    for _ in range(5):
        d._add("STARDUST", 1)
    chk("가진 수(3개)를 넘지 않는다", d.pick.get("STARDUST") == 3, d.pick)
    for _ in range(9):
        d._add("STARDUST", -1)
    chk("0 아래로 안 간다 · 0 이면 고른 것에서 빠진다", "STARDUST" not in d.pick, d.pick)
    d._set("PEARL", None)
    chk("'전부' 는 가진 수만큼", d.pick.get("PEARL") == 5, d.pick)
    d._all()
    chk("'전부 고르기' 는 모든 줄", d.pick == {"PEARL": 5, "STARDUST": 3}, d.pick)
    chk("  합계도 전부 (3,500 + 3,000)", "6,500원" in d.total.cget("text"),
        d.total.cget("text"))
    d._none()
    chk("'고른 것 지우기'", d.pick == {}, d.pick)

    print("\n=== 답")
    d._ok()
    chk("안 고르고 누르면 창이 안 닫힌다", d.win.winfo_exists() and d.result is None)
    chk("  고르라고 적는다", "골라" in d.total.cget("text"), d.total.cget("text"))
    d._add("PEARL", 2)
    d._add("STARDUST", 1)
    d._ok()
    chk("고른 것을 돌려준다",
        d.result == [{"item": "PEARL", "count": 2}, {"item": "STARDUST", "count": 1}],
        d.result)
    chk("  창이 닫힌다", not d.win.winfo_exists())

    d2 = ui_sell.SellMany(root, root, ITEMS, BAG, money=0)
    root.update()
    d2._cancel()
    chk("닫으면 None", d2.result is None, d2.result)

    d3 = ui_sell.SellMany(root, root, [], {}, money=0)
    root.update()
    texts = []

    def walk(w):
        for c in w.winfo_children():
            try:
                if "text" in c.keys() and c.cget("text"):
                    texts.append(str(c.cget("text")))
            except tk.TclError:
                pass
            walk(c)
    walk(d3.win)
    chk("팔 것이 없으면 그렇게 말한다",
        any("팔 수 있는 물건이 없습니다" in t for t in texts), texts[:4])
    d3._cancel()

    print("\n=== 확인 창에 보여줄 글")
    text = ui_sell.summary([{"item": "PEARL", "count": 2},
                            {"item": "STARDUST", "count": 1}], ITEMS)
    chk("무엇을 몇 개 파는지", "진주 2개" in text and "별가루 1개" in text, text)
    chk("  합계도 (1,400 + 1,000)", "2,400원" in text, text)
    chk("  되돌릴 수 없다고 적는다", "되돌릴 수 없습니다" in text, text)

    print("\n=== 가방에서 부르기")
    sent = []

    class Api(object):
        def sell_many(self, lines):
            sent.append(list(lines))
            return {"ok": True, "earned": 3400, "message": "진주 외 1가지 3개를 팔았다!"}

    win = tk.Toplevel(root)
    win.geometry("400x300+100+100")
    said, reloaded = [], []
    bag = types.SimpleNamespace(
        items=ITEMS, bag=BAG, money=500, win=win, root=root, alive=True,
        app=types.SimpleNamespace(api=Api()), _pending=None,
        say=lambda *a, **k: said.append(a[0] if a else ""),
        reload=lambda: reloaded.append(1))
    bag.do_sell_many = lambda: ui_bag.BagWindow.do_sell_many(bag)

    picked = [{"item": "PEARL", "count": 2}, {"item": "STARDUST", "count": 1}]
    real_ask, real_confirm = ui_sell.ask_sell_many, ui_box.confirm
    try:
        ui_sell.ask_sell_many = lambda *a, **k: None
        ui_box.confirm = lambda *a, **k: True
        bag.do_sell_many()
        chk("파는 창을 닫으면 서버에 안 보낸다", not sent, sent)

        ui_sell.ask_sell_many = lambda *a, **k: list(picked)
        ui_box.confirm = lambda *a, **k: False
        bag.do_sell_many()
        chk("확인 창에서 그만두면 안 보낸다", not sent, sent)

        ui_box.confirm = lambda *a, **k: True
        bag.do_sell_many()
        for _ in range(40):
            root.update()
        chk("고른 것을 한 번에 보낸다", sent == [picked], sent)
        chk("  끝나면 다시 불러온다", reloaded, reloaded)
        chk("  결과 말을 남긴다", bag._pending and "팔았다" in bag._pending[0],
            bag._pending)
    finally:
        ui_sell.ask_sell_many, ui_box.confirm = real_ask, real_confirm

    root.destroy()
    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
