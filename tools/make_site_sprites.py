# -*- coding: utf-8 -*-
"""사이트(docs/)의 풀밭을 걸어다니는 도트와 풀숲을 그린다.

    python tools/make_site_sprites.py        docs/sprites/critters.png 를 다시 만든다

**직접 그린 생물이다.** 게임 속 포켓몬의 도트가 아니다 - 공개 웹페이지에는 남의 캐릭터
그림을 올리지 않는다. 둥근 몸에 점 눈과 작은 발, 그리고 종류마다 무늬 하나가 전부다.

시트의 꼴 (docs/assets/pets.js 가 읽는다 - 순서를 바꾸면 거기 KINDS 도 같이 바꾼다):

    한 칸 16x16. 가로 = 프레임 4장.
    생물 하나가 4줄을 쓴다 (아래·오른쪽·위·왼쪽을 보는 걷기). 생물을 세로로 이어 붙인다.
    맨 아래 한 줄은 풀숲이다: [풀숲 1, 풀숲 2, 꽃 핀 풀숲 1, 꽃 핀 풀숲 2] (둘씩 번갈아 흔들린다).
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "docs", "sprites", "critters.png")

CELL = 16
FRAMES = 4
DIRS = ("down", "right", "up", "left")

# 몸통: (y, x0, x1) - 그 줄의 x0~x1 칸을 채운다
ROUND = [(5, 6, 9), (6, 5, 10), (7, 4, 11), (8, 4, 11), (9, 4, 11), (10, 4, 11),
         (11, 5, 10), (12, 6, 9)]
STONE = [(6, 5, 10), (7, 4, 11), (8, 3, 12), (9, 3, 12), (10, 3, 12), (11, 4, 11),
         (12, 5, 10)]
DROP = [(3, 7, 8), (4, 7, 8), (5, 6, 9), (6, 6, 9), (7, 5, 10), (8, 4, 11), (9, 4, 11),
        (10, 4, 11), (11, 5, 10), (12, 6, 9)]
MUSH = [(4, 6, 9), (5, 4, 11), (6, 3, 12), (7, 3, 12), (8, 3, 12),          # 갓
        (9, 5, 10), (10, 5, 10), (11, 5, 10), (12, 6, 9)]                    # 몸
CLOUD = [(5, 5, 6), (5, 9, 10), (6, 4, 7), (6, 8, 11), (7, 3, 12), (8, 3, 12), (9, 3, 12),
         (10, 3, 12), (11, 4, 11), (12, 5, 10)]

# 이름: (몸통, 채움, 가장자리, 밝은 점, 발, 무늬)
# 무늬는 (x, y, 색) 목록이다. 몸통 위에 덧그린다 (뒤를 볼 때도 그대로 보인다).
MOSS = (96, 190, 92)
MOSS_D = (58, 133, 72)
KINDS = [
    ("sprout", ROUND, (126, 211, 104), (58, 133, 72), (188, 240, 160), (58, 133, 72),
     [(7, 4, MOSS_D), (8, 3, MOSS), (9, 3, MOSS), (9, 2, MOSS_D), (10, 2, MOSS)]),
    ("pebble", STONE, (156, 166, 186), (88, 96, 120), (208, 215, 230), (88, 96, 120), []),
    ("drop", DROP, (104, 178, 240), (48, 104, 176), (196, 228, 255), (48, 104, 176), []),
    # 이끼 낀 조약돌: 머리에 이끼가 덮였다
    ("moss", STONE, (150, 158, 150), (86, 96, 92), (200, 208, 200), (86, 96, 92),
     [(5, 6, MOSS_D), (6, 6, MOSS), (7, 6, MOSS), (8, 6, MOSS), (9, 6, MOSS), (10, 6, MOSS_D),
      (5, 7, MOSS), (6, 7, MOSS), (9, 7, MOSS), (10, 7, MOSS), (7, 5, MOSS), (8, 5, MOSS_D)]),
    # 숯 조약돌: 까만 몸에 불씨가 비친다
    ("ember", STONE, (70, 70, 84), (36, 36, 48), (112, 112, 128), (224, 120, 48),
     [(10, 8, (255, 168, 64)), (11, 9, (255, 120, 48)), (10, 10, (255, 168, 64)),
      (4, 10, (255, 120, 48)), (5, 11, (255, 168, 64))]),
    # 눈 조약돌: 하얀 몸에 얼음빛 가장자리
    ("snow", STONE, (238, 244, 252), (150, 178, 214), (255, 255, 255), (110, 150, 200),
     [(4, 11, (196, 216, 240)), (5, 12, (196, 216, 240)), (11, 11, (196, 216, 240)),
      (10, 12, (196, 216, 240))]),
    # 모래 조약돌: 가운데에 줄무늬 한 줄
    ("sand", STONE, (226, 196, 140), (150, 116, 70), (246, 226, 180), (150, 116, 70),
     [(x, 11, (190, 152, 96)) for x in range(5, 11)]),
    # 버섯: 갈색 갓 아래에 하얀 몸 (흔한 숲 버섯 모양. 무늬는 넣지 않는다)
    ("mush", MUSH, (244, 232, 210), (170, 150, 124), (255, 250, 236), (170, 150, 124), []),
    # 솜구름: 머리가 몽글몽글한 분홍 구름
    ("cloud", CLOUD, (250, 220, 232), (198, 146, 176), (255, 244, 248), (198, 146, 176), []),
    # 꽃봉오리: 머리에 꽃 한 송이
    ("bud", ROUND, (244, 170, 196), (176, 96, 128), (255, 214, 228), (176, 96, 128),
     [(8, 4, (255, 226, 110)), (7, 4, (255, 255, 255)), (9, 4, (255, 255, 255)),
      (8, 3, (255, 255, 255)), (8, 5, (255, 255, 255))]),
    # 도토리: 갈색 몸에 짙은 모자, 꼭지 하나
    ("acorn", ROUND, (222, 178, 116), (146, 104, 60), (244, 214, 160), (146, 104, 60),
     [(8, 4, (104, 70, 40)), (8, 3, (104, 70, 40))]),
    # 금빛 조약돌: 꽃 핀 풀숲에서만 나온다 (**맨 끝에 둔다** - pets.js 가 마지막 종으로 안다)
    ("gold", STONE, (255, 200, 72), (184, 128, 24), (255, 240, 176), (184, 128, 24),
     [(10, 7, (255, 255, 255)), (11, 8, (255, 248, 208)), (4, 10, (255, 228, 128))]),
]
# 몸 위쪽을 다른 색으로 칠하는 종: 이름 -> (이 줄까지, 채움, 가장자리)
CAP = {
    "mush": (8, (178, 126, 86), (112, 74, 48)),
    "acorn": (7, (132, 90, 54), (92, 60, 36)),
}
# 눈 높이가 다른 종 (기본 9)
EYE_Y = {"mush": 10}
EYE = (24, 28, 40)

# 풀숲: 줄기 (x, 맨 위 y) - 아래(y=14)까지 한 칸 폭으로 선다. 둘째 장은 끝이 옆으로 눕는다
BLADES = [(3, 9), (5, 6), (7, 8), (8, 4), (10, 7), (12, 9), (13, 11)]
GRASS = (96, 200, 104)
GRASS_D = (52, 140, 76)
GRASS_L = (160, 232, 150)


def _cells(shape):
    out = set()
    for y, x0, x1 in shape:
        for x in range(x0, x1 + 1):
            out.add((x, y))
    return out


def frame(kind, facing, f):
    """한 칸(16x16)을 그린다. f = 0~3 (0·2 는 두 발이 닿고, 1·3 은 한 발을 들어 몸이 뜬다)."""
    name, shape, fill, edge, light, foot, marks = kind
    cap = CAP.get(name)
    im = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    px = im.load()
    bob = -1 if f in (1, 3) else 0
    cells = _cells(shape)

    for (x, y) in cells:
        rim = any((x + dx, y + dy) not in cells for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        f2, e2 = (cap[1], cap[2]) if cap and y <= cap[0] else (fill, edge)
        px[x, y + bob] = e2 + (255,) if rim else f2 + (255,)
    # 밝은 점 하나 (왼쪽 위에서 빛이 온다)
    top = min(y for _x, y in cells)
    for (x, y) in ((6, top + 2), (7, top + 2), (6, top + 3)):
        if (x, y) in cells and (x - 1, y) in cells and (x, y - 1) in cells:
            px[x, y + bob] = (light if not cap else tuple(min(255, v + 36) for v in cap[1])) + (255,)
    for (x, y, c) in marks:
        px[x, y + bob] = c + (255,)

    # 눈: 앞을 보면 둘, 옆을 보면 하나, 뒤를 보면 없다
    ey = EYE_Y.get(name, 9) + bob
    if facing == "down":
        px[6, ey] = EYE + (255,)
        px[9, ey] = EYE + (255,)
    elif facing == "right":
        px[9, ey] = EYE + (255,)
    elif facing == "left":
        px[6, ey] = EYE + (255,)

    # 발: 번갈아 디딘다. 옆으로 걸을 때는 가는 쪽으로 한 칸 나간다
    lean = 1 if facing == "right" else -1 if facing == "left" else 0
    left, right = 6, 9
    feet = {0: (left, right), 1: (left + lean,), 2: (left, right), 3: (right + lean,)}[f]
    for x in feet:
        px[x, 13] = foot + (255,)
    return im


def tuft(sway, flower):
    """풀숲 한 칸. sway 면 줄기 끝이 한 칸 눕는다. flower 면 꽃이 둘 핀다."""
    im = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    px = im.load()
    for i, (x, top) in enumerate(BLADES):
        for y in range(top, 15):
            tip = y <= top + 1
            sx = x + (1 if sway and tip and i % 2 == 0 else -1 if sway and tip else 0)
            sx = max(0, min(CELL - 1, sx))
            px[sx, y] = (GRASS_L if y == top else GRASS if y < 12 else GRASS_D) + (255,)
    for x in range(2, 15):                       # 밑동
        px[x, 15] = GRASS_D + (255,)
    if flower:
        for (cx, cy) in ((5, 5), (11, 6)):
            cx += 1 if sway else 0
            for (dx, dy) in ((0, -1), (-1, 0), (1, 0), (0, 1)):
                px[cx + dx, cy + dy] = (255, 150, 190, 255)
            px[cx, cy] = (255, 226, 110, 255)
    return im


def build():
    rows = len(KINDS) * len(DIRS) + 1
    sheet = Image.new("RGBA", (CELL * FRAMES, CELL * rows), (0, 0, 0, 0))
    for k, kind in enumerate(KINDS):
        for d, facing in enumerate(DIRS):
            for f in range(FRAMES):
                sheet.paste(frame(kind, facing, f), (f * CELL, (k * len(DIRS) + d) * CELL))
    y = (rows - 1) * CELL
    for i, (sway, flower) in enumerate(((False, False), (True, False), (False, True), (True, True))):
        sheet.paste(tuft(sway, flower), (i * CELL, y))
    return sheet


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    sheet = build()
    sheet.save(OUT, optimize=True)
    print("  %s  (%dx%d, 생물 %d종 + 풀숲)" % (os.path.relpath(OUT), sheet.size[0], sheet.size[1],
                                          len(KINDS)))


if __name__ == "__main__":
    main()
