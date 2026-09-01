# -*- coding: utf-8 -*-
"""배틀 API 통합 테스트.

    python server/test_battle.py [http://127.0.0.1:8787]

임시 계정을 만들고 끝나면 지운다.
"""
import json
import random
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787").rstrip("/")
OK = FAIL = 0
TOKEN = None


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token or TOKEN:
        req.add_header("Authorization", "Bearer " + (token or TOKEN))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            return r.status, json.loads(raw.decode("utf-8"))
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
        print("  FAIL %s   %s" % (label, detail))


def section(t):
    print("")
    print("=== %s ===" % t)


def best_move(side):
    """사람이 고를 법한 기술 — 쓸 수 있는 것 중 위력이 제일 높은 것."""
    usable = [m for m in side["moves"] if m["pp"] > 0] or side["moves"]
    dmg = [m for m in usable if (m.get("power") or 0) > 0]
    return max(dmg or usable, key=lambda m: m.get("power") or 0)


def weaken_and_catch():
    """실제 플레이처럼: 배틀 걸고 체력을 깎은 뒤 볼을 던진다."""
    wd = fresh_wild()
    if not wd:
        return None
    st, r = call("POST", "/api/wild/%d/battle" % wd["id"], {})
    if st != 200:
        return None
    bt = r["battle"]
    guard = 0
    while not bt["over"] and guard < 40:
        guard += 1
        # 절반까지 깎으면 볼을 던진다. 더 깎으려다간 쓰러뜨려버린다.
        if bt["foe"]["hp"] <= bt["foe"]["maxhp"] * 0.5:
            st, c = call("POST", "/api/battle/%d/ball" % bt["id"], {})
            if st != 200:
                return None
            if c.get("caught"):
                return c
            if c.get("balls", 0) <= 0:
                return None
            bt = c.get("battle") or bt
            if bt["over"]:
                return None
            continue
        # 잡으려면 살살 때려야 한다. 위력이 낮은 기술을 쓴다.
        dmg = [m for m in bt["me"]["moves"]
               if m["pp"] > 0 and (m.get("power") or 0) > 0]
        if not dmg:
            return None
        weak = min(dmg, key=lambda m: m["power"])
        st, r = call("POST", "/api/battle/%d/move" % bt["id"], {"move": weak["key"]})
        if st != 200:
            return None
        bt = r["battle"]
    return None


def fresh_wild():
    """새 야생 포켓몬을 앞에 세운다."""
    st, w = call("GET", "/api/wild?force=true")
    wd = (w or {}).get("wild")
    if not wd:
        return None
    if wd["state"] == "grass":
        st, r = call("POST", "/api/wild/%d/reveal" % wd["id"], {})
        wd = (r or {}).get("wild")
    return wd


def main():
    global TOKEN
    user = "b%06d" % random.randrange(1000000)
    pw = "1234"                       # 숫자 4자리

    section("준비")
    st, r = call("POST", "/api/auth/register",
                 {"username": user, "password": pw, "device": "bt",
                  "starter": "CHARMANDER"}, token="x")
    TOKEN = r.get("token")
    chk("가입", st == 200 and TOKEN, r)
    st, me = call("GET", "/api/me")
    chk("몬스터볼 10개", me.get("balls") == 10, me.get("balls"))
    chk("파티 상한 6", me["limits"].get("maxParty") == 6, me.get("limits"))

    section("배틀 시작")
    wd = fresh_wild()
    chk("야생 등장", bool(wd and wd.get("pokemon")), wd)
    wid = wd["id"]
    foe_name = wd["pokemon"]["info"]["species"]
    st, r = call("POST", "/api/wild/%d/battle" % wid, {})
    chk("배틀 시작 성공", st == 200 and r.get("battle"), r)
    bt = r["battle"]
    bid = bt["id"]
    print("       %s(Lv.%d) vs 야생 %s(Lv.%d)"
          % (bt["me"]["name"], bt["me"]["level"],
             bt["foe"]["name"], bt["foe"]["level"]))
    chk("내 포켓몬 체력이 가득", bt["me"]["hp"] == bt["me"]["maxhp"], bt["me"])
    chk("내 기술 목록이 옴", len(bt["me"].get("moves", [])) >= 1, bt["me"].get("moves"))
    chk("상대 기술은 안 알려줌", "moves" not in bt["foe"], list(bt["foe"].keys()))
    chk("기술에 PP 가 있음",
        all("pp" in m and "maxpp" in m for m in bt["me"]["moves"]),
        bt["me"]["moves"])
    chk("타입 정보 한글", bool(bt["foe"].get("types")), bt["foe"].get("types"))

    st, r = call("GET", "/api/battle")
    chk("진행 중 배틀 조회", r.get("battle", {}).get("id") == bid, r)
    st, r2 = call("POST", "/api/wild/%d/battle" % wid, {})
    chk("같은 야생에 또 걸면 이어받기", r2.get("resumed") is True, r2)

    section("턴 진행")
    mv = bt["me"]["moves"][0]
    pp_before = mv["pp"]
    st, r = call("POST", "/api/battle/%d/move" % bid, {"move": mv["key"]})
    chk("기술 사용 성공", st == 200 and "events" in r, r)
    ev = r["events"]
    chk("이벤트가 옴", len(ev) > 0, ev)
    kinds = set(e["t"] for e in ev)
    chk("기술 사용 이벤트 포함", "move" in kinds, kinds)
    now = r["battle"]
    used = [m for m in now["me"]["moves"] if m["key"] == mv["key"]]
    if used and mv["key"] != "STRUGGLE":
        chk("PP 가 1 줄어듦", used[0]["pp"] == pp_before - 1,
            (pp_before, used[0]["pp"]))
    chk("턴이 올라감", now["turn"] >= 1, now["turn"])
    dmg = [e for e in ev if e["t"] == "hit"]
    if dmg:
        chk("데미지가 1 이상", all(e["damage"] >= 1 for e in dmg), dmg)
        chk("체력이 음수가 안 됨", all(e["hp"] >= 0 for e in dmg), dmg)

    section("끝까지 싸우기")
    guard = 0
    while not now["over"] and guard < 100:
        guard += 1
        pick = best_move(now["me"])
        st, r = call("POST", "/api/battle/%d/move" % bid, {"move": pick["key"]})
        if st != 200:
            chk("전투 도중 오류", False, r)
            break
        now = r["battle"]
    chk("배틀이 끝남", now["over"], (guard, now))
    print("       결과: %s  (%d턴)" % (now["result"], now["turn"]))

    if now["result"] == "won":
        exp = r.get("exp") or []
        chk("경험치 지급됨", len(exp) >= 1, exp)
        part = [e for e in exp if not e.get("shared")]
        chk("싸운 포켓몬이 경험치 받음", len(part) == 1 and part[0]["gained"] > 0, exp)
        for e in exp:
            print("       %s +%d exp%s%s"
                  % (e["name"], e["gained"], "  (학습장치)" if e.get("shared") else "",
                     "  레벨업 -> %d" % e["level"] if e["leveledUp"] else ""))
        st, w2 = call("GET", "/api/wild")
        chk("이긴 뒤 야생이 사라짐", w2.get("wild") is None, w2)
    elif now["result"] == "lost":
        chk("졌을 때 교체 가능 여부를 알려줌", "canSwitch" in r, list(r.keys()))

    section("학습장치 (파티 전원 경험치)")
    # 확실히 이기도록 선두를 키워둔다 (야생은 파티 수준을 따라오므로
    # 상한을 넘지 않게 적당히만 올린다)
    st, p0 = call("GET", "/api/pokemon")
    lead = [m for m in p0["pokemon"] if m["onDesktop"]][0]
    call("POST", "/api/pokemon/%d/exp" % lead["id"], {"amount": 30000})
    # 파티를 여러 마리로 만든다
    caught_n = 0
    for _ in range(6):
        if weaken_and_catch():
            caught_n += 1
        st, mm = call("GET", "/api/me")
        if mm.get("balls", 0) <= 2:
            break
    print("       배틀로 깎아서 잡은 수: %d" % caught_n)
    st, p = call("GET", "/api/pokemon")
    party = [m for m in p["pokemon"] if m["onDesktop"]]
    print("       파티 %d마리 / 보유 %d마리" % (len(party), len(p["pokemon"])))
    if len(party) >= 2:
        before = dict((m["id"], m["info"]["expInLevel"] + m["level"] * 100000)
                      for m in party)
        wd = fresh_wild()
        if wd:
            st, r = call("POST", "/api/wild/%d/battle" % wd["id"], {})
            if st == 200:
                b2 = r["battle"]
                g = 0
                while not b2["over"] and g < 100:
                    g += 1
                    st, r = call("POST", "/api/battle/%d/move" % b2["id"],
                                 {"move": best_move(b2["me"])["key"]})
                    if st != 200:
                        break
                    b2 = r["battle"]
                if b2.get("result") == "won":
                    exp = r.get("exp") or []
                    shared = [e for e in exp if e.get("shared")]
                    chk("파티의 다른 포켓몬도 경험치를 받음", len(shared) >= 1, exp)
                    main_e = [e for e in exp if not e.get("shared")]
                    if shared and main_e:
                        chk("학습장치 몫이 더 적음",
                            shared[0]["gained"] < main_e[0]["gained"],
                            (main_e[0]["gained"], shared[0]["gained"]))

    section("배틀 중 몬스터볼 (체력을 깎으면 잘 잡힌다)")
    st, meb = call("GET", "/api/me")
    chk("볼이 남아 있어야 던질 수 있다", meb["balls"] >= 0, meb["balls"])
    wd = fresh_wild() if meb["balls"] > 0 else None
    if wd:
        st, r = call("POST", "/api/wild/%d/battle" % wd["id"], {})
        if st == 200:
            b3 = r["battle"]
            st, me2 = call("GET", "/api/me")
            balls_before = me2["balls"]
            st, r = call("POST", "/api/battle/%d/ball" % b3["id"], {})
            chk("배틀 중 볼 던지기 동작", st == 200 and "caught" in r, r)
            if st == 200:
                chk("볼이 1개 줄어듦", r["balls"] == balls_before - 1,
                    (balls_before, r["balls"]))
                chk("체력 비율이 판정에 쓰임", "hpRatio" in r, list(r.keys()))
                if r["caught"]:
                    chk("잡은 포켓몬이 파티나 박스로 감",
                        r.get("where") in ("party", "box"), r.get("where"))
                    print("       %s -> %s" % (r["message"], r.get("where")))
                else:
                    chk("실패하면 상대가 반격", "events" in r, list(r.keys()))
                    print("       %s" % r["message"])

    section("도망")
    wd = fresh_wild()
    if wd:
        st, r = call("POST", "/api/wild/%d/battle" % wd["id"], {})
        if st == 200:
            b4 = r["battle"]
            st, r = call("POST", "/api/battle/%d/run" % b4["id"], {})
            chk("도망 시도 동작", st == 200 and "escaped" in r, r)
            print("       %s" % ("도망 성공" if r.get("escaped") else "도망 실패"))
            if r.get("escaped"):
                st, w3 = call("GET", "/api/wild")
                chk("도망치면 야생이 사라짐", w3.get("wild") is None, w3)

    section("파티가 꽉 차면 PC 박스로")
    st, p = call("GET", "/api/pokemon")
    party = [m for m in p["pokemon"] if m["onDesktop"]]
    box = [m for m in p["pokemon"] if not m["onDesktop"]]
    chk("파티가 6마리를 넘지 않음", len(party) <= 6, len(party))
    print("       파티 %d / 박스 %d" % (len(party), len(box)))
    # 7마리 넘게 가졌을 때만 '넘쳤다' 고 말할 수 있다.
    # 딱 6마리면 넘친 게 없으니 박스가 비어 있는 게 맞다.
    total = len(party) + len(box)
    if total > 6:
        chk("넘친 만큼 박스로 갔다", len(box) == total - 6, (total, len(box)))
    else:
        chk("아직 넘치지 않았다 (파티 %d마리)" % total, len(box) == 0, len(box))

    section("남의 배틀 차단")
    other = "b%06d" % random.randrange(1000000)
    st, r = call("POST", "/api/auth/register",
                 {"username": other, "password": pw}, token="x")
    otok = r.get("token")
    st, r = call("POST", "/api/battle/%d/move" % bid, {"move": "TACKLE"}, otok)
    chk("남의 배틀에 기술 못 씀", st in (404, 409, 410), st)

    section("정리")
    st, r = call("DELETE", "/api/auth/account", {"password": pw})
    chk("탈퇴", st == 200, r)
    call("DELETE", "/api/auth/account", {"password": pw}, otok)

    print("")
    print("=" * 52)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 52)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
