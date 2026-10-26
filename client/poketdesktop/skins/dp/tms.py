# -*- coding: utf-8 -*-
"""DP 테마 - 가방의 기술머신 칸.

DP 에서 기술머신은 가방의 주머니 하나다 ('기술머신 · 비전머신' 주머니). 그래서 도구 칸과 **같은 판**에
그린다 - 왼쪽 다이얼은 '기술머신' 주머니가 켜진 채로 있고, 다른 주머니를 누르면 도구 칸의 그 주머니로
돌아간다. 줄의 타입은 타입 색 꼬리표 (직접 그린 원반 그림은 뺐다).

v2: 358줄이나 되는 목록이 5줄만 보이던 것을 고쳤다 - 오른쪽을 둘로 갈라 **목록은 가운데에 키 큰 한 칸**
(기본 기술머신 칸처럼 열 몇 줄), 보라 설명 띠와 올리브 포켓몬 판은 오른쪽에 쌓는다. 가운데 칸 폭은
도구 칸과 같다 (scene.mid_column - 창 폭을 따라 늘고 준다). 좁은 올리브 칸의 줄 바꾸기는 scene.Plates 가 한다.

동작은 기본 기술머신 칸(ui_tms.TmWindow)의 것을 그대로 쓴다 - 서버에서 받기, 가진 것만 · 타입 · 분류로
거르기, 새 기술머신 점, 배울 포켓몬 묻기, 가르치기(기술이 넷이면 무엇을 잊을지 묻기).
"""
import tkinter as tk

from common import tint as Tn
from common.korean import natural

from ... import ui_common as U
from ... import ui_tms as TM
from . import CUR, DIM, HOVER, INK, INK2, SEL, SEP, font
from . import kit as K
from .scene import Band, Plates, PocketDial, Scene, Slot, T, list_box, mid_column

CAT_COLOR = {"physical": "#d8582c", "special": "#3a6ad0", "status": "#7a7a86"}


class TmWindow(Scene, PocketDial, Plates, Band, TM.TmWindow):

    def _build(self):
        self._have = self._total_tms = 0
        self._move_t = None
        self._mon_note = "기술머신을 고르면 배울 수 있는 포켓몬이 나온다."
        self._tm_rows = []
        self._tm_badge = False
        self.ROW_H = U.h(30)
        self._scene_init()
        self._plates_init(self._arrange_mons)
        self.tms_vl = K.VList(self.cv, "#ffffff", self._draw_tm_row)
        self.tms_vl.on_click = self._click_tm
        # 기본 창의 동작 코드가 configure(text=) 로 글씨를 바꾸는 자리들 - 판이 그 글을 그린다
        self.filter_btn = Slot("가진 것만", self._soon)
        self.type_btn = Slot("타입: 전체", self._soon)
        self.cat_btn = Slot("분류: 전체", self._soon)
        self.use_btn = K.CButton(self.cv, "가르치기", self.teach, "blue", font(13))
        self.fresh_btn = K.CButton(self.cv, "", self.next_fresh, "red", font(10))
        self._tab_boxes = {}

    # ---------------- 칠하기 (기본 기술머신 칸이 부른다) ----------------
    def say(self, msg, color=None):
        if not self.alive:
            return
        self._toast(natural(msg or ""), color if color in (U.RED, U.DANGER, U.GOOD) else None)

    def _paint_count(self, have, total):
        self._have, self._total_tms = have, total
        self._soon()

    def _paint_list(self):
        self._show_rows()

    def _show_rows(self):
        self._tm_rows = list(self._visible())
        self.tms_vl.set([(self.ROW_H, t) for t in self._tm_rows], keep=True)
        self._soon()

    def _mark(self, n):
        self.tms_vl.refresh()

    def _paint_fresh(self):
        self.tms_vl.refresh()
        self._soon()

    def _scroll_to(self, n):
        idx = next((i for i, t in enumerate(self._tm_rows) if t["no"] == n), None)
        if idx is not None:
            self.tms_vl.see(idx)

    def _clear_mons(self):
        self._plates_set([], keep=False)

    def _paint_move(self, t):
        self._move_t = t
        if not t:
            self._mon_note = "기술머신을 고르면 배울 수 있는 포켓몬이 나온다."
        self._soon()

    def _mons_note(self, text):
        if text:
            self._mon_note = text
        elif self._mon_note == "불러오는 중...":
            self._mon_note = None
        self._soon()

    def _show_mons(self, view):
        self._mon_note = None if view else self.find.empty_note()
        self._plates_set(view, keep=False)
        self._soon()

    def _thumbs_ready(self, learners):
        self.mons_vl.refresh()

    def _mark_mons(self, prev, pid):
        self.mons_vl.refresh()

    def _menu(self, btn, rows):
        """타입 · 분류 드롭다운 - 그 탭 바로 아래에."""
        key = "type" if btn is self.type_btn else "cat"
        box = self._tab_boxes.get(key)
        try:
            if box:
                x = self.cv.winfo_rootx() + int(box[0])
                y = self.cv.winfo_rooty() + int(box[3]) + 2
            else:
                x, y = self.win.winfo_rootx() + 80, self.win.winfo_rooty() + 80
        except tk.TclError:
            return None
        return U.PopupMenu(self.root, rows, x, y, width=170)

    # ---------------- 왼쪽 다이얼 ----------------
    def _lcd_text(self):
        return "%d/%d" % (self._have, self._total_tms)

    def _line_text(self):
        return "기술머신 · 상점에서 살 수 없다"

    def _pocket_now(self):
        return "tms"

    def _pocket_label(self):
        return "기술머신"

    def _pocket_count(self, key):
        return 1

    def _dial_buttons(self):
        if self.fresh:
            self.fresh_btn.configure(text="새 기술머신 %d개" % len(self.fresh))
            return [self.fresh_btn]
        self.fresh_btn.hide()
        return []

    def _pocket_click(self, key):
        if key == "tms":
            return
        show = getattr(self._switch, "show", None)
        if show is None:
            return
        pane = show("items")
        pick = getattr(pane, "_pick_pocket", None)
        if pick is not None:
            pick(key)

    def badge(self, key, on):
        pass

    # ---------------- 목록 한 줄 ----------------
    def _draw_tm_row(self, cv, t, x, y, w, h, tags, hover=None):
        have = bool(t.get("have"))
        sel = t["no"] == self.no
        if sel:
            cv.create_rectangle(x, y, x + w, y + h, fill=SEL, outline="", tags=tags)
        elif hover is not None and have:
            cv.create_rectangle(x, y, x + w, y + h, fill=HOVER, outline="", tags=tags)
        cv.create_line(x, y + h - 1, x + w, y + h - 1, fill=SEP, tags=tags)
        m = y + h // 2
        if t["no"] in self.fresh:                       # 새로 받은 기술머신: 노란 점
            r = U.h(4)
            cv.create_oval(x + U.h(6) - r, m - r, x + U.h(6) + r, m + r, fill="#f0a800", outline="", tags=tags)
        cv.create_text(x + U.h(14), m, text="%03d" % t["no"], fill=INK2 if have else DIM, font=font(9),
                       anchor="w", tags=tags)
        cv.create_text(x + U.h(52), m, text=t["kr"], fill=INK if have else DIM, font=font(11), anchor="w",
                       tags=tags)
        cat = TM.CAT_KR.get(t["cat"], t["cat"])
        cv.create_text(x + w - U.h(10), m, text=cat, fill=CAT_COLOR.get(t["cat"], DIM) if have else DIM,
                       font=font(9), anchor="e", tags=tags)
        self._type_chip(cv, x + w - U.h(46), m, t.get("type"), have, tags)
        if sel:
            cv.create_rectangle(x, y, x + w - 1, y + h - 1, outline=CUR, width=2, tags=tags)

    @staticmethod
    def _type_chip(cv, xr, m, typ, have, tags):
        """타입 색 꼬리표 (오른쪽 끝이 xr). 못 가진 기술머신은 회색."""
        name = TM.TYPE_KR.get(typ, typ or "")
        col = U.TYPE_COLOR.get(typ, "#a0a0a8") if have else "#c8ccd2"
        f = K.tkfont_of(cv, font(9))
        cw, ch = max(U.h(40), f.measure(name) + U.h(12)), f.metrics("linespace") + U.h(4)
        K.rrect(cv, xr - cw, m - ch // 2, xr, m + ch // 2, 5, fill=col, tags=tags)
        ink = K.look_of(col)[3] if have else "#5a6270"
        cv.create_text(xr - cw // 2, m, text=name, fill=ink, font=font(9), anchor="center", tags=tags)

    def _click_tm(self, t, _x, _y, _w):
        if t.get("have"):
            self.pick(t["no"])

    # ---------------- 포켓몬 판 ----------------
    def _plate_info(self, m):
        known = bool(m.get("known"))
        return {"name": m.get("name", "?"), "sub": "Lv.%s" % m.get("level", "?"),
                "note": "이미 배움" if known else "", "color": U.FG_FAINT, "good": False, "blocked": known,
                "photo": self.photos.get((m.get("num"), Tn.skin(m))), "shiny": m.get("shiny")}

    def _plate_click(self, m):
        if not m.get("known"):
            self.pick_mon(m["id"])

    # ---------------- 보라 띠 ----------------
    def _band_content(self):
        t = self._move_t
        got = self.move_lines(t)
        if not got:
            return ("기술머신을 고르세요",
                    "가진 기술머신은 진하게, 아직 없는 것은 흐리게 보인다. 포켓몬을 잡으면 가끔 나온다.", None)
        title, sub, desc = got

        def art(cv, x, y, s):
            # 타입 색 꼬리표 (큰 것) - 그림을 따로 그리지 않는다
            self._type_chip(cv, x + s - U.h(6), y + s // 2, t.get("type"), True, T)
        return title, sub + ("\n" + desc if desc else ""), art

    # ---------------- 판 전체 ----------------
    def _paint(self):
        self._job = None
        if not self.alive:
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
        x0 = self._paint_left(cv, H)
        # 가운데: 키 큰 목록 칸 (아래까지, 도구 칸과 같은 폭) / 오른쪽: 보라 설명 띠 + 올리브 포켓몬 판 + 글상자 · 가르치기
        x1 = mid_column(x0, W)
        self._paint_tm_list(cv, x0, x1, H)
        # 아래 줄은 '가르치기' 하나, 알릴 말은 보라 띠 위에 잠깐 (도구 칸과 같다 - 글상자는 뺐다)
        BOT = U.h(self.ACTION_H)
        BH = self._band_height(cv, x1, W, H)
        self._paint_band(cv, x1, W, 0, BH)
        self._paint_plates_area(cv, x1, W, BH, H - BOT, "배울 수 있는 포켓몬",
                                "이미 배운 포켓몬은 회색" if self._move_t else "", self._mon_note)
        self._paint_action_row(cv, x1, W, H - BOT, H, self.use_btn)
        self._toast_box = (x1, 0, W, BH)
        self._paint_toast()

    def _paint_tm_list(self, cv, x0, x1, LH):
        ix1, iy1, ix2, iy2 = list_box(self, cv, x0, x1, LH)
        th = U.h(26)
        self._tabs(cv, ix1, iy1, th, [("have", "가진 것만"), ("all", "전부")],
                   "have" if self.only_have else "all", "flt",
                   lambda k: (k == "have") != self.only_have and self._toggle_filter())
        iy1b = iy1 + th + U.h(4)
        right = self._tabs(cv, ix1, iy1b, th, [("type", self.type_btn.text), ("cat", self.cat_btn.text)],
                           None, "tmf", lambda k: self._open_type_menu() if k == "type" else self._open_cat_menu())
        self._tab_boxes = dict(right)
        ly1 = iy1b + th + U.h(6)
        if self._tm_rows:
            self._place("tms", self.tms_vl.frame, ix1, ly1, ix2 - ix1, iy2 - ly1)
        else:
            self._hide("tms")
            K.text(cv, (ix1 + ix2) // 2, ly1 + U.h(40),
                   "아직 하나도 없습니다.\n포켓몬을 잡으면 가끔 나옵니다." if self.only_have else "보일 기술머신이 없습니다.",
                   font(11), anchor="n", justify="center", width=ix2 - ix1 - 20, tags=T)
