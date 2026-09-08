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
"""
import tkinter as tk

from common.korean import natural

from . import platform_os as PLAT
from . import ui_common as U

W, H = 420, 400


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
        U.style_window(self.win, "기술 배우기", W, H)
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

        box = tk.Frame(f, bg=U.BG)
        box.pack(fill="both", expand=True)
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

    # ---------------- 그리기 ----------------
    def _kr(self, mv):
        if self.dex is not None:
            try:
                return self.dex.move_name(mv)
            except Exception:                              # noqa: BLE001
                pass
        return mv

    def _row(self, parent, mv, is_new):
        f = tk.Frame(parent, bg=U.BG2, highlightthickness=1,
                     highlightbackground=U.LINE)
        f.pack(fill="x", pady=2)
        inner = tk.Frame(f, bg=U.BG2)
        inner.pack(fill="x", padx=10, pady=7)
        name = tk.Label(inner, text=self._kr(mv), bg=U.BG2, fg=U.FG,
                        font=U.FONT_B, anchor="w")
        name.pack(side="left")
        tag = tk.Label(inner, text="새 기술" if is_new else "",
                       bg=U.BG2, fg=U.ACCENT, font=U.FONT_XS, anchor="e")
        tag.pack(side="right")
        self.rows[mv] = (f, inner, name, tag, is_new)
        for w in (f, inner, name, tag):
            w.bind("<Button-1>", lambda _e, m=mv: self._pick(m))
        return f

    def _pick(self, mv):
        self.picked = mv
        for m, (f, inner, name, tag, is_new) in self.rows.items():
            on = (m == mv)
            bg = U.ACCENT_SOFT if on else U.BG2
            f.configure(highlightbackground=U.ACCENT if on else U.LINE)
            for w in (f, inner, name, tag):
                w.configure(bg=bg)
            name.configure(fg=U.ACCENT_TEXT if on else U.FG)
            tag.configure(fg=U.ACCENT)

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
        self.parent.wait_window(self.win)
        return self.result


def ask_forget(parent, mon_name, new_move, known, dex=None):
    """물어보고 답을 돌려준다.

      "TACKLE" 등  그 기술을 잊고 새 기술을 배운다
      ""           새 기술을 안 배운다
      None         창을 그냥 닫았다. 아무것도 하지 않는다.
    """
    return ForgetAsk(parent, mon_name, new_move, known, dex).show()
