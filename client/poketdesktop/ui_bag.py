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
* 휠은 창 하나가 받아서 포인터 밑의 목록으로 보낸다(U.install_wheel).
  이 창은 목록이 둘이라 어느 쪽을 굴릴지 그때그때 정해야 한다.
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
from . import ui_loading

LIST_W = 292            # 왼쪽 도구 목록 폭
ITEM_H = U.h(28)        # 도구 한 줄 높이 (글꼴 따라 늘어난다)
MON_H = U.h(34)         # 포켓몬 한 줄 높이
THUMB = 22              # 목록에 놓는 도트 높이 (다른 창과 겹치지 않는 값)
# 목록을 나눠 만드는 크기(U.Chunked). 가방의 줄은 위젯이 8~9개로 무겁고
# 목록 둘이 같이 자라서, 30줄씩 만들면 묶음 하나에 0.5초씩 멈췄다.
# 첫 묶음은 첫 화면만큼(도구 스무 줄 남짓, 포켓몬 열몇 줄)이면 된다.
FIRST_ROWS = 20
CHUNK_ROWS = 15

EV_STAT_MAX = 252       # 서버 config 와 같은 값 (스탯 하나당)
EV_TOTAL_MAX = 510      # 서버 config 와 같은 값 (여섯 개 합계)
HYPER_MIN_LEVEL = 50    # 병뚜껑을 받을 수 있는 최소 레벨

STAT_ROWS = [("hp", "HP"), ("atk", "공격"), ("def", "방어"),
             ("spa", "특수공격"), ("spd", "특수방어"), ("spe", "스피드")]
STAT_KR = dict(STAT_ROWS)

# 분류 — 실제로 쓸 수 있는 것부터 위로 올린다
CAT_ORDER = ["held", "stone", "ev", "iv", "misc", "ball"]
CAT_KR = {"held": "지닌 도구", "stone": "진화의 돌", "ev": "노력치",
          "iv": "단련", "misc": "기타", "ball": "볼"}
CAT_COLOR = {"held": U.ACCENT, "stone": U.PINK, "ev": U.GOOD, "iv": U.SHINY,
             "misc": U.INFO, "ball": U.RED}

# /api/bag/use 가 받아주는 효과. 나머지(볼, 파는 물건)는 여기서 쓸 수 없다.
# "held" 는 use 가 아니라 /api/pokemon/{id}/hold 로 간다 - 대상을 고르는
# 흐름은 같아서 여기서 같이 다룬다.
USABLE = ("ev", "iv", "level", "stone", "noevolve", "held")

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
    """도구 설명 한 줄. items.json 에 설명 문구가 없어서 effect 로 만든다.

    볼은 서버가 만들어 보낸 note 를 그대로 쓴다. 조건(밤인지, 무게가 얼마인지,
    이미 잡아본 종인지)을 아는 쪽은 서버뿐이라, 여기서 다시 만들면 화면에
    쓰인 말과 실제 판정이 어긋난다.
    """
    if item.get("note"):
        return item["note"]
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
            out = "특정 포켓몬을 진화시키는 돌이다."
        elif len(who) > 6:
            out = "%s 외 %d종이(가) 진화한다." % (", ".join(who[:6]),
                                            len(who) - 6)
        else:
            out = "%s이(가) 진화한다." % ", ".join(who)
        # **지닐 수도 있는 돌이 넷 있다** (예리한손톱·예리한이빨·
        # 왕의징표석·금속코트). 진화 얘기만 적어 두면 배틀에서
        # 무슨 일을 하는지 가방에서는 알 길이 없다.
        if item.get("holdable") and item.get("desc"):
            out += "\n\n지니게 하면: " + item["desc"]
        return out
    if kind == "noevolve":
        return "진화를 막는다. 한 번 더 쓰면 다시 진화할 수 있게 된다."
    if kind == "held":
        # 본가 설명 그대로 (서버가 items.json 에서 실어 보낸다)
        return item.get("desc") or "포켓몬에게 지니게 하는 도구다. 배틀에서 효과가 난다."
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
    if kind == "held":
        return "한 마리에 하나. 이미 지닌 것은 가방으로 돌아온다"
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


def _scrollable(cv):
    """이 캔버스가 실제로 굴러갈 데가 있나."""
    try:
        lo, hi = cv.yview()
        return (hi - lo) < 0.999
    except Exception:                                       # noqa: BLE001
        return False


# ---------------------------------------------------------------- 조각 위젯
def _scroller(parent, bg):
    """세로로 굴러가는 빈 영역을 만든다. (canvas, inner) 를 돌려준다.

    내용이 화면보다 짧으면 **스크롤할 게 없어야 한다.** bbox 를 그대로
    넣으면, 도구가 두 개뿐인데도 스크롤바가 움직이고 빈 화면이 보인다.
    포켓몬 관리 창에서 이미 같은 것을 고쳤다.

    맞추는 일은 U.scroll_fitter 가 **몰아서 한 번** 한다. 예전에는 여기서
    <Configure> 마다 update_idletasks 로 배치를 억지로 끝내고 쟀는데, 그게
    또 <Configure> 를 불러 제 발로 되돌아왔다. 기술머신 358줄을 그리는
    2.6초 중 2.3초가 이 한 줄이었다. 줄을 담자마자 굴려야 하면
    canvas.scroll_fit.fit_now() 를 부른다.
    """
    holder = tk.Frame(parent, bg=bg)
    holder.pack(fill="both", expand=True)
    cv = tk.Canvas(holder, bg=bg, highlightthickness=0, bd=0)
    sb = ttk.Scrollbar(holder, orient="vertical", command=cv.yview)
    cv.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    cv.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(cv, bg=bg)
    wid = cv.create_window((0, 0), window=inner, anchor="nw")
    cv.scroll_fit = U.scroll_fitter(cv, inner, wid)
    return cv, inner


class ItemRow(object):
    """왼쪽 도구 목록 한 줄 — 분류 색점 · 이름 · 개수."""

    def __init__(self, parent, item, count, on_pick, selected=False):
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
                                width=5, height=U.h(5))
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
        if selected:
            self.set_selected(True)      # 만들 때 칠한다 (나눠 만드는 줄)

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

    state=(good, blocked, note, color) 와 selected 를 주면 **만들 때 칠한다.**
    목록을 나눠 만들기 때문에, 다 만든 뒤 모든 줄을 다시 칠하면 줄 수만큼
    도로 멈춘다.
    """

    def __init__(self, parent, mon, on_pick, state=None, selected=False):
        self.mon = mon
        self.on_pick = on_pick
        self.selected = False
        self.good = False
        self.blocked = False
        self.note_text = ""
        self.photo = None
        # 아래에서 만든 모습 그대로의 상태. set_state 가 바뀐 것만 칠하려고 쓴다.
        self._state = (False, False, "", U.FG_FAINT)
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

        self.selected = bool(selected)
        if state is not None and tuple(state) != self._state:
            self.set_state(*state)           # 안에서 다시 칠한다
        elif self.selected:
            self.repaint()

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
        # 그대로면 안 칠한다. 도구를 고를 때마다 모든 줄에 부르는데,
        # 대부분의 줄은 바뀌는 게 없다(진화의 돌이면 거의 다 '해당 없음').
        if (good, blocked, note, color) == self._state:
            return
        self._state = (good, blocked, note, color)
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
    def __init__(self, root, app, parent=None):
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
        self._wait = None        # 여는 중 표시
        self._states = {}        # {포켓몬id: (good, blocked, note, color)} — 고른 도구 기준
        self._mon_ids = set()
        self._items_job = None   # 줄을 나눠 만드는 일 (U.Chunked)
        self._mons_job = None

        # parent 가 있으면 탭 안의 한 칸으로, 없으면 지금까지처럼 창으로.
        self.win = U.panel(parent, root, "포스크탑 — 가방",
                           1000, 664, 950, 600, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            # 탭으로 들어갈 때는 허브가 이미 걸어 두었다.
            U.install_wheel(self.win)

        self._header()
        self._bottom()
        body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True)
        self._items_pane(body)
        self._detail_pane(body)

        U.scrollable(self.item_canvas, 60)
        U.scrollable(self.mon_canvas, 60)
        self.reload()

    # ---------------- 머리 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=U.h(62))
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
                 font=(U.FAMILY_BLACK, U.pt(15))).pack(side="left", padx=(12, 12))
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
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

    # ---------------- 왼쪽: 가진 도구 ----------------
    def _items_pane(self, parent):
        wrap = tk.Frame(parent, bg=U.BG, width=LIST_W)
        wrap.pack(side="left", fill="y")
        wrap.pack_propagate(False)

        head = tk.Frame(wrap, bg=U.INK, height=U.h(26))
        head.pack(fill="x")
        head.pack_propagate(False)
        U.marker_label(head, "가진 도구", bg=U.INK).pack(side="left", padx=12,
                                                     pady=6)
        tk.Frame(wrap, bg=U.LINE, height=U.h(2)).pack(fill="x")
        self.item_canvas, self.item_inner = _scroller(wrap, U.BG)
        # 줄은 틀 하나에 담는다. 다시 불러올 때 틀째 숨기고 조금씩 부수려고
        # (U.retire). 틀은 바탕색이 같아 화면에는 차이가 없다.
        self.item_list = tk.Frame(self.item_inner, bg=U.BG)
        self.item_list.pack(fill="x")

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
                               fg=U.ACCENT_TEXT, font=(U.FAMILY_BLACK, U.pt(16)))
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
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x", side="bottom")
        bar = tk.Frame(self.win, bg=U.INK, height=U.h(58))
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        inner = tk.Frame(bar, bg=U.INK)
        inner.pack(fill="both", expand=True, padx=16)

        self.use_btn = U.PushButton(inner, "쓰기", self.do_use, height=34)
        self.use_btn.pack(side="right", pady=11)
        self.use_btn.configure(state="disabled")
        # **가방에서도 판다.** 팔려고 상점 탭으로 건너갔다가 목록에서 그
        # 도구를 다시 찾아야 하는 게 번거로웠다. 파는 곳은 서버가 같다
        # (/api/shop/sell) - 여기서는 부르기만 한다.
        self.sell_btn = U.ghost_button(inner, "팔기", self.do_sell, height=34)
        self.sell_btn.pack(side="right", padx=(0, 8), pady=11)
        self.sell_btn.configure(state="disabled")
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

    def current_item(self):
        return next((i for i in self.items if i["id"] == self.item_id), None)

    def current_mon(self):
        return next((m for m in self.mons if m["id"] == self.mon_id), None)

    # ---------------- 데이터 ----------------
    def reload(self):
        if not self.app.api:
            return self.say("로그인이 필요합니다.", U.DANGER, U.DANGER)
        # 여는 중 표시가 이미 떠 있으면 하나 더 띄우지 않는다. 겹쳐 띄우면
        # 먼저 온 답이 나중 것만 걷고, 먼저 띄운 것은 창을 덮은 채 남는다.
        if not self._pending and self._wait is None:
            self.say("가방을 여는 중...", U.FG_FAINT)
            self._wait = ui_loading.Overlay(self.win, "가방을 여는 중")
        api = self.app.api

        def work():
            shop = fetch_shop(api)
            mons = api.pokemon()
            # 도트는 여기서 그림까지 다 만들어 둔다. tk 스레드에서 만들면
            # 마릿수만큼 창이 멈춘다. PhotoImage 만 tk 쪽에서 씌운다.
            #
            # 칸(frame_art) 을 넘지 않게 max_size 로 줄인다. 옆으로 긴 종은
            # 높이만 맞추면 30px 칸 밖으로 나가 잘렸다(캐시된 312종 중 40종).
            # 칸을 넓히지는 않는다 - 이름과 레벨 자리가 옮겨 간다.
            thumbs = {}
            for m in mons:
                path = sprite_cache.ensure(api, m.get("num"), m.get("shiny"))
                if not path:
                    continue
                try:
                    anim = sprites.load_animation(path, target_height=THUMB,
                                                  min_scale=0.2, max_scale=3.0,
                                                  max_frames=1,
                                                  max_size=(26, MON_H - 4))
                    thumbs[m["id"]] = sprites.to_rgba(
                        anim.frames[sprites.RIGHT][0], anim.key)
                except Exception:                       # noqa: BLE001
                    pass
            # 도구 그림도 같이 받아 둔다 (가진 것만). 목록 크기(20)로
            # 풀어 두기까지 해서 tk 스레드는 감싸기만 한다.
            try:
                bag = (shop or {}).get("bag") or {}
                item_icons.prefetch(api, list(bag), sizes=(20,))
            except Exception:                           # noqa: BLE001
                pass
            return shop, mons, thumbs
        U.run_async(self.root, work, self._loaded)

    def _loaded(self, r, err):
        w, self._wait = self._wait, None
        if not self.alive:
            if w:
                w.close()
            return
        if err:
            if w:
                w.close()
            return self.say(getattr(err, "message", str(err)), U.DANGER,
                            U.DANGER)
        shop, mons, thumbs = r
        self.items = shop.get("items") or []
        self.bag = shop.get("bag") or {}
        self.money = int(shop.get("money") or 0)
        self.mons = mons or []
        self._mon_ids = set(m["id"] for m in self.mons)
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

        # 고를 도구를 먼저 정해 둔다. 줄을 만들면서 고른 줄을 바로 칠한다.
        keep_item = self.item_id
        if keep_item and self.bag.get(keep_item, 0) > 0:
            target = keep_item
        else:
            target = self._first_item()
        self.item_id = target
        self._fill_items()
        self._fill_mons()

        self.item_id = None
        self.pick_item(target)

        if self._pending:
            text, color = self._pending
            self._pending = None
            self.say(text, color)
        else:
            self.say("")

        if w:
            # **다 그리고 나서 걷는다.** 맨 앞에서 걷으면 줄을 만드는 동안
            # 아무 표시 없이 창이 멈춘 것처럼 보였다(4초). 첫 화면만큼은
            # 이미 만들었으니, 그것이 그려진 뒤(idle)에 걷는다.
            try:
                self.root.after_idle(w.close)
            except tk.TclError:
                w.close()

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
        """왼쪽 도구 목록을 새로 만든다.

        **나눠 만든다(U.Chunked).** 첫 화면만큼 먼저 만들고 나머지는 조금씩
        이어 만든다. 줄은 만들 때 고름까지 칠한다 - self.item_id 가 그 기준이다.
        """
        if self._items_job is not None:
            self._items_job.cancel()     # 옛 목록의 남은 줄이 뒤에 붙지 않게
            self._items_job = None
        old = self.item_list
        if old.winfo_children():
            # 옛 줄은 틀째 숨기고 조금씩 부순다. 수백 개를 한 번에 부수면
            # 그것만으로 0.8초 멈췄다(쓰기·팔기 뒤에 다시 불러올 때).
            self.item_list = tk.Frame(self.item_inner, bg=U.BG)
            self.item_list.pack(fill="x", before=old)
            U.retire(old)
        box = self.item_list
        self.item_rows = {}
        owned = self._owned()
        if not owned:
            tk.Label(box, text="가방이 비어 있다.", bg=U.BG,
                     fg=U.FG_DIM, font=U.FONT_S).pack(pady=(34, 4))
            tk.Label(box,
                     text="야생 포켓몬을 잡거나 배틀에서\n도구를 주울 수 있다.",
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS,
                     justify="center").pack()
            return
        counts = {}
        for x in owned:
            counts[x["cat"]] = counts.get(x["cat"], 0) + 1
        last = {"cat": None}

        def build(it):
            if it["cat"] != last["cat"]:
                cat = last["cat"] = it["cat"]
                strip = tk.Frame(box, bg=U.INK, height=U.h(26))
                strip.pack(fill="x")
                strip.pack_propagate(False)
                U.marker_label(strip, "%s · %d종" % (CAT_KR.get(cat, cat),
                                                    counts[cat]),
                               bg=U.INK,
                               mark=CAT_COLOR.get(cat, U.ACCENT)).pack(
                    side="left", padx=12, pady=6)
                tk.Frame(box, bg=U.LINE, height=U.h(1)).pack(fill="x")
            self.item_rows[it["id"]] = ItemRow(
                box, it, self.bag.get(it["id"], 0), self.pick_item,
                selected=(it["id"] == self.item_id)).pack()
            tk.Frame(box, bg="#161a24", height=U.h(1)).pack(fill="x")

        self._items_job = U.Chunked(self.win, owned, build,
                                    first=FIRST_ROWS, size=CHUNK_ROWS)

    def _fill_mons(self):
        """'누구에게 쓸까?' 목록을 새로 만든다. 나눠 만든다.

        줄은 만들 때 그 시점의 고른 도구 기준 상태(self._states)와 고름
        (self.mon_id)으로 칠한다. 첫 화면만큼은 곧이어 pick_item 이 맞춰
        칠하고, 나중에 만들어지는 줄은 이미 맞춰진 상태로 태어난다.
        """
        if self._mons_job is not None:
            self._mons_job.cancel()
            self._mons_job = None
        old = self.mon_list
        if old.winfo_children():
            # 도구 목록과 같다 - 틀째 숨기고 조금씩 부순다. 못 쓰는 도구를
            # 골라 틀이 빠져 있었으면 새 틀도 빠진 채로 둔다(_show_targets 가 담는다).
            self.mon_list = tk.Frame(self.mon_inner, bg=ROW_BG)
            if old.winfo_manager() == "pack":
                self.mon_list.pack(fill="both", expand=True, before=old)
            U.retire(old)
        self.mon_rows = {}
        if not self.mons:
            tk.Label(self.mon_list, text="가진 포켓몬이 없다.", bg=ROW_BG,
                     fg=U.FG_FAINT, font=U.FONT_S, pady=30).pack()
            return

        def build(m):
            row = MonRow(self.mon_list, m, self.pick_mon,
                         state=self._states.get(m["id"]),
                         selected=(m["id"] == self.mon_id)).pack()
            ph = self.photos.get(m["id"])
            if ph:
                row.set_photo(ph)
            self.mon_rows[m["id"]] = row
            tk.Frame(self.mon_list, bg="#161a24", height=U.h(1)).pack(fill="x")

        self._mons_job = U.Chunked(self.win, self.mons, build,
                                   first=FIRST_ROWS, size=CHUNK_ROWS)

    # ---------------- 고르기 ----------------
    def pick_item(self, item_id):
        prev = self.item_id
        self.item_id = item_id
        self.stat = None
        # 바뀐 두 줄만 칠한다. 고른 줄은 늘 하나라 나머지는 이미 안 고른
        # 모습이다. 아직 안 만든 줄은 만들 때 self.item_id 를 보고 칠한다.
        for i in set((prev, item_id)):
            r = self.item_rows.get(i)
            if r is not None:
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
            prev, self.mon_id = self.mon_id, None
            row = self.mon_rows.get(prev)
            if row is not None:
                row.set_selected(False)
            return
        self.mon_note.pack_forget()
        self.mon_list.pack(fill="both", expand=True)

        # 판정은 **줄이 아니라 데이터로** 한다. 줄은 나눠 만드는 중이라
        # 아직 없는 줄이 있을 수 있다. 없는 줄은 만들 때 이 상태로 칠해진다.
        self._states = {}
        first_ok = None
        for m in self.mons:
            good, blocked, note, color = self._target_state(it, m)
            self._states[m["id"]] = (good, blocked, note, color)
            if not blocked and (first_ok is None or (good and not self._is_good(first_ok))):
                first_ok = m["id"]
        for pid, row in self.mon_rows.items():
            row.set_state(*self._states[pid])
        # 고르고 있던 포켓몬이 이 도구로는 못 쓰는 대상이면 옮겨 준다
        cur = self._states.get(self.mon_id)
        if cur is None or cur[1]:
            self.pick_mon(first_ok, quiet=True)
        else:
            self.pick_mon(self.mon_id, quiet=True)

    def _is_good(self, pid):
        st = self._states.get(pid)
        return bool(st and st[0])

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

        if kind == "held":
            cur = mon.get("heldKr")
            if mon.get("held") == it["id"]:
                return False, True, "이미 지님", U.FG_FAINT
            if cur:
                return False, False, "지님: %s" % cur, U.FG_DIM
            return True, False, "빈손", U.GOOD

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
        # 줄이 아직 안 만들어졌을 수 있어서 데이터(self._states)로 본다.
        st = self._states.get(pid)
        if st is not None and st[1]:
            if not quiet:
                self.say(st[2] or "이 포켓몬에게는 쓸 수 없다.", U.ACCENT,
                         U.FG_DIM)
            return
        prev = self.mon_id
        self.mon_id = pid if pid in self._mon_ids else None
        # 바뀐 두 줄만 칠한다 (pick_item 과 같은 까닭).
        for i in set((prev, self.mon_id)):
            r = self.mon_rows.get(i)
            if r is not None:
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

        # 팔기는 포켓몬을 안 골라도 된다. 값이 붙어 있고 실제로 갖고
        # 있으면 팔 수 있다. 몬스터볼은 게임이 안 돌아가므로 뺀다.
        have = int(self.bag.get((it or {}).get("id"), 0)) if it else 0
        price = int((it or {}).get("sell") or 0)
        can_sell = bool(it) and price > 0 and have > 0 and it["id"] != "POKEBALL"
        self.sell_btn.configure(state="normal" if can_sell else "disabled")
        self.sell_btn.configure(
            text="%d원에 팔기" % price if can_sell else "팔기")

    # ---------------- 팔기 ----------------
    def do_sell(self):
        """가방에서 바로 판다. 값과 재고 판정은 서버가 한다.

        **되돌릴 수 없으니 한 번 묻는다.** 진화의 돌처럼 아껴 둔 것을
        잘못 누르면 그대로 사라진다.
        """
        it = self.current_item()
        if not it:
            return
        have = int(self.bag.get(it["id"], 0))
        price = int(it.get("sell") or 0)
        if have <= 0 or price <= 0:
            return
        n = 1
        if not ui_box.confirm(
                self.win, "팔기",
                "%s 을(를) 한 개 팔아 %d원을 받습니다. 되돌릴 수 없습니다."
                % (it["kr"], price),
                danger=True, ok_text="판다"):
            return

        api = self.app.api
        item_id = it["id"]
        self.sell_btn.configure(state="disabled")
        self.say("%s을(를) 파는 중..." % it["kr"], U.FG_FAINT)

        def work():
            fn = getattr(api, "sell", None)
            if fn is not None:
                return fn(item_id, n)
            return api._call("POST", "/api/shop/sell",
                             body={"item": item_id, "count": n})

        def done(r, err):
            if not self.alive:
                return
            if err:
                self.say(getattr(err, "message", str(err)), U.DANGER, U.DANGER)
                return self._refresh_button()
            r = r or {}
            self._pending = (r.get("message") or "팔았다.", U.GOOD)
            self.reload()

        U.run_async(self.root, work, done)

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

        held = (it.get("effect") or {}).get("kind") == "held"

        def work():
            if held:
                # 지니는 건 '쓰는' 게 아니다. 가방에서 빠져 포켓몬에게 간다.
                return api.hold(pid, item_id)
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
        for job in (self._items_job, self._mons_job):
            if job is not None:
                job.cancel()
        if getattr(self.app, "bag_window", None) is self:
            self.app.bag_window = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def focus(self):
        if U.is_embedded(self.win):
            return          # 탭이면 허브가 앞으로 꺼내 준다
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()


# ---------------------------------------------------------------- 진화 알림
def _gift_icon(parent, app, label, item_id, keep, tag):
    """선물 상자에 도구 그림을 넣는다. 안 받아 뒀으면 받아서 넣는다.

    **처음 받는 도구는 이 PC 에 그림이 없다.** 선물이 바로 그런 경우다 -
    이벤트 볼처럼 상점에 없는 물건은 가방을 열어 본 적이 없으면 그림도
    없다. 그대로 두면 이름만 뜨고 자리가 비어 보인다.

    창을 늦게 띄우지는 않는다. 먼저 글로 띄우고, 그림이 오면 채운다.
    """
    got = item_icons.photo(item_id, 26)
    if got is not None:
        keep[tag] = got
        return label.configure(image=got)

    def work():
        item_icons.raw(app.api, item_id)     # 받아서 이 PC 에 남긴다
        return True

    def done(_r, err):
        if err:
            return
        try:
            ph = item_icons.photo(item_id, 26)
            if ph is not None:
                keep[tag] = ph
                label.configure(image=ph)
        except Exception:                                  # noqa: BLE001
            pass

    U.run_async(parent, work, done)


def gift_line(g):
    """선물 한 줄에 적을 말.

    돈은 개수가 아니다. "돈 ×5000" 이라고 적으면 5000개를 받은 것처럼
    읽힌다. 화면 어디서나 돈은 "5,000원" 이라 여기서도 그렇게 적는다.
    """
    n = int(g.get("count", 1) or 0)
    if g.get("kind") == "money":
        return "%s원" % format(n, ",")
    return "%s ×%d" % (g.get("name") or "?", n)


def announce_gifts(parent, app, gifts):
    """운영자가 보낸 선물이 도착했다고 알린다.

    **여럿이면 한 창에 모아 보여준다.** 하나씩 띄우면 창이 줄줄이 뜬다.

    껍데기는 진화 알림과 같은 것을 쓴다(ui_box._shell). 창마다 다시
    그리면 미묘하게 달라진다.

    도구 그림은 이미 받아 둔 것만 쓴다. 없으면 글로만 보여준다 - 선물이
    왔다는 사실이 그림보다 중요하고, 그림 받다 창이 늦게 뜨면 안 된다.
    """
    if not gifts:
        return
    keep = {}
    n = len(gifts)
    # 창 높이는 줄 수에 따라 잡고, 글꼴이 커지면 같이 커진다.
    # **넉넉하게 잡는다.** 모자라면 아래에서부터 조용히 눌린다 - 실제로
    # 18px 이 모자라 단추 글씨('고맙습니다')까지 잘렸다.
    height = U.h(250) + min(n, 8) * U.h(38)
    win, f = ui_box._shell(parent, "선물", 420, height)

    tk.Label(f, text="선물이 도착했습니다", bg=U.BG, fg=U.ACCENT_TEXT,
             font=(U.FAMILY_BLACK, U.pt(20))).pack(anchor="w")
    # 제목과 메시지는 운영자가 적은 것이다. 첫 선물의 것을 쓴다 -
    # 한 번에 여러 개를 보낼 때는 보통 같은 이유로 보낸다.
    head = gifts[0].get("title") or ""
    msg = gifts[0].get("message") or ""
    if head:
        tk.Label(f, text=head, bg=U.BG, fg=U.FG, font=U.FONT_H,
                 wraplength=360, justify="left").pack(anchor="w", pady=(6, 0))
    if msg:
        tk.Label(f, text=natural(msg), bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
                 wraplength=360, justify="left").pack(anchor="w", pady=(4, 0))

    box = tk.Frame(f, bg=PANEL, highlightthickness=2,
                   highlightbackground=U.LINE)
    box.pack(fill="x", pady=(14, 0))
    inner = tk.Frame(box, bg=PANEL)
    inner.pack(fill="x", padx=14, pady=10)
    for i, g in enumerate(gifts[:8]):
        row = tk.Frame(inner, bg=PANEL, height=U.h(34))
        row.pack(fill="x")
        row.pack_propagate(False)
        # **그림 자리를 픽셀로 잡는다.** Label 의 width 는 글자일 때는
        # 글자 수인데 그림일 때는 픽셀이라, width=3 을 주면 그림이 3px
        # 로 눌린다. 게다가 돈처럼 그림이 없는 줄과 들여쓰기가 어긋난다.
        # 칸(Frame)으로 자리를 잡으면 있든 없든 줄이 맞는다.
        slot = tk.Frame(row, bg=PANEL, width=U.h(30), height=U.h(30))
        slot.pack(side="left", padx=(0, 8))
        slot.pack_propagate(False)
        icon = tk.Label(slot, bg=PANEL)
        icon.pack(expand=True)
        if g.get("kind") == "item" and g.get("item"):
            _gift_icon(parent, app, icon, g["item"], keep, i)
        tk.Label(row, text=gift_line(g), bg=PANEL, fg=U.FG, font=U.FONT_B,
                 anchor="w").pack(side="left")
    if n > 8:
        tk.Label(inner, text="그 밖 %d개" % (n - 8), bg=PANEL,
                 fg=U.FG_FAINT, font=U.FONT_XS).pack(anchor="w", pady=(4, 0))

    tk.Label(f, text="가방에 넣어 두었습니다.", bg=U.BG, fg=U.FG_DIM,
             font=U.FONT_S, wraplength=360,
             justify="left").pack(anchor="w", pady=(10, 0))

    row = tk.Frame(f, bg=U.BG)
    row.pack(fill="x", pady=(14, 0))
    U.PushButton(row, "고맙습니다", win.destroy, height=34,
                 font=U.FONT_B).pack(side="right")

    # **다 담고 나서 창을 내용에 맞춘다.**
    #
    # 줄 수만 세서 높이를 잡으면 모자란다. 제목과 설명이 길면 여러 줄로
    # 접히는데 그 줄 수는 글꼴에 달렸고, 글꼴은 OS 마다 다르다. 맥에서
    # 맞춰 둔 숫자가 윈도우(맑은 고딕)에서 맞으리라는 보장이 없다.
    #
    # 글자를 줄이지 않는다. 칸을 늘린다.
    try:
        win.update_idletasks()
        need = win.winfo_reqheight()
        if need > win.winfo_height():
            win.geometry("%dx%d" % (win.winfo_width() or 420, need))
    except Exception:                                      # noqa: BLE001
        pass

    win.grab_set()
    parent.wait_window(win)


def announce_evolve(parent, app, info):
    """진화했다고 크게 알린다.

    바탕화면 연출은 다른 파일이 맡는다. 여기서는 글로 알리는 것과, 전/후
    **실제 도트**를 나란히 보여주는 것까지만 한다. 대화상자 껍데기는
    ui_box 의 것을 그대로 쓴다. 창마다 다시 그리면 미묘하게 달라진다.
    """
    win, f = ui_box._shell(parent, "진화!", 420, 316)
    keep = {}

    tk.Label(f, text="축하합니다!", bg=U.BG, fg=U.ACCENT_TEXT,
             font=(U.FAMILY_BLACK, U.pt(20))).pack(anchor="w")
    # '(으)로' 는 natural() 이 못 고치는 표기다. '로(으로)' 로 적어야
    # 앞말의 받침을 보고 '로 / 으로' 가 제대로 골라진다.
    tk.Label(f, text=natural("%s은(는) %s로(으로) 진화했다!"
                             % (info.get("fromKr", "?"), info.get("toKr", "?"))),
             bg=U.BG, fg=U.FG, font=U.FONT_H, wraplength=360,
             justify="left").pack(anchor="w", pady=(6, 0))
    # 진화하면서 배우는 기술이 있으면 같이 적는다. 자리가 없어 못 배운
    # 것도 적는다 - 잠시 뒤에 무엇을 잊을지 묻는 창이 뜬다.
    learned = info.get("learned") or []
    pending = info.get("pending") or []
    if learned or pending:
        bits = []
        if learned:
            bits.append("%s 을(를) 배웠다!" % ", ".join(learned))
        if pending:
            bits.append("%s 을(를) 배우려 한다." % ", ".join(pending))
        line = "  ".join(bits)
        tk.Label(f, text=natural(line), bg=U.BG, fg=U.ACCENT_TEXT,
                 font=U.FONT_S, wraplength=360,
                 justify="left").pack(anchor="w", pady=(2, 0))

    art = tk.Frame(f, bg=PANEL, highlightthickness=2, highlightbackground=U.LINE,
                   height=U.h(110))
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
