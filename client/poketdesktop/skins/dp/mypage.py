# -*- coding: utf-8 -*-
"""DP 테마 - 마이페이지 (트레이너 카드).

DP 의 트레이너 카드처럼 - 파란 카드에 명패(이름) · 칭호 · 티어 · 함께한 날 · 소지금, 그 아래 모은 것
(포켓몬 · 도감 · 이긴 관장 …), 칭호 · 시즌 기록 · 게시판 활동 · 계정 단락.

v2 (2026-10-25): 카드를 낮게(한 화면에 단락이 더 보이게), 카드의 몬스터볼 무늬 · 테두리 글씨 · 겹 테를 걷고,
단락은 파란 꼬리표 + 흰 판 한 겹. 명패 빛깔은 이름 글씨가 아니라 이름을 감싼 명패 바탕에 칠한다 (밝은 카드
위에서 노란 글씨가 안 읽혔다). 머리 단추는 글자만 (쪽 넘기기는 ◀ ▶).

동작은 기본 마이페이지(ui_mypage.MyPageWindow)의 것을 그대로 쓴다 - 서버의 /api/mypage 한 번, 게시판 활동은
한 쪽(다섯 줄)씩 따로 받기, 알림 '모두 읽음', 줄을 누르면 게시판의 그 글, 칭호 · 명패 바꾸기, 로그아웃 · 회원탈퇴,
설정 단추를 누르면 설정 화면.
"""
import tkinter as tk

from common.korean import ago, natural

from ... import ui_common as U
from ... import ui_mypage as MP
from . import CUR, DIM, INK, INK2, LINE, WHITE, font, tone
from . import kit as K

PAGE = "#cfe0f4"                                     # 쪽 바탕 (무늬 없음)
HEAD, HEAD_D = "#3a68c8", "#1f3c84"                  # 머리 띠
CARD_A, CARD_LINE, CARD_IN, CARD_IN_LINE = "#5c8ce4", "#1f3c84", "#f4f8ff", "#9ab8ea"
TILE = "#f2f6fc"
OFF_TAB, OFF_TAB_LINE = "#eef1f5", "#b6becb"


class MyPageWindow(MP.MyPageWindow):

    def _build(self):
        self.b_what, self.b_page, self.b_pages = "posts", 1, 1
        self.b_counts = {}
        self.b_items = []
        self.b_gen = 0
        self._msg = ("", None)
        self._job = None
        self._btns = []
        self.win.configure(bg=PAGE, highlightthickness=0)
        self.hcv = tk.Canvas(self.win, bg=HEAD, highlightthickness=0, bd=0, height=U.h(56))
        self.hcv.pack(fill="x")
        self.hcv.bind("<Configure>", lambda _e: self._paint_head())
        self.refresh_btn = K.CButton(self.hcv, "새로고침", self.load, "gray", font(10))
        self.back_btn = K.CButton(self.hcv, "← 마이페이지", self.show_page, "gray", font(10))
        self.gear_btn = K.CButton(self.hcv, "설정", self.toggle_settings, "blue", font(10))
        self.page = tk.Frame(self.win, bg=PAGE)
        self.page.pack(fill="both", expand=True)
        self.set_box = tk.Frame(self.win, bg=PAGE)
        self.cv = tk.Canvas(self.page, bg=PAGE, highlightthickness=0, bd=0, yscrollincrement=1)
        self.sb = K.Scroll(self.page, self.cv, PAGE)
        self.sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.configure(yscrollcommand=self.sb.set)
        U.scrollable(self.cv, 3)
        self.cv.bind("<Configure>", lambda _e: self._soon())
        self.b_prev = K.CButton(self.cv, "◀", lambda: self.turn(-1), "gray", font(10))
        self.b_next = K.CButton(self.cv, "▶", lambda: self.turn(1), "gray", font(10))
        self.b_clear = K.CButton(self.cv, "모두 읽음", self.clear_notify, "gray", font(9))
        self.rewards_btn = K.CButton(self.cv, "칭호·명패 바꾸기", self.open_rewards, "blue", font(9))
        self.account_btns = {}
        for _t, label, fn, danger in self.account_rows():
            self.account_btns[label] = K.CButton(self.cv, label, fn, "red" if danger else "gray", font(10))
        for tag in ("btab", "bline"):
            self.cv.tag_bind(tag, "<Enter>", lambda _e: self.cv.configure(cursor="hand2"))
            self.cv.tag_bind(tag, "<Leave>", lambda _e: self.cv.configure(cursor=""))

    # ---------------- 기본 창의 칠하는 자리 ----------------
    def say(self, text, color=U.GOOD):
        if self.alive:
            self._msg = (natural(text or ""), color)
            self._soon()

    def _fill(self, d):
        self._board(d)
        self._soon()

    def _board(self, d):
        b = d.get("board") or {}
        first = b.get("first") or {}
        self.b_counts = dict(b)
        self.b_what = first.get("what") or "posts"
        self._fill_tab(first)

    def _fill_tab(self, r):
        self.b_what = r.get("what") or self.b_what
        self.b_page = int(r.get("page") or 1)
        self.b_pages = int(r.get("pages") or 1)
        if r.get("counts"):
            self.b_counts.update(r["counts"])
        self.b_items = list(r.get("items") or [])
        sync = getattr(self.app, "set_board_unseen", None)
        if sync and r.get("counts"):
            sync(self.b_counts.get("unseen"))
        self.b_prev.configure(state="normal" if self.b_page > 1 else "disabled")
        self.b_next.configure(state="normal" if self.b_page < self.b_pages else "disabled")
        self._soon()

    def pick_tab(self, what):
        self.b_what, self.b_page = what, 1
        self.load_tab()

    def show_settings(self):
        if self.settings is None:
            from ...ui_settings import SettingsWindow
            self.settings = SettingsWindow(self.app, self.set_box, header=False)
            self.settings.win.configure(highlightthickness=0)
            self.settings.win.pack(fill="both", expand=True)
            self.app.settings_win = self.settings
        self.view = "settings"
        self.page.pack_forget()
        self.set_box.pack(fill="both", expand=True)
        self._paint_head()

    def show_page(self):
        self.view = "page"
        self.set_box.pack_forget()
        self.page.pack(fill="both", expand=True)
        self._paint_head()

    def _paint_gear(self, hot):
        pass

    # ---------------- 머리 ----------------
    def _paint_head(self):
        cv = self.hcv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 50:
            return
        cv.delete("head")
        tg = ("head",)
        cv.create_rectangle(0, 0, W, H, fill=HEAD, outline="", tags=tg)
        cv.create_rectangle(0, H - 3, W, H, fill=HEAD_D, outline="", tags=tg)
        cv.create_text(U.h(16), (H - 3) // 2, text="설정" if self.view == "settings" else "트레이너 카드",
                       fill=WHITE, font=font(15), anchor="w", tags=tg)
        bh = U.h(34)
        y1 = (H - 3 - bh) // 2
        x2 = W - U.h(12)
        if self.view == "settings":
            self.refresh_btn.hide()
            order = [self.back_btn, self.gear_btn]
        else:
            self.back_btn.hide()
            order = [self.gear_btn, self.refresh_btn]
        for b in order:
            w = b.want_width(U.h(22))
            b.layout(x2 - w, y1, x2, y1 + bh)
            x2 -= w + U.h(8)

    # ---------------- 쪽 ----------------
    def _soon(self):
        if self._job is None and self.alive:
            try:
                self._job = self.cv.after_idle(self._paint)
            except tk.TclError:
                pass

    def _paint(self):
        self._job = None
        cv = self.cv
        try:
            W = cv.winfo_width()
        except tk.TclError:
            return
        if W < 100:
            return
        cv.delete("all")
        for b in self._all_btns():
            b.hide()
        d = self.data
        pad = U.h(14)
        x1, x2 = pad, W - pad
        y = U.h(12)
        if d is None:
            K.text(cv, W // 2, U.h(60), "불러오는 중...", font(11), anchor="n")
            return
        y = self._card(cv, d, x1, x2, y)
        y = self._tiles(cv, d, x1, x2, y + U.h(10))
        y = self._titles(cv, d, x1, x2, y + U.h(10))
        y = self._seasons(cv, d, x1, x2, y + U.h(10))
        y = self._board_box(cv, d, x1, x2, y + U.h(10))
        y = self._account(cv, x1, x2, y + U.h(10))
        if self._msg[0]:
            y = self._wrap(cv, x1 + 4, y + U.h(10), self._msg[0], font(10),
                           tone(self._msg[1]) if self._msg[1] else INK, x2 - x1)
        total = y + U.h(16)
        h = max(total, cv.winfo_height())
        cv.configure(scrollregion=(0, 0, W, h))
        bg = cv.create_rectangle(0, 0, W, h, fill=PAGE, outline="")
        cv.tag_lower(bg)
        for b in self._all_btns():
            if b.box:
                b.draw()

    def _all_btns(self):
        return [self.b_prev, self.b_next, self.b_clear, self.rewards_btn] + list(self.account_btns.values())

    def _wrap(self, cv, x, y, text, spec, fill=INK, width=100):
        t = cv.create_text(x, y, text=K.wrap(cv, text, spec, width), fill=fill, font=spec, anchor="nw")
        b = cv.bbox(t)
        return b[3] if b else y

    def _box(self, cv, x1, x2, y, title, right=None):
        """단락 머리: 파란 꼬리표 (판 위 테에 걸친다) + 오른쪽에 덧붙임. 내용이 시작하는 y."""
        w, h = K.tag(cv, x1 + U.h(10), y, title, tags=("head2",))
        if right:
            # 덧붙임은 흰 작은 표 (판 테에 걸쳐도 글씨 위로 금이 지나가지 않게)
            rw = K.tkfont_of(cv, font(9)).measure(right) + U.h(14)
            rx = x1 + U.h(16) + w
            K.rrect(cv, rx, y + 1, rx + rw, y + h - 1, 5, fill=WHITE, outline=LINE, width=1, tags=("head2",))
            cv.create_text(rx + rw // 2, y + h // 2, text=right, fill=INK2, font=font(9), tags=("head2",))
        return y + h + U.h(8)

    def _close(self, cv, x1, x2, top, bottom):
        """단락 판 (흰 판 한 겹) - 꼬리표 가운데쯤에서 시작해 꼬리표가 테에 걸친다."""
        p = K.panel(cv, x1, top + U.h(11), x2, bottom)
        cv.tag_lower(p)
        cv.tag_raise("head2")
        return bottom

    # ---------------- 카드 ----------------
    def _card(self, cv, d, x1, x2, y):
        u = d.get("user") or {}
        s = U.h
        band = s(28)
        ix1, ix2 = x1 + s(10), x2 - s(10)
        tx = ix1 + s(14)
        # 안쪽 칸의 줄들 (명패 줄 · 칭호 · 함께한 날)
        name = u.get("name") or "?"
        nf = font(15)
        nw = K.tkfont_of(cv, nf).measure(name) + (s(24) if u.get("frameColor") else 0)
        nh = K.tkfont_of(cv, nf).metrics("linespace") + s(8)
        chips = []
        if u.get("admin"):
            chips.append(("운영자", "#e8a838"))
        if u.get("tierKr"):
            chips.append((u["tierKr"], "#7a8aa8"))
        cf = font(9)
        chip_ws = [K.tkfont_of(cv, cf).measure(lb) + s(16) for lb, _c in chips]
        title = ("칭호  %s" % u["title"]) if u.get("title") else ""
        tf = font(11)
        row_end = tx + nw + sum(w + s(6) for w in chip_ws) + s(10)
        title_inline = bool(title) and row_end + K.tkfont_of(cv, tf).measure(title) <= ix2 - s(14)
        bits = []
        if u.get("days"):
            bits.append("함께한 지 %d일째" % int(u["days"]))
        if u.get("money") is not None:
            bits.append("소지금 {:,}원".format(int(u.get("money") or 0)))
        inner_h = s(10) + nh + s(8) + (0 if (title_inline or not title) else s(24)) + s(20) + s(10)
        h = band + inner_h + s(10)
        # 카드 (파랑, 테 한 겹) + 안쪽 흰 칸
        K.rrect(cv, x1, y, x2, y + h, 12, fill=CARD_A, outline=CARD_LINE, width=2)
        cv.create_text(x1 + s(16), y + band // 2 + 1, text="TRAINER CARD", fill=WHITE, font=font(10), anchor="w")
        if u.get("createdAt"):
            cv.create_text(x2 - s(16), y + band // 2 + 1, text="%s 가입" % MP._date(u.get("createdAt")), fill=WHITE,
                           font=font(9), anchor="e")
        iy1 = y + band
        K.rrect(cv, ix1, iy1, ix2, y + h - s(10), 8, fill=CARD_IN, outline=CARD_IN_LINE, width=1)
        iy = iy1 + s(10)
        # 명패: 명패 빛깔이 있으면 그 빛깔 판에 이름 (글씨는 판 빛깔에 맞춰 진하게 · 희게)
        if u.get("frameColor"):
            col = u["frameColor"]
            K.rrect(cv, tx, iy, tx + nw, iy + nh, 6, fill=col, outline=K.look_of(col)[2], width=1)
            cv.create_text(tx + nw // 2, iy + nh // 2, text=name, fill=K.look_of(col)[3], font=nf)
        else:
            cv.create_text(tx, iy + nh // 2, text=name, fill=INK, font=nf, anchor="w")
        cx = tx + nw + s(10)
        for (label, col), w in zip(chips, chip_ws):
            K.rrect(cv, cx, iy + nh // 2 - s(10), cx + w, iy + nh // 2 + s(10), 6, fill=col)
            cv.create_text(cx + w // 2, iy + nh // 2, text=label, fill=K.look_of(col)[3], font=cf)
            cx += w + s(6)
        if title and title_inline:
            cv.create_text(cx + s(8), iy + nh // 2, text=title, fill="#c06810", font=tf, anchor="w")
        iy += nh + s(8)
        if title and not title_inline:
            K.text(cv, tx, iy, title, tf, fill="#c06810", width=ix2 - tx - s(14))
            iy += s(24)
        cv.create_text(tx, iy, text="  ·  ".join(bits), fill=INK2, font=font(10), anchor="nw")
        return y + h

    def _tiles(self, cv, d, x1, x2, y):
        top = y
        y = self._box(cv, x1, x2, y, "모은 것")
        items = self.tiles(d)
        cols = 3
        gap = U.h(8)
        cw = (x2 - x1 - U.h(28) - gap * (cols - 1)) / float(cols)
        th = U.h(58)
        for i, (name, value, note) in enumerate(items):
            r, c = divmod(i, cols)
            tx = x1 + U.h(14) + c * (cw + gap)
            ty = y + r * (th + gap)
            K.rrect(cv, tx, ty, tx + cw, ty + th, 6, fill=TILE)
            cv.create_text(tx + U.h(10), ty + U.h(7), text=name, fill="#2a5ab8", font=font(9), anchor="nw")
            cv.create_text(tx + U.h(10), ty + U.h(24), text=value, fill=INK, font=font(12), anchor="nw")
            if note:
                cv.create_text(tx + cw - U.h(8), ty + th - U.h(7), text=note, fill=INK2, font=font(9), anchor="se")
        rows = -(-len(items) // cols)
        return self._close(cv, x1, x2, top, y + rows * (th + gap) + U.h(4))

    def _titles(self, cv, d, x1, x2, y):
        t = d.get("titles") or {}
        top = y
        y = self._box(cv, x1, x2, y, "내 칭호", "%d / %d" % (int(t.get("count") or 0), int(t.get("total") or 0)))
        w = self.rewards_btn.want_width(U.h(16))
        self.rewards_btn.layout(x2 - U.h(12) - w, top - U.h(1), x2 - U.h(12), top + U.h(24))
        own = t.get("owned") or []
        ix, iw = x1 + U.h(16), x2 - x1 - U.h(32)
        if not own:
            y = self._wrap(cv, ix, y, "아직 가진 칭호가 없습니다. 도감 탭의 '칭호' 에서 얻는 방법을 볼 수 있습니다.",
                           font(10), DIM, iw)
            return self._close(cv, x1, x2, top, y + U.h(12))
        f = K.tkfont_of(cv, font(10))
        x = ix
        rh = U.h(26)
        for c in own:
            label = c.get("name") or ""
            on = label == t.get("equipped")
            w = f.measure(label) + U.h(18)
            if x + w > ix + iw:
                x = ix
                y += rh + U.h(6)
            K.rrect(cv, x, y, x + w, y + rh, 7, fill="#fff3ec" if on else OFF_TAB, outline=CUR if on else OFF_TAB_LINE,
                    width=2 if on else 1)
            cv.create_text(x + w // 2, y + rh // 2, text=label, fill=CUR if on else INK, font=font(10))
            x += w + U.h(6)
        y += rh + U.h(6)
        if t.get("equipped"):
            y = self._wrap(cv, ix, y, "테를 두른 것이 지금 달고 있는 칭호입니다.", font(9), INK2, iw)
        return self._close(cv, x1, x2, top, y + U.h(10))

    def _seasons(self, cv, d, x1, x2, y):
        top = y
        y = self._box(cv, x1, x2, y, "시즌 기록")
        ix = x1 + U.h(16)
        rows = d.get("seasons") or []
        for s in rows:
            head, body = MP.season_line(s)
            cv.create_text(ix, y, text=head, fill="#c02828" if s.get("current") else INK, font=font(10), anchor="nw")
            y = self._wrap(cv, ix + U.h(130), y + 1, body, font(10), INK2, x2 - x1 - U.h(160)) + U.h(6)
        if not rows:
            y = self._wrap(cv, ix, y, "시즌 기록이 없습니다.", font(10), DIM, x2 - x1 - U.h(32))
        return self._close(cv, x1, x2, top, y + U.h(6))

    def _board_box(self, cv, d, x1, x2, y):
        top = y
        y = self._box(cv, x1, x2, y, "게시판 활동", "받은 좋아요 %d" % int(self.b_counts.get("likes") or 0))
        ix = x1 + U.h(16)
        th = U.h(26)
        # 탭 [알림 | 내 글 | 내 댓글]
        f = K.tkfont_of(cv, font(10))
        x = ix
        for what in MP.TABS:
            label = self.tab_label(what, self.b_counts)
            w = f.measure(label) + U.h(18)
            on = what == self.b_what
            tg = ("btab", "btab_" + what)
            K.rrect(cv, x, y, x + w, y + th, 7, fill="#fff3ec" if on else OFF_TAB, outline=CUR if on else OFF_TAB_LINE,
                    width=2 if on else 1, tags=tg)
            cv.create_text(x + w // 2, y + th // 2, text=label, fill=CUR if on else INK, font=font(10), tags=tg)
            cv.tag_bind("btab_" + what, "<Button-1>", lambda _e, k=what: self.pick_tab(k))
            x += w + U.h(6)
        # 쪽 넘기기 (오른쪽)
        bw = U.h(34)
        self.b_next.layout(x2 - U.h(12) - bw, y, x2 - U.h(12), y + th)
        cv.create_text(x2 - U.h(20) - bw, y + th // 2, text="%d / %d" % (self.b_page, self.b_pages), fill=INK2,
                       font=font(9), anchor="e")
        self.b_prev.layout(x2 - U.h(70) - 2 * bw, y, x2 - U.h(70) - bw, y + th)
        if self.b_what == "notify" and self.b_items:
            cw = self.b_clear.want_width(U.h(16))
            self.b_clear.layout(x2 - U.h(80) - 2 * bw - cw, y, x2 - U.h(80) - 2 * bw, y + th)
        y += th + U.h(10)
        cv.create_line(ix, y - U.h(4), x2 - U.h(16), y - U.h(4), fill=LINE)
        iw = x2 - x1 - U.h(32)
        for n, it in enumerate(self.b_items):
            tg = ("bline", "bline%d" % n)
            if self.b_what == "notify":
                kind = "답글" if it.get("kind") == "reply" else "댓글"
                tag = "%s 님의 %s" % (it.get("actor") or "?", kind)
                text = "%s — %s" % (it.get("title") or "", it.get("snippet") or "")
                tail = ago(it.get("agoSec"))
            elif self.b_what == "posts":
                tag = it.get("kindKr") or ""
                text = it.get("title") or ""
                bits = []
                if int(it.get("likes") or 0):
                    bits.append("좋아요 %d" % int(it["likes"]))
                if int(it.get("comments") or 0):
                    bits.append("댓글 %d" % int(it["comments"]))
                bits.append(ago(it.get("agoSec")))
                tail = " · ".join(b for b in bits if b)
            else:
                tag, text = "", it.get("snippet") or ""
                tail = "%s · %s" % (it.get("title") or "", ago(it.get("agoSec")))
            x = ix
            if tag:
                cv.create_text(x, y, text=tag, fill="#2a5ab8", font=font(10), anchor="nw", tags=tg)
                x += K.tkfont_of(cv, font(10)).measure(tag) + U.h(10)
            cv.create_text(x2 - U.h(16), y + 1, text=tail, fill=INK2, font=font(9), anchor="ne", tags=tg)
            tw = max(U.h(80), x2 - U.h(16) - K.tkfont_of(cv, font(9)).measure(tail) - U.h(12) - x)
            t = cv.create_text(x, y, text=K.wrap(cv, text, font(10), tw), fill=INK, font=font(10), anchor="nw",
                               tags=tg)
            pid = it.get("postId") or it.get("id")
            cv.tag_bind("bline%d" % n, "<Button-1>", lambda _e, i=pid: self.open_post(i))
            bb = cv.bbox(t)
            y = (bb[3] if bb else y + U.h(18)) + U.h(8)
        if not self.b_items:
            y = self._wrap(cv, ix, y, MP.EMPTY.get(self.b_what, ""), font(10), DIM, iw) + U.h(4)
        return self._close(cv, x1, x2, top, y + U.h(6))

    def _account(self, cv, x1, x2, y):
        top = y
        y = self._box(cv, x1, x2, y, "계정")
        ix = x1 + U.h(16)
        for text, label, _fn, _danger in self.account_rows():
            b = self.account_btns[label]
            w = max(U.h(90), b.want_width(U.h(22)))
            b.layout(x2 - U.h(16) - w, y, x2 - U.h(16), y + U.h(32))
            y2 = self._wrap(cv, ix, y + U.h(7), text, font(10), INK2, x2 - x1 - w - U.h(56))
            y = max(y + U.h(32), y2) + U.h(8)
        return self._close(cv, x1, x2, top, y)
