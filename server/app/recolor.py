# -*- coding: utf-8 -*-
"""이로치 시트가 없는 종의 이로치 동작 도트를 만든다 (1.10.1).

SpriteCollab 에는 보통 동작 시트는 있는데 **이로치 시트(0000/0001)가 없는**
종이 있다. 코라이돈·딱정곤·퍼퓨돈 등 8종과 메가 4폼은 통째로 없고, 레시라무·
루가루암·뜨아거 등 28종은 앉기·눕기 같은 동작만 없다. 그런 종은 이로치사탕을
먹여도 바탕화면·투기장에서 보통 색으로 걸었다 (앉을 때만 보통 색이 되거나).

그런데 같은 저장소의 **얼굴 그림(portrait)** 에는 이 40종 모두 이로치가 있다.
보통 얼굴과 이로치 얼굴은 같은 그림에 색만 바꾼 것이라, 같은 자리의 화소를
맞대 보면 '이 색은 이 색이 된다' 는 표가 나온다 (코라이돈):

    보통 (207, 86, 65) 빨간 몸     ->  이로치 (109,109,131) 검은 몸
    보통 ( 73, 87,219) 파란 끝     ->  이로치 (218, 88,127) 빨간 끝
    보통 (218,103,206) 자홍 깃털   ->  이로치 (234,237,102) 노란 깃털
    보통 ( 37, 40, 51) 테두리      ->  그대로

동작 시트의 색은 얼굴 그림의 색과 똑같지 않다 (같은 빨강이라도 더 진하다).
그래서 시트의 색마다 **가장 가까운 얼굴 색**을 찾아 그 이로치 색으로 바꾸되,
시트 색이 그 얼굴 색보다 밝거나 어두운 만큼은 남긴다. 그래야 시트에 원래 있던
명암(밝은 빨강 / 어두운 빨강)이 이로치에서도 남는다. 얼굴에서 안 바뀐
색(테두리·눈·이빨)은 시트에서도 그대로 둔다.

색 거리와 밝기는 CIELAB 으로 잰다. RGB 거리는 사람 눈과 어긋나서 어두운
빨강이 어두운 파랑과 가깝게 나온다.

**서버에는 Pillow 가 없다** (pngmini 와 같은 이유). 표준 라이브러리만 쓴다.
"""
import math

from . import pngmini

# 얼굴 두 장이 '같은 그림에 색만 바꾼 것' 인지 보는 기준. 이보다 어긋나면
# 다시 그린 그림이라 표를 믿을 수 없다 - 만들지 않는다.
ALPHA_MISS_MAX = 0.05       # 한쪽만 칠해진 화소의 비율
# 한 색이 늘 같은 색으로 바뀌는 화소의 비율. 이로치를 그리면서 명암을 다시 넣은
# 얼굴(퍼퓨돈 86%)도 있어서 0.9 는 빡빡하다. 진짜 이로치 시트가 있는 종으로 재
# 보면 0.8~0.9 는 대체로 보통 색보다 낫고, 0.8 밑(버드렉스 43%)은 오히려 못하다.
AGREE_MIN = 0.80


def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    c = min(1.0, max(0.0, c))
    c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return int(round(c * 255))


def _f(t):
    return t ** (1.0 / 3) if t > 0.008856 else 7.787 * t + 16.0 / 116


def _finv(t):
    return t ** 3 if t ** 3 > 0.008856 else (t - 16.0 / 116) / 7.787


def lab(rgb):
    """(r, g, b) 0~255 -> (L, a, b). sRGB, D65."""
    r, g, b = (_lin(float(v)) for v in rgb[:3])
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    fx, fy, fz = _f(x), _f(y), _f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def rgb(L, a, b):
    """lab() 의 거꾸로. RGB 밖으로 나간 색은 가장자리로 자른다."""
    fy = (L + 16) / 116.0
    x, y, z = _finv(fy + a / 500.0) * 0.95047, _finv(fy), _finv(fy - b / 200.0) * 1.08883
    return (_gam(3.2406 * x - 1.5372 * y - 0.4986 * z),
            _gam(-0.9689 * x + 1.8758 * y + 0.0415 * z),
            _gam(0.0557 * x - 0.2040 * y + 1.0570 * z))


def table(normal_png, shiny_png):
    """보통 얼굴·이로치 얼굴 PNG 로 색 바꾸기 표를 만든다. [(보통색, 이로치색)...].

    같은 그림에 색만 바꾼 것이 아니면 ValueError - 부르는 쪽이 '없다' 로 다룬다.
    """
    w, h, rows_n = pngmini.read_rgba(normal_png, 512)
    w2, h2, rows_s = pngmini.read_rgba(shiny_png, 512)
    if (w, h) != (w2, h2):
        raise ValueError("얼굴 그림 크기가 다르다")
    votes = {}
    painted = miss = 0
    for ln, ls in zip(rows_n, rows_s):
        for x in range(0, w * 4, 4):
            an, as_ = ln[x + 3], ls[x + 3]
            if not an and not as_:
                continue
            painted += 1
            if not an or not as_:
                miss += 1
                continue
            n, s = bytes(ln[x:x + 3]), bytes(ls[x:x + 3])
            cnt = votes.setdefault(n, {})
            cnt[s] = cnt.get(s, 0) + 1
    if not painted or miss > painted * ALPHA_MISS_MAX:
        raise ValueError("얼굴 그림의 모양이 다르다")
    pairs, agree = [], 0
    for n, cnt in votes.items():
        s, k = max(cnt.items(), key=lambda kv: kv[1])
        pairs.append((tuple(n), tuple(s)))
        agree += k
    if agree < (painted - miss) * AGREE_MIN:
        raise ValueError("색만 바꾼 그림이 아니다")
    if all(n == s for n, s in pairs):
        raise ValueError("이로치 얼굴이 보통 얼굴과 같다")
    return pairs


def _shift(p, n, s):
    """Lab 색 p 를 이로치 색 s 로. p 가 짝 n 보다 밝거나 어두운 만큼은 남긴다.

    색(a, b)은 이로치 얼굴 색을 그대로 쓴다. 시트 색의 색조·채도를 '얼굴이 바뀐
    만큼' 돌려 보기도 했는데, 파랑 쪽은 Lab 색조가 고르지 않아서 루카리오가
    노랑 대신 초록이 됐다. 진짜 이로치 시트가 있는 95종으로 재 보면 이쪽이
    가장 가깝다 (색이 맞는 화소: 보통 색 그대로 57% -> 84%).
    """
    return rgb(p[0] + (s[0] - n[0]), s[1], s[2])


def distance(p, q):
    """Lab 두 색의 거리 (CIE94). p 가 시트 쪽 색이다.

    그냥 Lab 거리로 재면 시트의 진한 보라(152,61,248)가 얼굴의 보라(134,86,199)
    보다 얼굴의 파랑(73,87,219)에 더 가깝게 나온다 - 시트가 얼굴보다 채도가 높아서다.
    CIE94 는 진한 색일수록 채도 차이를 덜 친다. 그러면 색조가 같은 쪽을 고른다.
    """
    cp, cq = math.hypot(p[1], p[2]), math.hypot(q[1], q[2])
    dl, dc = p[0] - q[0], cp - cq
    dh2 = max(0.0, (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2 - dc * dc)
    return dl * dl + (dc / (1 + 0.045 * cp)) ** 2 + dh2 / (1 + 0.015 * cp) ** 2


def mapper(pairs):
    """표로 색 하나를 바꾸는 함수를 만든다. 같은 색은 한 번만 계산한다."""
    refs = [(lab(n), n, s) for n, s in pairs]
    memo = {}

    def one(p):
        p = tuple(p)
        got = memo.get(p)
        if got is None:
            lp = lab(p)
            _d, ln, n, s = min((distance(lp, l), l, n, s) for l, n, s in refs)
            got = memo[p] = p if n == s else _shift(lp, ln, lab(s))
        return got
    return one


def apply(sheet_png, pairs):
    """동작 시트 PNG 에 표의 색을 입힌 PNG 를 준다. 투명한 자리·알파는 그대로."""
    w, h, rows = pngmini.read_rgba(sheet_png)
    one = mapper(pairs)
    for line in rows:
        for x in range(0, w * 4, 4):
            if line[x + 3]:
                line[x:x + 3] = bytes(one(line[x:x + 3]))
    return pngmini.write_rgba(w, h, rows)
