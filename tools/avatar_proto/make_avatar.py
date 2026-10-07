#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""사진 한 장 → 트레이너 도트(뒤·앞) + 걷기 도트 12칸. 포스크탑 아바타 시제품.

    python make_avatar.py 사진.jpg                    # 한 번 호출 (flash, 약 98원)
    python make_avatar.py 사진.jpg --mode split       # 두 번 호출 (트레이너 / 걷기 따로)
    python make_avatar.py 사진.jpg --model lite       # 가장 싼 모델 (약 49원, 걷기 도트가 덜 또렷)
    python make_avatar.py --reprocess out/폴더        # 모델을 다시 안 부르고, 받아 둔 그림으로 자르기만 다시
    python make_avatar.py --selftest                  # 키 없이: 자르고 도트로 만드는 뒷부분만 시험

키는 환경변수 GEMINI_API_KEY 나 이 폴더의 .env 에서 읽는다 (코드·깃에 적지 않는다).

## 어떻게 만드나

그림 모델에게 "도트 12칸을 그려 줘" 라고만 하면 칸 수도 크기도 방향도 제멋대로 나온다.
그래서 **틀(template)을 같이 준다**: 예시 도트를 자리에 맞춰 놓은 그림 한 장을 주고,
"이 틀의 모든 캐릭터를 사진 속 사람으로 다시 그려라. 자리·자세는 그대로" 라고 시킨다.

모델이 준 그림은 1024px 짜리 '도트처럼 보이는 큰 그림' 이다. 도트 한 칸이 약 4px 로
그려져 있다. 그래서

  1. 바탕색(마젠타)을 지우고
  2. 틀에서 정해 둔 자리로 캐릭터를 하나씩 잘라
  3. **모델이 그린 도트의 격자를 찾아서 칸마다 한 점씩** 뽑는다 (sample)

3 이 중요하다. 처음에는 정해 둔 크기(80x80)로 그냥 줄였는데, 모델의 격자와 어긋나서
안경·목도리 무늬 같은 한두 칸짜리가 다 뭉개졌다. 격자에 맞춰 뽑으면 모델이 그린 도트가
그대로 나온다. 그래서 도트의 크기는 우리가 아니라 모델이 정한다 (트레이너 약 116칸,
걷기 약 42칸) - 칸(TRAINER, CELL)은 그보다 넉넉하게 잡아 두고, 넘칠 때만 줄인다.

오른쪽을 보는 걷기 줄은 **왼쪽 줄을 뒤집어** 만든다. 모델에게 시키면 왼쪽을 한 번 더
그리는 일이 잦고(첫 시험에서 그랬다), 뒤집으면 두 방향이 어긋날 일도 없다.

## 값

그림 한 장이 곧 값이다 (사진·지시문 입력은 1원도 안 된다). 그래서 **한 장에 전부**
담는 것(combined)이 가장 싸다. 모델·값은 MODELS 를 보라 (2026-10 기준).
"""
import argparse
import base64
import glob
import io
import json
import math
import os
import sys
import time

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
REFS = os.path.join(HERE, "refs")
API = "https://generativelanguage.googleapis.com/v1beta"

BG = (255, 0, 255)          # 바탕색. 옷·머리에 거의 없는 색이라 지우기 쉽다
CANVAS = 1024               # 틀 한 변
BLOCK = 5                   # 틀에서 도트 한 칸의 크기 (px)
VIRT = 204                  # 틀의 크기 (도트 칸). 204 x 5 = 1020px, 둘레에 2px 를 남긴다
EDGE = (CANVAS - VIRT * BLOCK) // 2
TRAINER = 96                # 트레이너 도트 한 칸. 배틀 화면의 포켓몬 도트(96x96)와 같다
CELL_W, CELL_H = 32, 32     # 걷기 도트 한 칸. 모델은 키 46~48칸으로 그려 오고, 여기서 32 로 줄인다.
                            # 32x48 로 줄이지 않고 담는 것도 해 봤지만 사용자가 32x32 쪽 결과를 골랐다
KRW = 1400                  # 원화로 어림할 때 쓰는 환율 (가정)
LAYOUT_NOW = 5              # 틀의 판 (generate 가 모델에 맞춰 바꾼다 - MODEL_LAYOUT).
                            # 1 = 걷기 네 줄(처음), 2 = 세 줄, 3 = 한 칸 5px 격자 + 걷기 세 줄,
                            # 4 = 3 에 회색 마네킹 네 줄(버림), 5 = 한 칸 5px 격자 + 걷기 네 줄
# 모델마다 잘 따라오는 틀이 다르다. flash 는 세 줄 틀을 줘도 두 번 다 네 줄을 그려 왔다
# (정면을 두 줄, 또는 뒷모습을 두 줄) - 네 방향 시트가 몸에 밴 모양이라 아예 네 줄을 준다.
# lite 는 네 줄을 주면 도트 굵기를 바꾸거나 격자 없이 그려서 세 줄이 낫다. pro 는 세 줄을 그대로 따랐다.
MODEL_LAYOUT = {"lite": 3, "flash": 5, "pro": 3}

# 이름: (모델, 입력 $, 글 출력 $, 그림 출력 $ - 모두 100만 토큰당, 그림 한 장 정가 $)
# 2026-10-06 ai.google.dev/gemini-api/docs/pricing. 그림 모델은 무료 구간이 없다.
MODELS = {
    "lite": ("gemini-3.1-flash-lite-image", 0.25, 1.50, 30.0, 0.0336),   # 가장 싸다 (1K 만)
    "flash": ("gemini-3.1-flash-image", 0.50, 3.00, 60.0, 0.067),        # 한 단계 위
    "pro": ("gemini-3-pro-image", 2.00, 12.0, 120.0, 0.134),             # 가장 비싸다 (글 값은 어림)
}

# 틀에서 각 그림이 놓이는 칸 (도트 칸 단위, x0 y0 x1 y1). 걷기는 격자의 왼쪽 위와 칸 사이 틈.
# **틀 전체가 한 칸 = BLOCK px 인 진짜 도트**다. 모델은 받은 그림의 격자를 따라 그리므로,
# 격자가 분명한 틀을 주면 도트 굵기를 따라온다 (틀이 제각각일 때는 한 칸이 3.5~5.2px 이었다).
# 걷기는 세 줄(정면·왼쪽·뒤)이다. 네 줄로도 해 봤는데(판 4) 모델이 도트 굵기를 3.6px 로
# 바꾸거나 격자 없이 그려 와서 버렸다.
VBOX = {
    "combined": {"back": (2, 4, 74, 100), "front": (2, 104, 74, 200), "walk": (82, 46, 6, 8)},
    "trainer": {"back": (8, 54, 100, 150), "front": (104, 54, 196, 150)},
    "walk": {"walk": (48, 46, 6, 8)},
}


def walk_cells(kind, rows=3):
    """걷기 칸들 [줄][칸] (도트 칸 단위). 줄 수가 달라도 위아래 한가운데에 놓는다."""
    x0, _y0, gx, gy = VBOX[kind]["walk"]
    y0 = (VIRT - (rows * CELL_H + (rows - 1) * gy)) // 2
    return [[(x0 + c * (CELL_W + gx), y0 + r * (CELL_H + gy), x0 + c * (CELL_W + gx) + CELL_W,
              y0 + r * (CELL_H + gy) + CELL_H) for c in range(3)] for r in range(rows)]


def frac(box):
    """도트 칸 단위의 자리를 그림 전체에 대한 비율(0~1)로."""
    return tuple((EDGE + v * BLOCK) / float(CANVAS) for v in box)


# 자를 때의 경계 (덩어리로 못 가렸을 때만 쓴다). 그림이 자리에서 조금 밀려도 되게 넉넉히 나눈다.
PARTS = {
    "combined": {"back": (0.0, 0.0, 0.385, 0.5), "front": (0.0, 0.5, 0.385, 1.0),
                 "walk": (0.385, 0.0, 1.0, 1.0)},
    "trainer": {"back": (0.0, 0.0, 0.5, 1.0), "front": (0.5, 0.0, 1.0, 1.0)},
    "walk": {"walk": (0.0, 0.0, 1.0, 1.0)},
}
TEMPLATE_ROWS = {1: ("down", "left", "right", "up"), 2: ("down", "left", "up"),
                 3: ("down", "left", "up"), 4: ("down", "left", "right", "up"),
                 5: ("down", "left", "right", "up")}                               # 모델이 그리는 줄
SHEET_ROWS = ("down", "left", "right", "up")        # 게임에 주는 줄. right 는 left 를 뒤집은 것
STEP = (1, 0, 1, 2)                                 # 걷는 순서: 가운데 칸이 서 있는 모습이다

STYLE = """Style: clean hard-edged pixel art like a 16-bit / Nintendo DS era handheld RPG. Dark outline, \
flat cel shading with 2-3 tones per colour, small limited palette. No anti-aliasing, no gradients, no blur, \
no realistic shading.

Background: one completely flat solid magenta (#FF00FF) everywhere, also between arms and legs. \
No ground shadows, no text, no labels, no grid lines, no frames, no watermark."""

LIKENESS = """Likeness is the most important thing. Copy from the photo: hair style and hair colour, skin tone, \
face shape, glasses / facial hair / hat if present, and the exact clothing (type and colours of top, bottom, \
shoes, bag and accessories). If part of the body is not visible in the photo, invent plain clothes that match. \
Do NOT keep the template character's hair, cap, backpack or clothes - only its position and size."""

GRID = """Pixel grid (strict): the template is real low-resolution pixel art that has been enlarged - every \
pixel of it is a 5x5 block and the whole sheet is 204x204 pixels. Draw the new sheet on exactly the same grid \
with the same block size; do not use smaller or larger pixels anywhere."""

GRID_BIG = """Each large sprite stays inside the area of the template's large sprite and is at most 96 pixels \
tall (about 480 on screen)."""

GRID_SMALL = """Each small walking sprite must fit completely inside a 32x32-pixel cell (160x160 on screen), \
hair and feet included, exactly as large as the template's small sprites - do not enlarge them."""

FRONT_POSE = """The large FRONT sprite is this character's signature battle-intro pose, like the trainer sprite \
shown at the start of a battle in a classic monster-catching RPG. Do NOT copy the template's pose for this one: \
invent a confident, characterful full-body pose that suits this particular person and outfit - for example a \
hand on the hip, a hand in a coat pocket, adjusting the glasses or scarf, arms crossed, pointing forward, or \
holding a capture ball. Front or three-quarter front view, face clearly visible, standing, whole body visible \
from head to shoes.
Proportions of the FRONT sprite: draw it like a classic trainer battle sprite with natural, fairly realistic \
body proportions - a tall slim figure about five to six heads tall, with a small head, long legs and a long \
torso, the same build as the template's front sprite. It must NOT be chibi or super-deformed: no oversized \
head, no short stubby legs. (Only the small walking sprites are chibi.)"""

def rows_text(rows):
    """걷기 줄들이 무엇인지 적은 글 (틀의 줄 수에 맞춰)."""
    names = {"down": "FRONT view, all three face the viewer",
             "left": "SIDE view, all three face the LEFT edge of the image",
             "right": "SIDE view, all three face the RIGHT edge of the image",
             "up": "BACK view, all three face away from the viewer (we see the back of the head)"}
    lines = ["  row %d - %s;" % (i + 1, names[r]) for i, r in enumerate(rows)]
    return ("Each ROW is ONE facing direction shown as three animation frames, so all three sprites in a row "
            "face the SAME direction, and every row is a DIFFERENT direction:\n" + "\n".join(lines) + "\n"
            "Within a row the three columns are animation frames only: column 1 = mid-step with one foot "
            "forward, column 2 = standing still, column 3 = mid-step with the other foot forward. Columns are "
            "NOT directions. Do not add any extra row or extra sprite.")


PROMPTS = {
    "combined": """You are a sprite artist for a retro handheld monster-collecting RPG.

IMAGE 1 is a PHOTO of a real person.
IMAGE 2 is a LAYOUT TEMPLATE: a sprite sheet on a flat magenta background. It contains
- top-left: one large BACK-VIEW battle sprite (the character seen from behind, upper body, cut off at the bottom),
- bottom-left: one large FRONT-VIEW full-body standing sprite,
- right side: a grid of %(n_small)d small chibi walking sprites, %(dims)s. %(rows)s

TASK: redraw the whole template as ONE new sprite sheet in which every figure is the person from the photo, \
drawn as one and the same character.

%(likeness)s

%(pose)s

Layout is strict: exactly 2 large figures and %(n_small)d small figures, each in the same position as in the \
template. The back sprite and the %(n_small)d small sprites keep the template's pose and facing direction (only \
the front sprite gets a new pose). All %(n_all)d figures must clearly be the same person in the same outfit. \
All %(n_small)d small sprites have the same height. Keep clear empty gaps between figures - they must not touch or overlap. The small sprites are \
chibi (large head, about two heads tall).

%(grid)s %(grid_big)s %(grid_small)s

%(style)s""",
    "trainer": """You are a sprite artist for a retro handheld monster-collecting RPG.

IMAGE 1 is a PHOTO of a real person.
IMAGE 2 is a LAYOUT TEMPLATE on a flat magenta background with two trainer sprites: on the LEFT a BACK-VIEW \
battle sprite (seen from behind, upper body, cut off at the bottom), on the RIGHT a FRONT-VIEW full-body \
standing sprite.

TASK: redraw the template so that both sprites are the person from the photo, as one and the same character.

%(likeness)s

%(pose)s

Layout is strict: exactly two figures, each in the same position as in the template. The back sprite keeps the \
template's pose and facing direction. Keep a clear empty gap between them.

%(grid)s %(grid_big)s

%(style)s""",
    "walk": """You are a sprite artist for a retro handheld monster-collecting RPG.

IMAGE 1 is a PHOTO of a real person.
IMAGE 2 is a LAYOUT TEMPLATE: %(n_small)d small chibi walking sprites on a flat magenta background, %(dims)s. \
%(rows)s
%(extra)s
TASK: redraw the template so that all %(n_small)d sprites are the person from the photo, as one and the same \
character.

%(likeness)s

Layout is strict: exactly %(n_small)d figures in a grid of %(dims)s, each in the same position, in the same \
pose and facing the same direction as in the template. All %(n_small)d must clearly be the same person in the \
same outfit and have the same height. Keep clear empty gaps between figures. The sprites are chibi (large head, about two heads tall).

%(grid)s %(grid_small)s

%(style)s""",
}
WALK_EXTRA = """IMAGE 3 is the full-size sprite of this same character that was already drawn. Use it as the \
character design: the small sprites must have the same hair, face and clothes.
"""


# ---------------------------------------------------------------- 바탕 지우기·자리 찾기
def blobs(bits, w, h):
    """켜진 칸(1)들의 덩어리 목록 [[칸 번호 ...]]. 대각선으로 닿은 것도 한 덩어리다."""
    seen = bytearray(w * h)
    out = []
    for start in range(w * h):
        if not bits[start] or seen[start]:
            continue
        seen[start] = 1
        comp, stack = [], [start]
        while stack:
            i = stack.pop()
            comp.append(i)
            x, y = i % w, i // w
            for nx in (x - 1, x, x + 1):
                for ny in (y - 1, y, y + 1):
                    if 0 <= nx < w and 0 <= ny < h:
                        j = ny * w + nx
                        if bits[j] and not seen[j]:
                            seen[j] = 1
                            stack.append(j)
        out.append(comp)
    return out


def drop_specks(mask, small=4, min_area=5):
    """그림 자리(255)에서 **티끌 덩어리**를 지운다. 몸에 붙은 가는 팔다리는 건드리지 않는다.

    티끌 하나가 캐릭터 옆에 떠 있으면 '그림의 테두리' 가 그만큼 늘어나서 캐릭터가 칸에서
    밀린다. 덩어리를 세는 일은 느려서 1/small 로 줄여서 한다.
    """
    w, h = mask.size
    sw, sh = max(1, w // small), max(1, h // small)
    low = mask.resize((sw, sh), Image.BOX).point(lambda v: 1 if v > 0 else 0)
    bits = low.tobytes()
    keep = bytearray(sw * sh)
    for comp in blobs(bits, sw, sh):
        if len(comp) >= min_area:
            for i in comp:
                keep[i] = 255
    big = Image.frombytes("L", (sw, sh), bytes(keep)).resize((w, h), Image.NEAREST)
    return ImageChops.multiply(mask, big)


def white_key(img, tol=30, colors=14):
    """흰 바탕의 예시 그림에서 바탕만 투명하게. **가장자리와 이어진 흰색만** 지운다.

    흰 옷·눈의 흰자까지 지우면 안 된다. 그래서 색만 보지 않고 가장자리에서 번져 들어간다.
    예시는 JPEG 라 그림 둘레에 얼룩이 있다 - 떨어져 있는 티끌은 지우고 색 수도 줄여 둔다
    (틀이 깨끗해야 모델이 '도트' 로 알아듣는다).
    """
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    seen = bytearray(w * h)
    stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= w or y >= h or seen[y * w + x]:
            continue
        r, g, b = px[x, y]
        if min(r, g, b) < 255 - tol:
            continue
        seen[y * w + x] = 1
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    alpha = Image.frombytes("L", (w, h), bytes(0 if s else 255 for s in seen))
    alpha = drop_specks(alpha, small=1, min_area=14)
    out = rgb.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.NONE).convert("RGBA")
    out.putalpha(alpha)
    return out


def peel_light(sprite, floor=185, times=2):
    """가장자리의 허연 점을 벗긴다. 흰 바탕의 예시를 줄이면 그림 둘레에 흰 테가 남는다 -
    그대로 틀에 두면 모델이 흰 윤곽선을 따라 그린다."""
    w, h = sprite.size
    px = sprite.load()
    for _ in range(times):
        drop = []
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if not a or min(r, g, b) < floor:
                    continue
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h or not px[nx, ny][3]:
                        drop.append((x, y))
                        break
        for x, y in drop:
            px[x, y] = (0, 0, 0, 0)
    return sprite


def runs(profile, want, min_gap):
    """한 줄로 눌러 본 그림(0=빈칸)에서 덩어리의 (시작, 끝) 들. want 개가 아니면 None."""
    out, start = [], None
    for i, v in enumerate(profile):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append([start, i])
            start = None
    if start is not None:
        out.append([start, len(profile)])
    merged = []
    for r in out:
        if merged and r[0] - merged[-1][1] < min_gap:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    merged = [r for r in merged if r[1] - r[0] >= min_gap]       # 티끌은 덩어리가 아니다
    return merged if len(merged) == want else None


def cuts(found, total, want):
    """덩어리 사이 한가운데를 자르는 선 want+1 개. 못 찾았으면 똑같이 나눈다."""
    if not found:
        return [int(round(total * i / float(want))) for i in range(want + 1)]
    out = [0]
    for a, b in zip(found, found[1:]):
        out.append((a[1] + b[0]) // 2)
    return out + [total]


def figure_mask(img, tol=60):
    """모델이 준 그림에서 캐릭터 자리(255)와 바탕(0).

    바탕색은 네 귀퉁이에서 읽는다 - 모델이 #FF00FF 를 정확히 안 지킨다 (245, 6, 237 이었다).
    가장자리를 깎거나 세게 다듬지 않는다: 한 칸(약 4px)짜리 머리끝·손끝이 같이 사라진다.
    윤곽선과 바탕이 섞인 테두리는 어차피 칸의 가운데만 뽑으므로(sample) 도트에 안 들어간다.
    """
    rgb = img.convert("RGB")
    w, h = rgb.size
    k = max(4, w // 64)
    corners = [rgb.crop(b).resize((1, 1), Image.BOX).getpixel((0, 0))
               for b in ((0, 0, k, k), (w - k, 0, w, k), (0, h - k, k, h), (w - k, h - k, w, h))]
    bg = tuple(sorted(c[i] for c in corners)[1] for i in range(3))
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, bg))
    r, g, b = diff.split()
    far = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mask = far.point(lambda v: 255 if v > tol else 0)
    mask = mask.filter(ImageFilter.MedianFilter(3))          # 한 점짜리 티끌을 없앤다
    return drop_specks(mask, small=2, min_area=3), bg        # 떨어져 있는 작은 덩어리도


def region(size, frac):
    w, h = size
    return (int(round(frac[0] * w)), int(round(frac[1] * h)),
            int(round(frac[2] * w)), int(round(frac[3] * h)))


def find_one(mask, box):
    """그 구역 안의 그림 테두리 (전체 좌표). 없으면 None."""
    bb = mask.crop(box).getbbox()
    if not bb:
        return None
    return (box[0] + bb[0], box[1] + bb[1], box[0] + bb[2], box[1] + bb[3])


def find_grid(mask, box, cols=3, rows=3):
    """걷기 칸들의 테두리 [줄][칸]. 빈 칸은 None. 틀에서 조금 밀려 나와도 칸을 찾는다."""
    part = mask.crop(box)
    bb = part.getbbox()
    if not bb:
        return [[None] * cols for _ in range(rows)]
    part = part.crop(bb)
    ox, oy = box[0] + bb[0], box[1] + bb[1]
    w, h = part.size
    col_p = list(part.resize((w, 1), Image.BOX).tobytes())
    row_p = list(part.resize((1, h), Image.BOX).tobytes())
    xs = cuts(runs([v > 2 for v in col_p], cols, max(2, w // 60)), w, cols)
    ys = cuts(runs([v > 2 for v in row_p], rows, max(2, h // 80)), h, rows)
    out = []
    for r in range(rows):
        line = []
        for c in range(cols):
            cell = (ox + xs[c], oy + ys[r], ox + xs[c + 1], oy + ys[r + 1])
            line.append(find_one(mask, cell))
        out.append(line)
    return out


# ---------------------------------------------------------------- 모델이 그린 도트의 격자
def edge_profile(fig, axis):
    """이웃한 줄끼리 얼마나 다른가 (줄 번호 -> 값). 도트의 경계에서 값이 튄다.

    값 i 는 i-1 번째 줄과 i 번째 줄 사이다. 즉 i 에서 튀면 i 번째 줄부터 새 칸이다.
    """
    w, h = fig.size
    if axis == "x":
        d = ImageChops.difference(fig.crop((1, 0, w, h)), fig.crop((0, 0, w - 1, h)))
        d = d.convert("L").resize((w - 1, 1), Image.BOX)
    else:
        d = ImageChops.difference(fig.crop((0, 1, w, h)), fig.crop((0, 0, w, h - 1)))
        d = d.convert("L").resize((1, h - 1), Image.BOX)
    return [0] + list(d.tobytes())


def on_grid(prof, p, phase):
    """그 간격·시작점의 선 위에 경계가 얼마나 몰려 있나 (선 하나당 평균).

    선이 놓인 **바로 그 줄**만 본다. 옆줄까지 봐 주면(±1) 간격 3 은 모든 줄을 덮어서
    무엇이든 잘 맞는 것처럼 나온다 - 실제로 4 를 3 으로 잘못 쟀다.
    """
    n = len(prof)
    tot = cnt = 0
    x = phase
    while x < n - 0.5:
        tot += prof[min(n - 1, int(round(x)))]
        cnt += 1
        x += p
    return tot / float(cnt) if cnt else 0.0


def best_phase(prof, p):
    """그 간격에서 가장 잘 맞는 시작점의 점수."""
    return max(on_grid(prof, p, s / 4.0) for s in range(max(1, int(p * 4))))


def find_pitch(prof, lo=2.5, hi=9.0):
    """경계가 되풀이되는 간격 (얼마나 뚜렷한가, 간격). 못 찾으면 (0, None).

    진짜 간격의 두 배·세 배도 똑같이 잘 맞는다 (선이 전부 진짜 경계 위에 놓인다) - 실제로
    3.9 를 7.85 로 쟀다. 그래서 가장 잘 맞는 간격을 찾은 뒤 **그 절반·3분의 1 도 맞는지**
    본다. 진짜 간격의 절반은 선의 반이 칸 한가운데에 놓여서 점수가 반 토막 난다 (0.6 아래).
    0.75 넘게 맞으면 그쪽이 진짜다.
    """
    if len(prof) < 24:
        return 0.0, None
    mean = sum(prof) / float(len(prof)) or 1.0
    top, pitch = 0.0, None
    p = 3.0
    while p <= hi + 1e-9:
        v = best_phase(prof, p)
        if v > top:
            top, pitch = v, p
        p += 0.05
    if not pitch:
        return 0.0, None
    changed = True
    while changed:
        changed = False
        for k in (2, 3):
            base = pitch / k
            if base < lo:
                continue
            v, q = max((best_phase(prof, base * (1 + d / 100.0)), base * (1 + d / 100.0)) for d in range(-3, 4))
            if v >= top * 0.75:
                top, pitch, changed = v, q, True
                break
    return top / mean, pitch


def pixel_pitch(raw, boxes):
    """모델이 그린 도트 한 칸이 원본 몇 px 인가. 큰 그림들에서 재서 가운뎃값을 쓴다.

    작은 그림(걷기)에서는 경계가 몇 개 없어서 재는 값이 들쭉날쭉하다 (3.0 ~ 5.9 가 나왔다).
    한 장 안에서는 칸 크기가 같으므로 큰 그림에서 잰 값을 다 같이 쓴다.
    """
    got = []
    for bb in boxes:
        fig = raw.crop(bb)
        for axis in ("x", "y"):
            score, p = find_pitch(edge_profile(fig, axis))
            if p and score >= 1.35:
                got.append(p)
    if not got:
        return None
    got.sort()
    return got[len(got) // 2]


def phase_of(prof, pitch):
    """그 그림에서 격자가 시작하는 자리 (간격, 시작점). 간격은 6% 안에서 다듬는다.

    전체에서 잰 간격이 3% 만 틀려도 32칸짜리 그림에서는 끝에서 한 칸이 어긋난다 (32칸이
    33칸으로 뽑힌다). 그림마다 가장 잘 맞는 간격을 다시 찾는다.
    """
    best = (-1.0, pitch, 0.0)
    for k in range(-12, 13):
        p = pitch * (1.0 + k / 200.0)
        for s in range(int(p * 4)):
            v = on_grid(prof, p, s / 4.0)
            if v > best[0]:
                best = (v, p, s / 4.0)
    return best[1], best[2]


def cells_of(length, p, phase):
    """격자 선으로 나눈 칸들 [(시작, 끝)] (px, 소수). 가장자리의 덜 찬 칸도 넣는다."""
    x = phase - math.ceil(phase / p) * p
    out = []
    while x < length:
        out.append((x, x + p))
        x += p
    return out


def inner(a, b, limit):
    """칸의 가운데 절반에 드는 (px 번호들, 원래 몇 개여야 하나). 칸 가장자리는 옆 칸과 섞여 있어서 안 본다.

    그림 테두리에 걸친 칸은 px 가 일부만 들어온다. '원래 몇 개' 를 같이 줘서, 번진 테두리
    한 줄만 걸친 칸이 한 칸으로 세어지지 않게 한다 (32칸짜리가 33칸으로 뽑혔다).
    """
    q = (b - a) / 4.0
    lo, hi = int(math.ceil(a + q)), int(math.floor(b - q))
    if hi < lo:
        lo = hi = int((a + b) / 2.0)
    return [i for i in range(lo, hi + 1) if 0 <= i < limit], hi - lo + 1


def flatten_colors(sprites, colors):
    """뽑아 낸 도트들의 색을 **같이** 줄인다 (같은 색표를 쓰게). None 은 그대로 둔다.

    걷기 칸들을 칸마다 따로 줄이면 같은 옷이 칸마다 조금씩 다른 색이 되어 걸을 때 깜빡인다.
    색은 **뽑아 낸 뒤에** 줄인다. 큰 그림에서 먼저 줄였더니 검은 코트가 색표를 다 차지해서
    흰 셔츠가 살색과 한 색이 됐다 - 줄인 뒤에는 칸 하나가 한 표라 작은 부분도 살아남는다.
    """
    real = [s for s in sprites if s is not None]
    if not real:
        return sprites
    w = sum(s.size[0] for s in real)
    h = max(s.size[1] for s in real)
    pool = Image.new("RGB", (w, h), (24, 24, 28))       # 빈 곳은 윤곽선 같은 어두운 색 (색표 한 자리만 쓴다)
    x = 0
    for s in real:
        pool.paste(s.convert("RGB"), (x, 0), s.getchannel("A"))
        x += s.size[0]
    pal = pool.quantize(colors=colors, method=Image.FASTOCTREE, dither=Image.NONE)
    out = []
    for s in sprites:
        if s is None:
            out.append(None)
            continue
        q = s.convert("RGB").quantize(palette=pal, dither=Image.NONE).convert("RGBA")
        q.putalpha(s.getchannel("A"))
        out.append(q)
    return out


def unspill(sprite):
    """가장자리에 묻은 바탕색(마젠타)을 걷어 낸다. 두 번 돈다 (한 겹 벗기면 새 가장자리가 나온다).

    모델은 윤곽선 바깥에 바탕과 섞인 자줏빛 칸을 한 겹 두른다. 바탕색이 짙게 묻은 칸은
    지우고, 옅게 묻은 칸은 자줏빛만 뺀다 (윤곽선으로 남는다).
    """
    w, h = sprite.size
    px = sprite.load()
    for _ in range(2):
        drop, fix = [], []
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                tint = min(r, b) - g
                if not a or tint <= 12:
                    continue
                if tint > 120:
                    drop.append((x, y))             # 거의 바탕색이다 (손가락 사이 같은 작은 구멍)
                    continue
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h or not px[nx, ny][3]:
                        (drop if tint > 70 else fix).append((x, y))
                        break
        for x, y in drop:
            px[x, y] = (0, 0, 0, 0)
        for x, y in fix:
            r, g, b, a = px[x, y]
            px[x, y] = (min(r, g + 6), g, min(b, g + 6), a)
    return sprite


def middle(values):
    values.sort()
    return values[len(values) // 2]


def pick(fig, m, cols, rows):
    """칸마다(cols x rows 의 px 번호 묶음) 색 한 점. 그림만큼 잘라 RGBA 로.

    칸 안에서 색마다 가운뎃값을 쓴다. 평균을 내면 옆 칸의 색이 섞여 윤곽선이 번진다.
    """
    w = fig.size[0]
    data, alpha = fig.tobytes(), m.tobytes()
    out = Image.new("RGBA", (len(cols), len(rows)), (0, 0, 0, 0))
    px = out.load()
    for j, (ys, ny) in enumerate(rows):
        for i, (xs, nx) in enumerate(cols):
            rs, gs, bs, n = [], [], [], nx * ny
            for y in ys:
                row = y * w
                for x in xs:
                    if alpha[row + x]:
                        k = (row + x) * 3
                        rs.append(data[k])
                        gs.append(data[k + 1])
                        bs.append(data[k + 2])
            if n and len(rs) * 2 > n:
                px[i, j] = (middle(rs), middle(gs), middle(bs), 255)
    box = out.getbbox()
    return unspill(out.crop(box)) if box else None


def sample(raw, fig, pitch):
    """그림 하나를 **모델이 그린 격자대로** 한 칸에 한 점씩 뽑는다. fig = (테두리, 자리 그림).

    칸의 가운데 절반만 본다. 칸 가장자리는 옆 칸과 섞여 있다.
    """
    bb, m = fig
    img = raw.crop(bb)
    w, h = img.size
    px_, phx = phase_of(edge_profile(img, "x"), pitch)
    py_, phy = phase_of(edge_profile(img, "y"), pitch)
    cols = [inner(a, b, w) for a, b in cells_of(w, px_, phx)]
    rows = [inner(a, b, h) for a, b in cells_of(h, py_, phy)]
    return pick(img, m, cols, rows)


def sample_fixed(raw, fig, scale):
    """격자를 못 찾았을 때: 정한 배율로 줄인다 (조금 뭉개진다)."""
    bb, m = fig
    img = raw.crop(bb)
    w, h = img.size
    tw, th = max(1, int(round(w / scale))), max(1, int(round(h / scale)))
    cols = [list(range(tx * w // tw, max(tx * w // tw + 1, (tx + 1) * w // tw))) for tx in range(tw)]
    rows = [list(range(ty * h // th, max(ty * h // th + 1, (ty + 1) * h // th))) for ty in range(th)]
    return pick(img, m, [(c, len(c)) for c in cols], [(r, len(r)) for r in rows])


def shrink_together(figs, max_w, max_h):
    """칸보다 큰 그림이 있으면 **다 같이 같은 배율로** 줄인다 (없으면 그대로). 쓴 배율도 돌려준다."""
    real = [f for f in figs if f is not None]
    if not real:
        return figs, 1.0
    k = min(1.0, max_w / float(max(f.size[0] for f in real)), max_h / float(max(f.size[1] for f in real)))
    if k >= 1.0:
        return figs, 1.0
    out = []
    for f in figs:
        out.append(None if f is None else f.resize(
            (max(1, int(round(f.size[0] * k))), max(1, int(round(f.size[1] * k)))), Image.NEAREST))
    return out, k


def place(fig, size, bottom=0):
    """작은 그림을 size 칸의 가운데 아래에 놓는다 (발이 바닥에 닿게)."""
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.paste(fig, ((size[0] - fig.size[0]) // 2, size[1] - fig.size[1] - bottom), fig)
    return out


def figures(mask, small=4):
    """떨어져 있는 그림 덩어리들 [(넓이, 테두리, 그 덩어리만의 자리 그림)]. 큰 것부터.

    손끝처럼 **몸에서 떨어져 나온 작은 조각**은 바로 옆의 큰 덩어리에 붙인다. 옆에 아무것도
    없는 조각은 티끌이라 버린다.
    """
    w, h = mask.size
    sw, sh = w // small, h // small
    low = mask.resize((sw, sh), Image.BOX).point(lambda v: 1 if v > 0 else 0)
    comps = sorted(blobs(low.tobytes(), sw, sh), key=len, reverse=True)
    if not comps:
        return []

    def box_of(comp):
        xs, ys = [i % sw for i in comp], [i // sw for i in comp]
        return min(xs), min(ys), max(xs) + 1, max(ys) + 1
    limit = max(6, len(comps[min(len(comps) - 1, 3)]) // 12)        # 이보다 작으면 조각이다
    main = [list(c) for c in comps if len(c) >= limit]
    boxes = [box_of(c) for c in main]
    for c in comps:
        if len(c) >= limit:
            continue
        x0, y0, x1, y1 = box_of(c)
        for i, (a0, b0, a1, b1) in enumerate(boxes):
            if x0 <= a1 + 3 and x1 >= a0 - 3 and y0 <= b1 + 3 and y1 >= b0 - 3:
                main[i].extend(c)
                break
    out = []
    for comp in main:
        x0, y0, x1, y1 = box_of(comp)
        bits = bytearray((x1 - x0) * (y1 - y0))
        for i in comp:
            bits[(i // sw - y0) * (x1 - x0) + (i % sw - x0)] = 255
        up = Image.frombytes("L", (x1 - x0, y1 - y0), bytes(bits)).resize(
            ((x1 - x0) * small, (y1 - y0) * small), Image.NEAREST)
        box = (x0 * small, y0 * small, x1 * small, y1 * small)
        own = ImageChops.multiply(mask.crop(box), up)
        bb = own.getbbox()
        if not bb:
            continue
        tight = (box[0] + bb[0], box[1] + bb[1], box[0] + bb[2], box[1] + bb[3])
        out.append((len(comp), tight, own.crop(bb)))
    return sorted(out, key=lambda f: -f[0])


def assign(found, kind, layout):
    """덩어리들을 뒷모습·앞모습·걷기 [줄][칸] 으로 나눈다. 수가 안 맞으면 None.

    자리를 틀에 맞춰 자르지 않고 **덩어리의 크기와 서로의 위아래·좌우**로 가린다. 모델은
    그림을 틀에서 꽤 밀어 놓는다 (앞모습의 머리가 화면 절반 위로 올라가고, 걷기 칸이
    왼쪽으로 60px 넘어와서 옆 그림의 조각이 딸려 들어왔다).
    """
    parts = PARTS[kind]
    n_big = 2 if "back" in parts else 0
    rows = TEMPLATE_ROWS[layout]
    n_walk = 3 * len(rows) if "walk" in parts else 0
    if len(found) < n_big + n_walk:
        return None
    big, walk = found[:n_big], found[n_big:]
    if big and walk and big[-1][0] < walk[0][0] * 1.5:
        return None                                 # 큰 그림과 작은 그림이 안 갈린다
    # 걷기 그림보다 훨씬 작은 덩어리는 티끌이다 (가장 큰 걷기 그림의 3분의 1 아래)
    walk = [f for f in walk if f[0] * 3 >= walk[0][0]] if walk else walk
    if len(walk) < n_walk:
        return None
    out = {}
    if big:
        center = (lambda f: (f[1][1] + f[1][3]) / 2.0) if kind == "combined" else \
                 (lambda f: (f[1][0] + f[1][2]) / 2.0)
        first, second = sorted(big, key=center)
        out["back"], out["front"] = (first[1], first[2]), (second[1], second[2])
    if walk:
        # **줄부터 가른다** (위아래로 떨어진 곳에서 끊는다). 모델이 한 줄에 네 칸을 그릴 때가
        # 있다 - 그때는 그 줄의 앞 세 칸만 쓴다. 크기순으로 아홉 개를 고르면 줄이 섞인다.
        walk = sorted(walk, key=lambda f: (f[1][1] + f[1][3]) / 2.0)
        tall = sorted(f[1][3] - f[1][1] for f in walk)[len(walk) // 2]
        lines = [[walk[0]]]
        for prev, f in zip(walk, walk[1:]):
            gap = (f[1][1] + f[1][3]) / 2.0 - (prev[1][1] + prev[1][3]) / 2.0
            if gap > tall * 0.5:
                lines.append([])
            lines[-1].append(f)
        # 세 칸이 안 되는 줄은 덤으로 그린 그림이다 (flash 가 맨 위에 하나를 따로 그렸다).
        # 줄이 더 많으면 **위에서부터** 쓴다 - 덤으로 그린 줄은 아래에 붙는다 (뒷모습을 한 줄 더 그렸다).
        full = [line for line in lines if len(line) >= 3]
        if len(full) < len(rows):
            return None
        if len(full) != len(lines) or len(full) > len(rows):
            out["extra"] = sum(len(line) for line in lines) - 3 * len(rows)
        lines = full[:len(rows)]
        grid = []
        for line in lines:
            line = sorted(line, key=lambda f: (f[1][0] + f[1][2]) / 2.0)[:3]
            grid.append([(f[1], f[2]) for f in line])
        out["walk"] = grid
    return out


def by_layout(mask, kind, layout, size):
    """덩어리로 못 가렸을 때: 틀에서 정해 둔 자리대로 자른다 (처음 쓰던 방식)."""
    parts = PARTS[kind]
    out = {}
    for name in ("back", "front"):
        if name in parts:
            bb = find_one(mask, region(size, parts[name]))
            if bb:
                out[name] = (bb, mask.crop(bb))
    if "walk" in parts:
        grid = find_grid(mask, region(size, parts["walk"]), rows=len(TEMPLATE_ROWS[layout]))
        out["walk"] = [[(b, mask.crop(b)) if b else None for b in line] for line in grid]
    return out


def cut_sprites(raw, kind, layout=None):
    """모델이 준 그림 한 장 → ({'back':…, 'front':…, 'walk':…}, 알릴 말들, 잰 값들)."""
    layout = layout or LAYOUT_NOW
    raw = raw.convert("RGB")
    mask, bg = figure_mask(raw)
    parts = PARTS[kind]
    rows = TEMPLATE_ROWS[layout]
    out, notes, info = {}, [], {"bg": bg}
    found = figures(mask)
    got = assign(found, kind, layout)
    info["figures"] = len(found)
    if got is None:
        want = (2 if "back" in parts else 0) + (3 * len(rows) if "walk" in parts else 0)
        notes.append("그림 덩어리가 %d개입니다 (%d개여야 합니다) - 틀의 자리대로 잘랐습니다. 캐릭터끼리 "
                     "붙었거나 빠진 칸이 있습니다" % (len(found), want))
        got = by_layout(mask, kind, layout, raw.size)
    if got.get("extra"):
        notes.append("모델이 걷기 그림을 %d개 더 그렸습니다 - 위의 %d줄만 썼습니다" % (got["extra"], len(rows)))
    big = dict((n, got[n]) for n in ("back", "front") if got.get(n))
    for n in ("back", "front"):
        if n in parts and n not in big:
            notes.append("%s 그림을 못 찾았습니다" % n)
    if "front" in big:
        bb = big["front"][0]
        if bb[3] >= raw.size[1] - 3 or bb[1] <= 2 or bb[0] <= 2 or bb[2] >= raw.size[0] - 3:
            notes.append("앞모습이 그림 가장자리에 닿아 잘렸습니다 (전신이 다 안 나왔습니다) - 다시 그려야 합니다")
    grid = got.get("walk") or []
    small = [f for line in grid for f in line if f]
    if "walk" in parts and len(small) < 3 * len(rows):
        notes.append("걷기 %d칸 중 %d칸만 찾았습니다" % (3 * len(rows), len(small)))

    pitch = pixel_pitch(raw, [f[0] for f in big.values()] or [f[0] for f in small])
    info["pitch"] = pitch
    if not pitch:
        notes.append("모델이 그린 도트의 격자를 못 찾아서 정한 크기로 줄였습니다 (조금 뭉개집니다)")

    if big:
        names = sorted(big)
        figs = []
        for n in names:
            bb = big[n][0]
            scale = max((bb[2] - bb[0]) / float(TRAINER - 2), (bb[3] - bb[1]) / float(TRAINER - 1))
            figs.append(sample(raw, big[n], pitch) if pitch else sample_fixed(raw, big[n], scale))
        figs = flatten_colors(figs, 64)
        info["trainer_native"] = dict((n, f.size) for n, f in zip(names, figs) if f)
        figs, k = shrink_together(figs, TRAINER, TRAINER)
        if k < 1.0:
            notes.append("트레이너 도트가 칸(%d)보다 커서 %.0f%% 로 줄였습니다" % (TRAINER, k * 100))
        for n, f in zip(names, figs):
            if f:
                # 뒷모습은 아래에서 잘린 그림이라 바닥에 붙이고, 앞모습은 발밑에 한 줄 띄운다
                out[n] = place(f, (TRAINER, TRAINER), 0 if n == "back" else min(1, TRAINER - f.size[1]))
    if small:
        common = max(max((f[0][2] - f[0][0]) for f in small) / float(CELL_W),
                     max((f[0][3] - f[0][1]) for f in small) / float(CELL_H))
        flat = [(sample(raw, f, pitch) if pitch else sample_fixed(raw, f, common))
                if f else None for line in grid for f in line]
        flat = flatten_colors(flat, 32)
        info["walk_native"] = [f.size for f in flat if f]
        flat, k = shrink_together(flat, CELL_W, CELL_H)
        if k < 1.0:
            notes.append("걷기 도트가 칸(%dx%d)보다 커서 %.0f%% 로 줄였습니다" % (CELL_W, CELL_H, k * 100))
        rowed = dict((rows[r], flat[r * 3:r * 3 + 3]) for r in range(len(rows)))
        # 오른쪽은 왼쪽을 뒤집어 만든다 (모델이 그린 오른쪽 줄이 있어도 안 쓴다)
        rowed["right"] = [None if f is None else ImageOps.mirror(f) for f in rowed.get("left", [None] * 3)]
        sheet = Image.new("RGBA", (CELL_W * 3, CELL_H * len(SHEET_ROWS)), (0, 0, 0, 0))
        for r, name in enumerate(SHEET_ROWS):
            for c, f in enumerate(rowed.get(name) or []):
                if f:
                    cell = place(f, (CELL_W, CELL_H))
                    sheet.paste(cell, (c * CELL_W, r * CELL_H), cell)
        out["walk"] = sheet
    return out, notes, info


# ---------------------------------------------------------------- 틀
def ref_figures():
    """예시 그림에서 캐릭터를 하나씩: (뒷모습, 앞모습, 걷기 {방향: [세 칸]}).

    걷기 예시는 32x32 도트를 1.42배로 키운 JPEG 이다 (547px / 12칸 = 45.6). 원래 크기로
    되돌려서 쓴다.
    """
    t = white_key(Image.open(os.path.join(REFS, "trainer_ref.png")))
    a = t.getchannel("A")
    col = list(a.resize((t.size[0], 1), Image.BOX).tobytes())
    found = runs([v > 0 for v in col], 2, 2)
    if not found:
        raise SystemExit("refs/trainer_ref.png 에서 뒷모습·앞모습 두 그림을 못 찾았습니다.")
    back, front = [t.crop((x0, 0, x1, t.size[1])) for x0, x1 in found]
    back, front = back.crop(back.getbbox()), front.crop(front.getbbox())
    sheet = Image.open(os.path.join(REFS, "walk_ref.png")).convert("RGB").resize((32 * 3, 32 * 4), Image.BOX)
    w = peel_light(white_key(sheet, tol=40))
    walk = {}
    for r, name in enumerate(TEMPLATE_ROWS[1]):
        line = []
        for c in range(3):
            cell = w.crop((c * 32, r * 32, (c + 1) * 32, (r + 1) * 32))
            box = cell.getbbox()
            line.append(cell.crop(box) if box else cell)
        walk[name] = line
    return back, front, walk


def stretch(fig, tall, wide=None):
    """도트를 키 tall 칸으로 (폭이 wide 를 넘으면 거기에 맞춘다). 점을 뭉개지 않고 늘린다."""
    k = tall / float(fig.size[1])
    if wide and fig.size[0] * k > wide:
        k = wide / float(fig.size[0])
    return fig.resize((max(1, int(round(fig.size[0] * k))), max(1, int(round(fig.size[1] * k)))), Image.NEAREST)


def build_template(kind):
    """모델에게 줄 틀. **한 칸이 BLOCK px 인 진짜 도트 한 장**이다 (마젠타 바탕).

    작은 판(VIRT x VIRT)에 도트를 1칸 = 1점으로 놓고 통째로 BLOCK 배 키운다. 예전에는 그림마다
    제각각 키워서 놓았더니(뒷모습 7.4배, 걷기 2.1배) 틀에 격자라고 할 것이 없었고, 모델도
    도트 굵기를 제멋대로 골랐다 (한 칸 3.5~5.2px).
    """
    back, front, walk = ref_figures()
    virt = Image.new("RGB", (VIRT, VIRT), BG)
    lay = VBOX[kind]

    def put(fig, box):
        virt.paste(fig, (box[0] + (box[2] - box[0] - fig.size[0]) // 2, box[3] - fig.size[1]), fig)
    for name, fig in (("back", back), ("front", front)):
        if name in lay:
            box = lay[name]
            put(stretch(fig, box[3] - box[1] - 2, box[2] - box[0] - 2), box)
    if "walk" in lay:
        rows = TEMPLATE_ROWS[LAYOUT_NOW]
        cells = walk_cells(kind, len(rows))
        # **모든 칸의 키를 같게** 놓는다. 예시의 뒷모습 줄은 발이 잘려 있어 키가 작은데,
        # 모델이 그걸 그대로 따라 그려서 위를 볼 때만 캐릭터가 줄어들었다.
        tall = min(CELL_H - 2, max(f.size[1] for name in rows for f in walk[name]))
        for r, name in enumerate(rows):
            for c in range(3):
                put(stretch(walk[name][c], tall, CELL_W - 2), cells[r][c])
    out = Image.new("RGB", (CANVAS, CANVAS), BG)
    out.paste(virt.resize((VIRT * BLOCK, VIRT * BLOCK), Image.NEAREST), (EDGE, EDGE))
    return out


# ---------------------------------------------------------------- 제미나이
def png_b64(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def photo_b64(path, longest=768):
    """사진을 보낼 크기로. 돌아간 사진을 바로 세우고, 위치 같은 딸린 정보(EXIF)는 버린다."""
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    img.thumbnail((longest, longest), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode("ascii"), img


def find_images(node, out):
    """응답 어디에 들어 있든 그림(base64)을 찾는다. API 모양이 조금 달라도 받게."""
    if isinstance(node, dict):
        data = node.get("data")
        if isinstance(data, str) and len(data) > 1000 and (
                node.get("type") == "image" or str(node.get("mime_type") or node.get("mimeType") or "")
                .startswith("image/")):
            out.append(data)
        for v in node.values():
            find_images(v, out)
    elif isinstance(node, list):
        for v in node:
            find_images(v, out)
    return out


def find_uris(node, out):
    """그림을 주소로 줬을 때 (data 대신 uri)."""
    if isinstance(node, dict):
        if node.get("type") == "image" and isinstance(node.get("uri"), str):
            out.append(node["uri"])
        for v in node.values():
            find_uris(v, out)
    elif isinstance(node, list):
        for v in node:
            find_uris(v, out)
    return out


def usage_of(resp):
    """(입력 토큰, 출력 토큰, 그중 그림 토큰). 모르는 것은 None."""
    u = resp.get("usage") or resp.get("usageMetadata") or {}
    tin = u.get("total_input_tokens", u.get("promptTokenCount"))
    tout = u.get("total_output_tokens", u.get("candidatesTokenCount"))
    img = None
    for m in u.get("output_tokens_by_modality") or []:
        if str(m.get("modality")).lower() == "image":
            img = (img or 0) + int(m.get("tokens") or 0)
    return tin, tout, img


def trim(node):
    """기록용: 긴 base64 는 길이만 남긴다."""
    if isinstance(node, dict):
        return dict((k, trim(v)) for k, v in node.items())
    if isinstance(node, list):
        return [trim(v) for v in node]
    if isinstance(node, str) and len(node) > 300:
        return "<%d자 생략>" % len(node)
    return node


def call_gemini(key, model, prompt, images, log=None):
    """지시문 + 그림들 → (그림, 쓴 토큰). 그림은 [(mime, base64)]."""
    import requests
    parts = []
    for i, (mime, data) in enumerate(images):
        parts.append({"type": "text", "text": "IMAGE %d:" % (i + 1)})
        parts.append({"type": "image", "mime_type": mime, "data": data})
    parts.append({"type": "text", "text": prompt})
    full = {"model": model, "input": parts, "store": False,
            # 이 모델은 PNG 로 안 준다 ("Supported values: 'image/jpeg'" 로 거절당했다)
            "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": "1:1",
                                "image_size": "1K"}}
    plain = {"model": model, "input": parts}        # 위의 덧붙인 값을 안 받아 주면 이걸로 한 번 더
    head = {"x-goog-api-key": key, "Content-Type": "application/json"}
    last, used, refused = None, None, None
    for name, body in (("full", full), ("plain", plain)):
        for attempt in range(2):
            r = requests.post(API + "/interactions", headers=head, data=json.dumps(body), timeout=240)
            last, used = r, name
            if r.status_code in (429, 500, 502, 503) and attempt == 0:
                time.sleep(4)
                continue
            break
        if last.status_code != 400:
            break
        refused = last.text[:600]                   # 왜 안 받았는지 남겨 둔다
    try:
        resp = last.json()
    except ValueError:
        resp = {"text": last.text[:2000]}
    if log:
        with io.open(log, "w", encoding="utf-8") as f:
            f.write(json.dumps({"status": last.status_code, "request": used, "refused_first": refused,
                                "body": trim(resp)}, ensure_ascii=False, indent=1))
    if last.status_code != 200:
        err = resp.get("error") or resp
        raise SystemExit("제미나이가 거절했습니다 (HTTP %d): %s"
                         % (last.status_code, json.dumps(trim(err), ensure_ascii=False)[:600]))
    found = find_images(resp, [])
    if found:
        raw = base64.b64decode(found[-1])
    else:
        uris = find_uris(resp, [])
        if not uris:
            raise SystemExit("응답에 그림이 없습니다. 무엇이 왔는지는 %s 를 보세요 (안전 필터에 걸렸을 수 "
                             "있습니다)." % (log or "기록"))
        raw = requests.get(uris[-1], headers={"x-goog-api-key": key}, timeout=120).content
    return Image.open(io.BytesIO(raw)).convert("RGB"), usage_of(resp)


def cost_of(model_key, usage):
    """($, 쓴 토큰으로 계산했나). 그림 토큰과 글 토큰은 값이 스무 배 다르다."""
    _id, pin, ptext, pimg, each = MODELS[model_key]
    tin, tout, img = usage
    if tin is None or tout is None:
        return each, False
    if img is None:
        img = min(tout, 1120)
    return tin / 1e6 * pin + img / 1e6 * pimg + max(0, tout - img) / 1e6 * ptext, True


# ---------------------------------------------------------------- 보여 주기
def font(size):
    for path in ("/System/Library/Fonts/AppleSDGothicNeo.ttc", "C:/Windows/Fonts/malgun.ttf",
                 "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except Exception:                                   # noqa: BLE001
            pass
    return ImageFont.load_default()


def checker(size, a=(176, 184, 198), b=(196, 203, 215), step=8):
    out = Image.new("RGB", size, a)
    d = ImageDraw.Draw(out)
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            if (x // step + y // step) % 2:
                d.rectangle((x, y, x + step - 1, y + step - 1), fill=b)
    return out


def on_checker(sprite, k):
    big = sprite.resize((sprite.size[0] * k, sprite.size[1] * k), Image.NEAREST)
    out = checker(big.size)
    out.paste(big, (0, 0), big)
    return out


def preview(photo, raws, sprites, lines, path):
    """한눈에: 사진 · 모델이 준 그림 · 게임에 들어갈 도트(크게)."""
    f, fs = font(17), font(13)
    tiles = []
    if photo is not None:
        p = photo.copy()
        p.thumbnail((300, 300))
        tiles.append(("올린 사진", p))
    for name, raw in raws:
        r = raw.copy()
        r.thumbnail((300, 300))
        tiles.append((name, r))
    for name, label in (("back", "뒷모습 (실시간 배틀의 내 쪽)"), ("front", "앞모습 (프로필 · 상대가 보는 나)"),
                        ("walk", "걷기 12칸 (아래·왼쪽·오른쪽·위)")):
        if name in sprites:
            s = sprites[name]
            tiles.append(("%s %dx%d" % (label, s.size[0], s.size[1]), on_checker(s, 4)))
    pad, top = 18, 18
    w = sum(t[1].size[0] for t in tiles) + pad * (len(tiles) + 1)
    h = max(t[1].size[1] for t in tiles) + top + 44 + 22 * len(lines) + 20
    out = Image.new("RGB", (max(w, 700), h), (24, 27, 36))
    d = ImageDraw.Draw(out)
    x = pad
    for label, im in tiles:
        d.text((x, top), label, fill=(210, 214, 224), font=fs)
        out.paste(im, (x, top + 24))
        x += im.size[0] + pad
    y = max(t[1].size[1] for t in tiles) + top + 40
    for line in lines:
        d.text((pad, y), line, fill=(255, 208, 90), font=f)
        y += 22
    out.save(path)


def walk_gif(sheet, path, k=5):
    """네 방향이 걷는 모습 (한 줄에 나란히). 게임에서 어떻게 보일지 본다."""
    frames = []
    for i in STEP:
        im = Image.new("RGB", (CELL_W * 4 * k + 5 * 8, CELL_H * k + 16), (104, 168, 88))
        for r in range(4):
            cell = sheet.crop((i * CELL_W, r * CELL_H, (i + 1) * CELL_W, (r + 1) * CELL_H))
            big = cell.resize((CELL_W * k, CELL_H * k), Image.NEAREST)
            im.paste(big, (8 + r * (CELL_W * k + 8), 8), big)
        frames.append(im)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=170, loop=0)


def save_all(out_dir, photo, raws, sprites, lines):
    for name, im in sprites.items():
        im.save(os.path.join(out_dir, name + ".png"))
    if "walk" in sprites:
        walk_gif(sprites["walk"], os.path.join(out_dir, "walk.gif"))
    preview(photo, raws, sprites, lines, os.path.join(out_dir, "preview.png"))


def info_line(info):
    bits = []
    if info.get("pitch"):
        bits.append("모델의 도트 한 칸 = %.2fpx" % info["pitch"])
    t = info.get("trainer_native") or {}
    if t:
        bits.append("트레이너 원래 크기 " + ", ".join("%s %dx%d" % (n, s[0], s[1]) for n, s in sorted(t.items())))
    wn = info.get("walk_native") or []
    if wn:
        bits.append("걷기 원래 키 %d~%d칸" % (min(s[1] for s in wn), max(s[1] for s in wn)))
    return " · ".join(bits)


# ---------------------------------------------------------------- 실행
def find_key():
    """키를 찾는다: 환경변수 → 이 폴더의 .env (GEMINI_API_KEY=...). 값은 어디에도 찍지 않는다.

    터미널에서 export 한 값은 **그 터미널에서만** 산다. 다른 창·다른 프로그램에서 돌리면
    안 보인다. 그래서 .env 파일도 본다 (.gitignore 에 넣어 뒀다).
    """
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key.strip()
    path = os.path.join(HERE, ".env")
    if os.path.exists(path):
        with io.open(path, encoding="utf-8") as f:
            for line in f:
                name, _, value = line.strip().partition("=")
                if name.replace("export ", "").strip() in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                    value = value.strip().strip("'\"")
                    if value:
                        return value
    return None


def generate(args):
    global LAYOUT_NOW
    LAYOUT_NOW = MODEL_LAYOUT[args.model]
    key = find_key()
    if not key:
        raise SystemExit("제미나이 키가 안 보입니다. aistudio.google.com/apikey 에서 만든 뒤 둘 중 하나:\n"
                         "  · 이 터미널에서  export GEMINI_API_KEY=만든키\n"
                         "  · 이 폴더의 .env 파일에  GEMINI_API_KEY=만든키  한 줄")
    model = MODELS[args.model][0]
    name = os.path.splitext(os.path.basename(args.photo))[0]
    out_dir = os.path.join(args.out, "%s-%s-%s%s" % (name, args.mode, args.model,
                                                    ("-" + args.tag) if args.tag else ""))
    os.makedirs(out_dir, exist_ok=True)
    b64, photo = photo_b64(args.photo)
    photo.save(os.path.join(out_dir, "photo.jpg"), quality=88)
    rows = TEMPLATE_ROWS[LAYOUT_NOW]
    say = dict(likeness=LIKENESS, style=STYLE, rows=rows_text(rows), extra="", pose=FRONT_POSE, grid=GRID,
               grid_big=GRID_BIG, grid_small=GRID_SMALL, n_small=3 * len(rows), n_all=3 * len(rows) + 2,
               dims="3 columns x %d rows" % len(rows))
    sprites, raws, notes, total, exact, calls, infos = {}, [], [], 0.0, True, 0, {}
    kinds = ["combined"] if args.mode == "combined" else ["trainer", "walk"]
    with io.open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"layout": LAYOUT_NOW, "mode": args.mode, "model": model}))
    for kind in kinds:
        tpl = build_template(kind)
        tpl.save(os.path.join(out_dir, "template_%s.png" % kind))
        images = [("image/jpeg", b64), ("image/png", png_b64(tpl))]
        words = dict(say)
        if kind == "walk" and "front" in sprites:
            # 먼저 그린 앞모습을 같이 준다 - 큰 도트와 작은 도트가 같은 사람으로 나오게
            big = sprites["front"].resize((TRAINER * 4, TRAINER * 4), Image.NEAREST)
            flat = Image.new("RGB", big.size, BG)
            flat.paste(big, (0, 0), big)
            images.append(("image/png", png_b64(flat)))
            words["extra"] = WALK_EXTRA
        prompt = PROMPTS[kind] % words
        with io.open(os.path.join(out_dir, "prompt_%s.txt" % kind), "w", encoding="utf-8") as f:
            f.write(prompt)                     # 어떤 지시문으로 나온 그림인지 남겨 둔다
        print("· %s 그리는 중 (%s) ..." % (kind, model))
        t0 = time.time()
        raw, usage = call_gemini(key, model, prompt, images,
                                 log=os.path.join(out_dir, "response_%s.json" % kind))
        calls += 1
        raw.save(os.path.join(out_dir, "raw_%s.png" % kind))
        raws.append(("모델이 준 그림 (%s)" % kind, raw))
        c, ok = cost_of(args.model, usage)
        total, exact = total + c, exact and ok
        print("  %.1f초 · 입력 %s · 출력 %s (그림 %s) 토큰 · $%.4f" % (time.time() - t0, usage[0], usage[1],
                                                                 usage[2], c))
        got, n, info = cut_sprites(raw, kind)
        sprites.update(got)
        notes.extend(n)
        infos.update(info)
    lines = ["%s · 호출 %d번 · $%.4f (약 %d원, 1달러 %d원 가정)%s"
             % (model, calls, total, round(total * KRW), KRW, "" if exact else " - 쓴 토큰을 못 받아 정가로 어림"),
             info_line(infos)]
    lines += ["⚠ " + n for n in notes]
    save_all(out_dir, photo, raws, sprites, [x for x in lines if x])
    print("\n".join(x for x in lines if x))
    print("결과: %s/preview.png" % out_dir)
    return 0


def reprocess(args):
    """받아 둔 그림(raw_*.png)으로 자르기만 다시 한다. 모델을 안 부르니 값이 안 든다."""
    d = args.reprocess
    layout = 1                                      # meta.json 이 없으면 처음 판(걷기 네 줄)이다
    try:
        with io.open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
            layout = int(json.load(f).get("layout") or 1)
    except (IOError, OSError, ValueError):
        pass
    photo = None
    if os.path.exists(os.path.join(d, "photo.jpg")):
        photo = Image.open(os.path.join(d, "photo.jpg")).convert("RGB")
    sprites, raws, notes, infos = {}, [], [], {}
    for path in sorted(glob.glob(os.path.join(d, "raw_*.png"))):
        kind = os.path.basename(path)[4:-4]
        raw = Image.open(path).convert("RGB")
        raws.append(("모델이 준 그림 (%s)" % kind, raw))
        got, n, info = cut_sprites(raw, kind, layout)
        sprites.update(got)
        notes.extend(n)
        infos.update(info)
    if not raws:
        raise SystemExit("%s 에 raw_*.png 가 없습니다." % d)
    lines = ["받아 둔 그림으로 다시 자름 (모델을 부르지 않음)", info_line(infos)] + ["⚠ " + n for n in notes]
    save_all(d, photo, raws, sprites, [x for x in lines if x])
    print("\n".join(x for x in lines if x))
    print("결과: %s/preview.png" % d)
    return 0


def fake_output(kind, pitch=5.0, shift=(0, 0)):
    """모델이 준 그림 흉내 (자체 검사용). (그림, 심어 둔 원래 도트들) 을 돌려준다.

    진짜처럼 만든다: 작은 판에 도트를 1칸 = 1점으로 놓고 → 한 칸이 pitch px 가 되게 키우고
    → 뭉개고 → 바탕색을 살짝 틀고 → JPEG 로 한 번 굽는다. 그러면 자르는 쪽이 **심어 둔
    도트를 그대로 되찾는지** 볼 수 있다. pitch 가 BLOCK 과 달라도(모델이 격자를 안 지켜도)
    되찾아야 한다.
    """
    back, front, walk = ref_figures()
    n = int(CANVAS / pitch)
    k = n / float(VIRT)
    small = Image.new("RGB", (n, n), BG)
    planted = {}
    lay = VBOX[kind]

    def put(fig, box):
        x0, x1, y1 = int(box[0] * k), int(box[2] * k), int(box[3] * k)
        small.paste(fig, (x0 + (x1 - x0 - fig.size[0]) // 2 + shift[0], y1 - fig.size[1] + shift[1]), fig)
    for name, fig in (("back", back), ("front", front)):
        if name in lay:
            fig = stretch(fig, 88, lay[name][2] - lay[name][0] - 4)     # 진짜처럼 걷기 도트보다 훨씬 크게
            put(fig, lay[name])
            planted[name] = fig
    if "walk" in lay:
        rows = TEMPLATE_ROWS[LAYOUT_NOW]
        cells = walk_cells(kind, len(rows))
        for r, name in enumerate(rows):
            for c in range(3):
                put(walk[name][c], cells[r][c])
                planted[(name, c)] = walk[name][c]
    side = int(round(n * pitch))
    big = Image.new("RGB", (CANVAS, CANVAS), BG)
    big.paste(small.resize((side, side), Image.NEAREST), (0, 0))
    keyed = ImageChops.difference(big, Image.new("RGB", big.size, BG)).convert("L").point(
        lambda v: 255 if v > 30 else 0)
    base = Image.new("RGB", big.size, (246, 8, 238))        # 모델은 바탕색을 정확히 안 지킨다
    base.paste(big, (0, 0), keyed)
    soft = base.filter(ImageFilter.GaussianBlur(0.6))
    buf = io.BytesIO()
    soft.save(buf, "JPEG", quality=85)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB"), planted


def same_share(got, want):
    """되찾은 도트가 심어 둔 도트와 얼마나 같은가 (0~1). 모양(투명)과 색을 같이 본다.

    한 줄쯤 밀려 있어도 맞춰 본다 (가장자리 한 칸이 빠지면 테두리가 한 줄 달라진다).
    크기가 두 줄 넘게 다르면 다른 그림이다.
    """
    if got is None or abs(got.size[0] - want.size[0]) > 2 or abs(got.size[1] - want.size[1]) > 2:
        return 0.0
    w, h = max(got.size[0], want.size[0]) + 4, max(got.size[1], want.size[1]) + 4
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    base.paste(want.convert("RGBA"), (2, 2))
    b = base.load()
    best = 0.0
    for dx in range(0, 5):
        for dy in range(0, 5):
            cand = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            cand.paste(got.convert("RGBA"), (dx, dy))
            a = cand.load()
            same = total = 0
            for y in range(h):
                for x in range(w):
                    p, q = a[x, y], b[x, y]
                    if not p[3] and not q[3]:
                        continue
                    total += 1
                    if p[3] and q[3] and max(abs(p[i] - q[i]) for i in range(3)) <= 48:
                        same += 1
            best = max(best, same / float(total or 1))
    return best


def selftest(args):
    """키 없이 뒷부분(틀 만들기 → 자르기 → 격자대로 뽑기)을 본다."""
    out_dir = os.path.join(args.out, "selftest")
    os.makedirs(out_dir, exist_ok=True)
    ok = bad = 0

    def chk(name, cond, got=""):
        nonlocal ok, bad
        if cond:
            ok += 1
        else:
            bad += 1
        print("  %s %s %s" % ("OK  " if cond else "FAIL", name, "" if cond else got))

    global LAYOUT_NOW
    for layout, kind, pitch, shift in ((3, "combined", 5.0, (0, 0)), (3, "combined", 4.8, (2, -2)),
                                       (3, "trainer", 5.0, (2, 1)), (3, "walk", 5.3, (-2, 2)),
                                       (5, "combined", 5.0, (0, 0)), (5, "combined", 5.1, (-2, 1))):
        LAYOUT_NOW = layout
        raw, planted = fake_output(kind, pitch, shift)
        got, notes, info = cut_sprites(raw, kind)
        tag = "%s 걷기 %d줄 (한 칸 %.1fpx%s)" % (kind, len(TEMPLATE_ROWS[layout]), pitch,
                                            "" if shift == (0, 0) else ", 밀림")
        chk("%s: 못 찾은 것·줄인 것 없음" % tag, not notes, notes)
        chk("%s: 도트 한 칸의 크기를 잰다" % tag, info.get("pitch") and abs(info["pitch"] - pitch) <= 0.12,
            info.get("pitch"))
        for name in ("back", "front"):
            if name not in planted:
                continue
            im = got.get(name)
            box = im.getbbox() if im else None
            share = same_share(im.crop(box) if box else None, planted[name])
            chk("%s: %s - 심어 둔 도트를 그대로 되찾는다 (%d%%)" % (tag, name, share * 100), share >= 0.9,
                (box, planted[name].size))
            chk("%s: %s - %dx%d 칸, 바닥에 붙는다" % (tag, name, TRAINER, TRAINER), im is not None
                and im.size == (TRAINER, TRAINER) and box[3] >= TRAINER - 1, box)
        if "walk" in got:
            sheet = got["walk"]
            cells = dict(((r, c), sheet.crop((c * CELL_W, r * CELL_H, (c + 1) * CELL_W, (r + 1) * CELL_H)))
                         for r in range(4) for c in range(3))
            chk("%s: 걷기 %dx%d (한 칸 %dx%d), 12칸이 다 차 있다" % (tag, CELL_W * 3, CELL_H * 4, CELL_W, CELL_H),
                sheet.size == (CELL_W * 3, CELL_H * 4) and all(v.getbbox() for v in cells.values()), sheet.size)
            shares = []
            for r, name in enumerate(SHEET_ROWS):
                for c in range(3):
                    want = planted[("left", c)] if name == "right" else planted[(name, c)]
                    if name == "right":
                        want = ImageOps.mirror(want)
                    cell = cells[(r, c)]
                    shares.append(same_share(cell.crop(cell.getbbox()), want))
            chk("%s: 걷기 - 심어 둔 도트를 되찾는다 (가장 낮은 칸 %d%%)" % (tag, min(shares) * 100),
                min(shares) >= 0.85, ["%.2f" % s for s in shares])
            def tight(im):
                return im.crop(im.getbbox())
            chk("%s: 오른쪽 줄은 왼쪽 줄을 뒤집은 것" % tag, all(
                ImageOps.mirror(tight(cells[(1, c)])).tobytes() == tight(cells[(2, c)]).tobytes()
                for c in range(3)))
            chk("%s: 발이 칸 바닥에 닿는다" % tag, all(v.getbbox()[3] == CELL_H for v in cells.values()))
            cols = sheet.getcolors(4096) or []
            solid = [c for _n, c in cols if c[3] == 255]
            chk("%s: 걷기 칸들이 같은 색표를 쓴다 (%d색), 반투명 없음" % (tag, len(solid)),
                0 < len(solid) <= 40 and not [c for _n, c in cols if 0 < c[3] < 255], len(solid))
        if kind == "combined" and shift == (0, 0) and layout == 5:
            raw.save(os.path.join(out_dir, "raw_combined.png"))
            save_all(out_dir, None, [("모델이 준 그림 흉내", raw)], got,
                     ["자체 검사: 제미나이를 부르지 않고 흉내 낸 그림으로 뒷부분만 돌린 것", info_line(info)])
    for layout, kind in ((3, "combined"), (3, "trainer"), (3, "walk"), (5, "combined"), (5, "walk")):
        LAYOUT_NOW = layout
        tpl = build_template(kind)
        tpl.save(os.path.join(out_dir, "template_%s_%d.png" % (kind, len(TEMPLATE_ROWS[layout]))))
        kind_tag = kind
        inside = tpl.crop((EDGE, EDGE, EDGE + VIRT * BLOCK, EDGE + VIRT * BLOCK))
        again = inside.resize((VIRT, VIRT), Image.NEAREST).resize(inside.size, Image.NEAREST)
        chk("틀 %s: 전체가 한 칸 %dpx 인 도트다 (칸 안에 색이 하나뿐)" % (kind, BLOCK),
            ImageChops.difference(inside, again).getbbox() is None)
        got, notes, info = cut_sprites(tpl, kind)
        chk("틀 %s: 그대로 잘라도 크기가 맞는다 (한 칸 %.2fpx, 줄인 것 없음)" % (kind, info.get("pitch") or 0),
            not notes and info.get("pitch") and abs(info["pitch"] - BLOCK) <= 0.1, (notes, info.get("pitch")))
        mask, _bg = figure_mask(tpl)
        if kind != "walk":
            two = [find_one(mask, region(tpl.size, PARTS[kind][n])) for n in ("back", "front")]
            chk("틀 %s: 뒷모습·앞모습이 제자리에 있다" % kind, all(two) and two[0] != two[1], two)
        if kind != "trainer":
            grid = find_grid(mask, region(tpl.size, PARTS[kind]["walk"]), rows=len(TEMPLATE_ROWS[LAYOUT_NOW]))
            hs = [b[3] - b[1] for line in grid for b in line if b]
            n = 3 * len(TEMPLATE_ROWS[LAYOUT_NOW])
            chk("틀 %s: 걷기 %d칸의 키가 같다" % (kind, n), len(hs) == n and max(hs) - min(hs) <= 2, hs)
    fake = {"id": "x", "status": "completed", "steps": [{"type": "thought", "signature": "S" * 5000}, {
        "type": "model_output", "content": [{"type": "image", "mime_type": "image/jpeg", "data": "A" * 2000}]}],
        "usage": {"total_input_tokens": 2726, "total_output_tokens": 1704,
                  "output_tokens_by_modality": [{"modality": "image", "tokens": 1120}]}}
    chk("응답에서 그림을 찾는다 (interactions 모양)", find_images(fake, []) == ["A" * 2000])
    old = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": "B" * 2000}}]}}],
           "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20}}
    chk("  옛 모양(generateContent)도 받는다", find_images(old, []) == ["B" * 2000]
        and usage_of(old) == (10, 20, None))
    c, exact = cost_of("lite", usage_of(fake))
    want = 2726 / 1e6 * 0.25 + 1120 / 1e6 * 30 + 584 / 1e6 * 1.5
    chk("값 계산: 그림 토큰은 그림 값, 나머지는 글 값 ($%.4f)" % want, exact and abs(c - want) < 1e-9, c)
    chk("  토큰을 못 받으면 정가로", cost_of("flash", (None, None, None)) == (0.067, False))
    chk("기록에는 긴 base64 를 안 남긴다", "A" * 50 not in json.dumps(trim(fake)))
    keep = dict((k, os.environ.pop(k, None)) for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"))
    try:
        os.environ["GEMINI_API_KEY"] = " abc123 "
        chk("키: 환경변수에서 읽는다 (앞뒤 빈칸은 뗀다)", find_key() == "abc123")
    finally:
        for k, v in keep.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    print("\n%d개 통과, %d개 실패 · 그림: %s/preview.png" % (ok, bad, out_dir))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description="사진 → 포스크탑 트레이너·걷기 도트 (시제품)")
    ap.add_argument("photo", nargs="?", help="사람이 나온 사진 (jpg/png)")
    ap.add_argument("--mode", choices=("combined", "split"), default="combined",
                    help="combined=한 장에 전부(가장 쌈), split=트레이너·걷기를 따로(두 배)")
    ap.add_argument("--model", choices=sorted(MODELS), default="flash",
                    help="flash=기본(격자·크기를 지킨다, 약 98원), lite=가장 쌈(약 49원), pro=가장 비쌈(약 200원)")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--tag", default="", help="결과 폴더 이름 끝에 붙일 말 (여러 번 돌려 비교할 때)")
    ap.add_argument("--reprocess", metavar="폴더", help="받아 둔 그림으로 자르기만 다시 (모델을 안 부른다)")
    ap.add_argument("--selftest", action="store_true", help="키 없이 뒷부분만 시험")
    args = ap.parse_args()
    if args.selftest:
        return selftest(args)
    if args.reprocess:
        return reprocess(args)
    if not args.photo:
        ap.error("사진 파일을 주세요 (또는 --selftest / --reprocess 폴더)")
    return generate(args)


if __name__ == "__main__":
    sys.exit(main())
