# -*- coding: utf-8 -*-
"""열매 텃밭 (다음 시즌, 2026-11-26) 화단 그림 — 나무 화단 위 화분 셋 · 자라는 열매 · 물방울 · 물뿌리개.

원래 칸(W x H)에 점을 찍고 SCALE 배로 키운다 (2배 도트 - 연못 · 다른 바탕화면 도트와 같은 굵기).
바탕은 투명색(key)으로 채운 RGB 다. 윈도우는 색 열쇠로 창을 뚫어서 반투명을 못 쓴다 - 그래서 알파 없이 찍고,
친구 화단의 '흐림' 도 반투명 대신 빛깔을 옅게 섞어서 낸다. 맥은 SpriteView.frames 가 key 를 알파로 되돌린다.

화분 하나의 모습 (look) = (단계, 열매, wetMask, friendBonus)
    단계 0 빈 흙 · 1 새싹 · 2 줄기 · 3 꽃 · 4 열매 (익으면 반짝)
    흙은 '지금 단계에 물을 줬으면' 짙다. 화분 아래 화단 판자에 작은 물방울 셋 ●●○ = 단계마다 물을 줬는지 (bit0 새싹 · bit1 줄기 · bit2 꽃).
    친구 물 보너스가 붙었으면 물방울 옆에 금빛 별 하나.

모드 (장 수)
    idle   4장 - 익은 화분 위에서 반짝임이 자리를 옮긴다 (안 익었으면 넉 장이 같다)
    water  6장 - 물뿌리개가 물이 필요했던 화분 위에서 물을 붓는다
"""
import functools

from PIL import Image, ImageDraw

W, H = 60, 40                      # 원래 칸 (점 하나 = 화면 SCALE 칸) - 화면에서 120 x 80
SCALE = 2
POT_CX = (11, 30, 49)              # 화분 가운데 x (원래 칸)
SOIL_Y = 21                        # 흙 윗줄 - 식물 밑동은 그 위(20)에 선다
BASE_Y = 19                        # 식물 그림의 맨 아랫줄
STAND_Y = 30                       # 화단 윗판
DROP_Y = 34                        # 물방울 꼭지 줄

# 빛깔 - 투명색(255, 0, 255)과 겹치지 않게
WOOD_D = (98, 62, 36)
WOOD_C = (156, 104, 60)
WOOD_L = (196, 142, 86)
WOOD_HI = (224, 180, 122)
POT_D = (122, 58, 38)
POT_C = (198, 104, 62)
POT_L = (228, 142, 94)
POT_HI = (246, 180, 132)
SOIL_C = (122, 80, 50)
SOIL_L = (152, 104, 66)
WET_C = (62, 40, 30)               # 물을 준 흙 - 짙다
WET_L = (88, 60, 44)
WET_SHINE = (150, 186, 214)
LEAF_C = (92, 178, 72)
LEAF_D = (50, 122, 52)
LEAF_L = (164, 224, 108)
STEM = (72, 142, 60)
CENTER = (255, 214, 72)            # 꽃술
DROP_C = (78, 152, 232)            # 찬 물방울 ●
DROP_L = (186, 224, 255)
DROP_D = (40, 96, 180)
GOLD = (255, 212, 71)              # 친구 물 보너스 별
SPARK = (255, 255, 236)            # 익은 열매 반짝임
SPARK_C = (255, 236, 140)
CAN_C = (92, 170, 196)             # 물뿌리개
CAN_D = (40, 94, 126)
CAN_L = (176, 224, 238)
WATER = (150, 210, 255)
FADE = (236, 238, 242)             # 친구 화단 - 이 빛깔로 옅게 섞는다

# 열매 빛깔 (지닌 열매 47종 가운데 자주 보는 것 - 나머지는 이름에서 고른 빛깔)
BERRY_COLOR = {
    "CHERIBERRY": (226, 58, 70), "CHESTOBERRY": (128, 96, 200), "PECHABERRY": (248, 148, 184),
    "RAWSTBERRY": (84, 196, 164), "ASPEARBERRY": (238, 222, 92), "LEPPABERRY": (234, 92, 58),
    "ORANBERRY": (64, 118, 232), "PERSIMBERRY": (250, 138, 116), "LUMBERRY": (112, 204, 88),
    "SITRUSBERRY": (250, 210, 56), "FIGYBERRY": (210, 72, 96), "WIKIBERRY": (150, 96, 210),
    "MAGOBERRY": (250, 168, 70), "AGUAVBERRY": (120, 200, 120), "IAPAPABERRY": (250, 200, 90),
    "LIECHIBERRY": (232, 76, 92), "GANLONBERRY": (110, 110, 200), "SALACBERRY": (90, 190, 110),
    "PETAYABERRY": (240, 120, 160), "APICOTBERRY": (110, 140, 230), "LANSATBERRY": (232, 72, 72),
    "STARFBERRY": (250, 220, 80), "ENIGMABERRY": (110, 80, 150), "CUSTAPBERRY": (230, 100, 120),
    "OCCABERRY": (236, 104, 60), "PASSHOBERRY": (70, 140, 230), "WACANBERRY": (250, 214, 70),
    "RINDOBERRY": (100, 190, 90), "YACHEBERRY": (140, 210, 240), "CHOPLEBERRY": (220, 80, 60),
    "KEBIABERRY": (150, 90, 190), "SHUCABERRY": (200, 160, 90), "COBABERRY": (150, 200, 240),
    "PAYAPABERRY": (240, 120, 200), "TANGABERRY": (150, 200, 80), "CHARTIBERRY": (200, 170, 110),
    "KASIBBERRY": (130, 110, 180), "HABANBERRY": (120, 100, 220), "COLBURBERRY": (110, 90, 80),
    "BABIRIBERRY": (170, 180, 190), "CHILANBERRY": (230, 210, 170), "ROSELIBERRY": (250, 150, 200),
    "KEEBERRY": (120, 190, 200), "MARANGABERRY": (90, 110, 210), "JABOCABERRY": (210, 150, 60),
    "ROWAPBERRY": (130, 160, 230),
}
_SPARE = ((226, 58, 70), (64, 118, 232), (250, 210, 56), (128, 96, 200), (112, 204, 88), (248, 148, 184))

MODES = {"idle": 4, "water": 6}
STAGE_KR = {1: "새싹", 2: "줄기", 3: "꽃", 4: "열매"}

# ---------------------------------------------------------------- 식물 도트 (아랫줄 가운데가 밑동)
# '.' 빈칸 · g 잎 · G 짙은 잎 · l 밝은 잎 · s 줄기 · p 꽃잎 · P 짙은 꽃잎 · c 꽃술 · b 열매 · B 짙은 열매 · h 열매 빛
SPROUT = (
    "lg...gl",
    "gGg.gGg",
    ".gGsGg.",
    "...s...",
    "...s...",
)
STEM_ = (
    "....l....",
    "...lgg...",
    "...gGs...",
    "....s....",
    "lgg.s....",
    "gGGgs....",
    ".gg.s.ggl",
    "....sgGGg",
    "....s.gg.",
    "....s....",
    "....s....",
)
FLOWER = (
    "....p.p....",
    "...ppPpp...",
    "..pPpcpPp..",
    "...ppPpp...",
    "....psp....",
    ".....s.....",
    ".lgg.s.....",
    ".gGGgs..gl.",
    "..gg.s.gGGg",
    ".....sggg..",
    ".....s.....",
    "..lg.s.....",
    "..gGgs.....",
    ".....s.....",
    ".....s.....",
)
FRUIT = (
    ".....lgl.....",
    "....lgGgg....",
    "...gGgsgGg...",
    ".bb.ggsgg.bb.",
    "bhbb..s..bhbb",
    "bbbB.lsg.bbbB",
    ".bB.gGsGg.bB.",
    "...ggGsGgg...",
    "..lgg.s.ggl..",
    ".gGGg.s.gGGg.",
    "..gg..s..gg..",
    "......s......",
    "......s......",
    "......s......",
)
# 가운데 열매 하나는 따로 (줄기 꼭대기 옆에 매달린다)
TOP_BERRY = (".bb.", "bhbb", "bbbB", ".bB.")
STAGES = {1: SPROUT, 2: STEM_, 3: FLOWER, 4: FRUIT}

# 물뿌리개 (오른쪽 위로 뻗은 꼭지 끝에서 물이 나온다) - o 테 · m 몸 · L 빛 · r 꼭지
CAN = (
    "..ooo.......",
    ".o...o....rr",
    "ooooooo..rr.",
    "oLmmmmo.r...",
    "oLmmmmorr...",
    "ommmmmo.....",
    "ooooooo.....",
)


def size():
    """창 크기 (화면 픽셀)."""
    return W * SCALE, H * SCALE


def pot_x(slot):
    """그 화분 가운데 x (창 안 화면 픽셀)."""
    return POT_CX[int(slot)] * SCALE + SCALE // 2


def slot_at(x):
    """창 안 x (화면 픽셀) 에 있는 화분 번호 0~2 - 화분 사이 한가운데를 경계로 나눈다."""
    a = (POT_CX[0] + POT_CX[1]) / 2.0 * SCALE
    b = (POT_CX[1] + POT_CX[2]) / 2.0 * SCALE
    return 0 if x < a else (1 if x < b else 2)


def berry_color(berry):
    if not berry:
        return LEAF_C
    c = BERRY_COLOR.get(berry)
    if c is None:
        c = _SPARE[sum(ord(ch) for ch in berry) % len(_SPARE)]
    return c


def _mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _pal(berry):
    c = berry_color(berry)
    return {
        "g": LEAF_C, "G": LEAF_D, "l": LEAF_L, "s": STEM,
        "p": _mix(c, (255, 255, 255), 0.45), "P": c, "c": CENTER,
        "b": c, "B": _mix(c, (0, 0, 0), 0.35), "h": _mix(c, (255, 255, 255), 0.7),
    }


def _blit(d, rows, x0, y0, pal):
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch != ".":
                d.point((x0 + i, y0 + j), fill=pal[ch])


def _plant(d, cx, stage, berry):
    rows = STAGES.get(stage)
    if not rows:
        return
    w = len(rows[0])
    _blit(d, rows, cx - w // 2, BASE_Y - len(rows) + 1, _pal(berry))


# ---------------------------------------------------------------- 화단 · 화분 · 흙 · 물방울
def _stand(d):
    """나무 화단 - 윗판 하나 · 앞판 셋 (판자 이음매) · 못 두 개."""
    d.rectangle((0, STAND_Y, W - 1, STAND_Y + 1), fill=WOOD_L)
    d.line((1, STAND_Y, W - 2, STAND_Y), fill=WOOD_HI)
    d.point((0, STAND_Y), fill=WOOD_D)
    d.point((W - 1, STAND_Y), fill=WOOD_D)
    d.rectangle((1, STAND_Y + 2, W - 2, H - 1), fill=WOOD_C, outline=WOOD_D)
    d.line((1, STAND_Y + 2, W - 2, STAND_Y + 2), fill=WOOD_D)            # 윗판 그림자
    for sx in ((POT_CX[0] + POT_CX[1]) // 2, (POT_CX[1] + POT_CX[2]) // 2):
        d.line((sx, STAND_Y + 3, sx, H - 2), fill=WOOD_D)               # 판자 이음매
    for x, y, n in ((4, 38, 3), (23, 37, 4), (42, 38, 3), (55, 37, 1)):
        d.line((x, y, x + n, y), fill=WOOD_L)                           # 나뭇결
    d.point((3, 33), fill=WOOD_HI)
    d.point((W - 4, 33), fill=WOOD_HI)


def _pot(d, cx):
    """테라코타 화분 - 넓은 테 · 아래로 좁아지는 몸 · 왼쪽에 빛 한 줄."""
    d.line((cx - 6, 22, cx + 6, 22), fill=POT_HI)
    d.line((cx - 6, 23, cx + 6, 23), fill=POT_L)
    for y in (22, 23):
        d.point((cx - 7, y), fill=POT_D)
        d.point((cx + 7, y), fill=POT_D)
    for y in range(24, 30):
        half = 6 if y < 27 else 5
        d.line((cx - half, y, cx + half, y), fill=POT_C)
        d.point((cx - half, y), fill=POT_D)
        d.point((cx + half, y), fill=POT_D)
    d.line((cx - 5, 24, cx + 5, 24), fill=POT_D)                         # 테 밑 그림자
    d.line((cx - 3, 25, cx - 3, 28), fill=POT_L)                         # 빛
    d.line((cx - 5, 29, cx + 5, 29), fill=POT_D)


def _soil(d, cx, wet):
    c, l = (WET_C, WET_L) if wet else (SOIL_C, SOIL_L)
    d.line((cx - 6, SOIL_Y, cx + 6, SOIL_Y), fill=c)
    d.line((cx - 4, SOIL_Y - 1, cx + 3, SOIL_Y - 1), fill=c)
    d.point((cx - 3, SOIL_Y - 1), fill=l)
    d.point((cx + 4, SOIL_Y), fill=l)
    d.point((cx - 5, SOIL_Y), fill=l)
    if wet:
        d.point((cx + 1, SOIL_Y), fill=WET_SHINE)                         # 촉촉한 빛
        d.point((cx - 2, SOIL_Y), fill=WET_SHINE)


def _drop(d, x, full):
    y = DROP_Y
    if full:
        d.point((x, y), fill=DROP_C)
        d.line((x - 1, y + 1, x + 1, y + 1), fill=DROP_C)
        d.line((x - 1, y + 2, x + 1, y + 2), fill=DROP_C)
        d.point((x - 1, y + 1), fill=DROP_L)
        d.point((x + 1, y + 2), fill=DROP_D)
    else:
        for p in ((x, y), (x - 1, y + 1), (x + 1, y + 1), (x - 1, y + 2), (x, y + 2), (x + 1, y + 2)):
            d.point(p, fill=WOOD_D)


def _drops(d, cx, mask, bonus):
    for k, dx in enumerate((-4, 0, 4)):
        _drop(d, cx + dx, bool(int(mask or 0) & (1 << k)))
    if bonus:
        _star(d, cx)


def _star(d, cx):
    """친구 물 보너스 - 물방울 오른쪽 금빛 별."""
    x, y = cx + 7, DROP_Y + 1
    for p in ((x, y - 1), (x - 1, y), (x, y), (x + 1, y), (x, y + 1)):
        d.point(p, fill=GOLD)


def _spark(d, x, y, big):
    if big:
        d.line((x, y - 2, x, y + 2), fill=SPARK)
        d.line((x - 2, y, x + 2, y), fill=SPARK)
    else:
        for p in ((x, y - 1), (x - 1, y), (x + 1, y), (x, y + 1)):
            d.point(p, fill=SPARK)
    d.point((x, y), fill=SPARK_C)


# 익은 화분 위 반짝임 자리 (장마다) - 화분 가운데에서 (dx, y, 큰 별)
SPARKS = (((5, 7, True), (-6, 12, False)), ((-4, 4, False),), ((6, 11, False), (-5, 8, True)), ((2, 2, False),))


def _can(d, cx, i):
    """물뿌리개 - 화분 왼쪽 위에서 물을 붓는다. 물줄기가 장마다 흘러내린다."""
    x0 = cx - 11
    _blit(d, CAN, x0, 0, {"o": CAN_D, "m": CAN_C, "L": CAN_L, "r": CAN_D})
    rx = x0 + 10                                                         # 꼭지 끝
    for k in range(4):
        y = 3 + ((i * 2 + k * 4) % 16)
        if y < SOIL_Y - 1:
            x = rx - 1 + (k % 3)
            d.point((x, y), fill=WATER)
            d.point((x, y + 1), fill=WATER)


@functools.lru_cache(maxsize=64)
def frames(pots, key=(255, 0, 255), mode="idle", water=(), faded=False):
    """화단 그림들 (화면 크기, RGB, 바탕은 key).

    pots  화분 셋의 모습 ((단계, 열매, wetMask, friendBonus), ...) - 친구 화단은 wetMask 를 None 으로 (물방울 · 젖은 흙 없이)
    water 물을 붓는 화분 번호들 (mode 'water')
    faded 친구 화단 - 옅게
    """
    n = MODES[mode]
    out = []
    for i in range(n):
        im = Image.new("RGB", (W, H), tuple(key))
        d = ImageDraw.Draw(im)
        _stand(d)
        for slot, look in enumerate(pots):
            stage, berry, mask, bonus = look
            cx = POT_CX[slot]
            stage = int(stage or 0)
            wet = 1 <= stage <= 3 and mask is not None and bool(int(mask) & (1 << (stage - 1)))
            _soil(d, cx, wet)
            _pot(d, cx)
            _plant(d, cx, stage, berry)
            if stage == 4:
                _blit(d, TOP_BERRY, cx - 1, BASE_Y - len(FRUIT) - 1, _pal(berry))
                if mode == "idle":
                    for dx, y, big in SPARKS[i % len(SPARKS)]:
                        _spark(d, cx + dx, y, big)
            if stage >= 1 and mask is not None:
                _drops(d, cx, mask, bonus)
            elif stage >= 1 and bonus:
                _star(d, cx)                                             # 친구 화단: 물방울 없이 별만
            if mode == "water" and slot in water:
                _can(d, cx, i)
        if faded:
            im = _fade(im, key)
        out.append(im.resize((W * SCALE, H * SCALE), Image.NEAREST))
    return tuple(out)


def _fade(im, key):
    """친구 화단 - key 가 아닌 점을 FADE 쪽으로 옅게 (반투명 없이 '흐림')."""
    key = tuple(key)
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            c = px[x, y]
            if c != key:
                px[x, y] = _mix(c, FADE, 0.5)
    return im
