# -*- coding: utf-8 -*-
"""붙잡혀 있는 것 (게시판 #664 뒤, 11/19) - 관장 · 실시간 배틀 창과 테마들이 같이 쓴다.

회오리불꽃에 묶여도 화면에 아무 표시가 없고 교체 단추가 켜져 있어서, 묶기가 걸렸는지 실패했는지 알 수 없었다.
판정은 서버가 한다 (common/statusmoves). 여기서는 서버가 view 에 실은 것을 보여 주기만 한다.

    side["noSwitch"]  지금 스스로 바꿀 수 없는 까닭 (문구). 있으면 교체 단추를 잠그고 '무엇을 할까?' 앞에 띄운다.
    mon["bound"]      조이기류 {move, moveKr, turns} - 이름표 꼬리표. turns 는 내가 건 것만 온다
                      (상대가 건 것의 턴 수는 상대의 끈기갈고리손톱을 드러낸다).

옛 서버에는 둘 다 없다 - 그러면 예전 그대로 (단추 켜짐 · 꼬리표 없음).
"""

COLOR = "#b4582c"        # 이름표 꼬리표 빛깔 (DP 계열) - 상태 이상 꼬리표들과 안 겹치는 녹슨 주황


def locked(side):
    """교체 단추를 잠글까 (서버가 까닭을 실었다)."""
    return bool((side or {}).get("noSwitch"))


def prompt(name, side):
    """'무엇을 할까?' 줄. 스스로 바꿀 수 없으면 그 까닭을 앞에 붙인다."""
    why = (side or {}).get("noSwitch")
    if why:
        return "%s 무엇을 할까?" % why
    return "%s 은(는) 무엇을 할까?" % (name or "")


def bound_tag(mon):
    """이름표 꼬리표 '회오리불꽃에 붙잡힘' (+ ' 3턴' - 내가 건 것). 안 붙잡혔으면 ''."""
    b = (mon or {}).get("bound")
    if not b:
        return ""
    tag = "%s에 붙잡힘" % (b.get("moveKr") or b.get("move") or "조이기")
    if b.get("turns"):
        tag += " %d턴" % b["turns"]
    return tag
