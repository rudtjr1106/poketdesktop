# -*- coding: utf-8 -*-
"""게시판 — 공지와 자유 글, 댓글과 답글 (1.8.0).

화면은 셋이고 한 칸(self.body)에서 갈아 끼운다.

  · **목록** — [전체 | 공지 | 자유]. '전체' 는 최근 공지 셋이 맨 위에 붙는다.
  · **글** — 내용과 댓글. 댓글마다 '답글' 을 누르면 아래 입력칸이 그 댓글에
    다는 답글이 된다. 답글은 한 단계까지만 들여 쓴다.
  · **쓰기** — 제목과 내용. 공지는 운영자에게만 고르는 칸이 보인다.

## 누가 썼는지

글·댓글마다 이름을 적는다. 명패를 단 사람은 그 색으로, 칭호가 있으면 옆에
작게, 운영자는 '운영자' 표시를 붙인다. 표시는 **서버가 정한다** - 비슷한
이름으로 운영자를 흉내 내도 표시는 안 붙는다.

## 넘치면 굴린다

목록, 글과 댓글, 쓰는 칸 모두 길어지면 굴려서 본다. 댓글 입력칸과 단추
줄은 굴러가는 칸 밖(아래)에 붙여서, 댓글이 아무리 많아도 늘 보인다.

## 판정은 서버가 한다

글자 수, 공지 권한, 도배(글 30초·댓글 5초), 지울 수 있는지 - 전부 서버가
본다. 여기서는 서버가 준 canNotice / canDelete / canEdit 대로 단추를 보이고,
거절당하면 그 말을 아래 줄에 그대로 적는다.
"""
import re
import tkinter as tk
from tkinter import ttk

from common.korean import ago, natural

from . import ui_common as U
from .ui_common import run_async

W, H = 760, 660
ROW_BG = "#161b28"
PIN_BG = "#231d10"            # 공지 줄
REPLY_BG = "#10141e"
KINDS = [("all", "전체"), ("notice", "공지"), ("free", "자유"), ("qna", "Q&A")]
KIND_COLOR = {"notice": U.ACCENT, "free": U.INFO, "qna": U.GOOD}
# 글을 쓸 때 고르는 종류. 공지는 운영자에게만 보인다.
WRITE_KINDS = [("free", "자유"), ("qna", "Q&A")]
LIMITS = {"title": 40, "body": 2000, "comment": 300}


def _err(e):
    return getattr(e, "message", None) or str(e)


# ---------------------------------------------------------------- 공지의 링크
LINK = "#6fb7ff"
LINK_HOVER = "#a8d4ff"
# 주소에 쓸 수 있는 글자만 잇는다. 한글이 바로 붙어 있어도 ("…/releases에서")
# 주소가 거기서 끝난다.
_URL = re.compile(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+")
_URL_TAIL = ".,;:!?)]'"


def split_links(text):
    """글을 [("text", ..), ("link", 주소), ..] 로 가른다. 주소는 한 줄을 통째로 차지한다."""
    text = text or ""
    out, pos = [], 0
    for m in _URL.finditer(text):
        url = m.group(0).rstrip(_URL_TAIL)
        if len(url) <= len("https://"):
            continue
        before = text[pos:m.start()]
        if before.strip():
            out.append(("text", before.strip("\n")))
        out.append(("link", url))
        pos = m.start() + len(url)
    rest = text[pos:]
    if rest.strip() or not out:
        out.append(("text", rest.strip("\n") if out else rest))
    return out


def open_url(url):
    """기본 브라우저로 연다. http·https 만."""
    if not (url or "").lower().startswith(("http://", "https://")):
        return False
    import webbrowser
    try:
        return bool(webbrowser.open(url))
    except Exception:                                       # noqa: BLE001
        return False


class BoardWindow(object):

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        self.alive = True
        self.kind = "all"
        self.page = 1
        self.data = None          # 마지막으로 받은 목록
        self.post = None          # 열어 본 글 (댓글 포함)
        self.view = None          # list / post / write
        self.reply_to = None      # 답글을 달 댓글
        self.edit_id = None       # 고치는 중인 글 번호
        self.can_notice = False
        self.limits = dict(LIMITS)
        self._gen = 0             # 화면을 바꿀 때마다 오른다. 늦게 온 답은 버린다
        self.cv = None
        self.fit = None

        self.win = U.panel(parent, self.root, "포스크탑 — 게시판",
                           W, H, 560, 480, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            U.install_wheel(self.win)

        self._header()
        self.status = U.status_line(self.win, "")
        self.status.pack(side="bottom", fill="x", padx=16, pady=(6, 12))
        self.body = tk.Frame(self.win, bg=U.BG)
        self.body.pack(fill="both", expand=True)
        self.show_list()

    # ---------------- 머리 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=U.h(62))
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)
        # 게시판 그림 — 종이 한 장
        cv = tk.Canvas(inner, width=28, height=28, bg=U.BG2,
                       highlightthickness=0, bd=0)
        cv.pack(side="left")
        cv.create_rectangle(4, 3, 24, 25, fill="#f4f6fb", outline=U.INK, width=2)
        for y in (9, 14, 19):
            cv.create_line(8, y, 20, y, fill=U.INK, width=2)
        tk.Label(inner, text="게시판", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(15))).pack(side="left", padx=(12, 12))
        self.count = tk.Label(inner, text="", bg=U.BG2, fg=U.FG_FAINT,
                              font=U.FONT_S)
        self.count.pack(side="left")
        self.write_btn = U.PushButton(inner, "글쓰기", self.show_write, height=32,
                                      font=U.FONT_B)
        self.write_btn.pack(side="right")
        U.ghost_button(inner, "새로고침", self.refresh,
                       height=32).pack(side="right", padx=(0, 8))
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

    def say(self, text, color=U.GOOD):
        if self.alive:
            U.set_status(self.status, natural(text or ""), color)

    # ---------------- 화면 갈아 끼우기 ----------------
    def _clear(self, view):
        self._gen += 1
        self.view = view
        self.cv = None
        self.fit = None
        for w in self.body.winfo_children():
            w.destroy()
        return self._gen

    def _scroll_area(self, parent, bg=U.BG):
        """굴러가는 칸 하나. 안쪽 틀을 돌려준다."""
        holder = tk.Frame(parent, bg=bg)
        holder.pack(fill="both", expand=True)
        cv = tk.Canvas(holder, bg=bg, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(holder, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(cv, bg=bg)
        wid = cv.create_window((0, 0), window=inner, anchor="nw")
        self.fit = U.scroll_fitter(cv, inner, wid)
        U.scrollable(cv, 60)
        self.cv = cv
        return inner

    def refresh(self):
        if self.view == "post" and self.post:
            return self.open_post(self.post["id"])
        if self.view == "write":
            return
        self.load_list()

    # ---------------- 누가 썼는지 ----------------
    def _author(self, parent, item, bg, time=True):
        f = tk.Frame(parent, bg=bg)
        tk.Label(f, text=item.get("author") or "?", bg=bg,
                 fg=item.get("authorColor") or U.FG, font=U.FONT_B).pack(side="left")
        if item.get("authorAdmin"):
            U.chip(f, "운영자", U.ACCENT, font=U.FONT_XS, padx=5).pack(
                side="left", padx=(6, 0))
        if item.get("authorTitle"):
            tk.Label(f, text=item["authorTitle"], bg=bg, fg=U.ACCENT_TEXT,
                     font=U.FONT_XS).pack(side="left", padx=(6, 0))
        if time:
            bits = [ago(item.get("agoSec"))]
            if item.get("edited"):
                bits.append("고침")
            tk.Label(f, text="  ·  ".join(b for b in bits if b), bg=bg,
                     fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left", padx=(8, 0))
        return f

    # ================================================================ 목록
    def show_list(self):
        gen = self._clear("list")
        self.post = None
        self.reply_to = None
        self.edit_id = None
        self.write_btn.configure(state="normal")
        bar = tk.Frame(self.body, bg=U.BG)
        bar.pack(fill="x", padx=16, pady=(12, 8))
        self.seg = U.Segmented(bar, KINDS, self.kind, self.pick_kind)
        self.seg.pack(side="left")
        nav = tk.Frame(bar, bg=U.BG)
        nav.pack(side="right")
        self.prev_btn = U.ghost_button(nav, "◀", lambda: self.turn(-1), height=28)
        self.prev_btn.pack(side="left")
        self.page_lbl = tk.Label(nav, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S)
        self.page_lbl.pack(side="left", padx=10)
        self.next_btn = U.ghost_button(nav, "▶", lambda: self.turn(1), height=28)
        self.next_btn.pack(side="left")
        wrap = tk.Frame(self.body, bg=U.BG)
        wrap.pack(fill="both", expand=True, padx=16)
        self.list = self._scroll_area(wrap)
        if self.data and self.data.get("kind") == self.kind \
                and self.data.get("page") == self.page:
            self._fill_list(self.data)          # 보던 것을 먼저 그리고 새로 받는다
        else:
            tk.Label(self.list, text="불러오는 중...", bg=U.BG, fg=U.FG_FAINT,
                     font=U.FONT_S).pack(pady=30)
        self.load_list(gen)

    def pick_kind(self, kind):
        self.kind = kind
        self.page = 1
        self.seg.set(kind)
        self.load_list()

    def turn(self, delta):
        pages = (self.data or {}).get("pages") or 1
        page = max(1, min(pages, self.page + delta))
        if page != self.page:
            self.page = page
            self.load_list()

    def load_list(self, gen=None):
        gen = self._gen if gen is None else gen
        kind, page = self.kind, self.page
        api = self.app.api

        def done(r, err):
            if not self.alive or gen != self._gen or self.view != "list":
                return
            if err:
                return self.say(_err(err), U.DANGER)
            if (kind, page) != (self.kind, self.page):
                return                       # 그사이 다른 것을 골랐다
            self.data = r or {}
            self.page = self.data.get("page") or page
            self._fill_list(self.data)
        run_async(self.root, lambda: api.board(kind, page), done)

    def _fill_list(self, d):
        self.can_notice = bool(d.get("canNotice"))
        self.limits.update(d.get("limits") or {})
        for w in self.list.winfo_children():
            w.destroy()
        pinned, posts = d.get("pinned") or [], d.get("posts") or []
        for p in pinned:
            self._row(p, pinned=True)
        for p in posts:
            self._row(p)
        if not pinned and not posts:
            tk.Label(self.list, text="아직 글이 없습니다. 첫 글을 써 보세요.",
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S).pack(pady=40)
        pages = d.get("pages") or 1
        self.page_lbl.configure(text="%d / %d" % (d.get("page") or 1, pages))
        self.prev_btn.configure(state="normal" if self.page > 1 else "disabled")
        self.next_btn.configure(state="normal" if self.page < pages else "disabled")
        self.count.configure(text="글 %d개" % (d.get("total") or 0))
        try:
            self.cv.yview_moveto(0.0)
        except tk.TclError:
            pass
        self.say("")
        # 공지를 봤다 - 탭과 트레이의 '새 공지' 표시를 끈다
        seen = [p["id"] for p in pinned] + [p["id"] for p in posts
                                             if p.get("kind") == "notice"]
        mark = getattr(self.app, "mark_notice_seen", None)
        if seen and mark:
            try:
                mark(max(seen))
            except Exception:                               # noqa: BLE001
                pass

    def _row(self, p, pinned=False):
        bg = PIN_BG if pinned else ROW_BG
        row = tk.Frame(self.list, bg=bg, highlightthickness=1,
                       highlightbackground=U.ACCENT_SHADOW if pinned else U.LINE,
                       cursor="hand2")
        row.pack(fill="x", pady=(0, 6), padx=(0, 8))
        top = tk.Frame(row, bg=bg)
        top.pack(fill="x", padx=12, pady=(9, 2))
        U.chip(top, p.get("kindKr") or "", KIND_COLOR.get(p.get("kind"), U.BG3),
               font=U.FONT_XS, padx=7).pack(side="left", anchor="n", pady=(2, 0))
        n = int(p.get("comments") or 0)
        if n:
            tk.Label(top, text="댓글 %d" % n, bg=bg, fg=U.ACCENT, font=U.FONT_XS).pack(
                side="right", anchor="n", padx=(8, 0), pady=(2, 0))
        title = tk.Label(top, text=p.get("title") or "", bg=bg, fg=U.FG,
                         font=U.FONT_B, anchor="w", justify="left")
        title.pack(side="left", fill="x", expand=True, padx=(8, 0))
        U.wrap_to_width(title)
        who = self._author(row, p, bg)
        who.pack(anchor="w", padx=12, pady=(0, 9))
        for w in [row, top, title, who] + list(top.winfo_children()) \
                + list(who.winfo_children()):
            w.bind("<Button-1>", lambda _e, i=p["id"]: self.open_post(i))
        return row

    # ================================================================ 글
    def open_post(self, pid, bottom=False):
        gen = self._clear("post")
        self.reply_to = None
        self.write_btn.configure(state="normal")
        tk.Label(self.body, text="불러오는 중...", bg=U.BG, fg=U.FG_FAINT,
                 font=U.FONT_S).pack(pady=30)
        api = self.app.api

        def done(r, err):
            if not self.alive or gen != self._gen:
                return
            if err:
                self.say(_err(err), U.DANGER)
                return self.show_list()
            self._show_post(r, bottom)
        run_async(self.root, lambda: api.board_post(pid), done)

    def _show_post(self, p, bottom=False, keep=None):
        """글과 댓글을 그린다. keep 은 입력칸에 남길 글 (실패했을 때)."""
        self._clear("post")
        self.post = p
        self.reply_to = None                 # 입력칸을 새로 만든다 - 답글 상태도 처음부터
        bar = tk.Frame(self.body, bg=U.BG)
        bar.pack(fill="x", padx=16, pady=(12, 8))
        U.ghost_button(bar, "← 목록", self.show_list, height=28).pack(side="left")
        if p.get("canDelete"):
            U.ghost_button(bar, "삭제", self.delete_post, height=28,
                           fg=U.DANGER).pack(side="right")
        if p.get("canEdit"):
            U.ghost_button(bar, "수정", self.show_edit, height=28).pack(
                side="right", padx=(0, 8))

        # **입력칸을 먼저 아래에 붙인다.** 댓글이 많아도 늘 보인다.
        self._composer()

        wrap = tk.Frame(self.body, bg=U.BG)
        wrap.pack(fill="both", expand=True, padx=16)
        f = self._scroll_area(wrap)
        f.configure(padx=2)
        head = tk.Frame(f, bg=U.BG)
        head.pack(fill="x", padx=(0, 8))
        U.chip(head, p.get("kindKr") or "", KIND_COLOR.get(p.get("kind"), U.BG3),
               font=U.FONT_XS, padx=7).pack(side="left", anchor="n", pady=(4, 0))
        title = tk.Label(head, text=p.get("title") or "", bg=U.BG, fg=U.FG,
                         font=U.FONT_H, anchor="w", justify="left")
        title.pack(side="left", fill="x", expand=True, padx=(8, 0))
        U.wrap_to_width(title)
        self._author(f, p, U.BG).pack(anchor="w", pady=(6, 10))
        tk.Frame(f, bg=U.LINE, height=U.h(1)).pack(fill="x", padx=(0, 8))
        self._body(f, p)
        tk.Frame(f, bg=U.LINE, height=U.h(1)).pack(fill="x", padx=(0, 8))
        U.marker_label(f, "댓글 %d" % int(p.get("comments") or 0),
                       bg=U.BG).pack(anchor="w", pady=(12, 8))
        comments = p.get("commentList") or []
        for c in comments:
            self._comment(f, c)
        if not comments:
            tk.Label(f, text="아직 댓글이 없습니다.", bg=U.BG, fg=U.FG_FAINT,
                     font=U.FONT_S).pack(anchor="w", pady=(0, 12))
        self.count.configure(text="")
        if keep:
            self.input.insert("1.0", keep)
            self._count_input()
        if bottom:
            self.fit.fit_now()
            try:
                self.cv.yview_moveto(1.0)
            except tk.TclError:
                pass

    def _body(self, parent, p):
        """본문. **공지는 주소(http·https)를 누를 수 있다** (1.8.1).

        자유 글과 댓글은 그냥 글자다 - 아무나 쓰는 글의 주소를 누르게 하면
        낚시 링크를 걸 수 있다. 공지는 운영자만 쓴다 (서버가 kind 를 지킨다).
        """
        box = tk.Frame(parent, bg=U.BG)
        box.pack(fill="x", pady=(12, 16), padx=(0, 8))
        text = p.get("body") or ""
        parts = split_links(text) if p.get("kind") == "notice" else [("text", text)]
        for kind, chunk in parts:
            if kind == "link":
                lb = tk.Label(box, text=chunk, bg=U.BG, fg=LINK, font=self._link_font(),
                              anchor="w", justify="left", cursor="hand2")
                lb.bind("<Button-1>", lambda _e, u=chunk: open_url(u))
                lb.bind("<Enter>", lambda _e, w=lb: w.configure(fg=LINK_HOVER))
                lb.bind("<Leave>", lambda _e, w=lb: w.configure(fg=LINK))
            else:
                lb = tk.Label(box, text=chunk, bg=U.BG, fg=U.FG, font=U.FONT,
                              anchor="w", justify="left")
            lb.pack(fill="x")
            U.wrap_to_width(lb)

    def _link_font(self):
        f = getattr(self, "_lf", None)
        if f is None:
            import tkinter.font as tkfont
            f = self._lf = tkfont.Font(family=U.FONT[0], size=U.FONT[1], underline=True)
        return f

    def _comment(self, parent, c, reply=False):
        bg = REPLY_BG if reply else ROW_BG
        box = tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground=U.LINE)
        box.pack(fill="x", pady=(0, 6), padx=(U.h(28) if reply else 0, 8))
        if reply:
            tk.Frame(box, bg=U.ACCENT_SHADOW, width=3).pack(side="left", fill="y")
        inner = tk.Frame(box, bg=bg)
        inner.pack(fill="x", padx=11, pady=8)
        if c.get("deleted"):
            tk.Label(inner, text="삭제된 댓글입니다.", bg=bg, fg=U.FG_FAINT,
                     font=U.FONT_S, anchor="w").pack(fill="x")
        else:
            top = tk.Frame(inner, bg=bg)
            top.pack(fill="x")
            self._author(top, c, bg).pack(side="left")
            if c.get("canDelete"):
                self._link(top, "삭제", lambda cid=c["id"]: self.delete_comment(cid),
                           bg, U.DANGER).pack(side="right")
            self._link(top, "답글", lambda cc=c: self.set_reply(cc), bg,
                       U.INFO).pack(side="right", padx=(0, 10))
            body = tk.Label(inner, text=c.get("body") or "", bg=bg, fg=U.FG,
                            font=U.FONT, anchor="w", justify="left")
            body.pack(fill="x", pady=(5, 0))
            U.wrap_to_width(body)
        for r in c.get("replies") or []:
            self._comment(parent, r, reply=True)

    def _link(self, parent, text, cmd, bg, fg):
        lb = tk.Label(parent, text=text, bg=bg, fg=fg, font=U.FONT_XS, cursor="hand2")
        lb.bind("<Button-1>", lambda _e: cmd())
        return lb

    # ---------------- 댓글 쓰기 ----------------
    def _composer(self):
        box = tk.Frame(self.body, bg=U.BG2, highlightthickness=1,
                       highlightbackground=U.LINE)
        box.pack(side="bottom", fill="x", padx=16, pady=(8, 0))
        self.reply_bar = tk.Frame(box, bg=U.BG2)
        self.reply_lbl = tk.Label(self.reply_bar, text="", bg=U.BG2, fg=U.INFO,
                                  font=U.FONT_XS, anchor="w")
        self.reply_lbl.pack(side="left")
        self._link(self.reply_bar, "취소", lambda: self.set_reply(None), U.BG2,
                   U.FG_DIM).pack(side="left", padx=(10, 0))
        row = tk.Frame(box, bg=U.BG2)
        row.pack(fill="x", padx=10, pady=8)
        self.comp_row = row
        side = tk.Frame(row, bg=U.BG2)
        side.pack(side="right", fill="y", padx=(8, 0))
        self.send_btn = U.PushButton(side, "댓글 등록", self.send_comment, height=32,
                                     font=U.FONT_B)
        self.send_btn.pack()
        self.input_count = tk.Label(side, text="", bg=U.BG2, fg=U.FG_FAINT,
                                    font=U.FONT_XS)
        self.input_count.pack(pady=(4, 0))
        frame = tk.Frame(row, bg=U.INK, highlightthickness=2,
                         highlightbackground=U.LINE, highlightcolor=U.ACCENT)
        frame.pack(side="left", fill="x", expand=True)
        # **width=1.** Text 는 기본이 80자 폭을 달라고 해서, 그대로 두면 좁은
        # 창에서 입력칸이 창보다 넓게 잡힌다. 폭은 fill/expand 가 준다.
        self.input = tk.Text(frame, height=3, width=1, bg=U.INK, fg=U.FG,
                             insertbackground=U.ACCENT,
                             relief="flat", bd=0, font=U.FONT, wrap="word",
                             highlightthickness=0, undo=True)
        self.input.pack(fill="x", padx=8, pady=6)
        self.input.bind("<KeyRelease>", lambda _e: self._count_input())
        for seq in ("<Control-Return>", "<Command-Return>"):
            try:
                self.input.bind(seq, lambda _e: (self.send_comment(), "break")[1])
            except tk.TclError:
                pass
        self._count_input()

    def _count_input(self):
        n = len(self.input.get("1.0", "end-1c").strip())
        lim = self.limits.get("comment", 300)
        self.input_count.configure(text="%d / %d" % (n, lim),
                                   fg=U.DANGER if n > lim else U.FG_FAINT)

    def set_reply(self, c):
        self.reply_to = c
        if c is None:
            self.reply_bar.pack_forget()
            self.send_btn.configure(text="댓글 등록")
            return
        self.reply_lbl.configure(text=natural("%s 님의 댓글에 답글을 답니다"
                                              % (c.get("author") or "?")))
        self.reply_bar.pack(fill="x", padx=10, pady=(6, 0), before=self.comp_row)
        self.send_btn.configure(text="답글 등록")
        try:
            self.input.focus_set()
        except tk.TclError:
            pass

    def send_comment(self):
        if not self.post:
            return
        text = self.input.get("1.0", "end-1c").strip()
        if not text:
            return self.say("댓글을 적어 주세요.", U.DANGER)
        pid = self.post["id"]
        parent = (self.reply_to or {}).get("id") or 0
        gen = self._gen
        api = self.app.api
        self.send_btn.configure(state="disabled")

        def done(r, err):
            if not self.alive or gen != self._gen:
                return
            if err:
                self.send_btn.configure(state="normal")
                return self.say(_err(err), U.DANGER)
            self._show_post(r, bottom=not parent)
            self.say("답글을 달았습니다." if parent else "댓글을 달았습니다.")
        run_async(self.root, lambda: api.board_comment(pid, text, parent), done)

    def delete_comment(self, cid):
        from .ui_box import confirm
        if not confirm(self.win.winfo_toplevel(), "댓글 삭제", "이 댓글을 지울까요?",
                       danger=True, ok_text="삭제"):
            return
        gen = self._gen
        api = self.app.api
        keep = self.input.get("1.0", "end-1c")

        def done(r, err):
            if not self.alive or gen != self._gen:
                return
            if err:
                return self.say(_err(err), U.DANGER)
            self._show_post(r, keep=keep)
            self.say("댓글을 지웠습니다.")
        run_async(self.root, lambda: api.board_comment_delete(cid), done)

    def delete_post(self):
        from .ui_box import confirm
        if not self.post or not confirm(
                self.win.winfo_toplevel(), "글 삭제",
                "이 글을 지울까요? 댓글도 함께 보이지 않게 됩니다.",
                danger=True, ok_text="삭제"):
            return
        pid = self.post["id"]
        gen = self._gen
        api = self.app.api

        def done(_r, err):
            if not self.alive or gen != self._gen:
                return
            if err:
                return self.say(_err(err), U.DANGER)
            self.data = None
            self.show_list()
            self.say("글을 지웠습니다.")
        run_async(self.root, lambda: api.board_delete(pid), done)

    # ================================================================ 쓰기
    def show_write(self):
        self._write_form(None)

    def show_edit(self):
        if self.post:
            self._write_form(self.post)

    def _write_form(self, post):
        self._clear("write")
        self.edit_id = post["id"] if post else None
        self.write_btn.configure(state="disabled")
        self.count.configure(text="")
        back = (lambda: self.open_post(post["id"])) if post else self.show_list
        bar = tk.Frame(self.body, bg=U.BG)
        bar.pack(fill="x", padx=16, pady=(12, 4))
        U.ghost_button(bar, "← 취소", back, height=28).pack(side="left")
        tk.Label(bar, text="글 고치기" if post else "새 글", bg=U.BG, fg=U.FG,
                 font=U.FONT_H).pack(side="left", padx=(12, 0))

        # 등록 줄을 먼저 아래에 붙인다 (내용 칸이 남은 자리를 다 쓴다)
        foot = tk.Frame(self.body, bg=U.BG)
        foot.pack(side="bottom", fill="x", padx=16, pady=(8, 0))
        self.post_btn = U.PushButton(foot, "고치기" if post else "등록", self.submit_post,
                                     height=34, font=U.FONT_B)
        self.post_btn.pack(side="right")
        self.body_count = tk.Label(foot, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS)
        self.body_count.pack(side="right", padx=(0, 12))

        form = tk.Frame(self.body, bg=U.BG)
        form.pack(fill="both", expand=True, padx=16)
        self.kind_var = "free"
        if post:
            self.kind_var = post.get("kind") or "free"
        elif self.kind == "notice" and self.can_notice:
            self.kind_var = "notice"
        elif self.kind == "qna":
            self.kind_var = "qna"           # Q&A 를 보다가 쓰면 Q&A 로
        if not post:
            # 종류는 쓸 때만 고른다 (고칠 때는 못 바꾼다).
            kinds = WRITE_KINDS + ([("notice", "공지")] if self.can_notice else [])
            row = tk.Frame(form, bg=U.BG)
            row.pack(fill="x", pady=(8, 0))
            tk.Label(row, text="종류", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
                     width=5, anchor="w").pack(side="left")
            self.kind_seg = U.Segmented(row, kinds, self.kind_var, self._pick_post_kind)
            self.kind_seg.pack(side="left")
            tk.Label(row, text=("공지는 운영자만 쓸 수 있습니다." if self.can_notice
                                else "질문은 Q&A 에 올려 주세요."),
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left", padx=(10, 0))
        row = tk.Frame(form, bg=U.BG)
        row.pack(fill="x", pady=(10, 0))
        tk.Label(row, text="제목", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
                 width=5, anchor="w").pack(side="left")
        self.title_var = tk.StringVar(value=(post or {}).get("title") or "")
        self.title_count = tk.Label(row, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS)
        self.title_count.pack(side="right", padx=(8, 0))
        self.title_entry = U.entry(row, self.title_var)
        self.title_entry.pack(side="left", fill="x", expand=True)
        self.title_var.trace_add("write", lambda *_a: self._count_post())

        tk.Label(form, text="내용", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
                 anchor="w").pack(fill="x", pady=(12, 4))
        frame = tk.Frame(form, bg=U.INK, highlightthickness=2,
                         highlightbackground=U.LINE, highlightcolor=U.ACCENT)
        frame.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical")
        self.text = tk.Text(frame, bg=U.INK, fg=U.FG, insertbackground=U.ACCENT,
                            relief="flat", bd=0, font=U.FONT, wrap="word",
                            highlightthickness=0, undo=True, height=6, width=1,
                            yscrollcommand=sb.set)
        sb.configure(command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True, padx=8, pady=6)
        if post:
            self.text.insert("1.0", post.get("body") or "")
        self.text.bind("<KeyRelease>", lambda _e: self._count_post())
        self._count_post()
        self.say("")
        try:
            (self.text if post else self.title_entry.winfo_children()[0]).focus_set()
        except Exception:                                   # noqa: BLE001
            pass

    def _pick_post_kind(self, kind):
        self.kind_var = kind
        self.kind_seg.set(kind)

    def _count_post(self):
        try:
            t = len(self.title_var.get().strip())
            b = len(self.text.get("1.0", "end-1c").strip())
        except tk.TclError:
            return
        tl, bl = self.limits.get("title", 40), self.limits.get("body", 2000)
        self.title_count.configure(text="%d / %d" % (t, tl),
                                   fg=U.DANGER if t > tl else U.FG_FAINT)
        self.body_count.configure(text="%d / %d자" % (b, bl),
                                  fg=U.DANGER if b > bl else U.FG_FAINT)

    def submit_post(self):
        title = self.title_var.get().strip()
        body = self.text.get("1.0", "end-1c").strip()
        if not title:
            return self.say("제목을 적어 주세요.", U.DANGER)
        if not body:
            return self.say("내용을 적어 주세요.", U.DANGER)
        gen = self._gen
        api = self.app.api
        pid, kind = self.edit_id, self.kind_var
        self.post_btn.configure(state="disabled")

        def work():
            if pid:
                return api.board_edit(pid, title, body)
            return api.board_write(kind, title, body)

        def done(r, err):
            if not self.alive or gen != self._gen:
                return
            if err:
                self.post_btn.configure(state="normal")
                return self.say(_err(err), U.DANGER)
            self.data = None                 # 목록은 다음에 새로 받는다
            self._show_post(r)
            self.say("글을 고쳤습니다." if pid else "글을 올렸습니다.")
        run_async(self.root, work, done)

    # ---------------- 끝 ----------------
    def close(self):
        self.alive = False
        self._gen += 1
        if getattr(self.app, "board_window", None) is self:
            self.app.board_window = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def focus(self):
        if U.is_embedded(self.win):
            return
        try:
            self.win.deiconify()
            self.win.lift()
        except tk.TclError:
            pass
