# -*- coding: utf-8 -*-
"""블랙·화이트 테마 - 가방의 기술머신 칸.

도구 칸(bag.py)과 같은 시안 H 의 판(BWBag)이다: 위 줄의 동그란 주머니 단추('기술 머신' 이 하늘빛 고리),
왼쪽 어두운 판에 거르기 알약 · 기술머신 목록, 오른쪽 위 설명 판(고리 안에 타입 꼬리표), 그 밑 배울 포켓몬 카드,
오른쪽 아래 하늘빛 '가르치기'. 동작은 DP 기술머신 칸(skins/dp/tms.py) 그대로다.
"""
from common.korean import natural

from ... import ui_common as U
from ... import ui_tms as TM
from ..dp import font
from ..dp import kit as K
from ..dp import tms as DPT
from ..dp.scene import T
from . import CYAN, DIMT, FAINT, GLOW_FAR, PANEL, PANEL_HI, SEL, TEXT
from .bag import BWBag, BWButton


class TmWindow(BWBag, DPT.TmWindow):

    def _build(self):
        DPT.TmWindow._build(self)
        self.PLATE_H = U.h(self.PLATE_PX)
        BWButton.adopt(self.use_btn, "go")
        BWButton.adopt(self.fresh_btn, "dark_cyan")
        self.tms_vl.cv.configure(bg=PANEL)
        self.tms_vl.frame.configure(bg=PANEL)
        self._bw_restyle()

    def _line_text(self):
        return "상점에서 살 수 없다"        # (돈 알약 자리에 가진 수 / 모두 - 위 줄에 들게 짧게)

    def _bw_actions(self):
        acts = []
        if self.fresh:
            self.fresh_btn.configure(text="새 기술머신 %d개" % len(self.fresh))
            acts.append(self.fresh_btn)
        else:
            self.fresh_btn.hide()
        return acts + [self.use_btn]

    def _bw_plates(self, width):
        return ("배울 수 있는 포켓몬", "이미 배운 포켓몬은 회색" if self._move_t else "", self._mon_note, ())

    def _detail_content(self):
        t = self._move_t
        got = self.move_lines(t)
        if not got:
            return ("기술머신을 고르세요", "",
                    "가진 기술머신은 진하게, 아직 없는 것은 흐리게 보인다. 포켓몬을 잡으면 가끔 나온다.", None)
        title, sub, desc = got

        def art(cv, cx, cy):
            # 타입 빛깔 꼬리표 (그림을 따로 그리지 않는다)
            name = TM.TYPE_KR.get(t.get("type"), t.get("type") or "")
            cw = max(U.h(40), K.tkfont_of(cv, font(9)).measure(name) + U.h(12))
            self._type_chip(cv, cx + cw // 2, cy, t.get("type"), True, T)
        return title, sub, natural(desc or ""), art

    # ---------------- 왼쪽 목록 판 ----------------
    def _bw_list(self, cv, ix1, iy1, ix2, iy2):
        s = U.h
        th = s(26)
        self._tabs(cv, ix1, iy1, th, [("have", "가진 것만"), ("all", "전부")],
                   "have" if self.only_have else "all", "flt",
                   lambda k: (k == "have") != self.only_have and self._toggle_filter(), x2=ix2)
        iy1b = iy1 + th + s(8)
        right = self._tabs(cv, ix1, iy1b, th, [("type", self.type_btn.text + " ▾"), ("cat", self.cat_btn.text + " ▾")],
                           None, "tmf", lambda k: self._open_type_menu() if k == "type" else self._open_cat_menu(),
                           x2=ix2)
        self._tab_boxes = dict(right)
        ly1 = iy1b + th + s(10)
        if self._tm_rows:
            self._place("tms", self.tms_vl.frame, ix1, ly1, ix2 - ix1, iy2 - ly1)
        else:
            self._hide("tms")
            K.text(cv, (ix1 + ix2) // 2, ly1 + s(40),
                   "아직 하나도 없습니다.\n포켓몬을 잡으면 가끔 나옵니다." if self.only_have else "보일 기술머신이 없습니다.",
                   font(11), fill=DIMT, anchor="n", justify="center", width=ix2 - ix1 - 20, tags=T)

    # ---------------- 목록 한 줄 (시안 .ln) ----------------
    def _draw_tm_row(self, cv, t, x, y, w, h, tags, hover=None):
        s = U.h
        have = bool(t.get("have"))
        sel = t["no"] == self.no
        x2 = x + w - s(4)
        if sel:
            K.rrect(cv, x, y + 1, x2, y + h - 1, s(7), fill=GLOW_FAR, tags=tags)
            K.rrect(cv, x + 1, y + 2, x2 - 1, y + h - 2, s(6), fill=SEL, outline=CYAN, width=1, tags=tags)
        elif hover is not None and have:
            K.rrect(cv, x + 1, y + 2, x2 - 1, y + h - 2, s(6), fill=PANEL_HI, tags=tags)
        m = y + h // 2
        if t["no"] in self.fresh:                       # 새로 받은 기술머신: 노란 점
            r = s(4)
            cv.create_oval(x + s(7) - r, m - r, x + s(7) + r, m + r, fill="#f2c445", outline="", tags=tags)
        cv.create_text(x + s(16), m, text="%03d" % t["no"], fill=DIMT if have else FAINT, font=font(9),
                       anchor="w", tags=tags)
        cv.create_text(x + s(54), m, text=t["kr"], fill=TEXT if have else FAINT, font=font(11), anchor="w",
                       tags=tags)
        cat = TM.CAT_KR.get(t["cat"], t["cat"])
        cv.create_text(x2 - s(10), m, text=cat, fill=DPT.CAT_COLOR.get(t["cat"], FAINT) if have else FAINT,
                       font=font(9), anchor="e", tags=tags)
        self._type_chip(cv, x2 - s(46), m, t.get("type"), have, tags)

    @staticmethod
    def _type_chip(cv, xr, m, typ, have, tags):
        """타입 빛깔 꼬리표 (오른쪽 끝이 xr). 못 가진 기술머신은 어두운 회색."""
        name = TM.TYPE_KR.get(typ, typ or "")
        col = U.TYPE_COLOR.get(typ, "#a0a0a8") if have else "#3a4048"
        f = K.tkfont_of(cv, font(9))
        cw, ch = max(U.h(40), f.measure(name) + U.h(12)), f.metrics("linespace") + U.h(4)
        K.rrect(cv, xr - cw, m - ch // 2, xr, m + ch // 2, 5, fill=col, tags=tags)
        ink = K.look_of(col)[3] if have else FAINT
        cv.create_text(xr - cw // 2, m, text=name, fill=ink, font=font(9), anchor="center", tags=tags)
