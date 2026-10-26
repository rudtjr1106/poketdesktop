# -*- coding: utf-8 -*-
"""DP 테마 - 가방 (도구 칸).

기술머신 칸(tms.py)과 같은 세 칸이다:

    ┌ 하늘 칸: 가방 · 포켓치(돈) ──┐┌ 초록 칸 안의 흰 목록 ─┐┌ 보라 설명 띠 ─────────────────┐
    │ 주머니 띠 · 주머니 이름       ││ 찾기 [            ]   ││ 올리브: 누구에게 쓸까?        │
    ├ 황토 바탕의 몬스터볼 다이얼 ──┤│ [이름|종류|등급|개수] ││   포켓몬 찾기 · 줄 세우기     │
    │   둘레에 주머니 단추 (11개)   ││ ■ 도구 이름  등급  ×3 ││   (병뚜껑 능력 칸 · 노력치 칸)│
    │   가운데 단추 = 새로고침      ││ (빨간 테 = 고른 도구) ││   모서리를 깎은 하늘색 판     │
    │ [팔기] [여러 개 팔기]          ││ ... 창 아래까지       │├ 글상자 · 닫기 / ○○ 쓰기 ─────┤

가운데 목록 칸의 폭은 기술머신 칸과 같다 (scene.mid_column - 창 폭을 따라 늘고 준다).
오른쪽 칸이 좁으면 아래 줄을 두 단으로 놓는다 (위: 글상자 · 닫기, 아래: 칸 폭 가득 '○○ 쓰기').

**동작은 기본 가방(ui_bag.BagWindow)의 것을 그대로 쓴다** - 서버 호출, 누구에게 쓸 수 있나, 단추를 켤까.
여기서는 그 창이 칠하라고 부르는 자리(_build · _paint_* · _show_* · _repaint_* · _mon_list · say)만 DP 로 그린다.

DP 와 다른 점 하나: 원작 주머니는 한 번에 하나만 보이지만 '전체' 주머니를 둔다 (지금까지처럼 다 보기),
그리고 찾는 말을 넣으면 모든 주머니에서 찾는다.
"""
import tkinter as tk

from common.korean import natural

from ... import item_icons
from ... import ui_bag as B
from ... import ui_common as U
from . import CUR, DIM, HOVER, INK, LIST_FRAME, LIST_IN, SEP, font
from . import kit as K
from .scene import POCKET_NAME, T, Band, Plates, PocketDial, Scene, list_box, mid_column

# 화면 밖에서 쓰던 이름 (bag_tabs · 검사)
from .scene import POCKETS  # noqa: F401

# 줄의 등급 글 (DP 상점 칸과 같은 빛깔)
RARITY_KR = {"common": "흔함", "uncommon": "조금귀함", "rare": "귀함", "epic": "진귀", "legendary": "전설"}
RARE = {"common": "#6a6a74", "uncommon": "#2c8a3c", "rare": "#2860c0", "epic": "#8a4ad0", "legendary": "#c06810"}


class BagWindow(Scene, PocketDial, Plates, Band, B.BagWindow):

    # ---------------- 판 ----------------
    def _build(self):
        self.pocket = "all"
        self._kinds = self._total = 0
        self._item = None
        self._stat = None
        self._ev = None
        self._mon_note = None            # None 이면 판 목록, 글이면 그 자리에 안내
        self._items_state = "list"
        self._items_note = ""
        self._entries = []
        self._tm_badge = bool(getattr(self.app, "tm_new", 0))
        self.ROW_H = U.h(30)             # 기술머신 줄과 같은 높이
        self.HEAD_H = U.h(22)

        self._scene_init()
        self.item_q = tk.StringVar()
        self.item_find = K.entry(self.cv, self.item_q, width=10)
        self.item_q.trace_add("write", lambda *_a: self._items_changed())
        self.items_vl = K.VList(self.cv, "#ffffff", self._draw_item_row)
        self.items_vl.on_click = self._click_item
        self._plates_init(self._find_changed)

        self.use_btn = K.CButton(self.cv, "쓰기", self.do_use, "blue", font(13))
        self.use_btn.configure(state="disabled")
        self.sell_btn = K.CButton(self.cv, "팔기", self.do_sell, "gray", font(10))
        self.sell_btn.configure(state="disabled")
        self.sell_many_btn = K.CButton(self.cv, "여러 개 팔기", self.do_sell_many, "gray", font(10))
        self.close_btn = K.CButton(self.cv, "닫기", self.close, "gray", font(10))
        self._hand("stc")

        reg = getattr(self._switch, "register", None)
        if reg is not None:
            reg(self)

    # 기술머신 주머니의 점 (받고 아직 안 본 기술머신) - 가방 탭(bag_tabs)이 칠하라고 부른다
    def badge(self, key, on):
        if key == "tms" and bool(on) != self._tm_badge:
            self._tm_badge = bool(on)
            self._soon()

    # ---------------- 칠하기 (기본 가방이 부른다) ----------------
    def _paint_money(self, kinds, total):
        self._kinds, self._total = kinds, total
        self._soon()

    def _paint_sort(self):
        self._soon()

    def _item_entries(self, owned):
        """고른 주머니의 도구만 (찾는 말이 있으면 모든 주머니에서)."""
        if self.pocket not in ("all", "tms") and not self.item_q.get().strip():
            owned = [i for i in owned if i.get("cat") == self.pocket]
        return B.BagWindow._item_entries(self, owned)

    def _show_item_entries(self, state, entries=(), keep=True, note=""):
        if state == "nomatch" and not self.item_q.get().strip():
            note = "이 주머니는 비어 있다."
        self._items_state, self._items_note = state, note
        self._entries = list(entries) if state == "list" else []
        rows = [((self.HEAD_H if k == "head" else self.ROW_H), (k, v)) for k, v in self._entries]
        self.items_vl.set(rows, keep=keep)
        self._soon()

    def _repaint_items(self):
        self.items_vl.refresh()
        if self.item_id:
            idx = next((n for n, (k, v) in enumerate(self._entries) if k == "item" and v["id"] == self.item_id), None)
            if idx is not None:
                self.items_vl.see(idx)

    def _show_mons(self, keep):
        self._plates_set(self._view, keep)

    def _repaint_mons(self):
        self.mons_vl.refresh()

    def _paint_item(self, it):
        self._item = it
        self._soon()

    def _paint_stats(self, hint, cells):
        self._stat = (hint, cells)
        self._soon()

    def _paint_evs(self, rows, total_text, total_full):
        self._ev = (rows, total_text, total_full)
        self._soon()

    def _paint_buttons(self, use_ok, use_text, sell_ok, sell_text):
        self.use_btn.configure(state="normal" if use_ok else "disabled", text=use_text)
        self.sell_btn.configure(state="normal" if sell_ok else "disabled", text=sell_text)
        self._soon()                     # 글씨 폭이 바뀌면 단추 자리도 바뀐다

    def _mon_list(self, on, note=""):
        self._mon_note = None if on else note
        self._soon()

    def say(self, text, color=U.GOOD, fg=None):
        self._toast(natural(text or ""), fg if fg else (color if color == U.DANGER else None))

    def shown_items(self):
        return [(v["id"], None) for k, v in self.items_vl.visible() if k == "item"]

    def shown_mons(self):
        return [(m["id"], None) for row in self.mons_vl.visible() for m in row]

    # ---------------- 왼쪽 다이얼 (scene.PocketDial 이 묻는다) ----------------
    def _lcd_text(self):
        return "{:,}원".format(self.money)

    def _line_text(self):
        return "%d종 · 모두 %d개" % (self._kinds, self._total)

    def _pocket_now(self):
        return self.pocket

    def _pocket_label(self):
        if self.item_q.get().strip():
            return "모든 주머니에서 찾기"
        return POCKET_NAME.get(self.pocket, self.pocket).replace("\n", " ")

    def _pocket_count(self, key):
        if key in ("all", "tms"):
            return 1
        return sum(1 for i in self.items if i.get("cat") == key and self.bag.get(i["id"], 0) > 0)

    def _dial_buttons(self):
        return [self.sell_btn, self.sell_many_btn]

    def _pocket_click(self, key):
        self._pick_pocket(key)

    def _pick_pocket(self, key):
        if key == "tms":
            show = getattr(self._switch, "show", None)
            if show is not None:
                show("tms")
            return
        if key == self.pocket:
            return
        self.pocket = key
        self._fill_items(keep=False)
        it = self.current_item()
        if key != "all" and (not it or it.get("cat") != key) and not self.item_q.get().strip():
            first = next((v["id"] for k, v in self._entries if k == "item"
                          and (v.get("effect") or {}).get("kind") in B.USABLE), None)
            first = first or next((v["id"] for k, v in self._entries if k == "item"), None)
            self.pick_item(first)
        self._soon()

    # ---------------- 목록 한 줄 ----------------
    def _draw_item_row(self, cv, data, x, y, w, h, tags, hover=None):
        kind, val = data
        if kind == "head":
            cat, n = val[0], val[1]
            sub = val[2] if len(val) > 2 else None
            label = ("%s · %s · %d종" % (B.CAT_KR.get(cat, cat), sub, n)) if sub else \
                "%s · %d종" % (B.CAT_KR.get(cat, cat), n)
            m = y + h // 2
            cv.create_rectangle(x + 6, m - 3, x + 12, m + 3, fill=B.CAT_COLOR.get(cat, DIM), outline="", tags=tags)
            cv.create_text(x + 18, m, text=label, fill=DIM, font=font(9), anchor="w", tags=tags)
            cv.create_line(x + 4, y + h - 1, x + w - 4, y + h - 1, fill="#e6e9ee", tags=tags)
            return
        it = val
        usable = (it.get("effect") or {}).get("kind") in B.USABLE
        sel = it["id"] == self.item_id
        if hover is not None and not sel:
            cv.create_rectangle(x, y, x + w, y + h, fill=HOVER, outline="", tags=tags)
        cv.create_line(x, y + h - 1, x + w, y + h - 1, fill=SEP, tags=tags)
        m = y + h // 2
        icon = item_icons.photo(it["id"], 20)
        if icon is not None:
            cv.create_image(x + U.h(16), m, image=icon, tags=tags)
        else:
            cv.create_rectangle(x + U.h(16) - 3, m - 3, x + U.h(16) + 3, m + 3,
                                fill=B.CAT_COLOR.get(it.get("cat"), DIM), outline="", tags=tags)
        fg = INK if usable else DIM
        nid = cv.create_text(x + U.h(34), m, text=it["kr"], fill=fg, font=font(11), anchor="w", tags=tags)
        cx = x + w - U.h(10)
        cv.create_text(cx, m, text="×%d" % self.bag.get(it["id"], 0), fill=fg, font=font(11), anchor="e",
                       tags=tags)
        # 등급 (개수 칸 왼쪽). 이름이 길어 닿으면 등급은 뺀다 - 이름이 먼저다
        rk = it.get("rarity")
        if rk in RARITY_KR:
            rx = cx - U.h(46)
            f = K.tkfont_of(cv, font(9))
            b = cv.bbox(nid)
            if not b or b[2] + U.h(10) <= rx - f.measure(RARITY_KR[rk]):
                cv.create_text(rx, m, text=RARITY_KR[rk], fill=RARE[rk] if usable else DIM, font=font(9),
                               anchor="e", tags=tags)
        if sel:
            cv.create_rectangle(x + 1, y + 1, x + w - 2, y + h - 2, outline=CUR, width=2, tags=tags)

    def _click_item(self, data, _x, _y, _w):
        kind, val = data
        if kind == "item":
            self.pick_item(val["id"])

    # ---------------- 포켓몬 판 (scene.Plates 가 묻는다) ----------------
    def _plate_info(self, m):
        good, blocked, note, color = self._states.get(m["id"]) or (False, False, "", U.FG_FAINT)
        info = m.get("info") or {}
        sub = "Lv.%d" % m.get("level", 0)
        if m.get("onDesktop"):
            sub += " · 따라다님"
        return {"name": info.get("name", m.get("species", "?")), "sub": sub, "note": note, "color": color,
                "good": good, "blocked": blocked, "photo": self.photos.get(m["id"]), "shiny": m.get("shiny")}

    def _plate_click(self, m):
        self.pick_mon(m["id"])

    # ---------------- 보라 띠 (scene.Band 가 묻는다) ----------------
    def _band_content(self):
        it = self._item
        if not it:
            return ("도구를 고르세요",
                    "왼쪽에서 주머니를 고르고, 목록에서 도구를 고르면 여기에 설명이 뜬다.", None)
        title = "%s · %s · %d개" % (it["kr"], B.CAT_KR.get(it["cat"], it["cat"]), self.bag.get(it["id"], 0))

        def art(cv, x, y, s):
            ph = item_icons.photo(it["id"], 32)
            if ph is not None:
                cv.create_image(x + s // 2, y + s // 2, image=ph, tags=T)
        return title, natural(B.item_desc(it)), art

    # ---------------- 판 전체 ----------------
    def _boxes(self, cv, width):
        """판 목록 위에 끼우는 칸 [(높이, 그리는 함수)] - 병뚜껑의 능력 칸 · 노력치 도구의 노력치 칸."""
        out = []
        it = self._item
        if self.stat_needed and self._stat:
            out.append((self._stat_layout(cv, width)[0], self._paint_statbox))
        if it and (it.get("effect") or {}).get("kind") == "ev" and self._ev:
            out.append((self._ev_layout(cv, width)[0], self._paint_evbox))
        return out

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
        # 가운데: 키 큰 도구 목록 (아래까지) / 오른쪽: 보라 띠 + 올리브 '누구에게' 칸 + 아래 줄
        x1 = mid_column(x0, W)
        self._paint_list(cv, x0, x1, H)
        # 아래 줄은 'OO 쓰기' 단추 하나, 알릴 말은 보라 띠 위에 잠깐 (글상자 · 닫기는 뺐다)
        BOT = U.h(self.ACTION_H)
        BH = self._band_height(cv, x1, W, H)
        self._paint_band(cv, x1, W, 0, BH)
        it = self._item
        self._paint_plates_area(cv, x1, W, BH, H - BOT, "누구에게 쓸까?",
                                B.target_hint(it) if it else "", self._mon_note,
                                self._boxes(cv, W - x1 - U.h(24)))
        self.close_btn.hide()
        self._paint_action_row(cv, x1, W, H - BOT, H, self.use_btn)
        self._toast_box = (x1, 0, W, BH)
        self._paint_toast()

    def _paint_list(self, cv, x0, x1, H):
        """가운데 칸: 찾기 + 줄 세우기 탭 (좁으면 탭은 아래 줄로) + 도구 목록."""
        ix1, iy1, ix2, iy2 = list_box(self, cv, x0, x1, H)
        th = U.h(26)
        K.text(cv, ix1, iy1 + th // 2, "찾기", font(10), anchor="w", tags=T)
        ex = ix1 + U.h(40)
        f = K.tkfont_of(cv, font(10))
        tabs_w = sum(f.measure(lb) + U.h(18) for _k, lb in B.ITEM_SORTS) + U.h(4) * (len(B.ITEM_SORTS) - 1)
        if ix2 - tabs_w - U.h(12) - ex >= U.h(110):                    # 한 줄에 다 든다
            tabs = self._tabs(cv, ix2, iy1, th, B.ITEM_SORTS, self.item_sort, "srt", self.set_item_sort,
                              align="right")
            self._place("ifind", self.item_find, ex, iy1, tabs[0][1][0] - ex - U.h(12), th)
            ly1 = iy1 + th + U.h(6)
        else:                                                           # 탭은 찾기 줄 아래로
            self._place("ifind", self.item_find, ex, iy1, ix2 - ex, th)
            iy1b = iy1 + th + U.h(4)
            self._tabs(cv, ix1, iy1b, th, B.ITEM_SORTS, self.item_sort, "srt", self.set_item_sort)
            ly1 = iy1b + th + U.h(6)
        if self._items_state == "list":
            self._place("items", self.items_vl.frame, ix1, ly1, ix2 - ix1, iy2 - ly1)
        else:
            self._hide("items")
            note = self._items_note if self._items_state == "nomatch" else \
                "가방이 비어 있다.\n야생 포켓몬을 잡거나 배틀에서 도구를 주울 수 있다."
            K.text(cv, (ix1 + ix2) // 2, ly1 + U.h(40), note, font(11), anchor="n", justify="center",
                   width=ix2 - ix1 - 20, tags=T)

    # ---------------- 능력 칸 (병뚜껑) ----------------
    def _stat_layout(self, cv, width):
        """(높이, 안내를 제목 아래 줄로 내리나, 한 줄 칸 수, 칸 폭). 칸은 6 → 3 → 2 개씩, 글씨가 다 들게."""
        hint, cells = self._stat
        f10, f9 = K.tkfont_of(cv, font(10)), K.tkfont_of(cv, font(9))
        inner = width - U.h(24)
        below = f10.measure("어느 능력을 단련할까?") + U.h(12) + f9.measure(hint) > inner
        need = max([f9.measure(lb) for _k, lb, _s in cells] or [0]) + U.h(16)
        gap = U.h(6)
        for cols in (6, 3, 2):
            cw = (inner - (cols - 1) * gap) / float(cols)
            if cw >= need:
                break
        rows = -(-len(cells) // cols)
        head = U.h(30) + (U.h(18) if below else 0)
        return head + rows * U.h(24) + (rows - 1) * gap + U.h(8), below, cols, cw

    def _paint_statbox(self, cv, x1, y, x2):
        hint, cells = self._stat
        h, below, cols, cw = self._stat_layout(cv, x2 - x1)
        K.framed(cv, x1, y, x2, y + h, 8, "#ffffff", LIST_FRAME, LIST_IN, lw=2, iw=2, tags=T)
        K.text(cv, x1 + U.h(12), y + U.h(8), "어느 능력을 단련할까?", font(10), tags=T)
        if below:
            cv.create_text(x1 + U.h(12), y + U.h(28), text=hint, fill=DIM, font=font(9), anchor="nw", tags=T)
        else:
            cv.create_text(x2 - U.h(12), y + U.h(8), text=hint, fill=DIM, font=font(9), anchor="ne", tags=T)
        gap = U.h(6)
        top = y + U.h(30) + (U.h(18) if below else 0)
        for i, (key, label, state) in enumerate(cells):
            r, c = divmod(i, cols)
            cx1 = x1 + U.h(12) + c * (cw + gap)
            cy1 = top + r * (U.h(24) + gap)
            cy2 = cy1 + U.h(24)
            tg = T + ("stc", "stc_" + key)
            if state == "on":
                fill, line, fg = "#fff3ec", CUR, CUR
            elif state == "free":
                fill, line, fg = "#f4f7fb", "#8a96a8", INK
            else:
                fill, line, fg = "#eceef1", "#c4c8ce", DIM
            K.rrect(cv, cx1, cy1, cx1 + cw, cy2, 6, fill=fill, outline=line, width=2, tags=tg)
            cv.create_text(cx1 + cw / 2, (cy1 + cy2) // 2, text=label, fill=fg, font=font(9), anchor="center",
                           tags=tg)
            cv.tag_bind("stc_" + key, "<Button-1>", lambda _e, k=key: self.pick_stat(k))

    # ---------------- 노력치 칸 ----------------
    def _ev_layout(self, cv, width):
        """(높이, 단 수, 이름 칸 폭, 값 칸 폭). 세 단 (두 줄)이 안 들면 두 단 (세 줄)."""
        rows = self._ev[0]
        f9 = K.tkfont_of(cv, font(9))
        lab = max([f9.measure(lb) for _k, lb, _v, _o in rows] or [0]) + U.h(8)
        val = f9.measure("252") + U.h(12)
        inner = width - U.h(24)
        cols = 3 if inner / 3.0 >= lab + U.h(40) + val else 2
        lines = -(-len(rows) // cols)
        return U.h(36) + lines * U.h(24), cols, lab, val

    def _paint_evbox(self, cv, x1, y, x2):
        rows, total_text, total_full = self._ev
        h, cols, lab, val = self._ev_layout(cv, x2 - x1)
        lines = -(-len(rows) // cols)
        K.framed(cv, x1, y, x2, y + h, 8, "#ffffff", LIST_FRAME, LIST_IN, lw=2, iw=2, tags=T)
        K.text(cv, x1 + U.h(12), y + U.h(8), "지금 노력치", font(10), tags=T)
        cv.create_text(x2 - U.h(12), y + U.h(8), text=total_text,
                       fill="#d02828" if total_full else (DIM if total_full is None else "#606068"),
                       font=font(9), anchor="ne", tags=T)
        colw = (x2 - x1 - U.h(24)) / float(cols)
        for i, (_key, label, v, on) in enumerate(rows):
            r, c = i % lines, i // lines
            cx = x1 + U.h(12) + c * colw
            cy = y + U.h(32) + r * U.h(24)
            cv.create_text(cx, cy, text=label, fill="#c02828" if on else "#606068", font=font(9), anchor="nw",
                           tags=T)
            bx1 = cx + lab
            bx2 = cx + colw - val
            cv.create_rectangle(bx1, cy + 3, bx2, cy + U.h(11), fill="#44484e", outline="", tags=T)
            fw = int((bx2 - bx1 - 2) * min(v or 0, B.EV_STAT_MAX) / float(B.EV_STAT_MAX))
            if fw > 0:
                cv.create_rectangle(bx1 + 1, cy + 4, bx1 + 1 + fw, cy + U.h(11) - 1,
                                    fill="#f6b42a" if on else "#58c878", outline="", tags=T)
            cv.create_text(cx + colw - U.h(10), cy, text=str(v) if v is not None else "-",
                           fill="#c02828" if on else INK, font=font(9), anchor="ne", tags=T)
