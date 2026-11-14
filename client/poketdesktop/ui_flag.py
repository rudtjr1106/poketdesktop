# -*- coding: utf-8 -*-
"""길드 깃발 그리기 창 (2.5.0, 시즌 6).

2026-11-14 사용자: "길드 상점에 길드 깃발 - 아이콘인데 사람들이 자유롭게 도트로 만들 수 있는 거야, 픽셀로 그림
그릴 수 있게." 설계: design-notes/2026-11-14-guild-flag.md '앱'. 길드마다 깃발 하나 - 마스터 · 부마스터가 길드 창
'관리' 탭의 [깃발 그리기] 로 이 창을 연다 (11/15 사용자: 코인으로 사지 않고 그냥 - 처음엔 코인 상점 상품이었다).

    왼쪽   24 x 24 칸 (누르거나 누른 채 끌어서 칠한다). 투명 칸은 바둑판 무늬
           그 아래 되돌리기 · 다시 하기 · 모두 지우기 (맥 ⌘Z · ⌘⇧Z, 윈도우 Ctrl+Z · Ctrl+Y)
    오른쪽 도구 (펜 · 지우개 · 채우기 · 스포이드) · 빛깔 32 + 투명 · 미리보기 (1배 · 2배, 밝은 · 어두운 바탕)
    아래   알림 줄 / 닫기 · 저장

지금 길드 깃발을 불러와 시작한다. 그림 꼴은 common/flag.py ('.' 투명, '0'~'v' = PALETTE 32색). 저장하면
api.guild_flag(576자) - 다 지우고 저장하면 깃발이 내려간다. 안 저장한 그림이 있으면 닫을 때 묻는다.

**칠할 때는 바뀐 칸의 사각형 빛깔만 바꾼다** (itemconfigure). 맥 Tk 는 캔버스를 통째로 다시 칠하므로, 칸을 지우고
새로 그리면 끌 때마다 도형이 쌓이고 그만큼 느려진다 (2.1.0 의 맥 캔버스 비용). 576칸은 창을 열 때 한 번만 만든다.

창은 내용만큼 크다 (_fit). 칸 크기는 화면 높이에 맞춰 CELL_MIN~CELL_MAX 에서 고른다 - 그림이라 글자 크기를
따르지 않는다. 기본 테마 부품(U.*)으로만 짓는다 - DP 계열 테마에서도 같은 창이 뜬다.
"""
import tkinter as tk

from common import flag as F
from common.korean import natural

from . import ui_box
from . import ui_common as U
from .ui_common import run_async

TITLE = "길드 깃발 그리기"
TOOLS = (("pen", "펜"), ("eraser", "지우개"), ("fill", "채우기"), ("picker", "스포이드"))
CELL_MAX, CELL_MIN = 18, 10        # 칸 하나의 px. 화면 높이에 맞춰 이 사이에서 고른다
SWATCH = 20                        # 팔레트 한 칸의 px (테 빼고)
PAL_COLS = 8
START_COLOR = 27                   # 처음 고른 빛깔 (빨강 - 어두운 바둑판에서도 잘 보인다)
UNDO_MAX = 200                     # 되돌리기를 이만큼까지 기억한다
CHECK = (U.BG2, U.BG3)             # 투명 칸의 바둑판 (기본 테마의 빛깔)
LIGHT_BG, DARK_BG = U.FG, U.INK    # 미리보기 바탕 (밝은 · 어두운)
HELP = "칸을 누르거나 누른 채 끌어서 칠합니다. 깃발은 길드 이름 옆에 보입니다."
UNSAVED = "저장하지 않은 그림이 있습니다. 저장하지 않고 닫을까요?"
BLANK_SAVE = "그림이 비어 있습니다. 저장하면 길드 깃발이 내려가서 길드 이름 옆에서 없어집니다. 저장할까요?"

# 되돌리기 · 다시 하기 글쇠. 글쇠 이름이 아니라 **자리**로도 본다 - 자판이 한글이면 Z 자리가 'ㅋ', Y 자리가 'ㅛ'
# 로 들어온다 (ui_common.edit_event_for 와 같은 까닭). 맥 keycode 는 (자리 << 24) | 글자 (Tk 8.6.11~).
_KEY_BY_CHAR = {"z": "z", "ㅋ": "z", "y": "y", "ㅛ": "y"}
_MAC_VK = {6: "z", 16: "y"}
_WIN_VK = {90: "z", 89: "y"}


def key_action(keysym, char, keycode, shift, mac):
    """⌘/Ctrl 과 같이 눌린 글쇠가 되돌리기('undo') · 다시 하기('redo') 인가. 아니면 None.

    Z = 되돌리기, Shift+Z · Y = 다시 하기 (맥은 ⌘⇧Z, 윈도우는 Ctrl+Y 가 버릇 - 둘 다 받는다)."""
    key = None
    for c in ((keysym or "").lower(), (char or "").lower()):
        if c in _KEY_BY_CHAR:
            key = _KEY_BY_CHAR[c]
            break
    if key is None:
        try:
            kc = int(keycode)
        except (TypeError, ValueError):
            kc = 0
        if mac:
            try:
                key = _KEY_BY_CHAR.get(chr(kc & 0xFFFF))
            except ValueError:
                key = None
            if key is None and kc >> 24:
                key = _MAC_VK.get((kc >> 24) & 0xFF)
        else:
            key = _WIN_VK.get(kc)
    if key == "z":
        return "redo" if shift else "undo"
    if key == "y":
        return "redo"
    return None


def shortcut_text(mac):
    return "되돌리기 ⌘Z · 다시 하기 ⌘⇧Z" if mac else "되돌리기 Ctrl+Z · 다시 하기 Ctrl+Y"


def line_cells(x0, y0, x1, y1):
    """(x0, y0) 에서 (x1, y1) 까지 이어지는 칸들 (끝 둘 다 넣는다) - 빨리 끌어도 칸이 비지 않게."""
    out = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        out.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return out
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def cell_size(room_w, room_h, other_w, other_h, side_h):
    """칸 하나의 px: 창이 화면(room_w x room_h) 안에 들어가는 가장 큰 값 (CELL_MIN~CELL_MAX).

    other_w · other_h = 판을 뺀 나머지가 차지하는 폭 · 높이, side_h = 오른쪽 기둥의 높이 (판이 이보다 낮으면 높이는
    기둥이 정한다)."""
    for c in range(CELL_MAX, CELL_MIN, -1):
        side = F.SIZE * c + 1
        if other_w + side <= room_w and other_h + max(side, side_h) <= room_h:
            return c
    return CELL_MIN


def color_of(ch):
    """깃발 글자 하나의 빛깔 '#rrggbb' (투명이면 None)."""
    return None if ch == F.EMPTY else F.PALETTE[F.DIGITS.index(ch)]


class FlagEditor(object):
    """깃발 그리기 창 하나. on_saved(서버 답) 은 저장이 될 때마다 부른다 (길드 창이 다시 받는다)."""

    def __init__(self, parent, app, pixels=None, on_saved=None, on_close=None):
        self.app = app
        self.root = app.root
        self.on_saved = on_saved
        self.on_close = on_close
        self.alive = True
        start = pixels if (pixels and F.valid(pixels)) else F.BLANK
        self.cells = list(start)
        self.saved = start               # 서버에 있는 그림 (이것과 다르면 '안 저장한 것이 있다')
        self.undo_stack = []
        self.redo_stack = []
        self.tool = "pen"
        self.color = START_COLOR         # 빛깔 번호 (None = 투명)
        self._before = None              # 누르고 끄는 동안: 누르기 전 그림 (뗄 때 한 걸음으로 기억한다)
        self._last = None                # 끄는 동안 마지막 칸
        self._busy = False
        self._states = {}                # 단추의 켜짐 (바뀔 때만 다시 칠한다)

        self.win, f = ui_box._shell(parent, TITLE, 640, 560)
        self.win.withdraw()              # 다 지은 뒤 내용만큼 잡고 띄운다 (깜빡이지 않게)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.mac = self.win.tk.call("tk", "windowingsystem") == "aqua"
        except tk.TclError:
            self.mac = False
        self.cell = CELL_MIN             # 먼저 가장 작게 짓고, 나머지를 재서 화면에 맞게 키운다 (_grow_board)

        main = tk.Frame(f, bg=U.BG)
        main.pack(fill="x")
        left = tk.Frame(main, bg=U.BG)
        left.pack(side="left", anchor="n")
        right = tk.Frame(main, bg=U.BG)
        right.pack(side="left", anchor="n", padx=(U.h(20), 0))
        self._build_board(left)
        self._build_edit(left)
        self._build_tools(right)
        self._build_palette(right)
        self._build_preview(right)
        self._grow_board(main, left, right)
        wide = main.winfo_reqwidth()
        self.help = tk.Label(f, text=HELP, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left",
                             wraplength=wide)
        self.help.pack(fill="x", pady=(0, U.h(12)), before=main)
        self.status = U.status_line(f, "")
        self.status.pack(fill="x", pady=(U.h(14), 0))
        self.status._label.configure(anchor="w", justify="left", wraplength=max(120, wide - 24))
        bottom = tk.Frame(f, bg=U.BG)
        bottom.pack(fill="x", pady=(U.h(12), 0))
        self.b_save = U.PushButton(bottom, "저장", self.save, height=34, font=U.FONT_B)
        self.b_save.pack(side="right")
        self.b_close = U.ghost_button(bottom, "닫기", self.close, height=34)
        self.b_close.pack(side="right", padx=(0, 8))

        for i in range(F.SIZE * F.SIZE):
            self._show(i)
        self._paint_swatches()
        self._paint_buttons()
        seq = "<Mod1-KeyPress>" if self.mac else "<Control-KeyPress>"
        self.win.bind(seq, self._on_key)
        self.win.bind("<Escape>", lambda _e: self.close())
        self._fit()
        self.win.deiconify()
        self.win.after(60, self.focus)

    # ---------------------------------------------------------------- 짓기
    def _build_board(self, parent):
        n, c = F.SIZE, self.cell
        side = n * c + 1
        frame = tk.Frame(parent, bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2, bd=0)
        frame.pack(anchor="w")
        self.board = tk.Canvas(frame, width=side, height=side, bg=U.LINE, highlightthickness=0, bd=0,
                               cursor="crosshair")
        self.board.pack()
        self.rects = [self.board.create_rectangle((i % n) * c, (i // n) * c, (i % n) * c + c, (i // n) * c + c,
                                                  outline=U.LINE, width=1) for i in range(n * n)]
        self.board.bind("<ButtonPress-1>", self._press)
        self.board.bind("<B1-Motion>", self._drag)
        self.board.bind("<ButtonRelease-1>", self._release)

    def _grow_board(self, main, left, right):
        """칸 크기를 화면에 맞춘다: 나머지(글 · 단추 · 기둥)를 재고, 창이 작업 영역에 들어가는 가장 큰 칸으로."""
        try:
            main.update_idletasks()
            room_w, room_h = U.work_size(self.win)
            side = F.SIZE * self.cell + 1
            other_w = main.winfo_reqwidth() - side + U.h(36) + 8           # 판 밖의 폭 + 창 안쪽 여백 · 테
            # 판 아래 · 위 (단추 줄 · 알림 · 저장 줄 · 머리띠) - 아직 안 지은 것은 넉넉히 어림한다
            other_h = left.winfo_reqheight() - side + U.h(34 + 32 + 40 + 60 + 50) + 8
            c = cell_size(room_w, room_h, other_w, other_h, right.winfo_reqheight())
        except tk.TclError:
            return
        if c == self.cell:
            return
        self.cell = c
        n, side = F.SIZE, F.SIZE * c + 1
        self.board.configure(width=side, height=side)
        for i, r in enumerate(self.rects):
            x, y = (i % n) * c, (i // n) * c
            self.board.coords(r, x, y, x + c, y + c)
        main.update_idletasks()

    def _build_edit(self, parent):
        row = tk.Frame(parent, bg=U.BG)
        row.pack(fill="x", pady=(U.h(10), 0))
        self.b_undo = U.ghost_button(row, "되돌리기", self.undo, height=30)
        self.b_undo.pack(side="left")
        self.b_redo = U.ghost_button(row, "다시 하기", self.redo, height=30)
        self.b_redo.pack(side="left", padx=(6, 0))
        self.b_clear = U.ghost_button(row, "모두 지우기", self.clear, height=30)
        self.b_clear.pack(side="right", padx=(12, 0))
        tk.Label(parent, text=shortcut_text(self.mac), bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS,
                 anchor="w").pack(fill="x", pady=(U.h(6), 0))

    def _build_tools(self, parent):
        U.marker_label(parent, "도구", bg=U.BG, color=U.FG).pack(anchor="w", pady=(0, U.h(6)))
        self.seg = U.Segmented(parent, TOOLS, self.tool, self.set_tool)
        self.seg.frame.pack(anchor="w")

    def _build_palette(self, parent):
        U.marker_label(parent, "빛깔", bg=U.BG, color=U.FG).pack(anchor="w", pady=(U.h(14), U.h(6)))
        grid = tk.Frame(parent, bg=U.BG)
        grid.pack(anchor="w")
        self.swatches = {}
        for k, col in enumerate(F.PALETTE):
            sw = self._swatch(grid, col)
            sw.grid(row=k // PAL_COLS, column=k % PAL_COLS, padx=1, pady=1)
            sw.bind("<Button-1>", lambda _e, k=k: self.pick_color(k))
            self.swatches[k] = sw
        row = tk.Frame(parent, bg=U.BG)
        row.pack(anchor="w", pady=(U.h(4), 0))
        sw = self._swatch(row, CHECK[0])
        half = SWATCH // 2
        sw.create_rectangle(half, 0, SWATCH, half, fill=CHECK[1], outline="")
        sw.create_rectangle(0, half, half, SWATCH, fill=CHECK[1], outline="")
        sw.create_line(1, SWATCH - 1, SWATCH - 1, 1, fill=U.DANGER, width=2)
        sw.pack(side="left", padx=1)
        sw.bind("<Button-1>", lambda _e: self.pick_color(None))
        self.swatches[None] = sw
        tk.Label(row, text="투명 (칸을 비웁니다)", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS).pack(side="left", padx=(6, 0))

    def _swatch(self, parent, color):
        # 캔버스는 width 가 테 안쪽의 폭이다 (테 2px 은 바깥에 붙는다) - 투명 칸의 무늬를 0~SWATCH 에 그린다
        return tk.Canvas(parent, width=SWATCH, height=SWATCH, bg=color, highlightthickness=2,
                         highlightbackground=U.BG, bd=0, cursor="hand2")

    def _build_preview(self, parent):
        head = tk.Frame(parent, bg=U.BG)
        head.pack(anchor="w", fill="x", pady=(U.h(14), U.h(6)))
        U.marker_label(head, "미리보기", bg=U.BG, color=U.FG).pack(side="left")
        tk.Label(head, text="1배 · 2배", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left", padx=(8, 0))
        n = F.SIZE
        self.p1 = tk.PhotoImage(master=self.win, width=n, height=n)
        self.p2 = tk.PhotoImage(master=self.win, width=n * 2, height=n * 2)
        row = tk.Frame(parent, bg=U.BG)
        row.pack(anchor="w")
        self.previews = []               # [(바탕, 1배 라벨, 2배 라벨)]
        for k, (bg, name) in enumerate(((LIGHT_BG, "밝은 바탕"), (DARK_BG, "어두운 바탕"))):
            col = tk.Frame(row, bg=U.BG)
            col.pack(side="left", padx=(0 if not k else U.h(10), 0), anchor="n")
            box = tk.Frame(col, bg=bg, highlightthickness=1, highlightbackground=U.LINE2, bd=0)
            box.pack(anchor="w")
            l1 = tk.Label(box, image=self.p1, bg=bg, bd=0, highlightthickness=0)
            l1.pack(side="left", padx=(8, 8), pady=8, anchor="s")
            l2 = tk.Label(box, image=self.p2, bg=bg, bd=0, highlightthickness=0)
            l2.pack(side="left", padx=(0, 8), pady=8)
            tk.Label(col, text=name, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS).pack(anchor="w", pady=(3, 0))
            self.previews.append((bg, l1, l2))

    # ---------------------------------------------------------------- 그림
    @property
    def pixels(self):
        return "".join(self.cells)

    def dirty(self):
        """서버에 있는 것과 다른가 (안 저장한 것이 있나)."""
        return self.pixels != self.saved

    def _show(self, i):
        """칸 하나를 보이는 대로 - 캔버스 사각형의 빛깔과 미리보기 그림의 그 점만 고친다."""
        n = F.SIZE
        x, y = i % n, i // n
        color = color_of(self.cells[i])
        try:
            self.board.itemconfigure(self.rects[i], fill=color or CHECK[(x + y) % 2])
            for img, k in ((self.p1, 1), (self.p2, 2)):
                if color:
                    img.put(color, to=(x * k, y * k, x * k + k, y * k + k))
                else:
                    for dx in range(k):
                        for dy in range(k):
                            img.tk.call(img.name, "transparency", "set", x * k + dx, y * k + dy, 1)
        except tk.TclError:
            pass

    def _set(self, x, y, ch):
        i = y * F.SIZE + x
        if self.cells[i] == ch:
            return False
        self.cells[i] = ch
        self._show(i)
        return True

    def _load(self, pixels):
        """그림을 통째로 바꾼다 (되돌리기 · 다시 하기 · 모두 지우기 · 채우기) - 다른 칸만 고친다."""
        for i, ch in enumerate(pixels):
            if self.cells[i] != ch:
                self.cells[i] = ch
                self._show(i)

    def _remember(self, before):
        """한 걸음을 기억한다 (되돌리기용). 새 걸음을 두면 다시 하기는 사라진다."""
        self.undo_stack.append(before)
        if len(self.undo_stack) > UNDO_MAX:
            del self.undo_stack[0]
        self.redo_stack = []

    def _ink(self):
        """지금 도구 · 빛깔로 칠할 글자."""
        if self.tool == "eraser" or self.color is None:
            return F.EMPTY
        return F.DIGITS[self.color]

    def cell_at(self, x, y):
        """캔버스 위 자리 -> (칸 x, 칸 y). 판 밖이면 None."""
        try:
            cx, cy = int(self.board.canvasx(x)) // self.cell, int(self.board.canvasy(y)) // self.cell
        except tk.TclError:
            return None
        if 0 <= cx < F.SIZE and 0 <= cy < F.SIZE:
            return cx, cy
        return None

    def _press(self, e):
        at = self.cell_at(e.x, e.y)
        if at is None:
            return
        self.press_cell(*at)

    def _drag(self, e):
        if self._before is None:
            return
        at = self.cell_at(e.x, e.y)
        if at is None:
            # 판 밖으로 나갔다 - 가장자리까지만 칠한다
            try:
                cx = int(self.board.canvasx(e.x)) // self.cell
                cy = int(self.board.canvasy(e.y)) // self.cell
            except tk.TclError:
                return
            at = (max(0, min(F.SIZE - 1, cx)), max(0, min(F.SIZE - 1, cy)))
        self.drag_cell(*at)

    def _release(self, _e):
        self.end_stroke()

    def press_cell(self, x, y):
        """그 칸을 눌렀다 (도구대로)."""
        if self.tool == "picker":
            ch = self.cells[y * F.SIZE + x]
            self.pick_color(None if ch == F.EMPTY else F.DIGITS.index(ch))
            return self.set_tool("pen")              # 빛깔을 집었으면 바로 칠한다
        if self.tool == "fill":
            before = self.pixels
            after = F.fill(before, x, y, None if self._ink() == F.EMPTY else F.DIGITS.index(self._ink()))
            if after != before:
                self._remember(before)
                self._load(after)
                self._paint_buttons()
            return None
        self._before = self.pixels                   # 펜 · 지우개: 뗄 때까지가 한 걸음
        self._last = (x, y)
        self._set(x, y, self._ink())
        self._paint_buttons()
        return None

    def drag_cell(self, x, y):
        """누른 채 그 칸까지 끌었다 - 지난 칸에서 이어서 칠한다."""
        if self._before is None or (x, y) == self._last:
            return
        ink = self._ink()
        lx, ly = self._last or (x, y)
        changed = False
        for cx, cy in line_cells(lx, ly, x, y):
            changed = self._set(cx, cy, ink) or changed
        self._last = (x, y)
        if changed:
            self._paint_buttons()

    def end_stroke(self):
        before, self._before, self._last = self._before, None, None
        if before is not None and before != self.pixels:
            self._remember(before)
        self._paint_buttons()

    # ---------------------------------------------------------------- 고르기
    def set_tool(self, key):
        if key not in dict(TOOLS):
            return
        self.tool = key
        try:
            self.seg.set(key)
        except tk.TclError:
            pass

    def pick_color(self, index):
        """빛깔을 고른다 (None = 투명). 지우개 · 스포이드를 들고 있었으면 펜으로 바꾼다 - 빛깔을 고르는 것은 칠하려는 것."""
        self.color = index
        if self.tool in ("eraser", "picker"):
            self.set_tool("pen")
        self._paint_swatches()

    def _paint_swatches(self):
        for k, sw in self.swatches.items():
            try:
                sw.configure(highlightbackground=U.ACCENT if k == self.color else U.BG)
            except tk.TclError:
                pass

    # ---------------------------------------------------------------- 되돌리기 · 지우기
    def undo(self):
        if self._before is not None:
            self.end_stroke()
        if not self.undo_stack:
            return
        self.redo_stack.append(self.pixels)
        self._load(self.undo_stack.pop())
        self._paint_buttons()

    def redo(self):
        if self._before is not None:
            self.end_stroke()
        if not self.redo_stack:
            return
        self.undo_stack.append(self.pixels)
        self._load(self.redo_stack.pop())
        self._paint_buttons()

    def clear(self):
        if F.is_blank(self.pixels):
            return
        self._remember(self.pixels)
        self._load(F.BLANK)
        self._paint_buttons()

    def _on_key(self, e):
        act = key_action(e.keysym, e.char, e.keycode, bool(int(e.state) & 0x1), self.mac)
        if act == "undo":
            self.undo()
        elif act == "redo":
            self.redo()
        else:
            return None
        return "break"

    def _paint_buttons(self):
        want = {"undo": bool(self.undo_stack), "redo": bool(self.redo_stack),
                "clear": not F.is_blank(self.pixels), "save": self.dirty() and not self._busy}
        for key, on in want.items():
            if self._states.get(key) == on:
                continue
            self._states[key] = on
            try:
                getattr(self, "b_" + key).configure(state="normal" if on else "disabled")
            except (tk.TclError, AttributeError):
                pass

    # ---------------------------------------------------------------- 저장 · 닫기
    def say(self, text, color=U.GOOD):
        if not self.alive:
            return
        try:
            U.set_status(self.status, natural(text or ""), color)
        except tk.TclError:
            return
        self._fit(keep_pos=True)

    def save(self):
        """서버로 보낸다 (576자). 바뀐 것이 없으면 안 보낸다 - 길드 채팅에 '새로 그렸습니다' 가 괜히 뜨지 않게."""
        if self._busy or not self.alive:
            return
        if self._before is not None:
            self.end_stroke()
        px = self.pixels
        if px == self.saved:
            return self.say("바뀐 것이 없습니다.", U.FG_DIM)
        if F.is_blank(px) and not ui_box.confirm(self.win, TITLE, BLANK_SAVE, danger=True, ok_text="깃발 내리기"):
            return None
        self._busy = True
        self._paint_buttons()
        self.say("저장하는 중...", U.FG_DIM)
        api = self.app.api

        def done(r, err):
            self._busy = False
            if not self.alive:
                return
            if err:
                self._paint_buttons()
                return self.say(getattr(err, "message", None) or str(err), U.DANGER)
            self.saved = px
            self._paint_buttons()
            self.say((r or {}).get("message")
                     or ("길드 깃발을 내렸습니다." if F.is_blank(px) else "길드 깃발을 저장했습니다."), U.GOOD)
            if self.on_saved:
                self.on_saved(r or {})
        return run_async(self.root, lambda: api.guild_flag(px), done)

    def close(self, force=False):
        """닫는다. 안 저장한 그림이 있으면 먼저 묻는다 (force 면 묻지 않는다)."""
        if not self.alive:
            return True
        if not force and self.dirty() and not ui_box.confirm(self.win, TITLE, UNSAVED, danger=True,
                                                             ok_text="저장 안 하고 닫기"):
            return False
        self.alive = False
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        if self.on_close:
            self.on_close()
        return True

    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass

    def _fit(self, keep_pos=False):
        """창을 내용만큼 (폭도 높이도). 떠 있는 창은 자리를 안 옮기고 좁히지도 않는다."""
        try:
            self.win.update_idletasks()
            w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
            if keep_pos:
                w = max(w, self.win.winfo_width())
            U.place_window(self.win, w, h, keep_pos=keep_pos)
        except tk.TclError:
            pass
