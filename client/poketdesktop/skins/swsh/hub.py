# -*- coding: utf-8 -*-
"""소드·실드 테마 - 허브 창 (시안 K 의 언어로 위 탭 줄 · 하위 탭 줄을 그린다 - 시안에 허브 그림은 없다).

틀(묶음 여섯 · 하위 탭 · 창 크기 · 탭을 오가는 일)은 DP 허브 그대로다. 칠하는 것만 바꾼다:

    위 탭 줄     남색 빗금 바탕 + 왼쪽 위 하늘색 모서리 · 오른쪽 아래 분홍 모서리.
                 묶음마다 흰 알약 (포켓몬 도구 그림 + 남색 굵은 글씨), 고른 묶음은 분홍 알약 + 흰 글씨 (.tabs span).
                 올리면 분홍 테. 아이콘은 DP 와 같은 도구 그림 (poke_icons - 직접 그리지 않는다).
    하위 탭 줄   빗금이 위 줄에서 이어지고, 작은 흰 알약 (고른 탭은 분홍).
    새 소식      빨간 점 (흰 테).
"""
import tkinter as tk

from ... import ui_common as U
from ... import ui_hub
from ..dp import font
from ..dp import hub as DPH
from ..dp import kit as K
from ..dp import poke_icons
from . import _sw as S

ICON = DPH.ICON
DOT = "#ff3b3b"


def pills(cv, x, y, h, items, current, hover, spec, pad, gap, icons=None):
    """알약 줄. items = [(열쇠, 글)]. 그린 칸들 [(열쇠, (x1, y1, x2, y2))]."""
    out = []
    for key, label in items:
        ph = (icons or {}).get(key)
        w = S.pill_w(cv, label, spec, pad, ph)
        S.pill(cv, x, y, x + w, y + h, label, on=key == current, hover=key == hover, spec=spec, icon=ph)
        out.append((key, (x, y, x + w, y + h)))
        x += w + gap
    return out


class HubWindow(DPH.HubWindow):

    def _make_sub(self, g, gf):
        body = DPH.HubWindow._make_sub(self, g, gf)
        try:
            self.subs[g].configure(bg=S.NAVY)
        except tk.TclError:
            pass
        return body

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
        S.stripes(cv, 0, 0, w, h, 0)
        S.corner(cv, 0, 0, U.h(150), "tl")
        S.corner(cv, w, h, U.h(46), "br")
        spec = font(11)
        f = K.tkfont_of(cv, spec)
        icons = dict((g, poke_icons.photo(ICON.get(g, "poke-ball"))) for g in self.groups)
        items = [(g, self.group_labels[g]) for g in self.groups]
        pad, gap = U.h(14), U.h(6)
        x0 = U.h(10)
        # 넘치면 여백만 줄인다 (글씨는 그대로)
        need = sum((icons[g].width() + U.h(6) if icons[g] is not None else 0) + f.measure(lb) for g, lb in items)
        room = w - 2 * x0 - gap * (len(items) - 1) - U.h(30)
        if need + 2 * pad * len(items) > room:
            pad = max(U.h(5), int((room - need) / (2.0 * len(items))))
        cur = ui_hub.GROUP_OF.get(self.current)
        ph = h - U.h(10)
        boxes = pills(cv, x0, (h - ph) // 2, ph, items, cur, self._hover, spec, pad, gap, icons)
        self._boxes = {}
        for g, (x1, y1, x2, _y2) in boxes:
            self._boxes[g] = (x1, x2)
            if any(k in self.badges for k in ui_hub.GROUP_TABS[g]):
                d = U.h(4)
                bx, by = x2 - U.h(7), y1 + U.h(5)
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=DOT, outline="#ffffff", width=2)

    # ---------------- 하위 탭 줄 ----------------
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
        S.stripes(cv, 0, 0, w, h, self.bar.winfo_height() or U.h(DPH.BAR_H))
        items = [(k, self.labels[k]) for k in ui_hub.GROUP_TABS[g]]
        ph = h - U.h(5)
        boxes = pills(cv, U.h(14), (h - ph) // 2, ph, items, self.last.get(g), self._sub_hover, font(11),
                      U.h(12), U.h(6))
        self._sub_boxes[g] = boxes
        d = U.h(3)
        for key, (_x1, y1, x2, _y2) in boxes:
            if key in self.badges:
                bx, by = x2 - U.h(6), y1 + U.h(4)
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=DOT, outline="#ffffff", width=1)
