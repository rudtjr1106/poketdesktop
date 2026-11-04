# -*- coding: utf-8 -*-
"""타입 스프레이 남은 시간 (2.1.3, 게시판 #445 니뉴) — 바탕화면 오른쪽 아래의 작은 띠.

    badge = BoostBadge(app)
    badge.note({"lureLeft": 초, "lureType": "FIRE"})     서버가 준 대로 띄우거나 치운다

스프레이를 켜 두면 남은 시간이 가방에서 그 도구를 골라야만 보였다. 이제 켜져 있는 동안 주 화면 작업 영역의
오른쪽 아래(작업표시줄 · 독 바로 위)에 '불꽃 스프레이 1:41:05' 처럼 띠가 떠 있고, 초마다 줄어들다가 다 되면
사라진다 (사용자 결정: 오른쪽 하단, 끝나면 없어지게).

남은 초는 서버가 야생 확인(약 90초마다) · 동기화 · 가방 응답에 싣는다 (boosts.state). 받을 때마다 끝나는 시각을
다시 맞추고, 그 사이에는 이 컴퓨터의 시계로 센다 - 띠가 서버에 묻지 않는다. 옛 서버(싣지 않음)면 아무것도 안 한다.

누르는 일은 없다 (띠는 알림일 뿐이다). 긴급 숨기기는 따로 손보지 않아도 된다 - 떠 있는 Toplevel 을 다 거둔다.
"""
import time
import tkinter as tk

from . import platform_os as PLAT
from . import ui_common as U

TICK_MS = 1000
MARGIN = 14            # 작업 영역 모서리에서 띄우는 거리


def clock(secs):
    """남은 초 -> '1:41:05' · '41:05' · '0:09'."""
    s = max(0, int(secs))
    h, rest = divmod(s, 3600)
    m, s = divmod(rest, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def type_kr(t):
    from .ui_tms import TYPE_KR
    return TYPE_KR.get(t, t or "?")


class BoostBadge(object):
    def __init__(self, app, now=time.monotonic):
        self.app = app
        self.now = now
        self.end = None            # 끝나는 시각 (now() 기준)
        self.kind = None           # 타입 열쇠
        self.win = None
        self._job = None

    # ---------------- 서버가 준 것
    def note(self, boosts):
        """{"lureLeft", "lureType"} 를 받는다. None(옛 서버 · 그 칸 없음)이면 그대로 둔다."""
        if boosts is None:
            return
        left = int(boosts.get("lureLeft") or 0)
        kind = boosts.get("lureType")
        if left <= 0 or not kind:
            return self.hide()
        self.end = self.now() + left
        if kind != self.kind:
            self.kind = kind
            self._close_win()                  # 타입이 바뀌면 빛깔 칩부터 다시 만든다
        self._show()

    def left(self):
        return 0 if self.end is None else max(0, int(round(self.end - self.now())))

    # ---------------- 띠
    def _show(self):
        if self.win is None:
            self._build()
        self._paint()
        if self._job is None:
            self._job = self.app.root.after(TICK_MS, self._tick)

    def _build(self):
        root = self.app.root
        w = tk.Toplevel(root)
        w.overrideredirect(True)
        w.configure(bg=U.LINE)                            # 1px 테
        body = tk.Frame(w, bg=U.TIP_BG, padx=8, pady=4)
        body.pack(padx=1, pady=1)
        color = U.TYPE_COLOR.get(self.kind, U.BG2)
        self.chip = U.chip(body, "%s 스프레이" % type_kr(self.kind), color, font=U.FONT_S, padx=6, pady=1)
        self.chip.pack(side="left")
        self.time_lbl = tk.Label(body, text="", bg=U.TIP_BG, fg=U.FG, font=U.FONT_B, padx=0)
        self.time_lbl.pack(side="left", padx=(8, 0))
        self.win = w
        PLAT.raise_above(w)                               # (윈도우: 쓰던 창의 포커스는 안 가져간다 - focus_guard)

    def _paint(self):
        if self.win is None:
            return
        try:
            self.time_lbl.configure(text=clock(self.left()))
            self.win.update_idletasks()
            self._place()
        except tk.TclError:
            self.win = None

    def _place(self):
        w = self.win
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        try:
            _x1, _y1, x2, y2 = PLAT.work_area(sw, sh)
        except Exception:                                   # noqa: BLE001
            x2, y2 = sw, sh
        ww, wh = w.winfo_reqwidth(), w.winfo_reqheight()
        pos = "+%d+%d" % (x2 - ww - MARGIN, y2 - wh - MARGIN)
        if pos != getattr(self, "_pos", None):              # 글 폭이 바뀔 때만 옮긴다 (초마다 옮기면 깜빡인다)
            self._pos = pos
            w.geometry(pos)

    def _tick(self):
        self._job = None
        if self.end is None:
            return
        if self.left() <= 0:
            return self.hide()                              # 다 됐다 - 서버에 묻지 않고 바로 치운다
        self._paint()
        self._job = self.app.root.after(TICK_MS, self._tick)

    def hide(self):
        self.end = None
        self.kind = None
        if self._job is not None:
            try:
                self.app.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None
        self._close_win()

    def _close_win(self):
        w, self.win = self.win, None
        self._pos = None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass
