# -*- coding: utf-8 -*-
"""타입 스프레이 남은 시간 띠 (2.1.3, 게시판 #445) - 진짜 Tk.

    python client/test_boost_badge.py

시계는 가짜(now)를 넣어 돌린다 - 1초씩 기다리지 않는다. 못 박는 것:

  1. 서버가 남은 초를 주면 주 화면 작업 영역 오른쪽 아래에 '불꽃 스프레이 2:05' 띠가 뜬다.
  2. 초마다 줄고(1:05), 다 되면 서버에 묻지 않고 사라진다. 서버가 0 · 타입 없음을 주면 바로 사라진다.
  3. 옛 서버(boosts 없음 = None)면 그대로 둔다. 다시 받으면 끝나는 시각을 서버 값으로 맞춘다.
  4. 타입이 바뀌면 칩 글 · 빛깔이 바뀐다. 한 시간 넘게 남으면 '1:41:05'.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-badge-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import boost_badge as BB                  # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Clock(object):
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class App(object):
    def __init__(self, root):
        self.root = root


def settle(root, n=6):
    for _ in range(n):
        root.update()


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append("%s: %s" % (e.__name__, v))
    clock = Clock()
    b = BB.BoostBadge(App(root), now=clock)

    print("1. 띄우기")
    chk("시계 글", BB.clock(125) == "2:05" and BB.clock(9) == "0:09" and BB.clock(6065) == "1:41:05",
        (BB.clock(125), BB.clock(9), BB.clock(6065)))
    b.note(None)
    chk("옛 서버(None)면 아무것도 안 띄운다", b.win is None)
    b.note({"lureLeft": 125, "lureType": "FIRE"})
    settle(root)
    chk("남은 초를 받으면 띠가 뜬다", b.win is not None and b.win.winfo_ismapped(), b.win)
    chk("  '불꽃 스프레이' 칩 + 2:05", b.chip.cget("text") == "불꽃 스프레이" and b.time_lbl.cget("text") == "2:05",
        (b.chip.cget("text"), b.time_lbl.cget("text")))
    chk("  칩 빛깔은 그 타입 빛깔", b.chip.cget("bg").lower() == U.TYPE_COLOR["FIRE"].lower(), b.chip.cget("bg"))
    sw, sh = b.win.winfo_screenwidth(), b.win.winfo_screenheight()
    _x1, _y1, x2, y2 = PLAT.work_area(sw, sh)
    gx, gy = b.win.winfo_x(), b.win.winfo_y()
    ww, wh = b.win.winfo_width(), b.win.winfo_height()
    chk("  주 화면 작업 영역 오른쪽 아래 (작업표시줄 · 독 위)",
        abs((gx + ww) - (x2 - BB.MARGIN)) <= 2 and abs((gy + wh) - (y2 - BB.MARGIN)) <= 2,
        (gx, gy, ww, wh, x2, y2))
    chk("  테두리 없는 창", bool(b.win.overrideredirect()))

    print("2. 줄어들다 사라진다")
    clock.t += 60
    b._tick()
    chk("1분 뒤 1:05", b.time_lbl.cget("text") == "1:05", b.time_lbl.cget("text"))
    b.note({"lureLeft": 70, "lureType": "FIRE"})
    chk("다시 받으면 서버 값으로 (1:10)", b.time_lbl.cget("text") == "1:10" and b.left() == 70,
        (b.time_lbl.cget("text"), b.left()))
    clock.t += 71
    b._tick()
    settle(root)
    chk("다 되면 서버에 묻지 않고 사라진다", b.win is None and b.end is None and b._job is None, (b.win, b.end))
    b.note({"lureLeft": 6065, "lureType": "WATER"})
    settle(root)
    chk("한 시간 넘게: 1:41:05 · 물 스프레이", b.time_lbl.cget("text") == "1:41:05"
        and b.chip.cget("text") == "물 스프레이", (b.time_lbl.cget("text"), b.chip.cget("text")))
    first = b.win
    b.note({"lureLeft": 300, "lureType": "GRASS"})
    settle(root)
    chk("타입이 바뀌면 칩을 다시 (풀)", b.chip.cget("text") == "풀 스프레이" and b.win is not first
        and b.chip.cget("bg").lower() == U.TYPE_COLOR["GRASS"].lower(), b.chip.cget("text"))
    b.note({"lureLeft": 0, "lureType": None})
    settle(root)
    chk("서버가 0 을 주면 바로 사라진다", b.win is None and b._job is None)
    b.note({"lureLeft": 30, "lureType": "FIRE"})
    b.note({"lureLeft": 30})
    chk("타입이 없어도 사라진다", b.win is None)

    chk("그리는 중에 난 예외가 없다", not errors, errors[:3])
    root.destroy()
    print("합계 OK %d FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
