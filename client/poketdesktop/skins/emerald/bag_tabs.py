# -*- coding: utf-8 -*-
"""에메랄드 테마 - 가방 탭 (도구 · 기술머신).

DP 가방 탭 그대로이고, 두 칸만 에메랄드 것(시안 A 의 가방 - bag.GBABag)으로 바꿔 끼운다.
"""
from ..dp import bag_tabs as DPBT
from .bag import BagWindow
from .tms import TmWindow


class BagTabs(DPBT.BagTabs):
    CLASSES = {"items": BagWindow, "tms": TmWindow}
