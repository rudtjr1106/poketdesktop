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


def screen_origin(root):
    """모니터 전부를 아우르는 사각형의 왼쪽 위 (x, y). 주 화면 왼쪽 · 위에 둔 화면이 있으면 음수다.

    화면 안으로 창 자리를 맞출 때 **0 이 아니라 이것으로** 자른다 - 0 으로 자르면 왼쪽 모니터에
    있어야 할 것이 주 화면 왼쪽 끝으로 끌려가거나 안 보인다 (게시판 #268).
    """
    try:
        x1, y1, _x2, _y2 = PLAT.virtual_screen(root.winfo_screenwidth(), root.winfo_screenheight())
        return int(x1), int(y1)
    except Exception:                                       # noqa: BLE001
        return 0, 0


def set_alpha(win, alpha):
    """테두리 없는 창 전체를 alpha 만큼 비치게 (1.0 · None 이면 손대지 않는다 - 예전과 똑같은 창). 바꿨으면 True."""
    if alpha is None or alpha >= 1.0:
        return False
    try:
        win.attributes("-alpha", max(0.01, float(alpha)))
        return True
    except Exception:                                       # noqa: BLE001
        return False


def open_layer(root, area, alpha=None):
    """이펙트 레이어를 연다. 클릭이 통과하지 않으면 None 을 돌려준다.

    alpha: 레이어 전체(기술 연출 · 글씨 · 체력바)를 이만큼 비치게 한다 - 공습이 '포켓몬 투명도' 를 따른다.
    None 이나 1.0 이면 예전 그대로 (야생 · 투기장 배틀은 글을 읽으라고 또렷하게 둔다).
    """
    try:
        layer = FxLayer(root, area, alpha)
    except Exception:                                       # noqa: BLE001
        return None
    if not layer.click_through:
        config.log("이펙트 레이어: 클릭 통과를 못 걸어서 띄우지 않습니다")
        layer.destroy()
        return None
    return layer


class FxLayer(object):
    """이펙트를 그리는 캔버스. 좌표는 화면 좌표로 주고받는다."""

    def __init__(self, root, area, alpha=None):
        self.root = root
        x1, y1, x2, y2 = area
        # 이펙트가 활동 영역 밖으로 조금 튀어도 잘리지 않게 넉넉히
        pad = 90
        # **0 이 아니라 모니터 전부의 왼쪽 위에서 자른다** (게시판 #268, 듀얼 모니터). 주 화면 왼쪽(위)에 둔
        # 화면은 좌표가 음수다. 예전에는 max(0, …) 이라 레이어가 주 화면 쪽으로 밀려나서, 왼쪽 화면의 포켓몬
        # 위에 그리는 체력바 · '지금 던지세요' · 기술 이펙트 · 실시간 배틀 이름표가 레이어 밖이라 안 보였다.
        vx, vy = screen_origin(root)
        self.x = max(vx, x1 - pad)
        self.y = max(vy, y1 - pad)
        # 영역이 모니터 전부의 밖일 수도 있다 - 왼쪽 모니터를 뺀 직후 2초 동안은 영역을 기억해 둔 옛 자리
        # (Overlay._drawn_area)가 남는다. 그때 폭이 0 아래가 되면 geometry 가 터진다. 1 로 막는다.
        w = max(1, int((x2 + pad) - self.x))
        h = max(1, int((y2 + pad) - self.y))

        self.win = tk.Toplevel(root)
        # 3초마다 도는 Overlay.keep_on_top 이 이 창을 늘 도트 창들 바로 위로 올린다 (11/27 게시판 #1002 -
        # 윈도우에서 레이어보다 나중에 생긴 도트가 체력바 · 글씨를 덮었다)
        self.win._poket_over = True
        try:
            self.win.overrideredirect(True)
            bg = PLAT.transparent_window(self.win, KEY)
            self.win.geometry("%dx%d+%d+%d" % (w, h, self.x, self.y))
            # 여기는 도트(그림)가 아니라 선과 글자만 그린다. 맥에서도 캔버스
            # 벡터는 투명 배경 위에 그대로 그려지므로 Canvas 를 그냥 쓴다.
            self.cv = tk.Canvas(self.win, width=w, height=h, bg=bg,
                                highlightthickness=0, bd=0)
            self.cv.pack()
        except Exception:
            # 만들다 만 창을 남기지 않는다 - 투명한 빈 창이 화면에 떠서 클릭을 먹는다 (open_layer 는 None 을 준다)
            self.destroy()
            raise
        # 투명도는 클릭 통과보다 **먼저** 건다 - 윈도우는 -alpha 를 걸 때 창 모양을 다시 걸면서 클릭 통과가
        # 풀릴 수 있다 (deco_fx)
        self.alpha = alpha if set_alpha(self.win, alpha) else 1.0
        PLAT.raise_above(self.win)
        self.click_through = make_click_through(self.win)
        # 지금 떠 있는 짧은 글씨들. 새로 뜨는 것이 겹치지 않게 이걸 본다
        # (FloatText).
        self.floats = []

    def to_local(self, sx, sy):
        """화면 좌표 -> 이 캔버스 좌표."""
        return sx - self.x, sy - self.y

    def keep_alive(self):
        """맥에서 풀린 클릭 통과만 다시 건다. **창 순서는 건드리지 않는다.**

        체력바 틱이 몇 프레임마다 부른다. 순서를 올리는 일은 raise_above 가
        따로 맡는다 - 그 둘을 한 함수에 두었던 것이 메뉴 위로 체력바가
        올라오던 원인이었다.
        """
        try:
            PLAT.keep_click_through(self.win)
        except Exception:                                   # noqa: BLE001
            pass

    def raise_above(self):
        """레이어를 '항상 위' 무리의 맨 위로 올린다.

        **새 창이 생긴 직후에만 부른다** (상대 도트 입장, 교체로 다시
        보이는 도트). 시간에 맞춰 되풀이해 부르면 안 된다 - 예전에는
        체력바 틱이 0.5초마다 불렀는데, 볼 고르는 메뉴가 떠 있는 동안에도
        레이어가 계속 맨 위로 올라와서 메뉴 위에 체력바가 찍혔다. 도트는
        만들 때 한 번만 올리기 때문에 메뉴 뒤로 얌전히 들어갔고, 레이어만
        메뉴를 뚫고 나왔다.
        """
        try:
            PLAT.raise_above(self.win)
            self.win.lift()
            # 맥은 창을 다시 올리거나 숨겼다 켜면 클릭 통과가 풀린다.
            PLAT.keep_click_through(self.win)
        except Exception:
            pass

    def clear(self):
        self.floats = []
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
    """도트 위에 잠깐 떠올랐다 사라지는 짧은 글씨.

    **같은 자리에 겹쳐 띄우지 않는다.** 한 번에 여러 개가 뜨는 자리가
    많다 - 배틀이 끝나면 '+120 exp' 와 주운 도구가 같이 뜨고, 한 방에
    '급소!', '효과가 굉장하다!', '-38' 이 한꺼번에 뜬다. 그동안은 셋 다
    같은 좌표에서 시작해서 글씨가 포개져 아무것도 못 읽었다.

    아직 떠 있는 글씨가 근처에 있으면 그만큼 아래에서 시작한다. 올라가는
    속도가 같으니 간격이 그대로 유지된다.
    """

    GAP = 15                   # 글씨 사이 최소 간격 (px)
    NEAR = 90                  # 이만큼 가로로 가까우면 같은 자리로 본다

    def __init__(self, layer, sx, sy, text, color="#ffffff", ms=900):
        self.layer = layer
        self.sx = sx
        self.step = 0
        live = [t for t in getattr(layer, "floats", None) or [] if t.items]
        # 위에서부터 훑으며 부딪히면 그 아래로 내린다.
        for t in sorted(live, key=lambda t: t.y()):
            if abs(t.sx - sx) < self.NEAR and sy < t.y() + self.GAP:
                sy = t.y() + self.GAP
        self.sy = sy
        x, y = layer.to_local(sx, sy)
        self.items = [
            layer.cv.create_text(x + 1, y + 1, text=text, fill="#101014",
                                 font=(U.FAMILY, U.pt(10), "bold")),
            layer.cv.create_text(x, y, text=text, fill=color,
                                 font=(U.FAMILY, U.pt(10), "bold")),
        ]
        self._keep_inside(layer.cv)
        self.jobs = []
        self.ms = ms
        live.append(self)
        layer.floats = live
        # **첫 올라감은 한 틱 뒤에.** 여기서 바로 부르면 놓자마자 2px 이
        # 올라가 버려서, 방금 계산한 간격이 그만큼 어긋난다.
        self.jobs.append(layer.root.after(int(self.ms / 16.0), self._rise))

    def _keep_inside(self, cv, margin=2):
        """글씨가 캔버스 밖으로 나가면 가로로만 안쪽으로 민다 (1.13.2). 도트 가운데에 맞추므로 화면 끝에 붙은 도트
        위의 긴 글씨('볼을 던지기 전에 쓰러뜨렸다', 게시판 #280)는 앞이나 뒤가 잘렸다. 글꼴은 줄이지 않는다."""
        try:
            w = int(cv.cget("width"))
            boxes = [cv.bbox(i) for i in self.items]
        except Exception:                                   # noqa: BLE001
            return
        boxes = [b for b in boxes if b]
        if not boxes or w <= 0:
            return
        x1, x2 = min(b[0] for b in boxes), max(b[2] for b in boxes)
        dx = (margin - x1) if x1 < margin else (w - margin - x2) if x2 > w - margin else 0
        if dx:
            for i in self.items:
                cv.move(i, dx, 0)

    def y(self):
        """지금 떠 있는 높이 (화면 좌표). _rise 가 한 번에 2px 올린다."""
        return self.sy - 2 * self.step

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
