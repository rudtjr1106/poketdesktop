# -*- coding: utf-8 -*-
"""'항상 위' 를 몇 초마다 다시 거는 부분. 진짜 Tk 로 확인한다.

    python client/test_topmost.py

사용자 제보: "포켓몬이 always top 아니야? 가끔 시간이 지나면 다른 창에 가려진다".
창을 만들 때 한 번만 -topmost 를 걸어서, 나중에 뜬 다른 '항상 위' 창이 위에
얹히면 그대로 가려져 있었다. 이제 Overlay 가 3초마다 다시 올린다.

  1. 올리는 대상은 **-topmost 가 걸린, 보이는 창만** 이다 (숨긴 도트·보통 창은 뺀다).
  2. 다시 올려도 **자리가 안 움직인다.** 윈도우에서 -topmost 를 다시 걸면 창이
     (0,0) 으로 튀어서, 그것 때문에 SetWindowPos 로 바꿨다.
  3. 틱이 돌면 주기가 되는 순간 부른다.
  4. 연출 레이어(체력바 · 글씨, fx_layer)는 도트 창들 바로 위로 올린다 - 레이어보다 나중에 생긴 도트가
     3초마다 그 위로 올라와 체력바를 덮던 것 (11/27 게시판 #1002, 윈도우). 그 뒤에 뜬 메뉴는 그대로 레이어 위.
"""
import os
import sys
import tempfile
import types

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-topmost-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import overlay as OV                      # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def main():
    PLAT.before_tk()                 # 맥은 Tk 를 만들기 전에 이걸 불러야 한다
    root = tk.Tk()
    root.withdraw()

    top = tk.Toplevel(root)
    top.geometry("120x80+300+200")
    top.attributes("-topmost", True)
    plain = tk.Toplevel(root)
    plain.geometry("120x80+300+320")
    hidden = tk.Toplevel(root)
    hidden.geometry("120x80+300+440")
    hidden.attributes("-topmost", True)
    hidden.withdraw()
    for _ in range(10):
        root.update()

    print("=== 어떤 창을 다시 올리나")
    seen = []
    real = PLAT.keep_on_top
    OV.PLAT.keep_on_top = lambda w: seen.append(str(w))
    try:
        ov = types.SimpleNamespace(root=root)
        OV.Overlay.keep_on_top(ov)
    finally:
        OV.PLAT.keep_on_top = real
    chk("'항상 위' 창을 다시 올린다", str(top) in seen, seen)
    chk("보통 창은 건드리지 않는다", str(plain) not in seen, seen)
    chk("숨겨 둔 창은 건드리지 않는다 (배틀 중 도트)", str(hidden) not in seen, seen)

    print("\n=== 다시 올려도 자리가 안 움직인다")
    root.update()
    before = (top.winfo_x(), top.winfo_y())
    for _ in range(3):
        PLAT.keep_on_top(top)
        root.update()
    after = (top.winfo_x(), top.winfo_y())
    chk("자리가 그대로 (%s)" % (before,), before == after, (before, after))
    chk("여전히 '항상 위'", int(top.attributes("-topmost")) == 1)

    print("\n=== 주기")
    chk("3초마다", OV.TOP_EVERY_MS == 3000, OV.TOP_EVERY_MS)
    calls = []
    ov = types.SimpleNamespace(root=root, _running=True, settings={"fps": 30},
                               pets={}, extra=[], eggs={}, _top_ms=0)
    ov.keep_on_top = lambda: calls.append(1)
    ov._tick = lambda: None          # 다음 틱 예약은 빈 것으로 (여기서는 한 번씩 손으로 돈다)
    ms = int(1000 / 30)
    for _ in range(int(OV.TOP_EVERY_MS / ms) + 1):
        OV.Overlay._tick(ov)
    chk("틱을 3초어치 돌리면 한 번 부른다", len(calls) == 1, len(calls))

    print("\n=== 연출 레이어는 도트 창들 바로 위로 (#1002)")
    from poketdesktop import fx_layer as FL

    def win_at(y, topmost=True):
        w = tk.Toplevel(root)
        w.geometry("60x40+40+%d" % y)
        if topmost:
            w.attributes("-topmost", True)
        return w
    mine = win_at(40)                                   # 앱을 켤 때 나온 우리 도트 (레이어보다 먼저)
    layer = FL.FxLayer(root, (0, 0, 400, 300))          # 투기장이 연 연출 레이어
    foe = win_at(100)                                   # 그 뒤에 들어온 상대 도트
    menu = win_at(160)                                  # 그 뒤에 뜬 메뉴 (도트가 아니다)
    for _ in range(10):
        root.update()
    chk("FxLayer 창에 _poket_over 표시", getattr(layer.win, "_poket_over", False) is True)
    pet = lambda w: types.SimpleNamespace(win=w, name_win=None)     # noqa: E731
    ov = types.SimpleNamespace(root=root, pets={1: pet(mine)}, extra=[pet(foe)], eggs={})
    seen = []
    OV.PLAT.keep_on_top = lambda w: seen.append(str(w))
    try:
        OV.Overlay.keep_on_top(ov)
    finally:
        OV.PLAT.keep_on_top = real
    order = [n for n in seen if n in (str(mine), str(layer.win), str(foe), str(menu))]
    chk("올리는 차례: 우리 도트 -> 상대 도트 -> 레이어 -> 메뉴 (나중에 올린 것이 위)",
        order == [str(mine), str(foe), str(layer.win), str(menu)], order)
    ov2 = types.SimpleNamespace(root=root)               # 도트를 모르는 overlay (검사용 가짜) - 예전처럼 만든 차례
    seen = []
    OV.PLAT.keep_on_top = lambda w: seen.append(str(w))
    try:
        OV.Overlay.keep_on_top(ov2)
    finally:
        OV.PLAT.keep_on_top = real
    order = [n for n in seen if n in (str(mine), str(layer.win), str(foe), str(menu))]
    chk("도트를 모르면 레이어가 맨 앞 (그 뒤에 만든 창들이 위)", order[0] == str(layer.win) and len(order) == 4, order)
    layer.destroy()

    root.destroy()
    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
