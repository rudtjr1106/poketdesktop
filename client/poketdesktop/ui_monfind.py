# -*- coding: utf-8 -*-
"""'누구에게' 목록 위의 찾기·줄 세우기 한 줄 (1.13.1, 가방·기술머신이 같이 쓴다).

가방에서 도구를 쓸 포켓몬, 기술머신을 가르칠 포켓몬을 고르는 오른쪽 목록은 받은 순서
그대로였다. 수백 마리가 되면 끝까지 굴려야 했다 (건의). 포켓몬 관리 창과 같은 규칙으로
찾고(box_filter.matches - 별명·종 이름·도감 번호) 줄 세운다(box_filter.sort_by).

    bar = FindBar(parent, U.BG2, on_change)
    bar.frame.pack(fill="x")
    shown = bar.view(mons, dex)        # 거르고 줄 세운 목록 (받은 목록은 그대로)

**찾는 말과 순서는 창에 남는다.** 다른 도구·기술머신을 골라도 그대로다 - 고를 때마다
다시 치게 하면 안 된다.

찾는 말은 StringVar 의 trace 로 듣는다. KeyRelease 로 들으면 한글 자판에서 조합 중인
글자를 놓친다 (도감 찾기에서 겪었다, 제보 #194).
"""
import tkinter as tk

from . import box_filter
from . import ui_common as U


class FindBar(object):

    def __init__(self, parent, bg, on_change, stacked=False):
        """stacked = [기본|가나다순|레벨순] 을 찾기 줄 아래 오른쪽 줄로 내린다. 가방·기술머신처럼 넓은 칸은
        한 줄이면 되지만, 탐험 탭의 '누구를' 단은 좁아서(가장 좁게 줄이면 340px 남짓) 한 줄에 안 든다."""
        self.on_change = on_change
        self.sort = ""
        self.frame = tk.Frame(parent, bg=bg)
        top = tk.Frame(self.frame, bg=bg) if stacked else self.frame
        if stacked:
            top.pack(fill="x")
        tk.Label(top, text="포켓몬 찾기", bg=bg, fg=U.FG_DIM,
                 font=U.FONT_XS).pack(side="left")
        self.q = tk.StringVar()
        self.box = U.entry(top, self.q, width=12)
        self.box.pack(side="left", padx=(8, 0))
        # 찾는 말이 있을 때만 '몇 마리' 를 적는다.
        self.count = tk.Label(top, text="", bg=bg, fg=U.FG_FAINT,
                              font=U.FONT_XS)
        self.count.pack(side="left", padx=(10, 0))
        row = tk.Frame(self.frame, bg=bg) if stacked else self.frame
        if stacked:
            row.pack(fill="x", pady=(6, 0))
        self.seg = U.Segmented(row, box_filter.PICK_SORTS, "", self.pick_sort)
        self.seg.pack(side="right")
        self.q.trace_add("write", lambda *_a: self._changed())

    def query(self):
        return self.q.get()

    def searching(self):
        return bool(box_filter._norm(self.q.get()))

    def pick_sort(self, key):
        self.sort = key or ""
        self.seg.set(self.sort)
        self._changed()

    def _changed(self):
        if self.on_change:
            self.on_change()

    def view(self, mons, dex):
        """찾는 말로 거르고 고른 순서로 줄 세운 새 목록. '몇 마리' 도 여기서 고친다."""
        out = box_filter.pick_view(mons or [], dex, self.q.get(), self.sort)
        try:
            self.count.configure(text=("%d마리" % len(out)) if self.searching() else "")
        except tk.TclError:
            pass
        return out

    def empty_note(self):
        """찾았는데 하나도 없을 때 목록 자리에 적을 말."""
        return "'%s' 에 맞는 포켓몬이 없다." % self.q.get().strip()
