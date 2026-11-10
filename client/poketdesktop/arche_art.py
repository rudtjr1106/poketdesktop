# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 (시즌 6) — 그림.

전부 PIL 로 **낮은 해상도에 그려 NEAREST 로 키운다** (도트 결). 글자는 Galmuri11.

    glyph(i, k, color)          아르케 글자 (번호 0~23). **번호만 있고 뜻은 없다** - 무슨 소리인지는 비공개 답안지에만.
    relic(k) · star(mag, k) · drip(k) · sand(k)      바탕화면 현상의 작은 그림 (RGBA)
    item_icon(key)              열쇠 아이템 아이콘 24x24 (tools/build_arche_icons.py 가 PNG 로 굽는다)
    scene(place, w, h, state, t)     장소 그림 (RGB). state: sealed(봉인된 입구) / open(열린 입구) / inside(배틀하는 안쪽)
    entry_frames(place, w, h)        입장 장면 [(그림, ms), ...] 6~8초
    book(w, h, ...)             발굴 일지 (펼친 수첩)

장소 열쇠: cave · volcano · abyss · sky · castle · throne (common/arche.CHAPTERS 와 같다).
"""
import functools
import hashlib
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GALMURI = os.path.join(HERE, "fonts", "Galmuri11.ttf")

PLACES = ("cave", "volcano", "abyss", "sky", "castle", "throne")

TEAL = (95, 227, 208)
TEAL_DIM = (47, 87, 82)
GOLD = (232, 195, 106)
INK = (61, 43, 31)
PAPER = (239, 228, 200)

# ---------------------------------------------------------------- 아르케 글자 (7 x 9)
# 새로 지은 글자다 (안농 글자를 베끼지 않는다). 세로 줄기 + 꺾인 획 + 점, 돌에 새긴 결.
# **차례를 바꾸지 말 것** - 번호가 곧 서버 비공개 데이터의 글자 번호다 (바꾸면 이미 낸 단서가 다른 글자로 보인다).
GLYPHS = [
    ["...#...", "..###..", ".#.#.#.", "...#...", "...#...", "...#...", "..#.#..", ".#...#.", "#.....#"],
    ["#.....#", ".#...#.", "..#.#..", "...#...", "#######", "...#...", "..#.#..", ".#...#.", "#.....#"],
    ["#####..", "#...#..", "#...#..", "#####..", "#.#....", "#..#...", "#...#..", "#....#.", "#.....#"],
    ["..###..", ".#...#.", "#.....#", "...#...", "..###..", "...#...", "#.....#", ".#...#.", "..###.."],
    ["#.#.#.#", "#.#.#.#", ".#####.", "...#...", "...#...", "...#...", ".#####.", "#.#.#.#", "#.#.#.#"],
    ["...#...", ".#.#.#.", "..###..", "#######", "..###..", ".#.#.#.", "...#...", "...#...", "...#..."],
    ["#######", "......#", ".....#.", "....#..", "...#...", "..#....", ".#.....", "#......", "#######"],
    ["#...#..", "#..#...", "#.#....", "##.....", "#.#....", "#..#...", "#...#..", "#....#.", "#.....#"],
    ["...#...", "...#...", "#######", "...#...", "..#.#..", "..#.#..", ".#...#.", ".#...#.", "#.....#"],
    [".#####.", "#.....#", "#.###.#", "#.#.#.#", "#.###.#", "#.....#", ".#####.", "...#...", "..###.."],
    ["#......", "##.....", "#.#....", "#..#...", "#...#..", "#..#...", "#.#....", "##.....", "#......"],
    ["......#", ".....##", "....#.#", "...#..#", "..#...#", "...#..#", "....#.#", ".....##", "......#"],
    ["#######", "#.....#", "#.....#", ".#...#.", "..#.#..", "...#...", "...#...", "..###..", ".#...#."],
    ["...#...", "..#.#..", ".#...#.", "#.....#", "#######", "#.....#", ".#...#.", "..#.#..", "...#..."],
    ["#.....#", "#.....#", "#######", "#.....#", "#.....#", "#######", "#.....#", "#.....#", "#.....#"],
    ["...#...", "...#...", "...#...", "#..#..#", ".#.#.#.", "..###..", "...#...", "...#...", "...#..."],
    ["##...##", "#.#.#.#", "#..#..#", "#.....#", "#.....#", "#.....#", "#..#..#", "#.#.#.#", "##...##"],
    ["#......", "#......", "#......", "#######", "......#", "......#", "#######", "#......", "#......"],
    [".##.##.", "#..#..#", "#..#..#", ".#...#.", "..#.#..", "...#...", "..#.#..", ".#...#.", "#.....#"],
    ["#######", "...#...", "...#...", "..#.#..", ".#...#.", "#.....#", "...#...", "...#...", "#######"],
    ["....#..", "...#...", "..#....", ".######", "..#....", "...#...", "....#..", "...#...", "..#...."],
    ["#.#.#.#", ".......", "#.....#", ".......", "#..#..#", ".......", "#.....#", ".......", "#.#.#.#"],
    ["...#...", "..#.#..", ".#.#.#.", "#.#.#.#", ".#.#.#.", "..#.#..", "...#...", "..#.#..", ".#...#."],
    ["#.....#", "##...##", "#.#.#.#", "#..#..#", "...#...", "...#...", "..#.#..", ".#...#.", ".#...#."],
]
GLYPH_W, GLYPH_H = 7, 9


def _glyph_ok():
    assert len(GLYPHS) == 24 and len(set(tuple(g) for g in GLYPHS)) == 24
    for g in GLYPHS:
        assert len(g) == GLYPH_H and all(len(r) == GLYPH_W for r in g)


_glyph_ok()


@functools.lru_cache(maxsize=256)
def glyph(i, k=2, color=TEAL, glow=True):
    """아르케 글자 하나 (RGBA, (7+2)k x (9+2)k). glow: 둘레에 어두운 빛 1칸 (바탕화면에서 잘 보이게)."""
    g = GLYPHS[int(i) % len(GLYPHS)]
    im = Image.new("RGBA", (GLYPH_W + 2, GLYPH_H + 2), (0, 0, 0, 0))
    px = im.load()
    on = [(x + 1, y + 1) for y, row in enumerate(g) for x, ch in enumerate(row) if ch == "#"]
    if glow:
        halo = tuple(max(0, c // 4) for c in color) + (170,)
        for x, y in on:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if px[x + dx, y + dy][3] == 0:
                        px[x + dx, y + dy] = halo
    for x, y in on:
        px[x, y] = tuple(color) + (255,)
    return up(im, k)


# ---------------------------------------------------------------- 작은 그림
def up(im, k):
    k = max(1, int(k))
    return im if k == 1 else im.resize((im.width * k, im.height * k), Image.NEAREST)


@functools.lru_cache(maxsize=16)
def relic(k=2):
    """깨진 돌 조각 (14 x 11): 바탕화면에 떨어지는 유물. 가운데에 희미한 글자 자국."""
    rows = [
        "....#######...",
        "...#.......##.",
        "..#..........#",
        ".#...........#",
        "#............#",
        "#...........#.",
        "#..........#..",
        ".#........#...",
        "..#......#....",
        "...#....#.....",
        "....####......",
    ]
    im = Image.new("RGBA", (14, 11), (0, 0, 0, 0))
    px = im.load()
    inside = []
    for y, r in enumerate(rows):
        xs = [x for x, c in enumerate(r) if c == "#"]
        if len(xs) >= 2:
            inside.extend((x, y) for x in range(xs[0] + 1, xs[-1]))
        for x in xs:
            px[x, y] = (52, 56, 66, 255)
    for x, y in inside:
        px[x, y] = (118, 122, 134, 255) if (x + y) % 5 else (98, 102, 114, 255)
    for x, y in inside:
        if y <= 2 or x <= 3:
            px[x, y] = (150, 155, 168, 255)
    for x, y in ((6, 4), (6, 5), (6, 6), (5, 5), (7, 5), (8, 3)):
        px[x, y] = TEAL + (255,)
    return up(im, k)


@functools.lru_cache(maxsize=32)
def star(mag=1, k=2):
    """별 (mag 0~2: 작은 점 / 십자 / 큰 십자)."""
    n = 3 + 2 * int(mag)
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    px = im.load()
    c = n // 2
    px[c, c] = (255, 255, 255, 255)
    for r in range(1, int(mag) + 1 + (1 if mag else 0)):
        a = 220 - 70 * r
        for x, y in ((c + r, c), (c - r, c), (c, c + r), (c, c - r)):
            if 0 <= x < n and 0 <= y < n:
                px[x, y] = (200, 214, 255, max(60, a))
    return up(im, k)


@functools.lru_cache(maxsize=8)
def drip(k=2):
    rows = ["..#..", ".###.", "#####", "##o##", ".###."]
    im = Image.new("RGBA", (5, 5), (0, 0, 0, 0))
    px = im.load()
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch == "#":
                px[x, y] = (90, 170, 230, 230)
            elif ch == "o":
                px[x, y] = (210, 240, 255, 255)
    return up(im, k)


@functools.lru_cache(maxsize=8)
def sand(k=2, seed=0):
    rng = random.Random(seed)
    im = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
    px = im.load()
    for _ in range(26):
        x, y = rng.randrange(16), rng.randrange(8)
        px[x, y] = rng.choice(((214, 180, 112, 230), (190, 154, 92, 200), (236, 208, 150, 170)))
    return up(im, k)


# ---------------------------------------------------------------- 열쇠 아이템 아이콘 (24 x 24)
ITEMS = ("ARCHESTONE", "ARCHESHELL", "ARCHESTAR", "ARCHESAND", "ARCHECROWN", "ARCHELAMP")


def item_icon(key):
    """24x24 RGBA. 깨진 돌판 · 조개 비석 · 별의 조각 · 모래시계 · 왕관 조각 · 고대의 등불."""
    im = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = (key or "").upper()
    if k == "ARCHESTONE":
        d.polygon([(4, 5), (17, 3), (20, 9), (18, 20), (6, 21), (3, 13)], fill=(112, 116, 128), outline=(48, 52, 62))
        d.line([(9, 4), (12, 12), (8, 20)], fill=(70, 74, 86))
        im.paste(glyph(3, 1, TEAL, glow=False), (11, 7), glyph(3, 1, TEAL, glow=False))
    elif k == "ARCHESHELL":
        d.pieslice([2, 4, 22, 24], 180, 360, fill=(236, 214, 196), outline=(140, 102, 86))
        for x in (6, 9, 12, 15, 18):
            d.line([(12, 14), (x, 5)], fill=(184, 146, 128))
        d.rectangle([4, 14, 20, 19], fill=(98, 120, 140), outline=(52, 66, 84))
        d.point([(9, 16), (12, 16), (15, 16)], fill=TEAL)
    elif k == "ARCHESTAR":
        pts = []
        for i in range(10):
            r = 10 if i % 2 == 0 else 4
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((12 + r * math.cos(a), 12 + r * math.sin(a)))
        d.polygon(pts, fill=(255, 226, 120), outline=(176, 128, 40))
        d.point([(11, 10), (12, 10), (11, 11)], fill=(255, 255, 255))
    elif k == "ARCHESAND":
        d.rectangle([5, 2, 18, 4], fill=(140, 96, 52))
        d.rectangle([5, 19, 18, 21], fill=(140, 96, 52))
        d.polygon([(7, 5), (16, 5), (12, 12), (16, 18), (7, 18), (11, 12)], fill=(200, 228, 240), outline=(96, 128, 150))
        d.polygon([(8, 17), (15, 17), (12, 13)], fill=(226, 190, 112))
        d.point([(11, 9), (12, 10)], fill=(226, 190, 112))
    elif k == "ARCHECROWN":
        d.polygon([(3, 18), (3, 8), (8, 13), (12, 5), (16, 13), (21, 8), (21, 18)], fill=(232, 195, 106), outline=(132, 92, 30))
        d.rectangle([3, 17, 21, 20], fill=(196, 150, 60), outline=(132, 92, 30))
        d.line([(16, 5), (21, 20)], fill=(60, 40, 20))
        d.point([(12, 15), (7, 16), (17, 16)], fill=TEAL)
    else:   # ARCHELAMP
        d.rectangle([9, 2, 14, 4], fill=(110, 80, 50))
        d.polygon([(6, 6), (17, 6), (19, 18), (4, 18)], fill=(70, 60, 50), outline=(40, 32, 26))
        d.rectangle([8, 8, 15, 16], fill=(255, 196, 96))
        d.rectangle([10, 10, 13, 14], fill=(255, 238, 180))
        d.rectangle([5, 18, 18, 21], fill=(110, 80, 50))
    return im


# ---------------------------------------------------------------- 장소 · 입장 · 수첩 (Task 6 에서 다듬는다)
PALETTE = {
    "cave": ((10, 15, 29), (43, 49, 64), TEAL),
    "volcano": ((32, 12, 10), (92, 40, 28), (255, 138, 60)),
    "abyss": ((4, 16, 34), (18, 60, 92), (110, 220, 255)),
    "sky": ((120, 160, 220), (236, 242, 252), (255, 236, 160)),
    "castle": ((54, 34, 20), (196, 156, 96), (255, 214, 120)),
    "throne": ((8, 6, 14), (40, 30, 56), (190, 120, 255)),
}


def _rng(*parts):
    return random.Random(int(hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest()[:12], 16))


# 입구 한가운데 (입장 장면이 빨려 들어가는 곳, 그림 폭 · 높이에 대한 비율)
GATE = {"cave": (0.50, 0.62), "volcano": (0.50, 0.74), "abyss": (0.50, 0.62),
        "sky": (0.36, 0.18), "castle": (0.58, 0.64), "throne": (0.50, 0.30)}
ACCENT = {"cave": TEAL, "volcano": (255, 150, 60), "abyss": (110, 220, 255),
          "sky": (255, 244, 200), "castle": (255, 214, 120), "throne": (190, 120, 255)}


def scene(place, w, h, state="sealed", t=0, marks=None):
    """장소 그림 (RGB, w x h). 그리는 것은 arche_places."""
    from . import arche_places
    return arche_places.render(place, int(w), int(h), state, t, marks)


def _zoom(im, cx, cy, z):
    """(cx, cy) 를 가운데로 z 배 확대한 같은 크기 그림 (NEAREST)."""
    w, h = im.size
    cw, ch = max(2, int(w / z)), max(2, int(h / z))
    x0 = int(min(max(0, cx * w - cw / 2.0), w - cw))
    y0 = int(min(max(0, cy * h - ch / 2.0), h - ch))
    return im.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), Image.NEAREST)


def _shake(im, dx, dy):
    from PIL import ImageChops
    return ImageChops.offset(im, dx, dy)


def entry_frames(place, w, h, marks=None):
    """입장 장면 [(RGB 그림, ms)] - 합계 약 6.5초.

    봉인된 입구 (판의 글자가 하나씩 빛난다) → 땅울림 → 입구가 열리고 빛이 샌다 → 빛 속으로 빨려 든다 →
    장소 빛깔로 하얗게 → 안쪽 (배틀 배경). 장소마다 그림 · 빛깔 · 빨려 드는 자리가 다르다.
    """
    w, h = int(w), int(h)
    gx, gy = GATE.get(place, (0.5, 0.6))
    acc = ACCENT.get(place, TEAL)
    out = []
    for t in (0, 1, 3, 4, 6, 7, 9, 10):                 # 판이 하나씩 빛난다 (arche_places 가 t//3 으로 센다)
        out.append((scene(place, w, h, "sealed", t, marks), 260))
    base = scene(place, w, h, "sealed", 10, marks)
    for dx, dy in ((3, 0), (-3, 1), (2, -1), (-2, 0), (1, 1), (0, 0)):
        out.append((_shake(base, dx * max(1, w // 480), dy * max(1, w // 480)), 70))
    for t in range(4):
        im = scene(place, w, h, "open", t, marks)
        out.append((Image.blend(im, Image.new("RGB", im.size, acc), 0.10 * t), 230))
    opened = scene(place, w, h, "open", 3, marks)
    steps = 9
    for i in range(1, steps + 1):
        z = 1.0 + (i / float(steps)) ** 1.6 * 5.0
        im = _zoom(opened, gx, gy, z)
        out.append((Image.blend(im, Image.new("RGB", im.size, acc), min(0.85, 0.08 * i)), 110))
    inside = scene(place, w, h, "inside", 1, marks)
    flash = Image.new("RGB", (w, h), _lighten(acc, 0.6))
    for i in range(5):
        out.append((Image.blend(flash, inside, (i + 1) / 6.0), 110))
    out.append((inside, 650))
    return out


def _lighten(c, k):
    return tuple(int(v + (255 - v) * k) for v in c)


_fonts = {}


def font(px):
    f = _fonts.get(px)
    if f is None:
        try:
            f = ImageFont.truetype(GALMURI, px)
        except Exception:                                   # noqa: BLE001
            f = ImageFont.load_default()
        _fonts[px] = f
    return f
