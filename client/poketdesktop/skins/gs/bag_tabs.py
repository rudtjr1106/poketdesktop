# -*- coding: utf-8 -*-
"""금·은 테마 - 가방 탭 (도구 · 기술머신). DP 가방 탭 그대로, 두 칸만 금·은 것으로."""
from ..dp import bag_tabs as DPBT
from .bag import BagWindow
from .tms import TmWindow


class BagTabs(DPBT.BagTabs):
    CLASSES = {"items": BagWindow, "tms": TmWindow}
