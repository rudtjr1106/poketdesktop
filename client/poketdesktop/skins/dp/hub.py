# -*- coding: utf-8 -*-
"""DP 테마 - 허브 창 (v2).

창 크기는 기본 허브 그대로다 (ui_hub.W x H). 위에 탭 줄 하나: 묶음(ui_hub.GROUPS)마다 포켓몬 도구 그림 + 이름,
고른 탭은 빨간 글씨 · 빨간 줄 (DP 의 커서 빛깔), 새 소식은 빨간 점. 탭이 여럿 든 묶음은 그 아래에 얇은
글자 탭 줄(빨간 밑줄 - kit.tabs)을 하나 더 둔다. 아래가 그 탭의 화면이다.

아이콘은 직접 그리지 않는다 - 본가 4세대 도구 그림(poke_icons.py)을 쓴다.
허브가 앱에 내주는 것은 그대로다: panes · current · show(key) · set_badge(key, on) · focus() · close().
묶음 · 하위 탭을 오가는 일(_open)은 기본 허브의 것을 그대로 쓰고, 여기서는 칠하는 것만 한다.
"""
import tkinter as tk

from ... import ui_common as U
from ... import ui_hub
from . import CUR, HOV, INK2, LINE, PANEL, WIN_BG, font
from . import kit as K
from . import poke_icons

ICON = {"pokemon": "poke-ball", "bag": "loot-sack", "shop": "coin-case", "adventure": "town-map",
        "community": "pal-pad", "my": "member-card"}
BAR_H = 40          # 묶음 탭 줄 (하위 탭 줄이 생겨 몸 높이를 아끼려고 46 에서 줄였다 - 글씨는 그대로)
SUB_H = 28          # 하위 탭 줄
DOT = "#ff3b3b"


class HubWindow(ui_hub.HubWindow):

    def __init__(self, app):
        self._init_state(app)
        self.group_labels = dict((g, label) for g, label, _keys in ui_hub.GROUPS)
        self._hover = None
        self._boxes = {}
        self.gframes = {}        # 묶음 -> 틀
        self.subs = {}           # 묶음 -> 하위 탭 줄 캔버스 (탭이 여럿인 묶음만)
        self._sub_boxes = {}     # 묶음 -> [(탭 열쇠, 상자)]

        self.win = tk.Toplevel(self.root)
        U.style_window(self.win, "포스크탑", ui_hub.W, ui_hub.H)        # 기본 허브와 같은 크기
        U.apply_theme(self.win)
        self.win.configure(bg=WIN_BG, highlightthickness=0)
        self.win.minsize(980, 620)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        U.install_wheel(self.win)

        self.bar = tk.Canvas(self.win, height=U.h(BAR_H), bg=WIN_BG, highlightthickness=0, bd=0)
        self.bar.pack(side="top", fill="x")
        self.body = tk.Frame(self.win, bg=WIN_BG)
        self.body.pack(side="top", fill="both", expand=True)
        for g, _label, keys in ui_hub.GROUPS:
            gf = tk.Frame(self.body, bg=WIN_BG)
            self.gframes[g] = gf
            parent = gf
            if len(keys) > 1:
                parent = self._make_sub(g, gf)
            for key in keys:
                self.frames[key] = tk.Frame(parent, bg=WIN_BG)
        self.bar.bind("<Configure>", lambda _e: self._paint_bar())
        self.bar.bind("<Motion>", self._motion)
        self.bar.bind("<Leave>", self._leave)
        self.bar.bind("<Button-1>", self._click)
        # 기본 허브처럼 탭은 처음 볼 때 만든다 - 앱은 만들자마자 show(key) 를 부르므로 보통 여기는 안 탄다
        # (root 에 건다 - 이 창에 걸면 그사이 창을 닫았을 때 없어진 명령을 부른다.)
        self.root.after_idle(self._first)

    def _first(self):
        try:
            alive = bool(self.win.winfo_exists())
        except tk.TclError:
            alive = False
        if alive and self.current is None:
            self._open(self.order[0])

    # ---------------- 위 탭 줄 (묶음) ----------------
    def _paint_bar(self):
        cv = self.bar
        try:
            cv.delete("all")
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w < 50:
            return
        spec = font(11)
        f = K.tkfont_of(cv, spec)
        icons = dict((g, poke_icons.photo(ICON.get(g, "poke-ball"))) for g in self.groups)
        iw = dict((g, ph.width() if ph is not None else 0) for g, ph in icons.items())
        gap, pad = U.h(6), U.h(14)
        want = [iw[g] + gap + f.measure(self.group_labels[g]) + 2 * pad for g in self.groups]
        x0 = U.h(6)
        # 넘치면 여백만 줄인다 (글씨는 그대로)
        room = w - 2 * x0
        if sum(want) > room:
            cut = (sum(want) - room) / float(2 * len(want))
            pad = max(U.h(4), int(pad - cut))
            want = [iw[g] + gap + f.measure(self.group_labels[g]) + 2 * pad for g in self.groups]
        cv.create_line(0, h - 1, w, h - 1, fill=LINE)
        cur = ui_hub.GROUP_OF.get(self.current)
        x = x0
        self._boxes = {}
        for g, tw in zip(self.groups, want):
            on = g == cur
            y1, y2 = U.h(6), h
            if on:
                K.rrect(cv, x, y1, x + tw, y2 + 6, 6, fill=PANEL, outline=LINE, width=1)
                cv.create_rectangle(x + 1, h - 2, x + tw - 1, h + 1, fill=PANEL, outline="")   # 아래와 이어지게
                cv.create_rectangle(x + pad, y1 + 1, x + tw - pad, y1 + 4, fill=CUR, outline="")
            elif g == self._hover:
                K.rrect(cv, x + 2, y1 + 2, x + tw - 2, y2 - 3, 6, fill=HOV)
            cx = x + pad
            cy = (y1 + y2) // 2 + 1
            if icons[g] is not None:
                cv.create_image(cx + iw[g] // 2, cy, image=icons[g])
            cv.create_text(cx + iw[g] + gap, cy, text=self.group_labels[g], fill=CUR if on else INK2, font=spec,
                           anchor="w")
            if any(k in self.badges for k in ui_hub.GROUP_TABS[g]):
                d = U.h(4)
                bx, by = x + tw - pad // 2, y1 + U.h(11)      # 글자 오른쪽 여백 안 · 고른 탭의 빨간 줄 아래
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=DOT, outline=PANEL, width=2)
            self._boxes[g] = (x, x + tw)
            x += tw

    def _group_hit(self, x):
        for g, (x1, x2) in self._boxes.items():
            if x1 <= x < x2:
                return g
        return None

    def _motion(self, e):
        g = self._group_hit(e.x)
        if g != self._hover:
            self._hover = g
            self._paint_bar()
        self.bar.configure(cursor="hand2" if g else "")

    def _leave(self, _e):
        if self._hover is not None:
            self._hover = None
            self._paint_bar()

    def _click(self, e):
        g = self._group_hit(e.x)
        if g:
            self._open(self.last[g])

    # ---------------- 하위 탭 줄 ----------------
    def _make_sub(self, g, gf):
        """묶음 안의 글자 탭 줄 (흰 띠 - 고른 위 탭과 이어진다). 탭 화면이 들어갈 틀을 돌려준다."""
        cv = tk.Canvas(gf, height=U.h(SUB_H), bg=PANEL, highlightthickness=0, bd=0)
        cv.pack(side="top", fill="x")
        cv.bind("<Configure>", lambda _e, gg=g: self._paint_sub(gg))
        cv.bind("<Motion>", lambda e, gg=g: self._sub_motion(gg, e))
        cv.bind("<Leave>", lambda _e, gg=g: self._sub_left(gg))
        cv.bind("<Button-1>", lambda e, gg=g: self._sub_click(gg, e))
        self.subs[g] = cv
        body = tk.Frame(gf, bg=WIN_BG)
        body.pack(side="top", fill="both", expand=True)
        return body

    def _paint_sub(self, g):
        cv = self.subs.get(g)
        if cv is None:
            return
        try:
            cv.delete("all")
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w < 50:
            return
        cv.create_line(0, h - 1, w, h - 1, fill=LINE)
        items = [(k, self.labels[k]) for k in ui_hub.GROUP_TABS[g]]
        boxes = K.tabs(cv, U.h(14), 0, h - 1, items, self.last.get(g), "sub_", spec=font(11),
                       hover=self._sub_hover)
        self._sub_boxes[g] = boxes
        d = U.h(3)
        for key, (x1, y1, x2, _y2) in boxes:
            if key in self.badges:
                bx, by = x2 - U.h(3), y1 + U.h(8)              # 글자 오른쪽 여백 안 (칸 폭은 그대로)
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=DOT, outline=PANEL, width=1)

    def _sub_hit(self, g, x):
        for key, (x1, _y1, x2, _y2) in self._sub_boxes.get(g, ()):
            if x1 <= x < x2:
                return key
        return None

    def _sub_motion(self, g, e):
        k = self._sub_hit(g, e.x)
        if k != self._sub_hover:
            self._sub_hover = k
            self._paint_sub(g)
        self.subs[g].configure(cursor="hand2" if k else "")

    def _sub_left(self, g):
        if self._sub_hover is not None:
            self._sub_hover = None
            self._paint_sub(g)

    def _sub_click(self, g, e):
        k = self._sub_hit(g, e.x)
        if k:
            self._open(k)

    # ---------------- 탭 ----------------
    def _swap(self, key):
        g = ui_hub.GROUP_OF[key]
        for gg, f in self.gframes.items():
            if gg != g and f.winfo_manager():
                f.pack_forget()
        if not self.gframes[g].winfo_manager():
            self.gframes[g].pack(fill="both", expand=True)
        for k in ui_hub.GROUP_TABS[g]:
            f = self.frames[k]
            if k != key and f.winfo_manager():
                f.pack_forget()
        if not self.frames[key].winfo_manager():
            self.frames[key].pack(fill="both", expand=True)
        self._paint_bar()
        self._paint_sub(g)

    def _paint_dot(self, g):
        self._paint_bar()
        self._paint_sub(g)
