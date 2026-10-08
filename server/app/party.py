# -*- coding: utf-8 -*-
"""파티 프리셋 (1.10.3) — 데리고 다니는 파티를 몇 벌 두고 번호로 갈아탄다.

    GET  /api/party                 프리셋 목록과 지금 쓰는 번호
    POST /api/party/{no}/use        그 번호의 파티로 갈아탄다
    POST /api/party/{no}/name       이름을 붙인다 (비우면 기본 이름으로)

## 왜

랭크에 내보낼 여섯, 레이드에 데려갈 여섯, 바탕화면에 풀어 둘 여섯이 서로 다르다. 그때마다
박스에서 꺼내고 넣기를 되풀이해야 했다. 파티를 COUNT 벌까지 두고 번호를 눌러 바꾼다 -
'랭크', '레이드' 같은 이름도 붙일 수 있다.

## 지금 데리고 다니는 파티가 곧 '지금 번호' 의 파티다

따로 저장하는 단추가 없다. 다른 번호로 갈아탈 때 **지금 파티를 지금 번호에 적어 두고**, 가려는
번호에 적혀 있던 파티를 꺼낸다. 그래서 번호를 오가도 잃는 것이 없다. 포켓몬을 잡아 빈 자리에
들어온 것, 박스에서 꺼내 넣은 것, 순서를 바꾼 것 - 전부 '지금 번호' 에서 일어난 일이다.

**한 번도 안 쓴 번호로 가면 지금 파티를 그대로 들고 간다.** 바탕화면이 갑자기 텅 비지 않는다.
거기서 바꾸기 시작하면 그 번호만의 파티가 된다.

## 지키는 것

- 알은 프리셋에 들지 않는다. 데리고 다니는 알은 갈아타도 그대로 자리를 차지한다. 알까지 합쳐
  여섯을 넘으면 갈아타지 않고 까닭을 알린다 (아무것도 안 바뀐다).
- 그사이 놓아준 포켓몬은 조용히 빠진다. 한 포켓몬이 여러 번호에 들어 있어도 된다.
- 박스로 돌아가는 포켓몬은 원래 있던 박스로 간다 (deps.to_box). 꺼내는 일을 **먼저** 한다 -
  박스가 꽉 찬 사람도 자리를 맞바꿀 수 있다.
- 전설·환상 한 마리 제한은 배틀에 나갈 때 건다 (pvp.split_restricted). 여기서는 안 본다.
- 랭크 팀 등록(pvp.set_team)과는 따로다. 등록한 랭크 팀이 있으면 랜덤 배틀은 여전히 그 팀으로 싸운다.
"""
import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import config, db, deps

router = APIRouter()

COUNT = 5                   # 프리셋 수
NAME_MAX = 4                # 이름 글자 수. 탭 다섯이 포켓몬 관리 창의 한 줄에 들어가야 한다 ('바탕화면')


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def default_name(no):
    return "파티 %d" % no


def _rows(uid):
    return dict((r["no"], r) for r in db.q("SELECT * FROM party_preset WHERE user_id=?", (uid,)))


def _active(rows):
    """지금 쓰는 번호. 적힌 것이 없으면 1번이다 (프리셋을 한 번도 안 쓴 사람)."""
    for no in sorted(rows):
        if rows[no]["active"] and 1 <= no <= COUNT:
            return no
    return 1


def desktop_ids(uid):
    """지금 데리고 다니는 포켓몬의 id (자리 순). 알은 빼고."""
    return [r["id"] for r in db.q(
        "SELECT id FROM pokemon WHERE user_id=? AND on_desktop=1 ORDER BY slot, id", (uid,))]


def _stored(row):
    try:
        ids = json.loads(row["ids"] or "[]")
    except ValueError:
        ids = []
    out = []
    for i in ids if isinstance(ids, list) else []:
        if isinstance(i, int) and i not in out:
            out.append(i)
    return out[:config.MAX_PARTY]


def _owned(uid, ids):
    """그 가운데 아직 내 것인 포켓몬만 (순서는 그대로). 놓아준 것은 여기서 빠진다."""
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    mine = set(r["id"] for r in db.q(
        "SELECT id FROM pokemon WHERE user_id=? AND id IN (%s)" % marks, (uid,) + tuple(ids)))
    return [i for i in ids if i in mine]


def state(uid):
    """화면에 줄 것. 지금 번호의 내용은 적어 둔 것이 아니라 **지금 데리고 다니는 것**이다."""
    rows = _rows(uid)
    cur = _active(rows)
    live = desktop_ids(uid)
    out = []
    for no in range(1, COUNT + 1):
        r = rows.get(no)
        if no == cur:
            ids, saved = live, True
        elif r is not None and r["saved"]:
            ids, saved = _owned(uid, _stored(r)), True
        else:
            ids, saved = [], False
        name = (r["name"] if r is not None else None) or ""
        out.append({"no": no, "name": name or default_name(no), "named": bool(name),
                    "active": no == cur, "saved": saved, "size": len(ids), "ids": ids})
    return {"active": cur, "count": COUNT, "nameMax": NAME_MAX, "max": config.MAX_PARTY, "presets": out}


def _check(no):
    try:
        no = int(no)
    except (TypeError, ValueError):
        no = 0
    if not 1 <= no <= COUNT:
        raise HTTPException(404, "그런 파티 번호가 없습니다.")
    return no


def _write(uid, no, ids, active):
    db.run("INSERT INTO party_preset (user_id, no, ids, active, saved, updated_at) VALUES (?,?,?,?,1,?)"
           " ON CONFLICT(user_id, no) DO UPDATE SET ids=excluded.ids, active=excluded.active,"
           " saved=1, updated_at=excluded.updated_at",
           (uid, no, json.dumps(ids), 1 if active else 0, _now()))


def _apply(uid, live, want, egg_slots):
    """데리고 다니는 포켓몬을 want 로 바꾼다 (순서대로). 알의 자리는 건드리지 않는다."""
    taken = set(s for s in egg_slots if s is not None)
    free = [i for i in range(config.MAX_PARTY) if i not in taken]
    # 꺼내는 일이 먼저다. 박스가 꽉 찬 사람도, 나온 자리에 들어갈 것이 들어간다.
    for i, pid in enumerate(want):
        db.run("UPDATE pokemon SET on_desktop=1, slot=? WHERE id=? AND user_id=?",
               (free[i] if i < len(free) else i, pid, uid))
    keep = set(want)
    for pid in live:
        if pid in keep:
            continue
        row = db.q1("SELECT box FROM pokemon WHERE id=? AND user_id=?", (pid, uid))
        if row is not None:
            deps.to_box(uid, pid, prefer=(row["box"] if "box" in row.keys() else 0) or 0)


def use(uid, no):
    """그 번호의 파티로 갈아탄다."""
    no = _check(no)
    rows = _rows(uid)
    cur = _active(rows)
    if no == cur:
        return dict(state(uid), ok=True, changed=False, message="")
    live = desktop_ids(uid)
    row = rows.get(no)
    fresh = row is None or not row["saved"]       # 한 번도 안 쓴 번호: 지금 파티를 들고 간다
    want = live if fresh else _owned(uid, _stored(row))
    name = (row["name"] if row is not None else None) or default_name(no)
    if not fresh:
        eggs = deps._egg_slots(uid)
        if len(want) + len(eggs) > config.MAX_PARTY:
            raise HTTPException(409, "데리고 다니는 알이 %d개 있어서 [%s]의 %d마리를 다 꺼낼 수 없습니다. "
                                     "알을 내려놓고 다시 해 주세요." % (len(eggs), name, len(want)))
    _write(uid, cur, live, False)                 # 지금 파티를 지금 번호에 적어 둔다
    if not fresh:
        _apply(uid, live, want, eggs)
    _write(uid, no, want, True)
    # 이름에 조사를 붙이지 않는다 (사람이 지은 이름이라 '을/를' 을 맞출 수 없다)
    if fresh:
        message = "파티를 바꿨습니다: [%s] - 처음 쓰는 번호라 지금 파티를 그대로 가져왔습니다." % name
    elif want:
        message = "파티를 바꿨습니다: [%s]" % name
    else:
        message = "파티를 바꿨습니다: [%s] - 비어 있는 파티입니다." % name
    return dict(state(uid), ok=True, changed=not fresh, message=message)


def rename(uid, no, name):
    no = _check(no)
    text = " ".join((name or "").split())
    if len(text) > NAME_MAX:
        raise HTTPException(400, "파티 이름은 %d자까지입니다." % NAME_MAX)
    rows = _rows(uid)
    cur = _active(rows)
    if no in rows:
        db.run("UPDATE party_preset SET name=? WHERE user_id=? AND no=?", (text or None, uid, no))
    else:
        # 아직 줄이 없는 번호. 내용은 그대로 '안 쓴 번호' 로 두고 이름만 적는다
        # (지금 번호라면 active 를 같이 적는다 - 줄이 생기면 그 줄이 '지금 번호' 를 정한다).
        db.run("INSERT INTO party_preset (user_id, no, name, ids, active, saved, updated_at)"
               " VALUES (?,?,?,'[]',?,0,?)", (uid, no, text or None, 1 if no == cur else 0, _now()))
        if no != cur and cur not in rows:
            db.run("INSERT INTO party_preset (user_id, no, ids, active, saved, updated_at)"
                   " VALUES (?,?,'[]',1,0,?)", (uid, cur, _now()))
    return dict(state(uid), ok=True,
                message="파티 이름을 바꿨습니다: [%s]" % (text or default_name(no)))


class NameIn(BaseModel):
    name: str = ""


@router.get("/api/party")
def get(ctx=Depends(deps.current)):
    return state(ctx["user"]["id"])


@router.post("/api/party/{no}/use")
def post_use(no: int, ctx=Depends(deps.current)):
    return use(ctx["user"]["id"], no)


@router.post("/api/party/{no}/name")
def post_name(no: int, body: NameIn, ctx=Depends(deps.current)):
    return rename(ctx["user"]["id"], no, body.name)
