# -*- coding: utf-8 -*-
"""진화.

도감(pokedex.json)의 종마다 `evo` 가 들어 있고, 한 칸이 진화 한 갈래다.

    {"to": "리자드", "toNum": 5, "mode": "level", "level": 16}
    {"to": "샤미드", "toNum": 134, "mode": "stone", "item": "WATERSTONE"}
    {"to": "에브이", "toNum": 196, "mode": "friend", "happiness": 160,
     "time": "day"}

교환 진화는 이 게임에 교환이 없으므로 도구 사용으로 바뀌어 있다
(조건 없는 교환은 '연결의끈', 지닌 물건이 있던 것은 그 물건).

**성장 곡선이 조심스럽다.** 종마다 곡선이 다른데 경험치는 그대로 두면
같은 경험치가 다른 레벨로 읽혀서 레벨이 튄다. 그래서 진화 뒤에는
레벨을 기준으로 경험치를 새 곡선에 맞춰 다시 잡는다.
"""
import datetime
import json

from common import pokelogic as P

from . import db


def _hour(hour=None):
    return datetime.datetime.now().hour if hour is None else int(hour)


def _time_ok(want, hour=None):
    if not want:
        return True
    h = _hour(hour)
    if want == "day":
        return 6 <= h < 18
    if want == "night":
        return h >= 18 or h < 6
    if want == "dusk":
        return 17 <= h < 19
    return True


def _stats_ok(want, dex, mon):
    """발키 계열. 1 = 공>방, -1 = 공<방, 0 = 같음."""
    if want is None:
        return True
    sp = dex.get(mon["species"]) or {}
    st = P.calc_all_stats(sp, mon.get("ivs", {}), mon.get("evs", {}),
                          mon["level"], mon.get("nature", "HARDY"))
    a, d = st.get("atk", 0), st.get("def", 0)
    if want > 0:
        return a > d
    if want < 0:
        return a < d
    return a == d


def _move_type_ok(want, dex, mon):
    """님피아 — 페어리 기술을 알고 있어야 한다."""
    if not want:
        return True
    for mv in mon.get("moves", []):
        key = mv["id"] if isinstance(mv, dict) else mv
        m = dex.move(key)
        if m and m.get("type") == want:
            return True
    return False


def _move_ok(want, mon):
    """그 기술을 지금 알고 있는가.

    가중치(_COND_WEIGHT)에는 'move' 가 있었는데 정작 판정이 없었다.
    그래서 '기술을 알고 레벨업' 하는 열세 갈래가 조건을 무시한 채
    통과하거나(레벨 조건이 있으면) 아예 죽어 있었다.
    """
    if not want:
        return True
    for mv in mon.get("moves", []):
        key = mv["id"] if isinstance(mv, dict) else mv
        if key == want:
            return True
    return False


def _cond_ok(b, dex, mon, hour=None):
    """모드와 상관없이 붙는 부가 조건."""
    if not _time_ok(b.get("time"), hour):
        return False
    g = b.get("gender")
    if g and mon.get("gender") != g:
        return False
    if not _stats_ok(b.get("stats"), dex, mon):
        return False
    if not _move_ok(b.get("move"), mon):
        return False
    if not _move_type_ok(b.get("moveType"), dex, mon):
        return False
    return True


# 조건의 무게. 큰 것부터 본다.
# 시간대(낮/밤)는 가만히 있어도 반은 맞으므로 가장 약하다. 특정 기술을
# 배우고 있어야 한다든가 하는 건 사용자가 일부러 맞춘 것이니 세다.
_COND_WEIGHT = {"moveType": 8, "move": 8, "stats": 4, "gender": 4,
                "held": 4, "time": 1}


def branches(dex, mon):
    """진화 갈래. **조건이 많은 것부터** 돌려준다.

    이브이가 그 이유다. 친밀도 160 에 페어리 기술을 알고 낮이면, 본가는
    님피아가 된다. 그런데 에브이(친밀도+낮) 조건도 동시에 참이라, 먼저
    보는 쪽이 이긴다. 조건이 더 까다로운 쪽을 먼저 봐야 본가와 같아진다.
    """
    sp = dex.get(mon["species"]) or {}
    lst = sp.get("evo", []) or []
    return sorted(lst, key=lambda b: -sum(w for k, w in _COND_WEIGHT.items()
                                          if b.get(k) is not None))


def check_level(dex, mon, hour=None):
    """레벨업/친밀도로 지금 진화할 수 있는지. 되면 그 갈래를 준다."""
    if mon.get("noEvolve"):
        return None
    for b in branches(dex, mon):
        mode = b.get("mode")
        if mode == "level":
            if mon["level"] >= b.get("level", 999) and _cond_ok(b, dex, mon, hour):
                return b
        elif mode == "friend":
            if mon.get("happiness", 0) >= b.get("happiness", 999) \
                    and _cond_ok(b, dex, mon, hour):
                return b
    return None


def check_item(dex, mon, item_id, hour=None):
    """이 도구를 쓰면 진화하는지."""
    for b in branches(dex, mon):
        if b.get("mode") == "stone" and b.get("item") == item_id:
            if _cond_ok(b, dex, mon, hour):
                return b
    return None


def item_targets(dex, mon):
    """이 포켓몬에게 쓸 수 있는 진화 도구 목록."""
    return sorted(set(b["item"] for b in branches(dex, mon)
                      if b.get("mode") == "stone" and b.get("item")))


# ---------------------------------------------------------------- 실행
def _ability_after(dex, mon, new_sp):
    """특성은 자리를 지킨다. 새 종의 같은 자리 특성으로 바뀐다."""
    old_sp = dex.get(mon["species"]) or {}
    if mon.get("hiddenAbility"):
        return new_sp.get("hidden") or (new_sp.get("abil") or [None])[0], True
    old = old_sp.get("abil") or []
    new = new_sp.get("abil") or []
    if not new:
        return new_sp.get("hidden"), bool(new_sp.get("hidden"))
    try:
        i = old.index(mon.get("ability"))
    except (ValueError, AttributeError):
        i = 0
    return new[min(i, len(new) - 1)], False


def apply(uid, mon, branch, dex, now):
    """실제로 종을 바꾼다. 바뀐 mon dict 를 돌려준다.

    본가처럼 알던 기술은 그대로 두고, 특성은 같은 자리를 물려받는다.
    경험치는 새 성장 곡선에 맞춰 다시 잡는다 — 안 그러면 레벨이 튄다.
    """
    new_key = branch["to"]
    new_sp = dex.get(new_key)
    if not new_sp:
        raise ValueError("진화 대상이 도감에 없습니다: %s" % new_key)

    old_sp = dex.get(mon["species"]) or {}
    level = mon["level"]
    exp = mon["exp"]
    if old_sp.get("growth") != new_sp.get("growth"):
        # 곡선이 달라졌다. 같은 레벨을 유지하도록 경험치를 다시 잡는다.
        exp = P.exp_for_level(new_sp.get("growth", "medium"), level)

    ability, hidden = _ability_after(dex, mon, new_sp)

    db.run("UPDATE pokemon SET species=?, exp=?, ability=?, hidden_ability=?"
           " WHERE id=? AND user_id=?",
           (new_key, exp, ability, int(bool(hidden)), mon["id"], uid))

    out = dict(mon)
    out["species"] = new_key
    out["exp"] = exp
    out["ability"] = ability
    out["hiddenAbility"] = hidden
    return out


def public(dex, before, after):
    """클라이언트에 보낼 진화 알림 한 덩이."""
    a = dex.get(before) or {}
    b = dex.get(after) or {}
    return {
        "from": before, "fromKr": a.get("kr", before), "fromNum": a.get("num"),
        "to": after, "toKr": b.get("kr", after), "toNum": b.get("num"),
    }
