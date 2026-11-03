# -*- coding: utf-8 -*-
"""닉네임 변경권 검사 (2.1.1, app/rename.py). 서버를 띄우지 않는다.

    python server/test_rename.py

닉네임은 로그인 아이디이기도 하다. 못 박는 것:

  1. 도구가 있고 상점에서 30,000원. 드랍 · 코인 상점에는 없다.
  2. 규칙에 어긋나면 거절하고 **변경권은 그대로**: 가입 규칙(길이 · 글자 · 대괄호), 지금과 같은 이름, 남이 쓰는
     이름(대소문자 무시), 운영자 이름 · '운영자' 같은 말. 운영자 계정은 바꿀 수 없다 (403). 변경권이 없으면 거절.
  3. 바꾸면 한 번에: users · 내 게시판 글 · 댓글 · 길드 채팅 이름. 남의 줄은 그대로. 변경권 한 장이 빠진다.
  4. 새 이름 + 같은 비밀번호로 로그인되고 옛 이름으로는 안 된다. 자동 로그인 세션은 그대로 산다.
  5. 대소문자만 바꾸는 것은 된다.
  6. 검사와 바꾸기 사이에 누가 그 이름으로 가입하면(UNIQUE) 409 이고 **아무것도 안 바뀐다** (변경권도 그대로).
"""
import datetime
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-rename-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_HOUSEKEEP"] = "0"
os.environ["POKET_BOARD_ADMINS"] = "운영왕,AdminKim"

from fastapi import HTTPException                                # noqa: E402

from app import auth, db, guild, item_routes, items, main, rename  # noqa: E402

OK = FAIL = 0
PW = "1234"


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Req(object):
    headers = {}
    client = type("C", (), {"host": "127.0.0.1"})()


def iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def mkuser(name):
    h, salt, it = auth.hash_password(PW)
    return db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                  " created_at, last_login, last_ip) VALUES (?,?,?,?,10,0,?,?,'')",
                  (name, h, salt, it, iso(), iso())).lastrowid


def me(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def use(uid, name):
    try:
        return item_routes.use(item_routes.UseIn(item=rename.TICKET, name=name), me(uid)), None
    except HTTPException as e:
        return None, (e.status_code, e.detail)


def login(name):
    try:
        return main.login(main.LoginIn(username=name, password=PW), Req())
    except HTTPException as e:
        return None


def name_of(uid):
    return db.q1("SELECT username FROM users WHERE id=?", (uid,))["username"]


def tickets(uid):
    return items.bag_count(uid, rename.TICKET)


def catalog():
    print("-- 1. 도구")
    it = items.get(rename.TICKET)
    chk("닉네임 변경권이 있다 (상점 30,000원)", it and it["effect"]["kind"] == "rename"
        and items.buy_price(rename.TICKET) == 30000 and it["sell"] == 0)
    chk("  코인 상점에는 없다", guild.coin_price(rename.TICKET) == 0)
    chk("  드랍 표에는 없다", rename.TICKET not in set(i for i, _w in items.data()["dropTable"]))


def refuse():
    print("-- 2. 거절 (변경권은 그대로)")
    uid = mkuser("바꿀사람")
    mkuser("있는이름")
    mkuser("Taken")
    items.bag_add(uid, rename.TICKET, 1)
    cases = [("가", "한 글자"), ("가나다라마바사아자차카타파", "13자"), ("[길드]이름", "대괄호"),
             ("이름  둘", "공백 둘"), ("바꿀사람", "지금과 같은 이름"), ("있는이름", "남이 쓰는 이름"),
             ("TAKEN", "남이 쓰는 이름 (대소문자만 다름)"), ("운영왕", "운영자 이름"),
             ("adminkim", "운영자 이름 (대소문자만 다름)"), ("나는운영자", "'운영자' 가 든 이름"),
             ("GM철수", "'GM' 낱말이 든 이름"), ("admin_kim", "'admin' 낱말이 든 이름"),
             ("포스크탑짱", "'포스크탑' 이 든 이름")]
    for new, why in cases:
        r, err = use(uid, new)
        chk("%s: 거절" % why, r is None and err and err[0] in (400, 409) and tickets(uid) == 1
            and name_of(uid) == "바꿀사람", err)
    r, err = use(uid, "있는이름")
    chk("  남이 쓰는 이름은 409", err and err[0] == 409, err)

    boss = mkuser("운영왕")
    items.bag_add(boss, rename.TICKET, 1)
    r, err = use(boss, "평범한이름")
    chk("운영자 계정은 못 바꾼다 (403)", err and err[0] == 403 and tickets(boss) == 1
        and name_of(boss) == "운영왕", err)

    poor = mkuser("표없음")
    r, err = use(poor, "새이름하나")
    chk("변경권이 없으면 거절", r is None and err and "변경권" in err[1] and name_of(poor) == "표없음", err)


def apply_():
    print("-- 3. 바꾸기")
    uid = mkuser("옛닉네임")
    other = mkuser("남남")
    items.bag_add(uid, rename.TICKET, 2)
    tok, _exp = auth.issue_token(uid, "127.0.0.1", "dev", False)
    gid = db.run("INSERT INTO guild (name, master_id, created_at) VALUES (?,?,?)", ("길드", uid, iso())).lastrowid
    pid = db.run("INSERT INTO board_post (kind, user_id, author, title, body, created_at) VALUES (?,?,?,?,?,?)",
                 ("free", uid, "옛닉네임", "제목", "본문", iso())).lastrowid
    db.run("INSERT INTO board_post (kind, user_id, author, title, body, created_at) VALUES (?,?,?,?,?,?)",
           ("free", other, "남남", "남의 글", "본문", iso()))
    db.run("INSERT INTO board_comment (post_id, user_id, author, body, created_at) VALUES (?,?,?,?,?)",
           (pid, uid, "옛닉네임", "내 댓글", iso()))
    db.run("INSERT INTO board_comment (post_id, user_id, author, body, created_at) VALUES (?,?,?,?,?)",
           (pid, other, "남남", "남의 댓글", iso()))
    db.run("INSERT INTO guild_chat (guild_id, user_id, name, body, at) VALUES (?,?,?,?,?)",
           (gid, uid, "옛닉네임", "안녕", iso()))
    db.run("INSERT INTO guild_chat (guild_id, user_id, name, body, at) VALUES (?,?,?,?,?)",
           (gid, other, "남남", "반가워", iso()))
    db.run("INSERT INTO guild_chat (guild_id, user_id, name, body, at) VALUES (?,NULL,'',?,?)",
           (gid, "알림 줄", iso()))

    r, err = use(uid, "  새 닉네임 ")
    chk("바뀐다 (앞뒤 공백은 뗀다)", r and r["username"] == "새 닉네임" and name_of(uid) == "새 닉네임", err)
    chk("  말에 새 이름과 '다음에 로그인할 때'", r and "새 닉네임" in r["message"] and "로그인" in r["message"],
        r and r["message"])
    chk("  변경권 한 장이 빠진다", tickets(uid) == 1, tickets(uid))
    q = db.q
    chk("  내 글 · 댓글 · 채팅 이름이 바뀐다",
        [x["author"] for x in q("SELECT author FROM board_post WHERE user_id=?", (uid,))] == ["새 닉네임"]
        and [x["author"] for x in q("SELECT author FROM board_comment WHERE user_id=?", (uid,))] == ["새 닉네임"]
        and [x["name"] for x in q("SELECT name FROM guild_chat WHERE user_id=?", (uid,))] == ["새 닉네임"])
    chk("  남의 줄 · 알림 줄은 그대로",
        [x["author"] for x in q("SELECT author FROM board_post WHERE user_id=?", (other,))] == ["남남"]
        and [x["author"] for x in q("SELECT author FROM board_comment WHERE user_id=?", (other,))] == ["남남"]
        and [x["name"] for x in q("SELECT name FROM guild_chat WHERE user_id IS NOT ? ORDER BY id", (uid,))]
        == ["남남", ""])

    print("-- 4. 로그인")
    chk("새 이름 + 같은 비밀번호로 로그인된다", (login("새 닉네임") or {}).get("user", {}).get("username") == "새 닉네임")
    chk("  옛 이름으로는 안 된다", login("옛닉네임") is None)
    sess, user = auth.lookup_session_with_user(tok)
    chk("  자동 로그인 세션은 그대로 산다 (새 이름으로)", sess and user and user["username"] == "새 닉네임")
    chk("옛 이름은 이제 남이 가입할 수 있다", not auth.name_taken("옛닉네임") and auth.name_taken("새 닉네임"))

    u3 = mkuser("영어이름")
    items.bag_add(u3, rename.TICKET, 2)
    r, err = use(u3, "Sigma")
    chk("영어 말은 낱말로만 막는다 ('Sigma' 는 된다)", r and name_of(u3) == "Sigma", err)
    r, err = use(u3, "badminton")
    chk("  'badminton' 도 된다", r and name_of(u3) == "badminton", err)

    print("-- 5. 대소문자만")
    u2 = mkuser("abcd")
    items.bag_add(u2, rename.TICKET, 1)
    r, err = use(u2, "ABCD")
    chk("대소문자만 바꾸는 것은 된다", r and name_of(u2) == "ABCD" and tickets(u2) == 0, err)


def race():
    print("-- 6. 그사이 누가 그 이름으로 가입했다")
    uid = mkuser("느린사람")
    tok_pid = db.run("INSERT INTO board_post (kind, user_id, author, title, body, created_at) VALUES (?,?,?,?,?,?)",
                     ("free", uid, "느린사람", "t", "b", iso())).lastrowid
    items.bag_add(uid, rename.TICKET, 1)
    real = rename.check

    def late(u, new):
        got = real(u, new)
        mkuser(new)                                         # 검사를 지난 바로 뒤에 남이 가입했다
        return got
    rename.check = late
    try:
        r, err = use(uid, "빠른이름")
    finally:
        rename.check = real
    chk("409", r is None and err and err[0] == 409, err)
    chk("  아무것도 안 바뀐다 (변경권 · 이름 · 글쓴이)", tickets(uid) == 1 and name_of(uid) == "느린사람"
        and db.q1("SELECT author FROM board_post WHERE id=?", (tok_pid,))["author"] == "느린사람")
    r, err = use(uid, "다른이름")
    chk("  그 뒤에도 쓸 수 있다 (잠금이 남지 않는다)", r and name_of(uid) == "다른이름", err)


def main_():
    db.init()
    catalog()
    refuse()
    apply_()
    race()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
