# -*- coding: utf-8 -*-
"""관장 도전 API 검사. 서버를 띄워 놓고 돌린다.

    python server/test_gym.py http://127.0.0.1:8788 /tmp/poket-test.db

두 번째 인자(DB 경로)는 **강한 파티를 만드는 데만** 쓴다. 이기는 판을
보려면 Lv.100 이 있어야 하는데, 배틀로 키우면 몇 시간이 걸린다.

못 박는 것.

  1. 256곳이 다 나오고, 지도·트레이너·도트가 받아진다.
  2. **상대의 기술·특성은 붙기 전에 새지 않는다.**
  3. 한 번에 한 판. 다른 곳을 시작하면 막고, 같은 곳이면 이어서 한다.
  4. 교체 규칙은 서버가 지킨다(쓰러진 채로 기술 X, 쓰러진 포켓몬으로 교체 X).
  5. **이기면 기록되고 상금이 나온다.** 처음 50원x레벨, 다시 이기면 5원x레벨을
     하루 한 번. 진 판·기권한 판은 아무것도 안 준다.
  6. **겹친 요청이 턴을 두 번 먹지 않는다.**
  7. 오래 손 놓은 판은 접힌다.
"""
import gzip
import json
import random
import sqlite3
import sys
import threading
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788").rstrip("/")
DB = sys.argv[2] if len(sys.argv) > 2 else None
OK = FAIL = 0


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
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                b = gzip.decompress(b)
            if raw:
                # uvicorn 은 머리글 이름을 소문자로 보낸다
                return r.status, b, {k.lower(): v for k, v in r.headers.items()}
            return r.status, json.loads(b.decode() or "{}")
    except urllib.error.HTTPError as e:
        b = e.read()
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


def best_move(view):
    me = view["me"]["team"][view["me"]["slot"]]
    moves = [m for m in me["moves"] if m["pp"] > 0]
    return max(moves, key=lambda m: (m.get("power") or 0))["key"]


def play(bid, token, pick, limit=400):
    """판이 끝날 때까지. 마지막 응답과 받은 경험치를 돌려준다."""
    last, exp = None, []
    for _ in range(limit):
        st, r = call("GET", "/api/gym/battle", token=token)
        if st != 200:
            break
        v = r["battle"]
        if v["needSwitch"]:
            slots = [i for i, m in enumerate(v["me"]["team"]) if not m["fainted"]]
            st, last = call("POST", "/api/gym/battle/%d/act" % bid,
                            {"kind": "switch", "slot": slots[0]}, token)
        else:
            st, last = call("POST", "/api/gym/battle/%d/act" % bid,
                            {"kind": "move", "move": pick(v)}, token)
        if st != 200:
            return st, last, exp
        exp.extend(last.get("exp") or [])
        if last["battle"]["over"]:
            return st, last, exp
    return 0, last, exp


def give_strong(uid):
    """Lv.100 뮤츠를 파티 두 번째 자리에. 이기는 판을 보려고."""
    con = sqlite3.connect(DB)
    con.execute("INSERT INTO pokemon (user_id, species, nickname, level, exp, nature, ability,"
                " hidden_ability, gender, shiny, happiness, ivs, evs, moves, on_desktop, slot,"
                " met_level, caught_at, hyper, no_evolve, luxury, held)"
                " VALUES (?,?,NULL,100,1250000,'HARDY','PRESSURE',0,'N',0,70,?,?,?,1,1,100,"
                "'2026-01-01','{}',0,0,NULL)",
                (uid, "MEWTWO", json.dumps({s: 31 for s in ("hp", "atk", "def", "spa", "spd", "spe")}),
                 json.dumps({s: 85 for s in ("hp", "atk", "def", "spa", "spd", "spe")}),
                 json.dumps(["PSYSTRIKE", "AURASPHERE", "ICEBEAM", "FLAMETHROWER"])))
    # 스타팅은 무작위라(피카츄는 스타팅 목록에 없다) 뮤츠가 아닌 것을 전부 뒤로
    con.execute("UPDATE pokemon SET slot=2 WHERE user_id=? AND species!='MEWTWO'", (uid,))
    con.execute("UPDATE pokemon SET slot=0 WHERE user_id=? AND species='MEWTWO'", (uid,))
    con.commit()
    con.close()


def main():
    tag = random.randint(1000, 9999)
    token, uid = register("관장%d" % tag)

    print("=== 자료 ===")
    st, g = call("GET", "/api/gym", token=token)
    chk("요약이 온다", st == 200, (st, g))
    chk("256곳", len(g.get("regions", [])) == 256 and g.get("total") == 256, len(g.get("regions", [])))
    chk("처음엔 이긴 곳이 없다", g.get("cleared") == 0, g.get("cleared"))
    levels = sorted({r["level"] for r in g["regions"]})
    chk("레벨이 20~100, 5 단위 17단계", levels == list(range(20, 101, 5)), levels)
    chk("요약에는 팀이 없다", all("team" not in r for r in g["regions"]))

    st, raw, headers = call("GET", "/api/gym/map", raw=True)
    m = json.loads(raw.decode())
    chk("지도가 온다 (시군구 256)", st == 200 and len(m["sgg"]) == 256, len(m.get("sgg", [])))
    chk("지도 요약값이 요약과 같다", headers.get("x-digest") == g.get("mapDigest"),
        (headers.get("x-digest"), g.get("mapDigest")))

    seoul = next(r for r in g["regions"] if r["name"] == "난천")
    st, card = call("GET", "/api/gym/trainer/%s" % seoul["region"], token=token)
    chk("트레이너 카드", st == 200 and card["level"] == 100 and len(card["team"]) == 6, (st, card))
    leak = [k for m2 in card.get("team", []) for k in ("moves", "ability", "held") if k in m2]
    chk("붙기 전에 기술·특성·도구가 새지 않는다", not leak, leak)
    chk("에이스(한카리아스)가 마지막", card["team"][-1]["species"] == "GARCHOMP", card["team"][-1])
    chk("처음 이기면 상금 5,000원이라고 알려 준다", card["prize"] == 5000, card["prize"])
    # 여러 타입을 섞는 챔피언에게 '땅 타입을 주로 쓴다' 고 붙이면 틀린 말이다
    chk("섞어 쓰는 트레이너에게는 전문 타입을 안 붙인다", card.get("typeKr") is None, card.get("typeKr"))
    brycen = next(r for r in g["regions"] if r["name"] == "담죽")
    st, bc = call("GET", "/api/gym/trainer/%s" % brycen["region"], token=token)
    chk("얼음 관장은 '얼음'", st == 200 and bc.get("typeKr") == "얼음", bc.get("typeKr"))
    ice = sum(1 for m2 in bc.get("team", []) if "얼음" in m2.get("types", []))
    chk("얼음 관장 팀의 대부분이 얼음 타입", ice >= 4, [m2.get("kr") for m2 in bc.get("team", [])])

    st, png, _h = call("GET", "/api/gym/sprite/%s" % seoul["sprite"], raw=True)
    chk("트레이너 도트", st == 200 and png[:4] == b"\x89PNG", st)
    st, _ = call("GET", "/api/gym/sprite/..%2F..%2Fetc%2Fpasswd", raw=True)
    chk("도트 경로로 다른 파일을 못 읽는다", st == 404, st)
    st, _ = call("GET", "/api/gym/trainer/99999", token=token)
    chk("없는 지역은 404", st == 404, st)

    egg = next(r for r in g["regions"] if r["name"] == "나여조경석")
    st, ec = call("GET", "/api/gym/trainer/%s" % egg["region"], token=token)
    chk("이스터에그 에이스는 렌트라 (칠색조 대신 디아루가)",
        [m["species"] for m in ec.get("team", [])] == ["ARCEUS", "KYOGRE", "GROUDON", "DIALGA", "MEWTWO", "LUXRAY"],
        [m["species"] for m in ec.get("team", [])])
    chk("능력치 배율은 붙기 전에 새지 않는다", not any("boost" in m for m in ec.get("team", [])))
    chk("나여조경석은 개발자", ec.get("role") == "개발자", ec.get("role"))
    chk("나여조경석 소개 문구", ec.get("why") == "이스터에그 — 포스크탑 개발자", ec.get("why"))
    jw = next(r for r in g["regions"] if r["name"] == "지우")
    st, jc = call("GET", "/api/gym/trainer/%s" % jw["region"], token=token)
    chk("지우: 새 도트와 팀 (에이스 따라큐)", jc.get("sprite") == "jiwoo" and jc["team"][-1]["species"] == "MIMIKYU",
        (jc.get("sprite"), [m["species"] for m in jc.get("team", [])]))
    st, png, _h = call("GET", "/api/gym/sprite/jiwoo", raw=True)
    chk("지우 도트", st == 200 and png[:4] == b"\x89PNG", st)
    chk("이스터에그: 카드 그림과 배틀 그림이 따로", ec.get("sprite") == "easter-egg"
        and ec.get("battleSprite") == "easter-egg-solo", (ec.get("sprite"), ec.get("battleSprite")))
    for key in ("easter-egg", "easter-egg-solo"):
        st, png, _h = call("GET", "/api/gym/sprite/%s" % key, raw=True)
        chk("이스터에그 도트 %s" % key, st == 200 and png[:4] == b"\x89PNG", st)
    chk("다른 트레이너는 배틀 그림이 카드 그림과 같다", card.get("battleSprite") == card.get("sprite"),
        (card.get("sprite"), card.get("battleSprite")))

    print("\n=== 시작과 겹침 ===")
    low = [r for r in g["regions"] if r["level"] == 20]
    a, b = low[0], low[1]
    st, s1 = call("POST", "/api/gym/%s/start" % a["region"], token=token)
    chk("도전 시작", st == 200 and s1["battle"]["turn"] == 0, (st, s1))
    chk("시작 이벤트에 인사와 등장이 있다",
        [e["t"] for e in s1["events"]][:3] == ["intro", "switch", "switch"], [e["t"] for e in s1["events"]])
    foe = s1["battle"]["foe"]
    chk("나오지 않은 상대는 가려져 있다", sum(1 for x in foe["team"] if x.get("hidden")) == 5, foe)
    chk("나온 상대의 기술은 안 보인다", "moves" not in foe["team"][0], foe["team"][0].keys())
    bid = s1["id"]
    st, r = call("POST", "/api/gym/%s/start" % b["region"], token=token)
    chk("다른 곳을 시작하면 막는다 (409)", st == 409, (st, r))
    st, r = call("POST", "/api/gym/%s/start" % a["region"], token=token)
    chk("같은 곳을 다시 누르면 이어서 한다", st == 200 and r.get("resumed") and r["id"] == bid, (st, r))
    st, r = call("GET", "/api/gym", token=token)
    chk("요약에 진행 중인 판이 보인다", r["active"] and r["active"]["id"] == bid, r.get("active"))

    st, r = call("POST", "/api/gym/battle/%d/act" % bid, {"kind": "dance"}, token)
    chk("모르는 행동은 400", st == 400, st)
    st, r = call("POST", "/api/gym/battle/%d/act" % bid, {"kind": "switch", "slot": 7}, token)
    chk("없는 자리로 교체는 409", st == 409, (st, r))

    st, r = call("POST", "/api/gym/battle/%d/act" % bid, {"kind": "forfeit"}, token)
    chk("기권", st == 200 and r["battle"]["over"] and r["battle"]["result"] == "forfeit", (st, r))
    chk("기권해도 상금은 없다", "reward" not in r, r.get("reward"))
    st, r = call("POST", "/api/gym/battle/%d/act" % bid, {"kind": "move", "move": "TACKLE"}, token)
    chk("끝난 판에는 못 둔다 (409)", st == 409, st)

    print("\n=== 겹친 요청 ===")
    # **새 판에서** 한다. 약한 스타팅이라 몇 턴이면 끝나서, 이 검사 뒤에는
    # 판이 남아 있다는 보장이 없다.
    st, s1b = call("POST", "/api/gym/%s/start" % a["region"], token=token)
    bid = s1b["id"]
    res = []

    def fire():
        res.append(call("POST", "/api/gym/battle/%d/act" % bid,
                        {"kind": "move", "move": "THUNDERSHOCK"}, token)[0])
    ths = [threading.Thread(target=fire) for _ in range(6)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    st, cur = call("GET", "/api/gym/battle", token=token)
    ok200 = res.count(200)
    turn = cur["battle"]["turn"] if st == 200 else None
    if st != 200:
        # 판이 끝났다. 끝난 판의 턴은 DB 에서 직접 본다.
        con = sqlite3.connect(DB) if DB else None
        turn = con.execute("SELECT turn FROM gym_battle WHERE id=?", (bid,)).fetchone()[0] if con else None
    chk("동시에 여섯 번 보내도 성공한 만큼만 턴이 간다", turn is None or turn == ok200,
        (res, turn))
    chk("겹친 요청 중 적어도 하나는 들어간다", ok200 >= 1, res)
    call("POST", "/api/gym/battle/%d/act" % bid, {"kind": "forfeit"}, token)

    if not DB:
        print("\n(DB 경로를 안 줘서 이기는 판·강제 교체·만료는 건너뜁니다)")
    else:
        print("\n=== 이기는 판 ===")
        give_strong(uid)
        st, me = call("GET", "/api/me", token=token)
        money0 = me.get("money")
        st, s2 = call("POST", "/api/gym/%s/start" % b["region"], token=token)
        chk("뮤츠로 Lv.20 에 도전", st == 200 and s2["battle"]["me"]["team"][0]["species"] == "MEWTWO",
            (st, s2.get("battle", {}).get("me")))
        st, last, exp = play(s2["id"], token, best_move)
        chk("이긴다", last and last["battle"]["result"] == "won", (st, last and last["battle"].get("result")))
        rw = (last or {}).get("reward") or {}
        chk("처음 이기면 레벨 x 50 원", rw.get("prize") == b["level"] * 50 and rw.get("first"), rw)
        chk("돈이 그만큼 늘었다", rw.get("money") == (money0 or 0) + b["level"] * 50, (money0, rw))
        chk("이긴 곳이 1곳", rw.get("cleared") == 1, rw)
        chk("쓰러뜨릴 때마다 경험치 (학습장치로 스타팅도)", any(e.get("shared") for e in exp),
            [(e.get("level"), e.get("shared")) for e in exp][:6])
        st, g2 = call("GET", "/api/gym", token=token)
        mark = next(r2 for r2 in g2["regions"] if r2["region"] == b["region"])
        chk("요약에 이긴 곳으로 표시", mark["cleared"] and mark["wins"] == 1, mark)

        # 처음 이긴 날은 그날 몫을 이미 받은 것이다. 같은 날 다시 이기면 0원.
        st, s3 = call("POST", "/api/gym/%s/start" % b["region"], token=token)
        st, last, _ = play(s3["id"], token, best_move)
        rw = (last or {}).get("reward") or {}
        chk("처음 이긴 날 또 이기면 상금 없음", rw.get("prize") == 0 and not rw.get("first"), rw)
        # 하루가 지났다고 친다
        con = sqlite3.connect(DB)
        con.execute("UPDATE gym_clear SET paid_on='2000-01-01' WHERE user_id=? AND region=?",
                    (uid, b["region"]))
        con.commit()
        con.close()
        st, s4 = call("POST", "/api/gym/%s/start" % b["region"], token=token)
        st, last, _ = play(s4["id"], token, best_move)
        rw = (last or {}).get("reward") or {}
        chk("다음 날 다시 이기면 레벨 x 5 원", rw.get("prize") == b["level"] * 5, rw)
        st, s5b = call("POST", "/api/gym/%s/start" % b["region"], token=token)
        st, last, _ = play(s5b["id"], token, best_move)
        rw = (last or {}).get("reward") or {}
        chk("그날 또 이기면 다시 0원", rw.get("prize") == 0, rw)
        st, g3 = call("GET", "/api/gym", token=token)
        mark = next(r2 for r2 in g3["regions"] if r2["region"] == b["region"])
        chk("이긴 횟수는 계속 센다", mark["wins"] == 4, mark)

        print("\n=== 지는 판과 강제 교체 ===")
        token2, uid2 = register("관장패%d" % tag)
        top = next(r2 for r2 in g["regions"] if r2["level"] == 100 and r2["name"] == "레드")
        st, s5 = call("POST", "/api/gym/%s/start" % top["region"], token=token2)
        bid5 = s5["id"]
        for _ in range(30):
            st, r = call("POST", "/api/gym/battle/%d/act" % bid5,
                         {"kind": "move", "move": best_move(s5["battle"])}, token2)
            if r["battle"]["over"] or r["battle"]["needSwitch"]:
                break
        chk("스타팅 한 마리로 레드에게 진다", r["battle"]["over"] and r["battle"]["result"] == "lost",
            r["battle"].get("result"))
        chk("진 판에는 상금이 없다", "reward" not in r, r.get("reward"))
        st, g4 = call("GET", "/api/gym", token=token2)
        chk("진 곳은 기록되지 않는다", g4["cleared"] == 0, g4["cleared"])

        # 두 마리면 쓰러진 뒤 교체를 묻는다
        con = sqlite3.connect(DB)
        con.execute("INSERT INTO pokemon (user_id, species, nickname, level, exp, nature, ability,"
                    " hidden_ability, gender, shiny, happiness, ivs, evs, moves, on_desktop, slot,"
                    " met_level, caught_at, hyper, no_evolve, luxury, held)"
                    " VALUES (?,'MAGIKARP',NULL,5,100,'HARDY','SWIFTSWIM',0,'M',0,70,'{}','{}',"
                    "'[\"SPLASH\"]',1,1,5,'2026-01-01','{}',0,0,NULL)", (uid2,))
        con.commit()
        con.close()
        st, s6 = call("POST", "/api/gym/%s/start" % top["region"], token=token2)
        bid6 = s6["id"]
        r = s6
        for _ in range(30):
            st, r = call("POST", "/api/gym/battle/%d/act" % bid6,
                         {"kind": "move", "move": best_move(r["battle"])}, token2)
            if r["battle"]["needSwitch"] or r["battle"]["over"]:
                break
        chk("쓰러지면 교체를 묻는다", r["battle"]["needSwitch"], r["battle"])
        st, r2 = call("POST", "/api/gym/battle/%d/act" % bid6, {"kind": "move", "move": "SPLASH"}, token2)
        chk("교체해야 할 때 기술은 409", st == 409, (st, r2))
        dead = [i for i, x in enumerate(r["battle"]["me"]["team"]) if x["fainted"]][0]
        st, r2 = call("POST", "/api/gym/battle/%d/act" % bid6, {"kind": "switch", "slot": dead}, token2)
        chk("쓰러진 포켓몬으로 교체는 409", st == 409, (st, r2))
        alive = [i for i, x in enumerate(r["battle"]["me"]["team"]) if not x["fainted"]][0]
        st, r2 = call("POST", "/api/gym/battle/%d/act" % bid6, {"kind": "switch", "slot": alive}, token2)
        chk("살아 있는 포켓몬으로 교체", st == 200 and r2["battle"]["me"]["slot"] == alive, (st, r2))

        print("\n=== 오래 놔둔 판 ===")
        con = sqlite3.connect(DB)
        con.execute("UPDATE gym_battle SET updated_at='2000-01-01T00:00:00+00:00' WHERE id=?", (bid6,))
        con.commit()
        con.close()
        st, r = call("GET", "/api/gym/battle", token=token2)
        chk("오래 놔둔 판은 접힌다", st == 404, st)
        st, r = call("POST", "/api/gym/battle/%d/act" % bid6, {"kind": "move", "move": "SPLASH"}, token2)
        chk("접힌 판에 두면 410", st == 410, (st, r))

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
