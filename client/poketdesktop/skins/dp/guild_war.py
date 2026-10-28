# -*- coding: utf-8 -*-
"""DP 테마의 길드전 칸 - 길드 창(비밀기지)의 방 하나 (v2).

왼쪽은 타운맵 같은 지도(skins/dp/war_map.py), 오른쪽은 흰 판들(가는 테 · 파란 꼬리표 제목)을 굴린다.
판 안의 내용 · 단추 · 하는 일은 기본 길드전 칸(ui_guild_war.WarTab) 그대로다 - 판(_card)과 바탕만 바꾼다
(판 안의 글 · 단추 빛깔은 위젯 엔진이 DP 로 옮긴다).

v2: 1차는 판마다 두꺼운 진한 테 + 보라 띠 + 테두리 글씨였고, 왼쪽 기둥이 넓어 기본 창 크기에서 지도가
손가락 두 개 폭으로 줄었다. 이제 길드 창이 이 방에서는 기둥을 아이콘 줄로 접고(guild.py), 오른쪽 칸을
조금 좁히고(기본 330 -> 300) 바깥 여백을 줄여 지도를 넓힌다.
"""
import tkinter as tk
from tkinter import ttk

from ... import ui_common as U
from ... import ui_guild_war as GW
from . import WHITE, font
from . import kit as K
from .guild import BASE_BG, GLINE

SIDE_W = 300                 # 지도 옆 칸의 폭 (기본 330 - 지도 자리를 조금 더 준다)


class WarTab(GW.WarTab):
    SIDE_W = SIDE_W

    def __init__(self, gw, parent):
        GW.WarTab.__init__(self, gw, parent)
        s = U.h
        for w in (self.holder, self.left, self.right, self.cv, self.inner, self.hint):
            w.configure(bg=BASE_BG)
        self.holder.pack_configure(padx=s(10), pady=(s(8), s(6)))
        for ch in self.right.winfo_children():                 # 굴림 막대를 DP 것으로
            if isinstance(ch, ttk.Scrollbar):
                ch.destroy()
        sb = K.Scroll(self.right, self.cv, BASE_BG)
        sb.pack(side="right", fill="y", before=self.cv)
        self.cv.configure(yscrollcommand=sb.set)

    def _layout(self, wide):
        was = self.wide
        GW.WarTab._layout(self, wide)
        if wide and not was:
            self.right.configure(width=self._side_w())      # (보통 크기에서는 U.h(SIDE_W) 그대로)
            self.left.pack_configure(padx=(0, U.h(8)))

    def _card(self, title=None):
        """흰 판 한 겹 (가는 테). 제목은 파란 꼬리표."""
        s = U.h
        c = tk.Frame(self.inner, bg=WHITE, highlightthickness=1, highlightbackground=GLINE,
                     highlightcolor=GLINE, bd=0)
        c.pack(fill="x", pady=(0, s(8)))
        if title:
            th = K.tkfont_of(c, font(10)).metrics("linespace") + U.h(6)
            rib = tk.Canvas(c, bg=WHITE, height=th, highlightthickness=0, bd=0)
            rib.pack(fill="x", padx=s(12), pady=(s(10), s(4)))

            def draw(_e, cv=rib, t=title):
                cv.delete("all")
                K.tag(cv, 0, 0, t)
            rib.bind("<Configure>", draw)
        return c
