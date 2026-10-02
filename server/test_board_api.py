# -*- coding: utf-8 -*-
"""게시판 API 검사. 서버를 띄워 놓고 돌린다 (1.8.0, 1.9.0 에서 좋아요·찾기·알림·마이페이지).

    python server/test_board_api.py http://127.0.0.1:8788

단위 검사(test_board.py)가 규칙을 본다. 여기서는 **HTTP 로 실제로 오가는지**만
본다 - 경로 순서(comments/{id} 가 {id} 보다 먼저), 상태 코드, 한글 본문.
운영자 닉네임('나여조경석')은 이 검사용 서버에 아직 없을 때만 새로 만든다.
"""
import json
import random
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788").rstrip("/")
OK = FAIL = 0
ADMIN = "나여조경석"


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


def login_or_register(name):
    st, r = call("POST", "/api/auth/register",
                 {"username": name, "password": "1234", "starter": "PIKACHU", "device": "t"})
    if st != 200:
        st, r = call("POST", "/api/auth/login",
                     {"username": name, "password": "1234", "device": "t"})
    if st != 200:
        raise SystemExit("로그인 실패 %s %s %s" % (name, st, r))
    return r.get("token") or r["session"]["token"]


def main():
    tag = random.randint(1000, 9999)
    op = login_or_register(ADMIN)
    a = login_or_register("게시%d" % tag)
    b = login_or_register("댓글%d" % tag)

    st, r = call("GET", "/api/board")
    chk("로그인 없이는 못 본다 (401)", st == 401, st)
    st, r = call("POST", "/api/board", {"kind": "notice", "title": "가짜 공지", "body": "x"}, a)
    chk("남이 공지를 쓰면 403", st == 403 and "운영자" in r.get("error", ""), (st, r))
    st, n = call("POST", "/api/board", {"kind": "notice", "title": "공지 %d" % tag,
                                        "body": "한글 본문\n둘째 줄"}, op)
    chk("운영자는 공지를 쓴다", st == 200 and n["kind"] == "notice" and n["authorAdmin"]
        and n["body"] == "한글 본문\n둘째 줄", (st, n))
    st, p = call("POST", "/api/board", {"kind": "free", "title": "자유 %d" % tag, "body": "내용"}, a)
    chk("자유 글", st == 200 and p["author"] == "게시%d" % tag and p["mine"], (st, p))
    pid = p["id"]
    st, r = call("POST", "/api/board", {"kind": "free", "title": "또", "body": "x"}, a)
    chk("바로 또 쓰면 403 (30초)", st == 403 and "30초" in r.get("error", ""), (st, r))
    st, r = call("POST", "/api/board", {"kind": "free", "title": "", "body": "x"}, b)
    chk("빈 제목은 400", st == 400, (st, r))

    st, lst = call("GET", "/api/board?kind=all&page=1", token=b)
    chk("목록: 공지가 붙박이로, 자유 글이 아래에", st == 200
        and any(x["id"] == n["id"] for x in lst["pinned"])
        and any(x["id"] == pid for x in lst["posts"]) and lst["canNotice"] is False, (st, lst.keys()))
    st, r = call("GET", "/api/me", token=b)
    chk("/api/me 에 가장 최근 공지 번호", st == 200 and (r.get("board") or {}).get("notice", 0) >= n["id"],
        r.get("board"))

    st, d = call("POST", "/api/board/%d/comments" % pid, {"body": "첫 댓글"}, b)
    chk("댓글", st == 200 and d["commentList"][0]["author"] == "댓글%d" % tag, (st, d))
    cid = d["commentList"][0]["id"]
    st, d = call("POST", "/api/board/%d/comments" % pid, {"body": "답글", "parent": cid}, a)
    chk("답글", st == 200 and d["commentList"][0]["replies"][0]["body"] == "답글", (st, d))
    # ---- 1.9.0: 좋아요, 찾기(한글 q), 알림, 마이페이지 - 경로와 상태 코드
    from urllib.parse import quote
    st, r = call("GET", "/api/board/notify", token=a)
    # 글쓴이(a)는 방금 답글을 달며 그 글을 열어 봤다 - 본 알림은 없어진다
    chk("알림 목록 (경로가 글 번호로 안 읽힌다). 본 알림은 없다", st == 200
        and r["items"] == [] and r["unseen"] == 0, (st, r))
    st, r = call("GET", "/api/board/notify", token=b)
    chk("답글 알림은 댓글을 쓴 사람에게", st == 200
        and any(x["postId"] == pid and x["kind"] == "reply" for x in r["items"])
        and r["unseen"] >= 1, (st, r))
    st, r = call("GET", "/api/me", token=b)
    chk("/api/me 에 안 본 알림이 실린다", st == 200
        and ((r.get("board") or {}).get("notify") or {}).get("count", 0) >= 1, r.get("board"))
    st, r = call("POST", "/api/board/notify/seen", {}, b)
    chk("알림을 다 본 것으로 (다 지운다)", st == 200 and r["unseen"] == 0 and r["items"] == [], (st, r))
    # (좋아요는 글 전체를 돌려준다 = 글을 연 것이라, 알림 검사 뒤에 한다)
    st, d = call("POST", "/api/board/%d/like" % pid, {}, b)
    chk("좋아요", st == 200 and d["likes"] == 1 and d["liked"] is True, (st, d.get("likes")))
    st, lst = call("GET", "/api/board?kind=all&page=1&q=" + quote("자유 %d" % tag), token=b)
    chk("찾기: 한글로 찾는다", st == 200 and [x["id"] for x in lst["posts"]] == [pid]
        and lst["pinned"] == [] and lst["posts"][0]["likes"] == 1, (st, lst.get("posts")))
    st, r = call("POST", "/api/board", {"kind": "patch", "title": "가짜 패치노트", "body": "x"}, op)
    chk("패치노트는 사람이 못 쓴다 (운영자도 403)", st == 403, (st, r))
    st, r = call("GET", "/api/board?kind=patch", token=b)
    chk("패치노트 칸", st == 200 and r["kind"] == "patch", (st, r.get("kind")))
    st, r = call("GET", "/api/mypage", token=a)
    chk("마이페이지", st == 200 and r["user"]["name"] == "게시%d" % tag
        and r["board"]["postCount"] >= 1 and "seasons" in r and "gym" in r,
        (st, list(r.keys()) if isinstance(r, dict) else r))
    st, r = call("GET", "/api/mypage")
    chk("마이페이지도 로그인 없이는 못 본다 (401)", st == 401, st)
    st, r = call("GET", "/api/board/mine?what=posts&page=1", token=a)
    chk("내 활동 한 쪽 (경로가 글 번호로 안 읽힌다)", st == 200 and r["what"] == "posts"
        and any(x["id"] == pid for x in r["items"]) and r["size"] == 5, (st, r))
    st, r = call("GET", "/api/board/mine?what=notify&page=9", token=a)
    chk("없는 쪽을 달라면 마지막 쪽", st == 200 and r["what"] == "notify" and r["page"] == r["pages"], (st, r))

    st, r = call("DELETE", "/api/board/comments/%d" % cid, token=a)
    chk("남의 댓글은 못 지운다 (403)", st == 403, (st, r))
    st, d = call("DELETE", "/api/board/comments/%d" % cid, token=b)
    chk("내 댓글을 지우면 자리만 남는다 (경로가 글 번호로 안 읽힌다)", st == 200
        and d["commentList"][0]["deleted"] and len(d["commentList"][0]["replies"]) == 1, (st, d))
    st, d = call("PUT", "/api/board/%d" % pid, {"title": "고친 제목", "body": "고친 내용"}, a)
    chk("내 글 고치기", st == 200 and d["title"] == "고친 제목" and d["edited"], (st, d))
    st, r = call("PUT", "/api/board/%d" % pid, {"title": "x", "body": "y"}, b)
    chk("남의 글은 못 고친다 (403)", st == 403, (st, r))
    st, r = call("DELETE", "/api/board/%d" % pid, token=op)
    chk("운영자는 남의 글을 지운다", st == 200, (st, r))
    st, r = call("GET", "/api/board/%d" % pid, token=a)
    chk("지운 글은 404", st == 404, (st, r))
    call("DELETE", "/api/board/%d" % n["id"], token=op)     # 검사용 공지를 치운다

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
