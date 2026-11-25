# -*- coding: utf-8 -*-
"""기술 연출의 연장 — 다시 그린 연출(move_fx)이 전부 이 위에 선다.

예전 연출은 '도형 몇 개를 30ms 마다 옮겨 그리는 것' 이었다. 색은 타입마다 둘뿐이었고, 움직임은 일정한
속도였고, 맞는 순간은 어느 기술이나 같은 별 하나였다. 여기서는 손그림 이펙트(셀 애니메이션)의 문법을 쓴다.

    색        타입마다 다섯 단(가장 어두운 테 - 어두운 - 제 색 - 밝은 - 뜨거운 심) + 곁들이는 색 하나.
              빛은 반투명 대신 '어두운 테 · 제 색 · 흰 심' 세 겹으로 낸다 (바탕화면 레이어는 알파가 없다).
    모양      폭이 변하는 띠(ribbon)가 기본이다 - 광선 · 칼자국 · 꼬리 · 채찍이 다 이것이다. 선 대신 띠를 쓰면
              끝이 가늘어지고 배가 부풀어 '그린 것' 처럼 보인다.
    박자      모으고(움츠림) - 터뜨리고 - 맞는 순간 한 박자 멈추고(타격 프레임) - 흩어진다.
    몸        맞는 쪽 도트가 밀렸다 돌아온다 (무대의 fx_shift). 연출과 몸이 같이 움직여야 맞은 것 같다.
    시간      **실제 시각으로 굴린다.** 느린 PC 에서는 장을 건너뛸 뿐 길어지지 않는다 - 배틀 창은 2.4초가
              지나면 다음으로 넘어가므로, 장 수를 세어 굴리면 느린 PC 에서 연출이 다음 것과 겹친다.

    Tone / tone(타입)      색
    Show                   한 편의 시간표 (연출 하나에 하나, fx.show)
    Pen                    한 장을 그리는 붓 - 다음 장에 통째로 지운다
    Motes                  흩어지는 조각들 (위치가 나이의 함수라 장을 건너뛰어도 어긋나지 않는다)
    ribbon · flare · ...   도형
    impact · mini · rush   맞는 순간 · 작은 타격 · 달려들기
    jolt · shake · recoil  도트를 밀고 흔든다

캔버스에는 create_* / delete 만 쓴다 (관장 배틀 창은 이것들을 감싸 2배로 그린다 - ui_gym_battle._ScaledCanvas).
한때 떠 있는 도형 수는 client/test_move_fx.py 가 센다.
"""
import math
import random
import re
import time

WHITE = "#ffffff"
GOLD = "#ffd447"
INK = "#0e1018"                 # 거의 검정 (바탕화면 레이어의 투명색 #fe01fe 와 멀다)
SMOKE = ("#3d4152", "#6b7086", "#a4a9bd")
MS = 30                         # 한 장 (느리면 건너뛴다)
TAU = 2 * math.pi

#             가장 어두운   어두운     제 색      밝은       뜨거운 심  곁들이는 색
PAL = {
    "NORMAL":   ("#5a4416", "#c79a3a", "#f2d98c", "#fff4cf", "#ffffff", "#ff9d4a"),
    "FIRE":     ("#5a1206", "#c8321a", "#ff6a24", "#ffb52e", "#fff3b0", "#ffe36e"),
    "WATER":    ("#0d2a66", "#1f5fc4", "#3d94f0", "#8fd0ff", "#e9f8ff", "#b8f3ff"),
    "ELECTRIC": ("#5a4300", "#c79a00", "#ffd21f", "#fff27a", "#ffffe6", "#9fdcff"),
    "GRASS":    ("#12401a", "#2f8a35", "#5cc24a", "#a8e86a", "#f0ffd0", "#ffe56e"),
    "ICE":      ("#124a66", "#3d9ec4", "#7fd6ea", "#c8f6ff", "#ffffff", "#a8b8ff"),
    "FIGHTING": ("#571014", "#b83232", "#f0623a", "#ffa06a", "#fff0dc", "#ffd447"),
    "POISON":   ("#3a1259", "#7a2fb0", "#b25ae0", "#e0a8ff", "#fbeaff", "#b8f04a"),
    "GROUND":   ("#3d2409", "#8a5a24", "#bf8a42", "#e4c48a", "#fff3d6", "#ff9a3c"),
    "FLYING":   ("#2a3f73", "#6f8fd6", "#a9c2f5", "#dfe9ff", "#ffffff", "#bff5ff"),
    "PSYCHIC":  ("#5e1040", "#c42a70", "#f55a94", "#ffa8cf", "#fff0f8", "#b98bff"),
    "BUG":      ("#33420a", "#6f9412", "#a6cf2a", "#d6f27a", "#fbffd6", "#ffd84a"),
    "ROCK":     ("#2e2616", "#6e5f3c", "#a08a5a", "#d2c296", "#fff8e0", "#8f9aa8"),
    "GHOST":    ("#1f1640", "#4a3a8f", "#7a62c9", "#b9a8ef", "#f1ecff", "#ff6ad5"),
    "DRAGON":   ("#141a5e", "#3044c4", "#5a78f0", "#a3b8ff", "#eef2ff", "#ffd447"),
    "DARK":     ("#120f1c", "#3a3050", "#6a5a8a", "#a69ac4", "#eee8ff", "#ff3d5a"),
    "STEEL":    ("#2a3a48", "#62808f", "#9fb8c6", "#dbe8ef", "#ffffff", "#8fe0ff"),
    "FAIRY":    ("#6a1e52", "#d658ab", "#f58fd0", "#ffc8ea", "#fff5fb", "#ffe07a"),
}
PAL_DEFAULT = ("#3a3a3a", "#8a8a8a", "#c8c8c8", "#f0f0f0", "#ffffff", "#ffe9a0")
# 어두운 타입은 어두운 배경에 묻힌다 - 윤곽에 밝은 테를 한 줄 두른다
EDGE = {"GHOST": "#b9a8ef", "DARK": "#a69ac4"}


class Tone(object):
    """타입 하나의 색."""
    __slots__ = ("deep", "dark", "base", "light", "hot", "alt", "edge", "typ")

    def __init__(self, typ):
        self.typ = typ
        self.deep, self.dark, self.base, self.light, self.hot, self.alt = PAL.get(typ, PAL_DEFAULT)
        self.edge = EDGE.get(typ, "")

    @property
    def tri(self):
        """빛 세 겹 (테, 몸, 심)."""
        if self.typ in ("GHOST", "DARK"):
            return (self.dark, self.base, self.alt)
        return (self.dark, self.light, self.hot)


_TONES = {}


def tone(typ):
    t = _TONES.get(typ)
    if t is None:
        t = _TONES[typ] = Tone(typ)
    return t


_MIX = {}


def mix(a, b, t):
    """두 색 사이 (t=0 이면 a, 1 이면 b)."""
    t = max(0.0, min(1.0, t))
    key = (a, b, int(t * 16))
    got = _MIX.get(key)
    if got is None:
        t = key[2] / 16.0
        x, y = a.lstrip("#"), b.lstrip("#")
        got = _MIX[key] = "#%02x%02x%02x" % tuple(
            int(round(int(x[i:i + 2], 16) * (1 - t) + int(y[i:i + 2], 16) * t)) for i in (0, 2, 4))
    return got


def key_of(move):
    """기술의 영문 이름을 글자 · 숫자만 남긴 소문자로 (이름으로 연출을 고를 때 쓴다)."""
    return re.sub(r"[^a-z0-9]", "", ((move or {}).get("en") or "").lower())


# ---------------------------------------------------------------- 박자
def clamp(t):
    return 0.0 if t < 0.0 else 1.0 if t > 1.0 else t


def out2(t):
    t = clamp(t)
    return 1.0 - (1.0 - t) ** 2


def out3(t):
    t = clamp(t)
    return 1.0 - (1.0 - t) ** 3


def in2(t):
    t = clamp(t)
    return t * t


def in3(t):
    t = clamp(t)
    return t * t * t


def inout(t):
    t = clamp(t)
    return t * t * (3.0 - 2.0 * t)


def back(t, s=1.7):
    """조금 넘쳤다 돌아온다 (튀어나오는 것)."""
    t = clamp(t) - 1.0
    return t * t * ((s + 1.0) * t + s) + 1.0


def hump(t):
    """0 -> 1 -> 0."""
    return math.sin(math.pi * clamp(t))


def span(t, a, b):
    """t 가 a..b 를 지나는 동안 0..1."""
    return clamp((t - a) / float(b - a)) if b != a else (1.0 if t >= b else 0.0)


def fade(u, a=0.15, b=0.7):
    """나타났다(0..a) 머물다 사라지는(b..1) 크기 0..1..0."""
    return min(span(u, 0.0, a), 1.0 - span(u, b, 1.0))


_NOISE = [random.Random(20261125).random() for _ in range(257)]


def noise(i):
    """늘 같은 값이 나오는 0..1 (모양을 장마다 흔들리지 않게 고정한다)."""
    return _NOISE[int(i) % 257]


def snoise(i):
    return _NOISE[int(i) % 257] * 2.0 - 1.0


# ---------------------------------------------------------------- 길
class Geo(object):
    """쓰는 쪽에서 맞는 쪽으로 가는 길."""

    def __init__(self, fx):
        self.sx, self.sy = fx.src
        self.tx, self.ty = fx.dst
        dx, dy = self.tx - self.sx, self.ty - self.sy
        self.d = math.hypot(dx, dy) or 1.0
        self.ux, self.uy = dx / self.d, dy / self.d
        self.px, self.py = -self.uy, self.ux            # 길에 수직
        self.face = 1 if dx >= 0 else -1                # 맞는 쪽이 오른쪽이면 1
        self.ang = math.atan2(dy, dx)
        self.deg = -math.degrees(self.ang)              # Tk 의 호(arc)가 쓰는 각도
        self.gs = self.sy + 24.0                        # 쓰는 쪽 발밑
        self.gt = self.ty + 24.0                        # 맞는 쪽 발밑
        self.top = max(-14.0, self.ty - 190.0)          # 하늘 (화면 위 끝)

    def at(self, t, off=0.0):
        """길 위의 점. off 는 길 옆으로 비킨 만큼."""
        return (self.sx + (self.tx - self.sx) * t + self.px * off,
                self.sy + (self.ty - self.sy) * t + self.py * off)

    def mouth(self, r=16.0):
        """쓰는 쪽 몸 앞 (뭔가 뿜어 나오는 자리)."""
        return (self.sx + self.ux * r, self.sy + self.uy * r)

    def path(self, t0, t1, n, off=None, m=None):
        """t0..t1 사이의 가운데 길 (점 n+1 개). off(u) 는 옆으로 비킨 만큼. m 은 출발점 (기본: 쓰는 쪽)."""
        x0, y0 = m if m else (self.sx, self.sy)
        pts = []
        for i in range(n + 1):
            u = t0 + (t1 - t0) * i / float(n)
            o = off(u) if off else 0.0
            pts += [x0 + (self.tx - x0) * u + self.px * o, y0 + (self.ty - y0) * u + self.py * o]
        return pts


# ---------------------------------------------------------------- 붓
class Pen(object):
    """한 장을 그리는 붓. 그린 것은 시간표(Show)가 다음 장에 통째로 지운다."""
    __slots__ = ("cv", "ids")

    def __init__(self, cv, ids):
        self.cv = cv
        self.ids = ids

    def poly(self, pts, fill, outline="", width=1, smooth=False):
        if len(pts) >= 6:
            self.ids.append(self.cv.create_polygon(*pts, fill=fill, outline=outline, width=width, smooth=smooth))

    def line(self, pts, fill, width=2, smooth=False, cap="round"):
        if len(pts) >= 4:
            self.ids.append(self.cv.create_line(*pts, fill=fill, width=width, smooth=smooth, capstyle=cap,
                                                joinstyle="round"))

    def oval(self, x, y, rx, ry=None, fill="", outline="", width=1):
        ry = rx if ry is None else ry
        self.ids.append(self.cv.create_oval(x - rx, y - ry, x + rx, y + ry, fill=fill, outline=outline, width=width))

    def arc(self, x, y, rx, ry, start, extent, outline, width=2):
        if rx > 0.5 and ry > 0.5:
            self.ids.append(self.cv.create_arc(x - rx, y - ry, x + rx, y + ry, start=start, extent=extent,
                                               style="arc", outline=outline, width=width))

    def text(self, x, y, s, fill, font):
        self.ids.append(self.cv.create_text(x, y, text=s, fill=fill, font=font))


# ---------------------------------------------------------------- 시간표
class Show(object):
    """연출 한 편의 시간표. 연출(Effect) 하나에 하나고, 예약(after)도 이것 한 줄뿐이다.

        act(at, dur, draw, settle)   at 부터 dur 동안 장마다 draw(pen, u, ms) - u 는 0..1, ms 는 시작부터 지난 시간
        cue(at, fn)                  at 에 한 번 fn() (늦어도 꼭 한 번, 시간 순서대로)
        hold() / release()           바깥의 신호(무대의 달려들기)를 기다리는 동안 끝내지 않는다
        rebase()                     지금을 새 기준(0)으로 - 그 뒤에 넣는 것들의 at 이 여기서부터다

    넣은 것이 다 지나가면 fx.finish() 를 부른다 (done 을 걸어 두면 그것을). 조금 더 머물려면 wait(at).
    """

    def __init__(self, fx):
        self.fx = fx
        self.cv = fx.cv
        self.acts = []
        self.cues = []
        self.frame = []
        self.base = 0.0
        self.t = 0.0
        self.t0 = None
        self.holds = 0
        self.on = False
        self.done = None
        self._seq = 0
        self._in_cue = False

    # ---- 넣기 ----
    def now(self):
        return 0.0 if self.t0 is None else self.fx.clock() - self.t0

    def act(self, at, dur, draw, settle=None, z=0):
        a = self.base + at
        b = a + max(1.0, dur)
        self._seq += 1
        self.acts.append((z, self._seq, a, b, draw, settle))
        self.acts.sort(key=lambda v: (v[0], v[1]))
        self.kick()
        return at + dur

    def cue(self, at, fn):
        """at 에 한 번 fn(). 돌려주는 표로 cancel 할 수 있다."""
        self._seq += 1
        self.cues.append((self.base + at, self._seq, fn))
        self.kick()
        return self._seq

    def cancel(self, ticket):
        self.cues = [c for c in self.cues if c[1] != ticket]

    def wait(self, at):
        """at 까지는 끝내지 않는다 (아무것도 안 그리는 여운)."""
        return self.cue(at, lambda: None)

    def hold(self):
        self.holds += 1
        self.kick()

    def release(self):
        self.holds = max(0, self.holds - 1)

    def rebase(self):
        self.base = self.t if self._in_cue else max(self.t, self.now())
        return self.base

    def kick(self):
        if self.on or self.fx.dead:
            return
        self.on = True
        if self.t0 is None:
            self.t0 = self.fx.clock()
        self.fx.after(1, self._tick)

    # ---- 굴리기 ----
    def wipe(self):
        if self.frame:
            ids, self.frame = self.frame, []
            try:
                self.cv.delete(*ids)
            except Exception:                               # noqa: BLE001
                pass

    def _tick(self):
        fx = self.fx
        if fx.dead:
            return
        try:
            self._step()
        except Exception:                                   # noqa: BLE001
            if fx.debug():
                raise
            fx.finish()

    def _step(self):
        fx = self.fx
        began = time.monotonic()
        now = fx.clock() - self.t0
        self.wipe()
        while self.cues:                                    # 때가 된 신호 - 시간 순서대로, 늦어도 한 번은 꼭
            c = min(self.cues)
            if c[0] > now:
                break
            self.cues.remove(c)
            self.t, self._in_cue = c[0], True
            try:
                c[2]()
            finally:
                self._in_cue = False
            if fx.dead:
                return
        self.t = now
        sf = fx.surface                                     # [시범] 그림 바탕이면 그림판의 붓으로
        pen = sf.begin() if sf is not None else Pen(self.cv, self.frame)
        ended = set()
        for a in list(self.acts):
            if now < a[2]:
                continue
            if now >= a[3]:
                ended.add(a[1])
                if a[5]:
                    a[5]()
            else:
                a[4](pen, (now - a[2]) / (a[3] - a[2]), now - a[2])
        if sf is not None:
            sf.end()
        if ended:                                           # (그리는 동안 새로 넣은 것은 그대로 둔다)
            self.acts = [a for a in self.acts if a[1] not in ended]
        if not self.acts and not self.cues and not self.holds:
            self.on = False
            self.wipe()
            return (self.done or fx.finish)()
        if sf is not None:                                  # [시범] 그림 바탕: 그리는 데 쓴 시간만큼 다음 장을 당긴다
            return fx.after(max(1, int(MS - (time.monotonic() - began) * 1000.0)), self._tick)
        fx.after(MS, self._tick)

    def stop(self):
        """그리던 것을 지우고, 끝나면 하려던 마무리(도트 제자리)를 한다. 연출이 끝나거나 멈출 때 부른다."""
        self.wipe()
        acts, self.acts, self.cues = self.acts, [], []
        for a in acts:
            if a[5]:
                try:
                    a[5]()
                except Exception:                           # noqa: BLE001
                    pass


# ---------------------------------------------------------------- 조각
class Motes(object):
    """흩어지는 조각들. 저마다 태어난 때 · 수명 · 가는 길이 정해져 있어서, 위치가 나이의 함수다.

    add / burst / spray 로 넣어 두고 draw(pen, ms, paint) 로 그린다. paint(pen, x, y, 크기, 돌린 각, k, 번호) -
    k 는 남은 수명 1 -> 0 (작아지며 사라지게 쓴다).
    """

    def __init__(self, seed=None):
        self.ps = []
        self.rnd = random.Random(seed) if seed is not None else random

    def add(self, born, life, x, y, dx=0.0, dy=0.0, g=0.0, size=4.0, rot=0.0, spin=0.0, lift=0.0):
        self.ps.append((born, float(life), x, y, dx, dy, g, size, rot, spin, lift, len(self.ps)))

    def burst(self, born, n, x, y, dist=(18, 46), life=(240, 420), ang=(0.0, TAU), g=0.0, size=(3.0, 6.0),
              flat=0.85, spin=6.0, lift=0.0, spread=0.0):
        """한 점에서 사방으로 (ang 안에서). dist: 날아가는 거리, flat: 세로로 눌린 정도, lift: 위로 떠오르는 만큼."""
        r = self.rnd
        for j in range(n):
            a = ang[0] + (ang[1] - ang[0]) * (j + r.uniform(0.15, 0.85)) / float(n)
            d = r.uniform(*dist)
            self.add(born + r.uniform(0, 30), r.uniform(*life), x + r.uniform(-spread, spread),
                     y + r.uniform(-spread, spread), math.cos(a) * d, math.sin(a) * d * flat, g,
                     r.uniform(*size), r.uniform(0, TAU), r.uniform(-spin, spin), lift)

    def draw(self, p, ms, paint, scale=1.0):
        for born, life, x, y, dx, dy, g, size, rot, spin, lift, n in self.ps:
            age = ms - born
            if age < 0 or age >= life:
                continue
            u = age / life
            e = 1.0 - (1.0 - u) ** 2
            s = age / 1000.0
            paint(p, x + dx * e, y + dy * e + 0.5 * g * s * s - lift * u, size * scale, rot + spin * u, 1.0 - u, n)

    def last(self):
        return max([b + l for b, l, *_ in self.ps] or [0.0])


# ---------------------------------------------------------------- 도형
def widths(n, w, kind="spindle", a=0.18, b=0.82):
    """띠의 반폭 n+1 개. spindle: 양 끝이 뾰족 / comet: 꼬리가 뾰족, 머리가 굵다 / flat: 양 끝만 빨리 가늘어진다."""
    out = []
    for i in range(n + 1):
        u = i / float(n)
        if kind == "comet":
            k = u ** 0.7
        elif kind == "flat":
            k = min(1.0, u / a) if u < a else min(1.0, (1.0 - u) / (1.0 - b)) if u > b else 1.0
            k = k ** 0.6
        elif kind == "head":
            k = (1.0 - u) ** 0.7
        else:
            k = math.sin(math.pi * u) ** 0.75
        out.append(w * k)
    return out


def ribbon(p, pts, ws, fill, outline="", smooth=True, width=1):
    """가운데 길(pts)을 따라가는, 폭이 변하는 띠. ws 는 점마다의 반폭 (수 하나면 고른 폭)."""
    n = len(pts) // 2
    if n < 2:
        return
    left, right = [], []
    for i in range(n):
        x, y = pts[2 * i], pts[2 * i + 1]
        ax, ay = (pts[2 * i - 2], pts[2 * i - 1]) if i > 0 else (x, y)
        bx, by = (pts[2 * i + 2], pts[2 * i + 3]) if i < n - 1 else (x, y)
        dx, dy = bx - ax, by - ay
        d = math.hypot(dx, dy) or 1.0
        w = ws if isinstance(ws, (int, float)) else ws[i]
        nx, ny = -dy / d * w, dx / d * w
        left += [x + nx, y + ny]
        right += [y - ny, x - nx]
    right.reverse()
    p.poly(left + right, fill, outline, width, smooth)


def glow_ribbon(p, pts, ws, cols, k=(1.0, 0.62, 0.28), smooth=True):
    """빛 세 겹의 띠 (테 - 몸 - 심)."""
    for col, kk in zip(cols, k):
        if col:
            ribbon(p, pts, [w * kk for w in ws] if not isinstance(ws, (int, float)) else ws * kk, col, smooth=smooth)


def flare(p, x, y, r, n, fill, inner=0.35, rot=0.0, outline="", sy=1.0, width=1):
    """뾰족한 별. n 이 4 고 inner 가 작으면 반짝임, 많으면 맞는 순간의 번쩍."""
    pts = []
    for i in range(n * 2):
        a = rot + math.pi * i / n
        rr = r if i % 2 == 0 else r * inner
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr * sy]
    p.poly(pts, fill, outline, width)


def burst_star(p, x, y, r, n, fill, seed=0, inner=0.4, rot=0.0, sy=1.0, outline="", width=1):
    """가시 길이가 들쭉날쭉한 별 (손으로 그린 타격 자국)."""
    pts = []
    for i in range(n * 2):
        a = rot + math.pi * i / n
        rr = r * (0.62 + 0.38 * noise(seed * 13 + i * 5)) if i % 2 == 0 else r * inner * (0.8 + 0.4 * noise(seed + i))
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr * sy]
    p.poly(pts, fill, outline, width)


def glint(p, x, y, r, fill=WHITE, rot=0.0):
    """네 갈래 반짝임."""
    flare(p, x, y, r, 4, fill, inner=0.15, rot=rot - math.pi / 2)


def disc(p, x, y, r, fill, outline="", width=1, sy=1.0):
    p.oval(x, y, r, r * sy, fill, outline, width)


def ring(p, x, y, r, col, w=2, sy=1.0):
    p.oval(x, y, r, r * sy, "", col, w)


def arcs(p, x, y, r, col, w=2, rot=0.0, n=3, sweep=70, sy=1.0):
    """끊어진 고리 (도는 것처럼 보인다)."""
    for i in range(n):
        p.arc(x, y, r, r * sy, (rot + i * 360.0 / n) % 360, sweep, col, w)


def hoop(p, x, y, ra, rb, ang, col, w=2, fill=""):
    """기울어진 고리 (길을 감싸고 도는 테). ra 는 ang 쪽 반지름, rb 는 그 수직."""
    c, s = math.cos(ang), math.sin(ang)
    pts = []
    for i in range(10):
        a = TAU * i / 10
        dx, dy = math.cos(a) * ra, math.sin(a) * rb
        pts += [x + dx * c - dy * s, y + dx * s + dy * c]
    p.poly(pts, fill, col, w, True)


def cloud(p, x, y, r, cols, seed=0, wob=0.0):
    """구름 한 덩이 (어두운 밑 - 밝은 위)."""
    blob(p, x, y + r * 0.12, r, cols[0], seed, wob, n=10, jag=0.22, sy=0.62)
    blob(p, x - r * 0.1, y - r * 0.1, r * 0.72, cols[1], seed + 5, wob, n=9, jag=0.22, sy=0.6)


def orb(p, x, y, r, cols, shine=True):
    """빛나는 구슬: 테 - 몸 - 심, 그리고 왼쪽 위의 빛."""
    rim, body, core = cols
    p.oval(x, y, r, r, rim)
    p.oval(x, y, r * 0.74, r * 0.74, body)
    if core:
        p.oval(x, y, r * 0.42, r * 0.42, core)
    if shine and r > 6:
        p.oval(x - r * 0.42, y - r * 0.44, r * 0.2, r * 0.14, WHITE)


def blob(p, x, y, r, fill, seed=0, wob=0.0, n=9, jag=0.26, sy=1.0, outline="", width=1):
    """울퉁불퉁한 덩어리 (연기 · 불덩이 · 독). seed 가 같으면 같은 모양이고, wob 을 바꾸면 꿈틀거린다."""
    pts = []
    for i in range(n):
        a = TAU * i / n
        rr = r * (1.0 - jag + 2.0 * jag * noise(seed * 31 + i * 7) + 0.5 * jag * math.sin(wob + i * 2.1))
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr * sy]
    p.poly(pts, fill, outline, width, True)


def tongue(p, x, y, r, lean, fill, outline=""):
    """불꽃 혀 하나. 아래가 둥글고 위로 뾰족하다. lean 만큼 끝이 옆으로 기운다."""
    p.poly([x - r * 0.75, y + r * 0.4, x - r * 0.55, y - r * 0.4, x + lean, y - r * 1.75,
            x + r * 0.55, y - r * 0.4, x + r * 0.75, y + r * 0.4, x, y + r * 0.9], fill, outline, 1, True)


def flame(p, x, y, r, lean, cols):
    """세 겹 불꽃."""
    tongue(p, x, y, r, lean, cols[0])
    tongue(p, x, y + r * 0.22, r * 0.68, lean * 0.7, cols[1])
    if cols[2] and r > 5:
        tongue(p, x, y + r * 0.42, r * 0.36, lean * 0.4, cols[2])


def streak(p, x1, y1, x2, y2, w, fill, outline=""):
    """양 끝이 뾰족하고 가운데가 두꺼운 자국."""
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy) or 1.0
    px, py = -dy / d * w, dx / d * w
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    p.poly([x1, y1, mx + px, my + py, x2, y2, mx - px, my - py], fill, outline)


def comet(p, x1, y1, x2, y2, w, fill):
    """꼬리(x1, y1)는 뾰족하고 머리(x2, y2)는 둥글게 굵다."""
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy) or 1.0
    ux, uy = dx / d, dy / d
    p.poly([x1, y1, x2 - uy * w, y2 + ux * w, x2 + ux * w * 0.9, y2 + uy * w * 0.9, x2 + uy * w, y2 - ux * w], fill,
           "", 1, True)


def shard(p, x, y, r, ang, fill, outline="", slim=0.42):
    """ang 쪽을 보는 길쭉한 조각 (얼음 · 화살촉 · 바늘)."""
    c, s = math.cos(ang), math.sin(ang)
    pts = []
    for dx, dy in ((r * 1.5, 0), (0, r * slim), (-r * 0.9, 0), (0, -r * slim)):
        pts += [x + dx * c - dy * s, y + dx * s + dy * c]
    p.poly(pts, fill, outline)


def spike(p, x, y, w, h, ang, fill, outline="", width=1):
    """(x, y) 에 밑변을 두고 ang 쪽으로 솟는 가시 (돌기둥 · 얼음 기둥)."""
    c, s = math.cos(ang), math.sin(ang)
    p.poly([x - s * w, y + c * w, x + c * h, y + s * h, x + s * w, y - c * w], fill, outline, width)


def chunk(p, x, y, r, seed, light, dark):
    """모난 돌덩이 (밝은 면 하나)."""
    pts = []
    for i in range(6):
        a = TAU * i / 6 + snoise(seed * 7 + i) * 0.25
        rr = r * (0.74 + 0.34 * noise(seed * 3 + i * 11))
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
    p.poly(pts, dark, INK if r > 5 else "")
    if r > 3.5:
        p.poly([pts[6], pts[7], pts[8], pts[9], pts[10], pts[11], x, y], light)


def crescent(p, x, y, r, ang, sweep, thick, fill, outline="", a0=None, a1=None):
    """초승달 칼날. (x, y) 가 원의 중심, ang 이 휜 쪽. 가운데가 thick 만큼 두껍다. a0..a1 을 주면 그 사이만."""
    lo = ang - sweep / 2.0 if a0 is None else a0
    hi = ang + sweep / 2.0 if a1 is None else a1
    n = 9
    pts = []
    for i in range(n + 1):
        a = lo + (hi - lo) * i / n
        pts += [x + math.cos(a) * r, y + math.sin(a) * r]
    for i in range(n, -1, -1):
        a = lo + (hi - lo) * i / n
        rr = r - thick * math.sin(math.pi * i / n)
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
    p.poly(pts, fill, outline)


def leaf(p, x, y, r, ang, fill, vein=""):
    """잎 한 장 (ang 쪽이 끝)."""
    c, s = math.cos(ang), math.sin(ang)
    pts = []
    for dx, dy in ((-r, 0), (-r * 0.2, -r * 0.62), (r * 1.1, 0), (-r * 0.2, r * 0.62)):
        pts += [x + dx * c - dy * s, y + dx * s + dy * c]
    p.poly(pts, fill, vein, 1, False)
    if vein and r > 6:
        p.line([x - r * c, y - r * s, x + r * c, y + r * s], vein, 1)


def petal(p, x, y, r, ang, fill, outline=""):
    c, s = math.cos(ang), math.sin(ang)
    pts = []
    for dx, dy in ((-r, 0), (0, -r * 0.6), (r, -r * 0.25), (r * 0.7, 0), (r, r * 0.25), (0, r * 0.6)):
        pts += [x + dx * c - dy * s, y + dx * s + dy * c]
    p.poly(pts, fill, outline, 1, True)


def drop(p, x, y, r, ang, fill, outline=""):
    """물방울 (ang 쪽이 뾰족한 꼬리)."""
    c, s = math.cos(ang), math.sin(ang)
    pts = []
    for dx, dy in ((r * 1.7, 0), (0, r * 0.9), (-r, 0), (0, -r * 0.9)):
        pts += [x + dx * c - dy * s, y + dx * s + dy * c]
    p.poly(pts, fill, outline, 1, True)


def star(p, x, y, r, fill, outline="", rot=0.0):
    flare(p, x, y, r, 5, fill, inner=0.45, rot=rot - math.pi / 2, outline=outline)


def heart(p, x, y, r, fill, outline=""):
    pts = []
    for i in range(14):
        a = TAU * i / 14
        hx = 16 * math.sin(a) ** 3
        hy = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts += [x + hx * r / 16.0, y + hy * r / 16.0]
    p.poly(pts, fill, outline)


def feather(p, x, y, r, ang, fill, rib):
    c, s = math.cos(ang), math.sin(ang)
    pts = []
    for dx, dy in ((-r * 1.2, 0), (-r * 0.2, -r * 0.5), (r * 1.3, 0), (-r * 0.2, r * 0.5)):
        pts += [x + dx * c - dy * s, y + dx * s + dy * c]
    p.poly(pts, fill, rib, 1, True)
    p.line([x - r * 1.5 * c, y - r * 1.5 * s, x + r * 1.1 * c, y + r * 1.1 * s], rib, 1)


def chevron(p, x, y, w, h, up, fill, outline=""):
    """갈매기 화살표 (랭크 변화)."""
    d = -1 if up else 1
    p.poly([x - w, y, x, y + d * h, x + w, y, x + w, y - d * h * 0.55, x, y + d * h * 0.45, x - w, y - d * h * 0.55],
           fill, outline)


def plus(p, x, y, r, fill, outline=""):
    t = r * 0.36
    p.poly([x - t, y - r, x + t, y - r, x + t, y - t, x + r, y - t, x + r, y + t, x + t, y + t, x + t, y + r,
            x - t, y + r, x - t, y + t, x - r, y + t, x - r, y - t, x - t, y - t], fill, outline)


def note(p, x, y, r, col, rim=""):
    """음표 (글꼴에 기대지 않는다 - 없는 글꼴에서는 네모로 깨진다)."""
    if rim:
        p.oval(x, y, r * 1.25, r * 0.95, rim)
        p.line([x + r * 0.8, y, x + r * 0.8, y - r * 3.0, x + r * 2.1, y - r * 2.2], rim, max(2, r * 0.75))
    p.oval(x, y, r, r * 0.72, col)
    p.line([x + r * 0.8, y, x + r * 0.8, y - r * 3.0, x + r * 2.1, y - r * 2.2], col, max(1, r * 0.4))


def zee(p, x, y, r, col, rim=""):
    """잠의 Z."""
    pts = [x - r, y - r, x + r, y - r, x - r, y + r, x + r, y + r]
    if rim:
        p.line(pts, rim, max(3, r * 0.75), cap="projecting")
    p.line(pts, col, max(1, r * 0.36), cap="projecting")


def zigzag(x1, y1, x2, y2, jag, n, rnd=None):
    """지그재그 길의 좌표 (번개 · 갈라진 땅)."""
    r = rnd or random
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy) or 1.0
    px, py = -dy / d, dx / d
    pts = [x1, y1]
    for i in range(1, n):
        t = (i + r.uniform(-0.3, 0.3)) / float(n)
        o = r.uniform(-jag, jag)
        pts += [x1 + dx * t + px * o, y1 + dy * t + py * o]
    return pts + [x2, y2]


def bolt(p, pts, w, cols):
    """번개 한 줄: 테 - 몸 - 심."""
    p.line(pts, cols[0], w + 4, cap="round")
    p.line(pts, cols[1], w + 1, cap="round")
    if cols[2]:
        p.line(pts, cols[2], max(1, w - 2), cap="round")


def focus(p, x, y, r0, r1, n, col, seed=0, w=2.2, sy=0.85, alt=None):
    """집중선 - 한 점에서 바깥으로 뻗는 가는 쐐기들."""
    for j in range(n):
        a = TAU * (j + 0.6 * snoise(seed + j * 3)) / n
        k = 0.7 + 0.5 * noise(seed * 5 + j)
        c, s = math.cos(a), math.sin(a) * sy
        streak(p, x + c * r0, y + s * r0, x + c * (r0 + (r1 - r0) * k), y + s * (r0 + (r1 - r0) * k),
               w * (0.6 + 0.8 * noise(seed + j * 17)), alt if (alt and j % 3 == 0) else col)


def sigil(p, x, y, r, rot, col, w=2, sy=0.72, pts=3, ring_=True):
    """마법 문양: 마주 놓인 다각형 둘 + 테."""
    for turn in (0.0, math.pi):
        q = []
        for i in range(pts):
            a = rot + turn + i * TAU / pts
            q += [x + math.cos(a) * r, y + math.sin(a) * r * sy]
        p.poly(q, "", col, w)
    if ring_:
        p.oval(x, y, r, r * sy, "", col, max(1, w - 1))


def smoke(p, x, y, r, k, seed=0, cols=SMOKE):
    """연기 한 덩이 (k: 남은 수명 - 식으면서 어두워진다)."""
    blob(p, x, y, r, cols[0] if k < 0.4 else cols[1], seed, wob=k * 4, n=8, jag=0.2)
    if k > 0.45 and r > 6:
        blob(p, x - r * 0.18, y - r * 0.2, r * 0.6, cols[2], seed + 3, wob=k * 4, n=7, jag=0.2)


# ---------------------------------------------------------------- 타입의 조각
def _m_ember(p, x, y, s, rot, k, n, c):
    tongue(p, x, y, s * (0.5 + 0.9 * k), math.sin(rot) * 3, c.base if k < 0.45 else c.light)
    if k > 0.6:
        tongue(p, x, y + s * 0.3, s * 0.6 * k, math.sin(rot) * 2, c.hot)


def _m_drop(p, x, y, s, rot, k, n, c):
    drop(p, x, y, s * (0.45 + 0.6 * k), -math.pi / 2 + math.sin(rot) * 0.5, c.light if n % 2 else c.base, c.dark)


def _m_zap(p, x, y, s, rot, k, n, c):
    ln = s * (1.2 + 2.2 * k)
    a = rot
    q = [x, y]
    for i in range(1, 4):
        q += [x + math.cos(a) * ln * i / 3 + snoise(n * 7 + i + int(k * 9)) * s * 0.9,
              y + math.sin(a) * ln * i / 3 + snoise(n * 11 + i + int(k * 9)) * s * 0.9]
    p.line(q, c.base, 3, cap="butt")
    p.line(q, c.hot, 1, cap="butt")


def _m_leaf(p, x, y, s, rot, k, n, c):
    leaf(p, x, y, s * (0.6 + 0.6 * k), rot, c.light if n % 2 else c.base, c.dark)


def _m_crystal(p, x, y, s, rot, k, n, c):
    shard(p, x, y, s * (0.5 + 0.7 * k), rot, c.hot if n % 2 else c.light, c.dark)


def _m_chip(p, x, y, s, rot, k, n, c):
    streak(p, x - math.cos(rot) * s * 1.6 * k, y - math.sin(rot) * s * 1.6 * k,
           x + math.cos(rot) * s * 1.6 * k, y + math.sin(rot) * s * 1.6 * k, s * 0.45, c.hot if n % 2 else c.light)


def _m_bubble(p, x, y, s, rot, k, n, c):
    r = s * (0.5 + 0.6 * k)
    p.oval(x, y, r, r, c.base if n % 3 else c.alt, c.deep, 1)
    if r > 3:
        p.oval(x - r * 0.3, y - r * 0.3, r * 0.3, r * 0.3, c.hot)


def _m_pebble(p, x, y, s, rot, k, n, c):
    chunk(p, x, y, s * (0.55 + 0.6 * k), n, c.light, c.dark)


def _m_feather(p, x, y, s, rot, k, n, c):
    feather(p, x, y, s * (0.6 + 0.6 * k), rot, c.hot, c.base)


def _m_psi(p, x, y, s, rot, k, n, c):
    r = s * (0.5 + 0.8 * k)
    if n % 2:
        flare(p, x, y, r * 1.2, 4, c.alt if n % 4 == 1 else c.light, inner=0.42, rot=rot)
    else:
        p.oval(x, y, r, r, "", c.light, 2)


def _m_spore(p, x, y, s, rot, k, n, c):
    r = s * (0.35 + 0.5 * k)
    p.oval(x, y, r, r, c.alt if n % 3 == 0 else c.light, c.dark, 1)


def _m_wisp(p, x, y, s, rot, k, n, c):
    tongue(p, x, y, s * (0.5 + 0.9 * k), math.sin(rot) * 4, c.dark, c.light)
    if k > 0.5:
        p.oval(x, y + s * 0.2, s * 0.25, s * 0.25, c.alt)


def _m_scale(p, x, y, s, rot, k, n, c):
    flare(p, x, y, s * (0.6 + 0.8 * k), 2, c.alt if n % 3 == 0 else c.light, inner=0.5, rot=rot, outline=c.dark)


def _m_sliver(p, x, y, s, rot, k, n, c):
    shard(p, x, y, s * (0.5 + 0.8 * k), rot, c.alt if n % 3 == 0 else c.dark, c.light, slim=0.3)


def _m_glint(p, x, y, s, rot, k, n, c):
    glint(p, x, y, s * (0.5 + 1.2 * k), WHITE if k > 0.4 else c.light, rot=rot * 0.3)


def _m_fairy(p, x, y, s, rot, k, n, c):
    r = s * (0.5 + 0.8 * k)
    if n % 3 == 0:
        heart(p, x, y, r, c.base, c.deep)
    elif n % 3 == 1:
        star(p, x, y, r * 1.1, c.alt, "", rot)
    else:
        glint(p, x, y, r * 1.5, WHITE)


def _m_spark(p, x, y, s, rot, k, n, c):
    if n % 2:
        glint(p, x, y, s * (0.5 + 1.1 * k), c.hot)
    else:
        streak(p, x - math.cos(rot) * s * 1.5 * k, y - math.sin(rot) * s * 1.5 * k,
               x + math.cos(rot) * s * 1.5 * k, y + math.sin(rot) * s * 1.5 * k, s * 0.4, c.alt)


MOTE = {
    "NORMAL": _m_spark, "FIRE": _m_ember, "WATER": _m_drop, "ELECTRIC": _m_zap, "GRASS": _m_leaf,
    "ICE": _m_crystal, "FIGHTING": _m_chip, "POISON": _m_bubble, "GROUND": _m_pebble, "FLYING": _m_feather,
    "PSYCHIC": _m_psi, "BUG": _m_spore, "ROCK": _m_pebble, "GHOST": _m_wisp, "DRAGON": _m_scale,
    "DARK": _m_sliver, "STEEL": _m_glint, "FAIRY": _m_fairy,
}
# 조각이 어떻게 날리나: (중력, 떠오름, 눌림)
MOTE_FLY = {
    "FIRE": (0, 26, 0.7), "WATER": (520, 0, 0.9), "POISON": (120, 12, 0.8), "GROUND": (620, 0, 0.9),
    "ROCK": (620, 0, 0.9), "GHOST": (0, 22, 0.7), "FLYING": (90, 0, 0.8), "GRASS": (110, 0, 0.85),
    "BUG": (60, 8, 0.85), "FAIRY": (0, 14, 0.85), "STEEL": (300, 0, 0.9), "ICE": (200, 0, 0.9),
}


def mote(typ):
    """paint(pen, x, y, 크기, 각, k, 번호) - 그 타입의 조각 하나."""
    c = tone(typ)
    fn = MOTE.get(typ, _m_spark)
    return lambda p, x, y, s, rot, k, n: fn(p, x, y, s, rot, k, n, c)


def scatter(m, typ, born, x, y, n, k=1.0, ang=(0.0, TAU), dist=(20, 50), size=(3.5, 6.5), life=(260, 440)):
    """타입에 맞게 날리는 조각 n 개를 Motes 에 넣는다."""
    g, lift, flat = MOTE_FLY.get(typ, (0, 0, 0.85))
    m.burst(born, n, x, y, dist=(dist[0] * k, dist[1] * k), life=life, ang=ang, g=g, size=(size[0] * k, size[1] * k),
            flat=flat, lift=lift * k)


# ---------------------------------------------------------------- 도트를 밀고 흔든다
class Mover(object):
    """도트 하나를 제자리에서 (x, y) 만큼 비켜 놓는다. 끝나면 home()."""

    def __init__(self, fx, key):
        self.fx, self.key = fx, key
        self.off = [0.0, 0.0]

    def to(self, x, y):
        if self.key is None:
            return
        self.fx.body_move(self.key, x - self.off[0], y - self.off[1])
        self.off = [x, y]

    def home(self):
        self.to(0.0, 0.0)


def jolt(fx, at=0.0, power=1.0, key=None, dur=280):
    """맞은 쪽이 움찔 밀렸다가 떨며 돌아온다 (빗나갔으면 안 한다)."""
    if fx.miss or fx.immune:
        return
    key = fx.keys[1] if key is None else key
    if key is None or key == fx.keys[0]:
        return
    g = fx.geo
    amp = 7.0 * power * (1.25 if fx.eff > 1.0 else 0.7 if fx.eff < 1.0 else 1.0)
    mv = Mover(fx, key)

    def draw(p, u, ms):
        if u < 0.16:
            d = out2(u / 0.16)
        else:
            v = (u - 0.16) / 0.84
            d = (1.0 - v) ** 2 * math.cos(v * math.pi * 3.0)
        mv.to(g.ux * amp * d, g.uy * amp * d * 0.35)
    fx.show.act(at, dur, draw, settle=mv.home, z=-9)


def shake(fx, at, dur, amp=2.5, key=None, vertical=False):
    """도트가 떤다 (광선에 맞는 동안 · 땅이 흔들릴 때)."""
    if fx.miss or fx.immune:
        return
    key = fx.keys[1] if key is None else key
    if key is None:
        return
    mv = Mover(fx, key)

    def draw(p, u, ms):
        d = amp * (1.0 - u * 0.6) * (1 if int(ms / 34) % 2 else -1)
        mv.to(0.0 if vertical else d, d if vertical else 0.0)
    fx.show.act(at, dur, draw, settle=mv.home, z=-9)


def recoil(fx, at, power=1.0, dur=200):
    """쏘는 쪽이 반동으로 뒤로 밀렸다 돌아온다."""
    key = fx.keys[0]
    if key is None or fx.hidden(key):
        return
    g = fx.geo
    mv = Mover(fx, key)

    def draw(p, u, ms):
        d = out2(u / 0.2) if u < 0.2 else 1.0 - inout((u - 0.2) / 0.8)
        mv.to(-g.ux * 4.5 * power * d, -g.uy * 2.0 * power * d)
    fx.show.act(at, dur, draw, settle=mv.home, z=-9)


# ---------------------------------------------------------------- 맞는 순간
IMPACT_MS = 420
IMPACT_KIND = {
    "FIRE": "blaze", "WATER": "splash", "ELECTRIC": "zap", "GRASS": "bloom", "BUG": "bloom", "ICE": "frost",
    "POISON": "splat", "GROUND": "dust", "ROCK": "dust", "FLYING": "gust", "PSYCHIC": "warp", "GHOST": "shade",
    "DARK": "shade", "STEEL": "clang", "FAIRY": "twinkle",
}


def impact(fx, at=0.0, where=None, size=1.0, typ=None, final=True, move=True):
    """맞는 순간을 시간표에 얹는다 (at: 기준 시각에서 몇 ms 뒤). 끝나는 시각을 돌려준다.

      · 타격 프레임   들쭉날쭉한 별 세 겹(가장 어두운 색 - 제 색 - 흰 심)이 두 장 박힌다. 그 사이 맞은 도트가 밀린다.
      · 집중선        맞은 자리에서 바깥으로 뻗는 쐐기
      · 충격파        고리가 퍼지며 가늘어진다
      · 타입의 것     불은 불길이 치솟고, 물은 왕관처럼 튀고, 전기는 가지를 치고, 얼음은 결정이 돋는다 ...
      · 효과가 굉장하면 더 크고 금이 간다 (별로면 작고 조용하다). 급소면 금빛 십자 섬광.

    빗나간 기술(fx.miss)은 과녁 옆 빈 자리에 작게 떨어지고 도트는 안 밀린다.
    """
    sh = fx.show
    typ = typ or fx.type
    c = tone(typ)
    x, y = where or fx.dst
    if (fx.move.get("cat") or "status") == "status" and not fx.move.get("power"):
        if STATUS_HOOK:                                     # 변화기는 때리지 않는다 - 무슨 일이 일어났나를 보여 준다
            return STATUS_HOOK(fx, at)
        return settle(fx, at, x, y, size, typ)
    strong, weak = fx.eff > 1.0, (fx.eff < 1.0 or fx.miss or fx.immune)
    k = size * fx.big * (1.25 if strong else 0.74 if weak else 1.0)
    kind = IMPACT_KIND.get(typ, "smash")
    seed = random.randrange(1000)
    rot = random.uniform(0, math.pi)
    rnd = random.Random(seed)
    m = Motes(seed)
    scatter(m, typ, 20, x, y, 4 if weak else 9 if strong else 7, k, dist=(26, 58), size=(4.5, 8.0),
            life=(280, 400))
    paint = mote(typ)
    rim = c.deep
    body = c.base if typ not in ("GHOST", "DARK") else c.alt
    cracks = []
    if strong:
        for j in range(4):
            a = rot + math.pi / 4 + j * math.pi / 2 + rnd.uniform(-0.3, 0.3)
            rr = rnd.uniform(30, 44) * k
            cracks.append(zigzag(x, y, x + math.cos(a) * rr, y + math.sin(a) * rr * 0.8, 5 * k, 4, rnd))

    wave = c.light if typ not in ("GHOST", "DARK") else c.alt

    def draw(p, u, ms):
        # 충격파 - 굵은 띠가 빠르게 퍼지며 가늘어지다 사라진다 (가는 동심원이 오래 남으면 철사 같다)
        if 30 < ms < 170:
            v = (ms - 30) / 200.0
            r = (16 + 52 * out3(v)) * k
            ring(p, x, y, r, c.deep, int(round(11 * (1 - v) ** 1.2)) + 2, 0.8)
            ring(p, x, y, r, wave, int(round(7 * (1 - v) ** 1.2)) + 1, 0.8)
            if strong:
                ring(p, x, y, r * 1.32, WHITE, int(round(4 * (1 - v))) + 1, 0.8)
        if ms < 150 and not weak:                           # 튀는 불티 - 바깥으로 빠르게 날아가며 짧아진다
            v = ms / 150.0
            for j in range(6):
                a = rot + TAU * j / 6 + 0.5
                r0 = (22 + 54 * out2(v)) * k
                ln = 18 * k * (1 - v)
                streak(p, x + math.cos(a) * r0, y + math.sin(a) * r0 * 0.85, x + math.cos(a) * (r0 + ln),
                       y + math.sin(a) * (r0 + ln) * 0.85, 2.2 * k * (1 - v) + 0.4, c.hot if j % 2 else wave)
        if getattr(p, "raster", False) and ms < 190:        # (그림 바탕) 터지는 빛이 번졌다 빠르게 꺼진다
            f = ms / 190.0
            p.glow(x, y, (26 + 30 * out3(f)) * k, c.base if c.typ not in ("GHOST", "DARK") else c.alt,
                   (1.0 - f) ** 1.5, 0.85)
        _impact_kind(p, kind, c, x, y, k, u, ms, seed, rnd)
        m.draw(p, ms, paint)
        if cracks and ms < 300:
            for q in cracks:
                p.line(q, c.deep, 5, cap="butt")
                p.line(q, WHITE, 2, cap="butt")
        if ms < 150 and not weak:                           # 집중선
            f = out2(ms / 150.0)
            focus(p, x, y, (16 + 30 * f) * k, (40 + 62 * f) * k, 9 if strong else 7, WHITE, seed,
                  w=2.6 * (1 - f * 0.7) * k, alt=c.light)
        if ms < 110:                                        # 타격 프레임
            s = 1.0 if ms < 60 else 0.72
            if ms < 60:
                p.oval(x, y, 24 * k, 20 * k, c.hot)         # 번쩍이는 속
            burst_star(p, x, y, 36 * k * s, 9, rim, seed, rot=rot + (0.0 if ms < 60 else 0.25), sy=0.9)
            burst_star(p, x, y, 27 * k * s, 8, body, seed + 1, rot=rot + 0.3, sy=0.9)
            flare(p, x, y, 17 * k * s, 6, WHITE, inner=0.5, rot=rot + 0.1)
        elif ms < 180:
            flare(p, x, y, 13 * k * (1.0 - (ms - 110) / 90.0) + 2, 4, WHITE, inner=0.3, rot=rot)
        if fx.crit and ms < 240:                            # 급소 - 금빛 십자
            f = ms / 240.0
            ln = (46 - 14 * f) * k
            th = max(0.8, 5.5 * (1 - f)) * k
            for a in (rot * 0.2 - 0.5, rot * 0.2 + 1.07):
                ca, sa = math.cos(a), math.sin(a)
                streak(p, x - ca * ln, y - sa * ln, x + ca * ln, y + sa * ln, th + 1.5, GOLD)
                streak(p, x - ca * ln * 0.8, y - sa * ln * 0.8, x + ca * ln * 0.8, y + sa * ln * 0.8, th * 0.5, WHITE)
    end = sh.act(at, IMPACT_MS, draw, z=5)
    if move:
        jolt(fx, at, power=min(1.6, 0.8 + 0.5 * size * fx.big) * (1.3 if fx.crit else 1.0))
    return end


def _impact_kind(p, kind, c, x, y, k, u, ms, seed, rnd):
    """타입마다 다른, 맞은 자리의 모습."""
    if kind == "blaze":                                     # 불길이 치솟는다
        if ms < 330:
            f = fade(ms / 330.0, 0.2, 0.55)
            for j in range(5):
                r = (13 + 5 * math.sin(ms * 0.03 + j * 2.1)) * k * f * (1.2 - abs(j - 2) * 0.17)
                flame(p, x + (j - 2) * 11 * k, y + 16 * k - r * 0.4, r, snoise(seed + j + int(ms / 45)) * 5,
                      (c.dark, c.base if j % 2 else c.light, c.hot))
        if 160 < ms:
            v = (ms - 160) / 260.0
            for j in range(2):
                smoke(p, x + (j * 2 - 1) * 12 * k, y - (8 + 34 * v) * k, (9 - 3 * v) * k, 1 - v, seed + j)
    elif kind == "splash":                                  # 물왕관
        if ms < 300:
            f = ms / 300.0
            up = hump(min(1.0, f * 1.15))
            cr = (20 + 14 * out2(f)) * k
            pts = []
            for q in range(13):
                a = math.pi + math.pi * q / 12.0
                rq = cr * (1.0 if q % 2 else 0.5)
                pts += [x + math.cos(a) * rq * 1.1, y + 8 * k + math.sin(a) * rq * (0.5 + 0.9 * up)]
            p.poly(pts, c.base, c.deep, 1)
            p.oval(x, y + 8 * k, cr * 1.1, cr * 0.26, c.light, c.dark, 1)
            p.oval(x, y + 8 * k, cr * 0.6, cr * 0.13, c.hot)
    elif kind == "zap":                                     # 가지를 치는 전기
        if ms < 260 and int(ms / 40) % 3 != 2:
            r2 = random.Random(seed + int(ms / 40))
            for j in range(5):
                a = TAU * j / 5 + r2.uniform(-0.4, 0.4)
                rr = r2.uniform(26, 46) * k
                bolt(p, zigzag(x, y, x + math.cos(a) * rr, y + math.sin(a) * rr * 0.85, 7 * k, 4, r2), 1,
                     (c.dark, c.base, c.hot))
    elif kind == "frost":                                   # 결정이 돋았다가 깨진다
        f = fade(u, 0.14, 0.6)
        for j in range(6):
            a = j * math.pi / 3 + 0.26 + seed
            ln = (22 + 8 * noise(seed + j)) * k * f
            if ln > 2:
                spike(p, x + math.cos(a) * 5 * k, y + math.sin(a) * 5 * k, 4.5 * k, ln, a, c.light, c.dark)
                spike(p, x + math.cos(a) * 5 * k, y + math.sin(a) * 5 * k, 1.8 * k, ln * 0.8, a, WHITE)
    elif kind == "bloom":                                   # 감아 도는 잎바람
        if ms < 300:
            f = ms / 300.0
            arcs(p, x, y, (18 + 22 * f) * k, c.light, max(1, int(4 * (1 - f))), ms * 1.4, 3, 80, 0.7)
            arcs(p, x, y, (10 + 16 * f) * k, c.alt, max(1, int(3 * (1 - f))), -ms * 1.8, 2, 100, 0.7)
    elif kind == "splat":                                   # 철퍽 퍼지고 흘러내린다
        if ms < 380:
            f = ms / 380.0
            r = (14 + 14 * out3(f * 2)) * k * (1.0 - 0.5 * in2(f))
            flare(p, x, y, r * 1.5, 7, c.deep, inner=0.55, rot=seed, sy=0.8)
            blob(p, x, y, r, c.dark, seed, wob=ms * 0.02, sy=0.82, outline=c.alt, width=2)
            blob(p, x - r * 0.15, y - r * 0.15, r * 0.5, c.base, seed + 2, wob=ms * 0.02, sy=0.82)
            for j in range(3):
                dx = (j - 1) * 11 * k
                drop(p, x + dx, y + (10 + 30 * f) * k, (4 - 2 * f) * k, -math.pi / 2, c.base, c.deep)
    elif kind == "dust":                                    # 발밑에서 먼지가 번지고 돌이 튄다
        f = out2(u)
        for j in range(4):
            sgn = -1 if j % 2 else 1
            dx = sgn * (12 + (14 + 10 * (j // 2)) * f) * k
            r = (9 - 2 * (j // 2)) * k * (1.0 - 0.75 * in2(u))
            blob(p, x + dx, y + (17 - 5 * (j // 2) * f) * k, r, c.light if j < 2 else c.base, seed + j, wob=ms * 0.01,
                 n=8, jag=0.2, outline=c.dark)
    elif kind == "gust":                                    # 휘감는 바람
        if ms < 320:
            f = ms / 320.0
            for j in range(3):
                r = (14 + j * 9 + 14 * f) * k
                p.arc(x, y - (j - 1) * 5 * k, r, r * 0.42, (ms * 1.6 + j * 120) % 360, 150,
                      WHITE if j == 1 else c.light, max(1, int((4 - j) * (1 - f * 0.7))))
    elif kind == "warp":                                    # 공간이 조였다가 퍼진다
        if ms < 340:
            f = ms / 340.0
            rr = (34 - 22 * hump(f)) * k
            sigil(p, x, y, rr, ms * 0.012, c.alt, 2, 0.8)
            arcs(p, x, y, rr * 1.35, c.light, 2, -ms * 1.2, 4, 50, 0.8)
    elif kind == "shade":                                   # 어둠이 오그라든다
        if ms < 300:
            f = ms / 300.0
            r = (30 - 22 * out2(f)) * k
            blob(p, x, y, r, c.deep, seed, wob=ms * 0.03, n=10, jag=0.35, outline=c.light, width=1)
            streak(p, x - r * 1.5, y, x + r * 1.5, y, max(1.0, 4 * (1 - f)) * k, c.alt)
    elif kind == "clang":                                   # 쇠의 번쩍임
        if ms < 220:
            f = ms / 220.0
            ln = (30 + 34 * out2(f)) * k
            th = max(0.8, 3.5 * (1 - f)) * k
            streak(p, x - ln * 1.3, y, x + ln * 1.3, y, th, WHITE)
            streak(p, x, y - ln, x, y + ln, th, WHITE)
            flare(p, x, y, ln * 0.5, 4, c.light, inner=0.3, rot=math.pi / 4)
    elif kind == "twinkle":                                 # 별빛이 돈다
        if ms < 360:
            f = ms / 360.0
            for j in range(5):
                a = TAU * j / 5 + ms * 0.006
                rr = (16 + 22 * out2(f)) * k
                glint(p, x + math.cos(a) * rr, y + math.sin(a) * rr * 0.8,
                      (5 + 5 * abs(math.sin(ms * 0.02 + j))) * k * (1 - f * 0.6), WHITE if j % 2 else c.alt)
    else:                                                   # 정통으로 맞았다
        if ms < 200:
            f = ms / 200.0
            flare(p, x, y, (22 + 22 * out2(f)) * k, 4, WHITE, inner=0.12 + 0.1 * (1 - f), rot=math.pi / 4 + seed)


STATUS_HOOK = None              # fx_status.outcome 이 여기 걸린다 (변화기가 닿은 뒤의 모습: 랭크 · 상태이상 · 회복)


def settle(fx, at, x, y, size=1.0, typ=None):
    """변화기가 걸리는 순간: 별도 충격도 없이 고리 하나가 퍼지고 타입의 조각이 조용히 흩어진다."""
    typ = typ or fx.type
    c = tone(typ)
    k = size
    m = Motes(random.randrange(1000))
    scatter(m, typ, 0, x, y, 5, k * 0.8, dist=(14, 34), life=(260, 380))
    paint = mote(typ)

    def draw(p, u, ms):
        if u < 0.6:
            ring(p, x, y, (10 + 32 * out2(u / 0.6)) * k, c.light, int(4 * (1 - u / 0.6)) + 2, 0.8)
        if u < 0.5:
            glint(p, x, y - 4, 14 * k * (1 - u * 2) + 2, WHITE)
        m.draw(p, ms, paint)
    return fx.show.act(at, 320, draw, z=5)


def mini(fx, at, x, y, k=0.7, typ=None, n=3):
    """작은 타격 하나 (연속기의 한 대 · 조각이 꽂히는 자리)."""
    c = tone(typ or fx.type)
    k = k * fx.big
    seed = random.randrange(1000)
    rot = random.uniform(0, math.pi)
    m = Motes(seed)
    if n:
        scatter(m, typ or fx.type, 0, x, y, n, k * 0.8, life=(160, 260))
    paint = mote(typ or fx.type)

    def draw(p, u, ms):
        if ms < 80:
            burst_star(p, x, y, 21 * k, 7, c.deep, seed, rot=rot, sy=0.9)
            burst_star(p, x, y, 15 * k, 6, WHITE, seed + 1, rot=rot + 0.3, sy=0.9)
        if u < 0.5:
            ring(p, x, y, (8 + 26 * out2(u * 2)) * k, c.light, int(5 * (1 - u * 2)) + 2, 0.8)
        m.draw(p, ms, paint)
    return fx.show.act(at, 260, draw, z=4)


# ---------------------------------------------------------------- 달려든다
def rush(fx, then, trail=True):
    """접촉기: 몸이 달려드는 동안(무대의 lunge) 그 길에 잔상 띠와 속도선이 남고, 닿는 순간 then().

    몸을 옮기는 것은 무대다. then 안에서 넣는 것들의 시각(at)은 닿는 순간이 0 이다.
    """
    sh = fx.show
    g, c, k = fx.geo, fx.c, fx.big
    reach = max(0.0, 1.0 - 30.0 / g.d)
    state = {"hit": False, "guard": None}
    cols = c.tri

    def draw(p, u, ms):
        if state["hit"]:
            return
        head = reach * out2(min(1.0, ms / 130.0))
        tail = reach * in2(min(1.0, ms / 230.0)) * 0.96
        if ms < 90:                                         # 박차는 발밑
            f = ms / 90.0
            for sgn in (-1, 1):
                blob(p, g.sx - g.ux * (6 + 14 * f) + sgn * 5, g.gs - 2 - 4 * f, (7 - 3 * f) * k, c.light, sgn + 5,
                     n=7, jag=0.2, outline=c.dark)
        if head - tail < 0.03:
            return
        pts = g.path(tail, head, 6)
        glow_ribbon(p, pts, widths(6, 9.5 * k, "comet"), cols)
        for j, off in enumerate((-17, -8, 8, 17)):          # 속도선
            u0 = tail + (head - tail) * (0.1 + 0.12 * (j % 2))
            x1, y1 = g.at(u0, off * k)
            x2, y2 = g.at(head - 0.03, off * 0.5 * k)
            streak(p, x1, y1, x2, y2, 1.4 * k, WHITE if j in (1, 2) else c.light)

    def hit():
        if state["hit"] or fx.dead:
            return
        state["hit"] = True
        sh.cancel(state["guard"])
        sh.release()
        sh.rebase()
        then()

    if trail:
        sh.act(0, 420, draw, z=-2)
    sh.hold()
    state["guard"] = sh.cue(900, hit)                       # 무대가 신호를 안 주면 (창이 바뀌는 중) 그냥 닿은 것으로
    fx.st.lunge(fx.who, hit)
