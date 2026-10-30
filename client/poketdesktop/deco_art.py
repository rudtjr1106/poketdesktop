# -*- coding: utf-8 -*-
"""꾸미기 그림 (버전 2, 시안 4 - 사용자 '좋다 좋아 아주 좋아', 10/30). 목록 · 규칙은 common/deco.py.

장식은 **도트보다 두 배 촘촘한 칸**으로 그렸다. 바탕화면 포켓몬은 도트를 두 배쯤 키워 그리므로 촘촘한 칸 하나가
화면 픽셀 하나다 - 그래서 왕관 루비 구슬의 하이라이트, 꽃잎 사이 선, 진주알의 빛이 산다 (deco_place 가 얹는다).
효과(발자국 · 별가루 · 꽃잎 · 하트 · 발밑 빛)도 같은 칸으로 그렸다 (deco_fx 가 그린다).

꽃은 꽃잎 다섯 장을 계산으로 찍고 사이를 선으로 나눈 것(시안의 flower5.flower(11, 0.3, 0.18))을 격자로 굳혔다.
꽃핀의 파란 핀은 뺐다 (사용자 '오히려 더 이상하다').
"""
import functools

from PIL import Image

T = (0, 0, 0, 0)


def grid(rows, pal):
    w = max(len(r) for r in rows)
    im = Image.new("RGBA", (w, len(rows)), T)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), pal[ch])
    return im


def scaled(im, k):
    """정수 배로 키운다 (도트가 살게 NEAREST). 1 이면 그대로."""
    k = max(1, int(k))
    return im if k == 1 else im.resize((im.width * k, im.height * k), Image.NEAREST)


# ---------------------------------------------------------------- 왕관 (17 x 10) - 뾰족한 끝 셋 위에 루비 구슬
CROWN = [
    ".ooo...ooo...ooo.",
    "oWRRo.oWRRo.oWRRo",
    "oRRDo.oRRDo.oRRDo",
    ".oYo...oYo...oYo.",
    "oLYDo.oLYDo.oLYDo",
    "oLLYDoLLYDDoLYYDo",
    "oLWLLLLLLLLLLLLLo",
    "oYYRYYYYBYYYYRYYo",
    "oDDDDDDDDDDDDDDDo",
    ".ooooooooooooooo.",
]
METALS = {
    "gold": {"o": (112, 62, 14, 255), "L": (255, 232, 132, 255), "Y": (248, 190, 46, 255),
             "D": (200, 122, 24, 255), "W": (255, 255, 236, 255)},
    "silver": {"o": (66, 74, 98, 255), "L": (246, 249, 255, 255), "Y": (200, 210, 228, 255),
               "D": (128, 140, 168, 255), "W": (255, 255, 255, 255)},
    "bronze": {"o": (88, 44, 18, 255), "L": (250, 200, 150, 255), "Y": (212, 132, 72, 255),
               "D": (148, 82, 40, 255), "W": (255, 236, 214, 255)},
}
GEM = {"R": (232, 38, 76, 255), "B": (64, 156, 255, 255)}

# 반짝임 (7 x 7) - 왕관 오른쪽 구슬 위에서 가끔 (작은 점 -> 십자 -> 별 -> 십자 -> 점)
_S = {"W": (255, 255, 255, 255), "Y": (255, 246, 176, 255), "y": (255, 236, 120, 255)}
GLINT = [
    [".......", ".......", ".......", "...W...", ".......", ".......", "......."],
    [".......", ".......", "...Y...", "..YWY..", "...Y...", ".......", "......."],
    ["...y...", "...Y...", "...W...", "yYWWWYy", "...W...", "...Y...", "...y..."],
    [".......", "...y...", "...Y...", ".yYWYy.", "...Y...", "...y...", "......."],
    [".......", ".......", "...y...", "..yWy..", "...y...", ".......", "......."],
]

# ---------------------------------------------------------------- 리본 (11 x 8)
BOW = [
    ".oo.....oo.",
    "oprooooorpo",
    "oprRoKoRrpo",
    "oRRRoKoRRDo",
    "oRRDoooDRDo",
    ".oDo.o.oDo.",
    "..o.oRo.o..",
    "....oDo....",
]
BOW_PAL = {"o": (150, 40, 86, 255), "p": (255, 236, 244, 255), "r": (255, 176, 206, 255),
           "R": (246, 120, 168, 255), "D": (204, 72, 128, 255), "K": (232, 92, 148, 255)}

# ---------------------------------------------------------------- 꽃핀 (꽃 13 x 12 + 잎)
FLOWER = [
    ".....ooo.....",
    "....oppPo....",
    "...oopPPoo...",
    "..opPPPDDpo..",
    ".opPPPDDpPPo.",
    "oPPPDocoPPPDo",
    ".oPDDCCCPDDo.",
    "..oppPCppDo..",
    "..opPPppPPo..",
    "..oPPDDPPDo..",
    "..oPDDoPDDo..",
    "...ooo.ooo...",
]
FLOWER_PAL = {"p": (255, 238, 246, 255), "P": (255, 176, 210, 255), "D": (240, 122, 172, 255),
              "C": (255, 210, 60, 255), "c": (255, 248, 196, 255), "o": (190, 64, 124, 255)}
LEAF = [
    "..oo",
    ".oGo",
    "oGgo",
    "oGo.",
    ".o..",
]
LEAF_PAL = {"o": (40, 104, 56, 255), "G": (96, 196, 104, 255), "g": (180, 236, 160, 255)}

# ---------------------------------------------------------------- 목걸이 (진주 2 x 2 + 하트 펜던트 7 x 6)
PEARL = ["Wp", "pS"]
PEARL_PAL = {"W": (255, 255, 255, 255), "p": (240, 234, 248, 255), "S": (182, 170, 204, 255)}
HEART = [
    ".oo.oo.",
    "oWRoRRo",
    "oRRRRDo",
    ".oRRDo.",
    "..oDo..",
    "...o...",
]
HEART_PAL = {"o": (120, 10, 40, 255), "W": (255, 220, 228, 255), "R": (236, 48, 92, 255),
             "D": (170, 22, 60, 255)}

# ---------------------------------------------------------------- 효과
PAW = [
    ".X.X.X.",
    ".X.X.X.",
    ".......",
    "..XXX..",
    ".XXXXX.",
    ".XXXXX.",
    "..XXX..",
]
PAW_COLOR = (255, 238, 214, 255)
STAR_ROWS = {
    1: ["X"],
    3: [".Y.", "YWY", ".Y."],
    5: ["..Y..", "..Y..", "YYWYY", "..Y..", "..Y.."],
    7: ["...y...", "...Y...", "..YWY..", "yYWWWYy", "..YWY..", "...Y...", "...y..."],
}
STAR_TONES = {
    "gold": {"W": (255, 255, 230, 255), "Y": (255, 214, 64, 255), "y": (230, 160, 30, 255),
             "X": (255, 240, 160, 255)},
    "silver": {"W": (255, 255, 255, 255), "Y": (206, 222, 246, 255), "y": (150, 168, 200, 255),
               "X": (240, 246, 255, 255)},
    "bronze": {"W": (255, 236, 210, 255), "Y": (232, 150, 86, 255), "y": (170, 96, 46, 255),
               "X": (250, 210, 170, 255)},
}
PETAL_FRAMES = [
    [".oo.", "oPpo", "oPPo", ".oo."],
    ["..oo", ".oPo", "oPpo", "oo.."],
    ["....", "oooo", "oPpo", "oooo"],
    ["oo..", "oPo.", "opPo", "..oo"],
]
PETAL_PAL = {"o": (230, 120, 170, 255), "P": (255, 186, 214, 255), "p": (255, 236, 244, 255)}
HEART_FX = [
    ".oo.oo.",
    "oWPoPPo",
    "oPPPPPo",
    ".oPPPo.",
    "..oPo..",
    "...o...",
]
HEART_FX_PAL = {"o": (214, 60, 120, 255), "W": (255, 255, 255, 255), "P": (255, 140, 182, 255)}


@functools.lru_cache(maxsize=None)
def crown(metal="gold"):
    return grid(CROWN, dict(METALS[metal], **GEM))


@functools.lru_cache(maxsize=None)
def glint(i):
    return grid(GLINT[i % len(GLINT)], _S)


@functools.lru_cache(maxsize=None)
def bow():
    return grid(BOW, BOW_PAL)


@functools.lru_cache(maxsize=None)
def flower_pin():
    """꽃 + 왼쪽 아래 작은 잎. 오른쪽 가장자리에 다는 모양 - 왼쪽에 달 때는 부르는 쪽이 뒤집는다."""
    fl, lf = grid(FLOWER, FLOWER_PAL), grid(LEAF, LEAF_PAL)
    im = Image.new("RGBA", (fl.width + 2, fl.height + 1), T)
    im.alpha_composite(lf, (0, 7))
    im.alpha_composite(fl, (2, 0))
    return im


@functools.lru_cache(maxsize=None)
def pearl():
    return grid(PEARL, PEARL_PAL)


@functools.lru_cache(maxsize=None)
def heart():
    return grid(HEART, HEART_PAL)


@functools.lru_cache(maxsize=None)
def paw():
    return grid(PAW, {"X": PAW_COLOR})


@functools.lru_cache(maxsize=None)
def star(size, tone="gold"):
    return grid(STAR_ROWS[size], STAR_TONES.get(tone) or STAR_TONES["gold"])


@functools.lru_cache(maxsize=None)
def petal(i):
    return grid(PETAL_FRAMES[i % 4], PETAL_PAL)


@functools.lru_cache(maxsize=None)
def heart_fx():
    return grid(HEART_FX, HEART_FX_PAL)


GLOW_RIM = ((255, 226, 120), (255, 234, 150), (255, 242, 182), (255, 250, 214))


@functools.lru_cache(maxsize=None)
def glow_ring(w, phase=1):
    """발밑 빛 고리: 밝은 금빛 테 한 줄 + 아주 옅은 안쪽 (시안: 테 알파 210 · 안쪽 70).

    투명색 창이라 반투명이 안 된다 - 안쪽은 성긴 점(12칸에 하나)으로 옅게, 빛나는 것은 테 색을 밝혔다 낮췄다 (phase 0~3).
    """
    w = max(10, int(w))
    h = max(6, w // 3)
    rim = GLOW_RIM[max(0, min(3, int(phase)))] + (255,)
    im = Image.new("RGBA", (w, h), T)
    px = im.load()
    for y in range(h):
        for x in range(w):
            d = ((x + 0.5 - w / 2.0) / (w / 2.0)) ** 2 + ((y + 0.5 - h / 2.0) / (h / 2.0)) ** 2
            if d <= 1:
                if d > 0.62:
                    px[x, y] = rim
                elif y % 2 == 1 and (x + y // 2 * 2) % 6 == 0:
                    px[x, y] = (255, 240, 170, 255)
    return im


@functools.lru_cache(maxsize=None)
def necklace():
    """진주 목걸이 미리보기 (꾸미기 창): 진주 일곱 알을 반원으로 + 가운데 하트."""
    pr, ht = pearl(), heart()
    w, h = 21, 14
    im = Image.new("RGBA", (w, h), T)
    for i in range(7):
        t = i / 6.0
        x = int(round(1 + t * (w - 4)))
        y = int(round(1 + 5 * (1 - (2 * t - 1) ** 2)))
        im.alpha_composite(pr, (x, y))
    im.alpha_composite(ht, ((w - ht.width) // 2, h - ht.height))
    return im


def icon(key):
    """꾸미기 창의 칸 그림 (촘촘한 칸 그대로 - 창이 정수 배로 키운다). 모르는 열쇠면 None."""
    if key.startswith("crown_"):
        return crown(key[len("crown_"):])
    if key.startswith("fx_stars_"):
        tone = key[len("fx_stars_"):]
        im = Image.new("RGBA", (15, 13), T)
        im.alpha_composite(star(7, tone), (0, 0))
        im.alpha_composite(star(5, tone), (10, 8))
        im.alpha_composite(star(3, tone), (10, 1))
        im.alpha_composite(star(1, tone), (4, 10))
        return im
    got = {"bow": bow, "flower": flower_pin, "pearls": necklace, "fx_paw": paw,
           "fx_hearts": heart_fx, "fx_glow": lambda: glow_ring(18)}.get(key)
    if got is not None:
        return got()
    if key == "fx_petals":
        im = Image.new("RGBA", (12, 12), T)
        im.alpha_composite(petal(0), (0, 1))
        im.alpha_composite(petal(1), (7, 0))
        im.alpha_composite(petal(3), (4, 7))
        return im
    return None


# ---------------------------------------------------------------- 가방 · 꾸미기 창의 칸 그림
OUTLINE = (112, 120, 140, 255)
ITEM_PREFIX = "deco:"                # 가방에서 꾸미기를 도구처럼 다루는 이름 (ui_bag · item_icons)


def outlined(im, force=False):
    """밝은 그림(발자국 · 별 · 발밑 빛 · 진주)은 둘레에 1px 테를 두른다 - 밝은 테마(DP ...)의 흰 칸에서도 보이게.
    키운 뒤에 두른다 (촘촘한 칸에서 두르면 발가락 사이가 메워진다). 칸 바탕을 어둡게 깔면 테마가 위젯 빛깔을
    밝게 다시 칠해서(skins/dp/widgets.py) 그림 쪽에서 맞춘다."""
    from PIL import ImageFilter
    a = im.split()[3]
    px = [p for p, al in zip(im.convert("RGB").getdata(), a.getdata()) if al]
    if not px or (not force and sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px) / len(px) < 170):
        return im                   # 이미 짙다 (왕관 · 리본 · 꽃 · 하트 펜던트)
    big = Image.new("RGBA", (im.width + 2, im.height + 2), T)
    big.paste(im, (1, 1))
    ring = big.split()[3].filter(ImageFilter.MaxFilter(3))
    out = Image.new("RGBA", big.size, T)
    out.paste(Image.new("RGBA", big.size, OUTLINE), (0, 0), ring)
    out.alpha_composite(big)
    return out


def pick_icon():
    """참가 묶음 선택권: 리본 · 꽃 · 진주를 겹친 작은 꾸러미."""
    im = Image.new("RGBA", (17, 15), T)
    im.alpha_composite(flower_pin(), (0, 0))
    im.alpha_composite(bow(), (6, 7))
    return im


@functools.lru_cache(maxsize=None)
def item_icon(key, size):
    """size x size 칸 그림 (RGBA). 정수 배로 키우고 테를 두른 뒤 가운데에 놓는다. 모르는 열쇠면 None."""
    im = pick_icon() if key == "pick_join" else icon(key)
    if im is None:
        return None
    k = max(1, (int(size) - 2) // max(im.width, im.height))
    im = outlined(scaled(im, k), force=(key == "pearls"))     # 진주는 하트가 짙어도 알이 옅다
    if im.width > size or im.height > size:
        f = float(size) / max(im.width, im.height)
        im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))), Image.NEAREST)
    out = Image.new("RGBA", (int(size), int(size)), T)
    out.alpha_composite(im, ((int(size) - im.width) // 2, (int(size) - im.height) // 2))
    return out
