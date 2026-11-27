# -*- coding: utf-8 -*-
"""숨바꼭질 (시즌 7) - 창 뒤 · 작업표시줄 뒤 · 바탕화면 가장자리에 **진짜로 숨은** 야생 포켓몬 창 하나 (Hider).

흐름 (design-notes/2026-11-27-hide-and-seek.md)
    1. 서버가 풀숲 차례에 가끔 src 'hide' 야생을 준다 (앱이 GET /api/wild?hide=1 로 '보여 줄 수 있다' 고 할 때만).
       공개 전에는 peek {num, form} 만 온다 - 종의 걷는 도트 앞모습 첫 장을 먼저 받아 둔다 (WildController._start_hide)
    2. hide_spots.pick 이 지금 보이는 숨을 자리를 고르고, 그 자리의 **겹침 순서(z-order)** 로 창을 놓는다 -
       창 뒤면 그 창 바로 아래, 작업표시줄이면 그 바로 아래 층, 가장자리면 모든 보통 창 뒤.
       **'항상 위' 가 아니다** - 일하는 창을 덮어 클릭을 가로채지 않는다. Overlay.keep_on_top · PLAT.show_again 은
       창의 _poket_hider 표시를 보고 이 창을 올리지 않는다.
    3. Hider 는 풀숲(GrassPatch)과 같은 모양(x · y · fw · fh · view · center · destroy)이라 WildController.grass 에
       들어가 지금 흐름을 그대로 탄다 - 누르면 reveal, 만료되면 도망.
    4. 찾으면 '찾았다!' + 던져 버리는 도트 하나가 숨은 자리에서 활동 영역 가장자리로 뛰어 들어오고, 거기서
       show_wild(at=가장자리) - 그 뒤로는 평소 야생 (Pet.update 가 영역 안으로 가두므로 뛰는 것은 따로 그린다).

창 크기는 **처음 잡은 그대로** 다 (윈도우 색 열쇠 창은 크기가 바뀌는 순간 통째로 검게 번쩍인다 - platform_base.SpriteView.resize).
꼼지락 · 내밀기 · 따라가기는 그림(보이는 칸)과 창 자리만 바꾼다.
"""
import random
import time
import tkinter as tk

from . import config, sprites
from . import hide_spots as SP
from . import platform_os as PLAT
from . import ui_common as U

TIP = "누군가 숨어 있다!\n눌러서 찾기"
SAY_FOUND = "찾았다!"
SAY_HIDDEN = "숨겨진 특성!"
HINT_PEEK = "어디선가 누가 훔쳐보고 있어…"
HINT_FOUND = "숨바꼭질! 가끔 창 뒤 · 작업표시줄 뒤에 숨어요"
HINT_MISS = "아까 저쪽에 누가 숨어 있었는데…"
HINT_Q = "?"
# 설정 hideHints 의 칸 (한 번씩만 - 순서와 상관없이)
HINT_BIT_PEEK, HINT_BIT_FOUND, HINT_BIT_MISS = 1, 2, 4

OUTLINE = (0xe8, 0xe8, 0xf0)      # 어두운 바탕화면에서도 보이게 얇은 밝은 테
MIN_ALPHA = 0.85                  # '포켓몬 투명도' 가 이보다 흐리면 따르지 않는다 (찾을 수 있어야 한다)
HIDE_TTL = 240                    # 서버 HIDE_TTL 과 같다 (숨은 포켓몬이 떠 있는 초) - 다시 뜰 때 흐른 시간을 셈한다
GOOD = "#7bffa0"
GOLD = "#ffd447"


# ---------------------------------------------------------------- 플랫폼

def age_of(wild):
    """서버가 이 숨은 포켓몬을 낸 지 몇 초 (HIDE_TTL - expiresIn). 모르면 0."""
    try:
        left = float((wild or {}).get("expiresIn"))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(float(HIDE_TTL), float(HIDE_TTL) - left))

def plat(name, default=None):
    """플랫폼 함수 (platform_win / platform_mac / platform_base 의 것). platform_os 가 아직 내보내지 않는 이름은
    고른 모듈(PLAT._M)에서 바로 꺼낸다 - 부를 때마다 찾으므로 검사가 그 모듈의 함수를 바꿔 끼울 수 있다."""
    m = getattr(PLAT, "_M", None)
    fn = getattr(m, name, None) if m is not None else None
    if fn is None:
        fn = getattr(PLAT, name, None)
    return default if fn is None else fn


def os_name():
    n = str(getattr(PLAT, "NAME", ""))
    return "win" if n.endswith("win") else ("mac" if n.endswith("mac") else "other")


def kinds():
    """이 OS 에서 쓸 수 있는 숨는 자리 (맥 Step 0 시험 결과 - platform_mac.HIDE_KINDS). 없으면 숨기지 않는다."""
    return tuple(plat("HIDE_KINDS", ()) or ())


def kinds_at(area):
    """kinds() 가운데 지금 활동 영역의 모니터에서 쓸 수 있는 것. 그 모니터의 DPI 가 시스템 DPI 와 다르면(윈도우 - 모니터마다
    배율이 다름) 작업표시줄 자리만 - 그 모니터의 창 좌표 · 화면 좌표는 물리 픽셀과 어긋나서(가상화 배율) 창 뒤 자리는
    엉뚱한 데 걸리고 가장자리 자리는 덮였는지 못 믿는다 (검토 #3 · #7). 작업표시줄 자리는 작업 영역만 보니 그대로 맞다."""
    ks = kinds()
    try:
        odd = bool(plat("monitor_dpi_mismatch", lambda r: False)(tuple(area)))
    except Exception:                                       # noqa: BLE001
        odd = False
    return tuple(k for k in ks if k == "bar") if odd else ks


def strip_of(spot, wh):
    """그 자리에서 보일 띠 (x1, y1, x2, y2) - 고른 만큼 내밀었을 때."""
    return SP.shown_rect(spot["side"], spot["line"], spot["along"], wh[0], wh[1], spot["peek"])


def desk(ov, windows=True):
    """(활동 영역, 모니터들, 작업 영역들, 창들) - 자리를 고를 때마다 새로 본다. windows=False 면 창 목록은 None
    (작업표시줄 · 가장자리 자리는 1초마다 창 목록까지 읽을 까닭이 없다). 창 목록에는 이 앱의 테두리 있는 창(own) · 남의
    '항상 위' 창(top)도 가리는 창으로 든다 (PLAT.other_windows)."""
    root = ov.root
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    wins = None
    if windows:
        try:
            wins = list(plat("other_windows", lambda: [])() or [])
        except Exception:                                   # noqa: BLE001
            wins = []
    return tuple(ov.area()), list(PLAT.screens(sw, sh)), list(PLAT.screen_works(sw, sh)), wins


def order(kind, win, anchor=None, strip=None):
    """자리 종류대로 겹침 순서를 건다. 됐으면 True. **안 되면 '항상 위' 로 두지 않는다** - 부르는 쪽이 다른 자리를 본다.

    창 뒤 자리는 보일 띠(strip)도 넘긴다 - 맥은 걸고 나서 다른 창이 그 띠를 덮었으면(자식 창 · 시트는 부모 뒤로 간다)
    False 를 돌려준다 (검토 #5)."""
    try:
        if kind == "window":
            return bool(plat("order_just_below", lambda w, a, strip=None: False)(win, anchor, strip=strip))
        if kind == "bar":
            return bool(plat("order_below_bar", lambda w: False)(win))
        return bool(plat("order_above_desktop", lambda w: False)(win))
    except Exception as e:                                  # noqa: BLE001
        config.log("숨바꼭질 겹침 순서를 못 걸었습니다 (%s): %s" % (kind, e))
        return False


# ---------------------------------------------------------------- 그림
def body_image(img, key):
    """도트 한 장 -> 몸에 꼭 맞게 자르고 1px 밝은 테를 두른 RGBA (보통 색 - 특성 · 이로치는 찾은 뒤에 보인다)."""
    from PIL import Image, ImageChops, ImageFilter
    rgba = img if img.mode == "RGBA" else sprites.to_rgba(img.convert("RGB"), key)
    a = rgba.split()[3].point(lambda v: 255 if v >= 128 else 0)
    bb = a.getbbox()
    if not bb:
        return None
    l, t, r, b = bb
    body = rgba.crop((l, t, r, b))
    a = a.crop((l, t, r, b))
    w, h = body.size
    out = Image.new("RGBA", (w + 2, h + 2), (0, 0, 0, 0))
    big = Image.new("L", (w + 2, h + 2), 0)
    big.paste(a, (1, 1))
    ring = ImageChops.subtract(big.filter(ImageFilter.MaxFilter(3)), big)
    out.paste(Image.new("RGBA", out.size, OUTLINE + (255,)), (0, 0), ring)
    solid = body.copy()
    solid.putalpha(a)
    out.paste(solid, (1, 1), solid)
    return out


def load_look(ov, num, walk=None, path=None):
    """찾기 전 모습: 걷는 도트의 앞모습 첫 장 (없으면 배틀 도트 첫 장). 못 만들면 None."""
    s = ov.settings
    sheet, meta = walk or (None, None)
    if sheet and meta:
        try:
            anim = sprites.load_walk(sheet, meta, s["targetHeight"], s["minScale"], max(2.5, s["maxScale"]))
            fr = anim.frames.get(sprites.DOWN) or next(iter(anim.frames.values()), None)
            if fr:
                got = body_image(fr[0], anim.key)
                if got is not None:
                    return got
        except Exception as e:                              # noqa: BLE001
            config.log("숨은 포켓몬 걷는 도트를 못 읽었습니다 (%s): %s" % (num, e))
    if path:
        try:
            anim = sprites.load_battle_walker(path, s["targetHeight"], s["minScale"], s["maxScale"])
            fr = anim.frames.get(sprites.RIGHT) or next(iter(anim.frames.values()), None)
            if fr:
                return body_image(fr[0], anim.key)
        except Exception as e:                              # noqa: BLE001
            config.log("숨은 포켓몬 도트를 못 읽었습니다 (%s): %s" % (num, e))
    return None


def edge_point(area, margin, rect, w, h):
    """숨은 자리(rect)에서 가장 가까운 활동 영역 가장자리의 발 자리 (x, y) - 찾은 포켓몬이 뛰어 들어오는 곳."""
    x1, y1, x2, y2 = area
    cx, cy = (rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0
    lo_x, hi_x = x1 + margin + w / 2.0, x2 - margin - w / 2.0
    lo_y, hi_y = y1 + margin + h, y2 - margin
    fx = max(lo_x, min(hi_x, cx)) if hi_x >= lo_x else (x1 + x2) / 2.0
    fy = max(lo_y, min(hi_y, cy + h / 2.0)) if hi_y >= lo_y else y2
    return int(round(fx)), int(round(fy))


# ---------------------------------------------------------------- 숨은 포켓몬 창
class Hider(object):
    """숨은 야생 포켓몬 창 하나. WildController.grass 자리에 들어간다 (GrassPatch 와 같은 모양)."""

    is_hider = True
    TICK_MS = 100              # 맥 클릭 판정 · 움직임
    FOLLOW_TICKS = 10          # 1초마다 창을 다시 본다 (따라가기 · 겹침 순서)
    SLIDE_S = 0.6              # 스르륵 나오기
    STILL_S = 30.0             # 그동안은 가만
    WIGGLE_GAP = (10.0, 14.0)  # 30~180초는 이 간격으로 꼼지락
    LATE_S = 180.0
    LATE_GAP = 6.0             # 180~240초는 6초마다
    END_S = 240.0
    WIGGLE_PX = 3
    WIGGLE_S = 0.4
    MORE_AT = 200.0            # 이쯤 한 번 몸을 더 내민다 (70%)
    MORE_S = 1.5

    def __init__(self, ctl, wild, body, spot, rng=None):
        self.ctl = ctl
        self.wild = wild
        self.body = body
        self.rng = rng or random.Random()
        self.spot = spot
        self.dead = False
        self.moving = False        # 걸어 둔 창이 움직이는 중 - 숨긴다
        self.lost = False          # 숨을 자리가 없다 - 숨긴 채로 1초마다 다시 본다
        self.errors = 0
        self._job = None
        self._leap = None
        self._n = 0
        self._last_rect = spot.get("arect")
        self._cache = {}
        self.t0 = time.time()
        self._shown_at = self.t0   # 마지막으로 (다시) 나타난 때 - 다른 자리로 옮기면 거기서 다시 스르륵
        self._wiggles = self._wiggle_times()
        ov = ctl.app.overlay
        self.key = tuple(ov.key)
        self.bw, self.bh = body.size
        self.p = 0
        self.wx = self.wy = 0
        self.x = self.y = self.fw = self.fh = 0
        self.win = tk.Toplevel(ov.root)
        self.win.overrideredirect(True)
        # 표시를 먼저 단다 - 만드는 동안(raise_above) · 긴급 숨기기를 되돌릴 때(show_again) · 3초마다(keep_on_top)
        # 이 창을 '항상 위' 로 올리지 않는다
        self.win._poket_hider = True
        self.win._poket_reorder = self.reorder
        bg = PLAT.transparent_window(self.win, "#%02x%02x%02x" % self.key)
        self.view = PLAT.SpriteView(self.win, bg, self.bw, self.bh, cursor="hand2")
        self.view.exact_hit = True        # 맥: 지금 보이는 몸만 클릭을 받는다 (안 그린 자리는 밑의 창으로)
        self.label = self.view.widget
        self.label.bind("<Button-1>", lambda e: ctl.on_grass_click())
        self.label.bind("<Enter>", lambda e: ctl.show_hint(self, TIP))
        self.label.bind("<Leave>", lambda e: ctl.hide_hint())
        a = config.pet_alpha(ov.settings)
        if MIN_ALPHA <= a < 1.0:
            try:
                self.win.attributes("-alpha", a)
            except Exception:                               # noqa: BLE001
                pass
        self._apply(0)             # 아무것도 안 보이는 채로 자리 · 겹침 순서부터
        try:
            self.win.update_idletasks()    # 창을 화면에 올려 둔다 - 안 올린 창에는 겹침 순서를 걸 수 없다 (윈도우)
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------------------------------------------------------- 만들기
    @classmethod
    def make(cls, ctl, wild, body, rng=None):
        """자리를 골라 띄운다. 숨을 자리가 없거나 이 OS 가 겹침 순서를 못 걸면 None (부르는 쪽이 풀숲으로 띄운다).

        겹침 순서가 안 되는 종류는 빼고 다시 고른다 - **'항상 위' 로 돌아가지 않는다**."""
        rng = rng or random.Random()
        allowed = None
        ov = ctl.app.overlay
        self = None
        while allowed is None or allowed:
            area, screens, works, wins = desk(ov)
            if allowed is None:
                allowed = list(kinds_at(area))       # 배율이 다른 모니터면 작업표시줄 자리만 (검토 #3 · #7)
                if not allowed:
                    break
            spot = SP.pick(area, screens, works, wins, body.size, os_name(), rng, kinds=tuple(allowed))
            if spot is None:
                break
            if self is None:
                self = cls(ctl, wild, body, spot, rng)
            else:
                self.spot, self._last_rect = spot, spot.get("arect")
                self._apply(0)
            if order(spot["kind"], self.win, spot.get("anchor"), strip_of(spot, body.size)):
                # 시계는 서버 기준으로: 공습 · 집중 뒤에 같은 행이 다시 뜨면 이미 흐른 만큼을 빼고 시작한다 - 안 그러면
                # 200초 '더 내밀기' · 60초 안내가 다시 처음부터라 남은 시간 안에 못 온다 (실제 앱 시험 11/27)
                self._shown_at = time.time()
                self.t0 = self._shown_at - age_of(wild)
                self._job = ov.root.after(self.TICK_MS, self._tick)
                return self
            config.log("숨바꼭질: '%s' 자리에 겹침 순서를 못 걸었거나 걸고 보니 가려져서 뺍니다" % spot["kind"])
            allowed.remove(spot["kind"])
        if self is not None:
            self.destroy()
        return None

    # ---------------------------------------------------------------- 그림 · 자리
    def length(self):
        return SP.body_len(self.spot["side"], self.bw, self.bh)

    def _frame(self, side, p):
        k = (side, p)
        got = self._cache.get(k)
        if got is not None:
            return got
        from PIL import Image
        src = self.body
        if side == "bottom":
            src = src.transpose(Image.FLIP_TOP_BOTTOM)     # 위에서 아래로 - 머리부터 내민다
        _x, _y, crop = SP.place(side, 0, 0, self.bw, self.bh, p)
        canvas = Image.new("RGBA", (self.bw, self.bh), (0, 0, 0, 0))
        if crop[2] > crop[0] and crop[3] > crop[1]:
            canvas.paste(src.crop(crop), (crop[0], crop[1]))
        flat = sprites.flatten_rgba(sprites.premultiply(canvas), self.key)
        got = self.view.frames([flat], self.key)[0]
        self._cache[k] = got
        return got

    def _apply(self, p):
        """보이는 픽셀 p 로: 창 자리와 그림만 바꾼다 (**크기는 그대로**)."""
        s = self.spot
        p = max(0, min(int(p), self.length()))
        wx, wy, crop = SP.place(s["side"], s["line"], s["along"], self.bw, self.bh, p)
        self.p = p
        self.wx, self.wy = int(wx), int(wy)
        self.x, self.y = self.wx + crop[0], self.wy + crop[1]
        self.fw, self.fh = crop[2] - crop[0], crop[3] - crop[1]
        try:
            self.win.geometry("+%d+%d" % (self.wx, self.wy))
            self.view.show(self._frame(s["side"], p))
        except Exception as e:                              # noqa: BLE001
            self.errors += 1
            config.log("숨은 포켓몬 그리기 오류: %s" % e)

    def center(self):
        return self.x + self.fw // 2, self.y + self.fh // 2

    def sprite_rect(self):
        """몸 전체가 놓인 칸 (가려진 쪽까지) - 찾았을 때 뛰어나오는 자리."""
        return (self.wx, self.wy, self.wx + self.bw, self.wy + self.bh)

    def tip_at(self, tw, th):
        """마우스 올림 글 자리 (보이는 칸 바깥, 화면 쪽으로). 위에서 아래로 내밀면 아래에, 아니면 위에."""
        cx = self.x + self.fw // 2 - tw // 2
        if self.spot["side"] == "bottom":
            return cx, self.y + self.fh + 4
        if self.spot["side"] == "left":
            return self.x - tw - 4, self.y + self.fh // 2 - th // 2
        if self.spot["side"] == "right":
            return self.x + self.fw + 4, self.y + self.fh // 2 - th // 2
        return cx, self.y - th - 4

    # ---------------------------------------------------------------- 움직임
    def _wiggle_times(self):
        out, t = [], self.STILL_S
        while True:
            t += self.rng.uniform(*self.WIGGLE_GAP)
            if t >= self.LATE_S:
                break
            out.append(t)
        t = self.LATE_S
        while t < self.END_S:
            out.append(t)
            t += self.LATE_GAP
        return out

    def want(self, t, since=None):
        """나온 지 t 초에 보일 픽셀. since 는 지금 자리에 (다시) 나타난 지 몇 초 - 그동안은 스르륵 (없으면 t)."""
        if self.moving or self.lost or self.spot is None:
            return 0
        base = int(self.spot["peek"])
        s = t if since is None else since
        if s < self.SLIDE_S:
            return int(base * max(0.0, s) / self.SLIDE_S)
        if self.MORE_AT <= t < self.MORE_AT + self.MORE_S:
            return SP.more_px(self.length(), base)
        if any(w <= t < w + self.WIGGLE_S for w in self._wiggles):
            return min(self.length(), base + self.WIGGLE_PX)
        return base

    def _tick(self):
        self._job = None
        if self.dead:
            return
        try:
            now = time.time()
            p = self.want(now - self.t0, now - self._shown_at)
            if p != self.p:
                self._apply(p)
            self._n += 1
            if self._n % self.FOLLOW_TICKS == 0:
                self.follow()
            if PLAT.NEEDS_HIT_TRACKING:
                # 몸 둘레의 빈 자리가 밑의 클릭을 먹지 않게 (맥 - GrassPatch.animate 와 같다)
                cx, cy = self.ctl.app.root.winfo_pointerxy()
                self.view.update_hit(cx - self.wx, cy - self.wy)
        except Exception as e:                              # noqa: BLE001
            if not self.errors:
                import traceback
                config.log("숨은 포켓몬 틱 오류: %s\n%s" % (e, traceback.format_exc()))
            self.errors += 1
        if not self.dead:
            self._job = self.ctl.app.root.after(self.TICK_MS, self._tick)

    def _can_order(self):
        """지금 겹침 순서를 걸어도 되나 - 숨긴 창(긴급 숨기기)에 걸면 맥은 창이 도로 화면에 뜬다 (Step 0 시험)."""
        try:
            from . import stealth
            if stealth.active():
                return False
            return bool(self.win.winfo_viewable())
        except Exception:                                   # noqa: BLE001
            return False

    def reorder(self):
        """겹침 순서를 다시 건다 (1초마다 · 긴급 숨기기에서 돌아올 때 PLAT.show_again 이 부른다)."""
        if self.dead or self.spot is None or not self._can_order():
            return False
        # 창 뒤 자리는 띠를 같이 넘긴다 - 맥은 앞에 다른 창이 와서 덮으면 False 를 주지만 여기서는 안 본다 (쫓아다니지
        # 않는다 - follow 의 설명). 덮였나는 자리를 처음 걸 때(make · repick)만 본다
        return order(self.spot["kind"], self.win, self.spot.get("anchor"), strip_of(self.spot, (self.bw, self.bh)))

    def follow(self):
        """1초마다: 창 뒤 자리는 그 창을 따라간다 (움직이는 동안은 숨긴다), 사라지면 다른 자리로. 겹침 순서도 다시 건다."""
        if self.dead:
            return
        ov = self.ctl.app.overlay
        s = self.spot
        area, screens, works, wins = desk(ov, windows=self.lost or s is None or s["kind"] == "window")
        if self.lost or s is None:
            return self.repick(area, screens, works, wins)
        if s["kind"] not in kinds_at(area):
            # 켜 둔 사이 활동 영역 모니터의 배율이 시스템 DPI 와 달라졌다 - 그 자리 좌표를 못 믿는다 (검토 #3 · #7)
            return self.repick(area, screens, works, wins)
        if s["kind"] == "window":
            cur = next((w for w in wins if w.get("id") == s.get("anchor")), None)
            rect = tuple(cur["rect"]) if cur is not None else None
            if rect is not None and rect != tuple(self._last_rect or ()):
                self._last_rect = rect           # 움직이는(늘리는) 중 - 멈출 때까지 숨긴다
                if not self.moving:
                    self.moving = True
                    self._apply(0)
                return
            new = SP.follow(s, wins, area, screens, works, (self.bw, self.bh))
            if new is None:
                return self.repick(area, screens, works, wins)
            if self.moving or new != s:
                self.spot = new
                if self.moving:
                    self.moving = False
                    self._shown_at = time.time()     # 창이 멈췄다 - 새 자리에서 다시 스르륵
                self._apply(self.want(time.time() - self.t0, time.time() - self._shown_at))
        elif not SP.still_ok(s, area, screens, works, (self.bw, self.bh)):
            # 영역이 다른 모니터로 감 · 작업표시줄을 옮기거나 숨김 · 영역을 다시 그림 · 해상도 - 다른 자리로
            return self.repick(area, screens, works, None)
        self.reorder()

    def repick(self, area=None, screens=None, works=None, wins=None):
        """다른 자리로 (걸어 둔 창이 닫힘 · 내림 · 최대화 · 자리가 규칙에 안 맞게 됨). 없으면 숨긴 채 다음에 다시 본다."""
        if area is None or wins is None:
            area, screens, works, wins = desk(self.ctl.app.overlay)
        allowed = list(kinds_at(area))
        while allowed:
            spot = SP.pick(area, screens, works, wins, (self.bw, self.bh), os_name(), self.rng, kinds=tuple(allowed))
            if spot is None:
                break
            self.spot, self._last_rect = spot, spot.get("arect")
            self.moving = self.lost = False
            self._apply(0)
            if not self._can_order() or order(spot["kind"], self.win, spot.get("anchor"),
                                              strip_of(spot, (self.bw, self.bh))):
                self._shown_at = time.time()             # 새 자리에서 다시 스르륵 (틱이 내민다)
                return True
            allowed.remove(spot["kind"])
        self.lost = True
        self._apply(0)
        return False

    # ---------------------------------------------------------------- 찾음
    def leap(self, target, then):
        """찾았다 - 숨은 창을 걷고, 던져 버리는 도트 하나가 숨은 자리에서 target(발 자리)으로 뛰어 들어간다. 다 오면 then()."""
        root = self.ctl.app.root
        x0, y0 = self.wx, self.wy
        self._stop()
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        tx, ty = target[0] - self.bw / 2.0, target[1] - self.bh
        try:
            w = tk.Toplevel(root)
            w.overrideredirect(True)
            bg = PLAT.transparent_window(w, "#%02x%02x%02x" % self.key)
            view = PLAT.SpriteView(w, bg, self.bw, self.bh)
            flat = sprites.flatten_rgba(sprites.premultiply(self.body), self.key)
            ph = view.frames([flat], self.key)[0]
            view.show(ph)
            w.geometry("+%d+%d" % (x0, y0))
            PLAT.raise_above(w)
            self._leap = (w, view, ph)
        except Exception as e:                              # noqa: BLE001
            config.log("찾은 포켓몬 뛰기 연출 실패: %s" % e)
            self._leap = None
            return then()
        n = 12

        def step(k):
            self._job = None
            if self.dead or self._leap is None:
                return
            t = k / float(n)
            x = x0 + (tx - x0) * t
            y = y0 + (ty - y0) * t - 46 * 4 * t * (1 - t)
            try:
                self._leap[0].geometry("+%d+%d" % (int(x), int(y)))
            except Exception:                               # noqa: BLE001
                pass
            if k < n:
                self._job = root.after(28, lambda: step(k + 1))
                return
            self.destroy()
            then()
        step(0)

    # ---------------------------------------------------------------- 정리
    def _stop(self):
        if self._job is not None:
            try:
                self.ctl.app.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None

    def destroy(self):
        self.dead = True
        self._stop()
        lp, self._leap = self._leap, None
        if lp is not None:
            try:
                lp[0].destroy()
            except Exception:                               # noqa: BLE001
                pass
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass


class Say(object):
    """숨은 자리에 잠깐 뜨는 글 ('찾았다!') - 활동 영역 밖이라 이펙트 층(app.float_at)이 안 닿는다."""

    def __init__(self, root, text, at, color=GOOD, ms=1400):
        """at(폭, 높이) -> 글 창 왼쪽 위 (Hider.tip_at - 보이는 칸 바깥 화면 쪽)."""
        self.root = root
        self.text = text
        self.win = w = tk.Toplevel(root)
        w.overrideredirect(True)
        w.configure(bg=U.TIP_BG)
        tk.Label(w, text=text, bg=U.TIP_BG, fg=color, font=U.FONT_TIP, padx=7, pady=2).pack()
        w.update_idletasks()
        x, y = at(w.winfo_width(), w.winfo_height())
        w.geometry("+%d+%d" % (int(x), int(y)))
        PLAT.raise_above(w)
        self._job = root.after(ms, self.close)

    def close(self):
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
