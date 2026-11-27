# -*- coding: utf-8 -*-
"""굴러가는 메뉴 U.ScrollMenu (2.5.9, 게시판 #1015 '박스 여는 탭이 너무 길어서 잘 안 보인다') - 진짜 Tk.

    python client/test_scroll_menu.py

못 박는 것:

  1. 마흔여덟 줄이어도 visible(12) 줄 높이만 보이고 스크롤 막대가 있다. 단을 늘리지 않는다 (cols 1).
  2. head 줄은 위에, fixed 줄은 아래에 늘 보인다 (굴려도 그대로).
  3. focus 번째 줄이 보이게 열린다 (끝 박스도).
  4. 휠로 굴러간다 - 윈도우 꼴(delta 120) · 맥 꼴(delta 1~3) 둘 다. 이 메뉴 창에 건 것으로도,
     포커스를 가진 다른 창(박스 창)의 install_wheel 로도 (윈도우 Tk 은 휠을 포커스 창으로 보낸다).
  5. 줄이 적으면 막대 없이 다 보인다. 화면이 낮으면 그 화면 안에 든다.
  6. 줄을 누르면 메뉴가 닫히고 그 명령이 불린다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-scrollmenu-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402
from tkinter import ttk                                     # noqa: E402

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


def settle(root, n=6):
    for _ in range(n):
        root.update()


def rows_of(n, picked):
    return [{"text": "박스 %d  (30/30)" % (i + 1), "checked": i == 0,
             "command": (lambda x=i: picked.append(x))} for i in range(n)]


def visible_rows(menu):
    """캔버스 창 안에 다 보이는 줄 번호들."""
    cv = menu.canvas
    top, bot = cv.winfo_rooty(), cv.winfo_rooty() + cv.winfo_height()
    out = []
    for i, w in enumerate(menu.inner.winfo_children()):
        y0 = w.winfo_rooty()
        if y0 >= top - 1 and y0 + w.winfo_height() <= bot + 1:
            out.append(i)
    return out


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append("%s: %s" % (e.__name__, v))

    # install_wheel 이 거는 함수를 손에 쥔다 (가짜 이벤트로 부르려고)
    real_install = U.install_wheel
    caught = {}

    def install(top):
        real_install(top)
        script = top.bind("<MouseWheel>")
        caught[str(top)] = script
    U.install_wheel = install

    picked = []
    head = [{"text": "여러 마리 골라 옮기기 · 놓아주기…", "checked": False, "command": lambda: picked.append("multi")}]
    fixed = [{"text": "박스 안 순서", "header": True},
             {"text": "잡은 순", "checked": True, "command": lambda: picked.append("order")}]

    print("1. 마흔여덟 줄")
    m = U.ScrollMenu(root, rows_of(48, picked), 300, 80, width=220, head=head, fixed=fixed, focus=0)
    settle(root)
    shown = visible_rows(m)
    bars = [w for w in m.canvas.master.winfo_children() if isinstance(w, ttk.Scrollbar)]
    chk("한 단 (cols 1)", m.cols == 1, m.cols)
    chk("열두 줄만 보인다", len(shown) == 12 and shown[0] == 0, shown)
    chk("스크롤 막대가 있다", len(bars) == 1 and bars[0].winfo_ismapped(), bars)
    lo, hi = m.canvas.yview()
    chk("맨 위에서 시작 (focus 0)", lo == 0.0 and hi < 0.5, (lo, hi))
    texts = [w.cget("text") for w in m.win.winfo_children()[0].winfo_children()[0].winfo_children()
             if isinstance(w, tk.Label)]
    chk("head 줄이 위에", any("여러 마리" in t for t in texts), texts)

    print("2. 휠")
    win_top = m.win
    # 이 메뉴 창에 건 휠 (맥은 마우스 밑의 창으로 온다)
    chk("메뉴 창에 휠이 걸려 있다", bool(caught.get(str(win_top))), list(caught))
    cv = m.canvas
    x, y = cv.winfo_rootx() + 20, cv.winfo_rooty() + cv.winfo_height() // 2
    before = cv.yview()[0]
    win_top.event_generate("<MouseWheel>", delta=-120, x=20, y=20, rootx=x, rooty=y, when="now")
    settle(root, 3)
    after_win = cv.yview()[0]
    chk("윈도우 꼴 휠 한 칸(-120)이면 아래로 굴러간다", after_win > before, (before, after_win))
    win_top.event_generate("<MouseWheel>", delta=-2, x=20, y=20, rootx=x, rooty=y, when="now")
    settle(root, 3)
    chk("맥 꼴 휠(-2)도 굴러간다", cv.yview()[0] > after_win, (after_win, cv.yview()[0]))
    foot_lbl = [w for w in m.win.winfo_children()[0].winfo_children()[-1].winfo_children()
                if isinstance(w, tk.Label) and w.cget("text").endswith("잡은 순")]
    chk("굴려도 아래 고정 줄은 그대로 보인다", foot_lbl and foot_lbl[0].winfo_ismapped()
        and foot_lbl[0].winfo_rooty() > cv.winfo_rooty() + cv.winfo_height() - 2, foot_lbl)

    # 포커스를 가진 다른 창(박스 창)이 휠을 받아도 마우스 밑의 메뉴가 굴러간다 (윈도우)
    other = tk.Toplevel(root)
    other.geometry("200x200+700+80")
    U.install_wheel(other)
    settle(root)
    cv.yview_moveto(0)
    settle(root)
    other.event_generate("<MouseWheel>", delta=-240, x=5, y=5, rootx=x, rooty=y, when="now")
    settle(root, 3)
    chk("포커스 창(박스 창)이 받은 휠로도 메뉴가 굴러간다", cv.yview()[0] > 0, cv.yview())
    other.destroy()
    m.close()

    print("3. focus")
    m = U.ScrollMenu(root, rows_of(48, picked), 300, 80, width=220, fixed=fixed, focus=47)
    settle(root)
    shown = visible_rows(m)
    chk("끝 박스(47)가 보이게 열린다", 47 in shown and len(shown) == 12, shown)
    m.close()
    m = U.ScrollMenu(root, rows_of(48, picked), 300, 80, width=220, fixed=fixed, focus=20)
    settle(root)
    shown = visible_rows(m)
    chk("가운데 박스(20)는 가운데쯤", 20 in shown and shown[0] >= 10, shown)

    print("4. 누르기")
    lab = m.inner.winfo_children()[20]
    lab.event_generate("<Button-1>", x=3, y=3)
    settle(root)
    chk("누르면 그 명령 · 메뉴는 닫힌다", picked[-1:] == [20] and not m.alive(), (picked[-3:], m.alive()))

    print("5. 적을 때 · 낮은 화면")
    m = U.ScrollMenu(root, rows_of(5, picked), 300, 80, width=220, fixed=fixed, focus=4)
    settle(root)
    bars = [w for w in m.canvas.master.winfo_children() if isinstance(w, ttk.Scrollbar)]
    chk("다섯 줄이면 막대 없이 다 보인다", not bars and visible_rows(m) == [0, 1, 2, 3, 4], (bars, visible_rows(m)))
    m.close()
    real_screen = U.screen_at
    try:
        U.screen_at = lambda r, x, y: (0, 0, 1024, 300)
        m = U.ScrollMenu(root, rows_of(48, picked), 300, 40, width=220, head=head, fixed=fixed, focus=0)
        settle(root)
        chk("높이 300 화면: 화면 안에 다 들어온다 (줄 수를 줄인다)",
            m.win.winfo_rooty() + m.win.winfo_height() <= 300 and 3 <= len(visible_rows(m)) < 12,
            (m.win.winfo_rooty(), m.win.winfo_height(), len(visible_rows(m))))
        m.close()
    finally:
        U.screen_at = real_screen

    U.install_wheel = real_install
    chk("그리는 중에 난 예외가 없다", not errors, errors[:3])
    root.destroy()
    print("합계 OK %d FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
