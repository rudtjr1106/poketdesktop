# -*- coding: utf-8 -*-
"""배틀 창의 '메가진화' 단추 (시즌 3).

관장·실시간·레이드 창이 같이 쓴다.

## 어디에 붙나

**메시지 막대 오른쪽 끝.** 명령 칸 오른쪽 기둥에 넣으면 그 아래 기술 설명
칸이 50px 줄어 설명이 잘린다(관장 창은 설명 칸이 60px 남짓이다). 메시지
막대는 명령을 고르는 동안 '무엇을 할까?' 한 줄뿐이라 자리가 남는다.

## 켜고 끄기

  · 누르면 켜지고, 다음 **기술**과 함께 보낸다. 교체·기권에는 안 실린다.
  · 한 번 보내면 꺼진다. 한 판에 한 번은 서버가 막는다 - 쓰고 나면
    canMega 가 False 로 와서 단추가 아예 안 뜬다.
  · 명령을 고르는 때가 아니면(재생 중·교체 고르는 중) 숨긴다.
"""
from . import ui_common as U

ON_FILL = "#8a5cf6"
ON_HOVER = "#9f7af8"
ON_SHADOW = "#35206b"
TEXT = "메가진화"


class MegaToggle(object):
    def __init__(self, bar, before=None, height=34):
        self.bar = bar
        self.before = before
        self.on = False
        self.shown = False
        self.btn = U.ghost_button(bar, TEXT, self.toggle, height=height)
        b = self.btn
        self._off = (b.fill, b._fg, b.hover, b._shadow)

    def toggle(self):
        self.set(not self.on)

    def set(self, on):
        self.on = bool(on)
        b = self.btn
        if self.on:
            b.fill, b._fg, b.hover, b._shadow = ON_FILL, "#ffffff", ON_HOVER, ON_SHADOW
        else:
            b.fill, b._fg, b.hover, b._shadow = self._off
        b.configure(state="normal")          # 바탕·그림자·글자를 새 색으로 다시 칠한다

    def show(self, can):
        """명령을 고를 때 canMega 면 보인다. 숨기면 꺼진다."""
        can = bool(can)
        if can and not self.shown:
            kw = {"side": "right", "padx": (8, 12)}
            if self.before is not None:
                kw["before"] = self.before
            self.btn.holder.pack(**kw)
        elif not can and self.shown:
            self.btn.holder.pack_forget()
        self.shown = can
        if not can and self.on:
            self.set(False)

    def take(self):
        """이번 기술과 함께 보낼 값. 한 번 꺼내면 꺼진다."""
        v = bool(self.on and self.shown)
        if self.on:
            self.set(False)
        return v
