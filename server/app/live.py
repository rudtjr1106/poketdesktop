# -*- coding: utf-8 -*-
"""실시간 1:1 배틀 — 초대·수락·진행·기록.

친구끼리 **둘 다 접속한 채로** 두는 판이다. 지금까지의 유저 배틀은 매칭
순간 서버가 판 전체를 돌려 로그로 남기는 비동기였고(pvp + party_battle),
그건 상대가 자고 있어도 붙을 수 있어야 해서 그대로 둔다.

## 흐름

    a 가 친구를 고른다      state=invited, 60초 안에 답이 없으면 만료
    b 가 수락한다           그 순간 양쪽 팀을 읽어 판을 연다 (state=fighting)
    번갈아가 아니라 동시    둘 다 고르면 그 턴이 진행된다 (live_battle)
    끝나면                  양쪽 전적에 한 줄씩. **상금도 점수도 없다.**

**팀은 수락하는 순간 읽는다.** 초대할 때 읽으면 그 사이에 팀을 바꿔
유리하게 만들 수 있다. 랭크 팀을 등록했으면 그 팀, 아니면 바탕화면
파티다(pvp.ranked_team - 전설 제한도 그대로 걸린다). 레벨은 양쪽 다
config.LIVE_LEVEL 로 맞춘다.

## 시계가 없다

서버에 따로 도는 시계가 없다. 제한 시간이 지났는지는 **요청이 올 때** 본다
(tick). 배틀 창이 열려 있는 동안 1~2초마다 물어보므로, 한쪽이 창을 닫고
사라져도 남은 쪽의 폴링이 턴을 넘긴다.

## 겹친 요청

둘이 같은 판을 동시에 두드린다. 상태를 바꾸는 곳은 rev 로 잠그고, 부딪히면
다시 읽어서 얹는다 (레이드의 choose 와 같은 까닭).
"""
import datetime
import json
import random

from common import live_battle as LB

from . import config, db, deps, pvp, social

# 고른 것을 적다가 상대와 부딪혔을 때 다시 해보는 횟수.
ACT_TRIES = 5


def _now(now=None):
    return now or datetime.datetime.now(datetime.timezone.utc)


def _iso(now=None):
    return _now(now).replace(microsecond=0).isoformat()


def _name(uid):
    r = db.q1("SELECT username FROM users WHERE id=?", (uid,))
    return r["username"] if r else "?"


# ---------------------------------------------------------------- 찾기
def get(mid):
    return db.q1("SELECT * FROM live_match WHERE id=?", (mid,))


def side_of(row, uid):
    """이 사람이 a 인가 b 인가. 참가자가 아니면 None."""
    if row["a_id"] == uid:
        return "a"
    if row["b_id"] == uid:
        return "b"
    return None


def my_match(uid):
    """지금 걸려 있거나 싸우고 있는 판."""
    return db.q1(
        "SELECT * FROM live_match WHERE (a_id=? OR b_id=?)"
        " AND state IN ('invited','fighting') ORDER BY id DESC LIMIT 1",
        (uid, uid))


def recent(uid):
    """끝났는데 아직 결과를 안 본 판. 마지막 일격을 넣지 않은 쪽도 봐야 한다."""
    return db.q1(
        "SELECT * FROM live_match WHERE state='done'"
        " AND ((a_id=? AND a_seen=0) OR (b_id=? AND b_seen=0))"
        " AND result IN ('a','b','draw') ORDER BY id DESC LIMIT 1", (uid, uid))


def current(uid):
    """화면에 보여 줄 판. 진행 중인 것, 없으면 아직 안 본 결과."""
    return my_match(uid) or recent(uid)


def expire_old(now=None):
    """답 없는 초대와 아무도 안 돌아오는 판을 접는다."""
    cut = (_now(now) - datetime.timedelta(seconds=config.LIVE_INVITE_SEC)) \
        .replace(microsecond=0).isoformat()
    db.run("UPDATE live_match SET state='done', result='expired', updated_at=?"
           " WHERE state='invited' AND created_at < ?", (_iso(now), cut))
    cut = (_now(now) - datetime.timedelta(seconds=config.LIVE_TTL)) \
        .replace(microsecond=0).isoformat()
    db.run("UPDATE live_match SET state='done', result='expired', updated_at=?"
           " WHERE state='fighting' AND updated_at < ?", (_iso(now), cut))


# ---------------------------------------------------------------- 초대
def can_invite(uid, other):
    """지금 저 친구에게 걸 수 있나. 안 되면 까닭."""
    if uid == other:
        return "자기 자신과는 싸울 수 없습니다."
    if not db.q1("SELECT 1 x FROM users WHERE id=?", (other,)):
        return "그런 트레이너가 없습니다."
    if not social.is_friend(uid, other):
        return "친구끼리만 실시간 배틀을 할 수 있습니다."
    if social.blocked_between(uid, other):
        return "이 트레이너와는 싸울 수 없습니다."
    if not social.is_online(other):
        return "상대가 지금 접속해 있지 않습니다. 실시간 배틀은 둘 다 켜 있어야 합니다."
    if my_match(uid):
        return "이미 진행 중인 실시간 배틀이 있습니다."
    if my_match(other):
        return "상대가 다른 배틀을 하고 있습니다."
    if not pvp.ranked_team(uid):
        return "데리고 다니는 포켓몬이 없습니다."
    if not pvp.ranked_team(other):
        return "상대가 데리고 다니는 포켓몬이 없습니다."
    return None


def invite(uid, other, now=None):
    """실시간 배틀을 건다. 상대가 수락하면 그때 판이 열린다."""
    expire_old(now)
    why = can_invite(uid, other)
    if why:
        raise ValueError(why)
    cur = db.run(
        "INSERT INTO live_match (a_id, b_id, a_name, b_name, state, rev,"
        " events, turn, created_at, updated_at)"
        " VALUES (?,?,?,?,'invited',0,'[]',0,?,?)",
        (uid, other, _name(uid), _name(other), _iso(now), _iso(now)))
    return get(cur.lastrowid)


def _team(uid):
    """이 사람이 이 판에서 쓸 팀. 레벨은 맞춘다."""
    return [LB.leveled(m, config.LIVE_LEVEL) for m in pvp.ranked_team(uid)]


def accept(uid, mid, now=None):
    """초대를 받는다. **여기서 양쪽 팀을 읽고 판을 연다.**"""
    row = get(mid)
    if not row or row["b_id"] != uid:
        raise LookupError("그런 초대가 없습니다.")
    if row["state"] != "invited":
        raise ValueError("이미 끝난 초대입니다.")
    a_team, b_team = _team(row["a_id"]), _team(row["b_id"])
    if not a_team or not b_team:
        db.run("UPDATE live_match SET state='done', result='cancelled',"
               " updated_at=? WHERE id=? AND state='invited'", (_iso(now), mid))
        raise ValueError("양쪽 다 데리고 다니는 포켓몬이 있어야 합니다.")
    lb = LB.LiveBattle(deps.dex(),
                       (row["a_id"], row["a_name"], a_team),
                       (row["b_id"], row["b_name"], b_team),
                       rng=random.Random(), max_turns=config.LIVE_MAX_TURNS)
    ev = lb.start()
    cur = db.run(
        "UPDATE live_match SET state='fighting', data=?, events=?, turn=0,"
        " rev=rev+1, deadline=?, updated_at=? WHERE id=? AND rev=? AND state='invited'",
        (json.dumps(lb.dump()), json.dumps(ev), _deadline(now), _iso(now),
         mid, row["rev"]))
    if getattr(cur, "rowcount", 1) == 0:
        return get(mid)                      # 사이에 만료됐다
    return get(mid)


def answer(uid, mid, ok, now=None):
    """수락(ok=True) 또는 거절. 건 사람이 부르면 취소다."""
    row = get(mid)
    if not row or side_of(row, uid) is None:
        raise LookupError("그런 초대가 없습니다.")
    if row["state"] != "invited":
        raise ValueError("이미 끝난 초대입니다.")
    if ok:
        if row["b_id"] != uid:
            raise ValueError("받은 사람만 수락할 수 있습니다.")
        return accept(uid, mid, now)
    what = "cancelled" if row["a_id"] == uid else "declined"
    db.run("UPDATE live_match SET state='done', result=?, updated_at=?,"
           " a_seen=1, b_seen=1 WHERE id=? AND state='invited'",
           (what, _iso(now), mid))
    return get(mid)


def _deadline(now=None):
    return (_now(now) + datetime.timedelta(seconds=config.LIVE_TURN_SEC)) \
        .replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- 진행
def _load(row):
    return LB.LiveBattle.load(deps.dex(), json.loads(row["data"]))


def _save(row, lb, ev, now=None):
    """판을 적는다. rev 가 어긋나면 아무것도 안 하고 False."""
    cur = db.run(
        "UPDATE live_match SET data=?, events=?, turn=?, state=?, result=?,"
        " reason=?, rev=rev+1, deadline=?, updated_at=? WHERE id=? AND rev=?",
        (json.dumps(lb.dump()), json.dumps(ev), lb.turn,
         "done" if lb.over else "fighting", lb.result, lb.reason,
         None if lb.over else _deadline(now), _iso(now), row["id"], row["rev"]))
    ok = getattr(cur, "rowcount", 1) != 0
    if ok and lb.over:
        _record(row, lb, now)
    return ok


def act(uid, kind, value, now=None):
    """이번 턴에 할 것을 적는다. 둘 다 모이면 그 자리에서 턴이 돈다.

    **부딪히면 다시 해본다** - 둘이 같은 판을 동시에 두드리므로, rev 가
    어긋났다고 그대로 거절하면 상대가 먼저 눌렀다는 이유로 내 선택이 사라진다.
    """
    for _ in range(ACT_TRIES):
        row = my_match(uid)
        if not row or row["state"] != "fighting":
            raise LookupError("진행 중인 실시간 배틀이 없습니다.")
        lb = _load(row)
        who = side_of(row, uid)
        lb.choose(who, kind, value)
        ev = None
        if lb.ready():
            ev = lb.resolve()
        if _save(row, lb, ev if ev is not None else json.loads(row["events"]), now):
            return get(row["id"])
    raise RuntimeError("상대가 먼저 움직였습니다. 다시 불러오세요.")


def tick(row, now=None):
    """제한 시간이 지났으면 턴을 돌린다. 요청이 올 때마다 본다."""
    if not row:
        return row
    if row["state"] == "invited":
        born = row["created_at"]
        if born and _iso(now) > _add(born, config.LIVE_INVITE_SEC):
            db.run("UPDATE live_match SET state='done', result='expired',"
                   " updated_at=? WHERE id=? AND state='invited'", (_iso(now), row["id"]))
            return get(row["id"])
        return row
    if row["state"] != "fighting" or not row["deadline"]:
        return row
    if _now(now) < datetime.datetime.fromisoformat(row["deadline"]):
        return row
    lb = _load(row)
    if lb.over:
        return row
    ev = lb.resolve()
    _save(row, lb, ev, now)
    return get(row["id"])


def _add(iso, seconds):
    try:
        t = datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso
    return (t + datetime.timedelta(seconds=seconds)).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- 기록
def _record(row, lb, now=None):
    """양쪽 전적에 한 줄씩. **상금도 점수도 없다** (사용자가 정했다).

    두 번 쓰지 않게 이미 있는지 보고 넣는다 - rev 로 막혀 있지만, 전적이
    두 줄이 되면 사용자가 바로 알아챈다.
    """
    # **먼저 찍고 그다음에 쓴다.** 두 요청이 겹쳐도 한 번만 들어간다.
    cur = db.run("UPDATE live_match SET recorded=1 WHERE id=? AND recorded=0",
                 (row["id"],))
    if getattr(cur, "rowcount", 1) == 0:
        return
    for who in ("a", "b"):
        uid = row["%s_id" % who]
        foe = row["%s_id" % ("b" if who == "a" else "a")]
        foe_name = row["%s_name" % ("b" if who == "a" else "a")]
        me, other = lb.side(who), lb.side("b" if who == "a" else "a")
        db.run(
            "INSERT INTO battle_record (user_id, foe_id, foe_name, kind, result,"
            " rating, delta, reward, turns, my_left, foe_left, lead, foe_lead,"
            " match_id, started, ended_at, rp, rp_delta)"
            " VALUES (?,?,?,'live',?,0,0,0,?,?,?,?,?,NULL,?,?,0,0)",
            (uid, foe, foe_name, lb.outcome(who) or "draw", lb.turn,
             lb.left(who), lb.left("b" if who == "a" else "a"),
             me.team[0].name if me.team else "",
             other.team[0].name if other.team else "",
             1 if who == "a" else 0, _iso(now)))


def mark_seen(uid, now=None):
    """끝난 판의 결과를 화면에 알렸다."""
    db.run("UPDATE live_match SET a_seen=1 WHERE a_id=? AND state='done'", (uid,))
    db.run("UPDATE live_match SET b_seen=1 WHERE b_id=? AND state='done'", (uid,))


def unseen(uid):
    r = db.q1("SELECT COUNT(*) c FROM live_match WHERE state='done'"
              " AND result IN ('a','b','draw')"
              " AND ((a_id=? AND a_seen=0) OR (b_id=? AND b_seen=0))", (uid, uid))
    return (r["c"] if r else 0) or 0


# ---------------------------------------------------------------- 보여주기
def public(row, uid, now=None):
    """그 사람 시점의 판. 없으면 None."""
    if not row:
        return None
    who = side_of(row, uid)
    if who is None:
        return None
    foe = "b" if who == "a" else "a"
    out = {"id": row["id"], "state": row["state"], "rev": row["rev"],
           "turn": row["turn"], "me": who, "mine": row["a_id"] == uid,
           "foeId": row["%s_id" % foe], "foeName": row["%s_name" % foe],
           "level": config.LIVE_LEVEL, "turnSec": config.LIVE_TURN_SEC,
           "inviteSec": config.LIVE_INVITE_SEC}
    if row["state"] == "invited":
        out["inviteLeft"] = max(0, int((
            datetime.datetime.fromisoformat(_add(row["created_at"],
                                                 config.LIVE_INVITE_SEC))
            - _now(now)).total_seconds()))
    if row["data"]:
        lb = _load(row)
        out["battle"] = lb.view(who)
        out["events"] = lb.events_for(who, json.loads(row["events"] or "[]"))
        if row["deadline"] and row["state"] == "fighting":
            out["deadlineIn"] = max(0, int((
                datetime.datetime.fromisoformat(row["deadline"])
                - _now(now)).total_seconds()))
    if row["state"] == "done":
        out["result"] = row["result"]
        out["reason"] = row["reason"]
        if row["result"] in ("a", "b", "draw"):
            out["outcome"] = ("draw" if row["result"] == "draw"
                              else ("win" if row["result"] == who else "lose"))
    return out


def me_card(uid, now=None):
    """/api/me 에 얹는 짧은 안내. 폴링을 새로 두지 않으려고 여기 싣는다.

    **질의는 두 번이다** (진행 중인 판, 안 본 결과). 실시간 배틀은 상대가
    기다리고 있으므로 90초마다 오는 동기화로라도 알려야 한다.
    """
    row = my_match(uid)
    out = {"unseen": unseen(uid)}
    if not row:
        return out if out["unseen"] else None
    out["id"] = row["id"]
    out["state"] = row["state"]
    out["foeName"] = row["b_name"] if row["a_id"] == uid else row["a_name"]
    # 걸려온 초대인가 (내가 답해야 하는가)
    out["invited"] = row["state"] == "invited" and row["b_id"] == uid
    return out
