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
from . import skins
from . import ui_common as U
from . import ui_loading
from .ui_common import run_async

W, H = 900, 660
CELL_W, CELL_H = 84, U.h(92)
PAD = 6
COLS = 9                       # 창 너비에 맞춰 다시 계산한다

GENS = [(0, "전체"), (1, "1세대"), (2, "2세대"), (3, "3세대"), (4, "4세대"),
        (5, "5세대"), (6, "6세대"), (7, "7세대"), (8, "8세대"), (9, "9세대")]

MODES = [("all", "전부"), ("caught", "잡은 것"), ("miss", "아직")]

# 칸을 누르면 뜨는 도감 글 창 (게시판 #496, 11/10)
ENTRY_W = 440
ART = U.h(120)                  # 도트 칸 (정사각형 - 도트가 늦게 와도 창 크기가 안 바뀐다)


def flavor_text(sp, caught):
    """도감 글 창의 설명. 본가처럼 **잡아야** 보인다 (본 것만이면 분류 · 타입까지).

    글은 tools/add_flavor.py 가 넣은 본가 도감 글이다. 한국어 글은 898번(소드 · 실드)까지뿐이라 그 뒤는 없다고 적는다.
    """
    if not caught:
        return "잡으면 도감 설명을 볼 수 있다."
    return sp.get("flavor") or "아직 이 포켓몬의 도감 설명이 없다."


def keep_all(widget, s, spec, width):
    """**띄어쓰기에서** 줄을 바꾼 글 (keep-all). Tk 라벨은 한글을 아무 글자에서나 끊어서 '사냥한/다.' 가 된다.
    한 낱말이 폭보다 길면 그 낱말만 글자로 끊는다 (DP 테마의 kit.wrap 과 같다)."""
    import tkinter.font as tkfont
    f = tkfont.Font(root=widget, font=spec)
    out = []
    for para in str(s or "").split("\n"):
        line = ""
        for word in para.split(" "):
            cand = word if not line else line + " " + word
            if f.measure(cand) <= width:
                line = cand
                continue
            if line:
                out.append(line)
            while f.measure(word) > width and len(word) > 1:
                k = len(word)
                while k > 1 and f.measure(word[:k]) > width:
                    k -= 1
                out.append(word[:k])
                word = word[k:]
            line = word
        out.append(line)
    return "\n".join(out)


def entry_bits(sp):
    """'키 0.4m  ·  몸무게 6kg  ·  1세대'."""
    bits = []
    if sp.get("height"):
        bits.append("키 %gm" % sp["height"])
    if sp.get("kg"):
        bits.append("몸무게 %gkg" % sp["kg"])
    if sp.get("gen"):
        bits.append("%d세대" % int(sp["gen"]))
    return "  ·  ".join(bits)


def _norm(s):
    """비교용. 빈칸을 없애고 소문자로 (한글은 그대로다)."""
    return "".join((s or "").split()).lower()


def query_hit(sp, query):
    """이 종이 찾는 글에 걸리나: **이름(한글·영어)이나 도감 번호** (포켓몬 탭의 찾기와 같다).

    '피카', 'pika', '25', '0025' 가 다 피카츄를 찾는다. 숫자만 치면 번호로도 본다 - 번호는 앞에서부터
    맞아야 한다 ('25' 는 25 와 250번대를 찾고, 125·1025 는 안 찾는다). 0 으로 시작하면 **그 번호
    하나**다 - '025' 와 '0025' 는 25번만 찾는다 (칸에 적힌 모양대로 친 것이다).
    """
    q = _norm(query)
    if not q:
        return True
    if q in _norm(sp.get("kr")) or q in _norm(sp.get("en")):
        return True
    if q.isdigit():
        num = int(sp.get("num") or 0)
        return num == int(q) if q.startswith("0") else str(num).startswith(q)
    return False


@skins.skinnable
class DexWindow(object):

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        self.gen = 0
        self.mode = "all"
        self.q = ""
        self.seen = set()
        self.caught = set()
        self.gens = {}
        # 응답이 오기 전에 그릴 수도 있다(탭을 열자마자 세대 단추를 누르면).
        # reload() 의 콜백에서만 만들면 그때 AttributeError 로 터진다.
        self.total = 0
        self.rows = []             # 지금 보여줄 종 목록
        self.icons = {}            # num -> PhotoImage
        self.silhouettes = {}
        self.pending = set()       # 받는 중인 번호
        self.cols = COLS
        self.busy = False
        self._entry = None         # 열려 있는 도감 글 창 (하나만)

        # parent 가 있으면 탭 안의 한 칸으로, 없으면 지금까지처럼 창으로.
        self.win = U.panel(parent, self.root, "포스크탑 — 도감",
                           W, H, 560, 460, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            # 탭으로 들어갈 때는 허브가 이미 걸어 두었다.
            U.install_wheel(self.win)

        self.ach = None             # 처음 누를 때 만든다
        self.titles = None          # 칭호 목록 (1.8.1). 이것도 처음 누를 때
        self._ach_label = None
        self._build()
        self.reload()

    # 화면 테마(skins/)는 _build 와 칠하는 자리(draw · _redraw_cells · visible_nums · _show_panel)만 갈아 끼운다.
    def _build(self):
        self._header()
        # 격자와 업적 칸을 번갈아 보여주려고 격자 쪽을 한 틀에 담는다.
        self.dex_body = tk.Frame(self.win, bg=U.BG)
        self.dex_body.pack(fill="both", expand=True)
        self._filters()
        self._grid()

    # ---------------- 머리 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=U.h(62))
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)
        # **pady 를 주지 않는다.** 윈도우에서 이 글자는 34px 라 위아래 17 씩을 더하면
        # 68 로 머리줄(62)을 넘어 6px 눌렸다. 여백 없이도 세로 가운데에 놓인다.
        tk.Label(inner, text="도감", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(15))).pack(side="left")
        self.count = tk.Label(inner, text="", bg=U.BG2, fg=U.ACCENT,
                              font=U.FONT_B)
        self.count.pack(side="left", padx=(12, 0))
        self.sub = tk.Label(inner, text="", bg=U.BG2, fg=U.FG_FAINT,
                            font=U.FONT_XS)
        self.sub.pack(side="left", padx=(10, 0))
        U.ghost_button(inner, "새로고침", self.reload,
                       height=32).pack(side="right")
        # 도감 업적 (시즌 3). 누르면 격자 자리에 업적 칸이 들어간다.
        # **pady 를 주지 않는다** - 머리줄 62 에 단추(32+그림자 4)+30 이면
        # 윈도우(배율 1.0)에서 4px 눌린다(레이드 머리줄에서 겪었다).
        self.ach_btn = U.ghost_button(inner, "업적", self.toggle_achievements,
                                      height=32)
        self.ach_btn.pack(side="right", padx=(0, 8))
        # 칭호마다 얻는 조건을 적은 목록 (1.8.1). 업적과 같은 자리에 들어간다.
        self.title_btn = U.ghost_button(inner, "칭호", self.toggle_titles, height=32)
        self.title_btn.pack(side="right", padx=(0, 8))
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

    def _filters(self):
        bar = tk.Frame(self.dex_body, bg=U.BG)
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
        # **글자가 바뀔 때마다** 찾는다 (1.10.6). 예전에는 키를 뗄 때(<KeyRelease>)만 찾았는데, 한글은
        # 조합이 끝나야 칸에 들어가서 마지막 글자가 빠진 채로 찾았다 - 붙여넣은 글도 안 찾아졌다
        # (제보 #194: "포켓몬 탭처럼 검색이 되지 않는다"). 포켓몬 탭과 같은 방식이다.
        self.qv.trace_add("write", lambda *_a: self.set_query(self.qv.get()))
        e = U.entry(row2, self.qv, width=14)
        e.pack(side="left")

    # ---------------- 격자 ----------------
    def _grid(self):
        wrap = tk.Frame(self.dex_body, bg=U.BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        self.cv = tk.Canvas(wrap, bg=U.INK, highlightthickness=2,
                            highlightbackground=U.LINE, bd=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        self.cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.cv.bind("<Configure>", self._on_resize)
        U.scrollable(self.cv, 120,
                     lambda: self.root.after_idle(self.fetch_visible))
        self.cv.bind("<Motion>", self._on_hover)
        self.cv.bind("<Button-1>", self._on_click)      # 칸을 누르면 도감 글 (게시판 #496)

    def _on_wheel(self, e):
        self.cv.yview_scroll(U.wheel_units(e.delta, 120), "units")
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
            if err:
                wait.close()
                return self.app.notify(getattr(err, "message", str(err)))
            try:
                self.seen = set(r.get("seen") or [])
                self.caught = set(r.get("caught") or [])
                self.gens = r.get("gens") or {}
                self.total = r.get("total") or 0
                self.draw()
            finally:
                # **그린 뒤에 걷는다.** 맨 앞에서 걷으면 칸을 그리는 동안
                # 아무 표시 없는 창이 잠깐 보였다. 그려진 뒤(idle)에 걷고,
                # 그리다 터져도 걷는다 - 덮개가 남으면 새로고침 단추까지 가린다.
                try:
                    self.root.after_idle(wait.close)
                except tk.TclError:
                    wait.close()
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
            if self.q and not query_hit(sp, self.q):
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
    def _num_at(self, e):
        """마우스 아래 칸의 도감 번호. 칸 사이 틈이나 칸이 없는 자리면 None."""
        try:
            x, y = self.cv.canvasx(e.x) - PAD, self.cv.canvasy(e.y) - PAD
        except tk.TclError:
            return None
        cw, ch = CELL_W + PAD, CELL_H + PAD
        if x < 0 or y < 0 or x % cw > CELL_W or y % ch > CELL_H:
            return None
        c, r = int(x // cw), int(y // ch)
        i = r * self.cols + c
        if c >= self.cols or not 0 <= i < len(self.rows):
            return None
        return self.rows[i]["num"]

    def _on_hover(self, e):
        """본 적 있는 칸 위에서는 손 모양 - 누르면 도감 글이 열린다."""
        n = self._num_at(e)
        try:
            self.cv.configure(cursor="hand2" if n is not None and n in self.seen else "")
        except tk.TclError:
            pass

    def _on_click(self, e):
        n = self._num_at(e)
        if n is not None and n in self.seen:
            self.open_entry(n)

    # ---------------- 도감 글 창 (게시판 #496) ----------------
    def open_entry(self, n):
        """그 포켓몬의 도감 글 창. 본 적 있는 종만 열린다 (본 적 없으면 None). 한 번에 하나 - 다른 칸을 누르면 갈아 끼운다.

        도트 · 번호 · 이름 · 분류 · 타입 · 키 · 몸무게 · 세대, 그리고 본가 도감 글 (잡은 종만 - flavor_text).
        """
        dex = self.app.dex
        sp = dex.get(int(n)) if dex else None
        if sp is None or n not in self.seen:
            return None
        self._close_entry()
        from .ui_box import _shell, fit
        got = n in self.caught
        win, body = _shell(self.win, "도감 No.%04d" % n, ENTRY_W, U.h(300))
        self._entry = win
        win.bind("<Escape>", lambda _e: self._close_entry())
        win.bind("<Destroy>", lambda e: e.widget is win and self._entry_gone(win), add="+")
        U.ghost_button(body, "닫기", self._close_entry, height=32).pack(side="bottom", anchor="e", pady=(14, 0))
        top = tk.Frame(body, bg=U.BG)
        top.pack(fill="x")
        art = tk.Frame(top, bg=U.INK, width=ART, height=ART, highlightthickness=1, highlightbackground=U.LINE)
        art.pack(side="left", anchor="n")
        art.pack_propagate(False)
        win.entry_pic = tk.Label(art, bg=U.INK, bd=0, text="...", fg=U.FG_FAINT, font=U.FONT_S)
        win.entry_pic.place(relx=0.5, rely=0.5, anchor="center")
        info = tk.Frame(top, bg=U.BG)
        info.pack(side="left", fill="both", expand=True, padx=(14, 0))
        head = tk.Frame(info, bg=U.BG)
        head.pack(anchor="w", fill="x")
        tk.Label(head, text="No.%04d" % n, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left")
        tk.Label(head, text="잡았다" if got else "본 적 있다", bg=U.BG, fg=U.ACCENT if got else U.FG_DIM,
                 font=U.FONT_XS).pack(side="right")
        tk.Label(info, text=sp.get("kr") or sp["internal"], bg=U.BG, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(15)), anchor="w").pack(anchor="w")
        if sp.get("kind"):
            tk.Label(info, text=sp["kind"], bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(anchor="w")
        chips = tk.Frame(info, bg=U.BG)
        chips.pack(anchor="w", pady=(8, 0))
        for t in sp.get("types") or []:
            U.type_chip(chips, dex.type_name(t), t, small=False).pack(side="left", padx=(0, 6))
        bits = entry_bits(sp)
        if bits:
            tk.Label(info, text=bits, bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS, anchor="w").pack(anchor="w", pady=(8, 0))
        tk.Frame(body, bg=U.LINE, height=U.h(1)).pack(fill="x", pady=(14, 12))
        has = got and sp.get("flavor")
        # 접는 폭: 창 테두리 2x2 + 몸 여백 18x2 + 라벨 자신의 여백 (윈도우 글꼴이 조금 넓다). 띄어쓰기에서 미리 접고,
        # wraplength 는 그래도 넘칠 때의 울타리다.
        spec = U.FONT if has else U.FONT_S
        wrap_w = ENTRY_W - 4 - 36 - 8
        win.entry_text = tk.Label(body, text=keep_all(win, flavor_text(sp, got), spec, wrap_w), bg=U.BG,
                                  fg=U.FG if has else U.FG_FAINT, font=spec, justify="left", anchor="w",
                                  wraplength=wrap_w)
        win.entry_text.pack(fill="x")
        fit(win)
        self._entry_art(win, n)
        return win

    def _entry_art(self, win, n):
        """도트를 받아 칸에 맞게 키운다 (도트라 NEAREST, 정수 배는 아니어도 3배까지)."""
        api = self.app.api
        size = ART - U.h(12)

        def work():
            path = sprite_cache.ensure(api, n, False)
            if not path:
                return None
            im = Image.open(path)
            im.seek(0)
            im = im.convert("RGBA")
            bb = im.getbbox()
            if bb:
                im = im.crop(bb)
            k = min(3.0, size / float(max(im.size)))
            return im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.NEAREST)

        def done(img, err):
            if self._entry is not win or err or img is None:
                return
            try:
                win.entry_photo = ImageTk.PhotoImage(img)
                win.entry_pic.configure(image=win.entry_photo, text="")
            except tk.TclError:
                win.entry_photo = None
        run_async(self.root, work, done)

    def _entry_gone(self, win):
        # 그림은 여기(주 스레드)서 놓는다 - 작업 스레드의 GC 가 닫힌 창의 PhotoImage 를 치우면 멈춘다 (2.2.1)
        win.entry_photo = None
        if self._entry is win:
            self._entry = None

    def _close_entry(self):
        win, self._entry = self._entry, None
        if win is None:
            return
        try:
            win.destroy()
        except tk.TclError:
            pass

    # ---------------- 끝 ----------------
    # ---------------- 업적 ----------------
    def toggle_achievements(self):
        """격자 <-> 업적 칸."""
        from . import ui_achievements
        if self.ach is None:
            self.ach = ui_achievements.AchievementPanel(
                self.win, self.app, on_count=self._ach_count)
        self._show_panel(None if self.ach.f.winfo_manager() else "ach")

    def toggle_titles(self):
        """격자 <-> 칭호 목록 (칭호마다 얻는 조건)."""
        from . import ui_achievements
        if self.titles is None:
            self.titles = ui_achievements.TitlePanel(self.win, self.app)
        self._show_panel(None if self.titles.f.winfo_manager() else "titles")

    def _show_panel(self, which):
        """격자 자리에 무엇을 둘지: None(도감 격자) · "ach"(업적) · "titles"(칭호).

        셋 중 하나만 보인다. 보이는 칸의 단추는 '도감으로' 가 된다.
        """
        panes = {"ach": self.ach, "titles": self.titles}
        for p in panes.values():
            if p is not None and p.f.winfo_manager():
                p.pack_forget()
        if self.dex_body.winfo_manager():
            self.dex_body.pack_forget()
        self.ach_btn.configure(text="도감으로" if which == "ach"
                               else (self._ach_label or "업적"))
        self.title_btn.configure(text="도감으로" if which == "titles" else "칭호")
        if which is None:
            self.dex_body.pack(fill="both", expand=True)
            return
        panes[which].pack(fill="both", expand=True)
        panes[which].reload()

    def _ach_count(self, done, total):
        """업적 수는 단추 글씨에 둔다 - 머리줄의 작은 글씨는 세대·본 수 자리다."""
        self._ach_label = "업적 %d/%d" % (done, total)

    def focus(self):
        if U.is_embedded(self.win):
            return          # 탭이면 허브가 앞으로 꺼내 준다
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except Exception:                                   # noqa: BLE001
            pass

    def close(self):
        self._close_entry()
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        if getattr(self.app, "dex_window", None) is self:
            self.app.dex_window = None
