# -*- coding: utf-8 -*-
"""DP 테마의 '빛나는 돌' 표식 - 도트 머리 위에 뜨는 작은 보라 이름표.

DP 의 이름판처럼 모서리를 깎은 보라 판에 흰 글씨 ('빛나는 돌' · '메가스톤 고르기').
(v2: 테두리 글씨 · 손으로 그린 별을 걷고, 머리 위를 가리지 않게 작게 줄였다. 판이 작아 아이콘도 뺐다.) 반짝일 때는 판이 밝은 보라로 바뀐다. 자리 잡기 · 숨기기 · 누르기 · 반짝이는 시계는 기본 표식(bond_stone.StoneBadge)
그대로고, 여기서는 짓는 것(_build)과 반짝임 한 칸(_paint)만 덮는다. 표식 창은 맥에서 투명이 클릭 통과와
부딪히므로 모서리가 비치지 않게 창 바탕을 테두리 빛깔로 칠한다.
"""
import tkinter as tk

from ... import bond_stone as BS
from ... import ui_common as U
from . import PURPLE, PURPLE_HI, PURPLE_LO, WHITE, font
from . import kit as K

NAMES = {"ready": "빛나는 돌", "claim": "메가스톤 고르기"}


class StoneBadge(BS.StoneBadge):

    def _build(self, w):
        s = U.h
        spec = font(9)
        text = NAMES.get(self.kind, NAMES["ready"])
        f = K.tkfont_of(w, spec)
        bw = f.measure(text) + s(20)
        bh = f.metrics("linespace") + s(8)
        w.configure(bg=PURPLE_LO)
        cv = tk.Canvas(w, width=bw, height=bh, bg=PURPLE_LO, highlightthickness=0, bd=0, cursor="hand2")
        cv.pack()
        self._body = K.clipped(cv, 2, 2, bw - 2, bh - 2, s(5), PURPLE)
        K.text(cv, bw // 2, bh // 2, text, spec, fill=WHITE, anchor="center")
        cv.bind("<ButtonRelease-1>", self._click)
        self.label = cv
        self.text = text

    def _paint(self, lit):
        self.label.itemconfigure(self._body, fill=PURPLE_HI if lit else PURPLE)
