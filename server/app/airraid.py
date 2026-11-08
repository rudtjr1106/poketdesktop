# -*- coding: utf-8 -*-
"""공습 (2.3.0) — 하루 한 번, 낙하산을 타고 내려온 야생 무리와 바탕화면 파티의 각개전투.

    GET  /api/airraid          그날 공습 {day, dueAt, dueIn, done, result}
    POST /api/airraid/start    그날 시각이 지났으면 공습을 계산해 저장하고 각본을 준다 (이미 했으면 그 판, already)

설계 design-notes/2026-11-08-airraid.md · 계산 common/airraid.py.

## 하루 한 번

그날(KST)의 시각은 사람 · 날짜로 시드를 굴려 10:00~22:00 사이 (due_at). 앱이 켜진 채 그 시각이 지나면 앱이
start 를 부른다 (막힘이면 미룬다). 그 시각에 꺼져 있었으면 그날 켰을 때. 자정을 넘기면 새 날이다.

## 결과는 시작할 때 한 번 계산한다

판의 시드도 사람 · 날짜에서 나온다 - 같은 날 다시 계산해도 같은 판이다. **airraid 줄과 볼 · 돈을 한 트랜잭션으로**
넣어 두 번(동시에) 불러도 보상은 한 번 (UNIQUE(user_id, day) - 줄을 먼저 넣은 쪽만 준다, 올림픽 정산과 같은 틀).
경험치는 그 뒤에 (쓰러뜨린 공습 포켓몬마다 그 포켓몬을 쓰러뜨린 내 포켓몬에게 야생 배틀과 같은 battle_routes.award -
학습장치 몫 · 노력치 · 진화까지). 각본은 압축해 두고 7일 뒤 지운다 (housekeep).
"""
import base64
import datetime
import json
import zlib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common import airraid as CR
from common import battle as B

from . import config, db, deps

router = APIRouter()

KST = datetime.timezone(datetime.timedelta(hours=9))
WINDOW = (10, 22)            # 그날 시각은 이 사이 (KST 시)
REWARD = {"balls": 3, "money": 5000}         # 이기면 (사용자 11/08 '돈은 5000원으로')
KEEP_DAYS = 7


def _now(now=None):
    return (now or datetime.datetime.now(datetime.timezone.utc)).replace(microsecond=0)


def day_of(now):
    return now.astimezone(KST).date().isoformat()


def _crc(*parts):
    return zlib.crc32(("|".join(str(p) for p in parts)).encode("utf-8")) & 0x7fffffff


def due_at(uid, day):
    """그날 그 사람의 공습 시각 (UTC aware). 10:00 ~ 22:00 KST 사이, 사람 · 날짜마다 다르고 늘 같다."""
    y, m, d = int(day[0:4]), int(day[5:7]), int(day[8:10])
    span = (WINDOW[1] - WINDOW[0]) * 60
    mins = _crc("airraid-at", uid, day) % span
    t = datetime.datetime(y, m, d, WINDOW[0], 0, tzinfo=KST) + datetime.timedelta(minutes=mins)
    return t.astimezone(datetime.timezone.utc)


def _pack(obj):
    return base64.b64encode(zlib.compress(json.dumps(obj, ensure_ascii=False).encode("utf-8"))).decode("ascii")


def _unpack(s):
    return json.loads(zlib.decompress(base64.b64decode(s)).decode("utf-8"))


def _row(uid, day):
    return db.q1("SELECT * FROM airraid WHERE user_id=? AND day=?", (uid, day))


_card_sql = "SELECT result FROM airraid WHERE user_id=? AND day=?"     # 매 동기화 - 각본(data)은 안 읽는다


def state(uid, now=None):
    now = _now(now)
    day = day_of(now)
    due = due_at(uid, day)
    r = db.q1(_card_sql, (uid, day))
    return {"day": day, "dueAt": due.isoformat(), "dueIn": max(0, int((due - now).total_seconds())),
            "done": r is not None, "result": r["result"] if r else None}


def me_card(uid, now=None):
    """/api/me 에 싣는 짧은 것 - 앱이 그날 공습을 예약한다. 했으면 결과 · 보상 (다른 PC · 다시 켠 앱이 한 번 알린다),
    바탕화면 파티 수 (0 이면 앱이 부르지 않는다 - 서버가 거절할 것이라 10분마다 두드리지 않게)."""
    s = state(uid, now)
    out = {"day": s["day"], "dueIn": s["dueIn"], "done": s["done"],
           "party": db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=? AND on_desktop=1", (uid,))["c"]}
    if s["done"]:
        out["result"] = s["result"]
        out["reward"] = dict(REWARD) if s["result"] == "win" else None
    return out


def _view(r, already):
    d = _unpack(r["data"])
    return {"day": r["day"], "result": r["result"], "events": d["events"], "ids": d["ids"],
            "reward": d.get("reward"), "exp": [], "already": already}


def _insert(uid, day, result, data, reward, at):
    """줄과 볼 · 돈을 한 트랜잭션으로. 줄을 넣었으면 True (보상을 줬다)."""
    sql_r = ("INSERT INTO airraid (user_id, day, seed, result, data, created_at) VALUES (?,?,?,?,?,?)"
             " ON CONFLICT(user_id, day) DO NOTHING")
    sql_u = "UPDATE users SET balls=balls+?, money=money+? WHERE id=?"
    args = (uid, day, data["seed"], result, _pack(data), at)
    if db.using_turso():
        cur = db.run(sql_r, args)
        if not getattr(cur, "rowcount", 1):
            return False
        if reward:
            db.run(sql_u, (reward["balls"], reward["money"], uid))
        return True
    conn = db.connect()
    try:
        if conn.in_transaction:
            conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(sql_r, args)
        ok = bool(cur.rowcount)
        if ok and reward:
            conn.execute(sql_u, (reward["balls"], reward["money"], uid))
        conn.commit()
        return ok
    except Exception:
        try:
            conn.rollback()
        except Exception:                                   # noqa: BLE001
            pass
        raise


def start(uid, hour=None, now=None):
    now = _now(now)
    day = day_of(now)
    if now < due_at(uid, day):
        raise HTTPException(409, "아직 오늘 공습 시각이 아니에요.")
    r = _row(uid, day)
    if r is not None:
        return _view(r, True)
    rows = db.q("SELECT * FROM pokemon WHERE user_id=? AND on_desktop=1 ORDER BY slot, id", (uid,))
    if not rows:
        raise HTTPException(409, "바탕화면에 포켓몬이 없어요.")
    dex = deps.dex()
    mons = [db.row_to_mon(x) for x in rows]
    seed = _crc("airraid-seed", uid, day)
    import random
    foes = CR.roll_raiders(dex, [m["level"] for m in mons], random.Random(seed), lo=config.WILD_MIN_LEVEL)
    if not foes:
        raise HTTPException(500, "공습 포켓몬을 뽑지 못했어요.")
    out = CR.AirRaid(dex, mons, foes, seed=seed).run()
    reward = dict(REWARD) if out["result"] == "win" else None
    ids = [m["id"] for m in mons]
    data = {"events": out["events"], "kos": out["kos"], "ids": ids, "foes": foes, "reward": reward, "seed": seed}
    if not _insert(uid, day, out["result"], data, reward, now.isoformat()):
        r = _row(uid, day)                          # 동시에 부른 다른 요청이 먼저 넣었다
        if r is None:                               # (Turso 복제본은 쓴 직후 읽기가 늦을 수 있다)
            raise HTTPException(409, "오늘 공습을 정리하는 중이에요. 잠시 뒤 다시 해 주세요.")
        return _view(r, True)
    from . import battle_routes
    grants = []
    for fi, mi in out["kos"]:
        try:
            grants += battle_routes.award(dex, uid, B.Fighter(dex, foes[fi]), ids[mi],
                                          hour=hour if hour is not None and 0 <= hour < 24 else None)
        except Exception as e:                              # noqa: BLE001
            print("[airraid] 경험치 실패 %s: %r" % (uid, e))
    return {"day": day, "result": out["result"], "events": out["events"], "ids": ids, "reward": reward,
            "exp": grants, "already": False}


def prune(now=None, keep_days=KEEP_DAYS):
    cut = (_now(now) - datetime.timedelta(days=keep_days)).isoformat()
    cur = db.run("DELETE FROM airraid WHERE created_at < ?", (cut,))
    return cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0


# ---------------------------------------------------------------- 라우트
class StartIn(BaseModel):
    hour: int = -1


@router.get("/api/airraid")
def get_state(ctx=Depends(deps.current)):
    return state(ctx["user"]["id"])


@router.post("/api/airraid/start")
def post_start(body: StartIn, ctx=Depends(deps.current)):
    return start(ctx["user"]["id"], hour=body.hour)
