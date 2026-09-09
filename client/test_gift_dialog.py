# -*- coding: utf-8 -*-
"""선물 알림 창이 **어느 OS 에서나** 제대로 뜨는가.

이 창은 맥에서 만들었다. 윈도우는 글꼴이 다르고(맑은 고딕) 같은 pt 라도
글자 폭과 높이가 달라서, 맥에서 멀쩡해도 거기서는 눌릴 수 있다.

실제로 만들면서 두 번 걸렸다.

  · 창 높이가 18px 모자라 아래가 줄줄이 눌렸다. 단추 글씨('고맙습니다')
    까지 잘려 있었다.
  · `Label(width=3)` 은 글자일 때는 3글자지만 **그림일 때는 3픽셀**이다.
    아이콘이 납작해지고, 그림이 없는 줄과 들여쓰기도 어긋났다.

창을 진짜로 띄우므로 화면이 있는 곳에서만 돈다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_bag                             # noqa: E402
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


def squeezed(win):
    """눌린 것을 모은다. 필요한 크기가 실제 크기보다 크면 잘리는 중이다."""
    out = []

    def walk(w):
        for c in w.winfo_children():
            try:
                if c.winfo_height() > 1 and c.winfo_width() > 1:
                    txt = ""
                    if "text" in c.keys():
                        txt = str(c.cget("text"))[:14]
                    if c.winfo_reqheight() > c.winfo_height() + 1:
                        out.append(("세로", c.winfo_class(), txt,
                                    c.winfo_reqheight(), c.winfo_height()))
                    elif (txt.strip() and not int(c.cget("wraplength") or 0)
                          and c.winfo_reqwidth() > c.winfo_width() + 1):
                        out.append(("가로", c.winfo_class(), txt,
                                    c.winfo_reqwidth(), c.winfo_width()))
            except Exception:
                pass
            walk(c)
    walk(win)
    return out


class FakeApp(object):
    """그림을 받으러 가지 않는다. 없으면 없는 대로 떠야 한다."""

    def __init__(self, root):
        self.root = root
        self.api = None
        self.dex = None

    def notify(self, m):
        pass


GIFTS = [
    {"kind": "item", "item": "FLOWERBALL", "count": 1, "name": "플라워볼",
     "title": "50명 기념 선물", "message": "함께해 주셔서 고맙습니다!"},
    {"kind": "money", "item": None, "count": 5000, "name": "돈",
     "title": "50명 기념 선물", "message": ""},
    {"kind": "balls", "item": None, "count": 5, "name": "몬스터볼",
     "title": "50명 기념 선물", "message": ""},
]


def show(root, app, gifts, hold=700):
    """창을 띄우고 재고 닫는다. (재어 둔 것, 창 크기)"""
    box = {}

    def snap():
        for w in root.winfo_children():
            if isinstance(w, tk.Toplevel) and w.winfo_viewable():
                root.update_idletasks()
                box["sq"] = squeezed(w)
                box["size"] = (w.winfo_width(), w.winfo_height())
                box["rows"] = _rows(w)
                w.destroy()
                return
        root.after(120, snap)

    root.after(hold, snap)
    ui_bag.announce_gifts(root, app, gifts)
    return box.get("sq", []), box.get("size", (0, 0)), box.get("rows", [])


def _rows(win):
    """선물 한 줄의 이름 라벨 x 좌표. 줄이 맞는지 본다."""
    xs = []

    def walk(w):
        for c in w.winfo_children():
            try:
                if (c.winfo_class() == "Label" and "text" in c.keys()
                        and "×" in str(c.cget("text"))):
                    xs.append(c.winfo_rootx() - win.winfo_rootx())
            except Exception:
                pass
            walk(c)
    walk(win)
    return xs


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    app = FakeApp(root)
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)"
          % (U.FAMILY, U.FONT[1], U.BASE_PT))

    print("\n=== 선물 셋 ===")
    sq, size, xs = show(root, app, GIFTS)
    chk("창이 떴다", size[0] > 100 and size[1] > 100, size)
    chk("눌린 것이 없다", not sq, sq[:4])
    chk("줄이 셋", len(xs) == 3, xs)
    # 그림이 있는 줄과 없는 줄의 이름이 같은 x 에서 시작해야 한다.
    # Label 의 width 를 글자 수로 주면 여기가 어긋난다.
    chk("이름이 같은 자리에서 시작한다", len(set(xs)) <= 1, xs)

    print("\n=== 하나만 ===")
    sq, size, xs = show(root, app, GIFTS[:1])
    chk("눌린 것이 없다", not sq, sq[:4])
    chk("줄이 하나", len(xs) == 1, xs)

    print("\n=== 여덟 개 넘게 (넘치면 접어야 한다) ===")
    many = [dict(GIFTS[1], count=i + 1, name="돈") for i in range(12)]
    sq, size, xs = show(root, app, many)
    chk("눌린 것이 없다", not sq, sq[:4])
    chk("여덟 줄까지만 그린다", len(xs) <= 8, len(xs))

    print("\n=== 글이 길어도 안 잘린다 ===")
    longish = [dict(GIFTS[0],
                    title="아주 긴 제목을 넣어 봅니다 " * 2,
                    message="설명도 길게 넣어 봅니다. " * 4)]
    sq, size, xs = show(root, app, longish)
    chk("눌린 것이 없다", not sq, sq[:4])

    print("\n=== 빈 목록이면 창을 안 띄운다 ===")
    ui_bag.announce_gifts(root, app, [])
    root.update_idletasks()
    tops = [w for w in root.winfo_children()
            if isinstance(w, tk.Toplevel) and w.winfo_viewable()]
    chk("창이 안 떴다", not tops, tops)

    root.destroy()
    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
