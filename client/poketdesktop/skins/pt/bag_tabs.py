# -*- coding: utf-8 -*-
"""플라티나 테마 - 가방 탭 (도구 · 기술머신). DP 가방 탭 그대로이고, 두 칸만 시안의 것(bag · tms)으로 바꿔 끼운다."""
from ..dp import bag_tabs as DPBT
from . import STEEL
from .bag import BagWindow
from .tms import TmWindow


class BagTabs(DPBT.BagTabs):
    CLASSES = {"items": BagWindow, "tms": TmWindow}

    def __init__(self, root, app, parent=None):
        DPBT.BagTabs.__init__(self, root, app, parent)
        self.win.configure(bg=STEEL)
