# -*- coding: utf-8 -*-
"""공습 (2.3.0) 낙하산 그림 — 픽셀 둥근 천(갈래마다 두 빛깔) + 줄 넷이 아래 가운데(고리)로 모인다.

그림은 원래 칸 크기로 만든다 (36 x 30). 장면(airraid_show)이 도트 배율만큼 키워 낙하산 창에 건다.
아래 가운데(고리)가 공습 포켓몬 머리 위에 오게 놓는다.
"""
import functools

from PIL import Image, ImageDraw

W, H = 36, 30                     # 원래 칸 크기
DOME_H = 12                       # 천 높이
HOOK = (W // 2, H - 1)            # 줄이 모이는 고리 (아래 가운데)
OUTLINE = (40, 32, 48, 255)
STRING = (150, 140, 158, 255)       # 밝은 바탕 · 어두운 바탕 둘 다에서 보이게
# 갈래 빛깔 (공습 포켓몬마다 차례로)
PALETTES = (
    ((226, 52, 60, 255), (250, 246, 240, 255)),        # 빨강 · 흰
    ((52, 112, 220, 255), (240, 246, 252, 255)),       # 파랑 · 흰
    ((246, 176, 40, 255), (252, 232, 120, 255)),       # 주황 · 노랑
    ((60, 170, 96, 255), (236, 248, 228, 255)),        # 초록 · 흰
    ((150, 80, 200, 255), (248, 196, 228, 255)),       # 보라 · 분홍
)
GORES = 6                         # 갈래 수


def _dome(draw, x0, y0, w, h, pal):
    """반원 천 - 위가 둥글고 아래 끝은 물결."""
    cx = x0 + w / 2.0
    for yy in range(h):
        t = 1.0 - (yy + 0.5) / float(h)                  # 위 1 → 아래 0
        half = (w / 2.0) * (1.0 - t * t) ** 0.5 if t < 1 else 0
        if half < 0.5:
            continue
        for xx in range(int(cx - half), int(cx + half) + 1):
            g = int((xx - x0) * GORES / float(w))
            col = pal[g % 2]
            if yy < 2 and abs(xx - cx) > half - 2:
                col = pal[0]
            draw.point((xx, y0 + yy), fill=col)
    # 테두리 (바깥 둘레 + 갈래 금)
    pts = []
    for yy in range(h):
        t = 1.0 - (yy + 0.5) / float(h)
        half = (w / 2.0) * (1.0 - t * t) ** 0.5 if t < 1 else 0
        pts.append((int(cx - half), y0 + yy, int(cx + half), y0 + yy))
    for (l, y, r, _y) in pts:
        draw.point((l, y), fill=OUTLINE)
        draw.point((r, y), fill=OUTLINE)
    top = min(p[1] for p in pts)
    l0, r0 = pts[0][0], pts[0][2]
    draw.line((l0, top - 1, r0, top - 1), fill=OUTLINE)
    # 아래 끝 물결 - 갈래마다 살짝 처진다
    bottom = y0 + h
    for g in range(GORES):
        a = x0 + int(g * w / float(GORES))
        b = x0 + int((g + 1) * w / float(GORES))
        draw.line((a, bottom - 1, b, bottom - 1), fill=OUTLINE)
        draw.point(((a + b) // 2, bottom), fill=OUTLINE)


@functools.lru_cache(maxsize=None)
def parachute(i=0):
    """i 번째 빛깔의 펼친 낙하산 (W x H, RGBA). 아래 가운데가 고리."""
    pal = PALETTES[i % len(PALETTES)]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    _dome(d, 0, 1, W - 1, DOME_H, pal)
    by = 1 + DOME_H
    for x in (1, W // 3, 2 * W // 3, W - 2):
        d.line((x, by, HOOK[0], HOOK[1]), fill=STRING)
    d.point(HOOK, fill=OUTLINE)
    return im


@functools.lru_cache(maxsize=None)
def folding(i=0):
    """땅에 닿은 뒤 천이 바람 빠지듯 접히며 옆으로 눕는 그림들 (W x H). 마지막은 바닥에 깔린 천."""
    pal = PALETTES[i % len(PALETTES)]
    out = []
    for k, (h, dx) in enumerate(((9, 2), (6, 5), (4, 8), (2, 11))):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        w = W - 1 - k * 3
        top = H - 1 - h - 1
        _dome(d, dx, top, w - dx // 2, h, pal)
        if h > 3:
            for x in (dx + 1, dx + w // 2):
                d.line((x, top + h, HOOK[0], HOOK[1]), fill=STRING)
        out.append(im)
    return tuple(out)


def scaled(im, k):
    k = max(1, int(k))
    return im.resize((im.width * k, im.height * k), Image.NEAREST) if k > 1 else im
