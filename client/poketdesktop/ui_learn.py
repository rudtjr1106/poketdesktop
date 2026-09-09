# -*- coding: utf-8 -*-
"""무엇을 잊을지 고르는 창.

기술은 네 개까지다. 다섯 번째를 배우려면 하나를 버려야 한다.

**전에는 서버가 가장 오래된 것부터 말없이 밀어냈다.** 아끼던 기술이
사라진 것을 한참 뒤에야 알게 되는 게 문제였다. 이제는 서버가 밀어내지
않고 기다리는 목록에 적어 두고(pokemon.pending), 이 창이 물어본다.

두 곳에서 쓴다.
  · 기술머신을 썼는데 기술이 네 개일 때
  · 레벨업으로 배울 기술이 생겼는데 자리가 없을 때

레벨업 쪽은 **배틀이 끝난 뒤에** 뜬다. 싸우는 도중에 창이 튀어나오면
연출이 끊기고, 무엇보다 자동으로 도는 배틀 한가운데라 사용자가 화면을
보고 있지 않을 수 있다.

## 다섯 개를 한눈에

전에는 이름만 다섯 줄 늘어놨다. 그런데 이름만 보고는 무엇을 버릴지
고를 수가 없다 - '리프블레이드' 와 '기가드레인' 중 무엇을 버릴지는
위력과 분류(물리/특수)를 알아야 정해지고, 처음 보는 기술이면 무엇을
하는 기술인지조차 모른다.

그래서 **다섯 개 모두 설명까지 펼쳐 둔다.** 눌러야 설명이 나오게 하면
비교하려고 다섯 번을 눌러야 한다. 고르는 일 자체가 비교라서, 비교할
것을 감춰 두면 안 된다.

## 높이

내용이 길어지면 창을 키운다. 글자를 줄이지 않는다. 화면보다 커지면
그때만 굴린다 - 설명 길이는 기술마다 다르고(15~68자), 몇 줄로 접힐지는
글꼴에 달렸다(맥과 윈도우가 다르다). 숫자를 박아 두면 어느 한쪽이 잘린다.
"""
import tkinter as tk

from common import movetext as MT
from common.korean import natural

from . import platform_os as PLAT
from . import ui_common as U

W = 460
MIN_H = U.h(300)
# 화면 아래위로 이만큼은 남긴다. 창이 화면을 꽉 채우면 옮길 수가 없다.
SCREEN_PAD = U.h(120)


class ForgetAsk(object):
    """지금 아는 기술 넷 + 새 기술을 늘어놓고 하나를 고르게 한다.

    새 기술도 같은 목록에 둔다. '새 기술을 안 배운다' 가 곧 '새 기술을
    잊는다' 라서, 다섯 중 하나를 버린다고 보는 편이 헷갈리지 않는다.
    본가도 그렇게 물어본다.
    """

    def __init__(self, parent, mon_name, new_move, known, dex=None):
        self.result = None          # 잊을 기술 (내부 이름) 또는 "" = 안 배움
        self.new = new_move
        self.known = list(known)
        self.dex = dex
        self.picked = None
        self.rows = {}

        self.win = tk.Toplevel(parent)
        U.style_window(self.win, "기술 배우기", W, MIN_H)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        self.win.resizable(False, False)
        self.parent = parent

        bar = tk.Frame(self.win, bg=U.BG2, height=U.h(34))
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=U.ACCENT, width=3, height=U.h(13)).pack(side="left",
                                                            padx=(12, 8))
        tk.Label(bar, text="기술 배우기", bg=U.BG2, fg=U.FG,
                 font=U.FONT_B).pack(side="left")
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

        f = tk.Frame(self.win, bg=U.BG)
        f.pack(fill="both", expand=True, padx=18, pady=(14, 14))

        tk.Label(f, text=natural("%s이(가) %s을(를) 배우려 합니다."
                                 % (mon_name, self._kr(new_move))),
                 bg=U.BG, fg=U.FG, font=U.FONT_B, wraplength=W - 60,
                 justify="left").pack(anchor="w")
        tk.Label(f, text="기술은 네 개까지입니다. 버릴 것을 고르세요.",
                 bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
                 wraplength=W - 60, justify="left").pack(anchor="w",
                                                         pady=(4, 12))

        # 굴러가는 영역에 담는다. 다섯 개가 화면에 다 들어가면 스크롤바는
        # 움직이지 않는다(_scroller 가 그렇게 만든다).
        from .ui_bag import _scroller
        self.canvas, self.box = _scroller(f, U.BG)
        box = self.box
        for mv in self.known:
            self._row(box, mv, is_new=False)
        tk.Frame(box, bg=U.LINE, height=U.h(1)).pack(fill="x", pady=6)
        self._row(box, new_move, is_new=True)

        row = tk.Frame(f, bg=U.BG)
        row.pack(fill="x", pady=(14, 0))
        self.ok_btn = U.PushButton(row, "결정", self._ok, height=34,
                                   font=U.FONT_B)
        self.ok_btn.pack(side="right")

        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        self._fit()

    # ---------------- 그리기 ----------------
    def _kr(self, mv):
        if self.dex is not None:
            try:
                return self.dex.move_name(mv)
            except Exception:                              # noqa: BLE001
                pass
        return mv

    def _md(self, mv):
        """도감에 실린 그 기술. 도감이 없으면 빈 것."""
        if self.dex is not None:
            try:
                return self.dex.move(mv) or {}
            except Exception:                              # noqa: BLE001
                pass
        return {}

    def _type_kr(self, md):
        t = md.get("type")
        if not t:
            return ""
        if self.dex is not None:
            try:
                return self.dex.type_name(t)
            except Exception:                              # noqa: BLE001
                pass
        return str(t)

    def _row(self, parent, mv, is_new):
        md = self._md(mv)
        f = tk.Frame(parent, bg=U.BG2, highlightthickness=1,
                     highlightbackground=U.LINE)
        f.pack(fill="x", pady=2)
        inner = tk.Frame(f, bg=U.BG2)
        inner.pack(fill="x", padx=10, pady=7)

        head = tk.Frame(inner, bg=U.BG2)
        head.pack(fill="x")
        name = tk.Label(head, text=self._kr(mv), bg=U.BG2, fg=U.FG,
                        font=U.FONT_B, anchor="w")
        name.pack(side="left")
        # 분류는 색을 따로 준다. 다섯 줄을 훑을 때 글자만으로는 안 띈다.
        cat = tk.Label(head, text=MT.cat_name(md), bg=U.BG2,
                       fg=MT.cat_color(md), font=U.FONT_XS, anchor="w")
        cat.pack(side="left", padx=(8, 0))
        tag = tk.Label(head, text="새 기술" if is_new else "",
                       bg=U.BG2, fg=U.ACCENT, font=U.FONT_XS, anchor="e")
        tag.pack(side="right")

        bits = [self._type_kr(md)] + MT.stat_bits(md, with_cat=False)
        stat = tk.Label(inner, text=MT.SEP.join(b for b in bits if b),
                        bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w")
        stat.pack(fill="x", pady=(2, 0))

        desc = tk.Label(inner, text=MT.desc(md), bg=U.BG2, fg=U.FG_DIM,
                        font=U.FONT_XS, anchor="w", justify="left")
        desc.pack(fill="x", pady=(3, 0))
        U.wrap_to_width(desc)

        parts = (f, inner, head, name, cat, tag, stat, desc)
        self.rows[mv] = (f, parts, name, cat, md)
        for w in parts:
            w.bind("<Button-1>", lambda _e, m=mv: self._pick(m))
        return f

    def _pick(self, mv):
        self.picked = mv
        for m, (f, parts, name, cat, md) in self.rows.items():
            on = (m == mv)
            bg = U.ACCENT_SOFT if on else U.BG2
            f.configure(highlightbackground=U.ACCENT if on else U.LINE)
            for w in parts:
                w.configure(bg=bg)
            name.configure(fg=U.ACCENT_TEXT if on else U.FG)
            cat.configure(fg=MT.cat_color(md))

    def _fit(self):
        """다 담고 나서 창을 내용에 맞춘다.

        줄 수만 세서 높이를 잡으면 모자란다. 설명이 몇 줄로 접힐지는
        글꼴에 달렸고, 글꼴은 OS 마다 다르다. 화면보다 커질 때만
        거기서 자르고, 그때는 굴려서 본다.

        **창의 reqheight 를 보면 안 된다.** 줄들이 굴러가는 칸(Canvas)
        안에 있어서, 창은 그 안에 무엇이 얼마나 들었는지 모른다. 캔버스가
        원하는 크기는 자기 설정값이지 내용이 아니다. 그래서 안쪽 칸이
        원하는 높이와 지금 보이는 높이의 차이만큼만 창을 키운다.

        창이 아직 화면에 안 붙었으면 winfo_height 가 1 이라 이 계산이
        안 된다. 그래서 show() 에서 한 번 더 부른다.
        """
        try:
            self.win.update_idletasks()
            cur = self.win.winfo_height()
            if cur <= 1:
                cur = self.win.winfo_reqheight()
            seen = self.canvas.winfo_height()
            grow = self.box.winfo_reqheight() - seen if seen > 1 else 0
            cap = self.win.winfo_screenheight() - SCREEN_PAD
            h = max(MIN_H, min(cur + max(0, grow), cap))
            if h != self.win.winfo_height():
                self.win.geometry("%dx%d" % (self.win.winfo_width() or W, h))
        except Exception:                                  # noqa: BLE001
            pass

    # ---------------- 답 ----------------
    def _ok(self):
        if self.picked is None:
            return                    # 아직 아무것도 안 골랐다
        # 새 기술을 골랐으면 '안 배운다' 는 뜻이다.
        self.result = "" if self.picked == self.new else self.picked
        self.win.destroy()

    def _cancel(self):
        # 창을 그냥 닫으면 아무것도 안 한다. 기다리는 목록에 그대로 남아서
        # 다음에 다시 물어본다 - 실수로 닫았다고 기술이 사라지면 안 된다.
        self.result = None
        self.win.destroy()

    def show(self):
        PLAT.own_dialog(self.win, self.parent)
        self.win.lift()
        try:
            self.win.focus_force()
        except Exception:                                  # noqa: BLE001
            pass
        PLAT.surface(self.win)
        # 이제야 창이 화면에 붙어서 실제 크기를 잴 수 있다.
        self._fit()
        self.parent.wait_window(self.win)
        return self.result


def ask_forget(parent, mon_name, new_move, known, dex=None):
    """물어보고 답을 돌려준다.

      "TACKLE" 등  그 기술을 잊고 새 기술을 배운다
      ""           새 기술을 안 배운다
      None         창을 그냥 닫았다. 아무것도 하지 않는다.
    """
    return ForgetAsk(parent, mon_name, new_move, known, dex).show()
