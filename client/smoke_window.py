# -*- coding: utf-8 -*-
"""테두리 없는 창이 제자리에 뜨는지.

    python client/smoke_window.py

화면이 필요하다(창을 잠깐 만들었다 지운다).

## 왜 이 검사가 있나

윈도우에서 마우스를 포켓몬이나 풀숲 위에 올리면 설명이 그 위가 아니라
**화면 왼쪽 위 구석**에 떴다. 테두리 없는 창(overrideredirect)에
`-topmost` 를 geometry 뒤에 걸면 창이 (0, 0) 으로 튀기 때문이다.

맥은 정반대다 - **창이 뜬 뒤에** 걸어야 먹고, 만들자마자 걸면 조용히
씹힌다. 그래서 부르는 쪽에서 순서를 맞출 수가 없다(호출부가 열 군데다).
platform_*.raise_above 가 자리를 지켜 주기로 했고, 여기서 그것을 본다.
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-smoke-window"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, n=15):
    for _ in range(n):
        root.update()
        time.sleep(0.02)


def tip(root, x, y):
    """설명 풍선과 같은 방식으로 만든다 (wild_ui.show_hint / overlay 이름표)."""
    w = tk.Toplevel(root)
    w.overrideredirect(True)
    w.configure(bg="#101623")
    tk.Label(w, text="풀숲이 흔들린다!" + chr(10) + "눌러서 살펴보기",
             bg="#101623", fg="#5fd97a", padx=7, pady=3).pack()
    w.update_idletasks()
    w.geometry("+%d+%d" % (x, y))
    return w


def tip_and_raise(root, x, y):
    """실제 코드와 **같은 순서**로. 이게 핵심이다.

    wild_ui.show_hint / overlay 이름표는 geometry 를 놓자마자 곧바로
    raise_above 를 부른다. 그 사이에 창이 화면에 올라갈 틈이 없다.
    settle 을 한 번이라도 끼우면 버그가 재현되지 않는다 - 이미 자리를
    잡은 창은 -topmost 를 걸어도 안 움직이기 때문이다.
    """
    w = tip(root, x, y)
    PLAT.raise_above(w)
    return w


def main():
    root = tk.Tk()
    root.withdraw()
    try:
        # 화면 안쪽 어딘가. (0, 0) 과 확실히 다른 자리여야 한다.
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        X, Y = max(200, sw // 2), max(200, sh // 2)

        # **여기가 원래 버그다.** 창이 뜨기도 전에 -topmost 가 걸리면
        # 윈도우가 창을 (0, 0) 으로 옮겨 버린다.
        w = tip_and_raise(root, X, Y)
        settle(root)
        got = (w.winfo_rootx(), w.winfo_rooty())
        chk("놓은 자리에 뜬다", got == (X, Y), got)
        chk("구석으로 튀지 않는다", got != (0, 0), got)
        try:
            chk("항상 위가 실제로 걸렸다", bool(w.attributes("-topmost")),
                w.attributes("-topmost"))
        except Exception as e:                              # noqa: BLE001
            chk("항상 위가 실제로 걸렸다", False, e)
        w.destroy()

        # 두 번 불러도 안 흔들린다 (이펙트 레이어는 몇 프레임마다 부른다).
        w = tip_and_raise(root, X, Y)
        for _ in range(3):
            PLAT.raise_above(w)
        settle(root)
        got = (w.winfo_rootx(), w.winfo_rooty())
        chk("여러 번 불러도 그대로", got == (X, Y), got)
        w.destroy()

        # 자리를 안 잡은 창을 엉뚱한 데 붙박지 않는지. 만들자마자 부르고
        # 나중에 place 하는 곳이 있다(overlay.Pet, wild_ui 이름표).
        w = tk.Toplevel(root)
        w.overrideredirect(True)
        tk.Label(w, text="x", bg="#101623").pack()
        PLAT.raise_above(w)
        w.geometry("+%d+%d" % (X, Y))
        settle(root)
        got = (w.winfo_rootx(), w.winfo_rooty())
        chk("먼저 올리고 나중에 놓아도 된다", got == (X, Y), got)
        w.destroy()
    finally:
        try:
            root.destroy()
        except Exception:                                   # noqa: BLE001
            pass

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d  (%s)" % (OK, FAIL, PLAT.NAME))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
