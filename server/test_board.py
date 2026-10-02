# -*- coding: utf-8 -*-
"""게시판 검사 (1.8.0).

    python server/test_board.py

  1. 공지는 운영자(닉네임 '나여조경석')만 쓴다. 남이 쓰면 403.
  2. 자유 글은 누구나. 제목·내용이 비었거나 길면 400.
  3. '전체' 목록은 최근 공지 셋을 맨 위에 붙이고 자유 글을 쪽으로 넘긴다.
  4. 댓글과 답글 한 단계. 답글에 단 답글은 같은 댓글 아래로.
  5. 글·댓글에 **누가 썼는지**(이름·운영자 표시·칭호)가 실린다.
  6. 지우기는 쓴 사람과 운영자. 답글이 달린 댓글은 자리를 남긴다.
  7. 도배: 글 30초·댓글 5초에 하나.
  8. /api/me 에 가장 최근 공지 번호.
"""
import datetime
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-board-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ.pop("POKET_BOARD_ADMINS", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                            # noqa: E402

from app import board, board_routes, db, season              # noqa: E402

OK = FAIL = 0
T0 = datetime.datetime(2026, 10, 2, 3, 0, 0, tzinfo=datetime.timezone.utc)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def at(sec):
    return T0 + datetime.timedelta(seconds=sec)


def mkuser(name):
    cur = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                 " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')",
                 (name, b"x", b"x"))
    return {"id": cur.lastrowid, "username": name}


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc as e:
        return str(e) or True
    except Exception as e:                                   # noqa: BLE001
        return False if not isinstance(e, exc) else True
    return False


def status(fn, *a, **kw):
    try:
        fn(*a, **kw)
        return 200
    except HTTPException as e:
        return e.status_code


def main():
    db.init()
    op = mkuser("나여조경석")
    a = mkuser("지우")
    b = mkuser("이슬")
    fake = mkuser("나여조경석2")

    print("=== 공지는 운영자만 ===")
    chk("운영자 판정", board.is_admin(op) and not board.is_admin(a) and not board.is_admin(fake))
    n1 = board.create(op, "notice", "시즌 3 안내", "메가진화가 열렸습니다.", now=at(0))
    chk("운영자는 공지를 쓴다", n1 > 0)
    chk("남이 공지를 쓰면 막는다", raises(PermissionError, board.create, a, "notice", "가짜 공지", "x"))
    chk("  비슷한 이름도 막는다", raises(PermissionError, board.create, fake, "notice", "가짜", "x"))
    chk("  HTTP 로는 403", status(board_routes.create, board_routes.PostIn(
        kind="notice", title="가짜", body="x"), ctx={"user": a}) == 403)

    print("\n=== 자유 글 ===")
    f1 = board.create(a, "free", "  첫   글  ", "안녕하세요\r\n\r\n\r\n\r\n\r\n반갑습니다  ", now=at(10))
    p = board.detail(a, f1, now=at(20))
    chk("제목은 한 줄로 다듬는다", p["title"] == "첫 글", repr(p["title"]))
    chk("빈 줄은 두 줄까지만", p["body"] == "안녕하세요\n\n\n반갑습니다", repr(p["body"]))
    chk("작성자가 실린다", p["author"] == "지우" and p["authorId"] == a["id"]
        and p["authorAdmin"] is False and p["mine"] is True, p)
    chk("몇 초 전인지는 서버가 센다", p["agoSec"] == 10, p["agoSec"])
    chk("빈 제목은 400", raises(ValueError, board.create, b, "free", "   ", "내용"))
    chk("빈 내용은 400", raises(ValueError, board.create, b, "free", "제목", " \n "))
    chk("긴 제목은 400", raises(ValueError, board.create, b, "free", "가" * 41, "내용"))
    chk("긴 내용은 400", raises(ValueError, board.create, b, "free", "제목", "가" * 2001))
    chk("모르는 종류는 400", raises(ValueError, board.create, b, "ad", "제목", "내용"))
    chk("없는 글은 404", status(board_routes.detail, 99999, ctx={"user": a}) == 404)

    print("\n=== 도배 ===")
    chk("30초 안에 또 쓰면 막는다", raises(PermissionError, board.create, a, "free", "둘째", "x", now=at(25)))
    f2 = board.create(a, "free", "둘째 글", "x", now=at(45))
    chk("30초 뒤에는 된다", f2 > f1)
    chk("운영자는 안 막는다", board.create(op, "notice", "공지 2", "x", now=at(1)) > 0)

    print("\n=== 목록 ===")
    for i in range(3, 6):
        board.create(op, "notice", "공지 %d" % i, "x", now=at(i))
    for i in range(20):
        board.create(b, "free", "이슬의 글 %02d" % i, "x", now=at(100 + i * 40))
    lst = board.listing(a, "all", 1, now=at(2000))
    chk("전체: 최근 공지 셋이 맨 위", [x["title"] for x in lst["pinned"]] == ["공지 5", "공지 4", "공지 3"],
        [x["title"] for x in lst["pinned"]])
    chk("  그 아래 자유 글 15개 (최신부터)", len(lst["posts"]) == 15
        and lst["posts"][0]["title"] == "이슬의 글 19" and all(x["kind"] == "free" for x in lst["posts"]),
        [x["title"] for x in lst["posts"]][:3])
    chk("  쪽 수", (lst["page"], lst["pages"], lst["total"]) == (1, 2, 22), (lst["page"], lst["pages"], lst["total"]))
    lst2 = board.listing(a, "all", 2, now=at(2000))
    chk("  둘째 쪽에 나머지 7개 + 공지는 그대로", len(lst2["posts"]) == 7 and len(lst2["pinned"]) == 3)
    chk("  쪽 번호가 넘치면 마지막 쪽", board.listing(a, "all", 99)["page"] == 2)

    print("\n=== Q&A (1.8.1) ===")
    n_all = board.listing(a, "all", 1, now=at(2000))["total"]
    n_free = board.listing(a, "free", 1, now=at(2000))["total"]
    # (이슬은 위에서 하루치 스무 개를 다 썼다 - 지우가 묻는다)
    q1 = board.create(a, "qna", "키스톤은 어디서 얻나요", "관장 8곳이라던데", now=at(2100))
    q = board.detail(b, q1, now=at(2101))
    chk("누구나 Q&A 를 쓴다", q["kind"] == "qna" and q["kindKr"] == "Q&A", (q["kind"], q["kindKr"]))
    lq = board.listing(a, "qna", 1, now=at(2200))
    chk("Q&A 목록에는 질문만", [x["id"] for x in lq["posts"]] == [q1] and lq["total"] == 1
        and lq["pinned"] == [], (lq["total"], [x["id"] for x in lq["posts"]]))
    chk("자유 목록에는 안 나온다", board.listing(a, "free", 1, now=at(2200))["total"] == n_free)
    la = board.listing(a, "all", 1, now=at(2200))
    chk("전체에는 자유 글과 함께 흐른다 (최신이 맨 위)", la["total"] == n_all + 1
        and la["posts"][0]["id"] == q1 and all(x["kind"] != "notice" for x in la["posts"]),
        (la["total"], n_all, la["posts"][0]["id"]))
    chk("  공지는 여전히 맨 위에 따로", len(la["pinned"]) == 3 and all(x["kind"] == "notice"
                                                         for x in la["pinned"]))
    c1 = board.comment(b, q1, "관장 8곳을 깨면 받아요", now=at(2300))
    chk("Q&A 에도 댓글·답글이 달린다", board.detail(a, q1, now=at(2301))["comments"] == 1 and c1)
    board.remove(a, q1)
    chk("지우면 목록에서 빠진다", board.listing(a, "qna", 1, now=at(2400))["total"] == 0
        and board.listing(a, "all", 1, now=at(2400))["total"] == n_all)
    try:
        board.create(b, "잡담", "x", "y", now=at(2500))
        chk("모르는 종류는 거절", False)
    except ValueError:
        chk("모르는 종류는 거절", True)
    ln = board.listing(a, "notice", 1)
    chk("공지만: 다섯 개, 붙박이는 없다", len(ln["posts"]) == 5 and ln["pinned"] == []
        and all(x["kind"] == "notice" for x in ln["posts"]))
    chk("공지 글쓴이에 운영자 표시", all(x["authorAdmin"] for x in ln["posts"]))
    chk("운영자만 공지를 쓸 수 있다고 알려 준다",
        board.listing(op)["canNotice"] is True and lst["canNotice"] is False)
    chk("글자 수 한도를 같이 준다", lst["limits"] == {"title": 40, "body": 2000, "comment": 300})

    print("\n=== 댓글과 답글 ===")
    c1 = board.comment(b, f1, "첫 댓글", now=at(3000))
    c2 = board.comment(a, f1, "답글입니다", parent=c1, now=at(3010))
    c3 = board.comment(op, f1, "답글의 답글", parent=c2, now=at(3020))
    c4 = board.comment(a, f1, "둘째 댓글", now=at(3030))
    p = board.detail(b, f1, now=at(3100))
    cl = p["commentList"]
    chk("댓글 둘, 첫 댓글에 답글 둘", [c["id"] for c in cl] == [c1, c4]
        and [r["id"] for r in cl[0]["replies"]] == [c2, c3], cl)
    chk("답글의 답글은 같은 댓글 아래로 (한 단계)", cl[0]["replies"][1]["body"] == "답글의 답글")
    chk("댓글마다 작성자", cl[0]["author"] == "이슬" and cl[0]["replies"][0]["author"] == "지우"
        and cl[0]["replies"][1]["authorAdmin"] is True, cl[0])
    chk("내 댓글에만 mine", cl[0]["mine"] is True and cl[1]["mine"] is False)
    chk("목록의 댓글 수", [x for x in board.listing(a, "free", 2)["posts"] if x["id"] == f1][0]["comments"] == 4)
    chk("5초 안에 또 달면 막는다", raises(PermissionError, board.comment, a, f1, "또", now=at(3032)))
    chk("빈 댓글은 400", raises(ValueError, board.comment, b, f1, "  "))
    chk("긴 댓글은 400", raises(ValueError, board.comment, b, f1, "가" * 301))
    chk("다른 글의 댓글에는 답글을 못 단다", raises(LookupError, board.comment, b, f2, "x", parent=c1, now=at(3200)))

    print("\n=== 칭호 ===")
    season.grant(a["id"], "title", "s2_super", 2)
    p = board.detail(b, f1, now=at(3300))
    chk("칭호를 단 사람은 칭호가 같이 실린다", p["authorTitle"] == "시즌 2 슈퍼볼", p["authorTitle"])

    print("\n=== 지우기 ===")
    chk("남의 댓글은 못 지운다", raises(PermissionError, board.remove_comment, a, c1))
    board.remove_comment(b, c1)
    cl = board.detail(a, f1, now=at(3400))["commentList"]
    chk("답글이 달린 댓글은 자리를 남긴다 (내용·이름은 가린다)",
        cl[0]["deleted"] and cl[0]["body"] == "" and cl[0]["author"] == "" and len(cl[0]["replies"]) == 2, cl[0])
    board.remove_comment(op, c4)
    cl = board.detail(a, f1, now=at(3400))["commentList"]
    chk("운영자는 남의 댓글을 지운다. 답글 없는 댓글은 사라진다", [c["id"] for c in cl] == [c1], [c["id"] for c in cl])
    chk("이미 지운 댓글은 404", raises(LookupError, board.remove_comment, op, c4))
    chk("남의 글은 못 지운다", raises(PermissionError, board.remove, b, f1))
    chk("남의 글은 못 고친다", raises(PermissionError, board.edit, b, f1, "x", "y"))
    board.edit(a, f1, "고친 제목", "고친 내용", now=at(3500))
    p = board.detail(a, f1)
    chk("내 글은 고친다 (고쳤다는 표시)", p["title"] == "고친 제목" and p["edited"] is True)
    board.remove(a, f2)
    chk("내 글은 지운다 - 목록에서 빠지고 404", status(board_routes.detail, f2, ctx={"user": a}) == 404
        and f2 not in [x["id"] for x in board.listing(a, "free", 1)["posts"]])
    board.remove(op, f1)
    chk("운영자는 남의 글을 지운다", raises(LookupError, board.detail, a, f1))
    chk("지운 글에는 댓글을 못 단다", raises(LookupError, board.comment, b, f1, "x", now=at(9000)))

    print("\n=== 새 공지 알림 ===")
    latest = max(r["id"] for r in db.q("SELECT id FROM board_post WHERE kind='notice' AND deleted=0"))
    chk("/api/me 용: 가장 최근 공지 번호", board.me_card() == {"notice": latest}, board.me_card())

    print("\n=== 라우트 ===")
    r = board_routes.create(board_routes.PostIn(kind="FREE", title="라우트 글", body="내용"), ctx={"user": fake})
    chk("쓰면 그 글을 돌려준다 (종류는 대소문자 무관)", r["title"] == "라우트 글" and r["kind"] == "free")
    # 앞에서 댓글을 단 적이 없는 사람으로 (앞의 댓글들은 꾸민 시각이라 도배 판정에 걸린다)
    r = board_routes.comment(r["id"], board_routes.CommentIn(body="댓글"), ctx={"user": fake})
    chk("댓글을 달면 글 전체를 돌려준다", len(r["commentList"]) == 1 and r["comments"] == 1)
    chk("목록 라우트", board_routes.listing("all", 1, ctx={"user": a})["total"] >= 1)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
