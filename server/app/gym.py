# -*- coding: utf-8 -*-
"""관장 도전 — 자료와 기록.

자료는 두 파일이다. 둘 다 tools/ 가 만들어 저장소에 들어 있다.

    data/gyms.json        256곳의 트레이너와 팀 (tools/build_gyms.py)
    data/korea_map.json   시·도 / 시·군·구 경계 (tools/build_korea_map.py)

기록은 DB 의 gym_clear(이긴 곳)와 gym_battle(진행 중인 판)이다.
"""
import datetime
import gzip
import hashlib
import json
import os

from . import config, db

_GYMS = None
_MAP = None


def gyms():
    global _GYMS
    if _GYMS is None:
        with open(config.GYMS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        by_id = {t["id"]: t for t in raw["trainers"]}
        raw["_by_id"] = by_id
        raw["_by_region"] = {code: by_id[tid] for code, tid in raw["regions"].items()}
        _GYMS = raw
    return _GYMS


def korea_map():
    """(gzip 한 본문, 요약값). 710KB 를 매번 읽지 않게 한 번만 만든다."""
    global _MAP
    if _MAP is None:
        with open(config.KOREA_MAP_PATH, "rb") as f:
            raw = f.read()
        _MAP = (gzip.compress(raw, 6), hashlib.sha256(raw).hexdigest()[:16])
    return _MAP


def trainer_at(region):
    return gyms()["_by_region"].get(region)


def trainer(tid):
    return gyms()["_by_id"].get(tid)


def today_kst():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date().isoformat()


def public(t, dex, full=False):
    """화면에 보낼 트레이너. full 이면 팀(종·레벨)까지.

    기술·특성·도구는 보내지 않는다. 붙어 보기 전에 다 알면 재미가 없다 -
    원작도 상대 포켓몬이 무엇인지까지만 알 수 있다.
    """
    out = {"id": t["id"], "name": t["name"], "role": t["role"], "sprite": t["sprite"],
           "battleSprite": t.get("battleSprite") or t["sprite"],
           "level": t["level"], "type": main_type(t, dex),
           "region": t.get("region"), "why": t.get("why") or ""}
    out["typeKr"] = dex.type_name(out["type"]) if out["type"] else None
    if full:
        team = []
        for m in t["team"]:
            sp = dex.get(m["species"]) or {}
            team.append({"species": m["species"], "num": sp.get("num"), "kr": sp.get("kr"),
                         "level": m["level"],
                         "types": [dex.type_name(x) for x in sp.get("types", [])]})
        out["team"] = team
    return out


def main_type(t, dex):
    """'이 타입을 주로 쓴다' 고 말할 수 있는 타입. 없으면 None.

    자료의 type 은 배치에 쓰려고 **가장 많은 타입**을 무조건 하나 골라 둔
    값이다. 난천(한카리아스 한 마리뿐인 땅)이나 단델(고스트 둘)처럼 여러
    타입을 섞어 쓰는 트레이너에게 그대로 붙이면 틀린 말이 된다. 여섯 중
    셋 이상이 그 타입일 때만 전문 타입으로 친다.
    """
    ty = t.get("type")
    if not ty:
        return None
    n = sum(1 for m in t.get("team") or [] if ty in ((dex.get(m["species"]) or {}).get("types") or []))
    return ty if n >= 3 else None


def clears(uid):
    return {r["region"]: r for r in db.q("SELECT * FROM gym_clear WHERE user_id=?", (uid,))}


def record_win(uid, t, turns, now):
    """이긴 것을 적고 상금을 정한다. (상금, 처음 이겼나)"""
    region = t["region"]
    row = db.q1("SELECT * FROM gym_clear WHERE user_id=? AND region=?", (uid, region))
    today = today_kst()
    if not row:
        db.run("INSERT INTO gym_clear (user_id, region, trainer, wins, best_turns, first_at,"
               " last_at, paid_on) VALUES (?,?,?,1,?,?,?,?)",
               (uid, region, t["id"], turns, now, now, today))
        return t["level"] * config.GYM_PRIZE_PER_LEVEL, True
    best = min(row["best_turns"] or turns, turns)
    pay = 0
    if row["paid_on"] != today:
        pay = t["level"] * config.GYM_REPEAT_PER_LEVEL
    db.run("UPDATE gym_clear SET wins=wins+1, best_turns=?, last_at=?, trainer=?,"
           " paid_on=? WHERE user_id=? AND region=?",
           (best, now, t["id"], today if pay else row["paid_on"], uid, region))
    return pay, False


def sprite_path(key):
    safe = "".join(c for c in (key or "") if c.isalnum() or c == "-")
    if not safe:
        return None
    p = os.path.join(config.TRAINER_SPRITE_DIR, safe + ".png")
    return p if os.path.exists(p) else None
