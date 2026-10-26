# -*- coding: utf-8 -*-
"""DP 테마의 게시판 - 포켓몬센터 게시판처럼 (v2: 줄무늬 · 테두리 글씨 · 겹 테를 걷었다).

    위 띠      파란 띠에 '게시판'(제목만 테두리 글씨) · 글 몇 개 / 새로고침 · 글쓰기
    목록       무늬 없는 하늘색 바탕: [전체 | 공지 | 자유 | Q&A | 패치노트] 탭(빨간 밑줄)과 ◀ 쪽 ▶, 돋보기 · 찾기 칸,
               흰 판 한 장에 글 줄(종류 꼬리표 · 제목 / 쓴 사람 · 언제 · 댓글 · 좋아요). 공지는 크림색 줄에 주황 막대.
    글         제목 · 쓴 사람 · 본문(공지 · 패치노트의 주소는 파랗게, 누르면 열린다) · 좋아요 단추(하트 아이콘) ·
               파란 꼬리표 '댓글 N' · 댓글(답글은 들여 쓰고 주황 막대). 맨 아래에 늘 보이는 댓글 칸.
    쓰기       종류 고르기 · 제목 칸 · 내용 칸 · 글자 수 · 등록
    아래 줄    진한 테의 글상자 (알림)

아이콘은 쓰지 않는다 (좋아요의 ♥ 는 글자).

무엇을 보일지와 서버에 보내는 일은 기본 게시판의 것 그대로다 (_fill_list · open_post · send_comment ·
toggle_like · submit_post ...). 여기는 그리기만 한다.
"""
import tkinter as tk

from common.korean import ago, natural

from ... import ui_board as B
from ... import ui_common as U
from . import CUR, CYAN1, DIM, HOV, INK, INK2, LINE, PANEL, SEP, TAG_LINE, WHITE, WIN_BG, font, tone
from . import kit as K
from .battle import mix
from .rank import chip as _chip, head_band, paint_msg

BAND_LINE = "#1d5e80"

KIND_COLOR = {"notice": "#e07a28", "free": "#3a72cc", "qna": "#2c9a4c", "patch": "#d0508a"}
PIN_BG = "#fff4d8"
LINK, LINK_HOVER = "#2860c0", "#4a8ae8"
T = ("head",)


class _Text(object):
    def __init__(self, on_change):
        self.text = ""
        self.on_change = on_change

    def configure(self, text=None, **_kw):
        if text is not None and text != self.text:
            self.text = text
            self.on_change()

    config = configure

    def cget(self, key):
        return self.text if key == "text" else None


class _Pick(object):
    """기본 게시판이 U.Segmented 처럼 부르는 것 (set) 을 받아 다시 그린다."""

    def __init__(self, on_set):
        self.on_set = on_set

    def set(self, _key):
        self.on_set()


def chip(cv, x, y, text, col, tags=(), spec=None):
    """종류 꼬리표 (가운데 높이 y). 그린 폭. (옅은 바탕 · 진한 글씨 - 테두리 글씨를 쓰지 않는다)"""
    return _chip(cv, x, y, text, col, spec or font(9), tags)


def pill(cv, x, y, h, text, on, tags=(), spec=None):
    """고르는 칸 하나 (고른 것은 흰 바탕 · 빨간 테 · 빨간 글씨). 폭."""
    spec = spec or font(10)
    tw = K.tkfont_of(cv, spec).measure(text) + U.h(22)
    K.rrect(cv, x, y, x + tw, y + h, U.h(6), fill=WHITE if on else "#eef2f6", outline=CUR if on else LINE,
            width=2 if on else 1, tags=tags)
    cv.create_text(x + tw // 2, y + h // 2, text=text, fill=CUR if on else INK, font=spec, tags=tags)
    return tw


class BoardWindow(B.BoardWindow):

    # ---------------- 틀
    def _header(self):
        self.win.configure(bg=WIN_BG, highlightthickness=0)
        self.hcv = tk.Canvas(self.win, bg=TAG_LINE, highlightthickness=0, bd=0, height=U.h(56))
        self.hcv.pack(fill="x")
        self.hcv.bind("<Configure>", lambda _e: self._paint_head())
        self.count = _Text(self._paint_head)
        self.write_btn = K.CButton(self.hcv, "글쓰기", self.show_write, "red", font(10))
        self.refresh_btn = K.CButton(self.hcv, "새로고침", self.refresh, "gray", font(10))
        # 아래 줄 글상자 (기본 게시판은 self.status 를 만든 뒤 body 를 담는다)
        self._status_msg = ("", None)

    def _paint_head(self):
        cv, s = self.hcv, U.h
        try:
            w = cv.winfo_width() if cv.winfo_width() > 1 else U.h(B.W)
            h = cv.winfo_height() if cv.winfo_height() > 1 else s(56)
            cv.delete("head")
        except tk.TclError:
            return
        x = head_band(cv, w, h, TAG_LINE, BAND_LINE, "게시판")
        cv.create_text(x + s(14), h // 2 - s(1), text=self.count.text, fill=WHITE, font=font(10), anchor="w", tags=T)
        cv.tag_lower("head")
        bh, x2 = s(32), w - s(14)
        for btn in (self.write_btn, self.refresh_btn):
            bw = btn.want_width(s(24))
            btn.layout(x2 - bw, (h - bh) // 2 - s(1), x2, (h + bh) // 2 - s(1))
            x2 -= bw + s(8)

    def _make_status(self):
        self.stcv = tk.Canvas(self.win, bg=WIN_BG, highlightthickness=0, bd=0, height=U.h(38))
        self.stcv.bind("<Configure>", lambda _e: self._paint_status())
        return self.stcv

    def _paint_status(self):
        cv = getattr(self, "stcv", None)
        if cv is None:
            return
        text, color = self._status_msg
        paint_msg(cv, text, color)

    def say(self, text, color=U.GOOD):
        if not self.alive:
            return
        if getattr(self, "stcv", None) is None:
            # 기본 게시판의 __init__ 이 만든 status 를 DP 글상자로 바꿔 단다 (처음 한 번)
            try:
                self.status.pack_forget()
            except (AttributeError, tk.TclError):
                pass
            self._make_status().pack(side="bottom", fill="x", before=self.body)
        self._status_msg = (natural(text or ""), None if color in (U.GOOD, None) else color)
        self._paint_status()

    # ---------------- 목록
    def _build_list(self):
        if getattr(self, "stcv", None) is None:
            self.say("")
        s = U.h
        self.lcv = tk.Canvas(self.body, bg=CYAN1, highlightthickness=0, bd=0)
        self.lcv.pack(fill="both", expand=True)
        self.lcv.bind("<Configure>", lambda _e: self._paint_list_frame())
        self.seg = _Pick(self._paint_list_frame)
        self.prev_btn = K.CButton(self.lcv, "◀", lambda: self.turn(-1), "gray", font(10))
        self.next_btn = K.CButton(self.lcv, "▶", lambda: self.turn(1), "gray", font(10))
        self.q_var = tk.StringVar(value=self.q)
        self.q_box = K.entry(self.lcv, self.q_var, width=16)
        self.q_entry = self.q_box.entry
        self.q_entry.bind("<Return>", lambda _e: (self.search(), "break")[1])
        self.q_entry.bind("<Escape>", lambda _e: (self.clear_search(), "break")[1])
        # 빈 칸 안내 (입력칸은 캔버스 글 위를 덮는다 - 기본 게시판처럼 입력칸 안에 붙인다)
        self.q_hint = tk.Label(self.q_entry, text="제목·내용·쓴 사람으로 찾기", bg=WHITE, fg=DIM, font=font(9),
                               cursor="xterm")
        self.q_hint.bind("<Button-1>", lambda _e: self.q_entry.focus_set())

        def hint(*_a):
            try:
                if self.q_var.get() or self.q_entry.focus_get() is self.q_entry:
                    self.q_hint.place_forget()
                else:
                    self.q_hint.place(x=0, rely=0.5, anchor="w")
            except (tk.TclError, KeyError):
                pass
        self.q_var.trace_add("write", hint)
        self.q_entry.bind("<FocusIn>", hint, add="+")
        self.q_entry.bind("<FocusOut>", hint, add="+")
        hint()
        self.find_btn = K.CButton(self.lcv, "찾기", self.search, "blue", font(10))
        self.clear_btn = K.CButton(self.lcv, "전체 보기", self.clear_search, "gray", font(10))
        self.vl = K.VList(self.lcv, PANEL, self._draw_row)
        self.vl.on_click = lambda data, *_a: data[0] == "post" and self.open_post(data[1]["id"])
        self.vl.cv.bind("<Configure>", self._list_width, add="+")
        self.cv = self.vl.cv
        self._rows = []
        self._lw = 0
        self._wins = {}
        self._page_text = ""
        self._empty = None
        self._list_note = None

    def _search_row(self):
        pass

    def _paint_search(self):
        self._paint_list_frame()

    def _list_loading(self):
        self._list_note = "불러오는 중..."
        self._paint_list_frame()

    def _place(self, key, widget, x, y, w, h):
        cv = self.lcv
        w, h = max(1, int(w)), max(1, int(h))
        i = self._wins.get(key)
        if i is None:
            self._wins[key] = cv.create_window(x, y, window=widget, anchor="nw", width=w, height=h)
        else:
            cv.coords(i, x, y)
            cv.itemconfigure(i, width=w, height=h, state="normal")

    def _paint_list_frame(self):
        cv = getattr(self, "lcv", None)
        if cv is None or self.view != "list":
            return
        s = U.h
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
            cv.delete("frame")
        except tk.TclError:
            return
        if w <= 1:
            return
        t = ("frame",)
        cv.create_rectangle(0, 0, w, h, fill=CYAN1, outline="", tags=t)
        # 종류 탭 (빨간 밑줄) - 누름은 꼬리표로 받는다
        x, y, th = s(10), s(8), s(32)
        K.tabs(cv, x, y, th, B.KINDS, self.kind, "kind_", spec=font(11), tags=t)
        for key, _lb in B.KINDS:
            cv.tag_bind("kind_" + key, "<Button-1>", lambda _e, k=key: self.pick_kind(k))
        cv.tag_bind("kind_", "<Enter>", lambda _e: cv.configure(cursor="hand2"))
        cv.tag_bind("kind_", "<Leave>", lambda _e: cv.configure(cursor=""))
        # ◀ 쪽 ▶
        bw = s(34)
        self.next_btn.layout(w - s(14) - bw, y, w - s(14), y + th)
        pid = K.text(cv, w - s(14) - bw - s(10), y + th // 2, self._page_text, font(10), anchor="e", tags=t)[1]
        px = cv.bbox(pid)[0] if self._page_text else w - s(14) - bw - s(10)
        self.prev_btn.layout(px - s(10) - bw, y, px - s(10), y + th)
        # 찾기 줄: 입력칸 · 찾기 (· 전체 보기)
        y += th + s(8)
        bh = s(30)
        x2 = w - s(14)
        fw = self.find_btn.want_width(s(24))
        self.find_btn.layout(x2 - fw, y, x2, y + bh)
        x2 -= fw + s(6)
        if self.q:
            cw = self.clear_btn.want_width(s(24))
            self.clear_btn.layout(x2 - cw, y, x2, y + bh)
            x2 -= cw + s(6)
        else:
            self.clear_btn.hide()
        qx = s(14)
        self._place("q", self.q_box, qx, y, x2 - qx, bh)
        # 흰 목록 판 한 장 (가는 테)
        y += bh + s(8)
        x1, x2 = s(10), w - s(10)
        y2 = h - s(4)
        K.panel(cv, x1, y, x2, y2, tags=t)
        cv.tag_lower("frame")
        note = self._list_note or self._empty
        if note and not self._rows:
            self._unplace("vl")
            K.text(cv, (x1 + x2) // 2, y + s(40), note, font(10), fill=DIM, anchor="n", width=x2 - x1 - s(30),
                   justify="center", tags=t)
        else:
            self._place("vl", self.vl.frame, x1 + 2, y + 2, x2 - x1 - 4, y2 - y - 4)

    def _unplace(self, key):
        i = self._wins.get(key)
        if i is not None:
            self.lcv.itemconfigure(i, state="hidden")

    def _paint_list(self, pinned, posts, empty, page_text, can_prev, can_next, count):
        self._list_note = None
        self._empty = empty
        self._page_text = page_text
        self.prev_btn.configure(state="normal" if can_prev else "disabled")
        self.next_btn.configure(state="normal" if can_next else "disabled")
        self.count.configure(text=count)
        self._rows = [("post", p, True) for p in pinned] + [("post", p, False) for p in posts]
        self._paint_list_frame()
        self._relayout(keep=False)

    def _list_width(self, e):
        if e.width != self._lw:
            self._lw = e.width
            self._relayout(keep=True)

    def _relayout(self, keep):
        w = self._lw or self.vl.cv.winfo_width()
        if w <= 1:
            return
        s = U.h
        rows = []
        for kind, p, pinned in self._rows:
            tw = w - s(24) - s(60) - self._chip_w(p)
            th = K.text_height(self.vl.cv, p.get("title") or "", font(11), max(60, tw - s(120)))
            rows.append((s(18) + th + s(6) + s(18) + s(4), (kind, p, pinned)))
        self.vl.set(rows, keep=keep)

    def _chip_w(self, p):
        return K.tkfont_of(self.vl.cv, font(9)).measure(p.get("kindKr") or "") + U.h(14)

    def _draw_row(self, cv, data, x, y, w, h, tags, hov):
        s = U.h
        _kind, p, pinned = data
        bg = PIN_BG if pinned else PANEL
        if hov is not None:
            bg = HOV if not pinned else mix(PIN_BG, "#ffe4b0", 0.5)
        cv.create_rectangle(x, y, x + w, y + h, fill=bg, outline="", tags=tags)
        cv.create_line(x + s(8), y + h - 1, x + w - s(8), y + h - 1, fill=SEP, tags=tags)
        if pinned:
            cv.create_rectangle(x + s(2), y + s(6), x + s(6), y + h - s(6), fill="#e07a28", outline="", tags=tags)
        lx = x + s(14)
        ty = y + s(18)
        cw = chip(cv, lx, ty, p.get("kindKr") or "", KIND_COLOR.get(p.get("kind"), "#9aa2ae"), tags)
        # 오른쪽: 댓글 · 좋아요
        rx = x + w - s(14)
        likes = int(p.get("likes") or 0)
        if likes:
            col = "#c06810" if p.get("liked") else INK2
            lid = cv.create_text(rx, ty, text="좋아요 %d" % likes, fill=col, font=font(9), anchor="e", tags=tags)
            rx = cv.bbox(lid)[0] - s(10)
        n = int(p.get("comments") or 0)
        if n:
            nid = cv.create_text(rx, ty, text="댓글 %d" % n, fill="#c06810", font=font(9), anchor="e", tags=tags)
            rx = cv.bbox(nid)[0] - s(10)
        tx = lx + cw + s(8)
        _a, b = K.text(cv, tx, ty - K.tkfont_of(cv, font(11)).metrics("linespace") // 2, p.get("title") or "",
                       font(11), anchor="nw", width=max(60, rx - tx), tags=tags)
        ay = cv.bbox(b)[3] + s(4) + s(9)
        self._author_at(cv, lx, ay, p, tags)

    def _author_at(self, cv, x, y, item, tags, time=True):
        s = U.h
        col = item.get("authorColor")
        nid = K.text(cv, x, y, item.get("author") or "?", font(10), fill=tone(col) if col else INK, anchor="w",
                     tags=tags)[1]
        xx = cv.bbox(nid)[2] + s(6)
        if item.get("authorAdmin"):
            xx += chip(cv, xx, y, "운영자", "#e07a28", tags) + s(6)
        if item.get("authorTitle"):
            tid = cv.create_text(xx, y, text=item["authorTitle"], fill="#c06810", font=font(9), anchor="w", tags=tags)
            xx = cv.bbox(tid)[2] + s(8)
        if time:
            bits = [ago(item.get("agoSec"))]
            if item.get("edited"):
                bits.append("고침")
            cv.create_text(xx, y, text="  ·  ".join(b for b in bits if b), fill=INK2, font=font(9), anchor="w",
                           tags=tags)

    # ---------------- 글
    def _post_loading(self):
        cv = tk.Canvas(self.body, bg=WHITE, highlightthickness=0, bd=0)
        cv.pack(fill="both", expand=True)
        cv.create_text(U.h(30), U.h(30), text="불러오는 중...", fill=DIM, font=font(10), anchor="w")

    def _show_post(self, p, bottom=False, keep=None):
        self._clear("post")
        self.post = p
        self.reply_to = None
        self.like_busy = False
        s = U.h
        # 위 줄: ← 목록 / 수정 · 삭제
        top = tk.Canvas(self.body, bg=CYAN1, highlightthickness=0, bd=0, height=s(48))
        top.pack(fill="x")
        back = K.CButton(top, "← 목록", self.show_list, "gray", font(10))
        acts = []
        if p.get("canDelete"):
            acts.append(K.CButton(top, "삭제", self.delete_post, "red", font(10)))
        if p.get("canEdit"):
            acts.append(K.CButton(top, "수정", self.show_edit, "blue", font(10)))

        def lay(_e=None):
            w = top.winfo_width()
            top.delete("bg")
            top.create_line(0, s(48) - 1, w, s(48) - 1, fill=LINE, tags=("bg",))
            bw = back.want_width(s(24))
            back.layout(s(14), s(8), s(14) + bw, s(40))
            x2 = w - s(14)
            for b in acts:
                bw = b.want_width(s(24))
                b.layout(x2 - bw, s(8), x2, s(40))
                x2 -= bw + s(8)
        top.bind("<Configure>", lay)
        # 맨 아래의 댓글 칸을 먼저 붙인다 (늘 보인다)
        self._composer()
        # 굴러가는 글
        self.pcv = tk.Canvas(self.body, bg=WHITE, highlightthickness=0, bd=0)
        sb = K.Scroll(self.body, self.pcv, WHITE)
        sb.pack(side="right", fill="y")
        self.pcv.configure(yscrollcommand=sb.set)
        self.pcv.pack(fill="both", expand=True)
        self.cv = self.pcv
        U.scrollable(self.pcv, 60)
        self.pcv.bind("<Configure>", lambda e: self._paint_post(e.width))
        self.count.configure(text="")
        if keep:
            self.input.insert("1.0", keep)
            self._count_input()
        self._post_bottom = bottom

    def _paint_post(self, w):
        cv, s, p = self.pcv, U.h, self.post
        if not p or w <= 1:
            return
        cv.delete("all")
        x, iw = s(18), w - s(36)
        y = s(14)
        cw = chip(cv, x, y + s(12), p.get("kindKr") or "", KIND_COLOR.get(p.get("kind"), "#9aa2ae"))
        _a, b = K.text(cv, x + cw + s(10), y, p.get("title") or "", font(15), anchor="nw", width=iw - cw - s(10))
        y = cv.bbox(b)[3] + s(12)
        self._author_at(cv, x, y, p, ())
        y += s(16)
        cv.create_line(x, y, x + iw, y, fill=LINE)
        y += s(12)
        # 본문 - 공지 · 패치노트는 주소를 누를 수 있다
        text = p.get("body") or ""
        parts = B.split_links(text) if p.get("kind") in B.TRUSTED_KINDS else [("text", text)]
        for n, (kind, chunk) in enumerate(parts):
            if kind == "link":
                tag = "link%d" % n
                tid = cv.create_text(x, y, text=chunk, fill=LINK, font=font(11) + ("underline",), anchor="nw",
                                     width=iw, tags=(tag,))
                cv.tag_bind(tag, "<Button-1>", lambda _e, u=chunk: B.open_url(u))
                cv.tag_bind(tag, "<Enter>", lambda _e, t=tag: (cv.itemconfigure(t, fill=LINK_HOVER),
                                                                cv.configure(cursor="hand2")))
                cv.tag_bind(tag, "<Leave>", lambda _e, t=tag: (cv.itemconfigure(t, fill=LINK), cv.configure(cursor="")))
                y = cv.bbox(tid)[3] + s(4)
            else:
                _a, b = K.text(cv, x, y, chunk, font(11), anchor="nw", width=iw)
                y = cv.bbox(b)[3] + s(4)
        y += s(12)
        # 좋아요
        self._like_y = y
        self._paint_like(p)
        y += s(34) + s(14)
        cv.create_line(x, y, x + iw, y, fill=LINE)
        y += s(12)
        _tw, bh = K.tag(cv, x, y, "댓글 %d" % int(p.get("comments") or 0))
        y += bh + s(10)
        comments = p.get("commentList") or []
        for c in comments:
            y = self._paint_comment(cv, c, x, y, iw, False)
        if not comments:
            cv.create_text(x, y + s(8), text="아직 댓글이 없습니다.", fill=DIM, font=font(10), anchor="w")
            y += s(30)
        cv.configure(scrollregion=(0, 0, w, y + s(12)))
        if getattr(self, "_post_bottom", False):
            self._post_bottom = False
            cv.yview_moveto(1.0)

    def _paint_comment(self, cv, c, x, y, iw, reply):
        s = U.h
        if reply:
            x += s(28)
            iw -= s(28)
        tag = "cm%d" % c.get("id", 0)
        y1 = y
        inner = x + s(14)
        if c.get("deleted"):
            hy = y1 + s(10)
            tid = cv.create_text(inner, hy, text="삭제된 댓글입니다.", fill=DIM, font=font(9), anchor="nw", tags=(tag,))
            y2 = cv.bbox(tid)[3] + s(10)
        else:
            ay = y1 + s(18)
            self._author_at(cv, inner, ay, c, (tag,))
            rx = x + iw - s(12)
            links = []
            if c.get("canDelete"):
                links.append(("삭제", "#d02828", lambda cid=c["id"]: self.delete_comment(cid)))
            links.append(("답글", "#2860c0", lambda cc=c: self.set_reply(cc)))
            for n, (text, col, fn) in enumerate(links):
                lt = "%s_l%d" % (tag, n)
                lid = cv.create_text(rx, ay, text=text, fill=col, font=font(9), anchor="e", tags=(tag, lt))
                cv.tag_bind(lt, "<Button-1>", lambda _e, f=fn: f())
                cv.tag_bind(lt, "<Enter>", lambda _e: cv.configure(cursor="hand2"))
                cv.tag_bind(lt, "<Leave>", lambda _e: cv.configure(cursor=""))
                rx = cv.bbox(lid)[0] - s(12)
            _a, b = K.text(cv, inner, ay + s(12), c.get("body") or "", font(10), anchor="nw", width=iw - s(28),
                           tags=(tag,))
            y2 = cv.bbox(b)[3] + s(10)
        box = K.rrect(cv, x, y1, x + iw, y2, s(8), fill="#f8f8f4" if reply else "#fbfbfb", outline="#d4dae2",
                      width=1)
        cv.tag_lower(box)
        if reply:
            cv.create_rectangle(x + s(1), y1 + s(4), x + s(4), y2 - s(4), fill="#e07a28", outline="")
        y = y2 + s(6)
        for r in c.get("replies") or []:
            y = self._paint_comment(cv, r, x - (s(28) if reply else 0), y, iw + (s(28) if reply else 0), True)
        return y

    def _paint_like(self, p):
        cv = getattr(self, "pcv", None)
        if cv is None:
            return
        s = U.h
        try:
            cv.delete("like")
        except tk.TclError:
            return
        on = bool(p.get("liked"))
        n = int(p.get("likes") or 0)
        x, y = s(18), self._like_y
        text = "%s 좋아요 %d" % ("♥" if on else "♡", n)
        tw = K.tkfont_of(cv, font(10)).measure(text) + s(30)
        line, body = ("#c88a3a", "#ffe6b0") if on else (K.KINDS["gray"][2], K.KINDS["gray"][0])
        t = ("like",)
        K.button_shape(cv, x, y, x + tw, y + s(34), body, line, tags=t)
        cv.create_text(x + s(15), y + s(16), text=text, fill="#a85a20" if on else INK, font=font(10),
                       anchor="w", tags=t)
        cv.tag_bind("like", "<Button-1>", lambda _e: self.toggle_like())
        cv.tag_bind("like", "<Enter>", lambda _e: cv.configure(cursor="hand2"))
        cv.tag_bind("like", "<Leave>", lambda _e: cv.configure(cursor=""))

    def _composer(self):
        s = U.h
        box = tk.Frame(self.body, bg=WIN_BG, highlightthickness=1, highlightbackground=LINE)
        box.pack(side="bottom", fill="x")
        self.comp_box = box
        self.reply_bar = tk.Frame(box, bg=WIN_BG)
        self.reply_lbl = tk.Label(self.reply_bar, text="", bg=WIN_BG, fg="#2860c0", font=font(10), anchor="w")
        self.reply_lbl.pack(side="left")
        cancel = tk.Label(self.reply_bar, text="취소", bg=WIN_BG, fg=INK2, font=font(10), cursor="hand2")
        cancel.pack(side="left", padx=(10, 0))
        cancel.bind("<Button-1>", lambda _e: self.set_reply(None))
        row = tk.Frame(box, bg=WIN_BG)
        row.pack(fill="x", padx=s(10), pady=s(8))
        self.comp_row = row
        side = tk.Canvas(row, bg=WIN_BG, highlightthickness=0, bd=0, width=s(110), height=s(64))
        side.pack(side="right", fill="y", padx=(s(8), 0))
        self.send_btn = K.CButton(side, "댓글 등록", self.send_comment, "blue", font(10))
        self.send_btn.layout(1, 0, s(110) - 2, s(38))
        self._count_cv = side
        frame = tk.Frame(row, bg=WHITE, highlightthickness=2, highlightbackground="#a8b0bc",
                         highlightcolor=CUR)
        frame.pack(side="left", fill="x", expand=True)
        self.input = tk.Text(frame, height=3, width=1, bg=WHITE, fg=INK, insertbackground=INK, relief="flat",
                             bd=0, font=font(11), wrap="word", highlightthickness=0, undo=True)
        self.input.pack(fill="x", padx=8, pady=6)
        self.input.bind("<KeyRelease>", lambda _e: self._count_input())
        for seq in ("<Control-Return>", "<Command-Return>"):
            try:
                self.input.bind(seq, lambda _e: (self.send_comment(), "break")[1])
            except tk.TclError:
                pass
        self._count_input()

    def _count_input(self):
        cv = getattr(self, "_count_cv", None)
        if cv is None:
            return
        n = len(self.input.get("1.0", "end-1c").strip())
        lim = self.limits.get("comment", 300)
        cv.delete("cnt")
        cv.create_text(U.h(55), U.h(52), text="%d / %d" % (n, lim), fill="#d02828" if n > lim else DIM,
                       font=font(8), tags=("cnt",))

    def set_reply(self, c):
        self.reply_to = c
        if c is None:
            self.reply_bar.pack_forget()
            self.send_btn.configure(text="댓글 등록")
            return
        self.reply_lbl.configure(text=natural("%s 님의 댓글에 답글을 답니다" % (c.get("author") or "?")))
        self.reply_bar.pack(fill="x", padx=U.h(12), pady=(U.h(6), 0), before=self.comp_row)
        self.send_btn.configure(text="답글 등록")
        try:
            self.input.focus_set()
        except tk.TclError:
            pass

    # ---------------- 쓰기
    def _paint_write(self, post):
        s = U.h
        back = (lambda: self.open_post(post["id"])) if post else self.show_list
        self.wcv = cv = tk.Canvas(self.body, bg=CYAN1, highlightthickness=0, bd=0)
        cv.pack(fill="both", expand=True)
        self.back_btn = K.CButton(cv, "← 취소", back, "gray", font(10))
        self.post_btn = K.CButton(cv, "고치기" if post else "등록", self.submit_post, "red", font(11))
        self.kind_seg = _Pick(self._paint_write_frame)
        self._write_post = post
        self.title_var = tk.StringVar(value=(post or {}).get("title") or "")
        self.title_entry = K.entry(cv, self.title_var, width=20)
        self.title_var.trace_add("write", lambda *_a: self._count_post())
        tf = tk.Frame(cv, bg=WHITE, highlightthickness=2, highlightbackground="#a8b0bc", highlightcolor=CUR)
        self.text = tk.Text(tf, bg=WHITE, fg=INK, insertbackground=INK, relief="flat", bd=0, font=font(11),
                            wrap="word", highlightthickness=0, undo=True, height=6, width=1)
        self.text.pack(fill="both", expand=True, padx=8, pady=6)
        self._text_frame = tf
        if post:
            self.text.insert("1.0", post.get("body") or "")
        self.text.bind("<KeyRelease>", lambda _e: self._count_post())
        self._counts = ("", "", False, False)
        self._wwins = {}
        cv.bind("<Configure>", lambda _e: self._paint_write_frame())

    def _wplace(self, key, widget, x, y, w, h):
        cv = self.wcv
        w, h = max(1, int(w)), max(1, int(h))
        i = self._wwins.get(key)
        if i is None:
            self._wwins[key] = cv.create_window(x, y, window=widget, anchor="nw", width=w, height=h)
        else:
            cv.coords(i, x, y)
            cv.itemconfigure(i, width=w, height=h)

    def _paint_write_frame(self):
        cv = getattr(self, "wcv", None)
        if cv is None or self.view != "write":
            return
        s = U.h
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
            cv.delete("wf")
        except tk.TclError:
            return
        if w <= 1:
            return
        t = ("wf",)
        post = self._write_post
        cv.create_rectangle(0, 0, w, h, fill=CYAN1, outline="", tags=t)
        bw = self.back_btn.want_width(s(24))
        self.back_btn.layout(s(14), s(8), s(14) + bw, s(40))
        K.text(cv, s(14) + bw + s(14), s(24), "글 고치기" if post else "새 글", font(13), anchor="w", tags=t)
        x1, x2 = s(10), w - s(10)
        y = s(50)
        ph_bottom = h - s(56)
        K.panel(cv, x1, y, x2, ph_bottom, tags=t)
        ix1, ix2 = x1 + s(16), x2 - s(16)
        y += s(14)
        if not post:
            kinds, note = self._write_kinds()
            cv.create_text(ix1, y + s(15), text="종류", fill=INK2, font=font(10), anchor="w", tags=t)
            xx = ix1 + s(52)
            for key, lb in kinds:
                tg = t + ("wk", "wk_" + key)
                xx += pill(cv, xx, y, s(30), lb, key == self.kind_var, tags=tg) + s(6)
                cv.tag_bind("wk_" + key, "<Button-1>", lambda _e, k=key: self._pick_post_kind(k))
            cv.tag_bind("wk", "<Enter>", lambda _e: cv.configure(cursor="hand2"))
            cv.tag_bind("wk", "<Leave>", lambda _e: cv.configure(cursor=""))
            if note:
                K.text(cv, xx + s(4), y + s(15), note, font(9), fill=INK2, anchor="w", width=max(60, ix2 - xx - s(4)),
                       tags=t)
            y += s(42)
        cv.create_text(ix1, y + s(16), text="제목", fill=INK2, font=font(10), anchor="w", tags=t)
        tcount, bcount, tover, bover = self._counts
        cid = cv.create_text(ix2, y + s(16), text=tcount, fill="#d02828" if tover else INK2, font=font(9), anchor="e",
                             tags=t)
        cx = cv.bbox(cid)[0] if tcount else ix2
        self._wplace("title", self.title_entry, ix1 + s(52), y, cx - s(8) - (ix1 + s(52)), s(32))
        y += s(44)
        cv.create_text(ix1, y + s(10), text="내용", fill=INK2, font=font(10), anchor="w", tags=t)
        y += s(24)
        self._wplace("text", self._text_frame, ix1, y, ix2 - ix1, ph_bottom - s(16) - y)
        # 아래: 글자 수 · 등록
        pw = self.post_btn.want_width(s(36))
        self.post_btn.layout(x2 - pw, h - s(48), x2, h - s(10))
        cv.create_text(x2 - pw - s(12), h - s(29), text=bcount, fill="#d02828" if bover else INK2, font=font(9),
                       anchor="e", tags=t)
        cv.tag_lower("wf")

    def _count_post(self):
        try:
            t = len(self.title_var.get().strip())
            b = len(self.text.get("1.0", "end-1c").strip())
        except (tk.TclError, AttributeError):
            return
        tl, bl = self.limits.get("title", 40), self.limits.get("body", 2000)
        self._counts = ("%d / %d" % (t, tl), "%d / %d자" % (b, bl), t > tl, b > bl)
        self._paint_write_frame()
