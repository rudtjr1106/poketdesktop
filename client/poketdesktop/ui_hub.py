# -*- coding: utf-8 -*-
"""창 하나로 다 보는 곳.

지금까지는 트레이 메뉴에서 창을 하나씩 띄웠다. 가방을 보다가 상점에
가려면 트레이로 돌아가서 다시 골라야 했고, 창이 여섯 개까지 겹쳤다.

여기서는 창 하나에 탭을 두고 그 안에서 오간다. 탭 내용은 지금까지 쓰던
창 클래스를 **그대로** 쓴다 - parent 를 주면 창 대신 Frame 을 만들도록
여섯 클래스를 고쳐 뒀다(U.panel). 그래서 화면도 동작도 달라지지 않는다.

**탭은 처음 눌렀을 때 만든다.** 여섯 개를 미리 만들면 창을 여는 순간
서버를 여섯 번 두드리고 도트도 그만큼 받는다. 대부분은 한두 탭만 본다.
"""
import tkinter as tk
from tkinter import ttk

from . import ui_common as U
from .ui_bag_tabs import BagTabs
from .ui_board import BoardWindow
from .ui_box import BoxWindow
from .ui_dex import DexWindow
from .ui_expedition import ExpeditionWindow
from .ui_friends import FriendsWindow
from .ui_guild import GuildWindow
from .ui_gym import GymWindow
from .ui_mypage import MyPageWindow
from .ui_rank import RankWindow
from .ui_shop import ShopWindow

W, H = 1040, 700

# (열쇠, 탭 이름, 클래스, root 를 인자로 받는가)
TABS = [
    ("box", "포켓몬", BoxWindow, True),
    # 가방 안에서 [도구 | 기술머신] 으로 나뉜다 (1.8.0 - 기술머신 탭을 합쳤다)
    ("bag", "가방", BagTabs, True),
    ("shop", "상점", ShopWindow, True),
    # 탐험 파견 (1.10.4): 박스의 포켓몬을 몇 시간 보내 두면 도구를 가져온다. 상점 오른쪽 (사용자 결정)
    ("expedition", "탐험", ExpeditionWindow, False),
    ("dex", "도감", DexWindow, False),
    ("friends", "친구", FriendsWindow, False),
    ("guild", "길드", GuildWindow, False),            # 1.10.0
    ("gym", "관장", GymWindow, True),
    # 레이드 탭은 1.10.0 에서 뺐다 (이벤트가 2026-10-06 에 끝났다). 다시 열 때는 여기에
    # ("raid", "레이드", RaidWindow, False) 를 되살리고, 트레이의 '레이드' 줄과
    # app.sync 의 announce_raid 도 같이 되살린다 - 화면(ui_raid*.py)은 그대로 있다.
    ("rank", "랭킹", RankWindow, False),
    ("board", "게시판", BoardWindow, False),
    # 설정은 마이페이지 머리줄의 톱니바퀴 안으로 들어갔다 (1.9.0)
    ("my", "마이페이지", MyPageWindow, False),
]


class HubWindow(object):

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.panes = {}          # 열쇠 -> 창 객체 (처음 눌렀을 때 생긴다)
        self.frames = {}         # 열쇠 -> 탭 프레임
        self.order = [t[0] for t in TABS]

        self.win = tk.Toplevel(self.root)
        U.style_window(self.win, "포스크탑", W, H)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        self.win.minsize(980, 620)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        # 휠은 창 하나가 받아서 포인터 밑의 목록으로 보낸다. 탭마다 따로
        # 걸면 서로 덮어쓰고, 탭을 닫을 때 남의 것까지 지운다.
        U.install_wheel(self.win)

        self.nb = ttk.Notebook(self.win)
        self.nb.pack(fill="both", expand=True, padx=2, pady=2)
        for key, label, _cls, _needs_root in TABS:
            f = tk.Frame(self.nb, bg=U.BG)
            self.frames[key] = f
            self.nb.add(f, text="  %s  " % label)
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab)

    # ---------------- 탭 ----------------
    def _key_at(self, idx):
        try:
            return self.order[idx]
        except IndexError:
            return None

    def _on_tab(self, _e=None):
        key = self._key_at(self.nb.index("current"))
        if key:
            self._build(key)
        # 길드 탭의 점은 '안 읽은 채팅이 남았고 지금 그 탭을 안 보고 있다' 는 뜻이다. 탭을
        # 옮겼으면 바로 다시 본다 (1.10.2) - 전에는 다음 동기화(최대 90초 뒤)에야 다시 찍혀서,
        # 아무 일도 없는데 한참 뒤에 점이 켜지는 것처럼 보였다. 새 탭이 화면에 붙은 뒤에 본다.
        # (root 에 건다 - 이 창에 걸면 그사이 창을 닫았을 때 없어진 명령을 부른다.)
        paint = getattr(self.app, "_paint_guild", None)
        if paint is not None:
            try:
                self.root.after(80, paint)
            except Exception:                               # noqa: BLE001
                pass

    def _build(self, key):
        """그 탭을 처음 눌렀으면 그때 만든다."""
        if key in self.panes:
            return self.panes[key]
        row = next((t for t in TABS if t[0] == key), None)
        if not row:
            return None
        _k, _label, cls, needs_root = row
        holder = self.frames[key]
        try:
            pane = cls(self.root, self.app, holder) if needs_root \
                else cls(self.app, holder)
        except Exception:                                   # noqa: BLE001
            # 탭 하나가 못 떠도 나머지는 살아 있어야 한다. 무슨 일인지는
            # 로그에 남긴다 - 조용히 빈 탭만 보이면 원인을 못 찾는다.
            import traceback
            from . import config
            config.log("탭 '%s' 를 못 만들었습니다:\n%s"
                       % (key, traceback.format_exc()))
            tk.Label(holder, text="이 화면을 여는 데 실패했습니다.",
                     bg=U.BG, fg=U.DANGER, font=U.FONT_B).pack(pady=40)
            self.panes[key] = None
            return None
        pane.win.pack(fill="both", expand=True)
        self.panes[key] = pane
        return pane

    def set_badge(self, key, on):
        """탭 이름 옆에 점을 찍는다 (새 공지·새 패치노트·새 댓글). 켜고 끄는 것만 한다."""
        row = next((t for t in TABS if t[0] == key), None)
        if not row or key not in self.order:
            return
        try:
            self.nb.tab(self.order.index(key),
                        text="  %s%s  " % (row[1], " ●" if on else ""))
        except tk.TclError:
            pass

    def show(self, key):
        """그 탭으로 옮기고 창을 앞으로 꺼낸다."""
        if key in self.order:
            self.nb.select(self.order.index(key))
            self._build(key)
        self.focus()

    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------- 끝 ----------------
    def close(self):
        # 탭마다 정리할 것이 있다(휠 바인딩 풀기, 예약 취소).
        # 하나가 실패해도 나머지는 정리해야 한다.
        for pane in list(self.panes.values()):
            if pane is None:
                continue
            try:
                pane.close()
            except Exception:                               # noqa: BLE001
                pass
        self.panes = {}
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        if getattr(self.app, "hub", None) is self:
            self.app.hub = None
