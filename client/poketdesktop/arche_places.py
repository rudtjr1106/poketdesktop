# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 — 장소 그림 (동굴 · 화산 · 심해 · 하늘 · 고성 · 왕좌).

**낮은 해상도(높이 약 135칸)에 손으로 찍듯 그리고 NEAREST 로 키운다.** 명암은 3단 + 4x4 바이어 디더,
빛은 디더로 번지는 원 (glow). 장소마다 대표 빛깔이 다르다 (동굴 청록 · 화산 주황 · 심해 하늘빛 · 하늘 금빛 ·
고성 모래 금 · 왕좌 보라).

    render(place, w, h, state, t, marks)   -> RGB w x h
        state  sealed  봉인된 입구 (일지의 발굴 사진)
               open    열린 입구 (의식이 맞은 뒤 · 입장 장면)
               inside  안쪽 (전설 배틀 배경 - 상대 받침 (0.70, 0.50) · 내 받침 (0.28, 0.93) 자리를 비워 둔다)
        t      움직임 차례 (횃불 · 물결 · 별)
        marks  입구 판에 새길 아르케 글자 번호 목록들 (없으면 빈 판). 무슨 뜻인지는 여기서 모른다.

입장 장면은 arche_art.entry_frames 가 이 그림들을 이어 붙여 만든다.
"""
import functools
import hashlib
import math
import random

from PIL import Image, ImageDraw

BASE_H = 135

BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def _th(x, y):
    return (BAYER[y & 3][x & 3] + 0.5) / 16.0


def _mix(a, b, k):
    return (int(a[0] + (b[0] - a[0]) * k), int(a[1] + (b[1] - a[1]) * k), int(a[2] + (b[2] - a[2]) * k))


def _rng(*parts):
    return random.Random(int(hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest()[:12], 16))


class Cv(object):
    """낮은 해상도 그림판. 좌표는 칸 단위, 사각형은 끝점 포함."""

    def __init__(self, w, h, c=(0, 0, 0)):
        self.w, self.h = w, h
        self.im = Image.new("RGB", (w, h), c)
        self.px = self.im.load()
        self.d = ImageDraw.Draw(self.im)

    def put(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = c

    def get(self, x, y):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[x, y]
        return (0, 0, 0)

    def rect(self, x0, y0, x1, y1, c):
        x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
        if x1 < x0 or y1 < y0:
            return
        self.d.rectangle([x0, y0, x1, y1], fill=c)

    def poly(self, pts, c):
        self.d.polygon([(int(round(x)), int(round(y))) for x, y in pts], fill=c)

    def line(self, pts, c, w=1):
        self.d.line([(int(round(x)), int(round(y))) for x, y in pts], fill=c, width=w)

    def ellipse(self, cx, cy, rx, ry, c, outline=None):
        self.d.ellipse([int(cx - rx), int(cy - ry), int(cx + rx), int(cy + ry)], fill=c, outline=outline)

    def grad(self, y0, y1, cols, x0=0, x1=None):
        """세로 띠 그러데이션 (띠 사이는 디더)."""
        x1 = self.w - 1 if x1 is None else int(x1)
        y0, y1 = int(y0), int(min(self.h - 1, y1))
        n = len(cols) - 1
        span = max(1, y1 - y0)
        for y in range(max(0, y0), y1 + 1):
            f = (y - y0) / float(span) * n
            i = min(n - 1, int(f))
            fr = f - i
            a, b = cols[i], cols[i + 1]
            for x in range(max(0, int(x0)), x1 + 1):
                self.px[x, y] = b if fr > _th(x, y) else a

    def glow(self, cx, cy, r, c, a=0.6, ry=None, steps=3):
        """디더로 번지는 빛 (가운데일수록 c 쪽으로)."""
        ry = ry or r
        for y in range(max(0, int(cy - ry)), min(self.h, int(cy + ry) + 1)):
            dy = (y - cy) / float(ry)
            for x in range(max(0, int(cx - r)), min(self.w, int(cx + r) + 1)):
                dx = (x - cx) / float(r)
                dd = dx * dx + dy * dy
                if dd >= 1:
                    continue
                lv = (1 - dd) * steps
                L = int(lv)
                if lv - L > _th(x, y):
                    L += 1
                if L <= 0:
                    continue
                self.px[x, y] = _mix(self.px[x, y], c, a * L / float(steps))

    def shade(self, x0, y0, x1, y1, c, k):
        """사각형 안을 c 쪽으로 k 만큼 (디더 반칸)."""
        for y in range(max(0, int(y0)), min(self.h, int(y1) + 1)):
            for x in range(max(0, int(x0)), min(self.w, int(x1) + 1)):
                self.px[x, y] = _mix(self.px[x, y], c, k)

    def vignette(self, c=(0, 0, 0), k=0.5):
        """가장자리를 c 쪽으로 (가운데는 그대로, 8단 디더라 테 자국이 안 남는다)."""
        cx, cy = (self.w - 1) / 2.0, (self.h - 1) / 2.0
        for y in range(self.h):
            dy = (y - cy) / cy
            for x in range(self.w):
                dx = (x - cx) / cx
                dd = (dx * dx * 0.55 + dy * dy * 0.75)
                if dd <= 0.30:
                    continue
                lv = min(1.0, (dd - 0.30) / 0.75) * 8
                L = int(lv)
                if lv - L > _th(x, y):
                    L += 1
                if L:
                    self.px[x, y] = _mix(self.px[x, y], c, k * L / 8.0)


# ---------------------------------------------------------------- 공용 조각
def _stars(cv, R, n, x0, y0, x1, y1, t, col=(150, 162, 205)):
    for i in range(n):
        x, y = R.randint(x0, x1), R.randint(y0, y1)
        tw = (i * 7 + t) % 11 == 0
        cv.put(x, y, (255, 255, 255) if tw else col)
        if i % 9 == 0:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cv.put(x + dx, y + dy, _mix(cv.get(x + dx, y + dy), col, 0.5))


def _ridge(cv, R, base, amp, col, rough=1.6, x0=0, x1=None, hi=None, smooth=0.9):
    """왼쪽에서 오른쪽으로 이어진 산등성이. 꼭대기 한 줄은 hi."""
    x1 = cv.w if x1 is None else x1
    y = base + R.uniform(-amp, amp)
    v = 0.0
    tops = []
    for x in range(int(x0), int(x1)):
        v = v * smooth + R.uniform(-rough, rough)
        y = max(base - amp, min(base + amp, y + v * 0.5))
        tops.append(int(y))
        cv.rect(x, y, x, cv.h - 1, col)
        if hi:
            cv.put(x, y, hi)
    return tops


def _speck(cv, R, x0, y0, x1, y1, n, cols, only=None):
    for _ in range(n):
        x, y = R.randint(int(x0), int(x1)), R.randint(int(y0), int(y1))
        if only is None or cv.get(x, y) == only:
            cv.put(x, y, R.choice(cols))


def _boulders(cv, R, x0, x1, ytop_fn, ybot, cols, n=40, rmin=5, rmax=14):
    """둥근 바위를 겹쳐 쌓은 절벽 면. ytop_fn(x) 위로는 안 넘는다. cols = (어둠, 중간, 밝음, 윤곽)."""
    dark, mid, light, edge = cols
    for i in range(n):
        x = R.uniform(x0, x1)
        r = R.uniform(rmin, rmax)
        top = ytop_fn(int(max(0, min(cv.w - 1, x))))
        y = R.uniform(top + r * 0.6, ybot)
        ry = r * R.uniform(0.6, 0.9)
        cv.ellipse(x, y, r, ry, mid, outline=edge)
        # 위 왼쪽 밝은 면 · 아래 오른쪽 그늘
        cv.d.arc([int(x - r + 1), int(y - ry + 1), int(x + r - 1), int(y + ry - 1)], 190, 290, fill=light)
        cv.d.chord([int(x - r * 0.2), int(y), int(x + r - 1), int(y + ry - 1)], 0, 180, fill=dark)


def _blocks(cv, x0, y0, x1, y1, light, mid, mortar, bw=6, bh=4):
    """돌 벽돌 (줄마다 반 칸 어긋남)."""
    for j, y in enumerate(range(int(y0), int(y1) + 1, bh)):
        off = (bw // 2) if j % 2 else 0
        for x in range(int(x0) - off, int(x1) + 1, bw):
            a, b = max(int(x0), x), min(int(x1), x + bw - 2)
            if b < a:
                continue
            cv.rect(a, y, b, min(int(y1), y + bh - 2), mid)
            cv.rect(a, y, b, y, light)
        cv.rect(x0, min(int(y1), y + bh - 1), x1, min(int(y1), y + bh - 1), mortar)


def _torch(cv, x, y, t, n=0):
    cv.glow(x + 1, y - 4, 16, (255, 160, 70), 0.30)
    cv.glow(x + 1, y - 4, 7, (255, 190, 90), 0.35)
    cv.rect(x, y, x + 1, y + 13, (92, 60, 34))
    cv.rect(x - 1, y, x + 2, y + 1, (60, 38, 20))
    f = (t + n) % 3
    cv.rect(x, y - 4, x + 1, y - 1, (229, 83, 45))
    cv.put(x - (1 if f == 0 else 0), y - 3, (255, 154, 60))
    cv.put(x + (2 if f == 1 else 1), y - 5, (255, 154, 60))
    cv.put(x + (f == 2), y - 6, (255, 210, 122))
    cv.put(x, y - 2, (255, 230, 160))
    cv.put(x + 1, y - 3, (255, 210, 122))


def _plates(cv, x0, y, n, marks, lit, dark, glyph_col, dim_col, pw=9, ph=11, gap=3):
    """판 n 개에 아르케 글자를 새긴다. marks[i] = 글자 번호 목록 (판마다 첫 글자만 크게)."""
    from .arche_art import GLYPHS
    for i in range(n):
        px = x0 + i * (pw + gap)
        cv.rect(px, y, px + pw - 1, y + ph - 1, dark)
        cv.rect(px, y, px + pw - 1, y, _mix(dark, (255, 255, 255), 0.15))
        g = None
        if marks and i < len(marks) and marks[i]:
            g = GLYPHS[int(marks[i][0]) % len(GLYPHS)]
        if g:
            col = glyph_col if (lit is True or (isinstance(lit, int) and not isinstance(lit, bool) and i < lit)) else dim_col
            for yy, row in enumerate(g):
                for xx, ch in enumerate(row):
                    if ch == "#":
                        cv.put(px + 1 + xx, y + 1 + yy, col)


# ---------------------------------------------------------------- 동굴
def _cave(cv, st, t, R, marks):
    W, H = cv.w, cv.h
    if st == "inside":
        return _cave_inside(cv, t, R, marks)
    cv.grad(0, H * 0.55, [(8, 11, 24), (11, 16, 33), (15, 22, 44), (21, 30, 56)])
    _stars(cv, _rng("cave-stars"), 70, 0, 0, W - 1, int(H * 0.42), t)
    mx, my = W * 0.84, H * 0.15
    cv.glow(mx, my, 14, (190, 200, 255), 0.18)
    cv.ellipse(mx, my, 4, 4, (230, 234, 246))
    cv.ellipse(mx + 2, my - 1, 4, 4, (14, 20, 40))
    _ridge(cv, _rng("cave-m1"), H * 0.40, H * 0.07, (27, 34, 58), hi=(38, 46, 74))
    _ridge(cv, _rng("cave-m2"), H * 0.48, H * 0.06, (21, 27, 46))
    gy = int(H * 0.80)
    # 절벽 - 가운데가 높다. 바위 덩어리를 쌓고 위에 이끼, 가로 지층.
    RR = _rng("cave-cliff")
    top = H * 0.2
    tops = []
    for x in range(W):
        top += RR.uniform(-1.4, 1.4)
        e = abs(x - W / 2.0) / (W / 2.0)
        tops.append(int(max(H * 0.10, min(H * 0.36, top + e * e * H * 0.32))))
    for x in range(W):
        cv.rect(x, tops[x], x, gy, (38, 43, 56))
    _boulders(cv, RR, -10, W + 10, lambda x: tops[x], gy + 4, ((28, 31, 41), (44, 49, 63), (70, 78, 96), (24, 27, 36)), n=120, rmin=6, rmax=18)
    for x in range(W):                      # 꼭대기 선 · 이끼
        for y in range(0, tops[x]):
            pass
        cv.rect(x, 0, x, tops[x] - 1, cv.get(x, 0)) if False else None
    for x in range(W):
        cv.put(x, tops[x], (90, 98, 118))
        if RR.random() < 0.45:
            cv.put(x, tops[x] - 1, (52, 88, 70))
            if RR.random() < 0.3:
                cv.put(x, tops[x] - 2, (64, 108, 80))
    for k in range(5):                      # 지층
        y0 = H * (0.42 + k * 0.08)
        for x in range(W):
            y = int(y0 + math.sin(x * 0.05 + k) * 2)
            if y > tops[x] + 2 and RR.random() < 0.8:
                cv.put(x, y, (30, 34, 45))
    _speck(cv, RR, 0, H * 0.3, W - 1, gy, 260, [(58, 64, 80), (30, 33, 44)])
    # 땅
    cv.grad(gy, H - 1, [(30, 33, 44), (22, 25, 34), (15, 17, 24)])
    _speck(cv, RR, 0, gy + 2, W - 1, H - 1, 70, [(40, 44, 56), (36, 60, 50)])
    # 돌문
    dw, dh = int(W * 0.17), int(H * 0.40)
    dx0 = int(W / 2 - dw / 2)
    dx1 = dx0 + dw
    dy0 = gy - dh
    _blocks(cv, dx0 - 6, dy0 - 4, dx1 + 6, gy - 1, (122, 126, 140), (92, 96, 110), (56, 60, 72), bw=7, bh=5)
    # 아치 꼭대기
    for s in range(7):
        cv.rect(dx0 - 6 + s, dy0 - 10 + s, dx1 + 6 - s, dy0 - 10 + s, (112, 116, 130) if s % 2 else (126, 130, 146))
    cv.rect(dx0 + dw // 2 - 3, dy0 - 12, dx0 + dw // 2 + 3, dy0 - 5, (138, 142, 158))
    cv.put(dx0 + dw // 2, dy0 - 9, (95, 227, 208) if st == "open" else (60, 120, 112))
    ix0, ix1, iy0 = dx0 + 2, dx1 - 2, dy0 + 2
    if st == "sealed":
        cv.rect(ix0, iy0, ix1, gy - 1, (74, 78, 92))
        cv.rect(ix0, iy0, ix1, iy0, (96, 100, 116))
        cv.rect(ix0 + (ix1 - ix0) // 2, iy0, ix0 + (ix1 - ix0) // 2, gy - 1, (44, 47, 58))
        for y in range(iy0 + 4, gy - 2, 6):
            cv.rect(ix0 + 2, y, ix1 - 2, y, (66, 70, 84))
        n = 3
        pw, gap = 9, 3
        x0 = ix0 + ((ix1 - ix0 + 1) - (n * pw + (n - 1) * gap)) // 2
        lit = (t // 3) % 4 if marks else 0
        _plates(cv, x0, iy0 + 5, n, marks, lit, (30, 36, 46), (95, 227, 208), (47, 87, 82))
    else:
        cv.rect(ix0, iy0, ix1, gy - 1, (6, 8, 13))
        cv.glow((ix0 + ix1) / 2.0, gy - 4, (ix1 - ix0) * 0.7, (95, 227, 208), 0.55, ry=dh * 0.9)
        cv.rect(ix0, iy0, ix0 + 2, gy - 1, (74, 78, 92))
        cv.rect(ix1 - 2, iy0, ix1, gy - 1, (74, 78, 92))
        cv.glow((ix0 + ix1) / 2.0, gy + 6, dw * 1.1, (95, 227, 208), 0.25, ry=10)
    for s in range(3):
        cv.rect(dx0 - 5 - s * 4, gy + s * 3, dx1 + 5 + s * 4, gy + s * 3 + 2, (84, 88, 102) if s % 2 else (98, 102, 118))
        cv.rect(dx0 - 5 - s * 4, gy + s * 3, dx1 + 5 + s * 4, gy + s * 3, (124, 128, 144))
    _torch(cv, dx0 - 14, gy - 20, t, 0)
    _torch(cv, dx1 + 12, gy - 20, t, 1)
    cv.vignette((2, 3, 8), 0.65)


def _cave_inside(cv, t, R, marks):
    W, H = cv.w, cv.h
    cv.grad(0, H - 1, [(10, 13, 22), (16, 20, 32), (22, 27, 40), (14, 17, 26)])
    RR = _rng("cave-in")
    from .arche_art import GLYPHS
    # 벽에 새긴 글자 줄 (흐릿한 청록)
    for row, y in enumerate((int(H * 0.16), int(H * 0.30))):
        x = 4 + row * 5
        while x < W - 10:
            g = GLYPHS[RR.randrange(len(GLYPHS))]
            for yy, r in enumerate(g):
                for xx, ch in enumerate(r):
                    if ch == "#":
                        cv.put(x + xx, y + yy, (34, 70, 70) if (x // 9 + t) % 7 else (60, 140, 128))
            x += 11
    # 종유석
    for i in range(18):
        x = RR.randint(0, W - 1)
        ln = RR.randint(4, 18)
        for y in range(ln):
            w = max(0, 2 - y * 3 // ln)
            cv.rect(x - w, y, x + w, y, (38, 43, 56) if y < ln - 1 else (70, 78, 96))
    # 바닥
    fy = int(H * 0.58)
    cv.grad(fy, H - 1, [(26, 30, 42), (20, 23, 33), (13, 15, 22)])
    cv.rect(0, fy, W - 1, fy, (52, 58, 74))
    _speck(cv, RR, 0, fy + 1, W - 1, H - 1, 160, [(34, 38, 52), (18, 20, 28)])
    # 받침 둘 (청록 빛 고리)
    for (fx, fyy, rx, ry, a) in ((0.70, 0.50, 0.17, 0.05, 0.5), (0.28, 0.93, 0.21, 0.06, 0.35)):
        cx, cy = W * fx, H * fyy
        cv.glow(cx, cy, W * rx * 1.2, (95, 227, 208), 0.22, ry=H * ry * 2.2)
        cv.ellipse(cx, cy, W * rx, H * ry, (40, 46, 62), outline=(70, 150, 140))
        cv.ellipse(cx, cy - 1, W * rx - 3, H * ry - 2, (48, 54, 72))
    # 기둥 빛
    for x in (int(W * 0.06), int(W * 0.94)):
        cv.rect(x - 3, int(H * 0.08), x + 3, fy, (30, 34, 46))
        cv.rect(x - 3, int(H * 0.08), x - 2, fy, (52, 58, 76))
    cv.glow(W * 0.70, H * 0.22, W * 0.25, (95, 227, 208), 0.10, ry=H * 0.25)
    cv.vignette((2, 3, 8), 0.6)


# ---------------------------------------------------------------- 화산
def _volcano(cv, st, t, R, marks):
    W, H = cv.w, cv.h
    if st == "inside":
        return _volcano_inside(cv, t, R)
    cv.grad(0, H * 0.7, [(18, 8, 14), (40, 14, 18), (78, 26, 22), (120, 44, 28)])
    RR = _rng("vol")
    _stars(cv, _rng("vol-s"), 18, 0, 0, W - 1, int(H * 0.2), t, col=(150, 110, 120))
    # 먼 산
    _ridge(cv, _rng("vol-m"), H * 0.56, H * 0.06, (48, 18, 20))
    # 화산 몸
    cx = W * 0.58
    top = H * 0.20
    base = H * 0.84
    for y in range(int(top), int(base)):
        f = max(0.0, (y - top) / (base - top))
        half = W * (0.07 + 0.36 * f ** 1.25)
        x0, x1 = int(cx - half), int(cx + half)
        cv.rect(x0, y, x1, y, (44, 24, 24))
        cv.put(x0, y, (90, 46, 36))
        cv.rect(x0 + 1, y, x0 + int(half * 0.35), y, (56, 30, 28))
    # 분화구 빛 · 용암 줄기
    cv.glow(cx, top + 2, W * 0.16, (255, 120, 50), 0.55, ry=H * 0.10)
    cv.rect(cx - W * 0.06, top - 1, cx + W * 0.06, top + 1, (255, 170, 70))
    cv.rect(cx - W * 0.04, top - 2, cx + W * 0.04, top - 2, (255, 230, 150))
    for k, (dx, ln) in enumerate(((-0.03, 0.30), (0.02, 0.42), (0.05, 0.22))):
        x = cx + W * dx
        for y in range(int(top + 2), int(top + 2 + H * ln)):
            x += RR.choice((-0.5, 0, 0.5, 0.6))
            cv.put(x, y, (255, 120 + ((y + t * 2 + k * 5) % 9) * 10, 40))
            cv.put(x + 1, y, (190, 60, 30))
    # 연기
    for i in range(14):
        sx = cx + RR.uniform(-8, 8) + i * 1.8
        sy = top - 6 - i * 3.2
        r = 3 + i * 0.6
        cv.glow(sx + math.sin((t + i) * 0.7) * 1.5, sy, r * 1.4, (70, 54, 58), 0.55, ry=r)
    # 재
    for i in range(40):
        x = (RR.randint(0, W) + t * 2) % W
        y = (RR.randint(0, int(H * 0.8)) + t) % int(H * 0.8)
        cv.put(x, y, (255, 140, 70) if i % 4 == 0 else (120, 90, 90))
    # 앞 현무암 절벽 · 흑요석 문
    gy = int(H * 0.86)
    cv.grad(gy, H - 1, [(30, 16, 16), (20, 10, 12)])
    VV = _rng("vol-rocks")
    _boulders(cv, VV, -8, W * 0.40, lambda x: int(gy - H * 0.16), gy + 3, ((28, 14, 16), (46, 26, 26), (92, 52, 42), (22, 10, 12)), n=26, rmin=5, rmax=12)
    _boulders(cv, VV, W * 0.60, W + 8, lambda x: int(gy - H * 0.16), gy + 3, ((28, 14, 16), (46, 26, 26), (92, 52, 42), (22, 10, 12)), n=26, rmin=5, rmax=12)
    gx0, gx1 = int(W * 0.43), int(W * 0.57)
    gy0 = int(gy - H * 0.30)
    cv.rect(gx0 - 4, gy0 - 4, gx1 + 4, gy, (24, 14, 18))
    cv.rect(gx0 - 4, gy0 - 4, gx1 + 4, gy0 - 3, (70, 40, 44))
    if st == "sealed":
        cv.rect(gx0, gy0, gx1, gy, (16, 10, 14))
        cv.rect((gx0 + gx1) // 2, gy0, (gx0 + gx1) // 2, gy, (60, 24, 20))
        n = 2
        _plates(cv, (gx0 + gx1) // 2 - 10, gy0 + 6, n, marks, (t // 3) % 3, (30, 14, 16), (255, 140, 60), (100, 40, 30))
        for y in range(gy0 + 2, gy, 5):        # 갈라진 틈의 붉은 빛
            cv.put(gx0 + 2 + (y * 7) % (gx1 - gx0 - 4), y, (200, 70, 40))
    else:
        cv.rect(gx0, gy0, gx1, gy, (60, 18, 10))
        cv.glow((gx0 + gx1) / 2.0, gy - 2, (gx1 - gx0) * 0.9, (255, 150, 60), 0.7, ry=(gy - gy0))
    cv.glow((gx0 + gx1) / 2.0, gy + 3, W * 0.14, (255, 120, 50), 0.25, ry=6)
    cv.vignette((8, 2, 2), 0.6)


def _volcano_inside(cv, t, R):
    W, H = cv.w, cv.h
    RR = _rng("vol-in")
    cv.grad(0, H - 1, [(26, 8, 10), (54, 16, 14), (40, 14, 14), (20, 8, 10)])
    # 분화구 벽
    for side in (0, 1):
        for y in range(H):
            w = int(W * (0.16 + 0.10 * math.sin(y * 0.09 + side)) * (1 - y / float(H) * 0.4))
            xs = range(0, w) if side == 0 else range(W - w, W)
            for x in xs:
                cv.put(x, y, (44, 22, 22) if (x + y // 3) % 7 else (60, 30, 28))
    # 용암 호수
    ly = int(H * 0.62)
    cv.grad(ly, H - 1, [(255, 120, 40), (220, 70, 30), (150, 40, 24)])
    for i in range(70):
        x = (RR.randint(0, W) + t * 3) % W
        y = RR.randint(ly, H - 1)
        cv.put(x, y, (255, 210, 120))
    cv.glow(W * 0.5, ly, W * 0.6, (255, 140, 60), 0.35, ry=H * 0.25)
    # 바위 받침
    for (fx, fy, rx, ry) in ((0.70, 0.50, 0.17, 0.05), (0.28, 0.93, 0.22, 0.07)):
        cx, cy = W * fx, H * fy
        cv.ellipse(cx, cy + 3, W * rx, H * ry + 4, (34, 18, 18))
        cv.ellipse(cx, cy, W * rx, H * ry, (66, 36, 32), outline=(110, 60, 44))
    # 불티
    for i in range(30):
        x = RR.randint(0, W - 1)
        y = (RR.randint(0, H) - t * 2) % H
        cv.put(x, y, (255, 180, 90))
    cv.vignette((6, 0, 0), 0.6)


# ---------------------------------------------------------------- 심해
def _abyss(cv, st, t, R, marks):
    W, H = cv.w, cv.h
    if st == "inside":
        return _abyss_inside(cv, t, R)
    cv.grad(0, H - 1, [(30, 92, 140), (14, 58, 104), (8, 34, 70), (4, 18, 40), (2, 10, 24)])
    RR = _rng("abyss")
    # 빛줄기
    for k in range(5):
        x = W * (0.15 + k * 0.18) + math.sin(t * 0.3 + k) * 2
        for y in range(int(H * 0.75)):
            w = 2 + y // 14
            for xx in range(int(x + y * 0.35), int(x + y * 0.35 + w)):
                if (xx + y) % 2 == 0:
                    cv.put(xx, y, _mix(cv.get(xx, y), (120, 190, 230), 0.20 * (1 - y / (H * 0.75))))
    # 바닥 모래 · 바위
    gy = int(H * 0.82)
    _ridge(cv, _rng("ab-r"), gy, H * 0.03, (24, 40, 50), hi=(56, 84, 96))
    cv.grad(gy + 3, H - 1, [(20, 34, 44), (12, 22, 30)])
    # 신전 기둥
    tx0, tx1 = int(W * 0.30), int(W * 0.70)
    ty = int(H * 0.36)
    cv.rect(tx0 - 6, ty - 8, tx1 + 6, ty - 3, (58, 92, 112))
    cv.poly([(tx0 - 8, ty - 8), ((tx0 + tx1) / 2.0, ty - 24), (tx1 + 8, ty - 8)], (50, 82, 102))
    cv.line([(tx0 - 8, ty - 8), ((tx0 + tx1) / 2.0, ty - 24), (tx1 + 8, ty - 8)], (88, 128, 150))
    for i, x in enumerate(range(tx0, tx1 + 1, (tx1 - tx0) // 4)):
        broken = i == 3
        top = ty + (10 if broken else 0)
        cv.rect(x - 3, top, x + 3, gy, (48, 80, 100))
        cv.rect(x - 3, top, x - 2, gy, (78, 116, 138))
        cv.rect(x - 4, gy - 3, x + 4, gy, (40, 66, 84))
    # 둥근 문
    gx, gyc = (tx0 + tx1) / 2.0, gy - H * 0.20
    r = H * 0.16
    cv.ellipse(gx, gyc, r + 3, r + 3, (36, 62, 80), outline=(90, 140, 160))
    if st == "sealed":
        cv.ellipse(gx, gyc, r, r, (24, 44, 60))
        cv.line([(gx - r, gyc), (gx + r, gyc)], (16, 30, 42))
        cv.line([(gx, gyc - r), (gx, gyc + r)], (16, 30, 42))
        _plates(cv, int(gx - 15), int(gyc - 5), 3, marks, (t // 3) % 4, (18, 34, 48), (110, 220, 255), (40, 90, 110))
    else:
        cv.ellipse(gx, gyc, r, r, (4, 14, 24))
        cv.glow(gx, gyc, r * 1.6, (110, 220, 255), 0.6)
    # 해초
    for i in range(16):
        x = RR.randint(0, W - 1)
        ln = RR.randint(6, 18)
        for y in range(ln):
            cv.put(x + math.sin((y + t) * 0.5 + i) * 1.4, gy + 2 - y, (30, 110, 80) if y % 3 else (50, 150, 100))
    # 거품
    for i in range(26):
        x = RR.randint(0, W - 1) + math.sin(t * 0.5 + i) * 1
        y = (RR.randint(0, H) - t * 3) % H
        cv.put(x, y, (170, 220, 245))
        if i % 3 == 0:
            cv.put(x + 1, y - 1, (120, 180, 210))
    # 물고기 그림자
    for i in range(3):
        fx = (RR.randint(0, W) + t * (2 + i)) % (W + 20) - 10
        fy = RR.randint(int(H * 0.15), int(H * 0.5))
        cv.rect(fx, fy, fx + 4, fy + 1, (10, 30, 52))
        cv.put(fx - 1, fy - 1, (10, 30, 52))
        cv.put(fx - 1, fy + 2, (10, 30, 52))
    cv.vignette((0, 4, 12), 0.65)


def _abyss_inside(cv, t, R):
    W, H = cv.w, cv.h
    RR = _rng("ab-in")
    cv.grad(0, H - 1, [(10, 44, 80), (6, 30, 58), (4, 20, 40), (3, 12, 26)])
    for x in (int(W * 0.08), int(W * 0.30), int(W * 0.72), int(W * 0.93)):
        cv.rect(x - 4, 0, x + 4, H * 0.62, (20, 50, 74))
        cv.rect(x - 4, 0, x - 3, H * 0.62, (40, 84, 110))
    fy = int(H * 0.60)
    cv.grad(fy, H - 1, [(22, 54, 70), (14, 36, 50), (8, 22, 32)])
    for i in range(40):                       # 바닥 무늬
        x = RR.randint(0, W - 1)
        y = RR.randint(fy + 2, H - 1)
        cv.put(x, y, (30, 70, 86))
    for i in range(24):                       # 산호
        x = RR.choice((RR.randint(0, int(W * 0.18)), RR.randint(int(W * 0.82), W - 1)))
        for y in range(RR.randint(4, 12)):
            cv.put(x + (y % 3 == 0) * RR.choice((-1, 1)), fy + 4 - y, (220, 110, 130) if i % 2 else (240, 170, 90))
    for (fx, fyy, rx, ry) in ((0.70, 0.50, 0.17, 0.05), (0.28, 0.93, 0.21, 0.06)):
        cx, cy = W * fx, H * fyy
        cv.glow(cx, cy, W * rx * 1.2, (110, 220, 255), 0.25, ry=H * ry * 2.2)
        cv.ellipse(cx, cy, W * rx, H * ry, (24, 60, 80), outline=(90, 190, 220))
    for k in range(4):
        x = W * (0.2 + k * 0.2)
        for y in range(int(H * 0.55)):
            if (int(x + y * 0.3) + y) % 2 == 0:
                cv.put(x + y * 0.3, y, _mix(cv.get(x + y * 0.3, y), (130, 200, 240), 0.18))
    for i in range(20):
        cv.put(RR.randint(0, W - 1), (RR.randint(0, H) - t * 3) % H, (170, 220, 245))
    cv.vignette((0, 4, 12), 0.6)


# ---------------------------------------------------------------- 하늘
def _sky(cv, st, t, R, marks):
    W, H = cv.w, cv.h
    if st == "inside":
        return _sky_inside(cv, t, R)
    cv.grad(0, H * 0.62, [(66, 104, 176), (104, 146, 210), (170, 196, 232), (246, 214, 170)])
    cv.glow(W * 0.80, H * 0.40, W * 0.25, (255, 236, 170), 0.45, ry=H * 0.30)
    cv.ellipse(W * 0.80, H * 0.40, 6, 6, (255, 246, 214))
    RR = _rng("sky")
    # 구름 바다
    cy = int(H * 0.60)
    cv.grad(cy, H - 1, [(238, 230, 236), (214, 214, 232), (186, 192, 222)])
    for i in range(30):
        x = (RR.randint(-20, W) + t) % (W + 30) - 15
        y = RR.randint(cy - 6, H - 10)
        r = RR.randint(6, 16)
        cv.ellipse(x, y, r, r * 0.55, (250, 246, 248) if y < cy + 10 else (226, 226, 240))
        cv.d.arc([int(x - r), int(y - r * 0.55), int(x + r), int(y + r * 0.55)], 200, 340, fill=(255, 255, 255))
    # 탑
    tx = int(W * 0.36)
    tw = int(W * 0.12)
    ttop = int(H * 0.14)
    cv.rect(tx - tw // 2, ttop, tx + tw // 2, cy + 6, (226, 230, 240))
    cv.rect(tx - tw // 2, ttop, tx - tw // 2 + 2, cy + 6, (255, 255, 255))
    cv.rect(tx + tw // 2 - 3, ttop, tx + tw // 2, cy + 6, (184, 190, 210))
    for y in range(ttop + 6, cy, 9):
        cv.rect(tx - tw // 2, y, tx + tw // 2, y, (200, 170, 100))
        cv.rect(tx - 2, y + 2, tx + 2, y + 5, (90, 110, 160))
    cv.poly([(tx - tw // 2 - 4, ttop), (tx, ttop - 16), (tx + tw // 2 + 4, ttop)], (214, 180, 96))
    cv.line([(tx - tw // 2 - 4, ttop), (tx, ttop - 16)], (255, 226, 150))
    # 구름 계단 → 꼭대기 문
    for s in range(9):
        sx = W * 0.62 - s * (W * 0.024)
        sy = cy - 2 - s * (H * 0.045)
        cv.ellipse(sx, sy, 7, 2.5, (255, 255, 255), outline=(220, 220, 236))
    gx0, gy0 = tx - 5, ttop + 2
    if st == "sealed":
        cv.rect(gx0, gy0, gx0 + 10, gy0 + 13, (150, 156, 180))
        _plates(cv, gx0 + 1, gy0 + 1, 1, marks, (t // 3) % 2, (120, 126, 150), (255, 236, 160), (170, 150, 110), pw=9, ph=11)
    else:
        cv.rect(gx0, gy0, gx0 + 10, gy0 + 13, (255, 250, 220))
        cv.glow(gx0 + 5, gy0 + 7, 24, (255, 236, 160), 0.6)
    # 새
    for i in range(3):
        bx = (RR.randint(0, W) + t * 3) % W
        by = RR.randint(int(H * 0.1), int(H * 0.35))
        cv.put(bx, by, (60, 70, 110))
        cv.put(bx - 1, by - 1, (60, 70, 110))
        cv.put(bx + 1, by - 1, (60, 70, 110))
    cv.vignette((40, 50, 90), 0.35)


def _sky_inside(cv, t, R):
    W, H = cv.w, cv.h
    RR = _rng("sky-in")
    cv.grad(0, H - 1, [(40, 70, 150), (90, 130, 200), (180, 200, 236), (250, 226, 190)])
    cv.glow(W * 0.85, H * 0.20, W * 0.3, (255, 240, 190), 0.35, ry=H * 0.3)
    for i in range(22):
        x = (RR.randint(0, W) + t) % (W + 30) - 15
        y = RR.randint(int(H * 0.30), int(H * 0.70))
        r = RR.randint(6, 14)
        cv.ellipse(x, y, r, r * 0.5, (250, 248, 252))
    # 둥근 대리석 단 (위에서 본 탑 꼭대기)
    fy = int(H * 0.62)
    cv.ellipse(W * 0.5, H * 0.95, W * 0.62, H * 0.40, (218, 222, 236), outline=(200, 170, 100))
    cv.ellipse(W * 0.5, H * 0.95, W * 0.56, H * 0.34, (232, 236, 246))
    for k in range(7):
        a = math.pi * (0.05 + k * 0.15)
        x = W * 0.5 - math.cos(a) * W * 0.58
        y = fy + 4 - math.sin(a) * H * 0.06
        cv.rect(x - 2, y - 26, x + 2, y, (240, 242, 250))
        cv.rect(x + 1, y - 26, x + 2, y, (190, 196, 214))
        cv.rect(x - 3, y - 28, x + 3, y - 26, (214, 180, 96))
    for (fx, fyy, rx, ry) in ((0.70, 0.50, 0.17, 0.05), (0.28, 0.93, 0.21, 0.06)):
        cx, cy = W * fx, H * fyy
        cv.ellipse(cx, cy, W * rx, H * ry, (206, 210, 228), outline=(214, 180, 96))
    cv.vignette((40, 50, 90), 0.3)


# ---------------------------------------------------------------- 모래 속 고성
def _castle(cv, st, t, R, marks):
    W, H = cv.w, cv.h
    if st == "inside":
        return _castle_inside(cv, t, R)
    cv.grad(0, H * 0.60, [(54, 40, 90), (128, 70, 104), (226, 120, 90), (250, 184, 110)])
    cv.glow(W * 0.20, H * 0.52, W * 0.22, (255, 214, 140), 0.5, ry=H * 0.16)
    cv.ellipse(W * 0.20, H * 0.52, 8, 8, (255, 230, 170))
    RR = _rng("castle")
    _ridge(cv, _rng("c-d1"), H * 0.58, H * 0.05, (186, 120, 78), hi=(226, 160, 100), smooth=0.97, rough=0.6)
    # 반쯤 묻힌 성벽
    wx0, wx1 = int(W * 0.30), int(W * 0.86)
    wy = int(H * 0.40)
    _blocks(cv, wx0, wy, wx1, H * 0.80, (222, 176, 112), (196, 150, 92), (150, 106, 64), bw=8, bh=5)
    for x in range(wx0, wx1 + 1, 10):               # 성가퀴
        cv.rect(x, wy - 5, x + 5, wy - 1, (206, 160, 100))
        cv.rect(x, wy - 5, x + 5, wy - 5, (236, 196, 130))
    for x in (wx0 - 2, wx1 - 10):                  # 탑
        cv.rect(x, wy - 18, x + 12, H * 0.8, (208, 162, 100))
        cv.rect(x, wy - 18, x + 2, H * 0.8, (236, 196, 130))
        cv.rect(x + 4, wy - 12, x + 7, wy - 6, (60, 34, 30))
    gx, gw = int(W * 0.58), int(W * 0.12)
    gy0 = int(H * 0.50)
    cv.ellipse(gx, gy0, gw // 2 + 3, 10, (160, 110, 66))
    cv.rect(gx - gw // 2 - 3, gy0, gx + gw // 2 + 3, H * 0.80, (160, 110, 66))
    if st == "sealed":
        cv.ellipse(gx, gy0, gw // 2, 8, (96, 60, 38))
        cv.rect(gx - gw // 2, gy0, gx + gw // 2, H * 0.80, (96, 60, 38))
        _plates(cv, gx - 10, gy0 + 3, 2, marks, (t // 3) % 3, (70, 44, 30), (255, 214, 120), (130, 92, 50))
    else:
        cv.ellipse(gx, gy0, gw // 2, 8, (40, 24, 18))
        cv.rect(gx - gw // 2, gy0, gx + gw // 2, H * 0.80, (40, 24, 18))
        cv.glow(gx, H * 0.72, gw * 1.4, (255, 214, 120), 0.6, ry=H * 0.25)
    # 앞 모래 언덕 (성을 반쯤 덮는다)
    _ridge(cv, _rng("c-d2"), H * 0.76, H * 0.05, (222, 166, 98), hi=(246, 206, 140), smooth=0.98, rough=0.5)
    _ridge(cv, _rng("c-d3"), H * 0.90, H * 0.04, (204, 146, 84), hi=(232, 186, 120), smooth=0.98, rough=0.5)
    # 모래바람
    for i in range(60):
        x = (RR.randint(0, W) + t * 4) % W
        y = RR.randint(int(H * 0.45), H - 1)
        cv.put(x, y, (250, 220, 170))
        cv.put(x - 1, y, (236, 196, 140))
    cv.vignette((40, 20, 30), 0.45)


def _castle_inside(cv, t, R):
    W, H = cv.w, cv.h
    RR = _rng("c-in")
    cv.grad(0, H - 1, [(60, 36, 28), (100, 64, 42), (90, 58, 40), (50, 32, 24)])
    # 기둥 줄
    for x in (int(W * 0.05), int(W * 0.20), int(W * 0.80), int(W * 0.95)):
        cv.rect(x - 5, 0, x + 5, H * 0.66, (176, 128, 80))
        cv.rect(x - 5, 0, x - 3, H * 0.66, (214, 168, 110))
        cv.rect(x + 3, 0, x + 5, H * 0.66, (130, 90, 56))
    # 두 영웅 석상 (그림자)
    for x, flip in ((int(W * 0.40), 1), (int(W * 0.60), -1)):
        cv.rect(x - 6, H * 0.10, x + 6, H * 0.50, (120, 82, 54))
        cv.ellipse(x, H * 0.10, 5, 5, (120, 82, 54))
        cv.rect(x + flip * 6, H * 0.18, x + flip * 14, H * 0.22, (120, 82, 54))
    # 햇살
    for k in range(3):
        x = W * (0.28 + k * 0.22)
        for y in range(int(H * 0.62)):
            for dx in range(3 + y // 16):
                if (dx + y) % 2 == 0:
                    xx = x + y * 0.25 + dx
                    cv.put(xx, y, _mix(cv.get(xx, y), (255, 226, 160), 0.22))
    fy = int(H * 0.60)
    cv.grad(fy, H - 1, [(196, 150, 92), (170, 124, 74), (130, 92, 56)])
    _speck(cv, RR, 0, fy, W - 1, H - 1, 160, [(216, 172, 110), (150, 108, 64)])
    for (fx, fyy, rx, ry) in ((0.70, 0.50, 0.17, 0.05), (0.28, 0.93, 0.21, 0.06)):
        cx, cy = W * fx, H * fyy
        cv.ellipse(cx, cy, W * rx, H * ry, (150, 104, 62), outline=(240, 200, 120))
    for i in range(40):
        cv.put((RR.randint(0, W) + t * 2) % W, RR.randint(0, H - 1), (255, 230, 180))
    cv.vignette((20, 10, 6), 0.5)


# ---------------------------------------------------------------- 거인의 왕좌
def _throne(cv, st, t, R, marks):
    W, H = cv.w, cv.h
    if st == "inside":
        return _throne_inside(cv, t, R)
    cv.grad(0, H - 1, [(4, 3, 10), (12, 8, 22), (20, 12, 34), (8, 6, 14)])
    RR = _rng("throne")
    # 끝없는 계단 (위로 갈수록 좁아짐)
    cx = W * 0.5
    for s in range(26):
        y = H - 1 - s * 4
        half = W * 0.42 * (1 - s / 30.0)
        cv.rect(cx - half, y - 3, cx + half, y, (30, 24, 44) if s % 2 else (36, 28, 52))
        cv.rect(cx - half, y - 3, cx + half, y - 3, (60, 48, 86))
    # 거대한 문
    dw, dh = int(W * 0.26), int(H * 0.44)
    dx0, dy0 = int(cx - dw / 2), int(H * 0.04)
    cv.rect(dx0 - 4, dy0, dx0 + dw + 4, dy0 + dh, (22, 16, 34))
    cv.rect(dx0 - 4, dy0, dx0 + dw + 4, dy0 + 1, (80, 60, 120))
    if st == "sealed":
        cv.rect(dx0, dy0 + 3, dx0 + dw, dy0 + dh, (14, 10, 22))
        cv.rect(int(cx), dy0 + 3, int(cx), dy0 + dh, (40, 30, 60))
        # 어둠 속 두 눈
        on = (t // 2) % 5 != 0
        for ex in (cx - 9, cx + 6):
            cv.rect(ex, dy0 + dh * 0.35, ex + 3, dy0 + dh * 0.35 + 1, (200, 130, 255) if on else (60, 40, 90))
        cv.glow(cx, dy0 + dh * 0.35, 18, (190, 120, 255), 0.25 if on else 0.08, ry=6)
        _plates(cv, int(cx - 15), int(dy0 + dh * 0.6), 3, marks, (t // 3) % 4, (24, 18, 40), (190, 120, 255), (70, 50, 100))
    else:
        cv.rect(dx0, dy0 + 3, dx0 + dw, dy0 + dh, (40, 20, 70))
        cv.glow(cx, dy0 + dh * 0.6, dw * 1.2, (190, 120, 255), 0.65, ry=dh)
    # 떠다니는 먼지 · 무너진 기둥
    for x in (int(W * 0.10), int(W * 0.88)):
        cv.rect(x - 4, H * 0.20, x + 4, H - 1, (18, 14, 28))
        cv.rect(x - 4, H * 0.20, x - 3, H - 1, (40, 32, 62))
    for i in range(50):
        x = RR.randint(0, W - 1)
        y = (RR.randint(0, H) - t) % H
        cv.put(x, y, (120, 90, 170) if i % 3 else (200, 170, 255))
    cv.vignette((0, 0, 0), 0.75)


def _throne_inside(cv, t, R):
    W, H = cv.w, cv.h
    RR = _rng("th-in")
    cv.grad(0, H - 1, [(6, 4, 14), (16, 10, 30), (12, 8, 22), (4, 3, 10)])
    # 오로라
    for k in range(3):
        for x in range(W):
            y = H * (0.12 + k * 0.07) + math.sin(x * 0.05 + k * 2 + t * 0.2) * 5
            for dy in range(4):
                if (x + dy) % 2 == 0:
                    cv.put(x, y + dy, _mix(cv.get(x, y + dy), (150, 90, 230) if k != 1 else (90, 200, 220), 0.35 - dy * 0.07))
    # 거대한 왕좌 (등받이 뾰족 · 팔걸이 · 계단)
    cx = W * 0.5
    back, edge = (16, 11, 28), (84, 60, 130)
    bw, top, seat = W * 0.13, H * 0.05, H * 0.40
    b = bw * 0.72
    crown = [(cx - b, seat), (cx - b, top + 6), (cx - b * 0.62, top + 18), (cx - b * 0.30, top + 2),
             (cx, top + 14), (cx + b * 0.30, top + 2), (cx + b * 0.62, top + 18), (cx + b, top + 6), (cx + b, seat)]
    cv.poly(crown, back)
    cv.line(crown[1:-1], edge)
    cv.rect(cx - b + 3, top + 24, cx + b - 3, seat - 2, (20, 14, 34))
    for sx in (-1, 1):
        cv.rect(cx + sx * bw - (6 if sx > 0 else -6) * 0, seat - 18, cx + sx * (bw + 10), seat + 2, (20, 14, 34))
        cv.rect(cx + sx * (bw + 10) - (2 if sx > 0 else 0), seat - 22, cx + sx * (bw + 10) + (0 if sx > 0 else 2), seat - 18, edge)
        cv.rect(cx + sx * (bw + 14), top + 20, cx + sx * (bw + 18), seat + 2, (22, 16, 38))
    cv.rect(cx - bw - 10, seat, cx + bw + 10, seat + 6, (26, 18, 42))
    cv.rect(cx - bw - 10, seat, cx + bw + 10, seat, edge)
    for s_ in range(3):
        cv.rect(cx - bw - 14 - s_ * 6, seat + 7 + s_ * 4, cx + bw + 14 + s_ * 6, seat + 10 + s_ * 4, (22, 16, 36) if s_ % 2 else (28, 20, 46))
    cv.glow(cx, top + 30, 10, (190, 120, 255), 0.35)
    cv.rect(cx - 1, top + 26, cx + 1, top + 33, (200, 140, 255))
    fy = int(H * 0.58)
    cv.grad(fy, H - 1, [(22, 16, 36), (14, 10, 24), (6, 4, 12)])
    from .arche_art import GLYPHS
    for k in range(10):                  # 바닥 둘레의 글자
        g = GLYPHS[RR.randrange(len(GLYPHS))]
        a = k / 10.0 * math.pi * 2
        gx, gy = cx + math.cos(a) * W * 0.40 - 3, H * 0.80 + math.sin(a) * H * 0.12 - 4
        for yy, r in enumerate(g):
            for xx, ch in enumerate(r):
                if ch == "#":
                    cv.put(gx + xx, gy + yy, (70, 48, 110))
    for (fx, fyy, rx, ry) in ((0.70, 0.50, 0.17, 0.05), (0.28, 0.93, 0.21, 0.06)):
        cx2, cy2 = W * fx, H * fyy
        cv.glow(cx2, cy2, W * rx * 1.2, (190, 120, 255), 0.22, ry=H * ry * 2.2)
        cv.ellipse(cx2, cy2, W * rx, H * ry, (30, 22, 50), outline=(150, 100, 220))
    for i in range(30):
        cv.put(RR.randint(0, W - 1), (RR.randint(0, H) - t) % H, (200, 170, 255))
    cv.vignette((0, 0, 0), 0.7)


PAINT = {"cave": _cave, "volcano": _volcano, "abyss": _abyss, "sky": _sky, "castle": _castle, "throne": _throne}


def k_for(w, h):
    """확대 배율 - 높이가 BASE_H 칸 남짓 되게."""
    return max(1, int(round(h / float(BASE_H))))


@functools.lru_cache(maxsize=96)
def low(place, lw, lh, state="sealed", t=0, marks=None):
    """낮은 해상도 그림 (lw x lh). marks 는 튜플의 튜플 (캐시 열쇠)."""
    cv = Cv(lw, lh)
    PAINT.get(place, _cave)(cv, state, t, _rng(place, state), [list(m) for m in marks] if marks else None)
    return cv.im


def render(place, w, h, state="sealed", t=0, marks=None):
    k = k_for(w, h)
    lw, lh = -(-int(w) // k), -(-int(h) // k)
    mk = tuple(tuple(int(g) for g in m) for m in marks) if marks else None
    im = low(place, lw, lh, state, int(t) % 12, mk)
    big = im.resize((lw * k, lh * k), Image.NEAREST)
    if big.size != (w, h):
        big = big.crop((0, 0, int(w), int(h)))
    return big
