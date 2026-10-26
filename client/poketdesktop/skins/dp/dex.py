# -*- coding: utf-8 -*-
"""DP 테마 - 도감.

DP 의 빨간 도감처럼 - 몸체는 빨강, 화면 두 개 (v2, 2026-10-25):

    ┌ 빨간 띠: (렌즈) 도감 · [잡음 106 / 1025] · 본 것 ──────────── [칭호] [업적] [새로고침] ┐
    │ [전체|1세대|…|9세대]   [전부|잡은 것|아직]   찾기 [       ]                              │
    │ ┌ 왼쪽 화면 ─────────────┐ ┌ 오른쪽 화면: 번호 목록 (창 폭만큼 여러 칸) ──────────────┐ │
    │ │  큰 도트                │ │ ● 0001 (도트) 이상해씨 │ ● 0002 (도트) 이상해풀 │ ...   │ │
    │ │  No.0006  리자몽         │ │   0003 (도트) 이상해꽃 │   0004 (도트) 파이리   │ ...   │ │
    │ │  화염포켓몬 · 불꽃 비행   │ │  (고른 칸은 빨간 네모 커서)                              │ │
    │ └─────────────────────────┘ └────────────────────────────────────────────────────────┘ │

v2 에서 바꾼 것: 바탕 줄무늬 · 도트 무대의 격자 · 세 겹 화면 테 · 테두리 글씨를 걷고, 잡은 표시는 앱의 몬스터볼
도구 그림을 쓴다 (직접 그리지 않는다). 번호 목록은 한 줄에 한 마리였던 것을 창 폭만큼 여러 칸으로 - 기본 도감
격자만큼(40마리 남짓) 한 화면에 보인다.

동작은 기본 도감(ui_dex.DexWindow)의 것을 그대로 쓴다 - 서버의 본 것 · 잡은 것, 세대 · 잡은 것 · 찾기로
거르기, 보이는 칸의 도트만 받기, 업적 · 칭호 칸.
"""
import tkinter as tk

from PIL import Image, ImageTk

from ... import item_icons
from ... import sprite_cache
from ... import ui_common as U
from ... import ui_dex as DX
from . import CUR, DIM, FAINT, HOVER, INK, INK2, WHITE, font
from . import poke_icons
from . import kit as K
from .achievements import lcd
from .scene import Scene, T

RED, RED_D = "#d83c3c", "#a42424"
SCREEN, FRAME = "#eef4e8", "#3a1414"            # 도감 화면 (테 한 겹)
STAGE, STAGE_LINE = "#ffffff", "#b8c8b0"        # 큰 도트 무대
CELL_PX = 160                                   # 번호 목록 한 칸의 폭 (U.h - 이만큼씩 칸을 늘린다)


def _ball(px):
    """잡은 표시 - 앱의 몬스터볼 도구 그림. 아직 못 받았으면 본가 몬스터볼 그림."""
    return item_icons.photo("POKEBALL", px) or poke_icons.photo("poke-ball")


class DexWindow(Scene, DX.DexWindow):

    def _build(self):
        self._sel = None
        self._big = {}             # 번호 -> 큰 도트
        self._big_busy = set()
        self._cols = 1
        self.ROW_H = U.h(30)
        self.win.configure(bg=RED, highlightthickness=0)
        # 머리 (빨간 띠) - 업적 · 칭호 칸으로 바꿔도 남는다
        self.hcv = tk.Canvas(self.win, bg=RED, highlightthickness=0, bd=0, height=U.h(58))
        self.hcv.pack(fill="x")
        self.hcv.bind("<Configure>", lambda _e: self._paint_head())
        self.ach_btn = K.CButton(self.hcv, "업적", self.toggle_achievements, "gray", font(10))
        self.title_btn = K.CButton(self.hcv, "칭호", self.toggle_titles, "gray", font(10))
        self.reload_btn = K.CButton(self.hcv, "새로고침", self.reload, "gray", font(10))
        # 몸 (격자 자리 - 업적 · 칭호를 열면 이 자리에 들어간다)
        self.msg = ("", None)
        self._job = None
        self._wins = {}
        self._msg_ids = None
        self.cv = tk.Canvas(self.win, bg=RED, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", lambda _e: self._soon())
        self.dex_body = self.cv
        self.qv = tk.StringVar()
        self.qv.trace_add("write", lambda *_a: self.set_query(self.qv.get()))
        self.find_box = K.entry(self.cv, self.qv, width=12)
        self.vl = K.VList(self.cv, SCREEN, self._draw_row)
        self.vl.on_click = self._click_row
        self.vl.on_scroll = self.fetch_visible
        self.vl.col_of = lambda x: int(x // self._cell_w())

    # ---------------- 기본 도감의 칠하는 자리 ----------------
    def draw(self):
        self.rows = self._species()
        nums = [sp["num"] for sp in self.rows]
        if self._sel not in nums:
            self._sel = nums[0] if nums else None
        self._set_rows(keep=False)
        self._paint_head()
        self._soon()
        self._load_big(self._sel)
        self.root.after_idle(self.fetch_visible)

    def _set_rows(self, keep=True):
        c = max(1, self._cols)
        self.vl.set([(self.ROW_H, self.rows[i:i + c]) for i in range(0, len(self.rows), c)], keep=keep)

    def _cell_w(self):
        try:
            w = self.vl.cv.winfo_width()
        except tk.TclError:
            w = 1
        return max(1, w // max(1, self._cols))

    def visible_nums(self):
        return [sp["num"] for row in self.vl.visible() for sp in row]

    def _icon(self, path):
        try:
            im = Image.open(path)
            im.seek(0)
            im = im.convert("RGBA")
            s = U.h(25)
            im.thumbnail((int(s * 1.3), s), Image.LANCZOS)
            return ImageTk.PhotoImage(im)
        except Exception:                                   # noqa: BLE001
            return None

    def _redraw_cells(self, nums):
        self.vl.refresh()

    def _show_panel(self, which):
        """기본 것 그대로 + 머리 단추를 다시 놓는다 (단추 글이 '도감으로' · '업적 2/5' 로 바뀌면 폭도 바뀐다)."""
        DX.DexWindow._show_panel(self, which)
        self._paint_head()

    def pick(self, num):
        self._sel = num
        self.vl.refresh()
        self._load_big(num)
        self._soon()

    def _click_row(self, row, x, _y, w):
        k = int(x // max(1, w // max(1, self._cols)))
        if 0 <= k < len(row):
            self.pick(row[k]["num"])

    def _load_big(self, n):
        if n is None or n not in self.seen or n in self._big or n in self._big_busy:
            return
        self._big_busy.add(n)
        api = self.app.api
        size = U.h(150)

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
            self._big_busy.discard(n)
            if err or img is None:
                return
            try:
                self._big[n] = ImageTk.PhotoImage(img)
            except Exception:                               # noqa: BLE001
                return
            if n == self._sel:
                self._soon()
        U.run_async(self.root, work, done)

    # ---------------- 목록 한 줄 (칸 여럿) ----------------
    def _draw_row(self, cv, row, x, y, w, h, tags, hover=None):
        cw = max(1, w // max(1, self._cols))
        for k, sp in enumerate(row):
            x1 = x + k * cw
            self._draw_cell(cv, sp, x1, y, cw, h, tags, hover is not None and x1 <= hover < x1 + cw)

    def _draw_cell(self, cv, sp, x, y, w, h, tags, hov):
        n = sp["num"]
        got, seen = n in self.caught, n in self.seen
        sel = n == self._sel
        if hov and not sel:
            cv.create_rectangle(x + 2, y + 1, x + w - 2, y + h - 1, fill=HOVER, outline="", tags=tags)
        m = y + h // 2
        if got:
            ph = _ball(15)
            if ph is not None:
                cv.create_image(x + U.h(12), m, image=ph, tags=tags)
        cv.create_text(x + U.h(22), m, text="%04d" % n, fill=INK2 if seen else FAINT, font=font(9), anchor="w",
                       tags=tags)
        img = self.icons.get(n) if seen else None
        if img is not None:
            cv.create_image(x + U.h(74), m, image=img, tags=tags)
        nx = x + U.h(94)
        if seen:
            name = sp.get("kr") or sp["internal"]
            f = K.tkfont_of(cv, font(11))
            room = x + w - U.h(6) - nx
            if f.measure(name) > room:
                while len(name) > 1 and f.measure(name + "…") > room:
                    name = name[:-1]
                name += "…"
            cv.create_text(nx, m, text=name, fill=INK, font=font(11), anchor="w", tags=tags)
        else:
            cv.create_text(nx, m, text="?????", fill=FAINT, font=font(11), anchor="w", tags=tags)
        if sel:
            cv.create_rectangle(x + 2, y + 1, x + w - 3, y + h - 2, outline=CUR, width=2, tags=tags)

    # ---------------- 머리 ----------------
    def _paint_head(self):
        cv = self.hcv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 50:
            return
        cv.delete("head")
        tg = ("head",)
        cv.create_rectangle(0, 0, W, H, fill=RED, outline="", tags=tg)
        cv.create_rectangle(0, H - 4, W, H, fill=RED_D, outline="", tags=tg)
        # 렌즈 (DP 도감 위쪽의 파란 동그라미)
        r = U.h(15)
        cy = (H - 4) // 2
        lx = U.h(14)
        cv.create_oval(lx, cy - r, lx + 2 * r, cy + r, fill="#58a8f0", outline=WHITE, width=3, tags=tg)
        x = lx + 2 * r + U.h(12)
        cv.create_text(x, cy, text="도감", fill=WHITE, font=font(15), anchor="w", tags=tg)
        x += K.tkfont_of(cv, font(15)).measure("도감") + U.h(14)
        x += lcd(cv, x, cy - U.h(15), cy + U.h(15), "잡음  %d / %d" % (len(self.caught), self.total or 0),
                 font(12), tags=tg) + U.h(12)
        if self.gen:
            g = self.gens.get(str(self.gen)) or {}
            sub = "%d세대  %d / %d  ·  보인 것 %d종" % (self.gen, g.get("caught", 0), g.get("total", 0), len(self.rows))
        else:
            sub = "본 것 %d종  ·  보이는 것 %d종" % (len(self.seen), len(self.rows))
        bh = U.h(34)
        y1 = cy - bh // 2
        x2 = W - U.h(12)
        for b in (self.reload_btn, self.ach_btn, self.title_btn):
            w = b.want_width(U.h(22))
            b.layout(x2 - w, y1, x2, y1 + bh)
            x2 -= w + U.h(8)
        if x2 - x > U.h(60):
            K.text(cv, x, cy, sub, font(10), fill=WHITE, anchor="w", width=x2 - x - U.h(8), tags=tg)

    # ---------------- 몸 ----------------
    def _paint(self):
        self._job = None
        cv = self.cv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 200 or H < 150:
            return
        cv.delete("scene")
        cv.create_rectangle(0, 0, W, H, fill=RED, outline="", tags=T)          # (v2: 줄무늬 없이)
        pad = U.h(14)
        y = U.h(10)
        th = U.h(26)
        # 세대 · 잡은 것 · 찾기 - 한 줄에 다 들어가면 한 줄로 (목록이 한 줄 더 보인다)
        f9 = K.tkfont_of(cv, font(9))
        gap = U.h(4)
        gens_w = sum(f9.measure(lb) + U.h(18) for _k, lb in DX.GENS) + gap * (len(DX.GENS) - 1)
        modes_w = sum(f9.measure(lb) + U.h(18) for _k, lb in DX.MODES) + gap * (len(DX.MODES) - 1)
        find_w = K.tkfont_of(cv, font(10)).measure("찾기") + U.h(10)
        one = pad + gens_w + U.h(16) + modes_w + U.h(18) + find_w + U.h(110) <= W - pad
        self._tabs(cv, pad, y, th, DX.GENS, self.gen, "gen", self.set_gen, spec=font(9),
                   fill_off="#fbe8e8", line_off="#8a2020")
        y2 = y if one else y + th + U.h(6)
        mx = pad + gens_w + U.h(16) if one else pad
        mt = self._tabs(cv, mx, y2, th, DX.MODES, self.mode, "mode", self.set_mode, spec=font(9),
                        fill_off="#fbe8e8", line_off="#8a2020")
        fx = mt[-1][1][2] + U.h(18)
        cv.create_text(fx, y2 + th // 2, text="찾기", fill=WHITE, font=font(10), anchor="w", tags=T)
        fx += K.tkfont_of(cv, font(10)).measure("찾기") + U.h(10)
        self._place("find", self.find_box, fx, y2, max(U.h(100), min(U.h(240), W - pad - fx)), th)
        top = y2 + th + U.h(10)
        bottom = H - U.h(12)
        # 왼쪽 화면 (고른 종)
        LW = max(U.h(240), min(U.h(300), int(W * 0.3)))
        self._screen(cv, pad, top, pad + LW, bottom)
        self._paint_species(cv, pad + U.h(12), top + U.h(12), pad + LW - U.h(12), bottom - U.h(12))
        # 오른쪽 화면 (번호 목록 - 칸 여럿)
        rx1 = pad + LW + U.h(12)
        self._screen(cv, rx1, top, W - pad, bottom)
        lw = W - pad - rx1 - U.h(16)
        cols = max(1, min(4, (lw - U.h(12)) // U.h(CELL_PX)))
        if cols != self._cols:
            self._cols = cols
            self._set_rows(keep=True)
        if self.rows:
            self._place("list", self.vl.frame, rx1 + U.h(8), top + U.h(8), lw, bottom - top - U.h(16))
        else:
            self._hide("list")
            K.text(cv, (rx1 + W - pad) // 2, top + U.h(60), "맞는 포켓몬이 없다.", font(11), anchor="n", tags=T)

    def _screen(self, cv, x1, y1, x2, y2):
        """도감 화면: 짙은 테 한 겹 + 옅은 화면."""
        K.rrect(cv, x1, y1, x2, y2, 10, fill=SCREEN, outline=FRAME, width=3, tags=T)

    def _paint_species(self, cv, x1, y1, x2, y2):
        sp = next((s for s in self.rows if s["num"] == self._sel), None)
        if sp is None:
            K.text(cv, (x1 + x2) // 2, y1 + U.h(60), "목록에서 고르세요", font(11), anchor="n", tags=T)
            return
        n = sp["num"]
        got, seen = n in self.caught, n in self.seen
        cx = (x1 + x2) // 2
        # 도트 무대 (흰 칸 - v2: 격자 무늬 없이)
        sh = min(U.h(180), (y2 - y1) // 2)
        K.rrect(cv, x1, y1, x2, y1 + sh, 6, fill=STAGE, outline=STAGE_LINE, width=1, tags=T)
        img = self._big.get(n) if seen else None
        if img is not None:
            cv.create_image(cx, y1 + sh // 2, image=img, tags=T)
        else:
            cv.create_text(cx, y1 + sh // 2, text="?" if not seen else "...", fill="#a8b0a4", font=font(28), tags=T)
        y = y1 + sh + U.h(10)
        cv.create_text(x1 + 4, y, text="No.%04d" % n, fill=INK2, font=font(10), anchor="nw", tags=T)
        status = "잡았다" if got else ("본 적 있다" if seen else "아직 모른다")
        sx = x2 - 4
        cv.create_text(sx, y, text=status, fill="#c02828" if got else DIM, font=font(10), anchor="ne", tags=T)
        if got:
            ph = _ball(15)
            if ph is not None:
                tw = K.tkfont_of(cv, font(10)).measure(status)
                cv.create_image(sx - tw - U.h(12), y + U.h(8), image=ph, tags=T)
        y += U.h(22)
        K.text(cv, x1 + 4, y, (sp.get("kr") or sp["internal"]) if seen else "?????", font(16), tags=T,
               width=x2 - x1 - 8)
        y += U.h(32)
        if not seen:
            return
        K.text(cv, x1 + 4, y, sp.get("kind") or "", font(10), fill=INK2, tags=T, width=x2 - x1 - 8)
        y += U.h(24)
        dex = self.app.dex
        tx = x1 + 4
        for t in sp.get("types") or []:
            label = dex.type_name(t) if dex else t
            col = U.TYPE_COLOR.get(t, "#a0a0a8")
            w = K.tkfont_of(cv, font(10)).measure(label) + U.h(18)
            K.rrect(cv, tx, y, tx + w, y + U.h(22), 6, fill=col, tags=T)
            cv.create_text(tx + w // 2, y + U.h(11), text=label, fill=K.look_of(col)[3], font=font(10), tags=T)
            tx += w + U.h(6)
        y += U.h(32)
        ht, kg = sp.get("height"), sp.get("kg")
        bits = []
        if ht:
            bits.append("키 %sm" % ("%g" % ht))
        if kg:
            bits.append("몸무게 %skg" % ("%g" % kg))
        if bits:
            K.text(cv, x1 + 4, y, "  ·  ".join(bits), font(10), tags=T, width=x2 - x1 - 8)
            y += U.h(24)
        cv.create_text(x1 + 4, y, text="%d세대" % int(sp.get("gen") or 0), fill=INK2, font=font(10), anchor="nw",
                       tags=T)
