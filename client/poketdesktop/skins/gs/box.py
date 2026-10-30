# -*- coding: utf-8 -*-
"""금·은 테마 - 포켓몬 (PC 박스). 금·은의 '빌의 PC' 를 시안 G 의 말로 옮긴다:

    ┌ 왼쪽 상자 (요약) ──────┐ ┌ 머리 상자 ──────────────────────────────────────────────┐
    │ ┌ 도트 칸 ──────────┐ │ │ ◀ [  박스 1   8/30 ▾  ] ▶  [이름 바꾸기]         [새로고침] │
    │ │ No.0006  (도트)    │ │ │ ─────────────────────────────────────────────────────── │
    │ └────────────────────┘ │ │ [타입: 전체 ▾]  찾기 ________     [도감][이름][Lv][종족값] │
    │ 리자몽 ♂        Lv.60 │ └─────────────────────────────────────────────────────────┘
    │ [불꽃][비행]           │ ┌ 데리고 다니는 ┐ ┌ 박스 (빗금 벽지 위의 6 × 5 칸) ─────────┐
    │ [정보][능력][기술][메가] │ │ [파티 1 ▾]    │ │ ▶[도트] [도트] [도트] …                  │
    │ 특성 · 성격 · 도구 …   │ │ ▶ 도트 리자몽 │ │                                          │
    │                        │ │   도트 한카리 │ │                                          │
    └────────────────────────┘ └───────────────┘ └──────────────────────────────────────────┘
                               ┌ 아래 상자 ────────────────────────────────────────────────┐
                               │ ▶ 박스로 보내기   별명 짓기   박스 옮기기   색 고르기   놓아주기 │
                               │ ─────────────────────────────────────────────────────── │
                               │ 보유 14마리 · 데리고 다니는 중 6마리                        │
                               └──────────────────────────────────────────────────────────┘

    상자      진한 테 · 금빛 안쪽 줄의 두 겹 상자 (_gbc.gbox) - 글은 모두 종이빛 상자 안에
    바탕      창은 금빛 크림 점, 박스 칸 뒤는 옅은 빗금 벽지 (빈 칸은 테만 - 찬 칸은 종이빛이라 도트가 먼저 보인다)
    커서      빨간 ▶ - 고른 칸 · 고른 파티 자리 · 고른 기술 · 아래 메뉴의 주된 일
    칩        진한 테 2 의 네모 칩 (줄 세우기 · 요약의 쪽 · 타입 · 파티 고르기), 고르면 진한 바탕
    단추      아래 단추 줄은 시안의 글자 메뉴 (▶ 가 붙는 글), 요약 안 단추는 네모 칩

동작 · 고리(박스 넘기기 · 거르기 · 여러 마리 고르기 · 끌어서 맞바꾸기 · 지닌 도구 · 유대 미션)는 DP 박스
(skins/dp/box.py → ui_box.BoxWindow) 그대로다 - 칠하는 메서드만 바꾼다.
"""
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from common import legends as L
from common import movetext as MT

from ... import box_filter, item_icons, sprite_cache, sprites
from ... import ui_bond as BD
from ... import ui_common as U
from ..dp import box as DPB
from ..dp import font, tone
from ..dp import kit as K
from ..dp.scene import T
from . import AMBER, BROWN, BTN, BTN_HI, DIM, G_BG, GREEN, HOV, INK, INK2, PAPER, RED, SEL, SEP
from ._gbc import GSButton, arrow, chips, chips_width, dot_bg, entry, gbox, gbox_pad

D = DPB.D
SORTS = DPB.SORTS

# 이 화면의 빛깔 (gs/__init__.py 의 KEEP 에도 적어 둔다 - DP 빛깔 옮기기에 걸리지 않게)
GOOD = "#e6f1d2"          # 여러 마리 고르기로 고른 칸 (옅은 풀빛)
CELL_LINE = "#d6bd84"     # 찬 칸의 옅은 테
EMPTY_LINE = "#e0c890"    # 빈 칸의 테 (벽지가 비친다)
WALL = "#f7e9c0"          # 박스 벽지 바탕
WALL_LINE = "#ecd7a0"     # 벽지 빗금
STAGE = "#fbf0d2"         # 요약 도트 칸
FLOOR = "#efdcaa"         # 도트 밑 그림자
BAR_BG = "#efe2c0"        # 막대 홈
EXP = "#4890e0"           # 경험치 막대 (금·은의 파란 경험치 막대)
CHECK = "#2c8a3c"         # ✓ · 좋은 값
SHINY = "#b07800"         # ★ 색이 다른 개체
LEGEND = "#8a4ad0"        # ◆ ✦ 전설 · 환상
AWAY = "#2860c0"          # 탐험 중
MEGA = "#7a4ad0"          # 메가진화 글
DANGER = "#c83a24"        # 놓아주기 (되돌릴 수 없는 일)
OFF_BODY, OFF_LINE = "#e8e0cc", "#b0a488"
PRIMARY_LO = "#6a3a08"


# ---------------------------------------------------------------- 단추
class BoxButton(GSButton):
    """캔버스 단추 (kit.CButton 과 같은 말 - 동작 · 바인딩은 그대로). style:

        'menu'    시안의 글자 메뉴: 올리거나 primary 면 왼쪽에 빨간 ▶. danger 면 빨간 글
        'chip'    진한 테 2 의 네모 칩. primary 면 진한 호박빛 바탕 · 종이빛 글
        'arrow'   박스 넘기기 ◀ ▶ - 글 없이 진한 세모 (못 넘기면 흐린 세모)
    """

    danger = False
    left = False

    def want_width(self, pad=28):
        if self.style == "arrow":
            return U.h(30)
        return GSButton.want_width(self, pad)

    def draw(self):
        cv = self.cv
        cv.delete(self.tag)
        self._body_id = None
        self._arrow_id = None
        self._ink_id = None
        self._shift = 0
        self._hover = self._down = False
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        m = (self.tag, self.tag + "_m")
        on = self.enabled
        xm, ym = (x1 + x2) // 2, (y1 + y2) // 2
        if self.style == "arrow":
            self._body_id = cv.create_rectangle(x1, y1, x2, y2, fill=PAPER, outline="", tags=m)
            s = U.h(7)
            arrow(cv, xm - s // 2 - 1, ym, s, fill=INK if on else OFF_LINE, tags=m, left=self.left)
        elif self.style == "chip":
            if not on:
                body, line, ink = OFF_BODY, OFF_LINE, DIM
            elif self.primary:
                body, line, ink = BTN, INK, PAPER
            else:
                body, line, ink = PAPER, INK, INK
            self._body_id = cv.create_rectangle(x1 + 1, y1 + 1, x2 - 1, y2 - 1, fill=body, outline=line, width=2,
                                                tags=m)
            cv.create_text(xm, ym, text=self.text, fill=ink, font=self.spec, anchor="center", tags=m)
        else:
            self._body_id = cv.create_rectangle(x1, y1, x2, y2, fill=PAPER, outline="", tags=m)
            self._arrow_id = arrow(cv, x1 + U.h(6), ym, U.h(5), tags=m)
            ink = (DANGER if self.danger else INK) if on else DIM
            cv.create_text(x1 + U.h(22), ym, text=self.text, fill=ink, font=self.spec, anchor="w", tags=m)
        self._state()

    def _state(self):
        if self._body_id is None:
            return
        hot = self._hover and self.enabled
        if self.style == "chip":
            if not self.enabled:
                fill = OFF_BODY
            elif self.primary:
                fill = BTN_HI if hot else BTN
            else:
                fill = SEL if hot else PAPER
        else:
            fill = SEL if hot else PAPER
        try:
            self.cv.itemconfigure(self._body_id, fill=fill)
            if self._arrow_id is not None:
                show = self.enabled and (hot or self.primary)
                self.cv.itemconfigure(self._arrow_id, state="normal" if show else "hidden")
            want = 1 if (self._down and self.enabled) else 0
            if want != self._shift:
                self.cv.move(self.tag + "_m", 0, want - self._shift)
                self._shift = want
        except tk.TclError:
            pass


def _gs(btn, style="menu", primary=False, danger=False, left=False):
    """만들어 둔 kit.CButton 을 그대로 두고 그리는 법만 BoxButton 으로."""
    btn.__class__ = BoxButton
    btn.style, btn.primary, btn.danger, btn.left = style, primary, danger, left
    if btn.box:
        btn.draw()
    return btn


# ---------------------------------------------------------------- 박스 벽지 (옅은 빗금)
_WALLS = {}


def _wall(cv, w, h):
    """박스 칸 뒤의 벽지: 옅은 금빛 바탕에 가는 빗금 (그림 한 장)."""
    w, h = max(1, int(w)), max(1, int(h))
    ph = _WALLS.get((w, h))
    if ph is None:
        tile = Image.new("RGB", (10, 10), WALL)
        d = ImageDraw.Draw(tile)
        for i in range(10):
            d.point((i, 9 - i), fill=WALL_LINE)
        img = Image.new("RGB", (w, h), WALL)
        for yy in range(0, h, 10):
            for xx in range(0, w, 10):
                img.paste(tile, (xx, yy))
        try:
            ph = ImageTk.PhotoImage(img, master=cv)
        except tk.TclError:
            return None
        if len(_WALLS) > 8:
            _WALLS.clear()
        _WALLS[(w, h)] = ph
    return cv.create_image(0, 0, image=ph, anchor="nw")


def _square_chip(cv, x, y, label, col, spec, h, tags):
    """타입 꼬리표: 타입 빛깔의 네모 칩 (진한 테). 폭."""
    w = K.tkfont_of(cv, spec).measure(label) + U.h(16)
    cv.create_rectangle(x + 1, y + 1, x + w - 1, y + h - 1, fill=col, outline=INK, width=2, tags=tags)
    cv.create_text(x + w // 2, y + h // 2, text=label, fill=K.look_of(col)[3], font=spec, anchor="center", tags=tags)
    return w


def _bar(cv, x1, y1, x2, y2, ratio, col, tags):
    """진한 테 1 의 막대 (금·은의 체력 · 경험치 막대처럼)."""
    cv.create_rectangle(x1, y1, x2, y2, fill=BAR_BG, outline=INK, width=1, tags=tags)
    fw = int((x2 - x1 - 2) * max(0.0, min(1.0, ratio)))
    if fw > 0:
        cv.create_rectangle(x1 + 1, y1 + 1, x1 + 1 + fw, y2 - 1, fill=col, outline="", tags=tags)


# ---------------------------------------------------------------- 박스 창
class BoxWindow(DPB.BoxWindow):

    DW_PX = 330            # 요약 상자 폭
    PARTY_PX = 166         # 파티 상자 폭 (▶ 커서 · 도트 · 이름이 들게 DP 보다 조금 넓다)

    def _build(self):
        DPB.BoxWindow._build(self)
        s = U.h
        try:
            self.win.configure(bg=G_BG)
            self.cv.configure(bg=G_BG)
            self.dframe.configure(bg=PAPER, highlightthickness=0)
            self.dcv.configure(bg=PAPER)
            self.dsb.configure(bg=PAPER)
            self.dcv.pack_configure(padx=(s(10), s(2)), pady=s(8))
            self.dsb.pack_configure(pady=s(4))
            self.gframe.configure(bg=WALL)
            self.gcv.configure(bg=WALL)
            self.gsb.configure(bg=PAPER)
        except tk.TclError:
            pass
        entry(self.find_box)
        # 아래 단추 줄 = 글자 메뉴
        _gs(self.btn_party, "menu", primary=True)
        for b in (self.btn_nick, self.btn_move, self.btn_tint):
            _gs(b, "menu")
        _gs(self.btn_release, "menu", danger=True)
        _gs(self.btn_multi_move, "menu", primary=True)
        _gs(self.btn_multi_release, "menu", danger=True)
        for b in (self.btn_multi_all, self.btn_multi_clear, self.btn_multi_done):
            _gs(b, "menu")
        for b in (self.btn_party, self.btn_multi_move):
            b.spec = font(11)
        for b in (self.btn_nick, self.btn_move, self.btn_tint, self.btn_release, self.btn_multi_release,
                  self.btn_multi_all, self.btn_multi_clear, self.btn_multi_done):
            b.spec = font(11)
        # 머리 상자
        _gs(self.btn_prev, "arrow", left=True)
        _gs(self.btn_next, "arrow")
        for b in (self.btn_rename, self.btn_reload, self.btn_party_name):
            _gs(b, "chip")
        # 요약 안 단추 = 네모 칩
        _gs(self.btn_hold, "chip", primary=True)
        _gs(self.btn_unhold, "chip")
        _gs(self.btn_remember, "chip", primary=True)
        _gs(self.btn_bond, "chip", primary=True)

    # ---------------- 판 전체 ----------------
    def _paint(self):
        self._job = None
        cv = self.cv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 200 or H < 200:
            return
        cv.delete("scene")
        self._msg_ids = None
        s = U.h
        dot_bg(cv, 0, 0, W, H, tags=T)
        DW = s(self.DW_PX)
        ix1, iy1, ix2, iy2 = gbox(cv, s(10), s(8), s(10) + DW, H - s(8), tags=T)
        self._place("detail", self.dframe, ix1, iy1, ix2 - ix1, iy2 - iy1)
        self._paint_right(cv, s(10) + DW + s(8), W - s(10), H)

    def _paint_right(self, cv, x0, x2, H):
        s = U.h
        k = gbox_pad()
        # 1) 머리 상자: ◀ 박스 이름 ▶ · 이름 바꾸기 · 새로고침 / 타입 · 찾기 · 줄 세우기
        bh, th = s(28), s(26)
        top = s(8)
        hy2 = top + 2 * k + s(4) + bh + s(8) + th + s(4)
        ix1, iy1, ix2, iy2 = gbox(cv, x0, top, x2, hy2, tags=T)
        lx1, lx2 = ix1 + s(8), ix2 - s(8)
        y = iy1 + s(4)
        aw = self.btn_prev.want_width()
        self.btn_prev.layout(lx1, y, lx1 + aw, y + bh)
        nx1 = lx1 + aw + s(2)
        nw = max(s(190), K.tkfont_of(cv, font(12)).measure(self._page_text) + s(40))
        nx2 = nx1 + nw
        tg = T + ("page",)
        cv.create_rectangle(nx1, y, nx2, y + bh, fill=PAPER, outline="", tags=tg)
        cv.create_text((nx1 + nx2) // 2, y + bh // 2, text=self._page_text, fill=INK, font=font(12),
                       anchor="center", tags=tg)
        cv.create_line(nx1 + s(10), y + bh - 1, nx2 - s(10), y + bh - 1, fill=AMBER, width=2, tags=tg)
        self._boxes["page"] = (nx1, y, nx2, y + bh)
        cv.tag_bind("page", "<Button-1>", lambda _e: self.open_box_menu())
        self._hand("page")
        self.btn_next.layout(nx2 + s(2), y, nx2 + s(2) + aw, y + bh)
        rw = self.btn_rename.want_width(s(20))
        rx = nx2 + s(12) + aw
        self.btn_rename.layout(rx, y + s(2), rx + rw, y + bh - s(2))
        bw = self.btn_reload.want_width(s(20))
        self.btn_reload.layout(lx2 - bw, y + s(2), lx2, y + bh - s(2))
        y += bh + s(4)
        cv.create_line(ix1 + s(6), y, ix2 - s(6), y, fill=SEP, width=2, tags=T)
        y += s(4)
        # 타입 칩 · 찾기 밑줄 칸 · 줄 세우기 칩
        tlabel = self.btn_type.text + " ▾"
        tw = K.tkfont_of(cv, font(10)).measure(tlabel) + s(20)
        tg = T + ("tsel",)
        cv.create_rectangle(lx1 + 1, y + 1, lx1 + tw - 1, y + th - 1, fill=PAPER, outline=INK, width=2, tags=tg)
        cv.create_text(lx1 + tw // 2, y + th // 2, text=tlabel, fill=INK, font=font(10), anchor="center", tags=tg)
        self._boxes["type"] = (lx1, y, lx1 + tw, y + th)
        cv.tag_bind("tsel", "<Button-1>", lambda _e: self._open_type_menu())
        self._hand("tsel")
        right = chips(cv, lx2, y, th, SORTS, self.sort, "bsort", self.set_sort, spec=font(10), align="right",
                      hand=self._hand)
        fx = lx1 + tw + s(14)
        cv.create_text(fx, y + th // 2, text="찾기", fill=INK, font=font(10), anchor="w", tags=T)
        fx += K.tkfont_of(cv, font(10)).measure("찾기") + s(8)
        self._place("find", self.find_box, fx, y, max(s(90), right[0][1][0] - fx - s(14)), th)
        # 3) 아래 상자 높이를 먼저 (단추 줄 + 글 두 줄)
        f11 = K.tkfont_of(cv, font(11))
        msg_h = 2 * f11.metrics("linespace") + s(4)          # 알림 글 두 줄
        BOT = 2 * k + s(3) + s(26) + s(4) + msg_h + s(3)
        by1 = H - s(8) - BOT
        gy1, gy2 = hy2 + s(6), by1 - s(6)
        # 4) 데리고 다니는 포켓몬 + 박스 칸
        PW = s(self.PARTY_PX)
        self._paint_party_slots(cv, x0, gy1, x0 + PW, gy2)
        gx1 = x0 + PW + s(8)
        jx1, jy1, jx2, jy2 = gbox(cv, gx1, gy1, x2, gy2, tags=T)
        self._place("grid", self.gframe, jx1, jy1, jx2 - jx1, jy2 - jy1)
        # 5) 아래 상자: 글자 메뉴 줄 + 알림 글
        self._paint_bottom_box(cv, x0, by1, x2, H - s(8), msg_h)

    def _paint_bottom_box(self, cv, x1, y1, x2, y2, msg_h):
        s = U.h
        ix1, iy1, ix2, iy2 = gbox(cv, x1, y1, x2, y2, tags=T)
        if self.multi:
            btns = [self.btn_multi_move, self.btn_multi_release, self.btn_multi_all, self.btn_multi_clear,
                    self.btn_multi_done]
            hide = [self.btn_party, self.btn_nick, self.btn_move, self.btn_tint, self.btn_release]
        else:
            btns = [self.btn_party, self.btn_nick, self.btn_move, self.btn_tint, self.btn_release]
            hide = [self.btn_multi_move, self.btn_multi_release, self.btn_multi_all, self.btn_multi_clear,
                    self.btn_multi_done]
        for b in hide:
            b.hide()
        y = iy1 + s(3)
        rh = s(26)
        room = ix2 - ix1 - s(8)
        ws = [b.want_width(s(16)) for b in btns]
        if sum(ws) > room:                          # 좁은 창: 글자 메뉴 사이 여백을 줄인다 (글씨는 그대로)
            ws = [b.want_width(s(2)) for b in btns]
        gap = max(0, min(s(10), (room - sum(ws)) // max(1, len(btns) - 1)))
        x = ix1 + s(4)
        for b, w in zip(btns, ws):
            b.layout(x, y, x + w, y + rh)
            x += w + gap
        y += rh + s(2)
        cv.create_line(ix1 + s(6), y, ix2 - s(6), y, fill=SEP, width=2, tags=T)
        y += s(2)
        text, color = self.msg
        shown = text or self._count_text
        self._msg_w = max(40, ix2 - ix1 - s(32))
        ym = (y + iy2) // 2
        a, tid = K.text(cv, ix1 + s(16), ym, shown, font(11),
                        fill=(tone(color) if color else (INK if text else INK2)), anchor="w", width=self._msg_w,
                        tags=T)
        self._msg_ids = (None, tid)

    # ---------------- 칸 도트 (DP 것 + 원본 그림을 남겨 파티 자리용 작은 도트를 만든다) ----------------
    def _load_thumbs(self, mons):
        want = []
        for m in mons:
            if m.get("isEgg"):
                continue
            k = self._thumb_key(m)
            if k[0] and k not in self._thumbs and k not in self._thumb_busy and k not in want:
                want.append(k)
        if not want:
            return
        self._thumb_busy.update(want)
        api = self.app.api
        size = U.h(self.THUMB)

        def work():
            out = {}
            for num, skin in want:
                try:
                    path = sprite_cache.ensure(api, num, skin)
                    if not path:
                        continue
                    anim = sprites.load_animation(path, target_height=size, min_scale=0.2, max_scale=3.0,
                                                  max_frames=1, max_size=(int(size * 1.3), size))
                    out[(num, skin)] = sprites.to_rgba(anim.frames[sprites.RIGHT][0], anim.key)
                except Exception:                           # noqa: BLE001
                    pass
            return out

        def done(imgs, err):
            self._thumb_busy.difference_update(want)
            if err or not imgs or not self._alive():
                return
            raw = self.__dict__.setdefault("_thumb_raw", {})
            for k, img in imgs.items():
                try:
                    self._thumbs[k] = ImageTk.PhotoImage(img)
                    raw[k] = img
                except Exception:                           # noqa: BLE001
                    pass
            self._paint_grid()
            self._soon()
        U.run_async(self.root, work, done)

    def _fit_thumb(self, m, max_w, max_h):
        """칸 · 자리에 맞는 도트 - 칸이 도트보다 작으면 (창이 작을 때) 칸에 맞게 줄인 것 (넘쳐 옆 칸을 덮지 않게)."""
        ph = self._thumb(m)
        if ph is None or m.get("isEgg"):
            return ph
        try:
            if ph.width() <= max_w and ph.height() <= max_h:
                return ph
        except (tk.TclError, AttributeError):
            return ph
        img = getattr(self, "_thumb_raw", {}).get(self._thumb_key(m))
        if img is None:
            return ph
        r = min(max_w / float(img.width), max_h / float(img.height))
        w, h = max(8, int(img.width * r)), max(8, int(img.height * r))
        key = (self._thumb_key(m), w, h)
        cache = self.__dict__.setdefault("_thumb_small", {})
        got = cache.get(key)
        if got is None:
            if len(cache) > 300:
                cache.clear()
            try:
                got = ImageTk.PhotoImage(img.resize((w, h), Image.NEAREST))
            except Exception:                               # noqa: BLE001
                return ph
            cache[key] = got
        return got

    # ---------------- 데리고 다니는 여섯 자리 ----------------
    def _paint_party_slots(self, cv, x1, y1, x2, y2):
        s = U.h
        ix1, iy1, ix2, iy2 = gbox(cv, x1, y1, x2, y2, tags=T)
        cv.create_text(ix1 + s(8), iy1 + s(5), text="데리고 다니는", fill=BROWN, font=font(9), anchor="nw", tags=T)
        top = iy1 + s(24)
        rows = self.party_presets()
        if rows:
            name = next((p.get("name") or "파티 %d" % p.get("no") for p in rows if p.get("no") == self.party_active()),
                        "파티")
            px1, px2 = ix1 + s(6), ix2 - s(6)
            ph = s(26)
            tg = T + ("preset",)
            cv.create_rectangle(px1 + 1, top + 1, px2 - 1, top + ph - 1, fill=PAPER, outline=INK, width=2, tags=tg)
            cv.create_text((px1 + px2) // 2, top + ph // 2,
                           text=DPB._clamp(cv, name, font(10), px2 - px1 - s(30), 1) + " ▾",
                           fill=INK, font=font(10), anchor="center", tags=tg)
            self._boxes["preset"] = (px1, top, px2, top + ph)
            cv.tag_bind("preset", "<Button-1>", lambda _e: self._open_preset_menu())
            self._hand("preset")
            top += ph + s(6)
        self.btn_party_name.hide()
        n = 6
        sh = (iy2 - top - s(2)) / float(n)
        self._pslots = {}
        sx1, sx2 = ix1 + s(2), ix2 - s(2)
        for i in range(n):
            sy1 = top + i * sh
            sy2 = sy1 + sh
            mid = (sy1 + sy2) / 2
            if i < n - 1:
                cv.create_line(sx1 + s(6), sy2, sx2 - s(6), sy2, fill=SEP, tags=T)
            m = self._party_list[i] if i < len(self._party_list) else None
            if m is None:
                cv.create_text((sx1 + sx2) / 2, mid, text="- 빈 자리 -", fill=DIM, font=font(9), tags=T)
                continue
            pid = m["id"]
            sel, tgt, chk = pid == self.sel, pid == self._target, pid in self.checked
            tg = T + ("pslot",)
            fill = SEL if sel else (GOOD if chk else (HOV if pid == self._hover or tgt else PAPER))
            cv.create_rectangle(sx1, sy1 + 1, sx2, sy2 - 1, fill=fill, outline=RED if tgt else "",
                                width=2 if tgt else 1, tags=tg)
            if sel:
                arrow(cv, sx1 + s(3), mid, s(4), tags=tg)
            ph = self._fit_thumb(m, s(58), sh - 4)
            if ph is not None:
                cv.create_image(sx1 + s(36), mid, image=ph, tags=tg)
            info = m.get("info") or {}
            name = "알" if m.get("isEgg") else info.get("name", m.get("species", "?"))
            if m.get("shiny"):
                name = "★" + name
            tx = sx1 + s(64)
            cv.create_text(tx, mid - s(8), text=DPB._clamp(cv, name, font(10), sx2 - tx - s(4), 1),
                           fill=SHINY if m.get("shiny") else INK, font=font(10), anchor="w", tags=tg)
            cv.create_text(tx, mid + s(9), anchor="w", font=font(9), fill=BROWN, tags=tg,
                           text=("%d%%" % box_filter.egg_progress(m.get("egg") or {})[0]) if m.get("isEgg")
                           else "Lv.%d" % m.get("level", 0))
            if chk:
                cv.create_text(sx2 - s(4), sy2 - s(2), text="✓", fill=CHECK, font=font(12), anchor="se", tags=tg)
            self._pslots[pid] = (sx1, sy1, sx2, sy2)
        self._hand("pslot")

    # ---------------- 박스 칸 (6 × 5) ----------------
    def _paint_grid(self):
        cv = self.gcv
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.delete("all")
        s = U.h
        cols = 6
        n = len(self._page_mons)
        rows = max(5, -(-n // cols))
        pad = s(4)
        cw = (w - pad) / float(cols)
        # 다섯 줄이 늘 한 화면에 (칸 속 높이 >= 도트 높이 - 창이 가장 작아도 30칸이 다 보인다)
        ch = max(s(self.THUMB) + pad + 2, (h - pad) / 5.0)
        total = max(h, int(ch * rows + pad))
        cv.configure(scrollregion=(0, 0, w, total))
        _wall(cv, w, total)
        self._cells = {}
        for i in range(rows * cols):
            r, c = divmod(i, cols)
            x1, y1 = pad + c * cw, pad + r * ch
            x2, y2 = x1 + cw - pad, y1 + ch - pad
            if i >= n:
                cv.create_rectangle(x1, y1, x2, y2, fill="", outline=EMPTY_LINE, width=1)
                continue
            m = self._page_mons[i]
            pid = m["id"]
            sel, tgt, chk, hov = pid == self.sel, pid == self._target, pid in self.checked, pid == self._hover
            fill = SEL if sel else (GOOD if chk else (HOV if (hov or tgt) else PAPER))
            if tgt:
                line, lw = RED, 2
            elif sel:
                line, lw = INK, 2
            else:
                line, lw = CELL_LINE, 1
            cv.create_rectangle(x1, y1, x2, y2, fill=fill, outline=line, width=lw)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ph = self._fit_thumb(m, x2 - x1 - 4, y2 - y1 - 4)
            if ph is not None:
                cv.create_image(mx, my, image=ph)
            else:
                cv.create_oval(mx - 6, my - 6, mx + 6, my + 6, fill=PAPER, outline=CELL_LINE)
            if sel:
                arrow(cv, x1 + s(3), my, s(4))
            if m.get("shiny"):
                cv.create_text(x1 + 4, y1 + 2, text="★", fill=SHINY, font=font(9), anchor="nw")
            kind = None if m.get("isEgg") else L.kind_of(m.get("num"))
            if kind:
                cv.create_text(x2 - 3, y1 + 2, text="◆" if kind == "legendary" else "✦", fill=LEGEND,
                               font=font(8), anchor="ne")
            chip_l = None
            if chk:                                 # ✓ 는 도트 위가 아니라 작은 네모 칩 위에
                c_id = cv.create_text(x2 - 3, y2 - 2, text="✓", fill=CHECK, font=font(12), anchor="se")
                bb = cv.bbox(c_id)
                if bb:
                    chip_l = bb[0] - 2
                    cv.create_rectangle(chip_l, bb[1], x2 - 1, y2 - 1, fill=GOOD, outline=CHECK, width=2)
                    cv.tag_raise(c_id)
            if m.get("away"):                       # 도트 위에 글이 겹치지 않게 종이빛 띠 위에
                a_id = cv.create_text(mx, y2 - 2, text="탐험 중", fill=AWAY, font=font(8), anchor="s")
                bb = cv.bbox(a_id)
                if bb and chip_l is not None and bb[2] > chip_l - 1:      # ✓ 칩과 겹치면 한 줄 위로
                    cv.move(a_id, 0, -(y2 - 2 - (cv.bbox(c_id) or bb)[1]) - 1)
                    bb = cv.bbox(a_id)
                if bb:
                    cv.create_rectangle(x1 + 2, bb[1] - 1, x2 - 2, bb[3], fill=fill, outline="")
                    cv.tag_raise(a_id)
            self._cells[pid] = (x1, y1, x2, y2)
        # 마우스가 올라간 포켓몬의 이름 (진한 테의 네모 칩)
        m = self._by_id.get(self._hover) if self._hover else None
        box = self._cells.get(self._hover) if m is not None else None
        if box:
            info = m.get("info") or {}
            name = "알" if m.get("isEgg") else info.get("name", m.get("species", "?"))
            tip = "%s  Lv.%s" % (name, "-" if m.get("isEgg") else m.get("level", "?"))
            f = K.tkfont_of(cv, font(9))
            tw = f.measure(tip) + s(16)
            tx = min(max(tw / 2 + 2, (box[0] + box[2]) / 2), w - tw / 2 - 2)
            ty = max(s(22), box[1] - 2)
            cv.create_rectangle(tx - tw / 2, ty - s(20), tx + tw / 2, ty, fill=PAPER, outline=INK, width=2)
            cv.create_text(tx, ty - s(10), text=tip, fill=INK, font=font(9))

    # ---------------- 요약 ----------------
    def _paint_detail(self, top=False):
        """요약: 도트 칸 · 이름 · 타입은 늘 위에, 그 아래는 쪽 하나 (칩으로 고른다)."""
        self._job_d = None
        cv = self.dcv
        try:
            w, vh = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.delete("all")
        for b in (self.btn_hold, self.btn_unhold, self.btn_remember, self.btn_bond):
            b.hide()
        s = U.h
        d = self._d
        x1, x2 = 0, w - s(2)
        if not d:
            arrow(cv, w // 2 - s(70), s(90), s(5), tags=D)
            cv.create_text(w // 2 - s(56), s(90), text="포켓몬을 고르세요", fill=INK2, font=font(12), anchor="w",
                           tags=D)
            return
        y = 0
        # 도트 칸: 얇은 두 겹 테 + 왼쪽 위 진한 번호 칩
        sh = s(120)
        gbox(cv, x1, y, x2, y + sh, fill=STAGE, tags=D, k=0.5)
        cv.create_oval(w // 2 - s(60), y + sh - s(30), w // 2 + s(60), y + sh - s(12), fill=FLOOR, outline="",
                       tags=D)
        f9 = K.tkfont_of(cv, font(9))
        nw = f9.measure(d["num"]) + s(12)
        cv.create_rectangle(x1 + s(8), y + s(8), x1 + s(8) + nw, y + s(8) + s(20), fill=INK, outline="", tags=D)
        cv.create_text(x1 + s(8) + nw // 2, y + s(18), text=d["num"], fill=PAPER, font=font(9), anchor="center",
                       tags=D)
        a = cv.create_image(w // 2, y + sh // 2 + s(2), image=self.d_art.image or "", tags=D)
        b = cv.create_text(w // 2, y + sh // 2, text="" if self.d_art.image else self.d_art.text,
                           fill=tone(self.d_art.fg), font=font(11), tags=D)
        self.d_art.ids = (a, b)
        y += sh + s(8)
        # 이름 · 성별 · Lv (금·은의 상자 속 '이름 / Lv' 처럼)
        t = cv.create_text(x1 + s(4), y + s(12), text=d["name"], fill=SHINY if d["m"].get("shiny") else INK,
                           font=font(14), anchor="w", tags=D)
        bb = cv.bbox(t)
        if d.get("gender") and bb:
            cv.create_text(bb[2] + s(6), y + s(12), text=d["gender"], fill=d.get("gender_fg", INK2), font=font(12),
                           anchor="w", tags=D)
        cv.create_text(x2 - s(4), y + s(12), text=d["lv"], fill=INK, font=font(12), anchor="e", tags=D)
        y += s(28)
        if d.get("sub"):
            _a, t2 = K.text(cv, x1 + s(4), y, d["sub"], font(9), fill=BROWN, tags=D, width=x2 - x1 - s(8))
            y = cv.bbox(t2)[3] + s(6)
        cx = x1 + s(4)
        for label, col in d.get("chips") or []:
            cx += _square_chip(cv, cx, y, label, col, font(9), s(22), D) + s(5)
        y += s(30)
        if d.get("egg"):
            y = self._d_egg(cv, d, x1, x2, y)
        else:
            pages = [("info", "정보"), ("stats", "능력"), ("moves", "기술")]
            if self.bond.visible:
                pages.append(("mega", "메가진화"))
            if self._dpage not in dict(pages):
                self._dpage = "info"
            chips(cv, x1 + s(2), y, s(28), pages, self._dpage, "dpg", self._pick_dpage, spec=font(11), tags=D)
            cv.tag_bind("dpg", "<Enter>", lambda _e: cv.configure(cursor="hand2"))
            cv.tag_bind("dpg", "<Leave>", lambda _e: cv.configure(cursor=""))
            y += s(28) + s(8)
            cv.create_line(x1, y, x2, y, fill=INK, width=2, tags=D)
            y += s(10)
            y = {"info": self._d_info, "stats": self._d_stats, "moves": self._d_moves,
                 "mega": self._d_bond}[self._dpage](cv, d, x1 + s(4), x2 - s(4), y)
        total = y + s(12)
        cv.configure(scrollregion=(0, 0, w, max(total, vh)))
        if top:
            cv.yview_moveto(0)
        for b in (self.btn_hold, self.btn_unhold, self.btn_remember, self.btn_bond):
            if b.box:
                b.draw()

    def _label(self, cv, x, y, text):
        cv.create_text(x, y, text=text, fill=BROWN, font=font(9), anchor="nw", tags=D)

    def _d_info(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        for title, name, note in (("특성", d["ability"], d["ability_note"]), ("성격", d["nature"], d["nature_note"])):
            self._label(cv, x1, y + 1, title)
            y = self._wrap(cv, x1 + s(40), y, name, font(10), width=iw - s(40))
            y = self._wrap(cv, x1 + s(40), y + 2, note, font(9), fill=INK2, width=iw - s(40)) + s(10)
        # 지닌 도구
        self._label(cv, x1, y + 1, "도구")
        bw1, bw2 = self.btn_hold.want_width(s(14)), self.btn_unhold.want_width(s(14))
        self.btn_unhold.layout(x2 - bw2, y - s(4), x2, y + s(22))
        self.btn_hold.layout(x2 - bw2 - s(6) - bw1, y - s(4), x2 - bw2 - s(6), y + s(22))
        y += s(26)
        tx = x1 + s(40)
        if d["held"]:
            ph = item_icons.photo(d["held"], 24)
            if ph is not None:
                cv.create_image(x1 + s(14), y + s(10), image=ph, tags=D)
        y = self._wrap(cv, tx, y, d["held_text"], font(9), fill=INK if d["held"] else INK2, width=iw - s(40)) + s(10)
        # 경험치 (파란 막대)
        ratio, text = d["exp"]
        self._label(cv, x1, y, "경험치")
        cv.create_text(x2, y, text=text, fill=INK2, font=font(8), anchor="ne", tags=D)
        y += s(18)
        _bar(cv, x1, y, x2, y + s(9), ratio, EXP, D)
        y += s(17)
        if d.get("friend"):
            hearts, num, msg = d["friend"]
            self._label(cv, x1, y, "친밀도")
            cv.create_text(x1 + s(48), y - 1, text=hearts, fill="#e04888", font=font(10), anchor="nw", tags=D)
            cv.create_text(x2, y, text=num, fill=INK2, font=font(9), anchor="ne", tags=D)
            y = self._wrap(cv, x1, y + s(18), msg, font(9), fill=INK2, width=iw) + s(10)
        if d.get("evo"):
            self._label(cv, x1, y, "진화")
            y += s(18)
            for line in d["evo"]:
                y = self._wrap(cv, x1, y, line, font(9), width=iw) + s(3)
        return y

    def _d_stats(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        y = self._wrap(cv, x1, y, d["ivsum"], font(9), fill=CHECK, width=iw) + s(8)
        for label, v, iv, hy, mx in d["rows"]:
            cv.create_text(x1, y, text=label, fill=BROWN, font=font(9), anchor="nw", tags=D)
            cv.create_text(x1 + s(84), y, text=str(v), fill=INK, font=font(10), anchor="ne", tags=D)
            bx1, bx2 = x1 + s(92), x2 - s(66)
            col = GREEN if iv == 31 else (AMBER if iv >= 26 else "#b4a47c")
            _bar(cv, bx1, y + 3, bx2, y + s(13), v / float(mx or 1), col, D)
            cv.create_text(x2, y, text="개체 %d%s" % (iv, "✦" if hy else ""),
                           fill=CHECK if iv == 31 else INK2, font=font(8), anchor="ne", tags=D)
            y += s(22)
        y = self._wrap(cv, x1, y + s(4), d["evsum"], font(9), fill=INK2, width=iw)
        return y

    def _d_moves(self, cv, d, x1, x2, y):
        """기술 넷: 금·은의 기술 목록처럼 줄 - 고른 줄은 빨간 ▶ 와 옅은 금빛, 왼쪽에 타입 빛깔 네모."""
        s = U.h
        iw = x2 - x1
        dex = self.app.dex
        mh = s(44)
        for i, (mv, md) in enumerate(d["moves"]):
            col = U.TYPE_COLOR.get((md or {}).get("type"), "#a0a0a8")
            tg = D + ("mv%d" % i,)
            picked = bool(self._move_pick and self._move_pick[0] == i)
            cv.create_rectangle(x1, y, x2, y + mh, fill=SEL if picked else PAPER, outline="", tags=tg)
            cv.create_line(x1 + s(4), y + mh, x2 - s(4), y + mh, fill=SEP, tags=tg)
            if picked:
                arrow(cv, x1 + s(2), y + mh // 2, s(5), tags=tg)
            cv.create_rectangle(x1 + s(14), y + s(9), x1 + s(22), y + mh - s(9), fill=col, outline=INK, width=1,
                                tags=tg)
            cv.create_text(x1 + s(30), y + s(14), text=mv, fill=INK, font=font(11), anchor="w", tags=tg)
            sub = "%s · %s" % (dex.type_name((md or {}).get("type")) if dex else "", MT.short_line(md))
            cv.create_text(x1 + s(30), y + mh - s(12), text=sub, fill=BROWN, font=font(9), anchor="w", tags=tg)
            cv.tag_bind("mv%d" % i, "<Button-1>", lambda _e, n=i, dd=md, t=mv: self.pick_move(n, dd, t))
            cv.tag_bind("mv%d" % i, "<Enter>", lambda _e: cv.configure(cursor="hand2"))
            cv.tag_bind("mv%d" % i, "<Leave>", lambda _e: cv.configure(cursor=""))
            y += mh + s(2)
        if not d["moves"]:
            y = self._wrap(cv, x1, y, "아는 기술이 없습니다.", font(10), fill=INK2, width=iw) + s(6)
        if self._move_pick:
            _i, md, name = self._move_pick
            y = self._wrap(cv, x1, y + s(4), MT.stat_line(md, name or "?"), font(9), fill="#a05a10", width=iw)
            y = self._wrap(cv, x1, y + s(2), MT.desc(md), font(9), fill=INK2, width=iw) + s(6)
        if d.get("pending"):
            y = self._wrap(cv, x1, y + s(2), d["pending"], font(9), fill=CHECK, width=iw) + s(6)
        rw = self.btn_remember.want_width(s(20))
        self.btn_remember.layout(x2 - rw, y + s(6), x2, y + s(34))
        return y + s(38)

    def _d_bond(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        b = self.bond
        if b.btn_spec:
            self.btn_bond.configure(text=b.btn_spec[0], state="normal")
            bw = self.btn_bond.want_width(s(20))
            self.btn_bond.layout(x2 - bw, y, x2, y + s(28))
            y += s(36)
        for row in b.lines:
            if row[0] == "kv":
                _k, label, val, col = row
                self._label(cv, x1, y + 1, label)
                y = self._wrap(cv, x1 + s(48), y, val, font(9), fill=tone(col) if col != BD.MEGA else MEGA,
                               width=iw - s(48)) + s(4)
            elif row[0] == "bar":
                _k, label, num, ratio, col = row
                y2 = self._wrap(cv, x1, y, label, font(9), width=iw - s(60))
                cv.create_text(x2, y, text=num, fill=INK2, font=font(8), anchor="ne", tags=D)
                _bar(cv, x1, y2 + 3, x2, y2 + s(11), ratio, col, D)
                y = y2 + s(17)
            else:
                _k, text, col = row
                y = self._wrap(cv, x1, y, text, font(9), fill=MEGA if col == BD.MEGA else tone(col), width=iw) + s(4)
        dex = self.app.dex
        for pv in b.previews:
            cv.create_line(x1, y + s(4), x2, y + s(4), fill=SEP, width=2, tags=D)
            y += s(12)
            t = cv.create_text(x1, y, text=pv["name"], fill=MEGA, font=font(11), anchor="nw", tags=D)
            bb = cv.bbox(t)
            cv.create_text((bb[2] if bb else x1) + s(8), y + 2, text="메가진화하면", fill=BROWN, font=font(8),
                           anchor="nw", tags=D)
            y += s(22)
            cx = x1
            for tp in pv["types"]:
                label = dex.type_name(tp) if dex else tp
                cx += _square_chip(cv, cx, y, label, U.TYPE_COLOR.get(tp, "#a0a0a8"), font(8), s(20), D) + s(4)
            y += s(26)
            if pv.get("abilityKr"):
                y = self._wrap(cv, x1, y, "특성 %s (%s)" % (pv["abilityKr"], "바뀜" if pv["abilityChanged"] else "그대로"),
                               font(9), width=iw) + s(2)
            for _k, label, now, after, dlt in pv["rows"]:
                cv.create_text(x1, y, text=label, fill=BROWN, font=font(8), anchor="nw", tags=D)
                cv.create_text(x1 + s(110), y, text="%d → %d" % (now, after), fill=INK if dlt else DIM,
                               font=font(8), anchor="ne", tags=D)
                cv.create_text(x2, y, text=BD.delta_text(dlt),
                               fill=CHECK if dlt > 0 else (DANGER if dlt < 0 else DIM), font=font(8),
                               anchor="ne", tags=D)
                y += s(16)
        return y

    def _d_egg(self, cv, d, x1, x2, y):
        s = U.h
        x1, x2 = x1 + s(4), x2 - s(4)
        iw = x2 - x1
        self._label(cv, x1, y, "알의 상태")
        y = self._wrap(cv, x1, y + s(18), d["mood"], font(9), width=iw) + s(6)
        _bar(cv, x1, y, x2, y + s(9), d["ratio"], d["egg_color"], D)
        y += s(15)
        y = self._wrap(cv, x1, y, d["time"], font(9), fill=INK2, width=iw) + s(4)
        y = self._wrap(cv, x1, y, d["left"], font(10), width=iw) + s(10)
        self._label(cv, x1, y, "자라는 곳")
        y = self._wrap(cv, x1, y + s(18), d["where"], font(9), fill=CHECK if d["where_ok"] else DANGER,
                       width=iw) + s(4)
        from common.korean import natural
        y = self._wrap(cv, x1, y, natural("알도 데리고 다니는 여섯 자리 중 하나를 차지합니다. 알을 데리고 다니는 동안에는 "
                                          "포켓몬이 그만큼 적게 따라다닙니다."), font(8), fill=DIM, width=iw) + s(4)
        if d.get("day"):
            y = self._wrap(cv, x1, y, "받은 날 %s" % d["day"], font(8), fill=DIM, width=iw)
        return y


# 지닌 도구 고르기 창 - 스킨은 box 모듈에서 HeldPicker 를 이름으로 찾는다 (DP 의 것을 그대로 내보낸다:
# DP 틀 그대로 빛깔만 이 테마로 옮겨진다).
from ..dp.box import HeldPicker, _clamp  # noqa: E402,F401
