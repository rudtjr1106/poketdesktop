# -*- coding: utf-8 -*-
"""이로치 포켓몬의 색 고르기 (1.8.0).

이로치 포켓몬은 주인이 **어떤 색으로 보일지** 고를 수 있다. 서버가 포켓몬
행에 적어 두고(pokemon.tint) 그 포켓몬이 나오는 모든 자료에 실어 보내므로,
내 화면뿐 아니라 **남의 화면(친구·랭킹전 상대·레이드)에서도** 그 색이다.

## 값

    None        이로치 색 그대로 (고르지 않은 것)
    "normal"    기본 색 (이로치가 아닌 보통 도트)
    "s090"      이로치 도트의 색조를 90도 돌린 것
    "n090"      기본 도트의 색조를 90도 돌린 것

색조는 45도 간격 일곱 가지다. 그림을 따로 두지 않는다 - 화면 쪽이 받아 둔
도트의 색조를 돌려서 만든다 (client sprite_tint). 그래서 서버는 값이
맞는지만 본다.

## 화면 쪽에서: skin

도트를 고르는 자리는 지금까지 '이로치인가'(참/거짓)만 들고 다녔다. 여기에
색을 얹으려고 그 값을 **skin** 으로 넓힌다.

    False       기본 도트
    True        이로치 도트
    "s090" 등   색조를 돌린 도트

skin(mon) 이 포켓몬 한 마리의 값을 준다. 이로치가 아니면 tint 가 적혀 있어도
늘 False 다 (이로치만의 기능이다).
"""
HUES = (45, 90, 135, 180, 225, 270, 315)
NORMAL = "normal"
# 고를 수 있는 값 전부 (None = 이로치 색 그대로 는 따로)
CHOICES = ((NORMAL,)
           + tuple("s%03d" % h for h in HUES)
           + tuple("n%03d" % h for h in HUES))
_SET = frozenset(CHOICES)


def valid(t):
    """서버가 받아도 되는 값인가. None(되돌리기)도 된다."""
    return t is None or t in _SET


def clean(t):
    """DB·자료에서 읽은 값을 믿을 수 있게. 모르는 값은 None (이로치 색 그대로)."""
    return t if t in _SET else None


def norm(v):
    """아무 값이나 skin 으로: False / True / "s090"."""
    if not v:
        return False
    if isinstance(v, str):
        if v == NORMAL:
            return False
        return v if v in _SET else True
    return True


def skin(mon):
    """이 포켓몬을 그릴 때의 skin. 이로치가 아니면 False."""
    if not mon or not mon.get("shiny"):
        return False
    t = mon.get("tint")
    if not t:
        return True
    return norm(t)


def split(v):
    """skin -> (밑그림이 이로치 도트인가, 돌릴 색조). 색조가 없으면 0."""
    v = norm(v)
    if v is False:
        return False, 0
    if v is True:
        return True, 0
    return v[0] == "s", int(v[1:])


def suffix(v):
    """색조를 돌린 그림의 파일 이름 꼬리. 안 돌렸으면 ''."""
    _base, hue = split(v)
    return "-h%03d" % hue if hue else ""
