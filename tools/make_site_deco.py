# -*- coding: utf-8 -*-
"""사이트 안내서의 '꾸미기' 장(docs/guide/#deco)에 쓰는 그림과 자리를 만든다.

    python tools/make_site_deco.py                  docs/sprites/deco.png + docs/assets/deco-data.js
    python tools/make_site_deco.py --looks <폴더>   + docs/images/deco-<번호>-<장식>.png (포켓몬이 쓴 모습)

**그림도 자리도 게임 것 그대로다.** 장식 · 효과 그림은 client/poketdesktop/deco_art.py, 자리는 게임이 걷는 도트에
얹는 규칙(deco_place.plan)으로 잡는다. 장식 그림을 고치면 이것을 다시 돌린다.

입혀 보기 무대(docs/assets/deco.js)에서 걷는 것은 사이트의 직접 그린 생물(make_site_sprites)이다 - 공개 페이지에서
움직이는 것은 남의 캐릭터가 아니다. 포켓몬이 쓴 모습은 정지 그림(--looks)으로만 싣는다. <폴더> 는 SpriteCollab 의
`sprite/<번호>/` 들을 담은 곳이다 (AnimData.xml · Walk-Anim.png · Walk-Offsets.png).

deco.png 는 장식 칸 그대로(도트보다 두 배 촘촘한 칸)다. 무대는 생물을 4배, 장식을 2배로 그린다 - 게임과 같은 2:1 이다.
"""
import argparse
import json
import os
import re
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "client"))
sys.path.insert(0, ROOT)

import make_site_sprites as M                                   # noqa: E402
from poketdesktop import deco_art as A                          # noqa: E402
from poketdesktop import deco_place as P                        # noqa: E402

SHEET = os.path.join(ROOT, "docs", "sprites", "deco.png")
DATA = os.path.join(ROOT, "docs", "assets", "deco-data.js")
IMAGES = os.path.join(ROOT, "docs", "images")

DEMO = ("pebble", "drop", "cloud", "bud", "snow", "mush", "gold")   # 무대에 서는 생물 (차례대로 바꿔 입는다)
DIRS = ("down", "right", "up", "left")
ICON = 28                                                       # 고르는 단추의 그림 칸
RING = 18                                                       # 발밑 빛 고리 폭 (촘촘한 칸)
# 자리를 잡는 묶음: 머리 장식은 왕관과 같이 쓰면 조금 내려앉는다 (deco_place.plan)
SETS = {"crown": ("crown_gold",), "bow": ("bow",), "bowC": ("crown_gold", "bow"),
        "flower": ("flower",), "flowerC": ("crown_gold", "flower"), "pearls": ("pearls",)}
KEYS = ("crown_gold", "crown_silver", "crown_bronze", "bow", "flower", "pearls", "fx_stars_gold",
        "fx_stars_silver", "fx_stars_bronze", "fx_paw", "fx_petals", "fx_hearts", "fx_glow", "pick_join")
# 포켓몬이 쓴 모습 (정지 그림): (번호, 장식들)
LOOKS = (("0025", ("crown_gold",)), ("0133", ("crown_silver",)), ("0004", ("crown_bronze",)),
         ("0025", ("bow",)), ("0133", ("flower",)), ("0004", ("pearls",)),
         # 2.1.0 (길드 슬롯)
         ("0025", ("shades",)), ("0133", ("heart_shades",)), ("0004", ("flower_crown",)),
         ("0007", ("star_pin",)), ("0025", ("bowtie",)), ("0007", ("shades",)))


# ---------------------------------------------------------------- 그림 시트
def art():
    """[(이름, RGBA)] - deco.js 가 이름으로 찾는다."""
    out = [("crown_" + m, A.crown(m)) for m in ("gold", "silver", "bronze")]
    out += [("glint%d" % i, A.glint(i)) for i in range(len(A.GLINT))]
    out += [("bow", A.bow()), ("flower", A.flower_pin()), ("pearl", A.pearl()), ("heart", A.heart()),
            ("paw", A.paw()), ("heartfx", A.heart_fx())]
    out += [("star%d_%s" % (s, t), A.star(s, t)) for t in ("gold", "silver", "bronze") for s in (1, 3, 5, 7)]
    out += [("petal%d" % i, A.petal(i)) for i in range(4)]
    out += [("ring%d" % i, A.glow_ring(RING, i)) for i in range(4)]
    out += [("icon_" + k, A.item_icon(k, ICON)) for k in KEYS]
    return out


def pack(items, width=160):
    """선반 쌓기. -> (시트, {이름: [x, y, w, h]})"""
    x = y = shelf = 0
    rects = {}
    for name, im in items:
        if x + im.width > width:
            x, y, shelf = 0, y + shelf + 1, 0
        rects[name] = [x, y, im.width, im.height]
        x += im.width + 1
        shelf = max(shelf, im.height)
    sheet = Image.new("RGBA", (width, y + shelf), (0, 0, 0, 0))
    for name, im in items:
        r = rects[name]
        sheet.alpha_composite(im, (r[0], r[1]))
    return sheet, rects


# ---------------------------------------------------------------- 생물에 얹는 자리
def kind_of(name):
    for i, k in enumerate(M.KINDS):
        if k[0] == name:
            return i, k
    raise KeyError(name)


def spots(kind):
    """한 생물의 방향마다 {묶음: 프레임마다 자리}. 좌표는 16x16 칸을 두 배로 키운 촘촘한 칸 (칸 밖은 음수도 된다).

    머리 점(게임에서는 입 · 턱)은 눈 바로 위 줄 가운데로 둔다 - 몸이 곧 머리인 생물이라 그래야 목걸이가 발끝까지
    늘어지지 않는다. 왕관 · 머리 장식은 머리 점에서 위로 올라가 머리 꼭대기를 찾으므로 이 점의 높이와 무관하다."""
    hy = M.EYE_Y.get(kind[0], 9) - 1
    out = {}
    for d in DIRS:
        cells = [M.frame(kind, d, f) for f in range(M.FRAMES)]
        heads = [(8, hy)] * len(cells)
        got = {}
        for name, items in SETS.items():
            frames, crowns = P.plan(cells, heads, [(8, 10)] * len(cells), d, items)
            if name == "pearls":
                if not frames[0]:
                    continue                                              # 등을 보이면 목걸이를 안 그린다
                got["pearls"] = [[[x, y] for _im, x, y in fr[:-1]] for fr in frames]
                got["heart"] = [[fr[-1][1], fr[-1][2]] for fr in frames]
            else:
                got[name] = [[fr[-1][1], fr[-1][2]] for fr in frames]      # 맨 뒤 = 그 묶음의 마지막 장식
            if name == "crown":
                got["glint"] = [[c[0] + c[2] - 5, c[1] - 3] for c in crowns]
        got["flip"] = d in P.FACE_RIGHT
        out[d] = got
    return out, list(M.frame(kind, "down", 0).getbbox())


def data(rects):
    kinds = []
    for name in DEMO:
        i, kind = kind_of(name)
        at, box = spots(kind)
        kinds.append({"name": name, "row": i * len(DIRS), "box": box, "at": at})
    return {"cell": M.CELL, "frames": M.FRAMES, "dirs": list(DIRS), "sprites": rects, "kinds": kinds}


# ---------------------------------------------------------------- 포켓몬이 쓴 모습 (정지 그림)
def looks(root, scale=4):
    """SpriteCollab 걷기 시트의 앞모습 첫 프레임에 게임 규칙대로 얹는다. 왕관은 반짝이는 순간으로."""
    made = []
    for pid, items in LOOKS:
        base = os.path.join(root, pid)
        xml = open(os.path.join(base, "AnimData.xml"), encoding="utf-8").read()
        blk = re.search(r"<Name>Walk</Name>.*?<FrameWidth>(\d+)</FrameWidth>\s*<FrameHeight>(\d+)</FrameHeight>",
                        xml, re.S)
        fw, fh = int(blk.group(1)), int(blk.group(2))
        sheet = Image.open(os.path.join(base, "Walk-Anim.png")).convert("RGBA")
        n = sheet.width // fw
        cuts = [sheet.crop((f * fw, 0, f * fw + fw, fh)) for f in range(n)]      # 0행 = 앞모습
        from server.app import walkpts
        pts = walkpts.points(open(os.path.join(base, "Walk-Offsets.png"), "rb").read(), fw, fh)
        big = [c.resize((fw * scale, fh * scale), Image.NEAREST) for c in cuts]
        new, pad, glints, k = P.decorate({"down": big}, {"down": cuts}, {"down": "down"},
                                         {"down": (pts["head"][0], pts["center"][0])}, (0, 0), scale, items)
        im = new["down"][0]
        g = glints.get("down", [None])[0]
        if g:
            im.alpha_composite(A.scaled(A.glint(2), k), g)
        im = im.crop(im.getbbox())
        out = Image.new("RGBA", (im.width + 8, im.height + 8), (0, 0, 0, 0))
        out.alpha_composite(im, (4, 4))
        path = os.path.join(IMAGES, "deco-%s-%s.png" % (pid, items[0]))
        out.save(path, optimize=True)
        made.append((path, out.size))
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--looks", help="SpriteCollab sprite/<번호>/ 폴더들을 담은 곳")
    a = ap.parse_args()
    sheet, rects = pack(art())
    sheet.save(SHEET, optimize=True)
    body = json.dumps(data(rects), ensure_ascii=False, separators=(",", ":"))
    with open(DATA, "w", encoding="utf-8") as f:
        f.write("/* tools/make_site_deco.py 가 만든다 - 손으로 고치지 말 것. 장식 그림 시트(sprites/deco.png)의 자리와,\n"
                "   생물마다 · 방향마다 · 프레임마다 장식을 얹는 자리(게임의 deco_place 규칙). */\n")
        f.write("window.DECO_DATA = %s;\n" % body)
    print("  %s  (%dx%d)" % (os.path.relpath(SHEET), sheet.width, sheet.height))
    print("  %s  (%d 바이트)" % (os.path.relpath(DATA), len(body)))
    if a.looks:
        for path, size in looks(a.looks):
            print("  %s  (%dx%d)" % (os.path.relpath(path), size[0], size[1]))


if __name__ == "__main__":
    main()
