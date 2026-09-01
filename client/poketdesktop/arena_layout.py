# -*- coding: utf-8 -*-
"""투기장 좌표 계산.

창을 하나도 만들지 않는 순수 계산이라 따로 뒀다. 화면 크기가 제각각이라
(노트북 1366x768 부터 4K 까지) 숫자를 박아 두면 어딘가에서는 반드시
깨진다. 그래서 전부 작업 영역 크기에서 비율로 뽑는다.

좌표는 전부 **발밑 기준**이다. 창 왼쪽 위를 기준으로 두면 큰 포켓몬이
땅에 박힌 것처럼 보인다.

'원형으로 모인다' 를 정원으로 그리면 벽에 붙인 동그라미가 된다.
바탕화면은 위에서 내려다보는 평면이라, 세로를 눌러야 '바닥에 그린 링'
으로 읽힌다.
"""
import math

RING_FLATTEN = 0.58        # 원을 눕히는 정도. 1.0 이면 벽에 붙인 동그라미
ARC_SPREAD = 1.05          # 반원이 벌어지는 기본 각도 (약 ±60도)
ARC_SPREAD_MAX = 1.48      # 화면이 좁으면 여기까지 벌린다 (약 ±85도)
STAGE_PAD = 44
R_MIN, R_MAX = 130, 340


def stage_rect(work, pad=STAGE_PAD):
    """투기장이 쓸 영역. work 는 (l, t, r, b) 작업 영역.

    평소 활동 범위(기본 520x360, 오른쪽 아래)에 열두 마리를 욱여넣으면
    도트가 겹쳐서 누가 누군지 모른다. 배틀 동안만 화면을 통째로 빌린다.
    """
    l, t, r, b = work
    # 화면이 아주 작으면 여백부터 줄인다. 여백 때문에 링이 사라지면 안 된다.
    pad = min(pad, max(8, (r - l) // 12), max(8, (b - t) // 12))
    return l + pad, t + pad, r - pad, b - pad


def fit_height(rect, sprite_h, n=6):
    """자리를 벌리는 계산에 쓸 '가상의 도트 키'.

    640x400 화면에 120px 도트 열두 마리는 물리적으로 안 들어간다. 그런
    조합에서 실제 키로 계산하면 링이 화면 밖까지 커진다. 들어갈 만큼으로
    줄여서 계산하고, 겹치는 것은 받아들인다 - 겹치는 것보다 화면 밖으로
    나가서 아예 안 보이는 쪽이 훨씬 나쁘다.
    """
    _x1, y1, _x2, y2 = rect
    return max(20.0, min(float(sprite_h), (y2 - y1) / (n * 0.62 + 2.3)))


def ring_of(rect, sprite_h, n=6):
    """링(눌린 타원)의 중심과 반지름. sprite_h 는 도트 키(targetHeight).

    h    자리를 벌리는 데 쓰는 키 (화면이 작으면 줄어든다)
    sprite  실제 도트 키. 화면 밖으로 안 나가게 막을 때 쓴다.
    """
    x1, y1, x2, y2 = rect
    w, h = float(x2 - x1), float(y2 - y1)
    fit = fit_height(rect, sprite_h, n)
    # 세로는 눌린 만큼 자리를 덜 먹지만, 위아래 끝에 선 포켓몬의 키만큼은
    # 남겨 둬야 머리가 화면 밖으로 잘리지 않는다.
    ry = (h - float(sprite_h) * 2.3) / (2.0 * RING_FLATTEN)
    r = max(R_MIN, min(R_MAX, min(w * 0.34, ry)))
    # 아주 작은 화면에서는 R_MIN 도 안 들어간다. 그때는 들어가는 만큼만.
    r = max(24.0, min(r, w * 0.42, max(24.0, ry)))
    return {"cx": x1 + w / 2.0, "cy": y1 + h / 2.0, "r": r,
            "rect": (x1, y1, x2, y2), "h": fit, "sprite": float(sprite_h)}


def spread_for(n, r, sprite_h):
    """자리끼리 너무 붙으면 반원을 더 벌린다.

    작은 화면 대응이 여기 하나로 모여 있다. 다른 곳에서 또 손대면
    어디서 좁혀졌는지 알 수 없게 된다.
    """
    if n <= 1:
        return 0.0
    need = sprite_h * 0.62 * (n - 1)          # 세로로 이만큼은 벌어져야 한다
    half = max(1.0, r * RING_FLATTEN)
    want = math.asin(min(1.0, (need / 2.0) / half))
    return min(ARC_SPREAD_MAX, max(ARC_SPREAD, want))


def stagger_for(n, r, sprite_h):
    """자리를 번갈아 얼마나 바깥으로 내보낼지(px).

    반원을 최대로 벌려도 세로가 모자라는 화면이 있다(작은 노트북에 도트를
    크게 키운 경우). 각도로는 더 벌릴 수 없으니 앞뒤로 어긋나게 세운다 -
    실제로 사람들이 좁은 데 모여 설 때 하는 것과 같다.

    세로로 g 만큼 떨어져 있을 때 실제 거리가 d 가 되려면 가로로
    sqrt(d^2 - g^2) 만큼 어긋나면 된다.
    """
    if n <= 1:
        return 0.0
    sp = spread_for(n, r, sprite_h)
    # 자리는 세로로 고르게 놓이지 않는다. sin 이라 가운데가 넓고 양 끝이
    # 좁다. 가장 좁은 곳(맨 끝 두 자리)에 맞춰야 한다 - 평균이나 가운데
    # 간격으로 재면 정작 겹치는 데를 놓친다.
    ys = [math.sin(((i / float(n - 1)) - 0.5) * 2.0 * sp) * r * RING_FLATTEN
          for i in range(n)]
    g = min(abs(ys[i + 1] - ys[i]) for i in range(n - 1))
    d = sprite_h * 0.55                               # 이만큼은 떨어져야 한다
    if g >= d:
        return 0.0
    return math.sqrt(max(0.0, d * d - g * g))


def seat_point(ring, side, i, n):
    """반원 위 i번째 자리의 발밑 좌표. i=0 이 맨 위, i=n-1 이 맨 아래.

    각도로 좌우를 뒤집지 않고 dx 부호만 바꾼다. 그래야 양쪽이 정확히
    거울처럼 서고, 자리 순서가 위에서 아래로 똑같이 읽힌다.
    """
    sp = spread_for(n, ring["r"], ring["h"])
    t = 0.0 if n <= 1 else (i / float(n - 1) - 0.5) * 2.0      # -1(위)~+1(아래)
    # 좁을 때만 홀수 자리를 바깥으로 밀어 앞뒤로 어긋나게 세운다.
    out = stagger_for(n, ring["r"], ring["h"]) if i % 2 else 0.0
    dx = math.cos(t * sp) * ring["r"] + out
    dy = math.sin(t * sp) * ring["r"] * RING_FLATTEN
    # 반원을 크게 벌리면 양 끝에서 cos 이 0 에 가까워져 좌우 자리가
    # 가운데로 몰린다. 우리 팀 맨 위와 상대 팀 맨 위가 겹치는 것인데,
    # 누가 어느 편인지가 안 보이면 투기장이 성립하지 않는다.
    # 가운데선에서 이만큼은 떨어져 있게 한다.
    keep = min(ring["r"] * 0.5, ring["h"] * 0.45)
    dx = max(dx, keep)
    cx = ring["cx"] + (dx if side == "foe" else -dx)
    sy = ring["cy"] + dy

    # 마지막 안전장치. 여기까지 와서도 화면을 벗어나면 안으로 당긴다.
    # y 는 양쪽이 같은 값이라 당겨도 거울 관계가 깨지지 않는다.
    x1, y1, x2, y2 = ring["rect"]
    sp = ring["sprite"]
    sy = max(y1 + sp, min(sy, y2))
    cx = max(x1 + sp / 2.0, min(cx, x2 - sp / 2.0))
    return cx, sy


def duel_points(ring):
    """링 한가운데에서 마주 서는 두 자리. (내쪽, 상대쪽)

    도트 폭이 아니라 설정 크기로 고정 계산한다. 이긴 쪽이 링에 남는
    연전이라, 다음 상대의 덩치에 따라 서 있던 애가 옆으로 밀리면 이상하다.
    """
    # 여기는 계산용 키가 아니라 **실제 도트 키**로 벌린다. 반원의 자리는
    # 열둘이라 좁은 화면에서 겹치는 걸 받아들여야 하지만, 링 안은 둘뿐이고
    # 가로로 나란히 서므로 자리가 모자랄 일이 없다. 싸우는 두 마리가
    # 겹치면 그건 배틀이 안 보이는 것이다.
    gap = max(96.0, ring["sprite"] * 2.6)
    y = ring["cy"] + ring["r"] * RING_FLATTEN * 0.18      # 가운데보다 살짝 앞
    return (ring["cx"] - gap / 2.0, y), (ring["cx"] + gap / 2.0, y)


def entry_point(ring, side, i, n):
    """화면 밖 등장·퇴장 지점. 자기 자리와 같은 높이에서 옆으로 밀어 둔다."""
    _sx, sy = seat_point(ring, side, i, n)
    x1, _y1, x2, _y2 = ring["rect"]
    return ((x2 + 90.0) if side == "foe" else (x1 - 90.0)), sy


def feet_to_topleft(sx, sy, fw, fh):
    """발밑 좌표를 창 왼쪽 위로."""
    return sx - fw / 2.0, sy - fh


def clamp_topleft(x, y, fw, fh, work):
    """창이 화면 밖으로 나가지 않게. 등장·퇴장 지점에는 쓰지 않는다."""
    l, t, r, b = work
    return (max(l, min(x, r - fw)), max(t, min(y, b - fh)))
