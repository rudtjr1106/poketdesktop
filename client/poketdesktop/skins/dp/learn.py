"""DP 테마의 기술 배우기 창 (그리고 떠올리기 창이 같이 쓰는 기술 판).

DP 요약 화면의 기술 단추처럼 기술 하나를 판 하나로 그린다 (v2: 테 한 겹, 위력 줄은 이름 줄에 붙여 낮게):

    ┌ (타입 빛깔 테) ────────────────────────────────────┐
    │ [전기] 10만볼트 특수  위력 90 · 명중 100 · PP 15 새 기술 │
    │ 강한 전격을 상대에게 날려서 공격한다. ...           │
    └─────────────────────────────────────────────────────┘

고른 판은 빨간 테 · 크림빛 바탕 (DP 의 커서 빛깔). 굴림 막대도 DP 것.
고르기 · 결정 · 창 크기 맞추기는 기본 창(ui_learn.ForgetAsk) 그대로다 - 판(_plate)과 고른 표시(_paint_pick)만 바꾼다.
"""
import tkinter as tk
from tkinter import ttk

from common import movetext as MT

from ... import ui_common as U
from ... import ui_learn as L
from . import CUR, INK, INK2, SEL, WHITE, font, tone
from . import kit as K
from . import widgets as W
from .battle import mix


def type_badge(parent, text, col):
    """타입 표 - 타입 빛깔 둥근 판에 흰 글씨. 바탕은 부모 빛깔."""
    s = U.h
    spec = font(9)
    w = K.tkfont_of(parent, spec).measure(text) + s(14)
    h = K.tkfont_of(parent, spec).metrics("linespace") + s(4)
    cv = tk.Canvas(parent, width=w, height=h, bg=parent.cget("bg"), highlightthickness=0, bd=0)
    K.rrect(cv, 0, 0, w, h, s(5), fill=mix(col, "#000000", 0.2))
    cv.create_text(w // 2, h // 2, text=text, fill="#ffffff", font=spec, anchor="center")
    return cv


class MoveRows(object):
    """기술 판 - 배우기 · 떠올리기 창이 같이 쓴다."""

    def _wheel(self):
        """기본 창의 굴림 막대를 DP 것으로 바꿔 끼우고 휠을 건다."""
        holder = self.canvas.master
        for ch in holder.winfo_children():
            if isinstance(ch, (ttk.Scrollbar, tk.Scrollbar)):
                ch.destroy()
        sb = K.Scroll(holder, self.canvas, holder.cget("bg"))
        sb.pack(side="right", fill="y", before=self.canvas)
        self.canvas.configure(yscrollcommand=sb.set)
        L.ForgetAsk._wheel(self)

    def _plate(self, parent, mv, title, tag_text, tag_color):
        s = U.h
        md = self._md(mv)
        col = U.TYPE_COLOR.get(md.get("type"), "#a0a0a8")
        line = mix(col, "#000000", 0.3)
        f = tk.Frame(parent, bg=WHITE, highlightthickness=s(2), highlightbackground=line, highlightcolor=line, bd=0)
        f.pack(fill="x", pady=s(2))
        inner = tk.Frame(f, bg=WHITE)
        inner.pack(fill="x", padx=s(8), pady=s(5))
        head = tk.Frame(inner, bg=WHITE)
        head.pack(fill="x")
        badge = type_badge(head, self._type_kr(md) or "?", col)
        badge.pack(side="left")
        name = tk.Label(head, text=title, bg=WHITE, fg=INK, font=font(12), anchor="w")
        name.pack(side="left", padx=(s(8), 0))
        cat_text = MT.cat_name(md)
        cat = tk.Label(head, text=cat_text, bg=WHITE, fg=W.fg(MT.cat_color(md)), font=font(9), anchor="w")
        cat.pack(side="left", padx=(s(8), 0))
        tag = tk.Label(head, text=tag_text, bg=WHITE, fg=tone(tag_color), font=font(9), anchor="e")
        tag.pack(side="right")
        stat_text = MT.SEP.join(b for b in MT.stat_bits(md, with_cat=False) if b)
        # 위력 줄은 이름 줄에 붙인다 (자리가 되면) - 모자라면 다음 줄로 (글꼴은 줄이지 않는다)
        used = sum(K.tkfont_of(parent, sp).measure(t) for sp, t in
                   ((font(12), title), (font(9), cat_text), (font(9), tag_text), (font(9), stat_text)))
        used += s(110) + K.tkfont_of(parent, font(9)).measure(self._type_kr(md) or "?")
        inline = used <= s(L.W) - 2 * s(18) - 2 * s(8) - s(64)
        stat = tk.Label(head if inline else inner, text=stat_text, bg=WHITE, fg=INK2, font=font(9), anchor="w")
        if inline:
            stat.pack(side="left", padx=(s(10), 0))
        else:
            stat.pack(fill="x", pady=(s(3), 0))
        desc = tk.Label(inner, text=MT.desc(md), bg=WHITE, fg=INK2, font=font(9), anchor="w", justify="left")
        desc.pack(fill="x", pady=(s(3), 0))
        U.wrap_to_width(desc)
        parts = (f, inner, head, badge, name, cat, tag, stat, desc)   # (타입 표는 바탕만 따라간다 - 판 빛깔은 그대로)
        self.rows[mv] = (f, parts, name, cat, md)
        if not hasattr(self, "_lines"):
            self._lines = {}
        self._lines[mv] = line
        for w in parts:
            w.bind("<Button-1>", lambda _e, m=mv: self._pick(m))
            w.configure(cursor="hand2")
        return f

    def _paint_pick(self, mv):
        for m, (f, parts, name, _cat, _md) in self.rows.items():
            on = m == mv
            f.configure(highlightbackground=CUR if on else self._lines.get(m, "#8a96a8"))
            for w in parts:
                w.configure(bg=SEL if on else WHITE)
            name.configure(fg="#a02020" if on else INK)


class ForgetAsk(MoveRows, L.ForgetAsk):
    pass
