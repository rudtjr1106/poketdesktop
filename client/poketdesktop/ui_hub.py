# -*- coding: utf-8 -*-
"""창 하나로 다 보는 곳.

지금까지는 트레이 메뉴에서 창을 하나씩 띄웠다. 가방을 보다가 상점에
가려면 트레이로 돌아가서 다시 골라야 했고, 창이 여섯 개까지 겹쳤다.

여기서는 창 하나에 탭을 두고 그 안에서 오간다. 탭 내용은 지금까지 쓰던
창 클래스를 **그대로** 쓴다 - parent 를 주면 창 대신 Frame 을 만들도록
여섯 클래스를 고쳐 뒀다(U.panel). 그래서 화면도 동작도 달라지지 않는다.

**탭은 처음 눌렀을 때 만든다.** 여섯 개를 미리 만들면 창을 여는 순간
서버를 여섯 번 두드리고 도트도 그만큼 받는다. 대부분은 한두 탭만 본다.

**탭은 묶음으로 나눈다 (2026-10-25).** 탭이 열한 개로 한 줄이라 너무 많았다 (사용자). 위 탭은
묶음 여섯 개(GROUPS), 탭이 여럿 든 묶음은 그 안에 얇은 하위 탭 줄을 둔다. 바깥에서 부르는 말은
그대로 탭 열쇠다 - show("guild") 는 '커뮤니티' 묶음의 '길드' 하위 탭으로 간다.
"""
import tkinter as tk
from tkinter import ttk

from . import skins
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

# 위 탭(묶음): (열쇠, 이름, [탭 열쇠 ...]). 기본 · 화면 테마 허브가 같이 쓴다. 탭이 하나뿐인 묶음은
# 하위 탭 줄이 없다. 가방과 상점은 따로 둔다 (사용자). 묶음을 누르면 그 묶음에서 마지막으로 본 탭이 뜬다.
GROUPS = [
    ("pokemon", "포켓몬", ["box", "dex"]),
    ("bag", "가방", ["bag"]),
    ("shop", "상점", ["shop"]),
    ("adventure", "모험", ["gym", "expedition", "rank"]),
    ("community", "커뮤니티", ["friends", "guild", "board"]),
    ("my", "마이페이지", ["my"]),
]
GROUP_OF = dict((k, g) for g, _label, keys in GROUPS for k in keys)     # 탭 열쇠 -> 묶음 열쇠
GROUP_TABS = dict((g, keys) for g, _label, keys in GROUPS)


def make(app):
    """허브 창을 만든다 - 화면 테마(skins/)가 허브를 따로 그리면 그것으로."""
    return skins.override(HubWindow)(app)


@skins.skinnable
class HubWindow(object):

    SUB_PAD = 12             # 하위 탭 글자 양옆 (px)

    def __init__(self, app):
        self._init_state(app)

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
        self.cells = {}          # 탭 열쇠 -> (칸, 글자, 밑줄) - 하위 탭 줄이 있는 묶음만
        for g, label, keys in GROUPS:
            gf = tk.Frame(self.nb, bg=U.BG)
            self.nb.add(gf, text="  %s  " % label)
            parent = gf
            if len(keys) > 1:
                parent = self._sub_bar(gf, keys)
            for key in keys:
                self.frames[key] = tk.Frame(parent, bg=U.BG)
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab)

    def _init_state(self, app):
        """기본 · 화면 테마 허브가 같이 쓰는 것."""
        self.app = app
        self.root = app.root
        self.panes = {}          # 탭 열쇠 -> 창 객체 (처음 눌렀을 때 생긴다)
        self.frames = {}         # 탭 열쇠 -> 탭 프레임
        self.order = [t[0] for t in TABS]
        self.labels = dict((t[0], t[1]) for t in TABS)
        self.groups = [g[0] for g in GROUPS]
        self.last = dict((g, keys[0]) for g, _label, keys in GROUPS)   # 묶음 -> 마지막으로 본 탭
        self.current = None      # 지금 보이는 탭 열쇠
        self.badges = set()      # 점이 켜진 탭 열쇠
        self._sub_hover = None

    # ---------------- 하위 탭 줄 ----------------
    def _sub_bar(self, gf, keys):
        """묶음 안의 하위 탭 줄: 글자 탭 + 고른 것은 금색 밑줄. 탭 화면이 들어갈 틀을 돌려준다.

        ttk.Notebook 을 하나 더 겹치지 않는다 - 두 겹 탭처럼 보여 무엇이 위 탭인지 헷갈린다.
        """
        bar = tk.Frame(gf, bg=U.BG)
        bar.pack(side="top", fill="x", padx=6, pady=(4, 0))     # 위 탭 줄(tabmargins 6)과 왼쪽을 맞춘다
        tk.Frame(gf, bg=U.LINE, height=1).pack(side="top", fill="x")
        for key in keys:
            cell = tk.Frame(bar, bg=U.BG, cursor="hand2")
            cell.pack(side="left")
            lab = tk.Label(cell, text=self.labels[key], font=U.FONT, bg=U.BG, fg=U.FG_DIM,
                           bd=0, padx=0, pady=U.h(5), cursor="hand2")
            lab.pack(side="top", padx=self.SUB_PAD)
            line = tk.Frame(cell, bg=U.BG, height=2)
            line.pack(side="top", fill="x")
            for w in (cell, lab, line):
                w.bind("<Button-1>", lambda _e, k=key: self._open(k))
                w.bind("<Enter>", lambda _e, k=key: self._sub_hovered(k))
                w.bind("<Leave>", lambda _e, k=key: self._sub_hovered(None, k))
            self.cells[key] = (cell, lab, line)
        body = tk.Frame(gf, bg=U.BG)
        body.pack(side="top", fill="both", expand=True)
        return body

    def _sub_hovered(self, key, left=None):
        if key is None and self._sub_hover != left:
            return                   # 옆 칸으로 옮기며 늦게 온 Leave
        self._sub_hover = key
        g = GROUP_OF.get(key or left)
        if g:
            self._paint_sub(g)

    def _paint_sub(self, g):
        """그 묶음의 하위 탭 줄을 칠한다: 고른 것 금색 + 밑줄, 올리면 밝게, 점은 글자색을 따른다."""
        sp = None
        for key in GROUP_TABS.get(g, ()):
            got = self.cells.get(key)
            if not got:
                continue
            _cell, lab, line = got
            on = key == self.last.get(g)
            color = U.ACCENT if on else (U.FG if key == self._sub_hover else U.FG_DIM)
            try:
                line.configure(bg=U.ACCENT if on else U.BG)
                if key in self.badges:
                    if sp is None:
                        sp = U.space_px(lab, U.FONT)
                    img = U.mark_image(lab, U.FONT, color, "dot", left=sp)
                    lab.configure(fg=color, image=img, compound="right")
                    # 점 폭만큼 오른쪽 여백을 줄여 칸 폭을 그대로 둔다 (점을 켜고 끌 때 줄이 안 흔들린다)
                    iw = int(lab.tk.call("image", "width", img))
                    lab.pack_configure(padx=(self.SUB_PAD, max(2, self.SUB_PAD - iw)))
                else:
                    lab.configure(fg=color, image="", compound="none")
                    lab.pack_configure(padx=self.SUB_PAD)
            except tk.TclError:
                pass

    # ---------------- 탭 ----------------
    def _group_at(self, idx):
        try:
            return self.groups[idx]
        except IndexError:
            return None

    def _on_tab(self, _e=None):
        """위 탭(묶음)을 눌렀다 - 그 묶음에서 마지막으로 본 탭을 연다."""
        g = self._group_at(self.nb.index("current"))
        key = self.last.get(g)
        if key and key != self.current:
            self._open(key)

    def _open(self, key):
        """그 탭(하위 탭)을 보인다. 처음이면 만들고, 이미 만든 것이면 _shown 을 부른다."""
        g = GROUP_OF.get(key)
        if g is None:
            return None
        self.last[g] = key
        if key != self.current:
            self.current = key
            self._swap(key)
        had = key in self.panes
        pane = self._build(key)
        if had:
            self._shown(pane)
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
        return pane

    def _swap(self, key):
        """그 탭이 든 묶음을 고르고, 묶음 안에서는 그 탭 틀만 붙인다 (나머지는 pack_forget - 진짜로 안 보인다)."""
        g = GROUP_OF[key]
        try:
            idx = self.groups.index(g)
            if self.nb.index("current") != idx:
                self.nb.select(idx)              # 탭이 바뀌었다는 알림은 뒤에 온다 - _on_tab 이 거른다
        except tk.TclError:
            pass
        for k in GROUP_TABS[g]:
            f = self.frames[k]
            if k != key and f.winfo_manager():
                f.pack_forget()
        if not self.frames[key].winfo_manager():
            self.frames[key].pack(fill="both", expand=True)
        self._paint_sub(g)

    def _build(self, key):
        """그 탭을 처음 눌렀으면 그때 만든다."""
        if key in self.panes:
            return self.panes[key]
        row = next((t for t in TABS if t[0] == key), None)
        if not row:
            return None
        _k, _label, cls, needs_root = row
        cls = skins.override(cls)            # 화면 테마가 이 탭을 따로 그리면 그것으로
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
        """탭에 점을 찍는다 (새 공지·새 패치노트·새 댓글). 켜고 끄는 것만 한다.

        하위 탭에 점, 그 묶음의 위 탭에도 점 (묶음 안에 하나라도 켜져 있으면).
        점은 글자(●)가 아니라 그림이다 (1.11.0, U.mark_image) - 글자 ● 는 탭 글자만큼 커서 컸다.
        색은 탭 글자를 따른다: 평소 흐린 회색, 고른 탭은 금색, 마우스를 올리면 밝게 (TNotebook.Tab 의 map).
        """
        g = GROUP_OF.get(key)
        if g is None:
            return
        if on:
            self.badges.add(key)
        else:
            self.badges.discard(key)
        self._paint_dot(g)

    def _paint_dot(self, g):
        """묶음 g 의 점을 다시 칠한다 (위 탭 · 하위 탭)."""
        self._paint_sub(g)
        label = next(t[1] for t in GROUPS if t[0] == g)
        try:
            if any(k in self.badges for k in GROUP_TABS[g]):
                self.nb.tab(self.groups.index(g), text="  %s" % label,
                            image=self._dot_spec(), compound="right")
            else:
                self.nb.tab(self.groups.index(g), text="  %s  " % label, image="")
        except tk.TclError:
            pass

    def _dot_spec(self):
        """탭의 점 그림 (상태마다 색이 다르다). 뒤에 점이 없을 때의 끝 빈칸 둘을 붙인다.

        앞에는 빈칸을 안 넣는다 - ttk 탭은 글자와 그림 사이를 스스로 4px(space) 띄운다 (빈칸 하나 폭).
        """
        sp = U.space_px(self.nb, U.FONT)

        def img(color):
            return U.mark_image(self.nb, U.FONT, color, "dot", right=2 * sp)
        return (img(U.FG_DIM), "selected", img(U.ACCENT), "active", img(U.FG))

    def show(self, key):
        """그 탭(묶음 + 하위 탭)으로 옮기고 창을 앞으로 꺼낸다. 이미 그 탭이면 _shown 만."""
        if key in GROUP_OF:
            self._open(key)
        self.focus()

    @staticmethod
    def _shown(pane):
        """이미 만든 탭을 다시 보여 준다. 그 탭이 원하면(on_shown) 오래된 것을 새로 불러온다."""
        fn = getattr(pane, "on_shown", None)
        if fn is not None:
            try:
                fn()
            except Exception:                               # noqa: BLE001
                pass

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
