# -*- coding: utf-8 -*-
"""캐릭터 만들기 (1.10.3) — 마이페이지에서 여는 꾸미기 창.

    open_editor(parent, app, avatar, on_saved)

머리·모자·안경·윗옷·바지·신발·가방과 색을 골라 내 캐릭터를 만든다. 그림은 받지 않는다 -
common/avatar_art 가 고른 것(spec)으로 그때그때 그린다. 서버에도 고른 것만 보낸다
(PUT /api/avatar). 그래서 여기서 보이는 그림과 남이 보는 그림이 같다.

화면:

    [피부|머리|모자|안경|윗옷|바지|신발|가방]
    ┌ 미리보기 ─┐  종류   그 부위만 바꾼 내 캐릭터가 칸마다 보인다 - 누르면 바로 바뀐다
    │ 앞 (크게)  │         (머리 칸은 모자를 벗겨서 그린다 - 안 그러면 다 똑같아 보인다)
    │            │  색     색 칸. 부위가 '없음' 이면 칠할 것이 없으니 숨긴다
    │ 옆 · 뒤    │
    └───────────┘
    [무작위] [되돌리기] [초기화]              [취소] [저장]

- '초기화' 는 기본 캐릭터로 돌려놓는다. 다른 고르기와 마찬가지로 저장을 눌러야 반영되고,
  되돌리기로 무를 수 있다.
- 미리보기는 걷는다 (왼발·서기·오른발·서기). 걷는 칸은 나중에 직접 걸어다니는 기능이 쓴다.
- 탭마다 칸 수가 다르다. 창이 탭을 바꿀 때마다 커졌다 줄었다 하지 않게 **탭 여덟 장을 같은 자리에
  겹쳐 두고** 고른 것만 위로 올린다 - 자리는 가장 큰 탭만큼 잡힌다. 화면이 낮아 다 못 담으면
  창을 키우지 않고 안쪽을 굴린다.
- 칸의 폭은 글자가 정한다 (글자를 줄이지 않는다). 글꼴이 커서 한 줄에 다섯이 안 들어가면
  넷, 셋으로 줄을 바꾼다 (columns).
- 고르는 일(무엇이 바뀌고, 되돌리면 어디로 가는가)은 Model 이 한다. 창 없이 검사한다.
"""
import random
import tkinter as tk

from common import avatar_art as A
from common import avatar_sheet as SHEET
from common.korean import natural

from . import ui_common as U
from .ui_common import run_async

# **보류 중 (2026-10-08).** 캐릭터(유저 프로필 도트)는 길드 광장에서 걸어 다니는 데 쓰려고 만들었는데
# 광장을 접었다. 마이페이지의 '캐릭터 만들기' 와 길드 프로필의 그림을 화면에서 숨긴다 - 코드와 서버
# (/api/avatar)는 그대로 둔다. 다시 쓰게 되면 True 로 바꾸면 된다.
ENABLED = False
W = 700                       # 창 폭
MAX_H = 680                   # 창 높이는 이 값을 넘지 않는다. 넘치면 오른쪽 칸이 굴러간다
BIG, SMALL, THUMB = 4, 2, 2   # 미리보기(앞) · 미리보기(옆·뒤) · 고르는 칸의 배율
COLS = 5                      # 고르는 칸은 한 줄에 다섯까지
PREVIEW_W = BIG * A.CELL + 22 # 미리보기 칸의 폭 (그림 + 안쪽 여백 10x2 + 테두리)
# 고르는 칸들이 쓸 수 있는 폭: 창 - 테두리 4 - 안쪽 여백 18x2 - 미리보기 - 사이 16 - 굴림 막대 몫 18
AVAIL = W - 4 - 36 - PREVIEW_W - 16 - 18
GAP = 6
SWATCH = 28                   # 색 칸 한 변 (금테 3px 포함)
SWATCH_ROW = 8                # 색 칸은 한 줄에 여덟
STEP_MS = 190                 # 걷는 미리보기의 한 걸음
WALK = ("a", "stand", "b", "stand")
TILE = "#10141e"
HISTORY = 40                  # 되돌리기는 여기까지 기억한다

# (열쇠, 이름). 피부는 종류가 없고 색만 있다.
TABS = [("skin", "피부")] + [(p[0], p[1]) for p in A.PARTS]
# 고르는 칸이 보여 주는 방향. 가방은 앞에서 보면 끈만 보여서 옆에서 본다.
THUMB_DIR = {"bag": "left"}
# 고르는 칸에서만 벗겨 두는 것. 모자를 쓰고 있으면 머리 칸 열셋이 다 똑같아 보인다 (모자가 머리를 가린다).
THUMB_WITHOUT = {"hair": ("hat",)}


def _err(e):
    return getattr(e, "message", None) or str(e)


def options_of(tab):
    """그 탭에서 고를 수 있는 종류 [(값, 이름)]. 피부처럼 색만 있으면 빈 목록."""
    for key, _name, options, _color in A.PARTS:
        if key == tab:
            return list(options)
    return []


def color_key(tab):
    """그 탭의 색이 적히는 열쇠 ('hair' -> 'hairColor'). 색이 없는 탭이면 None."""
    if tab == "skin":
        return "skin"
    for key, _name, _options, color in A.PARTS:
        if key == tab:
            return color
    return None


def swatches(tab):
    """그 탭의 색 칸 [(이름, '#rrggbb')]. 색표에 적힌 순서 그대로."""
    key = color_key(tab)
    table = A.PALETTES.get(key) or {}
    return [(name, "#%02x%02x%02x" % tuple(rgb[:3])) for name, rgb in table.items()]


def columns(tile_w, avail=AVAIL, most=COLS):
    """폭이 tile_w 인 칸을 한 줄에 몇 개 놓을까. 글꼴이 커서 칸이 넓어지면 줄을 바꾼다."""
    return max(1, min(most, int(avail) // max(1, int(tile_w) + GAP)))


def thumb_spec(spec, tab, value):
    """고르는 칸 하나에 그릴 캐릭터: 그 부위만 value 로 바꾼 지금의 나."""
    out = dict(spec)
    out[tab] = value
    for key in THUMB_WITHOUT.get(tab, ()):
        out[key] = ""
    return out


def paintable(spec, tab):
    """그 탭의 색을 칠할 곳이 있는가. 모자가 '없음' 이면 모자 색은 고를 것이 없다."""
    return tab == "skin" or bool(spec.get(tab))


def silhouette(img, rgb):
    """그림의 모양만 남긴다 (칠해진 점을 전부 한 색으로). 캐릭터가 없을 때의 자리 그림."""
    fill = tuple(rgb[:3]) + (255,)
    return [[fill if px[3] else px for px in row] for row in img]


class Model(object):
    """지금 고른 것과 되돌릴 것들. 화면이 없어도 돈다.

    saved 는 서버에 있는 것이다 (없으면 None). 처음 만드는 사람은 기본 캐릭터에서 시작하고,
    아무것도 안 바꿔도 저장할 수 있다 (dirty) - '기본 캐릭터 그대로 쓰겠다' 도 고른 것이다.
    """

    def __init__(self, saved=None):
        self.saved = A.clean(saved) if saved else None
        self.spec = dict(self.saved or A.DEFAULT)
        self.history = []

    @property
    def dirty(self):
        return self.spec != self.saved

    def _push(self, new):
        new = A.clean(new)
        if new == self.spec:
            return False
        self.history.append(dict(self.spec))
        del self.history[:-HISTORY]
        self.spec = new
        return True

    def pick(self, key, value):
        """한 가지를 바꾼다. 실제로 바뀌었으면 True. 모르는 값이면 그대로 둔다."""
        new = dict(self.spec)
        new[key] = value
        if A.clean(new).get(key) != value:
            return False
        return self._push(new)

    def randomize(self, rng=None):
        rng = rng or random
        for _ in range(8):                    # 지금과 똑같은 것이 뽑히면 다시 뽑는다
            if self._push(A.random_spec(rng)):
                return True
        return False

    def reset(self):
        """기본 캐릭터로 돌려놓는다. 이미 기본이면 아무 일도 없다 (False). 되돌리기로 무를 수 있다."""
        return self._push(dict(A.DEFAULT))

    @property
    def plain(self):
        """지금이 기본 캐릭터인가 (초기화할 것이 없다)."""
        return self.spec == A.DEFAULT

    def undo(self):
        if not self.history:
            return False
        self.spec = self.history.pop()
        return True

    def mark_saved(self, spec=None):
        self.saved = A.clean(spec if spec is not None else self.spec)
        self.spec = dict(self.saved)


# ---------------------------------------------------------------- 그림
def to_pil(img):
    """[(r, g, b, a) 줄] -> PIL 그림."""
    from PIL import Image
    h, w = len(img), len(img[0])
    im = Image.new("RGBA", (w, h))
    im.putdata([tuple(px) for row in img for px in row])
    return im


def to_photo(img):
    """[(r, g, b, a) 줄] -> PhotoImage. tk 스레드에서 부른다. 투명한 곳은 위젯 바탕이 비친다."""
    from PIL import ImageTk
    return ImageTk.PhotoImage(to_pil(img))


def front_of(avatar, k=3):
    """캐릭터(서버가 준 것)의 앞모습 그림. **직접 그린 도트를 쓰는 중이면 그것**, 아니면 꾸민 캐릭터.

    도트가 깨져서 못 읽으면 꾸민 캐릭터로 넘어간다 - 빈칸보다 낫다.
    """
    avatar = avatar or {}
    sheet = SHEET.unpack(avatar.get("image")) if avatar.get("image") else None
    if sheet is not None:
        return SHEET.front(sheet, k)
    return A.front(A.clean(avatar.get("spec")), k)


def sheet_of(avatar):
    """캐릭터의 걷기 시트 (96x128). 직접 걸어다니는 기능이 쓴다. 직접 그린 도트가 먼저다."""
    avatar = avatar or {}
    sheet = SHEET.unpack(avatar.get("image")) if avatar.get("image") else None
    return sheet if sheet is not None else A.walk_sheet(A.clean(avatar.get("spec")))


def portrait(avatar, k=3):
    """마이페이지·프로필에 놓는 앞모습 PhotoImage (기본 96x96). avatar = 서버가 준 캐릭터."""
    return to_photo(front_of(avatar, k))


def placeholder(k=3, rgb=(46, 54, 76)):
    """캐릭터를 아직 안 만든 사람의 자리 그림 (기본 캐릭터의 그림자)."""
    return to_photo(silhouette(A.front(A.DEFAULT, k), rgb))


# ---------------------------------------------------------------- 창
class Editor(object):

    def __init__(self, parent, app, avatar=None, on_saved=None):
        from .ui_box import _shell, fit, scroll_body
        self.app = app
        self.root = app.root
        self.on_saved = on_saved
        self.model = Model((avatar or {}).get("spec"))
        self.first = not avatar
        self.drawn = bool((avatar or {}).get("image"))     # 지금은 직접 그린 도트를 쓰고 있다
        self.alive = True
        self.busy = False
        self.tab = "hair"
        self._tick = 0
        self._after = None
        self._keep = {}               # PhotoImage 를 붙들어 둔다 (놓으면 그림이 사라진다)
        self.pages = {}               # 탭 -> 그 탭의 틀
        self.tiles = {}               # 탭 -> {값: (칸, 그림 라벨, 이름 라벨)}
        self.dots = {}                # 탭 -> {색 이름: 색 칸}
        self.dot_rows = {}            # 탭 -> (색 칸들이 든 틀, '고르면 색을...' 글)
        self.cols = {}                # 탭 -> 한 줄에 놓은 칸 수

        title = "캐릭터 만들기" if self.first else "캐릭터 바꾸기"
        self.win, f = _shell(parent, title, W, MAX_H)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        # 아래부터 놓는다 - 화면이 낮아 줄어들 때 단추가 아니라 고르는 칸이 줄어들게.
        row = tk.Frame(f, bg=U.BG)
        row.pack(side="bottom", fill="x", pady=(10, 0))
        self.save_btn = U.PushButton(row, "저장", self.save, height=34, font=U.FONT_B)
        self.save_btn.pack(side="right")
        self.cancel_btn = U.ghost_button(row, "취소", self.close, height=34)
        self.cancel_btn.pack(side="right", padx=(0, 8))
        self.random_btn = U.ghost_button(row, "무작위", self.randomize, height=34)
        self.random_btn.pack(side="left")
        self.undo_btn = U.ghost_button(row, "되돌리기", self.undo, height=34)
        self.undo_btn.pack(side="left", padx=(8, 0))
        self.reset_btn = U.ghost_button(row, "초기화", self.reset, height=34)
        self.reset_btn.pack(side="left", padx=(8, 0))
        self.note = tk.Label(f, text=" ", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w",
                             justify="left", wraplength=W - 60)
        self.note.pack(side="bottom", fill="x", pady=(8, 0))

        # 탭은 창 폭을 다 쓴다 - 여덟 칸이라 오른쪽 칸 안에 두면 글꼴이 클 때 끝이 잘린다.
        self.seg = U.Segmented(f, TABS, self.tab, self.show_tab)
        self.seg.frame.pack(anchor="w")
        mid = tk.Frame(f, bg=U.BG)
        mid.pack(fill="both", expand=True, pady=(12, 0))
        left = tk.Frame(mid, bg=U.BG)
        left.pack(side="left", anchor="n", padx=(0, 16))
        self._preview(left)
        right = tk.Frame(mid, bg=U.BG)
        right.pack(side="left", fill="both", expand=True)
        self.inner, self.cv = scroll_body(right)
        self.inner.columnconfigure(0, weight=1)
        self.inner.rowconfigure(0, weight=1)
        for key, _name in TABS:
            self._page(key)
        self.paint()
        self.say("")
        # 창 높이는 가장 큰 탭(머리 - 종류가 가장 많다)에 맞춰진다. 그보다 화면이 낮으면 안쪽이 굴러간다.
        fit(self.win, hi=MAX_H, scroll=(self.cv, self.inner))
        self.show_tab(self.tab)
        self._walk()

    # ---------------- 미리보기 ----------------
    def _preview(self, parent):
        box = tk.Frame(parent, bg=TILE, highlightthickness=1, highlightbackground=U.LINE)
        box.pack()
        # 그림 라벨은 여백을 0 으로 둔다 (tk 기본은 1) - 그림 크기가 곧 칸 크기가 되게.
        self.big = tk.Label(box, bg=TILE, bd=0, padx=0, pady=0)
        self.big.pack(padx=10, pady=(8, 0))
        small = tk.Frame(box, bg=TILE)
        small.pack(pady=(0, 8))
        self.side = tk.Label(small, bg=TILE, bd=0, padx=0, pady=0)
        self.side.pack(side="left")
        self.rear = tk.Label(small, bg=TILE, bd=0, padx=0, pady=0)
        self.rear.pack(side="left")
        tk.Label(parent, text="앞 · 옆 · 뒤", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS).pack(
            pady=(6, 0))

    def _frames(self):
        """지금 고른 것의 걷는 그림을 미리 만들어 둔다. 걸을 때는 갈아 끼우기만 한다."""
        spec = self.model.spec
        out = {}
        for name, direction, k in (("big", "down", BIG), ("side", "left", SMALL), ("rear", "up", SMALL)):
            cells = dict((fr, to_photo(A.scale(A.cell(spec, direction, fr), k))) for fr in set(WALK))
            out[name] = [cells[fr] for fr in WALK]
        self._keep["walk"] = out

    def _show_frame(self):
        fr = self._keep.get("walk")
        if not fr:
            return
        i = self._tick % len(WALK)
        self.big.configure(image=fr["big"][i])
        self.side.configure(image=fr["side"][i])
        self.rear.configure(image=fr["rear"][i])

    def _walk(self):
        if not self.alive:
            return
        try:
            self._tick += 1
            self._show_frame()
            self._after = self.win.after(STEP_MS, self._walk)
        except tk.TclError:
            self.alive = False

    # ---------------- 고르는 칸 ----------------
    def _page(self, tab):
        page = tk.Frame(self.inner, bg=U.BG)
        # 여덟 장이 같은 자리를 **꽉 채워** 겹친다. 작은 탭을 올렸을 때 뒤의 큰 탭이 비치지 않게.
        page.grid(row=0, column=0, sticky="nsew")
        self.pages[tab] = page
        options = options_of(tab)
        self.tiles[tab] = {}
        if options:
            U.marker_label(page, "종류", bg=U.BG, color=U.FG).pack(anchor="w")
            grid = tk.Frame(page, bg=U.BG)
            grid.pack(anchor="w", pady=(8, 0))
            made = []
            for value, label in options:
                cell = tk.Frame(grid, bg=TILE, highlightthickness=2, highlightbackground=U.LINE,
                                cursor="hand2")
                art = tk.Label(cell, bg=TILE, bd=0, padx=0, pady=0, cursor="hand2")
                art.pack(padx=6, pady=(2, 0))
                name = tk.Label(cell, text=label, bg=TILE, fg=U.FG_DIM, font=U.FONT_XS, cursor="hand2")
                name.pack(padx=4, pady=(0, 4))
                for w in (cell, art, name):
                    w.bind("<Button-1>", lambda _e, t=tab, v=value: self.pick(t, v))
                self.tiles[tab][value] = (cell, art, name)
                made.append((cell, name))
            # 칸의 폭 = 그림과 가장 긴 이름 중 넓은 쪽 (+ 테두리). 그 폭으로 한 줄에 몇 칸인지 정한다.
            tile_w = max([THUMB * A.CELL + 12] + [n.winfo_reqwidth() + 8 for _c, n in made]) + 4
            cols = columns(tile_w)
            self.cols[tab] = cols
            for i, (cell, _n) in enumerate(made):
                cell.grid(row=i // cols, column=i % cols, padx=(0, GAP), pady=(0, GAP), sticky="nsew")
            for c in range(cols):
                grid.columnconfigure(c, uniform="tile")
        colors = swatches(tab)
        self.dots[tab] = {}
        if colors:
            U.marker_label(page, "색", bg=U.BG, color=U.FG).pack(anchor="w", pady=(10 if options else 0, 0))
            hold = tk.Frame(page, bg=U.BG)
            hold.pack(anchor="w", pady=(8, 0), fill="x")
            row = tk.Frame(hold, bg=U.BG)
            row.pack(anchor="w")
            for i, (name, hexa) in enumerate(colors):
                dot = tk.Frame(row, bg=hexa, width=SWATCH, height=SWATCH, highlightthickness=3,
                               highlightbackground=U.BG, cursor="hand2")
                dot.grid(row=i // SWATCH_ROW, column=i % SWATCH_ROW, padx=(0, 6), pady=(0, 6))
                dot.bind("<Button-1>", lambda _e, k=color_key(tab), v=name: self.pick(k, v))
                self.dots[tab][name] = dot
            what = dict(TABS).get(tab, "")
            hint = tk.Label(hold, text="%s 고르면 색을 바꿀 수 있습니다." % natural("%s을(를)" % what),
                            bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w")
            self.dot_rows[tab] = (row, hint)

    def show_tab(self, tab):
        self.tab = tab
        self.seg.set(tab)
        self.pages[tab].tkraise()
        self._paint_tiles(tab)
        try:
            self.cv.yview_moveto(0)
        except tk.TclError:
            pass

    def _paint_tiles(self, tab):
        """그 탭의 칸마다 '이것만 바꾼 내 캐릭터' 를 그리고, 지금 고른 칸에 금테를 두른다."""
        spec = self.model.spec
        keep = self._keep.setdefault("tiles", {})
        direction = THUMB_DIR.get(tab, "down")
        for value, (cell, art, name) in self.tiles.get(tab, {}).items():
            ph = to_photo(A.scale(A.cell(thumb_spec(spec, tab, value), direction, "stand"), THUMB))
            keep[(tab, value)] = ph
            art.configure(image=ph)
            on = spec.get(tab) == value
            cell.configure(highlightbackground=U.ACCENT if on else U.LINE)
            name.configure(fg=U.FG if on else U.FG_DIM)

    def _paint_colors(self):
        spec = self.model.spec
        for tab, dots in self.dots.items():
            now = spec.get(color_key(tab))
            for name, dot in dots.items():
                dot.configure(highlightbackground=U.ACCENT if name == now else U.BG)
            row, hint = self.dot_rows[tab]
            if paintable(spec, tab):
                hint.pack_forget()
                row.pack(anchor="w")
            else:
                row.pack_forget()
                hint.pack(anchor="w")

    def paint(self):
        """고른 것이 바뀌었다: 미리보기와 지금 탭의 칸을 다시 그린다."""
        self._frames()
        self._show_frame()
        self._paint_tiles(self.tab)
        self._paint_colors()
        self.undo_btn.configure(state="normal" if self.model.history else "disabled")
        self.reset_btn.configure(state="disabled" if self.model.plain else "normal")

    # ---------------- 하는 일 ----------------
    def say(self, text, color=None):
        if not self.alive:
            return
        if not text:
            if self.drawn:
                # 저장하면 꾸민 캐릭터로 바뀐다는 것을 미리 알린다 (넣어 둔 도트는 지워지지 않는다)
                text = ("지금은 직접 그린 도트를 쓰고 있습니다. 저장하면 이 꾸민 캐릭터로 바뀝니다 "
                        "(넣어 둔 도트는 남아 있어서 마이페이지에서 다시 고를 수 있습니다).")
            elif self.model.dirty:
                text = "저장을 누르면 마이페이지의 닉네임 옆에 이 캐릭터가 보입니다."
            else:
                text = "지금 쓰고 있는 캐릭터입니다."
        try:
            self.note.configure(text=natural(text), fg=color or U.FG_FAINT)
        except tk.TclError:
            pass

    def pick(self, key, value):
        if self.busy:
            return
        if self.model.pick(key, value):
            self.paint()
            self.say("")

    def randomize(self):
        if not self.busy and self.model.randomize():
            self.paint()
            self.say("")

    def undo(self):
        if not self.busy and self.model.undo():
            self.paint()
            self.say("")

    def reset(self):
        """초기화: 기본 캐릭터로 돌려놓는다. 저장을 눌러야 반영된다 (되돌리기로 무를 수 있다)."""
        if not self.busy and self.model.reset():
            self.paint()
            self.say("기본 캐릭터로 돌려놓았습니다. 저장을 눌러야 반영됩니다." if self.model.dirty
                     else "기본 캐릭터로 돌려놓았습니다.")

    def save(self):
        if self.busy:
            return
        if not self.model.dirty and not self.drawn:
            return self.close()
        self.busy = True
        self.save_btn.configure(state="disabled")
        self.say("저장하는 중...")
        spec = dict(self.model.spec)
        api = self.app.api

        def done(r, err):
            self.busy = False
            if not self.alive:
                return
            if err:
                self.save_btn.configure(state="normal")
                return self.say(_err(err), U.DANGER)
            av = (r or {}).get("avatar") or {"spec": spec}
            self.model.mark_saved(av.get("spec"))
            if self.on_saved:
                self.on_saved(av)
            self.close()
        run_async(self.root, lambda: api.avatar_save(spec), done)

    def close(self):
        self.alive = False
        try:
            if self._after:
                self.win.after_cancel(self._after)
        except tk.TclError:
            pass
        try:
            self.win.destroy()
        except tk.TclError:
            pass


def open_editor(parent, app, avatar=None, on_saved=None):
    """꾸미기 창을 띄운다. avatar 는 서버가 준 것({"spec": ...}) 또는 None(처음 만든다)."""
    return Editor(parent, app, avatar, on_saved)
