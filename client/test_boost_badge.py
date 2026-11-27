# -*- coding: utf-8 -*-
"""풀숲 부스트 남은 시간 띠 (2.1.3 스프레이 #445 · 2.5.9 버닝 #1016) - 진짜 Tk.

    python client/test_boost_badge.py

시계는 가짜(now)를 넣어 돌린다 - 1초씩 기다리지 않는다. 못 박는 것:

  1. 서버가 남은 초를 주면 주 화면 작업 영역 오른쪽 아래에 '불꽃 스프레이 2:05' 띠가 뜬다.
  2. 초마다 줄고(1:05), 다 되면 서버에 묻지 않고 사라진다. 서버가 0 · 타입 없음을 주면 바로 사라진다.
  3. 옛 서버(boosts 없음 = None)면 그대로 둔다. 다시 받으면 끝나는 시각을 서버 값으로 맞춘다.
  4. 타입이 바뀌면 칩 글 · 빛깔이 바뀐다. 한 시간 넘게 남으면 '1:41:05'.
  5. 버닝 부스터도 띠에 뜬다 (#1016 - 하나뿐인 부스터를 쓰면 가방에서 사라져 남은 시간을 볼 곳이 없었다).
     둘 다 켜져 있으면 한 띠에 두 줄 (위 버닝 · 아래 스프레이). 하나가 끝나면 남은 줄만, 둘 다 끝나면 사라진다.
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


def clock_text(secs):
    return BB.clock(secs)


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
    chk("  '불꽃 스프레이' 칩 + 2:05", b.chips["lure"].cget("text") == "불꽃 스프레이" and b.times["lure"].cget("text") == "2:05",
        (b.chips["lure"].cget("text"), b.times["lure"].cget("text")))
    chk("  칩 빛깔은 그 타입 빛깔", b.chips["lure"].cget("bg").lower() == U.TYPE_COLOR["FIRE"].lower(), b.chips["lure"].cget("bg"))
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
    chk("1분 뒤 1:05", b.times["lure"].cget("text") == "1:05", b.times["lure"].cget("text"))
    b.note({"lureLeft": 70, "lureType": "FIRE"})
    chk("다시 받으면 서버 값으로 (1:10)", b.times["lure"].cget("text") == "1:10" and b.left() == 70,
        (b.times["lure"].cget("text"), b.left()))
    clock.t += 71
    b._tick()
    settle(root)
    chk("다 되면 서버에 묻지 않고 사라진다", b.win is None and not b.ends and b._job is None, (b.win, b.ends))
    b.note({"lureLeft": 6065, "lureType": "WATER"})
    settle(root)
    chk("한 시간 넘게: 1:41:05 · 물 스프레이", b.times["lure"].cget("text") == "1:41:05"
        and b.chips["lure"].cget("text") == "물 스프레이", (b.times["lure"].cget("text"), b.chips["lure"].cget("text")))
    first = b.win
    b.note({"lureLeft": 300, "lureType": "GRASS"})
    settle(root)
    chk("타입이 바뀌면 칩을 다시 (풀)", b.chips["lure"].cget("text") == "풀 스프레이" and b.win is not first
        and b.chips["lure"].cget("bg").lower() == U.TYPE_COLOR["GRASS"].lower(), b.chips["lure"].cget("text"))
    b.note({"lureLeft": 0, "lureType": None})
    settle(root)
    chk("서버가 0 을 주면 바로 사라진다", b.win is None and b._job is None)
    b.note({"lureLeft": 30, "lureType": "FIRE"})
    b.note({"lureLeft": 30})
    chk("타입이 없어도 사라진다", b.win is None)

    print("5. 버닝 부스터 (#1016)")
    b.note({"burnLeft": 7200, "lureLeft": 0, "lureType": None})
    settle(root)
    chk("버닝만 켜져 있어도 띠가 뜬다", b.win is not None and b.win.winfo_ismapped(), b.win)
    chk("  '버닝 부스터' 칩 + 2:00:00", list(b.chips) == ["burn"] and b.chips["burn"].cget("text") == "버닝 부스터"
        and b.times["burn"].cget("text") == "2:00:00", (list(b.chips), b.times.get("burn") and b.times["burn"].cget("text")))
    chk("  칩 빛깔은 불꽃 타입과 다르다", b.chips["burn"].cget("bg").lower() == BB.BURN_COLOR
        and BB.BURN_COLOR != U.TYPE_COLOR["FIRE"].lower(), b.chips["burn"].cget("bg"))
    one_h = b.win.winfo_height()
    b.note({"burnLeft": 7190, "lureLeft": 125, "lureType": "FIRE"})
    settle(root)
    chk("둘 다 켜지면 한 띠에 두 줄 (위 버닝 · 아래 스프레이)", sorted(b.chips) == ["burn", "lure"]
        and b.chips["burn"].master.winfo_y() < b.chips["lure"].master.winfo_y()
        and b.win.winfo_height() > one_h, (sorted(b.chips), b.win.winfo_height(), one_h))
    gx, gy = b.win.winfo_x(), b.win.winfo_y()
    ww, wh = b.win.winfo_width(), b.win.winfo_height()
    chk("  두 줄이어도 오른쪽 아래 모서리에 붙는다",
        abs((gx + ww) - (x2 - BB.MARGIN)) <= 2 and abs((gy + wh) - (y2 - BB.MARGIN)) <= 2, (gx, gy, ww, wh, x2, y2))
    clock.t += 126
    b._tick()
    settle(root)
    chk("스프레이가 끝나면 버닝 줄만 남는다", list(b.chips) == ["burn"] and b.kind is None
        and b.times["burn"].cget("text") == clock_text(7190 - 126) and b._job is not None,
        (list(b.chips), b.kind, b.times.get("burn") and b.times["burn"].cget("text")))
    b.note({"burnLeft": 3, "lureLeft": 600, "lureType": "ICE"})
    settle(root)
    clock.t += 4
    b._tick()
    settle(root)
    chk("버닝이 먼저 끝나면 스프레이 줄만", list(b.chips) == ["lure"] and b.chips["lure"].cget("text") == "얼음 스프레이",
        list(b.chips))
    clock.t += 600
    b._tick()
    settle(root)
    chk("둘 다 끝나면 사라진다", b.win is None and not b.ends and b._job is None, (b.win, b.ends))
    b.note({"burnLeft": 60})
    b.note({"lureLeft": 0, "lureType": None})
    settle(root)
    chk("버닝 칸이 없는 응답(옛 서버의 2.1.x)이면 버닝 줄도 치운다", b.win is None and not b.ends)

    chk("그리는 중에 난 예외가 없다", not errors, errors[:3])
    root.destroy()
    print("합계 OK %d FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
