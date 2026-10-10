# -*- coding: utf-8 -*-
"""탐험 파견 탭 (1.10.4) — 박스의 포켓몬을 몇 시간 보내 두면 도구를 가져온다.

    왼쪽    탐험 칸 셋. 나가 있는 포켓몬과 남은 시간, 돌아온 보따리 받기, 불러들이기.
    가운데  ① 어디로 (갈 곳 여섯)  ② 얼마나 (2 · 4 · 8시간)
    오른쪽  ③ 누구를 (박스의 포켓몬, 그곳에서 잘할 차례로) -> [보내기]

세 단으로 나란히 둔다. 처음에는 오른쪽 한 단에 ①②③을 위에서 아래로 쌓았는데, 갈 곳 카드가
높이를 다 먹어서 정작 고를 포켓몬 목록이 두 줄밖에 안 보였다.

규칙(어디가 어떤 타입과 맞나, 성공도, 물건 수)은 common/expedition.py 에 있고 서버와 같이 쓴다.
그래서 **보내기 전에 성공도를 미리 보여 준다** - 목록은 지금 고른 곳에서 잘할 포켓몬부터 선다.

## 시간

서버가 '남은 초' 를 준다 (PC 시계와 상관없다). 받은 때부터 이 화면이 스스로 1초씩 센다.
0 이 되면 서버에 다시 물어 '돌아옴' 을 확인한다 - 화면이 먼저 '돌아왔다' 고 하지 않는다.

## 누구를: 긴 목록

박스에 수백 마리가 있을 수 있다. 목록은 보이는 줄만 만든다 (U.VirtualList).
데리고 다니는 포켓몬·알·이미 나가 있는 포켓몬은 목록에 없다 (보낼 수 없다).
"""
import time
import tkinter as tk

from PIL import ImageTk

from common import expedition as X
from common import tint as T
from common.korean import natural

from . import config, sprite_cache, sprites
from . import ui_common as U
from . import ui_loading
from .ui_common import run_async

LEFT_W = 300                 # 탐험 칸
MID_W = 304                  # 어디로 · 얼마나
CARD_H = U.h(96)             # 탐험 칸 하나. 창을 가장 낮게(620) 줄여도 셋이 다 들어가는 높이다
PLACE_H = U.h(30)            # 갈 곳 한 줄 (이름 + 맞는 타입 셋)
ROW_H = U.h(32)
THUMB = 40
PANEL = "#101623"
GRADE_COLOR = {"great": U.ACCENT, "good": U.GOOD, "normal": U.FG_DIM}
# 누구를: (제목, x, 폭, 정렬). 오른쪽 단의 폭(창 1020 에서 410 남짓)에 맞춘 값이다.
COLS = [("이름", 12, 132, "w"), ("Lv", 146, 32, "center"), ("타입", 182, 112, "w"),
        ("예상", 296, 54, "center"), ("물건", 352, 40, "center")]


def _err(e):
    return natural(getattr(e, "message", None) or str(e))


def types_of(dex, mon):
    sp = dex.get(mon.get("species")) if dex is not None else None
    return list((sp or {}).get("types") or [])


def candidates(mons, dex, place_id):
    """보낼 수 있는 포켓몬을 그곳에서 잘할 차례로. [(포켓몬, 점수, 성공도)]

    데리고 다니는 것·알·이미 나가 있는 것은 뺀다. 점수가 같으면 레벨 높은 것부터.
    """
    out = []
    for m in mons or []:
        if m.get("isEgg") or m.get("onDesktop") or m.get("away") or int(m.get("id") or 0) <= 0:
            continue
        pts = X.score(m.get("level", 0), types_of(dex, m), place_id)
        out.append((m, pts, X.grade(pts)))
    out.sort(key=lambda r: (-r[1], -int(r[0].get("level") or 0), r[0]["id"]))
    return out


class PickRow(object):
    """'누구를' 목록의 한 줄. 같은 줄이 여러 포켓몬을 돌아가며 보여 준다 (U.VirtualList)."""

    def __init__(self, parent, win):
        self.win = win
        self.data = None
        self.selected = False
        self.f = tk.Frame(parent, bg="#161a24")              # 아래 한 줄이 금으로 남는다
        self.body = tk.Frame(self.f, bg=U.BG, cursor="hand2")
        self.body.place(x=0, y=0, relwidth=1.0, height=ROW_H)
        self.mark = tk.Frame(self.body, bg=U.BG, width=3)
        self.mark.place(x=0, y=0, relheight=1.0)
        self.name = self._cell(COLS[0], U.FONT_S)
        self.lv = self._cell(COLS[1], U.FONT_B)
        self.types = tk.Frame(self.body, bg=U.BG)
        self.types.place(x=COLS[2][1], rely=0.5, anchor="w")
        self.chips = [U.chip(self.types, "", U.BG3, padx=6) for _i in range(2)]
        self.grade = self._cell(COLS[3], U.FONT_B)
        self.items = self._cell(COLS[4], U.FONT_XS)
        self.cells = [self.name, self.lv, self.types, self.grade, self.items]
        for w in [self.body] + self.cells + self.chips:
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>", self._in)
            w.bind("<Leave>", self._out)

    def _cell(self, col, font):
        _t, x, w, anchor = col
        lb = tk.Label(self.body, text="", bg=U.BG, fg=U.FG, font=font, anchor=anchor)
        lb.place(x=x, y=0, width=w, relheight=1.0)
        return lb

    def bind(self, data):
        self.data = data
        mon, _pts, grade = data
        dex = self.win.app.dex
        info = mon.get("info") or {}
        name = info.get("name") or mon.get("species") or "?"
        self.name.configure(text=("★ " if mon.get("shiny") else "") + name)
        self.lv.configure(text=str(mon.get("level", "")))
        tps = types_of(dex, mon)
        good = set((X.place(self.win.place) or {}).get("types") or ())
        for i, chip in enumerate(self.chips):
            if i < len(tps):
                t = tps[i]
                # 그곳과 맞는 타입은 제 색으로, 안 맞는 타입은 흐리게 - 왜 그 성공도인지가 보인다
                chip.configure(text=dex.type_name(t) if dex is not None else t,
                               bg=U.TYPE_COLOR.get(t, U.BG3) if t in good else U.BG3,
                               fg="#14141a" if t in good else U.FG_FAINT)
                if not chip.winfo_manager():
                    chip.pack(side="left", padx=(0, 3))
            elif chip.winfo_manager():
                chip.pack_forget()
        self.grade.configure(text=X.GRADE_KR.get(grade, ""), fg=GRADE_COLOR.get(grade, U.FG_DIM))
        self.items.configure(text="%d개" % X.item_count(self.win.hours, grade), fg=U.FG_DIM)
        self.selected = (mon["id"] == self.win.pick)
        self._look()

    def _paint(self, bg, mark):
        self.body.configure(bg=bg)
        self.mark.configure(bg=mark)
        for w in self.cells:
            w.configure(bg=bg)

    def _look(self):
        mon = self.data[0] if self.data else {}
        if self.selected:
            self._paint("#2b2417", U.ACCENT)
            self.name.configure(fg=U.ACCENT_TEXT, font=U.FONT_B)
        else:
            self._paint(U.BG, U.BG)
            self.name.configure(fg=U.SHINY if mon.get("shiny") else U.FG, font=U.FONT_S)

    def _click(self, _e):
        if self.data is not None:
            self.win.pick_mon(self.data[0]["id"])

    def _in(self, _e):
        if not self.selected:
            self._paint(U.BG2, U.LINE)

    def _out(self, _e):
        if not self.selected:
            self._paint(U.BG, U.BG)


class ExpeditionWindow(object):

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        self.alive = True
        self.state = None            # 서버가 준 것 (GET /api/expedition)
        self.mons = []               # 내 포켓몬 전부 (보낼 수 있는 것은 candidates 가 거른다)
        self.place = X.PLACES[0]["id"]
        self.hours = X.HOURS[1]
        self.pick = None             # 고른 포켓몬 id
        self.busy = False
        self._wait = None
        self._t0 = time.monotonic()  # state 를 받은 때 (남은 초를 여기서부터 센다)
        self._tick_job = None
        self._asked = False          # 0 이 된 것이 있어 서버에 물어보는 중
        self.thumbs = {}             # {(도감 번호, 색): PhotoImage}
        self.cards = []              # 탐험 칸의 틀 셋
        self.live = []               # 칸마다 1초에 한 번 고칠 것 [(탐험, 남은 시간 글, 막대)]
        self.place_cards = {}

        self.win = U.panel(parent, self.root, "포스크탑 — 탐험", 1020, 664, 980, 600, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            U.install_wheel(self.win)

        self._header()
        self._bottom()
        self.body = body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True)
        self._slots(body)
        self._send(body)
        self.reload()

    # ---------------- 머리 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=U.h(68))
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)
        # 나침반 (작은 그림)
        cv = tk.Canvas(inner, width=28, height=28, bg=U.BG2, highlightthickness=0, bd=0)
        cv.pack(side="left", pady=20)
        cv.create_oval(2, 2, 26, 26, fill="#f4f6fb", outline=U.INK, width=3)
        cv.create_polygon(14, 5, 18, 14, 14, 12, 10, 14, fill=U.RED, outline="")
        cv.create_polygon(14, 23, 18, 14, 14, 16, 10, 14, fill="#8a93a8", outline="")
        title = tk.Frame(inner, bg=U.BG2)
        title.pack(side="left", padx=(12, 0))
        tk.Label(title, text="탐험", bg=U.BG2, fg=U.FG, font=(U.FAMILY_BLACK, U.pt(15))).pack(anchor="w")
        self.sub = tk.Label(title, text="박스의 포켓몬을 보내 두면 도구를 가져옵니다", bg=U.BG2, fg=U.FG_FAINT,
                            font=U.FONT_XS)
        self.sub.pack(anchor="w")
        U.ghost_button(inner, "새로고침", self.reload, height=32).pack(side="right", pady=18)
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")
        tip = tk.Frame(self.win, bg=U.INK)
        tip.pack(fill="x")
        tk.Label(tip, text="타입이 맞고 레벨이 높을수록 잘 해냅니다.   프로그램을 꺼도 시간은 흐릅니다.   "
                           "나가 있는 동안은 데리고 다닐 수 없습니다.",
                 bg=U.INK, fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left", padx=16, pady=6)
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

    def _bottom(self):
        U.dot_footer(self.win, 1020, "길게, 잘 보낼수록 진화의 돌·병뚜껑 같은 귀한 것이 잘 나온다"
                     ).pack(fill="x", side="bottom")
        self.status = U.status_line(self.win, "", U.FG_FAINT)
        self.status.pack(fill="x", side="bottom")

    def say(self, msg, color=None):
        try:
            U.set_status(self.status, natural(msg or ""), color or U.FG_FAINT)
        except tk.TclError:
            pass

    # ---------------- 왼쪽: 탐험 칸 ----------------
    def _slots(self, body):
        left = tk.Frame(body, bg=U.BG, width=LEFT_W)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        head = tk.Frame(left, bg=U.BG)
        head.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(head, text="탐험 칸", bg=U.BG, fg=U.FG, font=U.FONT_B).pack(side="left")
        self.slot_note = tk.Label(head, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS)
        self.slot_note.pack(side="right")
        for _i in range(X.SLOTS):
            card = tk.Frame(left, bg=PANEL, height=CARD_H, highlightthickness=2, highlightbackground=U.LINE)
            card.pack(fill="x", padx=14, pady=(0, 6))
            card.pack_propagate(False)
            self.cards.append(card)
        tk.Frame(body, bg=U.LINE, width=1).pack(side="left", fill="y")

    def left_of(self, o):
        """그 탐험의 지금 남은 초 (받은 뒤 흐른 시간을 뺀다)."""
        return max(0, int(o.get("left") or 0) - int(time.monotonic() - self._t0))

    def _paint_slots(self):
        out = (self.state or {}).get("out") or []
        self.live = []
        ready = 0
        for i, card in enumerate(self.cards):
            for w in card.winfo_children():
                w.destroy()
            o = out[i] if i < len(out) else None
            if o is None:
                card.configure(highlightbackground=U.LINE)
                mid = tk.Frame(card, bg=PANEL)
                mid.place(relx=0.5, rely=0.5, anchor="center")
                tk.Label(mid, text="빈 칸", bg=PANEL, fg=U.FG_DIM, font=U.FONT_B).pack()
                tk.Label(mid, text="오른쪽에서 골라 보내세요", bg=PANEL, fg=U.FG_FAINT, font=U.FONT_XS).pack(pady=(3, 0))
                continue
            done = self.left_of(o) <= 0 and bool(o.get("ready"))
            ready += done
            card.configure(highlightbackground=U.ACCENT if done else U.LINE)
            self._slot_card(card, o, done)
        n = len(out)
        self.slot_note.configure(text="%d / %d 칸 사용 중" % (n, X.SLOTS) + (" · 돌아옴 %d" % ready if ready else ""))

    def _slot_card(self, card, o, done):
        mon = o.get("pokemon") or {}
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x", padx=10, pady=(7, 0))
        slot = tk.Frame(top, bg=PANEL, width=U.h(42), height=U.h(42))
        slot.pack(side="left")
        slot.pack_propagate(False)
        art = tk.Label(slot, bg=PANEL)
        art.pack(expand=True)
        self._thumb(art, mon)
        text = tk.Frame(top, bg=PANEL)
        text.pack(side="left", padx=(8, 0), fill="x", expand=True)
        line = tk.Frame(text, bg=PANEL)
        line.pack(fill="x")
        tk.Label(line, text=("★ " if mon.get("shiny") else "") + (mon.get("name") or "?"), bg=PANEL,
                 fg=U.SHINY if mon.get("shiny") else U.FG, font=U.FONT_B, anchor="w").pack(side="left")
        tk.Label(line, text="Lv.%s" % mon.get("level", "?"), bg=PANEL, fg=U.FG_DIM,
                 font=U.FONT_XS).pack(side="left", padx=(6, 0))
        sub = tk.Frame(text, bg=PANEL)
        sub.pack(fill="x", pady=(2, 0))
        tk.Label(sub, text="%s · %s시간" % (o.get("placeKr") or "", o.get("hours")), bg=PANEL, fg=U.FG_DIM,
                 font=U.FONT_XS).pack(side="left")
        tk.Label(sub, text=o.get("gradeKr") or "", bg=PANEL, fg=GRADE_COLOR.get(o.get("grade"), U.FG_DIM),
                 font=U.FONT_XS).pack(side="left", padx=(8, 0))
        tk.Label(sub, text="물건 %s개" % o.get("items", "?"), bg=PANEL, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="left", padx=(8, 0))

        foot = tk.Frame(card, bg=PANEL)
        foot.pack(fill="x", side="bottom", padx=10, pady=(0, 7))
        if done:
            U.PushButton(foot, "보따리 받기", lambda e=o["id"]: self.claim(e), height=28,
                         font=U.FONT_B).pack(side="right")
            tk.Label(foot, text="돌아왔습니다!", bg=PANEL, fg=U.ACCENT_TEXT, font=U.FONT_B).pack(side="left")
            return
        U.ghost_button(foot, "불러들이기", lambda e=o: self.recall(e), height=26).pack(side="right")
        left_lbl = tk.Label(foot, text="", bg=PANEL, fg=U.FG, font=U.FONT_S)
        left_lbl.pack(side="left")
        bar = tk.Frame(card, bg=U.INK, height=U.h(5))
        bar.pack(fill="x", side="bottom", padx=10, pady=(0, 6))
        fill = tk.Frame(bar, bg=U.GOOD)
        fill.place(x=0, y=0, relheight=1.0, relwidth=0.0)
        self.live.append((o, left_lbl, fill))
        self._paint_live(o, left_lbl, fill)

    def _paint_live(self, o, label, fill):
        left = self.left_of(o)
        total = max(1, int(o.get("total") or 1))
        try:
            label.configure(text=("%s 남음" % X.hours_text(left)) if left > 0 else "돌아오는 중...")
            fill.place_configure(relwidth=max(0.0, min(1.0, 1.0 - left / float(total))))
        except tk.TclError:
            pass

    def _tick(self):
        self._tick_job = None
        if not self.alive:
            return
        soon = False
        for o, label, fill in self.live:
            self._paint_live(o, label, fill)
            soon = soon or self.left_of(o) <= 0
        if soon and not self._asked:
            # 돌아올 때가 됐다. 서버에 물어 확인한다 (화면이 먼저 돌아왔다고 하지 않는다)
            self._asked = True
            self.root.after(1200, self._ask_state)
        if self.live:
            self._tick_job = self.root.after(1000, self._tick)

    def _ask_state(self):
        if not self.alive:
            return

        def done(r, err):
            self._asked = False
            if not self.alive or err or not isinstance(r, dict):
                return
            self.apply(r)
            desk = getattr(self.app, "expedition", None)
            if desk is not None:
                desk.note(r)
        run_async(self.root, self.app.api.expedition, done)

    # ---------------- 가운데: 어디로 · 얼마나 ----------------
    def _send(self, body):
        mid = tk.Frame(body, bg=U.BG, width=MID_W)
        mid.pack(side="left", fill="y")
        mid.pack_propagate(False)
        head = tk.Frame(mid, bg=U.BG)
        head.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(head, text="① 어디로", bg=U.BG, fg=U.FG, font=U.FONT_B).pack(side="left")
        tk.Label(head, text="곳마다 잘 맞는 타입이 다릅니다", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS).pack(side="right")
        dex = self.app.dex
        for p in X.PLACES:
            card = tk.Frame(mid, bg=PANEL, height=PLACE_H, highlightthickness=2, highlightbackground=U.LINE,
                            cursor="hand2")
            card.pack(fill="x", padx=14, pady=(0, 4))
            card.pack_propagate(False)
            name = tk.Label(card, text=p["kr"], bg=PANEL, fg=U.FG, font=U.FONT_B, anchor="w")
            name.place(x=10, rely=0.5, anchor="w")
            chips = tk.Frame(card, bg=PANEL)
            chips.place(x=U.h(54), rely=0.5, anchor="w")
            kids = [name, chips]
            for t in p["types"]:
                c = U.chip(chips, dex.type_name(t) if dex is not None else t, U.TYPE_COLOR.get(t, U.BG3), padx=6)
                c.pack(side="left", padx=(0, 4))
                kids.append(c)
            for w in [card] + kids:
                w.bind("<Button-1>", lambda _e, k=p["id"]: self.set_place(k))
            self.place_cards[p["id"]] = (card, name, chips)
        # 고른 곳에서 잘 나오는 것 (카드마다 적으면 카드가 두 줄이 되어 높이가 모자란다)
        box = tk.Frame(mid, bg=U.INK, highlightthickness=1, highlightbackground=U.LINE)
        box.pack(fill="x", padx=14, pady=(2, 0))
        self.place_head = tk.Label(box, text="", bg=U.INK, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w")
        self.place_head.pack(fill="x", padx=9, pady=(5, 0))
        self.place_hint = tk.Label(box, text="", bg=U.INK, fg=U.ACCENT_TEXT, font=U.FONT_S, anchor="w")
        self.place_hint.pack(fill="x", padx=9, pady=(1, 6))

        row = tk.Frame(mid, bg=U.BG)
        row.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(row, text="② 얼마나", bg=U.BG, fg=U.FG, font=U.FONT_B).pack(side="left")
        self.hours_seg = U.Segmented(row, [(h, "%d시간" % h) for h in X.HOURS], self.hours, self.set_hours)
        self.hours_seg.frame.pack(side="right")
        self.hours_note = tk.Label(mid, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="e")
        self.hours_note.pack(fill="x", padx=14, pady=(4, 0))
        tk.Frame(body, bg=U.LINE, width=1).pack(side="left", fill="y")

        # ---- 오른쪽: 누구를
        right = tk.Frame(body, bg=U.BG)
        right.pack(side="left", fill="both", expand=True)
        head = tk.Frame(right, bg=U.BG)
        head.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(head, text="③ 누구를", bg=U.BG, fg=U.FG, font=U.FONT_B).pack(side="left")
        self.pick_note = tk.Label(head, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS)
        self.pick_note.pack(side="right")

        # 바닥의 보내기 줄을 먼저 잡는다 (목록이 남은 높이를 다 먹는다)
        foot = tk.Frame(right, bg=U.BG2, height=U.h(62))
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)
        tk.Frame(right, bg=U.LINE, height=U.h(1)).pack(fill="x", side="bottom")
        self.send_btn = U.PushButton(foot, "보내기", self.do_send, height=34, font=U.FONT_B)
        self.send_btn.pack(side="right", padx=(8, 14), pady=12)
        self.summary = tk.Label(foot, text="", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left")
        self.summary.pack(side="left", padx=(14, 0), fill="both", expand=True)
        U.wrap_to_width(self.summary)

        colhead = tk.Frame(right, bg=U.INK, height=U.h(26))
        colhead.pack(fill="x", padx=14)
        colhead.pack_propagate(False)
        for title, x, w, anchor in COLS:
            tk.Label(colhead, text=title, bg=U.INK, fg=U.FG_FAINT, font=U.FONT_XS,
                     anchor=anchor).place(x=x, y=0, width=w, relheight=1.0)
        wrap = tk.Frame(right, bg=U.BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        self.vl = U.VirtualList(wrap, {"mon": (ROW_H + U.h(1), lambda p: PickRow(p, self))}, bg=U.BG)
        self.vl.pack(fill="both", expand=True)
        self.empty = tk.Label(wrap, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S, justify="center")
        self._paint_place()
        self._paint_hours()

    def _paint_place(self):
        for pid, (card, name, chips) in self.place_cards.items():
            on = pid == self.place
            bg = U.ACCENT_SOFT if on else PANEL
            card.configure(bg=bg, highlightbackground=U.ACCENT if on else U.LINE)
            name.configure(bg=bg, fg=U.ACCENT_TEXT if on else U.FG)
            chips.configure(bg=bg)
        p = X.place(self.place) or {}
        self.place_head.configure(text="%s에서 잘 나오는 것" % p.get("kr", ""))
        self.place_hint.configure(text=p.get("hint", ""))

    def _paint_hours(self):
        self.hours_seg.set(self.hours)
        row = X.ITEMS.get(self.hours) or (0, 0, 0)
        self.hours_note.configure(text="물건 %d ~ %d개를 가져옵니다 (성공도에 따라)" % (row[0], row[-1])
                                  if row[0] != row[-1] else "물건 %d개를 가져옵니다" % row[0])

    def set_place(self, place_id):
        if place_id == self.place or X.place(place_id) is None:
            return
        self.place = place_id
        self._paint_place()
        # 곳이 바뀌면 잘할 차례가 달라진다. 그곳에서 가장 잘할 포켓몬(맨 위)을 다시 골라 둔다 -
        # 고르던 포켓몬을 그대로 두면 다시 선 목록의 저 아래로 내려가 안 보인다.
        self.pick = None
        self._fill(keep=False)

    def set_hours(self, hours):
        self.hours = int(hours)
        self._paint_hours()
        self.vl.refresh()
        self._paint_summary()

    def shown(self):
        """지금 화면에 걸친 줄 [(포켓몬 id, 줄)] (검사가 본다)."""
        return [(r.data[0]["id"], r) for _i, r in self.vl.shown() if r.data is not None]

    def _fill(self, keep=True):
        rows = candidates(self.mons, self.app.dex, self.place)
        ids = [m["id"] for m, _p, _g in rows]
        if self.pick not in ids:
            self.pick = ids[0] if ids else None
        self.vl.set([("mon", r) for r in rows], keep=keep)
        boxed = len(rows)
        self.pick_note.configure(text="박스 %d마리 · 잘할 차례로" % boxed if boxed else "")
        if rows:
            self.empty.place_forget()
        else:
            have = any(not m.get("isEgg") for m in self.mons)
            self.empty.configure(text="박스에 있는 포켓몬만 보낼 수 있습니다.\n포켓몬 탭에서 박스에 넣어 주세요." if have
                                 else "보낼 포켓몬이 없습니다.")
            self.empty.place(relx=0.5, rely=0.4, anchor="center")
        self._paint_summary()

    def pick_mon(self, pid):
        self.pick = pid
        self.vl.refresh()
        self._paint_summary()

    def _picked(self):
        for kind, data in self.vl.entries:
            if data[0]["id"] == self.pick:
                return data
        return None

    def free(self):
        return max(0, X.SLOTS - len((self.state or {}).get("out") or []))

    def _paint_summary(self):
        data = self._picked()
        p = X.place(self.place) or {}
        if self.state is not None and self.free() <= 0:
            self.summary.configure(text="탐험 칸이 꽉 찼습니다.\n돌아온 보따리를 받으면 칸이 빕니다.", fg=U.FG_FAINT)
            self.send_btn.configure(state="disabled")
            return
        if data is None:
            self.summary.configure(text="보낼 포켓몬을 고르세요.", fg=U.FG_FAINT)
            self.send_btn.configure(state="disabled")
            return
        mon, _pts, grade = data
        name = (mon.get("info") or {}).get("name") or "?"
        self.summary.configure(
            text="%s Lv.%s → %s · %d시간\n예상 %s · 물건 %d개"
                 % (name, mon.get("level", "?"), p.get("kr", ""), self.hours, X.GRADE_KR.get(grade, ""),
                    X.item_count(self.hours, grade)),
            fg=U.FG)
        self.send_btn.configure(state="disabled" if self.busy else "normal")

    # ---------------- 서버 ----------------
    def reload(self):
        if self._wait is None:
            self._wait = ui_loading.Overlay(self.win, "불러오는 중")
        api = self.app.api

        def work():
            st = api.expedition()
            mons = api.pokemon_boxes()[0]
            return st, mons
        run_async(self.root, work, self._loaded)

    def _loaded(self, r, err):
        wait, self._wait = self._wait, None
        if wait is not None:
            wait.close()
        if not self.alive:
            return
        if err:
            return self.say("불러오지 못했습니다. %s" % _err(err), U.RED)
        st, mons = r
        self.mons = list(mons or [])
        self.apply(st)
        self._fill(keep=True)

    def apply(self, state):
        """서버가 준 탐험 상태를 화면에 올린다 (보내기·받기·불러들이기의 답도 같은 모양이다)."""
        if not self.alive or not isinstance(state, dict) or "out" not in state:
            return
        self.state = state
        self._t0 = time.monotonic()
        # 나가 있는 포켓몬은 '누구를' 목록에서 빠진다 (돌아온 포켓몬은 다시 들어온다)
        away = set(int((o.get("pokemon") or {}).get("id") or 0) for o in state.get("out") or [])
        changed = False
        for m in self.mons:
            now_away = m.get("id") in away
            if bool(m.get("away")) != now_away:
                m["away"] = now_away
                changed = True
        self._paint_slots()
        if changed:
            self._fill(keep=True)
        else:
            self._paint_summary()
        if self._tick_job is None and self.live:
            self._tick_job = self.root.after(1000, self._tick)

    def do_send(self):
        data = self._picked()
        if data is None or self.busy or self.free() <= 0:
            return                           # (칸이 꽉 찼으면 단추가 잠겨 있다 - 눌려도 서버에 안 간다)
        mon = data[0]
        self.busy = True
        self.send_btn.configure(state="disabled")
        place, hours = self.place, self.hours

        def done(r, err):
            self.busy = False
            if not self.alive:
                return
            if err:
                self._paint_summary()
                return self.say(_err(err), U.RED)
            self.apply(r)
            self.say(r.get("message") or "보냈습니다.", U.GOOD)
            self._after_change(r)
        run_async(self.root, lambda: self.app.api.expedition_send(mon["id"], place, hours), done)

    def claim(self, eid):
        desk = getattr(self.app, "expedition", None)
        if desk is not None:
            return desk.claim(eid, parent=self.win.winfo_toplevel())

    def recall(self, o):
        from . import ui_box
        mon = o.get("pokemon") or {}
        if not ui_box.confirm(self.win.winfo_toplevel(), "불러들이기",
                              "%s 을(를) 지금 불러들일까요? 빈손으로 돌아옵니다." % (mon.get("name") or "포켓몬"),
                              danger=False, ok_text="불러들이기"):
            return

        def done(r, err):
            if not self.alive:
                return
            if err:
                return self.say(_err(err), U.RED)
            self.apply(r)
            self.say(r.get("message") or "불러들였습니다.", U.FG_DIM)
            self._after_change(r)
        run_async(self.root, lambda: self.app.api.expedition_recall(o["id"]), done)

    def _after_change(self, state):
        """보내거나 불러들였다: 바탕화면의 보따리 예약과 포켓몬 관리 창을 맞춘다."""
        desk = getattr(self.app, "expedition", None)
        if desk is not None:
            desk.note(state)
        box = getattr(self.app, "box_window", None)
        if box is not None:
            try:
                box.reload()                 # '탐험 중' 표시가 바뀐다
            except Exception as e:                          # noqa: BLE001
                config.log("관리 창 갱신 오류: %s" % e)

    # ---------------- 도트 ----------------
    def _thumb(self, label, mon):
        num, skin = mon.get("num"), T.skin(mon)
        if not num:
            return
        key = (num, skin)
        got = self.thumbs.get(key)
        if got is not None:
            return label.configure(image=got)
        api = self.app.api
        size = U.h(THUMB)

        def work():
            path = sprite_cache.ensure(api, num, skin)
            if not path:
                return None
            anim = sprites.load_animation(path, size, 0.2, 3.0, max_frames=1, max_size=(size, size))
            return sprites.to_rgba(anim.frames[sprites.RIGHT][0], anim.key)

        def done(img, err):
            if not self.alive or err or img is None:
                return
            try:
                ph = self.thumbs.get(key) or ImageTk.PhotoImage(img)
                self.thumbs[key] = ph
                label.configure(image=ph)
            except tk.TclError:
                pass                         # 그사이 칸을 다시 그렸다
        run_async(self.root, work, done)

    # ---------------- 끝 ----------------
    def close(self):
        self.alive = False
        if self._tick_job is not None:
            try:
                self.root.after_cancel(self._tick_job)
            except Exception:                               # noqa: BLE001
                pass
            self._tick_job = None
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
