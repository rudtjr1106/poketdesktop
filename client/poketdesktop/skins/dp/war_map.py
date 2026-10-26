# -*- coding: utf-8 -*-
"""DP 테마의 길드전 지도 - 타운맵처럼: 무늬 없는 옅은 바다, 길드 이름은 흰 이름표.

칸 · 선 · 확대 · 고르기는 기본 지도(ui_war_map.WarMap) 그대로다. 바탕(_backdrop)과 이름표(_label)만 칠한다.
이름은 칸 빛깔(진한 것 · 옅은 것 · 바다) 어디에 놓여도 읽히도록 흰 이름표 위에 진한 글씨로 쓴다 (테두리 글씨 아님).
"""
import tkinter.font as tkfont

from ... import ui_common as U
from ... import ui_war_map as WM
from . import FONT, INK
from . import kit as K
from .battle import mix

SEA, SEA_EDGE = "#b4daf2", "#7ab0d6"


class WarMap(WM.WarMap):

    def __init__(self, parent, on_pick=None, on_hover=None):
        WM.WarMap.__init__(self, parent, on_pick, on_hover)
        self.cv.configure(bg=SEA)
        self.font = tkfont.Font(root=self.cv, family=FONT, size=U.pt(8))
        self.label_font = tkfont.Font(root=self.cv, family=FONT, size=U.pt(9))

    def _backdrop(self):
        """무늬 없는 바다와 가는 테. 'bg' 꼬리표라 확대 · 끌기에 안 움직인다."""
        cv = self.cv
        w, h = cv.winfo_width(), cv.winfo_height()
        if w <= 1:
            return
        cv.create_rectangle(1, 1, w - 2, h - 2, outline=SEA_EDGE, width=2, tags=("bg",))
        cv.tag_lower("bg")

    def recolor(self):
        WM.WarMap.recolor(self)
        self.cv.tag_raise("label")        # 칸 선을 다시 올리면 이름표가 선에 가려진다

    def _label(self, px, py, text, color):
        """흰 이름표. 판 바깥 가장자리의 이름이 캔버스 밖으로 나가면 안으로 민다 (글씨는 줄이지 않는다)."""
        cv, s = self.cv, U.h
        self._nlabel = getattr(self, "_nlabel", 0) + 1
        tg = "lb%d" % self._nlabel
        tags = ("map", "label", tg)
        f = K.tkfont_of(cv, (FONT, U.pt(9)))
        w, h = f.measure(text) + s(12), f.metrics("linespace") + s(4)
        K.rrect(cv, px - w / 2.0, py - h / 2.0, px + w / 2.0, py + h / 2.0, s(5), fill="#ffffff",
                outline=mix(color, "#000000", 0.45), width=1, tags=tags)
        cv.create_text(px, py, text=text, fill=INK, font=(FONT, U.pt(9)), anchor="center", tags=tags)
        bb, cw, pad = cv.bbox(tg), cv.winfo_width(), s(6)
        if bb and cw > 1:
            dx = (pad - bb[0]) if bb[0] < pad else ((cw - pad) - bb[2]) if bb[2] > cw - pad else 0
            if dx:
                cv.move(tg, dx, 0)
