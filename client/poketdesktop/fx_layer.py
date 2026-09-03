# -*- coding: utf-8 -*-
"""이펙트를 그릴 투명 레이어.

바탕화면 위에 아무것도 안 보이는 창을 하나 깔고, 그 위에 기술 이펙트를 그린다.
포켓몬 도트는 각자 자기 창에 있으므로 이펙트만 이 레이어에 올라간다.

이 창은 **클릭이 그대로 통과한다.** 그냥 투명하게만 만들면 그려진 부분은
클릭을 먹어버려서, 이펙트가 야생 포켓몬 위를 지나갈 때 오른쪽 클릭이 씹힌다.
그래서 창 전체를 통과시킨다 (윈도우는 WS_EX_TRANSPARENT, 맥은 NSWindow 의
ignoresMouseEvents — platform_os 가 고른다).

**통과시키지 못하면 레이어를 아예 안 만든다.** 통과하지 않는 투명 레이어는
화면 전체를 덮는 보이지 않는 벽이라, 바탕화면 아이콘도 다른 프로그램도
못 누르게 된다. 이펙트가 안 보이는 것보다 훨씬 나쁘다. 그래서
`open_layer()` 가 None 을 돌려주고, 부르는 쪽은 이펙트 없이 진행한다.
"""
import tkinter as tk

from . import config
from . import platform_os as PLAT
from . import ui_common as U

KEY = "#fe01fe"


def make_click_through(win):
    """창 전체를 클릭이 통과하도록 만든다. 실제 방법은 platform_os 가 안다."""
    return PLAT.make_click_through(win)


def open_layer(root, area):
    """이펙트 레이어를 연다. 클릭이 통과하지 않으면 None 을 돌려준다."""
    try:
        layer = FxLayer(root, area)
    except Exception:                                       # noqa: BLE001
        return None
    if not layer.click_through:
        config.log("이펙트 레이어: 클릭 통과를 못 걸어서 띄우지 않습니다")
        layer.destroy()
        return None
    return layer


class FxLayer(object):
    """이펙트를 그리는 캔버스. 좌표는 화면 좌표로 주고받는다."""

    def __init__(self, root, area):
        self.root = root
        x1, y1, x2, y2 = area
        # 이펙트가 활동 영역 밖으로 조금 튀어도 잘리지 않게 넉넉히
        pad = 90
        self.x = max(0, x1 - pad)
        self.y = max(0, y1 - pad)
        w = (x2 - x1) + pad * 2
        h = (y2 - y1) + pad * 2

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        bg = PLAT.transparent_window(self.win, KEY)
        self.win.geometry("%dx%d+%d+%d" % (w, h, self.x, self.y))
        # 여기는 도트(그림)가 아니라 선과 글자만 그린다. 맥에서도 캔버스
        # 벡터는 투명 배경 위에 그대로 그려지므로 Canvas 를 그냥 쓴다.
        self.cv = tk.Canvas(self.win, width=w, height=h, bg=bg,
                            highlightthickness=0, bd=0)
        self.cv.pack()
        PLAT.raise_above(self.win)
        self.click_through = make_click_through(self.win)

    def to_local(self, sx, sy):
        """화면 좌표 -> 이 캔버스 좌표."""
        return sx - self.x, sy - self.y

    def raise_above(self):
        try:
            PLAT.raise_above(self.win)
            self.win.lift()
            # 맥은 창을 다시 올리거나 숨겼다 켜면 클릭 통과가 풀린다.
            # 매 프레임 부르는 곳이 아니라 몇 프레임에 한 번이라 싸다.
            PLAT.keep_click_through(self.win)
        except Exception:
            pass

    def clear(self):
        try:
            self.cv.delete("all")
        except Exception:
            pass

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass


class FloatText(object):
    """도트 위에 잠깐 떠올랐다 사라지는 짧은 글씨."""

    def __init__(self, layer, sx, sy, text, color="#ffffff", ms=900):
        self.layer = layer
        x, y = layer.to_local(sx, sy)
        self.items = [
            layer.cv.create_text(x + 1, y + 1, text=text, fill="#101014",
                                 font=(U.FAMILY, 10, "bold")),
            layer.cv.create_text(x, y, text=text, fill=color,
                                 font=(U.FAMILY, 10, "bold")),
        ]
        self.step = 0
        self.jobs = []
        self.ms = ms
        self._rise()

    def _rise(self):
        if self.step > 14:
            return self.done()
        for it in self.items:
            try:
                self.layer.cv.move(it, 0, -2)
            except Exception:
                return
        self.step += 1
        self.jobs.append(self.layer.root.after(int(self.ms / 16.0), self._rise))

    def done(self):
        for it in self.items:
            try:
                self.layer.cv.delete(it)
            except Exception:
                pass
        self.items = []

    def stop(self):
        for j in self.jobs:
            try:
                self.layer.root.after_cancel(j)
            except Exception:
                pass
        self.jobs = []
        self.done()


# ---------------------------------------------------------------- 체력바
class HpBar(object):
    """배틀 중에 도트 위에 뜨는 작은 체력바.

    캔버스에 사각형 몇 개로 그린다. 창을 따로 띄우지 않는 이유는,
    포켓몬 창이 이미 '항상 위' 라서 바가 그 아래로 숨을 수 있기 때문이다.
    이펙트 레이어는 배틀 동안 가장 위에 있으므로 여기 그리면 안 가린다.

    체력이 줄면 색이 바뀐다 (초록 -> 노랑 -> 빨강). 본가와 같은 신호다.
    """

    W = 46
    H = 5
    PAD = 1

    def __init__(self, layer, name="", lift=0):
        self.layer = layer
        self.name = name
        self.lift = lift          # 위로 더 띄울 픽셀 (이름표와 안 겹치게)
        self.items = []
        self.ratio = 1.0
        self.shown = 1.0          # 스르륵 줄어드는 표시용 값

    def _color(self, r):
        if r > 0.5:
            return "#4cd964"
        if r > 0.2:
            return "#ffcc33"
        return "#ff4d4d"

    def draw(self, sx, sy):
        """도트의 (가운데 x, 위쪽 y) 를 화면 좌표로 받는다."""
        self.clear()
        cv = self.layer.cv
        x, y = self.layer.to_local(sx, sy)
        w, h, p = self.W, self.H, self.PAD
        x0 = x - w // 2
        y0 = y - h - 8 - self.lift
        # 테두리 겸 바탕
        self.items.append(cv.create_rectangle(
            x0 - p, y0 - p, x0 + w + p, y0 + h + p,
            fill="#14161f", outline="#3a4055"))
        fill = int(w * max(0.0, min(1.0, self.shown)))
        if fill > 0:
            self.items.append(cv.create_rectangle(
                x0, y0, x0 + fill, y0 + h,
                fill=self._color(self.shown), outline=""))

    def set(self, hp, maxhp):
        self.ratio = (float(hp) / maxhp) if maxhp else 0.0

    def ease(self):
        """표시값을 실제값 쪽으로 조금씩 옮긴다. 확 줄면 놀라니까."""
        d = self.ratio - self.shown
        if abs(d) < 0.005:
            self.shown = self.ratio
            return False
        self.shown += d * 0.25
        return True

    def clear(self):
        cv = self.layer.cv
        for i in self.items:
            try:
                cv.delete(i)
            except Exception:                              # noqa: BLE001
                pass
        self.items = []
