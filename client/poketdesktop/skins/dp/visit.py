# -*- coding: utf-8 -*-
"""DP 테마 - 놀러 가기 · 여기에 두기 (도구 고르는 창).

DP 가방과 포켓몬 센터의 말투로 한 판에 놓는다 (v2: 줄무늬 · 빗금 · 테두리 글씨 · 그림자를 걷고, 창을 기본 창과 같은
760 x 540 으로 되돌렸다 - 1차는 860 x 640 으로 커져 있었다):

    ┌ 하늘색 띠: [놀러 가기] ○○ 님의 집으로 ─────────────── [포켓치 액정: 들고 갈 도구 볼 2/5 · 지닌 도구 0/1] ┐
    │ 초록 칸 안의 흰 목록 (분류 머리줄 + 줄)  │ 보라 띠: 놀러 가는 포켓몬 (도트 · 이름 · 설명)        │
    │   ▶ 빨간 커서 = 담은 것                 │ [들고 갈 도구]                  왼쪽 줄을 누르면 하나씩 │
    │                                         │ ┌ 흰 판 ─────────────────────────────────────────┐ │
    │                                         │ │ ▶ [그림] 슈퍼볼   [-] ×02 [+] [빼기]          │ │
    │                                         │ └────────────────────────────────────────────────┘ │
    ├ 메시지 상자 ─────────────────────────── 안내 글 ─────────────── [닫기] [놀러 가기] ┤

고르기 · 한도(볼 5 · 지닌 도구 1) · 오늘 받을 수 있나 · 서버 호출은 기본 창(ui_visit.ItemPicker) 그대로다 -
짓는 고리(_build)와 칠하는 고리(_show_limit · _set_go · _paint_status · _show_who · _set_thumb ·
_set_entries · _refresh_list · _set_empty_text · _show_empty · _paint_picked)만 바꾼다.
왼쪽 줄을 누르면 하나 담긴다 (기본과 같다). - / + 단추는 글자다.
"""
import tkinter as tk

from PIL import ImageTk

from ... import item_icons
from ... import ui_bag as B
from ... import ui_common as U
from ... import ui_visit as V
from . import (BLUE, CYAN1, DIM, GRAY_BTN, GREEN, HOV, INK2, LINE_D, OFF_BTN, PURPLE, PURPLE_EM, SEL, SEP, TAG_LINE,
               WHITE, WIN_BG, font)
from . import kit as K
from .scene import Scene, T

ROW = 28                 # 왼쪽 도구 줄 (기본 ui_bag.ITEM_H 와 같다)
HEAD = 22                # 분류 머리줄
PICK = 42                # 오른쪽 담은 줄
LCD_INK, LCD_BAD = "#2f4a30", "#a02020"
ORANGE = "#c06810"       # 담은 수


def _geo(w):
    """담은 줄 오른쪽의 칸들 (- · 개수 · + · 빼기)의 가로 자리."""
    s = U.h
    r = w - s(10)
    rm = (r - s(52), r)
    up = (rm[0] - s(6) - s(28), rm[0] - s(6))
    cnt = (up[0] - s(50), up[0])
    dn = (cnt[0] - s(28), cnt[0])
    return dn, cnt, up, rm


def _bundle_art(size):
    """보따리 그림 - 기본 창의 것에서 바탕 빛깔(마젠타)을 투명으로 바꿔 띠 위에 얹는다."""
    from ... import visit as VIS
    key = (255, 0, 255)
    im = VIS.bundle_image(size, key=key).convert("RGBA")
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            if px[x, y][:3] == key:
                px[x, y] = (0, 0, 0, 0)
    return ImageTk.PhotoImage(im)


class ItemPicker(Scene, V.ItemPicker):
    # 창 크기는 기본 창 그대로 (V.ItemPicker.WIN_SIZE = 760 x 540 · WIN_MIN = 640 x 460)

    # ---------------- 짓기 ----------------
    def _build(self):
        self.limit_text, self.limit_fg = "", None
        self.who_title = self.who_text = ""
        self._thumb = None
        self._head_art = self._band_art = None
        self._empty, self._empty_note = True, "불러오는 중..."
        self._names = {}
        self._scene_init()
        self.win.bind("<Escape>", lambda _e: self.close())
        self.items_vl = K.VList(self.cv, WHITE, self._draw_item_row, on_click=self._click_item)
        self.vl = self.items_vl                              # 기본 창이 부르던 이름
        self.picked_vl = K.VList(self.cv, WHITE, self._draw_picked_row, on_click=self._click_picked)
        self.go_btn = K.CButton(self.cv, "놀러 가기" if self.carry else "보따리 두기", self.go, "red", font(13))
        self.close_btn = K.CButton(self.cv, "닫기", self.close, "gray", font(10))
        try:
            self._head_art = _bundle_art(U.h(30))
            self._band_art = _bundle_art(U.h(44))
        except Exception:                                   # noqa: BLE001
            self._head_art = self._band_art = None

    # ---------------- 칠하는 고리 (기본 창이 부른다) ----------------
    def _show_limit(self, text, fg=None):
        self.limit_text, self.limit_fg = text, fg
        self._soon()

    def _set_go(self, enabled):
        self.go_btn.configure(state="normal" if enabled else "disabled")

    def _paint_status(self, text, color, fg):
        self._say(text, fg if fg else (color if color == U.DANGER else None))

    def _show_who(self, title, sub):
        self.who_title, self.who_text = title, sub
        self._soon()

    def _set_thumb(self, img):
        self.keep["thumb"] = self._thumb = ImageTk.PhotoImage(img)
        self._soon()

    def _set_empty_text(self, text):
        self._empty_note = text
        self._soon()

    def _show_empty(self, on):
        self._empty = bool(on)
        self._soon()

    def _set_entries(self, entries):
        self._names = dict((v["id"], v.get("kr") or v["id"]) for k, v in entries if k == "item")
        self.items_vl.set([((U.h(HEAD) if k == "head" else U.h(ROW)), (k, v)) for k, v in entries], keep=True)
        self._soon()

    def _refresh_list(self):
        self.items_vl.refresh()

    def _paint_picked(self):
        rows = [(U.h(PICK), iid) for iid in self.order if self.plan.get(iid)]
        self.picked_vl.set(rows, keep=True)
        self._soon()

    # ---------------- 판 ----------------
    def _paint(self):
        self._job = None
        if not self.alive:
            return
        cv = self.cv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 300 or H < 260:
            return
        s = U.h
        cv.delete("scene")
        self._msg_ids = None
        head, bot = s(54), s(62)
        self._paint_head(cv, W, head)
        lw = min(int(W * 0.5), B.LIST_W + s(24))              # 기본 창과 같은 목록 폭 (가방의 292 에 판 몫)
        self._paint_left(cv, 0, head, lw, H - bot)
        self._paint_right(cv, lw, head, W, H - bot)
        self._paint_bottom(cv, 0, W, H - bot, H, [(self.go_btn, s(130), s(240)), (self.close_btn, s(70), s(110))])

    def _paint_head(self, cv, W, hh):
        s = U.h
        cv.create_rectangle(0, 0, W, hh, fill=CYAN1, outline="", tags=T)
        cv.create_rectangle(0, hh - s(2), W, hh, fill=TAG_LINE, outline="", tags=T)
        cy = (hh - s(2)) // 2
        title = "놀러 가기" if self.carry else "여기에 두기"
        spec = font(14)
        tw = K.tkfont_of(cv, spec).measure(title) + s(24)
        th = K.tkfont_of(cv, spec).metrics("linespace") + s(6)
        K.tag(cv, s(12), cy - th // 2, title, tags=T, spec=spec)
        x = s(12) + tw + s(12)
        if self._head_art is not None:
            cv.create_image(x, cy, image=self._head_art, anchor="w", tags=T)
            x += self._head_art.width() + s(8)
        # 포켓치 액정 (한도)
        lab = "들고 갈 도구" if self.carry else "친구가 오늘"
        fl, fv = K.tkfont_of(cv, font(8)), K.tkfont_of(cv, font(11))
        w = fl.measure(lab) + fv.measure(self.limit_text) + s(48)
        x2, y1, y2 = W - s(12), s(8), hh - s(10)
        x1 = x2 - w
        K.rrect(cv, x1, y1, x2, y2, 8, fill="#3b3b40", tags=T)
        cv.create_rectangle(x1 + 4, y1 + 4, x2 - 4, y2 - 4, fill="#a8d09e", outline="", tags=T)
        m = (y1 + y2) // 2
        cv.create_text(x1 + s(12), m, text=lab, fill=LCD_INK, font=font(8), anchor="w", tags=T)
        bad = self.limit_fg == U.DANGER
        cv.create_text(x2 - s(12), m, text=self.limit_text, fill=LCD_BAD if bad else LCD_INK, font=font(11),
                       anchor="e", tags=T)
        K.text(cv, x, cy, self._whose_home(), font(11), anchor="w", width=max(s(80), x1 - x - s(12)), tags=T)

    # ---------------- 왼쪽: 가진 도구 ----------------
    def _paint_left(self, cv, x1, y1, x2, y2):
        s = U.h
        cv.create_rectangle(x1, y1, x2, y2, fill=GREEN, outline="", tags=T)
        bx1, by1, bx2, by2 = x1 + s(8), y1 + s(8), x2 - s(8), y2 - s(8)
        K.panel(cv, bx1, by1, bx2, by2, strong=True, tags=T)
        ix1, iy1, ix2, iy2 = bx1 + s(10), by1 + s(8), bx2 - s(10), by2 - s(6)
        _w, th = K.tag(cv, ix1, iy1, "가진 도구" if self.carry else "들고 온 도구", tags=T)
        if self._names:
            cv.create_text(ix2, iy1 + th // 2, text="%d종" % len(self._names), fill=INK2, font=font(9), anchor="e",
                           tags=T)
        ly1 = iy1 + th + s(6)
        if self._empty or not self._names:
            self._hide("items")
            K.text(cv, (ix1 + ix2) // 2, ly1 + s(30), self._empty_note, font(11), anchor="n", justify="center",
                   width=ix2 - ix1 - s(16), tags=T)
        else:
            self._place("items", self.items_vl.frame, ix1, ly1, ix2 - ix1, iy2 - ly1)

    def _draw_item_row(self, cv, data, x, y, w, h, tags, hover=None):
        s = U.h
        kind, val = data
        m = y + h // 2
        if kind == "head":
            cat, n = val[0], val[1]
            cv.create_rectangle(x + 6, m - 3, x + 12, m + 3, fill=B.CAT_COLOR.get(cat, DIM), outline="", tags=tags)
            cv.create_text(x + 18, m, text="%s · %d종" % (B.CAT_KR.get(cat, cat), n), fill=INK2, font=font(9),
                           anchor="w", tags=tags)
            cv.create_line(x + 4, y + h - 1, x + w - 4, y + h - 1, fill=SEP, tags=tags)
            return
        it = val
        have = self.bag.get(it["id"], 0)
        n = self.plan.get(it["id"], 0)
        on = n > 0
        if on:
            K.rrect(cv, x + 2, y + 1, x + w - 2, y + h - 1, s(4), fill=SEL, tags=tags)
            K.cursor(cv, x + s(8), m, size=s(5), tags=tags)
        elif hover is not None:
            K.rrect(cv, x + 2, y + 1, x + w - 2, y + h - 1, s(4), fill=HOV, tags=tags)
        icon = item_icons.photo(it["id"], 20)
        ix = x + s(34)
        if icon is not None:
            cv.create_image(ix, m, image=icon, tags=tags)
        else:
            cv.create_rectangle(ix - 3, m - 3, ix + 3, m + 3, fill=B.CAT_COLOR.get(it.get("cat"), DIM),
                                outline="", tags=tags)
        K.text(cv, x + s(50), m, it["kr"], font(11), anchor="w", tags=tags)
        if on:
            K.text(cv, x + w - 12, m, "%d / %d" % (n, have), font(11), fill=ORANGE, anchor="e", tags=tags)
        else:
            K.text(cv, x + w - 12, m, "×%d" % have, font(11), anchor="e", tags=tags)

    def _click_item(self, data, _x, _y, _w):
        kind, val = data
        if kind == "item":
            self.pick_item(val["id"])

    # ---------------- 오른쪽: 담은 것 ----------------
    def _paint_right(self, cv, x1, y1, x2, y2):
        s = U.h
        cv.create_rectangle(x1, y1, x2, y2, fill=WIN_BG, outline="", tags=T)
        # 보라 띠 - 누가 가는지
        sz = s(48)
        tw = (x2 - x1) - sz - s(48)
        th = K.text_height(cv, self.who_title, font(12), tw) + s(2) + K.text_height(cv, self.who_text, font(10), tw)
        bh = max(s(68), th + s(22))
        cv.create_rectangle(x1, y1, x2, y1 + bh, fill=PURPLE, outline="", tags=T)
        ix, iy = x1 + s(14), y1 + (bh - sz) // 2
        K.rrect(cv, ix, iy, ix + sz, iy + sz, 8, fill=WHITE, tags=T)
        art = self._thumb if self._thumb is not None else self._band_art       # 보따리를 둘 때는 보따리 그림
        if art is not None:
            cv.create_image(ix + sz // 2, iy + sz // 2, image=art, tags=T)
        tx = ix + sz + s(12)
        ty = y1 + (bh - th) // 2
        _a, t1 = K.text(cv, tx, ty, self.who_title, font(12), fill=PURPLE_EM, tags=T, width=tw)
        b = cv.bbox(t1)
        K.text(cv, tx, (b[3] if b else ty + s(20)) + s(2), self.who_text, font(10), fill=WHITE, tags=T, width=tw)
        # 담은 도구 - 파란 꼬리표 + 흰 판
        hy = y1 + bh + s(10)
        _w, tagh = K.tag(cv, x1 + s(12), hy, "들고 갈 도구" if self.carry else "보따리에 쌀 도구", tags=T)
        cv.create_text(x2 - s(12), hy + tagh // 2, text="왼쪽 줄을 누르면 하나씩 담긴다", fill=INK2, font=font(9),
                       anchor="e", tags=T)
        # 안내 글 (맨 아래, 판 없이)
        nw = x2 - x1 - s(24)
        how = self._how_text()
        nh = K.text_height(cv, how, font(9), nw)
        ny = y2 - s(8) - nh
        K.text(cv, x1 + s(12), ny, how, font(9), fill=INK2, anchor="nw", width=nw, tags=T)
        # 담은 줄들의 흰 판
        py1, py2 = hy + tagh + s(6), ny - s(8)
        lx1, lx2 = x1 + s(12), x2 - s(12)
        K.panel(cv, lx1, py1, lx2, py2, strong=True, tags=T)
        if self.plan:
            self._place("picked", self.picked_vl.frame, lx1 + s(4), py1 + s(4), lx2 - lx1 - s(8),
                        max(s(30), py2 - py1 - s(8)))
        else:
            self._hide("picked")
            note = "왼쪽에서 도구를 누르면 여기에 담긴다." if self.carry else "왼쪽에서 보따리에 쌀 도구를 누른다."
            K.text(cv, (lx1 + lx2) // 2, py1 + s(24), note, font(10), fill=INK2, anchor="n", justify="center",
                   width=lx2 - lx1 - s(30), tags=T)

    def _draw_picked_row(self, cv, iid, x, y, w, h, tags, hov):
        s = U.h
        n = self.plan.get(iid, 0)
        have = self.bag.get(iid, 0)
        cy = y + h // 2
        if hov is not None:
            K.rrect(cv, x + 1, y + 1, x + w - 1, y + h - 1, s(4), fill=HOV, tags=tags)
        cv.create_line(x + 6, y + h - 1, x + w - 6, y + h - 1, fill=SEP, tags=tags)
        K.cursor(cv, x + s(8), cy, size=s(6), tags=tags)
        left = x + s(24)
        ph = item_icons.photo(iid, 24)
        if ph is not None:
            cv.create_image(left, cy, image=ph, anchor="w", tags=tags)
        tx = left + (s(32) if ph is not None else 0)
        dn, cnt, up, rm = _geo(w)
        tw = max(s(40), dn[0] - s(8) - tx)
        name = self._names.get(iid, iid)
        K.text(cv, tx, cy - s(2), K.wrap(cv, name, font(11), tw).split("\n")[0], font(11), anchor="sw", tags=tags)
        K.text(cv, tx, cy + s(1), "가진 %d개 중" % have, font(9), fill=INK2, anchor="nw", tags=tags, width=tw)
        bh = s(28)
        by1, by2 = cy - bh // 2, cy + bh // 2
        for box, name_ico, ok in ((dn, "minus", n > 0), (up, "plus", n < have)):
            K.rrect(cv, box[0], by1, box[1], by2, s(5), fill=BLUE if ok else OFF_BTN, tags=tags)
            cv.create_text((box[0] + box[1]) // 2, cy, text="−" if name_ico == "minus" else "+", fill=WHITE,
                           font=font(14), tags=tags)
        K.rrect(cv, cnt[0] + s(2), by1, cnt[1] - s(2), by2, s(5), fill=WHITE, outline=LINE_D, width=1, tags=tags)
        K.text(cv, (cnt[0] + cnt[1]) // 2, cy, "×%02d" % n, font(11), fill=ORANGE, anchor="center", tags=tags)
        K.rrect(cv, rm[0], by1, rm[1], by2, s(5), fill=GRAY_BTN, tags=tags)
        K.text(cv, (rm[0] + rm[1]) // 2, cy, "빼기", font(9), fill=WHITE, anchor="center", tags=tags)

    def _click_picked(self, iid, x, _y, w):
        dn, cnt, up, rm = _geo(w)
        if dn[0] <= x <= dn[1]:
            self.bump(iid, -1)
        elif up[0] <= x <= up[1]:
            self.bump(iid, 1)
        elif rm[0] <= x <= rm[1]:
            self.remove(iid)
