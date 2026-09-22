# -*- coding: utf-8 -*-
"""전설·환상 레이드 — 일정, 방, 진행, 보상.

## 일정

정해진 시각에만 열린다 (config.RAID_HOURS, 한국시간). 회차 하나를
**세션**이라 부르고 열쇠는 "2026-09-22T11" 꼴이다.

    보스 공개   정각 1시간 전 (RAID_REVEAL_SEC)
    모이기      정각 5분 전부터 (RAID_OPEN_SEC)
    시작        정각. 3명이 안 모였으면 2분 더 기다린다 (RAID_GRACE_SEC)
    취소        그래도 모자라면 접는다. **참가 횟수는 안 깎는다.**

보스는 세션 열쇠로 정한다 - 같은 회차면 어느 방이든 같은 보스이고,
서버를 껐다 켜도 안 바뀐다. 쉐이미는 eggs.pool 이 이미 빼 준다
(이벤트로 따로 나오는 종이라 알에서도 안 나온다).

## 시계는 KST

서버는 도커 안이라 UTC 로 돌고 pvp 의 하루 계산도 UTC 지만, 이벤트는
사람이 모이는 시각이 전부다. 여기서만 한국시간으로 잰다. 저장하는 시각은
다른 곳과 똑같이 UTC ISO 다 - 섞이면 문자열 비교가 어긋난다.

## 겹친 요청

방 하나에 여러 사람이 동시에 요청을 보낸다. 상태를 바꾸는 곳은 전부
rev 로 잠근다 - 읽을 때의 rev 로 UPDATE 해서 0줄이면 남이 먼저 쓴 것이다.
라운드 진행은 **아무나 먼저 온 요청**이 돌린다. 서버에 따로 도는 시계가
없으므로(폴링만 있다) 마감이 지났는지는 요청이 올 때 본다.
"""
import datetime
import hashlib
import json
import random

from common import raid_battle as RB

from . import config, db, deps, eggs, items

KST = datetime.timedelta(hours=9)
# 방 코드에 쓰는 글자. 0/O, 1/I/L 처럼 헷갈리는 것은 뺐다 - 불러 주는 코드다.
CODE_CHARS = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LEN = 6


# ---------------------------------------------------------------- 시계
def _utc(now=None):
    return now or datetime.datetime.now(datetime.timezone.utc)


def kst_now(now=None):
    """한국시간. tzinfo 없는 datetime 으로 다룬다 (날짜 계산만 한다)."""
    return _utc(now).astimezone(datetime.timezone.utc).replace(tzinfo=None) + KST


def to_utc(kst):
    return (kst - KST).replace(tzinfo=datetime.timezone.utc)


def today_kst(now=None):
    return kst_now(now).date().isoformat()


def now_iso(now=None):
    return _utc(now).replace(microsecond=0).isoformat()


def period():
    return config.RAID_START, config.RAID_END


def in_period(now=None):
    lo, hi = period()
    return lo <= today_kst(now) <= hi


def key_of(dt_kst):
    return "%sT%02d" % (dt_kst.date().isoformat(), dt_kst.hour)


def time_of(key):
    """세션 열쇠 -> 그 회차의 정각 (KST)."""
    day, hour = key.split("T")
    y, m, d = (int(x) for x in day.split("-"))
    return datetime.datetime(y, m, d, int(hour), 0, 0)


def all_keys():
    """이벤트 기간의 모든 회차 열쇠. 차례대로."""
    lo, hi = period()
    y, m, d = (int(x) for x in lo.split("-"))
    cur = datetime.date(y, m, d)
    y, m, d = (int(x) for x in hi.split("-"))
    end = datetime.date(y, m, d)
    out = []
    while cur <= end:
        for h in config.RAID_HOURS:
            out.append("%sT%02d" % (cur.isoformat(), h))
        cur += datetime.timedelta(days=1)
    return out


def open_key(now=None):
    """지금 모일 수 있는 회차. 없으면 None."""
    k = kst_now(now)
    for key in all_keys():
        t = time_of(key)
        if t - datetime.timedelta(seconds=config.RAID_OPEN_SEC) <= k \
                <= t + datetime.timedelta(seconds=config.RAID_GRACE_SEC):
            return key
    return None


def next_key(now=None):
    """다음(또는 지금 열린) 회차. 이벤트가 끝났으면 None."""
    k = kst_now(now)
    for key in all_keys():
        if time_of(key) + datetime.timedelta(seconds=config.RAID_GRACE_SEC) >= k:
            return key
    return None


def active_key(now=None):
    """지금 '돌아가고 있는' 회차. 모이기가 열린 뒤부터 다음 회차가 열릴 때까지.

    open_key 는 모이는 5분 + 유예 2분만 열려 있지만, 방은 그 뒤로도 살아
    있다(방장이 눌러야 시작한다). 그 방들이 **어느 회차의 방인지**를 가르는
    것이 이 값이다 - 이걸 안 보면 오전 11시 방이 저녁까지 남아 있을 때
    21시에 들어온 사람이 11시 보스와 싸우게 된다.
    """
    k = kst_now(now)
    got = None
    for key in all_keys():
        if time_of(key) - datetime.timedelta(seconds=config.RAID_OPEN_SEC) <= k:
            got = key
        else:
            break
    return got


def revealed(key, now=None):
    """보스를 미리 알릴 때가 됐나 (정각 1시간 전부터)."""
    if not key:
        return False
    return kst_now(now) >= time_of(key) - datetime.timedelta(seconds=config.RAID_REVEAL_SEC)


def seconds_to(key, now=None):
    return int((time_of(key) - kst_now(now)).total_seconds())


# ---------------------------------------------------------------- 보스
def pool():
    """레이드에 나올 수 있는 종. 알에서 나오는 전설·환상 전부.

    eggs.pool 을 그대로 쓴다 - 이벤트 종(쉐이미)은 거기서 이미 빠진다.
    """
    return sorted(set(eggs.pool("legendary")) | set(eggs.pool("mythical")))


def _seed(key, salt=""):
    raw = ("poket-raid:%s:%s" % (key, salt)).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:16], 16)


def boss_species(key):
    """이 회차의 보스. 열쇠만 있으면 언제 물어도 같은 답이 나온다."""
    p = pool()
    if not p:
        return None
    return p[_seed(key) % len(p)]


def kind_of(species):
    """전설 알인가 환상 알인가."""
    sp = deps.dex().get(species) or {}
    return "mythical" if sp.get("num") in set(eggs.MYTHICAL_POOL) else "legendary"


def boss_mon(key, level=None):
    """보스 개체. 회차마다 하나로 정해진다 (방이 달라도 같다)."""
    from common import pokelogic as P
    species = boss_species(key)
    sp = deps.dex().get(species)
    if not sp:
        raise LookupError("보스를 찾을 수 없습니다.")
    rng = random.Random(_seed(key, "mon"))
    mon = P.make_pokemon(sp, level or config.RAID_BOSS_LEVEL, rng, shiny_rate=10 ** 9)
    mon["ivs"] = dict((s, 31) for s in P.STATS)
    # 노력치는 config 를 본다 - 0 이면 키운 팀에게 너무 쉬웠다.
    mon["evs"] = dict((s, config.RAID_BOSS_EV) for s in P.STATS)
    mon["nature"] = "HARDY"
    mon["happiness"] = 255
    mon["held"] = None
    return mon


def boss_card(key):
    """화면에 줄 보스 소개. 공개 전에는 이름을 가린다."""
    if not key:
        return None
    out = {"session": key, "at": time_of(key).isoformat(),
           "leftSec": seconds_to(key), "revealed": revealed(key)}
    if not out["revealed"]:
        return out
    species = boss_species(key)
    sp = deps.dex().get(species) or {}
    out.update({"species": species, "num": sp.get("num"), "kr": sp.get("kr"),
                "types": [deps.dex().type_name(t) for t in sp.get("types") or []],
                # 색을 고를 때 쓴다 (바탕화면 기둥). 한글 이름으로는 못 찾는다.
                "typeIds": list(sp.get("types") or []),
                "kind": kind_of(species), "level": config.RAID_BOSS_LEVEL})
    return out


# ---------------------------------------------------------------- 방
def _code(rng=None):
    rng = rng or random.SystemRandom()
    return "".join(rng.choice(CODE_CHARS) for _ in range(CODE_LEN))


def members(room_id):
    return db.q("SELECT * FROM raid_member WHERE room_id=? ORDER BY pos", (room_id,))


def room(room_id):
    return db.q1("SELECT * FROM raid_room WHERE id=?", (room_id,))


def my_room(uid):
    """내가 들어 있는 (아직 안 끝난) 방. 참가·나가기 판정은 이것으로 한다."""
    return db.q1(
        "SELECT r.* FROM raid_room r JOIN raid_member m ON m.room_id=r.id"
        " WHERE m.user_id=? AND m.left_at IS NULL AND r.state IN ('lobby','fighting')"
        " ORDER BY r.id DESC LIMIT 1", (uid,))


def recent_room(uid):
    """화면에 보여 줄 방. 끝난 판도 **결과를 볼 때까지는** 같이 준다.

    안 그러면 마지막 일격을 넣지 않은 사람이 결과를 영영 못 본다 - 남의
    요청이 마지막 라운드를 돌리는 순간 그 방은 done 이 되고, 내 폴링은
    404 를 받아 상금도 알도 화면에 안 뜬다. seen 을 찍으면 그때 빠진다.
    """
    row = my_room(uid)
    if row:
        return row
    return db.q1(
        "SELECT r.* FROM raid_room r JOIN raid_member m ON m.room_id=r.id"
        " WHERE m.user_id=? AND m.seen=0 AND r.state='done'"
        " AND r.result IN ('won','lost','timeout') ORDER BY r.id DESC LIMIT 1",
        (uid,))


def played_today(uid, now=None):
    return db.q1("SELECT * FROM raid_entry WHERE user_id=? AND day=?",
                 (uid, today_kst(now)))


def party_of(uid):
    return [db.row_to_mon(r) for r in db.q(
        "SELECT * FROM pokemon WHERE user_id=? AND on_desktop=1 ORDER BY slot, id", (uid,))]


def expire_old(now=None):
    """아무도 안 돌아오는 방을 접는다."""
    cut = (_utc(now) - datetime.timedelta(seconds=config.RAID_TTL)) \
        .replace(microsecond=0).isoformat()
    db.run("UPDATE raid_room SET state='done', result='expired' WHERE state<>'done'"
           " AND updated_at < ?", (cut,))


def _can_play(uid, now=None):
    """참가할 수 있는 몸 상태인가. 안 되면 까닭을 던진다."""
    if not in_period(now):
        raise ValueError("레이드 기간이 아닙니다.")
    if played_today(uid, now):
        raise ValueError("오늘은 이미 레이드에 참가했습니다. 내일 다시 도전하세요.")
    if len(party_of(uid)) < config.RAID_MIN_PARTY:
        raise ValueError("포켓몬을 %d마리 이상 데리고 와야 합니다."
                         % config.RAID_MIN_PARTY)


def open_lobby(code=None, now=None):
    """지금 들어갈 수 있는 방. 없으면 None.

    **한 번 만들어진 방은 정각이 지나도 살아 있다.** 시작은 방장이 누르는
    것이라(begin) 시계로 접을 이유가 없다 - 아무도 안 오는 방은 TTL 이
    치운다(expire_old).
    """
    key = active_key(now)
    if not key:
        return None
    if code:
        return db.q1("SELECT * FROM raid_room WHERE code=? AND session=?"
                     " AND state='lobby'",
                     ((code or "").strip().upper(), key))
    # **가장 많이 찬 방부터 채운다** (n DESC). 안 그러면 한 명씩 든 방이
    # 여럿 생겨서 아무 방도 세 명을 못 채운다.
    row = db.q1(
        "SELECT r.id, COUNT(m.user_id) n FROM raid_room r"
        " LEFT JOIN raid_member m ON m.room_id=r.id AND m.left_at IS NULL"
        " WHERE r.code IS NULL AND r.state='lobby' AND r.session=?"
        " GROUP BY r.id HAVING n < ? ORDER BY n DESC, r.id LIMIT 1",
        (key, config.RAID_MAX_PLAYERS))
    return room(row["id"]) if row else None


def join(uid, name, code=None, now=None):
    """모집 중인 방에 들어간다. 코드가 있으면 그 방으로.

    **이미 있는 방에는 시각과 상관없이 들어간다.** 모이는 시간(정각 5분 전)은
    새 방을 **만들** 때만 본다 - 그래야 정각이 지나 아직 안 시작한 방에
    늦게 온 사람이 합류할 수 있다.
    """
    expire_old(now)
    mine = my_room(uid)
    if mine:
        return mine
    _can_play(uid, now)
    row = open_lobby(code, now)
    if row is None:
        if code:
            raise LookupError("그 코드의 방이 없습니다.")
        key = open_key(now)
        if not key:
            raise ValueError("지금은 모이는 시간이 아닙니다.")
        cur = db.run(
            "INSERT INTO raid_room (session, code, host, boss, state, rev, events,"
            " round, created_at, updated_at) VALUES (?,?,?,?,'lobby',0,'[]',0,?,?)",
            (key, None, uid, boss_species(key), now_iso(now), now_iso(now)))
        row = room(cur.lastrowid)
    return _seat(row, uid, name, now)


def create_code(uid, name, now=None):
    """친구끼리 할 방을 만든다. 코드를 돌려준다."""
    expire_old(now)
    if my_room(uid):
        raise ValueError("이미 다른 방에 들어가 있습니다.")
    _can_play(uid, now)
    key = open_key(now)
    if not key:
        raise ValueError("지금은 모이는 시간이 아닙니다.")
    code = None
    for _ in range(12):
        c = _code()
        # 아직 안 끝난 방끼리만 안 겹치면 된다 (끝난 방의 코드는 다시 써도 된다)
        if not db.q1("SELECT 1 FROM raid_room WHERE code=? AND state<>'done'", (c,)):
            code = c
            break
    if not code:
        raise ValueError("방을 만들지 못했습니다. 다시 시도해 주세요.")
    cur = db.run(
        "INSERT INTO raid_room (session, code, host, boss, state, rev, events,"
        " round, created_at, updated_at) VALUES (?,?,?,?,'lobby',0,'[]',0,?,?)",
        (key, code, uid, boss_species(key), now_iso(now), now_iso(now)))
    return _seat(room(cur.lastrowid), uid, name, now)


def _seat(row, uid, name, now=None):
    """방에 자리 하나. 이미 앉아 있으면 그대로."""
    got = db.q1("SELECT * FROM raid_member WHERE room_id=? AND user_id=?",
                (row["id"], uid))
    if got:
        if got["left_at"]:
            db.run("UPDATE raid_member SET left_at=NULL WHERE room_id=? AND user_id=?",
                   (row["id"], uid))
        return row
    here = members(row["id"])
    if len([m for m in here if not m["left_at"]]) >= config.RAID_MAX_PLAYERS:
        raise ValueError("그 방은 이미 꽉 찼습니다.")
    pos = max([m["pos"] for m in here] or [-1]) + 1
    db.run("INSERT INTO raid_member (room_id, user_id, pos, name) VALUES (?,?,?,?)",
           (row["id"], uid, pos, name))
    _touch(row["id"], now)
    return row


def _touch(room_id, now=None):
    db.run("UPDATE raid_room SET updated_at=? WHERE id=?", (now_iso(now), room_id))


def _keep_alive(row, now=None):
    """누가 아직 이 방을 보고 있다고 적어 둔다 (expire_old 가 안 접게).

    방장이 누를 때까지 로비가 오래 열려 있을 수 있어서, 사람이 들여다보는
    동안에는 안 늙어야 한다. 다만 **폴링마다 쓰지는 않는다** - 2초마다
    쓰기가 나가면 그것만으로 일이 된다. 절반쯤 늙었을 때만 한 번 쓴다.
    """
    try:
        last = datetime.datetime.fromisoformat(row["updated_at"])
    except (TypeError, ValueError):
        return
    if (_utc(now) - last).total_seconds() >= config.RAID_TTL / 3.0:
        _touch(row["id"], now)


def leave(uid, now=None):
    """방에서 나간다. 싸우는 중이면 그 사람만 물러난다."""
    row = my_room(uid)
    if not row:
        return None
    if row["state"] == "lobby":
        db.run("DELETE FROM raid_member WHERE room_id=? AND user_id=?", (row["id"], uid))
        left = [m for m in members(row["id"]) if not m["left_at"]]
        if not left:
            db.run("UPDATE raid_room SET state='done', result='cancelled', updated_at=?"
                   " WHERE id=? AND state='lobby'", (now_iso(now), row["id"]))
        elif row["host"] == uid:
            # 방장이 나갔다. 다음 사람이 방장이 된다 - 안 그러면 아무도
            # 시작을 못 눌러 방이 그대로 굳는다.
            db.run("UPDATE raid_room SET host=? WHERE id=?",
                   (left[0]["user_id"], row["id"]))
        _touch(row["id"], now)
        return row
    # 싸우는 중
    rb = _load(row)
    i = _index_of(row, uid)
    if i is None:
        return row
    ev = rb.leave(i)
    db.run("UPDATE raid_member SET left_at=? WHERE room_id=? AND user_id=?",
           (now_iso(now), row["id"], uid))
    _save(row, rb, ev, now)
    return room(row["id"])


# ---------------------------------------------------------------- 시작
def can_start(row):
    """지금 시작할 수 있나. (되나, 안 되면 까닭)"""
    if row["state"] != "lobby":
        return False, "이미 시작한 방입니다."
    n = len([m for m in members(row["id"]) if not m["left_at"]])
    if n < config.RAID_MIN_PLAYERS:
        return False, ("%d명부터 시작할 수 있습니다. (지금 %d명)"
                       % (config.RAID_MIN_PLAYERS, n))
    return True, ""


def begin(row, now=None):
    """판을 연다. 참가 횟수는 **여기서** 깎인다 (모이다 취소되면 안 깎인다)."""
    here = [m for m in members(row["id"]) if not m["left_at"]]
    players, dropped = [], []
    for m in here:
        mons = party_of(m["user_id"])
        if len(mons) < config.RAID_MIN_PARTY:
            dropped.append(m)
            continue
        players.append((m["user_id"], m["name"],
                        [RB.leveled(x, config.RAID_TEAM_LEVEL) for x in mons]))
    for m in dropped:
        db.run("DELETE FROM raid_member WHERE room_id=? AND user_id=?",
               (row["id"], m["user_id"]))
    if len(players) < config.RAID_MIN_PLAYERS:
        db.run("UPDATE raid_room SET state='done', result='cancelled', updated_at=?"
               " WHERE id=? AND rev=?", (now_iso(now), row["id"], row["rev"]))
        return room(row["id"])
    rb = RB.RaidBattle(
        deps.dex(), boss_mon(row["session"]), players,
        hp_mult=config.RAID_HP_BASE + config.RAID_HP_PER * len(players),
        max_rounds=config.RAID_ROUNDS, double_from=config.RAID_DOUBLE_FROM,
        rng=random.Random())
    ev = rb.start()
    cur = db.run(
        "UPDATE raid_room SET state='fighting', data=?, events=?, round=0, rev=rev+1,"
        " deadline=?, updated_at=? WHERE id=? AND rev=? AND state='lobby'",
        (json.dumps(rb.dump()), json.dumps(ev), _deadline(now), now_iso(now),
         row["id"], row["rev"]))
    if getattr(cur, "rowcount", 1) == 0:
        return room(row["id"])                     # 남이 먼저 열었다
    for uid, _n, _m in players:
        db.run("INSERT INTO raid_entry (user_id, day, room_id, at) VALUES (?,?,?,?)"
               " ON CONFLICT(user_id, day) DO NOTHING",
               (uid, today_kst(now), row["id"], now_iso(now)))
    return room(row["id"])


def _deadline(now=None):
    return (_utc(now) + datetime.timedelta(seconds=config.RAID_ROUND_SEC)) \
        .replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- 진행
def _load(row):
    return RB.RaidBattle.load(deps.dex(), json.loads(row["data"]))


def _index_of(row, uid):
    rb_players = json.loads(row["data"])["players"] if row["data"] else []
    for i, p in enumerate(rb_players):
        if int(p["uid"]) == int(uid):
            return i
    return None


def _save(row, rb, ev, now=None):
    """판을 적는다. rev 가 어긋나면 아무것도 안 하고 False."""
    cur = db.run(
        "UPDATE raid_room SET data=?, events=?, round=?, state=?, result=?, rev=rev+1,"
        " deadline=?, updated_at=? WHERE id=? AND rev=?",
        (json.dumps(rb.dump()), json.dumps(ev), rb.round,
         "done" if rb.over else "fighting", rb.result,
         None if rb.over else _deadline(now), now_iso(now), row["id"], row["rev"]))
    ok = getattr(cur, "rowcount", 1) != 0
    if ok and rb.over:
        _reward(row, rb, now)
    return ok


# 고른 것을 적다가 남과 부딪혔을 때 다시 해보는 횟수.
CHOOSE_TRIES = 5


def choose(uid, kind, value, now=None):
    """이번 라운드에 할 것을 적는다. 다 모이면 그 자리에서 라운드가 돈다.

    **부딪히면 다시 해본다.** 여섯 명이 같은 방을 동시에 두드리는 판이라,
    rev 가 어긋났다고 그대로 거절하면 남이 먼저 눌렀다는 이유로 내 선택이
    사라진다. 다시 읽어서 그 위에 얹는다 - 그 사이에 라운드가 넘어갔으면
    그때는 사실대로 알린다.
    """
    for _ in range(CHOOSE_TRIES):
        row = my_room(uid)
        if not row or row["state"] != "fighting":
            raise LookupError("진행 중인 레이드가 없습니다.")
        rb = _load(row)
        i = _index_of(row, uid)
        if i is None:
            raise LookupError("이 레이드의 참가자가 아닙니다.")
        rb.choose(i, kind, value)
        ev = None
        if rb.ready():
            ev = rb.resolve()
        if _save(row, rb, ev if ev is not None else json.loads(row["events"]), now):
            return room(row["id"])
    raise RuntimeError("다른 곳에서 먼저 움직였습니다. 다시 불러오세요.")


def tick(row, now=None):
    """마감이 지났으면 라운드를 돌린다. 서버에 도는 시계가 없어서 요청이 깨운다.

    **로비는 안 건드린다.** 시작은 방장이 누르는 것이고(begin), 정각이
    지났다고 접지도 않는다 - 모여서 이야기하다 늦게 시작할 수 있다.
    아무도 안 돌아오는 방은 expire_old 가 치운다.
    """
    if row["state"] == "lobby":
        _keep_alive(row, now)
        return row
    if row["state"] != "fighting" or not row["deadline"]:
        return row
    # 문자열로 비교하면 소수점 이하가 붙은 쪽과 안 붙은 쪽이 섞인다.
    if _utc(now) < datetime.datetime.fromisoformat(row["deadline"]):
        return row
    rb = _load(row)
    if rb.over:
        return row
    ev = rb.resolve()
    _save(row, rb, ev, now)
    return room(row["id"])


# ---------------------------------------------------------------- 보상
def _reward(row, rb, now=None):
    """이겼으면 알(확률)과 상금. 져도 위로금은 준다.

    **이미 준 적이 있으면 다시 안 준다** - rev 로 막고 있지만, 알을 두 번
    주는 것은 되돌릴 수 없어서 한 번 더 확인한다.
    """
    if db.q1("SELECT 1 FROM raid_member WHERE room_id=? AND prize>0 LIMIT 1", (row["id"],)):
        return
    rng = random.SystemRandom()
    won = rb.result == "won"
    order = [uid for _i, uid, _n, _d in rb.ranking()]
    for p in rb.players:
        # 스스로 나갔거나 전멸한 사람도 상금은 받는다. **알은 끝까지 서 있던
        # 사람만** - 들어와서 바로 나가고 알만 받아 가는 길을 막는다.
        prize = config.RAID_PRIZE if won else config.RAID_FAIL_PRIZE
        rank = order.index(p.uid) if p.uid in order else 99
        if won and rank < len(config.RAID_TOP_PRIZE) and p.damage > 0:
            prize += config.RAID_TOP_PRIZE[rank]
        got_egg = 0
        if won and p.counts() and rng.random() < config.RAID_EGG_CHANCE:
            try:
                eggs.give(p.uid, kind_of(row["boss"]), species=row["boss"],
                          known=True)
                got_egg = 1
            except Exception:                                   # noqa: BLE001
                got_egg = 0
        if prize:
            items.money_add(p.uid, prize)
        db.run("UPDATE raid_member SET damage=?, prize=?, got_egg=? WHERE room_id=?"
               " AND user_id=?", (p.damage, prize, got_egg, row["id"], p.uid))


# ---------------------------------------------------------------- 보여주기
def public(row, uid, now=None):
    """화면에 줄 방 상태."""
    out = {"id": row["id"], "session": row["session"], "code": row["code"],
           "host": row["host"], "state": row["state"], "result": row["result"],
           "rev": row["rev"], "round": row["round"], "boss": boss_card(row["session"]),
           "min": config.RAID_MIN_PLAYERS, "max": config.RAID_MAX_PLAYERS,
           "startsAt": time_of(row["session"]).isoformat(),
           "startsIn": seconds_to(row["session"], now)}
    ms = [m for m in members(row["id"])]
    out["members"] = [{"uid": m["user_id"], "name": m["name"], "pos": m["pos"],
                       "left": bool(m["left_at"]), "damage": m["damage"],
                       "prize": m["prize"], "egg": bool(m["got_egg"])} for m in ms]
    out["count"] = len([m for m in ms if not m["left_at"]])
    # 시작 단추를 누가 볼지는 **서버가 정한다.** 화면에서 규칙을 다시
    # 따지면 서버 판정과 어긋난다.
    ok, why = can_start(row)
    out["isHost"] = row["host"] == uid
    out["canStart"] = bool(ok and out["isHost"])
    out["startNote"] = why
    if row["data"]:
        rb = _load(row)
        i = _index_of(row, uid)
        out["battle"] = rb.view(i)
        out["events"] = json.loads(row["events"] or "[]")
        out["me"] = i
        if row["deadline"]:
            out["deadlineIn"] = max(0, int((
                datetime.datetime.fromisoformat(row["deadline"])
                - _utc(now)).total_seconds()))
    if row["state"] == "done":
        mine = next((m for m in ms if m["user_id"] == uid), None)
        if mine:
            out["reward"] = {"prize": mine["prize"], "egg": bool(mine["got_egg"]),
                             "damage": mine["damage"]}
    return out


def schedule(now=None):
    """레이드 탭 첫 화면. 다음 회차와 오늘 참가했는지."""
    key = next_key(now)
    lo, hi = period()
    return {"on": in_period(now), "start": lo, "end": hi,
            "hours": list(config.RAID_HOURS), "next": boss_card(key),
            "open": open_key(now) is not None,
            "openSec": config.RAID_OPEN_SEC, "graceSec": config.RAID_GRACE_SEC,
            "minPlayers": config.RAID_MIN_PLAYERS, "maxPlayers": config.RAID_MAX_PLAYERS,
            "minParty": config.RAID_MIN_PARTY, "teamLevel": config.RAID_TEAM_LEVEL,
            "bossLevel": config.RAID_BOSS_LEVEL, "bossEv": config.RAID_BOSS_EV,
            "revealSec": config.RAID_REVEAL_SEC,
            "rounds": config.RAID_ROUNDS,
            "roundSec": config.RAID_ROUND_SEC,
            "eggChance": config.RAID_EGG_CHANCE,
            "upcoming": [boss_card(k) for k in all_keys()
                         if time_of(k) >= kst_now(now)][:6]}


def history(uid, limit=10):
    rows = db.q(
        "SELECT r.session, r.boss, r.result, r.state, m.damage, m.prize, m.got_egg"
        " FROM raid_member m JOIN raid_room r ON r.id=m.room_id"
        " WHERE m.user_id=? AND r.state='done' ORDER BY r.id DESC LIMIT ?",
        (uid, int(limit)))
    d = deps.dex()
    out = []
    for r in rows:
        sp = d.get(r["boss"]) or {}
        out.append({"session": r["session"], "boss": r["boss"], "num": sp.get("num"),
                    "kr": sp.get("kr"), "result": r["result"], "damage": r["damage"],
                    "prize": r["prize"], "egg": bool(r["got_egg"])})
    return out


def me_card(uid, now=None):
    """/api/me 에 얹는 짧은 안내. 폴링을 새로 두지 않으려고 여기 싣는다.

    **질의는 한 번이다.** 90초마다 도는 동기화에 세 번을 더하면 Turso 에서는
    그것만으로 왕복 300ms 다. 이벤트 기간이 아니면 아예 안 묻는다.
    """
    if not in_period(now):
        return None
    r = db.q1(
        "SELECT"
        " (SELECT COUNT(*) FROM raid_member m JOIN raid_room x ON x.id=m.room_id"
        "   WHERE m.user_id=? AND m.seen=0 AND x.state='done'"
        "   AND x.result IN ('won','lost','timeout')) AS unseen,"
        " (SELECT x.id FROM raid_room x JOIN raid_member m ON m.room_id=x.id"
        "   WHERE m.user_id=? AND m.left_at IS NULL AND x.state IN ('lobby','fighting')"
        "   ORDER BY x.id DESC LIMIT 1) AS room,"
        " (SELECT 1 FROM raid_entry WHERE user_id=? AND day=?) AS played",
        (uid, uid, uid, today_kst(now)))
    key = next_key(now)
    return {"next": boss_card(key), "open": open_key(now) is not None,
            "openSec": config.RAID_OPEN_SEC,
            "unseen": (r["unseen"] if r else 0) or 0,
            "room": (r["room"] if r else None),
            "playedToday": bool(r and r["played"])}
