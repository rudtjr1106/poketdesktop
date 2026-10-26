# -*- coding: utf-8 -*-
"""금·은 테마 - 가방의 기술머신 칸. 도구 칸과 같은 판 (_gbc.GSBag - 시안 G 의 가방):

    왼쪽 위     ◀ 기술머신 ▶ · 둥근 칸에 타입 꼬리표 · 기술 이름 · 타입 · 분류 · 위력…
    왼쪽 아래   배울 수 있는 포켓몬 (이미 배운 것은 흐리게)
    가운데      큰 상자: [가진 것만][전부] · [타입][분류] 칩 · 가진 수 / 기술머신 줄 (▶ · 번호 · 이름 · 타입 · 분류)
    아래        넓은 상자: 기술 설명 / 오른쪽 메뉴 '▶ 가르치기' · (새 기술머신 N개)

동작은 DP 기술머신 칸(skins/dp/tms.py → ui_tms.TmWindow) 그대로다 - 그리는 것만 바꾼다.
"""
from ... import ui_common as U
from ... import ui_tms as TM
from ..dp import font
from ..dp import kit as K
from ..dp import tms as DPT
from ..dp.scene import T
from . import BROWN, DIM, HOV, INK, INK2
from ._gbc import GSBag, arrow, as_gs, chips, paper_list

CAT_COLOR = {"physical": "#c0501c", "special": "#2860c0", "status": "#6a5a44"}


class TmWindow(GSBag, DPT.TmWindow):

    def _build(self):
        DPT.TmWindow._build(self)
        paper_list(self.tms_vl)
        as_gs(self.use_btn, "menu", primary=True)
        self.use_btn.spec = font(12)
        as_gs(self.fresh_btn, "menu")
        self.fresh_btn.spec = font(11)
        self._gs_setup()

    # ---------------- 판 조각 (GSBag 이 묻는다) ----------------
    def _gs_has_pick(self):
        return bool(self._move_t)

    def _gs_card(self):
        t = self._move_t
        got = self.move_lines(t)
        if not got:
            return "기술머신을 고르세요", "", None
        title, sub, _desc = got

        def art(cv, cx, cy, d):
            self._type_chip(cv, cx + U.h(26), cy, t.get("type"), True, T)
        return title, sub, art

    def _gs_menu(self):
        out = [self.use_btn]
        if self.fresh:
            self.fresh_btn.configure(text="새 기술머신 %d개" % len(self.fresh))
            out.append(self.fresh_btn)
        else:
            self.fresh_btn.hide()
        return out

    def _gs_plates_title(self, width):
        return ("배울 수 있는 포켓몬", "이미 배운 포켓몬은 흐리게" if self._move_t else "", self._mon_note, ())

    def _gs_desc(self):
        t = self._move_t
        got = self.move_lines(t)
        if not got:
            return ("기술머신을 고르세요",
                    "가진 기술머신은 진하게, 아직 없는 것은 흐리게 보인다. 포켓몬을 잡으면 가끔 나온다.", "")
        title, sub, desc = got
        return title, desc or sub, (sub if desc else "")

    def _gs_mid(self, cv, x1, y1, x2, y2):
        """큰 상자: [가진 것만][전부] [타입][분류] · 가진 수 / 기술머신 목록."""
        ix1, iy1, ix2, iy2 = self._gs_list_frame(cv, x1, y1, x2, y2)
        lx1, lx2 = ix1 + U.h(10), ix2 - U.h(8)
        ch = U.h(24)
        y = iy1 + U.h(8)
        flt = [("have", "가진 것만"), ("all", "전부")]
        got = chips(cv, lx1, y, ch, flt, "have" if self.only_have else "all", "flt",
                    lambda k: (k == "have") != self.only_have and self._toggle_filter(), hand=self._hand)
        x = got[-1][1][2] + U.h(14)
        menus = [("type", self.type_btn.text + " ▾"), ("cat", self.cat_btn.text + " ▾")]
        right = chips(cv, x, y, ch, menus, None, "tmf",
                      lambda k: self._open_type_menu() if k == "type" else self._open_cat_menu(), hand=self._hand)
        self._tab_boxes = dict(right)
        cnt = "기술머신 %s" % self._lcd_text()
        end = right[-1][1][2] + U.h(10)
        if lx2 - K.tkfont_of(cv, font(10)).measure(cnt) >= end:
            cv.create_text(lx2, y + ch // 2, text=cnt, fill=BROWN, font=font(10), anchor="e", tags=T)
            ly1 = y + ch + U.h(4)
        else:
            cv.create_text(lx1, y + ch + U.h(12), text=cnt, fill=BROWN, font=font(10), anchor="w", tags=T)
            ly1 = y + ch + U.h(22)
        cv.create_text(lx1, ly1 + U.h(8), text=self._line_text(), fill=BROWN, font=font(9), anchor="w", tags=T)
        ly1 += U.h(20)
        if self._tm_rows:
            self._place("tms", self.tms_vl.frame, ix1 + U.h(2), ly1, ix2 - ix1 - U.h(4), iy2 - ly1 - 2)
        else:
            self._hide("tms")
            K.text(cv, (lx1 + lx2) // 2, ly1 + U.h(40),
                   "아직 하나도 없습니다.\n포켓몬을 잡으면 가끔 나옵니다." if self.only_have else "보일 기술머신이 없습니다.",
                   font(11), fill=INK2, anchor="n", justify="center", width=lx2 - lx1 - 20, tags=T)

    # ---------------- 목록 한 줄 ----------------
    def _draw_tm_row(self, cv, t, x, y, w, h, tags, hover=None):
        have = bool(t.get("have"))
        sel = t["no"] == self.no
        if hover is not None and not sel and have:
            cv.create_rectangle(x, y, x + w, y + h, fill=HOV, outline="", tags=tags)
        m = y + h // 2
        if sel:
            arrow(cv, x + U.h(6), m, U.h(5), tags=tags)
        if t["no"] in self.fresh:                       # 새로 받은 기술머신: 노란 점
            r = U.h(4)
            cv.create_oval(x + U.h(22) - r, m - r, x + U.h(22) + r, m + r, fill="#f0a800", outline="", tags=tags)
        cv.create_text(x + U.h(30), m, text="%03d" % t["no"], fill=BROWN if have else DIM, font=font(9),
                       anchor="w", tags=tags)
        cv.create_text(x + U.h(66), m, text=t["kr"], fill=INK if have else DIM, font=font(11), anchor="w",
                       tags=tags)
        cat = TM.CAT_KR.get(t["cat"], t["cat"])
        cv.create_text(x + w - U.h(10), m, text=cat, fill=CAT_COLOR.get(t["cat"], DIM) if have else DIM,
                       font=font(9), anchor="e", tags=tags)
        self._type_chip(cv, x + w - U.h(46), m, t.get("type"), have, tags)

    @staticmethod
    def _type_chip(cv, xr, m, typ, have, tags):
        """타입 빛깔 꼬리표 (오른쪽 끝이 xr) - 네모 (게임보이). 못 가진 기술머신은 회색."""
        name = TM.TYPE_KR.get(typ, typ or "")
        col = U.TYPE_COLOR.get(typ, "#a0a0a8") if have else "#d8d0bc"
        f = K.tkfont_of(cv, font(9))
        cw, ch = max(U.h(40), f.measure(name) + U.h(12)), f.metrics("linespace") + U.h(4)
        cv.create_rectangle(xr - cw, m - ch // 2, xr, m + ch // 2, fill=col, outline="", tags=tags)
        ink = K.look_of(col)[3] if have else "#6a5a44"
        cv.create_text(xr - cw // 2, m, text=name, fill=ink, font=font(9), anchor="center", tags=tags)
