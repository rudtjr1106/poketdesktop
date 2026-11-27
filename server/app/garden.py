# -*- coding: utf-8 -*-
"""열매 텃밭 (시즌 7) 서버 - 화분 셋 · 물 · 거두기 · 친구 물 · 열매 먹이기.

## 화분 (garden_pot - 사람마다 칸 셋, 빈 화분은 줄이 없다)

단계 · 남은 초는 **읽을 때 서버 시계로 센다** (planted_at + grow_sec, 탐험과 같은 방식 - 스레드 없음). 앱이 밤새 꺼져 있어도
자라고, 앱 시계를 돌려도 안 통한다. 물은 '준 그 순간의 단계' 비트(wet_mask), 친구 물은 작물마다 한 번(friend_bonus).
planted_at 은 그 작물의 열쇠다 - 거두기 · 물 · 뽑기가 `… AND planted_at=?` 를 걸어 쓰므로, 두 PC · 두 번 클릭이 같은 작물을
두 번 거두거나 새로 심은 작물에 옛 물을 주지 못한다 (rowcount 로 가른다). 쓰기는 모두 사람마다 잠금(user_lock) 안에서 한다
(uvicorn 한 프로세스 - 낚시와 같은 모양, 잠금은 따로).

## 하루 (KST - visit.today 와 같은 날)

거둠 천장 GARDEN_CAP: 거둘 때 오늘 거둔 수가 천장 **미만이면 그 화분은 통째로** 거둔다 (마지막 한 번은 넘칠 수 있다 - 익은
열매를 반만 주고 버리지 않는다). 다 차면 익은 화분은 그대로 기다리고 0시에 풀린다. 친구 물은 받는 쪽(주인) 하루 한 번
(garden_water 의 열쇠가 주인 · 날), 먹이는 포켓몬마다 하루 한 번 (feed_day). 지난 날 줄은 집안일(housekeep)이 치운다.

## 거두고 다시 심기

씨앗은 **거두기 전에 가방에 있던** 같은 열매에서 쓴다. 거둔 열매는 모든 화분을 다 거둔 뒤에 가방에 넣는다 - 거둔 것으로
다시 심으면 '없으면 빈 칸' 이 영영 안 생기고, 화분 순서에 따라 한쪽만 다시 심기는 일도 생긴다.

규칙 숫자 · 순수 계산은 common/garden.py. 설계: design-notes/2026-11-26-garden.md · -garden-plan.md
"""
import datetime
import threading

from common import garden as G
from common import korean

from . import auth, config, db, deps, items, season, visit, walk

UTC = datetime.timezone.utc
SLOTS = 3                   # 화분 수
NEXT_MAX = 6 * 3600         # nextIn 의 끝 - 앱은 이때 다시 묻는다 (그사이 /api/me 동기화도 카드를 싣는다)


class Refused(Exception):
    """요청을 받을 수 없다 - 라우트가 그 상태 번호 · 글로 돌려준다. why 는 친구 물이 앱에 알리는 까닭
    (empty · ripe · bonus · done · closed - WHY_TEXT 와 _why_not)."""

    def __init__(self, status, text, why=None):
        Exception.__init__(self, text)
        self.status = status
        self.text = text
        self.why = why


def is_open():
    """열렸나. 시즌 번호를 그때그때 본다 (fishing.is_open 과 같다)."""
    return season.SEASON >= config.GARDEN_FROM


def closed_text():
    return "열매 텃밭은 시즌 %d에 열립니다." % config.GARDEN_FROM


# ---------------------------------------------------------------- 시각 · 잠금
def _now():
    return datetime.datetime.now(UTC)


def iso(dt):
    """planted_at 칸 (초까지). 작물의 열쇠로 견주므로 늘 같은 꼴로 적는다."""
    return dt.astimezone(UTC).replace(microsecond=0).isoformat()


def _age(row, now):
    """심은 지 몇 초 (내림). 시계가 거꾸로면 0 - 새싹으로 읽는다."""
    return max(0, int((now - auth.parse_iso(row["planted_at"])).total_seconds()))


def _stage(row, now):
    return G.stage_at(_age(row, now), row["grow_sec"])


def _changed(cur):
    n = getattr(cur, "rowcount", 0)
    return n if n and n > 0 else 0


_locks = {}
_locks_guard = threading.Lock()


def user_lock(uid):
    """사람마다 잠금 하나 (심기 · 물 · 거두기 · 뽑기 · 친구 물 받기 · 먹이). 다시 들어가지 않는다 - 안에서 또 잡지 말 것."""
    with _locks_guard:
        lk = _locks.get(uid)
        if lk is None:
            lk = _locks[uid] = threading.Lock()
        return lk


# ---------------------------------------------------------------- 읽기 · 카드
# /api/me 가 90초마다 모든 사람에게 싣는다. Turso 는 원격이라 왕복 한 번이 100ms 다 - 화분 · 오늘 거둔 수 · 오늘 먹인 포켓몬 ·
# 오늘 받은 친구 물을 **한 번에** 읽는다 (칸 이름은 첫 SELECT 의 것: k 가 줄의 종류).
_LOAD = ("SELECT 'pot' AS k, slot AS a, berry AS b, planted_at AS c, grow_sec AS d, wet_mask AS e, friend_bonus AS f"
         " FROM garden_pot WHERE user_id=?"
         " UNION ALL SELECT 'day', harvested, NULL, NULL, NULL, NULL, NULL FROM garden_day WHERE user_id=? AND day=?"
         " UNION ALL SELECT 'fed', pokemon_id, NULL, NULL, NULL, NULL, NULL FROM feed_day WHERE user_id=? AND day=?"
         " UNION ALL SELECT 'water', w.giver_id, u.username, NULL, NULL, NULL, NULL FROM garden_water w"
         " LEFT JOIN users u ON u.id=w.giver_id WHERE w.host_id=? AND w.day=?")


def _load(uid, now):
    day = visit.today(now)
    st = {"pots": {}, "harvested": 0, "fed": [], "watered": False, "waterFrom": None}
    for r in db.q(_LOAD, (uid, uid, day, uid, day, uid, day)):
        k = r["k"]
        if k == "pot":
            st["pots"][int(r["a"])] = {"slot": int(r["a"]), "berry": r["b"], "planted_at": r["c"],
                                       "grow_sec": int(r["d"]), "wet_mask": int(r["e"] or 0),
                                       "friend_bonus": int(r["f"] or 0)}
        elif k == "day":
            st["harvested"] = int(r["a"] or 0)
        elif k == "fed":
            st["fed"].append(int(r["a"]))
        elif k == "water":
            st["watered"] = True
            st["waterFrom"] = r["b"] or "?"
    return st


def _pots(uid):
    """{칸: 줄} - 쓰기 전에 잠금 안에서 다시 읽는다."""
    return dict((int(r["slot"]), r) for r in db.q("SELECT * FROM garden_pot WHERE user_id=?", (uid,)))


def _pot_public(slot, row, now):
    if row is None:
        return {"slot": slot, "berry": None, "group": None, "stage": 0, "grow": None, "age": None, "left": None,
                "wetMask": 0, "friendBonus": 0, "ripe": False, "yield": None, "needsWater": False}
    group = G.group_of(row["berry"])
    grow = int(row["grow_sec"])
    age = _age(row, now)
    stage = G.stage_at(age, grow)
    wet, fb = int(row["wet_mask"] or 0), int(row["friend_bonus"] or 0)
    bit = G.wet_bit(stage)
    return {"slot": slot, "berry": row["berry"], "group": group, "stage": stage, "grow": grow, "age": age,
            "left": max(0, grow - age), "wetMask": wet, "friendBonus": fb, "ripe": stage == G.RIPE,
            "yield": G.yield_of(group, wet, fb), "needsWater": bool(bit) and not wet & bit}


def _card(st, now):
    pots = [_pot_public(i, st["pots"].get(i), now) for i in range(SLOTS)]
    nxt = [G.next_change(p["age"], p["grow"]) for p in pots if p["berry"] and not p["ripe"]]
    return {"open": True, "pots": pots, "harvested": st["harvested"], "cap": config.GARDEN_CAP,
            "nextIn": min(min(nxt), NEXT_MAX) if nxt else None,
            "fedToday": sorted(st["fed"]),
            "friendWater": {"from": st["waterFrom"]} if st["watered"] else None}


def card(uid, now=None):
    """텃밭 카드 (GET /api/garden · /api/me 의 garden). 열리기 전이면 None - 앱은 화단을 안 띄운다."""
    if not is_open():
        return None
    now = now or _now()
    return _card(_load(uid, now), now)


def _fresh(uid, now):
    return _card(_load(uid, now), now)


# 친구 물을 못 주는 까닭. 손님 view 의 why 와 POST /api/visit/water 409 의 why 가 같은 말이다 (앱이 메뉴 글을 고른다).
# 예전엔 셋을 empty 하나로 뭉쳐서, 흐린 화단에 화분이 보이는데 '심은 화분 없음' 이 떴다 (리뷰 3 · 15).
WHY_TEXT = {"empty": "물을 줄 화분이 없습니다 (심은 화분 없음).",
            "ripe": "물을 줄 화분이 없습니다 (다 익은 화분뿐 - 주인이 거두면 다시 자랍니다).",
            "bonus": "물을 줄 화분이 없습니다 (자라는 화분이 모두 이미 친구 물을 받았음).",
            "done": "오늘은 이미 친구에게 물을 받은 화단입니다 (하루 한 번)."}


def _why_not(pots):
    """심은 화분들의 [(단계, friend_bonus)] -> 친구 물을 못 주는 까닭 | None (줄 수 있다). 오늘 받았나(done)는 부르는 쪽이
    먼저 본다. bonus 가 ripe 보다 앞이다 - 자라는 화분이 있는데 못 주는 까닭은 +1 이다 (익은 화분이 같이 있어도)."""
    growing = [fb for stage, fb in pots if 1 <= stage <= G.STAGES]
    if any(not fb for fb in growing):
        return None
    if growing:
        return "bonus"
    if any(stage == G.RIPE for stage, _fb in pots):
        return "ripe"
    return "empty"


def friend_view(host, now=None):
    """놀러 간 손님에게 보일 주인의 화단 (visit.view 의 garden). 닫혔으면 None.

    why: done = 주인이 오늘 친구 물을 이미 받았다, empty = 심은 화분이 없다, ripe = 익은 화분뿐이다,
    bonus = 자라는 화분이 모두 이미 +1 이다 (water_by_friend 의 409 와 같은 말)."""
    if not is_open():
        return None
    now = now or _now()
    st = _load(host, now)
    pots = [_pot_public(i, st["pots"].get(i), now) for i in range(SLOTS)]
    why = "done" if st["watered"] else _why_not([(p["stage"], p["friendBonus"]) for p in pots if p["berry"]])
    return {"canWater": why is None, "why": why,
            "pots": [{"berry": p["berry"], "stage": p["stage"], "friendBonus": p["friendBonus"]} for p in pots]}


def _tell_guest(host, now):
    """주인 화단이 바뀌었다 - 지금 놀러 와 있는 손님이 있으면 새 view 를 민다 ({t: watered, garden} - 앱이 이미 받는 모양).

    손님 view 는 놀러 올 때 한 번 만든다. 안 밀면 빈 화단에 놀러 온 손님은 주인이 심어도 '심은 화분 없음' 이 방문 내내 죽은
    줄로 남고 (누를 수 없으니 409 로 고쳐질 길도 없다), 거두거나 뽑은 화분도 흐린 화단에 그대로 남는다 (리뷰 2 · 4 · 9 · 13).
    잠금 안에서 부른다 - 바로 뒤의 쓰기가 먼저 밀려 손님 화면이 거꾸로 가지 않게. 터져도 주인 쪽은 이미 썼으니 그대로 간다."""
    v = visit._visit_of(host)
    if not v or v.get("host") != host:
        return                               # 손님이 없거나, 이 사람이 남의 집에 놀러 가 있는 손님이다
    try:
        visit.push(v["guest"], {"t": "watered", "garden": friend_view(host, now)})
    except Exception as e:                                  # noqa: BLE001
        print("[garden] 손님에게 친구 화단 밀기 실패 %s: %r" % (host, e))


# ---------------------------------------------------------------- 심기 · 물 · 거두기 · 뽑기
def is_seed(item_id):
    """심을 수 있나 - 지닌 열매만 (낚시 미끼와 같은 47종). 노력치 열매(cat 'ev')는 상점 80원이라 뺀다."""
    it = items.get(item_id)
    return bool(it) and it.get("cat") == "held" and G.group_of(item_id) is not None


def _slot(slot):
    try:
        s = int(slot)
    except (TypeError, ValueError):
        s = -1
    if not 0 <= s < SLOTS:
        raise Refused(400, "화분은 %d개입니다." % SLOTS)
    return s


def _grass_n(uid):
    """바탕화면 파티의 풀 타입 수 (폼이 바꾼 타입으로 센다 - 커트롯 잔디깎기폼 같은 것). 상자 속은 안 센다."""
    d = deps.dex()
    n = 0
    for r in db.q("SELECT species, form FROM pokemon WHERE user_id=? AND on_desktop=1", (uid,)):
        sp = (d.get(r["species"] + "_" + r["form"]) if r["form"] else None) or d.get(r["species"]) or {}
        if "GRASS" in (sp.get("types") or ()):
            n += 1
    return n


def _grow(uid, berry):
    """자라는 시간은 심을 때 정한다 - 나중에 풀 타입을 바꿔 넣어도 이미 심은 작물은 그대로."""
    return G.grow_sec(G.group_of(berry), _grass_n(uid), config.GARDEN_SCALE)


def plant(uid, slot, berry, now=None):
    """빈 화분에 지닌 열매 하나를 씨앗으로 심는다. 카드를 준다."""
    now = now or _now()
    slot = _slot(slot)
    berry = str(berry or "").strip().upper()
    if not is_seed(berry):
        raise Refused(400, "화분에는 지닌 열매만 심을 수 있습니다.")
    with user_lock(uid):
        if db.q1("SELECT 1 FROM garden_pot WHERE user_id=? AND slot=?", (uid, slot)) is not None:
            raise Refused(409, "이미 심은 화분입니다.")       # 씨앗을 빼기 전에 본다
        if not items.bag_take(uid, berry, 1):
            raise Refused(400, korean.natural("%s 이(가) 없습니다." % items.name_of(berry)))
        cur = db.run("INSERT INTO garden_pot (user_id, slot, berry, planted_at, grow_sec) VALUES (?,?,?,?,?)"
                     " ON CONFLICT(user_id, slot) DO NOTHING", (uid, slot, berry, iso(now), _grow(uid, berry)))
        if _changed(cur) != 1:
            items.bag_add(uid, berry, 1)
            raise Refused(409, "이미 심은 화분입니다.")
        _tell_guest(uid, now)
        return _fresh(uid, now)


def water(uid, now=None):
    """지금 물이 필요한 화분 모두에 물을 준다 (그 순간의 단계 비트). {"watered": 준 화분 수, "card"}."""
    now = now or _now()
    with user_lock(uid):
        n = 0
        for slot, row in sorted(_pots(uid).items()):
            bit = G.wet_bit(_stage(row, now))
            if not bit or int(row["wet_mask"] or 0) & bit:
                continue                         # 익었거나 이 단계엔 이미 줬다 - 더 줘도 그대로
            n += _changed(db.run("UPDATE garden_pot SET wet_mask = wet_mask | ? WHERE user_id=? AND slot=?"
                                 " AND planted_at=? AND (wet_mask & ?) = 0",
                                 (bit, uid, slot, row["planted_at"], bit)))
        if n:
            _tell_guest(uid, now)            # 물 자체는 view 에 없지만 단계가 그사이 넘어갔을 수 있다 - 바뀐 김에 맞춘다
        return {"watered": n, "card": _fresh(uid, now)}


def harvest(uid, replant=True, now=None):
    """익은 화분을 모두 거둔다 (하루 천장까지). replant 면 거두기 전 가방에 있던 같은 열매로 그 자리에 다시 심는다.

    {"got": [{berry, kr, n}] (열매마다 합침), "replanted": [칸], "capped": 천장 때문에 익은 화분이 남았나, "card"}."""
    now = now or _now()
    day = visit.today(now)
    got, replanted, capped = [], [], False
    with user_lock(uid):
        ripe = [(slot, row) for slot, row in sorted(_pots(uid).items()) if _stage(row, now) == G.RIPE]
        if ripe:
            db.run("INSERT INTO garden_day (user_id, day, harvested) VALUES (?,?,0)"
                   " ON CONFLICT(user_id, day) DO NOTHING", (uid, day))
        for slot, row in ripe:
            berry = row["berry"]
            n = G.yield_of(G.group_of(berry), row["wet_mask"], row["friend_bonus"])
            # 천장 안에서 먼저 자리를 잡는다 (조건부 +n - 미만이면 통째로). 작물을 못 가져오면 아래에서 되돌린다
            if _changed(db.run("UPDATE garden_day SET harvested = harvested + ? WHERE user_id=? AND day=?"
                               " AND harvested < ?", (n, uid, day, config.GARDEN_CAP))) != 1:
                capped = True
                break
            seed = bool(replant) and items.bag_take(uid, berry, 1)
            if seed:
                cur = db.run("UPDATE garden_pot SET planted_at=?, grow_sec=?, wet_mask=0, friend_bonus=0"
                             " WHERE user_id=? AND slot=? AND planted_at=?",
                             (iso(now), _grow(uid, berry), uid, slot, row["planted_at"]))
            else:
                cur = db.run("DELETE FROM garden_pot WHERE user_id=? AND slot=? AND planted_at=?",
                             (uid, slot, row["planted_at"]))
            if _changed(cur) != 1:
                # 다른 요청이 이 작물을 먼저 가져갔다 - 잡아 둔 자리와 씨앗을 돌려놓는다
                db.run("UPDATE garden_day SET harvested = harvested - ? WHERE user_id=? AND day=?", (n, uid, day))
                if seed:
                    items.bag_add(uid, berry, 1)
                continue
            line = next((x for x in got if x["berry"] == berry), None)
            if line is None:
                got.append({"berry": berry, "kr": items.name_of(berry), "n": n})
            else:
                line["n"] += n
            if seed:
                replanted.append(slot)
        for x in got:                            # 다 거둔 뒤에 넣는다 (머리말 - 거둔 것으로 다시 심지 않게)
            items.bag_add(uid, x["berry"], x["n"])
        if got:
            _tell_guest(uid, now)            # 비었거나 다시 심어 새싹이 됐다 - 손님의 '물 주기' 가 켜질 수 있다
        return {"got": got, "replanted": replanted, "capped": capped, "card": _fresh(uid, now)}


def pull(uid, slot, now=None):
    """화분을 비운다. 새싹 단계면 씨앗을 돌려준다 (잘못 심은 것을 바로 무르는 길). 익은 화분도 뽑힌다 (설계 - 열매는 없다).
    카드 + refunded (씨앗을 돌려줬나) 를 준다."""
    now = now or _now()
    slot = _slot(slot)
    with user_lock(uid):
        row = db.q1("SELECT * FROM garden_pot WHERE user_id=? AND slot=?", (uid, slot))
        if row is None:
            raise Refused(409, "빈 화분입니다.")
        sprout = _stage(row, now) == 1
        cur = db.run("DELETE FROM garden_pot WHERE user_id=? AND slot=? AND planted_at=?",
                     (uid, slot, row["planted_at"]))
        gone = _changed(cur) == 1
        refunded = gone and sprout
        if refunded:
            items.bag_add(uid, row["berry"], 1)
        if gone:
            _tell_guest(uid, now)
        # 돌려줬는지는 서버 시계로 가른 것을 싣는다. 앱의 단계는 nextIn · 동기화 때만 다시 읽어 늦을 수 있다 - 깨어난 노트북에서
        # 앱은 새싹, 서버는 이미 줄기면 앱이 제 단계로 갈라 안 돌려준 씨앗을 '돌려받았어요' 라고 한다 (리뷰 1)
        return dict(_fresh(uid, now), refunded=refunded)


# ---------------------------------------------------------------- 친구 물 (놀러 가기)
def water_by_friend(host, guest, now=None):
    """놀러 온 손님(guest)이 주인(host)의 화분에 물을 준다 - 자라는 화분마다 friend_bonus=1. 보너스가 붙은 화분 수.

    손님이 지금 그 집에 놀러 가 있는지는 부르는 쪽(visit.water)이 본다. **받는 쪽 하루 한 번** - 부계정으로 몰아받지 못하게
    (보따리와 같은 까닭). 줄 화분이 없으면 하루를 쓰지 않는다 (심은 화분 없음 · 익은 화분뿐 · 모두 이미 +1 - 쓰면 헛물이다).
    까닭은 friend_view 의 why 와 같은 말로 올린다. 손님 view 를 미는 것도 부르는 쪽 몫. 준 사람 보상은 없다."""
    if not is_open():
        raise Refused(404, closed_text(), "closed")
    now = now or _now()
    day = visit.today(now)
    with user_lock(host):
        if db.q1("SELECT 1 FROM garden_water WHERE host_id=? AND day=?", (host, day)) is not None:
            raise Refused(409, WHY_TEXT["done"], "done")
        pots = [(slot, row, _stage(row, now)) for slot, row in sorted(_pots(host).items())]
        why = _why_not([(stage, int(row["friend_bonus"] or 0)) for _slot, row, stage in pots])
        if why:
            raise Refused(409, WHY_TEXT[why], why)
        todo = [(slot, row) for slot, row, stage in pots
                if 1 <= stage <= G.STAGES and not int(row["friend_bonus"] or 0)]
        cur = db.run("INSERT INTO garden_water (host_id, day, giver_id, at) VALUES (?,?,?,?)"
                     " ON CONFLICT(host_id, day) DO NOTHING", (host, day, guest, iso(now)))
        if _changed(cur) != 1:
            raise Refused(409, WHY_TEXT["done"], "done")
        n = 0
        for slot, row in todo:
            n += _changed(db.run("UPDATE garden_pot SET friend_bonus=1 WHERE user_id=? AND slot=? AND planted_at=?"
                                 " AND friend_bonus=0", (host, slot, row["planted_at"])))
        return n


# ---------------------------------------------------------------- 열매 먹이기
def _pick_berry(uid, avoid):
    """가방에서 가장 많은 지닌 열매 (같으면 id 순). avoid(지금 미끼)는 빼고 고르고, 그것밖에 없으면 그것."""
    have = sorted(((r["count"], r["item"]) for r in db.q("SELECT item, count FROM bag WHERE user_id=? AND count>0",
                                                          (uid,)) if r["item"] in G.GROUP),
                  key=lambda x: (-x[0], x[1]))
    pick = next((item for _n, item in have if item != avoid), None)
    if pick is None and any(item == avoid for _n, item in have):
        pick = avoid
    return pick


def feed(uid, pid, avoid=None, hour=None, now=None):
    """바탕화면 포켓몬에게 열매 하나를 먹인다 - 친밀도 +FEED_GAIN (255 까지), 포켓몬마다 하루 한 번. 친밀 진화는 그 자리에서.

    {"berry", "kr", "gain", "happiness", "evolve": 가방에서 도구로 진화할 때와 같은 모양 | None}.
    상자 속 포켓몬은 안 된다 (걷기처럼 '데리고 다니는' 것만 친해진다). 255 면 열매도 하루도 쓰지 않고 막는다."""
    now = now or _now()
    avoid = str(avoid or "").strip().upper() or None
    day = visit.today(now)
    with user_lock(uid):
        mon = db.q1("SELECT id, on_desktop, happiness FROM pokemon WHERE id=? AND user_id=?", (pid, uid))
        if mon is None:
            raise Refused(409, "내 포켓몬에게만 열매를 먹일 수 있습니다.")
        if not mon["on_desktop"]:
            raise Refused(409, "바탕화면에 데리고 다니는 포켓몬에게만 열매를 먹일 수 있습니다.")
        before = int(mon["happiness"])
        if before >= walk.MAX_HAPPINESS:
            raise Refused(409, "이미 더없이 친합니다 (친밀도 %d)." % walk.MAX_HAPPINESS)
        if db.q1("SELECT 1 FROM feed_day WHERE pokemon_id=? AND day=?", (pid, day)) is not None:
            raise Refused(409, "오늘은 이미 열매를 먹였습니다.")
        berry = _pick_berry(uid, avoid)
        if berry is None:
            raise Refused(409, "먹일 지닌 열매가 없습니다.")
        # 하루를 먼저 잡고 열매 · 친밀도를 쓴다. 뒤가 막히면 앞을 되돌린다 - 막혔는데 열매나 하루만 사라지지 않게
        if _changed(db.run("INSERT INTO feed_day (pokemon_id, day, user_id) VALUES (?,?,?)"
                           " ON CONFLICT(pokemon_id, day) DO NOTHING", (pid, day, uid))) != 1:
            raise Refused(409, "오늘은 이미 열매를 먹였습니다.")
        if not items.bag_take(uid, berry, 1):
            db.run("DELETE FROM feed_day WHERE pokemon_id=? AND day=?", (pid, day))
            raise Refused(409, "먹일 지닌 열매가 없습니다.")
        cur = db.run("UPDATE pokemon SET happiness = MIN(?, happiness + ?) WHERE id=? AND user_id=? AND on_desktop=1"
                     " AND happiness < ?", (walk.MAX_HAPPINESS, config.FEED_GAIN, pid, uid, walk.MAX_HAPPINESS))
        if _changed(cur) != 1:
            items.bag_add(uid, berry, 1)
            db.run("DELETE FROM feed_day WHERE pokemon_id=? AND day=?", (pid, day))
            raise Refused(409, "지금은 열매를 먹일 수 없습니다.")
        after = int(db.q1("SELECT happiness FROM pokemon WHERE id=?", (pid,))["happiness"])
    # 친밀 진화는 경험치를 얻을 때만 보고 있었다 - 먹여서 넘겼으면 여기서 본다 (이브이는 앱의 시각으로 낮 · 밤)
    evolve = deps.try_evolve(uid, pid, hour if isinstance(hour, int) and 0 <= hour <= 23 else None)
    return {"berry": berry, "kr": items.name_of(berry), "gain": after - before, "happiness": after,
            "evolve": evolve or None}


# ---------------------------------------------------------------- 집안일
def prune(now=None):
    """지난 날 줄을 지운다 (garden_day · garden_water · feed_day). 어제까지는 남긴다 - 0시 언저리에 읽는 요청이 있어도 안전하게.
    지운 줄 수. 한 시간마다 도는 housekeep 이 부른다."""
    keep = visit.today((now or _now()) - datetime.timedelta(days=1))
    n = 0
    for table in ("garden_day", "garden_water", "feed_day"):
        n += _changed(db.run("DELETE FROM %s WHERE day < ?" % table, (keep,)))
    return n
