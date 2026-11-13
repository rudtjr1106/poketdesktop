# -*- coding: utf-8 -*-
"""새 앱 판 알림 검사 (2.5.0) — 서버가 깃허브의 최신 릴리스를 보고 소켓으로 민다.

    python server/test_release_watch.py

깃허브에는 붙지 않는다 (가짜 opener). 소켓도 띄우지 않는다 (visit.push_all 을 바꿔 끼운다).

못 박는 것:

  1. 판 번호 꼴만 받는다 ('v2.5.0' -> '2.5.0'). 이상한 글자는 앱에 밀지 않는다.
  2. 판이 바뀔 때만 민다 (서버가 뜬 뒤 처음 읽은 것도 민다 - 그 사이에 붙은 앱은 hello 에 latest 가 없었다).
     같은 판을 다시 읽으면 안 민다.
  3. ETag 를 적어 두고 다음에 If-None-Match 로 묻는다. 304 · 실패면 아무것도 안 바꾼다.
  4. hello 에 push(이 서버가 밀어 주는 것) 와 latest 가 실린다. 모르면 latest 는 없다.
  5. 운영 서버에서만 켠다 (기본은 꺼짐).
"""
import io
import json
import os
import sys
import tempfile
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="poket-release-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ.pop("POKET_RELEASE_WATCH", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import config, release_watch as RW, visit          # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


class Resp(object):
    def __init__(self, body, etag=None):
        self.body = json.dumps(body).encode()
        self.headers = {"ETag": etag} if etag else {}

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Opener(object):
    """차례로 돌려줄 것들. 304 · 예외도 넣을 수 있다. 받은 요청을 적어 둔다."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.reqs = []

    def __call__(self, req, timeout=None):
        self.reqs.append(req)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


def http(code):
    return urllib.error.HTTPError("https://api.github.com/x", code, "x", {}, io.BytesIO(b""))


def main():
    pushed = []
    visit.push_all = lambda payload: pushed.append(payload) or 7

    print("1. 판 번호 꼴")
    chk("v2.5.0 -> 2.5.0", RW.tag_of({"tag_name": "v2.5.0"}) == "2.5.0")
    chk("V1.10.3 -> 1.10.3", RW.tag_of({"tag_name": "V1.10.3"}) == "1.10.3")
    chk("이상한 글자는 버린다", RW.tag_of({"tag_name": "v2.5.0<script>"}) is None)
    chk("없으면 None", RW.tag_of({}) is None and RW.tag_of(None) is None)
    chk("숫자 하나는 버린다 (판 번호 꼴이 아니다)", RW.tag_of({"tag_name": "v7"}) is None)

    print("2. 바뀔 때만 민다")
    RW.reset()
    op = Opener(Resp({"tag_name": "v2.4.0"}, '"e1"'), http(304), Resp({"tag_name": "v2.4.0"}, '"e1"'),
                Resp({"tag_name": "v2.5.0"}, '"e2"'), http(500), OSError("끊김"))
    chk("처음 읽은 판도 민다", RW.check_once(op) == "2.4.0" and pushed[-1] == {"t": "update", "v": "2.4.0"}, pushed)
    chk("latest 에 적힌다", RW.latest() == "2.4.0")
    n = len(pushed)
    chk("304 면 안 민다", RW.check_once(op) is None and len(pushed) == n)
    chk("두 번째 요청에 If-None-Match", op.reqs[1].get_header("If-none-match") == '"e1"', op.reqs[1].headers)
    chk("같은 판을 다시 읽으면 안 민다", RW.check_once(op) is None and len(pushed) == n)
    chk("새 판이면 민다", RW.check_once(op) == "2.5.0" and pushed[-1] == {"t": "update", "v": "2.5.0"}, pushed)
    chk("ETag 를 새것으로", op.reqs[3] is not None and RW._state["etag"] == '"e2"', RW._state)
    n = len(pushed)
    chk("깃허브가 500 이면 그대로", RW.check_once(op) is None and RW.latest() == "2.5.0" and len(pushed) == n)
    chk("끊겨도 그대로", RW.check_once(op) is None and RW.latest() == "2.5.0" and len(pushed) == n)
    chk("주소는 이 저장소의 releases/latest",
        op.reqs[0].full_url == "https://api.github.com/repos/%s/releases/latest" % config.RELEASE_REPO,
        op.reqs[0].full_url)
    chk("User-Agent 를 싣는다 (깃허브가 요구한다)", bool(op.reqs[0].get_header("User-agent")))

    print("3. hello")
    h = visit._hello(5)
    chk("push 에 live", h.get("t") == "hello" and "live" in h.get("push", []) and h.get("userId") == 5, h)
    chk("latest 가 실린다", h.get("latest") == "2.5.0", h)
    RW.reset()
    chk("모르면 latest 가 없다", "latest" not in visit._hello(5), visit._hello(5))
    json.dumps(visit._hello(5))

    print("4. 켜는 것")
    chk("기본은 꺼짐 (검사 서버가 깃허브를 두드리지 않게)", config.RELEASE_WATCH is False)
    chk("깃허브 한도(로그인 없이 시간당 60번 - 304 도 센다)의 반쯤만 쓴다: 기본 2분, 90초 밑으로는 안 내려간다",
        config.RELEASE_WATCH_SEC == 120 and RW.MIN_SEC >= 90 and 3600 / max(RW.MIN_SEC, config.RELEASE_WATCH_SEC) <= 30,
        (config.RELEASE_WATCH_SEC, RW.MIN_SEC))
    prod = open(os.path.join(os.path.dirname(HERE), "deploy", "docker-compose.prod.yml"), encoding="utf-8").read()
    chk("운영 compose 에서 켠다", 'POKET_RELEASE_WATCH: "1"' in prod)

    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
