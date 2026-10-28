# -*- coding: utf-8 -*-
"""'잡기 좋게 싸우기' 에서 멈출 포켓몬을 고르는 창 (설정 '고른 포켓몬만').

    ┌ 잡기 좋게 싸울 포켓몬 ─────────────┐
    │ 고른 포켓몬과 색이 다른 포켓몬만 …   │
    │ 찾기 [피카      ]      고른 3종      │
    │ ☐ 고른 것만 보기          [모두 풀기] │
    │ ☑ No.0025 피카츄                    │
    │ ☐ No.0026 라이츄                    │
    │ …                                   │
    └─────────────────────────────────────┘

**도트 없이 이름만** 보인다. 1025종의 도트를 받으면 창 하나 여는 데 한참 걸리고, 고르는 데는 이름이면
된다. 줄은 U.VirtualList 로 보이는 만큼만 만든다 (1025줄이어도 위젯은 화면만큼이다).

고를 때마다 바로 설정에 적는다 (설정 창의 다른 값과 같다 - '바꾸면 바로 적용됩니다'). 적는 것은 도감의
내부 이름이다 (config.catchPick). 폼(로토무 히트 …)은 목록에 따로 없다 - 원래 종을 고르면 그 폼도
멈춘다 (config.catch_for).

찾는 말은 StringVar 의 trace 로 듣는다. KeyRelease 로 들으면 한글 자판에서 조합 중인 글자를 놓친다
(도감 찾기에서 겪었다, 제보 #194). 찾는 규칙은 도감 창의 것을 그대로 쓴다 (ui_dex.query_hit -
한글·영어 이름, 도감 번호).
"""
import tkinter as tk

from . import config
from . import ui_common as U
from .ui_dex import query_hit

W, H = 380, 560


def rows_for(species, picked, query="", only=False, keep=()):
    """보여 줄 종 (도감 순서). picked 는 고른 내부 이름 집합, only 면 고른 것만.

    keep 은 '고른 것만 보기' 에서 방금 푼 줄 - 그대로 남겨 둔다 (바로 빼면 다음 줄이 밀려 올라와 손이 엉뚱한
    줄을 푼다).
    도감에 없는 이름을 골라 둔 것(옛 자료)은 목록에 안 보인다 - 그래도 설정에서 지우지는 않는다.
    """
    out = []
    for sp in species or ():
        if only and sp.get("internal") not in picked and sp.get("internal") not in keep:
            continue
        if query and not query_hit(sp, query):
            continue
        out.append(sp)
    return out


class Row(object):
    """목록의 한 줄 (체크 + 번호 + 이름). 같은 줄이 여러 종을 돌아가며 보여 준다 (U.VirtualList)."""

    def __init__(self, parent, win):
        self.win = win
        self.sp = None
        self.f = tk.Frame(parent, bg=U.LINE)                 # 아래 한 줄이 금으로 남는다
        self.var = tk.IntVar(value=0)
        self.chk = tk.Checkbutton(
            self.f, text="", variable=self.var, bg=U.BG, fg=U.FG,
            selectcolor=U.INK, activebackground=U.BG2, activeforeground=U.FG,
            font=U.FONT_S, anchor="w", highlightthickness=0, bd=0, padx=10,
            command=self._clicked)
        self.chk.place(x=0, y=0, relwidth=1.0, relheight=1.0, height=-1)

    def bind(self, sp):
        self.sp = sp
        self.var.set(1 if sp.get("internal") in self.win.picked else 0)
        # 고른 것만 보는 중에 방금 푼 줄은 흐리게 남는다 (win.dim)
        gone = sp.get("internal") in self.win.dim and sp.get("internal") not in self.win.picked
        self.chk.configure(fg=U.FG_FAINT if gone else U.FG, text="No.%04d  %s" % (int(sp.get("num") or 0),
                                                 sp.get("kr") or sp.get("en") or sp.get("internal") or "?"))

    def _clicked(self):
        if self.sp is not None:
            self.win.toggle(self.sp.get("internal"), bool(self.var.get()))


class CatchPickWindow(object):

    def __init__(self, app, on_change=None):
        self.app = app
        self.root = app.root
        self.on_change = on_change
        self.picked = set(config.catch_pick(app.settings))
        self.dim = set()                # '고른 것만 보기' 에서 방금 푼 줄 (찾기·보기를 바꾸면 비운다)
        self.species = self._read_species()
        self.win = U.panel(None, self.root, "잡기 좋게 싸울 포켓몬", W, H, None, None, self.close)
        self.win.configure(highlightthickness=2, highlightbackground=U.LINE2)
        U.dialog_bar(self.win, "잡기 좋게 싸울 포켓몬")
        body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True, padx=16, pady=(10, 12))

        self.note = tk.Label(body, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS,
                             anchor="w", justify="left", wraplength=W - 40)
        self.note.pack(fill="x")
        U.wrap_to_width(self.note)

        # 닫기 줄을 먼저 아래에 붙인다 - 목록이 남은 자리를 다 가져가도 잘리지 않게.
        end = tk.Frame(body, bg=U.BG)
        end.pack(side="bottom", fill="x", pady=(10, 0))
        U.ghost_button(end, "닫기", self.close, height=32).pack(side="right")

        bar = tk.Frame(body, bg=U.BG)
        bar.pack(fill="x", pady=(10, 6))
        tk.Label(bar, text="찾기", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS).pack(side="left")
        self.q = tk.StringVar()
        self.box = U.entry(bar, self.q, width=12)
        self.box.pack(side="left", padx=(8, 0))
        self.count = tk.Label(bar, text="", bg=U.BG, fg=U.ACCENT, font=U.FONT_S)
        self.count.pack(side="right")

        bar2 = tk.Frame(body, bg=U.BG)
        bar2.pack(fill="x", pady=(0, 6))
        self.only = tk.BooleanVar(value=False)
        tk.Checkbutton(bar2, text="고른 것만 보기", variable=self.only, bg=U.BG, fg=U.FG,
                       selectcolor=U.INK, activebackground=U.BG, activeforeground=U.FG,
                       font=U.FONT_S, anchor="w", highlightthickness=0, bd=0,
                       command=self.redraw).pack(side="left")
        U.ghost_button(bar2, "모두 풀기", self.clear, height=28).pack(side="right")

        tk.Frame(body, bg=U.LINE, height=1).pack(fill="x")
        self.vl = U.VirtualList(body, {"sp": (U.h(30), lambda p: Row(p, self))}, bg=U.BG)
        self.vl.pack(fill="both", expand=True)
        self.empty = tk.Label(self.vl.holder, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S,
                              justify="center")

        self.q.trace_add("write", lambda *_a: self.redraw(top=True))
        U.install_wheel(self.win)
        self.win.bind("<Escape>", lambda _e: self.close())
        self._paint_note()
        self.redraw(top=True)
        self.win.after(60, self._focus_box)

    def _read_species(self):
        dex = getattr(self.app, "dex", None)
        try:
            return list(dex.raw["species"]) if dex else []
        except (AttributeError, KeyError, TypeError):
            return []

    def _focus_box(self):
        try:
            self.box.entry.focus_set()
        except tk.TclError:
            pass

    # ---------------- 그리기 ----------------
    def _paint_note(self):
        text = ("고른 포켓몬과 색이 다른 포켓몬만 체력을 조금 남기고 멈춥니다. 나머지는 끝까지 싸웁니다. "
                "폼이 다른 포켓몬(로토무 히트 등)은 원래 포켓몬을 고르면 같이 멈춥니다.")
        color = U.FG_DIM
        if not self.species:
            text = "도감을 아직 못 받았습니다. 서버에 이어진 뒤 다시 열어 주세요."
            color = U.DANGER
        elif config.catch_mode(self.app.settings) != "pick":
            text += "\n지금은 '고른 포켓몬만' 이 아닙니다. 설정에서 그것을 골라야 적용됩니다."
            color = U.ACCENT
        self.note.configure(text=text, fg=color)

    def redraw(self, top=False, tidy=True):
        if tidy:
            self.dim.clear()            # 찾기·보기를 바꾸거나 모두 풀 때 흐린 줄을 정리한다
        rows = rows_for(self.species, self.picked, self.q.get(), bool(self.only.get()), self.dim)
        self.vl.set([("sp", sp) for sp in rows], keep=not top)
        n = len(self.picked)
        self.count.configure(text="고른 포켓몬 %d종" % n)
        if rows or not self.species:
            self.empty.place_forget()
        else:
            self.empty.configure(text="고른 포켓몬이 없습니다." if self.only.get() and not self.q.get().strip()
                                 else "찾는 포켓몬이 없습니다.")
            self.empty.place(relx=0.5, rely=0.3, anchor="center")

    # ---------------- 고르기 ----------------
    def toggle(self, internal, on):
        if not internal:
            return
        if on:
            self.picked.add(internal)
        else:
            self.picked.discard(internal)
        self._save()
        if self.only.get():
            # 풀어도 줄을 바로 빼지 않는다 - 다음 줄이 밀려 올라와 이어서 누르면 엉뚱한 줄이 풀린다.
            # 흐리게 남겨 두고, 찾기·보기를 바꿀 때 정리한다. 다시 체크하면 원래대로.
            if on:
                self.dim.discard(internal)
            else:
                self.dim.add(internal)
            self.vl.refresh()
        self.count.configure(text="고른 포켓몬 %d종" % len(self.picked))

    def clear(self):
        if not self.picked:
            return
        self.picked = set()
        self._save()
        self.redraw()

    def _save(self):
        # **늘 새 리스트로 갈아 끼운다** - 제자리에서 고치면 기본값(config.DEFAULTS)의 리스트까지 바뀐다.
        order = dict((sp.get("internal"), int(sp.get("num") or 0)) for sp in self.species)
        self.app.settings["catchPick"] = sorted(self.picked, key=lambda k: (order.get(k, 99999), k))
        config.save_settings(self.app.settings)
        # 설정 창은 **부를 때마다 지금 것을 찾는다** - 닫았다 다시 연 설정 창은 다른 객체라, 열 때 달아 둔
        # 것을 부르면 죽은 창을 가리킨다.
        st = getattr(self.app, "settings_win", None)
        paint = getattr(st, "_paint_catch_pick", None)
        if paint is not None:
            paint()
        if self.on_change:
            try:
                self.on_change()
            except tk.TclError:
                pass

    def repaint(self):
        """설정에서 모드를 바꾸거나 기본값으로 돌렸다 - 안내 글과 고른 수를 다시 칠한다."""
        self.picked = set(config.catch_pick(self.app.settings))
        self._paint_note()
        self.count.configure(text="고른 포켓몬 %d종" % len(self.picked))
        self.vl.refresh()

    # ---------------- 끝 ----------------
    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass
        if not self.species:
            # 도감이 오기 전에 열었다 - 지금 있으면 종 목록을 다시 읽는다
            self.species = self._read_species()
            if self.species:
                self.redraw(top=True)
        self._paint_note()

    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def close(self):
        if getattr(self.app, "catch_pick_window", None) is self:
            self.app.catch_pick_window = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass


def open_window(app, on_change=None):
    """하나만 띄운다. 이미 떠 있으면 앞으로 가져온다. (설정 창에는 on_change 를 안 써도 알려 준다 -
    _save 가 지금 설정 창을 찾는다.)"""
    w = getattr(app, "catch_pick_window", None)
    if w is not None and w.alive():
        if on_change is not None:
            w.on_change = on_change
        w.focus()
        return w
    app.catch_pick_window = CatchPickWindow(app, on_change)
    return app.catch_pick_window
