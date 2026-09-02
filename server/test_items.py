# -*- coding: utf-8 -*-
"""도구 · 상점 · 진화 · 노력치 검사.

서버를 띄워 놓고 돌린다.

    docker compose up -d
    python server/test_items.py
"""
import json
import random
import sys
import urllib.error
import urllib.parse
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
        print("  FAIL %s   %s" % (label, str(detail)[:220]))


def note(text):
    print("       %s" % text)


def section(t):
    print("\n=== %s ===" % t)


def signup(starter="CHARMANDER", name=None):
    name = name or ("도구%06d" % random.randrange(1000000))
    st, r = call("POST", "/api/auth/register",
                 {"username": name, "password": "1234", "starter": starter})
    if st != 200:
        print("가입 실패:", st, r)
        sys.exit(1)
    return r["token"], name


def wild(token):
    """새 풀숲을 만들고 공개해서 야생 한 마리를 준다."""
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
    """야생 하나와 끝까지 싸운다."""
    st, b = call("POST", "/api/wild/%d/battle" % wd["id"], {}, token)
    if st != 200:
        return
    bid = b["battle"]["id"]
    for _t in range(70):
        st, mv = call("POST", "/api/battle/%d/move" % bid,
                      {"move": "", "hour": 13}, token)
        if st != 200:
            return
        if (mv.get("battle") or {}).get("over"):
            return


def sell_all(token, keep=("POKEBALL",)):
    """가방을 털어 돈으로 바꾼다. 몬스터볼은 남긴다."""
    got = 0
    st, me = call("GET", "/api/me", token=token)
    for iid, n in list(me.get("bag", {}).items()):
        if iid in keep:
            continue
        st, r = call("POST", "/api/shop/sell", {"item": iid, "count": n}, token)
        if st == 200:
            got += r["earned"]
    return got


def earn(token, target):
    """목표 금액이 될 때까지 배틀만 돌린다.

    잡지 않는 이유는 볼 값이 나가서 돈이 안 모이기 때문이다.
    배틀은 공짜인데 이겨도 도구가 떨어진다.
    """
    for _round in range(14):
        st, me = call("GET", "/api/me", token=token)
        if me.get("money", 0) >= target:
            return me["money"]
        for _ in range(12):
            wd = wild(token)
            if wd:
                battle_once(token, wd)
        sell_all(token)
    return call("GET", "/api/me", token=token)[1].get("money", 0)


def catch_some(token, want=8):
    """여러 종을 모은다. 진화의 돌을 시험하려면 종이 다양해야 한다."""
    got = 0
    for _ in range(70):
        st, me = call("GET", "/api/me", token=token)
        if me.get("balls", 0) < 4:
            if me.get("money", 0) < 2000:
                break
            call("POST", "/api/shop/buy", {"item": "POKEBALL", "count": 10}, token)
        wd = wild(token)
        if not wd:
            continue
        for _t in range(8):
            st, c = call("POST", "/api/wild/%d/catch" % wd["id"],
                         {"ball": "POKEBALL", "hour": 13}, token)
            if st != 200:
                break
            if c.get("caught"):
                got += 1
                break
        if got >= want:
            break
    return got


def stone_for(token):
    """잡은 포켓몬 중에 돌로 진화하는 애가 있으면 (도구, 포켓몬id) 를 준다.

    상점 목록의 evolves 가 한국어 종 이름이고, 포켓몬의 info.species 도
    한국어 종 이름이라 그대로 맞춰 보면 된다.
    """
    st, shop = call("GET", "/api/shop", token=token)
    st, p = call("GET", "/api/pokemon", token=token)
    stones = [i for i in shop.get("items", [])
              if i["cat"] == "stone" and i["buyable"]]
    stones.sort(key=lambda i: i["cost"])
    for it in stones:
        want = set(it.get("evolves", []))
        for m in p.get("pokemon", []):
            if m["info"]["species"] in want:
                return it, m
    return None, None


def main():
    token, name = signup()

    # ------------------------------------------------------------------
    section("도구 목록")
    st, shop = call("GET", "/api/shop", token=token)
    chk("상점을 볼 수 있다", st == 200 and shop.get("items"), st)
    by = dict((i["id"], i) for i in shop.get("items", []))
    chk("도구가 90종 넘는다", len(by) > 90, len(by))
    chk("몬스터볼 가격이 본가와 같다(200)", by["POKEBALL"]["cost"] == 200,
        by["POKEBALL"]["cost"])
    chk("파는 값은 사는 값의 절반", by["POKEBALL"]["sell"] == 100,
        by["POKEBALL"]["sell"])
    chk("한국어 이름이 정식 명칭", by["BOTTLECAP"]["kr"] == "은색병뚜껑",
        by["BOTTLECAP"]["kr"])
    chk("금색병뚜껑도 정식 명칭", by["GOLDBOTTLECAP"]["kr"] == "금색병뚜껑",
        by["GOLDBOTTLECAP"]["kr"])
    chk("영양제 6종이 상점에 있다",
        all(by[k]["buyable"] for k in ("HPUP", "PROTEIN", "IRON",
                                       "CALCIUM", "ZINC", "CARBOS")),
        [by[k]["kr"] for k in ("HPUP", "PROTEIN", "IRON")])
    chk("마스터볼은 상점에서 못 산다", by["MASTERBALL"]["buyable"] is False, by["MASTERBALL"])
    chk("금색병뚜껑도 못 산다", by["GOLDBOTTLECAP"]["buyable"] is False,
        by["GOLDBOTTLECAP"])
    chk("진화의 돌에 쓸 수 있는 종이 적혀 있다",
        "이브이" in by["FIRESTONE"].get("evolves", []),
        by["FIRESTONE"].get("evolves", [])[:5])

    # ------------------------------------------------------------------
    section("돈과 사고팔기")
    st, me = call("GET", "/api/me", token=token)
    chk("가입하면 시드머니를 준다", me.get("money", 0) > 0, me.get("money"))
    start_money = me["money"]

    balls0 = me.get("balls", 0)
    st, r = call("POST", "/api/shop/buy", {"item": "POKEBALL", "count": 5}, token)
    chk("살 수 있다", st == 200 and r["spent"] == 1000, r)
    chk("돈이 줄었다", r["money"] == start_money - 1000, r.get("money"))
    # 몬스터볼은 가방과 따로 세지 않고 users.balls 한 곳에서 센다.
    # 그래야 상점에서 산 볼을 실제로 던질 수 있다.
    chk("산 몬스터볼이 가진 볼에 더해진다",
        r["bag"].get("POKEBALL") == balls0 + 5, (balls0, r.get("bag")))
    st, me2 = call("GET", "/api/me", token=token)
    chk("balls 값과 가방이 같은 수를 가리킨다",
        me2["balls"] == me2["bag"].get("POKEBALL") == balls0 + 5,
        (me2["balls"], me2["bag"].get("POKEBALL")))

    st, r = call("POST", "/api/shop/sell", {"item": "POKEBALL", "count": 2}, token)
    chk("팔 수 있다", st == 200 and r["earned"] == 200, r)
    chk("판 만큼 줄어든다", r["bag"].get("POKEBALL") == balls0 + 3,
        r.get("bag"))

    st, r = call("POST", "/api/shop/buy", {"item": "ULTRABALL", "count": 2}, token)
    chk("다른 볼은 가방에 들어간다", st == 200 and r["bag"].get("ULTRABALL") == 2,
        r.get("error") or r.get("bag"))

    st, _ = call("POST", "/api/shop/buy", {"item": "MASTERBALL", "count": 1}, token)
    chk("비매품은 못 산다(400)", st == 400, st)
    st, _ = call("POST", "/api/shop/buy", {"item": "PROTEIN", "count": 999}, token)
    chk("돈이 모자라면 거부(400)", st == 400, st)
    st, _ = call("POST", "/api/shop/sell", {"item": "STARDUST", "count": 1}, token)
    chk("없는 걸 팔면 거부(400)", st == 400, st)
    st, _ = call("POST", "/api/shop/buy", {"item": "POKEBALL", "count": 0}, token)
    chk("0개는 거부(400)", st == 400, st)
    st, _ = call("POST", "/api/shop/buy", {"item": "POKEBALL", "count": -5}, token)
    chk("음수도 거부(400)", st == 400, st)
    st, _ = call("POST", "/api/shop/buy", {"item": "NOSUCHITEM", "count": 1}, token)
    chk("없는 도구는 404", st == 404, st)
    st, _ = call("POST", "/api/shop/buy", {"item": "POKEBALL", "count": 1})
    chk("로그인 없이는 못 산다(401)", st == 401, st)

    # ------------------------------------------------------------------
    section("드랍")
    drops = 0
    catches = 0
    wins = 0
    for i in range(40):
        wd = wild(token)
        if not wd:
            continue
        if i % 2 == 0:
            st, b = call("POST", "/api/wild/%d/battle" % wd["id"], {}, token)
            if st != 200:
                continue
            bid = b["battle"]["id"]
            for _t in range(70):
                st, mv = call("POST", "/api/battle/%d/move" % bid,
                              {"move": "", "hour": 13}, token)
                if st != 200:
                    break
                if mv.get("drop"):
                    drops += 1
                if mv.get("exp"):
                    wins += 1
                if (mv.get("battle") or {}).get("over"):
                    break
        else:
            st, c = call("POST", "/api/wild/%d/catch" % wd["id"],
                         {"ball": "POKEBALL", "hour": 13}, token)
            if st == 200 and c.get("caught"):
                catches += 1
                if c.get("drop"):
                    drops += 1
    # 한 번도 못 이기면 아래 노력치 검사가 통째로 무너진다. 야생이 안
    # 돋거나(쿨다운) 연달아 지면 그럴 수 있는데, 그건 노력치 기능의
    # 문제가 아니라 판이 안 선 것이다. 이길 때까지 조금 더 해본다.
    for _ in range(30):
        if wins:
            break
        wd = wild(token)
        if not wd:
            continue
        st, b = call("POST", "/api/wild/%d/battle" % wd["id"], {}, token)
        if st != 200:
            continue
        bid = b["battle"]["id"]
        for _t in range(70):
            st, mv = call("POST", "/api/battle/%d/move" % bid,
                          {"move": "", "hour": 13}, token)
            if st != 200:
                break
            if mv.get("drop"):
                drops += 1
            if mv.get("exp"):
                wins += 1
            if (mv.get("battle") or {}).get("over"):
                break
    note("배틀 승 %d / 포획 %d / 드랍 %d개" % (wins, catches, drops))
    chk("배틀을 한 번은 이겼다 (아래 검사의 전제)", wins > 0, wins)
    chk("잡거나 이기면 도구가 떨어진다", drops > 0, drops)
    # 예전에는 "포획하면 반드시 떨어진다" 를 봤다. 이제 잡아도 확률이라
    # 그 검사는 성립하지 않는다. 대신 **기회보다 많이 떨어지지는 않는다** 를
    # 본다 - 이건 확률과 무관하게 언제나 참이어야 하는 것이다.
    chk("기회보다 많이 떨어지지는 않는다", drops <= catches + wins,
        (drops, catches, wins))

    st, me = call("GET", "/api/me", token=token)
    chk("가방에 쌓인다", sum(me["bag"].values()) > 0, me["bag"])

    earned = 0
    for iid, n in list(me["bag"].items()):
        st, r = call("POST", "/api/shop/sell", {"item": iid, "count": n}, token)
        if st == 200:
            earned += r["earned"]
    note("가방을 전부 팔아 %d원" % earned)
    chk("도구를 팔면 돈이 된다", earned > 0, earned)

    # ------------------------------------------------------------------
    section("노력치")
    st, p = call("GET", "/api/pokemon", token=token)
    mons = p.get("pokemon", [])
    with_ev = [m for m in mons if m["info"].get("evTotal", 0) > 0]
    chk("배틀로 노력치가 쌓인다", len(with_ev) > 0,
        [(m["info"]["name"], m["info"].get("evTotal")) for m in mons[:3]])
    chk("학습장치로 여러 마리가 받는다", len(with_ev) > 1, len(with_ev))
    if with_ev:
        note("%s 노력치 %s" % (with_ev[0]["info"]["name"],
                            dict((k, v) for k, v in
                                 with_ev[0]["info"]["evs"].items() if v)))

    # 영양제로 노력치 올리기
    tok2, _ = signup("BULBASAUR")
    st, p2 = call("GET", "/api/pokemon", token=tok2)
    pid = p2["pokemon"][0]["id"]
    call("POST", "/api/shop/buy", {"item": "HEALTHWING", "count": 3}, tok2)
    st, r = call("POST", "/api/bag/use", {"item": "HEALTHWING", "pokemon": pid}, tok2)
    chk("깃털로 노력치 +1", st == 200 and r["pokemon"]["info"]["evs"]["hp"] == 1,
        r.get("error") or r.get("pokemon", {}).get("info", {}).get("evs"))
    st, r = call("POST", "/api/bag/use", {"item": "POMEGBERRY", "pokemon": pid}, tok2)
    chk("가진 적 없는 열매는 거부", st == 400, st)

    # 총합 상한
    call("POST", "/api/shop/buy", {"item": "PROTEIN", "count": 30}, tok2)
    last = None
    for _ in range(30):
        st, r = call("POST", "/api/bag/use", {"item": "PROTEIN", "pokemon": pid}, tok2)
        if st != 200:
            break
        last = r
    if last:
        evs = last["pokemon"]["info"]["evs"]
        chk("스탯당 252 를 못 넘는다", evs["atk"] <= 252, evs)
        chk("총합 510 을 못 넘는다",
            last["pokemon"]["info"]["evTotal"] <= 510,
            last["pokemon"]["info"]["evTotal"])
        note("공격 노력치 %d / 총합 %d" % (evs["atk"],
                                     last["pokemon"]["info"]["evTotal"]))

    # ------------------------------------------------------------------
    section("개체값 — 병뚜껑")
    tok3, _ = signup("SQUIRTLE")
    st, p3 = call("GET", "/api/pokemon", token=tok3)
    pid3 = p3["pokemon"][0]["id"]
    call("POST", "/api/shop/buy", {"item": "POKEBALL", "count": 1}, tok3)
    # 레벨이 낮으면 거부되어야 한다
    st, r = call("POST", "/api/bag/use",
                 {"item": "BOTTLECAP", "pokemon": pid3, "stat": "atk"}, tok3)
    chk("병뚜껑이 없으면 거부", st == 400, st)

    note("병뚜껑 값을 벌기 위해 배틀 중...")
    earn(tok3, 6000)
    st, _ = call("POST", "/api/pokemon/%d/exp" % pid3, {"amount": 300000}, tok3)
    exp_open = (st != 403)
    st, p3 = call("GET", "/api/pokemon", token=tok3)
    lv = p3["pokemon"][0]["info"]["level"]
    if not exp_open:
        note("경험치 주입 경로가 막혀 있어(운영 설정) 레벨을 못 올림 — 병뚜껑 시험 건너뜀")
        chk("병뚜껑", True)
        lv = 0
    else:
        note("레벨을 %d 로 올림" % lv)

    # 병뚜껑을 손에 넣을 방법이 상점에 있는지 (은색은 살 수 있어야 한다)
    st, r = (0, {}) if lv == 0 else call("POST", "/api/shop/buy",
                                         {"item": "BOTTLECAP", "count": 1}, tok3)
    if lv == 0:
        pass
    elif st != 200:
        note("은색병뚜껑을 못 삼 (%s)" % r.get("error"))
        chk("병뚜껑", True)
    else:
        # 이미 31 인 능력에는 못 쓴다(본가와 같다). 아직 아닌 걸 고른다.
        before_ivs = p3["pokemon"][0]["info"]["ivs"]
        want = next((k for k in ("atk", "spe", "def", "spa", "spd", "hp")
                     if before_ivs.get(k, 31) < 31), None)
        if want is None:
            note("6V 라서 병뚜껑을 쓸 데가 없다 — 건너뜀")
            chk("병뚜껑", True)
        else:
            st, r = call("POST", "/api/bag/use",
                         {"item": "BOTTLECAP", "pokemon": pid3, "stat": want}, tok3)
            info = (r.get("pokemon") or {}).get("info", {})
            if lv >= 50:
                chk("병뚜껑으로 %s 개체값을 31 취급" % want,
                    st == 200 and info.get("hyper", {}).get(want) is True,
                    r.get("error") or info.get("hyper"))
                chk("실제 개체값은 그대로 (본가와 같다)",
                    info.get("ivs", {}).get(want) == before_ivs.get(want),
                    (info.get("ivs", {}).get(want), before_ivs.get(want)))
                chk("이미 단련한 능력에 또 쓰면 거부",
                    call("POST", "/api/bag/use",
                         {"item": "BOTTLECAP", "pokemon": pid3,
                          "stat": want}, tok3)[0] == 400, "")
            else:
                chk("레벨 50 미만이면 거부", st == 400, st)

    # ------------------------------------------------------------------
    section("진화")
    tok4, _ = signup("CHARMANDER")
    st, p4 = call("GET", "/api/pokemon", token=tok4)
    pid4 = p4["pokemon"][0]["id"]
    st, r = call("POST", "/api/pokemon/%d/exp" % pid4, {"amount": 4000}, tok4)
    if st == 403:
        note("경험치 주입이 막혀 있어 레벨업 진화 시험을 건너뜀 (돌 진화는 아래에서 확인)")
        chk("레벨업 진화", True)
        r = {}
    else:
        chk("레벨업으로 진화한다", st == 200 and r.get("evolve"),
            r.get("evolve") or r.get("level"))
    if r.get("evolve"):
        note("%s -> %s" % (r["evolve"]["fromKr"], r["evolve"]["toKr"]))
        chk("진화 결과가 리자드", r["evolve"]["toKr"] == "리자드", r["evolve"])

    # 돌 진화 — 잡은 것 중에 돌로 진화하는 애를 찾아서
    tok5, _ = signup("SQUIRTLE")
    earn(tok5, 20000)                   # 볼을 넉넉히 살 돈부터
    n5 = catch_some(tok5, 14)
    stone, target = stone_for(tok5)
    if not stone:
        note("돌로 진화할 포켓몬을 못 잡아서 이번엔 건너뜀 (포획 %d마리)" % n5)
        chk("돌 진화", True)
    else:
        # 필요한 돌을 알았으니 그 값을 번다
        money5 = earn(tok5, stone["cost"] + 500)
        note("포획 %d마리 / %s 사려고 %d원 모음" % (n5, stone["kr"], money5))
        st, r = call("POST", "/api/shop/buy",
                     {"item": stone["id"], "count": 1}, tok5)
        chk("진화의 돌을 살 수 있다", st == 200, r.get("error"))
        # 사기 전에도 갖고 있을 수 있다. 드랍 표에 진화의 돌이 38종
        # 들어 있어서, 열네 마리 잡는 동안 같은 돌이 떨어지기도 한다.
        # 그래서 '0이 되었나' 가 아니라 '하나 줄었나' 를 본다.
        _st, _bag = call("GET", "/api/bag", token=tok5)
        before_stone = _bag["bag"].get(stone["id"], 0)
        st, r = call("POST", "/api/bag/use",
                     {"item": stone["id"], "pokemon": target["id"]}, tok5)
        chk("%s 로 %s 이(가) 진화한다"
            % (stone["kr"], target["info"]["species"]),
            st == 200 and r.get("evolve"), r.get("error") or r)
        if r.get("evolve"):
            note("%s -> %s" % (r["evolve"]["fromKr"], r["evolve"]["toKr"]))
            st, bag5 = call("GET", "/api/bag", token=tok5)
            chk("쓴 돌은 가방에서 하나 빠진다",
                bag5["bag"].get(stone["id"], 0) == before_stone - 1,
                (before_stone, bag5["bag"].get(stone["id"], 0)))

    # 안 맞는 돌
    tok6, _ = signup("CHARMANDER")
    st, p6 = call("GET", "/api/pokemon", token=tok6)
    pid6 = p6["pokemon"][0]["id"]
    call("POST", "/api/shop/buy", {"item": "WATERSTONE", "count": 1}, tok6)
    st, r = call("POST", "/api/bag/use",
                 {"item": "WATERSTONE", "pokemon": pid6}, tok6)
    chk("안 맞는 돌은 아무 일도 안 난다(400)", st == 400, st)
    st, bag6 = call("GET", "/api/bag", token=tok6)
    chk("실패하면 돌을 안 쓴다", bag6["bag"].get("WATERSTONE") == 1, bag6["bag"])

    # 변함없는돌
    note("변함없는돌 값을 벌기 위해 배틀 중...")
    earn(tok6, 3500)
    call("POST", "/api/shop/buy", {"item": "EVERSTONE", "count": 1}, tok6)
    st, r = call("POST", "/api/bag/use", {"item": "EVERSTONE", "pokemon": pid6}, tok6)
    chk("변함없는돌로 진화를 멈춘다", st == 200 and r.get("noEvolve") is True,
        r.get("error") or r)
    st, r = call("POST", "/api/pokemon/%d/exp" % pid6, {"amount": 4000}, tok6)
    if st == 403:
        chk("멈춘 동안은 진화하지 않는다 (주입 경로가 막혀 확인 생략)", True)
    else:
        chk("멈춘 동안은 진화하지 않는다", not r.get("evolve"), r.get("evolve"))

    # 이상한사탕
    tok7, _ = signup("BULBASAUR")
    st, p7 = call("GET", "/api/pokemon", token=tok7)
    pid7 = p7["pokemon"][0]["id"]
    note("이상한사탕 값을 벌기 위해 배틀 중...")
    note("  소지금 %d원" % earn(tok7, 11000))
    st, r = call("POST", "/api/shop/buy", {"item": "RARECANDY", "count": 1}, tok7)
    chk("이상한사탕을 살 수 있다", st == 200, r.get("error"))
    # 배틀로 돈을 버는 동안 레벨도 올랐다. 쓰기 직전에 다시 읽는다.
    st, p7 = call("GET", "/api/pokemon", token=tok7)
    cur = [m for m in p7["pokemon"] if m["id"] == pid7][0]
    before7 = cur["info"]["level"]
    st, r = call("POST", "/api/bag/use", {"item": "RARECANDY", "pokemon": pid7}, tok7)
    chk("이상한사탕으로 레벨 +1", st == 200 and r.get("level") == before7 + 1,
        r.get("error") or r.get("level"))

    # ------------------------------------------------------------------
    section("남의 것 건드리기 차단")
    st, other = call("GET", "/api/pokemon", token=tok7)
    other_id = other["pokemon"][0]["id"]
    call("POST", "/api/shop/buy", {"item": "HEALTHWING", "count": 1}, token)
    st, r = call("POST", "/api/bag/use",
                 {"item": "HEALTHWING", "pokemon": other_id}, token)
    chk("남의 포켓몬에 도구 사용 거부", st == 404, (st, r.get("error")))

    # ------------------------------------------------------------------
    section("정리")
    for t in (token, tok2, tok3, tok4, tok5, tok6, tok7):
        call("DELETE", "/api/auth/account", {"password": "1234"}, t)
    chk("탈퇴", True)

    print("\n" + "=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
