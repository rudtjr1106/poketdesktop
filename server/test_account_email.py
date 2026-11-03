# -*- coding: utf-8 -*-
"""마이페이지 이메일 검사 (2.1.1, mypage.set_email). 서버를 띄우지 않는다.

    python server/test_account_email.py

비밀번호를 잊은 사람이 재설정을 부탁할 때 운영자가 계정에서 보는 연락처다 (확인 메일 · 비밀번호 찾기는 없다).
못 박는 것:

  1. 적으면 소문자로 저장하고, 빈 칸으로 적으면 지운다. 모양이 틀리면 400 이고 그대로다.
  2. 본인 마이페이지(build)에는 그대로 보이고, 길드원 프로필(card)에는 없다.
  3. 옛 DB 에 칸이 붙는다 (db.init 의 MIGRATIONS).
"""
import datetime
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="poket-acct-email-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_HOUSEKEEP"] = "0"

from fastapi import HTTPException                                # noqa: E402

from app import db, deps, mypage                                 # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def ctx(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def put(uid, email):
    try:
        return mypage.set_email(mypage.EmailIn(email=email), ctx(uid)), None
    except HTTPException as e:
        return None, (e.status_code, e.detail)


def stored(uid):
    return db.q1("SELECT email FROM users WHERE id=?", (uid,))["email"]


def main():
    db.init()
    chk("users 에 email 칸이 붙는다", any(c["name"] == "email" for c in db.q("PRAGMA table_info(users)")))
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login, last_ip)"
                 " VALUES ('이메일러', x'00', x'00', 1, 10, 0, ?, ?, '')", (iso(), iso())).lastrowid
    me = mypage.build(ctx(uid)["user"], deps.dex())["user"]
    chk("처음에는 빈 글자", me.get("email") == "", me.get("email"))

    r, err = put(uid, "  Trainer@Gmail.COM ")
    chk("적으면 앞뒤 공백을 떼고 소문자로", r and r["email"] == "trainer@gmail.com" and stored(uid) == "trainer@gmail.com",
        (r, err))
    for bad in ("abc", "a@b", "a b@c.com", "a@@b.com", "x" * 95 + "@a.com"):
        r, err = put(uid, bad)
        chk("모양이 틀리면 400, 그대로 (%s)" % bad[:12], err and err[0] == 400 and stored(uid) == "trainer@gmail.com", err)

    me = mypage.build(ctx(uid)["user"], deps.dex())["user"]
    chk("본인 마이페이지에는 그대로 보인다", me.get("email") == "trainer@gmail.com", me.get("email"))
    card = mypage.card(uid, deps.dex())
    chk("길드원 프로필(card)에는 없다", "trainer@" not in str(card) and "email" not in card["user"], card["user"])

    r, err = put(uid, "   ")
    chk("빈 칸으로 적으면 지운다", r and r["email"] == "" and stored(uid) is None and "지웠습니다" in r["message"],
        (r, err))
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
