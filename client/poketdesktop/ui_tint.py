# -*- coding: utf-8 -*-
"""이로치 포켓몬의 색 고르기 창 (1.8.0, common/tint).

이로치 포켓몬만 연다 (포켓몬 관리 창의 '색 고르기', 바탕화면 도트의 우클릭).
고른 색은 서버에 적혀서 **모든 사람의 화면에** 그 색으로 나온다 - 박스,
바탕화면, 배틀 창, 랭킹전 상대의 화면까지.

## 생김새

    이로치 색 계열   [이로치 색] [색조 7가지]
    기본 색 계열     [기본 색]   [색조 7가지]

색 이름을 글로 적지 않는다. 색조를 45도씩 돌린 것이라 종마다 나오는 색이
다르다 (리자몽의 +90도와 갸라도스의 +90도는 다른 색이다). 그래서 **그
포켓몬의 도트를 그 색으로 칠해서** 보여 주고 눈으로 고르게 한다.

  · 미리보기는 배틀 도트의 첫 장을 색조만 돌려 만든다 (파일을 안 만든다).
    파일은 고른 뒤에 그 색 하나만 만들어진다 (sprite_cache / walk_cache).
  · 칸을 누르면 고른 표시만 바뀐다. '이 색으로' 를 눌러야 서버에 간다 -
    남에게 보이는 것이라 잘못 눌러 바뀌면 안 된다.
"""
import tkinter as tk

from PIL import ImageTk

from common import tint as T
from common.korean import natural

from . import sprite_cache, sprite_tint, sprites
from . import ui_common as U

THUMB = 56                  # 미리보기 도트가 들어갈 칸 (px, U.h 로 늘린다)
GAP = 6                     # 칸 사이
PAD = 18                    # 창 안쪽 여백
ROWS = (
    ("이로치 색 계열", "이로치 색", True),
    ("기본 색 계열", "기본 색", False),
)


def value_of(base, hue):
    """그 칸이 뜻하는 tint 값. 이로치 색 그대로는 None."""
    if not hue:
        return None if base else T.NORMAL
    return "%s%03d" % ("s" if base else "n", hue)


def previews(api, num, box):
    """{tint 값: RGBA 그림}. 작업 스레드에서 부른다."""
    out = {}
    for _title, _name, base in ROWS:
        path = sprite_cache.ensure(api, num, base)
        if not path:
            continue
        frames, _durs = sprites.read_frames(path, max_frames=1)
        im = frames[0]
        bb = im.getbbox()
        if bb:
            im = im.crop(bb)
        k = min(float(box) / max(1, im.width), float(box) / max(1, im.height))
        size = (max(1, int(round(im.width * k))), max(1, int(round(im.height * k))))
        im = sprites._resize(sprites.premultiply(im), size) if k < 1 else sprites._resize(im, size)
        for hue in (0,) + T.HUES:
            out[value_of(base, hue)] = sprite_tint.shift(im, hue)
    return out


class TintPicker(object):

    def __init__(self, app, mon, parent=None, on_done=None):
        self.app = app
        self.root = app.root
        self.mon = mon
        self.on_done = on_done
        self.alive = True
        self.cells = {}             # tint 값 -> 칸(Frame)
        self.photos = {}
        self.current = T.clean(mon.get("tint")) if mon.get("shiny") else None
        self.picked = self.current
        info = mon.get("info") or {}
        self.name = info.get("name") or mon.get("nickname") or "포켓몬"

        # 창 폭은 칸 여덟 개에 맞춘다. 높이는 다 담은 뒤에 잰다 - 글꼴 배율마다
        # 줄 높이가 달라서 숫자로 박아 두면 어느 한쪽에서 단추가 눌린다.
        box = U.h(THUMB)
        cell_w = box + 12 + 4                   # 안쪽 여백 12 + 테두리 2x2
        width = 8 * cell_w + 7 * GAP + PAD * 2 + 8

        self.win = tk.Toplevel(parent or self.root)
        self.win.withdraw()
        U.style_window(self.win, "포스크탑 — 색 고르기")
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        bar = tk.Frame(self.win, bg=U.BG2, height=U.h(34))
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=U.ACCENT, width=3, height=U.h(13)).pack(side="left", padx=(12, 8))
        tk.Label(bar, text="색 고르기", bg=U.BG2, fg=U.FG, font=U.FONT_B).pack(side="left")
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

        f = tk.Frame(self.win, bg=U.BG)
        f.pack(fill="both", expand=True, padx=PAD, pady=(14, 14))
        self.head = tk.Label(f, text=natural("★ %s 의 색을 고릅니다" % self.name),
                             bg=U.BG, fg=U.SHINY, font=U.FONT_B, justify="left", anchor="w")
        self.head.pack(fill="x")
        self.note = tk.Label(
            f, text="고른 색은 내 화면뿐 아니라 친구와 대전 상대의 화면에도 그대로 보입니다.",
            bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, justify="left", anchor="w",
            wraplength=width - PAD * 2 - 8)
        self.note.pack(fill="x", pady=(4, 0))
        self.head.configure(wraplength=width - PAD * 2 - 8)

        # 단추를 먼저 담는다 - 칸들이 자리를 다 먹고 단추를 밀어내지 않게.
        row = tk.Frame(f, bg=U.BG)
        row.pack(side="bottom", fill="x", pady=(12, 0))
        self.ok_btn = U.PushButton(row, "이 색으로", self.apply, height=34, font=U.FONT_B)
        self.ok_btn.pack(side="left")
        U.ghost_button(row, "닫기", self.close, height=34).pack(side="left", padx=8)
        self.status = tk.Label(row, text="불러오는 중...", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S)
        self.status.pack(side="right")
        self.ok_btn.configure(state="disabled")

        self.grid = tk.Frame(f, bg=U.BG)
        self.grid.pack(fill="both", expand=True, pady=(12, 0))
        for title, name, base in ROWS:
            tk.Label(self.grid, text=title, bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
                     anchor="w").pack(fill="x", pady=(6, 4))
            line = tk.Frame(self.grid, bg=U.BG)
            line.pack(fill="x")
            for i, hue in enumerate((0,) + T.HUES):
                v = value_of(base, hue)
                cell = tk.Frame(line, bg=U.BG2, width=box + 12, height=box + 12,
                                highlightthickness=2, highlightbackground=U.BG2,
                                cursor="hand2")
                cell.pack(side="left", padx=(0, GAP if i < 7 else 0))
                cell.pack_propagate(False)
                art = tk.Label(cell, bg=U.BG2, bd=0, cursor="hand2")
                art.pack(expand=True)
                for w in (cell, art):
                    w.bind("<Button-1>", lambda _e, v=v: self.pick(v))
                self.cells[v] = (cell, art)
            # 첫 칸이 무엇인지만 글로 알려 준다 (나머지는 그 색조를 돌린 것)
            tk.Label(self.grid, text="맨 앞이 %s, 나머지는 그 색조를 돌린 것" % name,
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w").pack(fill="x", pady=(3, 0))
        self._paint()

        # 다 담았다. 필요한 높이를 재서 그만큼만 잡는다.
        self.win.update_idletasks()
        U.style_window(self.win, "포스크탑 — 색 고르기", width,
                       self.win.winfo_reqheight() + 4)
        self.win.deiconify()

        api, num = app.api, mon.get("num")
        U.run_async(self.root, lambda: previews(api, num, box), self._loaded)

    # ---------------- 그리기 ----------------
    def _loaded(self, imgs, err):
        if not self.alive:
            return
        if err or not imgs:
            self.status.configure(text="도트를 받지 못했습니다.", fg=U.DANGER)
            return
        for v, im in imgs.items():
            got = self.cells.get(v)
            if got is None:
                continue
            ph = ImageTk.PhotoImage(im)
            self.photos[v] = ph
            try:
                got[1].configure(image=ph)
            except tk.TclError:
                return
        self.status.configure(text="")
        self._paint()

    def _paint(self):
        for v, (cell, _art) in self.cells.items():
            on = (v == self.picked)
            try:
                cell.configure(highlightbackground=U.ACCENT if on else
                               (U.LINE2 if v == self.current else U.BG2))
            except tk.TclError:
                return
        ready = bool(self.photos)
        self.ok_btn.configure(
            state="normal" if ready and self.picked != self.current else "disabled")

    def pick(self, v):
        if v not in self.cells or v not in self.photos:
            return
        self.picked = v
        self.status.configure(text="", fg=U.FG_FAINT)
        self._paint()

    # ---------------- 보내기 ----------------
    def apply(self):
        if self.picked == self.current:
            return
        v = self.picked
        self.ok_btn.configure(state="disabled")
        self.status.configure(text="바꾸는 중...", fg=U.FG_FAINT)
        pid = self.mon["id"]
        U.run_async(self.root, lambda: self.app.api.set_tint(pid, v),
                    lambda r, err: self._applied(v, r, err))

    def _applied(self, v, r, err):
        if not self.alive:
            return
        if err:
            self.status.configure(text=natural(getattr(err, "message", str(err))), fg=U.DANGER)
            self._paint()
            return
        self.current = v
        self.mon["tint"] = v
        cb = self.on_done
        self.close()
        if cb:
            try:
                cb((r or {}).get("pokemon"))
            except Exception:                               # noqa: BLE001
                pass

    def close(self):
        if not self.alive:
            return
        self.alive = False
        try:
            self.win.destroy()
        except tk.TclError:
            pass
