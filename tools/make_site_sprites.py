# -*- coding: utf-8 -*-
"""사이트(docs/)의 풀밭을 걸어다니는 도트를 그린다.

    python tools/make_site_sprites.py        docs/sprites/critters.png 를 다시 만든다

**직접 그린 생물이다** (새싹이·조약돌·물방울). 게임 속 포켓몬의 도트가 아니다 - 공개
웹페이지에는 남의 캐릭터 그림을 올리지 않는다.

시트의 꼴 (docs/assets/pets.js 가 읽는다):

    한 칸 16x16. 가로 = 걷는 프레임 4장, 세로 = 방향 4줄(아래·오른쪽·위·왼쪽).
    생물 하나가 4줄을 쓰고, 생물 셋을 세로로 이어 붙인다 (64 x 192).
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "docs", "sprites", "critters.png")

CELL = 16
FRAMES = 4
DIRS = ("down", "right", "up", "left")

# 몸통: (y, x0, x1) - 그 줄의 x0~x1 칸을 채운다
BODY = {
    "sprout": [(5, 6, 9), (6, 5, 10), (7, 4, 11), (8, 4, 11), (9, 4, 11), (10, 4, 11),
               (11, 5, 10), (12, 6, 9)],
    "pebble": [(6, 5, 10), (7, 4, 11), (8, 3, 12), (9, 3, 12), (10, 3, 12), (11, 4, 11),
               (12, 5, 10)],
    "drop": [(3, 7, 8), (4, 7, 8), (5, 6, 9), (6, 6, 9), (7, 5, 10), (8, 4, 11), (9, 4, 11),
             (10, 4, 11), (11, 5, 10), (12, 6, 9)],
}
# (채움, 가장자리, 밝은 점, 발)
COLOR = {
    "sprout": ((126, 211, 104), (58, 133, 72), (188, 240, 160), (58, 133, 72)),
    "pebble": ((156, 166, 186), (88, 96, 120), (208, 215, 230), (88, 96, 120)),
    "drop": ((104, 178, 240), (48, 104, 176), (196, 228, 255), (48, 104, 176)),
}
EYE = (24, 28, 40)
LEAF = ((96, 190, 92), (58, 133, 72))


def _cells(kind):
    out = set()
    for y, x0, x1 in BODY[kind]:
        for x in range(x0, x1 + 1):
            out.add((x, y))
    return out


def frame(kind, facing, f):
    """한 칸(16x16)을 그린다. f = 0~3 (0·2 는 두 발이 닿고, 1·3 은 한 발을 들어 몸이 뜬다)."""
    im = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    px = im.load()
    fill, edge, light, foot = COLOR[kind]
    bob = -1 if f in (1, 3) else 0
    cells = _cells(kind)

    for (x, y) in cells:
        rim = any((x + dx, y + dy) not in cells for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        px[x, y + bob] = edge + (255,) if rim else fill + (255,)
    # 밝은 점 하나 (왼쪽 위에서 빛이 온다)
    top = min(y for _x, y in cells)
    for (x, y) in ((6, top + 2), (7, top + 2), (6, top + 3)):
        if (x, y) in cells and (x - 1, y) in cells and (x, y - 1) in cells:
            px[x, y + bob] = light + (255,)

    if kind == "sprout":                      # 머리 위의 잎
        lf, le = LEAF
        for (x, y, c) in ((7, 4, le), (8, 3, lf), (9, 3, lf), (9, 2, le), (10, 2, lf)):
            px[x, y + bob] = c + (255,)

    # 눈: 앞을 보면 둘, 옆을 보면 하나, 뒤를 보면 없다
    ey = 9 + bob
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


def build():
    kinds = ("sprout", "pebble", "drop")
    sheet = Image.new("RGBA", (CELL * FRAMES, CELL * len(DIRS) * len(kinds)), (0, 0, 0, 0))
    for k, kind in enumerate(kinds):
        for d, facing in enumerate(DIRS):
            for f in range(FRAMES):
                sheet.paste(frame(kind, facing, f), (f * CELL, (k * len(DIRS) + d) * CELL))
    return sheet


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    sheet = build()
    sheet.save(OUT, optimize=True)
    print("  %s  (%dx%d)" % (os.path.relpath(OUT), sheet.size[0], sheet.size[1]))


if __name__ == "__main__":
    main()
