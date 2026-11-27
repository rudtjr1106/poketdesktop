# -*- coding: utf-8 -*-
"""풀숲 부스트 남은 시간 (2.1.3 스프레이, 게시판 #445 니뉴 · 2.5.9 버닝, #1016 뱅이슝) — 바탕화면 오른쪽 아래의 작은 띠.

    badge = BoostBadge(app)
    badge.note({"burnLeft": 초, "lureLeft": 초, "lureType": "FIRE"})     서버가 준 대로 띄우거나 치운다

스프레이를 켜 두면 남은 시간이 가방에서 그 도구를 골라야만 보였다. 이제 켜져 있는 동안 주 화면 작업 영역의
오른쪽 아래(작업표시줄 · 독 바로 위)에 '불꽃 스프레이 1:41:05' 처럼 띠가 떠 있고, 초마다 줄어들다가 다 되면
사라진다 (사용자 결정: 오른쪽 하단, 끝나면 없어지게).

버닝 부스터도 같다 (2.5.9). 2.5.3 에는 가방 설명에만 적었는데, 하나뿐인 부스터를 쓰면 가방에서 사라져 남은 시간을
볼 곳이 없었다 (11/27 게시판 #1016). 둘 다 켜져 있으면 한 띠에 두 줄 - 위가 버닝, 아래가 스프레이.

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
ROWS = ("burn", "lure")            # 띠 안의 줄 차례 (위에서부터)
BURN_COLOR = "#f0643c"             # 버닝 칩 - 불꽃 타입 빛깔(#ff9d55)과 헷갈리지 않게 더 붉게


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
        self.ends = {}             # 줄 -> 끝나는 시각 (now() 기준). 줄은 ROWS 의 "burn" · "lure"
        self.kind = None           # 스프레이 타입 열쇠
        self.win = None
        self.chips = {}            # 줄 -> 칩 Label
        self.times = {}            # 줄 -> 남은 시간 Label
        self._job = None

    # ---------------- 서버가 준 것
    def note(self, boosts):
        """{"burnLeft", "lureLeft", "lureType"} 를 받는다. None(옛 서버 · 그 칸 없음)이면 그대로 둔다."""
        if boosts is None:
            return
        t = self.now()
        ends = {}
        burn = int(boosts.get("burnLeft") or 0)
        if burn > 0:
            ends["burn"] = t + burn
        lure = int(boosts.get("lureLeft") or 0)
        kind = boosts.get("lureType")
        if lure > 0 and kind:
            ends["lure"] = t + lure
        else:
            kind = None
        if not ends:
            return self.hide()
        if set(ends) != set(self.ends) or kind != self.kind:
            self._close_win()                  # 줄이 늘거나 줄었거나 타입이 바뀌면 칩부터 다시 만든다
        self.kind = kind
        self.ends = ends
        self._show()

    def left(self, row="lure"):
        end = self.ends.get(row)
        return 0 if end is None else max(0, int(round(end - self.now())))

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
        self.chips, self.times = {}, {}
        for row in ROWS:
            if row not in self.ends:
                continue
            line = tk.Frame(body, bg=U.TIP_BG)
            line.pack(side="top", anchor="e", pady=(0 if not self.chips else 3, 0))
            if row == "burn":
                text, color = "버닝 부스터", BURN_COLOR
            else:
                text, color = "%s 스프레이" % type_kr(self.kind), U.TYPE_COLOR.get(self.kind, U.BG2)
            chip = U.chip(line, text, color, font=U.FONT_S, padx=6, pady=1)
            chip.pack(side="left")
            lbl = tk.Label(line, text="", bg=U.TIP_BG, fg=U.FG, font=U.FONT_B, padx=0)
            lbl.pack(side="left", padx=(8, 0))
            self.chips[row], self.times[row] = chip, lbl
        self.win = w
        PLAT.raise_above(w)                               # (윈도우: 쓰던 창의 포커스는 안 가져간다 - focus_guard)

    def _paint(self):
        if self.win is None:
            return
        try:
            for row, lbl in self.times.items():
                lbl.configure(text=clock(self.left(row)))
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
        if not self.ends:
            return
        done = [row for row in self.ends if self.left(row) <= 0]
        if done:                                            # 다 된 줄은 서버에 묻지 않고 바로 뺀다
            for row in done:
                del self.ends[row]
            if "lure" not in self.ends:
                self.kind = None
            if not self.ends:
                return self.hide()
            self._close_win()                               # 남은 줄만으로 띠를 다시 (한 줄이 되면 폭 · 높이가 준다)
            return self._show()
        self._paint()
        self._job = self.app.root.after(TICK_MS, self._tick)

    def hide(self):
        self.ends = {}
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
        self.chips, self.times = {}, {}
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass
