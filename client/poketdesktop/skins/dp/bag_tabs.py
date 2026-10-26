# -*- coding: utf-8 -*-
"""DP 테마 - 가방 탭 (도구 · 기술머신).

DP 에서는 기술머신도 가방의 주머니 하나다. 그래서 [도구 | 기술머신] 고르기 단추 대신, 두 칸이 같은
몬스터볼 다이얼을 그리고 '기술머신' 주머니를 누르면 기술머신 칸으로, 다른 주머니를 누르면 도구 칸의 그
주머니로 넘어간다 (scene.POCKETS).
"""
from ... import ui_bag_tabs as BT
from ... import ui_common as U
from . import BEZEL
from .bag import BagWindow
from .tms import TmWindow


class Switch(object):
    """칸마다 넘겨 주는 '다른 칸으로 가기'.

    부르면(switch(parent)) 기본 칸의 머리줄에 넣을 [도구 | 기술머신] 단추를 만든다 - 기술머신 칸은
    아직 기본 화면이라 이것을 쓴다. DP 도구 칸은 show() 로 넘어가고, register() 로 점(새 기술머신)을 받는다.
    """

    def __init__(self, tabs, key):
        self.tabs = tabs
        self.key = key

    def __call__(self, parent):
        seg = U.Segmented(parent, BT.KINDS, self.key, self.tabs.show)
        self.tabs.segs.append(seg)
        seg.badge("tms", getattr(self.tabs.app, "tm_new", 0) > 0)
        return seg

    def show(self, key):
        return self.tabs.show(key)

    def register(self, view):
        """view.badge("tms", on) 를 받는 것 (DP 도구 칸의 다이얼)."""
        self.tabs.segs.append(view)


class BagTabs(BT.BagTabs):
    CLASSES = {"items": BagWindow, "tms": TmWindow}

    def __init__(self, root, app, parent=None):
        BT.BagTabs.__init__(self, root, app, parent)
        self.win.configure(bg=BEZEL)

    def _switch_for(self, key):
        return Switch(self, key)
