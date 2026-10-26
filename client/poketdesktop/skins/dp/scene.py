# -*- coding: utf-8 -*-
"""DP 판의 공통 조각 - 가방의 도구 칸 · 기술머신 칸이 같이 쓴다.

    Scene       캔버스 한 장에 그리는 판: 다시 그리기 예약, 진짜 위젯(입력칸 · 목록) 올리기, 메시지 상자
    PocketDial  왼쪽 - 하늘 칸(가방 이름표 · 포켓치 · 주머니 띠 · 주머니 이름) + 황토 바탕 몬스터볼 다이얼
    Plates      올리브 빗금 칸 - 제목 · 포켓몬 찾기 · 모서리를 깎은 판 목록 (DP 파티 화면)
    Band        보라 설명 띠
    mid_column  가운데 키 큰 목록 칸의 폭 (두 칸이 같은 폭)

창 클래스는 이것들을 섞고 (class BagWindow(Scene, PocketDial, Plates, Band, ui_bag.BagWindow)),
'무엇을 그릴지' 만 알려 준다 (_lcd_text, _plate_info …).
"""
import math
import tkinter as tk

from ... import box_filter
from ... import ui_bag as B
from ... import ui_common as U
from . import (BALL_BTN, BALL_RED, BALL_WHITE, BEZEL, BROWN, BTN_IN, BTN_INK, BTN_LINE, BTN_TAN, CELL,
               CELL_INK, CUR, CYAN1, CYAN2, DIM, INK, LIST_FRAME, LIST_IN, MSG_FRAME, MSG_ST1, MSG_ST2,
               MSG_ST_LINE, OLIVE1, OLIVE2, PLATE_BOT, PLATE_GOOD_BOT, PLATE_GOOD_TOP, PLATE_HOVER_BOT,
               PLATE_HOVER_TOP, PLATE_LINE, PLATE_OFF_BOT, PLATE_OFF_TOP, PLATE_SEL, PLATE_TOP, PURPLE,
               PURPLE_EM, PURPLE_HI, PURPLE_LO, PURPLE_SH, STRIP, STRIP_LINE, TAG, TAG_IN, TAG_LINE, TAN,
               TAN_D, TAN_L, font, tone)
from . import kit as K

T = ("scene",)

# 다이얼 둘레의 주머니 (위에서부터 시계 방향). "tms" 는 기술머신 칸이다.
POCKETS = [("all", "전체"), ("held", "지닌\n도구"), ("megastone", "메가\n스톤"), ("zcrystal", "Z\n크리스탈"),
           ("form", "폼\n도구"), ("stone", "진화의\n돌"), ("ev", "노력치"), ("iv", "단련"),
           ("misc", "기타"), ("ball", "볼"), ("tms", "기술\n머신")]
POCKET_NAME = dict(B.CAT_KR, all="전체", tms="기술머신")

# 가운데 키 큰 목록 칸 (도구 칸 · 기술머신 칸이 같은 폭). 왼쪽 다이얼을 뺀 나머지의 52% -
# 작은 창(980)에서도 290pt 는 지키고, 큰 창에서는 480pt 에서 멈춘다 (오른쪽 판 칸이 너무 좁아지지 않게).
MID_SHARE = 0.52
MID_MIN, MID_MAX = 290, 480


def mid_column(x0, W):
    """가운데 목록 칸의 오른쪽 끝 x (x0 = 왼쪽 다이얼 끝, W = 판 폭)."""
    return x0 + max(U.h(MID_MIN), min(U.h(MID_MAX), int((W - x0) * MID_SHARE)))


class Slot(object):
    """글씨만 바뀌는 자리 - 기본 창의 동작 코드가 단추처럼 configure(text=) 를 부른다. 판이 이 글을 그린다."""

    def __init__(self, text, on_change):
        self.text = text
        self.on_change = on_change

    def configure(self, text=None, **_kw):
        if text is not None and text != self.text:
            self.text = text
            self.on_change()

    config = configure


class Find(object):
    """'누구에게' 목록의 찾기 · 줄 세우기 (ui_monfind.FindBar 와 같은 말을 받는다). 그림은 판이 그린다."""

    def __init__(self, win, parent, on_change):
        self.win = win
        self.on_change = on_change
        self.sort = ""
        self.count = ""
        self.q = tk.StringVar()
        self.box = K.entry(parent, self.q, width=10)
        self.q.trace_add("write", lambda *_a: on_change())

    def query(self):
        return self.q.get()

    def searching(self):
        return bool(box_filter._norm(self.q.get()))

    def pick_sort(self, key):
        self.sort = key or ""
        self.on_change()
        self.win._soon()

    def view(self, mons, dex):
        out = box_filter.pick_view(mons or [], dex, self.q.get(), self.sort)
        self.count = ("%d마리" % len(out)) if self.searching() else ""
        return out

    def empty_note(self):
        return "'%s' 에 맞는 포켓몬이 없다." % self.q.get().strip()


# ---------------------------------------------------------------- 판
class Scene(object):

    def _scene_init(self):
        self.msg = ("", None)
        self._job = None
        self._wins = {}
        self._msg_ids = None
        self.win.configure(bg=BEZEL, highlightthickness=0)
        self.cv = tk.Canvas(self.win, bg=BEZEL, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", lambda _e: self._soon())

    def _hand(self, *tags):
        for tag in tags:
            self.cv.tag_bind(tag, "<Enter>", lambda _e: self.cv.configure(cursor="hand2"))
            self.cv.tag_bind(tag, "<Leave>", lambda _e: self.cv.configure(cursor=""))

    def _soon(self):
        if self._job is None and getattr(self, "alive", True):
            try:
                self._job = self.cv.after_idle(self._paint)
            except tk.TclError:
                pass

    def _place(self, key, widget, x, y, w, h):
        """진짜 위젯을 캔버스에 올린다 - 한 번 만든 항목은 옮기기만 한다 (지웠다 다시 올리면 깜빡인다)."""
        w, h = max(1, int(w)), max(1, int(h))
        i = self._wins.get(key)
        if i is None:
            self._wins[key] = self.cv.create_window(x, y, window=widget, anchor="nw", width=w, height=h)
        else:
            self.cv.coords(i, x, y)
            self.cv.itemconfigure(i, width=w, height=h, state="normal")

    def _hide(self, key):
        i = self._wins.get(key)
        if i is not None:
            self.cv.itemconfigure(i, state="hidden")

    def _say(self, text, color=None):
        """메시지 상자의 글. color 는 기본 테마의 뜻 색 (U.DANGER …) - 없으면 보통 글자색."""
        self.msg = (text or "", color)
        if self._msg_ids:
            try:
                a, b = self._msg_ids
                # 그린 글상자의 폭으로 다시 접는다 (그대로 바꿔 넣으면 긴 말이 상자 밖으로 한 줄로 나간다)
                shown = K.wrap(self.cv, self.msg[0], font(11), getattr(self, "_msg_w", 0))
                if a:
                    self.cv.itemconfigure(a, text=shown)
                self.cv.itemconfigure(b, text=shown, fill=tone(color) if color else INK)
                return
            except tk.TclError:
                pass
        self._soon()

    def _paint_message(self, cv, x1, y1, x2, y2):
        """DP 의 글 상자 (흰 바탕 · 진한 테). v2: 오른쪽 끝 줄무늬는 뺐다."""
        K.rrect(cv, x1, y1, x2, y2, 8, fill=MSG_FRAME, tags=T)
        K.rrect(cv, x1 + 3, y1 + 3, x2 - 3, y2 - 3, 6, fill="#ffffff", tags=T)
        text, c = self.msg
        self._msg_w = max(40, x2 - x1 - U.h(28))
        self._msg_ids = K.text(cv, x1 + U.h(14), (y1 + y2) // 2, text, font(11),
                               fill=tone(c) if c else INK, anchor="w", width=self._msg_w, tags=T)

    def _paint_bottom(self, cv, x0, W, y1, H, buttons):
        """아래 줄: 메시지 상자 + 오른쪽 단추들 (buttons = [(CButton, 최소 폭, 최대 폭)], 오른쪽부터)."""
        cv.create_rectangle(x0, y1, W, H, fill="#dfe4ea", outline="", tags=T)
        cv.create_line(x0, y1 + 1, W, y1 + 1, fill="#b8c0cc", width=2, tags=T)
        bh = U.h(42)
        by1 = y1 + (H - y1 - bh) // 2
        x2 = W - U.h(12)
        for btn, lo, hi in buttons:
            w = max(lo, min(hi, btn.want_width(U.h(30))))
            btn.layout(x2 - w, by1, x2, by1 + bh)
            x2 -= w + U.h(8)
        self._paint_message(cv, x0 + U.h(10), y1 + U.h(8), x2 - U.h(4), H - U.h(8))

    # ---- 글상자 없는 칸 (가방 · 기술머신): 아래 줄은 큰 단추 하나, 말은 보라 띠 위에 잠깐 ----
    ACTION_H = 58           # 아래 줄 높이 (pt)
    TOAST_MS = 3200         # 알림이 떠 있는 시간

    def _paint_action_row(self, cv, x0, W, y1, H, btn):
        """아래 줄: 칸 폭 가득 단추 하나 (사용자: 글상자 · 닫기는 필요 없다 - 그 자리를 포켓몬 판에 준다)."""
        cv.create_rectangle(x0, y1, W, H, fill="#dfe4ea", outline="", tags=T)
        cv.create_line(x0, y1 + 1, W, y1 + 1, fill="#b8c0cc", width=2, tags=T)
        btn.layout(x0 + U.h(12), y1 + U.h(9), W - U.h(12), H - U.h(9))

    def _toast(self, text, color=None):
        """쓰기 결과 · 오류처럼 알려야 할 말을 보라 띠 위에 잠깐 띄운다 (빈 말이면 지운다)."""
        job = getattr(self, "_toast_job", None)
        if job is not None:
            try:
                self.cv.after_cancel(job)
            except tk.TclError:
                pass
        self._toast_job = None
        self._toast_msg = (text, color) if text else None
        if text:
            try:
                self._toast_job = self.cv.after(self.TOAST_MS, lambda: self._toast(""))
            except tk.TclError:
                return
        self._paint_toast()

    def _paint_toast(self):
        """_paint 가 정한 자리(_toast_box = 띠의 x1, y1, x2, y2)에 흰 글상자. 띠는 캔버스 그림뿐이라 덮을 수 있다."""
        cv = self.cv
        try:
            cv.delete("toast")
        except tk.TclError:
            return
        m, box = getattr(self, "_toast_msg", None), getattr(self, "_toast_box", None)
        if not m or not box:
            return
        text, color = m
        x1, y1, x2, y2 = box
        bx1, bx2 = x1 + U.h(10), x2 - U.h(10)
        th = K.text_height(cv, text, font(11), bx2 - bx1 - U.h(24))
        h = min(y2 - y1 - U.h(8), th + U.h(22))
        by1 = (y1 + y2 - h) // 2
        K.msgbox(cv, bx1, by1, bx2, by1 + h, text, tone(color) if color else None, tags=("toast",))

    def _tabs(self, cv, x, y, h, items, current, tag, on_pick, spec=None, align="left", fill_off="#f2f4f7",
              line_off="#b6becb"):
        """작은 둥근 탭 줄 (줄 세우기 · 거르기). align="right" 면 x 가 오른쪽 끝. 그린 칸들 [(열쇠, 상자)]."""
        spec = spec or font(10)
        f = K.tkfont_of(cv, spec)
        ws = [f.measure(lb) + U.h(18) for _k, lb in items]
        gap = U.h(4)
        if align == "right":
            x -= sum(ws) + gap * (len(items) - 1)
        out = []
        for (key, lb), w in zip(items, ws):
            on = key == current
            tg = T + (tag, "%s_%s" % (tag, key or "_"))
            K.rrect(cv, x, y + 1, x + w, y + h - 1, 6, fill="#ffffff" if on else fill_off,
                    outline=CUR if on else line_off, width=2, tags=tg)
            cv.create_text(x + w // 2, y + h // 2, text=lb, fill=CUR if on else INK, font=spec, anchor="center",
                           tags=tg)
            cv.tag_bind("%s_%s" % (tag, key or "_"), "<Button-1>", lambda _e, k=key: on_pick(k))
            out.append((key, (x, y, x + w, y + h)))
            x += w + gap
        self._hand(tag)
        return out


# ---------------------------------------------------------------- 왼쪽: 주머니 다이얼
class PocketDial(object):
    """왼쪽 기둥. 부르는 창이 정하는 것:

        _lcd_text()          포켓치 액정에 띄울 글 (돈 · 개수)
        _line_text()         이름표 아래 한 줄
        _pocket_now()        지금 주머니 열쇠
        _pocket_label()      주머니 이름 칸의 글
        _pocket_count(key)   그 주머니에 든 것 (0 이면 흐리게)
        _pocket_click(key)   주머니를 눌렀다
        _dial_buttons()      다이얼 아래 단추들 [CButton]
        _tm_badge            기술머신 주머니의 점
    """
    LW_PX = 250
    TOPH_PX = 150

    def _paint_left(self, cv, H):
        LW, TOPH = U.h(self.LW_PX), U.h(self.TOPH_PX)
        self._paint_left_top(cv, LW, TOPH)
        self._paint_dial(cv, LW, TOPH, H)
        return LW

    def _paint_left_top(self, cv, LW, TOPH):
        cv.create_rectangle(0, 0, LW, TOPH, fill=CYAN1, outline="", tags=T)     # (v2: 줄무늬 없이)
        tx1, ty1 = U.h(12), U.h(10)
        tx2, ty2 = tx1 + U.h(84), ty1 + U.h(34)
        K.framed(cv, tx1, ty1, tx2, ty2, 9, TAG, TAG_LINE, TAG_IN, tags=T)
        K.outlined(cv, (tx1 + tx2) // 2, (ty1 + ty2) // 2, "가방", font(15), line="#2a74a0", anchor="center",
                   tags=T)
        # 포켓치 (짙은 회색 테 · 연두 액정 · 빨간 알약 단추 · 파란 몸통)
        px2 = LW - U.h(10)
        px1, py1, py2 = px2 - U.h(146), U.h(8), U.h(8) + U.h(46)
        K.rrect(cv, px1, py1, px2, py2, 8, fill="#3b3b40", tags=T)
        lx1, ly1, lx2, ly2 = px1 + 6, py1 + 6, px2 - U.h(32), py2 - 6
        cv.create_rectangle(lx1, ly1, lx2, ly2, fill="#a8d09e", outline="#7c9c74", tags=T)
        cv.create_text(lx2 - 6, (ly1 + ly2) // 2, text=self._lcd_text(), fill="#2f4a30", font=font(13), anchor="e",
                       tags=T)
        K.rrect(cv, px2 - U.h(25), py1 + U.h(9), px2 - U.h(12), py2 - U.h(9), U.h(6), fill="#e04848", tags=T)
        cv.create_rectangle(px2 - 6, py1 + 5, px2, py2 - 5, fill="#2d5ed4", outline="", tags=T)
        K.text(cv, tx1 + 2, ty2 + U.h(8), self._line_text(), font(9), tags=T)
        # 주머니 띠 (작은 칸, 지금 주머니는 빨강)
        sy1 = ty2 + U.h(30)
        sy2 = sy1 + U.h(22)
        sx1, sx2 = tx1, LW - U.h(10)
        K.rrect(cv, sx1, sy1, sx2, sy2, 6, fill=STRIP_LINE, tags=T)
        K.rrect(cv, sx1 + 2, sy1 + 2, sx2 - 2, sy2 - 2, 5, fill=STRIP, tags=T)
        now = self._pocket_now()
        n = len(POCKETS)
        cw = (sx2 - sx1 - 8) / float(n)
        for i, (key, _l) in enumerate(POCKETS):
            c1 = sx1 + 4 + i * cw
            on = key == now
            tg = T + ("pk", "pk_" + key)
            cv.create_rectangle(c1 + 1, sy1 + 4, c1 + cw - 1, sy2 - 4, fill="#e83838" if on else CELL, outline="",
                                tags=tg)
            dot = "#ffffff" if on else B.CAT_COLOR.get(key, CELL_INK)
            m = (sy1 + sy2) // 2
            cv.create_rectangle(c1 + cw / 2 - 2, m - 2, c1 + cw / 2 + 2, m + 2, fill=dot, outline="", tags=tg)
        # 주머니 이름 + '주머니'
        ny1 = sy2 + U.h(6)
        ny2 = ny1 + U.h(28)
        nx2 = LW - U.h(74)
        cv.create_rectangle(sx1, ny1, nx2, ny2, fill="#ffffff", outline="#9a9aa2", width=2, tags=T)
        K.text(cv, (sx1 + nx2) // 2, (ny1 + ny2) // 2, self._pocket_label(), font(11), anchor="center", tags=T)
        K.rrect(cv, nx2, ny1 + U.h(6), LW - U.h(10), ny2, 6, fill="#fbe6b4", tags=T)
        cv.create_text((nx2 + LW - U.h(10)) // 2, (ny1 + U.h(6) + ny2) // 2, text="주머니", fill="#d8902c",
                       font=font(9), anchor="center", tags=T)
        for key, _l in POCKETS:
            cv.tag_bind("pk_" + key, "<Button-1>", lambda _e, k=key: self._pocket_click(k))
        self._hand("pk", "refresh")

    def _paint_dial(self, cv, LW, TOPH, H):
        cv.create_rectangle(0, TOPH, LW, H, fill=TAN_D, outline="", tags=T)
        btns = [b for b in self._dial_buttons() if b is not None]
        btn_h = U.h(40)
        dy1, dy2 = TOPH, (H - btn_h - U.h(14)) if btns else H - U.h(6)
        cx, cy = LW // 2, (dy1 + dy2) // 2
        pr = U.h(24)
        R = max(U.h(70), min((dy2 - dy1) // 2 - pr - 4, LW // 2 - pr - 6))
        cv.create_oval(cx - R - pr - 8, cy - R - pr - 8, cx + R + pr + 8, cy + R + pr + 8, fill=TAN, outline="",
                       tags=T)
        inner = R - pr - 8
        cv.create_oval(cx - inner, cy - inner, cx + inner, cy + inner, fill=TAN_L, outline="", tags=T)
        rb = max(U.h(36), inner - U.h(10))
        ow = max(3, U.h(4))
        cv.create_oval(cx - rb, cy - rb, cx + rb, cy + rb, fill=BALL_WHITE, outline="", tags=T)
        cv.create_arc(cx - rb, cy - rb, cx + rb, cy + rb, start=0, extent=180, fill=BALL_RED, outline="",
                      style="chord", tags=T)
        band = U.h(8)
        cv.create_rectangle(cx - rb, cy - band // 2, cx + rb, cy + band // 2, fill=BROWN, outline="", tags=T)
        cv.create_oval(cx - rb, cy - rb, cx + rb, cy + rb, outline=BROWN, width=ow, tags=T)
        rc = int(rb * 0.40)
        cv.create_oval(cx - rc, cy - rc, cx + rc, cy + rc, fill=BALL_BTN, outline=BROWN, width=ow,
                       tags=T + ("refresh",))
        cv.create_oval(cx - rc + ow + 2, cy - rc + ow + 2, cx + rc - ow - 2, cy + rc - ow - 2, outline="#f4f4f4",
                       width=2, tags=T + ("refresh",))
        cv.create_text(cx, cy, text="새로\n고침", fill="#505058", font=font(9), justify="center", anchor="center",
                       tags=T + ("refresh",))
        cv.tag_bind("refresh", "<Button-1>", lambda _e: self.reload())
        now = self._pocket_now()
        n = len(POCKETS)
        for i, (key, label) in enumerate(POCKETS):
            a = math.radians(-90 + 360.0 * i / n)
            bx, by = cx + R * math.cos(a), cy + R * math.sin(a)
            on = key == now
            empty = self._pocket_count(key) == 0
            fill = "#fff2d6" if on else ("#efe4c0" if empty else BTN_TAN)
            tg = T + ("pk", "pk_" + key)
            cv.create_oval(bx - pr, by - pr, bx + pr, by + pr, fill=fill, outline=CUR if on else BTN_LINE, width=3,
                           tags=tg)
            cv.create_oval(bx - pr + 4, by - pr + 4, bx + pr - 4, by + pr - 4, outline="#ffffff" if on else BTN_IN,
                           width=2, tags=tg)
            cv.create_text(bx, by, text=label, fill="#c02828" if on else ("#c4ac78" if empty else BTN_INK),
                           font=font(8), justify="center", anchor="center", tags=tg)
            if key == "tms" and getattr(self, "_tm_badge", False):
                d = U.h(5)
                cv.create_oval(bx + pr * 0.55 - d, by - pr * 0.75 - d, bx + pr * 0.55 + d, by - pr * 0.75 + d,
                               fill="#ff4040", outline="#ffffff", width=2, tags=tg)
        if btns:
            by1, by2 = H - btn_h - U.h(10), H - U.h(10)
            ws = [b.want_width(U.h(22)) for b in btns]
            gap = U.h(8)
            x1 = max(U.h(8), (LW - (sum(ws) + gap * (len(btns) - 1))) // 2)
            for b, w in zip(btns, ws):
                b.layout(x1, by1, x1 + w, by2)
                x1 += w + gap


# ---------------------------------------------------------------- 보라 설명 띠
class Band(object):
    """부르는 창이 _band_content() -> (제목, 본문, 그림 그리는 함수(cv, x, y, s) 또는 None) 를 준다."""

    def _band_height(self, cv, x0, W, H):
        tw = (W - x0) - U.h(96)
        title, body, _art = self._band_content()
        th = K.text_height(cv, title, font(11), tw) + U.h(4) + K.text_height(cv, body, font(11), tw)
        # 상한은 판 높이의 40% - 오른쪽 칸이 좁아 긴 설명(뽑기권 등)이 여러 줄이 되어도 띠 안에 든다
        return max(U.h(74), min(int(H * 0.40), th + U.h(24)))

    def _paint_band(self, cv, x0, W, y, BH):
        tw = (W - x0) - U.h(96)
        title, body, art = self._band_content()
        cv.create_rectangle(x0, y, W, y + BH, fill=PURPLE, outline="", tags=T)
        cv.create_rectangle(x0, y, W, y + 3, fill=PURPLE_HI, outline="", tags=T)
        cv.create_rectangle(x0, y + BH - 3, W, y + BH, fill=PURPLE_LO, outline="", tags=T)
        s = U.h(52)
        ix, iy = x0 + U.h(14), y + (BH - s) // 2
        K.rrect(cv, ix, iy, ix + s, iy + s, 8, fill="#ffffff", outline="#a2a2b2", width=2, tags=T)
        if art is not None:
            art(cv, ix, iy, s)
        tx = ix + s + U.h(14)
        ty = y + U.h(10)
        _a, t1 = K.text(cv, tx, ty, title, font(11), fill=PURPLE_EM, shadow=PURPLE_SH, tags=T, width=tw)
        b = cv.bbox(t1)
        K.text(cv, tx, (b[3] if b else ty + U.h(18)) + U.h(4), body, font(11), fill="#ffffff", shadow=PURPLE_SH,
               tags=T, width=tw)


# ---------------------------------------------------------------- 올리브 칸: 포켓몬 판
class Plates(object):
    """부르는 창이 정하는 것:

        _plate_info(m)    {"name", "sub", "note", "color", "good", "blocked", "photo", "shiny"}
        _plate_click(m)   판을 눌렀다
        mon_id            고른 포켓몬
    """
    PLATE_PX = 52

    def _plates_init(self, on_find):
        self._plate_cols = 2
        self._plate_rows_src = []
        self.PLATE_H = U.h(self.PLATE_PX)
        self.find = Find(self, self.cv, on_find)
        self.mons_vl = K.VList(self.cv, OLIVE1, self._draw_plate_row)
        self.mons_vl.on_click = self._click_plate
        self.mons_vl.col_of = lambda x: int(x * self._plate_cols / max(1, self.mons_vl.cv.winfo_width()))

    def _plates_set(self, view, keep=True):
        self._plate_rows_src = list(view)
        cols = max(1, self._plate_cols)
        rows = [(self.PLATE_H, self._plate_rows_src[i:i + cols])
                for i in range(0, len(self._plate_rows_src), cols)]
        self.mons_vl.set(rows, keep=keep)

    def _plate_box(self, x, y, w, h, k):
        cols = max(1, self._plate_cols)
        gap = U.h(8)
        pw = (w - (cols + 1) * gap) // cols
        x1 = x + gap + k * (pw + gap)
        return x1, y + gap // 2, x1 + pw, y + h - gap // 2

    def _draw_plate_row(self, cv, row, x, y, w, h, tags, hover=None):
        for k, m in enumerate(row):
            x1, y1, x2, y2 = self._plate_box(x, y, w, h, k)
            hov = hover is not None and x1 <= hover <= x2
            self._draw_plate(cv, m, x1, y1, x2, y2, tags, hov)

    def _draw_plate(self, cv, m, x1, y1, x2, y2, tags, hov):
        info = self._plate_info(m)
        blocked, good = info.get("blocked"), info.get("good")
        sel = m.get("id") == self.mon_id
        if blocked:
            top, bot = PLATE_OFF_TOP, PLATE_OFF_BOT
        elif good:
            top, bot = PLATE_GOOD_TOP, PLATE_GOOD_BOT
        elif hov:
            top, bot = PLATE_HOVER_TOP, PLATE_HOVER_BOT
        else:
            top, bot = PLATE_TOP, PLATE_BOT
        c = U.h(10)
        K.clipped(cv, x1, y1, x2, y2, c, PLATE_SEL if sel else PLATE_LINE, tags)
        b = 3 if not sel else 4
        K.clipped(cv, x1 + b, y1 + b, x2 - b, y2 - b, c - 2, bot, tags)
        mid = (y1 + y2) // 2
        cc = c - 2
        cv.create_polygon(x1 + b + cc, y1 + b, x2 - b, y1 + b, x2 - b, mid, x1 + b, mid, x1 + b, y1 + b + cc,
                          fill=top, outline="", tags=tags)
        ph = info.get("photo")
        if ph is not None:
            cv.create_image(x1 + U.h(26), mid, image=ph, tags=tags)
        name = info.get("name") or "?"
        shiny = info.get("shiny")
        if shiny:
            name = "★ " + name
        tx = x1 + U.h(50)
        cv.create_text(tx, y1 + U.h(6), text=name, fill="#8a5a00" if shiny else "#1c2e44", font=font(11),
                       anchor="nw", tags=tags)
        cv.create_text(tx, y2 - U.h(6), text=info.get("sub") or "", fill="#34506c" if not blocked else DIM,
                       font=font(9), anchor="sw", tags=tags)
        if info.get("note"):
            # 좁은 판 (한 줄에 하나)에서 아래 줄 글과 닿으면 이름 줄 오른쪽으로 올린다
            f9 = K.tkfont_of(cv, font(9))
            nw = f9.measure(info["note"])
            low = tx + f9.measure(info.get("sub") or "") + U.h(10) <= x2 - U.h(10) - nw
            cv.create_text(x2 - U.h(10), (y2 - U.h(6)) if low else (y1 + U.h(8)), text=info["note"],
                           fill=tone(info.get("color") or U.FG_DIM), font=font(9), anchor="se" if low else "ne",
                           tags=tags)

    def _click_plate(self, row, x, _y, w):
        for k, m in enumerate(row):
            x1, _y1, x2, _y2 = self._plate_box(0, 0, w, self.PLATE_H, k)
            if x1 <= x <= x2:
                return self._plate_click(m)

    def _paint_plates_area(self, cv, x0, W, y1, y2, title, hint, note, boxes=()):
        """올리브 칸 전체. boxes = [(높이, 그리는 함수(cv, x1, y, x2))] - 판 목록 위에 끼우는 칸 (병뚜껑 능력 등).
        note 가 있으면 판 목록 대신 그 글.

        좁은 칸 (가운데 목록 옆): 안내 글이 제목 옆에 안 들어가면 제목 아래 줄로, 줄 세우기 탭이 찾기 칸 옆에
        안 들어가면 찾기 줄 아래 한 줄로 내린다 (글씨를 줄이지 않고 줄을 바꾼다)."""
        cv.create_rectangle(x0, y1, W, y2, fill=OLIVE1, outline="", tags=T)     # (v2: 빗금 없이)
        hy = y1 + U.h(8)
        cv.create_text(x0 + U.h(14), hy, text=title, fill="#262c14", font=font(12), anchor="nw", tags=T)
        fy = hy + U.h(28)
        if hint:
            tw = K.tkfont_of(cv, font(12)).measure(title)
            hw = K.tkfont_of(cv, font(9)).measure(hint)
            if x0 + U.h(14) + tw + U.h(16) + hw <= W - U.h(14):
                cv.create_text(W - U.h(14), hy + U.h(3), text=hint, fill="#2e3418", font=font(9), anchor="ne",
                               tags=T)
            else:
                _a, hid = K.text(cv, x0 + U.h(14), fy - U.h(4), hint, font(9), fill="#2e3418",
                                 width=W - x0 - U.h(28), tags=T)
                b = cv.bbox(hid)
                fy = (b[3] if b else fy + U.h(16)) + U.h(6)
        fh = U.h(26)
        if note is not None and not self.find.searching():
            # 판 목록 대신 안내 글만 놓일 때 (판을 고르지 않는 도구 · 아직 안 고름) 찾기 줄은 쓸 데가 없다 -
            # 비워 두고 그 자리를 글에 준다 (찾는 말이 들어 있으면 '맞는 포켓몬이 없다' 이므로 그대로 둔다)
            self._hide("mfind")
            self._paint_plates_rest(cv, x0, W, fy, y2, note, boxes)
            return
        cv.create_text(x0 + U.h(14), fy + fh // 2, text="포켓몬 찾기", fill="#262c14", font=font(10), anchor="w",
                       tags=T)
        ex = x0 + U.h(90)
        sorts = box_filter.PICK_SORTS
        f9 = K.tkfont_of(cv, font(9))
        tabs_w = sum(f9.measure(lb) + U.h(18) for _k, lb in sorts) + U.h(4) * (len(sorts) - 1)
        cnt_w = U.h(60) if self.find.count else 0
        kw = dict(spec=font(9), fill_off="#eef0e2", line_off="#7a8250")
        # (찾는 중에 붙는 'N마리' 자리도 늘 셈한다 - 찾을 때마다 줄이 오르내리지 않게)
        if W - U.h(14) - tabs_w - U.h(12) - U.h(60) - ex >= U.h(96):            # 한 줄에 다 든다
            tabs = self._tabs(cv, W - U.h(14), fy, fh, sorts, self.find.sort, "msrt", self.find.pick_sort,
                              align="right", **kw)
            tx = tabs[0][1][0] if tabs else W - U.h(14)
            y = fy + fh + U.h(8)
        else:                                                                    # 탭은 아래 줄로
            tx = W - U.h(4)
            self._tabs(cv, x0 + U.h(14), fy + fh + U.h(6), fh, sorts, self.find.sort, "msrt",
                       self.find.pick_sort, **kw)
            y = fy + 2 * fh + U.h(6) + U.h(8)
        self._place("mfind", self.find.box, ex, fy, max(U.h(80), tx - ex - U.h(12) - cnt_w), fh)
        if self.find.count:
            cv.create_text(tx - U.h(10), fy + fh // 2, text=self.find.count, fill="#2e3418", font=font(9),
                           anchor="e", tags=T)
        self._paint_plates_rest(cv, x0, W, y, y2, note, boxes)

    def _paint_plates_rest(self, cv, x0, W, y, y2, note, boxes):
        """올리브 칸의 아래: 끼우는 칸들 + 판 목록 (또는 안내 글 상자 - 글 길이만큼 키운다)."""
        for h, draw in boxes:
            draw(cv, x0 + U.h(12), y, W - U.h(12))
            y += h + U.h(6)
        lx1, lx2 = x0 + U.h(8), W - U.h(8)
        if note is None:
            cols = 2 if (lx2 - lx1) >= U.h(440) else 1
            if cols != self._plate_cols:
                self._plate_cols = cols
                self._plates_set(self._plate_rows_src, keep=True)
            self._place("mons", self.mons_vl.frame, lx1, y, lx2 - lx1, max(U.h(40), y2 - y - U.h(6)))
        else:
            self._hide("mons")
            th = K.text_height(cv, note, font(11), lx2 - lx1 - 40)
            K.framed(cv, lx1 + 4, y, lx2 - 4, min(y2 - 6, y + max(U.h(80), th + U.h(36))), 8, "#ffffff",
                     LIST_FRAME, LIST_IN, tags=T)
            K.text(cv, (lx1 + lx2) // 2, y + U.h(18), note, font(11), anchor="n", justify="center",
                   width=lx2 - lx1 - 40, tags=T)


def list_box(view, cv, x0, W, LH, colors=None):
    """초록 칸(colors 를 주면 그 색) + 흰 목록 상자를 그리고 안쪽 사각형을 돌려준다 (ix1, iy1, ix2, iy2)."""
    from . import GREEN, GREEN_IN, GREEN_LINE
    fill, line, inner = colors or (GREEN, GREEN_LINE, GREEN_IN)
    cv.create_rectangle(x0, 0, W, LH, fill=fill, outline="", tags=T)
    cv.create_rectangle(x0 + 2, 2, W - 2, LH - 2, outline=line, width=4, tags=T)
    cv.create_rectangle(x0 + 6, 6, W - 6, LH - 6, outline=inner, width=2, tags=T)
    bx1, by1, bx2, by2 = x0 + U.h(14), U.h(12), W - U.h(14), LH - U.h(12)
    K.framed(cv, bx1, by1, bx2, by2, 8, "#ffffff", LIST_FRAME, LIST_IN, lw=3, iw=3, tags=T)
    return bx1 + U.h(10), by1 + U.h(10), bx2 - U.h(10), by2 - U.h(8)
