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


def split(mons):
    """(데리고 다니는 것, PC 박스). 순서는 그대로."""
    party = [m for m in mons if m.get("onDesktop")]
    box = [m for m in mons if not m.get("onDesktop")]
    return party, box


def apply_box(mons, dex, type_id=None, query=""):
    """거름망은 **PC 박스에만** 건다. (파티 전부, 걸러진 박스).

    데리고 다니는 여섯은 늘 보여야 한다. 지금 뭐가 나와 있는지 보는
    자리인데 거름망에 가려지면 '사라졌나' 하고 놀란다. 거름망은 박스가
    몇십 마리로 늘었을 때 찾으려고 있는 것이다.
    """
    party, box = split(mons)
    return party, apply(box, dex, type_id, query)


def iv_of(mon):
    """개체값 % (0~100). 알은 개체값이 없다 - 늘 맨 뒤로 가게 -1."""
    if mon.get("isEgg"):
        return -1.0
    try:
        return float((mon.get("info") or {}).get("ivPercent") or 0)
    except (TypeError, ValueError):
        return 0.0


def bst_of(mon, dex):
    """종족값 합계 (그 종의 여섯 능력치 기본값을 더한 것). 알은 늘 맨 뒤로 가게 -1."""
    if mon.get("isEgg"):
        return -1
    sp = dex.get(mon.get("species")) if dex else None
    base = (sp or {}).get("base") or {}
    try:
        return sum(int(base.get(k) or 0) for k in ("hp", "atk", "def", "spa", "spd", "spe"))
    except (TypeError, ValueError):
        return 0


def sort_bst(mons, dex):
    """종족값 높은 순 (1.10.1). 받은 목록은 그대로 두고 새 목록을 준다.

    1.10.0 에서는 개체값 순이었다. 개체값은 같은 종 안에서의 차이고, 어느 포켓몬이 센지는
    종족값이 먼저 가른다 - 박스에서 센 포켓몬을 찾으려는 것이라 종족값으로 바꿨다.

    종족값이 같으면(같은 종이면) 개체값 높은 순 → 레벨 높은 순 → 도감 번호 → 먼저 잡은 순.
    늘 같은 순서가 나와야 다시 불러올 때마다 줄이 뒤바뀌지 않는다.
    """
    def key(m):
        try:
            level = int(m.get("level") or 0)
        except (TypeError, ValueError):
            level = 0
        return (-bst_of(m, dex), -iv_of(m), -level, int(m.get("num") or 0), m.get("id") or 0)
    return sorted(mons, key=key)


def egg_row(egg):
    """알 하나를 목록의 한 줄감으로 (1.4.1 - 알도 포켓몬처럼 관리한다).

    **id 는 -알id 다.** 포켓몬 id 와 겹치지 않고, 서버의 순서 목록도
    음수를 알로 읽는다. 종·레벨·타입이 없으니 거르기(matches)에서는 이름
    ('전설의 포켓몬 알') 으로만 찾히고 타입을 고르면 빠진다.
    """
    return {"id": -int(egg["id"]), "isEgg": True, "egg": egg,
            "species": "", "num": 0, "level": "", "shiny": False,
            "onDesktop": bool(egg.get("onDesktop")), "slot": egg.get("slot"),
            "info": {"name": egg.get("name") or "포켓몬 알"}}


def merge_eggs(mons, eggs):
    """포켓몬 목록에 안 깬 알을 섞는다.

    데리고 다니는 쪽은 **자리 번호 순서**다 (포켓몬과 알이 여섯 자리를
    나눠 쓴다). 박스는 알을 맨 앞에 둔다 - 몇십 마리 밑에 묻히면 알을
    박스에 넣어 둔 것을 잊는다.
    """
    rows = [egg_row(e) for e in eggs or [] if not e.get("hatched")]
    party = ([m for m in mons if m.get("onDesktop")]
             + [r for r in rows if r["onDesktop"]])
    party.sort(key=lambda m: (m.get("slot") is None, m.get("slot") or 0))
    box = ([r for r in rows if not r["onDesktop"]]
           + [m for m in mons if not m.get("onDesktop")])
    return party + box


def egg_progress(egg):
    """(자란 정도 %, 부화까지 남은 시간 - 시간 단위로 올림)."""
    need = max(1, int(egg.get("needSec") or 1))
    got = max(0, min(need, int(egg.get("gotSec") or 0)))
    left = egg.get("leftSec")
    left = max(0, int(need - got if left is None else left))
    return 100 * got // need, (left + 3599) // 3600


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
