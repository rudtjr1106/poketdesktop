# -*- coding: utf-8 -*-
"""블랙·화이트 테마 - 가방 탭 (도구 · 기술머신).

DP 가방 탭(skins/dp/bag_tabs.py) 그대로이고, 두 칸만 BW 것(bag.py · tms.py)으로 바꿔 끼운다
(DP 가방 탭이 칸 클래스를 직접 가리키므로 이 파일이 있어야 한다).
"""
from ..dp import bag_tabs as DPBT
from .bag import BagWindow
from .tms import TmWindow


class BagTabs(DPBT.BagTabs):
    CLASSES = {"items": BagWindow, "tms": TmWindow}
