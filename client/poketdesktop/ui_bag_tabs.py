# -*- coding: utf-8 -*-
"""가방 탭 — 도구와 기술머신을 한 탭 안에서 오간다 (1.8.0).

예전에는 '가방' 과 '기술머신' 이 따로 탭이었다. 둘 다 '가진 것을 포켓몬에게
쓰는' 화면이라 가방 하나로 합치고, 머리줄의 [도구 | 기술머신] 으로 오간다.

  · 두 칸은 지금까지의 창 클래스(BagWindow, TmWindow)를 **그대로** 쓴다.
    머리줄에 고르는 단추만 끼워 넣는다 (switch).
  · 기술머신 칸은 처음 눌렀을 때 만든다. 가방만 보는 사람에게 358줄짜리
    목록을 미리 받게 할 이유가 없다.
  · 한 번 만든 칸은 숨겨만 둔다. 다시 오면 보던 그대로다.
"""
import tkinter as tk

from . import ui_common as U
from .ui_bag import BagWindow
from .ui_tms import TmWindow

KINDS = [("items", "도구"), ("tms", "기술머신")]
CLASSES = {"items": BagWindow, "tms": TmWindow}


class BagTabs(object):

    def __init__(self, root, app, parent=None):
        self.root = root
        self.app = app
        self.panes = {}           # 열쇠 -> BagWindow / TmWindow (처음 눌렀을 때 생긴다)
        self.holders = {}
        self.current = None
        self.win = U.panel(parent, root, "포스크탑 — 가방",
                           1000, 664, 950, 600, self.close)
        self.win.configure(bg=U.BG)
        if not U.is_embedded(self.win):
            U.install_wheel(self.win)
        for key, _label in KINDS:
            self.holders[key] = tk.Frame(self.win, bg=U.BG)
        self.show("items")

    # ---------------- 고르기 ----------------
    def _switch_for(self, key):
        """그 칸의 머리줄에 넣을 단추를 만들어 주는 함수."""
        def build(parent):
            return U.Segmented(parent, KINDS, key, self.show)
        return build

    def show(self, key):
        if key not in CLASSES or key == self.current:
            return self.panes.get(key)
        if key not in self.panes:
            pane = CLASSES[key](self.root, self.app, self.holders[key],
                                switch=self._switch_for(key))
            pane.win.pack(fill="both", expand=True)
            self.panes[key] = pane
        for k, holder in self.holders.items():
            if k != key and holder.winfo_manager():
                holder.pack_forget()
        self.holders[key].pack(fill="both", expand=True)
        self.current = key
        return self.panes[key]

    @property
    def bag(self):
        return self.panes.get("items")

    @property
    def tms(self):
        return self.panes.get("tms")

    # ---------------- 끝 ----------------
    def close(self):
        for pane in list(self.panes.values()):
            try:
                pane.close()
            except Exception:                               # noqa: BLE001
                pass
        self.panes = {}
        if getattr(self.app, "bag_window", None) is self:
            self.app.bag_window = None
        if getattr(self.app, "tm_window", None) is self:
            self.app.tm_window = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass
