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


def t_메달():
    keys = ("medal_gold", "medal_silver", "medal_bronze")
    chk("올림픽 메달 셋이 목 장식으로", all(C.slot_of(k) == "neck" for k in keys)
        and [C.name(k) for k in keys] == ["금메달", "은메달", "동메달"])
    chk("메달은 랜덤 캡슐에서 안 나온다", not set(keys) & set(C.slot_pool()))
    chk("메달은 그릴 장식으로 친다", P.accessories(keys) == keys)
    for face in ("down", "right"):
        big, draws, eyes, sp = _draw(face, ("medal_gold",))
        chk("%s 메달: 끈 + 메달이 그려진다" % face, len(draws) >= 2, len(draws))
        im, x, y = draws[-1]                        # 마지막 = 메달 (끈 위에 얹는다)
        chk("%s 메달: 눈을 안 가리고 입 줄 아래 · 80%% 이상 몸 위" % face,
            not any(P._covers(i, (a, b), eyes, r=1) for i, a, b in draws) and y > sp.hy
            and P._over(big, im, (x, y)) >= 0.8, (x, y, sp.hy, P._over(big, im, (x, y))))
    _b, draws, _e, _s = _draw("up", ("medal_gold",))
    chk("뒤를 보면 메달을 안 그린다", draws == [])
    # 끈 모양: 목걸이처럼 목 양옆(턱 줄)에서 넓고 얕게 - 턱 위(얼굴)로 올라가면 빨간 입처럼 보인다 (11/08 사용자 '더 이상')
    for face in ("down", "right"):
        big, draws, eyes, sp = _draw(face, ("medal_gold",))
        st, sx, sy = draws[0]
        med, mx, my = draws[-1]
        chk("%s 끈이 턱(%d) 위 얼굴로 안 올라간다 (끈 꼭대기 %d)" % (face, sp.hy, sy), sy >= sp.hy - 1, (sy, sp.hy))
        if face == "down":
            nx, ny, half = sp.neck()
            chk("  정면 끈은 목 폭만큼 넓다 (끈 폭 >= 목 폭의 80%%, 메달보다 넓다)",
                st.width >= max(med.width + 4, int(1.6 * half)), (st.width, med.width, half))
        chk("  메달은 끈 아래 가슴에 (메달 위 > 끈 꼭대기 + 2)", my >= sy + 3, (my, sy))
    a, b = ART.medal("gold"), ART.medal("bronze")
    chk("금 · 동 메달은 빛깔이 다르다", a.size == b.size and a.tobytes() != b.tobytes())


def _edge(im):
    px = im.load()
    W, H = im.size
    for y in range(H):
        for x in range(W):
            if px[x, y][3] and any(not (0 <= x + dx < W and 0 <= y + dy < H) or px[x + dx, y + dy][3] == 0
                                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                px[x, y] = EDGE
    return im


def _eyes(im, xs, y):
    px = im.load()
    for ex in xs:
        for dy in (0, 1):
            px[ex, y + dy] = PUPIL
        px[ex + 1, y] = WHITE
    return im


def ball(dy=0, eye_y=19, eye_dx=0, r2=100, eye_xs=(12, 19)):
    """붐볼 꼴: 목이 없는 공 (반지름 10). 턱(머리 점 16,23)이 몸 아래 끝(26) 가까이. dy = 아래로 옮긴 만큼,
    eye_dx = 걸으며 표정이 바뀌어 눈만 옆으로 (몸 테두리는 그대로)."""
    im = Image.new("RGBA", (32, 40), (0, 0, 0, 0))
    px = im.load()
    for y in range(40):
        for x in range(32):
            if (x - 16) ** 2 + (y - 16 - dy) ** 2 <= r2:
                px[x, y] = BODY if y < eye_y + dy + 3 else CHEEK      # 아래 반은 빨강 (붐볼) - 경계도 얼굴과 같이
    return _eyes(_edge(im), tuple(e + eye_dx for e in eye_xs), eye_y + dy)


def giant():
    """코라이돈 꼴: 큰 도트(64칸) - 화면에서는 줄여 그린다. 몸통 타원 + 목 높이에 양팔이 넓게."""
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    px = im.load()
    for y in range(64):
        for x in range(64):
            if ((x - 32) / 13.0) ** 2 + ((y - 36) / 26.0) ** 2 <= 1 or (30 <= y <= 34 and 4 <= x <= 60):
                px[x, y] = BODY
    return _eyes(_edge(im), (27, 37), 20)


def _colors(canvas, cols):
    px = canvas.load()
    return [(x, y) for y in range(canvas.height) for x in range(canvas.width) if px[x, y] in cols]


def t_메달_자리():
    im = ball()
    frames, _c = P.plan([im], [(16, 23)], [(16, 16)], "down", ("medal_gold",))
    big = im.resize((64, 80), Image.NEAREST)
    eyes, _f = P.eye_points(im, P.Spot(big, (16, 23), (16, 16), "down"))
    med, x, y = frames[0][-1]
    chk("목 없는 공(붐볼): 메달이 몸 밖에 매달리지 않는다 (90% 이상 몸 위)", P._over(big, med, (x, y)) >= 0.9,
        (x, y, round(P._over(big, med, (x, y)), 2)))
    chk("목 없는 공: 메달 · 끈이 눈을 안 가린다", not any(P._covers(i, (a, b), eyes, r=1) for i, a, b in frames[0]))
    st, sx, sy = frames[0][0]
    chk("목 없는 공: 끈도 몸 위", P._over(big, st, (sx, sy)) >= 0.85, round(P._over(big, st, (sx, sy)), 2))
    # 가슴이 짧아 메달이 끈 끝 가까이 올라오면 끈도 좁혀 V 로 (넓은 수평 끈 = 허리띠처럼 보인다)
    im = Image.new("RGBA", (32, 40), (0, 0, 0, 0))         # 카르마돈 앞 꼴: 어깨까지 넓고 그 아래는 가는 다리
    px = im.load()
    for y in range(4, 36):
        hw = 10 if y < 25 else 2
        for x in range(16 - hw, 16 + hw):
            px[x, y] = BODY
    im = _eyes(_edge(im), (12, 19), 12)
    fr, _c = P.plan([im], [(16, 20)], [(16, 18)], "down", ("medal_gold",))
    st, sx, sy = fr[0][0]
    med, mx, my = fr[0][-1]
    rise = my - (sy + 2)
    chk("메달이 끈 끝 가까이면 끈 폭도 좁다 (반폭 <= 높이 x 2.5 · 메달 반폭 + 2)",
        (st.width - 4) / 2.0 <= max(med.width / 2.0 + 2, 2.5 * max(rise, 0)) + 1, (st.width, rise, med.width))
    # 실제 붐볼(반지름 9): 눈이 낮아 눈 아래가 메달 높이만큼밖에 없다 - 그래도 몸 밖으로 매달지 말고 눈을 피해 몸 위에
    im = ball(eye_y=20, r2=81, eye_xs=(13, 19))
    frames, _c = P.plan([im], [(16, 23)], [(16, 16)], "down", ("medal_gold",))
    big = im.resize((64, 80), Image.NEAREST)
    eyes, _f = P.eye_points(im, P.Spot(big, (16, 23), (16, 16), "down"))
    med, x, y = frames[0][-1]
    chk("눈이 낮은 공: 메달이 몸 위 (90%) · 눈은 안 가린다", P._over(big, med, (x, y)) >= 0.9
        and not any(P._covers(i, (a, b), eyes, r=0) for i, a, b in frames[0]),
        (x, y, eyes, round(P._over(big, med, (x, y)), 2)))
    # 걸으며 표정만 바뀌면(눈이 옆으로) 메달은 옆으로 튀지 않는다 - 몸 테두리가 그대로니까
    fr, _c = P.plan([ball(), ball(eye_dx=1), ball(eye_dx=-1)], [(16, 23)] * 3, [(16, 16)] * 3, "down",
                    ("medal_gold",))
    xs = [f[-1][1] - fr[0][-1][1] for f in fr]
    chk("표정이 바뀌어도 메달이 옆으로 안 튄다", xs == [0, 0, 0], xs)
    # 위치 점이 없는 도트(어림 머리 점 = 그림 위쪽 40%): 메달은 얼굴이 아니라 입 줄 아래 가슴에
    im = mon("down")
    frames, _c = P.plan([im], None, None, "down", ("medal_gold",))
    med, x, y = frames[0][-1]
    chk("위치 점이 없어도 메달은 입 줄(20) 아래 · 끈은 눈 아래", y >= 20 * 2 - 2
        and all(b > 13 * 2 + 1 for _i, _a, b in frames[0]), [(a, b) for _i, a, b in frames[0]])
    # 붐볼처럼 튀며 얼굴(눈)이 몸보다 더 움직여도 메달은 몸(테두리)을 따라간다
    fr, _c = P.plan([ball(), ball(dy=2, eye_y=21), ball(dy=3, eye_y=22)], [(16, 23)] * 3, [(16, 16)] * 3, "down",
                    ("medal_gold",))
    ys = [f[-1][2] - fr[0][-1][2] for f in fr]
    chk("튈 때 얼굴이 따로 움직여도 메달은 몸을 따라간다", ys == [0, 4, 6], ys)
    # 옆으로 걸으며 가슴 앞이 한 프레임만 뒤로 들어가도(그루돈 4번째 칸) 메달은 그 프레임에서도 몸 위
    def chest(cut):
        im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        px = im.load()
        for y in range(6, 34):
            for x in range(6, 30 - (cut if y >= 22 else 0)):
                px[x, y] = BODY
        return _eyes(_edge(im), (24,), 12)
    for cut in (4, 10):
        cells = [chest(0), chest(0), chest(cut)]
        fr, _c = P.plan(cells, [(26, 18)] * 3, [(16, 20)] * 3, "right", ("medal_gold",))
        ons = []
        for c, f in zip(cells, fr):
            big = c.resize((80, 80), Image.NEAREST)
            im, x, y = f[-1]
            ons.append(round(P._over(big, im, (x, y)), 2))
        chk("가슴 아래가 %d칸 들어간 프레임: 메달이 몸 위 (90%%)" % cut, min(ons) >= 0.9, ons)
        dy = [f[-1][2] - fr[0][-1][2] for f in fr]
        if cut == 4:                      # 10칸(다리 하나만큼)이 빠지면 몸 위에 남는 게 먼저 - 그만큼은 옮긴다
            chk("  머리 · 가슴 윗부분은 그대로라 메달이 위아래로 튀지 않는다 (원래 칸 2칸 = 촘촘한 칸 4 안)",
                max(abs(d) for d in dy) <= 4, dy)
    # 걸을 때: 몸이 2 · 4칸 내려가면 메달도 그만큼 (촘촘한 칸 4 · 8)
    fr, _c = P.plan([ball(0), ball(2), ball(4)], [(16, 23)] * 3, [(16, 16)] * 3, "down", ("medal_gold",))
    ys = [f[-1][2] - fr[0][-1][2] for f in fr]
    chk("걸을 때 메달이 몸을 따라간다 (튀지 않는다)", ys == [0, 4, 8], ys)
    # 화면에서 줄여 그리는 큰 포켓몬 - 장식 그림은 1픽셀 아래로 못 줄인다. 그래도 끈 끝 · 메달이 몸 위에
    g = giant()
    for scale in (0.8, 1.3):
        fs = g.resize((int(round(64 * scale)), int(round(64 * scale))), Image.NEAREST)
        new, pad, _sp, _k = P.decorate({"d": [fs]}, {"d": [g]}, {"d": "down"}, {"d": ([(32, 26)], [(32, 36)])},
                                       (0, 0), scale, ("medal_gold",))
        cv = new["d"][0]
        body = Image.new("L", cv.size, 0)
        body.paste(fs.split()[3], (pad[0], pad[1]))
        bp = body.load()
        med = _colors(cv, set(ART.MEDAL_TONES["gold"].values()))
        strap = _colors(cv, {ART.STRAP, ART.STRAP_DARK})
        on_m = sum(1 for p in med if bp[p]) / float(len(med) or 1)
        on_s = sum(1 for p in strap if bp[p]) / float(len(strap) or 1)
        chk("큰 포켓몬 배율 %.1f: 메달 90%% · 끈 85%% 이상이 몸 위 (끈이 허공으로 안 뻗는다)" % scale,
            med and strap and on_m >= 0.9 and on_s >= 0.85, (round(on_m, 2), round(on_s, 2)))
    # 실제처럼 여러 방향 · 머리 장식과 같이 - 방향마다 다 그려진다 (둘째 방향부터 빠지면 안 된다)
    fs = g.resize((51, 51), Image.NEAREST)
    new, _pad, _sp, _k = P.decorate({"d": [fs], "r": [fs], "dl": [fs]}, {"d": [g], "r": [g], "dl": [g]},
                                    {"d": "down", "r": "right", "dl": "downleft"},
                                    dict((k, ([(32, 26)], [(32, 36)])) for k in ("d", "r", "dl")),
                                    (0, 0), 0.8, ("bow", "medal_gold"))
    got = dict((d, bool(_colors(new[d][0], set(ART.MEDAL_TONES["gold"].values())))) for d in ("d", "r", "dl"))
    chk("여러 방향 + 리본: 방향마다 메달이 그려진다", all(got.values()), got)


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
