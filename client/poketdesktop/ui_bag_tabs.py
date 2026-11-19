# -*- coding: utf-8 -*-
"""가방 탭 — 도구와 기술머신을 한 탭 안에서 오간다 (1.8.0).

예전에는 '가방' 과 '기술머신' 이 따로 탭이었다. 둘 다 '가진 것을 포켓몬에게
쓰는' 화면이라 가방 하나로 합치고, 머리줄의 [도구 | 기술머신] 으로 오간다.

  · 두 칸은 지금까지의 창 클래스(BagWindow, TmWindow)를 **그대로** 쓴다.
    머리줄에 고르는 단추만 끼워 넣는다 (switch).
  · 기술머신 칸은 처음 눌렀을 때 만든다. 가방만 보는 사람에게 358줄짜리
    목록을 미리 받게 할 이유가 없다.
  · 한 번 만든 칸은 숨겨만 둔다. 다시 오면 보던 그대로다.
    단 도구 칸은 그사이 가방 속이 바뀌었거나(stale - 볼을 던짐 · 잡음 · 상점 …) 읽은 지 오래면(STALE_SEC)
    다시 읽는다 (게시판 #711 - 볼이 0개인데 열어 둔 가방에는 볼이 남아 보였다). 기술머신 칸은 그대로다.
"""
import time
import tkinter as tk

from . import skins
from . import ui_common as U
from .ui_bag import BagWindow
from .ui_tms import TmWindow

KINDS = [("items", "도구"), ("tms", "기술머신")]
CLASSES = {"items": BagWindow, "tms": TmWindow}
STALE_SEC = 60            # 도구 칸을 다시 볼 때 이보다 오래 전에 읽었으면 다시 읽는다 (게시판 #711)


@skins.skinnable
class BagTabs(object):
    CLASSES = CLASSES             # 화면 테마가 칸 클래스를 바꿔 끼운다 (skins/<열쇠>/bag_tabs.py)

    def __init__(self, root, app, parent=None):
        self.root = root
        self.app = app
        self.panes = {}           # 열쇠 -> BagWindow / TmWindow (처음 눌렀을 때 생긴다)
        self.holders = {}
        self.segs = []            # 칸마다 머리줄에 있는 [도구 | 기술머신] (점을 같이 칠한다)
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
            seg = U.Segmented(parent, KINDS, key, self.show)
            self.segs.append(seg)
            seg.badge("tms", getattr(self.app, "tm_new", 0) > 0)
            return seg
        return build

    def badge_tms(self, on):
        """[기술머신] 옆의 점 (1.11.0): 받고 아직 안 본 기술머신이 있다. 칸마다 단추가 따로라 둘 다 칠한다."""
        for seg in self.segs:
            seg.badge("tms", on)

    def show(self, key):
        if key not in self.CLASSES or key == self.current:
            return self.panes.get(key)
        had = key in self.panes
        if not had:
            pane = self.CLASSES[key](self.root, self.app, self.holders[key],
                                switch=self._switch_for(key))
            pane.win.pack(fill="both", expand=True)
            self.panes[key] = pane
        for k, holder in self.holders.items():
            if k != key and holder.winfo_manager():
                holder.pack_forget()
        self.holders[key].pack(fill="both", expand=True)
        self.current = key
        if had:
            self.on_shown()                 # 기술머신 칸을 보다 도구로 돌아왔다 - 그사이 바뀌었으면 읽는다
        return self.panes[key]

    def on_shown(self):
        """허브에서 가방 탭을 다시 골랐다 (게시판 #711). 지금 도구 칸이면, 그사이 가방 속이 바뀌었거나(stale) 읽은 지
        오래면 다시 읽는다 - 조용히 (여는 중 표시 없이 보던 칸이 새 개수로 바뀐다).

        **도구 칸에만 건다.** 기술머신 칸은 358줄이라 돌아올 때마다 받을 일이 아니다 (새 기술머신은 app.note_tms 가
        읽힌다). 읽는 중이면 또 읽지 않는다 (app.bag_changed 의 예약과 겹칠 때).
        """
        pane = self.bag if self.current == "items" else None
        if pane is None or not getattr(pane, "alive", False) or getattr(pane, "_loading", False):
            return
        if getattr(pane, "stale", False) or time.time() - getattr(pane, "_loaded_at", 0.0) > STALE_SEC:
            pane.reload(quiet=True)

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
