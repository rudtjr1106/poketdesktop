# -*- coding: utf-8 -*-
"""블랙·화이트 테마 - 허브 창.

시안에 허브 그림은 없다 - 시안 H 의 말(짙은 회색 바탕 · 가는 테의 알약 · 하늘빛 테와 번지는 빛으로 고름)로
그린다:

    위 탭 줄     짙은 바탕 위에 묶음마다 알약 하나 (도구 그림 + 이름). 고른 묶음은 하늘빛 테 · 둘레 빛 · 하늘빛 글씨
                 (시안 가방의 '지닌 도구' 고리처럼), 올리면 한 단계 밝은 판. 아래는 가는 테 한 줄.
    하위 탭 줄   시안 가방의 줄 세우기 칸(.seg)처럼 작은 알약, 고른 탭은 하늘빛 테 · 하늘빛 글씨.
    새 소식      빨간 점

창 크기 · 묶음 · 하위 탭 · 오가는 일은 DP 허브(skins/dp/hub.py) 그대로 - 칠하는 것만 바꾼다.
아이콘은 직접 그리지 않는다 (poke_icons).
"""
import tkinter as tk

from ... import ui_common as U
from ... import ui_hub
from ..dp import font
from ..dp import hub as DPH
from ..dp import kit as K
from ..dp import poke_icons
from . import BG, CYAN, DIMT, DOT, LINE, TEXT
from . import _art as A

BAR_H = 44          # 위 탭 줄 (검사: 46 을 넘지 않는다)
SUB_H = 34          # 하위 탭 줄 (알약이 들어갈 만큼)


class HubWindow(DPH.HubWindow):

    def __init__(self, app):
        DPH.HubWindow.__init__(self, app)
        self.win.configure(bg=BG)
        self.bar.configure(bg=BG, height=U.h(BAR_H))

    # ---------------- 위 탭 줄 (묶음) ----------------
    def _paint_bar(self):
        cv = self.bar
        try:
            cv.delete("all")
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w < 50:
            return
        spec = font(11)
        f = K.tkfont_of(cv, spec)
        icons = dict((g, poke_icons.photo(DPH.ICON.get(g, "poke-ball"))) for g in self.groups)
        iw = dict((g, ph.width() if ph is not None else 0) for g, ph in icons.items())
        gap, pad, between = U.h(6), U.h(14), U.h(8)
        x0 = U.h(12)
        room = w - 2 * x0 - between * (len(self.groups) - 1)

        def widths(p):
            return [iw[g] + gap + f.measure(self.group_labels[g]) + 2 * p for g in self.groups]
        want = widths(pad)
        if sum(want) > room:                                  # 넘치면 여백만 줄인다 (글씨는 그대로)
            cut = (sum(want) - room) / float(2 * len(want))
            pad = max(U.h(6), int(pad - cut))
            want = widths(pad)
        cv.create_rectangle(0, 0, w, h, fill=BG, outline="")
        cv.create_line(0, h - 1, w, h - 1, fill=LINE)
        cur = ui_hub.GROUP_OF.get(self.current)
        x = x0
        self._boxes = {}
        ph = U.h(32)
        y1 = (h - 1 - ph) // 2
        y2 = y1 + ph
        for g, tw in zip(self.groups, want):
            on = g == cur
            A.pill(cv, x, y1, x + tw, y2, on=on, hover=(g == self._hover), on_bg=True)
            cx = x + pad
            cy = (y1 + y2) // 2
            if icons[g] is not None:
                cv.create_image(cx + iw[g] // 2, cy, image=icons[g])
            cv.create_text(cx + iw[g] + gap, cy, text=self.group_labels[g], fill=CYAN if on else TEXT, font=spec,
                           anchor="w")
            if any(k in self.badges for k in ui_hub.GROUP_TABS[g]):
                d = U.h(4)
                bx, by = x + tw - U.h(8), y1 + U.h(6)
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=DOT, outline=BG, width=2)
            self._boxes[g] = (x - between // 2, x + tw + between // 2)
            x += tw + between

    # ---------------- 하위 탭 줄 ----------------
    def _make_sub(self, g, gf):
        cv = tk.Canvas(gf, height=U.h(SUB_H), bg=BG, highlightthickness=0, bd=0)
        cv.pack(side="top", fill="x")
        cv.bind("<Configure>", lambda _e, gg=g: self._paint_sub(gg))
        cv.bind("<Motion>", lambda e, gg=g: self._sub_motion(gg, e))
        cv.bind("<Leave>", lambda _e, gg=g: self._sub_left(gg))
        cv.bind("<Button-1>", lambda e, gg=g: self._sub_click(gg, e))
        self.subs[g] = cv
        body = tk.Frame(gf, bg=BG)
        body.pack(side="top", fill="both", expand=True)
        return body

    def _paint_sub(self, g):
        cv = self.subs.get(g)
        if cv is None:
            return
        try:
            cv.delete("all")
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w < 50:
            return
        cv.create_rectangle(0, 0, w, h, fill=BG, outline="")
        cv.create_line(0, h - 1, w, h - 1, fill=LINE)
        spec = font(11)
        f = K.tkfont_of(cv, spec)
        cur = self.last.get(g)
        x = U.h(14)
        ph = U.h(24)
        y1 = (h - 1 - ph) // 2
        boxes = []
        d = U.h(3)
        for key in ui_hub.GROUP_TABS[g]:
            label = self.labels[key]
            tw = f.measure(label) + U.h(28)
            on = key == cur
            A.pill(cv, x, y1, x + tw, y1 + ph, on=on, hover=(key == self._sub_hover), on_bg=True)
            cv.create_text(x + tw // 2, y1 + ph // 2, text=label, fill=CYAN if on else DIMT, font=spec,
                           anchor="center")
            if key in self.badges:
                bx, by = x + tw - U.h(8), y1 + U.h(6)
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=DOT, outline=BG, width=1)
            boxes.append((key, (x, 0, x + tw, h)))
            x += tw + U.h(8)
        self._sub_boxes[g] = boxes
