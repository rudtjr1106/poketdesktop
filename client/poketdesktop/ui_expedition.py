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
알·이미 나가 있는 포켓몬은 목록에 없다 (보낼 수 없다).

줄은 두 줄이다 (1.10.5): 이름·레벨 / 타입, 오른쪽에 예상 성공도 / 탐험 레벨. 한 줄에 다섯 칸을
나란히 뒀더니 허브를 가장 좁게 줄였을 때 오른쪽 두 칸이 창 밖으로 나가 있었다.

## 쉬기와 성장 (1.10.5)

다녀온 포켓몬은 24시간 쉰다. 쉬는 포켓몬은 목록의 **아래쪽**에 흐리게 서고 (곧 끝나는 차례로), 남은
시간이 적힌다. 골라서 성장치를 찍을 수는 있지만 보낼 수는 없다. 데리고 다니는 포켓몬 가운데 탐험을
다녀온 적이 있는 것도 맨 아래에 선다 - 성장치를 찍을 길이 있어야 한다.

성장치는 [성장] 단추의 창에서 찍는다 (GrowDialog). 레벨마다 받은 점수를 발걸음·눈썰미·주머니·호기심·
친화력에 나눠 찍고, 찍기 전에는 얼마든지 넣었다 뺐다 할 수 있다. 서버에는 [찍기] 를 눌렀을 때 한 번 간다.
"""
import time
import tkinter as tk

from PIL import ImageTk

from common import expedition as X
from common import tint as T
from common.korean import natural

from . import config, skins, sprite_cache, sprites
from . import ui_common as U
from . import ui_loading
from .ui_common import run_async

LEFT_W = 300                 # 탐험 칸
MID_W = 304                  # 어디로 · 얼마나
CARD_H = U.h(96)             # 탐험 칸 하나. 창을 가장 낮게(620) 줄여도 셋이 다 들어가는 높이다
PLACE_H = U.h(30)            # 갈 곳 한 줄 (이름 + 맞는 타입 셋)
ROW_H = U.h(44)              # '누구를' 의 한 줄 (이름·레벨 / 타입 두 줄)
THUMB = 40
PANEL = "#101623"
GRADE_COLOR = {"great": U.ACCENT, "good": U.GOOD, "normal": U.FG_DIM}
GROW_W = 470                 # 성장 창의 폭
PIP = 9                      # 성장치 한 점의 네모 (px - 글자가 아니라서 글꼴 배율을 안 탄다)


def _err(e):
    return natural(getattr(e, "message", None) or str(e))


def types_of(dex, mon):
    sp = dex.get(mon.get("species")) if dex is not None else None
    return list((sp or {}).get("types") or [])


def candidates(mons, dex, place_id, growth=None):
    """'누구를' 목록에 설 포켓몬. [(포켓몬, 점수, 성공도)]

    보낼 수 있는 것이 먼저다 (그곳에서 잘할 차례로, 점수가 같으면 레벨 높은 것부터). 그 아래에 쉬는
    포켓몬 (곧 끝나는 차례로), 맨 아래에 데리고 다니는 포켓몬 가운데 탐험을 다녀온 적이 있는 것.
    알과 이미 나가 있는 것은 뺀다. growth = {포켓몬 id(글자): {"rest": 남은 초, "xp": ...}} (서버가 준 것).
    """
    growth = growth or {}
    ok, resting, party = [], [], []
    for m in mons or []:
        if m.get("isEgg") or m.get("away") or int(m.get("id") or 0) <= 0:
            continue
        g = growth.get(str(m["id"])) or {}
        pts = X.score(m.get("level", 0), types_of(dex, m), place_id)
        row = (m, pts, X.grade(pts))
        if m.get("onDesktop"):
            if int(g.get("xp") or 0) > 0:
                party.append(row)
        elif int(g.get("rest") or 0) > 0:
            resting.append((int(g["rest"]), row))
        else:
            ok.append(row)
    by_score = lambda r: (-r[1], -int(r[0].get("level") or 0), r[0]["id"])      # noqa: E731
    ok.sort(key=by_score)
    resting.sort(key=lambda x: (x[0],) + by_score(x[1]))
    party.sort(key=by_score)
    return ok + [r for _rest, r in resting] + party


class PickRow(object):
    """'누구를' 목록의 한 줄. 같은 줄이 여러 포켓몬을 돌아가며 보여 준다 (U.VirtualList).

        ▌ 이상해꽃  Lv.80                 대성공
        ▌ [풀] [독]                    탐험 Lv.3

    쉬는 포켓몬은 흐리게, 오른쪽에 '쉬는 중 / 23시간 뒤'. 글자는 place 로 놓되 폭·높이를 주지 않는다 -
    제 크기만큼 선다 (폭을 박아 두면 글꼴이 다른 PC 에서 잘린다).
    """

    def __init__(self, parent, win):
        self.win = win
        self.data = None
        self.selected = False
        self.state = "ok"
        self.f = tk.Frame(parent, bg="#161a24")              # 아래 한 줄이 금으로 남는다
        self.body = tk.Frame(self.f, bg=U.BG, cursor="hand2")
        self.body.place(x=0, y=0, relwidth=1.0, height=ROW_H - U.h(1))
        self.mark = tk.Frame(self.body, bg=U.BG, width=3)
        self.mark.place(x=0, y=0, relheight=1.0)
        x = 12
        self.name = self._label(U.FONT_B)
        self.name.place(x=x, rely=0.30, anchor="w")
        self.lv = self._label(U.FONT_XS)
        self.types = tk.Frame(self.body, bg=U.BG)
        self.types.place(x=x, rely=0.72, anchor="w")
        self.chips = [U.chip(self.types, "", U.BG3, padx=6) for _i in range(2)]
        self.grade = self._label(U.FONT_B)
        self.grade.place(relx=1.0, x=-8, rely=0.30, anchor="e")
        self.grow = self._label(U.FONT_XS)
        self.grow.place(relx=1.0, x=-8, rely=0.72, anchor="e")
        self.cells = [self.name, self.lv, self.types, self.grade, self.grow]
        for w in [self.body] + self.cells + self.chips:
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>", self._in)
            w.bind("<Leave>", self._out)

    def _label(self, font):
        return tk.Label(self.body, text="", bg=U.BG, fg=U.FG, font=font, bd=0, padx=0, pady=0)

    def bind(self, data):
        self.data = data
        mon, _pts, grade = data
        win = self.win
        dex = win.app.dex
        info = mon.get("info") or {}
        name = info.get("name") or mon.get("species") or "?"
        self.state = st = win.mon_state(mon)
        g = win.growth_of(mon["id"])
        self.name.configure(text=("★ " if mon.get("shiny") else "") + name)
        self.lv.configure(text="Lv.%s" % mon.get("level", ""))
        self.lv.place(in_=self.name, relx=1.0, x=6, rely=0.5, anchor="w")       # 이름 바로 뒤에
        tps = types_of(dex, mon)
        good = set((X.place(win.place) or {}).get("types") or ())
        for i, chip in enumerate(self.chips):
            if i < len(tps):
                t = tps[i]
                # 그곳과 맞는 타입은 제 색으로, 안 맞는 타입은 흐리게 - 왜 그 성공도인지가 보인다
                lit = t in good and st == "ok"
                chip.configure(text=dex.type_name(t) if dex is not None else t,
                               bg=U.TYPE_COLOR.get(t, U.BG3) if lit else U.BG3,
                               fg="#14141a" if lit else U.FG_FAINT)
                if not chip.winfo_manager():
                    chip.pack(side="left", padx=(0, 3))
            elif chip.winfo_manager():
                chip.pack_forget()
        if st == "rest":
            self.grade.configure(text="쉬는 중", fg=U.FG_FAINT)
            self.grow.configure(text="%s 뒤" % X.hours_text(win.rest_left(mon["id"])), fg=U.FG_FAINT)
        elif st == "party":
            self.grade.configure(text="데리고 다니는 중", fg=U.FG_FAINT)
            self.grow.configure(text=grow_text(g), fg=U.ACCENT_TEXT if g.get("free") else U.FG_FAINT)
        else:
            self.grade.configure(text=X.GRADE_KR.get(grade, ""), fg=GRADE_COLOR.get(grade, U.FG_DIM))
            self.grow.configure(text=grow_text(g), fg=U.ACCENT_TEXT if g.get("free") else U.FG_FAINT)
        self.selected = (mon["id"] == win.pick)
        self._look()

    def _paint(self, bg, mark):
        self.body.configure(bg=bg)
        self.mark.configure(bg=mark)
        for w in self.cells:
            w.configure(bg=bg)

    def _look(self):
        mon = self.data[0] if self.data else {}
        dim = self.state != "ok"
        if self.selected:
            self._paint("#2b2417", U.ACCENT)
            self.name.configure(fg=U.ACCENT_TEXT)
        else:
            self._paint(U.BG, U.BG)
            self.name.configure(fg=U.FG_FAINT if dim else (U.SHINY if mon.get("shiny") else U.FG))
        self.lv.configure(fg=U.FG_FAINT if dim else U.FG_DIM)

    def _click(self, _e):
        if self.data is not None:
            self.win.pick_mon(self.data[0]["id"])

    def _in(self, _e):
        if not self.selected:
            self._paint(U.BG2, U.LINE)

    def _out(self, _e):
        if not self.selected:
            self._paint(U.BG, U.BG)


def grow_text(g):
    """줄의 오른쪽 아래: 탐험 레벨. 찍을 점수가 남았으면 점을 붙인다 (색은 부르는 쪽이 바꾼다)."""
    lv = int((g or {}).get("level") or 0)
    free = int((g or {}).get("free") or 0)
    if not lv and not free:
        return "탐험 Lv.0"
    return "탐험 Lv.%d" % lv + (" ● %d점" % free if free else "")


@skins.skinnable
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
        self.growth = {}             # {포켓몬 id(글자): 탐험 성장·쉬는 시간} - 서버가 준 것 (1.10.5)
        self._rest_job = None        # 쉬는 시간이 줄어드는 것을 가끔 다시 칠한다
        self.grow_dialog = None
        self._cands = []             # '누구를' 목록에 선 것 [(포켓몬, 점수, 성공도)]

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
        # 위아래 여백을 숫자로 박지 않는다 (pack 이 가운데로 놓는다). pady=18 로 두었더니 윈도우(글꼴 10pt)
        # 에서 머리줄이 68px 라 단추(36px)가 4px 눌려 있었다.
        self.reload_btn = U.ghost_button(inner, "새로고침", self.reload, height=32)
        self.reload_btn.pack(side="right")
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")
        tip = tk.Frame(self.win, bg=U.INK)
        tip.pack(fill="x")
        tk.Label(tip, text="타입이 맞고 레벨이 높을수록 잘 해냅니다.   꺼 두어도 시간은 흐릅니다.   "
                           "다녀온 포켓몬은 %d시간 쉬고, 탐험 경험치가 쌓입니다." % X.REST_HOURS,
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

    def _slots_data(self):
        """탐험 칸 셋: ([(탐험 또는 None, 돌아왔나)], '2 / 3 칸 사용 중 · 돌아옴 1')."""
        out = (self.state or {}).get("out") or []
        rows, ready = [], 0
        for i in range(X.SLOTS):
            o = out[i] if i < len(out) else None
            done = o is not None and self.left_of(o) <= 0 and bool(o.get("ready"))
            ready += done
            rows.append((o, done))
        return rows, "%d / %d 칸 사용 중" % (len(out), X.SLOTS) + (" · 돌아옴 %d" % ready if ready else "")

    def _paint_slots(self):
        rows, note = self._slots_data()
        self.live = []
        self._paint_slot_cards(rows, note)

    def _paint_slot_cards(self, rows, note):
        """탐험 칸 셋 (테마마다 그리는 곳). 남은 시간을 1초마다 고칠 것은 self.live 에 (탐험, ...) 로 넣는다."""
        for card, (o, done) in zip(self.cards, rows):
            for w in card.winfo_children():
                w.destroy()
            if o is None:
                card.configure(highlightbackground=U.LINE)
                mid = tk.Frame(card, bg=PANEL)
                mid.place(relx=0.5, rely=0.5, anchor="center")
                tk.Label(mid, text="빈 칸", bg=PANEL, fg=U.FG_DIM, font=U.FONT_B).pack()
                tk.Label(mid, text="오른쪽에서 골라 보내세요", bg=PANEL, fg=U.FG_FAINT, font=U.FONT_XS).pack(pady=(3, 0))
                continue
            card.configure(highlightbackground=U.ACCENT if done else U.LINE)
            self._slot_card(card, o, done)
        self.slot_note.configure(text=note)

    def _slot_card(self, card, o, done):
        mon = o.get("pokemon") or {}
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x", padx=10, pady=(7, 0))
        slot = tk.Frame(top, bg=PANEL, width=U.h(42), height=U.h(42))
        slot.pack(side="left")
        slot.pack_propagate(False)
        art = tk.Label(slot, bg=PANEL, bd=0, highlightthickness=0)     # (테두리 4px 이 칸보다 커서 눌렸다)
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

    def live_of(self, o):
        """나가 있는 탐험의 지금: ('3시간 12분 남음', 지난 몫 0~1)."""
        left = self.left_of(o)
        total = max(1, int(o.get("total") or 1))
        return (("%s 남음" % X.hours_text(left)) if left > 0 else "돌아오는 중..."), \
            max(0.0, min(1.0, 1.0 - left / float(total)))

    def _paint_live(self, o, label, fill):
        text, frac = self.live_of(o)
        try:
            label.configure(text=text)
            fill.place_configure(relwidth=frac)
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

        # 바닥의 보내기 줄을 먼저 잡는다 (목록이 남은 높이를 다 먹는다).
        # 높이를 박아 두지 않는다: 요약 글이 좁은 창에서 서너 줄로 접히면 그만큼 자란다 (단추의 높이가
        # 바닥값이다). 62px 로 박아 두면 성장치를 여럿 찍은 포켓몬의 요약이 아래로 잘린다.
        foot = tk.Frame(right, bg=U.BG2)
        foot.pack(fill="x", side="bottom")
        tk.Frame(right, bg=U.LINE, height=U.h(1)).pack(fill="x", side="bottom")
        self.send_btn = U.PushButton(foot, "보내기", self.do_send, height=34, font=U.FONT_B)
        self.send_btn.pack(side="right", padx=(6, 14), pady=12)
        # 성장: 고른 포켓몬의 탐험 레벨과 성장치 (찍을 점수가 남았으면 점이 붙는다)
        self.grow_btn = U.ghost_button(foot, "성장", self.open_grow, height=34)
        self.grow_btn.pack(side="right", pady=12)
        self.summary = tk.Label(foot, text="", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left")
        self.summary.pack(side="left", padx=(14, 6), pady=8, fill="both", expand=True)
        U.wrap_to_width(self.summary)

        tk.Frame(right, bg=U.LINE, height=U.h(1)).pack(fill="x", padx=14)
        wrap = tk.Frame(right, bg=U.BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        self.vl = U.VirtualList(wrap, {"mon": (ROW_H, lambda p: PickRow(p, self))}, bg=U.BG)
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
        self.hours_note.configure(text=self.hours_text())

    def hours_text(self):
        """고른 시간에 가져올 물건 수."""
        row = X.ITEMS.get(self.hours) or (0, 0, 0)
        return ("물건 %d ~ %d개를 가져옵니다 (성공도에 따라)" % (row[0], row[-1])
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

    # ---- 쉬기와 성장 (1.10.5)
    def growth_of(self, pid):
        """그 포켓몬의 탐험 성장 (다녀온 적이 없으면 0 에서 시작)."""
        return self.growth.get(str(pid)) or {"xp": 0, "level": 0, "into": 0, "need": X.level_need(1),
                                             "stats": dict((k, 0) for k in X.STATS), "free": 0, "rest": 0, "runs": 0}

    def rest_left(self, pid):
        """그 포켓몬이 쉬어야 할 남은 초 (받은 뒤 흐른 시간을 뺀다)."""
        rest = int((self.growth.get(str(pid)) or {}).get("rest") or 0)
        return max(0, rest - int(time.monotonic() - self._t0))

    def mon_state(self, mon):
        """'ok' 보낼 수 있다 · 'rest' 쉬는 중 · 'party' 데리고 다니는 중."""
        if mon.get("onDesktop"):
            return "party"
        return "rest" if self.rest_left(mon["id"]) > 0 else "ok"

    def _fill(self, keep=True):
        # 쉬는 시간은 지금 남은 값으로 (받은 뒤 흐른 만큼 뺀다) - 다 쉰 포켓몬이 위로 올라온다
        now = dict((k, dict(g, rest=self.rest_left(k))) for k, g in self.growth.items())
        rows = candidates(self.mons, self.app.dex, self.place, now)
        self._cands = rows
        ids = [m["id"] for m, _p, _g in rows]
        if self.pick not in ids:
            self.pick = ids[0] if ids else None
        ready = sum(1 for m, _p, _g in rows if self.mon_state(m) == "ok")
        resting = sum(1 for m, _p, _g in rows if self.mon_state(m) == "rest")
        note = ("보낼 수 있는 %d마리 · 잘할 차례로" % ready
                + (" · 쉬는 중 %d" % resting if resting else "")) if rows else ""
        empty = None
        if not rows:
            have = any(not m.get("isEgg") for m in self.mons)
            empty = ("박스에 있는 포켓몬만 보낼 수 있습니다.\n포켓몬 탭에서 박스에 넣어 주세요." if have
                     else "보낼 포켓몬이 없습니다.")
        self._paint_pick_list(rows, keep, note, empty)
        self._paint_summary()
        self._arm_rest()

    def _paint_pick_list(self, rows, keep, note, empty):
        """'누구를' 목록 (테마마다 그리는 곳). empty = 비었을 때의 말 (있으면 None)."""
        self.vl.set([("mon", r) for r in rows], keep=keep)
        self.pick_note.configure(text=note)
        if rows:
            self.empty.place_forget()
        else:
            self.empty.configure(text=empty)
            self.empty.place(relx=0.5, rely=0.4, anchor="center")

    def _arm_rest(self):
        """쉬는 포켓몬이 있으면 가끔 다시 칠한다 (남은 시간이 줄고, 다 쉬면 위로 올라온다)."""
        if self._rest_job is not None:
            try:
                self.root.after_cancel(self._rest_job)
            except Exception:                               # noqa: BLE001
                pass
            self._rest_job = None
        left = [self.rest_left(k) for k in self.growth]
        left = [x for x in left if x > 0]
        if left and self.alive:
            # 다음 것이 다 쉴 때, 아니면 1분 뒤 (적힌 '몇 분 뒤' 가 묵지 않게)
            self._rest_job = self.root.after(int(min(min(left) + 1, 60) * 1000), self._rest_tick)

    def _rest_tick(self):
        self._rest_job = None
        if self.alive:
            self._fill(keep=True)

    def pick_mon(self, pid):
        self.pick = pid
        self.vl.refresh()
        self._paint_summary()

    def _picked(self):
        for data in self._cands:
            if data[0]["id"] == self.pick:
                return data
        return None

    def free(self):
        return max(0, X.SLOTS - len((self.state or {}).get("out") or []))

    def _paint_summary(self):
        grow_text, grow_on, text, color, can_send = self._summary_data()
        self._show_summary(grow_text, grow_on, text, color, can_send)

    def _show_summary(self, grow_text, grow_on, text, color, can_send):
        """아래 줄 (테마마다 그리는 곳): 성장 단추 · 요약 글 · 보내기 단추."""
        self.grow_btn.configure(text=grow_text, state="normal" if grow_on else "disabled")
        self.summary.configure(text=text, fg=color)
        self.send_btn.configure(state="normal" if can_send else "disabled")

    def _summary_data(self):
        """(성장 단추 글, 성장을 열 수 있나, 요약 글, 글 색, 보낼 수 있나)."""
        data = self._picked()
        p = X.place(self.place) or {}
        g = self.growth_of(data[0]["id"]) if data is not None else {}
        grow = ("성장 ●" if g.get("free") else "성장", data is not None)
        if self.state is not None and self.free() <= 0:
            return grow + ("탐험 칸이 꽉 찼습니다.\n돌아온 보따리를 받으면 칸이 빕니다.", U.FG_FAINT, False)
        if data is None:
            return grow + ("보낼 포켓몬을 고르세요.", U.FG_FAINT, False)
        mon, _pts, grade = data
        name = (mon.get("info") or {}).get("name") or "?"
        st = self.mon_state(mon)
        if st != "ok":
            why = ("쉬는 중입니다.\n%s 뒤에 다시 나갈 수 있습니다." % X.hours_text(self.rest_left(mon["id"])) if st == "rest"
                   else "데리고 다니는 중입니다.\n박스에 넣으면 보낼 수 있습니다.")
            return grow + ("%s — %s" % (name, why), U.FG_FAINT, False)
        stats = g.get("stats") or {}
        took = X.duration(self.hours, stats.get("speed", 0))
        n = X.item_count(self.hours, grade)
        # 성장치로 붙는 덤은 셋째 줄에 따로 적는다 (없으면 두 줄이다)
        extra = []
        if stats.get("haul"):
            extra.append("물건 하나 더 %d%%" % round(100 * X.haul_chance(stats["haul"])))
        if stats.get("charm"):
            extra.append("포켓몬을 데려올 확률 %d%%" % round(100 * X.charm_chance(stats["charm"])))
        return grow + ("%s Lv.%s → %s · %s\n예상 %s · 물건 %d개%s"
                       % (name, mon.get("level", "?"), p.get("kr", ""), X.time_text(took), X.GRADE_KR.get(grade, ""), n,
                          "\n" + " · ".join(extra) if extra else ""), U.FG, not self.busy)

    def open_grow(self):
        data = self._picked()
        if data is None:
            return
        if self.grow_dialog is not None:
            self.grow_dialog.close()
        self.grow_dialog = GrowDialog(self, data[0])

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
        # 포켓몬마다의 탐험 성장과 쉬는 시간 (받으면 경험치가 오르고 쉬기 시작한다)
        growth = state.get("growth")
        changed = False
        if isinstance(growth, dict):
            changed = growth != self.growth
            self.growth = growth
        # 나가 있는 포켓몬은 '누구를' 목록에서 빠진다 (돌아온 포켓몬은 다시 들어온다)
        away = set(int((o.get("pokemon") or {}).get("id") or 0) for o in state.get("out") or [])
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
            self._arm_rest()             # (남은 초의 기준이 바뀌었다)
        if self._tick_job is None and self.live:
            self._tick_job = self.root.after(1000, self._tick)
        if self.grow_dialog is not None:
            self.grow_dialog.paint()

    def do_send(self):
        data = self._picked()
        if data is None or self.busy or self.free() <= 0 or self.mon_state(data[0]) != "ok":
            return                           # (칸이 꽉 찼거나 쉬는 중이면 단추가 잠겨 있다 - 눌려도 서버에 안 간다)
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
        if self.grow_dialog is not None:
            self.grow_dialog.close()
        for name in ("_tick_job", "_rest_job"):
            job = getattr(self, name)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:                           # noqa: BLE001
                    pass
                setattr(self, name, None)
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass


class GrowDialog(object):
    """탐험 성장치를 찍는 창 (1.10.5). 내용만큼만 크다.

    레벨마다 받은 점수를 다섯 중 원하는 데에 나눠 찍는다. [+] [-] 는 **이 창 안에서만** 움직인다 -
    [찍기] 를 눌러야 서버에 간다 (잘못 눌렀다고 되돌리는 값을 물지 않게). 이미 찍은 점수는 [-] 로
    못 뺀다. 그건 [되돌리기] 다 (돈이 든다, 전부 되돌린다).
    """

    def __init__(self, win, mon):
        from . import ui_box
        self.win = win
        self.app = win.app
        self.root = win.root
        self.mon = mon
        self.pid = mon["id"]
        self.alive = True
        self.busy = False
        self.pending = dict((k, 0) for k in X.STATS)
        self.rows = {}
        self.top, f = ui_box._shell(win.win.winfo_toplevel(), "탐험 성장", GROW_W, U.h(320))
        self.top.protocol("WM_DELETE_WINDOW", self.close)

        head = tk.Frame(f, bg=U.BG)
        head.pack(fill="x")
        name = (mon.get("info") or {}).get("name") or mon.get("species") or "?"
        tk.Label(head, text=("★ " if mon.get("shiny") else "") + name, bg=U.BG, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(16))).pack(side="left")
        self.lv = tk.Label(head, text="", bg=U.ACCENT_SOFT, fg=U.ACCENT_TEXT, font=U.FONT_B, padx=8, pady=2,
                           highlightthickness=1, highlightbackground=U.ACCENT)
        self.lv.pack(side="right")
        bar = tk.Frame(f, bg=U.INK, height=6)
        bar.pack(fill="x", pady=(10, 0))
        self.xp_fill = tk.Frame(bar, bg=U.GOOD)
        self.xp_fill.place(x=0, y=0, relheight=1.0, relwidth=0.0)
        line = tk.Frame(f, bg=U.BG)
        line.pack(fill="x", pady=(5, 0))
        self.xp_note = tk.Label(line, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS)
        self.xp_note.pack(side="left")
        self.free_note = tk.Label(line, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_B)
        self.free_note.pack(side="right")

        box = tk.Frame(f, bg=PANEL, highlightthickness=2, highlightbackground=U.LINE)
        box.pack(fill="x", pady=(12, 0))
        for i, k in enumerate(X.STATS):
            if i:
                tk.Frame(box, bg=U.LINE, height=1).pack(fill="x", padx=12)
            self._stat_row(box, k)

        # 처음부터 창 폭에 맞춰 접는다. 접히기 전의 한 줄 높이로 창을 재면 아래 단추가 눌린다
        # (wrap_to_width 는 창이 뜬 뒤에야 접는다).
        wrap = GROW_W - 2 * 18 - 12
        note = tk.Label(f, text="탐험을 다녀오면 경험치가 쌓이고, 탐험 레벨이 오를 때마다 성장치 1점을 받습니다 "
                                "(Lv.%d 까지). 나가 있는 동안에는 바꿀 수 없습니다." % X.MAX_LEVEL,
                        bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, justify="left", anchor="w", wraplength=wrap)
        note.pack(fill="x", pady=(10, 0))
        U.wrap_to_width(note)
        self.status = tk.Label(f, text=" ", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left",
                               wraplength=wrap)
        self.status.pack(fill="x", pady=(6, 0))
        U.wrap_to_width(self.status)

        foot = tk.Frame(f, bg=U.BG)
        foot.pack(fill="x", pady=(8, 0))
        self.reset_btn = U.ghost_button(foot, "되돌리기 %s원" % format(X.RESET_COST, ","), self.reset, height=34)
        self.reset_btn.pack(side="left")
        self.ok_btn = U.PushButton(foot, "찍기", self.commit, height=34, font=U.FONT_B)
        self.ok_btn.pack(side="right")
        U.ghost_button(foot, "닫기", self.close, height=34).pack(side="right", padx=(0, 6))

        self.paint()
        ui_box.fit(self.top)
        try:
            self.top.grab_set()
        except tk.TclError:
            pass

    def _stat_row(self, box, k):
        row = tk.Frame(box, bg=PANEL)
        row.pack(fill="x", padx=12, pady=7)
        top = tk.Frame(row, bg=PANEL)
        top.pack(fill="x")
        tk.Label(top, text=X.STAT_KR[k], bg=PANEL, fg=U.FG, font=U.FONT_B, bd=0).pack(side="left")
        plus = U.ghost_button(top, "+", lambda s=k: self.bump(s, 1), height=26)
        plus.pack(side="right")
        minus = U.ghost_button(top, "−", lambda s=k: self.bump(s, -1), height=26)
        minus.pack(side="right", padx=(0, 4))
        for b in (plus, minus):
            b.holder.configure(width=U.h(38))        # (단추의 기본 폭 72 는 글자 하나에 너무 넓다)
        num = tk.Label(top, text="", bg=PANEL, fg=U.FG_DIM, font=U.FONT_B, bd=0)
        num.pack(side="right", padx=(0, 10))
        # 열 점을 네모 열 개로 (글자가 아니라 그림이다 - 글꼴에 따라 모양이 달라지지 않는다)
        cv = tk.Canvas(top, width=X.STAT_CAP * (PIP + 3), height=PIP + 2, bg=PANEL, highlightthickness=0, bd=0)
        cv.pack(side="left", padx=(12, 0))
        effect = tk.Label(row, text="", bg=PANEL, fg=U.FG_DIM, font=U.FONT_XS, anchor="w", bd=0)
        effect.pack(fill="x", pady=(4, 0))
        self.rows[k] = (cv, num, effect, minus, plus)

    # ---- 값
    def growth(self):
        return self.win.growth_of(self.pid)

    def left(self):
        """아직 안 넣은 점수 (이 창에서 넣어 둔 것을 뺀다)."""
        return int(self.growth().get("free") or 0) - sum(self.pending.values())

    def bump(self, k, by):
        if self.busy:
            return
        have = int((self.growth().get("stats") or {}).get(k) or 0)
        if by > 0 and (self.left() <= 0 or have + self.pending[k] >= X.STAT_CAP):
            return
        if by < 0 and self.pending[k] <= 0:
            return
        self.pending[k] += by
        self.say("")
        self.paint()

    def say(self, text, color=None):
        try:
            self.status.configure(text=natural(text) if text else " ", fg=color or U.FG_FAINT)
        except tk.TclError:
            return
        self._refit()

    def _refit(self):
        """알림 글이 두 줄로 접히면 그만큼 창을 늘린다 (아래 단추가 눌리지 않게). 자리는 그대로."""
        from . import ui_box
        if self.alive and self.top.winfo_ismapped():
            ui_box.fit(self.top, keep_pos=True)

    def paint(self):
        if not self.alive:
            return
        g = self.growth()
        stats = g.get("stats") or {}
        free = int(g.get("free") or 0)
        # 서버의 값이 바뀌어(되돌리기·다른 창) 넣어 둔 것이 남은 점수를 넘으면 버린다
        if sum(self.pending.values()) > free:
            self.pending = dict((k, 0) for k in X.STATS)
        left = self.left()
        away = bool(self.mon.get("away"))
        try:
            self.lv.configure(text="탐험 Lv.%d" % int(g.get("level") or 0))
            need = g.get("need")
            if need:
                self.xp_fill.place_configure(relwidth=max(0.0, min(1.0, int(g.get("into") or 0) / float(need))))
                self.xp_note.configure(text="다음 레벨까지 %d / %d" % (int(g.get("into") or 0), need))
            else:
                self.xp_fill.place_configure(relwidth=1.0)
                self.xp_note.configure(text="가장 높은 레벨입니다")
            self.free_note.configure(text="남은 성장치 %d점" % left, fg=U.ACCENT_TEXT if left > 0 else U.FG_DIM)
            for k, (cv, num, effect, minus, plus) in self.rows.items():
                have, add = int(stats.get(k) or 0), self.pending[k]
                cv.delete("all")
                for i in range(X.STAT_CAP):
                    x = i * (PIP + 3) + 1
                    fill = U.ACCENT if i < have else (U.ACCENT_TEXT if i < have + add else U.INK)
                    cv.create_rectangle(x, 1, x + PIP, 1 + PIP, fill=fill,
                                        outline=U.ACCENT if i < have + add else U.LINE2)
                num.configure(text="%d" % have + (" +%d" % add if add else ""),
                              fg=U.ACCENT_TEXT if add else (U.FG if have else U.FG_DIM))
                effect.configure(text="%s  ·  %s" % (X.stat_text(k, have + add), X.STAT_HINT[k]) if have + add
                                 else X.STAT_HINT[k], fg=U.ACCENT_TEXT if add else U.FG_DIM)
                minus.configure(state="normal" if add > 0 and not self.busy else "disabled")
                plus.configure(state="normal" if left > 0 and have + add < X.STAT_CAP and not self.busy and not away
                               else "disabled")
            self.ok_btn.configure(state="normal" if sum(self.pending.values()) > 0 and not self.busy else "disabled")
            self.reset_btn.configure(state="normal" if X.spent(stats) > 0 and not self.busy and not away else "disabled")
        except tk.TclError:
            pass

    # ---- 서버
    def commit(self):
        add = dict((k, v) for k, v in self.pending.items() if v > 0)
        if not add or self.busy:
            return
        self._send(lambda: self.app.api.expedition_grow(self.pid, add), "성장치를 찍었습니다.")

    def reset(self):
        from . import ui_box
        n = X.spent(self.growth().get("stats") or {})
        if n <= 0 or self.busy:
            return
        if not ui_box.confirm(self.top, "성장치 되돌리기",
                              "찍은 성장치 %d점을 전부 되돌릴까요? %s원이 듭니다. (탐험 레벨은 그대로입니다)"
                              % (n, format(X.RESET_COST, ",")), danger=False, ok_text="되돌리기"):
            return
        self._send(lambda: self.app.api.expedition_reset(self.pid), "성장치를 되돌렸습니다.", money=True)

    def _send(self, call, fallback, money=False):
        self.busy = True
        self.paint()

        def done(r, err):
            self.busy = False
            if not self.alive:
                return
            if err:
                self.say(_err(err), U.RED)
                return self.paint()
            self.pending = dict((k, 0) for k in X.STATS)
            if money and isinstance(r, dict) and "money" in r:
                self.app.money = r["money"]
                try:
                    self.app.request_sync()          # 돈이 바뀌었다 - 상점·마이페이지가 새 값을 보게 한다
                except Exception:                               # noqa: BLE001
                    pass
            self.win.apply(r)                        # (목록의 '탐험 Lv' 와 이 창을 같이 다시 칠한다)
            self.say(r.get("message") or fallback, U.GOOD)
            self.paint()
        run_async(self.root, call, done)

    def close(self):
        if not self.alive:
            return
        self.alive = False
        if self.win.grow_dialog is self:
            self.win.grow_dialog = None
        try:
            self.top.grab_release()
        except tk.TclError:
            pass
        try:
            self.top.destroy()
        except tk.TclError:
            pass
