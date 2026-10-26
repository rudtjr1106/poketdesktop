# -*- coding: utf-8 -*-
"""금·은 테마 - 가방 (도구 칸). 시안 G 의 가방 그대로 (판 배치는 _gbc.GSBag):

    왼쪽 위     ◀ 주머니 ▶ · 고른 도구의 둥근 그림 칸 · 이름 · '등급 · 종류 · N개'
    왼쪽 아래   누구에게 쓸까? - 찾기 · 줄 세우기 칩 · 포켓몬 줄 (고른 것은 빨간 ▶, 오른쪽에 지닌 도구 등)
    가운데      큰 상자: 찾기 밑줄 칸 · 소지금 / 이름·종류·등급·개수 칩 · 몇 종 · 새로고침 /
                묶음 머리(갈색 '열매 · 3종') 아래 도구 줄 (▶ · 그림 · 이름 · 등급 · ×개수)
    아래        넓은 상자: 설명 + 누구에게 쓸지 안내 / 오른쪽 메뉴 '▶ ○○ 쓰기' · 팔기 · 여러 개 팔기

동작은 DP 도구 칸(skins/dp/bag.py → ui_bag.BagWindow) 그대로다 - 그리는 것만 바꾼다.
"""
from ... import item_icons
from ... import ui_bag as B
from ... import ui_common as U
from ..dp import bag as DPB
from ..dp import font
from ..dp import kit as K
from ..dp.scene import T
from . import BROWN, DIM, HOV, INK, INK2
from ._gbc import GSBag, arrow, as_gs, chips, chips_width, entry, paper_list

POCKETS = DPB.POCKETS            # (화면 밖에서 쓰던 이름 - bag_tabs · 검사)
RARITY_KR = DPB.RARITY_KR
RARE = {"common": "#6a5a44", "uncommon": "#2c8a3c", "rare": "#2860c0", "epic": "#8a4ad0", "legendary": "#c06810"}


class BagWindow(GSBag, DPB.BagWindow):

    def _build(self):
        DPB.BagWindow._build(self)
        entry(self.item_find)
        paper_list(self.items_vl)
        as_gs(self.use_btn, "menu", primary=True)
        self.use_btn.spec = font(12)
        as_gs(self.sell_btn, "menu")
        self.sell_btn.spec = font(11)
        as_gs(self.sell_many_btn, "menu")
        self.sell_many_btn.spec = font(11)
        self.refresh_btn = as_gs(K.CButton(self.cv, "새로고침", self.reload, "gray", font(9)), "chip")
        self._gs_setup()

    # ---------------- 판 조각 (GSBag 이 묻는다) ----------------
    def _gs_has_pick(self):
        return bool(self._item)

    def _gs_card(self):
        it = self._item
        if not it:
            return "도구를 고르세요", "", None
        bits = []
        if it.get("rarity") in RARITY_KR:
            bits.append(RARITY_KR[it["rarity"]])
        bits.append(B.CAT_KR.get(it.get("cat"), it.get("cat") or ""))
        bits.append("%d개" % self.bag.get(it["id"], 0))

        def art(cv, cx, cy, d):
            ph = item_icons.photo(it["id"], 48)
            if ph is not None:
                cv.create_image(cx, cy, image=ph, tags=T)
        return it["kr"], " · ".join(b for b in bits if b), art

    def _gs_menu(self):
        return [self.use_btn, self.sell_btn, self.sell_many_btn]

    def _gs_plates_title(self, width):
        it = self._item
        return ("누구에게 쓸까?", B.target_hint(it) if it else "", self._mon_note, self._boxes(self.cv, width))

    def _gs_mid(self, cv, x1, y1, x2, y2):
        """큰 상자: 찾기 · 소지금 / 칩 · 개수 · 새로고침 / 도구 목록."""
        ix1, iy1, ix2, iy2 = self._gs_list_frame(cv, x1, y1, x2, y2)
        lx1, lx2 = ix1 + U.h(10), ix2 - U.h(8)
        th = U.h(26)
        y = iy1 + U.h(6)
        money = "소지금 " + self._lcd_text()
        mw = K.tkfont_of(cv, font(11)).measure(money)
        cv.create_text(lx1, y + th // 2, text="찾기", fill=INK, font=font(10), anchor="w", tags=T)
        ex = lx1 + U.h(40)
        cv.create_text(lx2, y + th // 2, text=money, fill=INK, font=font(11), anchor="e", tags=T)
        self._place("ifind", self.item_find, ex, y, max(U.h(80), lx2 - mw - U.h(18) - ex), th)
        y += th + U.h(8)
        ch = U.h(24)
        chips(cv, lx1, y, ch, B.ITEM_SORTS, self.item_sort, "srt", self.set_item_sort, hand=self._hand)
        rw = self.refresh_btn.want_width(U.h(20))
        self.refresh_btn.layout(lx2 - rw, y, lx2, y + ch)
        line = self._line_text()
        left_end = lx1 + chips_width(cv, B.ITEM_SORTS) + U.h(12)
        if lx2 - rw - U.h(10) - K.tkfont_of(cv, font(9)).measure(line) >= left_end:
            cv.create_text(lx2 - rw - U.h(10), y + ch // 2, text=line, fill=BROWN, font=font(9), anchor="e", tags=T)
        else:                                       # 좁으면 칩 줄 아래 한 줄로
            y += ch + U.h(4)
            cv.create_text(lx1, y + U.h(8), text=line, fill=BROWN, font=font(9), anchor="w", tags=T)
            ch = U.h(16)
        ly1 = y + ch + U.h(8)
        if self._items_state == "list":
            self._place("items", self.items_vl.frame, ix1 + U.h(2), ly1, ix2 - ix1 - U.h(4), iy2 - ly1 - 2)
        else:
            self._hide("items")
            note = self._items_note if self._items_state == "nomatch" else \
                "가방이 비어 있다.\n야생 포켓몬을 잡거나 배틀에서 도구를 주울 수 있다."
            K.text(cv, (lx1 + lx2) // 2, ly1 + U.h(40), note, font(11), fill=INK2, anchor="n", justify="center",
                   width=lx2 - lx1 - 20, tags=T)

    # ---------------- 목록 한 줄 (시안 .g .ln · .g .gh) ----------------
    def _draw_item_row(self, cv, data, x, y, w, h, tags, hover=None):
        kind, val = data
        if kind == "head":
            cat, n = val[0], val[1]
            sub = val[2] if len(val) > 2 else None
            label = ("%s · %s · %d종" % (B.CAT_KR.get(cat, cat), sub, n)) if sub else \
                "%s · %d종" % (B.CAT_KR.get(cat, cat), n)
            cv.create_text(x + U.h(8), y + h - U.h(4), text=label, fill=BROWN, font=font(9), anchor="sw", tags=tags)
            return
        it = val
        usable = (it.get("effect") or {}).get("kind") in B.USABLE
        sel = it["id"] == self.item_id
        if hover is not None and not sel:
            cv.create_rectangle(x, y, x + w, y + h, fill=HOV, outline="", tags=tags)
        m = y + h // 2
        if sel:
            arrow(cv, x + U.h(6), m, U.h(5), tags=tags)
        icon = item_icons.photo(it["id"], 20)
        ix = x + U.h(34)
        if icon is not None:
            cv.create_image(ix, m, image=icon, tags=tags)
        else:
            cv.create_rectangle(ix - 3, m - 3, ix + 3, m + 3, fill=B.CAT_COLOR.get(it.get("cat"), DIM), outline="",
                                tags=tags)
        fg = INK if usable else DIM
        nid = cv.create_text(x + U.h(52), m, text=it["kr"], fill=fg, font=font(11), anchor="w", tags=tags)
        cx = x + w - U.h(10)
        cv.create_text(cx, m, text="×%d" % self.bag.get(it["id"], 0), fill=fg, font=font(11), anchor="e", tags=tags)
        rk = it.get("rarity")
        if rk in RARITY_KR:
            rx = cx - U.h(50)
            f = K.tkfont_of(cv, font(9))
            b = cv.bbox(nid)
            if not b or b[2] + U.h(10) <= rx - f.measure(RARITY_KR[rk]):
                cv.create_text(rx, m, text=RARITY_KR[rk], fill=RARE[rk] if usable else DIM, font=font(9),
                               anchor="e", tags=tags)

    # ---------------- 그 밖 ----------------
    def _gs_desc(self):
        it = self._item
        if not it:
            return ("도구를 고르세요",
                    "◀ ▶ 로 주머니를 넘기고, 목록에서 도구를 고르면 여기에 설명이 뜬다.", "")
        title, body, _art = self._band_content()
        return title, body, ""
