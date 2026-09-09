# -*- coding: utf-8 -*-
"""50명 기념 이벤트와 선물함.

서버를 띄워 놓고 돌린다.

    python server/test_event.py http://127.0.0.1:8788

여기서 못 박는 것은 넷이다.

  1. **이벤트를 안 한 사람에게 아무 변화가 없다.** 잡은 뒤에는 평소
     풀숲으로 돌아가야 하고, 다른 종이 골고루 나와야 한다.
  2. **잡을 때까지 다시 나온다.** 풀숲은 90초 뒤 사라지고 자리를 비운
     사이에 지나갈 수 있다. 한 번만 내면 그렇게 놓친 사람이 영영 못 갖는다.
  3. **종은 안 새어 나간다.** 풀숲 상태에서는 꽃이 폈다는 것만 알려준다.
  4. **선물은 두 번 지급되지 않는다.** /api/me 는 90초마다 온다.
"""
import collections
import json
import random
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788").rstrip("/")
DB = None                     # 두 번째 인자로 주면 풀숲 시각을 직접 되돌린다
if len(sys.argv) > 2:
    DB = sys.argv[2]

OK = FAIL = 0
TOKEN = {"v": None}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def call(method, path, body=None, auth=True):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if auth and TOKEN["v"]:
        req.add_header("Authorization", "Bearer " + TOKEN["v"])
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(json.loads(e.read().decode("utf-8")).get("error", ""))


def signup():
    name = "ev%d" % random.randint(100000, 999999)
    r = call("POST", "/api/auth/register", auth=False, body={
        "username": name, "password": "1234", "device": "test",
        "starter": "PIKACHU"})
    TOKEN["v"] = r.get("token") or r["session"]["token"]
    return name


def ready():
    """다음 풀숲을 바로 돋울 수 있게 한다."""
    if not DB:
        return
    import sqlite3
    c = sqlite3.connect(DB)
    c.execute("UPDATE wild_state SET next_at=NULL")
    c.commit()
    c.close()


def grass():
    ready()
    return call("GET", "/api/wild?force=true").get("wild")


def give(name, kind, item=None, count=1):
    """운영자가 SQL 한 줄로 넣는 것과 같은 일."""
    import datetime
    import sqlite3
    c = sqlite3.connect(DB)
    uid = c.execute("select id from users where username=?", (name,)).fetchone()[0]
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    c.execute("INSERT INTO gift (user_id,kind,item_id,count,title,message,"
              "created_at) VALUES (?,?,?,?,'시험','',?)",
              (uid, kind, item, count, now))
    c.commit()
    c.close()


def main():
    name = signup()
    print("계정 %s" % name)

    print("\n=== 볼이 없으면 평범하다 (신규 유저) ===")
    # **여기가 제일 중요하다.** 조건 없이 "안 잡았으면 반드시" 로 하면
    # 새로 가입한 사람의 첫 풀숲이 Lv30 짜리가 되어 게임이 안 굴러간다.
    plain = collections.Counter()
    blooms = 0
    for _ in range(12):
        g = grass()
        if not g:
            continue
        if g.get("bloom"):
            blooms += 1
        r = call("POST", "/api/wild/%d/reveal" % g["id"])
        plain[r["wild"]["pokemon"]["species"]] += 1
        call("POST", "/api/wild/%d/flee" % g["id"])
    chk("이벤트가 안 돋는다 (12번 중 %d)" % blooms, blooms == 0, blooms)
    chk("평범한 종이 여럿 나온다", len(plain) >= 6, len(plain))

    if not DB:
        print("  (DB 경로를 안 줘서 나머지는 건너뜁니다)")
        print()
        print("합계  OK %d   FAIL %d" % (OK, FAIL))
        return 1 if FAIL else 0

    print("\n=== 볼을 받으면 이벤트가 돋는다 ===")
    before = call("GET", "/api/me")
    give(name, "item", "FLOWERBALL", 1)
    give(name, "money", None, 5000)
    me = call("GET", "/api/me")
    gifts = me.get("gifts") or []
    chk("선물이 도착했다", len(gifts) == 2, gifts)
    chk("도구와 돈이 각각", sorted(x["kind"] for x in gifts) == ["item", "money"])
    chk("**같은 응답의 지갑이 이미 늘어 있다**",
        me["money"] == before["money"] + 5000, (before["money"], me["money"]))
    chk("가방에 들어왔다", (me.get("bag") or {}).get("FLOWERBALL") == 1)
    m2 = call("GET", "/api/me")
    m3 = call("GET", "/api/me")
    chk("**두 번 지급되지 않는다**",
        not m2.get("gifts") and not m3.get("gifts")
        and m3["money"] == me["money"], (m2.get("gifts"), m3["money"]))

    g = grass()
    chk("이제 풀숲이 돋는다", bool(g), g)
    chk("꽃이 폈다", g.get("bloom") is True, g.get("bloom"))
    chk("**종은 안 알려준다**", not g.get("pokemon"), g.get("pokemon"))

    rv = call("POST", "/api/wild/%d/reveal" % g["id"])
    mon = rv["wild"]["pokemon"]
    chk("이벤트 포켓몬이다", mon["species"] == "SHAYMIN", mon["species"])
    chk("레벨이 정해진 값", mon["level"] == 30, mon["level"])
    chk("그 레벨에 배우는 기술 넷", len(mon.get("moves") or []) == 4,
        mon.get("moves"))

    print("\n=== 볼 ===")
    opts = rv.get("ballOptions") or []
    by = dict((o["id"], o) for o in opts)
    fb = by.get("FLOWERBALL")
    chk("플라워볼이 목록에 있다", fb is not None)
    chk("이 종에는 배율이 255", fb and fb["mult"] >= 255, fb and fb["mult"])
    chk("왜 그런지 말해 준다", bool(fb and fb.get("why")), fb and fb.get("why"))
    mb = by.get("MASTERBALL")
    chk("마스터볼은 추천 안 한다", not (mb and mb.get("best")))

    print("\n=== 잡기 ===")
    call("POST", "/api/wild/%d/reveal" % g["id"])
    got = call("POST", "/api/wild/%d/catch" % g["id"],
               body={"ball": "FLOWERBALL"})
    chk("이벤트 볼로 반드시 잡힌다", got.get("caught") is True, got)

    print("\n=== 잡은 뒤에는 평소대로 ===")
    seen = collections.Counter()
    blooms = 0
    for _ in range(30):
        g = grass()
        if not g:
            continue
        if g.get("bloom"):
            blooms += 1
        r = call("POST", "/api/wild/%d/reveal" % g["id"])
        seen[r["wild"]["pokemon"]["species"]] += 1
        call("POST", "/api/wild/%d/flee" % g["id"])
    chk("이벤트가 거의 안 나온다 (30번 중 %d)" % blooms, blooms <= 2, blooms)
    chk("여러 종이 골고루 나온다", len(seen) >= 15, len(seen))
    chk("이벤트 종이 평소 풀에 섞이지 않았다",
        seen.get("SHAYMIN", 0) == blooms, (seen.get("SHAYMIN", 0), blooms))

    print("\n=== 상점에는 안 뜬다 ===")
    shop = call("GET", "/api/shop")
    ids = set(i["id"] for i in shop["items"])
    chk("플라워볼이 도구 목록에는 있다", "FLOWERBALL" in ids)
    fb = next(i for i in shop["items"] if i["id"] == "FLOWERBALL")
    chk("살 수 없다", not fb.get("buyable"), fb.get("buyable"))
    chk("값이 0", fb.get("cost") == 0 and fb.get("sell") == 0,
        (fb.get("cost"), fb.get("sell")))

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
