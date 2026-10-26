# -*- coding: utf-8 -*-
"""소드·실드 테마 - 가방의 기술머신 칸. 도구 칸과 같은 시안 판 (_bagscene.SwScene - '기술머신' 알약이 켜진 채,
머리 남색 판의 둘째 줄은 '기술머신 · 상점에서 살 수 없다').

    왼쪽 판    (가진 것만 | 전부) 알약 · (타입 ▾)(분류 ▾) 알약 / 목록 - 번호 · 이름 · 타입 꼬리표 · 분류,
               고른 줄은 남색 바탕 + 흰 글씨 + 왼쪽 분홍 띠, 새로 받은 것은 노란 점
    오른쪽 위  남색 칸에 타입 빛깔 원 · 기술머신 이름 · 분홍 꼬리표 (타입 · 분류 · 위력 …) · 설명
    오른쪽     배울 수 있는 포켓몬 (이미 배운 것은 회색)
    아래       [새 기술머신 N개] · 큰 분홍 '가르치기'

동작은 DP 기술머신 칸(그 밑의 기본 칸) 그대로다.
"""
from ... import ui_common as U
from ... import ui_tms as TM
from ..dp import font
from ..dp import kit as K
from ..dp import tms as DPT
from ..dp.scene import T
from . import DIMK, MAG, NAVY, ON_NAVY_DIM, PAPER2, SKY
from . import _sw as S
from ._bagscene import SwScene, type_art


class TmWindow(SwScene, DPT.TmWindow):

    def _build(self):
        DPT.TmWindow._build(self)
        self._sw_restyle()
        S.paper_list(self.tms_vl)
        S.restyle(self.use_btn, "go")
        S.restyle(self.fresh_btn, "red")

    # ---------------- 왼쪽 판 ----------------
    def _sw_list(self, cv, x1, y1, x2, y2):
        """(가진 것만 | 전부) + (타입 ▾)(분류 ▾) 알약 (자리가 되면 한 줄) / 개수 줄 / 목록."""
        s = U.h
        th = s(28)
        f10 = K.tkfont_of(cv, font(10))
        drops = [(key, text + " ▾") for key, text in (("type", self.type_btn.text), ("cat", self.cat_btn.text))]
        dws = [f10.measure(lb) + s(26) for _k, lb in drops]
        seg_w = sum(f10.measure(lb) + s(30) for lb in ("가진 것만", "전부"))
        one = seg_w + s(10) + sum(dws) + s(6) <= x2 - x1
        y = y1
        S.seg(cv, x1, y, x1 + seg_w if one else x2, th, [("have", "가진 것만"), ("all", "전부")],
              "have" if self.only_have else "all", "flt",
              lambda k: (k == "have") != self.only_have and self._toggle_filter(), hand=self._hand)
        if one:
            x = x2 - sum(dws) - s(6)
        else:
            y += th + s(6)
            x = x1
        # 타입 · 분류 드롭다운 알약 (누르면 그 알약 바로 아래에 메뉴 - DP _menu)
        boxes = {}
        for (key, lb), w in zip(drops, dws):
            tg = T + ("tmf", "tmf_" + key)
            K.rrect(cv, x, y, x + w, y + th, th // 2, fill=PAPER2, tags=tg)
            cv.create_text(x + w // 2, y + th // 2, text=lb, fill=NAVY, font=font(10), anchor="center", tags=tg)
            cv.tag_bind("tmf_" + key, "<Button-1>",
                        lambda _e, k=key: self._open_type_menu() if k == "type" else self._open_cat_menu())
            boxes[key] = (x, y, x + w, y + th)
            x += w + s(6)
        self._hand("tmf")
        self._tab_boxes = boxes
        y += th + s(6)
        if not (getattr(self, "_line_in_act", False) or getattr(self, "_count_shown", False)):
            _a, lid = K.text(cv, x1 + s(2), y - s(2), self._line_text(), font(9), fill=DIMK, width=x2 - x1, tags=T)
            b = cv.bbox(lid)
            y = (b[3] if b else y + s(14)) + s(4)
        if self._tm_rows:
            self._place("tms", self.tms_vl.frame, x1 - s(6), y, x2 - x1 + s(10), y2 - y)
        else:
            self._hide("tms")
            K.text(cv, (x1 + x2) // 2, y + s(40),
                   "아직 하나도 없습니다.\n포켓몬을 잡으면 가끔 나옵니다." if self.only_have else "보일 기술머신이 없습니다.",
                   font(11), anchor="n", justify="center", width=x2 - x1 - 20, tags=T)

    def _draw_tm_row(self, cv, t, x, y, w, h, tags, hover=None):
        s = U.h
        have = bool(t.get("have"))
        sel = t["no"] == self.no
        r = s(9)
        if sel:
            K.rrect(cv, x + s(2), y + s(1), x + w - s(4), y + h - s(1), r, fill=MAG, tags=tags)
            K.rrect(cv, x + s(8), y + s(1), x + w - s(4), y + h - s(1), r, fill=NAVY, tags=tags)
        elif hover is not None and have:
            K.rrect(cv, x + s(8), y + s(1), x + w - s(4), y + h - s(1), r, fill="#eceef8", tags=tags)
        m = y + h // 2
        if t["no"] in self.fresh:                       # 새로 받은 기술머신: 노란 점
            rr = s(4)
            cv.create_oval(x + s(14) - rr, m - rr, x + s(14) + rr, m + rr, fill="#f0a800", outline="", tags=tags)
        if sel:
            c_no, c_nm, c_cat = ON_NAVY_DIM, "#ffffff", SKY
        else:
            c_no, c_nm = (DIMK, NAVY) if have else (DIMK, DIMK)
            c_cat = DPT.CAT_COLOR.get(t["cat"], DIMK) if have else DIMK
        cv.create_text(x + s(22), m, text="%03d" % t["no"], fill=c_no, font=font(9), anchor="w", tags=tags)
        cv.create_text(x + s(58), m, text=t["kr"], fill=c_nm, font=font(11), anchor="w", tags=tags)
        cat = TM.CAT_KR.get(t["cat"], t["cat"])
        cv.create_text(x + w - s(16), m, text=cat, fill=c_cat, font=font(9), anchor="e", tags=tags)
        self._type_chip(cv, x + w - s(52), m, t.get("type"), have, tags)

    # ---------------- 오른쪽 ----------------
    def _sw_desc(self):
        t = self._move_t
        got = self.move_lines(t)
        if not got:
            return ("기술머신을 고르세요", None,
                    "가진 기술머신은 진하게, 아직 없는 것은 흐리게 보인다. 포켓몬을 잡으면 가끔 나온다.", None)
        title, sub, desc = got

        def art(cv, x, y, sz):
            type_art(cv, x, y, sz, t.get("type"))
        return title, sub, desc, art

    def _sw_who(self):
        return ("배울 수 있는 포켓몬", "이미 배운 포켓몬은 회색" if self._move_t else "", self._mon_note, ())

    def _sw_action(self):
        return self.use_btn
