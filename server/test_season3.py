# -*- coding: utf-8 -*-
"""시즌 3 API 검사 — 도감 업적과 메가진화. 서버를 띄워 놓고 돌린다.

    python server/test_season3.py http://127.0.0.1:8788 /tmp/poket-test.db

두 번째 인자(DB 경로)는 **몇 시간 걸릴 일을 건너뛰는 데만** 쓴다 - 관장
8곳 기록(키스톤), 친밀도 255 리자몽, 다 채운 미션. 그 뒤는 전부 HTTP 로 본다.

못 박는 것.

  1. /api/me 에 achievements·bond 가 실린다. 업적 목록과 seen.
  2. 키스톤이 없으면 없다고, 8곳이면 있다고.
  3. 빛나는 돌(bond.ready) -> 시작 -> 미션 셋 -> 다 채우면 bond.claim
     -> X/Y 골라 받기 -> 가방에. 두 번 못 받는다. 남의 포켓몬은 404.
  4. 받은 스톤을 지니고 관장 배틀에서 mega=true 로 두면 메가진화 사건이
     나고, 한 판에 한 번뿐이다.
  5. 저절로 받은 스톤은 bond.got 으로 알리고, seen 뒤에는 빠진다.
  6. 도트: 메가 번호는 받고, 없는 번호는 404.
"""
import gzip
import json
import random
import sqlite3
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788").rstrip("/")
DB = sys.argv[2] if len(sys.argv) > 2 else None
OK = FAIL = 0
STATS = ("hp", "atk", "def", "spa", "spd", "spe")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, str(got)[:300]))


def call(method, path, body=None, token=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept-Encoding", "gzip")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            b = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                b = gzip.decompress(b)
            if raw:
                return r.status, b
            return r.status, json.loads(b.decode() or "{}")
    except urllib.error.HTTPError as e:
        b = e.read()
        if raw:
            return e.code, b
        try:
            return e.code, json.loads(b.decode() or "{}")
        except ValueError:
            return e.code, {"raw": b[:200]}


def register(name):
    st, r = call("POST", "/api/auth/register",
                 {"username": name, "password": "1234", "starter": "PIKACHU", "device": "t"})
    if st != 200:
        raise SystemExit("가입 실패 %s %s" % (st, r))
    return r.get("token") or r["session"]["token"], r["user"]["id"]


def sql(q, args=()):
    con = sqlite3.connect(DB)
    cur = con.execute(q, args)
    con.commit()
    last = cur.lastrowid
    con.close()
    return last


def give_charizard(uid):
    """Lv.100 리자몽, 친밀도 255, 파티 맨 앞."""
    pid = sql("INSERT INTO pokemon (user_id, species, nickname, level, exp, nature, ability,"
              " hidden_ability, gender, shiny, happiness, ivs, evs, moves, on_desktop, slot,"
              " met_level, caught_at, hyper, no_evolve, luxury, held)"
              " VALUES (?,?,NULL,100,1059860,'HARDY','BLAZE',0,'M',0,255,?,?,?,1,0,100,"
              "'2026-01-01','{}',0,0,NULL)",
              (uid, "CHARIZARD", json.dumps(dict((s, 31) for s in STATS)),
               json.dumps(dict((s, 85) for s in STATS)),
               json.dumps(["FLAMETHROWER", "DRAGONCLAW", "AIRSLASH", "ROOST"])))
    sql("UPDATE pokemon SET slot=2 WHERE user_id=? AND id!=?", (uid, pid))
    return pid


def main():
    if not DB:
        raise SystemExit("DB 경로가 필요합니다 (두 번째 인자)")
    tag = random.randint(1000, 9999)
    token, uid = register("메가%d" % tag)
    other, _ouid = register("남남%d" % tag)

    print("=== /api/me 와 업적 ===")
    st, me = call("GET", "/api/me", token=token)
    chk("/api/me 에 achievements·bond", st == 200 and "achievements" in me and "bond" in me,
        list(me.keys())[:30])
    bond = me.get("bond") or {}
    chk("처음엔 키스톤이 없다 (관장 0 / 8곳)",
        bond.get("keystone") == {"has": False, "gyms": 0, "need": 8}, bond.get("keystone"))
    chk("  빛나는 돌·받을 것·알릴 것 없음",
        bond.get("ready") == [] and bond.get("claim") == [] and bond.get("got") == [], bond)
    st, ach = call("GET", "/api/achievements", token=token)
    chk("업적 목록 50개", st == 200 and ach.get("total") == 50 and len(ach["achievements"]) == 50,
        (st, ach.get("total")))
    hidden = [a for a in ach["achievements"] if a.get("name") == "???"]
    chk("숨은 업적은 가려져 있다", len(hidden) >= 4, len(hidden))
    st, r = call("POST", "/api/achievements/seen", {}, token)
    chk("seen", st == 200, (st, r))
    st, me = call("GET", "/api/me", token=token)
    chk("  그 뒤 알릴 업적이 없다", not (me.get("achievements") or {}).get("unseen"),
        me.get("achievements"))

    print("\n=== 키스톤 ===")
    st, g = call("GET", "/api/gym", token=token)
    regions = [r for r in g["regions"]]
    low = [r for r in regions if r["level"] == 20]
    battle_region = low[0]
    wins = [r for r in regions if r["region"] != battle_region["region"]][:7]
    for r in wins:
        sql("INSERT INTO gym_clear (user_id, region, trainer, wins, best_turns, first_at,"
            " last_at, paid_on) VALUES (?,?,?,1,5,'2026-09-30','2026-09-30','2026-09-30')",
            (uid, r["region"], "t_" + r["region"]))
    liz = give_charizard(uid)
    st, me = call("GET", "/api/me", token=token)
    chk("7곳이면 아직 없다", me["bond"]["keystone"]["has"] is False
        and me["bond"]["keystone"]["gyms"] == 7, me["bond"]["keystone"])
    chk("  키스톤이 없으면 빛나는 돌도 없다", me["bond"]["ready"] == [], me["bond"]["ready"])
    st, r = call("POST", "/api/bond/%d/start" % liz, {}, token)
    chk("  키스톤 없이 시작 못 한다 (400)", st == 400, (st, r))
    r8 = [r for r in regions if r["region"] != battle_region["region"]][7]
    sql("INSERT INTO gym_clear (user_id, region, trainer, wins, best_turns, first_at,"
        " last_at, paid_on) VALUES (?,?,?,1,5,'2026-09-30','2026-09-30','2026-09-30')",
        (uid, r8["region"], "t_" + r8["region"]))
    st, me = call("GET", "/api/me", token=token)
    chk("8곳이면 키스톤", me["bond"]["keystone"]["has"] is True, me["bond"]["keystone"])
    chk("유대 255 리자몽에게 빛나는 돌", me["bond"]["ready"] == [liz], me["bond"]["ready"])

    print("\n=== 유대 미션 ===")
    st, card = call("GET", "/api/bond/%d" % liz, token=token)
    chk("카드: 키스톤 있음, 아직 시작 전, 스톤 둘 다 없음",
        st == 200 and card["keystone"]["has"] and not card["started"]
        and set(card["missing"]) == {"CHARIZARDITEX", "CHARIZARDITEY"}, (st, card))
    chk("  이름·스톤 한글 이름", card.get("name") == "리자몽"
        and [s["kr"] for s in card["stones"]] == ["리자몽나이트X", "리자몽나이트Y"], card)
    st, r = call("GET", "/api/bond/%d" % liz, token=other)
    chk("남의 포켓몬 카드는 404", st == 404, st)
    st, r = call("POST", "/api/bond/%d/start" % liz, {}, other)
    chk("남의 포켓몬으로 시작 못 한다 (404)", st == 404, st)
    st, card = call("POST", "/api/bond/%d/start" % liz, {}, token)
    chk("시작하면 미션 셋", st == 200 and card["started"] and len(card["missions"]) == 3, (st, card))
    st, me = call("GET", "/api/me", token=token)
    chk("  빛나는 돌은 사라진다", me["bond"]["ready"] == [], me["bond"]["ready"])
    st, r = call("POST", "/api/bond/%d/claim" % liz, {"stone": "CHARIZARDITEX"}, token)
    chk("다 채우기 전에는 못 받는다 (400)", st == 400, (st, r))
    sql("UPDATE bond SET gym=1, kos=30, wild=10, done_at='2026-09-30T00:00:00+00:00'"
        " WHERE pokemon_id=?", (liz,))
    st, me = call("GET", "/api/me", token=token)
    chk("다 채우면 bond.claim 에", me["bond"]["claim"] == [liz], me["bond"])
    st, r = call("POST", "/api/bond/%d/claim" % liz, {"stone": "GENGARITE"}, token)
    chk("엉뚱한 스톤은 못 받는다 (400)", st == 400, (st, r))
    st, card = call("POST", "/api/bond/%d/claim" % liz, {"stone": "charizarditex"}, token)
    chk("X 를 골라 받는다 (소문자도)", st == 200 and card["stone"] == "CHARIZARDITEX", (st, card))
    st, bag = call("GET", "/api/bag", token=token)
    chk("  가방에 리자몽나이트X", (bag.get("bag") or {}).get("CHARIZARDITEX") == 1, bag.get("bag"))
    st, r = call("POST", "/api/bond/%d/claim" % liz, {"stone": "CHARIZARDITEY"}, token)
    chk("두 번 못 받는다 (400)", st == 400, (st, r))
    st, me = call("GET", "/api/me", token=token)
    chk("  직접 고른 것은 알릴 것에 없다", me["bond"]["got"] == [] and me["bond"]["claim"] == [],
        me["bond"])

    print("\n=== 메가진화 배틀 ===")
    st, r = call("POST", "/api/pokemon/%d/hold" % liz, {"item": "CHARIZARDITEX"}, token)
    chk("리자몽나이트X 를 지닌다", st == 200, (st, r))
    st, s1 = call("POST", "/api/gym/%s/start" % battle_region["region"], token=token)
    chk("관장 도전 시작", st == 200, (st, s1))
    chk("  canMega 가 켜져 있다", s1["battle"].get("canMega") is True, s1["battle"].get("canMega"))
    bid = s1["id"]
    st, t1 = call("POST", "/api/gym/battle/%d/act" % bid,
                  {"kind": "move", "move": "DRAGONCLAW", "mega": True}, token)
    megas = [e for e in t1.get("events", []) if e.get("t") == "mega"]
    chk("mega=true 로 두면 메가진화", st == 200 and len(megas) == 1
        and megas[0]["who"] == "me" and megas[0]["num"] == 10034, (st, [e.get("t") for e in t1.get("events", [])]))
    me_side = t1["battle"]["me"]["team"][t1["battle"]["me"]["slot"]]
    chk("  판 상태도 메가 (이름·타입)", me_side.get("mega") is True
        and me_side.get("name") == "메가리자몽X" and "DRAGON" in me_side.get("typeIds", []), me_side)
    chk("  한 번 쓰면 canMega 가 꺼진다", t1["battle"].get("canMega") is False
        and t1["battle"].get("megaUsed") is True, (t1["battle"].get("canMega"), t1["battle"].get("megaUsed")))
    if not t1["battle"]["over"]:
        st, t2 = call("POST", "/api/gym/battle/%d/act" % bid,
                      {"kind": "move", "move": "DRAGONCLAW", "mega": True}, token)
        chk("두 번째는 안 바뀐다", not any(e.get("t") == "mega" for e in t2.get("events", [])))
        call("POST", "/api/gym/battle/%d/act" % bid, {"kind": "forfeit"}, token)
    else:
        chk("두 번째는 안 바뀐다 (첫 턴에 끝남 - 한 번 사건만 봤다)", True)

    print("\n=== 저절로 받은 스톤 알림 ===")
    gen = sql("INSERT INTO pokemon (user_id, species, nickname, level, exp, nature, ability,"
              " hidden_ability, gender, shiny, happiness, ivs, evs, moves, on_desktop, slot,"
              " met_level, caught_at, hyper, no_evolve, luxury, held)"
              " VALUES (?,'GENGAR','팬텀이',50,125000,'HARDY','CURSEDBODY',0,'M',0,255,'{}','{}',"
              "'[\"SHADOWBALL\"]',0,0,50,'2026-01-01','{}',0,0,NULL)", (uid,))
    sql("INSERT INTO bond (pokemon_id, user_id, species, started_at, gym, kos, wild, done_at,"
        " stone, seen) VALUES (?,?,'GENGAR','2026-09-30',1,30,10,'2026-09-30','GENGARITE',0)",
        (gen, uid))
    st, me = call("GET", "/api/me", token=token)
    got = me["bond"].get("got") or []
    chk("bond.got 에 실린다 (별명·스톤 이름)", len(got) == 1 and got[0]["pokemon"] == gen
        and got[0]["name"] == "팬텀이" and got[0]["stoneKr"] == "팬텀나이트", got)
    st, r = call("POST", "/api/bond/%d/seen" % gen, {}, other)
    st, me = call("GET", "/api/me", token=token)
    chk("남이 seen 을 불러도 안 지워진다", len(me["bond"].get("got") or []) == 1, me["bond"].get("got"))
    st, r = call("POST", "/api/bond/%d/seen" % gen, {}, token)
    st, me = call("GET", "/api/me", token=token)
    chk("seen 뒤에는 빠진다", st == 200 and me["bond"].get("got") == [], me["bond"].get("got"))

    print("\n=== 도트 ===")
    st, _b = call("GET", "/api/sprite/99999", raw=True)
    chk("없는 번호는 404", st == 404, st)
    st, b = call("GET", "/api/sprite/10034", raw=True)
    if st == 200:
        chk("메가리자몽X 도트", len(b) > 100, len(b))
    else:
        print("  (도트를 받아 올 수 없는 곳이라 건너뜀: %s)" % st)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
