# -*- coding: utf-8 -*-
"""꾸미기 자리 (2.1.0 - deco_place 의 눈 찾기 · 자리 고르기, 새 장식 · 효과).

실제 걷는 도트(SpriteCollab)는 저장소에 없어서, 눈 · 흰 빛 · 색깔 눈동자를 그린 작은 가짜 도트로 규칙만 본다.
표본 69종 x 앞 · 옆 · 뒤로 픽셀을 센 것은 deco_place 머리말에 적었다 (그 셈의 기준을 여기 그대로 쓴다).

    python test_deco_place.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket_decoplace_"))

from PIL import Image                                           # noqa: E402

from common import deco as C                                    # noqa: E402
from poketdesktop import deco_art as ART                        # noqa: E402
from poketdesktop import deco_fx as FX                          # noqa: E402
from poketdesktop import deco_place as P                        # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


BODY, EDGE, CHEEK = (250, 210, 60, 255), (20, 20, 24, 255), (230, 80, 70, 255)
WHITE, PUPIL = (255, 255, 255, 255), (16, 16, 20, 255)


def mon(face="down", eye=None, eye_y=13):
    """32x32 칸에 둥근 머리(위 5~입 20) + 몸. eye = (눈동자 색, 빛 색) - None 이면 짙은 눈동자 + 흰 빛."""
    pupil, light = eye or (PUPIL, WHITE)
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    px = im.load()
    for y in range(4, 30):
        half = 9 if y < 22 else 7
        for x in range(16 - half, 16 + half):
            px[x, y] = BODY
    for y in range(4, 30):                      # 테두리
        for x in range(32):
            if px[x, y][3] and any(not (0 <= x + dx < 32 and 0 <= y + dy < 32) or px[x + dx, y + dy][3] == 0
                                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                px[x, y] = EDGE
    if face == "up":
        return im
    xs = (12, 19) if face == "down" else ((21,) if face == "right" else (10,))
    for ex in xs:
        for dy in (0, 1):
            px[ex, eye_y + dy] = pupil
        px[ex + 1, eye_y] = light               # 눈빛
    px[8, eye_y + 3] = CHEEK                     # 볼은 눈이 아니다
    px[23, eye_y + 3] = CHEEK
    for x in (15, 16):                           # 입
        px[x, 20] = EDGE
    return im


def spot(im, face, head=(16, 20)):
    big = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    return P.Spot(big, head, (16, 18), face)


def t_목록():
    new = ("flower_crown", "star_pin", "shades", "heart_shades", "bowtie", "fx_bubbles", "fx_notes", "fx_snow")
    chk("새 꾸미기 8개가 목록에", all(k in C.DECOS for k in new))
    chk("얼굴 칸이 새로", "face" in C.SLOTS and C.slot_of("shades") == "face")
    chk("슬롯 후보에 왕관 · 순위 효과 없음", not set(C.RANK_ONLY) & set(C.slot_pool()))
    chk("슬롯 후보에 새 꾸미기 전부", all(k in C.slot_pool() for k in new))
    chk("parts: 얼굴은 장식 쪽", C.parts({"face": "shades", "trail": "fx_snow"}) == (("shades",), ("fx_snow",)))
    chk("모든 꾸미기에 칸 그림이 있다", all(ART.item_icon(k, 40) is not None for k in C.DECOS))
    chk("새 장식은 그릴 장식으로 친다", P.accessories(new) == new[:5])


def t_눈_찾기():
    im = mon("down")
    sp = spot(im, "down")
    eyes = P.find_eyes(im, sp)
    chk("정면: 눈 둘", len(eyes) == 2, len(eyes))
    xs = sorted(round(e[0]) for e in eyes)
    chk("정면: 왼눈 · 오른눈 자리 (볼을 잡지 않는다)", xs[0] in (12, 13) and xs[1] in (19, 20), xs)
    im = mon("right")
    eyes = P.find_eyes(im, spot(im, "right"))
    chk("옆(오른쪽): 보는 쪽 눈 하나", len(eyes) == 1 and eyes[0][0] >= 20, eyes[:1] and eyes[0][:2])
    im = mon("up")
    chk("뒤: 눈 없음", P.find_eyes(im, spot(im, "up")) == [])
    red = ((210, 30, 50, 255), (210, 30, 50, 255))   # 블래키처럼 빨간 눈동자, 흰 빛 없음
    im = mon("down", eye=red)
    eyes = P.find_eyes(im, spot(im, "down"))
    chk("색깔 눈동자도 드문 색 쌍으로 찾는다", len(eyes) == 2 and sorted(round(e[0]) for e in eyes)[0] in (12, 13),
        [e[:2] for e in eyes])
    plain = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for y in range(4, 30):
        for x in range(8, 24):
            plain.putpixel((x, y), BODY)
    sp = spot(plain, "down")
    pts, found = P.eye_points(plain, sp)
    want_y = int(round(sp.top + (sp.hy - sp.top) * P.FRONT_EYE))
    chk("눈이 안 보이면 예상 높이(64%)에 둘", not found and len(pts) == 2 and pts[0][1] == want_y, (pts, want_y))


def _draw(face, items, eye=None):
    im = mon(face, eye=eye)
    frames, _crowns = P.plan([im], [(16, 20)], [(16, 18)], face, items)
    big = im.resize((64, 64), Image.NEAREST)
    sp = spot(im, face)
    eyes, _f = P.eye_points(im, sp)
    return big, frames[0], eyes, sp


def t_선글라스():
    big, draws, eyes, _sp = _draw("down", ("shades",))
    chk("정면 선글라스 한 장", len(draws) == 1)
    im, x, y = draws[0]
    chk("렌즈가 두 눈을 다 덮는다", all(P._covers(im, (x, y), [e], r=0) for e in eyes), (x, y, eyes))
    chk("렌즈 80% 이상이 도트 위 (허공에 안 뜸)", P._over(big, im, (x, y)) >= 0.8, P._over(big, im, (x, y)))
    big, draws, eyes, _sp = _draw("right", ("heart_shades",))
    im, x, y = draws[0]
    chk("옆모습 하트 선글라스가 보는 쪽 눈을 덮는다", P._covers(im, (x, y), eyes, r=0), (x, y, eyes))
    _b, draws, _e, _s = _draw("up", ("shades",))
    chk("뒤를 보면 선글라스를 안 그린다", draws == [])
    im, cx, ey = ART.glasses("shades", 14)
    chk("눈 간격에 맞춰 렌즈를 잇는다 (두 렌즈 가운데 사이 14)", im.width == 14 + ART.lens("shades").width and cx == 4)
    im2, _cx, _ey = ART.glasses("shades", 3)
    chk("눈이 붙어 있어도 렌즈가 안 겹친다", im2.width >= 2 * ART.lens("shades").width + 1)


def t_관_핀_넥타이():
    for face in ("down", "right"):
        big, draws, eyes, _sp = _draw(face, ("flower_crown",))
        im, x, y = draws[0]
        rows = set(range(im.height - 3, im.height))
        chk("%s 화관: 아래 세 줄이 머리에 걸친다" % face, P._over(big, im, (x, y), rows) >= 0.35)
        chk("%s 화관: 눈을 안 가린다" % face, not P._covers(im, (x, y), eyes))
        big, draws, eyes, _sp = _draw(face, ("crown_gold",))
        im, x, y = draws[0]
        chk("%s 금관도 눈을 안 가린다 (2.1.0 부터 같은 규칙)" % face, not P._covers(im, (x, y), eyes))
        big, draws, eyes, _sp = _draw(face, ("star_pin",))
        im, x, y = draws[0]
        chk("%s 별핀: 절반 이상 머리 위 · 눈을 안 가린다" % face,
            P._over(big, im, (x, y)) >= 0.5 and not P._covers(im, (x, y), eyes))
        big, draws, eyes, sp = _draw(face, ("bowtie",))
        im, x, y = draws[0]
        chk("%s 나비넥타이: 80%% 이상 몸 위 · 눈 아래 · 입 줄 아래" % face,
            P._over(big, im, (x, y)) >= 0.8 and not P._covers(im, (x, y), eyes, r=1) and y + im.height // 2 > sp.hy,
            (x, y, P._over(big, im, (x, y))))
    _b, draws, _e, _s = _draw("down", ("flower_crown", "star_pin", "shades", "bowtie"))
    chk("다 같이 쓰면 넷 다 그린다", len(draws) == 4)


def t_효과():
    for kind, kw in (("bubble", {"size": 9}), ("note", {"rot": 2, "two": True, "dir": -1}), ("snow", {})):
        p = FX.Particle(kind, 100, 100, 1000, **kw)
        p.age = 500
        got = FX.draws(p, 1)
        chk("효과 %s 가 그려진다 (그림 · 자리 · 보이는 정도)" % kind, got is not None and got[3] > 0, got and got[1:])
    p = FX.Particle("bubble", 100, 100, 1000, size=5)
    p.age = 600
    chk("비눗방울은 떠오른다", FX.draws(p, 1)[2] < 100)
    p = FX.Particle("snow", 100, 100, 1000)
    p.age = 600
    chk("눈송이는 내린다", FX.draws(p, 1)[2] > 100 - ART.snow().height)
    p = FX.Particle("note", 100, 100, 1000, rot=0, dir=-1)
    p.age = 900
    chk("음표는 뒤로 흘러간다", FX.draws(p, 1)[1] < 100)


def main():
    for name, fn in sorted(((k, v) for k, v in globals().items() if k.startswith("t_")), key=lambda t: t[0]):
        print("-- %s" % name[2:])
        fn()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
