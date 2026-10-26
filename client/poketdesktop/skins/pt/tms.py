# -*- coding: utf-8 -*-
"""플라티나 테마 - 가방의 기술머신 칸.

도구 칸과 같은 시안의 틀(bag.PtBag)이다 - 머리 띠 '기술머신' · 가진 수 캡슐, 왼쪽 세로 주머니(기술머신이 하늘색),
가운데 판의 고르기 줄(가진 것만 | 전부) · 타입 · 분류 캡슐과 흰 캡슐 줄 목록, 오른쪽 보라 머리 설명 판과
'배울 수 있는 포켓몬' 판, 아래 주황 캡슐 '가르치기'. 새로 받은 기술머신 단추는 머리 띠에.

동작은 DP 기술머신 칸(skins/dp/tms.py) → 기본 기술머신 칸(ui_tms.TmWindow) 그대로다.
"""
from ... import ui_common as U
from ... import ui_tms as TM
from ..dp import font
from ..dp import kit as K
from ..dp import tms as DPT
from ..dp.scene import T
from . import DIM, FAINT, INK
from . import _pt as P
from .bag import PtBag

CAT_COLOR = {"physical": "#c0501c", "special": "#2a5cc0", "status": "#5f6b78"}


class TmWindow(PtBag, DPT.TmWindow):

    def _build(self):
        DPT.TmWindow._build(self)
        self._pt_init()
        self._list_bg(self.tms_vl)
        self.ROW_H = U.h(30)
        P.to_capsule(self.use_btn, "orange")
        self.use_btn.spec = font(14)
        P.to_capsule(self.fresh_btn, "red")
        self._reload_btn = P.Capsule(self.cv, "새로고침", self.reload, "gray", font(10))

    # ---------------- 머리 띠 ----------------
    def _head_title(self):
        return "기술머신"

    def _line_text(self):
        return "상점에서 살 수 없다 · 포켓몬을 잡으면 가끔 나온다"

    def _head_buttons(self):
        out = []
        if self.fresh:
            self.fresh_btn.configure(text="새 기술머신 %d개" % len(self.fresh))
            out.append(self.fresh_btn)
        else:
            self.fresh_btn.hide()
        out.append(self._reload_btn)
        return out

    def _lcd_text(self):
        return "%d / %d" % (self._have, self._total_tms)

    # ---------------- 가운데 판 ----------------
    def _paint_mid(self, cv, ix1, iy1, ix2, iy2):
        s = U.h
        th = s(30)
        flt = [("have", "가진 것만"), ("all", "전부")]
        f10 = K.tkfont_of(cv, font(10))
        need = max(f10.measure(self.type_btn.text), f10.measure(self.cat_btn.text)) + s(44)
        sw = P.seg_width(cv, flt, font(10), pad=s(16))
        one = sw + 2 * (need + s(8)) <= ix2 - ix1          # 한 줄에 다 든다 (목록 줄을 아낀다)
        P.seg(cv, ix1, iy1, sw if one else ix2 - ix1, th, flt, "have" if self.only_have else "all", "flt",
              lambda k: (k == "have") != self.only_have and self._toggle_filter(), spec=font(10))
        self._hand("flt")
        # 타입 · 분류 (누르면 드롭다운) - 흰 캡슐 둘
        gap = s(8)
        if one:
            y, bx = iy1, ix1 + sw + gap
        else:
            y, bx = iy1 + th + s(6), ix1
        w = (ix2 - bx - gap) // 2
        self._tab_boxes = {}
        for i, (key, text) in enumerate((("type", self.type_btn.text), ("cat", self.cat_btn.text))):
            x1 = bx + i * (w + gap)
            tg = T + ("tmf", "tmf_" + key)
            P.capsule(cv, x1, y, x1 + w, y + th, "white", rim_w=2, tags=tg)
            cv.create_text(x1 + s(14), y + th // 2, text=text, fill=INK, font=font(10), anchor="w", tags=tg)
            cv.create_text(x1 + w - s(12), y + th // 2, text="▾", fill=DIM, font=font(10), anchor="e", tags=tg)
            cv.tag_bind("tmf_" + key, "<Button-1>",
                        lambda _e, k=key: self._open_type_menu() if k == "type" else self._open_cat_menu())
            self._tab_boxes[key] = (x1, y, x1 + w, y + th)
        self._hand("tmf")
        ly1 = y + th + s(6)
        if self._tm_rows:
            self._place("tms", self.tms_vl.frame, ix1 - s(4), ly1, ix2 - ix1 + s(8), iy2 - ly1)
        else:
            self._hide("tms")
            K.text(cv, (ix1 + ix2) // 2, ly1 + s(40),
                   "아직 하나도 없습니다.\n포켓몬을 잡으면 가끔 나옵니다." if self.only_have else "보일 기술머신이 없습니다.",
                   font(11), fill=DIM, anchor="n", justify="center", width=ix2 - ix1 - 20, tags=T)

    def _draw_tm_row(self, cv, t, x, y, w, h, tags, hover=None):
        s = U.h
        have = bool(t.get("have"))
        sel = t["no"] == self.no
        x1, y1, x2, y2 = x + s(5), y + s(2), x + w - s(5), y + h - s(2)
        P.row_capsule(cv, x1, y1, x2, y2, sel=sel, hover=hover is not None and have,
                      fill="#ffffff" if have else "#f0f2f5", tags=tags)
        m = (y1 + y2) // 2
        if t["no"] in self.fresh:                       # 새로 받은 기술머신: 노란 점
            r = s(4)
            cv.create_oval(x1 + s(9) - r, m - r, x1 + s(9) + r, m + r, fill="#f0a800", outline="", tags=tags)
        cv.create_text(x1 + s(18), m, text="%03d" % t["no"], fill=DIM if have else FAINT, font=font(9),
                       anchor="w", tags=tags)
        cv.create_text(x1 + s(54), m, text=t["kr"], fill=INK if have else FAINT, font=font(11), anchor="w",
                       tags=tags)
        cat = TM.CAT_KR.get(t["cat"], t["cat"])
        cv.create_text(x2 - s(14), m, text=cat, fill=CAT_COLOR.get(t["cat"], DIM) if have else FAINT,
                       font=font(9), anchor="e", tags=tags)
        self._type_chip(cv, x2 - s(50), m, t.get("type"), have, tags)

    @staticmethod
    def _type_chip(cv, xr, m, typ, have, tags):
        """타입 색 꼬리표 (알약) - 오른쪽 끝이 xr. 못 가진 기술머신은 회색."""
        name = TM.TYPE_KR.get(typ, typ or "")
        col = U.TYPE_COLOR.get(typ, "#a0a0a8") if have else "#c8ccd2"
        f = K.tkfont_of(cv, font(9))
        cw, ch = max(U.h(42), f.measure(name) + U.h(14)), f.metrics("linespace") + U.h(4)
        P.rpoly(cv, xr - cw, m - ch // 2, xr, m + ch // 2, ch // 2, fill=col, tags=tags)
        ink = K.look_of(col)[3] if have else "#5a6270"
        cv.create_text(xr - cw // 2, m, text=name, fill=ink, font=font(9), anchor="center", tags=tags)

    # ---------------- 오른쪽 ----------------
    def _info(self):
        t = self._move_t
        got = self.move_lines(t)
        if not got:
            return ("기술머신을 고르세요", "",
                    "가진 기술머신은 진하게, 아직 없는 것은 흐리게 보인다. 포켓몬을 잡으면 가끔 나온다.", None)
        title, sub, desc = got

        def art(cv, x, y, sz):
            # 타입 색 알약 (그림 칸 가운데) - 그림을 따로 그리지 않는다
            name = TM.TYPE_KR.get(t.get("type"), t.get("type") or "")
            col = U.TYPE_COLOR.get(t.get("type"), "#a0a0a8")
            ch = K.tkfont_of(cv, font(9)).metrics("linespace") + U.h(6)
            P.rpoly(cv, x + U.h(4), y + (sz - ch) // 2, x + sz - U.h(4), y + (sz + ch) // 2, ch // 2, fill=col, tags=T)
            cv.create_text(x + sz // 2, y + sz // 2, text=name, fill=K.look_of(col)[3], font=font(9), anchor="center",
                           tags=T)
        return title, sub, desc, art

    def _who(self):
        return ("배울 수 있는 포켓몬", "이미 배운 포켓몬은 회색" if self._move_t else "", self._mon_note, [])
