# -*- coding: utf-8 -*-
"""도감 창.

1025칸을 한 번에 그리면 안 된다. 창이 열리는 데 몇 초씩 걸리고, 도트를
1025장 받으면 그동안 아무것도 못 한다.

그래서 **캔버스 하나에 직접 그리고, 보이는 칸의 도트만 받는다.** 위젯을
1025개 만드는 대신 사각형과 글자를 그리면 tk 가 훨씬 가볍게 넘긴다.
스크롤하면 그때 화면에 들어온 칸의 도트를 받기 시작한다.

안 잡은 종은 실루엣으로 둔다. 본 적도 없으면 번호만 보인다 - 도감을
채우는 재미가 '무엇이 남았는지 보이는 것' 에서 오기 때문이다.
"""
import tkinter as tk

from PIL import Image, ImageTk

from . import sprite_cache
from . import ui_common as U
from . import ui_loading
from .ui_common import run_async

W, H = 900, 660
CELL_W, CELL_H = 84, 92
PAD = 6
COLS = 9                       # 창 너비에 맞춰 다시 계산한다

GENS = [(0, "전체"), (1, "1세대"), (2, "2세대"), (3, "3세대"), (4, "4세대"),
        (5, "5세대"), (6, "6세대"), (7, "7세대"), (8, "8세대"), (9, "9세대")]

MODES = [("all", "전부"), ("caught", "잡은 것"), ("miss", "아직")]


class DexWindow(object):

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.gen = 0
        self.mode = "all"
        self.q = ""
        self.seen = set()
        self.caught = set()
        self.gens = {}
        self.rows = []             # 지금 보여줄 종 목록
        self.icons = {}            # num -> PhotoImage
        self.silhouettes = {}
        self.pending = set()       # 받는 중인 번호
        self.cols = COLS
        self.busy = False

        self.win = tk.Toplevel(self.root)
        U.style_window(self.win, "포켓 데스크톱 — 도감", W, H)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        self.win.minsize(560, 460)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self._header()
        self._filters()
        self._grid()
        self.reload()

    # ---------------- 머리 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=62)
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)
        tk.Label(inner, text="도감", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, 15)).pack(side="left", pady=17)
        self.count = tk.Label(inner, text="", bg=U.BG2, fg=U.ACCENT,
                              font=U.FONT_B)
        self.count.pack(side="left", padx=(12, 0))
        self.sub = tk.Label(inner, text="", bg=U.BG2, fg=U.FG_FAINT,
                            font=U.FONT_XS)
        self.sub.pack(side="left", padx=(10, 0))
        U.ghost_button(inner, "새로고침", self.reload,
                       height=32).pack(side="right", pady=15)
        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x")

    def _filters(self):
        bar = tk.Frame(self.win, bg=U.BG)
        bar.pack(fill="x", padx=14, pady=(10, 6))

        self.gen_btns = {}
        row = tk.Frame(bar, bg=U.BG)
        row.pack(fill="x")
        for g, label in GENS:
            b = U.ghost_button(row, label, lambda x=g: self.set_gen(x),
                               height=26)
            b.pack(side="left", padx=(0, 3))
            self.gen_btns[g] = b

        row2 = tk.Frame(bar, bg=U.BG)
        row2.pack(fill="x", pady=(6, 0))
        self.mode_btns = {}
        for m, label in MODES:
            b = U.ghost_button(row2, label, lambda x=m: self.set_mode(x),
                               height=26)
            b.pack(side="left", padx=(0, 3))
            self.mode_btns[m] = b
        tk.Label(row2, text="  이름 찾기", bg=U.BG, fg=U.FG_DIM,
                 font=U.FONT_XS).pack(side="left", padx=(10, 4))
        self.qv = tk.StringVar()
        e = U.entry(row2, self.qv, width=14)
        e.pack(side="left")
        e.bind("<KeyRelease>", lambda _e: self.set_query(self.qv.get()))

    # ---------------- 격자 ----------------
    def _grid(self):
        wrap = tk.Frame(self.win, bg=U.BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        self.cv = tk.Canvas(wrap, bg=U.INK, highlightthickness=2,
                            highlightbackground=U.LINE, bd=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        self.cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.cv.bind("<Configure>", self._on_resize)
        self.cv.bind("<MouseWheel>", self._on_wheel)
        self.cv.bind("<Motion>", self._on_hover)

    def _on_wheel(self, e):
        self.cv.yview_scroll(int(-e.delta / 120), "units")
        # 스크롤한 뒤에 화면에 들어온 칸의 도트를 받기 시작한다
        self.root.after_idle(self.fetch_visible)

    def _on_resize(self, e):
        cols = max(1, (e.width - PAD) // (CELL_W + PAD))
        if cols != self.cols:
            self.cols = cols
            self.draw()
        else:
            self.root.after_idle(self.fetch_visible)

    # ---------------- 자료 ----------------
    def reload(self):
        if self.busy:
            return
        self.busy = True

        wait = ui_loading.Overlay(self.win, "도감을 불러오는 중")

        def done(r, err):
            self.busy = False
            wait.close()
            if err:
                return self.app.notify(getattr(err, "message", str(err)))
            self.seen = set(r.get("seen") or [])
            self.caught = set(r.get("caught") or [])
            self.gens = r.get("gens") or {}
            self.total = r.get("total") or 0
            self.draw()
        run_async(self.root, lambda: self.app.api.dexbook(), done)

    def set_gen(self, g):
        self.gen = g
        self.draw()

    def set_mode(self, m):
        self.mode = m
        self.draw()

    def set_query(self, q):
        self.q = (q or "").strip()
        self.draw()

    def _species(self):
        dex = self.app.dex
        if not dex:
            return []
        out = []
        for sp in dex.raw["species"]:
            if self.gen and sp.get("gen") != self.gen:
                continue
            n = sp["num"]
            if self.mode == "caught" and n not in self.caught:
                continue
            if self.mode == "miss" and n in self.caught:
                continue
            if self.q and self.q not in (sp.get("kr") or ""):
                continue
            out.append(sp)
        return out

    # ---------------- 그리기 ----------------
    def draw(self):
        self.cv.delete("all")
        self.rows = self._species()
        cw, ch = CELL_W + PAD, CELL_H + PAD
        for i, sp in enumerate(self.rows):
            x = PAD + (i % self.cols) * cw
            y = PAD + (i // self.cols) * ch
            self._cell(sp, x, y)
        rows = (len(self.rows) + self.cols - 1) // max(1, self.cols)
        self.cv.configure(scrollregion=(0, 0, 0, PAD + rows * ch))

        got = len(self.caught)
        self.count.configure(text="%d / %d" % (got, self.total or 0))
        if self.gen:
            g = self.gens.get(str(self.gen)) or {}
            self.sub.configure(text="%d세대  %d / %d  ·  보인 것 %d종"
                                    % (self.gen, g.get("caught", 0),
                                       g.get("total", 0), len(self.rows)))
        else:
            self.sub.configure(text="본 것 %d종  ·  보이는 것 %d종"
                                    % (len(self.seen), len(self.rows)))
        for g, b in self.gen_btns.items():
            b.set_active(g == self.gen) if hasattr(b, "set_active") else None
        self.root.after_idle(self.fetch_visible)

    def _cell(self, sp, x, y):
        n = sp["num"]
        got = n in self.caught
        seen = n in self.seen
        bg = "#1b2233" if got else ("#161b28" if seen else "#12151f")
        line = U.ACCENT if got else (U.LINE if seen else "#1a1e2b")
        self.cv.create_rectangle(x, y, x + CELL_W, y + CELL_H,
                                 fill=bg, outline=line,
                                 tags=("cell", "n%d" % n))
        self.cv.create_text(x + 6, y + 8, text="%04d" % n, anchor="nw",
                            fill=U.FG_FAINT if seen else "#3a4055",
                            font=U.FONT_XS, tags=("cell", "n%d" % n))
        name = sp.get("kr") or sp["internal"]
        self.cv.create_text(x + CELL_W / 2, y + CELL_H - 10,
                            text=name if seen else "??????",
                            fill=U.FG if got else (U.FG_DIM if seen else "#3a4055"),
                            font=U.FONT_XS, tags=("cell", "n%d" % n))
        img = self.icons.get(n) if seen else None
        if img is not None:
            self.cv.create_image(x + CELL_W / 2, y + CELL_H / 2 - 4,
                                 image=img, tags=("cell", "n%d" % n))

    # ---------------- 도트 ----------------
    def visible_nums(self):
        """지금 화면에 보이는 칸의 도감 번호."""
        try:
            top = self.cv.canvasy(0)
            bot = top + self.cv.winfo_height()
        except Exception:                                   # noqa: BLE001
            return []
        ch = CELL_H + PAD
        first = max(0, int((top - PAD) // ch) * self.cols)
        last = min(len(self.rows), (int((bot - PAD) // ch) + 2) * self.cols)
        return [self.rows[i]["num"] for i in range(first, last)]

    def fetch_visible(self):
        """보이는 칸 중 아직 도트가 없는 것만 받는다.

        1025장을 한꺼번에 받으면 창이 열리는 동안 아무것도 못 한다.
        스크롤을 따라가며 필요한 것만 받으면 처음 화면은 서른 장쯤으로 끝난다.
        """
        want = [n for n in self.visible_nums()
                if n in self.seen and n not in self.icons
                and n not in self.pending]
        if not want:
            return
        want = want[:24]
        for n in want:
            self.pending.add(n)

        def work():
            out = {}
            for n in want:
                try:
                    out[n] = sprite_cache.ensure(self.app.api, n, False)
                except Exception:                           # noqa: BLE001
                    out[n] = None
            return out

        def done(r, err):
            for n in want:
                self.pending.discard(n)
            if err or not r:
                return
            for n, path in r.items():
                if path:
                    img = self._icon(path)
                    if img is not None:
                        self.icons[n] = img
            self._redraw_cells(list(r))
        run_async(self.root, work, done)

    def _icon(self, path):
        try:
            im = Image.open(path)
            im.seek(0)
            im = im.convert("RGBA")
            im.thumbnail((CELL_W - 22, CELL_H - 34), Image.LANCZOS)
            return ImageTk.PhotoImage(im)
        except Exception:                                   # noqa: BLE001
            return None

    def _redraw_cells(self, nums):
        """도트가 도착한 칸만 다시 그린다. 전체를 다시 그리면 끊긴다."""
        by_num = dict((sp["num"], i) for i, sp in enumerate(self.rows))
        cw, ch = CELL_W + PAD, CELL_H + PAD
        for n in nums:
            i = by_num.get(n)
            if i is None:
                continue
            self.cv.delete("n%d" % n)
            self._cell(self.rows[i], PAD + (i % self.cols) * cw,
                       PAD + (i // self.cols) * ch)

    # ---------------- 마우스 ----------------
    def _on_hover(self, e):
        pass

    # ---------------- 끝 ----------------
    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except Exception:                                   # noqa: BLE001
            pass

    def close(self):
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        if getattr(self.app, "dex_window", None) is self:
            self.app.dex_window = None
