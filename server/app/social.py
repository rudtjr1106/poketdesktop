# -*- coding: utf-8 -*-
"""친구 — 찾기, 신청, 수락, 삭제, 차단.

관계를 **한 행**으로 둔다. 항상 작은 id 가 a_id 다. 양쪽에 한 행씩
두는 쪽이 조회는 쉽지만, db.run 은 한 문장씩 커밋이라 두 문장을 쓰는
중에 끊기면 한쪽만 남는다. Turso 는 끊기는 게 전제인 환경이라(그래서
3회 재시도가 있다) 그 반쪽 상태를 풀 방법이 없다. 한 행이면 애초에
어긋날 수가 없다.

차단만 비대칭이다 — 내가 저 사람을 차단하는 것이지 서로가 아니다.

**계정을 캐낼 수 없게 한다.** 닉네임은 정확히 맞아야만 찾아지고,
차단당했는지 차단했는지는 구분해서 알려주지 않으며, 없는 신청을
수락하려 하면 관계가 없을 때와 같은 말을 돌려준다.
"""
import datetime

from fastapi import HTTPException

from . import db

MAX_FRIENDS = 30
MAX_PENDING = 10           # 동시에 보내 둘 수 있는 신청 수
REJECT_COOLDOWN_H = 24     # 거절당한 뒤 다시 보낼 수 있을 때까지
ONLINE_WINDOW = 180        # 이 초 안에 서버에 말을 걸었으면 접속 중으로 본다
SEARCH_PER_MIN = 20


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(t=None):
    return (t or _now()).isoformat()


def _pair(x, y):
    """항상 작은 쪽이 앞. 관계 한 행의 자리를 정한다."""
    return (x, y) if x < y else (y, x)


# ---------------------------------------------------------------- 조회
def _row(me, other):
    a, b = _pair(me, other)
    return db.q1("SELECT * FROM friend WHERE a_id=? AND b_id=?", (a, b))


def blocked_between(me, other):
    """어느 쪽으로든 차단이 있는가. 어느 쪽인지는 알려주지 않는다."""
    r = db.q1("SELECT 1 x FROM friend_block WHERE (user_id=? AND target_id=?)"
              " OR (user_id=? AND target_id=?) LIMIT 1",
              (me, other, other, me))
    return r is not None


def relation(me, other):
    """none / self / friend / incoming / outgoing / rejected / blocked."""
    if me == other:
        return "self"
    if db.q1("SELECT 1 x FROM friend_block WHERE user_id=? AND target_id=?",
             (me, other)):
        return "blocked"
    if db.q1("SELECT 1 x FROM friend_block WHERE user_id=? AND target_id=?",
             (other, me)):
        # 내가 차단당했다는 것도 '차단' 으로만 말한다. 구분해서 알려주면
        # 상대가 나를 차단했는지를 알아낼 수 있다.
        return "blocked"
    r = _row(me, other)
    if not r:
        return "none"
    if r["state"] == "accepted":
        return "friend"
    if r["state"] == "rejected":
        return "rejected"
    return "outgoing" if r["asked_by"] == me else "incoming"


def is_friend(me, other):
    r = _row(me, other)
    return bool(r and r["state"] == "accepted")


def _online_map(ids):
    """여러 명의 접속 여부를 한 번에. 한 명씩 물어보면 안 된다."""
    if not ids:
        return {}
    cut = _iso(_now() - datetime.timedelta(seconds=ONLINE_WINDOW))
    marks = ",".join("?" * len(ids))
    rows = db.q("SELECT user_id, MAX(last_seen) seen FROM sessions"
                " WHERE user_id IN (%s) GROUP BY user_id" % marks, tuple(ids))
    return dict((r["user_id"], (r["seen"], r["seen"] >= cut)) for r in rows)


def is_online(uid):
    m = _online_map([uid])
    return bool(m.get(uid, ("", False))[1])


def _names(ids):
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return dict((r["id"], r["username"]) for r in
                db.q("SELECT id, username FROM users WHERE id IN (%s)" % marks,
                     tuple(ids)))


def _stats(ids):
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return dict((r["user_id"], r) for r in
                db.q("SELECT * FROM rank_stat WHERE user_id IN (%s)" % marks,
                     tuple(ids)))


def listing(uid):
    """친구 목록 화면에 필요한 것 전부.

    쿼리 넷으로 끝난다 — 관계 한 번, 이름 한 번, 접속 한 번, 점수 한 번.
    친구마다 한 번씩 물어보면 서른 명이면 서른 번이 된다.
    """
    rows = db.q("SELECT * FROM friend WHERE a_id=? OR b_id=?", (uid, uid))
    blocks = db.q("SELECT * FROM friend_block WHERE user_id=?", (uid,))

    friends, incoming, outgoing = [], [], []
    ids = set(b["target_id"] for b in blocks)
    for r in rows:
        other = r["b_id"] if r["a_id"] == uid else r["a_id"]
        ids.add(other)
        if r["state"] == "accepted":
            friends.append((other, r))
        elif r["state"] == "pending":
            (outgoing if r["asked_by"] == uid else incoming).append((other, r))

    names = _names(list(ids))
    online = _online_map([o for o, _ in friends])
    stats = _stats([o for o, _ in friends])

    def brief(other, r):
        st = stats.get(other)
        seen, on = online.get(other, (None, False))
        out = {"id": other, "name": names.get(other, "?"), "online": on,
               "lastSeen": seen, "since": r["decided_at"] or r["created_at"]}
        if st:
            out.update({"rating": st["rating"], "ranked": bool(st["ranked"]),
                        "wins": st["wins"], "losses": st["losses"],
                        "draws": st["draws"],
                        "friendWins": st["fr_wins"],
                        "friendLosses": st["fr_losses"]})
        return out

    return {
        "friends": sorted([brief(o, r) for o, r in friends],
                          key=lambda x: (not x["online"], x["name"])),
        "incoming": [{"id": o, "name": names.get(o, "?"), "at": r["created_at"]}
                     for o, r in incoming],
        "outgoing": [{"id": o, "name": names.get(o, "?"), "at": r["created_at"]}
                     for o, r in outgoing],
        "blocked": [{"id": b["target_id"],
                     "name": names.get(b["target_id"], "?"),
                     "at": b["created_at"]} for b in blocks],
        "limits": {"maxFriends": MAX_FRIENDS, "maxPending": MAX_PENDING,
                   "onlineWindow": ONLINE_WINDOW},
    }


def find(uid, name):
    """닉네임으로 한 명 찾기. **정확히 맞아야 한다.**

    앞글자만으로 찾게 하면 남의 계정 목록을 훑을 수 있다. 친구를 부르려면
    이름을 이미 알고 있어야 하므로 정확 일치로 충분하다.
    """
    name = (name or "").strip()
    if not name:
        return {"found": False}
    u = db.q1("SELECT id, username FROM users WHERE username=? COLLATE NOCASE",
              (name,))
    if not u:
        return {"found": False}
    st = _stats([u["id"]]).get(u["id"])
    out = {"found": True, "id": u["id"], "name": u["username"],
           "online": is_online(u["id"]), "relation": relation(uid, u["id"])}
    if st:
        out.update({"rating": st["rating"], "ranked": bool(st["ranked"]),
                    "wins": st["wins"], "losses": st["losses"]})
    return out


def _count_friends(uid):
    return db.q1("SELECT COUNT(*) c FROM friend WHERE state='accepted'"
                 " AND (a_id=? OR b_id=?)", (uid, uid))["c"]


def _count_pending(uid):
    return db.q1("SELECT COUNT(*) c FROM friend WHERE state='pending'"
                 " AND asked_by=?", (uid,))["c"]


# ---------------------------------------------------------------- 바꾸기
def request(uid, name):
    """닉네임으로 친구 신청. id 로는 받지 않는다 — 번호를 훑을 수 있다."""
    u = db.q1("SELECT id, username FROM users WHERE username=? COLLATE NOCASE",
              ((name or "").strip(),))
    if not u:
        raise HTTPException(404, "그런 닉네임의 트레이너가 없습니다.")
    other = u["id"]
    if other == uid:
        raise HTTPException(400, "자기 자신에게는 신청할 수 없습니다.")
    if blocked_between(uid, other):
        # 내가 차단했는지 당했는지 구분해 주지 않는다.
        raise HTTPException(403, "이 트레이너에게는 신청할 수 없습니다.")

    r = _row(uid, other)
    if r and r["state"] == "accepted":
        raise HTTPException(409, "이미 친구입니다.")
    if r and r["state"] == "pending":
        if r["asked_by"] == uid:
            raise HTTPException(409, "이미 신청을 보냈습니다.")
        # 상대가 먼저 보내 뒀다. 그럼 이건 수락이다.
        return accept(uid, other)
    if r and r["state"] == "rejected":
        # 거절당한 직후 다시 보내는 걸 막는다. 거절이 곧 잠깐의 차단이 된다.
        when = r["decided_at"] and _parse(r["decided_at"])
        if when and (_now() - when).total_seconds() < REJECT_COOLDOWN_H * 3600:
            raise HTTPException(
                429, "거절된 신청은 %d시간 뒤에 다시 보낼 수 있습니다."
                     % REJECT_COOLDOWN_H)

    if _count_friends(uid) >= MAX_FRIENDS:
        raise HTTPException(429, "친구는 %d명까지 둘 수 있습니다." % MAX_FRIENDS)
    if _count_pending(uid) >= MAX_PENDING:
        raise HTTPException(429, "보낸 신청이 %d건을 넘었습니다." % MAX_PENDING)

    a, b = _pair(uid, other)
    db.run("INSERT INTO friend (a_id, b_id, state, asked_by, created_at)"
           " VALUES (?,?,'pending',?,?)"
           " ON CONFLICT(a_id, b_id) DO UPDATE SET state='pending',"
           " asked_by=?, created_at=?, decided_at=NULL",
           (a, b, uid, _iso(), uid, _iso()))
    return {"state": "pending", "id": other, "name": u["username"],
            "message": "%s 님에게 친구 신청을 보냈습니다." % u["username"]}


def _parse(s):
    try:
        return datetime.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def accept(uid, other):
    r = _row(uid, other)
    # 관계가 없을 때와 내가 보낸 신청일 때를 같은 말로 막는다.
    if not r or r["state"] != "pending" or r["asked_by"] == uid:
        raise HTTPException(404, "그런 신청이 없습니다.")
    if _count_friends(uid) >= MAX_FRIENDS:
        raise HTTPException(429, "친구는 %d명까지 둘 수 있습니다." % MAX_FRIENDS)
    if _count_friends(other) >= MAX_FRIENDS:
        raise HTTPException(429, "상대의 친구가 가득 찼습니다.")
    a, b = _pair(uid, other)
    db.run("UPDATE friend SET state='accepted', decided_at=?"
           " WHERE a_id=? AND b_id=? AND state='pending'", (_iso(), a, b))
    nm = _names([other]).get(other, "?")
    return {"state": "accepted", "id": other, "name": nm,
            "message": "%s 님과 친구가 되었습니다." % nm}


def remove(uid, other):
    """거절 · 취소 · 삭제를 하나로.

    받은 신청을 지울 때만 rejected 로 남긴다. 재신청 쿨다운이 걸려야
    거절하자마자 다시 오는 걸 막을 수 있다. 나머지는 행을 지운다 —
    내가 취소한 것이나 친구를 끊은 것에 흔적을 남길 이유가 없다.
    """
    r = _row(uid, other)
    if not r:
        raise HTTPException(404, "그런 관계가 없습니다.")
    a, b = _pair(uid, other)
    if r["state"] == "pending" and r["asked_by"] != uid:
        db.run("UPDATE friend SET state='rejected', decided_at=?"
               " WHERE a_id=? AND b_id=?", (_iso(), a, b))
        return {"ok": True, "was": "incoming"}
    was = "friend" if r["state"] == "accepted" else "outgoing"
    db.run("DELETE FROM friend WHERE a_id=? AND b_id=?", (a, b))
    return {"ok": True, "was": was}


def block(uid, other):
    if uid == other:
        raise HTTPException(400, "자기 자신은 차단할 수 없습니다.")
    if not db.q1("SELECT 1 x FROM users WHERE id=?", (other,)):
        raise HTTPException(404, "그런 트레이너가 없습니다.")
    db.run("INSERT INTO friend_block (user_id, target_id, created_at)"
           " VALUES (?,?,?) ON CONFLICT(user_id, target_id) DO NOTHING",
           (uid, other, _iso()))
    # 차단하면 친구 관계와 오가던 신청을 같이 지운다. 안 그러면 목록에
    # 남아서 '차단했는데 아직 친구' 라는 이상한 상태가 된다.
    a, b = _pair(uid, other)
    db.run("DELETE FROM friend WHERE a_id=? AND b_id=?", (a, b))
    return {"ok": True,
            "message": "차단했습니다. 신청과 도전장이 오지 않습니다."}


def unblock(uid, other):
    db.run("DELETE FROM friend_block WHERE user_id=? AND target_id=?",
           (uid, other))
    return {"ok": True}


# ---------------------------------------------------------------- 프로필
def profile(uid, other):
    u = db.q1("SELECT id, username FROM users WHERE id=?", (other,))
    if not u:
        raise HTTPException(404, "그런 트레이너가 없습니다.")
    rel = relation(uid, other)
    st = _stats([other]).get(other)
    out = {"id": other, "name": u["username"], "relation": rel,
           "online": is_online(other)}
    if st:
        out.update({"rating": st["rating"], "ranked": bool(st["ranked"]),
                    "wins": st["wins"], "losses": st["losses"],
                    "draws": st["draws"], "streak": st["streak"],
                    "best": st["best"]})
    # 최근 전적은 나 자신이나 친구에게만 보여준다. 모르는 사람의 기록을
    # 마음대로 볼 수 있으면 그것도 정보 수집이 된다.
    out["recent"] = []
    if rel in ("self", "friend"):
        out["recent"] = [r["result"] for r in db.q(
            "SELECT result FROM battle_record WHERE user_id=?"
            " ORDER BY id DESC LIMIT 10", (other,))]
    return out
