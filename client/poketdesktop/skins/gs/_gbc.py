# -*- coding: utf-8 -*-
"""금·은 테마의 부품과 가방 판 - 허브 · 가방(도구 · 기술머신) · 배틀이 같이 쓴다.

부품 (시안 G 의 CSS 를 그대로 옮긴 것):

    gbox     두 겹 테 상자: 진한 테 4 · 종이빛 2 · 금빛 안쪽 줄 2 · 종이빛 속, 바깥 모서리는 6 깎음 (.g .bx)
    dot_bg   금빛 크림 바탕의 옅은 점 (12 칸마다 하나 - .g .win 의 radial-gradient). 판 바깥에만 깐다
    arrow    빨간 ▶ 커서 (.g .ln.sel::before)
    chips    진한 테 2 의 네모 칩, 고르면 진한 바탕 · 종이빛 글씨 (.g .sorts)
    entry    밑줄 하나뿐인 찾기 칸 (.g .tools u)
    GSButton 캔버스 단추 (kit.CButton 과 같은 말을 받는다): 'menu' = ▶ 가 붙는 글자 메뉴 (시안의 '▶ 지니게 한다'),
             'chip' = 칩 모양 작은 단추

가방 판 (GSBag - 도구 칸 bag.py 와 기술머신 칸 tms.py 가 섞는다). 시안 G 의 가방 그대로:

    ┌ 왼쪽 위 상자 ──────────┐ ┌ 큰 상자 ──────────────────────────────────┐
    │ ◀  지닌 도구 ▾  ▶       │ │ 찾기 ________________      소지금 48,200원 │
    │      ( 도구 그림 )      │ │ [이름][종류][등급][개수]     460종 [새로고침]│
    │      먹다남은음식       │ │ 열매 · 3종                                 │
    │   영웅 등급 · 1개       │ │    오랭열매                          ×5   │
    └────────────────────────┘ │ ▶  먹다남은음식                      ×1   │
    ┌ 왼쪽 아래 상자 ────────┐ │ …                                          │
    │ 누구에게 쓸까?          │ │                                            │
    │ 찾기 ____ [기본][가나다] │ │                                            │
    │ ▶ 리자몽 Lv.50    빈손  │ │                                            │
    └────────────────────────┘ └────────────────────────────────────────────┘
    ┌ 아래 넓은 상자 ─────────────────────────────────────────────────────────┐
    │ 지니게 하면 매 턴 끝에 최대 HP의 1/16만큼 회복한다.     ▶ 먹다남은음식 쓰기 │
    │ 리자몽에게 지니게 할까?                                    팔기          │
    └─────────────────────────────────────────────────────────────────────────┘

주머니는 ◀ ▶ 로 넘기고, 가운데 이름을 누르면 주머니 목록(개수와 함께)이 뜬다 (U.PopupMenu - 기본 메뉴 그대로).
잠깐 뜨는 알림(_toast)은 아래 넓은 상자 자리를 같은 모양의 상자로 덮는다.
부르는 창이 정하는 것: _gs_card() · _gs_mid(cv, x1, y1, x2, y2) · _gs_menu() · _gs_plates_title() ·
_band_content() · _plate_info(m) · _pocket_*() (DP 와 같은 이름).
"""
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from ... import box_filter
from ... import ui_common as U
from ..dp import font, tone
from ..dp import kit as K
from ..dp.scene import POCKET_NAME, POCKETS, T
from . import AMBER, BROWN, CIRCLE, DIM, DOT, G_BG, HOV, INK, INK2, PAPER, RED, SEL, SEP

BADGE = "#e02820"            # 새 소식 점


# ---------------------------------------------------------------- 부품
def _oct(x1, y1, x2, y2, c):
    return [x1 + c, y1, x2 - c, y1, x2, y1 + c, x2, y2 - c, x2 - c, y2, x1 + c, y2, x1, y2 - c, x1, y1 + c]


def gbox(cv, x1, y1, x2, y2, fill=PAPER, tags=(), k=1.0, edge=INK, inner=AMBER):
    """시안의 상자 (.g .bx): 진한 테 4 · 종이빛 2 · 금빛 줄 2 · 속. 바깥 모서리만 6 깎는다. 속 사각형을 돌려준다.

    k 는 테 두께 배율 (배틀 창은 창 크기 배율을 탄다)."""
    b = max(2, int(round(4 * k)))
    g = max(1, int(round(2 * k)))
    a = max(1, int(round(2 * k)))
    c = max(3, int(round(6 * k)))
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    cv.create_polygon(_oct(x1, y1, x2, y2, c), fill=edge, outline="", tags=tags)
    cv.create_rectangle(x1 + b, y1 + b, x2 - b, y2 - b, fill=PAPER, outline="", tags=tags)
    if inner:
        cv.create_rectangle(x1 + b + g, y1 + b + g, x2 - b - g, y2 - b - g, fill=inner, outline="", tags=tags)
    d = b + g + (a if inner else 0)
    cv.create_rectangle(x1 + d, y1 + d, x2 - d, y2 - d, fill=fill, outline="", tags=tags)
    return x1 + d, y1 + d, x2 - d, y2 - d


def gbox_pad(k=1.0):
    """gbox 의 테 두께 (바깥에서 속까지)."""
    return max(2, int(round(4 * k))) + max(1, int(round(2 * k))) + max(1, int(round(2 * k)))


_DOTS = {}


def dot_bg(cv, x1, y1, x2, y2, tags=()):
    """금빛 크림 바탕 + 옅은 점 (시안 .g .win). 그림 한 장으로 깐다 (점마다 도형을 만들면 느리다)."""
    w, h = max(1, int(x2 - x1)), max(1, int(y2 - y1))
    key = (w, h)
    ph = _DOTS.get(key)
    if ph is None:
        tile = Image.new("RGB", (12, 12), G_BG)
        d = ImageDraw.Draw(tile)
        d.rectangle((1, 1, 2, 2), fill=DOT)
        img = Image.new("RGB", (w, h), G_BG)
        for yy in range(0, h, 12):
            for xx in range(0, w, 12):
                img.paste(tile, (xx, yy))
        try:
            ph = ImageTk.PhotoImage(img, master=cv)
        except tk.TclError:
            return None
        if len(_DOTS) > 12:
            _DOTS.clear()
        _DOTS[key] = ph
    return cv.create_image(int(x1), int(y1), image=ph, anchor="nw", tags=tags)


def arrow(cv, x, ym, s, fill=RED, tags=(), left=False):
    """▶ 커서 (left=True 면 ◀). x 는 왼쪽 끝, ym 은 세로 가운데."""
    if left:
        return cv.create_polygon(x + s + 1, ym - s, x, ym, x + s + 1, ym + s, fill=fill, outline="", tags=tags)
    return cv.create_polygon(x, ym - s, x + s + 1, ym, x, ym + s, fill=fill, outline="", tags=tags)


def chips(cv, x, y, h, items, current, tag, on_pick, spec=None, align="left", tags=T, hand=None):
    """시안의 칩 줄 (.g .sorts): 진한 테 2, 고른 칩은 진한 바탕 · 종이빛 글씨. 그린 칸들 [(열쇠, 상자)]."""
    spec = spec or font(10)
    f = K.tkfont_of(cv, spec)
    ws = [f.measure(lb) + U.h(18) for _k, lb in items]
    gap = U.h(6)
    if align == "right":
        x -= sum(ws) + gap * (len(items) - 1)
    out = []
    for (key, lb), w in zip(items, ws):
        on = key == current
        tg = tuple(tags) + (tag, "%s_%s" % (tag, key or "_"))
        cv.create_rectangle(x + 1, y + 1, x + w - 1, y + h - 1, fill=INK if on else PAPER, outline=INK, width=2,
                            tags=tg)
        cv.create_text(x + w // 2, y + h // 2, text=lb, fill=PAPER if on else INK, font=spec, anchor="center",
                       tags=tg)
        cv.tag_bind("%s_%s" % (tag, key or "_"), "<Button-1>", lambda _e, k=key: on_pick(k))
        out.append((key, (x, y, x + w, y + h)))
        x += w + gap
    if hand is not None:
        hand(tag)
    return out


def chips_width(cv, items, spec=None):
    f = K.tkfont_of(cv, spec or font(10))
    return sum(f.measure(lb) + U.h(18) for _k, lb in items) + U.h(6) * (len(items) - 1)


def entry(box):
    """kit.entry 의 칸을 시안의 찾기 칸으로: 테 없이 밑줄 하나 (고르면 빨간 밑줄)."""
    try:
        box.configure(bg=PAPER, highlightthickness=0)
        e = box.entry
        e.configure(bg=PAPER, fg=INK, insertbackground=INK)
        line = tk.Frame(box, height=2, bg=INK, bd=0, highlightthickness=0)
        line.pack(side="bottom", fill="x", before=e)
        e.bind("<FocusIn>", lambda _e: line.configure(bg=RED), add="+")
        e.bind("<FocusOut>", lambda _e: line.configure(bg=INK), add="+")
    except tk.TclError:
        pass
    return box


def paper_list(vl):
    """kit.VList 의 바탕을 종이빛으로 (목록이 시안의 상자 속처럼)."""
    for w in (vl.frame, vl.cv, vl.sb):
        if w is not None:
            try:
                w.configure(bg=PAPER)
            except tk.TclError:
                pass


class GSButton(K.CButton):
    """캔버스 단추 (kit.CButton 과 같은 말). style:

        'menu'    시안의 메뉴 글자: 왼쪽에 ▶ (올렸을 때 · primary 면 늘), 올리면 옅은 금빛 줄
        'chip'    칩 모양: 진한 테 2 의 종이빛 네모, 올리면 옅은 금빛
    """

    style = "menu"
    primary = False

    def want_width(self, pad=28):
        w = K.tkfont_of(self.cv, self.spec).measure(self.text) + pad
        return w + (U.h(22) if self.style == "menu" else 0)

    def draw(self):
        cv = self.cv
        cv.delete(self.tag)
        self._body_id = None
        self._arrow_id = None
        self._shift = 0
        self._hover = self._down = False
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        m = (self.tag, self.tag + "_m")
        on = self.enabled
        if self.style == "chip":
            self._body_id = cv.create_rectangle(x1 + 1, y1 + 1, x2 - 1, y2 - 1, fill=PAPER,
                                                outline=INK if on else "#b0a488", width=2, tags=m)
            cv.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=self.text, fill=INK if on else DIM, font=self.spec,
                           anchor="center", tags=m)
        else:
            self._body_id = cv.create_rectangle(x1, y1, x2, y2, fill=PAPER, outline="", tags=m)
            ym = (y1 + y2) // 2
            s = U.h(5)
            self._arrow_id = arrow(cv, x1 + U.h(6), ym, s, tags=m)
            cv.create_text(x1 + U.h(22), ym, text=self.text, fill=INK if on else DIM, font=self.spec, anchor="w",
                           tags=m)
        self._state()

    def _state(self):
        if self._body_id is None:
            return
        hot = self._hover and self.enabled
        try:
            self.cv.itemconfigure(self._body_id, fill=SEL if hot else PAPER)
            if self._arrow_id is not None:
                show = self.enabled and (hot or self.primary)
                self.cv.itemconfigure(self._arrow_id, state="normal" if show else "hidden")
            want = 1 if (self._down and self.enabled) else 0
            if want != self._shift:
                self.cv.move(self.tag + "_m", 0, want - self._shift)
                self._shift = want
        except tk.TclError:
            pass


def as_gs(btn, style="menu", primary=False):
    """만들어 둔 kit.CButton 을 그대로 두고 그리는 법만 GSButton 으로 (동작 · 바인딩은 그대로)."""
    btn.__class__ = GSButton
    btn.style = style
    btn.primary = primary
    return btn


# ---------------------------------------------------------------- 가방 판
class GSBag(object):
    """가방 판 (도구 칸 · 기술머신 칸). 창 클래스의 맨 앞에 섞는다 (DP 칸의 _paint 를 이것으로 바꾼다)."""

    LW_PX = 350              # 왼쪽 기둥 폭 (pt) - 병뚜껑 능력 칸이 세 칸씩 들게
    MENU_ROW = 26            # 아래 상자의 메뉴 한 줄 (pt)

    def _gs_setup(self):
        """DP 칸이 만든 것을 시안 모양으로 (DP _build 다음에 부른다)."""
        self.PLATE_H = U.h(46)
        self._plate_cols = 1
        paper_list(self.mons_vl)
        entry(self.find.box)
        self._plates_set(self._plate_rows_src, keep=True)
        try:
            self.cv.configure(bg=G_BG)
            self.win.configure(bg=G_BG)
        except tk.TclError:
            pass

    # ---- 판 전체
    def _paint(self):
        self._job = None
        if not getattr(self, "alive", True):
            return
        cv = self.cv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 200 or H < 200:
            return
        cv.delete("scene")
        self._msg_ids = None
        pad, gap = U.h(10), U.h(8)
        dot_bg(cv, 0, 0, W, H, tags=T)
        LW = U.h(self.LW_PX)
        menu = [b for b in self._gs_menu() if b is not None]
        BH = self._gs_bottom_h(cv, W - 2 * pad, menu, H)
        by1 = H - pad - BH
        k = gbox_pad()
        plates = self._gs_plates_title(LW - 2 * k - U.h(12))
        # 판 목록 위에 끼우는 칸(병뚜껑 능력 · 노력치)이 있거나 창이 낮으면 그림 칸을 작게 (포켓몬 줄이 보이게)
        compact = bool(plates[3]) or H < U.h(520)
        cy2 = self._gs_paint_card(cv, pad, pad, pad + LW, compact)
        self._gs_paint_plates(cv, pad, cy2 + gap, pad + LW, by1 - gap, plates)
        self._gs_mid(cv, pad + LW + gap, pad, W - pad, by1 - gap)
        self._gs_paint_bottom(cv, pad, by1, W - pad, H - pad, menu)
        self._toast_box = (pad, by1, W - pad, H - pad)
        self._paint_toast()

    # ---- 왼쪽 위: 주머니 · 고른 것
    def _gs_paint_card(self, cv, x1, y1, x2, compact=False):
        """◀ 주머니 ▶ · 둥근 그림 칸 · 이름 · 작은 줄. 상자 아래 끝 y.
        compact 면 둥근 칸을 작게 왼쪽에 두고 이름 · 작은 줄을 그 오른쪽에 (높이가 반쯤)."""
        name, line, art = self._gs_card()
        k = gbox_pad()
        inner = x2 - x1 - 2 * k - U.h(16)
        f12 = K.tkfont_of(cv, font(12))
        label = self._pocket_label()
        lab_h = max(f12.metrics("linespace"), K.text_height(cv, label, font(12), inner - U.h(64)))
        rh = max(U.h(28), lab_h + U.h(6))
        D = U.h(44) if compact else U.h(64)
        tw = inner - D - U.h(12) if compact else inner
        name_h = K.text_height(cv, name, font(12), tw)
        line_h = K.text_height(cv, line, font(9), tw) if line else 0
        text_h = name_h + (U.h(3) + line_h if line else 0)
        if compact:
            h = 2 * k + U.h(6) + rh + U.h(6) + max(D, text_h) + U.h(10)
        else:
            h = 2 * k + U.h(6) + rh + U.h(8) + D + U.h(8) + text_h + U.h(10)
        y2 = y1 + h
        ix1, iy1, ix2, _iy2 = gbox(cv, x1, y1, x2, y2, tags=T)
        # ◀ 이름 ▾ ▶ (이름을 누르면 주머니 목록)
        ym = iy1 + U.h(6) + rh // 2
        s = U.h(6)
        hit = U.h(14)
        ax1 = ix1 + U.h(10)
        ax2 = ix2 - U.h(10) - s - 1
        cv.create_rectangle(ax1 - 6, ym - hit, ax1 + s + 8, ym + hit, fill=PAPER, outline="", tags=T + ("pkprev",))
        arrow(cv, ax1, ym, s, fill=INK, tags=T + ("pkprev",), left=True)
        cv.create_rectangle(ax2 - 8, ym - hit, ax2 + s + 6, ym + hit, fill=PAPER, outline="", tags=T + ("pknext",))
        arrow(cv, ax2, ym, s, fill=INK, tags=T + ("pknext",))
        cx = (ix1 + ix2) // 2
        lw = min(f12.measure(label), inner - U.h(64))
        tg = T + ("pkmenu",)
        cv.create_rectangle(cx - lw // 2 - U.h(6), ym - hit, cx + lw // 2 + U.h(20), ym + hit, fill=PAPER, outline="",
                            tags=tg)
        K.text(cv, cx, ym, label, font(12), anchor="center", justify="center", width=inner - U.h(64), tags=tg)
        tx = cx + lw // 2 + U.h(8)
        cv.create_polygon(tx, ym - U.h(2), tx + U.h(8), ym - U.h(2), tx + U.h(4), ym + U.h(3), fill=INK2,
                          outline="", tags=tg)
        if getattr(self, "_tm_badge", False):
            d = U.h(4)
            bx, by = ax2 - U.h(6), ym - U.h(10)
            cv.create_oval(bx - d, by - d, bx + d, by + d, fill=BADGE, outline=PAPER, tags=T + ("pknext",))
        # 둥근 그림 칸 (시안: 금빛 크림 원 · 진한 테 3)
        if compact:
            top = iy1 + U.h(6) + rh + U.h(6)
            hh = max(D, text_h)
            ccx, cy = ix1 + U.h(10) + D // 2, top + hh // 2
        else:
            ccx, cy = cx, iy1 + U.h(6) + rh + U.h(8) + D // 2
        cv.create_oval(ccx - D // 2, cy - D // 2, ccx + D // 2, cy + D // 2, fill=CIRCLE, outline=INK, width=3,
                       tags=T)
        if art is not None:
            art(cv, ccx, cy, D)
        ink = INK if self._gs_has_pick() else DIM
        if compact:
            tx, ny = ccx + D // 2 + U.h(12), cy - text_h // 2
            _a, nid = K.text(cv, tx, ny, name, font(12), fill=ink, anchor="nw", width=tw, tags=T)
            if line:
                b = cv.bbox(nid)
                cv.create_text(tx, (b[3] if b else ny + U.h(18)) + U.h(3), text=line, fill=BROWN, font=font(9),
                               anchor="nw", width=tw, tags=T)
        else:
            ny = cy + D // 2 + U.h(8)
            _a, nid = K.text(cv, cx, ny, name, font(12), fill=ink, anchor="n", justify="center", width=inner, tags=T)
            if line:
                b = cv.bbox(nid)
                cv.create_text(cx, (b[3] if b else ny + U.h(18)) + U.h(3), text=line, fill=BROWN, font=font(9),
                               anchor="n", justify="center", width=inner, tags=T)
        cv.tag_bind("pkprev", "<Button-1>", lambda _e: self._pocket_step(-1))
        cv.tag_bind("pknext", "<Button-1>", lambda _e: self._pocket_step(1))
        cv.tag_bind("pkmenu", "<Button-1>", lambda _e: self._pocket_menu())
        self._hand("pkprev", "pknext", "pkmenu")
        self._pk_box = (ix1, iy1 + U.h(6) + rh)
        return y2

    def _pocket_step(self, d):
        keys = [k for k, _l in POCKETS]
        now = self._pocket_now()
        i = keys.index(now) if now in keys else 0
        self._pocket_click(keys[(i + d) % len(keys)])

    def _pocket_menu(self):
        """주머니 목록 (개수와 함께). 뜨는 메뉴는 기본 모양 그대로 (U.PopupMenu)."""
        now = self._pocket_now()
        rows = []
        for key, _l in POCKETS:
            name = POCKET_NAME.get(key, key).replace("\n", " ")
            if key not in ("all", "tms") and now != "tms":
                name = "%s · %d" % (name, self._pocket_count(key))
            if key == "tms" and getattr(self, "_tm_badge", False):
                name += " · 새것"
            rows.append({"text": name, "command": (lambda k=key: self._pocket_click(k)), "checked": key == now})
        try:
            x0, y0 = self._pk_box
            x = self.cv.winfo_rootx() + int(x0)
            y = self.cv.winfo_rooty() + int(y0) + 2
        except (tk.TclError, AttributeError):
            return None
        return U.PopupMenu(self.root, rows, x, y, width=200)

    # ---- 왼쪽 아래: 누구에게
    def _gs_paint_plates(self, cv, x1, y1, x2, y2, plates):
        ix1, iy1, ix2, iy2 = gbox(cv, x1, y1, x2, y2, tags=T)
        lx1, lx2 = ix1 + U.h(8), ix2 - U.h(6)
        title, hint, note, boxes = plates
        y = iy1 + U.h(6)
        _a, tid = K.text(cv, lx1, y, title, font(11), tags=T, width=lx2 - lx1)
        b = cv.bbox(tid)
        y = (b[3] if b else y + U.h(18)) + U.h(2)
        if hint:
            _a, hid = K.text(cv, lx1, y, hint, font(9), fill=BROWN, tags=T, width=lx2 - lx1)
            b = cv.bbox(hid)
            y = (b[3] if b else y + U.h(14)) + U.h(4)
        y += U.h(2)
        fh = U.h(24)
        if note is not None and not self.find.searching():
            self._hide("mfind")
        else:
            sorts = box_filter.PICK_SORTS
            cv.create_text(lx1, y + fh // 2, text="찾기", fill=INK, font=font(10), anchor="w", tags=T)
            ex = lx1 + U.h(36)
            cw = chips_width(cv, sorts, font(9))
            cnt = self.find.count
            cnt_w = (K.tkfont_of(cv, font(9)).measure(cnt) + U.h(8)) if cnt else 0
            if lx2 - cw - U.h(8) - ex - cnt_w >= U.h(70):                 # 한 줄에 다 든다
                chips(cv, lx2, y, fh, sorts, self.find.sort, "msrt", self.find.pick_sort, spec=font(9),
                      align="right", hand=self._hand)
                ew = lx2 - cw - U.h(8) - ex - cnt_w
                y_next = y + fh + U.h(6)
            else:                                                          # 칩은 아래 줄로
                chips(cv, lx1, y + fh + U.h(4), fh, sorts, self.find.sort, "msrt", self.find.pick_sort,
                      spec=font(9), hand=self._hand)
                ew = lx2 - ex - cnt_w
                y_next = y + 2 * fh + U.h(10)
            self._place("mfind", self.find.box, ex, y, max(U.h(60), ew), fh)
            if cnt:
                cv.create_text(ex + max(U.h(60), ew) + U.h(4), y + fh // 2, text=cnt, fill=BROWN, font=font(9),
                               anchor="w", tags=T)
            y = y_next
        for h, draw in boxes:
            draw(cv, lx1 - U.h(2), y, lx2)
            y += h + U.h(6)
        if note is None:
            self._place("mons", self.mons_vl.frame, ix1 + U.h(2), y, ix2 - ix1 - U.h(4), max(U.h(40), iy2 - y - 2))
        else:
            self._hide("mons")
            K.text(cv, (lx1 + lx2) // 2, y + U.h(12), note, font(11), fill=INK2, anchor="n", justify="center",
                   width=lx2 - lx1 - U.h(8), tags=T)

    def _plate_box(self, x, y, w, h, k):
        return x, y, x + w, y + h

    def _draw_plate(self, cv, m, x1, y1, x2, y2, tags, hov):
        """'누구에게' 한 줄 (시안 .g .pm): 고른 것은 빨간 ▶, 도트 · 이름 / Lv · 오른쪽에 알림 글.
        쓸 수 있는 것은 옅은 풀빛, 못 쓰는 것은 흐리게 (DP 와 같은 뜻)."""
        info = self._plate_info(m)
        blocked, good = info.get("blocked"), info.get("good")
        sel = m.get("id") == self.mon_id
        if hov and not blocked and not sel:
            fill = HOV
        elif good:
            fill = "#eef6dc"
        else:
            fill = PAPER
        cv.create_rectangle(x1, y1, x2, y2, fill=fill, outline="", tags=tags)
        cv.create_line(x1 + U.h(6), y2 - 1, x2 - U.h(6), y2 - 1, fill=SEP, tags=tags)
        mid = (y1 + y2) // 2
        if sel:
            arrow(cv, x1 + U.h(5), mid, U.h(5), tags=tags)
        ph = info.get("photo")
        if ph is not None:
            cv.create_image(x1 + U.h(38), mid, image=ph, tags=tags)
        name = info.get("name") or "?"
        if info.get("shiny"):
            name = "★ " + name
        tx = x1 + U.h(62)
        ink = DIM if blocked else INK
        cv.create_text(tx, y1 + U.h(5), text=name, fill="#8a5a00" if info.get("shiny") else ink, font=font(11),
                       anchor="nw", tags=tags)
        sub = info.get("sub") or ""
        cv.create_text(tx, y2 - U.h(5), text=sub, fill=DIM if blocked else BROWN, font=font(9), anchor="sw",
                       tags=tags)
        if info.get("note"):
            f9 = K.tkfont_of(cv, font(9))
            nw = f9.measure(info["note"])
            low = tx + f9.measure(sub) + U.h(10) <= x2 - U.h(8) - nw
            cv.create_text(x2 - U.h(8), (y2 - U.h(5)) if low else (y1 + U.h(7)), text=info["note"],
                           fill=tone(info.get("color") or U.FG_DIM), font=font(9), anchor="se" if low else "ne",
                           tags=tags)

    # ---- 아래: 설명 + 메뉴
    def _gs_menu_w(self, cv, menu):
        return max([b.want_width(U.h(24)) for b in menu] or [0])

    def _gs_desc(self):
        """아래 상자의 글 (제목, 본문, 작은 줄)."""
        title, body, _art = self._band_content()
        return title, body, self._gs_desc_note()

    def _gs_desc_note(self):
        return ""

    def _gs_bottom_h(self, cv, width, menu, H):
        mw = self._gs_menu_w(cv, menu)
        tw = width - 2 * gbox_pad() - U.h(40) - mw
        title, body, note = self._gs_desc()
        th = K.text_height(cv, title, font(11), tw) + U.h(4) + K.text_height(cv, body, font(11), tw)
        if note:
            th += U.h(4) + K.text_height(cv, note, font(9), tw)
        mh = len(menu) * U.h(self.MENU_ROW)
        need = max(th, mh) + 2 * gbox_pad() + U.h(12)
        return max(U.h(88), min(int(H * 0.36), need))

    def _gs_paint_bottom(self, cv, x1, y1, x2, y2, menu):
        ix1, iy1, ix2, iy2 = gbox(cv, x1, y1, x2, y2, tags=T)
        mw = self._gs_menu_w(cv, menu)
        tw = (ix2 - ix1) - U.h(40) - mw
        title, body, note = self._gs_desc()
        tx, ty = ix1 + U.h(16), iy1 + U.h(9)
        _a, t1 = K.text(cv, tx, ty, title, font(11), fill="#7a4a10", tags=T, width=tw)
        b = cv.bbox(t1)
        _a, t2 = K.text(cv, tx, (b[3] if b else ty + U.h(18)) + U.h(4), body, font(11), fill=INK, tags=T, width=tw)
        if note:
            b = cv.bbox(t2)
            K.text(cv, tx, (b[3] if b else ty + U.h(36)) + U.h(4), note, font(9), fill=BROWN, tags=T, width=tw)
        # 메뉴 (오른쪽, 가운데 맞춤)
        rh = U.h(self.MENU_ROW)
        my = (iy1 + iy2) // 2 - len(menu) * rh // 2
        mx1 = ix2 - U.h(10) - mw
        for btn in menu:
            btn.layout(mx1, my, ix2 - U.h(10), my + rh - U.h(2))
            my += rh

    def _paint_toast(self):
        """잠깐 뜨는 알림: 아래 넓은 상자 자리를 같은 모양의 상자로 통째로 덮는다 (밑의 설명이 비치지 않게)."""
        cv = self.cv
        try:
            cv.delete("toast")
        except tk.TclError:
            return
        m, bx = getattr(self, "_toast_msg", None), getattr(self, "_toast_box", None)
        if not m or not bx:
            return
        text, color = m
        x1, y1, x2, y2 = bx
        tg = ("toast",)
        ix1, iy1, ix2, iy2 = gbox(cv, x1, y1, x2, y2, tags=tg)
        arrow(cv, ix1 + U.h(12), (iy1 + iy2) // 2, U.h(5), tags=tg)
        K.text(cv, ix1 + U.h(28), (iy1 + iy2) // 2, text, font(11), fill=tone(color) if color else INK, anchor="w",
               width=ix2 - ix1 - U.h(44), tags=tg)

    # ---- 가운데 목록 상자의 머리 (찾기 칸 · 칩 줄은 부르는 창이)
    def _gs_list_frame(self, cv, x1, y1, x2, y2):
        return gbox(cv, x1, y1, x2, y2, tags=T)
