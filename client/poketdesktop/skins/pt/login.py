# -*- coding: utf-8 -*-
"""플라티나 테마의 로그인 · 회원가입 - DP 틀(skins/dp/login.py) 그대로, 위 화면 빛깔만 시안 B 로.

DP 는 위 화면을 밤하늘 남빛 그라데이션으로 그린다 (코드가 섞어 만든 빛깔이라 derive 로는 안 옮겨진다).
플라티나는 시안의 머리 띠처럼 강철 그라데이션(#5b6676 → #465060)에 흰 제목, 아래 띠는 진한 캡슐 빛(#1e2630).
금빛 밑줄 · '접기' 는 주황. 자리 · 크기 · 글 · 하는 일은 DP 의 것 그대로다.

이 파일이 있으면 skins.view("login") 이 이것을 돌려주므로, 바꾸지 않는 것(PinEntry · StarterCard ·
ask_password)도 DP 의 것을 그대로 내보낸다.
"""
import tkinter as tk

from common.version import VERSION

from ... import item_icons
from ... import ui_common as U
from ..dp import font
from ..dp import login as DPL
from ..dp.login import PinEntry, StarterCard, ask_password, clamp_line  # noqa: F401  (DP 것 그대로 내보낸다)
from . import BAR1, BAR2, BAR_SH, ON_STEEL, ON_STEEL_DIM, ORANGE_TOP, RIM, WHITE
from . import _pt as P

W = DPL.W


class LoginWindow(DPL.LoginWindow):

    def _build(self):
        DPL.LoginWindow._build(self)
        try:
            self.top.configure(bg=BAR2)
        except tk.TclError:
            pass

    # ---------------- 위 화면 (DP 와 같은 자리, 강철 빛)
    def _paint_top(self):
        cv, s, H = self.top, U.h, self.TOP_H
        T = ("paint",)
        try:
            cv.delete("paint")
        except tk.TclError:
            return
        sy = H - self.STRIP
        P.gradient(cv, 0, 0, W, sy, BAR1, BAR2, tags=T)
        ph = item_icons.photo("POKEBALL", 60)
        if ph is not None:
            cv.create_image(W - s(64), (H - self.STRIP) // 2, image=ph, tags=T)
        P.band_title(cv, s(24), s(32), "포스크탑", font(24), tags=T)
        cv.create_rectangle(s(26), s(52), s(26) + s(64), s(54), fill=ORANGE_TOP, outline="", tags=T)
        cv.create_text(s(26), s(66), text="바탕화면에서 포켓몬을 만나고 키웁니다", fill=ON_STEEL, font=font(10),
                       anchor="w", tags=T)
        # 아래 띠: 서버 · 판
        my = sy + self.STRIP // 2
        cv.create_rectangle(0, sy, W, H, fill=BAR_SH, outline="", tags=T)
        cv.create_line(0, sy, W, sy, fill=RIM, width=2, tags=T)
        ver = cv.create_text(W - self.P, my, text="v" + VERSION, fill=ON_STEEL_DIM, font=font(9), anchor="e", tags=T)
        vx = cv.bbox(ver)[0]
        if self.server_open:
            lb = cv.create_text(self.P, my, text="서버", fill=ON_STEEL_DIM, font=font(9), anchor="w", tags=T)
            fold = cv.create_text(vx - s(14), my, text="접기", fill=ORANGE_TOP, font=font(9), anchor="e",
                                  tags=T + ("srv",))
            self._srv_box = (cv.bbox(lb)[2] + s(8), cv.bbox(fold)[0] - s(10))
        else:
            room = vx - self.P - s(14)
            cv.create_text(self.P, my, text=clamp_line(cv, self._server_text(), font(9), room), fill=WHITE,
                           font=font(9), anchor="w", tags=T + ("srv",))
