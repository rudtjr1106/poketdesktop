# -*- coding: utf-8 -*-
"""친구 기능 검사 — HTTP 로 실제 라우트를 두드린다.

    python server/test_social.py [http://127.0.0.1:8788]

계정을 캐낼 수 없어야 하는 곳이라, '되는가' 만큼 '안 되는가' 를 본다.
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
        with urllib.request.urlopen(req, timeout=60) as r:
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
    name = "zz%s%d" % (tag, random.randint(1000, 9999))
    s, r = call("POST", "/api/auth/register",
                {"username": name, "password": "1234",
                 "starter": "BULBASAUR", "device": "d" + tag})
    if s != 200:
        raise SystemExit("가입 실패 %s %s" % (s, r))
    return name, r["token"]


def main():
    an, at = mkuser("a")
    bn, bt = mkuser("b")
    cn, ct = mkuser("c")
    print("계정: %s / %s / %s" % (an, bn, cn))

    def uid_of(name, token):
        _s, _r = call("GET", "/api/friends/search?name=" +
                      urllib.parse.quote(name), None, token)
        return _r.get("id")

    ID_A, ID_B, ID_C = uid_of(an, bt), uid_of(bn, at), uid_of(cn, at)

    try:
        print("\n=== 찾기 ===")
        s, r = call("GET", "/api/friends/search?name=" + urllib.parse.quote(bn),
                    None, at)
        chk("정확한 닉네임은 찾아진다", s == 200 and r.get("found"), (s, r))
        chk("아직 남남", r.get("relation") == "none", r.get("relation"))
        s, r = call("GET", "/api/friends/search?name=" +
                    urllib.parse.quote(bn[:3]), None, at)
        chk("앞글자만으로는 못 찾는다 (계정 열거 방지)",
            s == 200 and not r.get("found"), (s, r))
        s, r = call("GET", "/api/friends/search?name=" +
                    urllib.parse.quote("없는사람"), None, at)
        chk("없으면 404 가 아니라 found:false", s == 200 and not r.get("found"),
            (s, r))
        s, r = call("GET", "/api/friends/search?name=" +
                    urllib.parse.quote(an), None, at)
        chk("나 자신은 self", r.get("relation") == "self", r.get("relation"))

        print("\n=== 신청 ===")
        s, r = call("POST", "/api/friends/request", {"username": an}, at)
        chk("자기 자신에게는 못 보낸다", s == 400, (s, r))
        s, r = call("POST", "/api/friends/request", {"username": "없는사람"}, at)
        chk("없는 사람에게는 404", s == 404, (s, r))
        s, r = call("POST", "/api/friends/request", {"username": bn}, at)
        chk("신청이 간다", s == 200 and r.get("state") == "pending", (s, r))
        s, r = call("POST", "/api/friends/request", {"username": bn}, at)
        chk("두 번 보내면 409", s == 409, (s, r))

        s, r = call("GET", "/api/friends", None, at)
        chk("보낸 신청이 outgoing 에 있다", len(r.get("outgoing") or []) == 1, r)
        s, r = call("GET", "/api/friends", None, bt)
        chk("받은 신청이 incoming 에 있다", len(r.get("incoming") or []) == 1, r)
        chk("신청을 보낸 사람이 a 로 보인다",
            r["incoming"][0]["id"] == ID_A, (r["incoming"], ID_A))

        print("\n=== 수락 ===")
        s, r = call("POST", "/api/friends/%d/accept" % ID_A, {}, at)
        chk("내가 보낸 신청은 내가 못 받는다", s == 404, (s, r))
        s, r = call("POST", "/api/friends/%d/accept" % ID_A, {}, bt)
        chk("받은 쪽이 수락한다", s == 200 and r.get("state") == "accepted",
            (s, r))
        s, r = call("GET", "/api/friends", None, at)
        chk("양쪽 다 친구 목록에 뜬다", len(r.get("friends") or []) == 1, r)
        chk("보낸 신청은 비었다", not r.get("outgoing"), r.get("outgoing"))
        f0 = r["friends"][0]
        chk("접속 중으로 보인다", f0["online"] is True, f0)
        # **시각이 아니라 초를 보낸다.** 시각을 보내면 받는 쪽이 자기 시계로
        # 빼는데, 몇 분 틀어진 PC 에서는 방금 접속한 친구가 "3시간 전" 으로
        # 보이거나 미래로 나온다. 센 쪽이 시계를 하나만 쓰면 그럴 일이 없다.
        chk("마지막 접속을 초로 보낸다", isinstance(f0.get("lastSeenAgo"), int),
            f0.get("lastSeenAgo"))
        # `x or -1` 로 쓰면 안 된다 - 0 초는 falsy 라 -1 이 되어 방금
        # 접속한 경우에만 검사가 실패한다.
        _sec = f0.get("lastSeenAgo")
        chk("방금 접속했으니 작은 값",
            _sec is not None and 0 <= _sec < 120, _sec)
        # 접속 중이 위, 그 다음은 최근에 본 순서. 한 번도 안 온 사람은 맨 뒤.
        _key = [(not x["online"],
                 x["lastSeenAgo"] if x["lastSeenAgo"] is not None
                 else float("inf")) for x in r["friends"]]
        chk("접속 중이 먼저, 그 다음 최근 순",
            _key == sorted(_key), _key)
        s, r = call("POST", "/api/friends/request", {"username": bn}, at)
        chk("이미 친구면 409", s == 409, (s, r))

        print("\n=== 서로 신청하면 바로 친구 ===")
        s, r = call("POST", "/api/friends/request", {"username": cn}, at)
        chk("a 가 c 에게 신청", s == 200 and r["state"] == "pending", (s, r))
        s, r = call("POST", "/api/friends/request", {"username": an}, ct)
        chk("c 도 a 에게 보내면 그 자리에서 친구가 된다",
            s == 200 and r.get("state") == "accepted", (s, r))

        print("\n=== 프로필 ===")
        s, r = call("GET", "/api/users/%d/profile" % ID_B, None, at)
        chk("친구 프로필이 보인다", s == 200 and r.get("relation") == "friend",
            (s, r))
        chk("친구는 최근 전적도 보인다", "recent" in r, r)
        chk("친구는 마지막 접속도 보인다",
            isinstance(r.get("lastSeenAgo"), int), r.get("lastSeenAgo"))
        s, r = call("GET", "/api/users/%d/profile" % ID_B, None, ct)
        chk("남의 최근 전적은 안 보인다", r.get("recent") == [], r)
        # "언제 컴퓨터 앞에 있었나" 는 접속 중 표시(3분 창)보다 훨씬 많은
        # 것을 말해 준다 - 생활 시간표가 그대로 드러난다.
        chk("남의 마지막 접속은 안 보인다", "lastSeenAgo" not in r, r)

        print("\n=== 거절 ===")
        s, r = call("POST", "/api/friends/request", {"username": cn}, bt)
        chk("b 가 c 에게 신청", s == 200, (s, r))
        s, r = call("DELETE", "/api/friends/%d" % ID_B, None, ct)
        chk("거절된다", s == 200 and r.get("was") == "incoming", (s, r))
        s, r = call("POST", "/api/friends/request", {"username": cn}, bt)
        chk("거절 직후 다시 보내면 막힌다 (429)", s == 429, (s, r))

        print("\n=== 차단 ===")
        s, r = call("POST", "/api/friends/%d/block" % ID_C, {}, bt)
        chk("차단된다", s == 200, (s, r))
        s, r = call("GET", "/api/friends", None, bt)
        chk("차단 목록에 뜬다", len(r.get("blocked") or []) == 1, r)
        s, r = call("POST", "/api/friends/request", {"username": cn}, bt)
        chk("차단한 사람에게는 못 보낸다", s == 403, (s, r))
        s, r = call("POST", "/api/friends/request", {"username": bn}, ct)
        chk("차단당한 쪽도 못 보낸다", s == 403, (s, r))
        s, r = call("GET", "/api/friends/search?name=" +
                    urllib.parse.quote(bn), None, ct)
        chk("차단당했는지 차단했는지 구분되지 않는다",
            r.get("relation") == "blocked", r.get("relation"))
        s, r = call("DELETE", "/api/friends/%d/block" % ID_C, None, bt)
        chk("차단이 풀린다", s == 200, (s, r))
        s, r = call("GET", "/api/friends", None, bt)
        chk("차단 목록이 빈다", not r.get("blocked"), r.get("blocked"))

        print("\n=== 친구 삭제 ===")
        s, r = call("DELETE", "/api/friends/%d" % ID_B, None, at)
        chk("친구가 끊긴다", s == 200 and r.get("was") == "friend", (s, r))
        s, r = call("GET", "/api/friends", None, bt)
        chk("상대 쪽에서도 사라진다",
            not any(f["id"] != 0 and f["name"] == an
                    for f in (r.get("friends") or [])), r.get("friends"))
        s, r = call("DELETE", "/api/friends/%d" % ID_B, None, at)
        chk("없는 관계를 지우면 404", s == 404, (s, r))

        print("\n=== 인증 없이는 ===")
        s, r = call("GET", "/api/friends")
        chk("토큰 없이는 401", s == 401, (s, r))
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
