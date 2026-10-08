# -*- coding: utf-8 -*-
"""배틀 창의 크기 (1.10.3).

관장·레이드·실시간 배틀 창은 크기를 바꿀 수 없었다 (장면을 픽셀로 짜 둔 창이었다). 건의(#148):
"배틀창은 크기 조절이 불가능하더라구요". 이제 **다른 창처럼 가장자리를 끌어서** 크기를 바꾼다 -
창이 커지면 장면·도트·글자·단추가 그만큼 커지고, 줄이면 작아진다. 바꾼 크기는 창 종류마다
기억해서 다음 판도 그 크기로 뜬다 (설정 battleSize).

## 어떻게 하나

세 창은 크기를 전부 ui_common 의 `U.h` · `U.pt` · `U.FONT_*` 로 잡는다. 그래서 창마다 줄줄이
고치지 않고, **그 창들이 쓰는 U 를 배율을 타는 것으로 바꿔 끼운다**:

    from . import battle_zoom as Z
    U = Z.U             # ui_common 그대로인데 h · pt · FONT_* · 단추 높이가 배율(Z.K)을 탄다

글꼴 배율을 안 타는 것(도트 높이처럼 픽셀로 적어 둔 값)은 `Z.px(n)` 으로 잡는다.

창 쪽의 일은 Resizable 이 한다 (세 창이 섞어 쓴다):

  * **배율은 창 크기에서 나온다.** 그 창에 들어가는 가장 큰 배율이다: 폭으로는 `폭 / 설계 폭`,
    높이로는 `높이 / (가장 낮은 장면 + 말풍선 + 명령 칸)`. 둘 중 작은 쪽.
  * **장면이 남는 자리를 다 쓴다.** 창은 사람이 끌어 놓은 크기 그대로다 (비율에 맞춰 도로 튕기지
    않는다). 장면은 창 폭 전체, 높이는 말풍선과 명령 칸을 뺀 나머지. 포켓몬과 이름표는 장면의
    크기를 따라 자리를 잡는다 (원래 그렇게 짜여 있다 - 화면이 낮으면 장면을 줄이던 창이다).
  * **끌기를 멈추면 다시 짓는다.** 끄는 동안 매번 짓지 않는다 (도트를 다시 읽어 키워야 한다).
    장면은 같은 캔버스를 비우고 다시 그리고, 말풍선·명령 칸은 헐고 다시 만든 다음, 창이 들고
    있던 것(지금 나와 있는 포켓몬, 고르던 칸, 마지막 말)으로 되돌린다. 재생 중이면 다음 일부터
    새 장면에 그려진다.

## 글자

줄이면 글자도 작아진다 - 줄인 사람이 정한 것이다. 다만 7pt 아래로는 안 내려가고 (U.pt 와 같은
바닥), 그래서 창도 MIN_K 아래로는 안 줄어든다 (윈도우의 작은 글자 8pt 가 바닥에 걸려 칸을 넘는다).
글자 크기는 **내림**한다: 칸은 0.85 배인데 글자가 반올림으로 0.9 배가 되면 넘친다.

## 창이 둘일 때

배율(K)은 모듈에 하나다. 배틀 창 둘이 다른 크기로 같이 떠 있으면(관장 배틀 중에 실시간 배틀)
그리기 직전에 제 배율을 걸어야 한다 - 창의 큰 길목들이 `zoom_use()` 를 부른다.
"""
import os
import tkinter as tk

from . import platform_os as PLAT
from . import ui_common as _U

MIN_K, MAX_K = 0.8, 1.8
MIN_PT = 7
SNAP = 0.95                 # 이만큼만 모자라면 줄이지 않는다 (화면이 조금 좁은 PC 에서 글자가 한 치 줄지 않게)
SETTLE_MS = 140             # 끌기를 멈춘 뒤 다시 짓기까지
CHROME = 44                 # 제목 막대와 약간의 여백 (화면에 넣을 때 뺀다)

K = 1.0                     # 지금 그리는 창의 배율


def px(n):
    """픽셀로 적어 둔 값(도트 높이처럼 글꼴 배율을 안 타는 것)에 배율을 건다."""
    return int(round(n * K))


def base_h(n):
    """글꼴 배율만 건 높이 (ui_common.h 그대로). **단추의 height 로 넘길 때** 쓴다 - 단추가 배율을
    한 번 걸기 때문에 U.h(...) 를 넘기면 두 번 걸린다."""
    return _U.h(n)


def font(f):
    """글꼴 (모음, 크기, ...) 의 크기에 배율을 건다 (내림, 7pt 바닥)."""
    if K == 1.0 or not isinstance(f, tuple) or len(f) < 2 or not isinstance(f[1], (int, float)):
        return f
    return (f[0], max(MIN_PT, int(f[1] * K + 1e-6))) + tuple(f[2:])


def scale_of(ww, wh, w, h_min):
    """창 크기(ww, wh)에 들어가는 가장 큰 배율. w = 설계 폭, h_min = 장면을 가장 낮게 했을 때의
    높이 (둘 다 글꼴 배율까지 건 px). MIN_K ~ MAX_K 사이로 돌려준다."""
    if w <= 0 or h_min <= 0:
        return 1.0
    k = min(ww / float(w), wh / float(h_min))
    if SNAP <= k < 1.0:
        k = 1.0
    return max(MIN_K, min(MAX_K, k))


def remembered(app, kind):
    """기억해 둔 창 크기 (w, h). 없거나 이상하면 None."""
    try:
        w, h = ((getattr(app, "settings", None) or {}).get("battleSize") or {}).get(kind)
        w, h = int(w), int(h)
    except (TypeError, ValueError):
        return None
    return (w, h) if w > 0 and h > 0 else None


def remember(app, kind, w, h):
    s = getattr(app, "settings", None)
    if s is None:
        return
    sizes = dict(s.get("battleSize") or {})
    if sizes.get(kind) == [int(w), int(h)]:
        return
    sizes[kind] = [int(w), int(h)]
    s["battleSize"] = sizes
    try:
        from . import config
        config.save_settings(s)
    except Exception:                                       # noqa: BLE001
        pass


def forget(app):
    """기억해 둔 크기를 다 지운다 - 다음 배틀 창은 기본 크기로 뜬다 (설정 창의 '기본 크기로')."""
    s = getattr(app, "settings", None)
    if s is None or not s.get("battleSize"):
        return
    s["battleSize"] = {}
    try:
        from . import config
        config.save_settings(s)
    except Exception:                                       # noqa: BLE001
        pass


def button_box(zoom, right):
    """명령 칸 오른쪽 줄의 단추 둘(교체 · 기권)이 들어갈 틀과 놓는 법: (틀, 첫 단추 pack, 둘째 단추 pack, 높이).

    **창을 줄였으면(배율 < 1) 둘을 옆으로 나란히 놓는다.** 그 아래 칸에는 기술 설명이 뜨는데
    (윈도우에서 가장 긴 것이 다섯 줄), 줄인 창에서는 위아래로 쌓은 단추 둘이 자리를 다 먹어
    설명이 잘렸다 - 글자는 7pt 아래로 안 줄고 여백도 그대로라, 창이 작아질수록 그 칸만 좁아진다.
    나란히 놓으면 단추 하나의 높이가 그 칸으로 간다. 줄이지 않은 창은 예전 그대로 (pack 은 None).
    """
    if zoom >= 1.0:
        return right, None, None, None
    row = tk.Frame(right, bg=right["bg"])
    row.pack(fill="x", pady=(px(6), 0))
    side = {"side": "left", "fill": "x", "expand": True}
    return row, dict(side, padx=(0, 3)), dict(side, padx=(3, 0)), 34


class _Zoomed(object):
    """ui_common 그대로인데 **크기에 관한 것만** 배율을 탄다. 배틀 창이 U 대신 쓴다."""

    def __getattr__(self, name):
        v = getattr(_U, name)
        if name.startswith("FONT"):
            return font(v)                   # FONT · FONT_B · FONT_S · FONT_XS · FONT_H · FONT_BTN ...
        return v

    def h(self, n):
        return int(round(_U.h(n) * K))

    def pt(self, n):
        return max(MIN_PT, int(_U.pt(n) * K + 1e-6)) if K != 1.0 else _U.pt(n)

    # 단추: 높이는 숫자로 받고 글꼴은 안에서 정한다 - 둘 다 여기서 배율을 건다
    def PushButton(self, parent, text, command=None, **kw):
        kw["height"] = px(kw.get("height", 40))
        kw["font"] = font(kw.get("font") or _U.FONT_BTN) if K != 1.0 else kw.get("font")
        return _U.PushButton(parent, text, command, **kw)

    def ghost_button(self, parent, text, command=None, height=36, fg=None, fill=None):
        if K == 1.0:
            return _U.ghost_button(parent, text, command, height=height,
                                   fg=_U.FG if fg is None else fg, fill=_U.BG3 if fill is None else fill)
        return _U.PushButton(parent, text, command, fill=_U.BG3 if fill is None else fill,
                             fg=_U.FG if fg is None else fg, shadow="#171c2b", hover=_U.BG4,
                             height=px(height), font=font(_U.FONT_S), border=_U.LINE2)


U = _Zoomed()


class Resizable(object):
    """배틀 창이 섞어 쓰는 것: 가장자리를 끌어서 크기를 바꾼다.

    창이 정해 둘 것 (설계 크기 - U.h 에 넣는 숫자):

        ZOOM_KIND                  기억해 둘 이름 ('gym' · 'live' · 'raid')
        ZOOM_W                     폭
        ZOOM_SCENE, ZOOM_MSG, ZOOM_CMD      장면 · 말풍선 · 명령 칸의 높이
        ZOOM_MIN_SCENE             장면을 가장 낮게 했을 때

    창이 갖출 것: app · root · win · alive · mega, 그리고

        _scene()        장면을 그린다. **self.cv 가 이미 있으면 그 캔버스를 비우고 다시 그린다**
                        (새로 만들지 않는다 - 돌고 있던 연출이 없어진 캔버스를 건드리지 않게).
                        크기는 self.ww · self.scene_h 를 쓴다.
        _message()      말풍선 줄. 틀을 self.msg_frame 에 둔다.
        _commands()     명령 칸. 틀을 self.cmd 에 둔다.
        _restore()      다시 지은 화면을 창이 들고 있던 것으로 되돌린다 (나와 있는 포켓몬, 고르던 칸).
        say(text)       마지막 말을 self._said 에 남긴다.

    쓰는 차례 (창의 __init__):

        ww, wh, x, y = self.zoom_open()      # 처음 크기와 자리. 배율을 잡는다
        ... 창을 만들고 geometry 를 건다 ...
        self._scene(); self._message(); self._commands()
        self.zoom_watch()                    # 이제부터 끌면 따라간다
    """

    ZOOM_KIND = ""
    ZOOM_W = ZOOM_SCENE = ZOOM_MSG = ZOOM_CMD = ZOOM_MIN_SCENE = 0
    zoom = 1.0
    _zoom_size = None
    _zoom_job = None
    _said = ""

    # ---- 크기 계산
    def _zoom_base(self):
        """(설계 폭, 설계 높이, 가장 낮은 높이) - 글꼴 배율까지 건 px, 배율 1 일 때."""
        w = _U.h(self.ZOOM_W)
        rest = _U.h(self.ZOOM_MSG) + _U.h(self.ZOOM_CMD) + 4
        return w, _U.h(self.ZOOM_SCENE) + rest, _U.h(self.ZOOM_MIN_SCENE) + rest

    def zoom_min(self):
        """창을 이보다 작게는 못 줄인다 (글자가 7pt 바닥에 걸려 칸을 넘는다)."""
        w, _h, h_min = self._zoom_base()
        return int(w * MIN_K), int(h_min * MIN_K)

    def zoom_layout(self, ww, wh):
        """창 크기에서 배율과 장면의 크기를 정한다 (self.zoom · self.ww · self.scene_h)."""
        global K
        w, _h, h_min = self._zoom_base()
        self.zoom = K = scale_of(ww, wh, w, h_min)
        self.ww = int(ww)
        # 장면은 말풍선과 명령 칸을 뺀 나머지를 다 쓴다
        self.scene_h = max(U.h(60), int(wh) - U.h(self.ZOOM_MSG) - U.h(self.ZOOM_CMD) - 4)
        return self.zoom

    def zoom_use(self):
        """이 창의 배율로 그린다. 배틀 창이 둘 떠 있을 때를 위해 그리기 전의 길목에서 부른다."""
        global K
        K = self.zoom

    def zoom_open(self):
        """처음 뜰 크기와 자리 (ww, wh, x, y). 기억해 둔 크기가 있으면 그것, 없으면 기본 크기.
        화면(독·작업표시줄을 뺀 자리)보다 크게는 안 뜬다."""
        root = self.root
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        try:
            x1, y1, x2, y2 = PLAT.work_area(sw, sh)
        except Exception:                                   # noqa: BLE001
            x1, y1, x2, y2 = 0, 0, sw, sh
        w, h, h_min = self._zoom_base()
        size = remembered(self.app, self.ZOOM_KIND)
        forced = os.environ.get("POKET_BATTLE_ZOOM")        # 검사용: 기본 크기의 몇 배로 띄운다
        if forced:
            try:
                size = (int(w * float(forced)), int(h * float(forced)))
            except ValueError:
                pass
        room_w, room_h = (x2 - x1) - _U.h(16), (y2 - y1) - CHROME
        if size is None:
            # 기본 크기. 화면이 낮으면 장면부터 줄이고(글자 칸은 그대로 - 예전부터 하던 일이다),
            # 가장 낮은 장면으로도 안 들어가면 **통째로 줄인다** (화면 밖으로 나가지 않는다).
            ww, wh = min(w, room_w), min(h, room_h)
        else:
            lo_w, lo_h = self.zoom_min()
            ww = max(lo_w, min(size[0], room_w))
            wh = max(lo_h, min(size[1], room_h))
        self.zoom_layout(ww, wh)
        gx = x1 + max(0, ((x2 - x1) - ww) // 2)
        gy = y1 + max(0, ((y2 - y1) - wh - 30) // 3)
        return int(ww), int(wh), gx, gy

    # ---- 끌어서 바꾸기
    def zoom_watch(self):
        """창을 끌어서 바꿀 수 있게 하고, 바뀌면 따라간다."""
        win = self.win
        try:
            win.resizable(True, True)
            win.minsize(*self.zoom_min())
        except tk.TclError:
            return
        self._zoom_size = (self.ww, self.scene_h + U.h(self.ZOOM_MSG) + U.h(self.ZOOM_CMD) + 4)
        win.bind("<Configure>", self._zoom_configure, add="+")

    def _zoom_configure(self, e):
        if e.widget is not self.win or not self.alive:
            return                           # (안에 든 것들의 Configure 도 여기로 온다)
        if (e.width, e.height) == self._zoom_size:
            return
        if self._zoom_job is not None:
            try:
                self.root.after_cancel(self._zoom_job)
            except Exception:                               # noqa: BLE001
                pass
        self._zoom_job = self.root.after(SETTLE_MS, self.zoom_apply)

    def zoom_apply(self):
        """지금 창 크기에 맞춰 다시 짓는다. 크기가 그대로면 아무것도 안 한다."""
        self._zoom_job = None
        if not self.alive:
            return
        try:
            ww, wh = self.win.winfo_width(), self.win.winfo_height()
        except tk.TclError:
            return
        if (ww, wh) == self._zoom_size or ww <= 1 or wh <= 1:
            return
        self._zoom_size = (ww, wh)
        said = self._said
        mega = getattr(self, "mega", None)
        mega_on = bool(mega is not None and mega.on and mega.shown)
        self._zoom_stop_fx()
        self.zoom_layout(ww, wh)
        try:
            for name in ("msg_frame", "cmd"):
                f = getattr(self, name, None)
                if f is not None:
                    f.destroy()
            self._scene()
            self._message()
            self._commands()
            self._restore()
            if mega_on and self.mega.shown:
                self.mega.set(True)          # 켜 둔 메가진화는 그대로다
            if said:
                self.say(said)
        except tk.TclError:
            return
        remember(self.app, self.ZOOM_KIND, ww, wh)

    def _zoom_stop_fx(self):
        """돌고 있는 기술 연출을 끝낸다 (옛 크기의 자리에 그리던 것이다). 재생은 다음 일로 넘어간다."""
        fx = getattr(self, "fx", None)
        if fx is None:
            return
        try:
            fx.stop()
        except Exception:                                   # noqa: BLE001
            pass
        done = getattr(self, "_fx_done", None)
        if done is not None:
            done()

    def zoom_close(self):
        if self._zoom_job is not None:
            try:
                self.root.after_cancel(self._zoom_job)
            except Exception:                               # noqa: BLE001
                pass
            self._zoom_job = None
