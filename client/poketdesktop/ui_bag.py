# -*- coding: utf-8 -*-
"""가방 창 — 가진 도구를 보고 포켓몬에게 쓴다.

왜 이렇게 만들었는지.

* 도구 목록만 보여주면 "이걸 누구한테 쓰지?" 에서 막힌다. 그래서 도구를
  고르는 순간 오른쪽에 **쓸 대상 목록**이 같이 뜬다. 창을 두 번 열 일이 없다.
* 진화의 돌만 38종이라 대부분은 지금 가진 포켓몬과 상관이 없다. 최종 판단은
  서버가 하지만(낮/밤 같은 조건이 있다), 화면에서도 도구의 evolves(한국어 종
  이름)와 포켓몬의 info.species 를 맞춰보고 **될 만한 대상을 밝게** 칠한다.
  아무 일도 안 일어나는 클릭을 줄이려는 것이다.
* 은색병뚜껑은 능력을 하나 골라야 한다. 그래서 대상을 고른 뒤에 능력 칸이
  열리고, 이미 31 이거나 이미 단련된 능력은 아예 눌리지 않는다. 서버도 같은
  것을 막지만, 눌러보고 거절당하는 것보다 미리 못 누르게 하는 편이 낫다.
* 목록에 놓는 도트는 **작업 스레드에서 그림까지 다 만들어 둔다.** 도트 한 장을
  만드는 데 픽셀을 파이썬으로 훑기 때문에(sprites.flatten_rgba) 마릿수만큼
  tk 스레드에서 돌리면 창이 눈에 띄게 멈춘다. tk 스레드에서는 PhotoImage 로
  감싸는 일만 한다.
* 휠은 창(Toplevel)에만 묶는다. ui_box 처럼 bind_all 로 묶으면 목록이 둘인
  이 창에서 어느 쪽을 굴릴지 알 수 없고, 열려 있는 다른 창의 휠까지 뺏는다.
"""
import datetime
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from common import pokelogic as P
from common.korean import natural

from . import sprite_cache, sprites
from . import ui_box
from . import item_icons
from . import ui_common as U

LIST_W = 292            # 왼쪽 도구 목록 폭
ITEM_H = 28             # 도구 한 줄 높이
MON_H = 34              # 포켓몬 한 줄 높이
THUMB = 22              # 목록에 놓는 도트 높이 (다른 창과 겹치지 않는 값)

EV_STAT_MAX = 252       # 서버 config 와 같은 값 (스탯 하나당)
EV_TOTAL_MAX = 510      # 서버 config 와 같은 값 (여섯 개 합계)
HYPER_MIN_LEVEL = 50    # 병뚜껑을 받을 수 있는 최소 레벨

STAT_ROWS = [("hp", "HP"), ("atk", "공격"), ("def", "방어"),
             ("spa", "특수공격"), ("spd", "특수방어"), ("spe", "스피드")]
STAT_KR = dict(STAT_ROWS)

# 분류 — 실제로 쓸 수 있는 것부터 위로 올린다
CAT_ORDER = ["stone", "ev", "iv", "misc", "heal", "ball"]
CAT_KR = {"stone": "진화의 돌", "ev": "노력치", "iv": "단련",
          "misc": "기타", "heal": "회복약", "ball": "볼"}
CAT_COLOR = {"stone": U.PINK, "ev": U.GOOD, "iv": U.SHINY,
             "misc": U.INFO, "heal": "#7fd4c1", "ball": U.RED}

# /api/bag/use 가 받아주는 효과. 나머지(볼, 파는 물건)는 여기서 쓸 수 없다.
USABLE = ("ev", "iv", "level", "stone", "noevolve")

ROW_BG = "#10131c"      # 목록 한 줄 바탕
SEL_BG = "#2b2417"      # 고른 줄
GOOD_BG = "#14211a"     # 진화의 돌이 통하는 줄
PANEL = "#101623"       # 액자 안쪽


# ---------------------------------------------------------------- 서버 호출
def _takes(fn, name):
    try:
        import inspect
        return name in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def fetch_shop(api):
    """도구 설명 · 가방 · 지갑을 한 번에 받는다.

    /api/bag 은 개수만 주고 이름도 효과도 없다. 화면에는 설명이 필요하므로
    도구 명세가 같이 오는 /api/shop 을 쓴다.
    """
    fn = getattr(api, "shop", None)
    if fn is not None:
        return fn()
    return api._call("GET", "/api/shop")


def use_item(api, item_id, pid, stat, hour):
    """도구를 쓴다. 시각(hour)은 **이 PC 기준**으로 반드시 같이 보낸다.

    서버는 도커 안에서 UTC 로 돌기 때문에 사용자의 밤낮을 스스로 알 수 없다.
    (이브이의 밤 진화처럼 시각을 보는 조건이 있다.)
    """
    fn = getattr(api, "use_item", None)
    if fn is not None and _takes(fn, "hour"):
        return fn(item_id, pid, stat or "", hour=hour)
    return api._call("POST", "/api/bag/use",
                     {"item": item_id, "pokemon": pid, "stat": stat or "",
                      "hour": hour})


# ---------------------------------------------------------------- 설명 만들기
def item_desc(item):
    """도구 설명 한 줄. items.json 에 설명 문구가 없어서 effect 로 만든다."""
    eff = item.get("effect") or {}
    kind = eff.get("kind")
    if kind == "ev":
        stat = STAT_KR.get(eff.get("stat"), "?")
        n = int(eff.get("amount", 0))
        if n >= 0:
            return ("%s 노력치가 %d 오른다. 스탯 하나당 %d, 여섯 개 합쳐 %d 까지."
                    % (stat, n, EV_STAT_MAX, EV_TOTAL_MAX))
        return "%s 노력치가 %d 내려간다." % (stat, abs(n))
    if kind == "iv":
        if int(eff.get("count", 1)) >= 6:
            return ("여섯 능력을 한꺼번에 최고까지 단련한다. Lv.%d 부터 받을 수 있다."
                    % HYPER_MIN_LEVEL)
        return ("고른 능력 하나를 최고(%d)까지 단련한다. Lv.%d 부터 받을 수 있다."
                % (P.IV_MAX, HYPER_MIN_LEVEL))
    if kind == "level":
        return ("레벨이 %d 오른다. 조건이 맞으면 그 자리에서 진화한다."
                % int(eff.get("amount", 1)))
    if kind == "stone":
        who = item.get("evolves") or []
        if not who:
            return "특정 포켓몬을 진화시키는 돌이다."
        if len(who) > 6:
            return "%s 외 %d종이(가) 진화한다." % (", ".join(who[:6]), len(who) - 6)
        return "%s이(가) 진화한다." % ", ".join(who)
    if kind == "noevolve":
        return "진화를 막는다. 한 번 더 쓰면 다시 진화할 수 있게 된다."
    if kind == "ball":
        return "야생 포켓몬을 만났을 때 던지는 볼이다. 가방에서는 쓸 수 없다."
    if kind == "sell":
        return "쓸 데는 없지만 상점에 팔면 값을 쳐준다."
    return "아직 쓸 수 없는 도구다."


def target_hint(item):
    """대상 목록 위에 붙일 한 줄 안내."""
    kind = (item.get("effect") or {}).get("kind")
    if kind == "stone":
        return "이 돌이 통하는 포켓몬을 밝게 표시했다"
    if kind == "iv":
        return "Lv.%d 부터 단련할 수 있다" % HYPER_MIN_LEVEL
    if kind == "ev":
        return "스탯당 %d · 합계 %d 까지" % (EV_STAT_MAX, EV_TOTAL_MAX)
    if kind == "level":
        return "레벨이 오르면서 기술도 배운다"
    if kind == "noevolve":
        return "한 마리씩 껐다 켰다 한다"
    return ""


def unusable_note(item):
    """여기서는 못 쓰는 도구에게 해줄 말."""
    eff = item.get("effect") or {}
    if eff.get("kind") == "ball":
        return "볼은 야생 포켓몬을 만났을 때 던진다.\n가방에서는 쓸 수 없다."
    if eff.get("kind") == "sell":
        return ("포켓몬에게 쓸 수 있는 도구가 아니다.\n"
                "상점에 팔면 한 개에 %d원을 받는다." % int(item.get("sell", 0)))
    return "이 도구는 아직 쓸 수 없다."


# ---------------------------------------------------------------- 조각 위젯
def _scroller(parent, bg):
    """세로로 굴러가는 빈 영역을 만든다. (canvas, inner) 를 돌려준다."""
    holder = tk.Frame(parent, bg=bg)
    holder.pack(fill="both", expand=True)
    cv = tk.Canvas(holder, bg=bg, highlightthickness=0, bd=0)
    sb = ttk.Scrollbar(holder, orient="vertical", command=cv.yview)
    cv.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    cv.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(cv, bg=bg)
    wid = cv.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>",
               lambda e: cv.configure(scrollregion=cv.bbox("all")))
    cv.bind("<Configure>", lambda e: cv.itemconfigure(wid, width=e.width))
    return cv, inner


class ItemRow(object):
    """왼쪽 도구 목록 한 줄 — 분류 색점 · 이름 · 개수."""

    def __init__(self, parent, item, count, on_pick):
        self.item = item
        self.on_pick = on_pick
        self.selected = False
        self.usable = (item.get("effect") or {}).get("kind") in USABLE

        self.f = tk.Frame(parent, bg=ROW_BG, height=ITEM_H, cursor="hand2")
        self.f.pack_propagate(False)
        self.mark = tk.Frame(self.f, bg=ROW_BG, width=3)
        self.mark.place(x=0, y=0, relheight=1.0)
        # 도구 그림. 아직 못 받았으면 분류 색점으로 대신한다.
        ph = item_icons.photo(item["id"], 20)
        if ph is not None:
            self.dot = tk.Label(self.f, image=ph, bg=ROW_BG, bd=0)
            self.dot.image = ph
            self.dot.place(x=8, rely=0.5, anchor="w")
        else:
            self.dot = tk.Frame(self.f, bg=CAT_COLOR.get(item.get("cat"), U.BG3),
                                width=5, height=5)
            self.dot.place(x=13, rely=0.5, anchor="w")
        self.name = tk.Label(self.f, text=item["kr"], bg=ROW_BG,
                             fg=U.FG if self.usable else U.FG_FAINT,
                             font=U.FONT_S, anchor="w")
        self.name.place(x=32, rely=0.5, anchor="w")
        self.count = tk.Label(self.f, text="%d개" % count, bg=ROW_BG,
                              fg=U.FG_DIM if self.usable else U.FG_FAINT,
                              font=U.FONT_XS, anchor="e")
        self.count.place(relx=1.0, x=-12, rely=0.5, anchor="e")

        self.cells = [self.name, self.count, self.dot]
        for w in [self.f] + self.cells:
            w.bind("<Button-1>", lambda e: self.on_pick(self.item["id"]))
            w.bind("<Enter>", self._in)
            w.bind("<Leave>", self._out)

    def pack(self, **kw):
        self.f.pack(fill="x", **kw)
        return self

    def _paint(self, bg, mark):
        self.f.configure(bg=bg)
        self.mark.configure(bg=mark)
        for w in (self.name, self.count):
            w.configure(bg=bg)

    def _in(self, _e):
        if not self.selected:
            self._paint(U.BG2, U.LINE)

    def _out(self, _e):
        if not self.selected:
            self._paint(ROW_BG, ROW_BG)

    def set_selected(self, on):
        self.selected = on
        if on:
            self._paint(SEL_BG, U.ACCENT)
            self.name.configure(fg=U.ACCENT_TEXT, font=U.FONT_B)
        else:
            self._paint(ROW_BG, ROW_BG)
            self.name.configure(fg=U.FG if self.usable else U.FG_FAINT,
                                font=U.FONT_S)


class MonRow(object):
    """'누구에게 쓸까?' 목록 한 줄 — 왼쪽에 **실제 도트**를 작게 놓는다.

    도트 자리는 그림이 오기 전에도 폭이 흔들리지 않게 고정 크기 액자에 넣는다.
    """

    def __init__(self, parent, mon, on_pick):
        self.mon = mon
        self.on_pick = on_pick
        self.selected = False
        self.good = False
        self.blocked = False
        self.note_text = ""
        self.photo = None
        info = mon.get("info") or {}

        self.f = tk.Frame(parent, bg=ROW_BG, height=MON_H, cursor="hand2")
        self.f.pack_propagate(False)
        self.mark = tk.Frame(self.f, bg=ROW_BG, width=3)
        self.mark.place(x=0, y=0, relheight=1.0)

        self.frame_art = tk.Frame(self.f, bg=ROW_BG, width=30, height=MON_H)
        self.frame_art.pack_propagate(False)
        self.frame_art.pack(side="left", padx=(9, 0))
        self.art = tk.Label(self.frame_art, bg=ROW_BG)
        self.art.pack(expand=True)

        name = info.get("name", mon.get("species", "?"))
        if mon.get("shiny"):
            name = "★ " + name
        self.name = tk.Label(self.f, text=name, bg=ROW_BG,
                             fg=U.SHINY if mon.get("shiny") else U.FG,
                             font=U.FONT_S, anchor="w", width=13)
        self.name.pack(side="left", padx=(7, 0))
        self.lv = tk.Label(self.f, text="Lv.%d" % mon.get("level", 0), bg=ROW_BG,
                           fg=U.FG_DIM, font=U.FONT_XS, anchor="w", width=6)
        self.lv.pack(side="left")
        sub = info.get("species", "") if info.get("name") != info.get("species") else ""
        if mon.get("onDesktop"):
            sub = (sub + " · 따라다님").strip(" ·")
        self.sub = tk.Label(self.f, text=sub, bg=ROW_BG, fg=U.FG_FAINT,
                            font=U.FONT_XS, anchor="w")
        self.sub.pack(side="left", padx=(4, 0))
        self.note = tk.Label(self.f, text="", bg=ROW_BG, fg=U.FG_FAINT,
                             font=U.FONT_XS, anchor="e")
        self.note.pack(side="right", padx=(6, 12))

        self.cells = [self.frame_art, self.art, self.name, self.lv, self.sub,
                      self.note]
        for w in [self.f] + self.cells:
            w.bind("<Button-1>", lambda e: self.on_pick(self.mon["id"]))
            w.bind("<Enter>", self._in)
            w.bind("<Leave>", self._out)

    def pack(self, **kw):
        self.f.pack(fill="x", **kw)
        return self

    def set_photo(self, photo):
        """도트를 올린다. 참조를 들고 있지 않으면 그림이 사라진다."""
        self.photo = photo
        try:
            self.art.configure(image=photo)
        except tk.TclError:
            pass

    def set_state(self, good, blocked, note, color):
        self.good = good
        self.blocked = blocked
        self.note_text = note
        self.note.configure(text=note, fg=color)
        self.f.configure(cursor="" if blocked else "hand2")
        self.repaint()

    def _bg(self):
        if self.selected:
            return SEL_BG, U.ACCENT
        if self.good:
            return GOOD_BG, U.GOOD
        return ROW_BG, ROW_BG

    def repaint(self):
        bg, mark = self._bg()
        self.f.configure(bg=bg)
        self.mark.configure(bg=mark)
        for w in self.cells:
            try:
                w.configure(bg=bg)
            except tk.TclError:
                pass
        if self.blocked:
            fg = U.FG_FAINT
        elif self.selected:
            fg = U.ACCENT_TEXT
        elif self.mon.get("shiny"):
            fg = U.SHINY
        else:
            fg = U.FG
        self.name.configure(fg=fg, font=U.FONT_B if self.selected else U.FONT_S)

    def _in(self, _e):
        if not self.selected:
            bg = U.BG2 if not self.good else "#1b2b21"
            self.f.configure(bg=bg)
            for w in self.cells:
                try:
                    w.configure(bg=bg)
                except tk.TclError:
                    pass

    def _out(self, _e):
        if not self.selected:
            self.repaint()

    def set_selected(self, on):
        self.selected = on
        self.repaint()


# ---------------------------------------------------------------- 가방 창
class BagWindow(object):
    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.alive = True

        self.items = []          # /api/shop 이 준 도구 명세
        self.bag = {}            # {도구ID: 개수}
        self.money = 0
        self.mons = []
        self.photos = {}         # {포켓몬id: PhotoImage} — 한 번 만들면 계속 쓴다
        self.item_rows = {}
        self.mon_rows = {}
        self.item_id = None
        self.mon_id = None
        self.stat = None         # 병뚜껑으로 단련할 능력
        self.stat_needed = False
        self._pending = None     # 다시 불러온 뒤에 띄울 말

        self.win = tk.Toplevel(root)
        U.style_window(self.win, "포켓 데스크톱 — 가방", 1000, 664)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        self.win.minsize(950, 600)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self._header()
        self._bottom()
        body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True)
        self._items_pane(body)
        self._detail_pane(body)

        self.win.bind("<MouseWheel>", self._wheel)
        self.reload()

    # ---------------- 머리 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=62)
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)

        # 가방 아이콘 — 몬스터볼 대신 여기서만 쓰는 그림이라 직접 그린다
        cv = tk.Canvas(inner, width=28, height=28, bg=U.BG2,
                       highlightthickness=0, bd=0)
        cv.pack(side="left", pady=17)
        cv.create_arc(9, 2, 19, 14, start=0, extent=180, style="arc",
                      outline=U.INK, width=3)
        cv.create_rectangle(3, 9, 25, 25, fill=U.ACCENT, outline=U.INK, width=2)
        cv.create_rectangle(3, 14, 25, 18, fill=U.RED, outline="")
        cv.create_rectangle(11, 13, 17, 19, fill="#f4f6fb", outline=U.INK,
                            width=1)

        tk.Label(inner, text="가방", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, 15)).pack(side="left", padx=(12, 12))
        self.count_label = tk.Label(inner, text="", bg=U.BG2, fg=U.FG_FAINT,
                                    font=U.FONT_S)
        self.count_label.pack(side="left")

        U.ghost_button(inner, "새로고침", self.reload,
                       height=32).pack(side="right", pady=15)
        purse = tk.Frame(inner, bg=U.INK, highlightthickness=2,
                         highlightbackground=U.LINE)
        purse.pack(side="right", padx=(0, 10), pady=17)
        tk.Label(purse, text="소지금", bg=U.INK, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="left", padx=(10, 6), pady=4)
        self.money_label = tk.Label(purse, text="0원", bg=U.INK, fg=U.ACCENT,
                                    font=U.FONT_B)
        self.money_label.pack(side="left", padx=(0, 10))
        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x")

    # ---------------- 왼쪽: 가진 도구 ----------------
    def _items_pane(self, parent):
        wrap = tk.Frame(parent, bg=U.BG, width=LIST_W)
        wrap.pack(side="left", fill="y")
        wrap.pack_propagate(False)

        head = tk.Frame(wrap, bg=U.INK, height=26)
        head.pack(fill="x")
        head.pack_propagate(False)
        U.marker_label(head, "가진 도구", bg=U.INK).pack(side="left", padx=12,
                                                     pady=6)
        tk.Frame(wrap, bg=U.LINE, height=2).pack(fill="x")
        self.item_canvas, self.item_inner = _scroller(wrap, U.BG)

    # ---------------- 오른쪽: 설명과 대상 ----------------
    def _detail_pane(self, parent):
        d = tk.Frame(parent, bg=U.BG2)
        d.pack(side="right", fill="both", expand=True)
        tk.Frame(d, bg=U.LINE2, width=2).place(x=0, y=0, relheight=1.0)
        p = tk.Frame(d, bg=U.BG2)
        p.pack(fill="both", expand=True, padx=(18, 16), pady=13)

        head = tk.Frame(p, bg=U.BG2)
        head.pack(fill="x")
        self.i_name = tk.Label(head, text="도구를 고르세요", bg=U.BG2,
                               fg=U.ACCENT_TEXT, font=(U.FAMILY_BLACK, 16))
        self.i_name.pack(side="left")
        self.i_cat = U.chip(head, "", U.BG3, fg=U.FG_DIM)
        self.i_cat.pack(side="left", padx=(10, 0), pady=5)
        self.i_count = tk.Label(head, text="", bg=U.BG3, fg=U.FG, font=U.FONT_B,
                                padx=9, pady=2, highlightthickness=2,
                                highlightbackground=U.LINE2)
        self.i_count.pack(side="right")

        self.i_desc = tk.Label(p, text="왼쪽에서 도구를 고르면 여기에 설명이 뜬다.",
                               bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                               justify="left", wraplength=580)
        self.i_desc.pack(fill="x", pady=(7, 0))

        self._stat_box(p)

        # 대상 목록
        lhead = tk.Frame(p, bg=U.BG2)
        lhead.pack(fill="x", pady=(12, 5))
        U.marker_label(lhead, "누구에게 쓸까?", bg=U.BG2).pack(side="left")
        self.t_hint = tk.Label(lhead, text="", bg=U.BG2, fg=U.FG_FAINT,
                               font=U.FONT_XS)
        self.t_hint.pack(side="right")

        frame = U.framed(p, bg=ROW_BG, border=U.LINE)
        frame.pack(fill="both", expand=True)
        self.mon_canvas, self.mon_inner = _scroller(frame, ROW_BG)
        self.mon_list = tk.Frame(self.mon_inner, bg=ROW_BG)
        self.mon_list.pack(fill="both", expand=True)
        self.mon_note = tk.Label(self.mon_inner, text="", bg=ROW_BG,
                                 fg=U.FG_FAINT, font=U.FONT_S, justify="center",
                                 pady=34)

        self._ev_box(p)

    def _stat_box(self, parent):
        """은색병뚜껑 전용 — 어느 능력을 단련할지 고르는 칸."""
        self.statbox = tk.Frame(parent, bg=PANEL, highlightthickness=2,
                                highlightbackground=U.LINE)
        top = tk.Frame(self.statbox, bg=PANEL)
        top.pack(fill="x", padx=11, pady=(9, 4))
        U.marker_label(top, "어느 능력을 단련할까?", bg=PANEL).pack(side="left")
        self.stat_hint = tk.Label(top, text="", bg=PANEL, fg=U.FG_FAINT,
                                  font=U.FONT_XS)
        self.stat_hint.pack(side="right")
        row = tk.Frame(self.statbox, bg=PANEL)
        row.pack(fill="x", padx=11, pady=(0, 10))
        self.stat_chips = {}
        for key, label in STAT_ROWS:
            lb = tk.Label(row, text=label, bg=U.BG3, fg=U.FG_DIM, font=U.FONT_XS,
                          padx=8, pady=5, highlightthickness=2,
                          highlightbackground=U.LINE)
            lb.pack(side="left", padx=(0, 5))
            lb.bind("<Button-1>", lambda e, k=key: self.pick_stat(k))
            self.stat_chips[key] = lb

    def _ev_box(self, parent):
        """노력치 도구 전용 — 고른 포켓몬의 지금 노력치를 막대로 보여준다."""
        self.evbox = tk.Frame(parent, bg=PANEL, highlightthickness=2,
                              highlightbackground=U.LINE)
        top = tk.Frame(self.evbox, bg=PANEL)
        top.pack(fill="x", padx=11, pady=(9, 5))
        U.marker_label(top, "지금 노력치", bg=PANEL).pack(side="left")
        self.ev_total = tk.Label(top, text="", bg=PANEL, fg=U.FG_DIM,
                                 font=U.FONT_XS)
        self.ev_total.pack(side="right")
        grid = tk.Frame(self.evbox, bg=PANEL)
        grid.pack(fill="x", padx=11, pady=(0, 10))
        self.ev_bars = {}
        for i, (key, label) in enumerate(STAT_ROWS):
            r, c = i % 3, i // 3
            cell = tk.Frame(grid, bg=PANEL)
            cell.grid(row=r, column=c, sticky="w", padx=(0, 18), pady=1)
            name = tk.Label(cell, text=label, bg=PANEL, fg=U.FG_DIM,
                            font=U.FONT_XS, anchor="w", width=7)
            name.pack(side="left")
            cv = tk.Canvas(cell, width=118, height=7, bg="#232b3d",
                           highlightthickness=0, bd=0)
            cv.pack(side="left", padx=(2, 7))
            val = tk.Label(cell, text="0", bg=PANEL, fg=U.FG, font=U.FONT_XS,
                           anchor="e", width=4)
            val.pack(side="left")
            self.ev_bars[key] = (name, cv, val)

    # ---------------- 바닥 ----------------
    def _bottom(self):
        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x", side="bottom")
        bar = tk.Frame(self.win, bg=U.INK, height=58)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        inner = tk.Frame(bar, bg=U.INK)
        inner.pack(fill="both", expand=True, padx=16)

        self.use_btn = U.PushButton(inner, "쓰기", self.do_use, height=34)
        self.use_btn.pack(side="right", pady=11)
        self.use_btn.configure(state="disabled")
        U.ghost_button(inner, "닫기", self.close,
                       height=34).pack(side="right", padx=(0, 8), pady=11)
        self.status = U.status_line(inner, "", bg=U.INK)
        self.status.pack(side="left", fill="x", expand=True, pady=11)

    # ---------------- 거들기 ----------------
    def say(self, text, color=U.GOOD, fg=None):
        try:
            U.set_status(self.status, natural(text or ""), color, fg)
        except tk.TclError:
            pass

    def _wheel(self, e):
        """포인터가 올라가 있는 목록만 굴린다. (목록이 둘이다)"""
        try:
            w = self.win.winfo_containing(e.x_root, e.y_root)
        except tk.TclError:
            return
        while w is not None:
            if w is self.item_canvas or w is self.mon_canvas:
                w.yview_scroll(int(-e.delta / 60), "units")
                return
            w = w.master

    def current_item(self):
        return next((i for i in self.items if i["id"] == self.item_id), None)

    def current_mon(self):
        return next((m for m in self.mons if m["id"] == self.mon_id), None)

    # ---------------- 데이터 ----------------
    def reload(self):
        if not self.app.api:
            return self.say("로그인이 필요합니다.", U.DANGER, U.DANGER)
        if not self._pending:
            self.say("가방을 여는 중...", U.FG_FAINT)
        api = self.app.api

        def work():
            shop = fetch_shop(api)
            mons = api.pokemon()
            # 도트는 여기서 그림까지 다 만들어 둔다. tk 스레드에서 만들면
            # 마릿수만큼 창이 멈춘다. PhotoImage 만 tk 쪽에서 씌운다.
            thumbs = {}
            for m in mons:
                path = sprite_cache.ensure(api, m.get("num"), m.get("shiny"))
                if not path:
                    continue
                try:
                    anim = sprites.load_animation(path, target_height=THUMB,
                                                  min_scale=0.2, max_scale=3.0,
                                                  max_frames=1)
                    thumbs[m["id"]] = sprites.to_rgba(
                        anim.frames[sprites.RIGHT][0], anim.key)
                except Exception:                       # noqa: BLE001
                    pass
            # 도구 그림도 같이 받아 둔다 (가진 것만)
            try:
                bag = (shop or {}).get("bag") or {}
                item_icons.prefetch(api, list(bag))
            except Exception:                           # noqa: BLE001
                pass
            return shop, mons, thumbs
        U.run_async(self.root, work, self._loaded)

    def _loaded(self, r, err):
        if not self.alive:
            return
        if err:
            return self.say(getattr(err, "message", str(err)), U.DANGER,
                            U.DANGER)
        shop, mons, thumbs = r
        self.items = shop.get("items") or []
        self.bag = shop.get("bag") or {}
        self.money = int(shop.get("money") or 0)
        self.mons = mons or []
        self.photos = {}
        for pid, img in thumbs.items():
            try:
                self.photos[pid] = ImageTk.PhotoImage(img)
            except Exception:                           # noqa: BLE001
                pass

        self.money_label.configure(text="{:,}원".format(self.money))
        kinds = sum(1 for v in self.bag.values() if v > 0)
        total = sum(v for v in self.bag.values() if v > 0)
        self.count_label.configure(text="%d종 · 모두 %d개" % (kinds, total))

        self._fill_items()
        self._fill_mons()

        keep_item = self.item_id
        self.item_id = None
        if keep_item and self.bag.get(keep_item, 0) > 0:
            self.pick_item(keep_item)
        else:
            self.pick_item(self._first_item())

        if self._pending:
            text, color = self._pending
            self._pending = None
            self.say(text, color)
        else:
            self.say("")

    def _first_item(self):
        """처음에 골라 둘 도구 — 쓸 수 있는 것 중 맨 위."""
        rows = self._owned()
        for it in rows:
            if (it.get("effect") or {}).get("kind") in USABLE:
                return it["id"]
        return rows[0]["id"] if rows else None

    def _owned(self):
        """가진 도구만 분류 순서대로."""
        owned = [i for i in self.items if self.bag.get(i["id"], 0) > 0]
        owned.sort(key=lambda i: (CAT_ORDER.index(i["cat"])
                                  if i["cat"] in CAT_ORDER else 99,
                                  i["kr"]))
        return owned

    def _fill_items(self):
        for w in self.item_inner.winfo_children():
            w.destroy()
        self.item_rows = {}
        owned = self._owned()
        if not owned:
            tk.Label(self.item_inner, text="가방이 비어 있다.", bg=U.BG,
                     fg=U.FG_DIM, font=U.FONT_S).pack(pady=(34, 4))
            tk.Label(self.item_inner,
                     text="야생 포켓몬을 잡거나 배틀에서\n도구를 주울 수 있다.",
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS,
                     justify="center").pack()
            return
        cat = None
        for it in owned:
            if it["cat"] != cat:
                cat = it["cat"]
                n = sum(1 for x in owned if x["cat"] == cat)
                strip = tk.Frame(self.item_inner, bg=U.INK, height=26)
                strip.pack(fill="x")
                strip.pack_propagate(False)
                U.marker_label(strip, "%s · %d종" % (CAT_KR.get(cat, cat), n),
                               bg=U.INK,
                               mark=CAT_COLOR.get(cat, U.ACCENT)).pack(
                    side="left", padx=12, pady=6)
                tk.Frame(self.item_inner, bg=U.LINE, height=1).pack(fill="x")
            self.item_rows[it["id"]] = ItemRow(self.item_inner, it,
                                               self.bag.get(it["id"], 0),
                                               self.pick_item).pack()
            tk.Frame(self.item_inner, bg="#161a24", height=1).pack(fill="x")

    def _fill_mons(self):
        for w in self.mon_list.winfo_children():
            w.destroy()
        self.mon_rows = {}
        for m in self.mons:
            row = MonRow(self.mon_list, m, self.pick_mon).pack()
            ph = self.photos.get(m["id"])
            if ph:
                row.set_photo(ph)
            self.mon_rows[m["id"]] = row
            tk.Frame(self.mon_list, bg="#161a24", height=1).pack(fill="x")
        if not self.mons:
            tk.Label(self.mon_list, text="가진 포켓몬이 없다.", bg=ROW_BG,
                     fg=U.FG_FAINT, font=U.FONT_S, pady=30).pack()

    # ---------------- 고르기 ----------------
    def pick_item(self, item_id):
        self.item_id = item_id
        self.stat = None
        for i, r in self.item_rows.items():
            r.set_selected(i == item_id)
        it = self.current_item()
        if not it:
            self.stat_needed = False
            self.i_name.configure(text="도구를 고르세요")
            self.i_cat.configure(text="", bg=U.BG2)
            self.i_count.configure(text="")
            self.i_desc.configure(text="왼쪽에서 도구를 고르면 여기에 설명이 뜬다.")
            self.t_hint.configure(text="")
            self.statbox.pack_forget()
            self.evbox.pack_forget()
            self._show_targets(None)
            return self._refresh_button()

        eff = it.get("effect") or {}
        kind = eff.get("kind")
        self.i_name.configure(text=it["kr"])
        self.i_cat.configure(text=CAT_KR.get(it["cat"], it["cat"]),
                             bg=CAT_COLOR.get(it["cat"], U.BG3), fg="#14141a")
        self.i_count.configure(text="%d개" % self.bag.get(it["id"], 0))
        self.i_desc.configure(text=natural(item_desc(it)))
        self.t_hint.configure(text=target_hint(it))

        # 병뚜껑처럼 능력을 골라야 하는 것만 능력 칸을 연다.
        # 금색병뚜껑(count 6)은 서버가 알아서 여섯 개를 다 단련한다.
        self.stat_needed = (kind == "iv" and int(eff.get("count", 1)) < 6)
        if self.stat_needed:
            self.statbox.pack(fill="x", pady=(11, 0), after=self.i_desc)
        else:
            self.statbox.pack_forget()
        if kind == "ev":
            self.evbox.pack(fill="x", pady=(11, 0))
        else:
            self.evbox.pack_forget()

        self._show_targets(it)
        self._refresh_stats()
        self._refresh_evs()
        self._refresh_button()

    def _show_targets(self, it):
        """도구에 맞춰 대상 목록을 칠하거나, 못 쓰는 도구면 안내로 바꾼다."""
        usable = bool(it) and (it.get("effect") or {}).get("kind") in USABLE
        if not usable:
            self.mon_list.pack_forget()
            self.mon_note.configure(
                text=natural(unusable_note(it)) if it else
                "도구를 고르면 쓸 수 있는 포켓몬을 보여준다.")
            self.mon_note.pack(fill="both", expand=True)
            self.mon_id = None
            for r in self.mon_rows.values():
                r.set_selected(False)
            return
        self.mon_note.pack_forget()
        self.mon_list.pack(fill="both", expand=True)

        first_ok = None
        for pid, row in self.mon_rows.items():
            good, blocked, note, color = self._target_state(it, row.mon)
            row.set_state(good, blocked, note, color)
            if not blocked and (first_ok is None or (good and not self._is_good(first_ok))):
                first_ok = pid
        # 고르고 있던 포켓몬이 이 도구로는 못 쓰는 대상이면 옮겨 준다
        cur = self.mon_rows.get(self.mon_id)
        if cur is None or cur.blocked:
            self.pick_mon(first_ok, quiet=True)
        else:
            self.pick_mon(self.mon_id, quiet=True)

    def _is_good(self, pid):
        row = self.mon_rows.get(pid)
        return bool(row and row.good)

    def _target_state(self, it, mon):
        """이 도구를 이 포켓몬에게 쓸 수 있는지.

        (밝게 칠할까, 막을까, 줄 끝에 붙일 말, 그 말의 색) 을 돌려준다.
        진화의 돌은 **막지 않는다.** 낮/밤 같은 조건은 서버가 보기 때문에
        여기서는 될 만한 대상을 밝게 알려주는 데까지만 한다.
        """
        eff = it.get("effect") or {}
        kind = eff.get("kind")
        info = mon.get("info") or {}
        level = int(mon.get("level", 0))

        if kind == "stone":
            if info.get("species") in (it.get("evolves") or []):
                return True, False, "진화할 수 있다", U.GOOD
            return False, False, "", U.FG_FAINT

        if kind == "iv":
            if level < HYPER_MIN_LEVEL:
                return False, True, "Lv.%d 부터" % HYPER_MIN_LEVEL, U.FG_FAINT
            ivs = info.get("ivs") or {}
            hyper = info.get("hyper") or {}
            left = [s for s, _l in STAT_ROWS
                    if int(ivs.get(s, 0)) < P.IV_MAX and not hyper.get(s)]
            if not left:
                return False, True, "이미 다 단련됨", U.FG_FAINT
            return False, False, "%d곳 남음" % len(left), U.SHINY

        if kind == "ev":
            stat = eff.get("stat")
            amount = int(eff.get("amount", 0))
            evs = info.get("evs") or {}
            cur = int(evs.get(stat, 0))
            total = int(info.get("evTotal", sum(int(v) for v in evs.values())))
            label = STAT_KR.get(stat, stat)
            if amount >= 0:
                if cur >= EV_STAT_MAX:
                    return False, True, "%s 이미 최대" % label, U.FG_FAINT
                if total >= EV_TOTAL_MAX:
                    return False, True, "합계가 꽉 참", U.FG_FAINT
                return False, False, "%s %d" % (label, cur), U.GOOD
            if cur <= 0:
                return False, True, "%s 내릴 것 없음" % label, U.FG_FAINT
            return False, False, "%s %d" % (label, cur), U.INFO

        if kind == "level":
            if level >= P.LEVEL_MAX:
                return False, True, "최고 레벨", U.FG_FAINT
            return False, False, "Lv.%d → %d" % (
                level, min(P.LEVEL_MAX, level + int(eff.get("amount", 1)))), U.INFO

        if kind == "noevolve":
            if mon.get("noEvolve"):
                return True, False, "진화 잠금 중 · 풀기", U.PINK
            return False, False, "진화를 막는다", U.FG_DIM

        return False, True, "쓸 수 없다", U.FG_FAINT

    def pick_mon(self, pid, quiet=False):
        row = self.mon_rows.get(pid)
        if row is not None and row.blocked:
            if not quiet:
                self.say(row.note_text or "이 포켓몬에게는 쓸 수 없다.", U.ACCENT,
                         U.FG_DIM)
            return
        self.mon_id = pid if row is not None else None
        for i, r in self.mon_rows.items():
            r.set_selected(i == self.mon_id)
        self.stat = None
        self._refresh_stats()
        self._refresh_evs()
        self._refresh_button()

    def pick_stat(self, key):
        mon = self.current_mon()
        if not self.stat_needed or not mon:
            return
        info = mon.get("info") or {}
        if int((info.get("ivs") or {}).get(key, 0)) >= P.IV_MAX \
                or (info.get("hyper") or {}).get(key):
            return self.say("%s은(는) 이미 최고치다." % STAT_KR[key], U.ACCENT,
                            U.FG_DIM)
        self.stat = key
        self._refresh_stats()
        self._refresh_button()

    # ---------------- 오른쪽 칸 새로 칠하기 ----------------
    def _refresh_stats(self):
        if not self.stat_needed:
            return
        mon = self.current_mon()
        info = (mon or {}).get("info") or {}
        ivs = info.get("ivs") or {}
        hyper = info.get("hyper") or {}
        if not mon:
            self.stat_hint.configure(text="먼저 포켓몬을 고르세요")
        elif int(mon.get("level", 0)) < HYPER_MIN_LEVEL:
            self.stat_hint.configure(text="Lv.%d 부터 단련할 수 있다"
                                          % HYPER_MIN_LEVEL)
        else:
            self.stat_hint.configure(text="회색은 이미 최고치")
        for key, label in STAT_ROWS:
            lb = self.stat_chips[key]
            if not mon:
                lb.configure(text=label, bg=U.BG2, fg="#5a6076",
                             highlightbackground=U.LINE, cursor="")
                continue
            iv = int(ivs.get(key, 0))
            done = hyper.get(key) or iv >= P.IV_MAX
            text = "%s %d" % (label, P.IV_MAX if done else iv)
            if done:
                lb.configure(text=text, bg=U.BG2, fg="#5a6076",
                             highlightbackground=U.LINE, cursor="")
            elif self.stat == key:
                lb.configure(text=text, bg=U.ACCENT, fg=U.ACCENT_DARK,
                             highlightbackground=U.INK, cursor="hand2")
            else:
                lb.configure(text=text, bg=U.BG3, fg=U.FG,
                             highlightbackground=U.LINE2, cursor="hand2")

    def _refresh_evs(self):
        it = self.current_item()
        if not it or (it.get("effect") or {}).get("kind") != "ev":
            return
        mon = self.current_mon()
        info = (mon or {}).get("info") or {}
        evs = info.get("evs") or {}
        total = int(info.get("evTotal", 0))
        want = (it.get("effect") or {}).get("stat")
        for key, label in STAT_ROWS:
            name, cv, val = self.ev_bars[key]
            v = int(evs.get(key, 0)) if mon else 0
            on = (key == want)
            name.configure(fg=U.ACCENT_TEXT if on else U.FG_DIM)
            val.configure(text=str(v) if mon else "-",
                          fg=U.ACCENT if on else U.FG_DIM)
            cv.delete("all")
            w = int(118 * min(v, EV_STAT_MAX) / float(EV_STAT_MAX))
            if w:
                cv.create_rectangle(0, 0, w, 7,
                                    fill=U.ACCENT if on else "#4a5878",
                                    outline="")
        if mon:
            self.ev_total.configure(
                text="합계 %d / %d" % (total, EV_TOTAL_MAX),
                fg=U.DANGER if total >= EV_TOTAL_MAX else U.FG_DIM)
        else:
            self.ev_total.configure(text="포켓몬을 고르세요", fg=U.FG_FAINT)

    def _refresh_button(self):
        it = self.current_item()
        mon = self.current_mon()
        usable = bool(it) and (it.get("effect") or {}).get("kind") in USABLE
        ok = bool(usable and mon and (not self.stat_needed or self.stat))
        self.use_btn.configure(state="normal" if ok else "disabled")
        if it and usable and mon:
            self.use_btn.configure(text="%s 쓰기" % it["kr"])
        else:
            self.use_btn.configure(text="쓰기")

    # ---------------- 쓰기 ----------------
    def do_use(self):
        it = self.current_item()
        mon = self.current_mon()
        if not it or not mon:
            return
        if self.stat_needed and not self.stat:
            return self.say("어느 능력을 단련할지 골라 주세요.", U.ACCENT, U.FG_DIM)

        api = self.app.api
        item_id, pid, stat = it["id"], mon["id"], self.stat or ""
        # 낮/밤을 보는 조건이 있어서 이 PC 의 시각을 같이 보낸다.
        hour = datetime.datetime.now().hour
        self.use_btn.configure(state="disabled")
        self.say("%s을(를) 쓰는 중..." % it["kr"], U.FG_FAINT)

        def work():
            return use_item(api, item_id, pid, stat, hour)

        def done(r, err):
            if not self.alive:
                return
            if err:
                self.say(getattr(err, "message", str(err)), U.DANGER, U.DANGER)
                return self._refresh_button()
            r = r or {}
            self.mon_id = pid
            self._pending = (r.get("message") or "도구를 썼다.", U.GOOD)
            self.reload()
            self.app.request_sync()          # 바탕화면 도트도 바뀔 수 있다
            if r.get("evolve"):
                announce_evolve(self.win, self.app, r["evolve"])
        U.run_async(self.root, work, done)

    # ---------------- 끝내기 ----------------
    def close(self):
        self.alive = False
        if getattr(self.app, "bag_window", None) is self:
            self.app.bag_window = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def focus(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()


# ---------------------------------------------------------------- 진화 알림
def announce_evolve(parent, app, info):
    """진화했다고 크게 알린다.

    바탕화면 연출은 다른 파일이 맡는다. 여기서는 글로 알리는 것과, 전/후
    **실제 도트**를 나란히 보여주는 것까지만 한다. 대화상자 껍데기는
    ui_box 의 것을 그대로 쓴다. 창마다 다시 그리면 미묘하게 달라진다.
    """
    win, f = ui_box._shell(parent, "진화!", 420, 316)
    keep = {}

    tk.Label(f, text="축하합니다!", bg=U.BG, fg=U.ACCENT_TEXT,
             font=(U.FAMILY_BLACK, 20)).pack(anchor="w")
    # '(으)로' 는 natural() 이 못 고치는 표기다. '로(으로)' 로 적어야
    # 앞말의 받침을 보고 '로 / 으로' 가 제대로 골라진다.
    tk.Label(f, text=natural("%s은(는) %s로(으로) 진화했다!"
                             % (info.get("fromKr", "?"), info.get("toKr", "?"))),
             bg=U.BG, fg=U.FG, font=U.FONT_H, wraplength=360,
             justify="left").pack(anchor="w", pady=(6, 0))

    art = tk.Frame(f, bg=PANEL, highlightthickness=2, highlightbackground=U.LINE,
                   height=110)
    art.pack(fill="x", pady=(14, 0))
    art.pack_propagate(False)
    before = tk.Label(art, bg=PANEL, text="...", fg=U.FG_FAINT, font=U.FONT_S)
    before.pack(side="left", expand=True)
    tk.Label(art, text="→", bg=PANEL, fg=U.ACCENT, font=U.FONT_T).pack(side="left")
    after = tk.Label(art, bg=PANEL, text="...", fg=U.FG_FAINT, font=U.FONT_S)
    after.pack(side="left", expand=True)

    def work():
        out = []
        for num in (info.get("fromNum"), info.get("toNum")):
            path = sprite_cache.ensure(app.api, num, False)
            img = None
            if path:
                try:
                    anim = sprites.load_animation(path, target_height=72,
                                                  min_scale=0.2, max_scale=3.0,
                                                  max_frames=1)
                    img = sprites.to_rgba(anim.frames[sprites.RIGHT][0],
                                          anim.key)
                except Exception:                       # noqa: BLE001
                    img = None
            out.append(img)
        return out

    def done(imgs, err):
        if err or not imgs:
            return
        for lb, img, tag in ((before, imgs[0], "b"), (after, imgs[1], "a")):
            if img is None:
                continue
            try:
                keep[tag] = ImageTk.PhotoImage(img)
                lb.configure(image=keep[tag], text="")
            except tk.TclError:
                return
    U.run_async(parent, work, done)

    row = tk.Frame(f, bg=U.BG)
    row.pack(fill="x", pady=(14, 0))
    U.PushButton(row, "좋아!", win.destroy, height=34,
                 font=U.FONT_B).pack(side="right")
    win.grab_set()
    parent.wait_window(win)
