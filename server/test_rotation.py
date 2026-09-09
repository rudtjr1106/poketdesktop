# -*- coding: utf-8 -*-
"""야생 배틀에서 쓰러진 포켓몬이 다시 나오지 않는가.

    python server/test_rotation.py [http://127.0.0.1:8787]

서버를 띄워 놓고 돌린다.

## 무엇을 잡는 검사인가

교체는 **같은 배틀 행을 다시 쓴다** (switch 가 mine_id 만 갈아 끼운다).
그런데 다음에 내보낼 후보를 고를 때 '방금 쓰러진 한 마리' 만 뺐다.

    nxt = [m for m in _party(uid) if m["id"] != row["mine_id"]]

그래서 1번이 지고 2번이 나오고, 2번이 지면 후보에서 2번만 빠져 1번이
다시 나왔다 - 1죽고 2죽고 1나오고 2나오고 끝없이 돌았다.

여기서는 실제로 질 때까지 야생과 싸워 보고, 지면 이렇게 되는지 본다.

  1. 다음 후보(party)에 **이미 쓰러진 애가 안 들어 있다**
  2. 이미 쓰러진 애로 교체하려 하면 막는다 (409)
  3. 여섯을 다 쓰면 allDown 이 오고 **야생이 사라진다**

지는 것은 운이라, 정해진 횟수 안에 한 번도 안 지면 그 항목은 건너뛴다
(그 경우에도 1번 전제 검사는 돈다).
"""
import json
import random
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1
        else "http://127.0.0.1:8787").rstrip("/")

OK = FAIL = 0
TOKEN = None


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Accept-Encoding", "identity")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except ValueError:
            return e.code, {}
    except Exception as e:                                  # noqa: BLE001
        return 0, {"error": str(e)}


def chk(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (label, detail))


def section(t):
    print()
    print("=== %s ===" % t)


def party_ids():
    _st, p = call("GET", "/api/pokemon/desktop", token=TOKEN)
    return [m["id"] for m in (p.get("pokemon") or [])]


def _wild():
    st, w = call("GET", "/api/wild?force=true", token=TOKEN)
    return (w or {}).get("wild")


def _battle_once(wd):
    """한 판 자동으로 싸운다. 이기면 도구가 떨어져서 팔 거리가 생긴다."""
    call("POST", "/api/wild/%d/reveal" % wd["id"], {}, TOKEN)
    st, r = call("POST", "/api/wild/%d/battle" % wd["id"], {}, TOKEN)
    if st != 200 or not r.get("battle"):
        return None
    bid = r["battle"]["id"]
    for _ in range(120):
        st, r = call("POST", "/api/battle/%d/move" % bid, {"move": "AUTO"},
                     TOKEN)
        if st != 200:
            return None
        res = (r.get("battle") or {}).get("result")
        if res:
            return res
    return None


def _sell_all():
    st, sh = call("GET", "/api/shop", token=TOKEN)
    for it in (sh or {}).get("items", []):
        n = ((sh.get("bag") or {}).get(it["id"]) or 0)
        if n > 0 and int(it.get("sell") or 0) > 0:
            call("POST", "/api/shop/sell", {"item": it["id"], "count": n},
                 TOKEN)


def build_party(want=3):
    """데리고 다니는 자리를 채운다. 여러 마리라야 로테이션이 돈다.

    볼은 열 개로 시작해 금방 떨어진다. test_items 와 같은 방법으로,
    배틀로 도구를 떨어뜨려 팔아 돈을 만들고 그 돈으로 볼을 산다.
    """
    for _ in range(90):
        ids = party_ids()
        if len(ids) >= want:
            return True
        st, me = call("GET", "/api/me", token=TOKEN)
        if me.get("balls", 0) < 4:
            if me.get("money", 0) < 2000:
                for _ in range(10):
                    wd = _wild()
                    if wd:
                        _battle_once(wd)
                _sell_all()
                continue
            call("POST", "/api/shop/buy",
                 {"item": "POKEBALL", "count": 10}, TOKEN)
        wd = _wild()
        if not wd:
            continue
        call("POST", "/api/wild/%d/reveal" % wd["id"], {}, TOKEN)
        for _ in range(8):
            st, c = call("POST", "/api/wild/%d/catch" % wd["id"],
                         {"ball": "POKEBALL", "hour": 13}, TOKEN)
            if st != 200:
                break
            if c.get("caught"):
                pid = (c.get("pokemon") or {}).get("id")
                if pid:
                    call("POST", "/api/pokemon/%d/desktop" % pid,
                         {"on": True}, TOKEN)
                break
            if c.get("balls", 0) <= 0:
                break
    return len(party_ids()) >= 2


def main():
    global TOKEN
    user = "rot%06d" % random.randrange(1000000)
    st, r = call("POST", "/api/auth/register",
                 {"username": user, "password": "1234", "device": "d1"})
    if st != 200:
        print("가입 실패:", st, r)
        return 1
    TOKEN = r["token"]

    section("데리고 다니는 포켓몬 모으기")
    ok = build_party()
    ids = party_ids()
    print("       데리고 다니는 %d마리: %s" % (len(ids), ids))
    chk("여러 마리를 데리고 다닌다 (검사 전제)", len(ids) >= 2, ids)
    if len(ids) < 2:
        print("       못 모아서 여기서 멈춥니다 (볼 운)")
        return 1 if FAIL else 0

    section("져 보고, 쓰러진 애가 다시 나오는지 본다")
    seen_loss = 0
    rounds = 0
    for _ in range(60):
        st, w = call("GET", "/api/wild?force=true", token=TOKEN)
        wd = (w or {}).get("wild")
        if not wd:
            continue
        call("POST", "/api/wild/%d/reveal" % wd["id"], {}, TOKEN)
        st, r = call("POST", "/api/wild/%d/battle" % wd["id"], {}, TOKEN)
        if st != 200 or not r.get("battle"):
            continue
        bid = r["battle"]["id"]
        rounds += 1
        down = []
        for _turn in range(120):
            st, r = call("POST", "/api/battle/%d/move" % bid,
                         {"move": "AUTO"}, TOKEN)
            if st != 200:
                break
            b = r.get("battle") or {}
            if b.get("result") != "lost":
                if b.get("result"):
                    break                       # 이겼거나 도망갔다
                continue
            # 졌다. 여기가 검사할 자리다.
            seen_loss += 1
            mine = b.get("me") or {}
            fell = r.get("fainted") or []
            nxt = [m["id"] for m in (r.get("party") or [])]
            chk("다음 후보에 이미 쓰러진 애가 없다",
                not (set(nxt) & set(fell)), (nxt, fell))
            chk("쓰러진 목록이 쌓인다", len(fell) >= len(down) + 1, (fell, down))
            down = fell
            if fell:
                st2, r2 = call("POST", "/api/battle/%d/switch" % bid,
                               {"pokemon": fell[0]}, TOKEN)
                # **야생이 먼저 떠나면 이 검사를 할 수가 없다.** 야생은
                # 60초면 사라지는데(POKET_WILD_TTL), 판을 여러 번 도는
                # 사이에 지금 싸우던 야생의 시간이 다 될 수 있다. 그러면
                # 서버는 '쓰러진 애다'(409) 를 따지기 전에 '야생이 떠났다'
                # (410) 로 먼저 끊는다 - 그게 맞는 순서다.
                #
                # 그걸 실패로 세면 검사가 시계에 따라 붙었다 떨어졌다
                # 한다. 실제로 CI 에서 그렇게 한 번 떨어졌다. 여기서는
                # 세지 않고 넘어간다 - 못 본 것이지 틀린 것이 아니다.
                if st2 == 410:
                    print("  건너뜀 이미 쓰러진 애 검사 (야생이 먼저 떠났다)")
                    break
                chk("이미 쓰러진 애로는 못 바꾼다 (409)", st2 == 409, (st2, r2))
            if r.get("canSwitch") and nxt:
                st3, _r3 = call("POST", "/api/battle/%d/switch" % bid,
                                {"pokemon": nxt[0]}, TOKEN)
                if st3 != 200:
                    break
                continue                        # 다음 애로 이어서 싸운다
            # 더 내보낼 애가 없다 - 여섯(또는 가진 만큼)을 다 썼다
            chk("다 쓰러지면 allDown 이 온다", bool(r.get("allDown")), r.keys())
            chk("쓰러진 수 = 데리고 다니던 수",
                len(fell) == len(ids), (len(fell), len(ids)))
            st4, w2 = call("GET", "/api/wild", token=TOKEN)
            chk("야생은 가 버렸다", (w2 or {}).get("wild") is None, w2)
            break
        if seen_loss:
            break
    print("       야생과 %d판, 진 판 %d번" % (rounds, seen_loss))
    if not seen_loss:
        print("       한 번도 안 져서 이 항목들은 건너뜁니다 (확률상 정상)")

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
