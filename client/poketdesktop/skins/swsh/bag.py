# -*- coding: utf-8 -*-
"""소드·실드 테마 - 가방 (도구 칸). 시안 K 의 가방 그림 그대로 (판은 _bagscene.SwScene).

    머리       '가방' (흰 큰 글씨, 하늘 모서리 위) · 주머니 알약 (고른 것 분홍) · 남색 판 ([새로고침] · 돈 · 개수 줄)
    왼쪽 판    찾기 칸 · 줄 세우기 알약 넷 (고른 것 분홍) / 목록 -
               묶음 머리는 흐린 굵은 글씨, 고른 줄은 남색 바탕 + 흰 글씨 + 왼쪽 분홍 띠
    오른쪽 위  남색 그림 칸 (도구 그림 - item_icons) · 이름 · 분홍 꼬리표 (종류 · 등급 · 개수) · 설명
    오른쪽     누구에게 쓸까? · 포켓몬 찾기 · 판 목록 (고른 것은 하늘 테) · 병뚜껑 능력 칸 · 노력치 칸
    아래       [팔기] [여러 개 팔기] (흰 알약) · 큰 분홍 단추 ('○○ 쓰기')

동작은 DP 도구 칸(그 밑의 기본 가방) 그대로다 - 주머니 · 찾기 · 줄 세우기 · 쓰기 · 팔기 · 알림.
"""
from common.korean import natural

from ... import item_icons
from ... import ui_bag as B
from ... import ui_common as U
from ..dp import font
from ..dp import bag as DPB
from ..dp import kit as K
from ..dp.scene import T
from . import DIMK, MAG, NAVY, ON_NAVY_DIM, SKY
from . import _sw as S
from ._bagscene import SwScene


class BagWindow(SwScene, DPB.BagWindow):

    def _build(self):
        DPB.BagWindow._build(self)
        self._sw_restyle()
        S.flat_entry(self.item_find)
        S.paper_list(self.items_vl)
        S.restyle(self.use_btn, "go")
        S.restyle(self.sell_btn, "white")
        S.restyle(self.sell_many_btn, "white")
        self.HEAD_H = U.h(22)

    # ---------------- 왼쪽 판 ----------------
    def _sw_list(self, cv, x1, y1, x2, y2):
        """찾기 칸 + 줄 세우기 알약 넷 (자리가 되면 같은 줄) / 목록. 개수 줄이 머리에 안 들었으면 찾기 칸 안 오른쪽에."""
        s = U.h
        fh = s(30)
        y = y1
        f10 = K.tkfont_of(cv, font(10))
        seg_w = sum(f10.measure(lb) + s(18) for _k, lb in B.ITEM_SORTS) + s(5) * (len(B.ITEM_SORTS) - 1)
        inside = not getattr(self, "_count_shown", False)
        count_w = (K.tkfont_of(cv, font(9)).measure(self._line_text()) + s(24)) if inside else 0
        label_w = f10.measure("찾기:") + s(20)
        one = (x2 - x1) - seg_w - s(8) >= label_w + s(100) + count_w
        fx2 = x2 - seg_w - s(8) if one else x2
        ex = S.field(cv, x1, y, fx2, y + fh, "찾기:", tags=T)
        cx = self._count_text(cv, fx2, y + fh // 2) if inside else fx2 - s(4)
        self._place("ifind", self.item_find, ex, y + s(5), max(s(50), cx - ex - s(8)), fh - s(10))
        if one:
            S.seg(cv, fx2 + s(8), y, x2, fh, B.ITEM_SORTS, self.item_sort, "srt", self.set_item_sort,
                  hand=self._hand)
            y += fh + s(6)
        else:
            y += fh + s(6)
            S.seg(cv, x1, y, x2, s(28), B.ITEM_SORTS, self.item_sort, "srt", self.set_item_sort, hand=self._hand)
            y += s(28) + s(6)
        if self._items_state == "list":
            self._place("items", self.items_vl.frame, x1 - s(6), y, x2 - x1 + s(10), y2 - y)
        else:
            self._hide("items")
            note = self._items_note if self._items_state == "nomatch" else \
                "가방이 비어 있다.\n야생 포켓몬을 잡거나 배틀에서 도구를 주울 수 있다."
            K.text(cv, (x1 + x2) // 2, y + s(40), note, font(11), anchor="n", justify="center",
                   width=x2 - x1 - 20, tags=T)

    def _draw_item_row(self, cv, data, x, y, w, h, tags, hover=None):
        kind, val = data
        s = U.h
        if kind == "head":                                   # .gh - 흐린 굵은 글씨
            cat, n = val[0], val[1]
            sub = val[2] if len(val) > 2 else None
            label = ("%s · %s · %d종" % (B.CAT_KR.get(cat, cat), sub, n)) if sub else \
                "%s · %d종" % (B.CAT_KR.get(cat, cat), n)
            m = y + h // 2 + s(3)
            cv.create_oval(x + s(8), m - s(3), x + s(14), m + s(3), fill=B.CAT_COLOR.get(cat, DIMK), outline="",
                           tags=tags)
            cv.create_text(x + s(20), m, text=label, fill=DIMK, font=font(9), anchor="w", tags=tags)
            return
        it = val
        usable = (it.get("effect") or {}).get("kind") in B.USABLE
        sel = it["id"] == self.item_id
        r = s(9)
        if sel:                                              # .ln.sel - 남색 + 왼쪽 분홍 띠
            K.rrect(cv, x + s(2), y + s(1), x + w - s(4), y + h - s(1), r, fill=MAG, tags=tags)
            K.rrect(cv, x + s(8), y + s(1), x + w - s(4), y + h - s(1), r, fill=NAVY, tags=tags)
        elif hover is not None:
            K.rrect(cv, x + s(8), y + s(1), x + w - s(4), y + h - s(1), r, fill="#eceef8", tags=tags)
        m = y + h // 2
        icon = item_icons.photo(it["id"], 22)
        ix = x + s(26)
        if icon is not None:
            cv.create_image(ix, m, image=icon, tags=tags)
        else:
            cv.create_oval(ix - s(4), m - s(4), ix + s(4), m + s(4), fill=B.CAT_COLOR.get(it.get("cat"), DIMK),
                           outline="", tags=tags)
        if sel:
            fg, sub = ("#ffffff", SKY) if usable else (ON_NAVY_DIM, ON_NAVY_DIM)
        else:
            fg, sub = (NAVY, None) if usable else (DIMK, DIMK)
        nid = cv.create_text(x + s(44), m, text=it["kr"], fill=fg, font=font(11), anchor="w", tags=tags)
        cx = x + w - s(16)
        cv.create_text(cx, m, text="×%d" % self.bag.get(it["id"], 0), fill=fg, font=font(11), anchor="e",
                       tags=tags)
        rk = it.get("rarity")
        if rk in DPB.RARITY_KR:
            rx = cx - s(46)
            f = K.tkfont_of(cv, font(9))
            b = cv.bbox(nid)
            if not b or b[2] + s(10) <= rx - f.measure(DPB.RARITY_KR[rk]):
                col = sub or DPB.RARE[rk]
                cv.create_text(rx, m, text=DPB.RARITY_KR[rk], fill=col, font=font(9), anchor="e", tags=tags)

    # ---------------- 오른쪽 ----------------
    def _sw_desc(self):
        it = self._item
        if not it:
            return ("도구를 고르세요", None,
                    "주머니를 고르고, 목록에서 도구를 고르면 여기에 설명이 뜬다.", None)
        tag = "%s · %s%d개" % (B.CAT_KR.get(it["cat"], it["cat"]),
                              (DPB.RARITY_KR[it["rarity"]] + " · ") if it.get("rarity") in DPB.RARITY_KR else "",
                              self.bag.get(it["id"], 0))

        def art(cv, x, y, sz):
            ph = item_icons.photo(it["id"], 44)
            if ph is not None:
                cv.create_image(x + sz // 2, y + sz // 2, image=ph, tags=T)
        return it["kr"], tag, natural(B.item_desc(it)), art

    def _sw_who(self):
        it = self._item
        return ("누구에게 쓸까?", B.target_hint(it) if it else "", self._mon_note,
                self._boxes(self.cv, getattr(self, "_who_w", U.h(300))))

    def _sw_action(self):
        return self.use_btn
