# -*- coding: utf-8 -*-
"""포켓몬이 돌아다닐 영역을 **화면에 직접 그려서** 정한다.

화면 갈무리(캡처)처럼 화면 전체에 덮개를 깔고 끌어서 사각형을 그린다.
끌기를 놓으면 그 사각형이 활동 영역이 된다. Esc 를 누르면 그만둔다.

## 왜 화면 위에 그리나

지금까지는 '좁게 / 보통 / 넓게 / 화면 전체' 네 가지뿐이었고, 자리는 늘
오른쪽 아래였다. 그런데 화면을 어떻게 쓰는지는 사람마다 다르다 - 작업
표시줄 위 띠만 쓰고 싶은 사람, 둘째 모니터에만 두고 싶은 사람이 있다.
숫자로 넣게 하면(폭·높이·여백) 몇 번을 고쳐 봐야 원하는 자리가 나온다.
직접 그리면 한 번에 끝난다.

## 모니터가 여럿일 때

덮개는 **모든 모니터를 아우르는 사각형**에 깐다(PLAT.virtual_screen).
그래서 둘째 모니터에도 그릴 수 있고, 두 화면에 걸쳐 그릴 수도 있다.

## 너무 작게 그리면

포켓몬이 들어갈 자리가 없다. 그때는 창을 닫지 않고 다시 그리라고 적는다 -
말없이 무시하면 고장으로 읽힌다(기술 배우기 창에서 겪은 것과 같다).
"""
import tkinter as tk

from . import platform_os as PLAT
from . import ui_common as U

# 이보다 작으면 포켓몬이 돌아다닐 자리가 안 나온다.
MIN_W, MIN_H = 200, 150

DIM = "#0b1020"          # 덮개 색. 창 전체에 반투명으로 깔린다
ALPHA = 0.5

# 덮개를 다시 맨 위로 올리는 주기(ms). **도트도 '항상 위' 다.** Overlay 가
# 3초마다 도트를 다시 올리므로(overlay.TOP_EVERY_MS), 가만히 두면 그리는
# 중에 포켓몬이 덮개 위로 올라온다. 이쪽이 더 자주 올라오면 된다.
TOP_EVERY_MS = 700


class AreaPicker(object):
    """화면 전체에 덮개를 깔고 사각형 하나를 받는다. 답은 절대 좌표."""

    def __init__(self, root, current=None):
        self.root = root
        self.result = None
        self.start = None
        self.rect_id = None
        self.size_id = None
        self.chip_id = None
        self.ox, self.oy, x2, y2 = PLAT.virtual_screen(
            root.winfo_screenwidth(), root.winfo_screenheight())
        w, h = x2 - self.ox, y2 - self.oy

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry("%dx%d+%d+%d" % (w, h, self.ox, self.oy))
        try:
            self.win.attributes("-alpha", ALPHA)
        except tk.TclError:
            pass
        PLAT.raise_above(self.win)

        self.cv = tk.Canvas(self.win, width=w, height=h, bg=DIM,
                            highlightthickness=0, bd=0, cursor="crosshair")
        self.cv.pack(fill="both", expand=True)

        # 지금 영역을 옅게 그려 둔다. 어디를 쓰고 있었는지 보여야 다시 그리기 쉽다.
        if current and len(current) == 4:
            a, b, c, d = current
            self.cv.create_rectangle(a - self.ox, b - self.oy,
                                     c - self.ox, d - self.oy,
                                     outline=U.LINE2, dash=(6, 4), width=2)

        self._guide(w)
        self.cv.bind("<Button-1>", self._press)
        self.cv.bind("<B1-Motion>", self._drag)
        self.cv.bind("<ButtonRelease-1>", self._release)
        self.win.bind("<Escape>", lambda _e: self._cancel())
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        self._top_job = None
        self._stay_on_top()

    # ---------------- 그리기 ----------------
    def _guide(self, w):
        """무엇을 하면 되는지. 화면 위쪽 가운데에 둔다."""
        box = tk.Frame(self.cv, bg=U.BG2, highlightthickness=2,
                       highlightbackground=U.ACCENT)
        inner = tk.Frame(box, bg=U.BG2)
        inner.pack(padx=18, pady=12)
        tk.Label(inner, text="포켓몬이 돌아다닐 영역을 끌어서 그리세요",
                 bg=U.BG2, fg=U.FG, font=U.FONT_H).pack(anchor="w")
        self.note = tk.Label(
            inner, text="놓으면 정해집니다.  ·  Esc 를 누르면 그만둡니다.",
            bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S)
        self.note.pack(anchor="w", pady=(4, 0))
        self.cv.create_window(w // 2, U.h(80), window=box, anchor="n")

    def _stay_on_top(self):
        """덮개를 계속 맨 위에 둔다 (도트가 위로 올라오지 않게)."""
        try:
            if not self.win.winfo_exists():
                return
            PLAT.keep_on_top(self.win)
            self._top_job = self.win.after(TOP_EVERY_MS, self._stay_on_top)
        except tk.TclError:
            self._top_job = None

    def _say(self, text, color=None):
        self.note.configure(text=text, fg=color or U.FG_DIM)

    def _draw(self, x1, y1, x2, y2):
        a, b = min(x1, x2), min(y1, y2)
        c, d = max(x1, x2), max(y1, y2)
        if self.rect_id is None:
            # **창 전체가 반투명이다.** 그래서 안을 옅게만 채우고(stipple) 테두리를
            # 굵게 둔다. 크기 글자는 바탕을 깔아야 읽힌다 - 그냥 글자만 두면
            # 45% 로 흐려져서 안 보인다.
            self.rect_id = self.cv.create_rectangle(a, b, c, d, outline=U.ACCENT,
                                                    width=3, fill=U.ACCENT,
                                                    stipple="gray12")
            self.chip_id = self.cv.create_rectangle(0, 0, 0, 0, fill=U.ACCENT,
                                                    outline=U.ACCENT)
            self.size_id = self.cv.create_text(0, 0, anchor="nw", text="",
                                               fill=U.ACCENT_DARK, font=U.FONT_B)
        else:
            self.cv.coords(self.rect_id, a, b, c, d)
        text = "%d x %d" % (c - a, d - b)
        self.cv.itemconfigure(self.size_id, text=text)
        # 사각형이 화면 위쪽에 붙어 있으면 글자를 안쪽에 둔다 (밖이면 잘린다).
        ty = b - U.h(26) if b > U.h(30) else b + 6
        self.cv.coords(self.size_id, a + 8, ty + 3)
        bb = self.cv.bbox(self.size_id)
        if bb:
            self.cv.coords(self.chip_id, bb[0] - 6, bb[1] - 3, bb[2] + 6, bb[3] + 3)
        self.cv.tag_raise(self.chip_id)
        self.cv.tag_raise(self.size_id)

    # ---------------- 마우스 ----------------
    def _press(self, e):
        self.start = (e.x, e.y)
        self._draw(e.x, e.y, e.x, e.y)

    def _drag(self, e):
        if self.start:
            self._draw(self.start[0], self.start[1], e.x, e.y)

    def _release(self, e):
        if not self.start:
            return
        x1, y1 = self.start
        self.start = None
        a, b = min(x1, e.x), min(y1, e.y)
        c, d = max(x1, e.x), max(y1, e.y)
        if c - a < MIN_W or d - b < MIN_H:
            self._say("너무 작습니다. 최소 %d x %d 로 다시 그려 주세요. (지금 %d x %d)"
                      % (MIN_W, MIN_H, c - a, d - b), U.DANGER)
            return
        self.result = (a + self.ox, b + self.oy, c + self.ox, d + self.oy)
        self._close()

    def _cancel(self):
        self.result = None
        self._close()

    def _close(self):
        if self._top_job is not None:
            try:
                self.win.after_cancel(self._top_job)
            except tk.TclError:
                pass
            self._top_job = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    # ---------------- 띄우기 ----------------
    def show(self):
        PLAT.activate()
        try:
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass
        PLAT.surface(self.win)
        self.root.wait_window(self.win)
        return self.result


def pick_area(root, current=None):
    """영역을 그려서 받는다. (x1, y1, x2, y2) 또는 그만두면 None."""
    return AreaPicker(root, current).show()
