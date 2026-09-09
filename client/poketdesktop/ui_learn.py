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
#
# **넉넉히 잡으면 안 된다.** 120 을 남겼더니 1366x768 화면에서 창이
# 648 로 잘려, 다섯 줄 중 넷만 보이고 나머지는 굴려야 나왔다(CI 의
# 윈도우·맥 러너가 그 크기라 검사에서 걸렸다). 가장 긴 설명 다섯 개를
# 다 펼치면 창이 710 쯤 되므로, 768 화면에서도 들어가려면 40 이 맞다.
# 그보다 작은 화면에서는 굴려서 본다 - 그때는 어쩔 수 없다.
SCREEN_PAD = U.h(40)


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
        # 크기 고정은 _fit 이 끝에서 건다. 여기서 미리 걸면 안 된다 -
        # 창이 화면에 붙은 뒤에는 창 관리자가 크기 바꾸기를 거절해서,
        # 처음 잡아 둔 360 에 그대로 묶인다. CI 의 맥 러너가 그랬다
        # (내 맥은 받아 줘서 안 드러났다).
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

        # **단추를 먼저 담는다.** pack 은 먼저 담은 쪽에 자리를 먼저 준다.
        # 굴러가는 칸을 먼저 담으면 그것이 자리를 다 먹고 단추를 밀어낸다 -
        # 작은 화면에서 '결정' 글씨가 23px 이 필요한데 5px 만 받았다.
        # 단추가 안 보이면 창을 닫는 것 말고 할 수 있는 일이 없어진다.
        row = tk.Frame(f, bg=U.BG)
        row.pack(side="bottom", fill="x", pady=(14, 0))
        self.ok_btn = U.PushButton(row, "결정", self._ok, height=34,
                                   font=U.FONT_B)
        self.ok_btn.pack(side="right")

        # 굴러가는 영역에 담는다. 다섯 개가 화면에 다 들어가면 스크롤바는
        # 움직이지 않는다(_scroller 가 그렇게 만든다).
        from .ui_bag import _scroller
        self.canvas, self.box = _scroller(f, U.BG)
        box = self.box
        for mv in self.known:
            self._row(box, mv, is_new=False)
        tk.Frame(box, bg=U.LINE, height=U.h(1)).pack(fill="x", pady=6)
        self._row(box, new_move, is_new=True)

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

    def _resize(self, h):
        """창 높이를 h 로 못 박는다.

        **resizable(False, False) 로 잠그면 안 된다.** 그렇게 잠그면 창이
        자기 '요청 높이' 로 되돌아간다. 그런데 요청 높이는 실제로 필요한
        높이보다 몇 px 작게 나올 때가 있어서(창 테두리·스크롤바를 어떻게
        세는지가 OS 마다 다르다), 애써 키운 창이 도로 줄어든다. CI 의 맥
        러너에서 709 로 키워도 649 로 돌아가 마지막 줄이 안 보였다.

        min 과 max 를 같은 값으로 두면 그 크기로 못 박히고, 크기를 바꿀
        수 없다는 점도 그대로다.
        """
        self.win.minsize(W, h)
        self.win.maxsize(W, h)
        self.win.geometry("%dx%d" % (W, h))
        # **update_idletasks 로는 모자란다.** 창 크기는 창 관리자가
        # 나중에 알려 준다(ConfigureNotify). idle 만 돌리면 그 소식을
        # 못 받아서, 바로 재면 옛 크기가 나온다.
        try:
            self.win.update()
        except Exception:                                  # noqa: BLE001
            self.win.update_idletasks()

    def _fit(self):
        """다 담고 나서 창을 내용에 맞춘다.

        줄 수만 세서 높이를 잡으면 모자란다. 설명이 몇 줄로 접힐지는
        글꼴에 달렸고, 글꼴은 OS 마다 다르다. 화면보다 커질 때만
        거기서 자르고, 그때는 굴려서 본다.

        ## 두 단계로 맞춘다

        **먼저 요청 크기로 어림잡는다.** 줄들이 든 칸이 원하는 높이를
        캔버스에 요청 높이로 물려 주면 창의 요청 높이에 내용이 포함된다.
        요청 크기는 그리기 전에도 맞는 값이라, 창이 아직 화면에 안 붙은
        상태에서도 쓸 수 있다.

        **그다음 그려진 크기로 다듬는다.** 요청 크기만으로는 몇 px 이
        어긋난다 - 창 테두리와 스크롤바가 어떻게 잡히는지는 OS 마다
        다르다. 맥 러너에서 8px 이 모자라 마지막 줄이 잘렸다. 실제로
        보이는 높이를 보고 모자란 만큼 더 키운다. 두어 번이면 맞는다.
        """
        try:
            self.win.update_idletasks()
            need = self.box.winfo_reqheight()
            self.canvas.configure(height=max(1, need))
            self.win.update_idletasks()

            cap = self.win.winfo_screenheight() - SCREEN_PAD
            want = self.win.winfo_reqheight()
            if want > cap:
                # **넘친 만큼 캔버스에서 덜어낸다.** 안 그러면 굴러가는
                # 칸이 자리를 다 먹고 아래 '결정' 단추를 밀어낸다 -
                # 600px 화면에서 단추 글씨가 5px 로 눌려 있었다.
                self.canvas.configure(height=max(U.h(80), need - (want - cap)))
                self.win.update_idletasks()
                want = self.win.winfo_reqheight()
            h = max(MIN_H, min(want, cap))
            self._resize(h)

            for _ in range(5):
                seen = self.canvas.winfo_height()
                now = self.win.winfo_height()
                if seen <= 1 or now <= 1:
                    break                     # 아직 안 그려졌다. 어림잡은 값으로 둔다
                short = need - seen
                if short <= 0:
                    break                     # 다 보인다
                nxt = min(now + short, cap)
                if nxt <= now:
                    break                     # 화면이 작다. 굴려서 본다
                self._resize(nxt)
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
