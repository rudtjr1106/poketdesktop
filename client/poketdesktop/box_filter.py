# -*- coding: utf-8 -*-
"""포켓몬 관리 창의 거르기 — 타입과 이름.

창(ui_box)에서 떼어 둔 순수 계산이다. 화면 없이 검사할 수 있고, 창은
'무엇을 보여줄지' 만 여기서 받아 그린다.

이름 찾기는 **별명, 종 이름, 도감 번호** 를 다 본다. 별명을 지어 준
포켓몬은 종 이름으로도 찾혀야 한다 - "파이리" 를 쳤는데 별명이 "불꽃이"
라서 안 나오면 없는 줄 안다.
"""


def _norm(s):
    """비교용. 빈칸을 없애고 소문자로. 한글은 그대로다."""
    return "".join((s or "").split()).lower()


def matches(mon, dex, type_id=None, query=""):
    """이 포켓몬이 거름망을 통과하는가."""
    sp = (dex.get(mon.get("species")) if dex else None) or {}
    if type_id:
        if type_id not in (sp.get("types") or []):
            return False
    q = _norm(query)
    if not q:
        return True
    info = mon.get("info") or {}
    hay = [info.get("name"), info.get("species"), sp.get("kr"),
           mon.get("nickname"), mon.get("species")]
    num = mon.get("num") or sp.get("num")
    if num:
        hay.append(str(num))
        hay.append("%04d" % int(num))
    return any(q in _norm(h) for h in hay if h)


def apply(mons, dex, type_id=None, query=""):
    """거른 목록. 순서는 그대로 둔다 (파티 -> 박스 순이 유지되어야 한다)."""
    return [m for m in mons if matches(m, dex, type_id, query)]


def types_present(mons, dex):
    """지금 갖고 있는 포켓몬들의 타입만. 없는 타입까지 단추로 깔면
    열여덟 개가 늘어서서 정작 쓸 것을 못 찾는다."""
    seen = []
    for m in mons:
        sp = (dex.get(m.get("species")) if dex else None) or {}
        for t in sp.get("types") or []:
            if t not in seen:
                seen.append(t)
    return seen
