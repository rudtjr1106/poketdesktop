# -*- coding: utf-8 -*-
"""전설·환상 목록. **서버와 클라이언트가 같은 것을 본다.**

도감 파일(pokedex.json)의 `legendary` 는 전설과 환상을 함께 묶고
(울트라비스트·패러독스는 빼 둔다), 둘을 가르는 자료는 알 뽑기 목록뿐이었다.
그래서 서버 eggs.py 에만 있던 두 목록을 여기로 옮긴다 - 포켓몬 관리 창이
"전설"·"환상" 을 갈라 보여주려면 클라이언트도 같은 목록이 필요하다.

번호는 전국도감 번호다.
"""

LEGENDARY = (
    144, 145, 146, 150,                                   # 1세대
    243, 244, 245, 249, 250,                              # 2세대
    377, 378, 379, 380, 381, 382, 383, 384,               # 3세대
    480, 481, 482, 483, 484, 485, 486, 487, 488,          # 4세대
    638, 639, 640, 641, 642, 643, 644, 645, 646,          # 5세대
    716, 717, 718,                                        # 6세대
    772, 773, 785, 786, 787, 788, 789, 790, 791, 792, 800,  # 7세대
    888, 889, 890, 891, 892, 894, 895, 896, 897, 898, 905,  # 8세대
    1001, 1002, 1003, 1004, 1007, 1008,                   # 9세대
    1014, 1015, 1016, 1017, 1024,
)
MYTHICAL = (
    151, 251, 385, 386, 489, 490, 491, 492, 493, 494,
    647, 648, 649, 719, 720, 721, 801, 802, 807, 808, 809,
    893, 1025,
)

_LEG = frozenset(LEGENDARY)
_MYTH = frozenset(MYTHICAL)


def kind_of(num):
    """전국도감 번호로 "legendary" / "mythical" / None."""
    try:
        n = int(num)
    except (TypeError, ValueError):
        return None
    if n in _MYTH:
        return "mythical"
    if n in _LEG:
        return "legendary"
    return None


KR = {"legendary": "전설", "mythical": "환상"}


def label(num):
    """화면에 적을 말. 아니면 None."""
    return KR.get(kind_of(num))


# 숨은 특성 표식 (2.1.3, 게시판 #435 하늬바람). 박스에서 전설 ◆ · 환상 ✦ · 이로치 ★ 처럼 한눈에 보이게
# 이름 앞(기본 테마 목록) · 칸 왼쪽 위 ★ 옆(다른 테마 칸)에 붙인다. 앞의 셋과 겹치지 않는 모양이고
# 갈무리11 에 있다 (Pretendard 에는 없어 시스템 글꼴로 그린다 - ✦ 와 같다).
HIDDEN_MARK = "◎"


def has_hidden(mon):
    """숨은 특성인가. 알은 아니다. 박스 줄은 info 에, 포켓몬 원래 값은 바깥에 있다 (둘 다 본다)."""
    if not mon or mon.get("isEgg"):
        return False
    return bool((mon.get("info") or {}).get("hiddenAbility") or mon.get("hiddenAbility"))
