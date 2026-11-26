# -*- coding: utf-8 -*-
"""낚시 (다음 시즌, 2026-11-26) 연못 그림 — 둑 · 물 · 낚싯대 · 찌 · '!' 말풍선 · 물보라.

원래 칸(W x H)에 점을 찍고 SCALE 배로 키운다 (2배 도트 - 다른 바탕화면 도트와 같은 굵기).
바탕은 투명색(key)으로 채운 RGB 다. 윈도우는 색 열쇠로 창을 뚫어서 반투명을 못 쓴다 - 그래서 알파 없이
찍는다. 맥은 SpriteView.frames 가 key 를 알파로 되돌린다.

상태마다 몇 장 (모두 같은 크기 - 맥은 같은 크기 그림의 알파를 합쳐 클릭 자리로 쓴다):

    idle    낚싯대가 둑에 누워 있다 (줄 없음) - 곁눈으로도 '안 던졌다' 가 보인다
    cast    낚싯대가 서고 줄 끝에 찌가 뜬다 (살랑)
    nibble  찌가 콕콕 흔들린다
    strike  찌가 쏙 잠기고 물보라 + '!' 말풍선이 깜빡인다
    splash  낚아 올린 순간의 물보라
"""
import functools

from PIL import Image, ImageDraw

W, H = 58, 30                     # 원래 칸 (점 하나 = 화면 SCALE 칸)
SCALE = 2
BANK = (7, 13, 57, 29)            # 둑 (타원 상자) - 화면에서 약 100 x 34
WATER = (10, 15, 54, 27)          # 물
BOB = (38, 21)                    # 찌가 물에 닿는 점 (가운데)
ROD_BASE = (3, 28)                # 선 낚싯대 손잡이 끝
ROD_TIP = (17, 3)
BUBBLE = (33, 0, 43, 11)          # '!' 말풍선 (찌 바로 위)

# 빛깔 - 투명색(255, 0, 255)과 겹치지 않게
BANK_OUT = (44, 90, 50)
BANK_C = (92, 164, 78)
BANK_L = (140, 204, 104)
WATER_OUT = (30, 72, 140)
WATER_D = (42, 100, 182)
WATER_C = (62, 134, 214)
WATER_L = (152, 208, 246)
SHINE = (228, 244, 255)
LILY = (72, 152, 72)
LILY_D = (40, 102, 52)
FLOWER = (250, 172, 204)
ROD_C = (134, 88, 46)
ROD_D = (78, 50, 28)
REEL = (178, 182, 192)
LINE = (224, 228, 236)
BOB_RED = (226, 54, 54)
BOB_WHITE = (250, 250, 250)
BUBBLE_C = (255, 255, 255)
BUBBLE_OUT = (44, 44, 58)
BANG = (226, 40, 40)
DROP = (204, 234, 255)

COUNTS = {"idle": 4, "cast": 4, "nibble": 4, "strike": 6, "splash": 4}
STATES = tuple(COUNTS)


def size():
    """창 크기 (화면 픽셀)."""
    return W * SCALE, H * SCALE


def bob_point():
    """찌 자리 (창 안 화면 픽셀) - 낚인 포켓몬이 여기서 튀어나온다."""
    return BOB[0] * SCALE, BOB[1] * SCALE


def _bank(d):
    d.ellipse(BANK, fill=BANK_C, outline=BANK_OUT)
    # 위쪽 둑에 빛이 닿는다 - 한 줄 밝게
    d.arc((BANK[0] + 1, BANK[1] + 1, BANK[2] - 1, BANK[3] - 1), 200, 340, fill=BANK_L)
    # 풀 몇 포기 (둑 가장자리)
    for x, y in ((12, 15), (52, 15), (21, 28), (46, 28)):
        d.point((x - 1, y), fill=BANK_L)
        d.point((x, y - 1), fill=BANK_L)
        d.point((x + 1, y), fill=BANK_L)


def _water(d, i):
    d.ellipse(WATER, fill=WATER_D, outline=WATER_OUT)
    # 둑 그림자 - 물 위쪽 한 줄만 어둡게 남기고 나머지를 밝게
    d.ellipse((WATER[0] + 1, WATER[1] + 2, WATER[2] - 1, WATER[3] - 1), fill=WATER_C)
    # 일렁이는 물결: 장마다 한 칸씩 밀리고, 가끔 하나가 반짝인다
    off = (0, 1, 2, 1)[i % 4]
    for x, y, n in ((15, 21, 4), (25, 24, 3), (43, 24, 3), (29, 18, 2)):
        d.line((x + off, y, x + off + n, y), fill=WATER_L)
    d.point((18 + off, 19), fill=SHINE if i % 2 == 0 else WATER_L)
    # 연잎 하나 (꽃 한 점)
    d.ellipse((45, 18, 51, 21), fill=LILY, outline=LILY_D)
    d.point((48, 18), fill=WATER_C)
    d.point((49, 19), fill=WATER_C)
    d.point((47, 19), fill=FLOWER)


def _rod_up(d):
    d.line((ROD_BASE, ROD_TIP), fill=ROD_C)
    d.line((ROD_BASE[0], ROD_BASE[1], ROD_BASE[0] + 2, ROD_BASE[1] - 5), fill=ROD_D, width=2)     # 손잡이
    d.rectangle((6, 22, 7, 23), fill=REEL)                                                         # 릴


def _rod_down(d):
    d.line((1, 28, 22, 24), fill=ROD_C)
    d.line((1, 28, 6, 27), fill=ROD_D, width=2)
    d.rectangle((6, 25, 7, 26), fill=REEL)


def _line(d, bx, by):
    """낚싯대 끝에서 찌까지 살짝 처진 줄."""
    tx, ty = ROD_TIP
    pts = []
    for k in range(13):
        t = k / 12.0
        pts.append((tx + (bx - tx) * t, ty + (by - ty) * t + 3.0 * 4 * t * (1 - t)))
    d.line(pts, fill=LINE)


def _bobber(d, bx, by):
    """찌 - 위는 빨강, 아래는 하양, 꼭대기에 작은 막대. by 가 물에 닿는 줄."""
    d.point((bx, by - 4), fill=BOB_RED)
    d.line((bx - 1, by - 3, bx + 1, by - 3), fill=BOB_RED)
    d.line((bx - 1, by - 2, bx + 1, by - 2), fill=BOB_RED)
    d.line((bx - 1, by - 1, bx + 1, by - 1), fill=BOB_WHITE)


def _ring(d, bx, by, r):
    d.ellipse((bx - r, by - 1, bx + r, by + 1), outline=WATER_L)


def _bubble(d):
    x1, y1, x2, y2 = BUBBLE
    d.rectangle((x1 + 1, y1, x2 - 1, y2), fill=BUBBLE_C)
    d.rectangle((x1, y1 + 1, x2, y2 - 1), fill=BUBBLE_C)
    d.line((x1 + 1, y1, x2 - 1, y1), fill=BUBBLE_OUT)
    d.line((x1 + 1, y2, x2 - 1, y2), fill=BUBBLE_OUT)
    d.line((x1, y1 + 1, x1, y2 - 1), fill=BUBBLE_OUT)
    d.line((x2, y1 + 1, x2, y2 - 1), fill=BUBBLE_OUT)
    cx = (x1 + x2) // 2
    d.point((cx, y2 + 1), fill=BUBBLE_OUT)                     # 꼬리 (찌를 가리킨다)
    d.rectangle((cx - 1, y1 + 2, cx, y2 - 4), fill=BANG)
    d.rectangle((cx - 1, y2 - 2, cx, y2 - 2), fill=BANG)


def _drops(d, bx, by, i):
    """찌가 잠길 때의 작은 물보라 - 장마다 솟았다 떨어진다."""
    h = (2, 4, 5, 3, 1, 0)[i % 6]
    if h <= 0:
        return
    for dx in (-3, 3):
        d.point((bx + dx, by - h + 1), fill=DROP)
    d.point((bx, by - h - 1), fill=DROP)


def _crown(d, bx, by, i):
    """낚아 올린 순간의 물기둥 - 가운데가 솟고 양옆으로 물방울이 튄다."""
    h = (4, 8, 6, 3)[i % 4]
    d.line((bx, by - 1, bx, by - h), fill=DROP)
    d.line((bx - 2, by - 1, bx - 2, by - h + 3), fill=DROP)
    d.line((bx + 2, by - 1, bx + 2, by - h + 3), fill=DROP)
    d.line((bx - 3, by, bx + 3, by), fill=DROP)
    for dx, dy in ((-5, 2), (5, 2), (-4, 5), (4, 5)):
        d.point((bx + dx + (dx // 4) * i, by - h + dy), fill=SHINE)


@functools.lru_cache(maxsize=None)
def frames(state, key=(255, 0, 255)):
    """그 상태의 그림들 (화면 크기, RGB, 바탕은 key)."""
    n = COUNTS[state]
    out = []
    bx, by = BOB
    for i in range(n):
        im = Image.new("RGB", (W, H), tuple(key))
        d = ImageDraw.Draw(im)
        _bank(d)
        _water(d, i)
        if state == "idle":
            _rod_down(d)
        elif state == "splash":
            _rod_down(d)
            _ring(d, bx, by, 3 + i)
            _crown(d, bx, by, i)
        else:
            _rod_up(d)
            if state == "cast":
                dy = (0, 0, 1, 1)[i]
                _line(d, bx, by - 4 + dy)
                if i % 2 == 0:
                    _ring(d, bx, by, 3)
                _bobber(d, bx, by + dy)
            elif state == "nibble":
                dy = (0, 1, 0, 2)[i]
                _line(d, bx, by - 4 + dy)
                _ring(d, bx, by, 2 + (i % 2) * 2)
                _bobber(d, bx, by + dy)
            else:                                          # strike - 찌가 잠겼다
                _line(d, bx, by)
                _ring(d, bx, by, 3 + (i % 3))
                d.point((bx, by), fill=BOB_RED)             # 물 밑에 비치는 찌 끝
                _drops(d, bx, by, i)
                if i < n // 2:                              # 깜빡임 - 앞 반은 켜고 뒤 반은 끈다
                    _bubble(d)
        out.append(im.resize((W * SCALE, H * SCALE), Image.NEAREST))
    return tuple(out)
