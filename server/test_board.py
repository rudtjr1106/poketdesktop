# -*- coding: utf-8 -*-
"""게시판 검사 (1.8.0, 1.9.0 에서 좋아요·찾기·알림·패치노트).

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


def t_190(op, a, b):
    """1.9.0: 좋아요, 찾기, 알림, 패치노트."""
    c = mkuser("씨")
    base = 100000

    print("\n=== 좋아요 ===")
    p1 = board.create(a, "free", "좋아요 받을 글", "토게키스 불새 배웠다", now=at(base))
    p2 = board.create(b, "qna", "질문 있어요", "로토무 폼은 어떻게 바꾸나요?", now=at(base + 40))
    chk("누르면 켜진다", board.like(b, p1) is True)
    chk("다른 사람도 누른다", board.like(c, p1) is True)
    d = board.detail(b, p1, now=at(base + 50))
    chk("글에 수와 내가 눌렀는지가 실린다", d["likes"] == 2 and d["liked"] is True, (d["likes"], d["liked"]))
    chk("안 누른 사람에게는 꺼져 있다", board.detail(a, p1)["liked"] is False)
    row = [x for x in board.listing(a, "free", 1)["posts"] if x["id"] == p1][0]
    chk("목록에도 수가 실린다", row["likes"] == 2 and row["liked"] is False, row)
    chk("다시 누르면 취소된다", board.like(b, p1) is False and board.detail(b, p1)["likes"] == 1)
    chk("내 글에도 누를 수 있다", board.like(a, p1) is True and board.detail(a, p1)["likes"] == 2)
    chk("없는 글은 404", raises(LookupError, board.like, a, 999999))
    r = board_routes.like(p2, ctx={"user": a})
    chk("라우트는 글 전체를 돌려준다", r["id"] == p2 and r["likes"] == 1 and r["liked"] is True)

    print("\n=== 찾기 ===")
    lst = board.listing(a, "all", 1, q="토게키스")
    chk("내용으로 찾는다", [x["id"] for x in lst["posts"]] == [p1] and lst["q"] == "토게키스", lst["posts"])
    chk("찾을 때는 맨 위 공지를 안 붙인다", lst["pinned"] == [])
    chk("제목으로 찾는다", [x["id"] for x in board.listing(a, "all", 1, q="질문")["posts"]] == [p2])
    chk("쓴 사람으로 찾는다", p2 in [x["id"] for x in board.listing(a, "all", 1, q=b["username"])["posts"]])
    chk("칸 안에서만 찾는다", board.listing(a, "free", 1, q="질문")["posts"] == []
        and [x["id"] for x in board.listing(a, "qna", 1, q="질문")["posts"]] == [p2])
    n1 = board.create(op, "notice", "점검 안내", "토게키스 관련 수정", now=at(base + 80))
    chk("'전체' 에서 찾으면 공지도 나온다",
        set(x["id"] for x in board.listing(a, "all", 1, q="토게키스")["posts"]) == {p1, n1})
    chk("없는 말은 0개", board.listing(a, "all", 1, q="없는말없는말")["total"] == 0)
    board.create(c, "free", "100% 확률", "under_score 글", now=at(base + 120))
    chk("% 와 _ 는 글자 그대로 찾는다",
        board.listing(a, "all", 1, q="%")["total"] == 1 and board.listing(a, "all", 1, q="r_s")["total"] == 1
        and board.listing(a, "all", 1, q="rXs")["total"] == 0)
    chk("지운 글은 안 나온다", (board.remove(op, n1), board.listing(a, "all", 1, q="점검")["total"])[1] == 0)
    chk("빈 말이면 평소 목록", board.listing(a, "all", 1, q="   ")["q"] == "")
    chk("라우트가 q 를 받는다", board_routes.listing("all", 1, "질문", ctx={"user": a})["total"] == 1)

    print("\n=== 알림 ===")
    db.run("DELETE FROM board_notify")
    c1 = board.comment(b, p1, "댓글입니다", now=at(base + 200))
    card = board.me_card(a["id"])
    chk("내 글에 댓글이 달리면 알림이 온다",
        card["notify"]["count"] == 1 and card["notify"]["items"][0]["kind"] == "comment"
        and card["notify"]["items"][0]["actor"] == b["username"]
        and card["notify"]["items"][0]["postId"] == p1, card["notify"])
    chk("댓글 쓴 사람에게는 안 온다", board.me_card(b["id"])["notify"]["count"] == 0)
    board.comment(a, p1, "내가 내 글에", now=at(base + 210))
    chk("내가 내 글에 단 댓글은 알리지 않는다", board.me_card(a["id"])["notify"]["count"] == 1)
    r1 = board.comment(c, p1, "답글입니다", parent=c1, now=at(base + 220))
    nb = board.me_card(b["id"])["notify"]
    chk("내 댓글에 답글이 달리면 알림이 온다",
        nb["count"] == 1 and nb["items"][0]["kind"] == "reply" and nb["items"][0]["actor"] == c["username"], nb)
    chk("글쓴이에게도 댓글 알림이 온다", board.me_card(a["id"])["notify"]["count"] == 2)
    board.comment(b, p1, "답글의 답글", parent=r1, now=at(base + 230))
    nc = board.me_card(c["id"])["notify"]
    chk("답글에 단 답글은 그 답글을 쓴 사람에게 간다", nc["count"] == 1 and nc["items"][0]["kind"] == "reply", nc)
    board.comment(c, p1, "글쓴이 댓글에 답글", parent=db.q1(
        "SELECT id FROM board_comment WHERE body='내가 내 글에'")["id"], now=at(base + 240))
    na = board.me_card(a["id"])["notify"]
    chk("내 글의 내 댓글에 답글이 달리면 한 줄만 온다 (답글)",
        na["count"] == 4 and na["items"][0]["kind"] == "reply", na)
    chk("글 제목과 댓글 앞부분이 실린다",
        na["items"][0]["title"] == "좋아요 받을 글" and na["items"][0]["snippet"] == "글쓴이 댓글에 답글", na["items"][0])
    chk("목록 API", board.notifications(a["id"])["unseen"] == 4
        and len(board.notifications(a["id"])["items"]) == 4)
    board.detail(a, p1)
    chk("그 글을 열면 그 알림은 없어진다 (본 알림은 남기지 않는다)",
        board.me_card(a["id"])["notify"]["count"] == 0
        and board.notifications(a["id"])["items"] == []
        and db.q1("SELECT COUNT(*) c FROM board_notify WHERE user_id=?", (a["id"],))["c"] == 0)
    chk("남의 알림은 그대로다", board.me_card(b["id"])["notify"]["count"] == 1)
    board.notify_seen(b["id"])
    chk("다 본 것으로 할 수 있다 ('모두 읽음' = 다 지운다)", board.me_card(b["id"])["notify"]["count"] == 0
        and board.notifications(b["id"])["items"] == [])
    c9 = board.comment(b, p1, "지울 댓글", now=at(base + 300))
    chk("댓글 알림이 왔다", board.me_card(a["id"])["notify"]["count"] == 1)
    board.remove_comment(b, c9)
    chk("댓글을 지우면 알림도 사라진다", board.me_card(a["id"])["notify"]["count"] == 0)
    r = board_routes.notifications(ctx={"user": a})
    chk("알림 라우트", r["unseen"] == 0 and r["items"] == [])
    chk("알림 지우기 라우트", board_routes.notify_seen(ctx={"user": a})["unseen"] == 0)

    print("\n=== 내 활동 ===")
    m = board.mine(a["id"])
    chk("수: 내 글·댓글·받은 좋아요·알림", m["postCount"] >= 1 and m["commentCount"] >= 1
        and m["likes"] == 2 and m["notifyCount"] == 0 and m["unseen"] == 0, m)
    pg = board.mine_page(a["id"], "posts", 1, now=at(base + 400))
    chk("내 글 한 쪽", pg["what"] == "posts" and p1 in [x["id"] for x in pg["items"]]
        and pg["total"] == m["postCount"] and pg["size"] == board.MINE_PAGE, pg)
    row = [x for x in pg["items"] if x["id"] == p1][0]
    chk("  글마다 좋아요·댓글 수와 누르면 갈 글 번호", row["likes"] == 2 and row["comments"] >= 1
        and row["postId"] == p1, row)
    pg = board.mine_page(a["id"], "comments", 1, now=at(base + 400))
    chk("내 댓글 한 쪽 (어느 글에 달았는지와 함께)", pg["total"] == m["commentCount"]
        and pg["items"][0]["title"] == "좋아요 받을 글" and pg["items"][0]["postId"] == p1, pg["items"][:1])
    pg = board.mine_page(a["id"], "notify", 1, now=at(base + 400))
    chk("알림 한 쪽 - 본 알림은 없다", pg["total"] == 0 and pg["items"] == [] and pg["pages"] == 1, pg)
    chk("모르는 종류는 내 글로", board.mine_page(a["id"], "zzz", 1)["what"] == "posts")

    # 활동이 쌓여도 한 쪽은 다섯 개다 (마이페이지가 길어지지 않는다)
    d = mkuser("다작")
    made = [board.create(d, "free", "글 %02d" % i, "내용", now=at(base + 1000 + i * 40)) for i in range(12)]
    for i in range(7):
        board.comment(a, made[0], "남이 단 댓글 %d" % i, now=at(base + 2000 + i * 10))
    p1_ = board.mine_page(d["id"], "posts", 1)
    p3_ = board.mine_page(d["id"], "posts", 3)
    chk("한 쪽은 다섯 개, 12개면 세 쪽", len(p1_["items"]) == 5 and p1_["pages"] == 3 and p1_["total"] == 12
        and [x["title"] for x in p1_["items"]][:2] == ["글 11", "글 10"], p1_)
    chk("마지막 쪽에는 남은 것만", [x["title"] for x in p3_["items"]] == ["글 01", "글 00"], p3_["items"])
    chk("없는 쪽을 달라면 마지막 쪽", board.mine_page(d["id"], "posts", 99)["page"] == 3
        and board.mine_page(d["id"], "posts", 0)["page"] == 1)
    n1 = board.mine_page(d["id"], "notify", 1)
    n2 = board.mine_page(d["id"], "notify", 2)
    chk("알림도 쪽으로: 7개면 두 쪽, 최근 것부터", n1["pages"] == 2 and len(n1["items"]) == 5
        and len(n2["items"]) == 2 and n1["items"][0]["snippet"] == "남이 단 댓글 6"
        and n1["counts"]["unseen"] == 7, (n1["pages"], n1["items"][:1]))
    board.detail(d, made[0])
    n1 = board.mine_page(d["id"], "notify", 1)
    chk("그 글을 열면 알림 쪽에서도 사라진다", n1["total"] == 0 and n1["items"] == []
        and n1["counts"]["unseen"] == 0, n1)
    chk("라우트: /api/board/mine", board_routes.mine("COMMENTS", 1, ctx={"user": a})["what"] == "comments")

    print("\n=== 패치노트 ===")
    from common import patchnotes
    made = board.ensure_patch_posts(now=at(base + 500))
    chk("버전마다 글 하나", len(made) == len(patchnotes.NOTES) and made[0] == patchnotes.NOTES[-1]["version"]
        and made[-1] == patchnotes.NOTES[0]["version"], (len(made), made[:2], made[-2:]))
    chk("두 번 부르면 아무것도 안 올린다", board.ensure_patch_posts(now=at(base + 600)) == [])
    lst = board.listing(a, "patch", 1)
    top = lst["posts"][0]
    chk("패치노트 칸에 최신 버전이 맨 위", lst["total"] == len(patchnotes.NOTES)
        and top["title"] == "v%s 업데이트" % patchnotes.NOTES[0]["version"]
        and top["kindKr"] == "패치노트", top)
    chk("운영자 이름으로 올라간다", top["author"] == op["username"] and top["authorAdmin"] is True)
    d = board.detail(a, top["id"])
    chk("내용은 요약과 항목들", patchnotes.NOTES[0]["headline"] in d["body"] and "■ " in d["body"])
    old = lst["posts"][1]
    ver = old["title"].split()[0].lstrip("v")
    chk("옛 버전은 나온 날짜로", old["createdAt"] == patchnotes.RELEASED[ver], (ver, old["createdAt"]))
    chk("'전체' 에는 안 흐른다", all(x["kind"] != "patch" for x in board.listing(a, "all", 1)["posts"]))
    chk("사람은 패치노트를 못 쓴다 (운영자도)", raises(PermissionError, board.create, op, "patch", "t", "b"))
    chk("고치거나 지울 수 없다", raises(PermissionError, board.edit, op, top["id"], "t", "b")
        and raises(PermissionError, board.remove, op, top["id"]) and d["canEdit"] is False
        and board.detail(op, top["id"])["canDelete"] is False)
    board.comment(b, top["id"], "잘 봤습니다", now=at(base + 700))
    board.like(b, top["id"])
    d = board.detail(a, top["id"])
    chk("댓글과 좋아요는 달 수 있다", d["comments"] == 1 and d["likes"] == 1)
    chk("패치노트의 댓글은 운영자에게 알리지 않는다", board.me_card(op["id"])["notify"]["count"] == 0)
    card = board.me_card(a["id"])
    chk("/api/me 에 최신 패치노트 번호", card["patch"] == top["id"] and card["notice"] > 0, card)
    chk("내 글 목록에 패치노트는 안 섞인다",
        all(x["kind"] != "patch" for x in board.mine_page(op["id"], "posts", 1)["items"])
        and board.mine(op["id"])["postCount"] == board.mine_page(op["id"], "posts", 1)["total"])
    chk("upto 로 끊어 올릴 수 있다 (새 판이 나오면 그 글만 생긴다)",
        (db.run("DELETE FROM board_post WHERE ref=?", ("patch:" + patchnotes.NOTES[0]["version"],)),
         board.ensure_patch_posts(now=at(base + 800)))[1] == [patchnotes.NOTES[0]["version"]])


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
    chk("글자 수 한도를 같이 준다", lst["limits"] == {"title": 40, "body": 2000, "comment": 300,
                                                 "search": 30}, lst["limits"])

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
    chk("/api/me 용: 가장 최근 공지 번호", board.me_card()["notice"] == latest, board.me_card())

    print("\n=== 라우트 ===")
    r = board_routes.create(board_routes.PostIn(kind="FREE", title="라우트 글", body="내용"), ctx={"user": fake})
    chk("쓰면 그 글을 돌려준다 (종류는 대소문자 무관)", r["title"] == "라우트 글" and r["kind"] == "free")
    # 앞에서 댓글을 단 적이 없는 사람으로 (앞의 댓글들은 꾸민 시각이라 도배 판정에 걸린다)
    r = board_routes.comment(r["id"], board_routes.CommentIn(body="댓글"), ctx={"user": fake})
    chk("댓글을 달면 글 전체를 돌려준다", len(r["commentList"]) == 1 and r["comments"] == 1)
    chk("목록 라우트", board_routes.listing("all", 1, ctx={"user": a})["total"] >= 1)

    t_190(op, a, b)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
