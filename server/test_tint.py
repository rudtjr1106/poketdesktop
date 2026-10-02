# -*- coding: utf-8 -*-
"""이로치 색 고르기 검사 (1.8.0). 서버를 띄워 놓고 돌린다.

    python server/test_tint.py http://127.0.0.1:8788 /tmp/poket-test.db

## 무엇을 못 박나

  1. 값: None(이로치 색 그대로) · "normal"(기본 색) · 색조 열네 가지만 받는다.
  2. skin: 이로치가 아니면 tint 가 적혀 있어도 늘 기본 도트다.
  3. **이로치 포켓몬만** 고를 수 있다 (409). 남의 포켓몬은 404. 모르는 값은 400.
  4. 고른 색이 포켓몬 목록·바탕화면 목록에 실려 온다. None 으로 되돌린다.
  5. 배틀 자료에도 실린다 - 남의 화면에서도 그 색이어야 한다. **고른 색이
     없으면 대전 로그에 tint 칸 자체가 없다** (옛 판의 로그 글자가 바뀌면 안 된다).

이로치는 운이라 만들 수가 없어서 DB 를 직접 고친다 (검사용 DB 만).
"""
import json
import os
import random
import sqlite3
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from common import battle as B                               # noqa: E402
from common import party_battle as PB                        # noqa: E402
from common import pokelogic as P                            # noqa: E402
from common import tint as T                                 # noqa: E402

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


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except ValueError:
            return e.code, {}


def register(name):
    st, r = call("POST", "/api/auth/register",
                 {"username": name, "password": "1234", "starter": "PIKACHU", "device": "t"})
    if st != 200:
        raise SystemExit("가입 실패 %s %s %s" % (name, st, r))
    return r.get("token") or r["session"]["token"]


def sql(q, args=()):
    con = sqlite3.connect(DB)
    try:
        con.execute(q, args)
        con.commit()
    finally:
        con.close()


def unit_part():
    print("=== 값과 skin ===")
    chk("고를 수 있는 값은 기본 색 + 색조 14", len(T.CHOICES) == 15 and T.NORMAL in T.CHOICES,
        T.CHOICES)
    chk("None(되돌리기)은 된다", T.valid(None))
    chk("모르는 값은 안 된다", not T.valid("h090") and not T.valid("s091") and not T.valid(""),
        "")
    chk("DB 의 엉뚱한 값은 None 으로 읽는다", T.clean("zzz") is None and T.clean("n180") == "n180")
    chk("이로치가 아니면 늘 기본 도트", T.skin({"shiny": False, "tint": "s090"}) is False)
    chk("안 골랐으면 이로치 도트", T.skin({"shiny": True}) is True
        and T.skin({"shiny": True, "tint": None}) is True)
    chk("'기본 색' 은 기본 도트", T.skin({"shiny": True, "tint": "normal"}) is False)
    chk("색조를 고르면 그 값", T.skin({"shiny": True, "tint": "n135"}) == "n135")
    chk("모르는 글자는 이로치로 본다 (옛 화면이 새 값을 받아도 안 깨진다)",
        T.norm("x999") is True)
    chk("밑그림과 색조로 가른다", T.split("s090") == (True, 90) and T.split("n315") == (False, 315)
        and T.split(True) == (True, 0) and T.split(False) == (False, 0), "")
    chk("파일 이름 꼬리", T.suffix("s090") == "-h090" and T.suffix(True) == "" and T.suffix(False) == "")

    print("\n=== 대전 로그 ===")
    dex = P.Pokedex.load(os.path.join(ROOT, "server", "data", "pokedex.json"))
    m = P.make_pokemon(dex.get("PIKACHU"), 20, random.Random(1), shiny_rate=10 ** 9)
    plain = PB._side_view(B.Fighter(dex, dict(m)))
    chk("고른 색이 없으면 tint 칸이 없다 (옛 로그와 글자가 같다)", "tint" not in plain, plain)
    tinted = PB._side_view(B.Fighter(dex, dict(m, shiny=True, tint="s180")))
    chk("고른 색은 상대 화면으로 간다", tinted.get("tint") == "s180" and tinted.get("shiny") is True,
        tinted)
    fake = PB._side_view(B.Fighter(dex, dict(m, shiny=False, tint="s180")))
    chk("이로치가 아니면 안 싣는다", "tint" not in fake, fake)


def http_part():
    print("\n=== 서버 ===")
    tag = random.randint(1000, 9999)
    a = register("색%d" % tag)
    b = register("남%d" % tag)
    st, p = call("GET", "/api/pokemon", token=a)
    mine = p["pokemon"][0]
    pid = mine["id"]
    chk("처음엔 고른 색이 없다", mine.get("tint") is None, mine.get("tint"))
    st, r = call("POST", "/api/pokemon/%d/tint" % pid, {"tint": "s090"}, a)
    chk("이로치가 아니면 못 고른다 (409)", st == 409 and "이로치" in r.get("error", ""), (st, r))
    if not DB:
        print("  (DB 경로를 안 줘서 여기까지만 본다)")
        return
    sql("UPDATE pokemon SET shiny=1 WHERE id=?", (pid,))
    st, r = call("POST", "/api/pokemon/%d/tint" % pid, {"tint": "s090"}, a)
    chk("이로치는 색을 고른다", st == 200 and r["pokemon"]["tint"] == "s090", (st, r))
    st, p = call("GET", "/api/pokemon", token=a)
    got = [m for m in p["pokemon"] if m["id"] == pid][0]
    chk("포켓몬 목록에 실려 온다", got.get("tint") == "s090" and got.get("shiny") is True, got.get("tint"))
    st, d = call("GET", "/api/pokemon/desktop", token=a)
    desk = [m for m in d["pokemon"] if m["id"] == pid]
    chk("바탕화면 목록에도", desk and desk[0].get("tint") == "s090", desk and desk[0].get("tint"))
    st, r = call("POST", "/api/pokemon/%d/tint" % pid, {"tint": "h090"}, a)
    chk("모르는 값은 400", st == 400, (st, r))
    st, r = call("POST", "/api/pokemon/%d/tint" % pid, {"tint": "normal"}, a)
    chk("기본 색을 고른다", st == 200 and r["pokemon"]["tint"] == "normal"
        and r["pokemon"]["shiny"] is True, (st, r))
    st, r = call("POST", "/api/pokemon/%d/tint" % pid, {"tint": "n315"}, a)
    chk("기본 색 계열의 색조", st == 200 and r["pokemon"]["tint"] == "n315", (st, r))
    st, r = call("POST", "/api/pokemon/%d/tint" % pid, {"tint": "s180"}, b)
    chk("남의 포켓몬은 404", st == 404, (st, r))
    st, r = call("POST", "/api/pokemon/%d/tint" % pid, {"tint": None}, a)
    chk("None 으로 이로치 색으로 되돌린다", st == 200 and r["pokemon"]["tint"] is None, (st, r))
    st, r = call("POST", "/api/pokemon/%d/tint" % pid, {}, a)
    chk("값을 안 보내도 되돌리기다", st == 200 and r["pokemon"]["tint"] is None, (st, r))
    # 이로치가 아니게 된 행에 값이 남아 있어도 내보내지 않는다
    sql("UPDATE pokemon SET tint='s090', shiny=0 WHERE id=?", (pid,))
    st, p = call("GET", "/api/pokemon", token=a)
    got = [m for m in p["pokemon"] if m["id"] == pid][0]
    chk("이로치가 아니면 값이 남아 있어도 안 내보낸다", got.get("tint") is None, got.get("tint"))


def main():
    unit_part()
    http_part()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
