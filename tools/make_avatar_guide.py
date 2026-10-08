# -*- coding: utf-8 -*-
"""직접 그린 캐릭터 도트 안내서(docs/avatar/)에 쓰는 그림을 만든다.

    python tools/make_avatar_guide.py

만드는 것 (전부 common/avatar_art 가 그린 우리 캐릭터다 - 남의 그림은 없다):

    template.png          96x128 견본. 이 위에 덧그려서 내 캐릭터를 만들면 된다
    example-1~3.png       96x128 견본 셋 (꾸민 캐릭터)
    template-guide.png    견본을 키워서 칸·줄·발 닿는 줄을 적어 넣은 설명 그림
    preview.png           마이페이지에 어떻게 보이는지

규격이 바뀌면(common/avatar_sheet.py) 다시 돌린다. 글자를 그려 넣어야 해서 Pillow 가 필요하다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw, ImageFont                  # noqa: E402

from common import avatar_art as A                           # noqa: E402
from common import avatar_sheet as S                         # noqa: E402

OUT = os.path.join(ROOT, "docs", "avatar")
BG, PANEL, LINE, GOLD, FG, DIM, RED = ((13, 17, 26), (22, 27, 40), (58, 68, 94), (255, 212, 71),
                                       (236, 240, 250), (150, 160, 184), (255, 120, 120))
EXAMPLES = (
    dict(A.DEFAULT, hair="pony", hairColor="orange", hat="bucket", hatColor="beige", top="hoodie", topColor="yellow",
         bottom="shorts", bottomColor="navy", bag="satchel", bagColor="brown"),
    dict(A.DEFAULT, skin="tan", hair="spiky", hairColor="black", glasses="square", top="jacket", topColor="forest",
         bottom="pants", bottomColor="black", shoeColor="red", bag="backpack", bagColor="gray"),
    dict(A.DEFAULT, skin="light", hair="long", hairColor="pink", hat="beret", hatColor="red", top="shirt",
         topColor="white", bottom="skirt", bottomColor="navy", shoes="boots", shoeColor="black"),
)


def font(size, bold=False):
    for path in ("/System/Library/Fonts/AppleSDGothicNeo.ttc", "C:/Windows/Fonts/malgunbd.ttf" if bold else
                 "C:/Windows/Fonts/malgun.ttf", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"):
        try:
            return ImageFont.truetype(path, size, index=(6 if bold else 0)) if path.endswith(".ttc") \
                else ImageFont.truetype(path, size)
        except Exception:                                   # noqa: BLE001
            continue
    return ImageFont.load_default()


def pil(img):
    im = Image.new("RGBA", (len(img[0]), len(img)))
    im.putdata([tuple(px) for row in img for px in row])
    return im


def save_sheet(name, sheet):
    S.check(sheet)                                           # 견본이 규격을 어기면 여기서 멈춘다
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(A.png(sheet))


def guide(sheet):
    """견본을 6배로 키우고 칸·줄 이름, 발이 닿는 줄을 적어 넣는다."""
    k, left, top = 6, 132, 64
    cw = A.CELL * k
    w, h = left + cw * 3 + 24, top + cw * 4 + 56
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    f, fb, fs = font(15), font(16, True), font(12)
    for c, name in enumerate(("왼발을 내딛음", "서 있음", "오른발을 내딛음")):
        tw = d.textlength(name, font=fb)
        d.text((left + c * cw + (cw - tw) / 2, 14), name, font=fb, fill=FG)
        d.text((left + c * cw + (cw - d.textlength("칸 %d" % (c + 1), font=fs)) / 2, 38), "칸 %d" % (c + 1), font=fs, fill=DIM)
    for r, (name, sub) in enumerate((("아래를 봄", "앞모습"), ("왼쪽을 봄", ""), ("오른쪽을 봄", "왼쪽을 뒤집어도 됨"),
                                     ("위를 봄", "뒷모습"))):
        y = top + r * cw
        d.text((12, y + cw / 2 - 22), "줄 %d" % (r + 1), font=fs, fill=DIM)
        d.text((12, y + cw / 2 - 6), name, font=fb, fill=FG)
        if sub:
            d.text((12, y + cw / 2 + 16), sub, font=fs, fill=GOLD if r in (0, 3) else DIM)
    for r in range(4):
        for c in range(3):
            x, y = left + c * cw, top + r * cw
            d.rectangle((x, y, x + cw - 1, y + cw - 1), fill=PANEL)
            for i in range(0, A.CELL):                       # 점 하나하나의 눈금 (옅게)
                if i % 4 == 0:
                    d.line((x + i * k, y, x + i * k, y + cw - 1), fill=(28, 34, 50))
                    d.line((x, y + i * k, x + cw - 1, y + i * k), fill=(28, 34, 50))
    big = pil(A.scale(sheet, k))
    im.paste(big, (left, top), big)
    d = ImageDraw.Draw(im)
    for r in range(4):
        for c in range(3):
            x, y = left + c * cw, top + r * cw
            d.rectangle((x, y, x + cw - 1, y + cw - 1), outline=LINE, width=2)
            gy = y + 31 * k                                  # 발바닥이 닿는 줄(아래에서 둘째 줄)의 아래 금
            d.line((x + 4, gy, x + cw - 5, gy), fill=RED, width=1)
    d.rectangle((left, top, left + cw - 1, top + cw - 1), outline=LINE, width=2)
    x, y = left + cw, top                                    # 닉네임 옆에 보이는 칸
    d.rectangle((x, y, x + cw - 1, y + cw - 1), outline=GOLD, width=3)
    d.text((left, top + cw * 4 + 12), "금색 테두리 = 마이페이지의 닉네임 옆에 보이는 칸   ·   빨간 줄 = 발바닥이 닿는 자리 (칸의 아래에서 둘째 줄)",
           font=fs, fill=DIM)
    d.text((left, top + cw * 4 + 32), "한 칸 32 x 32 점 · 전체 96 x 128 점 · 배경은 투명 (이 그림은 6배로 키운 것)", font=fs, fill=DIM)
    im.save(os.path.join(OUT, "template-guide.png"))
    return im.size


def preview(sheets):
    """마이페이지에서 어떻게 보이는지 (닉네임 옆 96x96)."""
    f, fb, fs = font(13), font(18, True), font(12)
    w, h = 720, 132 * len(sheets) + 16
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    names = ("내가그린도트", "길드원", "트레이너")
    for i, sheet in enumerate(sheets):
        y = 16 + i * 132
        d.rectangle((16, y, w - 16, y + 116), fill=PANEL, outline=(120, 96, 30))
        d.rectangle((30, y + 9, 30 + 97, y + 9 + 97), fill=(16, 20, 30), outline=LINE)
        face = pil(S.front(sheet))
        im.paste(face, (31, y + 10), face)
        d = ImageDraw.Draw(im)
        d.text((144, y + 16), names[i % len(names)], font=fb, fill=GOLD)
        d.text((144, y + 46), "함께한 지 25일째  ·  2026.09.08 가입", font=fs, fill=DIM)
        x = 430
        for fr in ("a", "stand", "b"):                       # 걷는 세 칸 (앞)
            cell = pil(A.scale(S.cell_of(sheet, "down", fr), 2))
            im.paste(cell, (x, y + 26), cell)
            x += 70
        d = ImageDraw.Draw(im)
        d.text((430, y + 94), "걷는 세 칸 (나중에 직접 걸어다닐 때 쓰입니다)", font=fs, fill=DIM)
    im.save(os.path.join(OUT, "preview.png"))
    return im.size


def main():
    os.makedirs(OUT, exist_ok=True)
    base = A.walk_sheet(A.DEFAULT)
    save_sheet("template.png", base)
    sheets = []
    for i, spec in enumerate(EXAMPLES):
        sheet = A.walk_sheet(spec)
        save_sheet("example-%d.png" % (i + 1), sheet)
        sheets.append(sheet)
    print("template-guide.png", guide(base))
    print("preview.png", preview(sheets))
    for name in sorted(os.listdir(OUT)):
        if name.endswith(".png"):
            print("  %-22s %6d bytes" % (name, os.path.getsize(os.path.join(OUT, name))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
