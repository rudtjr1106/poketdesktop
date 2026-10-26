# -*- coding: utf-8 -*-
"""에메랄드 테마 - 설정 창. DP 배치 그대로이고, 값 막대의 채운 빛만 남색으로.

DP 의 값 막대는 '#3a6ad0'(파랑)인데, 이 빛깔은 기술 분류 '특수'와 같아서 빛깔 옮기기(KEEP)가 그대로 둔다 -
그래서 여기서 막대만 골라 바꾼다.
"""
import tkinter as tk

from ..dp import settings as DPS
from ..dp.settings import *          # noqa: F401,F403  (DP 설정 모듈의 다른 이름도 그대로)
from . import NAVY

BAR_DP = "#3a6ad0"


class SettingsWindow(DPS.SettingsWindow):

    def _paint(self):
        DPS.SettingsWindow._paint(self)
        cv = self.cv
        try:
            for i in range(len(self.rows)):
                for it in cv.find_withtag("bar%d" % i):
                    if cv.itemcget(it, "fill").lower() == BAR_DP:
                        cv.itemconfigure(it, fill=NAVY)
        except (tk.TclError, AttributeError):
            pass
