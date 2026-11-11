# -*- coding: utf-8 -*-
"""나그네 예약 글 검사 (2.4.0 - 아르케 이벤트 본체는 2.5.0).

    python server/test_traveler_posts.py

서버를 띄우지 않는다 (임시 DB · 임시 비공개 자료 폴더). 글 내용은 검사용으로 지어낸 것이다 (진짜 글은 운영 볼륨에만).

무엇을 못 박나:
  1. 때가 된 **나그네(traveler)** 글만 올라간다 - 고고학자(npc) 글 · 아직 때가 안 된 글 · ref 가 arche: 로 시작하지 않는
     글 · 본문이 빈 글은 안 올라간다. 같은 글은 두 번 안 올라간다 (지워도 다시 안 올린다).
  2. 나그네 계정은 로그인할 수 없다 (비밀번호 해시가 비어 있다). 그 이름을 진짜 사람이 쓰고 있으면 올리지 않는다.
  3. 비공개 자료의 게시판 계정 이름(나그네 · 고고학자)과 '고고학자' 가 든 이름은 가입 · 닉네임 바꾸기에서 막는다.
  4. 비공개 자료가 없거나 깨졌으면 아무것도 안 하고 아무것도 안 깨진다.
  5. 게시판 목록을 열면 (때가 된 글이 있으면) 먼저 올라간다. 프로세스 안에서는 30초에 한 번만 본다.
"""
import datetime
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-traveler-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_ARCHE_DIR"] = os.path.join(TMP, "arche")
os.environ["POKET_BOARD_IMG_DIR"] = os.path.join(TMP, "board_img")

from app import auth, board_routes, config, db, traveler_posts as TP   # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc
KST = datetime.timezone(datetime.timedelta(hours=9))
NAME, NPC = "떠도는나그네", "시험고고학자"


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def kst(*a):
    return datetime.datetime(*a, tzinfo=KST)


def write_secrets(data):
    os.makedirs(config.ARCHE_DIR, exist_ok=True)
    path = os.path.join(config.ARCHE_DIR, "secrets.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1000))     # 같은 초에 다시 써도 다시 읽게


SECRETS = {
    "traveler": NAME, "npc": NPC, "chapters": {},
    "posts": [
        {"ref": "arche:pre1", "at": "2026-11-13T21:00:00+09:00", "by": "traveler", "title": "첫 글", "body": "나그네 첫 글"},
        {"ref": "arche:pre2", "at": "2026-11-14T22:00:00+09:00", "by": "traveler", "title": "둘째 글", "body": "나그네 둘째 글"},
        {"ref": "arche:end", "at": "2026-11-13T20:00:00+09:00", "by": "npc", "title": "고고학자", "body": "고고학자 글"},
        {"ref": "pre-x", "at": "2026-11-13T20:00:00+09:00", "by": "traveler", "title": "모양 틀림", "body": "ref 가 틀렸다"},
        {"ref": "arche:empty", "at": "2026-11-13T20:00:00+09:00", "by": "traveler", "title": "빈 글", "body": " "},
        {"ref": "arche:naive", "at": "2026-11-13T12:30:00", "by": "traveler", "title": "시간대 없음", "body": "UTC 로 읽는다"},
    ],
}


def posts():
    return db.q("SELECT * FROM board_post ORDER BY id")


def mkuser(name, pw=b"x"):
    return db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login,"
                  " last_ip) VALUES (?,?,?,1,10,0,'','','')", (name, pw, b"x")).lastrowid


def main():
    db.init()

    print("=== 비공개 자료가 없으면 ===")
    TP.reset()
    chk("아무것도 안 하고 안 깨진다", TP.ensure(kst(2026, 11, 20), force=True) == 0 and not posts())
    chk("  이름도 안 막는다 (막을 이름이 없다)", TP.reserved_name(NAME) is False)
    os.makedirs(config.ARCHE_DIR, exist_ok=True)
    with open(os.path.join(config.ARCHE_DIR, "secrets.json"), "w") as f:
        f.write("{깨진")
    TP.reset()
    chk("깨진 파일도 안 깨진다", TP.ensure(kst(2026, 11, 20), force=True) == 0)

    print("=== 때가 된 나그네 글만 ===")
    write_secrets(SECRETS)
    TP.reset()
    chk("때가 되기 전에는 하나도 안 올라간다", TP.ensure(kst(2026, 11, 13, 20, 59), force=True) == 0 and not posts())
    n = TP.ensure(kst(2026, 11, 13, 21, 0), force=True)
    refs = [p["ref"] for p in posts()]
    chk("21시가 되면 첫 글 (시간대 없는 12:30 은 UTC = 21:30 이라 아직)", refs == ["arche:pre1"] and n == 1, refs)
    p = posts()[0]
    chk("  나그네 이름으로 · 자유 글", p["author"] == NAME and p["kind"] == "free" and p["body"] == "나그네 첫 글"
        and p["title"] == "첫 글", dict(p))
    u = db.q1("SELECT * FROM users WHERE username=?", (NAME,))
    chk("  나그네 계정이 생겼다", u is not None and p["user_id"] == u["id"])
    chk("  그 계정으로는 로그인할 수 없다", not auth.verify_password("0000", u["pw_hash"], u["pw_salt"], u["pw_iter"])
        and not auth.verify_password("", u["pw_hash"], u["pw_salt"], u["pw_iter"]))
    chk("두 번 불러도 한 번만", TP.ensure(kst(2026, 11, 13, 21, 5), force=True) == 0 and len(posts()) == 1)
    TP.ensure(kst(2026, 11, 13, 21, 31), force=True)
    chk("21:31 에는 시간대 없는 글도 (UTC 12:30 = 21:30)", [x["ref"] for x in posts()] == ["arche:pre1", "arche:naive"],
        [x["ref"] for x in posts()])
    TP.ensure(kst(2026, 12, 1), force=True)
    refs = [x["ref"] for x in posts()]
    chk("때가 지나면 남은 나그네 글도", refs == ["arche:pre1", "arche:naive", "arche:pre2"], refs)
    chk("  고고학자(npc) 글은 안 올린다 (2.5.0)", "arche:end" not in refs)
    chk("  ref 가 틀린 글 · 빈 글은 안 올린다", "pre-x" not in refs and "arche:empty" not in refs)
    chk("  고고학자 계정은 만들지 않는다", db.q1("SELECT 1 x FROM users WHERE username=?", (NPC,)) is None)
    db.run("UPDATE board_post SET deleted=1 WHERE ref='arche:pre1'")       # 게시판의 지우기는 표시만 한다
    TP.ensure(kst(2026, 12, 1), force=True)
    chk("지운 글은 다시 안 올린다 (ref 로 한 번)", [x["ref"] for x in posts()].count("arche:pre1") == 1
        and len(posts()) == 3, [(x["ref"], x["deleted"]) for x in posts()])

    print("=== 이름 막기 ===")
    for name, why in ((NAME, "나그네 이름"), ("떠도는 나그네", "빈칸 넣은 나그네 이름"), (NPC, "고고학자 이름"),
                      ("아르케고고학자", "'고고학자' 가 든 이름")):
        clean, err = auth.check_username(name)
        chk("가입 · 닉네임 바꾸기에서 막는다: %s" % why, clean is None and "쓸 수 없습니다" in (err or ""), (clean, err))
    clean, err = auth.check_username("평범한트레이너")
    chk("  보통 이름은 그대로", clean == "평범한트레이너" and err is None, (clean, err))

    print("=== 진짜 사람이 그 이름을 쓰고 있으면 ===")
    db.run("DELETE FROM board_post")
    db.run("DELETE FROM users WHERE username=?", (NAME,))
    mkuser(NAME, pw=b"real-hash")
    TP.reset()
    chk("올리지 않는다 (남의 이름으로 글을 쓰지 않는다)", TP.ensure(kst(2026, 12, 1), force=True) == 0 and not posts())

    print("=== 게시판 목록에서 ===")
    db.run("DELETE FROM users WHERE username=?", (NAME,))
    reader = mkuser("게시판독자")
    TP.reset()
    real_now = TP._now
    TP._now = lambda now=None: (now or kst(2026, 11, 14, 22, 1)).astimezone(UTC).replace(microsecond=0)
    try:
        out = board_routes.listing(kind="all", page=1, q="", ctx={"user": dict(db.q1(
            "SELECT * FROM users WHERE id=?", (reader,)))})
        refs = sorted(x["ref"] for x in posts())
        chk("게시판을 열면 때가 된 글이 먼저 올라간다", refs == ["arche:naive", "arche:pre1", "arche:pre2"], refs)
        titles = json.dumps(out, ensure_ascii=False)
        chk("  그 목록에 바로 보인다", "첫 글" in titles and "둘째 글" in titles, titles[:200])
        db.run("DELETE FROM board_post")
        board_routes.listing(kind="all", page=1, q="", ctx={"user": dict(db.q1(
            "SELECT * FROM users WHERE id=?", (reader,)))})
        chk("  30초 안에 다시 열면 다시 안 본다", not posts())
    finally:
        TP._now = real_now

    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
