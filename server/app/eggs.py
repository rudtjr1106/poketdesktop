# -*- coding: utf-8 -*-
"""포켓몬 알 — 랭크 시즌 1·2등급 보상.

전설의 포켓몬 알(1위)과 환상의 포켓몬 알(2~5위). **바탕화면에 켜 둔
시간만큼 자라서** 다 차면 부화한다. 본가의 '걸어서 부화' 를 이 게임식으로
옮긴 것이다.

시간은 친밀도와 같은 시계로 잰다(walk.settle). 클라이언트가 보내는 숫자는
없고, 서버가 '어디까지 쳐줬나' 를 앞으로만 옮기므로 폴링을 아무리 자주 해도
벽시계보다 빨리 자라지 않는다. 앱을 꺼 두면 안 자란다.

**알 속의 종은 받는 순간 정해진다.** 부화할 때 굴리면 기다리는 동안 몇 번
이고 새로 굴린 셈이 되고, 무엇이 나올지는 서버만 안다(목록에 안 싣는다).

**알은 파티 한 자리를 차지한다** (1.4.1). 포켓몬 관리 창에서 박스에 넣거나
데리고 다닐 수 있고, 데리고 다니는 동안에만 자란다. 알이 있으면 포켓몬은
다섯 마리까지 데리고 다닌다. 배틀에는 안 나간다.
"""
import datetime
import random

from common import pokelogic as P

from . import config, db, deps, items

# (이름, 부화까지 켜 둬야 하는 시간)
KINDS = {
    "legendary": ("전설의 포켓몬 알", 48 * 3600),
    "mythical": ("환상의 포켓몬 알", 36 * 3600),
}

# 알에서 나오는 종. 도감 번호로 적는다. **본가 분류의 전설·환상 전부**이고
# 그중에서 고르게 하나를 뽑는다 (PokeAPI 의 is_legendary / is_mythical 와 같다).
#
# 도감 파일(pokedex.json)의 legendary 표시에는 울트라비스트(11종)와
# 패러독스(20종)까지 섞여 있다. 본가에서 전설로 치지 않으므로 여기 안 넣는다.
LEGENDARY_POOL = (
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
MYTHICAL_POOL = (
    151, 251, 385, 386, 489, 490, 491, 492, 493, 494,
    647, 648, 649, 719, 720, 721, 801, 802, 807, 808, 809,
    893, 1025,
)

# 태어날 때. 본가에서 전설은 개체값 셋이 최고로 정해져 나온다.
HATCH_LEVEL = 5
PERFECT_IVS = 3
HATCH_HAPPINESS = 120


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()


def pool(kind):
    """그 알에서 나올 수 있는 종 (내부 이름).

    이벤트로 따로 나오는 종은 뺀다 - 알에서 먼저 나오면 이벤트의 놀라움이 없다.
    """
    dex = deps.dex()
    nums = LEGENDARY_POOL if kind == "legendary" else MYTHICAL_POOL
    out = []
    for n in nums:
        sp = dex.get(n)
        if sp and sp["internal"] != config.EVENT_SPECIES:
            out.append(sp["internal"])
    return out


def give_species(kind, rng=None):
    """알 속 종을 뽑는다. 목록 안에서 고르게."""
    rng = rng or random.SystemRandom()
    return rng.choice(pool(kind))


def give(uid, kind, rng=None, now=None, species=None, known=None):
    """알을 하나 준다. 새 알의 id.

    species 를 주면 그 종으로 정해진 알이다 (레이드 보상 - 방금 잡은 보스가
    그대로 들어 있다). 안 주면 지금까지처럼 목록에서 고르게 뽑는다.

    known 이면 **무엇이 들어 있는지 화면에도 알린다** (public 을 보라).
    안 주면 species 를 준 알만 그렇게 친다.
    """
    if kind not in KINDS:
        raise ValueError("그런 알이 없습니다.")
    if species is not None and species not in pool(kind):
        raise ValueError("그 종은 이 알에서 나오지 않습니다.")
    known = bool(species is not None if known is None else known)
    species = species or give_species(kind, rng)
    # 자리가 있으면 바로 데리고 다닌다. 꽉 찼으면 박스로 - 받자마자 누구를
    # 억지로 내리지 않는다. 관리 창에서 옮기면 그때부터 자란다.
    slot = deps.free_slot(uid)
    return db.run(
        "INSERT INTO egg (user_id, kind, species, need_sec, got_sec, created_at,"
        " on_desktop, slot, known) VALUES (?,?,?,?,0,?,?,?,?)",
        (uid, kind, species, KINDS[kind][1], now or _now_iso(),
         1 if slot is not None else 0, slot, 1 if known else 0)).lastrowid


def set_desktop(uid, egg_id, on):
    """알을 데리고 다니거나(on) 박스에 넣는다."""
    r = db.q1("SELECT * FROM egg WHERE id=? AND user_id=? AND hatched_at IS NULL",
              (egg_id, uid))
    if not r:
        raise LookupError("그런 알이 없습니다.")
    if not on:
        db.run("UPDATE egg SET on_desktop=0, slot=NULL WHERE id=?", (egg_id,))
        return
    if r["on_desktop"]:
        return
    slot = deps.free_slot(uid, exclude_egg=egg_id)
    if slot is None:
        raise ValueError("데리고 다닐 수 있는 건 알까지 합쳐 최대 %d마리입니다."
                         % config.MAX_PARTY)
    db.run("UPDATE egg SET on_desktop=1, slot=? WHERE id=?", (slot, egg_id))


def add_time(uid, seconds):
    """켜 둔 시간을 알에 더한다. walk.settle 이 부른다."""
    if seconds <= 0:
        return
    # 데리고 다니는 알만. 박스에 넣어 둔 알은 멈춰 있다.
    db.run("UPDATE egg SET got_sec = MIN(need_sec, got_sec + ?)"
           " WHERE user_id=? AND hatched_at IS NULL AND on_desktop=1",
           (int(seconds), uid))


def hatch_ready(uid, rng=None, now=None):
    """다 자란 알을 부화시킨다. 부화한 알 id 목록.

    **먼저 부화했다고 찍고 그다음에 포켓몬을 넣는다** (선물 지급과 같은 순서).
    /api/me 는 90초마다 오고 창을 여러 개 띄울 수도 있어서, 반대로 하면
    한 알에서 두 마리가 나온다.
    """
    rows = db.q("SELECT * FROM egg WHERE user_id=? AND hatched_at IS NULL"
                " AND got_sec >= need_sec", (uid,))
    out = []
    for r in rows:
        now = now or _now_iso()
        cur = db.run("UPDATE egg SET hatched_at=? WHERE id=? AND hatched_at IS NULL",
                     (now, r["id"]))
        if getattr(cur, "rowcount", 1) == 0:
            continue
        pid = _make_mon(uid, r["species"], rng, now,
                        r["slot"] if r["on_desktop"] else None)
        db.run("UPDATE egg SET pokemon_id=? WHERE id=?", (pid, r["id"]))
        out.append(r["id"])
    return out


def _make_mon(uid, species, rng, now, egg_slot=None):
    rng = rng or random.SystemRandom()
    sp = deps.dex().get(species)
    mon = P.make_pokemon(sp, HATCH_LEVEL, rng, shiny_rate=config.SHINY_RATE)
    for s in rng.sample(list(P.STATS), PERFECT_IVS):
        mon["ivs"][s] = P.IV_MAX
    mon["happiness"] = max(int(mon.get("happiness") or 0), HATCH_HAPPINESS)
    pid = db.insert_mon(uid, mon, now)
    # 알이 있던 자리에서 태어난다 (알은 방금 깼으니 그 자리가 비었다). 그 번호가
    # 어긋나 있으면 아무 빈 자리, 그것도 없으면 박스.
    slot = deps.free_slot(uid)
    if slot is not None and egg_slot is not None:
        taken = set(x["slot"] for x in db.q(
            "SELECT slot FROM pokemon WHERE user_id=? AND on_desktop=1 AND id<>?",
            (uid, pid)))
        if egg_slot not in taken and egg_slot not in deps._egg_slots(uid):
            slot = egg_slot
    if slot is not None:
        db.run("UPDATE pokemon SET on_desktop=1, slot=? WHERE id=?", (slot, pid))
    items.mark_seen(uid, species, True, now)
    return pid


def public(uid):
    """화면에 줄 알 목록. 아직 안 부화한 알과, 부화했지만 아직 안 알린 알.

    **알 속 종은 싣지 않는다.** 부화한 알만 태어난 포켓몬을 붙인다.

    딱 하나 예외가 있다 - `known` 인 알(레이드 보상)은 받는 사람이 무엇을
    잡았는지 이미 안다. 이름을 "테오키스의 알" 로 바꿔 준다. 화면은 전부
    이 name 을 쓰므로(바탕화면 이름표·포켓몬 관리·부화 연출) 여기 한 줄로
    끝난다.
    """
    rows = db.q("SELECT * FROM egg WHERE user_id=? AND"
                " (hatched_at IS NULL OR announced=0) ORDER BY id", (uid,))
    out = []
    for r in rows:
        name, need = KINDS.get(r["kind"], ("포켓몬 알", r["need_sec"]))
        known = bool(r["known"]) if "known" in r.keys() else False
        if known:
            sp = deps.dex().get(r["species"]) or {}
            if sp.get("kr"):
                name = "%s의 알" % sp["kr"]
        e = {"id": r["id"], "kind": r["kind"], "name": name, "known": known,
             "gotSec": r["got_sec"], "needSec": r["need_sec"],
             "leftSec": max(0, r["need_sec"] - r["got_sec"]),
             "hatched": r["hatched_at"] is not None,
             "onDesktop": bool(r["on_desktop"]), "slot": r["slot"],
             "createdAt": r["created_at"]}
        if r["hatched_at"] is not None and r["pokemon_id"]:
            m = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?",
                      (r["pokemon_id"], uid))
            if m:
                e["pokemon"] = deps.decorate(db.row_to_mon(m))
        out.append(e)
    return out


def box_list(uid):
    """포켓몬 관리 창에 보일 알 (아직 안 깬 것만)."""
    return [e for e in public(uid) if not e["hatched"]]


def mark_announced(uid, egg_id):
    return db.run("UPDATE egg SET announced=1 WHERE id=? AND user_id=?"
                  " AND hatched_at IS NOT NULL", (egg_id, uid)).rowcount > 0
