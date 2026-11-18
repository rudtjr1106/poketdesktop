# -*- coding: utf-8 -*-
"""액션 배틀 (2.6.0) — 도전 · 수락 · 입장권 · 기록 · 정리.

친구나 같은 길드원끼리 키보드로 하는 실시간 대전이다. 판은 서버가 30번/초로 굴리고(action_ws 의 방), 웹 화면이
그린다 (server/web/action, /action/play). 여기는 판 밖의 일이다 - 표 action_match 의 한 줄이 한 판이다.

## 흐름

    a 가 건다               state=invited, 받는 사람에게 ask. ACTION_INVITE_SEC 안에 답이 없으면 expired
    b 가 받는다             그 순간 두 팀을 읽어 Lv.50 으로 맞춰 data 에 둔다 (state=open). 건 사람에게 open
    둘 다 입장권을 받는다    앱이 창을 띄우며 주소 조각(#)으로 넘긴다 - 그 판의 두 사람만 · 한 번만 · 60초 안에만
    둘 다 들어오면          방이 판을 굴린다 (state=fighting). 받은 뒤 ACTION_JOIN_SEC 안에 못 오면 기록 없이 aborted
    끝나면                  양쪽 전적에 한 줄씩 (kind='action'). **상금도 점수도 없다** (실시간 배틀과 같다)

**팀은 받는 순간 읽는다** (live 와 같은 까닭 - 걸어 놓고 팀을 바꿔 유리하게 만들지 못하게). 랭크 팀, 없으면 바탕화면
파티의 앞 6마리다. 판이 열리면 그중 3마리를 고른다.

## 한 사람은 한 번에 한 판

걸어 둔 도전도 판으로 센다 (실시간 배틀과 같다). 도전을 넣는 문장 하나가 '둘 다 살아 있는 줄이 없을 때만' 넣으므로
동시에 걸어도 한 사람에게 살아 있는 줄은 하나뿐이다. 실시간 배틀 · 챔피언리그 · 친선전과도 겹치지 않는다 - 이쪽은
live.my_match 를 보고, 저쪽은 live.BUSY 에 건 busy 를 본다 (live.other_busy).

## 시간

서버에 따로 도는 시계가 없다 (live 와 같다). 살아 있는 줄은 시각으로 가린다 (my_match) - 시간이 지난 줄은 치우기
전에도 걸린 것으로 안 본다. 치우기(expire_old)는 요청이 올 때 하고, 그때 알림도 보낸다. 들어오기를 기다리는 판은
방이 자기 시계로 접는다 - OPEN_TTL 은 방이 아예 안 생긴 판을 치우는 여유다.

## 알림

    visit.push(uid, {"t": "action", "s": ..., "id": 판})
        ask       도전이 왔다 (받는 사람)
        open      받았다 - 판이 열렸다, 창을 띄운다 (건 사람. 받은 사람은 답으로 판을 받는다)
        declined  거절했다 (건 사람)
        gone      건 사람이 거뒀다 · 도전이 만료됐다 (받는 사람)
        over      판이 끝났다 · 접혔다 - 정리한다 (둘 다. 만료된 도전이면 건 사람)

판은 싣지 않는다 - 받은 앱이 GET /api/action 을 한 번 묻는다 (live._poke 와 같다). 소켓이 끊겨 있었으면 /api/me 의
action(me_card)이 받친다.

## 입장권

창을 띄우는 앱이 POST /api/action/{판}/ticket 으로 받아 주소 조각(#m=..&t=..)으로 넘기고, 웹 화면이 /ws/action 의
**첫 메시지로만** 보낸다 (주소 쿼리나 머리말에 실으면 Caddy · uvicorn 로그에 남는다). 메모리에만 둔다 - 서버가
다시 켜지면 판도 없어지므로 같이 없어져도 된다. 한 사람이 새로 받으면 그 판의 앞 입장권은 버린다.
"""
import datetime
import json
import secrets
import threading
import time

from common import pokelogic as P

from . import config, db, live, pvp, social, visit

LEVEL = 50                   # 판의 레벨 (엔진 common/action_battle.LEVEL 과 같다)
TEAM_MAX = 6                 # 받는 순간 읽어 두는 마리 수 - 판이 열리면 이 가운데 3마리를 고른다
OPEN_TTL = config.ACTION_JOIN_SEC + 15     # 열린 판이 이만큼 지나도 안 바뀌었으면 방이 없는 것이다 - 접는다
FIGHT_TTL = 900              # 싸우는 판은 길어야 4분이다. 이만큼 안 바뀌었으면 방이 없어진 것이다 - 접는다
ALIVE = ("invited", "open", "fighting")
ROOMS_FULL = "지금은 액션 배틀 방이 다 찼습니다. 잠시 뒤에 다시 해 주세요."

_lock = threading.Lock()
_tickets = {}                # {입장권: (판, 사람, a|b, 만료 - time.monotonic)}


def _now(now=None):
    return now or datetime.datetime.now(datetime.timezone.utc)


def _iso(now=None):
    return _now(now).replace(microsecond=0).isoformat()


def _ago(seconds, now=None):
    return _iso(_now(now) - datetime.timedelta(seconds=seconds))


def _name(uid):
    r = db.q1("SELECT username FROM users WHERE id=?", (uid,))
    return r["username"] if r else "?"


def _poke(uid, s, mid):
    """그 사람 앱에 '액션 배틀이 바뀌었다' 를 민다 (놀러 가기 소켓). 못 가도 판은 그대로다."""
    try:
        visit.push(uid, {"t": "action", "s": s, "id": mid})
    except Exception:                                       # noqa: BLE001
        pass


# ---------------------------------------------------------------- 찾기
def get(mid):
    return db.q1("SELECT * FROM action_match WHERE id=?", (mid,))


def side_of(row, uid):
    """이 사람이 a(건 쪽)인가 b(받은 쪽)인가. 참가자가 아니면 None."""
    if row["a_id"] == uid:
        return "a"
    if row["b_id"] == uid:
        return "b"
    return None


def _cuts(now=None):
    """(도전 · 열린 판 · 싸우는 판) 이 살아 있다고 보는 가장 이른 시각."""
    return _ago(config.ACTION_INVITE_SEC, now), _ago(OPEN_TTL, now), _ago(FIGHT_TTL, now)


def my_match(uid, now=None):
    """걸려 있거나(invited) 열렸거나(open) 싸우는(fighting) 판. 시간이 지난 줄은 치우기 전에도 안 본다."""
    return db.q1(
        "SELECT * FROM action_match WHERE (a_id=? OR b_id=?) AND ((state='invited' AND created_at >= ?)"
        " OR (state='open' AND updated_at >= ?) OR (state='fighting' AND updated_at >= ?))"
        " ORDER BY id DESC LIMIT 1", (uid, uid) + _cuts(now))


def busy(uid):
    """액션 배틀에 걸려 있거나 싸우는 중인가 (live.BUSY - 실시간 배틀 · 챔피언리그 · 친선전이 본다)."""
    return my_match(uid) is not None


if busy not in live.BUSY:
    live.BUSY.append(busy)


def rooms_in_use():
    """열렸거나 싸우는 판 수 (config.ACTION_ROOMS 까지)."""
    return db.q1("SELECT COUNT(*) n FROM action_match WHERE state IN ('open','fighting')")["n"]


def expire_old(now=None):
    """시간이 지난 줄을 접는다: 답 없는 도전은 expired, 아무도 안 온 판(noshow) · 방이 없어진 판(stale)은 aborted."""
    inv, opn, fgt = _cuts(now)
    for r in db.q("SELECT * FROM action_match WHERE (state='invited' AND created_at < ?)"
                  " OR (state='open' AND updated_at < ?) OR (state='fighting' AND updated_at < ?)",
                  (inv, opn, fgt)):
        if r["state"] != "invited":
            abort(r["id"], "noshow" if r["state"] == "open" else "stale", now)
        elif _end(r["id"], "invited", "expired", now):
            _poke(r["b_id"], "gone", r["id"])
            _poke(r["a_id"], "over", r["id"])


def _end(mid, frm, state, now=None, result=None, reason=None):
    """frm 상태(하나 또는 여럿)인 판을 끝나는 상태로. 다 쓴 팀(data)은 지운다. 사이에 바뀌었으면 False."""
    frm = (frm,) if isinstance(frm, str) else tuple(frm)
    cur = db.run("UPDATE action_match SET state=?, result=?, reason=?, data=NULL, updated_at=?"
                 " WHERE id=? AND state IN (%s)" % ",".join("?" * len(frm)),
                 (state, result, reason, _iso(now), mid) + frm)
    return cur.rowcount == 1


# ---------------------------------------------------------------- 도전
def can_invite(uid, other, now=None):
    """지금 저 사람에게 걸 수 있나. 안 되면 까닭."""
    if uid == other:
        return "자기 자신과는 싸울 수 없습니다."
    if not db.q1("SELECT 1 x FROM users WHERE id=?", (other,)):
        return "그런 트레이너가 없습니다."
    if not social.is_friend(uid, other) and not live._same_guild(uid, other):
        return "친구나 같은 길드원끼리만 액션 배틀을 할 수 있습니다."
    if social.blocked_between(uid, other):
        return "이 트레이너와는 싸울 수 없습니다."
    if not visit.online(other):
        return "상대가 지금 접속해 있지 않습니다. 액션 배틀은 둘 다 앱을 켜 두어야 합니다."
    if not visit.has_cap(other, "action"):
        return "상대 앱이 아직 액션 배틀을 모릅니다. 상대가 앱을 새 판으로 올려야 합니다."
    if my_match(uid, now) or live.my_match(uid):
        return "이미 진행 중인 배틀이 있습니다."
    if my_match(other, now) or live.my_match(other):
        return "상대가 다른 배틀을 하고 있습니다."
    mine = pvp.ranked_team(uid)
    if not mine:
        return "데리고 다니는 포켓몬이 없습니다."
    if not pvp.ranked_team(other):
        return "상대가 데리고 다니는 포켓몬이 없습니다."
    # 같은 도구는 한 팀에 한 마리 (2.0.2) - 거는 사람만 막는다. 받는 쪽은 판에서만 뺀다 (_team, live 와 같다)
    why = pvp.held_why(mine, "랭크 팀" if pvp.team_ids(uid) else "바탕화면 파티")
    if why:
        return why
    if rooms_in_use() >= config.ACTION_ROOMS:
        return ROOMS_FULL
    return None


def invite(uid, other, now=None):
    """액션 배틀을 건다. 상대가 받으면 그때 판이 열린다."""
    expire_old(now)
    why = can_invite(uid, other, now)
    if why:
        raise ValueError(why)
    # 둘 다 살아 있는 줄이 없을 때만 넣는다 - 확인과 넣기를 한 문장으로 (두 사람이 같은 사람에게 동시에 걸어도 하나만)
    cur = db.run(
        "INSERT INTO action_match (a_id, b_id, a_name, b_name, state, created_at, updated_at)"
        " SELECT ?,?,?,?,'invited',?,? WHERE NOT EXISTS (SELECT 1 FROM action_match"
        " WHERE state IN ('invited','open','fighting') AND (a_id IN (?,?) OR b_id IN (?,?)))",
        (uid, other, _name(uid), _name(other), _iso(now), _iso(now), uid, other, uid, other))
    if cur.rowcount != 1:
        raise ValueError("둘 중 한 사람이 방금 다른 배틀을 시작했습니다.")
    _poke(other, "ask", cur.lastrowid)
    return get(cur.lastrowid)


def _team(uid):
    """이 판에서 쓸 팀: 랭크 팀(없으면 바탕화면 파티)의 앞 TEAM_MAX 마리를 Lv.50 으로. 개체값 · 노력치 · 성격 ·
    도구 · 기술은 그대로다. 같은 도구는 앞의 한 마리만 지닌 셈으로 (live._team 과 같다)."""
    return [P.at_level(m, LEVEL) for m in pvp.strip_held(pvp.ranked_team(uid))[0][:TEAM_MAX]]


def answer(uid, mid, ok, now=None):
    """받기(ok=True) 또는 거절. 건 사람이 부르면 거두기다."""
    expire_old(now)
    row = get(mid)
    if not row or side_of(row, uid) is None:
        raise LookupError("그런 도전이 없습니다.")
    if row["state"] != "invited":
        raise ValueError("이미 끝난 도전입니다.")
    if not ok:
        return _withdraw(uid, row, now)
    if row["b_id"] != uid:
        raise ValueError("받은 사람만 수락할 수 있습니다.")
    return _accept(row, now)


def cancel(uid, mid, now=None):
    """도전을 거둔다 (건 사람). 받은 사람이 부르면 거절이다 - answer(..., False) 와 같다."""
    return answer(uid, mid, False, now)


def _withdraw(uid, row, now=None):
    what = "cancelled" if row["a_id"] == uid else "declined"
    if _end(row["id"], "invited", what, now):
        if what == "cancelled":
            _poke(row["b_id"], "gone", row["id"])
        else:
            _poke(row["a_id"], "declined", row["id"])
    return get(row["id"])


def _accept(row, now=None):
    """받는다. **여기서 두 팀을 읽어 판을 연다** (state=open - 둘이 들어오기를 기다린다)."""
    uid = row["b_id"]
    # 받는 사람도 그 자리에서 누른다 - 같은 도구가 겹치면 막고 알린다 (live.answer 와 같다, 도전은 그대로 둔다)
    why = pvp.held_why(pvp.ranked_team(uid), "랭크 팀" if pvp.team_ids(uid) else "바탕화면 파티")
    if why:
        raise ValueError(why)
    if rooms_in_use() >= config.ACTION_ROOMS:
        raise ValueError(ROOMS_FULL)
    a_team, b_team = _team(row["a_id"]), _team(uid)
    if not a_team or not b_team:
        if _end(row["id"], "invited", "cancelled", now):
            _poke(row["a_id"], "over", row["id"])
        raise ValueError("양쪽 다 데리고 다니는 포켓몬이 있어야 합니다.")
    data = {"a": a_team, "b": b_team, "seed": secrets.randbelow(2 ** 31)}
    cur = db.run("UPDATE action_match SET state='open', data=?, updated_at=? WHERE id=? AND state='invited'",
                 (json.dumps(data, ensure_ascii=False), _iso(now), row["id"]))
    if cur.rowcount != 1:
        raise ValueError("이미 끝난 도전입니다.")
    _poke(row["a_id"], "open", row["id"])
    return get(row["id"])


# ---------------------------------------------------------------- 입장권
def ticket(uid, mid, now=None, clock=None):
    """그 판에 들어갈 입장권 (한 번만 · ACTION_TICKET_SEC 안에만). (입장권, 웹 화면 주소 - 서버 주소에 붙인다).

    없는 판은 LookupError, 남의 판은 PermissionError, 들어갈 수 없는 판(아직 안 받았다 · 끝났다)은 ValueError.
    싸우는 중에도 준다 - 창이 닫혔으면 ACTION_GRACE 안에 다시 들어와 이어 한다.
    """
    row = get(mid)
    if not row:
        raise LookupError("그런 판이 없습니다.")
    side = side_of(row, uid)
    if side is None:
        raise PermissionError("내 판이 아닙니다.")
    cur = my_match(uid, now)
    if not cur or cur["id"] != mid or cur["state"] not in ("open", "fighting"):
        raise ValueError("들어갈 수 있는 판이 아닙니다.")
    clock = time.monotonic() if clock is None else clock
    t = secrets.token_urlsafe(24)
    with _lock:
        for k, v in list(_tickets.items()):
            if v[3] <= clock or v[:2] == (mid, uid):          # 지난 것 · 이 사람이 이 판에 받아 둔 앞의 것
                del _tickets[k]
        _tickets[t] = (mid, uid, side, clock + config.ACTION_TICKET_SEC)
    return t, "/action/play#m=%d&t=%s" % (mid, t)


def redeem(t, clock=None):
    """입장권을 쓴다 -> (판, 사람, a|b). 없거나 지났거나 이미 썼으면 None. 한 번 보면 없어진다."""
    if not isinstance(t, str):
        return None
    clock = time.monotonic() if clock is None else clock
    with _lock:
        got = _tickets.pop(t, None)
    if not got or got[3] <= clock:
        return None
    return got[:3]


# ---------------------------------------------------------------- 판 (방이 부른다)
def start_fight(mid, now=None):
    """둘 다 들어왔다: open -> fighting. 사이에 접혔으면 False (방은 판을 열지 않는다)."""
    cur = db.run("UPDATE action_match SET state='fighting', updated_at=? WHERE id=? AND state='open'",
                 (_iso(now), mid))
    return cur.rowcount == 1


def finish(mid, winner, reason, left, lead, secs=0, now=None):
    """판이 끝났다: 결과를 적고 전적을 남기고 둘 다에게 over. 이미 끝났거나 접힌 판이면 아무것도 안 하고 False.

    winner a / b / draw · reason ko / timeout / forfeit · left {a|b: 남은 마리} · lead {a|b: 선봉 이름} ·
    secs = 싸움이 이어진 초 (ActionBattle.fight_secs).
    """
    if not _end(mid, "fighting", "done", now, result=winner, reason=reason):
        return False
    row = get(mid)
    _record(row, left, lead, secs, now)
    for u in (row["a_id"], row["b_id"]):
        _poke(u, "over", mid)
    return True


def abort(mid, reason, now=None):
    """판을 기록 없이 접는다 (noshow · error · stale · cancel). 접었으면 True."""
    row = get(mid)
    if not row or not _end(mid, ALIVE, "aborted", now, reason=reason):
        return False
    for u in (row["a_id"], row["b_id"]):
        _poke(u, "over", mid)
    return True


def abort_all(now=None):
    """서버가 뜰 때: 판은 메모리(방)에 있었다 - 끝나지 않은 줄은 전부 기록 없이 접는다. 접은 수."""
    cur = db.run("UPDATE action_match SET state='aborted', reason='restart', data=NULL, updated_at=?"
                 " WHERE state IN ('invited','open','fighting')", (_iso(now),))
    return cur.rowcount


def _outcome(result, who):
    if result not in ("a", "b", "draw"):
        return None
    return "draw" if result == "draw" else ("win" if result == who else "lose")


def _record(row, left, lead, secs=0, now=None):
    """양쪽 전적에 한 줄씩 (live._record 와 같은 모양). **먼저 찍고 그다음에 쓴다** - 두 번 불러도 한 번만.

    액션 배틀에는 턴이 없다 - turns 칸에는 싸움이 이어진 초를 적는다 (대전 기록 창이 kind 를 보고 'N초' 로 쓴다).
    """
    cur = db.run("UPDATE action_match SET recorded=1 WHERE id=? AND recorded=0", (row["id"],))
    if cur.rowcount != 1:
        return
    for who, foe in (("a", "b"), ("b", "a")):
        db.run(
            "INSERT INTO battle_record (user_id, foe_id, foe_name, kind, result,"
            " rating, delta, reward, turns, my_left, foe_left, lead, foe_lead,"
            " match_id, started, ended_at, rp, rp_delta)"
            " VALUES (?,?,?,'action',?,0,0,0,?,?,?,?,?,NULL,?,?,0,0)",
            (row["%s_id" % who], row["%s_id" % foe], row["%s_name" % foe], _outcome(row["result"], who),
             max(0, int(secs or 0)),
             int(left.get(who) or 0), int(left.get(foe) or 0), lead.get(who) or "", lead.get(foe) or "",
             1 if who == "a" else 0, _iso(now)))


# ---------------------------------------------------------------- 보여주기
def public(row, uid):
    """그 사람 시점의 판 M. 참가자가 아니면 None. result 는 내 기준 win / lose / draw (끝난 판만)."""
    who = side_of(row, uid)
    if who is None:
        return None
    foe = "b" if who == "a" else "a"
    return {"id": row["id"], "state": row["state"],
            "foe": {"id": row["%s_id" % foe], "name": row["%s_name" % foe]},
            "mine": who == "a", "result": _outcome(row["result"], who), "reason": row["reason"],
            "created": row["created_at"]}


def state(uid, now=None):
    """GET /api/action: 내 판(건 도전 · 열린 판 · 싸우는 판)과 받은 도전."""
    row = my_match(uid, now)
    if row and row["state"] == "invited" and row["b_id"] == uid:
        return {"match": None, "incoming": [public(row, uid)]}
    return {"match": public(row, uid) if row else None, "incoming": []}


def me_card(uid, now=None):
    """/api/me 에 얹는 짧은 안내 (앱이 소켓이 끊겨 있던 동안의 알림을 따라잡는다). 없으면 None.

    s = ask (받은 도전 - 답해야 한다) · wait (건 도전 - 기다린다) · open (판이 열렸다 · 싸우는 중 - 창을 띄운다).
    """
    row = my_match(uid, now)
    if not row:
        return None
    if row["state"] == "invited":
        s = "ask" if row["b_id"] == uid else "wait"
    else:
        s = "open"
    return {"id": row["id"], "state": row["state"], "s": s}
