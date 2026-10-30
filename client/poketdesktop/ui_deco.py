# -*- coding: utf-8 -*-
"""꾸미기 창 (버전 2, common/deco). 바탕화면 포켓몬의 우클릭 '꾸미기...' 로 연다.

## 생김새

    ★ 피카츄 꾸미기
    장식 하나는 한 마리만 씁니다 ...
    ┌ 참가 묶음 선택권 1장 - 하나를 고르세요 ───────────┐   (선택권이 있을 때만)
    │ [리본 + 발자국] [꽃핀 + 꽃잎] [진주 목걸이 + 하트]  │
    └──────────────────────────────────────────────┘
    장식   [금관][리본] ...        - **가진 것만** (사용자 10/30: 꾸미기는 가방의 개별 아이템이다)
    효과   [금빛 별가루][발밑 빛] ...
    (고른 칸의 설명 · 누가 쓰고 있나)
    상태 글                                   [닫기]

칸을 누르면 **바로** 끼우고 뺀다 (색 고르기와 달리 '확인' 단추가 없다 - 다시 누르면 되돌아간다).
같은 칸(머리 · 발자취 ...)에 이미 끼운 것이 있으면 바꿔 낀다. 다른 포켓몬이 쓰던 것이면 그 포켓몬에서 빠진다
(서버 규칙, server/app/deco.py). 가방의 '꾸미기' 주머니(ui_bag.deco_items)에도 같은 것이 도구처럼 있다.

묶음 고르기는 되돌릴 수 없어서 한 번 묻는다.
"""
import tkinter as tk

from PIL import ImageTk

from common import deco as C
from common.korean import natural

from . import deco_art as ART
from . import skins
from . import ui_common as U

CELL = 64                   # 칸 크기 (px, U.h 로 늘린다)
GAP = 6
PAD = 18
ACC = ("crown_gold", "crown_silver", "crown_bronze", "bow", "flower", "pearls")
FX = ("fx_stars_gold", "fx_stars_silver", "fx_stars_bronze", "fx_paw", "fx_petals", "fx_hearts", "fx_glow")
EMPTY = ("아직 가진 꾸미기가 없습니다. 시즌 5 길드전 순위 보상 · 참가 보상으로 받습니다 "
         "(선물함으로 오고, 가방의 '꾸미기' 주머니에 들어갑니다).")
WHERE = {"rank1": "길드전 1위", "rank2": "길드전 2위", "rank3": "길드전 3위"}
NOTE = "장식 하나는 한 마리만 씁니다. 다른 포켓몬에 끼우면 먼저 쓰던 포켓몬에서 빠집니다. 다시 누르면 뺍니다."


def where(key):
    """그 장식을 얻는 곳 (길드전 순위 · 참가 묶음)."""
    got = [WHERE[b] for b in ("rank1", "rank2", "rank3") if key in C.BUNDLES[b]]
    if any(key in C.BUNDLES[b] for b in C.JOIN_CHOICES):
        got.append("길드전 참가 묶음")
    return " · ".join(got)


def _why(err, default):
    """실패한 까닭 (서버가 준 말이 먼저 - 색 고르기 창과 같다)."""
    if err is None:
        return default
    return getattr(err, "message", None) or str(err) or default


def icon_photo(key, box):
    """칸에 넣을 그림 (deco_art.item_icon - 가방의 꾸미기 줄과 같은 그림)."""
    return ART.item_icon(key, box)


@skins.skinnable
class DecoWindow(object):

    def __init__(self, app, mon, parent=None, on_done=None):
        self.app = app
        self.root = app.root
        self.mon = mon
        self.on_done = on_done
        self.alive = True
        self.busy = False
        self.state = None            # 서버가 준 꾸미기 목록 (deco.state)
        self.cells = {}              # 열쇠 -> (칸, 그림, 이름, 상태 글)
        self.photos = {}
        self.focus = None            # 설명을 보여 주는 칸
        info = mon.get("info") or {}
        self.name = info.get("name") or mon.get("nickname") or "포켓몬"
        box = U.h(CELL)

        self.win = tk.Toplevel(parent or self.root)
        self.win.withdraw()
        U.style_window(self.win, "포스크탑 — 꾸미기")
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.bind("<Escape>", lambda _e: self.close())

        U.dialog_bar(self.win, "꾸미기")
        width = self._build(box)
        self.width = width
        self._fit()
        self.win.deiconify()

        api = app.api
        U.run_async(self.root, api.deco_state, self._loaded)

    # ---------------- 짓는 고리 (화면 테마가 덮을 수 있다) ----------------
    def _build(self, box):
        """창 안을 짓는다. 만들어 둬야 할 것: head · note · pick_box · desc · status · cells. 창 폭을 돌려준다."""
        cw = box + 8
        n = max(len(ACC), len(FX))
        width = n * cw + (n - 1) * GAP + PAD * 2 + 8
        wrap = width - PAD * 2 - 8
        f = tk.Frame(self.win, bg=U.BG)
        f.pack(fill="both", expand=True, padx=PAD, pady=(14, 14))
        self.body = f
        self.head = tk.Label(f, text=natural("★ %s 꾸미기" % self.name), bg=U.BG, fg=U.ACCENT,
                             font=U.FONT_B, justify="left", anchor="w", wraplength=wrap)
        self.head.pack(fill="x")
        self.note = tk.Label(f, text=NOTE, bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, justify="left",
                             anchor="w", wraplength=wrap)
        self.note.pack(fill="x", pady=(4, 0))

        # 단추를 먼저 담는다 - 칸들이 자리를 다 먹고 단추를 밀어내지 않게.
        row = tk.Frame(f, bg=U.BG)
        row.pack(side="bottom", fill="x", pady=(12, 0))
        U.ghost_button(row, "닫기", self.close, height=34).pack(side="right")
        self.status = tk.Label(row, text="불러오는 중...", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S,
                               anchor="w", justify="left", wraplength=wrap - U.h(90))
        self.status.pack(side="left", fill="x", expand=True)

        # 참가 묶음 선택권 (있을 때만 채운다)
        self.pick_box = tk.Frame(f, bg=U.BG2, highlightthickness=1, highlightbackground=U.LINE2)
        self.pick_wrap = wrap

        # 칸은 목록을 받은 뒤 **가진 것만** 짓는다 (_fill_cells)
        self.grid = tk.Frame(f, bg=U.BG)
        self.grid.pack(fill="x", pady=(10, 0))
        self.tile = U.BG2
        self.box, self.cw = box, cw
        self._keys = None

        # 두 줄을 늘 잡아 둔다 (설명 + 얻는 곳) - 칸에 마우스를 올릴 때마다 창 높이가 출렁이지 않게
        self.desc = tk.Label(f, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, justify="left",
                             anchor="nw", wraplength=wrap, height=2)
        self.desc.pack(fill="x", pady=(10, 0))
        return width

    def _fill_cells(self, keys):
        """가진 꾸미기만 칸으로 (장식 줄 · 효과 줄). 없으면 안내 한 줄."""
        for w in self.grid.winfo_children():
            w.destroy()
        self.cells = {}
        box, cw, tile = self.box, self.cw, self.tile
        groups = [(title, [k for k in order if k in keys]) for title, order in (("장식", ACC), ("효과", FX))]
        if not any(g for _t, g in groups):
            tk.Label(self.grid, text=EMPTY, bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, justify="left", anchor="w",
                     wraplength=self.pick_wrap).pack(fill="x", pady=(12, 6))
            return
        for title, group in groups:
            if not group:
                continue
            tk.Label(self.grid, text=title, bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
                     anchor="w").pack(fill="x", pady=(8, 4))
            line = tk.Frame(self.grid, bg=U.BG)
            line.pack(fill="x")
            for i, key in enumerate(group):
                col = tk.Frame(line, bg=U.BG)
                col.pack(side="left", padx=(0, GAP if i < len(group) - 1 else 0), anchor="n")
                cell = tk.Frame(col, bg=tile, width=cw, height=cw, highlightthickness=2,
                                highlightbackground=tile, cursor="hand2")
                cell.pack()
                cell.pack_propagate(False)
                art = tk.Label(cell, bg=tile, bd=0, cursor="hand2")
                art.pack(expand=True)
                name = tk.Label(col, text=C.name(key), bg=U.BG, fg=U.FG, font=U.FONT_XS,
                                wraplength=cw, justify="center")
                name.pack(pady=(3, 0))
                tag = tk.Label(col, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS,
                               wraplength=cw, justify="center")
                tag.pack()
                for w in (cell, art, name):
                    w.bind("<Button-1>", lambda _e, k=key: self.press(k))
                    w.bind("<Enter>", lambda _e, k=key: self.show_desc(k))
                if key not in self.photos:
                    ph = icon_photo(key, box - 8)
                    if ph is not None:
                        self.photos[key] = ImageTk.PhotoImage(ph)
                if key in self.photos:
                    art.configure(image=self.photos[key])
                self.cells[key] = (cell, art, name, tag)

    def _paint_cell(self, key, owned, mine, other):
        """칸 하나 (owned = 가졌다, mine = 이 포켓몬이 쓰는 중, other = 다른 포켓몬이 쓰는 중)."""
        cell, art, name, tag = self.cells[key]
        if mine:
            line, text, fg = U.ACCENT, "쓰는 중", U.ACCENT
        elif other:
            line, text, fg = U.LINE2, "다른 포켓몬", U.FG_DIM
        elif owned:
            line, text, fg = self.tile, "", U.FG_FAINT
        else:
            line, text, fg = self.tile, "없음", U.FG_FAINT
        cell.configure(highlightbackground=line, cursor="hand2" if owned else "arrow")
        art.configure(cursor="hand2" if owned else "arrow")
        name.configure(fg=U.FG if owned else U.FG_FAINT)
        tag.configure(text=text, fg=fg)

    def _paint_picks(self, picks, choices):
        """참가 묶음 선택권 띠. picks 가 0 이면 감춘다."""
        for w in self.pick_box.winfo_children():
            w.destroy()
        if not picks:
            self.pick_box.pack_forget()
            return
        tk.Label(self.pick_box, text="참가 묶음 선택권 %d장 - 하나를 고르세요" % picks, bg=U.BG2, fg=U.FG,
                 font=U.FONT_B, anchor="w", wraplength=self.pick_wrap - 20).pack(fill="x", padx=10, pady=(8, 4))
        row = tk.Frame(self.pick_box, bg=U.BG2)
        row.pack(fill="x", padx=10, pady=(0, 10))
        for c in choices:
            U.PushButton(row, c["kr"], lambda b=c["key"]: self.pick(b), height=34,
                         font=U.FONT_S).pack(side="left", padx=(0, 8))
        self.pick_box.pack(fill="x", pady=(10, 0), before=self.grid)

    def _say(self, text, bad=False):
        self.status.configure(text=text, fg=U.DANGER if bad else U.FG_FAINT)

    def _set_desc(self, text):
        self.desc.configure(text=text)

    def _fit(self):
        """내용만큼만 (넘치면 창을 키우지 않는다 - 칸 수가 정해져 있어 넘칠 일이 없다).
        처음에만 가운데에 놓고, 그 뒤(목록을 받은 뒤 · 끼울 때마다)는 사용자가 옮긴 자리를 지킨다."""
        self.win.update_idletasks()
        h = self.win.winfo_reqheight() + 4
        if not getattr(self, "_placed", False):
            U.style_window(self.win, "포스크탑 — 꾸미기", self.width, h)
            self._placed = True
        else:
            U.place_window(self.win, self.width, h, keep_pos=True)

    # ---------------- 그리기 ----------------
    def _loaded(self, st, err):
        if not self.alive:
            return
        if err or not st:
            self._say(natural(_why(err, "꾸미기 목록을 받지 못했습니다.")), True)
            return
        self.state = st
        self._say("")
        self._paint()

    def worn(self):
        """이 포켓몬이 쓰는 것 {칸: 열쇠} (서버 목록 기준)."""
        st = self.state or {}
        return C.clean((st.get("worn") or {}).get(str(self.mon.get("id"))) or {})

    def _paint(self):
        st = self.state or {}
        items = dict((it["key"], it) for it in st.get("items") or [])
        pid = self.mon.get("id")
        try:
            keys = tuple(k for k in ACC + FX if (items.get(k) or {}).get("owned"))
            if keys != self._keys:
                self._keys = keys
                self._fill_cells(keys)
                if self.focus not in keys:
                    self.focus = None
            for key in self.cells:
                it = items.get(key) or {}
                by = it.get("wornBy")
                self._paint_cell(key, True, by == pid, by is not None and by != pid)
            self._paint_picks(int(st.get("picks") or 0), st.get("choices") or [])
            if self.focus:
                self.show_desc(self.focus)
            self._fit()
        except tk.TclError:
            return

    def show_desc(self, key):
        self.focus = key
        d = C.DECOS.get(key) or {}
        it = dict((i["key"], i) for i in (self.state or {}).get("items") or []).get(key) or {}
        text = "%s (%s) - %s" % (C.name(key), C.SLOT_KR.get(d.get("slot"), ""), d.get("desc", ""))
        by = it.get("wornBy")
        if by and by != self.mon.get("id"):
            text += "\n다른 포켓몬이 쓰고 있습니다 - 누르면 이 포켓몬에게 옮겨 옵니다."
        elif self.state is not None and not it.get("owned"):
            text += "\n얻는 곳: %s" % (where(key) or "-")
        try:
            self._set_desc(text)
        except tk.TclError:
            pass

    # ---------------- 끼우기 · 빼기 ----------------
    def press(self, key):
        if self.busy or self.state is None:
            return
        it = dict((i["key"], i) for i in self.state.get("items") or []).get(key) or {}
        self.show_desc(key)
        if not it.get("owned"):
            self._say("가지고 있지 않은 꾸미기입니다.", True)
            return
        on = it.get("wornBy") != self.mon.get("id")
        self.busy = True
        self._say("끼우는 중..." if on else "빼는 중...")
        pid = self.mon["id"]
        U.run_async(self.root, lambda: self.app.api.deco_equip(pid, key, on),
                    lambda r, err: self._equipped(key, on, r, err))

    def _equipped(self, key, on, r, err):
        self.busy = False
        if not self.alive:
            return
        if err or not r:
            self._say(natural(_why(err, "바꾸지 못했습니다.")), True)
            return
        self.state = r
        self.mon["deco"] = r.get("deco") or {}
        self._say(natural("%s 을(를) %s" % (C.name(key), "끼웠습니다." if on else "뺐습니다.")))
        self._paint()
        self._changed()

    def _changed(self):
        cb = self.on_done
        if cb:
            try:
                cb(self.mon)
            except Exception:                               # noqa: BLE001
                pass

    # ---------------- 참가 묶음 고르기 ----------------
    def pick(self, bundle):
        if self.busy:
            return
        from . import ui_box
        if not ui_box.confirm(self.win, "참가 묶음 고르기",
                              natural("%s 을(를) 고릅니다.\n고른 뒤에는 바꿀 수 없습니다." % C.name(bundle)),
                              danger=False, ok_text="고르기"):
            return
        self.busy = True
        self._say("고르는 중...")
        U.run_async(self.root, lambda: self.app.api.deco_pick(bundle),
                    lambda r, err: self._picked(bundle, r, err))

    def _picked(self, bundle, r, err):
        self.busy = False
        if not self.alive:
            return
        if err or not r:
            self._say(natural(_why(err, "고르지 못했습니다.")), True)
            return
        self.state = r
        self._say(natural("받았습니다: %s" % " · ".join(r.get("got") or [C.name(bundle)])))
        self._paint()

    def close(self):
        if not self.alive:
            return
        self.alive = False
        try:
            self.win.destroy()
        except tk.TclError:
            pass
