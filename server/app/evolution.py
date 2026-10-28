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

from . import db, items


KST = datetime.timezone(datetime.timedelta(hours=9))


def _hour(hour=None):
    # 앱이 시각을 안 보낸 길(탐험 · 레이드 경험치 같은 것)은 서버 시계를 본다. 그게 그냥 now() 였는데
    # 컨테이너는 UTC 라 한국과 9시간 어긋났다 - 밤 11시가 낮(14시)으로 읽혔다 (게시판 #370 을 보다 찾음).
    return datetime.datetime.now(KST).hour if hour is None else int(hour)


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
    # 능력치를 보는 곳이라 **병뚜껑을 쳐준 개체값**으로 센다 (화면에 뜨는
    # 능력치와 같은 값이어야 한다). 발키는 Lv.20 에 진화하고 병뚜껑은
    # Lv.50 부터라 실제로 갈릴 일은 거의 없지만, 기준이 둘이면 안 된다.
    st = P.calc_all_stats(sp, P.effective_ivs(mon), mon.get("evs", {}),
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
    sp = b.get("split")
    if sp is not None and int(mon.get("id") or 0) % 2 != sp:
        return False                      # 개체마다 정해진 갈래 (개무소 - 본가는 성격값, 게시판 #370)
    return True


# 조건의 무게. 큰 것부터 본다.
# 시간대(낮/밤)는 가만히 있어도 반은 맞으므로 가장 약하다. 특정 기술을
# 배우고 있어야 한다든가 하는 건 사용자가 일부러 맞춘 것이니 세다.
_COND_WEIGHT = {"moveType": 8, "move": 8, "stats": 4, "gender": 4,
                "held": 4, "time": 1, "split": 1}


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


TIME_KR = {"day": "낮(6~18시)", "night": "밤(18~6시)", "dusk": "해 질 녘(17~19시)"}


def why_not(dex, mon, hour=None):
    """레벨업 · 친밀도 진화가 지금 왜 안 되는지 한 줄. 그런 진화가 아예 없으면 None.

    Lv.100 에게 이상한사탕을 쓰면 진화 판정만 한다(item_routes._use_level). 안 되면 예전에는
    '이미 최고 레벨입니다' 뿐이라, 친밀도가 모자란지 밤이라 안 되는지 알 길이 없었다
    (Lv.100 리오르 - 친밀도 160 + 낮, 게시판 #351).
    """
    if mon.get("noEvolve"):
        return "변함없는돌로 진화를 막아 두었습니다."
    from . import walk
    for b in branches(dex, mon):
        mode = b.get("mode")
        if mode not in ("level", "friend"):
            continue
        need = []
        if mode == "level" and mon["level"] < b.get("level", 999):
            need.append("Lv.%d" % b["level"])
        if mode == "friend":
            have, want = int(mon.get("happiness", 0)), int(b.get("happiness", 999))
            if have < want:
                hrs = walk.hours_to(have, want, bool(mon.get("luxury")), mon.get("held") == "SOOTHEBELL")
                need.append("친밀도 %d 이상 (지금 %d - 데리고 다니면 %d시간쯤 걸립니다)"
                            % (want, have, max(1, int(round(hrs)))))
            else:
                need.append("친밀도 %d 이상 (지금 %d - 됐습니다)" % (want, have))
        if b.get("time"):
            ok = _time_ok(b["time"], hour)
            need.append(TIME_KR.get(b["time"], b["time"]) + ("" if ok else " - 지금은 아닙니다"))
        to = (dex.get(b["to"]) or {}).get("kr", b["to"])
        return "%s(으)로 진화하려면: %s" % (to, " · ".join(need))
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

    # **진화하면서 배우는 기술을 넣는다.** 알던 기술은 그대로 두고 새로
    # 배우는 것만 얹는다. 이걸 안 해서 버터플이 염동력도 바람일으키기도
    # 못 배우고, Lv21 까지 때릴 방법이 없었다 (279종, 기술 383개).
    #
    # **네 개가 차 있으면 안 밀어낸다.** 레벨업과 같은 규칙이다 - 기다리는
    # 목록에 적어 두고 나중에 무엇을 잊을지 물어본다. 전에는 오래된 것부터
    # 밀어냈는데(P.trim_moves), 진화 연출 한가운데라 무엇이 사라졌는지
    # 더 안 보였다.
    moves = list(mon.get("moves") or [])
    pending = list(mon.get("pending") or [])
    learned = []
    for m in P.evolution_moves(new_sp):
        if m in moves or m in pending:
            continue
        if len(moves) < P.MAX_MOVES:
            moves.append(m)
            learned.append(m)
        else:
            pending.append(m)

    db.run("UPDATE pokemon SET species=?, exp=?, ability=?, hidden_ability=?,"
           " moves=?, pending=? WHERE id=? AND user_id=?",
           (new_key, exp, ability, int(bool(hidden)), json.dumps(moves),
            json.dumps(pending), mon["id"], uid))
    # **진화한 종도 도감에 올린다.** 도감(seen)은 잡을 때만 올리고 있어서,
    # 파이리를 키워 리자드가 돼도 리자드 칸은 비어 있었다. 이제 가진
    # 포켓몬이니 '잡음' 으로 올린다. 이미 쓰던 사람 몫은 migrations 가 한 번 채운다.
    items.mark_seen(uid, new_key, True, now or items._now_iso())
    from . import achievements
    achievements.safe_check(uid)

    out = dict(mon)
    out["species"] = new_key
    out["exp"] = exp
    out["ability"] = ability
    out["hiddenAbility"] = hidden
    out["moves"] = moves
    out["learned"] = learned
    out["pending"] = pending
    out["pendingIds"] = list(pending)
    return out


def public(dex, before, after, learned=(), pending=()):
    """클라이언트에 보낼 진화 알림 한 덩이.

    **무엇을 배웠는지 같이 보낸다.** 진화하면서 배우는 기술이 있는데
    말없이 들어가면 언제 생긴 건지 알 길이 없다. 밀려난 것도 적는다 -
    아끼던 기술이 조용히 사라지면 나중에야 알게 된다.
    """
    a = dex.get(before) or {}
    b = dex.get(after) or {}
    return {
        "from": before, "fromKr": a.get("kr", before), "fromNum": a.get("num"),
        "to": after, "toKr": b.get("kr", after), "toNum": b.get("num"),
        "learned": [dex.move_name(m) for m in learned],
        # 자리가 없어 아직 못 배운 것. 클라이언트가 이걸 보고 물어본다.
        "pending": [dex.move_name(m) for m in pending],
        "pendingIds": list(pending),
    }
