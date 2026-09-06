# -*- coding: utf-8 -*-
"""지닌 도구 API 검사. 서버를 띄워 놓고 돌린다.

    python server/test_held_api.py [http://127.0.0.1:8787]

임시 계정을 만들어 도구를 사고, 지니게 하고, 벗기고, 놓아준다.
돈은 배틀로 번다 - 새 계정은 0원이라 열매(80원) 하나도 못 산다.
"""
import json
import random
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787").rstrip("/")
OK = FAIL = 0


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw.decode("utf-8")) if raw else {})
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def chk(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % label)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (label, str(detail)[:240]))


def section(t):
    print("\n=== %s ===" % t)


def signup():
    name = "지님%06d" % random.randrange(1000000)
    st, r = call("POST", "/api/auth/register",
                 {"username": name, "password": "1234", "starter": "CHARMANDER"})
    if st != 200:
        print("가입 실패:", st, r)
        sys.exit(1)
    return r["token"], name


def wild(token):
    for _ in range(6):
        st, w = call("GET", "/api/wild?force=1", token=token)
        wd = (w or {}).get("wild")
        if not wd:
            continue
        if wd.get("state") == "grass":
            st, rr = call("POST", "/api/wild/%d/reveal" % wd["id"], {}, token)
            wd = (rr or {}).get("wild") or {}
        if wd.get("pokemon"):
            return wd
    return None


def battle_once(token, wd):
    st, b = call("POST", "/api/wild/%d/battle" % wd["id"], {}, token)
    if st != 200:
        return
    bid = b["battle"]["id"]
    for _t in range(70):
        st, mv = call("POST", "/api/battle/%d/move" % bid, {"move": "", "hour": 13}, token)
        if st != 200 or (mv.get("battle") or {}).get("over"):
            return


def earn(token, target):
    """배틀로 도구를 떨어뜨려 팔아 목표 금액을 만든다."""
    for _round in range(16):
        st, me = call("GET", "/api/me", token=token)
        if me.get("money", 0) >= target:
            return me["money"]
        for _ in range(10):
            wd = wild(token)
            if wd:
                battle_once(token, wd)
        st, me = call("GET", "/api/me", token=token)
        for iid, n in list(me.get("bag", {}).items()):
            if iid != "POKEBALL":
                call("POST", "/api/shop/sell", {"item": iid, "count": n}, token)
    return call("GET", "/api/me", token=token)[1].get("money", 0)


def bag(token):
    return call("GET", "/api/bag", token=token)[1].get("bag", {})


def main():
    token, name = signup()
    st, r = call("GET", "/api/pokemon", token=token)
    mon = r["pokemon"][0]
    pid = mon["id"]

    section("카탈로그")
    st, shop = call("GET", "/api/shop", token=token)
    items = dict((it["id"], it) for it in shop["items"])
    held = [it for it in shop["items"] if it["cat"] == "held"]
    chk("상점에 지닌 도구가 있다 (117종)", len(held) == 117, len(held))
    chk("지닌 도구는 본가 설명이 붙어 있다", all(it.get("desc") for it in held))
    chk("holdable 표시가 온다", items["LEFTOVERS"].get("holdable") is True
        and items["POKEBALL"].get("holdable") is False)
    chk("금속코트는 돌이지만 지닐 수 있다",
        items["METALCOAT"]["cat"] == "stone" and items["METALCOAT"].get("holdable") is True)
    # 값은 본가 정가가 아니다 (tools/build_items._held_price). 열매 1000,
    # 판을 바꾸는 것 15000. 정가대로면 첫날에 구애머리띠까지 다 산다.
    chk("열매는 1,000원", items["ORANBERRY"]["cost"] == 1000, items["ORANBERRY"]["cost"])
    chk("선제공격손톱은 8,000원", items["QUICKCLAW"]["cost"] == 8000, items["QUICKCLAW"]["cost"])
    chk("구애머리띠·생명의구슬·먹다남은음식은 15,000원",
        all(items[k]["cost"] == 15000 for k in ("CHOICEBAND", "LIFEORB", "LEFTOVERS")))
    chk("파는 값은 사는 값의 절반", items["QUICKCLAW"]["sell"] == 4000, items["QUICKCLAW"]["sell"])
    chk("목탄(타입 강화)은 3,000원", items["CHARCOAL"]["cost"] == 3000, items["CHARCOAL"]["cost"])

    section("돈 벌기")
    money = earn(token, 2100)
    chk("열매 둘을 살 만큼 벌었다", money >= 2000, money)
    if money < 2000:
        print("  (돈이 모자라 나머지 검사를 건너뛴다)")
        return finish(token)

    section("사서 지니게 하기")
    st, r = call("POST", "/api/shop/buy", {"item": "ORANBERRY", "count": 1}, token)
    chk("오랭열매를 산다", st == 200, (st, r))
    st, r = call("POST", "/api/shop/buy", {"item": "CHERIBERRY", "count": 1}, token)
    chk("버치열매를 산다", st == 200, (st, r))
    st, r = call("POST", "/api/pokemon/%d/hold" % pid, {"item": "ORANBERRY"}, token)
    chk("지니게 한다", st == 200 and r.get("ok"), (st, r))
    chk("응답의 포켓몬에 held 가 있다", r.get("pokemon", {}).get("held") == "ORANBERRY", r.get("pokemon", {}).get("held"))
    chk("한글 이름과 설명도 온다", r["pokemon"].get("heldKr") == "오랭열매" and r["pokemon"].get("heldDesc"),
        (r["pokemon"].get("heldKr"), r["pokemon"].get("heldDesc")))
    chk("가방에서 빠졌다", not bag(token).get("ORANBERRY"), bag(token))
    st, r = call("GET", "/api/pokemon", token=token)
    chk("목록에서도 보인다", r["pokemon"][0].get("heldKr") == "오랭열매", r["pokemon"][0].get("heldKr"))

    section("같은 것 · 바꾸기")
    st, r = call("POST", "/api/pokemon/%d/hold" % pid, {"item": "ORANBERRY"}, token)
    chk("이미 지닌 것을 또 주면 그대로 (가방도 그대로 - 없음)",
        st == 200 and not bag(token).get("ORANBERRY"), (st, bag(token)))
    st, r = call("POST", "/api/pokemon/%d/hold" % pid, {"item": "CHERIBERRY"}, token)
    chk("다른 도구로 바꾼다", st == 200 and r["pokemon"].get("held") == "CHERIBERRY", (st, r))
    b = bag(token)
    chk("전에 지닌 것은 가방으로 돌아온다", b.get("ORANBERRY") == 1 and not b.get("CHERIBERRY"), b)

    section("못 하는 것")
    st, r = call("POST", "/api/pokemon/%d/hold" % pid, {"item": "POKEBALL"}, token)
    chk("몬스터볼은 지닐 수 없다", st == 400, (st, r))
    st, r = call("POST", "/api/pokemon/%d/hold" % pid, {"item": "LEFTOVERS"}, token)
    chk("가방에 없는 도구는 못 지닌다", st == 400, (st, r))
    st, r = call("POST", "/api/pokemon/%d/hold" % pid, {"item": "NOPE"}, token)
    chk("없는 도구는 400", st == 400, (st, r))
    st, r = call("POST", "/api/pokemon/999999/hold", {"item": "ORANBERRY"}, token)
    chk("남의/없는 포켓몬은 404", st == 404, (st, r))

    section("벗기기")
    st, r = call("DELETE", "/api/pokemon/%d/hold" % pid, token=token)
    chk("벗긴다", st == 200 and r.get("pokemon", {}).get("held") is None, (st, r))
    st, r = call("DELETE", "/api/pokemon/%d/hold" % pid, token=token)
    chk("빈손인데 또 벗기면 400", st == 400, (st, r))

    section("지닌 채로 놓아주면 도구는 가방으로")
    # 잡아서 한 마리 더 만들거나, 있으면 그걸 쓴다
    st, r = call("GET", "/api/pokemon", token=token)
    mons = r["pokemon"]
    victim = None
    if len(mons) >= 2:
        victim = mons[-1]
    else:
        # 볼이 있으면 야생을 잡아 본다 (몇 번 시도)
        for _ in range(8):
            wd = wild(token)
            if not wd:
                continue
            st, c = call("POST", "/api/wild/%d/catch" % wd["id"], {"ball": "POKEBALL", "hour": 13}, token)
            if st == 200 and (c.get("caught") or c.get("pokemon")):
                st, r = call("GET", "/api/pokemon", token=token)
                if len(r["pokemon"]) >= 2:
                    victim = r["pokemon"][-1]
                    break
    if victim is None:
        print("  (놓아줄 둘째 포켓몬을 못 만들어 건너뛴다)")
    else:
        before = bag(token).get("ORANBERRY", 0)
        st, r = call("POST", "/api/pokemon/%d/hold" % victim["id"], {"item": "ORANBERRY"}, token)
        chk("둘째에게 지니게 한다", st == 200, (st, r))
        st, r = call("DELETE", "/api/pokemon/%d" % victim["id"], token=token)
        chk("놓아준다", st == 200, (st, r))
        chk("놓아주면 도구가 가방으로 돌아온다", bag(token).get("ORANBERRY", 0) == before, (before, bag(token)))
        chk("메시지에 도구 얘기가 있다", "가방" in r.get("message", ""), r.get("message"))

    return finish(token)


def finish(token):
    call("POST", "/api/auth/delete", {"password": "1234"}, token)
    print()
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
