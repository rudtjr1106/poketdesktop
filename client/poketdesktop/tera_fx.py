# -*- coding: utf-8 -*-
"""배틀 창의 테라스탈 연출 (2.5.0).

본가의 테라스탈처럼: 결정 조각이 몸으로 모여들고, 몸이 그 타입 빛깔의 결정에 갇혔다가, 결정이 깨지며
빛이 퍼지고, **그 뒤로는 포켓몬이 결정으로 빛난다** (머리 위에 테라 왕관). 메가진화 연출(ui_mega.MegaFx)과
같은 약속으로 캔버스에 바로 그린다.

  1. 모인다    타입 빛깔 결정 조각 열 개가 소용돌이치며 몸 쪽으로 날아들고, 빛 고리가 조여든다
  2. 갇힌다    면이 나뉜 육각 결정이 몸 위로 자라고, 빛 한 줄기가 결정 위를 스친다 - 다 자라면 on_cover
               (창이 그 순간 도트를 결정 모습으로 바꾼다 - 바뀌는 순간이 결정에 가려진다)
  3. 번쩍인다  하얀 빛이 한 번 터진다
  4. 깨진다    결정의 면들이 돌며 흩어지고, 육각 충격파 두 겹이 퍼지고, 둘레에 반짝임이 남는다

판이 끝날 때까지의 모습은 crystal_frames 가 도트 그림에 입힌다 (결정 질감 + 테두리 빛 + 머리 위 왕관).
배틀 창 셋(관장 · 실시간 · 레이드)의 set_mon 이 mon["tera"] 를 보고 부른다 - 테마도 그 set_mon 을 쓴다.

시간은 창의 later 로 흘린다 (창이 닫히면 같이 멈추고, 검사는 빨리 돌릴 수 있다).
"""
import math
import random
import tkinter as tk

from . import ui_common as U

GATHER_STEPS = 11
GATHER_MS = 38
COVER_STEPS = 8
COVER_MS = 36
FLASH_STEPS = 3
FLASH_MS = 45
BREAK_STEPS = 14
BREAK_MS = 38
LIGHT = math.radians(135)      # 빛이 오는 쪽 (왼쪽 위) - 결정 면의 밝기를 정한다


def _mix(color, other, t):
    """color 를 other 쪽으로 t 만큼 섞은 색."""
    try:
        a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    except (TypeError, ValueError):
        return color
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def hexagon(cx, cy, r):
    """뾰족한 쪽이 위인 육각형의 꼭짓점 (세로로 조금 길다 - 결정처럼 보이게)."""
    pts = []
    for k in range(6):
        a = math.pi / 2 + k * math.pi / 3
        pts += [cx + math.cos(a) * r, cy - math.sin(a) * r * 1.15]
    return pts


def _corners(cx, cy, r):
    p = hexagon(cx, cy, r)
    return [(p[i], p[i + 1]) for i in range(0, 12, 2)]


def _star(cx, cy, r):
    """네 갈래 반짝임."""
    q = r * 0.28
    return [cx, cy - r, cx + q, cy - q, cx + r, cy, cx + q, cy + q,
            cx, cy + r, cx - q, cy + q, cx - r, cy, cx - q, cy - q]


def _shade(color, ang):
    """면의 바깥쪽 방향(ang)에 따라 밝게 · 어둡게 (빛은 왼쪽 위에서)."""
    lit = 0.5 + 0.5 * math.cos(ang - LIGHT)
    if lit >= 0.5:
        return _mix(color, "#ffffff", 0.25 + 0.55 * (lit - 0.5) * 2)
    return _mix(color, "#000000", 0.08 + 0.42 * (0.5 - lit) * 2)


def _rot(pts, cx, cy, a):
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for x, y in pts:
        dx, dy = x - cx, y - cy
        out += [cx + dx * ca - dy * sa, cy + dx * sa + dy * ca]
    return out


class TeraFx(object):
    """캔버스 위의 테라스탈 연출 한 번.

        fx = TeraFx(cv, (x, y), later, color, on_cover=..., on_done=...)
        fx.play()

    on_cover 는 결정이 몸을 다 덮은 순간 한 번, on_done 은 끝나면 한 번. 창을 닫을 때는 stop().
    """

    def __init__(self, cv, center, later, color, on_cover=None, on_done=None, size=None):
        self.cv = cv
        self.cx, self.cy = center
        self.later = later
        self.color = color or "#9bd7ff"
        self.lite = _mix(self.color, "#ffffff", 0.6)
        self.glow = _mix(self.color, "#ffffff", 0.82)
        self.deep = _mix(self.color, "#000000", 0.45)
        self.on_cover = on_cover
        self.on_done = on_done
        self.size = float(size or U.h(64))
        self.items = []
        self.dead = False
        self._covered = False
        self.rng = random.Random(int(self.cx * 7 + self.cy * 13))

    # ---- 도구 ----
    def _add(self, item):
        self.items.append(item)
        return item

    def _kill(self, item):
        try:
            self.cv.delete(item)
        except tk.TclError:
            pass
        if item in self.items:
            self.items.remove(item)

    def _ok(self):
        if self.dead:
            return False
        try:
            return bool(self.cv.winfo_exists())
        except tk.TclError:
            return False

    def play(self):
        try:
            shards = []
            for k in range(10):
                a = 2 * math.pi * k / 10 + 0.35
                hi = self._add(self.cv.create_polygon(0, 0, 0, 0, 0, 0, fill=self.glow, outline=""))
                lo = self._add(self.cv.create_polygon(0, 0, 0, 0, 0, 0, fill=self.color if k % 2 else self.deep,
                                                      outline=""))
                spark = self._add(self.cv.create_polygon(*_star(0, 0, 1), fill="#ffffff", outline=""))
                shards.append((hi, lo, spark, a, 1.0 + 0.25 * (k % 3)))
            ring = self._add(self.cv.create_oval(0, 0, 0, 0, outline=self.lite, width=3))
            self._gather(0, shards, ring)
        except tk.TclError:
            self._finish()
        return self

    # ---- 1. 모인다 ----
    def _gather(self, i, shards, ring):
        if not self._ok():
            return self._finish()
        if i >= GATHER_STEPS:
            for hi, lo, spark, _a, _f in shards:
                self._kill(hi)
                self._kill(lo)
                self._kill(spark)
            self._kill(ring)
            return self._cover(0)
        t = i / float(GATHER_STEPS - 1)
        try:
            rr = self.size * (2.3 - 1.4 * t)
            self.cv.coords(ring, self.cx - rr, self.cy - rr * 1.1, self.cx + rr, self.cy + rr * 1.1)
            self.cv.itemconfigure(ring, width=max(1, int(5 * t) + 1),
                                  outline=_mix(self.lite, "#ffffff", t))
            self.cv.tag_raise(ring)
            for hi, lo, spark, a, far in shards:
                ang = a + t * 2.4                                        # 소용돌이
                dist = self.size * 2.2 * far * (1.0 - t) ** 1.25 + U.h(6)
                x = self.cx + math.cos(ang) * dist
                y = self.cy + math.sin(ang) * dist * 0.85
                r = U.h(9) * (1.0 - 0.35 * t)
                # 날아드는 쪽으로 긴 마름모 - 빛 받는 반쪽과 그늘 반쪽
                dx, dy = math.cos(ang), math.sin(ang)
                tip_out = (x + dx * r * 1.9, y + dy * r * 1.9)
                tip_in = (x - dx * r * 1.9, y - dy * r * 1.9)
                side1 = (x - dy * r * 0.65, y + dx * r * 0.65)
                side2 = (x + dy * r * 0.65, y - dx * r * 0.65)
                self.cv.coords(hi, *(tip_out + side1 + tip_in))
                self.cv.coords(lo, *(tip_out + side2 + tip_in))
                sr = U.h(3 + 3 * ((i + int(far * 4)) % 3 == 0))
                self.cv.coords(spark, *_star(x + dx * r * 2.6, y + dy * r * 2.6, sr))
                for it in (lo, hi, spark):
                    self.cv.tag_raise(it)
        except tk.TclError:
            return self._finish()
        self.later(GATHER_MS, lambda: self._gather(i + 1, shards, ring))

    # ---- 2. 갇힌다 ----
    def _crystal(self, r):
        """면이 나뉜 육각 결정을 그린다 - 바깥 면 여섯 + 위 면(작은 육각) + 흰 테. 그린 항목들을 돌려준다."""
        out = []
        cs = _corners(self.cx, self.cy, r)
        for k in range(6):
            a, b = cs[k], cs[(k + 1) % 6]
            ang = math.atan2(-((a[1] + b[1]) / 2 - self.cy), (a[0] + b[0]) / 2 - self.cx)
            out.append(self._add(self.cv.create_polygon(self.cx, self.cy, a[0], a[1], b[0], b[1],
                                                        fill=_shade(self.color, ang), outline="")))
        out.append(self._add(self.cv.create_polygon(*hexagon(self.cx, self.cy - r * 0.08, r * 0.46),
                                                    fill=self.glow, outline="#ffffff", width=1)))
        out.append(self._add(self.cv.create_polygon(*hexagon(self.cx, self.cy, r), fill="",
                                                    outline="#ffffff", width=2)))
        return out

    def _cover(self, i, parts=None, glint=None):
        if not self._ok():
            return self._finish()
        try:
            for it in parts or ():
                self._kill(it)
            t = (i + 1) / float(COVER_STEPS)
            r = self.size * (0.35 + 0.9 * t ** 0.8)              # 다 자라면 날개를 편 도트까지 덮는다
            parts = self._crystal(r)
            # 빛 한 줄기가 결정 위를 왼쪽 아래에서 오른쪽 위로 스친다 (뒤의 절반)
            if glint is not None:
                self._kill(glint)
                glint = None
            if i >= COVER_STEPS // 2:
                g = (i - COVER_STEPS // 2 + 1) / float(COVER_STEPS - COVER_STEPS // 2)
                gx = self.cx + (g - 0.5) * r * 1.3
                w = r * 0.13
                h = r * 0.7
                glint = self._add(self.cv.create_polygon(gx - w - h * 0.5, self.cy + h, gx + w - h * 0.5, self.cy + h,
                                                         gx + w + h * 0.5, self.cy - h, gx - w + h * 0.5, self.cy - h,
                                                         fill="#ffffff", outline=""))
            for it in parts + ([glint] if glint else []):
                self.cv.tag_raise(it)
        except tk.TclError:
            return self._finish()
        if i + 1 >= COVER_STEPS:
            self._covered_now()
            return self.later(COVER_MS, lambda: self._flash(0, parts + ([glint] if glint else []), r))
        self.later(COVER_MS, lambda: self._cover(i + 1, parts, glint))

    def _covered_now(self):
        if self._covered:
            return
        self._covered = True
        if self.on_cover:
            try:
                self.on_cover()
            except Exception:                               # noqa: BLE001
                pass

    # ---- 3. 번쩍인다 ----
    def _flash(self, i, parts, r, flash=None):
        if not self._ok():
            return self._finish()
        try:
            if flash is None:
                flash = self._add(self.cv.create_polygon(*hexagon(self.cx, self.cy, r * 1.2), fill="#ffffff",
                                                         outline=""))
            self.cv.coords(flash, *hexagon(self.cx, self.cy, r * (1.2 + 0.2 * i)))
            self.cv.itemconfigure(flash, fill=_mix("#ffffff", self.glow, i / float(FLASH_STEPS)))
            self.cv.tag_raise(flash)
        except tk.TclError:
            return self._finish()
        if i + 1 >= FLASH_STEPS:
            self._kill(flash)
            return self._break(0, parts, r)
        self.later(FLASH_MS, lambda: self._flash(i + 1, parts, r, flash))

    # ---- 4. 깨진다 ----
    def _break(self, i, parts, r, bits=None, rings=None, sparks=None):
        if not self._ok():
            return self._finish()
        try:
            if bits is None:
                for it in parts:
                    self._kill(it)
                bits = []
                cs = _corners(self.cx, self.cy, r)
                for k in range(6):                               # 결정의 바깥 면 여섯이 그대로 조각이 된다
                    a, b = cs[k], cs[(k + 1) % 6]
                    tri = [(self.cx, self.cy), a, b]
                    mx = (self.cx + a[0] + b[0]) / 3.0
                    my = (self.cy + a[1] + b[1]) / 3.0
                    ang = math.atan2(my - self.cy, mx - self.cx)
                    fill = _shade(self.color, math.atan2(-(my - self.cy), mx - self.cx))
                    it = self._add(self.cv.create_polygon(*[v for p in tri for v in p], fill=fill,
                                                          outline="#ffffff", width=1))
                    sp = self.size * self.rng.uniform(0.10, 0.16)
                    bits.append([it, tri, mx, my, math.cos(ang) * sp, math.sin(ang) * sp - self.size * 0.05,
                                 self.rng.uniform(-0.35, 0.35), 0.0, 1.0])
                for k in range(16):                              # 잔 조각
                    ang = self.rng.uniform(0, 2 * math.pi)
                    q = self.rng.uniform(2.5, 5.5) * U.h(1)
                    tri = [(self.cx, self.cy - q), (self.cx + q * 0.7, self.cy), (self.cx, self.cy + q),
                           (self.cx - q * 0.7, self.cy)]
                    it = self._add(self.cv.create_polygon(*[v for p in tri for v in p],
                                                          fill=self.glow if k % 3 else self.color, outline=""))
                    sp = self.size * self.rng.uniform(0.07, 0.2)
                    bits.append([it, tri, self.cx, self.cy, math.cos(ang) * sp, math.sin(ang) * sp * 0.85,
                                 self.rng.uniform(-0.5, 0.5), 0.0, 1.0])
                rings = [self._add(self.cv.create_polygon(0, 0, 0, 0, 0, 0, fill="", outline="#ffffff", width=4)),
                         self._add(self.cv.create_polygon(0, 0, 0, 0, 0, 0, fill="", outline=self.color, width=3))]
                sparks = []
                for k in range(7):
                    ang = 2 * math.pi * k / 7 + self.rng.uniform(-0.3, 0.3)
                    d = r * self.rng.uniform(0.7, 1.35)
                    sparks.append([self._add(self.cv.create_polygon(*_star(0, 0, 1), fill="#ffffff", outline="")),
                                   self.cx + math.cos(ang) * d, self.cy + math.sin(ang) * d * 1.1,
                                   2 + k % 5, U.h(5 + 4 * (k % 3))])
            if i >= BREAK_STEPS:
                return self._finish()
            g = self.size * 0.018                                 # 떨어지는 힘
            for b in bits:
                it, tri, mx, my, vx, vy, va, ang, sc = b
                b[2], b[3] = mx + vx, my + vy
                b[5] = vy + g
                b[7] = ang + va
                b[8] = sc * 0.93
                pts = [(b[2] + (x - tri_c(tri)[0]) * b[8], b[3] + (y - tri_c(tri)[1]) * b[8]) for x, y in tri]
                self.cv.coords(it, *_rot(pts, b[2], b[3], b[7]))
                self.cv.tag_raise(it)
            for k, ring in enumerate(rings):
                rr = r * (1.0 + (0.16 if k == 0 else 0.1) * (i + 1) * (1.0 if k == 0 else 1.25))
                self.cv.coords(ring, *hexagon(self.cx, self.cy, rr))
                self.cv.itemconfigure(ring, width=max(1, (4 if k == 0 else 3) - i // 4))
                if i >= BREAK_STEPS - 3:
                    self.cv.itemconfigure(ring, outline=_mix(self.glow, self.color, 0.5))
                self.cv.tag_raise(ring)
            for s in sparks:
                it, sx, sy, start, big = s
                k = i - start
                if 0 <= k < 6:
                    rr = big * (1.0 - abs(k - 2) / 3.5)
                    self.cv.coords(it, *_star(sx, sy, max(1.0, rr)))
                    self.cv.tag_raise(it)
                else:
                    self.cv.coords(it, *_star(sx, sy, 0.01))
        except tk.TclError:
            return self._finish()
        self.later(BREAK_MS, lambda: self._break(i + 1, parts, r, bits, rings, sparks))

    # ---- 끝 ----
    def _finish(self):
        if self.dead:
            return
        self.dead = True
        self._covered_now()                        # 도중에 끊겨도 도트는 결정 모습이 되어 있어야 한다
        for it in list(self.items):
            try:
                self.cv.delete(it)
            except tk.TclError:
                pass
        self.items = []
        cb, self.on_done = self.on_done, None
        if cb:
            try:
                cb()
            except Exception:                               # noqa: BLE001
                pass

    def stop(self):
        """창을 닫을 때. 다음으로 넘기지 않고 조용히 치운다."""
        self.on_done = None
        self.on_cover = None
        self._covered = True
        self._finish()


def tri_c(pts):
    """조각의 무게중심 (처음 모양 기준)."""
    n = float(len(pts))
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)


# ---------------------------------------------------------------- 결정이 된 도트 (판이 끝날 때까지)
_FACETS = {}
CROWN_ROOM = 0.30          # 왕관 자리 - 도트 높이에 대한 비율 (그림 위쪽에 이만큼 늘린다)


def _facets(w, h):
    """결정 면 무늬 (회색 128 이 '그대로'). 같은 크기면 다시 만들지 않는다."""
    key = (w, h)
    if key in _FACETS:
        return _FACETS[key]
    from PIL import Image, ImageDraw
    img = Image.new("L", (w, h), 128)
    d = ImageDraw.Draw(img)
    cell = max(7, int(min(w, h) / 5.5))
    rng = random.Random(w * 131 + h)
    for gy in range(-1, h // cell + 2):
        for gx in range(-1, w // cell + 2):
            x0 = gx * cell + (cell // 2 if gy % 2 else 0)
            y0 = gy * cell
            # 왼쪽 위가 밝고 오른쪽 아래가 어둡다 + 면마다 조금씩 다른 밝기
            base = 128 + int(26 * (1.0 - (x0 / float(max(1, w)) + y0 / float(max(1, h)))))
            for tri, bias in ((((x0, y0), (x0 + cell, y0), (x0, y0 + cell)), 14),
                              (((x0 + cell, y0), (x0 + cell, y0 + cell), (x0, y0 + cell)), -14)):
                v = base + bias + rng.randint(-26, 26)
                d.polygon(tri, fill=max(40, min(225, v)))
    # 빛줄기 두 개 (대각선)
    for k, off in enumerate((0.28, 0.62)):
        x = int(w * off)
        d.line([(x - h // 2, h), (x + h // 2, 0)], fill=236, width=max(1, cell // (4 + k)))
    _FACETS[key] = img
    return img


def _crown(width, height, color):
    """테라 왕관 - 띠 위에 결정 보석 셋 (가운데가 크다). 크게 그려 줄인다."""
    from PIL import Image, ImageDraw
    k = 4
    W, H = max(8, width) * k, max(6, height) * k
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    light, mid, dark = (_rgb(_mix(color, "#ffffff", 0.72)), _rgb(color), _rgb(_mix(color, "#000000", 0.38)))
    rim = (255, 255, 255, 255)
    lw = max(2, k + 1)
    band_top, band_bot = H * 0.74, H * 0.96
    # 보석 셋 (가운데 큰 것을 맨 나중에 - 위에 오게)
    for cx, top, half in ((0.24, 0.30, 0.13), (0.76, 0.30, 0.13), (0.5, 0.02, 0.17)):
        x = cx * W
        t = top * H
        mid_y = t + (band_top - t) * 0.58
        d.polygon([(x, t), (x - half * W, mid_y), (x, band_top + H * 0.04)], fill=light + (255,))
        d.polygon([(x, t), (x + half * W, mid_y), (x, band_top + H * 0.04)], fill=dark + (255,))
        d.polygon([(x, t + (mid_y - t) * 0.38), (x - half * W * 0.42, mid_y), (x, band_top - H * 0.02),
                   (x + half * W * 0.42, mid_y)], fill=mid + (255,))
        d.line([(x, t), (x - half * W, mid_y), (x, band_top + H * 0.04), (x + half * W, mid_y), (x, t)],
               fill=rim, width=lw)
    # 띠
    d.rounded_rectangle([W * 0.1, band_top, W * 0.9, band_bot], radius=int((band_bot - band_top) / 2),
                        fill=dark + (255,), outline=rim, width=lw)
    d.line([(W * 0.18, band_top + (band_bot - band_top) * 0.38), (W * 0.82, band_top + (band_bot - band_top) * 0.38)],
           fill=light + (255,), width=max(1, k))
    return img.resize((max(8, width), max(6, height)), Image.LANCZOS)


SWEEP_PART = 0.4           # 한 바퀴(애니메이션 한 번) 가운데 빛이 몸을 스쳐 가는 몫 - 나머지는 쉰다


def _sweep(w, h, k, n):
    """k 번째 프레임에 몸을 비스듬히 스쳐 가는 빛 띠의 가림판 (L). 그 프레임에 없으면 None.

    애니메이션 한 바퀴의 앞 SWEEP_PART 동안 왼쪽 아래에서 오른쪽 위로 지나가고 나머지는 쉰다 - 늘 번쩍이면
    눈이 아프다. 프레임이 넷도 안 되는 도트(멈춘 그림)는 지나가는 것이 안 보이므로 안 그린다.
    """
    if n < 4:
        return None
    t = k / float(max(1, n - 1)) / SWEEP_PART
    if t > 1.0:
        return None
    from PIL import Image, ImageDraw
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    x = -0.35 * w + t * 1.7 * w
    bw = max(3, w // 9)
    d.polygon([(x - bw - h * 0.4, h), (x + bw - h * 0.4, h), (x + bw + h * 0.4, 0), (x - bw + h * 0.4, 0)], fill=150)
    d.polygon([(x - bw * 0.35 - h * 0.4, h), (x + bw * 0.35 - h * 0.4, h), (x + bw * 0.35 + h * 0.4, 0),
               (x - bw * 0.35 + h * 0.4, 0)], fill=220)
    return m


def crystal_frames(frames, color):
    """도트 프레임(RGBA)들을 테라스탈한 모습으로 - 타입 빛깔 결정 질감 · 면 · 빛줄기 · 테두리 빛 · 머리 위 왕관.

    그림 위쪽에 왕관 자리(CROWN_ROOM)를 늘린다. 창의 도트는 발(아래 가운데, anchor="s")에 맞춰 서므로
    발 자리는 그대로다. 왕관은 첫 프레임의 윗몸 한가운데 위에 두고 모든 프레임에 같게 둔다 (흔들리지 않게).
    PIL 이 없거나 무엇이 터지면 원래 프레임을 그대로 돌려준다 (연출이 판을 막으면 안 된다).
    """
    if not frames:
        return frames
    try:
        from PIL import Image, ImageChops, ImageFilter, ImageOps
        color = color or "#9bd7ff"
        deep, mid = _rgb(_mix(color, "#000000", 0.58)), _rgb(color)
        shine = _rgb(_mix(color, "#ffffff", 0.7))
        halo_c = _rgb(_mix(color, "#ffffff", 0.45))
        w, h = frames[0].size
        room = max(12, int(h * CROWN_ROOM))
        a0 = frames[0].getchannel("A")
        bb = a0.getbbox() or (0, 0, w, h)
        # 왕관 자리: 윗몸(위 40%)에 칠해진 칸들의 가로 무게중심
        upper = a0.crop((bb[0], bb[1], bb[2], bb[1] + max(2, int((bb[3] - bb[1]) * 0.4))))
        colsum = list(upper.resize((upper.width, 1), Image.BOX).getdata())
        tot = float(sum(colsum))
        hx = bb[0] + (sum(i * v for i, v in enumerate(colsum)) / tot if tot else upper.width / 2.0)
        cw = max(12, min(int(w * 0.5), int(room * 1.7)))
        ch = max(10, int(room * 0.92))
        crown = _crown(cw, ch, color)
        fac = _facets(w, h).convert("RGB")
        white = Image.new("RGB", (w, h), (255, 255, 255))
        n = len(frames)
        out = []
        for k, f in enumerate(frames):
            f = f.convert("RGBA")
            a = f.getchannel("A")
            rgb = f.convert("RGB")
            gray = ImageOps.autocontrast(ImageOps.grayscale(rgb), cutoff=2)
            # 어두운 곳은 그 타입의 짙은 빛, 밝은 곳은 흰빛에 가깝게 - 원래 무늬는 조금 남긴다
            tint = ImageOps.colorize(gray, black=deep, white=shine, mid=mid, midpoint=122)
            body = Image.blend(rgb, tint, 0.84)
            body = Image.blend(body, ImageChops.overlay(body, fac), 0.8)      # 결정 면 · 빛줄기
            inner = a.filter(ImageFilter.FIND_EDGES).point(lambda v: 230 if v > 40 else 0)
            body.paste(Image.new("RGB", (w, h), shine), mask=inner)           # 안쪽 테두리 빛
            sweep = _sweep(w, h, k, n)
            if sweep is not None:                                             # 반짝 지나가는 빛 (움직이는 도트만)
                body.paste(white, mask=ImageChops.multiply(sweep, a))
            body = body.convert("RGBA")
            body.putalpha(a)
            halo = ImageChops.subtract(a.filter(ImageFilter.MaxFilter(3)), a).point(lambda v: 150 if v > 0 else 0)
            glow = Image.new("RGBA", (w, h), halo_c + (0,))
            glow.putalpha(halo)                                                # 바깥 테두리 빛 (한 칸)
            canvas = Image.new("RGBA", (w, h + room), (0, 0, 0, 0))
            canvas.alpha_composite(glow, (0, room))
            canvas.alpha_composite(body, (0, room))
            top = bb[1] + room                                   # 몸 꼭대기 (늘린 그림 안에서)
            cx = int(round(hx - cw / 2.0))
            cy = max(0, top - ch - max(1, room // 8))
            canvas.alpha_composite(crown, (max(0, min(w - cw, cx)), cy))
            out.append(canvas)
        return out
    except Exception:                                           # noqa: BLE001
        return frames


# ---------------------------------------------------------------- 바탕화면 배틀 (랭크 재생 · arena)
def desk(host, pet, typ, done):
    """바탕화면 배틀(arena)에서 pet 이 테라스탈한다 - 같은 결정 연출을 바탕화면 판(layer) 위에 조금 작게. 끝나면 done.

    바탕화면 도트는 걷는 도트라 결정 모습으로 바꾸지 않는다 (판이 짧고, 끝나면 cleanup 이 되돌린다).
    host 는 arena.Arena 처럼 layer · after 를 가진 판이다. 판이 없으면 잠깐 쉬고 넘어간다.
    """
    layer = getattr(host, "layer", None)
    if not layer or not pet:
        return host.after(400, done)
    try:
        x, y = layer.to_local(pet.x + pet.fw / 2.0, pet.y + pet.fh / 2.0)
        fx = TeraFx(layer.cv, (x, y), host.after, U.TYPE_COLOR.get(typ),
                    on_done=lambda: host.after(160, done), size=max(pet.fw, pet.fh) * 0.5)
        fx.play()
    except Exception:                                           # noqa: BLE001
        return host.after(400, done)
    return None
