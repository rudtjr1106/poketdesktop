# -*- coding: utf-8 -*-
"""프렌들리샵 — 도구를 사고파는 창.

돈이 오가는 곳이라 값은 하나도 여기서 정하지 않는다. 가격·잔고·가방은
서버가 준 것을 그대로 비추고, 사고팔 때 보내는 것도 '무엇을 몇 개' 뿐이다.
돈이 모자라거나 가진 게 없으면 서버가 400 으로 막아 주므로, 이 창이 할 일은
그 이유를 바닥 상태줄에 옮겨 적는 것뿐이다.

생김새는 ui_box 의 포켓몬 목록과 같은 꼴로 맞췄다.

    왼쪽    분류 (전체 / 몬스터볼 / 진화의돌 / 노력치 / 개체값 / 회복 / 기타)
    가운데  도구 목록 — 한 줄에 이름 · 등급 · 사는값 · 파는값 · 보유
    오른쪽  고른 도구의 설명, 개수 조절, [사기] [팔기]

effect 사전({"kind": "ev", "stat": "atk", "amount": 10})을 그대로 보여주면
아무도 못 읽는다. effect_text() 가 "공격 노력치가 10 오른다" 같은 한 줄로
바꾼다. 서버가 도구를 늘려도 여기 문장만 더하면 되도록 표로 만들어 뒀다.

등급은 색으로 읽는다. 줄 왼쪽 3px 막대와 등급 글자가 같은 색이라
목록을 훑기만 해도 귀한 물건이 눈에 걸린다 (회색 → 금색).
"""
import tkinter as tk
from tkinter import ttk

from common.korean import natural

from . import ui_common as U

ROW_H = 30
CATS_W = 136
DETAIL_W = 348
WRAP = DETAIL_W - 62          # 설명 액자 안에서 줄을 접는 폭
MAX_QTY = 999                 # 서버 item_routes.MAX_QTY 와 같은 값

PANEL = "#101623"             # 액자 안 (ui_box 상세와 같은 색)

# (분류 키, 보여줄 이름)
CATS = [("all", "전체"), ("ball", "몬스터볼"), ("stone", "진화의돌"),
        ("ev", "노력치"), ("iv", "개체값"), ("heal", "회복"), ("misc", "기타")]

# (제목, x, 너비, 정렬)
COLS = [("도구", 14, 194, "w"), ("등급", 214, 64, "center"),
        ("사는 값", 284, 84, "e"), ("파는 값", 374, 72, "e"),
        ("보유", 452, 56, "center")]

RARITY_KR = {"common": "흔함", "uncommon": "조금귀함", "rare": "귀함",
             "epic": "진귀", "legendary": "전설"}
RARITY_COLOR = {"common": "#7b8399", "uncommon": U.GOOD, "rare": U.INFO,
                "epic": "#c08bff", "legendary": U.ACCENT}

STAT_KR = {"hp": "HP", "atk": "공격", "def": "방어",
           "spa": "특수공격", "spd": "특수방어", "spe": "스피드"}

# 볼의 조건. %s 자리에는 배율이 들어간다.
BALL_COND = {
    "water_or_bug": "물·벌레 타입에게 던지면 포획률 %s배",
    "low_level": "상대 레벨이 낮을수록 잘 잡힌다 (최대 %s배)",
    "many_turns": "턴이 길어질수록 잘 잡힌다 (최대 %s배)",
    "first_turn": "첫 턴에 던지면 포획률 %s배",
    "night": "밤(20시~새벽 4시)에 던지면 포획률 %s배",
    "level_gap": "내 포켓몬이 더 높은 레벨이면 최대 %s배",
    "moon_family": "달의돌로 진화하는 종에게 포획률 %s배",
    "fast_species": "스피드 종족값이 100 이상인 종에게 포획률 %s배",
    "heavy": "상대가 무거울수록 잘 잡힌다",
    "same_species_other_gender": "같은 종의 다른 성별에게 포획률 %s배",
    "asleep": "잠든 상대에게 포획률 %s배",
    "already_caught": "이미 잡아 본 종에게 포획률 %s배",
}


# ---------------------------------------------------------------- 글로 바꾸기
def won(n):
    """12345 -> '12,345'. 돈은 세 자리마다 끊어야 눈에 들어온다."""
    try:
        return "{:,}".format(int(n))
    except (TypeError, ValueError):
        return str(n)


def _num(v):
    """4.0 -> '4', 3.5 -> '3.5'. 배율에 붙는 소수점 0 이 지저분해서 지운다."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f == int(f) else ("%.1f" % f)


def effect_text(it):
    """effect 사전을 사람이 읽는 한 줄로 바꾼다."""
    eff = (it or {}).get("effect") or {}
    kind = eff.get("kind")

    if kind == "ball":
        mult = _num(eff.get("mult", 1.0))
        cond = eff.get("cond")
        if cond:
            fmt = BALL_COND.get(cond)
            if not fmt:
                return "특별한 조건에서 더 잘 잡힌다"
            return (fmt % mult) if "%s" in fmt else fmt
        if float(eff.get("mult", 1.0) or 1.0) > 1.0:
            return "포획률 %s배" % mult
        return "포획률은 몬스터볼과 같다"

    if kind == "ev":
        stat = STAT_KR.get(eff.get("stat"), eff.get("stat", ""))
        amount = int(eff.get("amount", 0) or 0)
        if amount < 0:
            return "%s 노력치가 %d 내려간다" % (stat, -amount)
        return "%s 노력치가 %d 오른다" % (stat, amount)

    if kind == "iv":
        count = int(eff.get("count", 1) or 1)
        if count >= 6:
            return "개체값 6개를 전부 31로 만든다"
        return "고른 능력 하나의 개체값을 31로 만든다"

    if kind == "level":
        return "레벨이 %d 오른다" % int(eff.get("amount", 1) or 1)

    if kind == "stone":
        names = (it or {}).get("evolves") or []
        if not names:
            return "아직 이 돌로 진화하는 포켓몬이 없다"
        return natural("%s 이(가) 진화한다" % ", ".join(names))

    if kind == "noevolve":
        return "이 표시를 켠 포켓몬은 진화하지 않는다 (다시 쓰면 풀린다)"

    if kind == "sell":
        return "팔아서 돈으로 바꾸는 물건"

    return "아직 쓸 수 없는 물건"


def effect_note(it):
    """설명 아래에 작게 붙는 덧말. 없으면 빈 글자."""
    eff = (it or {}).get("effect") or {}
    kind = eff.get("kind")
    note = eff.get("note") or ""
    if kind == "iv":
        note = note or "레벨이 어느 정도 오른 포켓몬만 단련할 수 있다"
    elif kind == "ev":
        note = note or "능력 하나에 252, 전부 합쳐 510 까지"
    elif kind == "stone" and not (it or {}).get("evolves"):
        note = note or ""
    return note


def _err(e):
    return natural(getattr(e, "message", None) or str(e))


# ---------------------------------------------------------------- 목록 한 줄
class Row(object):
    """도구 목록 한 줄.

    ui_box.Row 와 같은 방식이다. place 로 칸을 잡고, 마우스가 올라오거나
    골라지면 바탕색을 칠한다. 왼쪽 3px 막대는 등급 색이다.
    """

    def __init__(self, parent, it, have, on_pick):
        self.it = it
        self.iid = it["id"]
        self.on_pick = on_pick
        self.selected = False
        self.base = U.BG
        self.rare = RARITY_COLOR.get(it.get("rarity"), U.FG_FAINT)

        self.f = tk.Frame(parent, bg=self.base, height=ROW_H, cursor="hand2")
        self.f.pack_propagate(False)
        self.mark = tk.Frame(self.f, bg=self.rare, width=3)
        self.mark.place(x=0, y=0, relheight=1.0)

        self.cells = []
        self.name_cell = self._cell(it.get("kr", self.iid), COLS[0], U.FG, U.FONT_S)
        self._cell(RARITY_KR.get(it.get("rarity"), "-"), COLS[1],
                   self.rare, U.FONT_XS)

        buyable = bool(it.get("buyable")) and int(it.get("cost") or 0) > 0
        self._cell(won(it.get("cost")) if buyable else "안 판다", COLS[2],
                   U.FG_DIM if buyable else U.FG_FAINT, U.FONT_XS)
        sell = int(it.get("sell") or 0)
        self._cell(won(sell) if sell else "—", COLS[3],
                   U.FG_DIM if sell else U.FG_FAINT, U.FONT_XS)
        self.have_cell = self._cell("", COLS[4], U.ACCENT, U.FONT_XS)
        self.set_have(have)

        for w in [self.f] + self.cells:
            w.bind("<Button-1>", lambda e: self.on_pick(self.iid))
            w.bind("<Enter>", self._hover_in)
            w.bind("<Leave>", self._hover_out)

    def _cell(self, text, col, fg, font):
        _title, x, w, anchor = col
        lb = tk.Label(self.f, text=text, bg=self.base, fg=fg, font=font,
                      anchor=anchor)
        lb.place(x=x, y=0, width=w, relheight=1.0)
        self.cells.append(lb)
        return lb

    def pack(self, **kw):
        self.f.pack(fill="x", **kw)
        return self

    def set_have(self, n):
        n = int(n or 0)
        self.have = n
        self.have_cell.configure(text=("%d개" % n) if n else "—",
                                 fg=U.ACCENT if n else U.FG_FAINT)

    def _paint(self, bg, mark):
        self.f.configure(bg=bg)
        self.mark.configure(bg=mark)
        for w in self.cells:
            try:
                w.configure(bg=bg)
            except tk.TclError:
                pass

    def _hover_in(self, _e):
        if not self.selected:
            self._paint(U.BG2, self.rare)

    def _hover_out(self, _e):
        if not self.selected:
            self._paint(self.base, self.rare)

    def set_selected(self, on):
        self.selected = on
        if on:
            self._paint("#2b2417", U.ACCENT)
            self.name_cell.configure(fg=U.ACCENT_TEXT, font=U.FONT_B)
        else:
            self._paint(self.base, self.rare)
            self.name_cell.configure(fg=U.FG, font=U.FONT_S)


# ---------------------------------------------------------------- 창
class ShopWindow(object):
    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.items = []
        self.bag = {}
        self.money = 0
        self.sell_rate = 0.5
        self.rows = {}
        self.cat_btns = {}
        self.sel = None
        self.cat = "all"
        self.qty = 1
        self.busy = False

        self.win = tk.Toplevel(root)
        U.style_window(self.win, "포켓 데스크톱 — 프렌들리샵", 1020, 664)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        self.win.minsize(980, 600)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self._header()
        self._bottom()

        body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True)
        self._cats(body)
        self._detail(body)      # 오른쪽을 먼저 잡아야 가운데가 남은 폭을 다 먹는다
        self._list(body)

        # 휠은 창에 건다. bind_all 로 걸면 포켓몬 관리 창의 휠까지 빼앗는다.
        self.win.bind("<MouseWheel>", self._wheel)
        self.reload()

    # ---------------- 머리 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=68)
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)

        cv = tk.Canvas(inner, width=28, height=28, bg=U.BG2,
                       highlightthickness=0, bd=0)
        cv.pack(side="left", pady=20)
        cv.create_oval(2, 2, 26, 26, fill="#f4f6fb", outline=U.INK, width=3)
        cv.create_arc(2, 2, 26, 26, start=0, extent=180, fill=U.RED,
                      outline=U.INK, width=3)
        cv.create_rectangle(2, 12, 26, 16, fill=U.INK, outline="")
        cv.create_oval(10, 10, 18, 18, fill="#f4f6fb", outline=U.INK, width=2)

        title = tk.Frame(inner, bg=U.BG2)
        title.pack(side="left", padx=(12, 0))
        tk.Label(title, text="프렌들리샵", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, 15)).pack(anchor="w")
        self.sub = tk.Label(title, text="", bg=U.BG2, fg=U.FG_FAINT,
                            font=U.FONT_XS)
        self.sub.pack(anchor="w")

        U.ghost_button(inner, "새로고침", self.reload,
                       height=32).pack(side="right", pady=18)

        # 소지금은 이 창에서 가장 큰 글씨다. 사고팔 때마다 바로 갈아 끼운다.
        wallet = U.framed(inner, bg=U.INK, border=U.LINE)
        wallet.pack(side="right", padx=(0, 12), pady=15)
        tk.Label(wallet, text="소지금", bg=U.INK, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="left", padx=(13, 9), pady=6)
        self.money_lb = tk.Label(wallet, text="0", bg=U.INK, fg=U.ACCENT,
                                 font=(U.FAMILY_BLACK, 17))
        self.money_lb.pack(side="left")
        tk.Label(wallet, text="원", bg=U.INK, fg=U.ACCENT_TEXT,
                 font=U.FONT_S).pack(side="left", padx=(4, 14), pady=(0, 2))

        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x")

    # ---------------- 바닥 ----------------
    def _bottom(self):
        U.dot_footer(self.win, 1020,
                     "가격은 정식 도감 기준 · 도구는 포켓몬 관리 창에서 쓴다"
                     ).pack(fill="x", side="bottom")
        self.status = U.status_line(self.win, "", U.FG_FAINT)
        self.status.pack(fill="x", side="bottom")
        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x", side="bottom")

    def say(self, msg, color=U.GOOD):
        U.set_status(self.status, natural(msg or ""), color)

    # ---------------- 분류 ----------------
    def _cats(self, parent):
        p = tk.Frame(parent, bg=U.BG2, width=CATS_W)
        p.pack(side="left", fill="y")
        p.pack_propagate(False)
        tk.Frame(p, bg=U.LINE2, width=2).place(relx=1.0, x=-2, y=0, relheight=1.0)

        U.marker_label(p, "분류", bg=U.BG2).pack(anchor="w", padx=14, pady=(15, 9))
        for key, label in CATS:
            b = tk.Label(p, text=label, bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S,
                         anchor="w", padx=11, pady=7, cursor="hand2")
            b.pack(fill="x", padx=(10, 12), pady=1)
            b.bind("<Button-1>", lambda e, k=key: self.set_cat(k))
            b.bind("<Enter>", lambda e, k=key: self._cat_hover(k, True))
            b.bind("<Leave>", lambda e, k=key: self._cat_hover(k, False))
            self.cat_btns[key] = b
        self._paint_cats()

    def _cat_hover(self, key, on):
        if key == self.cat:
            return
        self.cat_btns[key].configure(bg=U.BG3 if on else U.BG2,
                                     fg=U.FG if on else U.FG_DIM)

    def _paint_cats(self):
        for key, w in self.cat_btns.items():
            on = (key == self.cat)
            w.configure(bg=U.ACCENT_SOFT if on else U.BG2,
                        fg=U.ACCENT_TEXT if on else U.FG_DIM,
                        font=U.FONT_B if on else U.FONT_S)

    def _paint_cat_counts(self):
        """분류마다 몇 개인지 이름 뒤에 적는다."""
        for key, label in CATS:
            n = len(self.items) if key == "all" else \
                len([i for i in self.items if i.get("cat") == key])
            self.cat_btns[key].configure(text="%s  %d" % (label, n))

    def set_cat(self, key):
        self.cat = key
        self._paint_cats()
        self.render()

    # ---------------- 목록 ----------------
    def _list(self, parent):
        wrap = tk.Frame(parent, bg=U.BG)
        wrap.pack(side="left", fill="both", expand=True)

        bar = tk.Frame(wrap, bg=U.BG2, height=46)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        U.marker_label(bar, "이름으로 찾기", bg=U.BG2).pack(side="left",
                                                       padx=(14, 9))
        self.q = tk.StringVar()
        box = U.entry(bar, self.q, width=16)
        box.pack(side="left", pady=6)
        self.found = tk.Label(bar, text="", bg=U.BG2, fg=U.FG_FAINT,
                              font=U.FONT_XS)
        self.found.pack(side="right", padx=16)
        self.q.trace_add("write", lambda *a: self.render())
        tk.Frame(wrap, bg=U.LINE2, height=2).pack(fill="x")

        head = tk.Frame(wrap, bg=U.INK, height=26)
        head.pack(fill="x")
        head.pack_propagate(False)
        for title, x, w, anchor in COLS:
            tk.Label(head, text=title, bg=U.INK, fg=U.FG_FAINT, font=U.FONT_XS,
                     anchor=anchor).place(x=x, y=0, width=w, relheight=1.0)
        tk.Frame(wrap, bg=U.LINE, height=2).pack(fill="x")

        holder = tk.Frame(wrap, bg=U.BG)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg=U.BG, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=U.BG)
        self._win = self.canvas.create_window((0, 0), window=self.inner,
                                              anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=e.width))

    def _wheel(self, e):
        """목록 위에 있을 때만 굴린다. 상세 패널에서는 아무 일도 없다."""
        w = e.widget
        while w is not None:
            if w is self.canvas or w is self.inner:
                self.canvas.yview_scroll(int(-e.delta / 60), "units")
                return
            w = getattr(w, "master", None)

    # ---------------- 상세 ----------------
    def _detail(self, parent):
        d = tk.Frame(parent, bg=U.BG2, width=DETAIL_W)
        d.pack(side="right", fill="y")
        d.pack_propagate(False)
        tk.Frame(d, bg=U.LINE2, width=2).place(x=0, y=0, relheight=1.0)

        p = tk.Frame(d, bg=U.BG2)
        p.pack(fill="both", expand=True, padx=(17, 15), pady=14)

        self.d_name = tk.Label(p, text="도구를 고르세요", bg=U.BG2, fg=U.FG_FAINT,
                               font=(U.FAMILY_BLACK, 16), anchor="w")
        self.d_name.pack(fill="x")
        self.d_en = tk.Label(p, text="", bg=U.BG2, fg=U.FG_FAINT,
                             font=U.FONT_XS, anchor="w")
        self.d_en.pack(fill="x", pady=(2, 0))
        self.d_tags = tk.Frame(p, bg=U.BG2)
        self.d_tags.pack(anchor="w", pady=(9, 0))

        eff = U.framed(p, bg=PANEL, border=U.LINE)
        eff.pack(fill="x", pady=(12, 0))
        self.d_eff = tk.Label(eff, text="", bg=PANEL, fg=U.FG, font=U.FONT_S,
                              wraplength=WRAP, justify="left", anchor="w")
        self.d_eff.pack(fill="x", padx=13, pady=(12, 0))
        self.d_note = tk.Label(eff, text="", bg=PANEL, fg=U.FG_FAINT,
                               font=U.FONT_XS, wraplength=WRAP, justify="left",
                               anchor="w")
        self.d_note.pack(fill="x", padx=13, pady=(5, 12))

        price = tk.Frame(p, bg=U.BG2)
        price.pack(fill="x", pady=(12, 0))
        self.d_cost = self._price_cell(price, "사는 값", 0)
        self.d_sell = self._price_cell(price, "파는 값", 1)
        self.d_have = self._price_cell(price, "보유", 2)

        U.marker_label(p, "개수", bg=U.BG2).pack(anchor="w", pady=(15, 7))
        qrow = tk.Frame(p, bg=U.BG2)
        qrow.pack(fill="x")
        U.ghost_button(qrow, "-", lambda: self.add_qty(-1),
                       height=36).pack(side="left")
        self.qty_lb = tk.Label(qrow, text="1", bg=U.INK, fg=U.FG,
                               font=(U.FAMILY_BLACK, 14), highlightthickness=2,
                               highlightbackground=U.LINE, highlightcolor=U.LINE)
        self.qty_lb.pack(side="left", fill="both", expand=True, padx=8, pady=2)
        U.ghost_button(qrow, "+", lambda: self.add_qty(1),
                       height=36).pack(side="left")

        quick = tk.Frame(p, bg=U.BG2)
        quick.pack(fill="x", pady=(8, 0))
        for i, n in enumerate((1, 10, 99)):
            U.ghost_button(quick, str(n), lambda v=n: self.set_qty(v), height=30
                           ).pack(side="left", fill="x", expand=True,
                                  padx=(0, 0 if i == 2 else 7))

        self.total = tk.Label(p, text="", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S,
                              anchor="w")
        self.total.pack(fill="x", pady=(11, 0))

        brow = tk.Frame(p, bg=U.BG2)
        brow.pack(fill="x", pady=(12, 0))
        self.btn_buy = U.PushButton(brow, "사기", self.do_buy, height=42)
        self.btn_buy.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.btn_sell = U.ghost_button(brow, "팔기", self.do_sell, height=42)
        self.btn_sell.pack(side="left", fill="x", expand=True)
        self._paint_buttons()

    def _price_cell(self, parent, title, col):
        """사는 값 / 파는 값 / 보유 를 담는 작은 액자 하나."""
        box = U.framed(parent, bg=PANEL, border=U.LINE)
        box.grid(row=0, column=col, sticky="nsew", padx=(0, 6 if col < 2 else 0))
        parent.grid_columnconfigure(col, weight=1)
        tk.Label(box, text=title, bg=PANEL, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(pady=(8, 0))
        val = tk.Label(box, text="—", bg=PANEL, fg=U.FG, font=U.FONT_NUM)
        val.pack(pady=(1, 9))
        return val

    # ---------------- 데이터 ----------------
    def reload(self):
        self.say("상점을 불러오는 중...", U.FG_FAINT)
        U.run_async(self.root, self.app.api.shop, self._loaded)

    def _loaded(self, data, err):
        if err:
            return self.say(_err(err), U.DANGER)
        data = data or {}
        self.items = data.get("items") or []
        self.bag = data.get("bag") or {}
        self.money = int(data.get("money") or 0)
        self.sell_rate = float(data.get("sellRate") or 0.5)
        self.sub.configure(text="파는 값은 사는 값의 %d%%  ·  도구 %d종"
                                % (round(self.sell_rate * 100), len(self.items)))
        self._paint_money()
        self._paint_cat_counts()
        self.render()
        self.say("무엇을 사시겠습니까?", U.GOOD)

    def _match(self, it, q):
        if self.cat != "all" and it.get("cat") != self.cat:
            return False
        if not q:
            return True
        return q in (it.get("kr", "") + it.get("en", "") + it.get("id", "")).lower()

    def render(self):
        """분류·검색어에 맞는 줄만 다시 그린다."""
        for w in self.inner.winfo_children():
            w.destroy()
        self.rows = {}
        q = (self.q.get() or "").strip().lower()
        shown = [it for it in self.items if self._match(it, q)]
        for it in shown:
            r = Row(self.inner, it, self.bag.get(it["id"], 0), self.select)
            r.pack()
            self.rows[it["id"]] = r
            tk.Frame(self.inner, bg="#181d2a", height=1).pack(fill="x")
        if not shown:
            tk.Label(self.inner, text="찾는 도구가 없습니다.", bg=U.BG,
                     fg=U.FG_FAINT, font=U.FONT_S).pack(pady=40)
        self.found.configure(text="%d개" % len(shown))
        self.canvas.yview_moveto(0)

        if self.sel in self.rows:
            self.select(self.sel, keep_qty=True)
        elif shown:
            self.select(shown[0]["id"])
        else:
            self.sel = None
            self._clear_detail()

    def current(self):
        return next((i for i in self.items if i["id"] == self.sel), None)

    def select(self, iid, keep_qty=False):
        changed = (iid != self.sel)
        self.sel = iid
        for key, r in self.rows.items():
            r.set_selected(key == iid)
        if changed and not keep_qty:
            self.qty = 1          # 다른 물건으로 옮겼는데 99개가 남아 있으면 위험하다
        self.show_detail()

    # ---------------- 상세 그리기 ----------------
    def _clear_detail(self):
        self.d_name.configure(text="도구를 고르세요", fg=U.FG_FAINT)
        self.d_en.configure(text="")
        for w in self.d_tags.winfo_children():
            w.destroy()
        self.d_eff.configure(text="가운데 목록에서 도구를 고르면\n설명이 여기에 나옵니다.")
        self.d_note.configure(text="")
        self.d_note.pack_forget()
        self.d_eff.pack_configure(pady=(12, 12))
        for lb in (self.d_cost, self.d_sell, self.d_have):
            lb.configure(text="—", fg=U.FG)
        self.total.configure(text="")
        self._paint_buttons()

    def show_detail(self):
        it = self.current()
        if not it:
            return self._clear_detail()

        rare = RARITY_COLOR.get(it.get("rarity"), U.FG_FAINT)
        self.d_name.configure(text=it.get("kr", it["id"]), fg=U.ACCENT_TEXT)
        self.d_en.configure(text=it.get("en", ""))

        for w in self.d_tags.winfo_children():
            w.destroy()
        U.chip(self.d_tags, RARITY_KR.get(it.get("rarity"), "등급 없음"), rare,
               padx=8, pady=2).pack(side="left", padx=(0, 5))
        cat_kr = dict(CATS).get(it.get("cat"), it.get("cat", ""))
        U.chip(self.d_tags, cat_kr, U.BG3, fg=U.FG,
               padx=8, pady=2).pack(side="left")

        # 덧말이 없으면 액자가 위아래로 찌그러지지 않게 여백을 옮겨 준다.
        self.d_eff.configure(text=effect_text(it))
        note = effect_note(it)
        self.d_note.configure(text=note)
        if note:
            self.d_note.pack(fill="x", padx=13, pady=(5, 12))
        else:
            self.d_note.pack_forget()
        self.d_eff.pack_configure(pady=(12, 0 if note else 12))

        buyable = bool(it.get("buyable")) and int(it.get("cost") or 0) > 0
        sell = int(it.get("sell") or 0)
        have = int(self.bag.get(it["id"], 0) or 0)
        self.d_cost.configure(text=won(it.get("cost")) if buyable else "안 판다",
                              fg=U.FG if buyable else U.FG_FAINT)
        self.d_sell.configure(text=won(sell) if sell else "—",
                              fg=U.FG if sell else U.FG_FAINT)
        self.d_have.configure(text=str(have),
                              fg=U.ACCENT if have else U.FG_FAINT)

        self._paint_totals()
        self._paint_buttons()

    def _paint_money(self):
        self.money_lb.configure(text=won(self.money))

    def _paint_totals(self):
        self.qty_lb.configure(text=str(self.qty))
        it = self.current()
        if not it:
            self.total.configure(text="")
            return
        bits = []
        buyable = bool(it.get("buyable")) and int(it.get("cost") or 0) > 0
        cost = int(it.get("cost") or 0) * self.qty
        if buyable:
            bits.append("사면 %s원" % won(cost))
        if int(it.get("sell") or 0):
            bits.append("팔면 %s원" % won(int(it["sell"]) * self.qty))
        short = buyable and cost > self.money
        self.total.configure(text="  ·  ".join(bits) or "사고팔 수 없는 물건",
                             fg=U.DANGER if short else U.FG_DIM)

    def _paint_buttons(self):
        it = self.current()
        have = int(self.bag.get(it["id"], 0) or 0) if it else 0
        can_buy = bool(it) and bool(it.get("buyable")) \
            and int((it or {}).get("cost") or 0) > 0 and not self.busy
        can_sell = bool(it) and int((it or {}).get("sell") or 0) > 0 \
            and have > 0 and not self.busy
        self.btn_buy.configure(state="normal" if can_buy else "disabled")
        self.btn_sell.configure(state="normal" if can_sell else "disabled")

    def _refresh_counts(self):
        """사고판 뒤 — 목록의 보유 개수와 상세를 다시 칠한다."""
        for iid, r in self.rows.items():
            r.set_have(self.bag.get(iid, 0))
        self.show_detail()

    # ---------------- 개수 ----------------
    def set_qty(self, n):
        self.qty = max(1, min(MAX_QTY, int(n)))
        self._paint_totals()

    def add_qty(self, d):
        # 1 -> 10 -> 99 처럼 자릿수가 커지면 걸음도 커지게 한다.
        step = 1 if self.qty < 10 else (5 if self.qty < 50 else 10)
        self.set_qty(self.qty + d * step)

    # ---------------- 사고팔기 ----------------
    def _done(self):
        def cb(res, err):
            self.busy = False
            if err:
                self._paint_buttons()
                return self.say(_err(err), U.DANGER)
            res = res or {}
            self.money = int(res.get("money", self.money))
            if isinstance(res.get("bag"), dict):
                self.bag = res["bag"]
            self._paint_money()
            self._refresh_counts()
            self.say(res.get("message") or "됐습니다.", U.GOOD)
            # 트레이의 몬스터볼 수를 서버 값과 맞춘다.
            try:
                self.app.request_sync()
            except Exception:
                pass
        return cb

    def do_buy(self):
        it = self.current()
        if not it or self.busy or not it.get("buyable"):
            return
        n = self.qty
        self.busy = True
        self._paint_buttons()
        self.say("%s %d개를 사는 중..." % (it["kr"], n), U.FG_FAINT)
        U.run_async(self.root, lambda: self.app.api.buy(it["id"], n),
                    self._done())

    def do_sell(self):
        it = self.current()
        if not it or self.busy or not int(it.get("sell") or 0):
            return
        n = self.qty
        self.busy = True
        self._paint_buttons()
        self.say("%s %d개를 파는 중..." % (it["kr"], n), U.FG_FAINT)
        U.run_async(self.root, lambda: self.app.api.sell(it["id"], n),
                    self._done())

    # ---------------- 창 ----------------
    def close(self):
        self.app.shop_window = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def focus(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()
