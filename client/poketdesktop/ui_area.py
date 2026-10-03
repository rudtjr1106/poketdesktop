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

**모니터마다 덮개를 하나씩** 깐다 (PLAT.screens). 둘째 모니터에도 그릴 수 있고,
끌다가 옆 모니터로 넘어가면 두 화면에 걸쳐 그려진다.

예전에는 모든 모니터를 아우르는 덮개 **하나**를 깔고, 그 창 안의 좌표에 창의
자리를 더해 화면 좌표를 냈다. 그러면 두 가지가 어긋난다 (제보, 1.9.1):

  · 모니터마다 배율이 다르면(노트북 150% + 외부 100%) 창 하나가 한 배율로만
    그려져서, 다른 쪽 모니터에서는 그린 자리와 포켓몬이 가는 자리가 다르다.
  · 창이 달라는 자리에 안 놓이면(맥의 메뉴 막대, 화면보다 큰 창) 그만큼
    전부 밀린다.

그래서 **포인터의 화면 좌표**(x_root, y_root)를 그대로 쓴다. 포켓몬 창을 놓을
때 쓰는 좌표와 같은 것이라, 덮개가 어디에 어떤 배율로 놓였든 그린 자리로 간다.

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
    """모니터마다 덮개를 깔고 사각형 하나를 받는다. 답은 화면 좌표."""

    def __init__(self, root, current=None):
        self.root = root
        self.result = None
        self.start = None             # 누른 자리 (화면 좌표)
        self.panes = []               # 모니터마다 {win, cv, ox, oy, rect, chip, size, note}
        self._top_job = None
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        try:
            scrs = [s for s in PLAT.screens(sw, sh) if s[2] > s[0] and s[3] > s[1]]
        except Exception:                                   # noqa: BLE001
            scrs = []
        self.screens = scrs or [(0, 0, sw, sh)]
        for i, scr in enumerate(self.screens):
            self.panes.append(self._pane(scr, i == 0, current))
        self.win = self.panes[0]["win"]          # 기다릴 창 (주 화면)
        self._stay_on_top()

    def _pane(self, scr, first, current):
        x1, y1, x2, y2 = scr
        w, h = x2 - x1, y2 - y1
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.geometry("%dx%d+%d+%d" % (w, h, x1, y1))
        try:
            win.attributes("-alpha", ALPHA)
        except tk.TclError:
            pass
        PLAT.raise_above(win)
        cv = tk.Canvas(win, width=w, height=h, bg=DIM,
                       highlightthickness=0, bd=0, cursor="crosshair")
        cv.pack(fill="both", expand=True)
        pane = {"win": win, "cv": cv, "ox": x1, "oy": y1, "w": w, "h": h,
                "rect": None, "chip": None, "size": None, "note": None}
        # 지금 영역을 옅게 그려 둔다. 어디를 쓰고 있었는지 보여야 다시 그리기 쉽다.
        if current and len(current) == 4:
            a, b, c, d = current
            cv.create_rectangle(a - x1, b - y1, c - x1, d - y1,
                                outline=U.LINE2, dash=(6, 4), width=2)
        self._guide(pane, first)
        cv.bind("<Button-1>", self._press)
        cv.bind("<B1-Motion>", self._drag)
        cv.bind("<ButtonRelease-1>", self._release)
        win.bind("<Escape>", lambda _e: self._cancel())
        win.protocol("WM_DELETE_WINDOW", self._cancel)
        return pane

    # ---------------- 그리기 ----------------
    def _guide(self, pane, first):
        """무엇을 하면 되는지. 화면마다 위쪽 가운데에 둔다."""
        cv = pane["cv"]
        box = tk.Frame(cv, bg=U.BG2, highlightthickness=2,
                       highlightbackground=U.ACCENT)
        inner = tk.Frame(box, bg=U.BG2)
        inner.pack(padx=18, pady=12)
        tk.Label(inner, text="포켓몬이 돌아다닐 영역을 끌어서 그리세요",
                 bg=U.BG2, fg=U.FG, font=U.FONT_H).pack(anchor="w")
        text = "놓으면 정해집니다.  ·  Esc 를 누르면 그만둡니다."
        if len(self.screens) > 1:
            text += "\n어느 모니터에든 그릴 수 있습니다."
        pane["note"] = tk.Label(inner, text=text, bg=U.BG2, fg=U.FG_DIM,
                                font=U.FONT_S, justify="left")
        pane["note"].pack(anchor="w", pady=(4, 0))
        cv.create_window(pane["w"] // 2, U.h(80), window=box, anchor="n")

    def _stay_on_top(self):
        """덮개를 계속 맨 위에 둔다 (도트가 위로 올라오지 않게)."""
        try:
            if not self.win.winfo_exists():
                return
            for p in self.panes:
                PLAT.keep_on_top(p["win"])
            self._top_job = self.win.after(TOP_EVERY_MS, self._stay_on_top)
        except tk.TclError:
            self._top_job = None

    def _say(self, text, color=None):
        for p in self.panes:
            try:
                p["note"].configure(text=text, fg=color or U.FG_DIM)
            except tk.TclError:
                pass

    def _draw(self, x1, y1, x2, y2):
        """화면 좌표의 사각형을 **모든 덮개에** 그린다 (덮개마다 제 자리만큼 뺀다)."""
        a, b = min(x1, x2), min(y1, y2)
        c, d = max(x1, x2), max(y1, y2)
        text = "%d x %d" % (c - a, d - b)
        for p in self.panes:
            cv, ox, oy = p["cv"], p["ox"], p["oy"]
            la, lb, lc, ld = a - ox, b - oy, c - ox, d - oy
            if p["rect"] is None:
                # **창 전체가 반투명이다.** 그래서 안을 옅게만 채우고(stipple) 테두리를
                # 굵게 둔다. 크기 글자는 바탕을 깔아야 읽힌다 - 그냥 글자만 두면
                # 흐려져서 안 보인다.
                p["rect"] = cv.create_rectangle(la, lb, lc, ld, outline=U.ACCENT,
                                                width=3, fill=U.ACCENT, stipple="gray12")
                p["chip"] = cv.create_rectangle(0, 0, 0, 0, fill=U.ACCENT, outline=U.ACCENT)
                p["size"] = cv.create_text(0, 0, anchor="nw", text="",
                                           fill=U.ACCENT_DARK, font=U.FONT_B)
            else:
                cv.coords(p["rect"], la, lb, lc, ld)
            cv.itemconfigure(p["size"], text=text)
            # 사각형이 화면 위쪽에 붙어 있으면 글자를 안쪽에 둔다 (밖이면 잘린다).
            ty = lb - U.h(26) if lb > U.h(30) else lb + 6
            cv.coords(p["size"], la + 8, ty + 3)
            bb = cv.bbox(p["size"])
            if bb:
                cv.coords(p["chip"], bb[0] - 6, bb[1] - 3, bb[2] + 6, bb[3] + 3)
            cv.tag_raise(p["chip"])
            cv.tag_raise(p["size"])

    # ---------------- 마우스 ----------------
    # **화면 좌표(x_root, y_root)를 쓴다.** 덮개 안의 좌표(e.x)에 덮개의 자리를
    # 더하면, 덮개가 달라는 자리·배율로 안 놓였을 때 그만큼 어긋난다 (맨 위 설명).
    def _press(self, e):
        self.start = (e.x_root, e.y_root)
        self._draw(e.x_root, e.y_root, e.x_root, e.y_root)

    def _drag(self, e):
        if self.start:
            self._draw(self.start[0], self.start[1], e.x_root, e.y_root)

    def _release(self, e):
        if not self.start:
            return
        x1, y1 = self.start
        self.start = None
        a, b = min(x1, e.x_root), min(y1, e.y_root)
        c, d = max(x1, e.x_root), max(y1, e.y_root)
        if c - a < MIN_W or d - b < MIN_H:
            self._say("너무 작습니다. 최소 %d x %d 로 다시 그려 주세요. (지금 %d x %d)"
                      % (MIN_W, MIN_H, c - a, d - b), U.DANGER)
            return
        self.result = (a, b, c, d)
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
        # 주 화면의 덮개(기다리는 창)를 맨 나중에 닫는다
        for p in reversed(self.panes):
            try:
                p["win"].destroy()
            except tk.TclError:
                pass

    # ---------------- 띄우기 ----------------
    def show(self):
        PLAT.activate()
        for p in reversed(self.panes):
            try:
                p["win"].lift()
            except tk.TclError:
                pass
            PLAT.surface(p["win"])
        try:
            self.win.focus_force()
        except tk.TclError:
            pass
        self.root.wait_window(self.win)
        return self.result


def pick_area(root, current=None):
    """영역을 그려서 받는다. (x1, y1, x2, y2) 또는 그만두면 None."""
    return AreaPicker(root, current).show()
