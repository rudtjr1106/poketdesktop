"""DP 테마의 업데이트 창 - 새 판 받기(UpdateWindow)와 새 판이 있다고 묻는 창(NewVersionAsk).

v2 (2026-10-25): 글상자 한 겹 · 무늬 없음 · 기본 창보다 낮게. 몬스터볼은 앱의 도구 그림이다 (loading.ball).

    받는 창   납작한 하늘색 띠 아래에 DP 글상자(새 판 · 통통 튀는 몬스터볼), 지금 하는 일, 체력 막대 같은 홈 + 막대
              (절반 밑은 주황, 절반부터 초록), 오른쪽 아래 회색 '나중에'
    묻는 창   글상자(버전 · 크기) · 파란 꼬리표 '바뀐 것' · 물음 글상자 옆에 '지금 받기 / 나중에' 상자
              (빨간 화살표 커서, 위아래 · Enter · Esc 로도 고른다)

받는 일 · 푸는 일 · 결과값(updated / skip / failed · now / later)은 기본 창의 것을 그대로 쓴다 -
테마는 _frame · _head · _body · roll · say · progress (받는 창)와 _frame · _build · _fit (묻는 창)만 덮는다.
"""
import tkinter as tk

from ... import ui_common as U
from ... import ui_update as base
from . import DIM, INK, INK2, LINE, font
from . import dialogs as D
from . import kit as K
from .loading import ball

BAR_GREEN = "#38b848"
BAR_ORANGE = "#f09028"


def _box_lines(cv, x1, y1, x2, lines, min_h=0):
    """DP 글상자(한 겹)에 (글, 글꼴, 빛깔) 줄들을 쌓는다. 그린 바닥의 y."""
    s = U.h
    tw = x2 - x1 - s(24)
    hs = [K.text_height(cv, t, f, tw) for t, f, _c in lines]
    y2 = y1 + max(min_h, s(10) + sum(hs) + s(3) * (len(lines) - 1) + s(10))
    K.panel(cv, x1, y1, x2, y2, strong=True)
    y = y1 + (y2 - y1 - sum(hs) - s(3) * (len(lines) - 1)) // 2
    for (t, f, c), h in zip(lines, hs):
        K.text(cv, x1 + s(12), y, t, f, fill=c, anchor="nw", width=tw)
        y += h + s(3)
    return y2


class UpdateWindow(base.UpdateWindow):
    PAD = D.PAD

    def _frame(self):
        self.win.configure(bg=D.BODY, highlightthickness=0)

    def _head(self):
        D.dialog_bar(self.win, "포스크탑 업데이트")
        self._ball_xy = None
        self.msg_text = "받을 준비를 하고 있습니다..."
        self.ratio = 0.0
        self.label = ""

    def _body(self):
        s = U.h
        cw = base.W - 2 * self.PAD
        cv = tk.Canvas(self.win, bg=D.BODY, width=cw, height=10, highlightthickness=0, bd=0)
        cv.pack(padx=self.PAD, pady=(s(12), s(12)))
        self.cv = cv
        # 새 판 글상자 - 오른쪽에 통통 튀는 몬스터볼
        r = s(17)
        bottom = _box_lines(cv, 0, 0, cw, [
            ("새 버전이 있습니다", font(12), INK),
            ("v%s  →  v%s" % (base.VERSION, self.info["version"]), font(10), INK2)], min_h=s(56))
        self._ball_xy = (cw - r - s(14), bottom // 2, r)
        # 지금 하는 일 - 가장 긴 말에 맞춰 칸을 잡는다 (말이 바뀌어도 아래가 움직이지 않는다)
        longest = ("다 받았습니다. 새 버전으로 다시 시작합니다.", "받지 못했습니다. 지금 버전으로 계속합니다.",
                   "받을 준비를 하고 있습니다...")
        mh = max(K.text_height(cv, t, font(11), cw) for t in longest)
        self._msg_box = (0, bottom + s(10), cw, bottom + s(10) + mh)
        # 막대 - 왼쪽에 '받기' 꼬리표
        by = self._msg_box[3] + s(8)
        tw_, th_ = K.tag(cv, 0, by - s(2), "받기")
        self._bar = (tw_ + s(8), by, cw, by + s(16))
        pct_y = by + s(16) + s(6)
        self._pct_pos = (cw, pct_y)
        # 아래 줄 - 안내 · 나중에
        row_y = pct_y + s(16)
        cv.create_text(0, row_y + s(17), text="받는 동안 잠시만 기다려 주세요", fill=DIM, font=font(9), anchor="w")
        self.btn_skip = K.CButton(cv, "나중에", self.on_skip, "gray", font(11))
        bw = self.btn_skip.want_width(s(36))
        self.btn_skip.layout(cw - bw, row_y, cw, row_y + s(34))
        cv.configure(height=row_y + s(34))
        self._draw_msg()
        self._draw_bar()
        self.win.update_idletasks()
        U.place_window(self.win, base.W, self.win.winfo_reqheight())
        self.roll()

    # ---------------- 그리는 것 ----------------
    def _draw_msg(self):
        cv = self.cv
        cv.delete("msg")
        x1, y1, x2, _y2 = self._msg_box
        K.text(cv, x1, y1, self.msg_text, font(11), anchor="nw", width=x2 - x1, tags=("msg",))

    def _draw_bar(self):
        cv, s = self.cv, U.h
        cv.delete("bar")
        x1, y1, x2, y2 = self._bar
        tg = ("bar",)
        K.rrect(cv, x1, y1, x2, y2, s(8), fill="#ffffff", outline=LINE, width=2, tags=tg)
        inner = x2 - x1 - s(6)
        w = int(inner * max(0.0, min(1.0, self.ratio)))
        if w > s(4):
            col = BAR_GREEN if self.ratio >= 0.5 else BAR_ORANGE
            K.rrect(cv, x1 + s(3), y1 + s(3), x1 + s(3) + w, y2 - s(3), s(5), fill=col, tags=tg)
        cv.delete("pct")
        if self.label:
            cv.create_text(self._pct_pos[0], self._pct_pos[1], text=self.label, fill=INK2, font=font(9), anchor="ne",
                           tags=("pct",))

    def roll(self):
        """몬스터볼이 구른다. 받는 동안 계속."""
        if self.done_flag:
            return
        self.spin = (self.spin + 11) % 360
        if self._ball_xy:
            try:
                self.cv.delete("ball")
                x, y, r = self._ball_xy
                ball(self.cv, x, y, r, self.spin, tags=("ball",))
            except tk.TclError:
                return
        self.spin_job = self.root.after(40, self.roll)

    def say(self, text):
        self.msg_text = text
        try:
            self._draw_msg()
        except Exception:                                   # noqa: BLE001
            pass

    def progress(self, ratio, label=""):
        self.ratio, self.label = ratio, label
        try:
            self._draw_bar()
        except Exception:                                   # noqa: BLE001
            pass

    def finish(self):
        try:
            self.btn_skip.dispose()
        except Exception:                                   # noqa: BLE001
            pass
        base.UpdateWindow.finish(self)


class NewVersionAsk(base.NewVersionAsk):
    PAD = D.PAD

    def _frame(self):
        self.win.configure(bg=D.BODY, highlightthickness=0)

    def _build(self, sub, bits):
        s = U.h
        D.dialog_bar(self.win, "포스크탑 — 새 버전")
        cw = base.ASK_W - 2 * self.PAD
        cv = tk.Canvas(self.win, bg=D.BODY, width=cw, height=10, highlightthickness=0, bd=0)
        cv.pack(padx=self.PAD, pady=(s(12), s(14)))
        self.cv = cv
        y = _box_lines(cv, 0, 0, cw, [("새 버전이 나왔습니다", font(12), INK), (sub, font(10), INK2)]) + s(12)
        if bits:
            y = D.heading(cv, 0, cw, y, "바뀐 것")
            for b in bits:
                _a, tid = K.text(cv, s(4), y, "· " + b, font(10), anchor="nw", width=cw - s(8))
                y = cv.bbox(tid)[3] + s(4)
            y += s(6)
        else:
            _a, tid = K.text(cv, s(4), y, "새 판으로 갈아탈 수 있습니다.", font(11), anchor="nw", width=cw - s(8))
            y = cv.bbox(tid)[3] + s(12)
        items = [("now", "지금 받기", None, None), ("later", "나중에", None, None)]
        box = D.ChoiceBox(cv, items, self._pick, current=0)
        self.choice = box
        bw = max(box.want_width(), s(120))
        D.message_box(cv, 0, y, cw - bw - s(8), "지금 새 판을 받을까요?",
                      hint="받으면 프로그램이 새 판으로 다시 시작합니다.", min_h=box.height())
        box.layout(cw - bw, y, cw)
        cv.configure(height=y + box.height())
        self.win.bind("<Up>", lambda _e: box.move(-1))
        self.win.bind("<Down>", lambda _e: box.move(1))
        self.win.bind("<Return>", lambda _e: box.pick())
        self.win.bind("<Escape>", lambda _e: self.on_later())

    def _pick(self, key):
        if key == "now":
            self.on_now()
        else:
            self.on_later()

    def _fit(self):
        """내용이 바라는 만큼 (모자라면 화면이 허락하는 데까지)."""
        try:
            self.win.update_idletasks()
            U.place_window(self.win, base.ASK_W, self.win.winfo_reqheight())
        except Exception:                                   # noqa: BLE001
            pass
