# -*- coding: utf-8 -*-
"""뜨는 메뉴가 바깥을 누르면 닫히는가, 그리고 글꼴이 커져도 안 눌리는가.

## 왜 이 검사가 있나

우클릭 메뉴(몬스터볼 던지기 · 포켓몬 정보보기)가 **다른 데를 눌러도
안 닫혔다.** 화면을 덮는 catcher 창이 있었지만 맥에서는 부족했다 -
Tk 은 앱이 활성일 때만 클릭을 받아서, 다른 앱의 창을 누르면 그 클릭이
우리에게 오지 않는다.

그래서 Tk 을 거치지 않고 눌린 단추를 직접 물어본다. 여기서는 그 판단만
떼어 내 돌린다 - 진짜 마우스는 안 움직인다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

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
        print("  FAIL %s   %s" % (name, got))


ROWS = [{"text": "몬스터볼 던지기", "command": lambda: None},
        {"text": "포켓몬 정보보기", "command": lambda: None},
        None,
        {"text": "놓아주기", "command": lambda: None}]


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)

    real = PLAT.mouse_buttons_down

    def press(m, down, inside):
        """단추 상태와 커서 위치를 흉내내고 한 번 살펴보게 한다."""
        PLAT.mouse_buttons_down = lambda: down
        m._inside = lambda: inside
        m._watch()

    print("=== 바깥을 누르면 닫힌다 ===")
    m = U.PopupMenu(root, ROWS, 400, 300)
    root.update_idletasks()
    chk("메뉴가 떴다", m.alive())
    chk("감시 고리가 돈다", m._watch_job is not None)

    m._was_down = 0
    press(m, 1, inside=True)
    root.update_idletasks()
    chk("메뉴 안을 누르면 안 닫힌다", m.alive())

    m._was_down = 0
    press(m, 1, inside=False)
    root.update_idletasks()
    chk("메뉴 밖을 누르면 닫힌다", not m.alive())
    chk("닫히면 감시 고리도 멈춘다", m._watch_job is None)

    print("\n=== 누른 채로 열려도 그 눌림으론 안 닫힌다 ===")
    # 우클릭한 손가락이 아직 안 떨어졌는데 그걸로 닫아 버리면
    # 메뉴가 뜨자마자 사라진다.
    PLAT.mouse_buttons_down = lambda: 2       # 오른쪽 단추를 누른 채
    m2 = U.PopupMenu(root, ROWS, 400, 300)
    m2._inside = lambda: False
    m2._watch()
    m2._watch()
    root.update_idletasks()
    chk("뜨자마자 사라지지 않는다", m2.alive())

    press(m2, 0, inside=False)                # 손을 뗐다
    press(m2, 1, inside=False)                # 다시 눌렀다
    root.update_idletasks()
    chk("떼었다 다시 누르면 닫힌다", not m2.alive())

    print("\n=== 여러 개가 겹치지 않는다 ===")
    PLAT.mouse_buttons_down = lambda: 0
    a = U.PopupMenu(root, ROWS, 100, 100)
    b = U.PopupMenu(root, ROWS, 300, 300)
    root.update_idletasks()
    chk("새로 열면 앞의 것이 닫힌다", not a.alive() and b.alive())
    U.close_all()
    chk("close_all 로 전부 닫힌다", not b.alive())

    print("\n=== 어느 OS 에서나 뜬다 ===")
    # 커서 이름 하나로 죽은 적이 있다. `pointinghand` 는 맥에만 있어서
    # 윈도우 Tk 이 `bad cursor spec` 으로 그 자리에서 멈췄다.
    made = None
    try:
        made = U.PopupMenu(root, ROWS, 200, 200)
        root.update_idletasks()
        ok = made.alive()
    except Exception as e:                                  # noqa: BLE001
        ok = False
        print("     못 만들었다: %s" % e)
    chk("이 OS 에서 메뉴가 만들어진다", ok)
    if made is not None and made.alive():
        cur = []

        def walkc(w):
            for c in w.winfo_children():
                try:
                    if str(c.cget("cursor")):
                        cur.append(str(c.cget("cursor")))
                except Exception:
                    pass
                walkc(c)
        walkc(made.win)
        chk("커서 이름이 이 OS 에서 통한다 (%s)" % (sorted(set(cur)) or "없음"),
            True)
        U.close_all()

    print("\n=== 글꼴이 커져도 글이 안 눌린다 ===")
    # 줄 높이를 픽셀로 박아 두면 글꼴을 키웠을 때 세로로 눌린다.
    m3 = U.PopupMenu(root, ROWS, 400, 300)
    root.update_idletasks()
    squeezed = []

    def walk(w):
        for c in w.winfo_children():
            if (c.winfo_height() > 1
                    and c.winfo_reqheight() > c.winfo_height() + 1):
                squeezed.append((str(c.cget("text"))[:14]
                                 if "text" in c.keys() else c.winfo_class(),
                                 c.winfo_reqheight(), c.winfo_height()))
            walk(c)
    walk(m3.win)
    chk("메뉴 안에 눌린 글이 없다", not squeezed, squeezed[:4])
    chk("줄 높이가 글꼴을 따라간다", U.h(30) >= 30, (U.BASE_PT, U.h(30)))
    U.close_all()

    PLAT.mouse_buttons_down = real
    root.destroy()
    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
