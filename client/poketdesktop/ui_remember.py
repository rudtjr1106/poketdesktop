# -*- coding: utf-8 -*-
"""기술 떠올리기 창.

레벨업으로 배울 수 있었던 기술(지금 레벨 이하)을 늘어놓고 하나를 고르게
한다. 한 번에 5,000원이고, 레벨업 때 자리가 없어 못 배운 기술은 공짜다.
무엇을 떠올릴 수 있는지와 값은 **서버가 정한다** - 여기서는 받은 목록을
보여주고 고른 것을 돌려줄 뿐이다.

## 무엇을 버릴지 묻는 창(ui_learn.ForgetAsk)과 한 몸

창 크기 맞추기(_fit)는 OS 마다 몇 px 씩 어긋나서 여러 번 고친 코드다.
같은 것을 또 만들면 한쪽만 고쳐지는 날이 온다. 그래서 그 창을 물려받고
내용(줄)과 답만 바꾼다.

## 고르기 전에 누르면 까닭을 적는다

말없이 무시하면 고장으로 읽힌다. 돈이 모자랄 때도 창을 닫지 않고
얼마가 모자란지 적는다.
"""
import tkinter as tk

from common.korean import natural

from . import skins
from . import ui_common as U
from .ui_learn import MIN_H, SCREEN_PAD, W, ForgetAsk

# 창 높이 상한. **화면을 꽉 채우지 않는다.** 떠올릴 기술은 스무 개가 넘기도
# 해서 '무엇을 버릴까' 창처럼 화면 높이까지 키우면 창이 화면을 다 덮고,
# 맥에서는 아래 '떠올리기' 단추가 Dock 뒤로 들어갔다. 줄 네 개쯤 보이는
# 높이로 두고 나머지는 굴려서 본다(휠이 먹는다). 600 으로 잡았더니 900px
# 화면의 3/4 라 여전히 컸다. 화면이 작으면 화면의 65% 까지만 쓴다.
MAX_H = U.h(520)
SCREEN_SHARE = 0.65


def won(n):
    """12345 -> '12,345'."""
    try:
        return "{:,}".format(int(n))
    except (TypeError, ValueError):
        return str(n)


def tag_text(entry):
    """줄 오른쪽 꼬리표. 언제 배우는 기술인지와 공짜인지."""
    lv = entry.get("level")
    if entry.get("form"):
        when = entry["form"]          # 그 모습이 될 때 배우는 기술 (워시로토무 - 하이드로펌프, 게시판 #279)
    elif lv is None:
        when = "배우려던 기술"
    elif int(lv) == 0:
        when = "진화"
    else:
        when = "Lv.%d" % int(lv)
    return "%s · 무료" % when if entry.get("free") else when


@skins.skinnable
class RememberAsk(ForgetAsk):
    """떠올릴 기술 하나를 고르게 한다. result 는 기술 내부 이름, 안 고르면 None."""

    def __init__(self, parent, mon_name, entries, cost, money, dex=None):
        self.result = None
        self.new = None
        self.known = []
        self.dex = dex
        self.picked = None
        self.rows = {}
        self.parent = parent
        self.entries = dict((e["move"], e) for e in entries)
        self.cost = int(cost or 0)
        self.money = int(money or 0)

        self.win = tk.Toplevel(parent)
        U.style_window(self.win, "기술 떠올리기", W, MIN_H)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)

        U.dialog_bar(self.win, "기술 떠올리기")

        f = tk.Frame(self.win, bg=U.BG)
        f.pack(fill="both", expand=True, padx=18, pady=(14, 14))

        tk.Label(f, text=natural("%s이(가) 떠올릴 수 있는 기술" % mon_name),
                 bg=U.BG, fg=U.FG, font=U.FONT_B, wraplength=W - 60,
                 justify="left").pack(anchor="w")
        self.wallet = tk.Label(
            f, text="한 번에 %s원  ·  가진 돈 %s원" % (won(self.cost), won(self.money)),
            bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, wraplength=W - 60,
            justify="left")
        self.wallet.pack(anchor="w", pady=(4, 0))
        if any(e.get("free") for e in entries):
            note = "레벨업 때 자리가 없어 못 배운 기술은 무료입니다."
            if any(e.get("form") for e in entries):
                note = "지금 모습의 기술과 레벨업 때 자리가 없어 못 배운 기술은 무료입니다."
            tk.Label(f, text=note,
                     bg=U.BG, fg=U.GOOD, font=U.FONT_XS, wraplength=W - 60,
                     justify="left").pack(anchor="w", pady=(2, 0))
        tk.Frame(f, bg=U.BG, height=U.h(10)).pack(fill="x")

        # 단추를 먼저 담는다 (ForgetAsk 와 같은 까닭 - 굴러가는 칸이 자리를
        # 다 먹고 단추를 밀어내지 않게).
        row = tk.Frame(f, bg=U.BG)
        row.pack(side="bottom", fill="x", pady=(14, 0))
        if entries:
            self.ok_btn = U.PushButton(row, "떠올리기", self._ok, height=34,
                                       font=U.FONT_B)
        else:
            self.ok_btn = U.ghost_button(row, "닫기", self._cancel, height=34)
        self.ok_btn.pack(side="right")
        self._hint_label(row)

        from .ui_bag import _scroller
        self.canvas, self.box = _scroller(f, U.BG)
        self._wheel()
        if entries:
            for e in entries:
                self._entry_row(self.box, e)
        else:
            tk.Label(self.box,
                     text="떠올릴 수 있는 기술이 없습니다.\n"
                          "레벨이 오르면 떠올릴 수 있는 기술이 늘어납니다.",
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S,
                     justify="left").pack(anchor="w", pady=8)

        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        self._fit()

    def _cap(self):
        sh = self.win.winfo_screenheight()
        return max(MIN_H, min(sh - SCREEN_PAD, MAX_H, int(sh * SCREEN_SHARE)))

    # ---------------- 그리기 ----------------
    def _entry_row(self, parent, entry):
        mv = entry["move"]
        return self._plate(parent, mv, entry.get("kr") or self._kr(mv), tag_text(entry),
                           U.GOOD if entry.get("free") else U.FG_FAINT)

    def _short(self, entry):
        """이 기술을 떠올리는 데 모자란 돈. 공짜거나 넉넉하면 0."""
        if entry.get("free"):
            return 0
        return max(0, self.cost - self.money)

    # ---------------- 답 ----------------
    def _pick(self, mv):
        ForgetAsk._pick(self, mv)
        e = self.entries[mv]
        short = self._short(e)
        if short:
            self._hint("골드가 %s원 모자랍니다." % won(short), U.DANGER)
        elif e.get("free"):
            self._hint("무료로 떠올립니다.", U.GOOD)
        else:
            self._hint("%s원을 냅니다." % won(self.cost))

    def _ok(self):
        if self.picked is None:
            return self._hint("떠올릴 기술을 눌러서 고르세요.", U.ACCENT)
        short = self._short(self.entries[self.picked])
        if short:
            return self._hint("골드가 %s원 모자랍니다." % won(short), U.DANGER)
        self.result = self.picked
        self.win.destroy()


def ask_remember(parent, mon_name, entries, cost, money, dex=None):
    """물어보고 답을 돌려준다.

      "TACKLE" 등  그 기술을 떠올린다
      None         창을 닫았다. 아무것도 하지 않는다.
    """
    return RememberAsk(parent, mon_name, entries, cost, money, dex).show()
