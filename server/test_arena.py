# -*- coding: utf-8 -*-
"""유저 배틀 걸기 검사 — HTTP 로 실제 라우트를 두드린다.

    python server/test_arena.py [http://127.0.0.1:8788]

대전은 비동기다. 상대가 접속해 있지 않아도 그 사람의 지금 파티를 가져와
붙인다. 그래서 '자는 사람을 계속 때릴 수 있는가' 를 특히 본다.
"""
import json
import random
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788").rstrip("/")
OK = FAIL = 0


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:                                   # noqa: BLE001
            return e.code, {}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(tag):
    name = "zzar%s%d" % (tag, random.randint(1000, 9999))
    s, r = call("POST", "/api/auth/register",
                {"username": name, "password": "1234",
                 "starter": "BULBASAUR", "device": "d" + tag})
    if s != 200:
        raise SystemExit("가입 실패 %s %s" % (s, r))
    return name, r["token"]


def uid_of(name, token):
    s, r = call("GET", "/api/friends/search?name=" +
                urllib.parse.quote(name), None, token)
    return r.get("id")


def main():
    an, at = mkuser("a")
    bn, bt = mkuser("b")
    cn, ct = mkuser("c")
    ID_A, ID_B, ID_C = uid_of(an, bt), uid_of(bn, at), uid_of(cn, at)
    print("계정: %s(%s) / %s(%s) / %s(%s)" % (an, ID_A, bn, ID_B, cn, ID_C))

    try:
        print("\n=== 친구가 아니면 못 건다 ===")
        s, r = call("POST", "/api/pvp/challenge/%d" % ID_B, {}, at)
        chk("남에게는 지목 배틀을 못 건다", s == 403, (s, r))

        print("\n=== 친구가 되고 나서 ===")
        call("POST", "/api/friends/request", {"username": bn}, at)
        call("POST", "/api/friends/%d/accept" % ID_A, {}, bt)
        s, r = call("POST", "/api/pvp/challenge/%d" % ID_B, {}, at)
        chk("친구에게는 걸린다", s == 200 and r.get("matchId"), (s, r))
        chk("바로 결과가 나온다", r.get("a", {}).get("result") in
            ("win", "lose", "draw"), r.get("a"))
        chk("상대 수락을 기다리지 않는다", "pending" not in json.dumps(r), r)
        mid = r["matchId"]

        print("\n=== 상대는 나중에 받는다 ===")
        s, r = call("GET", "/api/pvp/pending", None, bt)
        got = [m for m in r.get("matches", []) if m["id"] == mid]
        chk("상대의 '안 본 대전' 에 들어온다", len(got) == 1, r)
        chk("상대는 '걸려온' 것으로 표시된다",
            got and got[0]["attacked"] is False, got)
        s, r = call("GET", "/api/me", None, bt)
        chk("sync 응답에도 개수가 실린다", r.get("pvpUnseen", 0) >= 1,
            r.get("pvpUnseen"))
        s, r = call("GET", "/api/pvp/pending", None, at)
        chk("건 사람은 이미 본 것으로 친다",
            not [m for m in r.get("matches", []) if m["id"] == mid], r)

        print("\n=== 친구 배틀은 점수를 안 건드린다 ===")
        s, ra = call("GET", "/api/pvp/records", None, at)
        s, rb = call("GET", "/api/pvp/records", None, bt)
        chk("건 쪽 점수 그대로", ra["records"][0]["delta"] == 0,
            ra["records"][0])
        chk("받은 쪽 점수도 그대로", rb["records"][0]["delta"] == 0,
            rb["records"][0])
        chk("자는 쪽도 전적은 남는다", len(rb["records"]) == 1, rb)

        print("\n=== 같은 상대 쿨다운 ===")
        s, r = call("POST", "/api/pvp/challenge/%d" % ID_B, {}, at)
        chk("바로 다시 걸면 막힌다", s == 409, (s, r))
        chk("이유를 알려준다", "분에 한 번" in str(r.get("error", "")), r)

        print("\n=== 랜덤 배틀 ===")
        s, r = call("POST", "/api/pvp/random", {}, ct)
        chk("상대를 찾아 붙는다", s == 200 and r.get("matchId"), (s, r))
        chk("랜덤으로 기록된다", r.get("kind") == "random", r.get("kind"))
        s, r = call("GET", "/api/pvp/pending", None, ct)
        chk("남은 도전 횟수를 알려준다",
            (r.get("fight") or {}).get("left") is not None, r.get("fight"))

        print("\n=== 랜덤 배틀은 서로 점수를 주고받는다 ===")
        # **여기서 계정을 하나 더 만든다.** 계정이 셋뿐이면 b 가 앞에서
        # a·c 둘 다와 붙어 버리는 경우가 생기고, 그러면 짝 쿨다운(30분)에
        # 걸려 "붙을 상대가 없습니다" 로 끝난다. 앞의 랜덤 배틀이 누구를
        # 고르냐에 따라 갈려서 세 번에 한 번쯤 실패했다. 아직 아무와도
        # 안 붙은 상대를 하나 넣어 두면 항상 성사된다.
        mkuser("d")
        # 응답에 양쪽 결과가 다 들어 있다. 상대의 전적을 따로 조회하면
        # 안 된다 - 상대가 누구인지 모르고(서버가 고른다), 그 사람의
        # 최근 전적이 이 판이라는 보장도 없다.
        s, rb2 = call("POST", "/api/pvp/random", {}, bt)
        if s != 200:
            chk("랜덤 배틀 성사 (%s)" % s, False, rb2)
        else:
            da, dbv = rb2["a"]["delta"], rb2["b"]["delta"]
            chk("랜덤은 점수가 움직인다", da != 0 or dbv != 0, (da, dbv))
            chk("한쪽이 얻으면 한쪽이 잃는다", da * dbv < 0, (da, dbv))
            chk("주고받는 크기가 같다", abs(da + dbv) <= 1, (da, dbv))
            chk("건 쪽도 받은 쪽도 랜덤으로 기록된다",
                rb2.get("kind") == "random", rb2.get("kind"))
            chk("자던 쪽 점수도 깎인다 (사용자가 정한 대로)",
                rb2["b"]["rating"] != 1000 or rb2["b"]["delta"] != 0,
                rb2["b"])

        print("\n=== 차단하면 안 붙는다 ===")
        call("POST", "/api/friends/%d/block" % ID_C, {}, at)
        s, r = call("POST", "/api/pvp/challenge/%d" % ID_C, {}, at)
        chk("차단한 상대에게는 못 건다", s in (403, 409), (s, r))
        call("DELETE", "/api/friends/%d/block" % ID_C, None, at)

        print("\n=== 하루 상한 ===")
        # c 로 계속 걸어 본다. 쿨다운 때문에 상대가 곧 동나므로,
        # 상한과 '상대 없음' 중 무엇에 걸리든 무한히는 안 된다.
        codes = []
        for _ in range(25):
            s, r = call("POST", "/api/pvp/random", {}, ct)
            codes.append(s)
            if s != 200:
                break
        chk("무한히 걸 수는 없다", codes[-1] != 200, codes[-3:])
        chk("멈추는 이유가 분명하다", codes[-1] in (404, 409), codes[-1])
        s, r = call("GET", "/api/pvp/pending", None, ct)
        f = r.get("fight") or {}
        chk("건 횟수가 상한을 안 넘는다",
            f.get("foughtToday", 0) <= f.get("dailyBattles", 20), f)

        print("\n=== 다시보기 ===")
        s, r = call("GET", "/api/pvp/match/%d" % mid, None, bt)
        chk("상대도 그 판을 볼 수 있다", s == 200 and r.get("events"), s)
        chk("자기 시점으로 온다", r.get("me", {}).get("name") == bn,
            r.get("me"))
        s, r = call("GET", "/api/pvp/match/%d" % mid, None, ct)
        chk("낀 적 없는 사람은 못 본다", s == 404, s)

        print("\n=== 순위표 ===")
        s, r = call("GET", "/api/pvp/ranking", None, ct)
        chk("순위표를 볼 수 있다", s == 200 and "ranking" in r, s)
    finally:
        print("\n=== 정리 ===")
        for t in (at, bt, ct):
            call("DELETE", "/api/auth/account", {"password": "1234"}, t)

    print("\n======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
