# -*- coding: utf-8 -*-
"""소드·실드 테마 - 가방 탭 (도구 · 기술머신). DP 가방 탭에 이 테마의 두 칸을 끼운다 (바탕은 남색)."""
from ..dp import bag_tabs as DPBT
from .bag import BagWindow
from .tms import TmWindow


class BagTabs(DPBT.BagTabs):
    CLASSES = {"items": BagWindow, "tms": TmWindow}
