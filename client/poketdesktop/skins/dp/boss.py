# -*- coding: utf-8 -*-
"""DP 테마의 악당 출현 창 - 갤럭시단을 만났을 때처럼.

    머리     검은 판에 빨간 테 - 조직 이름(흰 글씨)과 나타난 곳 · 남은 시간
    간부     한 사람에 판 하나: 도트 칸(둥근 네모) · 이름 · 직함 · 상태표(이김 초록 · 도전 빨강 · 잠김 회색)
             잠긴 간부는 판이 회색이다 (판마다 테는 한 겹)
    전설     다 이기기 전에는 검은 판에 '???' (그림자). 드러나면 금빛 판에 이름 · 타입
    아래     흰 글상자에 지금 할 일 한 줄, 오른쪽에 빨간 승부 단추

불러오기 · 도트 받기(_thumbs) · 승부 열기(challenge)는 기본 창(ui_boss.BossWindow) 그대로다. 그리는 것(paint)만 바꾼다.
창 높이는 기본 창과 같게 맞춘다 (줄 높이 · 사이 · 머리).
"""
import tkinter as tk

from ... import ui_boss as BO
from ... import ui_box
from ... import ui_common as U
from . import INK, INK2, LINE, LINE_D, WHITE, font
from . import kit as K
from .dialogs import BODY, PAD
from .guild import clamp_lines

DARK, EVIL = BO.DARK, "#d83a40"
STATE = {"won": ("이김", "#23813f"), "next": ("도전", "#d02e34"), "locked": ("잠김", "#6e7684")}


class _Pic(object):
    """기본 창이 rows[i]["pic"].configure(image=...) 로 도트를 붙인다 - 그 자리에 캔버스 그림을 놓는다."""

    def __init__(self, cv, x, y, tag):
        self.cv, self.x, self.y, self.tag = cv, x, y, tag

    def configure(self, image=None, **_kw):
        if image is None:
            return
        try:
            self.cv.delete(self.tag)
            self.cv.create_image(self.x, self.y, image=image, tags=(self.tag,))
        except tk.TclError:
            pass

    config = configure


class BossWindow(BO.BossWindow):

    HEAD_H = 56          # 머리 판
    ROW_PAD = 12         # 줄 위아래 여백 합 (도트 칸 둘레)
    GAP = 3              # 줄 사이

    def _note(self, cv, x1, y1, x2, text, hint="", spec=None, pad=8):
        """흰 글상자 (진한 테 한 겹). 그린 바닥의 y."""
        s = U.h
        tw = x2 - x1 - s(28)
        spec = spec or font(10)
        th = K.text_height(cv, text, spec, tw)
        hh = (K.text_height(cv, hint, font(9), tw) + s(3)) if hint else 0
        y2 = y1 + s(pad) + th + hh + s(pad)
        K.panel(cv, x1, y1, x2, y2, strong=True)
        K.text(cv, x1 + s(14), y1 + s(pad), text, spec, anchor="nw", width=tw)
        if hint:
            K.text(cv, x1 + s(14), y1 + s(pad) + th + s(3), hint, font(9), fill=INK2, anchor="nw", width=tw)
        return y2

    def _make_body(self, f):
        """몸통은 늘 틀 하나 - 판(캔버스)이 스스로 굴린다 (_fit_canvas)."""
        self._scroll = None
        body = tk.Frame(f, bg=U.BG)
        body.pack(fill="both", expand=True)
        return body

    def _fit_canvas(self, cv):
        """창 높이를 판에 맞춘다. **화면보다 길면 판을 줄이고 안에서 굴린다** - 작은 화면(1366x768 등)에서
        글자를 '아주 크게' 하면 창이 화면보다 길어져 아래 승부 단추가 잘렸고 굴릴 방법도 없었다.
        막대는 판 오른쪽에 붙이고 그만큼 창을 넓힌다 (판의 폭은 그대로). 화면에 들어가면 예전 그대로다."""
        top = self.top
        top.shell_w = self._shell_w0
        try:
            full = int(cv.cget("height"))
            top.update_idletasks()
            over = top.winfo_reqheight() - U.work_size(top)[1]
        except (tk.TclError, ValueError):
            over = 0
        if over > 0:
            sbw = U.h(12)
            cv.configure(height=max(U.h(120), full - over), yscrollincrement=1,
                         scrollregion=(0, 0, int(cv.cget("width")), full))
            sb = K.Scroll(self.body, cv, BODY, width=sbw)
            sb.pack(side="right", fill="y", padx=(U.h(4), 0), before=cv)
            cv.configure(yscrollcommand=sb.set)
            U.scrollable(cv, 3)
            U.install_wheel(top)
            top.shell_w = self._shell_w0 + sbw + U.h(4)
        ui_box.fit(top)

    def paint(self):
        for w in self.body.winfo_children():
            w.destroy()
        self.go_btn = None
        self.rows = []
        c = self.card or {}
        s = U.h
        width = self._shell_w0 - 2 * PAD          # 기본 창과 같은 폭 (글자를 키우면 같이 넓어진다)
        cv = tk.Canvas(self.body, bg=BODY, highlightthickness=0, bd=0, width=width, height=10)
        cv.pack(fill="x")
        self.cv = cv
        x2 = width - 2
        if not c.get("active"):
            y = self._note(cv, 1, 1, x2, "지금은 악당이 나타나 있지 않습니다.\n악당은 시즌이 시작한 날부터 2주 동안, "
                           "하루에 한 번 오전 9시부터 낮 12시 사이에 나타나 밤 11시까지 머뭅니다.",
                           spec=font(9), pad=6)
            cv.configure(height=y + s(2))
            self._fit_canvas(cv)
            return
        # 머리
        hh = s(self.HEAD_H)
        K.rrect(cv, 1, 1, x2, hh, 8, fill=DARK, outline=EVIL, width=2)
        cv.create_text(s(16), s(19), text=c.get("team") or "악당", fill=WHITE, font=font(16), anchor="w")
        cv.create_text(s(16), s(40), text="%s 에 나타났다 · 밤 11시까지 %s"
                       % (c.get("sidoName") or "", BO.left_text(c.get("endsIn"))), fill="#c9cfdf", font=font(9),
                       anchor="w")
        y = hh + s(8)
        # 간부들 · 전설
        th = U.h(BO.THUMB)
        rh = th + s(self.ROW_PAD)
        for i, m in enumerate(c.get("members") or []):
            self.rows.append(self._plate(cv, i, y, x2, rh, th, m.get("sprite"), m.get("role") or "",
                                         m.get("name") or "", m.get("state")))
            y += rh + s(self.GAP)
        lg = c.get("legend") or {}
        i = len(self.rows)
        if lg.get("open"):
            state = "won" if lg.get("done") else "next"
            sub = " · ".join(lg.get("types") or []) or "전설의 포켓몬"
            self.rows.append(self._plate(cv, i, y, x2, rh, th, None, sub, lg.get("name") or "?", state,
                                         legend=lg))
        else:
            self.rows.append(self._plate(cv, i, y, x2, rh, th, None, "간부를 모두 이기면 모습을 드러낸다", "???",
                                         "locked", hidden=True))
        y += rh + s(10)
        # 아래: 할 일 한 줄 + 승부 단추
        text, can, note = BO.action_of(c)
        bw = 0
        if text:
            b = K.CButton(cv, text, self.challenge, "red", font(11))
            bw = b.want_width(s(30))
        y2 = self._note(cv, 1, y, x2 - (bw + s(10) if bw else 0), note or " ")
        if text:
            b.enabled = can
            mid = (y + y2) // 2
            b.layout(x2 - bw, mid - s(21), x2, mid + s(21))
            self.go_btn = b
        cv.configure(height=max(y2, y + s(42)) + s(2))
        self._thumbs()
        self._fit_canvas(cv)

    def _plate(self, cv, i, y, x2, rh, th, sprite, role, name, state, legend=None, hidden=False):
        """한 줄 (간부 또는 전설). 기본 창의 rows 와 같은 모양의 dict 를 돌려준다."""
        s = U.h
        locked = state == "locked"
        if hidden:
            fill, line, w = "#2a2e3a", "#141720", 1
        elif legend is not None:
            fill, line, w = "#fff6d8", "#c89a30", 2
        elif state == "next":
            fill, line, w = WHITE, LINE_D, 2
        else:
            fill, line, w = ("#f1f3f6" if locked else WHITE), LINE, 1
        K.rrect(cv, 1, y, x2, y + rh, s(8), fill=fill, outline=line, width=w)
        cx, cy = s(12) + th // 2, y + rh // 2
        r = th // 2
        K.rrect(cv, cx - r, cy - r, cx + r, cy + r, s(6), fill="#1c202a" if hidden else "#f4f6f9",
                outline="#3a3f4c" if hidden else LINE, width=1)
        if hidden:
            cv.create_text(cx, cy, text="?", fill="#8a90a0", font=font(16), anchor="center")
        label, col = STATE.get(state, STATE["locked"])
        f = K.tkfont_of(cv, font(10))
        cw, ch = f.measure(label) + s(16), f.metrics("linespace") + s(6)
        K.rrect(cv, x2 - s(14) - cw, cy - ch // 2, x2 - s(14), cy + ch // 2, s(5), fill=col)
        cv.create_text(x2 - s(14) - cw // 2, cy, text=label, fill=WHITE, font=font(10), anchor="center")
        tx = s(12) + th + s(14)
        room = x2 - tx - cw - s(30)
        ink = "#e0e4ec" if hidden else (INK2 if locked else INK)
        cv.create_text(tx, cy - s(11), text=clamp_lines(cv, name, font(12), room, 1), font=font(12), fill=ink,
                       anchor="w")
        cv.create_text(tx, cy + s(13), text=clamp_lines(cv, role, font(9), room, 1),
                       fill="#9aa2b4" if hidden else INK2, font=font(9), anchor="w")
        return {"pic": _Pic(cv, cx, cy, "pic%d" % i), "sprite": sprite, "legend": legend, "name": name,
                "state": state, "chip": label}
