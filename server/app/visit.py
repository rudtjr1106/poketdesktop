# -*- coding: utf-8 -*-
"""친구 집에 놀러 가기 · 친구 채팅 (1.11.0, 2026-10-15 사용자 기획).

## 얼개

**무조건 1:1.** 내가 친구에게 파티 맨 앞 포켓몬 한 마리를 보내면 수락 없이 바로 간다. 둘 중 누구든
이미 연결돼 있으면(놀러 가 있거나 손님을 받고 있으면) 못 보낸다.

    손님(guest)  내 바탕화면에서 내 포켓몬은 잠시 빠지고, 친구 파티의 포켓몬들이 돌아다닌다. 내가 보낸
                 포켓몬은 오른쪽 아래에 서 있다.
    주인(host)   평소처럼 내 포켓몬들이 돌아다니고, 친구가 보낸 포켓몬이 오른쪽 아래에 선다.

그래서 두 화면에 같은 7마리가 보인다. **맞추는 것은 '누가 있나(파티)' 와 말·동작뿐이다** - 걷는 자리는
맞추지 않는다 (10/15 사용자 결정: 0.5초마다 자리를 따라가게 했더니 뚝뚝 끊겼다. 친구 포켓몬은 손님
화면에서 제 발로 돌아다닌다). 말을 치면 그 사람의 포켓몬(손님은 보낸 포켓몬, 주인은 말한 그 포켓몬)
머리 위에 말풍선이 뜨고, /춤 · /자기 같은 명령으로 동작을 하면 상대 화면에서도 같이 한다. 메가진화한
모습으로 걷기를 켜고 끄는 것도 같이 보인다.

## 도구 - 들고 가서 보따리로 두고 온다 (10/15 사용자 교정)

보낼 때는 **들고 갈 것만** 고른다 (아무것도 안 옮긴다). 놀러 가 있는 동안 손님이 내 포켓몬을 우클릭해
'여기에 두기' 를 하면 들고 온 것 중 고른 만큼을 **보따리**에 싸서 주인 바탕화면에 둔다 - 그 순간 손님
가방에서 빠진다. 주인이 보따리를 누르면 주인 가방으로 들어가고 둘 다에게 '누가 무엇을 받았다' 가 간다.
주인이 안 받은 채 끝나면 손님에게 돌려준다 (서버를 다시 켜도 - visit_bundle 표에 적어 두고 켤 때 돌려준다).

**들고 갈 수 있는 것** (10/15 사용자 결정 - 부계정으로 몰아주기를 막으려고): 볼과 지닌 도구 중 등급이
귀함(rare) 이하인 것만 (마스터볼·진귀한 지닌 도구는 안 된다). 볼은 합쳐서 BALL_MAX 개, 지닌 도구는
HELD_MAX 개까지.

**받는 것은 하루(KST)에 한 번** (RECEIVE_PER_DAY). 주인이 오늘 보따리를 받았거나 안 받은 보따리가 놓여
있으면 손님은 더 둘 수 없다 (visit_bundle 의 open·taken 으로 센다 - 돌려준 것은 안 센다). 손님 화면은
view 의 canGive 를 보고 '여기에 두기' 를 끈다.

## 실시간

    WS /ws/visit        머리말 Authorization: Bearer <토큰>

앱이 켜져 있는 동안 늘 붙어 있다 - **붙어 있는 것이 '지금 놀러 갈 수 있다' 는 뜻**이다 (친구 목록의
visitable). 놀러 가기는 POST /api/visit/start 로 하고, 그 뒤의 파티·말·동작은 이 소켓으로 오간다.

    화면 -> 서버   {"t": "party", "party": [...]}   주인: 바탕화면 파티 (바뀔 때만 - 번호·모습·이름·레벨)
                  {"t": "say", "text": "...", "pet": 12}   말 (SAY_MAX 자까지). pet = 주인이 말한 포켓몬
                  {"t": "act", "act": "dance", "pet": 12}  동작 (ACTS)
                  {"t": "look", "look": 10006}      손님: 보낸 포켓몬의 모습 (메가진화한 모습으로 걷기)
                  "ping"                            -> "pong"
    서버 -> 화면   {"t": "hello"}                    붙었다
                  {"t": "visit", "visit": {...}}    연결됐다 (role 이 host / guest)
                  {"t": "party"/"say"/"act"/"look", ...}  상대가 보낸 것 (from = host / guest)
                  {"t": "end", "by", "text"}        끝났다

끊기면 GRACE 초를 기다렸다가 끝낸다 (프로그램을 다시 켜는 사이에 끝나지 않게). 서버를 다시 올리면
놀러 간 것은 전부 끝난다 (적어 두지 않는다 - 옮긴 도구는 이미 옮겼다).

서버는 프로세스 하나로 돈다 (guild_ws 와 같은 까닭으로 이 모듈의 사전에 들고 있다).
"""
import asyncio
import datetime
import json
import os
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from . import auth, db, deps, items, social

router = APIRouter()

KST = datetime.timezone(datetime.timedelta(hours=9))
RECEIVE_PER_DAY = 1          # 보따리를 받는 것은 하루에 한 번 (사용자 결정 - 부계정 몰아주기 막기)
BALL_MAX = 5                 # 들고 갈 수 있는 볼 (합쳐서)
HELD_MAX = 1                 # 들고 갈 수 있는 지닌 도구 (합쳐서)
CARRY_RARITY = ("common", "uncommon", "rare")    # 흔함 · 조금귀함 · 귀함 까지 (진귀·전설·등급 없음은 안 된다)
CARRY_CATS = ("ball", "held")
SAY_MAX = 60                 # 말 한 번의 글자 수
ACTS = ("dance", "sleep", "sit", "lie", "hop", "hello", "faint", "wake")
GRACE = float(os.environ.get("POKET_VISIT_GRACE", "20"))   # 끊긴 뒤 이만큼 기다렸다가 끝낸다 (초, 검사는 짧게)
PARTY_GAP = 0.5              # 주인의 파티 보내기를 이보다 자주 받지 않는다 (초, 화면은 바뀔 때만 1초에 한 번 본다)
SAY_GAP = 0.6                # 말·동작을 이보다 자주 받지 않는다 (도배 막기)
MAX_PER_USER = 3
MAX_TOTAL = 600

_lock = threading.RLock()
_conns = {}                  # {사람: set(Conn)}
_visits = {}                 # {번호: 놀러 가기}
_of = {}                     # {사람: 번호} - 손님도 주인도
_seq = [0]
_loop = None
_gone = {}                   # {사람: 끊긴 시각} - GRACE 를 센다


class Conn(object):
    __slots__ = ("ws", "uid", "last")

    def __init__(self, ws, uid):
        self.ws, self.uid, self.last = ws, uid, {}


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(t=None):
    return (t or _now()).replace(microsecond=0).isoformat()


def today(now=None):
    return (now or _now()).astimezone(KST).date().isoformat()


def reset():
    """검사용: 전부 비운다."""
    with _lock:
        _conns.clear()
        _visits.clear()
        _of.clear()
        _gone.clear()


# ---------------------------------------------------------------- 붙어 있나
def online(uid):
    with _lock:
        return bool(_conns.get(uid))


def busy(uid):
    with _lock:
        return uid in _of


def presence(ids):
    """친구 목록이 쓴다: {사람: (지금 붙어 있나, 이미 연결돼 있나)}."""
    with _lock:
        return dict((i, (bool(_conns.get(i)), i in _of)) for i in ids)


def _add(c):
    with _lock:
        mine = len(_conns.get(c.uid, ()))
        total = sum(len(s) for s in _conns.values())
        if mine >= MAX_PER_USER or total >= MAX_TOTAL:
            return False
        _conns.setdefault(c.uid, set()).add(c)
        _gone.pop(c.uid, None)
        return True


def _drop(c):
    with _lock:
        s = _conns.get(c.uid)
        if s is not None:
            s.discard(c)
            if not s:
                _conns.pop(c.uid, None)
                return True          # 이 사람의 마지막 연결이 끊겼다
    return False


# ---------------------------------------------------------------- 밀기
async def _send(c, text):
    try:
        await c.ws.send_text(text)
    except Exception:                                       # noqa: BLE001
        _drop(c)


def push(uid, payload):
    """그 사람의 화면들로 보낸다. 스레드풀에서도, 이벤트 루프에서도 부를 수 있다."""
    loop = _loop
    if loop is None or loop.is_closed():
        return
    with _lock:
        targets = list(_conns.get(uid, ()))
    if not targets:
        return
    text = json.dumps(payload, ensure_ascii=False)
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    for c in targets:
        try:
            if running is loop:
                loop.create_task(_send(c, text))
            else:
                asyncio.run_coroutine_threadsafe(_send(c, text), loop)
        except RuntimeError:
            pass


# ---------------------------------------------------------------- 놀러 가기
def _visit_of(uid):
    with _lock:
        vid = _of.get(uid)
        return _visits.get(vid) if vid else None


def _role(v, uid):
    return "host" if v["host"] == uid else "guest"


def _partner(v, uid):
    return v["guest"] if v["host"] == uid else v["host"]


def view(v, uid):
    """그 사람의 화면에 줄 것."""
    role = _role(v, uid)
    out = {"id": v["id"], "role": role, "host": v["host"], "guest": v["guest"],
           "hostName": v["hostName"], "guestName": v["guestName"],
           "partner": v["hostName"] if role == "guest" else v["guestName"],
           "mon": v["mon"], "look": v["look"], "hostLead": v.get("hostLead"),
           "carry": v["carry"], "bundles": v["bundles"], "canGive": can_give(v), "since": v["since"]}
    if role == "guest" and v.get("party") is not None:
        out["party"] = v["party"]
    return out


def _lead(uid):
    """파티 맨 앞 포켓몬 (바탕화면, 자리 순). 없으면 None."""
    r = db.q1("SELECT * FROM pokemon WHERE user_id=? AND on_desktop=1 ORDER BY slot, id LIMIT 1", (uid,))
    return db.row_to_mon(r) if r else None


def _public_mon(m):
    d = deps.dex()
    sp = d.get(m["species"]) or {}
    return {"id": m["id"], "num": sp.get("num"), "species": m["species"],
            "name": m.get("nickname") or sp.get("kr") or m["species"], "level": int(m.get("level") or 1),
            "shiny": bool(m.get("shiny")), "tint": m.get("tint") if m.get("shiny") else None,
            "deco": m.get("deco") or {}}             # 꾸미기 (버전 2) - 놀러 간 포켓몬도 쓰고 간다


def received_today(uid, now=None):
    """오늘 받았거나 받을 보따리 수 (안 받고 놓여 있는 것도 센다 - 돌려준 것은 안 센다)."""
    r = db.q1("SELECT COUNT(*) n FROM visit_bundle WHERE receiver_id=? AND day=? AND state IN ('open','taken')",
              (uid, today(now)))
    return int(r["n"] or 0)


def can_give(v, now=None):
    """손님이 지금 주인에게 보따리를 둘 수 있나 (주인이 오늘 한 번을 아직 안 썼나)."""
    return received_today(v["host"], now) < RECEIVE_PER_DAY


def carryable(it):
    """들고 갈 수 있는 도구인가: 볼·지닌 도구 중 귀함 이하."""
    return bool(it) and it.get("cat") in CARRY_CATS and it.get("rarity") in CARRY_RARITY


def _clean_items(raw):
    """[(도구, 개수)] - 같은 도구는 합친다. 들고 갈 수 없는 도구·한도를 넘는 것은 거절."""
    want = {}
    for x in raw or []:
        try:
            iid = str(x.get("id") or "").upper()
            n = int(x.get("count") or 0)
        except (TypeError, ValueError, AttributeError):
            raise HTTPException(400, "도구를 알 수 없습니다.")
        if not iid or n <= 0:
            continue
        it = items.get(iid)
        if not it:
            raise HTTPException(400, "그런 도구는 없습니다.")
        if not carryable(it):
            raise HTTPException(400, "%s은(는) 들고 갈 수 없습니다 (볼·지닌 도구 중 귀함까지)." % it["kr"])
        want[iid] = want.get(iid, 0) + n
    balls = sum(n for iid, n in want.items() if items.get(iid)["cat"] == "ball")
    held = sum(n for iid, n in want.items() if items.get(iid)["cat"] == "held")
    if balls > BALL_MAX:
        raise HTTPException(400, "볼은 %d개까지 들고 갈 수 있습니다." % BALL_MAX)
    if held > HELD_MAX:
        raise HTTPException(400, "지닌 도구는 %d개까지 들고 갈 수 있습니다." % HELD_MAX)
    return sorted(want.items())


def _rows(plan):
    return [{"id": iid, "kr": items.name_of(iid), "count": n} for iid, n in plan]


def start(uid, friend, raw_items=None, look=None, now=None):
    """친구 집에 놀러 간다 (수락 없이 바로). 들고 가는 도구는 보여 주기만 한다. 연결된 놀러 가기를 돌려준다."""
    friend = int(friend)
    if friend == uid:
        raise HTTPException(400, "자기 집에는 놀러 갈 수 없습니다.")
    if not social.is_friend(uid, friend):
        raise HTTPException(403, "친구에게만 놀러 갈 수 있습니다.")
    if not online(friend):
        raise HTTPException(409, "친구가 지금 접속해 있지 않습니다.")
    mon = _lead(uid)
    if not mon:
        raise HTTPException(409, "데리고 다니는 포켓몬이 없습니다.")
    plan = _clean_items(raw_items)
    for iid, n in plan:
        if items.bag_count(uid, iid) < n:
            raise HTTPException(409, "%s이(가) 모자랍니다." % items.name_of(iid))
    names = social._names([uid, friend])
    with _lock:
        # **둘 다 비어 있을 때만** - 확인과 자리 잡기를 한 덩어리로 (두 사람이 서로에게 동시에 보내도 하나만)
        if uid in _of:
            raise HTTPException(409, "이미 친구와 연결돼 있습니다. 먼저 끝내 주세요.")
        if friend in _of:
            raise HTTPException(409, "친구가 지금 다른 친구와 연결돼 있습니다.")
        _seq[0] += 1
        v = {"id": _seq[0], "host": friend, "guest": uid,
             "hostName": names.get(friend, "?"), "guestName": names.get(uid, "?"),
             "mon": _public_mon(mon), "look": int(look) if look else None,
             "carry": _rows(plan), "bundles": [], "since": _iso(now), "party": None, "hostLead": None}
        _visits[v["id"]] = v
        _of[uid] = _of[friend] = v["id"]
    push(friend, {"t": "visit", "visit": view(v, friend)})
    push(uid, {"t": "visit", "visit": view(v, uid)})
    return view(v, uid)


def _push_bundles(v):
    ok = can_give(v)
    for u in (v["host"], v["guest"]):
        push(u, {"t": "bundles", "bundles": v["bundles"], "carry": v["carry"], "canGive": ok})


def drop(uid, raw_items, now=None):
    """손님: 들고 온 도구 중 고른 만큼을 보따리에 싸서 주인 바탕화면에 둔다. 손님 가방에서 바로 빠진다."""
    v = _visit_of(uid)
    if not v or v["guest"] != uid:
        raise HTTPException(409, "친구 집에 놀러 가 있을 때만 둘 수 있습니다.")
    plan = _clean_items(raw_items)
    if not plan:
        raise HTTPException(400, "둘 도구를 골라 주세요.")
    total = sum(n for _i, n in plan)
    with _lock:
        carry = dict((x["id"], x["count"]) for x in v["carry"])
        for iid, n in plan:
            if carry.get(iid, 0) < n:
                raise HTTPException(409, "들고 온 %s이(가) 모자랍니다." % items.name_of(iid))
        if not can_give(v, now):
            raise HTTPException(409, "%s 님은 오늘 이미 보따리를 받았습니다 (하루 한 번)." % v["hostName"])
        # **먼저 다 빼고, 다 빠졌을 때만 싼다** - 그사이 다른 창에서 써서 모자라면 뺀 것을 돌려놓는다.
        taken = []
        for iid, n in plan:
            if not items.bag_take(uid, iid, n):
                for t_iid, t_n in taken:
                    items.bag_add(uid, t_iid, t_n)
                raise HTTPException(409, "%s이(가) 모자랍니다." % items.name_of(iid))
            taken.append((iid, n))
        rows = _rows(plan)
        cur = db.run("INSERT INTO visit_bundle (giver_id, receiver_id, items, count, day, state, at) "
                     "VALUES (?,?,?,?,?,'open',?)",
                     (uid, v["host"], json.dumps(rows, ensure_ascii=False), total, today(now), _iso(now)))
        b = {"id": int(cur.lastrowid), "items": rows, "count": total, "from": v["guestName"]}
        v["bundles"].append(b)
        for iid, n in plan:
            carry[iid] -= n
        v["carry"] = [dict(x, count=carry[x["id"]]) for x in v["carry"] if carry.get(x["id"], 0) > 0]
    _push_bundles(v)
    return b


def claim(uid, bundle_id, now=None):
    """주인: 보따리를 받는다 (주인 가방으로). 둘 다에게 '누가 무엇을 받았다' 를 민다."""
    v = _visit_of(uid)
    if not v or v["host"] != uid:
        raise HTTPException(409, "놀러 온 친구가 둔 보따리만 받을 수 있습니다.")
    try:
        bid = int(bundle_id)
    except (TypeError, ValueError):
        raise HTTPException(400, "보따리를 알 수 없습니다.")
    b = next((x for x in v["bundles"] if x["id"] == bid), None)
    if b is None:
        raise HTTPException(404, "그 보따리는 이미 없습니다.")
    # 한 번만 받는다 - 두 창에서 동시에 눌러도 open -> taken 은 한 번뿐이다
    cur = db.run("UPDATE visit_bundle SET state='taken', done_at=? WHERE id=? AND state='open'", (_iso(now), bid))
    if cur.rowcount != 1:
        raise HTTPException(409, "그 보따리는 이미 받았습니다.")
    for x in b["items"]:
        items.bag_add(uid, x["id"], int(x["count"]))
    with _lock:
        v["bundles"] = [x for x in v["bundles"] if x["id"] != bid]
    _push_bundles(v)
    msg = {"t": "claimed", "bundle": b, "by": v["hostName"], "from": v["guestName"]}
    for u in (v["host"], v["guest"]):
        push(u, msg)
    return b


def _return_bundle(bid, giver, items_, now=None):
    """안 받은 보따리를 준 사람에게 돌려준다 (한 번만). 돌려줬으면 True."""
    cur = db.run("UPDATE visit_bundle SET state='returned', done_at=? WHERE id=? AND state='open'",
                 (_iso(now), bid))
    if cur.rowcount != 1:
        return False
    for x in items_:
        items.bag_add(giver, x["id"], int(x["count"]))
    return True


def return_open():
    """서버를 켤 때: 놀러 가기는 메모리에만 있어서 다 끝났다 - 남은 보따리를 준 사람에게 돌려준다."""
    n = 0
    for r in db.q("SELECT * FROM visit_bundle WHERE state='open'"):
        if _return_bundle(r["id"], r["giver_id"], json.loads(r["items"])):
            n += 1
    return n


def _end(v, by, text):
    with _lock:
        if _visits.pop(v["id"], None) is None:
            return False
        for u in (v["host"], v["guest"]):
            if _of.get(u) == v["id"]:
                _of.pop(u, None)
    back = []
    for b in v.get("bundles") or []:                       # 안 받은 보따리는 손님에게 돌려준다
        if _return_bundle(b["id"], v["guest"], b["items"]):
            back.extend(b["items"])
    for u in (v["host"], v["guest"]):
        push(u, {"t": "end", "id": v["id"], "by": by, "text": text, "returned": back})
    return True


def end(uid, now=None):
    """끝낸다. 손님이면 '돌아오기', 주인이면 '돌려보내기'."""
    v = _visit_of(uid)
    if not v:
        return False
    role = _role(v, uid)
    if role == "guest":
        text = "%s 님의 포켓몬이 집으로 돌아갔습니다." % v["guestName"]
    else:
        text = "%s 님이 놀러 온 포켓몬을 돌려보냈습니다." % v["hostName"]
    return _end(v, role, text)


def state(uid, now=None):
    v = _visit_of(uid)
    return {"visit": view(v, uid) if v else None, "receivedToday": received_today(uid, now),
            "receivePerDay": RECEIVE_PER_DAY, "ballMax": BALL_MAX, "heldMax": HELD_MAX,
            "rarities": list(CARRY_RARITY), "sayMax": SAY_MAX, "acts": list(ACTS), "online": online(uid)}


# ---------------------------------------------------------------- 소켓으로 오는 것
def _clean_party(raw, uid=None):
    """주인이 보낸 파티를 다듬는다 (믿지 않는다 - 숫자만, 여섯 마리까지). 자리는 없다 - 걷는 것은 손님 화면 몫.

    꾸미기(버전 2)는 보낸 값을 안 믿는다 - 주인(uid)의 포켓몬이 서버에 쓰고 있는 것(pokemon.deco)을 싣는다.
    고친 화면이 안 가진 금관을 친구에게 보여 주지 못하게.
    """
    out = []
    for p in (raw or [])[:6]:
        try:
            x = {"id": int(p.get("id")), "num": int(p.get("num") or 0), "look": int(p.get("look") or 0),
                 "shiny": bool(p.get("shiny")), "name": str(p.get("name") or "")[:16],
                 "level": int(p.get("level") or 1), "lead": bool(p.get("lead"))}
        except (TypeError, ValueError, AttributeError):
            continue
        tint = p.get("tint")
        if isinstance(tint, str) and len(tint) <= 16:
            x["tint"] = tint
        if x["num"] > 0 and x["id"] not in [o["id"] for o in out]:
            out.append(x)
    if uid and out:
        # 꾸미기 (버전 2) - 손님 화면도 장식 · 효과를 그린다
        from . import deco
        rows = db.q("SELECT id, deco FROM pokemon WHERE user_id=? AND deco IS NOT NULL AND id IN (%s)"
                    % ",".join("?" * len(out)), tuple([uid] + [x["id"] for x in out]))
        worn = dict((r["id"], deco.worn(r["deco"])) for r in rows)
        for x in out:
            if worn.get(x["id"]):
                x["deco"] = worn[x["id"]]
    return out


def _speaker(v, role, msg):
    """말·동작을 한 포켓몬. 주인만 고른다 (지금 파티에 있는 것만) - 손님은 늘 보낸 포켓몬이다."""
    if role != "host":
        return None
    try:
        pid = int(msg.get("pet") or 0)
    except (TypeError, ValueError):
        return None
    return pid if pid and pid in [p["id"] for p in v.get("party") or []] else None


def receive(uid, msg, now_s=None, conn=None):
    """화면이 보낸 한 줄. 상대에게 넘길 것을 (받을 사람, payload) 로 돌려준다 (None 이면 버린다)."""
    v = _visit_of(uid)
    if not v or not isinstance(msg, dict):
        return None
    t = msg.get("t")
    role = _role(v, uid)
    to = _partner(v, uid)
    now_s = now_s if now_s is not None else time.time()
    last = conn.last if conn is not None else {}
    if t == "party":
        if role != "host":
            return None
        if now_s - last.get("party", 0) < PARTY_GAP:
            return None
        last["party"] = now_s
        party = _clean_party(msg.get("party"), uid)
        lead = next((p["id"] for p in party if p["lead"]), party[0]["id"] if party else None)
        v["party"], v["hostLead"] = party, lead
        return to, {"t": "party", "party": party, "lead": lead}
    if t in ("say", "act"):
        if now_s - last.get("say", 0) < SAY_GAP:
            return None
        last["say"] = now_s
        pet = _speaker(v, role, msg)
        if t == "say":
            text = " ".join(str(msg.get("text") or "").split())[:SAY_MAX]
            if not text:
                return None
            return to, {"t": "say", "from": role, "text": text, "pet": pet}
        act = str(msg.get("act") or "")
        if act not in ACTS:
            return None
        return to, {"t": "act", "from": role, "act": act, "pet": pet}
    if t == "look" and role == "guest":
        try:
            look = int(msg.get("look") or 0) or None
        except (TypeError, ValueError):
            return None
        v["look"] = look
        return to, {"t": "look", "look": look}
    return None


def _gone_later(uid):
    """끊긴 뒤 GRACE 초가 지나도 안 돌아왔으면 끝낸다."""
    with _lock:
        if _conns.get(uid) or uid not in _gone:
            return False
        _gone.pop(uid, None)
    v = _visit_of(uid)
    if not v:
        return False
    name = v["hostName"] if v["host"] == uid else v["guestName"]
    return _end(v, "gone", "%s 님의 연결이 끊겨 놀러 가기를 끝냈습니다." % name)


# ---------------------------------------------------------------- HTTP
class StartIn(BaseModel):
    friend: int
    items: list = []
    look: int = 0


class DropIn(BaseModel):
    items: list = []


class ClaimIn(BaseModel):
    bundle: int


@router.get("/api/visit")
def get_state(ctx=Depends(deps.current)):
    return state(ctx["user"]["id"])


@router.post("/api/visit/start")
def post_start(body: StartIn, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    v = start(uid, body.friend, body.items, body.look or None)
    return dict(state(uid), visit=v)


@router.post("/api/visit/drop")
def post_drop(body: DropIn, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    b = drop(uid, body.items)
    return dict(state(uid), bundle=b)


@router.post("/api/visit/claim")
def post_claim(body: ClaimIn, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    b = claim(uid, body.bundle)
    return dict(state(uid), bundle=b)


@router.post("/api/visit/end")
def post_end(ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    ended = end(uid)                      # 끝낸 뒤의 모습을 준다 (먼저 끝낸다)
    return dict(state(uid), ended=ended)


# ---------------------------------------------------------------- 웹소켓
def _who(token):
    sess, user = auth.lookup_session_with_user(token)
    return user["id"] if sess else None


@router.websocket("/ws/visit")
async def visit_socket(ws: WebSocket):
    global _loop
    _loop = asyncio.get_running_loop()
    head = ws.headers.get("authorization") or ""
    await ws.accept()
    if not head.lower().startswith("bearer "):
        return await ws.close(code=4401)
    uid = await run_in_threadpool(_who, head[7:].strip())
    if uid is None:
        return await ws.close(code=4401)
    c = Conn(ws, uid)
    if not _add(c):
        return await ws.close(code=4429)
    try:
        await ws.send_text(json.dumps({"t": "hello", "userId": uid}))
        v = _visit_of(uid)
        if v:
            await ws.send_text(json.dumps({"t": "visit", "visit": view(v, uid)}, ensure_ascii=False))
        while True:
            text = await ws.receive_text()
            if text == "ping":
                await ws.send_text("pong")
                continue
            try:
                msg = json.loads(text)
            except ValueError:
                continue
            got = receive(uid, msg, conn=c)
            if got:
                push(got[0], got[1])
    except WebSocketDisconnect:
        pass
    except Exception:                                       # noqa: BLE001
        pass
    finally:
        if _drop(c) and busy(uid):
            with _lock:
                _gone[uid] = time.time()
            try:
                _loop.call_later(GRACE, lambda: _gone_later(uid))
            except Exception:                               # noqa: BLE001
                pass
